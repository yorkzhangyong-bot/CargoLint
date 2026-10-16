"""Assistant rail: compact welcome with quick-action cards, message history, live progress for the running
turn, structured check summaries, line cards for pasted lines, grouped sources and retrieval steps, chat input."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from agent.config import MAX_PASTED_LINES
from agent.schemas import CreatedBy, ParsedLine
from ui import jobs

QUESTION_RE = re.compile(
    r"\?|？|^(why|what|which|how|is|are|can|could|does|do|did|when|where|who|should|explain|tell|show|list|compare)\b"
    r"|为什么|什么|哪些|如何|怎么|吗$", re.I)
LINE_REF_RE = re.compile(r"\bline\s*(\d{1,3})\b|第\s*(\d{1,3})\s*行", re.I)

QUICK_ACTIONS = [
    ("Try one description", "e.g. 不锈钢保温杯 500ml", "不锈钢保温杯 500ml"),
    ("Use the sample packing list", "12 Yiwu consolidation lines, 5 problematic", "__sample__"),
    ("Which terms does customs reject?", "The ICS2 unacceptable-terms lists", "__terms__"),
]

FLAG_BADGE = {"ok": ":gray-badge[OK]", "vague": ":orange-badge[Vague]", "stop_word": ":red-badge[Stop-word]", "failed": ":red-badge[Failed]",
              "pending": ":gray-badge[…]"}
ROUTE_BADGE = {"auto_accept": ":green-badge[Auto-accept]", "accepted": ":green-badge[Accepted]", "review": ":orange-badge[Review]",
               "ask_shipper": ":blue-badge[Ask shipper]"}
ROUTE_LABEL = {"auto_accept": "Auto-accept", "accepted": "Accepted", "review": "Human review", "ask_shipper": "Ask the shipper"}
SOURCE_GROUP = {"nomenclature": "Nomenclature", "bti": "BTI rulings", "ics2_rule": "ICS2 rules", "firm_rule": "Firm list", "shipper_history": "Shipper history"}


# --------------------------------------------------------------------------- message classification
def classify_message(text: str, store) -> tuple[str, Any]:
    """('lines', [...]) | ('reply', (line_no|None, text)) | ('question', text) — decided in code, never by the model."""
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


# --------------------------------------------------------------------------- starting turns (background)
def _ensure_shipment(store) -> None:
    if not store.has_shipment():
        store.new_shipment(reference=st.session_state.get("reference", "") or "", threshold=int(st.session_state.get("threshold", 85)),
                           hybrid=bool(st.session_state.get("hybrid", True)))


def _start(message: str, store, kb, *, file_ref=None, reply_ref=None, is_check=None, new_line_nos=None, label_prefix=None, note=None,
           kind: str = "question") -> None:
    history = [(m["role"], m.get("agent_text") or m["content"]) for m in st.session_state["chat"][-6:] if m.get("role") in ("user", "assistant")]
    job = jobs.Job(kind=kind, message=message, is_check=bool(is_check), file_ref=file_ref, reply_ref=reply_ref, new_line_nos=new_line_nos,
                   label_prefix=label_prefix, selected_line_no=st.session_state.get("selected_line_no"), history=history, note=note)
    st.session_state["job"] = jobs.start(job, store, kb)
    return None


def handle_message(text: str, store, kb) -> None:
    kind, payload = classify_message(text, store)
    chat = st.session_state["chat"]
    if kind == "lines":
        lines = payload
        if len(lines) > MAX_PASTED_LINES:
            chat.append({"role": "user", "content": text})
            chat.append({"role": "assistant", "content": f"That is {len(lines)} lines; I can take up to {MAX_PASTED_LINES} pasted lines per "
                                                        "message. Please upload the list as a file instead."})
            return
        _ensure_shipment(store)
        parsed = [ParsedLine(text_zh=_zh(l), text_en=_en(l), source_ref=f"pasted line {i + 1}") for i, l in enumerate(lines)]
        added = store.add_lines(parsed, CreatedBy.paste)
        nos = [l.line_no for l in added]
        chat.append({"role": "user", "content": f"[{len(nos)} description{'s' if len(nos) != 1 else ''} added as line{'s' if len(nos) != 1 else ''} "
                                                f"{nos[0]}{'–' + str(nos[-1]) if len(nos) > 1 else ''}]", "raw": text})
        req = f"Check lines {nos[0]}–{nos[-1]}" if len(nos) > 1 else f"Check line {nos[0]}"
        _start(req, store, kb, is_check=True, new_line_nos=nos, kind="check")
    elif kind == "reply":
        from ui import replies

        replies.handle(payload[0], payload[1], store, kb, chat, _start)
    else:
        chat.append({"role": "user", "content": text})
        _start(text, store, kb, is_check=False, kind="question")


def _split(line: str) -> list[str]:
    from tools.parsers import split_mixed

    zh, en = split_mixed(line)
    return [zh, en] if zh and en else [line]


def _zh(line: str) -> str:
    parts = _split(line)
    return parts[0].strip() if re.search(r"[一-鿿]", parts[0]) else ""


def _en(line: str) -> str:
    parts = _split(line)
    if len(parts) > 1:
        return parts[1].strip()
    return "" if re.search(r"[一-鿿]", parts[0]) else parts[0].strip()


def _finish_job(store, kb) -> None:
    job = st.session_state.pop("job")
    label = jobs.finish_label(job, store)
    if job.error:
        content = f"I could not finish this: {job.error}"
    else:
        content = (job.result.text if job.result else "") or ""
        if job.note:
            content = job.note + "\n\n" + content
    msg = {"role": "assistant", "content": content, "agent_text": job.result.text if job.result else "", "label": label,
           "steps": job.step_lines(), "line_nos": job.new_line_nos,
           "counts": (job.result.counts if (job.result and job.is_check and (job.file_ref or len(job.new_line_nos or []) >= 3)) else None),
           "is_check": job.is_check, "kind": job.kind, "error": bool(job.error)}
    if job.kind == "check" and job.file_ref:
        msg["source_lines"] = [l.line_no for l in store.lines]
    if job.kind == "reply" and job.new_line_nos:
        msg["trace_from"] = job.new_line_nos[0]
        msg["source_lines"] = job.new_line_nos
    if job.kind == "question":
        msg["trace_from"] = job.selected_line_no
    st.session_state["chat"].append(msg)
    from ui.review import reset_selection

    if job.kind == "check" and store.has_shipment() and st.session_state.get("selected_line_no") is None:
        first = next((l.line_no for l in store.lines if store.needs_action(l)), None)
        st.session_state["selected_line_no"] = first
        reset_selection()
    elif job.kind == "reply" and job.new_line_nos and not job.error:
        st.session_state["selected_line_no"] = job.new_line_nos[0]   # show the clerk the updated version
        reset_selection()
    st.rerun()


# --------------------------------------------------------------------------- rendering
def _welcome(store, kb, compact: bool) -> None:
    busy = st.session_state.get("job") is not None
    with st.chat_message("assistant"):
        if compact:
            st.caption("Ask about any line, paste the shipper's reply, or start again from the sidebar.")
            return
        st.markdown("I catch cargo descriptions customs will reject before you file ICS2, suggest HS-6 codes with reasoning "
                    "and a precedent, and route every line: **auto-accept**, **human review** or **ask the shipper**.")
        for label, hint, action in QUICK_ACTIONS:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1.3], vertical_alignment="center")
                c1.markdown(f"**{label}**  \n:gray[{hint}]")
                if c2.button("Go", key=f"qa_{action}", width="stretch", disabled=busy):
                    st.session_state["quick_action"] = action
        with st.expander("What I can and cannot do"):
            st.markdown("**Can:** check descriptions, suggest HS-6 subheadings with reasoning, cite BTI precedents, verify a code exists "
                        "in the current nomenclature.\n\n**Cannot:** make the final classification decision for you. A line below the "
                        "threshold is never auto-accepted, and a flagged line is never accepted without your click. Text inside your files "
                        "is treated as data, never as instructions.")


def _render_counts(counts: dict) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Auto-accept", counts.get("auto_accept", 0))
    c2.metric("Human review", counts.get("review", 0))
    c3.metric("Ask the shipper", counts.get("ask_shipper", 0))


def _needs_action_list(store) -> None:
    items = [l for l in store.lines if store.needs_action(l)]
    if not items:
        st.caption("No line needs you — all auto-accepted.")
        return
    st.markdown("**Lines that need you**")
    for line in items[:12]:
        v = line.current
        flag = "failed" if v.status.value == "failed" else (v.flag.kind.value if v.flag else "ok")
        ask = ""
        if v.flag and v.flag.kind.value != "ok":
            ask = " → ask for " + ", ".join(a.replace("_", " ") for a in v.flag.ask_for[:3])
        elif v.status.value == "failed":
            ask = f" → {v.error_reason}"
        else:
            ask = f" → {v.route_reason}"
        st.markdown(f"- **{line.line_no}** {v.display_text[:48]} {FLAG_BADGE.get(flag, '')}{ask}")
    if len(items) > 12:
        st.caption(f"… and {len(items) - 12} more in the table.")


def _render_line_cards(store, line_nos: list[int]) -> None:
    for n in line_nos:
        try:
            line = store.get_line(n)
        except KeyError:
            continue
        v = line.current
        route = store.effective_route(line)
        with st.container(border=True):
            flag = "failed" if v.status.value == "failed" else (v.flag.kind.value if v.flag else "ok")
            st.markdown(f"**Line {line.line_no}** · {v.display_text}  {FLAG_BADGE.get(flag, '')} {ROUTE_BADGE.get(route, '')}")
            if v.flag and v.flag.kind.value != "ok":
                st.caption(f"{v.flag.reason}. Ask the shipper for: {', '.join(a.replace('_', ' ') for a in v.flag.ask_for)}.")
            if v.status.value == "failed":
                st.caption(f"Check failed: {v.error_reason}")
            for c in v.candidates[:3]:
                prec = f" · BTI {c.precedent.member_state} {c.precedent.reference}" if c.precedent else ""
                hist = " · history only" if c.history_only else ""
                st.progress(c.confidence / 100, text=f"`{c.code}` {c.subheading_text[:56]} · {c.confidence}%{hist}{prec}")
            if v.status.value == "checked" and not v.candidates:
                st.caption("No candidate" + (" (no valid candidate)" if v.no_valid_candidate else "") + " — " + v.route_reason)
            st.caption(f"{ROUTE_LABEL.get(route, route)} — {v.route_reason}")
    st.caption("Confidence is a model estimate, not a calibrated probability.")


def _render_sources(store, line_nos: list[int]) -> None:
    groups: dict[str, dict[str, str]] = {}
    for n in line_nos:
        try:
            v = store.get_line(n).current
        except KeyError:
            continue
        for s in v.sources:
            groups.setdefault(SOURCE_GROUP.get(s.kind.value, s.kind.value), {}).setdefault(s.id, s.title)
    total = sum(len(g) for g in groups.values())
    if not total:
        return
    summary = " · ".join(f"{name} {len(items)}" for name, items in groups.items())
    with st.expander(f"Sources · {total} — {summary}"):
        for name, items in groups.items():
            st.markdown(f"**{name}**")
            for sid, title in list(items.items())[:40]:
                st.markdown(f"- `{sid}` — {title}")
            if len(items) > 40:
                st.caption(f"… and {len(items) - 40} more")


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
    with st.expander(f"Retrieval steps · line {line_no}"):
        hist = f" (+{t.history_chunks} from the shipper's past codes)" if t.history_chunks else ""
        if t.precedent_codes:
            hist += f" (+{t.precedent_chunks} from BTI precedents; precedent codes {', '.join(t.precedent_codes)})"
        st.markdown(f"- **Original**: {t.original}\n- **Translation / expansion**: {', '.join(t.queries)}\n"
                    f"- **Metadata filter**: {('chapters ' + ', '.join(t.chapter_filter) + ' — ' + t.filter_reason) if t.chapter_filter else 'none'}\n"
                    f"- **Hits**: BM25 {t.bm25_hits} + vectors {t.vector_hits} → RRF {t.fused} → {t.sent_to_model} chunks to the model{hist} ({t.mode.value})")


def terms_table(kb) -> pd.DataFrame:
    rows = []
    for rl in kb.rules.ics2_lists:
        for e in rl.entries:
            rows.append({"Term": e.term, "List": "ICS2 stop words" if rl.list == "ics2_stop_words" else "ICS2 unacceptable terms",
                         "Source": rl.source_doc[:60], "Flag": "Vague"})
    for e in kb.rules.firm.entries:
        rows.append({"Term": e.term, "List": "Firm stop-words", "Source": kb.rules.firm.source_doc[:60], "Flag": "Stop-word"})
    return pd.DataFrame(rows)


def _render_message(msg: dict, store, kb, latest: bool) -> None:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
            if msg.get("file"):
                st.caption(f":material/attach_file: {msg['file']}")
            if msg.get("raw") and msg.get("content", "").startswith("["):
                st.caption(msg["raw"][:300])
            return
        if msg.get("label") is not None:
            with st.status(msg["label"], state="complete", expanded=False):
                for s in msg.get("steps") or []:
                    st.markdown(s)
        if msg.get("counts"):
            _render_counts(store.counts() if store.has_shipment() else msg["counts"])
            if latest and store.has_shipment():
                _needs_action_list(store)
        if msg.get("kind") == "terms":
            st.markdown(msg["content"])
            st.dataframe(terms_table(kb), hide_index=True, width="stretch", height=300)
            return
        text = msg.get("content") or ""
        if msg.get("error"):
            st.error(text, icon="⚠️")
        elif text and msg.get("kind") == "check" and (msg.get("line_nos") or msg.get("counts")):
            with st.expander("Assistant notes"):  # the cards and counts below are the structured summary
                st.markdown(text)
        elif text:
            st.markdown(text)
        if msg.get("line_nos") and msg.get("kind") in ("check", "reply"):
            if latest:
                _render_line_cards(store, msg["line_nos"])
            else:
                with st.expander(f"Line results · {len(msg['line_nos'])}"):
                    _render_line_cards(store, msg["line_nos"])
        if msg.get("source_lines") or msg.get("line_nos"):
            _render_sources(store, msg.get("source_lines") or msg["line_nos"])
        if msg.get("trace_from"):
            _render_trace(store, msg["trace_from"])


def _live_turn(store) -> None:
    @st.fragment(run_every=0.7)
    def _poll() -> None:
        job = st.session_state.get("job")
        if job is None:
            return
        has_lines = store.has_shipment() and bool(store.lines)
        if job.done or has_lines != st.session_state.get("layout_has_lines", False):
            st.rerun()  # finished, or the review column must appear now that the parse step added lines
            return
        with st.chat_message("assistant"):
            # not a `with` block: leaving a status context would flip it to "complete" while the job still runs
            status = st.status(jobs.running_label(job, store), expanded=True, state="running")
            for line in job.step_lines():
                status.markdown(line)
            if job.is_check and store.has_shipment():
                n = len(store.lines)
                done = sum(1 for l in store.lines if l.current.status.value != "pending")
                if n:
                    status.progress(done / n, text=f"{done} / {n} lines classified")

    _poll()


def _turns(messages: list[dict]) -> list[list[dict]]:
    """Group the history into turns: a clerk message starts a turn, the replies that follow belong to it."""
    turns: list[list[dict]] = []
    for m in messages:
        if m["role"] == "user" or not turns:
            turns.append([m])
        else:
            turns[-1].append(m)
    return turns


def render(store, kb) -> None:
    job = st.session_state.get("job")
    if job is not None and job.done:
        _finish_job(store, kb)

    has_lines = store.has_shipment() and bool(store.lines)
    _welcome(store, kb, compact=has_lines)
    placeholder = "Ask about any line, or paste the shipper's reply…" if has_lines else "Paste descriptions (one per line) or ask a question…"
    prompt = st.chat_input(placeholder, disabled=job is not None)   # under the welcome, above the history

    messages = st.session_state["chat"]
    last_assistant = max((i for i, m in enumerate(messages) if m["role"] == "assistant"), default=-1)
    latest_msg = messages[last_assistant] if last_assistant >= 0 else None
    running = job is not None and not job.done
    turns = _turns(messages)
    if running and not turns:
        _live_turn(store)
    for t_idx, turn in enumerate(reversed(turns)):   # newest turn first, chronological inside a turn
        for msg in turn:
            _render_message(msg, store, kb, latest=(msg is latest_msg))
        if t_idx == 0 and running:
            _live_turn(store)   # the running turn's progress sits right under the chat box

    pending = st.session_state.pop("pending_check", None) if job is None else None
    if pending:
        ref = store.shipment.reference if store.has_shipment() else ""
        label = f"Check the packing list{(' for ' + ref) if ref else ''}."
        st.session_state["chat"].append({"role": "user", "content": label, "file": pending["name"]})
        _start(label, store, kb, file_ref=pending["file_ref"], is_check=True, kind="check")
        st.rerun()

    action = st.session_state.pop("quick_action", None)
    if action == "__terms__":
        st.session_state["chat"].append({"role": "user", "content": "Which terms does customs reject?"})
        facts = kb.rules.caption_facts()
        st.session_state["chat"].append({"role": "assistant", "kind": "terms",
                                         "content": f"Customs rejects descriptions that are only a generic term. {facts['ics2_terms']} ICS2 terms "
                                                    f"(→ *Vague*) and {facts['firm_terms']} firm stop-words (→ *Stop-word*). Search the table:"})
        st.rerun()
    elif action == "__sample__":
        st.session_state["load_sample"] = True
        st.rerun()
    elif action:
        handle_message(action, store, kb)
        st.rerun()

    if prompt:
        handle_message(prompt, store, kb)
        st.rerun()
