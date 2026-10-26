"""Tool 1 — parse_packing_list: file bytes → structured lines, shipment metadata and the line store
(FR-002 … FR-006, FR-042, FR-050)."""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agent.config import MAX_DESC_CHARS, MAX_LINES
from agent.schemas import CreatedBy, ParsedLine, ParsePackingListOutput, ShipperRef, SourceFile
from rag.rules import detect_shipper, find_shipper, load_shippers
from tools import register
from tools.common import get_context
from tools.ocr import OCREngine, ocr_image, ocr_pdf
from tools.parsers import (
    NoHeaderRow,
    TooManyLines,
    check_caps,
    detect_meta,
    find_header_row,
    head_cells,
    read_pdf_tables,
    read_table,
    rows_to_lines,
    split_mixed,
)

_ocr_engine: OCREngine | None = None


def default_ocr_engine() -> OCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        from tools.ocr import RapidOCREngine

        _ocr_engine = RapidOCREngine()
    return _ocr_engine


def _lines_from_ocr(ocr: list, warnings: list[str]) -> list[ParsedLine]:
    lines: list[ParsedLine] = []
    for item in ocr:
        text = item.text.strip()
        if len(re.findall(r"[一-鿿A-Za-z]", text)) < 2:
            continue  # numbers-only fragments, rulers, noise
        if len(lines) >= MAX_LINES:
            raise TooManyLines(f"more than {MAX_LINES} lines were recognised; split the document")
        zh, en = split_mixed(text)
        truncated = len(zh) > MAX_DESC_CHARS or len(en) > MAX_DESC_CHARS
        page = f"page {item.page} " if item.page else ""
        lines.append(ParsedLine(line_no=len(lines) + 1, text_zh=zh[:MAX_DESC_CHARS], text_en=en[:MAX_DESC_CHARS],
                                source_ref=f"{page}OCR line {len(lines) + 1}", truncated=truncated, unreadable=item.unreadable))
    unreadable = sum(1 for l in lines if l.unreadable)
    if unreadable:
        warnings.append(f"{unreadable} OCR line{'s' if unreadable != 1 else ''} could not be read reliably and need a human look")
    return lines


def parse_packing_list(data: bytes, name: str, shippers: list | None = None, ocr_engine: OCREngine | None = None,
                       min_score: float | None = None) -> ParsePackingListOutput:
    """Plain function: caps → read → header → lines (+ OCR for scans and photos) → shipper and meta detection."""
    kind = check_caps(data, name)
    warnings: list[str] = []
    rows: list[list[Any]] = []
    sheet: str | None = None
    header_row: int | None = None
    skipped = 0
    if kind in ("xlsx", "csv"):
        rows, sheet = read_table(data, kind)
        idx, colmap = find_header_row(rows)
        source = f'sheet "{sheet}"' if sheet else "csv"
        lines, skipped = rows_to_lines(rows, idx, colmap, source)
        skipped += idx
        header_row = idx + 1
    elif kind == "pdf":
        rows, scanned_pages = read_pdf_tables(data)
        lines = []
        if rows:
            try:
                idx, colmap = find_header_row(rows)
                lines, skipped = rows_to_lines(rows, idx, colmap, "pdf")
                skipped += idx
                header_row = idx + 1
            except NoHeaderRow:
                warnings.append("no table header found in the PDF text; falling back to OCR")
                scanned_pages = scanned_pages or None
        if not lines:
            ocr = ocr_pdf(data, ocr_engine or default_ocr_engine(), min_score, pages=scanned_pages or None)
            lines = _lines_from_ocr(ocr, warnings)
            if scanned_pages:
                warnings.append(f"OCR used for scanned page{'s' if len(scanned_pages) != 1 else ''} {', '.join(map(str, scanned_pages))}")
    else:
        ocr = ocr_image(data, ocr_engine or default_ocr_engine(), min_score)
        lines = _lines_from_ocr(ocr, warnings)
        warnings.append("OCR used for a photo; quantities and values are not read from photos")
    if not lines:
        from tools.parsers import EmptyFile

        raise EmptyFile("no goods lines were found in the file")
    cells = head_cells(rows) if rows else [l.text_en for l in lines[:5]] + [l.text_zh for l in lines[:5]]
    shipper = detect_shipper(cells, shippers if shippers is not None else load_shippers())
    return ParsePackingListOutput(lines=lines, sheet=sheet, header_row=header_row, skipped_rows=skipped,
                                  shipper_name_detected=shipper.name if shipper else None, meta=detect_meta(rows) if rows else
                                  {"origin": None, "destination": None, "mode": None}, warnings=warnings)


def load_into_store(store, parsed: ParsePackingListOutput, name: str, size: int, shippers: list | None = None) -> None:
    """Fill the open shipment from a parse result: source file, shipper, meta and v1 lines (created_by=file)."""
    s = store.shipment
    s.source = SourceFile(name=name, size_bytes=size, kind=check_caps(b"", name) if size <= 0 else name.rsplit(".", 1)[-1].lower())
    if s.source.kind == "jpeg":
        s.source.kind = "jpg"
    profile = find_shipper(parsed.shipper_name_detected, shippers if shippers is not None else load_shippers())
    if profile is not None:
        store.set_shipper(profile.name, known=True, past_shipment_count=len(profile.past_shipments))
    elif parsed.shipper_name_detected:
        store.set_shipper(parsed.shipper_name_detected, known=False)
    s.origin = s.origin or parsed.meta.get("origin")
    s.destination = s.destination or parsed.meta.get("destination")
    s.mode = s.mode or parsed.meta.get("mode")
    store.add_lines(parsed.lines, CreatedBy.file)


def summarize(parsed: ParsePackingListOutput, name: str) -> str:
    where = f'sheet “{parsed.sheet}”, ' if parsed.sheet else f"{name}, "
    header = f"header row {parsed.header_row}, " if parsed.header_row else ""
    n = len(parsed.lines)
    split = sum(1 for l in parsed.lines if l.text_zh and l.text_en)
    unread = sum(1 for l in parsed.lines if l.unreadable)
    text = f"{where}{header}{n} lines, {split} Chinese/English split"
    if unread:
        text += f", {unread} unreadable"
    if parsed.shipper_name_detected:
        text += f", shipper {parsed.shipper_name_detected}"
    return text


class ParseArgs(BaseModel):
    file_ref: str = Field(description="Reference of the uploaded file as given in the request (for example f1)")


@tool("parse_packing_list", args_schema=ParseArgs)
def parse_packing_list_tool(file_ref: str) -> str:
    """Read the uploaded packing list or invoice (xlsx, csv, pdf, photo) into numbered lines with Chinese and
    English descriptions, quantities and the shipper. Call it first when the request gives a FILE REFERENCE."""
    ctx = get_context()
    store = ctx.store
    data, name = store.get_file(file_ref)
    parsed = parse_packing_list(data, name, shippers=getattr(ctx.kb, "shippers", None))
    if not store.has_shipment() or store.lines:
        store.new_shipment(reference=store.shipment.reference if store.has_shipment() else "",
                           threshold=store.shipment.threshold if store.has_shipment() else 85,
                           hybrid=store.shipment.hybrid_search if store.has_shipment() else True,
                           hs6_override_min=store.shipment.hs6_override_min if store.has_shipment() else None)
    load_into_store(store, parsed, name, len(data), shippers=getattr(ctx.kb, "shippers", None))
    payload = {"summary": summarize(parsed, name), "line_count": len(parsed.lines), "shipper": parsed.shipper_name_detected,
               "meta": parsed.meta, "warnings": parsed.warnings,
               "lines": [{"line_no": l.line_no, "text_zh": l.current.text_zh, "text_en": l.current.text_en, "qty": l.qty,
                          "unreadable": l.current.unreadable} for l in store.lines]}
    return json.dumps(payload, ensure_ascii=False)


register(parse_packing_list_tool)
