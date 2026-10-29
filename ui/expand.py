"""The open line (feature 012, FR-011; feature 005, contracts/ui.md §5, before it), in four numbered blocks:

1. Description: the original, the stop-word check, the editable description and "Re-check this line";
2. HS-6 candidates: a radio over the model's three and "Other HS-6 code…"; the choice is held in the session, and
   only "Accept" writes it (D5);
3. Similar rulings: the vote of the nearest EBTI rulings on the chosen code, and the candidates' precedents;
4. Tariff: the CN-8 lines under a newly chosen code, the CN-8 or subdivision pick that is open, or the decided codes
   with their duty, requirements and measures;

then "Accept" and "Ask shipper". A decision writes through a store method and returns at once; the later steps run as
a background job (clarification 3). Every text comes from ui/view.py."""
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
from ui import actions, runner, view
from ui.view import OTHER, md_escape

GROUP_LABEL = {"duties": "Duties", "trade_defence": "Trade defence", "requirements": "Requirements"}
TABLE_PX = 250   # a fixed height: one subdivision of 7318 15 58 has about 100 trade-defence rows for China
A_COLS = [1.15, 4.4, 1.5, 0.95]
B_COLS = [1.35, 2.9, 1.7, 1.45, 0.95]
REFUSED = (LockedError, UnknownCodeError, ValueError)
ESTIMATE = "Confidence is a model estimate, not a calibrated probability."
FOLLOW = "CN-8 and TARIC-10 follow when you accept this code."
BAR_GAP = 7      # px: a radio option is 25 px tall at base font 18 and a bar 18 px, so each bar sits beside its option


def forget(line_no: int | None) -> None:
    """Drop a line's picks, so it opens again on the pre-selection (research R-14)."""
    for key in [k for k in st.session_state if str(k).startswith(f"pick_{line_no}_")]:
        del st.session_state[key]


def _pick_key(line: Any, kind: str, form: str) -> str:
    return f"pick_{line.line_no}_{line.current.version_no}_{kind}_{form}"


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


def _precedent(p: Any, key: str, code: str | None = None) -> None:
    if p is None:
        st.caption("no close precedent")
        return
    label = f"BTI {md_escape(p.member_state)} {md_escape(p.reference)}" + (f" · {code}" if code else "")
    with st.popover(label, key=key):
        st.markdown(f"**{md_escape(p.reference)}** → `{p.code}` · {md_escape(p.member_state)} · valid "
                    f"{p.valid_from or '?'} – {p.valid_to or 'open'}")
        if p.description:
            st.markdown(md_escape(p.description[:600]))
        if p.url:
            st.link_button("Open ruling ↗", p.url, key=f"{key}_url")


def _a_table(rows: list[view.CandidateRow], key: str, pick_key: str, picked: str | None) -> None:
    """Code | Description · precedent | Confidence | Pick, for the CN-8 lines under the decided HS-6."""
    head = st.columns(A_COLS, vertical_alignment="bottom")
    for col, name in zip(head, ("Code", "Description · precedent", "Confidence", "Pick")):
        col.caption(f"**{name}**")
    head[2].caption("model estimate")
    for i, r in enumerate(rows):
        c = st.columns(A_COLS, vertical_alignment="center")
        c[0].markdown(f"`{r.code}`")
        with c[1]:
            st.markdown(md_escape(r.description) + (" :gray-badge[history only]" if r.history_only else ""))
            if r.rationale:
                st.caption(md_escape(view.cut(r.rationale, 150)), help=md_escape(r.rationale))
            if r.confidence is not None or r.precedent is not None:   # CN-8 rows other than the chosen one show none
                _precedent(r.precedent, key=f"{key}_bti_{i}")
        if r.confidence is not None:
            c[2].progress(r.confidence / 100, text=f"{r.confidence} %")
        _pick_button(c[3], pick_key, r.value, picked)


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


# --------------------------------------------------------------------------- 1 Description
def description(store: Any, kb: Any, line: Any) -> None:
    """The description field and "Re-check this line", in block 1 (D2). The edit is checked at once; the store takes it
    when the re-check starts, which waits behind a running job (contracts/ui.md §6)."""
    n, v = line.line_no, line.current
    area_key, button_key = f"edit_{n}_{v.version_no}", f"recheck_{n}_{v.version_no}"
    if area_key not in st.session_state:
        st.session_state[area_key] = v.display_text
    field, act = st.columns([4, 1.3])
    field.text_area("Description", key=area_key, max_chars=2 * MAX_DESC_CHARS + 3, height="content",
                    label_visibility="collapsed",
                    help=f"Original: '{md_escape(v.display_text)}' — kept in the audit trail as 'description updated by clerk'")
    problem = None
    if act.button("Re-check this line", key=button_key, width="stretch"):
        zh, en = view.split_description(st.session_state.get(area_key) or "")
        problem = view.edit_problem(zh, en)            # "Write the goods description first." when both are empty
        if problem is None:
            try:
                runner.start_recheck(store, kb, n, zh, en)
            except (ValueError, KeyError) as exc:
                problem = f"Not re-checked: {exc}"
            else:
                forget(n)
                if st.session_state.get("selected_line_no") == n:
                    st.session_state["selected_line_no"] = None
                st.rerun()
        elif zh.strip() or en.strip():
            problem = f"Not re-checked: {problem}"
    act.caption("runs the model again")
    if problem:
        st.error(md_escape(problem))


def _block1(store: Any, kb: Any, line: Any, status: view.LineStatus) -> None:
    st.markdown("**1 Description**")
    original = f"Original: {md_escape(line.versions[0].display_text) or '_(no readable text)_'}"   # as in its row
    if status.colour == "red" and view.reason_is_stop_word(line):   # the reason below states it: shown once
        st.caption(original)
    else:
        st.caption(f"{original} · Stop-word check: {md_escape(view.stop_word_result(line))}")
    if status.colour == "red":
        _lines(view.reason_line(store, line) or "")
        if status.question:
            st.code(status.question, language=None, wrap_lines=True)
            st.caption(":material/content_copy: Copy question — the copy button at the top right of the box")
    description(store, kb, line)


# --------------------------------------------------------------------------- 2 HS-6 candidates
def selected_code(line: Any) -> str | None:
    """Block 2's choice as the session holds it: the HS-6, the typed code for "Other HS-6 code…", or None before the
    line's block 2 first shows."""
    n, vn = line.line_no, line.current.version_no
    picked = st.session_state.get(f"pick_{n}_{vn}_hs6")
    if picked is None:
        return None
    return (st.session_state.get(f"typed_{n}_{vn}") or "").strip() if picked == OTHER else picked


def _block2(store: Any, line: Any) -> str | None:
    """Returns the chosen code; "" while "Other HS-6 code…" holds no code."""
    n, vn = line.line_no, line.current.version_no
    st.markdown("**2 HS-6 candidates**")
    rows = {r.value: r for r in view.hs6_rows(store, line)}
    default, held = view.preselect(store, line, "a_change" if store.decided_code(line)[0] else "a_hs6", "hs6")
    key, typed_key = f"pick_{n}_{vn}_hs6", f"typed_{n}_{vn}"
    options = [*rows, OTHER]
    _pick(key, default if default in options else OTHER)

    def label(value: str) -> str:
        if value == OTHER:
            return "Other HS-6 code…"
        r = rows[value]
        return md_escape(view.candidate_label(r)) + (" :gray-badge[history only]" if r.history_only else "")

    choice, bars, _ = st.columns([2.6, 1, 0.5])
    picked = choice.radio("HS-6 candidates", options, key=key, format_func=label, label_visibility="collapsed")
    with bars.container(gap=BAR_GAP):                # one confidence bar beside each candidate
        for r in rows.values():
            st.progress(r.confidence)                  # an int is a percentage, kept exact
    if picked == OTHER:
        if typed_key not in st.session_state:
            st.session_state[typed_key] = held
        st.text_input("Other HS-6 code", key=typed_key, placeholder="e.g. 8452.90", max_chars=7,
                      label_visibility="collapsed")
        return selected_code(line)
    r = rows[picked]
    if r.rationale:
        st.caption(f"Why: {md_escape(r.rationale)}")
    st.caption(ESTIMATE)
    return picked


# --------------------------------------------------------------------------- 3 Similar rulings
def _block3(store: Any, line: Any, code: str | None, kind: str | None) -> None:
    st.markdown("**3 Similar rulings (5 nearest, EBTI)**")
    vote = line.current.hs6_vote
    if vote is None or not vote.competing:
        st.caption("No ruling was within the similarity floor.")
    else:
        for same, c, countries in view.vote_lines(vote, code):
            st.markdown(f"{':green[✓]' if same else ':red[✗]'} {c} · {md_escape(countries)}")
        if code:
            st.caption(view.agree_text(vote, code))
    if kind == "a_hs6":
        _lines(view.explain_a(store, line, kind)[1])      # why the line waits for the clerk
    for i, c in enumerate(line.current.candidates[:3]):
        if c.precedent is not None:
            _precedent(c.precedent, key=f"bti_{line.line_no}_{i}", code=c.code)


# --------------------------------------------------------------------------- 4 Tariff
def _cn8_list(store: Any, line: Any, code: str) -> None:
    lines = view.cn8_lines(store, line, code)
    if not lines:
        st.caption(f"No CN-8 line under {md_escape(code)}.")
    for cn8, label in lines:
        st.markdown(f"`{cn8}` {md_escape(label)}")


def _cn8_pick(store: Any, line: Any, kind: str) -> str | None:
    pick_key = _pick_key(line, kind, "cn8")
    picked = _pick(pick_key, view.preselect(store, line, kind, "cn8")[0])
    _a_table(view.cn8_rows(store, line), key=f"cn8_{line.line_no}", pick_key=pick_key, picked=picked)
    return picked


def _taric_pick(store: Any, line: Any, kind: str, tv: Any) -> str | None:
    """The subdivisions with their duty and anti-dumping, to pick one (feature 004 kind b)."""
    if tv is None:
        return None
    n = line.line_no
    _lines(*view.explain_b(store, line, tv))
    c8 = line.current.cn8
    if c8.precedent is not None:
        _precedent(c8.precedent, key=f"b_{n}_bti")
    st.caption(f"TARIC snapshot {tv.snapshot_date} · origin {tv.origin}")
    if tv.suggestion_error:
        st.caption(f"Suggestion unavailable: {md_escape(tv.suggestion_error)}")
    pick_key = _pick_key(line, kind, "taric10")
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
    _measures(tv, picked, key=f"b_{n}")
    return picked


def _tariff(store: Any, kb: Any, line: Any) -> None:
    """The decided CN-8 and TARIC-10 for the origin, the third-country duty and the requirements (D16), then all
    measures and the links."""
    n = line.line_no
    cn8, t10 = store.decided_cn8(line), store.decided_taric10(line)
    tv = line_taric_view(store, kb, n) if cn8 else None
    sv = next((s for s in tv.subdivisions if s.code == t10), None) if tv is not None and t10 else None
    t = line.current.taric
    with st.container(border=True):
        st.markdown(f"**CN-8: {view.spaced(cn8) if cn8 else '—'} · TARIC: {view.spaced(t10) if t10 else '—'}**")
        if sv is not None:
            duty = next(r.duty for r in view.subdivision_rows(tv) if r.value == t10)
            st.markdown(f"Third-country duty {md_escape(duty)} · Requirements: {md_escape(view.requirements_text(sv))}")
        elif cn8 and t is not None and t.rule in view.NOT_8_DIGITS:
            st.markdown(view.NOT_8_DIGITS[t.rule])
        if tv is not None and tv.snapshot_date:
            st.caption(f"TARIC snapshot {tv.snapshot_date} · origin {tv.origin}")
    if sv is not None:
        _measures(tv, t10, key=f"box_{n}")


def _decided(store: Any, kb: Any, line: Any) -> tuple[str | None, str | None, Any]:
    """A green line: who decided each code, the decided codes, and "Change the code at" CN-8 or TARIC-10."""
    n, vn = line.line_no, line.current.version_no
    _lines(view.explain_a(store, line, "a_change")[0])
    level_key = f"change_level_{n}_{vn}"
    if st.session_state.get(level_key) != "TARIC-10":       # the TARIC-10 pick shows the same subdivision itself
        _tariff(store, kb, line)
    forms = view.change_forms(store, line)
    level = st.segmented_control("Change the code at", forms, key=level_key) if forms else None
    if level == "CN-8":
        _lines(view.CHANGE_NOTE)
        return "cn8", _cn8_pick(store, line, "a_change"), None
    if level == "TARIC-10":
        tv = line_taric_view(store, kb, n)
        return "taric10", _taric_pick(store, line, "a_change", tv), tv
    return None, None, None


def _block4(store: Any, kb: Any, line: Any, status: view.LineStatus, code: str | None) -> tuple[str | None, str | None, Any]:
    """Returns the open pick's form ("cn8" or "taric10"), its pick and its TARIC view, or three Nones."""
    kind = status.kind
    st.markdown(f"**4 Tariff (Origin {store.shipment.taric_origin})**")
    if not code:
        st.caption("Choose a candidate, or type the HS-6 code.")
        return None, None, None
    if code != store.decided_code(line)[0]:
        _cn8_list(store, line, code)
        if status.colour != "red":
            st.caption(FOLLOW)
        return None, None, None
    if kind == "a_cn8":
        _lines(*view.explain_a(store, line, kind))
        return "cn8", _cn8_pick(store, line, kind), None
    if kind == "b":
        tv = line_taric_view(store, kb, line.line_no)
        return "taric10", _taric_pick(store, line, kind, tv), tv
    if kind == "a_change":
        return _decided(store, kb, line)
    if store.decided_cn8(line):                             # a red line: what is decided so far
        _tariff(store, kb, line)
    else:
        _cn8_list(store, line, code)
    return None, None, None


# --------------------------------------------------------------------------- "Accept" and "Ask shipper"
def _decide_hs6(store: Any, kb: Any, n: int, code: str) -> str | None:
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


def _confirm_cn8(store: Any, kb: Any, n: int, cn8: str) -> str | None:
    try:
        store.confirm_cn8(n, cn8)
    except REFUSED as exc:
        return str(exc)
    if view.next_step(store, store.get_line(n)) == "TARIC step":
        runner.queue_finer_codes(n, store, kb, taric_only=True)
    return None


def _confirm_taric10(store: Any, n: int, code: str) -> str | None:
    try:
        store.confirm_taric10(n, code)
    except REFUSED as exc:
        return str(exc)
    return None


def _accept_ready(store: Any, n: int) -> str | None:
    return None if actions.accept_ready(store, [n]) else "the line is not ready to accept"


def _ask_shipper(store: Any, n: int) -> str | None:
    store.set_decision(n, Decision(route=DecisionRoute.ask_shipper))
    return None


def _ask_for_taric(store: Any, n: int, tv: Any) -> str | None:
    try:
        store.ask_shipper_for_taric(n, view.taric_question(tv))
    except ValueError as exc:
        return str(exc)
    return None


Action = Callable[[], str | None]


def _accept(store: Any, kb: Any, line: Any, status: view.LineStatus, code: str | None, form: str | None,
            picked: str | None) -> tuple[str, Action | None, str | None]:
    """"Accept": its label, what it writes, and why it is disabled. Another HS-6 is decided first; on the line's own
    HS-6, the open pick is confirmed, or a Ready line accepted (FR-011)."""
    n = line.line_no
    if status.colour == "red":
        return "Accept", None, md_escape(status.lock_reason or "")
    if code != store.decided_code(line)[0]:
        return "Accept", lambda: _decide_hs6(store, kb, n, code or ""), None
    changing = status.kind == "a_change"
    if form == "cn8" and picked and not (changing and picked == store.decided_cn8(line)):
        return "Accept", lambda: _confirm_cn8(store, kb, n, picked), None
    if form == "taric10" and picked and not (changing and picked == store.decided_taric10(line)):
        return "Accept", lambda: _confirm_taric10(store, n, picked), None
    if changing and not status.accepted:
        return "Accept", lambda: _accept_ready(store, n), None
    if changing:
        return "Accepted", None, "Accepted; pick another code to change it"
    return "Accept", None, "Pick a code first"


def _ask(store: Any, line: Any, status: view.LineStatus, form: str | None, tv: Any) -> tuple[Action | None, str | None]:
    n = line.line_no
    if status.kind == "c_failed":
        return None, "The check failed: re-check the line first"
    if status.colour == "red":
        return None, "This line asks the shipper already"
    if form == "taric10" and tv is not None:
        return lambda: _ask_for_taric(store, n, tv), None
    return lambda: _ask_shipper(store, n), None


def _decide(store: Any, kb: Any, line: Any, status: view.LineStatus, code: str | None, form: str | None,
            picked: str | None, tv: Any) -> None:
    """"Accept" closes the line and leaves the later steps to a background job; "Ask shipper" keeps it open on its
    question. A refusal shows "Not confirmed: {reason}" and changes nothing."""
    n, vn = line.line_no, line.current.version_no
    label, accept, accept_help = _accept(store, kb, line, status, code, form, picked)
    ask, ask_help = _ask(store, line, status, form, tv)
    a, b, _ = st.columns([1.2, 1.2, 3], vertical_alignment="center")
    reason = None
    if a.button(label, key=f"accept_{n}_{vn}", type="primary", width="stretch", disabled=accept is None,
                help=accept_help):
        reason = accept()
        if reason is None:
            forget(n)
            st.session_state["selected_line_no"] = None
            st.rerun()
    if b.button("Ask shipper", key=f"ask_{n}_{vn}", width="stretch", disabled=ask is None, help=ask_help):
        reason = ask()
        if reason is None:
            forget(n)
            st.rerun()
    if reason:
        st.error(f"Not confirmed: {md_escape(reason)}")


# --------------------------------------------------------------------------- entry point
def render(store: Any, kb: Any, line: Any, status: view.LineStatus) -> None:
    """The open line's blocks and decisions (FR-011)."""
    _top(line)
    _block1(store, kb, line, status)
    code = _block2(store, line)
    _block3(store, line, code, status.kind)
    form, picked, tv = _block4(store, kb, line, status, code)
    _decide(store, kb, line, status, code, form, picked, tv)
