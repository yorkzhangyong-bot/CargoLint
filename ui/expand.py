"""The open row's content (feature 005, contracts/ui.md §5): kind (a) chooses the HS-6 or the CN-8, kind (b) the
TARIC-10, "Change" opens kind (a) on a green row's decided codes, and kind (c) asks the shipper, then updates and
re-checks the line. A confirmation writes through the store and returns at once; the later steps run as a
background job (clarification 3). Every text comes from ui/view.py."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st
from pydantic import ValidationError

from agent.agent import line_taric_view
from agent.config import MAX_DESC_CHARS
from agent.schemas import Decision, DecisionRoute
from agent.store import LockedError, UnknownCodeError
from agent.taric_rules import EZT_ONLINE_URL, GROUPS, eu_taric_url
from ui import runner, view
from ui.view import OTHER, md_escape

GROUP_LABEL = {"duties": "Duties", "trade_defence": "Trade defence", "requirements": "Requirements"}
TABLE_PX = 250   # a fixed height: one subdivision of 7318 15 58 has about 100 trade-defence rows for China
A_COLS = [1.15, 4.4, 1.5, 0.95]
B_COLS = [1.35, 2.9, 1.7, 1.45, 0.95]
REFUSED = (LockedError, UnknownCodeError, ValueError)
BLOCK = "HS-6 candidates (model estimate)"
ESTIMATE = "Confidence is a model estimate, not a calibrated probability."


def forget(line_no: int | None) -> None:
    """Drop a row's picks, so it opens again on the pre-selection (research R-14)."""
    for key in [k for k in st.session_state if str(k).startswith(f"pick_{line_no}_")]:
        del st.session_state[key]


def _keys(line: Any, kind: str, form: str) -> tuple[str, str, str]:
    base = f"{line.line_no}_{line.current.version_no}_{kind}_{form}"
    return f"pick_{base}", f"confirm_{base}", f"none_{base}"


def _set(key: str, value: str) -> None:
    st.session_state[key] = value


def _pick(key: str, default: str | None) -> str | None:
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _pick_button(col: Any, key: str, value: str, picked: str | None) -> None:
    on = value == picked
    col.button("◉ Picked" if on else "○ Pick", key=f"{key}_{value}", type="primary" if on else "tertiary",
               on_click=_set, args=(key, value))


def _lines(*texts: str) -> None:
    for text in texts:
        if text:
            st.markdown(md_escape(text))


# --------------------------------------------------------------------------- shared parts
def _top(line: Any) -> None:
    """Today's detail card behaviour: the contradiction note and the fields of a shipper's reply (FR-013)."""
    v = line.current
    if v.contradiction_note:
        st.warning(md_escape(v.contradiction_note), icon="⚠️")
    x = v.extracted
    if x is not None and any((x.material, x.part_name, x.use)):
        st.caption(f"From the shipper's reply — material: {md_escape(x.material) or '—'} · part: "
                   f"{md_escape(x.part_name) or '—'} · use: {md_escape(x.use) or '—'}")


def _precedent(p: Any, key: str) -> None:
    if p is None:
        st.caption("no close precedent")
        return
    with st.popover(f"BTI {md_escape(p.member_state)} {md_escape(p.reference)}", key=key):
        st.markdown(f"**{md_escape(p.reference)}** → `{p.code}` · {md_escape(p.member_state)} · valid "
                    f"{p.valid_from or '?'} – {p.valid_to or 'open'}")
        if p.description:
            st.markdown(md_escape(p.description[:600]))
        if p.url:
            st.link_button("Open ruling ↗", p.url, key=f"{key}_url")


def _a_table(rows: list[view.CandidateRow], key: str, pick_key: str | None = None, picked: str | None = None) -> list:
    """Code | Description · precedent | Confidence (| Pick); returns the columns, for the "Other HS-6 code…" row."""
    cols = A_COLS if pick_key else A_COLS[:3]
    head = st.columns(cols, vertical_alignment="bottom")
    for col, name in zip(head, ("Code", "Description · precedent", "Confidence", "Pick")):
        col.caption(f"**{name}**")
    head[2].caption("model estimate")
    for i, r in enumerate(rows):
        c = st.columns(cols, vertical_alignment="center")
        c[0].markdown(f"`{r.code}`")
        with c[1]:
            st.markdown(md_escape(r.description) + (" :gray-badge[history only]" if r.history_only else ""))
            if r.rationale:
                st.caption(md_escape(view.cut(r.rationale, 150)), help=md_escape(r.rationale))
            if r.confidence is not None or r.precedent is not None:   # CN-8 rows other than the chosen one show none
                _precedent(r.precedent, key=f"{key}_bti_{i}")
        if r.confidence is not None:
            c[2].progress(r.confidence / 100, text=f"{r.confidence} %")
        if pick_key:
            _pick_button(c[3], pick_key, r.value, picked)
    return cols


def _candidates_block(store: Any, line: Any, expanded: bool) -> None:
    """The HS-6 candidates as context where the HS-6 is not being picked (Principle III)."""
    rows = view.hs6_rows(store, line)
    if rows:
        with st.expander(BLOCK, expanded=expanded):
            _a_table(rows, key=f"block_{line.line_no}")
            st.caption(ESTIMATE)


def _confirm_row(line: Any, kind: str, form: str, label: str, enabled: bool, same: bool, caption: str | None,
                 confirm: Callable[[], str | None], ask: Callable[[], str | None]) -> None:
    """"Confirm {code}" and "None of these → ask shipper". A refusal shows "Not confirmed: {reason}" and changes
    nothing; a confirmation closes the row, an ask leaves it open on its question."""
    _, confirm_key, none_key = _keys(line, kind, form)
    a, b = st.columns([1, 1.4], vertical_alignment="center")
    reason = None
    with a:
        if st.button(label, key=confirm_key, type="primary", disabled=same or not enabled,
                     help="This is the current code" if same else None):
            reason = confirm()
            if reason is None:
                forget(line.line_no)
                st.session_state["selected_line_no"] = None
                st.rerun()
        if caption:
            st.caption(caption)
    if b.button("None of these → ask shipper", key=none_key, type="tertiary"):
        reason = ask()
        if reason is None:
            forget(line.line_no)
            st.rerun()
    if reason:
        st.error(f"Not confirmed: {md_escape(reason)}")


# --------------------------------------------------------------------------- kind (a): the HS-6 or the CN-8 (§5.1)
def _ask_shipper(store: Any, line: Any) -> Callable[[], str | None]:
    def ask() -> str | None:
        store.set_decision(line.line_no, Decision(route=DecisionRoute.ask_shipper))
        return None
    return ask


def _hs6_form(store: Any, kb: Any, line: Any, kind: str) -> None:
    n, vn = line.line_no, line.current.version_no
    pick_key, _, _ = _keys(line, kind, "hs6")
    default, held = view.preselect(store, line, kind, "hs6")
    picked = _pick(pick_key, default)
    rows = view.hs6_rows(store, line)
    cols = _a_table(rows, key=f"a_{n}", pick_key=pick_key, picked=picked)
    c = st.columns(cols, vertical_alignment="center")
    c[1].markdown("Other HS-6 code…")
    _pick_button(c[3], pick_key, OTHER, picked)
    typed_key = f"typed_{n}_{vn}"
    if picked == OTHER:
        if typed_key not in st.session_state:
            st.session_state[typed_key] = held
        c[1].text_input("Other HS-6 code", key=typed_key, placeholder="e.g. 8452.90", max_chars=7,
                        label_visibility="collapsed")
    st.caption(ESTIMATE)
    typed = (st.session_state.get(typed_key) or "").strip() if picked == OTHER else ""
    code = typed if picked == OTHER else picked
    shown = md_escape(typed) if picked == OTHER else next((r.code for r in rows if r.value == picked), "")
    decided = store.decided_code(line)[0] if kind == "a_change" else None

    def confirm() -> str | None:
        if not code:
            return "type the HS-6 code first, e.g. 8452.90"
        try:
            store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code=code))
        except ValidationError:
            return f"{code!r} is not an HS-6 code; type it as 8452.90"
        except REFUSED as exc:
            return str(exc)
        runner.queue_finer_codes(n, store, kb)
        return None

    _confirm_row(line, kind, "hs6", f"Confirm {shown}".strip(), enabled=picked is not None,
                 same=decided is not None and code == decided, caption="then TARIC-10 runs on this code",
                 confirm=confirm, ask=_ask_shipper(store, line))


def _cn8_form(store: Any, kb: Any, line: Any, kind: str) -> None:
    n = line.line_no
    pick_key, _, _ = _keys(line, kind, "cn8")
    picked = _pick(pick_key, view.preselect(store, line, kind, "cn8")[0])
    rows = view.cn8_rows(store, line)
    _a_table(rows, key=f"cn8_{n}", pick_key=pick_key, picked=picked)
    decided = store.decided_cn8(line) if kind == "a_change" else None

    def confirm() -> str | None:
        try:
            store.confirm_cn8(n, picked)
        except REFUSED as exc:
            return str(exc)
        if view.next_step(store, store.get_line(n)) == "TARIC step":
            runner.queue_finer_codes(n, store, kb, taric_only=True)
        return None

    _confirm_row(line, kind, "cn8", f"Confirm {next((r.code for r in rows if r.value == picked), '')}".strip(),
                 enabled=picked is not None, same=decided is not None and picked == decided,
                 caption="then TARIC-10 runs on this code", confirm=confirm, ask=_ask_shipper(store, line))


# --------------------------------------------------------------------------- kind (b): the TARIC-10 (§5.2)
def _measure_table(measures: Any, group: str) -> None:
    """One group of measures exactly as returned (feature 004 FR-013); conditional duty text stays text."""
    st.markdown(f"**{GROUP_LABEL[group]}** · {len(measures)}")
    if not measures:
        st.caption("none")
        return
    rows = []
    for m in measures:
        row = {"Type": f"{m.measure_type} {m.measure_type_label}", "Area": f"{m.geo_area} {m.geo_area_name}".strip()}
        if group == "trade_defence":
            row["Additional code"] = m.additional_code or ""
        row["Duty"] = m.duty
        row["Regulation"] = f"{m.regulation_id} {m.regulation_ref}".strip()
        rows.append(row)
    st.dataframe(rows, hide_index=True, height=min(35 * (len(rows) + 1) + 3, TABLE_PX))


def _measures(tv: Any, code: str | None, key: str) -> None:
    """"All measures" and "Open in EU TARIC ↗" for one subdivision."""
    sv = next((s for s in tv.subdivisions if s.code == code), None)
    if sv is None:
        return
    with st.expander("All measures"):
        for group in GROUPS:
            _measure_table(sv.groups[group], group)
        a, b = st.columns([1, 2.6], vertical_alignment="center")
        a.link_button("EZT-online ↗", EZT_ONLINE_URL, key=f"{key}_ezt",
                      help="The EZT-online start page; copy the code and origin from beside it")
        b.code(f"{sv.code} {tv.origin}", language=None)
    st.link_button("Open in EU TARIC ↗", eu_taric_url(sv.code, tv.origin, tv.snapshot_date), key=f"{key}_eu")


def _ad_cell(text: str) -> str:
    return text if text == "none" else f":red[{md_escape(text)}]"


def _kind_b(store: Any, kb: Any, line: Any, kind: str) -> None:
    n = line.line_no
    tv = line_taric_view(store, kb, n)
    if tv is None:
        return
    _lines(*view.explain_b(store, line, tv))
    c8 = line.current.cn8
    if c8.precedent is not None:
        _precedent(c8.precedent, key=f"b_{n}_bti")
    st.caption(f"TARIC snapshot {tv.snapshot_date} · origin {tv.origin}")
    if tv.suggestion_error:
        st.caption(f"Suggestion unavailable: {md_escape(tv.suggestion_error)}")
    _candidates_block(store, line, expanded=False)
    pick_key, _, _ = _keys(line, kind, "taric10")
    picked = _pick(pick_key, view.preselect(store, line, kind, "taric10")[0])
    rows = view.subdivision_rows(tv)
    for col, name in zip(st.columns(B_COLS, vertical_alignment="bottom"), ("Code", "Description", "Duty", "Anti-dumping", "Pick")):
        col.caption(f"**{name}**")
    for r in rows:
        c = st.columns(B_COLS, vertical_alignment="center")
        c[0].markdown(f"`{r.code}`")
        suggestion = tv.suggestion
        c[1].markdown(md_escape(r.description)
                      + (f" :blue-badge[suggested · {suggestion.confidence} %]" if r.suggested else ""))
        c[2].markdown(md_escape(r.duty))
        c[3].markdown(_ad_cell(r.anti_dumping))
        _pick_button(c[4], pick_key, r.value, picked)
    if any(r.suggested for r in rows):
        st.caption("Suggested: a model estimate; it is never written without your confirmation.")
    decided = store.decided_taric10(line) if kind == "a_change" else None

    def confirm() -> str | None:
        try:
            store.confirm_taric10(n, picked)
        except REFUSED as exc:
            return str(exc)
        return None

    def ask() -> str | None:
        try:
            store.ask_shipper_for_taric(n, view.taric_question(tv))
        except ValueError as exc:
            return str(exc)
        return None

    _confirm_row(line, kind, "taric10", f"Confirm {view.spaced(picked)}".strip(), enabled=picked is not None,
                 same=decided is not None and picked == decided, caption=None, confirm=confirm, ask=ask)
    _measures(tv, picked, key=f"b_{n}")


# --------------------------------------------------------------------------- "Change" on a green row (§5.4)
def _taric_block(store: Any, kb: Any, line: Any) -> None:
    """The written TARIC-10's cells, "All measures" and "Open in EU TARIC ↗"."""
    tv = line_taric_view(store, kb, line.line_no)
    t10 = store.decided_taric10(line)
    row = next((r for r in view.subdivision_rows(tv) if r.value == t10), None) if tv is not None else None
    if row is None:
        return
    st.caption(f"TARIC snapshot {tv.snapshot_date} · origin {tv.origin}")
    c = st.columns(B_COLS[:4], vertical_alignment="center")
    c[0].markdown(f"`{row.code}`")
    c[1].markdown(md_escape(row.description))
    c[2].markdown(md_escape(row.duty))
    c[3].markdown(_ad_cell(row.anti_dumping))
    _measures(tv, t10, key=f"block_{line.line_no}")


def _change(store: Any, kb: Any, line: Any) -> None:
    n, vn = line.line_no, line.current.version_no
    decided, note = view.explain_a(store, line, "a_change")
    _lines(decided)
    forms = view.change_forms(store, line)
    level_key = f"change_level_{n}_{vn}"
    if st.session_state.get(level_key, "HS-6") != "TARIC-10":   # the TARIC-10 form shows the same subdivision itself
        _taric_block(store, kb, line)
    level = "HS-6"
    if len(forms) > 1:
        level = st.segmented_control("Change the code at", forms, key=level_key, default="HS-6", required=True) or "HS-6"
    if level == "HS-6":
        _lines(note)
        _hs6_form(store, kb, line, "a_change")
    elif level == "CN-8":
        _lines(note)
        _candidates_block(store, line, expanded=False)
        _cn8_form(store, kb, line, "a_change")
    else:
        _kind_b(store, kb, line, "a_change")


# --------------------------------------------------------------------------- kind (c): ask the shipper, update, re-check (§5.3)
def _edit(store: Any, kb: Any, line: Any) -> None:
    """The description field and "Re-check line". The edit is checked at once; the store takes it when the re-check
    starts, which waits behind a running job (contracts/ui.md §6)."""
    n, v = line.line_no, line.current
    area_key, button_key = f"edit_{n}_{v.version_no}", f"recheck_{n}_{v.version_no}"
    if area_key not in st.session_state:
        st.session_state[area_key] = v.display_text
    st.text_area("Update the description with the shipper's answer", key=area_key, max_chars=2 * MAX_DESC_CHARS + 3,
                 help=f"Original: '{md_escape(v.display_text)}' — kept in the audit trail as 'description updated by clerk'")
    problem = None
    if st.button("Re-check line", key=button_key, type="primary"):
        zh, en = view.split_description(st.session_state.get(area_key) or "")
        problem = view.edit_problem(zh, en)            # "Write the goods description first." when both are empty
        if problem is None:
            try:
                runner.start_recheck(store, kb, n, zh, en)
            except (ValueError, KeyError) as exc:
                problem = f"Not re-checked: {exc}"
            else:
                forget(n)
                st.session_state["selected_line_no"] = None
                st.rerun()
        elif zh.strip() or en.strip():
            problem = f"Not re-checked: {problem}"
    st.caption("All steps run again for this line, from the stop-word check.")
    if problem:
        st.error(md_escape(problem))


def _kind_c(store: Any, kb: Any, line: Any, status: view.LineStatus) -> None:
    if status.kind != "c_failed":
        with st.container(border=True):
            st.markdown("**Ask the shipper**")
            st.code(status.question, language=None, wrap_lines=True)
            st.caption(":material/content_copy: Copy question — the copy button at the top right of the box")
    candidates = view.candidates_line(line)
    if candidates:
        st.markdown(md_escape(candidates))
    _candidates_block(store, line, expanded=True)
    _lines(view.reason_line(store, line) or "")
    _edit(store, kb, line)


# --------------------------------------------------------------------------- entry point
def render(store: Any, kb: Any, line: Any, status: view.LineStatus) -> None:
    """The content of the open row, by its kind (contracts/view.md §1)."""
    _top(line)
    kind = status.kind
    if kind == "a_hs6":
        _lines(*view.explain_a(store, line, kind))
        _hs6_form(store, kb, line, kind)
    elif kind == "a_cn8":
        _lines(*view.explain_a(store, line, kind))
        _candidates_block(store, line, expanded=False)
        _cn8_form(store, kb, line, kind)
    elif kind == "b":
        _kind_b(store, kb, line, kind)
    elif kind == "a_change":
        _change(store, kb, line)
    elif kind in ("c", "c_failed"):
        _kind_c(store, kb, line, status)
