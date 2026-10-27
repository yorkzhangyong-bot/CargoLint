"""app.py and the two pages' links (feature 005, contracts/ui.md §1): the hidden navigation, "Admin ⚙", "← Back to
shipment", and the missing-key message. Feature 011: the demo password gate and a demo store that fails its checksum."""
from __future__ import annotations

import dataclasses
import zipfile
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tests.ui import harness as h

pytestmark = pytest.mark.integration
APP = str(Path(__file__).resolve().parents[2] / "app.py")


@pytest.fixture
def settings(monkeypatch):
    import agent.config as config

    base = config.load_settings({})

    def use(key, **changes):
        s = dataclasses.replace(base, api_key=key, **changes)
        monkeypatch.setattr(config, "get_settings", lambda: s)
        return s
    return use


@pytest.fixture
def kb_opened(monkeypatch):
    """Counts the knowledge base openings; load_kb is cached per process, so each test starts with an empty cache."""
    import rag.loader

    calls: list[int] = []

    def open_kb(*args, **kwargs):
        calls.append(1)
        return h.make_kb()

    monkeypatch.setattr(rag.loader, "open_knowledge_base", open_kb)
    st.cache_resource.clear()
    return calls


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
                                           "variable and restart CargoLint; on Streamlit Community Cloud, add it to the "
                                           "app's Secrets settings and reboot the app."]
    assert ".env" not in at.error[0].value


def test_without_a_password_there_is_no_gate(settings, kb_opened):
    settings("test-key-not-real")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "Demo password" not in [t.label for t in at.text_input]
    assert kb_opened == [1]


def test_with_a_password_nothing_loads_until_it_is_entered(settings, kb_opened):
    settings("test-key-not-real", app_password="demo-pass")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Demo password"]
    assert not at.get("page_link") and kb_opened == []
    at.text_input(key="gate_password").input("wrong").run()
    assert [e.value for e in at.error] == ["Wrong password."]
    assert not at.get("page_link") and kb_opened == []


def test_the_right_password_opens_the_app(settings, kb_opened):
    settings("test-key-not-real", app_password="demo-pass")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input(key="gate_password").input("demo-pass").run()
    assert not at.exception and not at.error
    assert [n.proto.label for n in at.get("page_link")] == ["Admin ⚙"]
    assert kb_opened == [1]


def test_the_password_comes_before_the_missing_key_message(settings):
    settings(None, app_password="demo-pass")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.error and [t.label for t in at.text_input] == ["Demo password"]
    at.text_input(key="gate_password").input("demo-pass").run()
    assert at.error[0].value.startswith("OPENROUTER_API_KEY is not set.")


def test_a_demo_store_that_fails_its_checksum_stops_the_app(monkeypatch, settings, kb_opened, tmp_path):
    import rag.demo_store

    archive = tmp_path / "demo.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("store/index_meta.json", "{}")
    monkeypatch.setattr(rag.demo_store, "ROOT", tmp_path / "repo")          # no store there: the app fetches
    settings("test-key-not-real", demo_store_url=archive.as_uri(), demo_store_sha256="0" * 64)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) == 1 and at.error[0].value.startswith("Demo knowledge base: the archive's SHA-256 is ")
    assert kb_opened == [] and not (tmp_path / "repo").exists()


def test_the_admin_page_links_back(monkeypatch):
    kb = h.make_kb()
    store, _ = h.store_with("ready", kb=kb)
    at = h.app(store, kb, page="admin").run()
    assert not at.exception
    assert [n.proto.label for n in at.get("page_link")] == ["← Back to shipment"]
    at.session_state["_harness_page"] = "main"
    at.run()
    assert [n.proto.label for n in at.get("page_link")] == ["Admin ⚙"]
