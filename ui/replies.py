"""Chat hook for pasted shipper replies: store the text by reference, resolve the line in code, run the agent
(FR-036, FR-037). The raw reply never enters the agent conversation; only the reference does."""
from __future__ import annotations

import streamlit as st

WHICH_LINE = ("Which line is this reply for? Say for example “line 3 is steel bobbin cases for industrial sewing machines”, "
              "or select the line in the review table and paste the reply again.")


def handle(line_no: int | None, reply_text: str, store, kb, chat: list, run) -> None:
    selected = st.session_state.get("selected_line_no")
    target = line_no if line_no is not None else selected
    known = {l.line_no for l in store.lines}
    if target is None or int(target) not in known:
        chat.append({"role": "user", "content": "[Shipper reply pasted]", "raw": reply_text})
        chat.append({"role": "assistant", "content": WHICH_LINE})
        return
    target = int(target)
    ref = store.register_reply(reply_text)
    chat.append({"role": "user", "content": f"[Shipper reply pasted for line {target}]", "raw": reply_text})
    msg = run(f"Apply reply {ref} to line {target}", store, kb, reply_ref=ref, is_check=False, new_line_nos=[target],
              label_prefix=f"Line {target} updated")
    if line_no is None:
        msg["content"] = f"Applied to line {target} (selected).\n\n" + (msg.get("content") or "")
    msg["trace_from"] = target
    chat.append(msg)
