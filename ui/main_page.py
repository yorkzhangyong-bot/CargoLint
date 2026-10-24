"""The main page, the clerk's one page (feature 005, contracts/ui.md §2, §3, §7): no sidebar and no chat. The header,
then the empty state, or the summary bar over the decision table with the buttons under it. Every count, route and
code comes from the line store through ui/view.py; the model is reached only through background jobs (ui/runner.py)."""
from __future__ import annotations

import re
from typing import Any

import streamlit as st

from agent.agent import apply_taric_origin
from agent.config import MAX_DESC_CHARS
from agent.schemas import ORIGIN_PATTERN
from ui import actions, runner, shipper_email, table, upload, view

WAIT = "Wait for the running check"
WAITS = "Waits for the running check"


def _flip(flag: str) -> None:
    st.session_state[flag] = not st.session_state.get(flag, False)


def _line_count(store: Any) -> int:
    return len(store.lines) if store.has_shipment() else 0


def _lines(n: int) -> str:
    return f"{n} line{'' if n == 1 else 's'}"


def _file_name(store: Any) -> str | None:
    source = store.shipment.source
    return source.name if source is not None else (st.session_state.get("uploaded_file") or {}).get("name")


def _typed(store: Any, kb: Any, key: str, close: str | None = None) -> None:
    """Enter in "Check one line" or "+ Check one more line": the line is added and checked, or waits behind the
    running job (runner.check_typed_line)."""
    text = (st.session_state.get(key) or "").strip()
    st.session_state[key] = ""
    if close:
        st.session_state[close] = False
    if text:
        runner.check_typed_line(store, kb, text)


# --------------------------------------------------------------------------- header (§2)
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


def _header(store: Any, kb: Any, admin_page: Any) -> None:
    n = _line_count(store)
    c = st.columns([1.5, 3.3, 1.2, 1.5, 0.9], vertical_alignment="center")
    c[0].markdown("### CargoLint")
    if n:
        name = _file_name(store)
        c[1].markdown(f"{view.md_escape(name) if name else 'Typed lines'} · {_lines(n)}")
    with c[2]:
        if "origin_field" not in st.session_state:   # the field would otherwise start empty
            st.session_state["origin_field"] = store.shipment.taric_origin if store.has_shipment() else "CN"
        st.text_input("Origin", key="origin_field", max_chars=2, persist_state="session",
                      help="The goods' country of origin for TARIC, two letters; CN by default",
                      on_change=_origin_changed, args=(store, kb, st.session_state["origin_field"]))
        st.caption(view.snapshot_caption(kb))
    if n:
        busy = runner.busy()
        c[3].button("Open another file", key="open_file_button", on_click=_flip, args=("open_file",), disabled=busy,
                    help=WAIT if busy else None)
    if admin_page is not None:
        c[4].page_link(admin_page, label="Admin ⚙")


# --------------------------------------------------------------------------- empty state (§2)
def _empty_state(store: Any, kb: Any) -> None:
    job = runner.current_job()
    if job is not None and not job.done and job.kind == "check" and job.file_ref:
        name = (st.session_state.get("uploaded_file") or {}).get("name") or "the file"
        st.info(f"Checking {view.md_escape(name)}…", icon=":material/hourglass_top:")
        return
    upload.render_drop_zone(store, kb, key="empty")
    busy = runner.busy()
    st.text_input("Check one line", key="check_one_line", max_chars=MAX_DESC_CHARS,
                  placeholder="Type a goods description and press Enter, e.g. bicycle frames, aluminium",
                  on_change=_typed, args=(store, kb, "check_one_line"), disabled=busy, help=WAIT if busy else None)
    table.render(store, kb, {})


# --------------------------------------------------------------------------- summary, table and buttons (§3, §4, §7)
def _checking() -> bool:
    job = runner.current_job()
    return job is not None and not job.done and job.kind == "check"


def _accept(store: Any, line_nos: list[int] | None) -> None:
    actions.accept_ready(store, line_nos)


def _summary(store: Any, statuses: dict[int, view.LineStatus]) -> None:
    s = view.summary(store, statuses)
    if _checking():
        st.markdown(f"**Checking {_lines(s.lines)}… · {runner.current_job().elapsed:.0f} s**")
    else:
        st.markdown(view.summary_text(s))
    bar = view.split_bar(s)
    if bar:
        st.markdown(bar)
    if _checking():
        return
    selected = [n for n, status in statuses.items() if status.selectable and st.session_state.get(f"accept_{n}")]
    c = st.columns([1.3, 1.3, 3])
    if s.to_accept:
        c[0].button(view.accept_all_label(s.to_accept), key="accept_all", type="primary", on_click=_accept,
                    args=(store, None))
    if selected:
        c[1].button(view.accept_selected_label(len(selected)), key="accept_selected", on_click=_accept,
                    args=(store, selected))


def _email(store: Any, kb: Any, c: int) -> None:
    """The draft under the button row (FR-020, FR-021): string templates, to copy; nothing is sent or stored."""
    with st.container(border=True):
        st.markdown(f"**Email to shipper — generated from the {c} open question{'' if c == 1 else 's'}, no model call**")
        lang = st.segmented_control("Language", ["EN", "中文"], key="email_lang", default="EN", required=True,
                                    label_visibility="collapsed")
        st.caption(":material/content_copy: Copy email — the copy button at the top right of the text")
        st.code(shipper_email.draft(store, kb, "zh" if lang == "中文" else "en").text, language=None, wrap_lines=True)


def _buttons(store: Any, kb: Any, ask: int) -> None:
    row = st.columns([1, 1, 1.8, 1.8])
    checking = _checking()
    wait = WAIT if checking else None
    row[0].download_button("Export CSV", store.to_csv_bytes(), file_name=store.export_filename("csv"), mime="text/csv",
                           key="export_csv", disabled=checking, help=wait, on_click="ignore")
    row[1].download_button("Export JSON", store.to_json_bytes(knowledge_base_updated=kb.updated),
                           file_name=store.export_filename("json"), mime="application/json", key="export_json",
                           disabled=checking, help=wait, on_click="ignore")
    row[2].button(view.email_label(ask), key="email_button", on_click=_flip, args=("email_open",), disabled=not ask)
    row[3].button("+ Check one more line", key="more_line_button", on_click=_flip, args=("more_line_open",))
    if ask and st.session_state.get("email_open"):
        _email(store, kb, ask)
    if st.session_state.get("more_line_open"):
        st.text_input("Type a goods description and press Enter", key="more_line", max_chars=MAX_DESC_CHARS,
                      on_change=_typed, args=(store, kb, "more_line", "more_line_open"))
    for entry in runner.queue():
        if entry[0] == "check":
            st.markdown(f":material/schedule: {view.md_escape(entry[1])}")
            st.caption(WAITS)
        elif entry[0] == "recheck":
            text = " / ".join(part for part in entry[2:] if part)
            st.markdown(f":material/schedule: Re-check line {entry[1]}: {view.md_escape(text)}")
            st.caption(WAITS)


def _live(store: Any, kb: Any) -> None:
    """The summary, the table and the blocks under it, in one fragment that refreshes every second while a job runs or
    waits; when a job starts or ends, or lines appear, the whole page renders again."""
    live = runner.occupied() or bool(runner.queue())
    count = _line_count(store)

    @st.fragment(run_every=1 if live else None)
    def _part() -> None:
        job = runner.current_job()
        if (job is not None and job.done) or (runner.occupied() or bool(runner.queue())) != live \
                or _line_count(store) != count:
            st.rerun()
        if not count:
            return
        statuses = {l.line_no: view.line_status(store, l, runner.line_activity(l.line_no)) for l in store.lines}
        _summary(store, statuses)
        table.render(store, kb, statuses)
        _buttons(store, kb, view.summary(store, statuses).ask)

    _part()


def render(store: Any, kb: Any, admin_page: Any = None) -> None:
    job = runner.current_job()
    if job is not None and job.done:
        runner.finish(store, kb)   # reruns the app
    _header(store, kb, admin_page)
    for level, text in runner.pop_messages():
        getattr(st, level)(view.md_escape(text))
    n = _line_count(store)
    if n and st.session_state.get("open_file"):
        upload.render_drop_zone(store, kb, key="open")
    if not n:
        _empty_state(store, kb)
    _live(store, kb)
