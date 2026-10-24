"""The drop zone, the sample, the replacement question, and the one way a new shipment opens (feature 005,
contracts/ui.md §2). The file is parsed by the agent's check, as before; this module only starts it."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from agent.config import DEFAULT_THRESHOLD, ROOT
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
    the Admin threshold and hybrid values and the kept origin (uploads, the sample, typed lines, the Admin chat)."""
    if store.has_shipment():
        st.session_state.setdefault("session_usage", Usage()).add(store.shipment.usage)
    st.session_state.pop("uploaded_file", None)   # `begin` sets it again for a file; typed lines name no file
    shipment = store.new_shipment(reference=reference, threshold=int(st.session_state.get("threshold", DEFAULT_THRESHOLD)),
                                  hybrid=bool(st.session_state.get("hybrid", True)))
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
    st.session_state["open_file"] = False
    runner.start_check(store, kb, file_ref=file_ref, file_name=name)


def _validate(data: bytes, name: str) -> str | None:
    try:
        check_caps(data, name)
    except ParseError as exc:
        return str(exc)
    return None


def render_drop_zone(store, kb, key: str = "empty") -> None:
    """The drop zone and "Try the sample invoice", disabled while any job runs, with the replacement question when a
    checked shipment is open."""
    running = runner.busy()
    wait = "Wait for the running check" if running else None
    uploaded = st.file_uploader("Drop a packing list or invoice here", type=FILE_TYPES, key=f"uploader_{key}",
                                disabled=running, help=wait)
    st.caption("XLSX · CSV · PDF · JPG · PNG — up to 20 MB, one file per shipment")
    if uploaded is not None and st.session_state.get("last_upload_id") != uploaded.file_id:
        data = uploaded.getvalue()
        st.session_state["last_upload_id"] = uploaded.file_id
        err = _validate(data, uploaded.name)
        if err:
            st.error(err, icon="⚠️")
        elif needs_confirmation(store):
            st.session_state["pending_replacement"] = {"data": data, "name": uploaded.name}
        else:
            begin(store, kb, data, uploaded.name)
            st.rerun()
    if st.button("Try the sample invoice", key=f"sample_{key}", disabled=running, help=wait):
        data = SAMPLE_PATH.read_bytes()
        if needs_confirmation(store):
            st.session_state["pending_replacement"] = {"data": data, "name": SAMPLE_PATH.name, "reference": SAMPLE_REFERENCE}
        else:
            begin(store, kb, data, SAMPLE_PATH.name, reference=SAMPLE_REFERENCE)
            st.rerun()
    pending = st.session_state.get("pending_replacement")
    if pending:
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
