"""Feature 006: the default chat model is Gemini 2.5 Flash with thinking turned off in the OpenRouter request
(reasoning: {"enabled": false}); CARGOLINT_REASONING other than "off" sends no reasoning parameter, as a model without
one needs (OpenRouter's require_parameters refuses it). Feature 008: the precedent override is on by default (T027);
CARGOLINT_HS6_OVERRIDE "off" or "false" turns it off."""
import dataclasses

import pytest

from agent.config import get_settings, load_settings
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


@pytest.fixture
def fresh_settings():
    get_settings.cache_clear()
    yield get_settings
    get_settings.cache_clear()


def test_the_precedent_override_is_on_by_default(monkeypatch, fresh_settings):
    monkeypatch.delenv("CARGOLINT_HS6_OVERRIDE", raising=False)
    assert fresh_settings().hs6_override is True


@pytest.mark.parametrize("value, on", [("on", True), ("true", True), ("off", False), ("false", False), ("False", False)])
def test_off_or_false_turns_the_precedent_override_off(monkeypatch, fresh_settings, value, on):
    monkeypatch.setenv("CARGOLINT_HS6_OVERRIDE", value)
    assert fresh_settings().hs6_override is on
