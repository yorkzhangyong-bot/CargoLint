"""Feature 006: the default chat model is Gemini 2.5 Flash with thinking turned off in the OpenRouter request
(reasoning: {"enabled": false}); CARGOLINT_REASONING other than "off" sends no reasoning parameter, as a model without
one needs (OpenRouter's require_parameters refuses it)."""
import dataclasses

import pytest

from agent.config import load_settings
from agent.llm import get_chat_model

pytestmark = pytest.mark.unit


@pytest.fixture
def built(monkeypatch):
    import langchain_openai

    kwargs: dict = {}
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kw: kwargs.update(kw) or object())
    return kwargs


def test_the_default_is_gemini_with_thinking_off(built):
    settings = dataclasses.replace(load_settings({}), api_key="test-key-not-real")
    assert (settings.chat_model, settings.reasoning_off) == ("google/gemini-2.5-flash", True)
    get_chat_model(settings)
    assert built["model"] == "google/gemini-2.5-flash"
    assert built["extra_body"] == {"provider": {"require_parameters": True}, "reasoning": {"enabled": False}}


def test_a_model_without_the_reasoning_parameter_gets_none(built):
    settings = dataclasses.replace(load_settings({"CARGOLINT_CHAT_MODEL": "openai/gpt-4.1-mini", "CARGOLINT_REASONING": "model"}),
                                   api_key="test-key-not-real")
    assert settings.reasoning_off is False
    get_chat_model(settings)
    assert (built["model"], built["extra_body"]) == ("openai/gpt-4.1-mini", {"provider": {"require_parameters": True}})
