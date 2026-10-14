"""Sidebar: title, uploader and shipment fields (US2), rules, knowledge-base caption, cost and export (US4)."""
from __future__ import annotations

import importlib.util

import streamlit as st

from agent.config import DEFAULT_THRESHOLD, THRESHOLD_MAX, THRESHOLD_MIN


def _on_threshold(store) -> None:
    value = int(st.session_state.get("threshold", DEFAULT_THRESHOLD))
    if store.has_shipment():
        store.set_threshold(value)


def _on_hybrid(store) -> None:
    if store.has_shipment():
        store.set_hybrid(bool(st.session_state.get("hybrid", True)))


def kb_caption(kb) -> str:
    facts = kb.rules.caption_facts()
    year = kb.index.edition_year or ""
    return (f"Knowledge base: HS 2022 / CN {year} — {len(kb.index):,} subheadings · ICS2 lists ({facts['ics2_terms']} terms) · "
            f"firm stop-words ({facts['firm_terms']}) · {len(kb.bti):,} BTI rulings · updated {kb.updated or 'unknown'}")


def render(store, kb) -> None:
    with st.sidebar:
        st.title("CargoLint")
        st.caption("Description check · HS-6 suggestions · ICS2 house filings")

        st.subheader("Packing list / invoice")
        if importlib.util.find_spec("ui.upload") is not None:
            from ui import upload

            upload.render(store, kb)
        else:
            st.caption("File upload arrives with the next increment; paste descriptions in the chat for now.")

        st.subheader("Rules")
        current = store.shipment.threshold if store.has_shipment() else DEFAULT_THRESHOLD
        st.session_state.setdefault("threshold", current)
        st.slider("Auto-accept threshold", THRESHOLD_MIN, THRESHOLD_MAX, key="threshold", format="%d%%",
                  on_change=_on_threshold, args=(store,),
                  help="Unflagged lines at or above this confidence are auto-accepted. Changing it re-routes lines without re-checking them.")
        st.session_state.setdefault("hybrid", True)
        st.toggle("Hybrid search", key="hybrid", on_change=_on_hybrid, args=(store,),
                  help="BM25 keyword search plus vector search, fused by reciprocal rank fusion. Off = vector-only baseline for comparison.")
        st.caption(kb_caption(kb))

        if importlib.util.find_spec("ui.cost") is not None:
            from ui import cost

            cost.render(store, kb)
