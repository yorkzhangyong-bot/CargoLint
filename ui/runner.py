"""Background jobs on the script thread, for both pages (feature 005, contracts/ui.md §6, research R-15).

One job runs at a time in `st.session_state["job"]`; others wait in `job_queue` as data and touch the store only when
they start, so nothing new appears while a worker reads the store. `finish` adds the chat record of a finished job,
fails what an errored job left pending, and starts the next entry. The worker thread (ui/jobs.py) never calls
Streamlit; `activity` and `fail_pending` are pure."""
from __future__ import annotations

from typing import Any

import streamlit as st

from agent.schemas import CreatedBy, ParsedLine
from ui import jobs
from ui.view import split_description

QUEUE = "job_queue"
MESSAGES = "job_messages"     # (level, text) shown once by the page, then cleared


# --------------------------------------------------------------------------- pure parts
def activity(job: Any, queue: list, line_no: int) -> str | None:
    """Whether a background job covers this line: "running", "queued", "recheck_queued" or None."""
    for entry in queue:
        if entry[0] == "recheck" and entry[1] == line_no:
            return "recheck_queued"
    if job is not None and not job.done:
        if job.kind == "check":
            return "running"
        if job.kind in ("finer_codes", "recheck") and job.line_no == line_no:
            return "running"
        if job.kind == "reply" and job.new_line_nos and job.new_line_nos[0] == line_no:
            return "running"
    for entry in queue:
        if entry[0] == "finer_codes" and entry[1] == line_no:
            return "queued"
    return None


def fail_pending(store: Any, job: Any) -> None:
    """A job that ended with an error fails what it left pending, through the store (Principle V)."""
    if not job.error or not store.has_shipment():
        return
    if job.kind == "check":
        store.finalize_check()
    elif job.kind == "recheck" and job.line_no is not None:
        try:
            line = store.get_line(job.line_no)
        except KeyError:
            return
        if line.current.status.value == "pending":
            store.mark_failed(job.line_no, f"re-check failed: {job.error}")


# --------------------------------------------------------------------------- session helpers
def current_job() -> Any:
    return st.session_state.get("job")


def queue() -> list:
    return st.session_state.setdefault(QUEUE, [])


def occupied() -> bool:
    """A job holds the slot: running, or done but not finished yet."""
    return st.session_state.get("job") is not None


def busy() -> bool:
    job = current_job()
    return job is not None and not job.done


def line_activity(line_no: int) -> str | None:
    return activity(current_job(), st.session_state.get(QUEUE, []), line_no)


def note(level: str, text: str) -> None:
    st.session_state.setdefault(MESSAGES, []).append((level, text))


def pop_messages() -> list[tuple[str, str]]:
    return st.session_state.pop(MESSAGES, [])


# --------------------------------------------------------------------------- starting jobs
def start_check(store: Any, kb: Any, *, file_ref: str | None = None, file_name: str | None = None,
                line_nos: list[int] | None = None, raw: str | None = None) -> None:
    """A check of a file (upload or sample) or of typed lines, as an agent turn with its chat record."""
    chat = st.session_state.setdefault("chat", [])
    if file_ref:
        ref = store.shipment.reference
        message = f"Check the packing list{(' for ' + ref) if ref else ''}."
        chat.append({"role": "user", "content": message, "file": file_name})
    else:
        nos = line_nos or []
        message = f"Check lines {nos[0]}–{nos[-1]}" if len(nos) > 1 else f"Check line {nos[0]}"
        chat.append({"role": "user", "content": f"[{len(nos)} description{'s' if len(nos) != 1 else ''} added as line"
                                                f"{'s' if len(nos) != 1 else ''} {nos[0]}{'–' + str(nos[-1]) if len(nos) > 1 else ''}]",
                     "raw": raw or ""})
    st.session_state["job"] = jobs.start(jobs.Job(kind="check", message=message, is_check=True, file_ref=file_ref,
                                                  new_line_nos=line_nos), store, kb)


def check_typed_line(store: Any, kb: Any, text: str) -> int | None:
    """"+ Check one more line": add the line and start its check, or queue it behind the running job (it is then added
    when its check starts). Returns the new line number, or None when queued."""
    if occupied():
        queue().append(("check", text))
        return None
    return _add_and_check(store, kb, text)


def _add_and_check(store: Any, kb: Any, text: str) -> int:
    from ui import upload

    if not store.has_shipment():
        upload.open_shipment(store)
    zh, en = split_description(text)
    line = store.add_lines([ParsedLine(text_zh=zh, text_en=en, source_ref=f"typed line {len(store.lines) + 1}")],
                           CreatedBy.paste)[0]
    start_check(store, kb, line_nos=[line.line_no], raw=text)
    return line.line_no


def queue_finer_codes(line_no: int, store: Any, kb: Any, taric_only: bool = False) -> None:
    """Feature 004: the CN-8 and TARIC steps after the clerk's HS-6 decision, or the TARIC step alone after a CN-8
    confirmation, in the background; behind a job, the line waits in the queue."""
    if occupied():
        q = queue()
        idx = next((i for i, e in enumerate(q) if e[0] == "finer_codes" and e[1] == line_no), None)
        if idx is None:
            q.append(("finer_codes", line_no, taric_only))
        elif not taric_only:
            q[idx] = ("finer_codes", line_no, False)   # the full run includes the TARIC step
        return
    st.session_state["job"] = jobs.start(jobs.Job(kind="finer_codes", message="", is_check=False, line_no=line_no,
                                                  taric_only=taric_only), store, kb)


def start_recheck(store: Any, kb: Any, line_no: int, text_zh: str, text_en: str) -> None:
    """"Re-check line" (contracts/ui.md §5.3): with the slot free, store the edit and start the job. Behind a job, the
    edit waits in the queue as data and is stored only when its re-check starts, so no new version appears while a
    worker reads the store."""
    if occupied():
        queue().append(("recheck", line_no, text_zh, text_en))
        return
    store.update_description(line_no, text_zh, text_en)
    _start_recheck_job(store, kb, line_no)


def _start_recheck_job(store: Any, kb: Any, line_no: int) -> None:
    st.session_state["job"] = jobs.start(jobs.Job(kind="recheck", message="", is_check=False, line_no=line_no), store, kb)


def _reason(exc: Exception) -> str:
    return str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)


def start_next(store: Any, kb: Any) -> None:
    """Start the queued entries in order until one holds the slot. A queued edit that the store refuses is dropped."""
    q = queue()
    while q and not occupied():
        entry = q.pop(0)
        if entry[0] == "finer_codes":
            queue_finer_codes(entry[1], store, kb, entry[2])
        elif entry[0] == "check":
            _add_and_check(store, kb, entry[1])
        elif entry[0] == "recheck":
            _, line_no, text_zh, text_en = entry
            try:
                store.update_description(line_no, text_zh, text_en)
            except (ValueError, KeyError) as exc:
                note("error", f"Line {line_no}: re-check not started: {_reason(exc)}")
                continue
            _start_recheck_job(store, kb, line_no)


# --------------------------------------------------------------------------- finishing
def _chat_record(job: Any, store: Any) -> dict | None:
    if job.kind == "finer_codes":
        return None
    label = jobs.finish_label(job, store)
    if job.error:
        content = f"I could not finish this: {job.error}"
    else:
        content = "\n\n".join(part for part in (job.note, job.result.text if job.result else "") if part)
    msg = {"role": "assistant", "content": content, "agent_text": job.result.text if job.result else "", "label": label,
           "steps": job.step_lines(), "line_nos": job.new_line_nos,
           "counts": (job.result.counts if (job.result and job.is_check and (job.file_ref or len(job.new_line_nos or []) >= 3)) else None),
           "is_check": job.is_check, "kind": job.kind, "error": bool(job.error)}
    if job.kind == "check" and job.file_ref and store.has_shipment():
        msg["source_lines"] = [l.line_no for l in store.lines]
    if job.kind == "reply" and job.new_line_nos:
        msg["trace_from"] = job.new_line_nos[0]
        msg["source_lines"] = job.new_line_nos
    if job.kind == "question":
        msg["trace_from"] = job.selected_line_no
    if job.kind == "recheck":   # feature 005: "Line {n} re-checked", with that line's sources and retrieval steps
        msg["source_lines"] = [job.line_no]
        msg["trace_from"] = job.line_no
    return msg


def _error_text(job: Any) -> str:
    if job.kind == "finer_codes":
        step = "the TARIC step" if job.taric_only else "the CN-8 and TARIC steps"
        return f"Line {job.line_no}: {step} did not finish: {job.error}"
    if job.kind == "check":
        return f"The check did not finish: {job.error}"
    return f"Line {job.line_no}: the re-check did not finish: {job.error}" if job.line_no else f"That did not finish: {job.error}"


def finish(store: Any, kb: Any, rerun: bool = True) -> None:
    """The job is done: fail what it left pending, add its chat record, start the next queued entry, rerun the app.
    It never changes `selected_line_no`, so no row opens by itself."""
    job = st.session_state.pop("job", None)
    if job is None:
        return
    fail_pending(store, job)
    if job.error:
        note("error", _error_text(job))
    record = _chat_record(job, store)
    if record is not None:
        st.session_state.setdefault("chat", []).append(record)
    start_next(store, kb)
    if rerun:
        st.rerun()
