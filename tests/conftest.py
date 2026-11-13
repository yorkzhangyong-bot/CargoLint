"""Shared fixtures: fake model client, fake embeddings, in-memory line store, small index, rules."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def pytest_collection_modifyitems(config, items):
    if os.environ.get("OPENROUTER_API_KEY"):
        return
    skip = pytest.mark.skip(reason="OPENROUTER_API_KEY not set")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _offline(request, monkeypatch):
    """Offline tests never reach OpenRouter, the GitHub CLI, a download or the network. OPENROUTER_API_KEY is an
    operating-system variable, so a test that is not marked live and runs without a fake client fails here instead of
    spending credits; a refresh test without a fake service or a download copier fails here instead of acting on the
    maintainer's releases or the EU sources (feature 013, spec FR-025). `urllib.request.urlopen` passes `file:` URLs
    only."""
    if request.node.get_closest_marker("live") is not None:
        return
    import urllib.request

    import langchain_openai

    import agent.llm
    import rag.embeddings
    import rag.loader
    import rag.refresh

    def refuse(*args, **kwargs):
        raise RuntimeError("an offline test tried to reach OpenRouter; install a fake with set_client_factory")

    def refuse_gh(argv):
        raise RuntimeError(f"an offline test tried to run gh {' '.join(argv[:2])}; inject a FakeReleaseService")

    def refuse_download(url, dest, *args, **kwargs):
        raise RuntimeError(f"an offline test tried to download {url}; monkeypatch rag.loader.download")

    real_urlopen = urllib.request.urlopen

    def file_only_urlopen(url, *args, **kwargs):
        target = url.full_url if isinstance(url, urllib.request.Request) else str(url)
        if not target.lower().startswith("file:"):
            raise RuntimeError(f"an offline test tried to open {target}; point the URL templates at file: URLs")
        return real_urlopen(url, *args, **kwargs)

    monkeypatch.setattr(agent.llm, "OpenRouterRawClient", refuse)
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", refuse)
    monkeypatch.setattr(rag.embeddings, "OpenRouterEmbeddings", refuse)
    monkeypatch.setattr(rag.refresh, "_run_gh", refuse_gh)
    monkeypatch.setattr(rag.loader, "download", refuse_download)
    monkeypatch.setattr(urllib.request, "urlopen", file_only_urlopen)


@pytest.fixture
def small_index():
    from rag.nomenclature import NomenclatureIndex

    return NomenclatureIndex.from_jsonl(FIXTURES / "cn2026_excerpt.jsonl")


@pytest.fixture
def rules():
    from rag.rules import RuleSet

    return RuleSet.load(FIXTURES / "rules")


@pytest.fixture
def sample_lines() -> dict:
    return json.loads((ROOT / "data" / "samples" / "sample_lines.json").read_text(encoding="utf-8"))


@pytest.fixture
def labelled_lines() -> list[dict]:
    path = ROOT / "data" / "labelled" / "lines_20.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def adversarial_lines() -> list[dict]:
    path = FIXTURES / "adversarial.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def fake_embeddings():
    from rag.embeddings import FakeEmbeddings

    return FakeEmbeddings(dim=16)


@pytest.fixture
def fake_llm():
    """Injects a FakeRawClient as the structured-output backend for the duration of a test."""
    from agent.llm import set_client_factory
    from tests.fakes import FakeRawClient

    from rag.translate import clear_cache

    clear_cache()
    client = FakeRawClient.from_dir(FIXTURES / "recorded")
    set_client_factory(lambda: client)
    try:
        yield client
    finally:
        set_client_factory(None)


@pytest.fixture
def memory_store(small_index):
    from agent.store import LineStore

    store = LineStore(backend={}, index=small_index)
    store.new_shipment(reference="TEST-001", threshold=85)
    return store
