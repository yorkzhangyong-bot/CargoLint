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
