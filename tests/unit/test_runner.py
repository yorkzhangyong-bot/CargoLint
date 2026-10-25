"""The job runner's pure parts (feature 005, contracts/ui.md §6): which lines a job covers, and what a failed job
leaves pending. No Streamlit session."""
from __future__ import annotations

import pytest

from tests.ui import harness as h
from ui import runner
from ui.jobs import Job

pytestmark = pytest.mark.unit


def job(kind, line_no=None, done=False, error=None, new_line_nos=None):
    j = Job(kind=kind, message="", is_check=kind == "check", line_no=line_no, new_line_nos=new_line_nos)
    j.done, j.error = done, error
    return j


def test_a_running_check_covers_every_line():
    j = job("check")
    assert all(runner.activity(j, [], n) == "running" for n in (1, 2, 7))


def test_a_running_finer_codes_or_reply_job_covers_its_line_only():
    assert runner.activity(job("finer_codes", line_no=3), [], 3) == "running"
    assert runner.activity(job("finer_codes", line_no=3), [], 4) is None
    assert runner.activity(job("reply", new_line_nos=[5]), [], 5) == "running"
    assert runner.activity(job("reply", new_line_nos=[5]), [], 6) is None


def test_queued_entries_and_no_job():
    queue = [("finer_codes", 4, False)]
    assert runner.activity(None, queue, 4) == "queued"
    assert runner.activity(None, queue, 5) is None
    assert runner.activity(None, [], 1) is None
    assert runner.activity(job("check", done=True), [], 1) is None      # a finished job covers nothing


def test_a_failed_check_fails_every_pending_line():
    store, nos = h.store_with("pending", "ready")
    runner.fail_pending(store, job("check", done=True, error="ReadTimeout"))
    line = store.get_line(nos["pending"])
    assert line.current.status.value == "failed" and line.current.error_reason == "not checked — a step did not run"
    assert store.get_line(nos["ready"]).current.status.value == "checked"


def test_a_finer_codes_error_and_a_clean_job_change_nothing():
    store, nos = h.store_with("pending", "cn8_missing")
    before = [l.current.model_dump() for l in store.lines], len(store.shipment.audit)
    runner.fail_pending(store, job("finer_codes", line_no=nos["cn8_missing"], done=True, error="boom"))
    runner.fail_pending(store, job("check", done=True))
    assert ([l.current.model_dump() for l in store.lines], len(store.shipment.audit)) == before


# --------------------------------------------------------------------------- re-check (US3, T025)
@pytest.fixture
def session(monkeypatch):
    """The runner's session helpers on a plain dict, without a Streamlit script run."""
    from types import SimpleNamespace

    state: dict = {}
    monkeypatch.setattr(runner, "st", SimpleNamespace(session_state=state))
    return state


def test_a_running_recheck_covers_its_line_and_a_queued_one_reads_recheck_queued():
    assert runner.activity(job("recheck", line_no=3), [], 3) == "running"
    assert runner.activity(job("recheck", line_no=3), [], 4) is None
    queue = [("recheck", 4, "", "Brake pads"), ("finer_codes", 5, False)]
    assert runner.activity(job("check"), queue, 4) == "recheck_queued"           # queued behind a running check
    assert runner.activity(None, queue, 5) == "queued"


def test_a_failed_recheck_fails_its_line_only_while_it_is_pending():
    store, nos = h.store_with("pending", "review")
    runner.fail_pending(store, job("recheck", line_no=nos["pending"], done=True, error="ReadTimeout"))
    line = store.get_line(nos["pending"])
    assert line.current.status.value == "failed" and line.current.error_reason == "re-check failed: ReadTimeout"
    before = store.get_line(nos["review"]).current.model_dump()
    runner.fail_pending(store, job("recheck", line_no=nos["review"], done=True, error="ReadTimeout"))
    assert store.get_line(nos["review"]).current.model_dump() == before


def test_start_recheck_stores_the_edit_then_starts_the_job_or_queues_it(session, monkeypatch):
    recorder = h.JobRecorder().keep_running().install(monkeypatch)
    store, nos = h.store_with("ics2_term", "review")
    n, m = nos["ics2_term"], nos["review"]
    runner.start_recheck(store, None, n, "", "Brake pads for bicycles, steel")
    assert store.get_line(n).current.created_by.value == "clerk"
    assert [(j.kind, j.line_no) for j in recorder.jobs] == [("recheck", n)]
    runner.start_recheck(store, None, m, "", "LED desk lamp, USB powered")      # a job runs: the edit waits as data
    assert session[runner.QUEUE] == [("recheck", m, "", "LED desk lamp, USB powered")]
    assert store.get_line(m).current.version_no == 1 and len(recorder.jobs) == 1


def test_a_queued_recheck_whose_edit_fails_is_dropped(session, monkeypatch):
    recorder = h.JobRecorder().keep_running().install(monkeypatch)
    store, nos = h.store_with("ics2_term", "review")
    n, m = nos["ics2_term"], nos["review"]
    session[runner.QUEUE] = [("recheck", n, " ", ""), ("recheck", 99, "", "Brake pads"),
                             ("recheck", m, "", "LED desk lamp, USB powered")]
    runner.start_next(store, None)
    assert session[runner.MESSAGES] == [("error", f"Line {n}: re-check not started: write the goods description"),
                                        ("error", "Line 99: re-check not started: line 99 not found")]
    assert store.get_line(n).current.version_no == 1
    assert [(j.kind, j.line_no) for j in recorder.jobs] == [("recheck", m)] and session[runner.QUEUE] == []
    assert store.get_line(m).current.created_by.value == "clerk"
