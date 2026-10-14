"""Sidebar upload section: uploader, file chip, replacement confirmation, the bundled sample, and the
shipment fields (reference, shipper, filing type) — FR-002, FR-005, FR-042, US2 scenario 8."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from agent.config import ROOT
from agent.schemas import ShipperRef
from tools.parse_packing_list import load_into_store, parse_packing_list
from tools.parsers import ParseError

SAMPLE_PATH = ROOT / "data" / "samples" / "sample_packing_list.xlsx"
SAMPLE_REFERENCE = "HOL-2026-10-0472"
FILING_OPTIONS = ["ICS2 house (ENS)"]
DETECT = "Detect from file"
NEW_SHIPPER = "New shipper…"


def needs_confirmation(store) -> bool:
    return store.has_shipment() and bool(store.lines)


def start_shipment_from_parsed(store, parsed, name: str, size: int, shippers: list, threshold: int, hybrid: bool,
                               reference: str = "", shipper_choice: str | None = None):
    """Create a fresh shipment from a parse result (used by tests and by direct loading paths)."""
    shipment = store.new_shipment(reference=reference, threshold=threshold, hybrid=hybrid)
    load_into_store(store, parsed, name, size, shippers)
    if shipper_choice and shipper_choice not in (DETECT, NEW_SHIPPER):
        from rag.rules import find_shipper

        p = find_shipper(shipper_choice, shippers)
        store.set_shipper(shipper_choice, known=p is not None, past_shipment_count=len(p.past_shipments) if p else 0)
    return shipment


# --------------------------------------------------------------------------- upload flow (agent parses)
def _begin(store, data: bytes, name: str, reference: str | None = None) -> None:
    """Register the file, open an empty shipment and ask the chat to run the agent (the agent parses)."""
    try:
        parse_packing_list.__wrapped__  # type: ignore[attr-defined]  # no-op, keeps import used
    except AttributeError:
        pass
    store.new_shipment(reference=reference or st.session_state.get("reference", "") or "",
                       threshold=int(st.session_state.get("threshold", 85)), hybrid=bool(st.session_state.get("hybrid", True)))
    file_ref = store.register_file(data, name)
    st.session_state["uploaded_file"] = {"name": name, "size": len(data), "ref": file_ref}
    st.session_state["pending_check"] = {"file_ref": file_ref, "name": name}
    st.session_state["selected_line_no"] = None
    st.session_state["chat"] = st.session_state.get("chat", [])


def _validate(data: bytes, name: str) -> str | None:
    """Reject unsupported or oversize files before anything else (FR-002); returns the error text."""
    from tools.parsers import check_caps

    try:
        check_caps(data, name)
    except ParseError as exc:
        return str(exc)
    return None


def render(store, kb) -> None:
    uploaded = st.file_uploader("Drag and drop files here", type=["xlsx", "csv", "pdf", "jpg", "jpeg", "png"],
                                help="Limit 20 MB · XLSX, CSV, PDF, JPG, PNG", key="uploader", label_visibility="collapsed")
    st.caption("Limit 20MB · XLSX, CSV, PDF, JPG, PNG")

    if uploaded is not None and st.session_state.get("last_upload_id") != uploaded.file_id:
        data = uploaded.getvalue()
        err = _validate(data, uploaded.name)
        st.session_state["last_upload_id"] = uploaded.file_id
        if err:
            st.error(err)
        elif needs_confirmation(store):
            st.session_state["pending_replacement"] = {"data": data, "name": uploaded.name}
        else:
            _begin(store, data, uploaded.name)
            st.rerun()

    if st.session_state.pop("load_sample", False):
        data = SAMPLE_PATH.read_bytes()
        if needs_confirmation(store):
            st.session_state["pending_replacement"] = {"data": data, "name": SAMPLE_PATH.name, "reference": SAMPLE_REFERENCE}
        else:
            st.session_state["reference"] = SAMPLE_REFERENCE
            _begin(store, data, SAMPLE_PATH.name, reference=SAMPLE_REFERENCE)
            st.rerun()

    pending = st.session_state.get("pending_replacement")
    if pending:
        st.warning(f"A checked shipment is open. Replace it with **{pending['name']}**? Results, counts and cost will reset.")
        c1, c2 = st.columns(2)
        if c1.button("Replace shipment", type="primary", use_container_width=True):
            st.session_state.pop("pending_replacement", None)
            st.session_state["chat"] = []
            if pending.get("reference"):
                st.session_state["reference"] = pending["reference"]
            _begin(store, pending["data"], pending["name"], reference=pending.get("reference"))
            st.rerun()
        if c2.button("Cancel", use_container_width=True):
            st.session_state.pop("pending_replacement", None)
            st.rerun()

    chip = st.session_state.get("uploaded_file")
    if chip:
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"📄 **{chip['name']}**  \n{chip['size'] / 1024:.0f} KB")
        if c2.button("✕", help="Remove file", key="remove_file"):
            st.session_state.pop("uploaded_file", None)
            st.rerun()

    st.subheader("Shipment")
    current_ref = store.shipment.reference if store.has_shipment() else ""
    st.session_state.setdefault("reference", current_ref)
    ref = st.text_input("Your reference", key="reference", placeholder="HOL-2026-10-…")
    if store.has_shipment() and ref != store.shipment.reference:
        store.shipment.reference = ref

    names = [p.name for p in getattr(kb, "shippers", [])]
    options = [DETECT, *names, NEW_SHIPPER]
    detected = store.shipment.shipper.name if store.has_shipment() and store.shipment.shipper.known else None
    default_idx = options.index(detected) if detected in options else 0
    widget_key = f"shipper_choice_{store.shipment.id if store.has_shipment() else 'none'}_{detected or 'none'}"
    choice = st.selectbox("Shipper", options, index=default_idx, key=widget_key, format_func=lambda n: _shipper_label(n, kb))
    if store.has_shipment() and choice not in (DETECT,) and choice != store.shipment.shipper.name:
        if choice == NEW_SHIPPER:
            store.set_shipper("New shipper", known=False)
        else:
            p = next((p for p in kb.shippers if p.name == choice), None)
            store.set_shipper(choice, known=p is not None, past_shipment_count=len(p.past_shipments) if p else 0)
    st.selectbox("Filing", FILING_OPTIONS, index=0, key="filing")


def _shipper_label(name: str, kb) -> str:
    for p in getattr(kb, "shippers", []):
        if p.name == name:
            return f"{p.name} · {len(p.past_shipments)} past shipments"
    return name


__all__ = ["needs_confirmation", "start_shipment_from_parsed", "render", "ShipperRef", "Path"]
