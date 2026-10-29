"""The Admin page with AppTest (feature 005, contracts/ui.md §8; feature 012: a section switch instead of the sidebar):
rules, data, cost, quality and the agent chat, for the operator and the course evaluators; offline, with a seeded
store."""
from __future__ import annotations

import json
import re

import pytest

from agent.config import get_settings
from agent.schemas import ChangeKind, Route, Usage
from tests.ui import harness as h
from ui import admin, view

pytestmark = pytest.mark.integration

HISTORY = [{"iteration": 3, "change": "word-level evidence", "top1": 91, "n": 120},
           {"iteration": 4, "change": "T060 validation run", "top1": 93, "n": 120}]
RESULTS = {"hybrid": {"mode": "hybrid", "clear_lines": 12, "top1": 10, "top3": 12}}


def plain(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text or "")


def texts(at) -> list[str]:
    out = [m.value for m in at.markdown] + [c.value for c in at.caption]
    out += [e.value for kind in ("info", "warning", "error", "success") for e in getattr(at, kind)]
    return [plain(t) for t in out]


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


@pytest.fixture
def recorder(monkeypatch):
    return h.JobRecorder().install(monkeypatch)


@pytest.fixture
def downloads(monkeypatch):
    """The download buttons' data, which AppTest does not keep: label → keyword arguments with the data."""
    import streamlit
    from streamlit.delta_generator import DeltaGenerator

    seen: dict = {}
    module_fn, method = streamlit.download_button, DeltaGenerator.download_button

    def on_module(label, data, *args, **kwargs):
        seen[label] = dict(kwargs, data=data)
        return module_fn(label, data, *args, **kwargs)

    def on_container(self, label, data, *args, **kwargs):
        seen[label] = dict(kwargs, data=data)
        return method(self, label, data, *args, **kwargs)
    monkeypatch.setattr(streamlit, "download_button", on_module)
    monkeypatch.setattr(DeltaGenerator, "download_button", on_container)
    return seen


def empty_store():
    from agent.store import LineStore

    return LineStore(backend={}, index=h.small_index())


def admin_app(store, kb, section: str | None = None):
    at = h.app(store, kb, page="admin").run()
    if section:
        at.segmented_control(key="admin_section").set_value(section).run()
    assert not at.exception
    return at


def test_layout(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    at = admin_app(store, kb)
    assert "### CargoLint · Admin" in [m.value for m in at.markdown]
    assert "For the operator and course evaluators. The clerk's work happens on the shipment page." in texts(at)
    model = f"Model: {get_settings().chat_model} via OpenRouter"      # a small caption on every section (the author)
    assert model in [c.value for c in at.caption]
    assert model in [c.value for c in admin_app(store, kb, "Cost").caption]
    assert [n.proto.label for n in at.get("page_link")] == ["← Back to shipment"]
    assert len(at.sidebar.children) == 0                              # feature 012 (D17): no sidebar
    switch = at.segmented_control(key="admin_section")
    assert switch.options == ["Rules", "Data", "Cost", "Quality", "Ask the agent"] and switch.value == "Rules"


def test_rules_start_at_85_and_on_even_when_admin_opens_first(kb, recorder):
    at = admin_app(empty_store(), kb)
    slider = at.slider(key="threshold")
    assert (slider.value, slider.min, slider.max) == (85, 60, 99) and at.toggle(key="hybrid").value is True
    assert slider.label == "Auto-accept threshold, when no ruling can vote"     # feature 006: both layers' fallback
    assert ("Re-routes every unconfirmed line, no model call; clerk-confirmed lines are never touched. An HS-6 is "
            "auto-accepted and a CN-8 written when the nearest EBTI rulings agree with the model; at both layers the "
            "threshold applies only when no eligible ruling exists.") in texts(at)


def test_the_threshold_reroutes_unconfirmed_lines_only(kb, recorder):
    store, nos = h.store_with("review", "ready", "accepted", kb=kb)
    at = admin_app(store, kb)
    accepted = store.get_line(nos["accepted"]).current.model_dump()
    with h.ModelGuard() as guard:
        at.slider(key="threshold").set_value(95).run()
    assert store.shipment.threshold == 95 and guard.calls == 0
    ready = store.get_line(nos["ready"])
    assert ready.current.computed_route == Route.review                             # 92 % is under 95 now
    assert any(r.change == ChangeKind.threshold_recomputed and r.line_no == nos["ready"] for r in store.shipment.audit)
    assert store.get_line(nos["accepted"]).current.model_dump() == accepted          # the clerk's codes are untouched
    at.toggle(key="hybrid").set_value(False).run()
    assert store.shipment.hybrid_search is False


def test_the_rules_and_the_section_stay_across_pages(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    at = admin_app(store, kb)
    at.slider(key="threshold").set_value(90).run()
    at.toggle(key="hybrid").set_value(False).run()
    at.segmented_control(key="admin_section").set_value("Data").run()
    at.session_state["_harness_page"] = "main"
    at.run()
    at.button(key="sample").click().run()                            # a new shipment opened in between
    at.button(key="check_all").click().run()
    at.button(key="replace_yes").click().run()
    assert (store.shipment.threshold, store.shipment.hybrid_search) == (90, False)
    at.session_state["_harness_page"] = "admin"
    at.run()
    assert at.segmented_control(key="admin_section").value == "Data"
    at.segmented_control(key="admin_section").set_value("Rules").run()
    assert at.slider(key="threshold").value == 90 and at.toggle(key="hybrid").value is False


def test_data(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    page = texts(admin_app(store, kb, "Data"))
    assert "EBTI rulings: 2" in page and view.taric_statement(kb) in page
    assert f"Model: {get_settings().chat_model} via OpenRouter" in page
    assert view.kb_statement(kb) in page and view.kb_statement(kb).endswith("updated 2026-10-15")
    at = admin_app(store, kb, "Data")
    assert at.button(key="refresh_data").label == "Refresh (later)" and at.button(key="refresh_data").disabled
    assert "TARIC not loaded" in texts(admin_app(store, h.make_kb(taric=None), "Data"))


def test_cost(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    store.add_usage(Usage(total_tokens=1500, cost_eur=0.42, calls=3))
    at = h.app(store, kb, page="admin")
    at.session_state["session_usage"] = Usage(total_tokens=1000, cost_eur=0.5, calls=2)   # a replaced shipment's
    at.run()
    at.segmented_control(key="admin_section").set_value("Cost").run()
    assert [(m.label, m.value) for m in at.metric] == [("Tokens", "1,500"), ("Cost", "€0.42"), ("Lines", "1"),
                                                       ("Check time", "0 s"), ("Tokens", "2,500"), ("Cost", "€0.92")]
    assert "**This shipment**" in texts(at) and "**This session**" in texts(at)


def test_quality(kb, recorder, downloads, monkeypatch, tmp_path):
    (tmp_path / "history.json").write_text(json.dumps(HISTORY), encoding="utf-8")
    (tmp_path / "results.json").write_text(json.dumps(RESULTS), encoding="utf-8")
    monkeypatch.setattr(admin, "HISTORY", tmp_path / "history.json")
    monkeypatch.setattr(admin, "RESULTS", tmp_path / "results.json")
    store, _ = h.store_with("ready", "review", kb=kb)
    at = admin_app(store, kb, "Quality")
    assert at.table[0].value.to_dict("records") == view.quality_rows(HISTORY, RESULTS)
    page = texts(at)
    assert "Iteration 3: word-level evidence" in page and "Iteration 4: T060 validation run" in page
    assert "Full history: tests/eval/cn8_eval_history.json and tests/eval/cn8_eval.md." in page
    assert downloads["Export audit trail"]["data"] == view.audit_csv(store)
    monkeypatch.setattr(admin, "HISTORY", tmp_path / "missing.json")
    monkeypatch.setattr(admin, "RESULTS", tmp_path / "missing.json")
    at = admin_app(store, kb, "Quality")
    assert "No evaluation run yet." in texts(at) and not at.table


def test_ask_the_agent(kb, recorder):
    store, _ = h.store_with("ready", "review", kb=kb)                # lines open: the statement still shows
    at = admin_app(store, kb, "Ask the agent")
    assert len(at.chat_input) == 1
    assert any(t.startswith("**Which terms does customs reject?**") for t in texts(at))
    assert at.button(key="qa___terms__").label == "Go"
    block = [e for e in at.expander if e.label == "What I can and cannot do"]
    assert len(block) == 1
    assert any("draft the email to the shipper (you copy and send it)" in plain(m.value) for m in block[0].markdown)
