"""Detail panel for the selected line: candidates, route control, decided code, lock and contradiction
notes, why it was flagged and how to update it (FR-022, FR-023, FR-035, FR-038, FR-039)."""
from __future__ import annotations

import streamlit as st

from agent.schemas import Decision, DecisionRoute
from agent.store import LockedError, UnknownCodeError
from ui.chat import FLAG_BADGE, ROUTE_BADGE, ROUTE_LABEL


def _money(line) -> str:
    if line.value is None:
        return ""
    return f"{line.value.currency} {float(line.value.amount):,.0f}"


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
    header = " · ".join(b for b in (f"Line {line.line_no}", line.qty, f"{line.weight_kg:,.0f} kg" if line.weight_kg else None, _money(line)) if b)
    with st.container(border=True):
        st.markdown(f"**{header}**")
        flag = "failed" if v.status.value == "failed" else (v.flag.kind.value if v.flag else "ok")
        badge = f"{FLAG_BADGE.get(flag, '')} {ROUTE_BADGE.get(route, '')}"
        version = f"v{v.version_no} · updated {v.created_at.astimezone().strftime('%H:%M')}" if v.version_no > 1 else f"v{v.version_no}"
        st.markdown(f"{v.text_zh}{' · ' if v.text_zh and v.text_en else ''}{v.text_en}  {badge}  \n:gray[{version}]")
        if v.contradiction_note:
            st.warning(v.contradiction_note)
        if v.extracted and any((v.extracted.material, v.extracted.part_name, v.extracted.use)):
            st.caption(f"Extracted from the shipper's reply — material: {v.extracted.material or '—'} · part: {v.extracted.part_name or '—'} · use: {v.extracted.use or '—'}")

        st.markdown("**Top-3 HS-6 candidates**")
        if v.candidates:
            for c in v.candidates[:3]:
                hist = " · history only" if c.history_only else ""
                st.progress(c.confidence / 100, text=f"{c.code} — {c.subheading_text} · {c.confidence}%{hist}")
                if c.rationale:
                    st.caption(c.rationale)
                if c.precedent:
                    p = c.precedent
                    valid = f"valid {p.valid_from or '?'} – {p.valid_to or 'open'}"
                    st.caption(f"Precedent: BTI {p.member_state} {p.reference} → {p.code} ({valid}) — {p.description[:140]}")
                else:
                    st.caption("No current BTI precedent found for this code.")
        elif v.status.value == "failed":
            st.caption(f"Check failed: {v.error_reason}")
        else:
            st.caption("No candidate" + (" (no valid candidate)" if v.no_valid_candidate else "") + ".")
        st.caption("Confidence is a model estimate, not a calibrated probability.")

        _route_control(store, line)

        if v.flag and v.flag.kind.value != "ok":
            st.markdown("**Why it was flagged**")
            rule = f" — {v.flag.rule_source.value.replace('_', ' ')}: “{v.flag.matched_term}”" if v.flag.rule_source and v.flag.matched_term else ""
            st.write(f"{v.flag.reason}{rule}. Ask the shipper for: {', '.join(a.replace('_', ' ') for a in v.flag.ask_for)}.")
        st.markdown("**Updating this line**")
        st.caption(f"Paste the shipper's reply into the chat on the left (e.g. “line {line.line_no} is steel bobbin cases for industrial "
                   "sewing machines”). Only this line is re-checked and the table refreshes.")


def _route_control(store, line) -> None:
    v = line.current
    route = store.effective_route(line)
    lock = store.accept_lock_reason(line)
    st.markdown("**Route**")
    c1, c2, c3 = st.columns(3)
    accepting = st.session_state.get("accepting_line") == line.line_no
    if c1.button("Accept" + (" ✓" if route in ("accepted", "auto_accept") else ""), key=f"acc_{line.line_no}", disabled=lock is not None,
                 use_container_width=True, type="primary" if route in ("accepted", "auto_accept") else "secondary"):
        st.session_state["accepting_line"] = line.line_no
        accepting = True
    if c2.button("Human review" + (" ✓" if route == "review" else ""), key=f"rev_{line.line_no}", use_container_width=True):
        store.set_decision(line.line_no, Decision(route=DecisionRoute.review))
        st.session_state.pop("accepting_line", None)
        st.rerun()
    if c3.button("Ask the shipper" + (" ✓" if route == "ask_shipper" else ""), key=f"ask_{line.line_no}", use_container_width=True):
        store.set_decision(line.line_no, Decision(route=DecisionRoute.ask_shipper))
        st.session_state.pop("accepting_line", None)
        st.rerun()
    code, how = store.decided_code(line)
    if code:
        how_text = {"auto": "top candidate, auto-accepted", "top": "top candidate, confirmed by you", "other_candidate": "another candidate, chosen by you",
                    "typed": "typed by you"}.get(how or "", how or "")
        st.caption(f"✅ Decided code **{code}** ({how_text}).")
    if lock:
        st.caption(f"🔒 {lock}.")
    elif store.ready_to_accept(line):
        st.caption("Ready to accept — click Accept to confirm.")
    elif v.decision is None:
        st.caption(f"{ROUTE_LABEL.get(route, route)}: {v.route_reason}.")
    if accepting and lock is None:
        _decided_code_control(store, line)


def _decided_code_control(store, line) -> None:
    v = line.current
    codes = [c.code for c in v.candidates[:3]]
    options = [f"{c.code} — {c.subheading_text}" for c in v.candidates[:3]] + ["Other HS-6 code…"]
    pick = st.radio("Decided code", options, index=0, key=f"pick_{line.line_no}")
    typed = ""
    if pick == "Other HS-6 code…":
        typed = st.text_input("Other HS-6 code", key=f"typed_{line.line_no}", placeholder="e.g. 8452.90").strip()
    code = typed if pick == "Other HS-6 code…" else codes[options.index(pick)]
    if st.button("Confirm decided code", key=f"confirm_{line.line_no}", type="primary"):
        try:
            store.set_decision(line.line_no, Decision(route=DecisionRoute.accepted, decided_code=code or None))
        except (LockedError, UnknownCodeError, ValueError) as exc:
            st.error(f"Not accepted: {exc}")
            return
        st.session_state.pop("accepting_line", None)
        st.rerun()
