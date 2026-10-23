"""Detail card for the selected line: compact candidates, route pills, the Accept popover with the decided
code, lock / ready / contradiction notes, why it was flagged, how to update it, triage navigation
(FR-022, FR-023, FR-035, FR-038, FR-039)."""
from __future__ import annotations

import streamlit as st

from agent.schemas import Decision, DecisionRoute
from agent.store import LockedError, UnknownCodeError
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
        _cn8_section(store, line)

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
        line_no in (st.session_state.get("finer_codes_queue") or [])


def _cn8_section(store, line) -> None:
    """Feature 004 (contracts/ui.md): the CN-8 under the decided HS-6, its evidence and ruling, and its state."""
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
        return
    if c.error:
        st.error(f"CN-8 step failed: {c.error}. The line is in review; choose the CN-8.", icon="⚠️")
    elif c.question:
        st.warning(c.question, icon="❓")
    else:
        st.info("CN-8 to confirm: its confidence is below the auto-accept threshold.")
    _cn8_confirm(store, line)


def _cn8_confirm(store, line) -> None:
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
        st.rerun()
