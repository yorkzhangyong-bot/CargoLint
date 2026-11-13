"""app.py and the two pages (feature 005, contracts/ui.md §1; feature 012): the hidden navigation, no link from the main
page to the Admin page (which keeps its own address and "← Back to shipment"), no sidebar, and the missing-key message. Feature 011: the demo password gate and a demo store that fails its checksum."""
from __future__ import annotations

import dataclasses
import zipfile
from pathlib import Path
from types import SimpleNamespace

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


def test_app_opens_the_main_page_with_no_admin_link(monkeypatch, settings):
    import rag.loader

    settings("test-key-not-real")
    monkeypatch.setattr(rag.loader, "open_knowledge_base", lambda *a, **k: h.make_kb())
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.selectbox(key="origin_field").value == "CN" and not at.get("page_link")   # the Admin page: /admin only
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
    assert not at.selectbox and kb_opened == []                    # nothing of the main page yet
    at.text_input(key="gate_password").input("wrong").run()
    assert [e.value for e in at.error] == ["Wrong password."]
    assert not at.selectbox and kb_opened == []


def test_the_right_password_opens_the_app(settings, kb_opened):
    settings("test-key-not-real", app_password="demo-pass")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input(key="gate_password").input("demo-pass").run()
    assert not at.exception and not at.error
    assert at.selectbox(key="origin_field").value == "CN"            # the main page
    assert kb_opened == [1]


def test_the_password_comes_before_the_missing_key_message(settings):
    settings(None, app_password="demo-pass")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.error and [t.label for t in at.text_input] == ["Demo password"]
    at.text_input(key="gate_password").input("demo-pass").run()
    assert at.error[0].value.startswith("OPENROUTER_API_KEY is not set.")


def test_the_demo_notice_shows_only_when_switched_on(settings, kb_opened):
    settings("test-key-not-real", demo_notice=True)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    notice = [e for e in at.expander if e.label == "Before you upload"]
    assert len(notice) == 1
    assert [m.value for m in notice[0].markdown] == [
        "This is a demo for evaluation, not customs advice. Every code and rewrite must be checked by the declarant "
        "before use.",
        "CargoLint stores nothing you upload. Each line is sent to an AI model through OpenRouter (US-hosted) to be "
        "classified. Please use lists without personal data such as names, phone numbers or email addresses.",
        "Your shipment lives only in this browser session: export your results before you close the tab.",
    ]
    settings("test-key-not-real", demo_notice=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "Before you upload" not in [e.label for e in at.expander]


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
    assert len(at.sidebar.children) == 0 and at.segmented_control(key="admin_section").value == "Rules"
    at.session_state["_harness_page"] = "main"
    at.run()
    assert not at.get("page_link")                                 # the main page links nowhere
    assert len(at.sidebar.children) == 0                           # feature 012: no sidebar on either page


# --------------------------------------------------------------------------- feature 013: the releases at a cold start
import hashlib  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402


@pytest.fixture
def releases(tmp_path, monkeypatch):
    """A folder of releases behind file: URL templates and an empty root; the pointer names the releases given."""
    import rag.refresh as rf

    base = tmp_path / "site"
    base.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    uri = base.as_uri()
    monkeypatch.setattr(rf, "ROOT", root)
    monkeypatch.setattr(rf, "LATEST", uri + "/latest/{asset}")
    monkeypatch.setattr(rf, "API", uri + "/releases.json")
    monkeypatch.setattr(rf, "DOWNLOAD", uri + "/{tag}/{asset}")

    def add(name: str, *, sha: str | None = None, archive: bool = True) -> None:
        kind, day = rf.parse_release_name(name)
        folder = base / name
        folder.mkdir()
        entries = {"store/index_meta.json": b"{}", "store/bm25.pkl": b"bm25"} if kind == "ebti" else {"data/taric.jsonl": b"{}\n"}
        path = folder / rf.archive_name(kind, day)
        with zipfile.ZipFile(path, "w") as z:
            for entry, data in entries.items():
                z.writestr(entry, data)
        fields = {"kind": kind, "release": name, "archive": path.name, "sha256": sha or hashlib.sha256(path.read_bytes()).hexdigest()}
        if not archive:
            path.unlink()
        (folder / "metadata.json").write_text(json.dumps(fields), encoding="utf-8")

    def point(current: dict) -> None:
        (base / "latest").mkdir(exist_ok=True)
        (base / "latest" / "metadata.json").write_text(json.dumps({"kind": "ebti", "release": "x", "archive": "x", "sha256": "x",
                                                                   "current": current}), encoding="utf-8")

    return SimpleNamespace(base=base, root=root, add=add, point=point)


def test_an_ebti_release_that_fails_its_checksum_stops_the_app(settings, kb_opened, releases):
    releases.add("ebti-2026-11-01", sha="0" * 64)
    releases.point({"ebti": ["ebti-2026-11-01"], "taric": []})
    settings("test-key-not-real", release_repo="owner/name")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) == 1 and at.error[0].value.startswith("Knowledge base release: ebti: ebti-2026-11-01: the archive's SHA-256 is ")
    assert kb_opened == [] and not (releases.root / "store").exists()


def test_a_taric_release_that_cannot_be_fetched_opens_the_app_without_taric(monkeypatch, settings, releases):
    import rag.loader

    calls: list[int] = []
    monkeypatch.setattr(rag.loader, "open_knowledge_base", lambda *a, **k: (calls.append(1), h.make_kb(taric=None))[1])
    st.cache_resource.clear()
    releases.add("ebti-2026-11-01")
    releases.add("taric-2026-11-02", sha="0" * 64)
    releases.add("taric-2026-10-01", archive=False)
    releases.point({"ebti": ["ebti-2026-11-01"], "taric": ["taric-2026-11-02", "taric-2026-10-01"]})
    settings("test-key-not-real", release_repo="owner/name")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) == 1 and at.error[0].value.startswith("Knowledge base release: taric: taric-2026-11-02: the archive's SHA-256 is ")
    assert "; taric-2026-10-01: the archive could not be downloaded" in at.error[0].value
    assert calls == [1] and at.selectbox(key="origin_field").value == "CN"             # the page opened
    assert any(c.value.startswith("TARIC not loaded") for c in at.caption)
    assert (releases.root / "store" / "index_meta.json").exists() and not (releases.root / "data" / "taric.jsonl").exists()
    at.run()                                                                            # the error stays on every run
    assert len(at.error) == 1


def test_with_both_settings_the_release_fetch_runs_and_the_demo_fetch_does_not(monkeypatch, settings, kb_opened, releases, caplog):
    import rag.demo_store

    monkeypatch.setattr(rag.demo_store, "fetch_demo_store", lambda *a, **k: pytest.fail("the feature-011 fetch must not run"))
    releases.add("ebti-2026-11-01")
    releases.add("taric-2026-11-02")
    releases.point({"ebti": ["ebti-2026-11-01"], "taric": ["taric-2026-11-02"]})
    settings("test-key-not-real", release_repo="owner/name", demo_store_url="https://example.invalid/demo.zip",
             demo_store_sha256="0" * 64)
    with caplog.at_level(logging.INFO):
        at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception and not at.error and kb_opened == [1]
    assert (releases.root / "store" / "release.json").exists() and (releases.root / "data" / "taric_release.json").exists()
    assert any("CARGOLINT_RELEASE_REPO is set" in r.getMessage() and "ignored" in r.getMessage() for r in caplog.records)
