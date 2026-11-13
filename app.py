"""CargoLint — Streamlit entry point.

Two pages under a hidden navigation (contracts/ui.md §1). The main page is the clerk's one page: header, upload,
summary bar, decision table and the shipper email draft, with no sidebar and no chat. The Admin page holds the rules,
data, cost, quality and the agent chat. The pages link to each other; no page list is shown.
All line data is read from the LineStore; nothing in the UI is reconstructed from model prose.
"""
from __future__ import annotations

import hmac
import logging

import streamlit as st

from agent.config import configure_logging, get_settings
from agent.store import LineStore
from rag.demo_store import DemoStoreError, demo_store_needed, fetch_demo_store
from rag.refresh import RefreshError, fetch_releases, releases_needed
from rag.retriever import IndexMismatchError

st.set_page_config(page_title="CargoLint", page_icon="📦", layout="wide")

DEMO_NOTICE = (   # feature 011: shown when CARGOLINT_DEMO_NOTICE is "on"
    "This is a demo for evaluation, not customs advice. Every code and rewrite must be checked by the declarant before "
    "use.",
    "CargoLint stores nothing you upload. Each line is sent to an AI model through OpenRouter (US-hosted) to be classified. "
    "Please use lists without personal data such as names, phone numbers or email addresses.",
    "Your shipment lives only in this browser session: export your results before you close the tab.",
)


@st.cache_resource(show_spinner="Loading the knowledge base…")
def load_kb():
    """Once per server process. A hosted demo first fetches its knowledge base when it is missing: the newest complete
    release of each kind when CARGOLINT_RELEASE_REPO is set (feature 013), else the demo archive of feature 011. A TARIC
    release that cannot be fetched leaves the app running without TARIC, with the reason kept on the knowledge base;
    an EBTI release that cannot be fetched raises RefreshError, which main() shows before it stops."""
    from rag.loader import open_knowledge_base

    settings = get_settings()
    failures: dict[str, str] = {}
    if settings.release_repo:
        if settings.demo_store_url:
            logging.getLogger("app").info("CARGOLINT_RELEASE_REPO is set: the demo store settings of feature 011 "
                                          "(CARGOLINT_DEMO_STORE_URL, CARGOLINT_DEMO_STORE_SHA256) are ignored")
        if releases_needed(settings):
            with st.spinner("Downloading the knowledge base releases…"):
                failures = fetch_releases(settings).failed
    elif demo_store_needed(settings.demo_store_url):
        with st.spinner("Downloading the demo knowledge base…"):
            fetch_demo_store(settings.demo_store_url, settings.demo_store_sha256)
    kb = open_knowledge_base(settings)
    kb.fetch_failures = failures
    return kb


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
    if settings.demo_notice:
        with st.expander("Before you upload", expanded=True):
            for line in DEMO_NOTICE:
                st.markdown(line)
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
    except RefreshError as exc:
        st.error(f"Knowledge base release: {exc}", icon="📚")
        st.stop()
    for kind, reason in kb.fetch_failures.items():   # feature 013: a TARIC release not fetched; the app runs without it
        st.error(f"Knowledge base release: {kind}: {reason}", icon="📚")
    store = get_store(kb)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("selected_line_no", None)

    from ui import admin, main_page

    pages: dict = {}

    def shipment() -> None:
        main_page.render(store, kb)

    def admin_page() -> None:
        admin.render(store, kb, pages["main"])

    pages["main"] = st.Page(shipment, title="CargoLint", default=True)
    pages["admin"] = st.Page(admin_page, title="CargoLint · Admin", url_path="admin")
    st.navigation([pages["main"], pages["admin"]], position="hidden").run()


main()
