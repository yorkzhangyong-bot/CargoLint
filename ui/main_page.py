"""The main page, the clerk's one page (feature 012, spec FR-002 to FR-014; feature 005, contracts/ui.md §2 to §7, before
it): no sidebar and no chat. The header with the Origin box, the two input tabs and the status line, then the counts
row, the sorted list with the open line, the shipper email draft, and the "Advanced" link at the bottom. Every count,
route and code comes from the line store through ui/view.py; the model is reached only through background jobs
(ui/runner.py)."""
from __future__ import annotations

import re
from typing import Any

import streamlit as st

from agent.agent import apply_taric_origin
from agent.config import MAX_DESC_CHARS, get_settings
from agent.schemas import ORIGIN_PATTERN
from ui import actions, expand, runner, shipper_email, table, upload, view

WAIT = "Wait for the running check"
WAITS = "Waits for the running check"
SUBTITLE = "Check invoice and packing-list lines before customs declaration"
ORIGIN_CAPTION = "duty and measures for goods from this country · change → re-applied, no model call"
ADVANCED = "Advanced: Ask the agent · paste shipper reply · audit trail · Admin"


def _line_count(store: Any) -> int:
    return len(store.lines) if store.has_shipment() else 0


def _file_name(store: Any) -> str | None:
    source = store.shipment.source if store.has_shipment() else None
    return source.name if source is not None else (st.session_state.get("uploaded_file") or {}).get("name")


# --------------------------------------------------------------------------- header (FR-003)
def _origin_changed(store: Any, kb: Any, previous: str) -> None:
    """A new origin re-applies the TARIC rules with no model call (FR-022). With no shipment open, a valid origin is
    kept for every new shipment. A refused one puts the field back."""
    typed = st.session_state.get("origin_field") or ""
    try:
        if store.has_shipment():
            st.toast(view.origin_toast(apply_taric_origin(store, kb, typed)))
            value = store.shipment.taric_origin
        else:
            value = typed.strip().upper()
            if re.fullmatch(ORIGIN_PATTERN, value) is None:
                raise ValueError(f"the origin must be two letters, such as CN or US, not {typed!r}")
    except ValueError as exc:
        runner.note("error", f"Origin not changed: {exc}")
        value = store.shipment.taric_origin if store.has_shipment() else previous
    st.session_state["origin_field"] = value


def _header(store: Any, kb: Any) -> None:
    left, right = st.columns([2.6, 1.4])
    left.markdown("### CargoLint")
    left.caption(SUBTITLE)
    with right.container(border=True):
        if "origin_field" not in st.session_state:   # the box would otherwise start at the list's first code
            st.session_state["origin_field"] = store.shipment.taric_origin if store.has_shipment() else "CN"
        st.selectbox("Origin", view.ORIGIN_CODES, key="origin_field", persist_state="session", width=160,
                     help="The goods' country of origin for TARIC, as an ISO code; type to filter",
                     on_change=_origin_changed, args=(store, kb, st.session_state["origin_field"]))
        st.caption(ORIGIN_CAPTION)
        st.caption(view.snapshot_caption(kb))


# --------------------------------------------------------------------------- input tabs (FR-004 to FR-006)
def _check_line(store: Any, kb: Any) -> None:
    """"Check this line" (D14): the line joins the open shipment, or opens one, through the typed-line path; behind a
    running job it waits in the queue."""
    text = (st.session_state.get("single_line") or "").strip()
    st.session_state["single_line"] = ""
    if not text:
        runner.note("warning", "Write the goods description first.")
        return
    runner.check_typed_line(store, kb, text)


def _input(store: Any, kb: Any) -> None:
    upload_tab, line_tab = st.tabs(["Upload file", "Check a single line"])
    with upload_tab:
        upload.render(store, kb)
    with line_tab, st.form("single_line_form", border=False):   # Enter checks the line too
        st.text_input("Goods description, in English or Chinese", key="single_line", max_chars=MAX_DESC_CHARS,
                      placeholder="e.g. bicycle frames, aluminium")
        st.form_submit_button("Check this line", key="check_line", type="primary", width="stretch",
                              on_click=_check_line, args=(store, kb))


def _open_typed_line(job: Any) -> None:
    """FR-006: a single typed line opens when its check ends; runner.finish itself never opens a row."""
    if job.kind == "check" and not job.file_ref and job.new_line_nos and len(job.new_line_nos) == 1:
        expand.forget(st.session_state.get("selected_line_no"))
        st.session_state["selected_line_no"] = job.new_line_nos[0]
        st.session_state[table.SHOW] = True


# --------------------------------------------------------------------------- status line (FR-007, D10)
def _checking() -> bool:
    job = runner.current_job()
    return job is not None and not job.done and job.kind == "check"


def _status(store: Any, s: view.Summary, messages: list[tuple[str, str]]) -> None:
    """The running check, else the lines checked, their file, time and model; then the queue and the job messages."""
    model = get_settings().chat_model
    if _checking():
        job = runner.current_job()
        name = (st.session_state.get("uploaded_file") or {}).get("name") if job.file_ref else None
        text = view.status_line(s, model, checking=len(job.new_line_nos) if job.new_line_nos else s.lines,
                                elapsed=job.elapsed, file_name=name)
    else:
        text = view.status_line(s, model, file_name=_file_name(store))
    if text:
        st.caption(view.md_escape(text))
    for entry in runner.queue():
        if entry[0] == "check":
            st.markdown(f":material/schedule: {view.md_escape(entry[1])}")
            st.caption(WAITS)
        elif entry[0] == "recheck":
            text = " / ".join(part for part in entry[2:] if part)
            st.markdown(f":material/schedule: Re-check line {entry[1]}: {view.md_escape(text)}")
            st.caption(WAITS)
    for level, text in messages:
        getattr(st, level)(view.md_escape(text))


# --------------------------------------------------------------------------- counts row and email draft (FR-008, FR-012)
def _accept(store: Any, line_nos: list[int] | None) -> None:
    actions.accept_ready(store, line_nos)


def _counts(store: Any, kb: Any, s: view.Summary) -> None:
    """Three bordered cards with coloured counts, "Accept all K ready" and the downloads, which add `clerk_changed`
    to the store's export (FR-013). Nothing is accepted or downloaded while a check runs."""
    checking = _checking()
    wait = WAIT if checking else None
    c = st.columns([1, 1, 1, 1.25, 1.05], vertical_alignment="center")
    for col, key, (label, colour, count) in zip(c, ("count_ready", "count_review", "count_ask"), view.count_cards(s)):
        with col.container(border=True, key=key):
            st.caption(label)
            st.subheader(f":{colour}[{count}]", anchor=False)
    if s.to_accept and not checking:
        c[3].button(view.accept_all_label(s.to_accept), key="accept_all", width="stretch", on_click=_accept,
                    args=(store, None))
    c[4].download_button("Download CSV", view.export_csv(store), file_name=store.export_filename("csv"),
                         mime="text/csv", key="export_csv", width="stretch", disabled=checking, help=wait,
                         on_click="ignore")
    c[4].download_button("JSON", view.export_json(store, kb.updated), file_name=store.export_filename("json"),
                         mime="application/json", key="export_json", type="tertiary", disabled=checking, help=wait,
                         on_click="ignore")


def _draft(store: Any, kb: Any, s: view.Summary) -> None:
    """The shipper email draft under the list (FR-012, D18): string templates to copy, in English or Chinese; nothing is
    sent or stored. Under it, folded, each asking line's update field and "Re-check this line"."""
    if not s.ask:
        return
    st.space("small")
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("**Shipper email draft** ·", width="content")
        lang = st.segmented_control("Language", ["EN", "中文"], key="email_lang", default="EN", required=True,
                                    label_visibility="collapsed")
    draft = shipper_email.draft(store, kb, "zh" if lang == "中文" else "en")
    q = len(draft.line_nos)
    st.caption(f"{q} question{'' if q == 1 else 's'} ready for the shipper")
    st.caption(":material/content_copy: Copy email — the copy button at the top right of the text")
    st.code(draft.text, language=None, wrap_lines=True)
    with st.expander(f"Shipper's answers: update {q} line{'' if q == 1 else 's'} and re-check"):
        for n in draft.line_nos:
            line = store.get_line(n)
            st.markdown(f"**Line {n}** · {view.md_escape(line.versions[0].display_text)}")
            expand.description(store, kb, line, prefix="draft_")


def _live(store: Any, kb: Any, messages: list[tuple[str, str]]) -> None:
    """The status line, the counts row, the list and the email draft, in one fragment that refreshes every second
    while a job runs or waits; when a job starts or ends, or lines appear, the whole page renders again."""
    live = runner.occupied() or bool(runner.queue())
    count = _line_count(store)

    @st.fragment(run_every=1 if live else None)
    def _part() -> None:
        job = runner.current_job()
        if (job is not None and job.done) or (runner.occupied() or bool(runner.queue())) != live \
                or _line_count(store) != count:
            st.rerun()
        statuses = {l.line_no: view.line_status(store, l, runner.line_activity(l.line_no)) for l in store.lines} \
            if count else {}
        s = view.summary(store, statuses)
        _status(store, s, messages)
        if not count:
            return
        _counts(store, kb, s)
        table.render(store, kb, statuses)
        _draft(store, kb, s)

    _part()


def render(store: Any, kb: Any, admin_page: Any = None) -> None:
    job = runner.current_job()
    if job is not None and job.done:
        _open_typed_line(job)
        runner.finish(store, kb)   # reruns the app
    _header(store, kb)
    _input(store, kb)
    _live(store, kb, runner.pop_messages())
    if admin_page is not None:
        st.page_link(admin_page, label=ADVANCED, icon=":material/arrow_right:")
