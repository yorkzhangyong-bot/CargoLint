"""CargoLint — Streamlit entry point.

Two pages under a hidden navigation (contracts/ui.md §1). The main page is the clerk's one page: header, upload,
summary bar, decision table and the shipper email draft, with no sidebar and no chat. The Admin page holds the rules,
data, cost, quality and the agent chat. The pages link to each other; no page list is shown.
All line data is read from the LineStore; nothing in the UI is reconstructed from model prose.
"""
from __future__ import annotations

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


def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.api_key:
        st.error("OPENROUTER_API_KEY is not set. Set it as an operating-system environment variable and restart CargoLint.", icon="🔑")
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

    from ui import admin, main_page

    pages: dict = {}

    def shipment() -> None:
        main_page.render(store, kb, pages["admin"])

    def admin_page() -> None:
        admin.render(store, kb, pages["main"])

    pages["main"] = st.Page(shipment, title="CargoLint", default=True)
    pages["admin"] = st.Page(admin_page, title="CargoLint · Admin", url_path="admin")
    st.navigation([pages["main"], pages["admin"]], position="hidden").run()


main()
