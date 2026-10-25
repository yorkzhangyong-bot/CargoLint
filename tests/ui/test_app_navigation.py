"""app.py and the two pages' links (feature 005, contracts/ui.md §1): the hidden navigation, "Admin ⚙", "← Back to
shipment", and the missing-key message."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.ui import harness as h

pytestmark = pytest.mark.integration
APP = str(Path(__file__).resolve().parents[2] / "app.py")


@pytest.fixture
def settings(monkeypatch):
    import agent.config as config

    base = config.load_settings({})

    def use(key):
        s = dataclasses.replace(base, api_key=key)
        monkeypatch.setattr(config, "get_settings", lambda: s)
        return s
    return use


def test_app_opens_the_main_page_with_the_admin_link(monkeypatch, settings):
    import rag.loader

    settings("test-key-not-real")
    monkeypatch.setattr(rag.loader, "open_knowledge_base", lambda *a, **k: h.make_kb())
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert [n.proto.label for n in at.get("page_link")] == ["Admin ⚙"]
    assert len(at.sidebar.children) == 0                           # hidden navigation: no page list


def test_without_a_key_the_app_stops_with_the_message(monkeypatch, settings):
    settings(None)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert [e.value for e in at.error] == ["OPENROUTER_API_KEY is not set. Set it as an operating-system environment "
                                           "variable and restart CargoLint."]
    assert ".env" not in at.error[0].value


def test_the_admin_page_links_back(monkeypatch):
    kb = h.make_kb()
    store, _ = h.store_with("ready", kb=kb)
    at = h.app(store, kb, page="admin").run()
    assert not at.exception
    assert [n.proto.label for n in at.get("page_link")] == ["← Back to shipment"]
    at.session_state["_harness_page"] = "main"
    at.run()
    assert [n.proto.label for n in at.get("page_link")] == ["Admin ⚙"]
