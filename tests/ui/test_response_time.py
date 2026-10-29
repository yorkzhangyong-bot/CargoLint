"""Response time of the clerk's actions (feature 005, SC-002, FR-029): on the 12-line sample, each action is one
AppTest run that returns within 1 s, calls no model, and only records the jobs it starts."""
from __future__ import annotations

import time

import pytest

from tests.ui import harness as h

pytestmark = pytest.mark.integration

LIMIT_S = 1.0
KIND_A, KIND_B, KIND_B_ASK, READY = 2, 5, 8, 3        # sample lines: a review line, two TARIC-10 picks, the Ready line


@pytest.fixture(scope="module")
def kb():
    return h.make_kb("sample")


@pytest.fixture
def recorder(monkeypatch):
    return h.JobRecorder().keep_running().install(monkeypatch)


@pytest.fixture
def page(kb):
    store = h.sample_store(kb)
    return store, h.app(store, kb).run()                             # the first run imports and warms up


def pick(store, n, kind, form):
    vn = store.get_line(n).current.version_no
    return f"{n}_{vn}_{kind}_{form}"


def line_key(store, n, name):
    """A key of the open line: accept, ask, typed or change_level (feature 012)."""
    return f"{name}_{n}_{store.get_line(n).current.version_no}"


def timed(at, action) -> float:
    with h.ModelGuard() as guard:
        start = time.perf_counter()
        action()
        elapsed = time.perf_counter() - start
    assert not at.exception and guard.calls == 0
    return elapsed


def test_open_a_row(page, recorder):
    store, at = page
    assert timed(at, lambda: at.button(key=f"open_{KIND_B}").click().run()) < LIMIT_S


def test_accept_an_hs6_picked_and_typed(page, recorder, kb):
    store, at = page
    at.button(key=f"open_{KIND_A}").click().run()
    assert timed(at, lambda: at.button(key=line_key(store, KIND_A, "accept")).click().run()) < LIMIT_S
    other = h.sample_store(kb)
    at2 = h.app(other, kb).run()
    at2.button(key=f"open_{KIND_A}").click().run()
    at2.radio(key=f"pick_{KIND_A}_{other.get_line(KIND_A).current.version_no}_hs6").set_value("other").run()
    at2.text_input(key=line_key(other, KIND_A, "typed")).set_value("8543.70").run()
    assert timed(at2, lambda: at2.button(key=line_key(other, KIND_A, "accept")).click().run()) < LIMIT_S
    assert [j.kind for j in recorder.jobs] == ["finer_codes", "finer_codes"]


def test_accept_a_subdivision_and_ask_the_shipper(page, recorder):
    store, at = page
    at.button(key=f"open_{KIND_B}").click().run()
    assert timed(at, lambda: at.button(key=line_key(store, KIND_B, "accept")).click().run()) < LIMIT_S
    at.button(key=f"open_{KIND_B_ASK}").click().run()
    assert timed(at, lambda: at.button(key=line_key(store, KIND_B_ASK, "ask")).click().run()) < LIMIT_S
    assert not recorder.jobs


def test_repick_a_taric10_on_an_accepted_line(page, recorder):
    store, at = page
    at.button(key=f"open_{KIND_B}").click().run()
    at.button(key=line_key(store, KIND_B, "accept")).click().run()                     # now Accepted, green
    at.button(key=f"open_{KIND_B}").click().run()
    at.segmented_control(key=line_key(store, KIND_B, "change_level")).set_value("TARIC-10").run()
    base = pick(store, KIND_B, "a_change", "taric10")
    other = next(b.key for b in at.button if b.key and b.key.startswith(f"pick_{base}_") and b.label == "○ Pick")
    at.button(key=other).click().run()
    assert timed(at, lambda: at.button(key=line_key(store, KIND_B, "accept")).click().run()) < LIMIT_S
    assert not recorder.jobs


def test_accept_all_ready(page, recorder):
    store, at = page
    assert timed(at, lambda: at.button(key="accept_all").click().run()) < LIMIT_S
    assert not recorder.jobs


def test_change_the_origin(page, recorder):
    store, at = page
    assert timed(at, lambda: at.selectbox(key="origin_field").set_value("US").run()) < LIMIT_S
    assert store.shipment.taric_origin == "US" and not recorder.jobs


def test_the_email_draft_in_both_languages(page, recorder):
    store, at = page
    assert timed(at, lambda: at.segmented_control(key="email_lang").set_value("中文").run()) < LIMIT_S
    assert timed(at, lambda: at.segmented_control(key="email_lang").set_value("EN").run()) < LIMIT_S
    assert not recorder.jobs


@pytest.mark.parametrize("key", ["export_csv", "export_json"])
def test_each_export(page, recorder, key):
    store, at = page
    button = next(b for b in at.get("download_button") if b.key == key)
    assert timed(at, lambda: button.click().run()) < LIMIT_S
    assert not recorder.jobs
