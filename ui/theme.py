"""Layout CSS for the main page, the one exception to native Streamlit (constitution 1.10.0, Principle VI): a single
style block, injected once, that adjusts only spacing, padding, margins, font sizes, widths and card heights. No HTML
elements, no JavaScript, no components and no change of behaviour; tests/unit/test_native_ui.py checks all of it."""
from __future__ import annotations

import streamlit as st

CSS = """
/* The page starts 1rem below the top; Streamlit's header bar above it is transparent and lets clicks through. */
[data-testid="stMainBlockContainer"] { padding-top: 1rem !important; }
/* The Origin block and the upload box with less padding, and a tab's content closer to its tab. */
.st-key-origin, .st-key-upload_box { padding: 0.6rem 1rem !important; }
[data-testid="stTabPanel"] { padding-top: 0.5rem !important; }
/* Count cards about 90 px tall: the label, then the count right under it, with little room below. */
[class*="st-key-count_"] { padding: 0.8rem 1rem 0.6rem !important; }
[class*="st-key-count_"] h3 { padding-top: 0 !important; }
"""


def apply() -> None:
    """Inject the layout CSS. The main page calls it once per run, inside a container with no gap, so it takes no
    room."""
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
