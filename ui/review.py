"""Review column: compact header, filter pills, the review list (needs-action first; proportional columns that wrap
instead of clipping), paging and row selection (FR-024, FR-033, FR-034). Re-renders every second while a check
is running so rows fill in."""
from __future__ import annotations

import math

import streamlit as st

FILTERS = ["All", "Needs action", "Accepted"]
FLAG_LABEL = {"ok": "OK", "vague": "Vague", "stop_word": "Stop-word", "failed": "Failed", "pending": "…"}
ROUTE_LABEL = {"auto_accept": "Auto-accept", "accepted": "Accepted", "review": "Review", "ask_shipper": "Ask shipper", "pending": "…"}
FLAG_BADGE = {"OK": ":gray-badge[OK]", "Vague": ":orange-badge[Vague]", "Stop-word": ":red-badge[Stop-word]", "Failed": ":red-badge[Failed]",
              "…": ":gray[checking…]"}
ROUTE_BADGE = {"Auto-accept": ":green-badge[Auto-accept]", "Accepted": ":green-badge[Accepted]", "Review": ":orange-badge[Review]",
               "Ask shipper": ":blue-badge[Ask shipper]", "…": ":gray[…]"}
PAGE_SIZE = 25
LIST_PX = 420          # scroll height of the list once it holds more than SCROLL_FROM rows
SCROLL_FROM = 8
COLS = [0.42, 3.3, 0.95, 1.5, 1.15, 0.5]   # #, description, flag, HS-6 · confidence, route, open


def table_rows(store) -> list[dict]:
    rows = []
    for line in store.lines:
        v = line.current
        pending = v.status.value == "pending"
        route = "pending" if pending else store.effective_route(line)
        flag = "failed" if v.status.value == "failed" else ("pending" if pending or v.flag is None else v.flag.kind.value)
        desc = " · ".join(t for t in (v.text_zh, v.text_en) if t)
        rows.append({
            "line_no": line.line_no, "description": desc, "text_zh": v.text_zh, "text_en": v.text_en, "qty": line.qty or "",
            "flag": FLAG_LABEL[flag], "hs6": v.top_code or ("…" if pending else "—"), "confidence": (v.top_confidence or 0) / 100.0,
            "route": ROUTE_LABEL.get(route, route), "needs_action": (not pending) and store.needs_action(line),
            "pending": pending, "version": v.version_no,
        })
    rows.sort(key=lambda r: (0 if r["needs_action"] else (1 if not r["pending"] else 2), r["line_no"]))
    return rows


def filter_rows(rows: list[dict], name: str) -> list[dict]:
    if name == "Needs action":
        return [r for r in rows if r["needs_action"]]
    if name == "Accepted":
        return [r for r in rows if not r["needs_action"] and not r["pending"]]
    return list(rows)


def next_needs_action(store, current: int | None, direction: int = 1) -> int | None:
    rows = [r["line_no"] for r in table_rows(store) if r["needs_action"]]
    if not rows:
        return None
    if current not in rows:
        return rows[0] if direction > 0 else rows[-1]
    return rows[(rows.index(current) + direction) % len(rows)]


def reset_selection() -> None:
    """Called when the selected line changes outside the list: the list jumps to the page holding it."""
    st.session_state["review_follow"] = True


def _description(r: dict) -> str:
    qty = f" :gray[· {r['qty']}]" if r["qty"] else ""
    if r["text_zh"] and r["text_en"]:
        return f"{r['text_zh']}  \n{r['text_en']}{qty}"
    return f"{r['text_zh'] or r['text_en'] or ':gray[(unreadable)]'}{qty}"


def _row(r: dict, selected: bool) -> bool:
    c = st.columns(COLS, vertical_alignment="center", gap="small")
    c[0].markdown(f"**{r['line_no']}**" if selected else f":gray[{r['line_no']}]")
    c[1].markdown(_description(r))
    c[2].markdown(FLAG_BADGE.get(r["flag"], r["flag"]))
    if r["pending"]:
        c[3].markdown(":gray[checking…]")
    elif r["hs6"] == "—":
        c[3].markdown(":gray[no code]")
    else:
        c[3].progress(r["confidence"], text=f"`{r['hs6']}` · {round(r['confidence'] * 100)}%")
    c[4].markdown(ROUTE_BADGE.get(r["route"], r["route"]))
    return c[5].button("", icon=":material/chevron_right:", key=f"open_{r['line_no']}", type="primary" if selected else "tertiary",
                       help=f"Open line {r['line_no']}")


def _page(shown: list[dict], selected: int | None, choice: str) -> list[dict]:
    pages = max(1, math.ceil(len(shown) / PAGE_SIZE))
    key = f"review_page_{choice}"
    if st.session_state.pop("review_follow", False) and selected is not None:
        idx = next((i for i, r in enumerate(shown) if r["line_no"] == selected), None)
        if idx is not None:
            st.session_state[key] = idx // PAGE_SIZE + 1
    if st.session_state.get(key, 1) > pages:
        st.session_state[key] = 1
    st.session_state.setdefault(key, 1)
    page = 1
    if pages > 1:
        labels = {p: f"{(p - 1) * PAGE_SIZE + 1}–{min(p * PAGE_SIZE, len(shown))}" for p in range(1, pages + 1)}
        page = st.segmented_control("Page", list(labels), format_func=lambda p: labels[p], key=key, label_visibility="collapsed") or 1
    return shown[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]


def render(store, kb, live: bool = False) -> None:
    @st.fragment(run_every=1.0 if live else None)
    def _list() -> None:
        s = store.shipment
        rows = table_rows(store)
        pending = sum(1 for r in rows if r["pending"])
        counts = {"needs_action": sum(1 for r in rows if r["needs_action"]),
                  "accepted": sum(1 for r in rows if not r["needs_action"] and not r["pending"])}
        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            st.markdown(f"#### Review · {s.reference}" if s.reference else "#### Review")
            bits = [b for b in (f"{s.origin} → {s.destination}" if s.origin and s.destination else None, s.mode,
                                f"{len(rows)} lines", f"{pending} still checking" if pending else "needs-action first") if b]
            st.caption(" · ".join(bits))
        with right:
            labels = {"All": f"All {len(rows)}", "Needs action": f"Needs action {counts['needs_action']}", "Accepted": f"Accepted {counts['accepted']}"}
            choice = st.segmented_control("Filter", FILTERS, default="All", format_func=lambda f: labels[f], key="review_filter",
                                          label_visibility="collapsed") or "All"
        shown = filter_rows(rows, choice)
        if not shown:
            st.info("No lines in this filter.")
            return
        selected = st.session_state.get("selected_line_no")
        if selected not in {r["line_no"] for r in rows}:
            first = next((r for r in shown if r["needs_action"]), shown[0])
            selected = st.session_state["selected_line_no"] = int(first["line_no"])
        page_rows = _page(shown, selected, choice)

        head = st.columns(COLS, gap="small")
        for col, title in zip(head, ("No.", "Description as filed", "Flag", "HS-6 · confidence", "Route", "")):
            col.caption(title)
        box = st.container(height=LIST_PX if len(page_rows) > SCROLL_FROM else "content", border=True, gap=None, autoscroll=False)
        with box:
            for r in page_rows:
                if _row(r, r["line_no"] == selected):
                    st.session_state["selected_line_no"] = int(r["line_no"])
                    st.rerun()  # whole app: the detail card lives outside this fragment

    _list()
