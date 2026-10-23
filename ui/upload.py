"""Upload section (uploader, file chip, replacement confirmation, bundled sample) and the shipment fields
(reference, shipper, filing type) — FR-002, FR-005, FR-042, US2 scenario 8."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from agent.agent import apply_taric_origin
from agent.config import ROOT
from tools.parse_packing_list import load_into_store
from tools.parsers import ParseError, check_caps
from ui.review import reset_selection

SAMPLE_PATH = ROOT / "data" / "samples" / "sample_packing_list.xlsx"
SAMPLE_REFERENCE = "HOL-2026-10-0472"
FILING_OPTIONS = ["ICS2 house (ENS)"]
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


def begin(store, data: bytes, name: str, reference: str | None = None) -> None:
    """Register the file, open an empty shipment and ask the chat to run the agent (the agent parses)."""
    store.new_shipment(reference=reference or st.session_state.get("reference", "") or "",
                       threshold=int(st.session_state.get("threshold", 85)), hybrid=bool(st.session_state.get("hybrid", True)))
    file_ref = store.register_file(data, name)
    st.session_state["uploaded_file"] = {"name": name, "size": len(data), "ref": file_ref}
    st.session_state["pending_check"] = {"file_ref": file_ref, "name": name}
    st.session_state["selected_line_no"] = None
    st.session_state["chat"] = []
    reset_selection()


def _validate(data: bytes, name: str) -> str | None:
    try:
        check_caps(data, name)
    except ParseError as exc:
        return str(exc)
    return None


def busy() -> bool:
    job = st.session_state.get("job")
    return job is not None and not job.done


def render_uploader(store, kb) -> None:
    running = busy()
    uploaded = st.file_uploader("Packing list or invoice", type=["xlsx", "csv", "pdf", "jpg", "jpeg", "png"],
                                key="uploader", label_visibility="collapsed", disabled=running,
                                help="Stand by: a check is running." if running else None)
    if uploaded is not None and st.session_state.get("last_upload_id") != uploaded.file_id:
        data = uploaded.getvalue()
        st.session_state["last_upload_id"] = uploaded.file_id
        err = _validate(data, uploaded.name)
        if err:
            st.error(err, icon="⚠️")
        elif needs_confirmation(store):
            st.session_state["pending_replacement"] = {"data": data, "name": uploaded.name}
        else:
            begin(store, data, uploaded.name)
            st.rerun()

    if not running and st.session_state.pop("load_sample", False):
        data = SAMPLE_PATH.read_bytes()
        if needs_confirmation(store):
            st.session_state["pending_replacement"] = {"data": data, "name": SAMPLE_PATH.name, "reference": SAMPLE_REFERENCE}
        else:
            st.session_state["reference"] = SAMPLE_REFERENCE
            begin(store, data, SAMPLE_PATH.name, reference=SAMPLE_REFERENCE)
            st.rerun()

    pending = st.session_state.get("pending_replacement")
    if pending:
        st.warning(f"A checked shipment is open. Replace it with **{pending['name']}**? Results, counts and cost reset.",
                   icon=":material/swap_horiz:")
        c1, c2 = st.columns(2)
        if c1.button("Replace", type="primary", width="stretch", key="replace_yes"):
            st.session_state.pop("pending_replacement", None)
            if pending.get("reference"):
                st.session_state["reference"] = pending["reference"]
            begin(store, pending["data"], pending["name"], reference=pending.get("reference"))
            st.rerun()
        if c2.button("Cancel", width="stretch", key="replace_no"):
            st.session_state.pop("pending_replacement", None)
            st.rerun()

    chip = st.session_state.get("uploaded_file")
    if chip:
        c1, c2 = st.columns([6, 1], vertical_alignment="center")
        name = chip["name"]
        short = name if len(name) <= 22 else name[:11] + "…" + name[-8:]
        c1.markdown(f":material/description: {short} :gray[· {chip['size'] / 1024:.0f} KB]", help=name)
        if c2.button("", icon=":material/close:", key="remove_file", help="Remove file", type="tertiary"):
            st.session_state.pop("uploaded_file", None)
            st.rerun()


def _shipper_label(name: str, kb) -> str:
    for p in getattr(kb, "shippers", []):
        if p.name == name:
            return f"{p.name} · {len(p.past_shipments)} past shipments"
    return name


def render_shipment_fields(store, kb) -> None:
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
    if store.has_shipment() and choice != DETECT and choice != store.shipment.shipper.name:
        if choice == NEW_SHIPPER:
            store.set_shipper("New shipper", known=False)
        else:
            p = next((p for p in kb.shippers if p.name == choice), None)
            store.set_shipper(choice, known=p is not None, past_shipment_count=len(p.past_shipments) if p else 0)
    st.selectbox("Filing", FILING_OPTIONS, index=0, key="filing")
    if store.has_shipment():   # feature 004: the goods' origin for TARIC, per invoice
        key = f"taric_origin_{store.shipment.id}"
        st.session_state.setdefault(key, store.shipment.taric_origin)
        st.text_input("Origin (TARIC)", key=key, max_chars=2, on_change=_on_taric_origin, args=(store, kb, key),
                      help="The goods' country of origin for the TARIC lookup, two letters; CN by default")
        error = st.session_state.pop("taric_origin_error", None)
        if error:
            st.error(error)


def _on_taric_origin(store, kb, key: str) -> None:
    """A new origin re-applies the TARIC rules, with no model call (FR-017, FR-018); a refused one is put back."""
    try:
        apply_taric_origin(store, kb, st.session_state[key])
    except ValueError as exc:
        st.session_state["taric_origin_error"] = f"Origin not changed: {exc}"
    st.session_state[key] = store.shipment.taric_origin


def render(store, kb) -> None:  # kept for compatibility
    render_uploader(store, kb)
    st.subheader("Shipment")
    render_shipment_fields(store, kb)


__all__ = ["needs_confirmation", "start_shipment_from_parsed", "render", "render_uploader", "render_shipment_fields", "begin", "Path"]
