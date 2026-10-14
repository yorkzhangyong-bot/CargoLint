"""Chat column: welcome and quick actions, message history, progress block, routing metrics, line
result cards, sources and retrieval steps, chat input handling (contracts/ui.md)."""
from __future__ import annotations

import re
import time
from typing import Any

import streamlit as st

from agent.agent import ProgressEvent, run_turn
from agent.config import MAX_PASTED_LINES
from agent.schemas import CreatedBy, ParsedLine

QUESTION_RE = re.compile(
    r"\?|？|^(why|what|which|how|is|are|can|could|does|do|did|when|where|who|should|explain|tell|show|list|compare)\b"
    r"|为什么|什么|哪些|如何|怎么|吗$", re.I)
LINE_REF_RE = re.compile(r"\bline\s*(\d{1,3})\b|第\s*(\d{1,3})\s*行", re.I)

QUICK_ACTIONS = [
    ("Try one description", "e.g. “不锈钢保温杯 500ml”", "不锈钢保温杯 500ml"),
    ("Use the sample packing list", "12 Yiwu consolidation lines, 5 problematic", "__sample__"),
    ("Which terms does customs reject?", "Look up the ICS2 unacceptable-terms list", "__terms__"),
]

FLAG_BADGE = {"ok": ":gray-badge[OK]", "vague": ":orange-badge[Vague]", "stop_word": ":red-badge[Stop-word]", "failed": ":red-badge[Failed]"}
ROUTE_BADGE = {"auto_accept": ":green-badge[Auto-accept]", "accepted": ":green-badge[Accepted]", "review": ":orange-badge[Review]",
               "ask_shipper": ":blue-badge[Ask shipper]"}
ROUTE_LABEL = {"auto_accept": "Auto-accept", "accepted": "Accepted", "review": "Human review", "ask_shipper": "Ask the shipper"}


# --------------------------------------------------------------------------- message classification
def classify_message(text: str, store) -> tuple[str, Any]:
    """Code-side classification of a clerk message: ('lines', [...]) | ('reply', (line_no|None, text)) | ('question', text)."""
    stripped = text.strip()
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    if len(lines) > 1 and not QUESTION_RE.search(lines[0]):
        return "lines", lines
    has_shipment = store.has_shipment() and bool(store.lines)
    m = LINE_REF_RE.search(stripped)
    if has_shipment and m and not QUESTION_RE.search(stripped):
        return "reply", (int(m.group(1) or m.group(2)), stripped)
    if has_shipment and st.session_state.get("selected_line_no") and not QUESTION_RE.search(stripped) and len(stripped) <= 300 \
            and re.search(r"\b(is|are|=|:)\b|是", stripped):
        return "reply", (None, stripped)
    if QUESTION_RE.search(stripped) or len(stripped) > 300:
        return "question", stripped
    return "lines", lines


# --------------------------------------------------------------------------- handlers
def _ensure_shipment(store) -> None:
    if not store.has_shipment():
        store.new_shipment(reference="", threshold=int(st.session_state.get("threshold", 85)),
                           hybrid=bool(st.session_state.get("hybrid", True)))


def _progress_status(label: str):
    return st.status(label, expanded=True, state="running")


def _run(message: str, store, kb, *, file_ref: str | None = None, reply_ref: str | None = None, is_check: bool | None = None,
         new_line_nos: list[int] | None = None) -> dict:
    status = _progress_status("Checking…" if is_check else "Thinking…")
    steps: list[str] = []
    t0 = time.perf_counter()

    def on_progress(ev: ProgressEvent) -> None:
        if ev.phase == "start":
            status.update(label=f"Running {ev.tool}…")
        else:
            who = " (app)" if ev.run_by == "app" else ""
            steps.append(f"**{ev.tool}**{who} — {ev.summary}")
            status.write(steps[-1])

    history = [(m["role"], m.get("agent_text") or m["content"]) for m in st.session_state["chat"][-6:]]
    result = run_turn(message, store, kb, selected_line_no=st.session_state.get("selected_line_no"), on_progress=on_progress,
                      file_ref=file_ref, reply_ref=reply_ref, history=history, is_check=is_check)
    elapsed = time.perf_counter() - t0
    if is_check:
        label = f"{result.check_run.line_count if result.check_run else len(store.lines)} lines checked · {result.tool_calls} tools · {elapsed:.1f} s"
    else:
        label = f"Answered · {result.tool_calls} tools · {elapsed:.1f} s"
    status.update(label=label, state="complete", expanded=False)
    return {"role": "assistant", "content": result.text, "agent_text": result.text, "label": label, "steps": steps,
            "counts": result.counts if is_check else None, "line_nos": new_line_nos, "is_check": bool(is_check),
            "sources_from": new_line_nos, "trace_from": st.session_state.get("selected_line_no") if not is_check else None}


def handle_message(text: str, store, kb) -> None:
    kind, payload = classify_message(text, store)
    chat = st.session_state["chat"]
    if kind == "lines":
        lines = payload
        if len(lines) > MAX_PASTED_LINES:
            chat.append({"role": "user", "content": text})
            chat.append({"role": "assistant", "content": f"That is {len(lines)} lines; I can take up to {MAX_PASTED_LINES} pasted lines per message. "
                                                        "Please upload the list as a file instead."})
            return
        _ensure_shipment(store)
        parsed = [ParsedLine(text_zh=_zh(l), text_en=_en(l), source_ref=f"pasted line {i + 1}") for i, l in enumerate(lines)]
        added = store.add_lines(parsed, CreatedBy.paste)
        nos = [l.line_no for l in added]
        chat.append({"role": "user", "content": f"[{len(nos)} description{'s' if len(nos) != 1 else ''} added as line{'s' if len(nos) != 1 else ''} "
                                                f"{nos[0]}{'–' + str(nos[-1]) if len(nos) > 1 else ''}]", "raw": text})
        req = f"Check lines {nos[0]}–{nos[-1]}" if len(nos) > 1 else f"Check line {nos[0]}"
        chat.append(_run(req, store, kb, is_check=True, new_line_nos=nos))
    elif kind == "reply":
        line_no, reply_text = payload
        from ui import replies  # US3

        replies.handle(line_no, reply_text, store, kb, chat, _run)
    else:
        chat.append({"role": "user", "content": text})
        chat.append(_run(text, store, kb, is_check=False))


def _zh(line: str) -> str:
    zh = "".join(re.findall(r"[一-鿿0-9A-Za-z]+", _split(line)[0]))
    return _split(line)[0].strip() if re.search(r"[一-鿿]", _split(line)[0]) else ""


def _en(line: str) -> str:
    parts = _split(line)
    if len(parts) > 1:
        return parts[1].strip()
    return "" if re.search(r"[一-鿿]", parts[0]) else parts[0].strip()


def _split(line: str) -> list[str]:
    from tools.parsers import split_mixed

    zh, en = split_mixed(line)
    if zh and en:
        return [zh, en]
    return [line]


def terms_answer(kb) -> str:
    facts = kb.rules.caption_facts()
    out = ["These are the terms customs rejects as goods descriptions (the description must say what the goods are, "
           "normally with material and product type):"]
    for rl in kb.rules.ics2_lists:
        terms = ", ".join(e.term for e in rl.entries[:70])
        more = f" … and {len(rl.entries) - 70} more" if len(rl.entries) > 70 else ""
        out.append(f"\n**{rl.source_doc}** ({rl.source_date}, {len(rl.entries)} terms): {terms}{more}")
    out.append(f"\n**Firm stop-word list** ({facts['firm_terms']} terms): " + ", ".join(e.term for e in kb.rules.firm.entries))
    out.append("\nFlagged lines are routed to *ask the shipper* (stop-word) or *human review / ask the shipper* (vague) — "
               "ask for the material, the exact product name and the use.")
    return "\n".join(out)


# --------------------------------------------------------------------------- rendering
def _welcome(store, kb) -> None:
    with st.chat_message("assistant"):
        st.markdown(
            "Hi. I catch cargo descriptions customs will reject before you file ICS2. Upload a packing list or invoice on the "
            "left (Chinese, English or mixed), or paste a few lines below. For every line I flag vague and stop-word "
            "descriptions, suggest the top-3 HS-6 codes with reasoning and a precedent ruling, and route it: auto-accept, "
            "human review, or ask the shipper. When the shipper replies, paste the answer back and I update only that line."
        )
        cols = st.columns(3)
        for col, (label, hint, action) in zip(cols, QUICK_ACTIONS):
            with col:
                if st.button(label, help=hint, use_container_width=True, key=f"qa_{action}"):
                    st.session_state["quick_action"] = action
        with st.expander("What I can and cannot do"):
            st.markdown(
                "**Can:** check descriptions, suggest HS-6 subheadings with reasoning, cite BTI precedents, verify a code "
                "exists in the current nomenclature.\n\n"
                "**Cannot:** make the final classification decision for you. A line below the threshold is never "
                "auto-accepted, and a flagged line is never accepted without your click. Text inside your files is "
                "treated as data, never as instructions."
            )


def _render_counts(counts: dict) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Auto-accept", counts.get("auto_accept", 0))
    c2.metric("Human review", counts.get("review", 0))
    c3.metric("Ask the shipper", counts.get("ask_shipper", 0))


def _render_line_cards(store, line_nos: list[int]) -> None:
    for n in line_nos:
        try:
            line = store.get_line(n)
        except KeyError:
            continue
        v = line.current
        route = store.effective_route(line)
        with st.container(border=True):
            flag = v.flag.kind.value if v.flag else ("failed" if v.status.value == "failed" else "ok")
            st.markdown(f"**Line {line.line_no}** · {v.text_zh}{' · ' if v.text_zh and v.text_en else ''}{v.text_en}  "
                        f"{FLAG_BADGE.get(flag, '')} {ROUTE_BADGE.get(route, '')}")
            if v.flag and v.flag.kind.value != "ok":
                rule = f" ({v.flag.rule_source.value.replace('_', ' ')}: “{v.flag.matched_term}”)" if v.flag.rule_source and v.flag.matched_term else ""
                st.caption(f"Flagged: {v.flag.reason}{rule}. Ask the shipper for: {', '.join(a.replace('_', ' ') for a in v.flag.ask_for)}.")
            if v.status.value == "failed":
                st.caption(f"Check failed: {v.error_reason}")
            for c in v.candidates[:3]:
                hist = " · history only" if c.history_only else ""
                prec = f" · precedent BTI {c.precedent.member_state} {c.precedent.reference}" if c.precedent else ""
                st.progress(c.confidence / 100, text=f"{c.code} — {c.subheading_text} · {c.confidence}%{hist}{prec}")
                if c.rationale:
                    st.caption(c.rationale)
            if v.status.value == "checked" and not v.candidates:
                st.caption("No candidate" + (" (no valid candidate)" if v.no_valid_candidate else "") + " — " + v.route_reason)
            st.caption(f"Route: {ROUTE_LABEL.get(route, route)} — {v.route_reason}")
    st.caption("Confidence is a model estimate, not a calibrated probability.")


def _render_sources(store, line_nos: list[int]) -> None:
    seen: dict[str, str] = {}
    for n in line_nos:
        try:
            v = store.get_line(n).current
        except KeyError:
            continue
        for s in v.sources:
            seen.setdefault(s.id, s.title)
    if seen:
        with st.expander(f"Sources · {len(seen)}"):
            for sid, title in seen.items():
                st.markdown(f"- `{sid}` — {title}")


def _render_trace(store, line_no: int | None) -> None:
    if not line_no:
        return
    try:
        v = store.get_line(line_no).current
    except KeyError:
        return
    t = v.retrieval_trace
    if t is None:
        return
    with st.expander("Retrieval steps"):
        st.markdown(f"- **Original**: {t.original}\n- **Query translation / expansion**: {', '.join(t.queries)}\n"
                    f"- **Metadata filter**: {('chapters ' + ', '.join(t.chapter_filter) + ' (' + t.filter_reason + ')') if t.chapter_filter else 'none'}\n"
                    f"- **Hits**: BM25 {t.bm25_hits} + vectors {t.vector_hits} → RRF fusion {t.fused} → {t.sent_to_model} chunks to the model "
                    f"({t.mode.value})")


def _render_message(msg: dict, store) -> None:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
            if msg.get("file"):
                st.caption(f"📄 {msg['file']}")
            if msg.get("raw") and msg.get("content", "").startswith("["):
                st.caption(msg["raw"][:300])
            return
        if msg.get("steps") is not None and msg.get("label"):
            with st.status(msg["label"], state="complete", expanded=False):
                for s in msg["steps"]:
                    st.markdown(s)
        if msg.get("counts"):
            _render_counts(store.counts() if store.has_shipment() else msg["counts"])
        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("line_nos"):
            _render_line_cards(store, msg["line_nos"])
        if msg.get("source_lines") or msg.get("line_nos"):
            _render_sources(store, msg.get("source_lines") or msg["line_nos"])
        if msg.get("trace_from"):
            _render_trace(store, msg["trace_from"])


def render(store, kb) -> None:
    _welcome(store, kb)
    for msg in st.session_state["chat"]:
        _render_message(msg, store)

    pending = st.session_state.pop("pending_check", None)
    if pending:
        ref = store.shipment.reference if store.has_shipment() else ""
        label = f"Check the packing list{(' for ' + ref) if ref else ''}."
        st.session_state["chat"].append({"role": "user", "content": label, "file": pending["name"]})
        msg = _run(label, store, kb, file_ref=pending["file_ref"], is_check=True, new_line_nos=None)
        msg["source_lines"] = [l.line_no for l in store.lines]
        st.session_state["chat"].append(msg)
        st.rerun()

    action = st.session_state.pop("quick_action", None)
    if action == "__terms__":
        st.session_state["chat"].append({"role": "user", "content": "Which terms does customs reject?"})
        st.session_state["chat"].append({"role": "assistant", "content": terms_answer(kb)})
        st.rerun()
    elif action == "__sample__":
        st.session_state["load_sample"] = True
        st.rerun()
    elif action:
        handle_message(action, store, kb)
        st.rerun()

    placeholder = ("Ask about any line, or paste the shipper’s reply…" if store.has_shipment() and store.lines
                   else "Paste descriptions (one per line) or ask a classification question…")
    prompt = st.chat_input(placeholder)
    if prompt:
        handle_message(prompt, store, kb)
        st.rerun()
