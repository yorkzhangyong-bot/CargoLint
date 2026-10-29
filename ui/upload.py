"""The upload tab (feature 012, FR-005; feature 005 before it): the drop zone, the sample, "Check all lines", the
replacement question, and the one way a new shipment opens. The file is parsed by the agent's check, as before; this
module only starts it."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from agent.config import DEFAULT_THRESHOLD, OVERRIDE_MIN, ROOT, get_settings
from agent.schemas import Usage
from tools.parse_packing_list import load_into_store
from tools.parsers import ParseError, check_caps
from ui import runner
from ui.view import md_escape

SAMPLE_PATH = ROOT / "data" / "samples" / "sample_packing_list.xlsx"
SAMPLE_REFERENCE = "HOL-2026-10-0472"
FILE_TYPES = ["xlsx", "csv", "pdf", "jpg", "jpeg", "png"]
DETECT = "Detect from file"
NEW_SHIPPER = "New shipper…"
PENDING = "pending_file"          # feature 012: the dropped file or the sample, waiting for "Check all lines"
WAIT = "Wait for the running check"
NOTHING_TO_CHECK = "Drop a file or load the sample invoice first"


def needs_confirmation(store) -> bool:
    return store.has_shipment() and bool(store.lines)


def start_shipment_from_parsed(store, parsed, name: str, size: int, shippers: list, threshold: int, hybrid: bool,
                               reference: str = "", shipper_choice: str | None = None):
    """Create a fresh shipment from a parse result (used by tests and direct loading paths)."""
    shipment = store.new_shipment(reference=reference, threshold=threshold, hybrid=hybrid)
    load_into_store(store, parsed, name, size, shippers)
    if shipper_choice and shipper_choice not in (DETECT, NEW_SHIPPER):
        from rag.rules import find_shipper

        p = find_shipper(shipper_choice, shippers)
        store.set_shipper(shipper_choice, known=p is not None, past_shipment_count=len(p.past_shipments) if p else 0)
    return shipment


def busy() -> bool:
    return runner.busy()


def open_shipment(store, reference: str = ""):
    """The one way a new shipment opens: the old shipment's usage joins the session total, and the new one starts with
    the Admin threshold and hybrid values, the kept origin and the precedent override switch of feature 008 (uploads,
    the sample, typed lines, the Admin chat)."""
    if store.has_shipment():
        st.session_state.setdefault("session_usage", Usage()).add(store.shipment.usage)
    st.session_state.pop("uploaded_file", None)   # `begin` sets it again for a file; typed lines name no file
    shipment = store.new_shipment(reference=reference, threshold=int(st.session_state.get("threshold", DEFAULT_THRESHOLD)),
                                  hybrid=bool(st.session_state.get("hybrid", True)),
                                  hs6_override_min=OVERRIDE_MIN if get_settings().hs6_override else None)
    origin = st.session_state.get("origin_field") or "CN"
    try:
        store.set_taric_origin(origin)
    except ValueError:
        pass   # an invalid kept origin was refused when it was typed; the shipment keeps CN
    return shipment


def begin(store, kb, data: bytes, name: str, reference: str | None = None) -> None:
    """Open a shipment for the file and start its check; the agent parses it."""
    open_shipment(store, reference or Path(name).stem)
    file_ref = store.register_file(data, name)
    st.session_state["uploaded_file"] = {"name": name, "size": len(data), "ref": file_ref}
    st.session_state["chat"] = []
    st.session_state["selected_line_no"] = None
    runner.start_check(store, kb, file_ref=file_ref, file_name=name)


def _validate(data: bytes, name: str) -> str | None:
    try:
        check_caps(data, name)
    except ParseError as exc:
        return str(exc)
    return None


def _take_upload(uploaded) -> None:
    """A new file is validated as before and becomes the pending file; taking it out of the drop zone drops it."""
    if uploaded is None:
        if (st.session_state.get(PENDING) or {}).get("source") == "upload":
            st.session_state.pop(PENDING)
        return
    if st.session_state.get("last_upload_id") == uploaded.file_id:
        return
    data = uploaded.getvalue()
    st.session_state["last_upload_id"] = uploaded.file_id
    err = _validate(data, uploaded.name)
    if err:
        st.session_state.pop(PENDING, None)
        st.error(err, icon="⚠️")
    else:
        st.session_state[PENDING] = {"data": data, "name": uploaded.name, "source": "upload"}


def _replace_prompt(store, kb, pending: dict, running: bool) -> None:
    st.warning(f"A checked shipment is open. Replace it with {md_escape(pending['name'])}? Results, counts and cost "
               "reset.", icon=":material/swap_horiz:")
    c1, c2 = st.columns(2)
    if c1.button("Replace", type="primary", width="stretch", key="replace_yes", disabled=running):
        st.session_state.pop("pending_replacement", None)
        begin(store, kb, pending["data"], pending["name"], reference=pending.get("reference"))
        st.rerun()
    if c2.button("Cancel", width="stretch", key="replace_no"):
        st.session_state.pop("pending_replacement", None)
        st.rerun()


def render(store, kb) -> None:
    """The upload tab: a dropped file or the sample waits as the pending file until "Check all lines" (FR-005), which
    asks first when a checked shipment is open; everything waits while any job runs. Compact: the sample button and
    its captions share one row under the drop zone, at small gaps."""
    running = runner.busy()
    wait = WAIT if running else None
    with st.container(gap="xsmall"):
        with st.container(border=True, gap="xsmall"):
            _take_upload(st.file_uploader("Drag and drop a PDF, Excel, CSV or photo (jpg/png) here, or browse files",
                                          type=FILE_TYPES, key="uploader", disabled=running, help=wait))
            with st.container(horizontal=True, vertical_alignment="center"):
                if st.button("Load sample invoice", key="sample", disabled=running, help=wait):
                    st.session_state[PENDING] = {"data": SAMPLE_PATH.read_bytes(), "name": SAMPLE_PATH.name,
                                                 "reference": SAMPLE_REFERENCE, "source": "sample"}
                st.caption("about 1 minute for 30 lines", width="content")
                pending = st.session_state.get(PENDING)
                if pending:
                    st.caption(f"Ready to check: {md_escape(pending['name'])}", width="content")
        replacing = st.session_state.get("pending_replacement")
        if replacing:
            _replace_prompt(store, kb, replacing, running)
            return
        if st.button("Check all lines", key="check_all", type="primary", width="stretch",
                     disabled=running or not pending, help=wait or (None if pending else NOTHING_TO_CHECK)):
            st.session_state.pop(PENDING)
            if needs_confirmation(store):
                st.session_state["pending_replacement"] = pending
            else:
                begin(store, kb, pending["data"], pending["name"], reference=pending.get("reference"))
            st.rerun()
