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
