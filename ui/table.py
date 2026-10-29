"""The list (feature 012, FR-009 to FR-011; feature 005's decision table before it): one row per line, built from
columns and a status badge, sorted ask shipper → review → ready, then the accepted lines and the lines still being
checked, 50 a page. The open line unfolds in an expander under its row; a line still being checked does not open.
Every cell comes from ui/view.py."""
from __future__ import annotations

import math
from typing import Any

import streamlit as st

from ui import expand, view

PAGE_SIZE = 50
COLS = [0.4, 1.2, 3, 3, 1.4, 0.8]
COL_GAP = "xsmall"               # small gaps between the columns (the author's polish)
HEADERS = ("#", "Status", "Description", "Need / description", "HS code", "Conf.")
SHOW = "show_open_line"          # set when a line opens by itself: the list shows that line's page once
ROW_GAP = 1                      # px: 45 px rows 46 px apart, as in the final picture


def _toggle(line_no: int) -> None:
    current = st.session_state.get("selected_line_no")
    expand.forget(current)        # a line opens again on its pre-selection
    expand.forget(line_no)
    st.session_state["selected_line_no"] = None if current == line_no else line_no


def _folded(line_no: int) -> None:
    """The open line's expander was folded: the line closes, as a click on its description does."""
    if not st.session_state.get(f"row_{line_no}"):
        expand.forget(line_no)
        if st.session_state.get("selected_line_no") == line_no:
            st.session_state["selected_line_no"] = None


def _row(store: Any, line: Any, status: view.LineStatus, selected: str | None) -> None:
    n = line.line_no
    cells = view.row_cells(store, line, status, selected)
    with st.container(key=f"line_{n}"):
        c = st.columns(COLS, vertical_alignment="center", gap=COL_GAP)
        c[0].markdown(f"{n}")
        c[1].badge(f"**{cells.badge}**", color=cells.colour, help=view.md_escape(status.text))
        text = view.md_escape(cells.filed) or "_(no readable text)_"
        if status.colour == "grey":
            c[2].markdown(text)
        else:
            c[2].button(text, key=f"open_{n}", type="tertiary", on_click=_toggle, args=(n,), help="Open the line")
        c[3].caption(view.md_escape(cells.need))
        c[4].markdown(f"`{cells.code}`" if cells.code != "—" else "—")
        if cells.note:
            c[4].caption(cells.note)
        c[5].markdown(cells.conf)


def render(store: Any, kb: Any, statuses: dict[int, view.LineStatus]) -> None:
    lines = sorted(store.lines, key=lambda l: (view.sort_group(statuses[l.line_no]), l.line_no))
    pages = max(1, math.ceil(len(lines) / PAGE_SIZE))
    selected = st.session_state.get("selected_line_no")
    if st.session_state.pop(SHOW, False):
        at = next((i for i, l in enumerate(lines) if l.line_no == selected), None)
        if at is not None:
            st.session_state["table_page"] = at // PAGE_SIZE + 1
    page = min(max(int(st.session_state.get("table_page") or 1), 1), pages)
    st.markdown(f"**Lines (sorted: ask shipper → review → ready)** · Page {page} of {pages}")
    for col, name in zip(st.columns(COLS, vertical_alignment="bottom", gap=COL_GAP), HEADERS):
        col.caption(f"**{name}**")
    with st.container(key="lines", gap=ROW_GAP):
        for line in lines[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]:
            n, status = line.line_no, statuses[line.line_no]
            is_open = selected == n and status.colour != "grey"
            _row(store, line, status, expand.selected_code(line) if is_open else None)
            if is_open:
                label = f"Line {n} · {view.md_escape(view.cut(line.current.display_text, 80))}"
                with st.expander(label, expanded=True, key=f"row_{n}", on_change=_folded, args=(n,)):
                    expand.render(store, kb, line, status)
    if pages > 1:
        st.session_state["table_page"] = page        # within range for this shipment
        st.segmented_control("Page", list(range(1, pages + 1)), key="table_page", required=True)
