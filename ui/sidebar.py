"""Sidebar: title, upload (expander), shipment, rules, knowledge base, cost and export — grouped so nothing
important sits below the fold."""
from __future__ import annotations

import streamlit as st

from agent.config import DEFAULT_THRESHOLD, THRESHOLD_MAX, THRESHOLD_MIN, get_settings
from agent.schemas import LineStatus


def _on_threshold(store) -> None:
    if store.has_shipment():
        store.set_threshold(int(st.session_state.get("threshold", DEFAULT_THRESHOLD)))


def _on_hybrid(store) -> None:
    if store.has_shipment():
        store.set_hybrid(bool(st.session_state.get("hybrid", True)))


def kb_caption(kb) -> str:
    facts = kb.rules.caption_facts()
    year = kb.index.edition_year or ""
    return (f"HS 2022 / CN {year} · {len(kb.index):,} subheadings · ICS2 {facts['ics2_terms']} terms · "
            f"firm list {facts['firm_terms']} · {len(kb.bti):,} BTI rulings · updated {kb.updated or 'unknown'}")


def _tokens(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def render(store, kb) -> None:
    has = store.has_shipment() and bool(store.lines)
    with st.sidebar:
        st.markdown("## CargoLint")
        st.caption("Description check · HS-6 suggestions · ICS2 house filings")

        from ui import upload

        with st.expander("Packing list / invoice", expanded=not has):
            upload.render_uploader(store, kb)
        with st.expander("Shipment", expanded=True):
            upload.render_shipment_fields(store, kb)
        with st.expander("Rules", expanded=not has):
            current = store.shipment.threshold if store.has_shipment() else DEFAULT_THRESHOLD
            st.session_state.setdefault("threshold", current)
            st.slider("Auto-accept threshold", THRESHOLD_MIN, THRESHOLD_MAX, key="threshold", format="%d%%",
                      on_change=_on_threshold, args=(store,),
                      help="Unflagged lines at or above this confidence are auto-accepted. Changing it re-routes lines without re-checking them.")
            st.session_state.setdefault("hybrid", True)
            st.toggle("Hybrid search", key="hybrid", on_change=_on_hybrid, args=(store,),
                      help="BM25 keyword search plus vector search, fused by reciprocal rank fusion. Off = vector-only baseline.")
        with st.expander("Knowledge base", expanded=False):
            st.caption(kb_caption(kb))
            st.caption(f"Model via OpenRouter · {get_settings().chat_model}")

        st.divider()
        usage = store.shipment.usage if store.has_shipment() else None
        cost = usage.cost_eur if usage else 0.0
        c1, c2 = st.columns(2)
        c1.metric("Tokens", _tokens(usage.total_tokens) if usage else "0", help="Tokens used for this shipment")
        c2.metric("Cost", f"€{cost:.2f}" if cost >= 0.01 or cost == 0 else f"€{cost:.3f}", help="Token counts × price table, in EUR")
        checked = has and any(l.current.status != LineStatus.pending for l in store.lines)
        e1, e2 = st.columns(2)
        e1.download_button("CSV", data=store.to_csv_bytes() if checked else b"", file_name=store.export_filename("csv") if checked else "cargolint.csv",
                           mime="text/csv", disabled=not checked, on_click="ignore", width="stretch", key="export_csv",
                           help="Export results (CSV)")
        e2.download_button("JSON", data=store.to_json_bytes(knowledge_base_updated=kb.updated) if checked else b"",
                           file_name=store.export_filename("json") if checked else "cargolint.json", mime="application/json",
                           disabled=not checked, on_click="ignore", width="stretch", key="export_json", help="Export results (JSON)")
