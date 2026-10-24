"""accept_ready (feature 005, research R-06): "Accept all K ready" and "Accept n selected" confirm each Ready line with
feature 004's confirmations, with no model call and no job."""
from __future__ import annotations

import pytest

from tests.ui import harness as h
from ui import actions, view

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


def text(store, n):
    return view.line_status(store, store.get_line(n)).text


def test_accept_ready_confirms_every_ready_line(kb):
    store, nos = h.store_with("ready", "ready_not_loaded", "accepted", "review", "taric_two", "ics2_term", "pending", kb=kb)
    others = {s: view.line_status(store, store.get_line(nos[s])) for s in ("review", "taric_two", "ics2_term", "pending")}
    with h.ModelGuard() as guard:
        assert actions.accept_ready(store) == 2                       # ready and ready_not_loaded; accepted already is
    assert [text(store, nos[s]) for s in ("ready", "ready_not_loaded", "accepted")] == ["Accepted"] * 3
    assert {s: view.line_status(store, store.get_line(nos[s])) for s in others} == others
    line = store.get_line(nos["ready"])                               # stops at 8 digits: confirm_cn8
    assert line.current.cn8.written_by.value == "clerk" and line.current.taric.written_by is None
    us, us_nos = h.store_with("ready_taric", origin="US", kb=kb)
    with h.ModelGuard() as guard2:
        assert actions.accept_ready(us) == 1                          # a written TARIC-10: confirm_taric10
    t_line = us.get_line(us_nos["ready_taric"])
    assert t_line.current.taric.written_by.value == "clerk" and t_line.current.cn8.written_by.value == "clerk"
    assert guard.calls == guard2.calls == 0
    store.set_threshold(99)
    us.set_threshold(99)                                              # confirmed codes no longer follow the threshold
    assert store.decided_cn8(store.get_line(nos["ready"])) == "96170000"
    assert us.decided_cn8(t_line) == "73181568" and us.decided_taric10(t_line) == "7318156800"
    assert text(us, us_nos["ready_taric"]) == "Accepted"


def test_accept_selected_confirms_only_the_ready_lines_named(kb):
    store, nos = h.store_with("ready", "ready_not_loaded", "accepted", "review", "ics2_term", "pending", kb=kb)
    third = h.build_state(store, kb, "ready")
    picked = [nos["ready"], third, nos["review"], nos["ics2_term"], nos["pending"], nos["accepted"]]
    assert actions.accept_ready(store, picked) == 2
    assert [text(store, n) for n in (nos["ready"], third, nos["ready_not_loaded"])] == ["Accepted", "Accepted", "Ready"]
    assert actions.accept_ready(store, []) == 0
