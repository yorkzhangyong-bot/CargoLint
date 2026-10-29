"""The Admin page (feature 005, contracts/ui.md §8), for the operator and the course evaluators: the rules, the data,
the cost, the quality and the agent chat, behind a section switch at the top (feature 012, D17). The clerk's work
happens on the main page."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from agent.config import DEFAULT_THRESHOLD, ROOT, THRESHOLD_MAX, THRESHOLD_MIN, get_settings
from agent.schemas import Usage
from ui import chat, runner, view

SECTIONS = ["Rules", "Data", "Cost", "Quality", "Ask the agent"]
HISTORY = ROOT / "tests" / "eval" / "cn8_eval_history.json"
RESULTS = ROOT / "tests" / "eval" / "results.json"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _money(eur: float) -> str:
    return f"€{eur:.3f}" if 0 < eur < 0.01 else f"€{eur:.2f}"


# --------------------------------------------------------------------------- Rules
def _threshold_changed(store: Any) -> None:
    if store.has_shipment():
        store.set_threshold(st.session_state["threshold"])


def _hybrid_changed(store: Any) -> None:
    if store.has_shipment():
        store.set_hybrid(st.session_state["hybrid"])


def _rules(store: Any) -> None:
    """Both values survive a page switch, and every new shipment starts with them (upload.open_shipment). Missing
    values are set before the widgets render: the slider would otherwise start at 60."""
    has = store.has_shipment()
    if "threshold" not in st.session_state:
        st.session_state["threshold"] = store.shipment.threshold if has else DEFAULT_THRESHOLD
    if "hybrid" not in st.session_state:
        st.session_state["hybrid"] = store.shipment.hybrid_search if has else True
    st.slider("Auto-accept threshold, when no ruling can vote", THRESHOLD_MIN, THRESHOLD_MAX, key="threshold",
              format="%d %%", persist_state="session", on_change=_threshold_changed, args=(store,))
    st.caption("Re-routes every unconfirmed line, no model call; clerk-confirmed lines are never touched. An HS-6 is "
               "auto-accepted and a CN-8 written when the nearest EBTI rulings agree with the model; at both layers the "
               "threshold applies only when no eligible ruling exists.")
    st.toggle("Hybrid search (BM25 and vectors)", key="hybrid", persist_state="session", on_change=_hybrid_changed,
              args=(store,))


# --------------------------------------------------------------------------- Data, Cost, Quality
def _data(kb: Any) -> None:
    st.markdown(f"EBTI rulings: {len(kb.bti):,}")
    st.markdown(view.taric_statement(kb))
    st.markdown(f"Model: {get_settings().chat_model} via OpenRouter")
    st.markdown(view.kb_statement(kb))
    st.button("Refresh (later)", key="refresh_data", disabled=True, help="A later feature refreshes the data from here")


def _cost(store: Any) -> None:
    usage = store.shipment.usage if store.has_shipment() else Usage()
    s = view.summary(store, {})
    st.markdown("**This shipment**")
    c = st.columns(4)
    c[0].metric("Tokens", f"{usage.total_tokens:,}")
    c[1].metric("Cost", _money(usage.cost_eur))
    c[2].metric("Lines", f"{s.lines}")
    c[3].metric("Check time", f"{s.seconds:.0f} s")
    total = Usage()
    total.add(st.session_state.get("session_usage") or Usage())   # the shipments replaced in this session
    total.add(usage)
    st.markdown("**This session**")
    d = st.columns(4)
    d[0].metric("Tokens", f"{total.total_tokens:,}")
    d[1].metric("Cost", _money(total.cost_eur))


def _quality(store: Any) -> None:
    history = _read(HISTORY)
    rows = view.quality_rows(history, _read(RESULTS))
    if rows:
        st.table(rows, hide_index=True)
        for caption in view.quality_captions(history):
            st.caption(view.md_escape(caption))
    else:
        st.markdown("No evaluation run yet.")
    if store.has_shipment():
        st.download_button("Export audit trail", view.audit_csv(store), key="export_audit", mime="text/csv",
                           file_name="cargolint_audit_" + store.export_filename("csv").removeprefix("cargolint_"),
                           on_click="ignore")
    st.caption("Full history: tests/eval/cn8_eval_history.json and tests/eval/cn8_eval.md.")


# --------------------------------------------------------------------------- the page
def render(store: Any, kb: Any, main_page: Any = None) -> None:
    job = runner.current_job()
    if job is not None and job.done:
        runner.finish(store, kb)   # reruns the app; the queue moves on from either page
    head = st.columns([5, 2], vertical_alignment="center")
    head[0].markdown("### CargoLint · Admin")
    if main_page is not None:
        head[1].page_link(main_page, label="← Back to shipment")
    st.caption("For the operator and course evaluators. The clerk's work happens on the shipment page.")
    st.caption(f"Model: {get_settings().chat_model} via OpenRouter")   # here only, not on the main page
    section = st.segmented_control("Section", SECTIONS, key="admin_section", default="Rules", required=True,
                                   persist_state="session", label_visibility="collapsed")
    if section == "Rules":
        _rules(store)
    elif section == "Data":
        _data(kb)
    elif section == "Cost":
        _cost(store)
    elif section == "Quality":
        _quality(store)
    else:
        st.session_state.setdefault("chat", [])
        chat.render(store, kb)
