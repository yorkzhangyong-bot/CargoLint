"""The decision table (feature 005, contracts/ui.md §4): one row per line, built from the view module, in file order
and in pages of 25. A row opens in place under itself; grey rows do not open."""
from __future__ import annotations

import math
from typing import Any

import streamlit as st

from ui import expand, view

PAGE_SIZE = 25
COLS = [0.32, 0.38, 3.3, 1.35, 2.25, 0.85]
HEADERS = ("✓", "#", "Description", "Code", "Status", "Action")
EMPTY = "No lines yet — drop a file or type one description"


def _toggle(line_no: int) -> None:
    current = st.session_state.get("selected_line_no")
    expand.forget(current)        # a row opens again on its pre-selection
    expand.forget(line_no)
    st.session_state["selected_line_no"] = None if current == line_no else line_no


def render_header() -> None:
    for col, name in zip(st.columns(COLS, vertical_alignment="bottom"), HEADERS):
        col.caption(f"**{name}**")


def render(store: Any, kb: Any, statuses: dict[int, view.LineStatus]) -> None:
    render_header()
    lines = store.lines if store.has_shipment() else []
    if not lines:
        st.caption(EMPTY)
        return
    pages = max(1, math.ceil(len(lines) / PAGE_SIZE))
    page = min(max(int(st.session_state.get("table_page") or 1), 1), pages)
    for line in lines[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]:
        status = statuses[line.line_no]
        _row(store, line, status)
        if st.session_state.get("selected_line_no") == line.line_no and status.colour != "grey":
            _open_row(store, kb, line, status)
    if pages > 1:
        st.segmented_control("Page", list(range(1, pages + 1)), key="table_page", default=1, required=True)


def _accept_cell(col: Any, line: Any, status: view.LineStatus) -> None:
    """The Accept control: enabled on Ready rows for "Accept n selected" (FR-006); locked on red rows, with the lock
    reason as its help (FR-011); empty otherwise."""
    if status.selectable:
        col.checkbox("Accept", key=f"accept_{line.line_no}", label_visibility="collapsed",
                     help="Tick to accept this line with the other ticked Ready lines")
    elif status.lock_reason:
        col.checkbox("Accept", key=f"accept_{line.line_no}", disabled=True, help=view.md_escape(status.lock_reason),
                     label_visibility="collapsed")


def _row(store: Any, line: Any, status: view.LineStatus) -> None:
    n = line.line_no
    c = st.columns(COLS, vertical_alignment="center")
    _accept_cell(c[0], line, status)
    c[1].markdown(f"**{n}**")
    text = view.md_escape(line.current.display_text) or "_(no readable text)_"
    if status.colour == "grey":
        c[2].markdown(text)
    else:
        c[2].button(text, key=f"open_{n}", type="tertiary", on_click=_toggle, args=(n,), help="Open the line")
    if status.lock_reason:
        c[2].caption(f":material/lock: {view.md_escape(status.lock_reason)}")
    code = view.code_display(store, line)
    c[3].markdown(f"`{code.text}`")
    if code.note:
        c[3].caption(code.note)
    c[4].markdown(f"{status.dot} {view.md_escape(status.text)}")
    if status.action:
        c[5].button(status.action, key=f"act_{n}", on_click=_toggle, args=(n,))


def _open_row(store: Any, kb: Any, line: Any, status: view.LineStatus) -> None:
    with st.container(border=True):
        top = st.columns([6, 1])
        top[1].button("▲ close", key=f"close_{line.line_no}", type="tertiary", on_click=_toggle, args=(line.line_no,))
        expand.render(store, kb, line, status)
