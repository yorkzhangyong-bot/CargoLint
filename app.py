"""CargoLint — Streamlit entry point.

Layout per contracts/ui.md: sidebar (uploader, shipment, rules, knowledge-base caption, cost, export),
a chat column and, once a shipment exists, the review column with the detail panel. All line data is
read from the LineStore; nothing in the UI is reconstructed from model prose.
"""
from __future__ import annotations

import importlib.util

import streamlit as st

from agent.config import configure_logging, get_settings
from agent.store import LineStore
from rag.retriever import IndexMismatchError

st.set_page_config(page_title="CargoLint", page_icon="📦", layout="wide")


@st.cache_resource(show_spinner="Loading the knowledge base…")
def load_kb():
    from rag.loader import open_knowledge_base

    return open_knowledge_base(get_settings())


def get_store(kb) -> LineStore:
    backend = st.session_state.setdefault("store_backend", {})
    return LineStore(backend=backend, index=kb.index)


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.api_key:
        st.error("OPENROUTER_API_KEY is not set. Put it in the environment or in a `.env` file at the project root and restart.")
        st.stop()
    try:
        kb = load_kb()
    except IndexMismatchError as exc:
        st.error(f"Knowledge base problem: {exc}")
        st.code("python -m rag.loader --demo", language="bash")
        st.stop()
    store = get_store(kb)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("selected_line_no", None)

    from ui import sidebar

    sidebar.render(store, kb)

    from ui import chat

    show_review = store.has_shipment() and bool(store.lines) and _has("ui.review")
    if show_review:
        left, right = st.columns([45, 55], gap="large")
        with left:
            chat.render(store, kb)
        with right:
            from ui import review

            review.render(store, kb)
            if _has("ui.detail"):
                from ui import detail

                detail.render(store, kb)
    else:
        chat.render(store, kb)


main()
