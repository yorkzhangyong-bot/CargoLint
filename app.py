"""CargoLint — Streamlit entry point.

Layout per contracts/ui.md: sidebar (upload, shipment, rules, knowledge base, cost, export), a compact
assistant rail on the left and, once a shipment exists, the review table with the detail card on the right.
All line data is read from the LineStore; nothing in the UI is reconstructed from model prose.
"""
from __future__ import annotations

import streamlit as st

from agent.config import configure_logging, get_settings
from agent.store import LineStore
from rag.retriever import IndexMismatchError

st.set_page_config(page_title="CargoLint", page_icon="📦", layout="wide", initial_sidebar_state="expanded")


@st.cache_resource(show_spinner="Loading the knowledge base…")
def load_kb():
    from rag.loader import open_knowledge_base

    return open_knowledge_base(get_settings())


def get_store(kb) -> LineStore:
    backend = st.session_state.setdefault("store_backend", {})
    return LineStore(backend=backend, index=kb.index)


def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.api_key:
        st.error("OPENROUTER_API_KEY is not set. Put it in the environment or in a `.env` file at the project root and restart.", icon="🔑")
        st.stop()
    try:
        kb = load_kb()
    except IndexMismatchError as exc:
        st.error(f"Knowledge base problem: {exc}", icon="📚")
        st.code("python -m rag.loader --demo", language="bash")
        st.stop()
    store = get_store(kb)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("selected_line_no", None)

    from ui import chat, detail, review, sidebar

    sidebar.render(store, kb)
    job = st.session_state.get("job")
    live = job is not None and not job.done
    has_lines = store.has_shipment() and bool(store.lines)
    st.session_state["layout_has_lines"] = has_lines   # the live-progress fragment reruns the app when this flips
    if has_lines:
        left, right = st.columns([32, 68], gap="medium")
        with left:
            chat.render(store, kb)
        with right:
            review.render(store, kb, live=live)
            detail.render(store, kb)
    else:
        left, _ = st.columns([2, 1])
        with left:
            chat.render(store, kb)


main()
