"""Review column: header, filters, the review table (needs-action first) and row selection (FR-024, FR-033, FR-034)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

FILTERS = ["All", "Needs action", "Accepted"]
FLAG_LABEL = {"ok": "OK", "vague": "Vague", "stop_word": "Stop-word", "failed": "Failed", "pending": "…"}
ROUTE_LABEL = {"auto_accept": "Auto-accept", "accepted": "Accepted", "review": "Review", "ask_shipper": "Ask shipper"}
FLAG_STYLE = {"OK": "background-color:#EEEEF2;color:#555867", "Vague": "background-color:#FBEBD2;color:#7A4306",
              "Stop-word": "background-color:#F9DEDE;color:#8A1C1C", "Failed": "background-color:#F9DEDE;color:#8A1C1C"}
ROUTE_STYLE = {"Auto-accept": "background-color:#E3F3EA;color:#0F5B34", "Accepted": "background-color:#E3F3EA;color:#0F5B34",
               "Review": "background-color:#FBEBD2;color:#7A4306", "Ask shipper": "background-color:#E1EAFB;color:#163C8E"}


def table_rows(store) -> list[dict]:
    rows = []
    for line in store.lines:
        v = line.current
        route = store.effective_route(line)
        flag = "failed" if v.status.value == "failed" else (v.flag.kind.value if v.flag else "pending")
        desc = " · ".join(t for t in (v.text_zh, v.text_en, line.qty) if t)
        rows.append({
            "line_no": line.line_no, "description": desc, "flag": FLAG_LABEL[flag], "hs6": v.top_code or "—",
            "confidence": (v.top_confidence or 0) / 100.0, "route": ROUTE_LABEL.get(route, route),
            "needs_action": store.needs_action(line), "version": v.version_no,
        })
    rows.sort(key=lambda r: (0 if r["needs_action"] else 1, r["line_no"]))
    return rows


def filter_rows(rows: list[dict], name: str) -> list[dict]:
    if name == "Needs action":
        return [r for r in rows if r["needs_action"]]
    if name == "Accepted":
        return [r for r in rows if not r["needs_action"]]
    return list(rows)


def _style(df: pd.DataFrame):
    return df.style.map(lambda v: FLAG_STYLE.get(v, ""), subset=["Flag"]).map(lambda v: ROUTE_STYLE.get(v, ""), subset=["Route"])


def render(store, kb) -> None:
    s = store.shipment
    counts = store.counts()
    st.subheader(f"Review · {s.reference or s.id}")
    bits = [b for b in (f"{s.origin} → {s.destination}" if s.origin and s.destination else None, s.mode, f"{len(store.lines)} lines",
                        "needs-action first") if b]
    st.caption(" · ".join(bits))
    rows = table_rows(store)
    labels = {"All": f"All {len(rows)}", "Needs action": f"Needs action {counts['needs_action']}", "Accepted": f"Accepted {counts['accepted']}"}
    choice = st.segmented_control("Filter", FILTERS, default="All", format_func=lambda f: labels[f], key="review_filter",
                                  label_visibility="collapsed") or "All"
    shown = filter_rows(rows, choice)
    df = pd.DataFrame([{"#": r["line_no"], "Description as filed": r["description"], "Flag": r["flag"], "HS-6": r["hs6"],
                        "Confidence": r["confidence"], "Route": r["route"]} for r in shown])
    if df.empty:
        st.info("No lines in this filter.")
        return
    event = st.dataframe(
        _style(df), hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", key="review_table",
        column_config={"Confidence": st.column_config.ProgressColumn("Confidence", format="percent", min_value=0, max_value=1.0),
                       "#": st.column_config.NumberColumn("#", width="small"),
                       "Description as filed": st.column_config.TextColumn("Description as filed", width="large")},
        lazy=False,
    )
    selected = event.selection.rows if event is not None and hasattr(event, "selection") else []
    if selected:
        st.session_state["selected_line_no"] = int(shown[selected[0]]["line_no"])
    elif st.session_state.get("selected_line_no") is None and shown:
        st.session_state["selected_line_no"] = int(shown[0]["line_no"])
