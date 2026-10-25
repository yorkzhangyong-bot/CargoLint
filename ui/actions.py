"""Batch acceptance (feature 005, research R-06), with no Streamlit import: "Accept all K ready" and "Accept n
selected" confirm each Ready line with feature 004's confirmations, so its codes are the clerk's and a threshold change
no longer touches them. No model call and no job."""
from __future__ import annotations

from typing import Any

from ui import view


def accept_ready(store: Any, line_nos: list[int] | None = None) -> int:
    """Confirm every Ready line, or only the Ready lines among `line_nos`; returns how many were confirmed. A written
    TARIC-10 is confirmed with `confirm_taric10`, which confirms its CN-8 too; a line that stops at 8 digits with
    `confirm_cn8`. Any other line number is ignored."""
    wanted = None if line_nos is None else set(line_nos)
    confirmed = 0
    for line in store.lines:
        if wanted is not None and line.line_no not in wanted:
            continue
        if not view.line_status(store, line).selectable:   # Ready: green and not yet Accepted
            continue
        taric10, cn8 = store.decided_taric10(line), store.decided_cn8(line)
        if taric10:
            store.confirm_taric10(line.line_no, taric10)
        elif cn8:
            store.confirm_cn8(line.line_no, cn8)
        else:
            continue
        confirmed += 1
    return confirmed
