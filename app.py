"""CargoLint — Streamlit entry point.

Two pages under a hidden navigation (contracts/ui.md §1). The main page is the clerk's one page: header, upload,
summary bar, decision table and the shipper email draft, with no sidebar and no chat. The Admin page holds the rules,
data, cost, quality and the agent chat. The pages link to each other; no page list is shown.
All line data is read from the LineStore; nothing in the UI is reconstructed from model prose.
"""
from __future__ import annotations

import hmac

import streamlit as st

from agent.config import configure_logging, get_settings
from agent.store import LineStore
from rag.demo_store import DemoStoreError, demo_store_needed, fetch_demo_store
from rag.retriever import IndexMismatchError

st.set_page_config(page_title="CargoLint", page_icon="📦", layout="wide")


@st.cache_resource(show_spinner="Loading the knowledge base…")
def load_kb():
    """Once per server process. A hosted demo first fetches its store when it is missing (feature 011)."""
    from rag.loader import open_knowledge_base

    settings = get_settings()
    if demo_store_needed(settings.demo_store_url):
        with st.spinner("Downloading the demo knowledge base…"):
            fetch_demo_store(settings.demo_store_url, settings.demo_store_sha256)
    return open_knowledge_base(settings)


def get_store(kb) -> LineStore:
    backend = st.session_state.setdefault("store_backend", {})
    return LineStore(backend=backend, index=kb.index)


def password_ok(password: str) -> bool:
    """True when no demo password is set or this session has entered it; until then only the password field shows
    (feature 011)."""
    if not password or st.session_state.get("gate_ok"):
        return True
    entered = st.text_input("Demo password", type="password", key="gate_password")
    if entered and hmac.compare_digest(entered.encode(), password.encode()):
        st.session_state["gate_ok"] = True
        st.rerun()
    if entered:
        st.error("Wrong password.")
    return False


def main() -> None:
    configure_logging()
    settings = get_settings()
    if not password_ok(settings.app_password):
        st.stop()
    if not settings.api_key:
        st.error("OPENROUTER_API_KEY is not set. Set it as an operating-system environment variable and restart CargoLint; "
                 "on Streamlit Community Cloud, add it to the app's Secrets settings and reboot the app.", icon="🔑")
        st.stop()
    try:
        kb = load_kb()
    except IndexMismatchError as exc:
        st.error(f"Knowledge base problem: {exc}", icon="📚")
        st.code("python -m rag.loader --demo", language="bash")
        st.stop()
    except DemoStoreError as exc:
        st.error(f"Demo knowledge base: {exc}", icon="📚")
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
