"""Sidebar block: tokens and cost for the shipment, model caption, CSV/JSON export (FR-040, FR-041)."""
from __future__ import annotations

import streamlit as st

from agent.config import get_settings
from agent.schemas import LineStatus


def _tokens(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def render(store, kb) -> None:
    has = store.has_shipment()
    usage = store.shipment.usage if has else None
    c1, c2 = st.columns(2)
    c1.metric("Tokens this shipment", _tokens(usage.total_tokens) if usage else "0")
    c2.metric("Cost", f"€{usage.cost_eur:.2f}" if usage else "€0.00", help="Estimated from OpenRouter token counts × the price table, converted to EUR")
    st.caption(f"Model via OpenRouter ({get_settings().chat_model}) · knowledge base updated {kb.updated or 'unknown'}")
    checked = has and any(l.current.status != LineStatus.pending for l in store.lines)
    st.download_button("Export results (CSV)", data=store.to_csv_bytes() if checked else b"",
                       file_name=store.export_filename("csv") if checked else "cargolint.csv", mime="text/csv",
                       disabled=not checked, on_click="ignore", use_container_width=True, key="export_csv")
    st.download_button("Export results (JSON)", data=store.to_json_bytes(knowledge_base_updated=kb.updated) if checked else b"",
                       file_name=store.export_filename("json") if checked else "cargolint.json", mime="application/json",
                       disabled=not checked, on_click="ignore", use_container_width=True, key="export_json")
