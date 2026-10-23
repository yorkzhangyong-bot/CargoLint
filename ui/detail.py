"""Detail card for the selected line: compact candidates, route pills, the Accept popover with the decided
code, lock / ready / contradiction notes, why it was flagged, how to update it, triage navigation
(FR-022, FR-023, FR-035, FR-038, FR-039)."""
from __future__ import annotations

import streamlit as st

from agent.agent import line_taric_view
from agent.schemas import Decision, DecisionRoute
from agent.store import LockedError, UnknownCodeError
from agent.taric_rules import EZT_ONLINE_URL, GROUPS, eu_taric_url
from ui.chat import FLAG_BADGE, ROUTE_BADGE, ROUTE_LABEL, queue_finer_codes
from ui.review import next_needs_action, reset_selection

ROUTE_PILLS = {"review": "Human review", "ask_shipper": "Ask the shipper"}


def _money(line) -> str:
    return f"{line.value.currency} {float(line.value.amount):,.0f}" if line.value is not None else ""


def _short(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def render(store, kb) -> None:
    line_no = st.session_state.get("selected_line_no")
    if not line_no:
        return
    try:
        line = store.get_line(int(line_no))
    except KeyError:
        return
    v = line.current
    route = store.effective_route(line)
    with st.container(border=True):
        head, nav = st.columns([4, 1.6], vertical_alignment="center")
        with head:
            parts = [f"Line {line.line_no}", line.qty, f"{line.weight_kg:,.0f} kg" if line.weight_kg else None, _money(line)]
            st.markdown("**" + " · ".join(p for p in parts if p) + "**")
        with nav:
            b1, b2 = st.columns(2)
            if b1.button("◀", key="nav_prev", help="Previous line needing action", width="stretch"):
                st.session_state["selected_line_no"] = next_needs_action(store, line.line_no, -1) or line.line_no
                reset_selection()
                st.rerun()
            if b2.button("Next ▶", key="nav_next", help="Next line needing action", width="stretch"):
                st.session_state["selected_line_no"] = next_needs_action(store, line.line_no, 1) or line.line_no
                reset_selection()
                st.rerun()
        flag = "failed" if v.status.value == "failed" else ("pending" if v.status.value == "pending" else (v.flag.kind.value if v.flag else "ok"))
        version = f"v{v.version_no} · updated {v.created_at.astimezone().strftime('%H:%M')}" if v.version_no > 1 else "v1"
        st.markdown(f"{v.text_zh}{' · ' if v.text_zh and v.text_en else ''}{v.text_en}  {FLAG_BADGE.get(flag, '')} "
                    f"{ROUTE_BADGE.get(route, '') if v.status.value != 'pending' else ''}  :gray[{version}]")
        if v.status.value == "pending":
            st.caption("Still checking…")
            return
        if v.contradiction_note:
            st.warning(v.contradiction_note, icon="⚠️")
        if v.extracted and any((v.extracted.material, v.extracted.part_name, v.extracted.use)):
            st.caption(f"From the shipper's reply — material: {v.extracted.material or '—'} · part: {v.extracted.part_name or '—'} · use: {v.extracted.use or '—'}")

        st.markdown("**Top-3 HS-6 candidates**")
        if v.candidates:
            for c in v.candidates[:3]:
                c1, c2, c3 = st.columns([1.15, 4.6, 1.5], vertical_alignment="center")
                c1.markdown(f"`{c.code}`")
                hist = " :gray-badge[history only]" if c.history_only else ""
                c2.markdown(f"{_short(c.subheading_text, 64)}{hist}", help=c.subheading_text)
                c3.progress(c.confidence / 100, text=f"{c.confidence}%")
                r1, r2 = st.columns([5.75, 1.5], vertical_alignment="center")
                if c.rationale:
                    r1.caption(_short(c.rationale, 150), help=c.rationale)
                if c.precedent:
                    p = c.precedent
                    with r2.popover(f"BTI {p.member_state}", help="Current binding tariff information ruling for this code", width="stretch"):
                        st.markdown(f"**{p.reference}** → `{p.code}` · {p.member_state} · valid {p.valid_from or '?'} – {p.valid_to or 'open'}")
                        st.write(p.description[:600])
                        if p.reasoning:
                            st.caption(p.reasoning[:400])
                        if p.url:
                            st.link_button("Open ruling", p.url)
                else:
                    r2.caption("no precedent")
        elif v.status.value == "failed":
            st.error(f"Check failed: {v.error_reason}", icon="⚠️")
        else:
            st.caption("No candidate" + (" (no valid candidate)" if v.no_valid_candidate else "") + ".")
        st.caption("Confidence is a model estimate, not a calibrated probability.")

        _route_control(store, line, kb)
        _cn8_section(store, line, kb)

        if v.flag and v.flag.kind.value != "ok":
            rule = f" — {v.flag.rule_source.value.replace('_', ' ')}: “{v.flag.matched_term}”" if v.flag.rule_source and v.flag.matched_term else ""
            ask = ", ".join(a.replace("_", " ") for a in v.flag.ask_for)
            st.warning(f"**Why it was flagged.** {v.flag.reason}{rule}. Ask the shipper for: {ask}.", icon="🚩")
        st.caption(f"**Updating this line:** paste the shipper's reply into the chat (e.g. “line {line.line_no} is steel bobbin cases for "
                   "industrial sewing machines”). Only this line is re-checked.")


def _route_control(store, line, kb) -> None:
    v = line.current
    route = store.effective_route(line)
    lock = store.accept_lock_reason(line)
    code, how = store.decided_code(line)
    st.markdown("**Route**")
    left, right = st.columns([3.2, 1.8], vertical_alignment="center")
    with left:
        current = ROUTE_PILLS.get(route)
        pick = st.pills("Route", list(ROUTE_PILLS.values()), default=current, selection_mode="single",
                        key=f"route_{line.line_no}_{v.version_no}_{route}", label_visibility="collapsed")
        if pick and pick != current:
            target = DecisionRoute.review if pick == "Human review" else DecisionRoute.ask_shipper
            store.set_decision(line.line_no, Decision(route=target))
            st.rerun()
    with right:
        if code:
            st.success(f"Accepted · `{code}`", icon="✅")
        else:
            with st.popover("Accept…", disabled=lock is not None, width="stretch", help=lock or "Accept this line with a decided code"):
                _decided_code_control(store, line, kb)
    if code:
        how_text = {"auto": "top candidate, auto-accepted", "top": "top candidate, confirmed by you",
                    "other_candidate": "another candidate, chosen by you", "typed": "typed by you"}.get(how or "", how or "")
        st.caption(f"Decided code {code} ({how_text}).")
    elif lock:
        st.caption(f"🔒 {lock}.")
    elif store.ready_to_accept(line):
        st.caption("Ready to accept — open *Accept…* to confirm the code.")
    elif v.decision is None:
        st.caption(f"{ROUTE_LABEL.get(route, route)}: {v.route_reason}.")


def _decided_code_control(store, line, kb) -> None:
    v = line.current
    codes = [c.code for c in v.candidates[:3]]
    options = [f"{c.code} — {_short(c.subheading_text, 48)}" for c in v.candidates[:3]] + ["Other HS-6 code…"]
    pick = st.radio("Decided code", options, index=0, key=f"pick_{line.line_no}_{v.version_no}")
    typed = ""
    if pick == "Other HS-6 code…":
        typed = st.text_input("Other HS-6 code", key=f"typed_{line.line_no}_{v.version_no}", placeholder="e.g. 8452.90").strip()
    code = typed if pick == "Other HS-6 code…" else codes[options.index(pick)]
    if st.button("Confirm", key=f"confirm_{line.line_no}_{v.version_no}", type="primary", width="stretch"):
        try:
            store.set_decision(line.line_no, Decision(route=DecisionRoute.accepted, decided_code=code or None))
        except (LockedError, UnknownCodeError, ValueError) as exc:
            st.error(f"Not accepted: {exc}")
            return
        queue_finer_codes(line.line_no, store, kb)   # feature 004: the CN-8 step for the decided HS-6
        st.rerun()


def _spaced(code: str) -> str:
    return " ".join([code[:4], code[4:6], code[6:8]] + ([code[8:]] if len(code) > 8 else []))


def _cn8_running(line_no: int) -> bool:
    job = st.session_state.get("job")
    return (job is not None and job.kind == "finer_codes" and job.line_no == line_no) or \
        any(n == line_no for n, _ in st.session_state.get("finer_codes_queue") or [])


def _cn8_section(store, line, kb) -> None:
    """Feature 004 (contracts/ui.md): the CN-8 under the decided HS-6, its evidence and ruling, and its state; then the
    TARIC subdivisions of a chosen CN-8."""
    v = line.current
    c = v.cn8
    st.markdown("**CN-8 and TARIC-10**")
    if c is None:
        st.caption("Choosing the CN-8…" if _cn8_running(line.line_no) else "Decide the HS-6 first.")
        return
    labels = dict(c.options)
    if c.cn8:
        a, b = st.columns([1.3, 5.9], vertical_alignment="center")
        a.markdown(f"`{_spaced(c.cn8)}`")
        b.markdown(_short(labels.get(c.cn8, ""), 90), help=labels.get(c.cn8, ""))
        if len(c.options) > 1 and c.confidence > 0:   # a single line or a clerk's choice has no model estimate
            st.progress(c.confidence / 100, text=f"{c.confidence}% · model estimate")
        if c.evidence:
            st.caption(f"Evidence: {_short(c.evidence, 160)}")
        if c.precedent:
            p = c.precedent
            with st.popover(f"BTI {p.member_state} {p.reference}", help="The EBTI ruling cited as precedent for this CN-8"):
                st.markdown(f"**{p.reference}** → `{p.code}` · {p.member_state} · valid {p.valid_from or '?'} – {p.valid_to or 'open'}")
                st.write(p.description[:600])
                if p.url:
                    st.link_button("Open ruling", p.url)
        else:
            st.caption("no ruling")
    if c.cn8 and c.written_by is not None and not (c.question or c.error):
        if c.written_by.value == "clerk":
            st.caption("Confirmed by you.")
        elif len(c.options) == 1:
            st.caption("Single CN-8 line.")
        else:
            st.caption(f"Written by rule (confidence {c.confidence} ≥ {store.shipment.threshold}).")
    else:
        if c.error:
            st.error(f"CN-8 step failed: {c.error}. The line is in review; choose the CN-8.", icon="⚠️")
        elif c.question:
            st.warning(c.question, icon="❓")
        elif c.precedent is not None and c.precedent.code[:8] != c.cn8:
            st.info(f"CN-8 to confirm: the cited ruling {c.precedent.reference} classifies under "
                    f"{_spaced(c.precedent.code[:8])}, not this CN-8.")
        else:
            st.info(f"CN-8 to confirm: its confidence ({c.confidence}) is below the auto-accept threshold "
                    f"({store.shipment.threshold}).")
        _cn8_confirm(store, line, kb)
    if c.cn8 and not (c.question or c.error):
        _taric_section(store, line, kb)


def _cn8_confirm(store, line, kb) -> None:
    v = line.current
    c = v.cn8
    codes = [code for code, _ in c.options]
    if not codes:
        return
    texts = [f"{_spaced(code)} — {_short(path, 70)}" for code, path in c.options]
    pick = st.radio("CN-8", texts, index=codes.index(c.cn8) if c.cn8 in codes else 0,
                    key=f"cn8_pick_{line.line_no}_{v.version_no}", label_visibility="collapsed")
    hs6, _ = store.decided_code(line)
    reason = None if hs6 else "Decide the HS-6 first"
    if st.button("Confirm CN-8", key=f"cn8_confirm_{line.line_no}_{v.version_no}", type="primary", disabled=reason is not None,
                 help=reason):
        try:
            store.confirm_cn8(line.line_no, codes[texts.index(pick)])
        except (LockedError, UnknownCodeError) as exc:
            st.error(f"Not confirmed: {exc}")
            return
        queue_finer_codes(line.line_no, store, kb, taric_only=True)   # the TARIC step for the written CN-8
        st.rerun()


GROUP_LABEL = {"duties": "Duties", "trade_defence": "Trade defence", "requirements": "Requirements"}
TABLE_PX = 250   # a fixed height: one subdivision of 7318 15 58 has about 100 trade-defence rows for China
TARIC_NOTES = {"auto_completed": "Auto-completed: single TARIC subdivision", "choose": "Choose a subdivision",
               "trade_defence": "Trade-defence measures: confirm the subdivision",
               "not_available": "TARIC not available — the line stops at 8 digits"}


def _taric_section(store, line, kb) -> None:
    """Feature 004 (contracts/ui.md): the subdivisions of the CN-8 for the shipment's origin, from the agent's
    `line_taric_view` (the UI never reads the snapshot itself), the rule that applied, and the clerk's confirmation or
    question."""
    view = line_taric_view(store, kb, line.line_no)
    if view is None:
        return
    if view.snapshot_date is None:
        st.caption("TARIC not loaded")
        return
    st.caption(f"TARIC snapshot {view.snapshot_date} · origin {view.origin}")
    t = line.current.taric
    if t is None or t.origin != view.origin:
        st.caption("Looking up TARIC…" if _cn8_running(line.line_no) else "TARIC is not looked up for this origin yet.")
        return
    rule = view.rule.value
    if rule == "not_available":
        st.info(TARIC_NOTES[rule], icon="ℹ️")
        return
    pending = rule == "auto_completed" and not t.taric10
    st.markdown(f"**{TARIC_NOTES[rule]}**" + (" — written once the CN-8 is written" if pending else ""))
    if view.suggestion_error:
        st.caption(f"Suggestion unavailable: {view.suggestion_error}")
    for sv in view.subdivisions:
        _subdivision_card(sv, view, t, line.line_no)
    if t.taric10:
        who = "Confirmed by you" if t.written_by is not None and t.written_by.value == "clerk" else "Auto-completed"
        st.success(f"{who} · TARIC-10 `{_spaced(t.taric10)}`", icon="✅")
    elif t.question:
        st.info(f"Sent to the shipper: {t.question}", icon="✉️")
    elif rule in ("choose", "trade_defence"):
        _taric_controls(store, line, view)


def _sub_text(sv) -> str:
    """A subdivision's TARIC text; a code ending in 00 has none of its own (feature 002)."""
    return sv.description or ("the whole CN-8" if sv.code.endswith("00") else "no description")


def _measure_table(measures, group: str, key: str) -> None:
    """One group of measures exactly as returned (FR-013); conditional duty text stays text."""
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
    st.dataframe(rows, hide_index=True, height=min(35 * (len(rows) + 1) + 3, TABLE_PX), key=key)


def _subdivision_card(sv, view, t, line_no: int) -> None:
    suggested = view.suggestion is not None and view.suggestion.code == sv.code
    badges = ([f":blue-badge[Suggested · {view.suggestion.confidence} %]"] if suggested else []) \
        + ([":orange-badge[Trade defence]"] if sv.trade_defence else []) + ([":green-badge[Written]"] if t.taric10 == sv.code else [])
    label = f"`{_spaced(sv.code)}` {_short(_sub_text(sv), 64)} " + " ".join(badges)
    with st.expander(label, expanded=t.taric10 == sv.code or (suggested and not t.taric10)):
        st.markdown(_sub_text(sv))
        if suggested:
            st.caption("Suggested: a model estimate; it is never written without your confirmation.")
        if sv.trade_defence:
            st.caption(f"Trade-defence measures {', '.join(sv.confirm_types)} apply: confirm the subdivision.")
        for g in GROUPS:
            _measure_table(sv.groups[g], g, key=f"measures_{line_no}_{sv.code}_{view.origin}_{g}")
        a, b, c = st.columns([1.1, 1.2, 2.4], vertical_alignment="center")
        a.link_button("EU TARIC", eu_taric_url(sv.code, view.origin, view.snapshot_date), key=f"eu_{line_no}_{sv.code}",
                      help=f"The EU TARIC consultation page for this code, origin {view.origin}, on {view.snapshot_date}")
        b.link_button("EZT-online", EZT_ONLINE_URL, key=f"ezt_{line_no}_{sv.code}",
                      help="The EZT-online start page; copy the code and origin from beside it")
        c.code(f"{sv.code} {view.origin}", language=None)


def _taric_controls(store, line, view) -> None:
    """Confirm a subdivision or ask the shipper; the guardrails are shown, not hidden (Principle VI)."""
    codes = [sv.code for sv in view.subdivisions]
    texts = [f"{_spaced(sv.code)} — {_short(_sub_text(sv), 70)}" for sv in view.subdivisions]
    first = codes.index(view.suggestion.code) if view.suggestion is not None and view.suggestion.code in codes else 0
    v = line.current
    pick = st.radio("TARIC-10", texts, index=first, key=f"taric_pick_{line.line_no}_{v.version_no}_{view.origin}",
                    label_visibility="collapsed")
    hs6, _ = store.decided_code(line)
    reason = "Decide the HS-6 first" if not hs6 else (None if store.decided_cn8(line) else "Confirm the CN-8 first")
    if st.button("Confirm TARIC-10", key=f"taric_confirm_{line.line_no}_{v.version_no}", type="primary",
                 disabled=reason is not None, help=reason):
        try:
            store.confirm_taric10(line.line_no, codes[texts.index(pick)])
        except (LockedError, UnknownCodeError) as exc:
            st.error(f"Not confirmed: {exc}")
            return
        st.rerun()
    if reason:
        st.caption(f"🔒 {reason}.")
    prefill = "Which of these describes the goods: " + "; ".join(sv.description or sv.code for sv in view.subdivisions) + "?"
    question = st.text_input("Ask the shipper", value=prefill, key=f"taric_ask_{line.line_no}_{v.version_no}")
    if st.button("Ask the shipper", key=f"taric_ask_btn_{line.line_no}_{v.version_no}"):
        try:
            store.ask_shipper_for_taric(line.line_no, question)
        except ValueError as exc:
            st.error(f"Not sent: {exc}")
            return
        st.rerun()
