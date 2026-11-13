"""The offline guard of tests/conftest.py: without a fake, a test that is not marked live cannot reach OpenRouter."""
from __future__ import annotations

import dataclasses

import pytest

pytestmark = pytest.mark.unit


def test_the_real_clients_are_refused_without_a_fake():
    from agent.config import load_settings
    from agent.llm import get_chat_model, get_client, set_chat_model_factory, set_client_factory
    from rag.embeddings import get_embeddings

    set_client_factory(None)
    set_chat_model_factory(None)
    settings = dataclasses.replace(load_settings({}), api_key="test-key-not-real")
    for build in (lambda: get_client(settings=settings), lambda: get_chat_model(settings),
                  lambda: get_embeddings(settings)):
        with pytest.raises(RuntimeError, match="offline test"):
            build()


def test_the_release_service_the_download_and_the_network_are_refused_without_a_fake(tmp_path):
    """Feature 013 (spec FR-025): the gh runner, the loader's download and any URL that is not file: are refused."""
    import urllib.request

    import rag.loader
    from rag.refresh import ReleaseService

    with pytest.raises(RuntimeError, match="offline test"):
        ReleaseService().check()
    with pytest.raises(RuntimeError, match="offline test"):
        rag.loader.download("https://example.invalid/DDS2-EBTI_Full.zip", tmp_path / "x.zip")
    with pytest.raises(RuntimeError, match="offline test"):
        urllib.request.urlopen("https://example.invalid/")
    with pytest.raises(RuntimeError, match="offline test"):
        urllib.request.urlopen(urllib.request.Request("http://example.invalid/releases"))
    (tmp_path / "ok.txt").write_text("fine", encoding="utf-8")
    with urllib.request.urlopen((tmp_path / "ok.txt").as_uri()) as response:   # file: URLs still work
        assert response.read() == b"fine"
