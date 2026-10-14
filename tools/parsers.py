"""Spreadsheet, CSV and PDF-table readers: header detection, bilingual cell splitting, caps,
totals skipping, shipper and shipment-meta detection (FR-002, FR-003, FR-006, FR-045, FR-050).

Files are read for their cell or text content only: workbooks open data-only without VBA, and no
link inside a file is ever followed.
"""
from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from agent.config import MAX_DESC_CHARS, MAX_FILE_BYTES, MAX_LINES, SUPPORTED_FILE_KINDS
from agent.schemas import Money, ParsedLine


class ParseError(Exception):
    """Base class: the message is shown to the clerk as-is."""


class UnsupportedFileType(ParseError):
    pass


class FileTooLarge(ParseError):
    pass


class TooManyLines(ParseError):
    pass


class NoHeaderRow(ParseError):
    pass


class EmptyFile(ParseError):
    pass


HEADER_ALIASES: dict[str, list[str]] = {
    "description": ["description", "goods description", "description of goods", "commodity", "product name", "product",
                    "item name", "item", "goods", "品名", "货物描述", "货物名称", "商品名称", "货名", "名称", "货物"],
    "qty": ["qty", "quantity", "q'ty", "pcs", "ctns", "ctn", "cartons", "packages", "数量", "件数", "箱数", "包装件数"],
    "weight": ["gross weight", "g.w", "gw", "weight", "kgs", "kg", "毛重", "重量"],
    "volume": ["cbm", "volume", "measurement", "体积", "立方", "材积"],
    "value": ["amount", "total value", "value", "price", "usd", "金额", "总价", "价值", "货值"],
    "line_no": ["item no", "no.", "no", "sn", "序号", "项号", "#"],
}
TOTAL_RE = re.compile(r"\b(grand total|sub ?total|totals?)\b|合计|小计|总计|共计", re.I)
_CJK = re.compile(r"[一-鿿]")
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_CURRENCY_RE = re.compile(r"\b(USD|EUR|CNY|RMB|GBP|JPY|HKD)\b|US\$|\$|€|¥", re.I)


# --------------------------------------------------------------------------- caps and kinds
def check_caps(data: bytes, name: str) -> str:
    """Return the file kind or raise UnsupportedFileType / FileTooLarge before any parsing (FR-002)."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "jpeg":
        ext = "jpg"
    if ext not in SUPPORTED_FILE_KINDS:
        raise UnsupportedFileType(f"unsupported file type '.{ext}' — use XLSX, CSV, PDF, JPG or PNG" if ext else
                                  "the file has no extension — use XLSX, CSV, PDF, JPG or PNG")
    if len(data) > MAX_FILE_BYTES:
        raise FileTooLarge(f"the file is {len(data) / 1e6:.1f} MB; the limit is {MAX_FILE_BYTES / 1e6:.0f} MB")
    return ext


# --------------------------------------------------------------------------- cells
def cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()


def split_mixed(text: str) -> tuple[str, str]:
    """Split a mixed Chinese/English cell into (zh, en) on '/', newline, parentheses or the CJK↔Latin boundary."""
    t = (text or "").strip()
    if not t:
        return "", ""
    parts = [p.strip(" \t/（）()【】[]") for p in re.split(r"\n|\r|\s*/\s*|\s*[（(]\s*|\s*[)）]\s*", t)]
    parts = [p for p in parts if p]
    if len(parts) >= 2:
        zh = [p for p in parts if _CJK.search(p)]
        en = [p for p in parts if not _CJK.search(p)]
        if zh and en:
            return " ".join(zh), " ".join(en)
    m = re.match(r"^([一-鿿][^A-Za-z]*?)\s+([A-Za-z].*)$", t)
    if m and len(m.group(2).split()) >= 2:
        return m.group(1).strip(), m.group(2).strip()
    if _CJK.search(t):
        return t, ""
    return "", t


def parse_number(text: Any) -> float | None:
    s = cell_text(text)
    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


# --------------------------------------------------------------------------- header detection
def _alias_in(cell_lower: str, alias: str) -> bool:
    a = alias.lower()
    if _CJK.search(a) or not re.fullmatch(r"[a-z' ]+", a):
        return a in cell_lower
    return re.search(r"(?<![a-z])" + re.escape(a) + r"(?![a-z])", cell_lower) is not None


def find_header_row(rows: list[list[Any]], max_scan: int = 30) -> tuple[int, dict[str, int]]:
    for i, row in enumerate(rows[:max_scan]):
        colmap: dict[str, int] = {}
        for j, raw in enumerate(row):
            c = cell_text(raw).lower()
            if not c:
                continue
            for field, aliases in HEADER_ALIASES.items():
                if field in colmap:
                    continue
                if any(_alias_in(c, a) for a in aliases):
                    colmap[field] = j
                    break
        if "description" in colmap and len(colmap) >= 2:
            return i, colmap
    raise NoHeaderRow("no header row found — the file needs a description column plus a quantity, weight, volume or value column")


# --------------------------------------------------------------------------- rows → lines
def rows_to_lines(rows: list[list[Any]], header_idx: int, colmap: dict[str, int], source: str) -> tuple[list[ParsedLine], int]:
    header = [cell_text(c) for c in rows[header_idx]]
    currency = "USD"
    if "value" in colmap and colmap["value"] < len(header):
        m = _CURRENCY_RE.search(header[colmap["value"]])
        if m:
            token = m.group(0).upper()
            currency = {"US$": "USD", "$": "USD", "€": "EUR", "¥": "CNY", "RMB": "CNY"}.get(token, token)
    lines: list[ParsedLine] = []
    skipped = 0

    def col(cells: list[str], field: str) -> str:
        j = colmap.get(field)
        return cells[j] if j is not None and j < len(cells) else ""

    for row_no, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        cells = [cell_text(c) for c in row]
        desc = col(cells, "description")
        first = cells[0] if cells else ""
        if not desc.strip() or TOTAL_RE.search(desc) or TOTAL_RE.search(first):
            skipped += 1
            continue
        if len(lines) >= MAX_LINES:
            raise TooManyLines(f"the file has more than {MAX_LINES} lines; split it and check the parts separately")
        zh, en = split_mixed(desc)
        truncated = False
        if len(zh) > MAX_DESC_CHARS:
            zh, truncated = zh[:MAX_DESC_CHARS], True
        if len(en) > MAX_DESC_CHARS:
            en, truncated = en[:MAX_DESC_CHARS], True
        qty = col(cells, "qty") or None
        weight = parse_number(col(cells, "weight")) if "weight" in colmap else None
        volume = parse_number(col(cells, "volume")) if "volume" in colmap else None
        value_num = parse_number(col(cells, "value")) if "value" in colmap else None
        money = None
        if value_num is not None:
            try:
                money = Money(amount=Decimal(str(value_num)), currency=currency)
            except InvalidOperation:
                money = None
        lines.append(ParsedLine(line_no=len(lines) + 1, text_zh=zh, text_en=en, qty=qty, weight_kg=weight, volume_cbm=volume,
                                value=money, source_ref=f"{source} row {row_no}", truncated=truncated))
    return lines, skipped


# --------------------------------------------------------------------------- readers
def _decode_csv(data: bytes) -> str:
    for enc in ("utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_table(data: bytes, kind: str) -> tuple[list[list[Any]], str | None]:
    """Rows of the first sheet that has a header row (xlsx) or of the CSV; raises EmptyFile."""
    if kind == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_vba=False)
        fallback: tuple[list[list[Any]], str] | None = None
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            while rows and not any(cell_text(c) for c in rows[-1]):
                rows.pop()
            if not any(any(cell_text(c) for c in r) for r in rows):
                continue
            try:
                find_header_row(rows)
                return rows, ws.title
            except NoHeaderRow:
                fallback = fallback or (rows, ws.title)
        if fallback:
            return fallback
        raise EmptyFile("the workbook has no sheet with content")
    if kind == "csv":
        text = _decode_csv(data)
        rows = [row for row in csv.reader(io.StringIO(text)) if any(c.strip() for c in row)]
        if not rows:
            raise EmptyFile("the file is empty")
        return rows, None
    raise UnsupportedFileType(f"read_table does not handle {kind}")


def read_pdf_tables(data: bytes) -> tuple[list[list[Any]], list[int]]:
    """Rows from every text page's tables; returns (rows, page numbers that had no extractable text)."""
    import pdfplumber

    from tools.ocr import is_scanned_page

    rows: list[list[Any]] = []
    scanned: list[int] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            if is_scanned_page(page):
                scanned.append(pno)
                continue
            for table in page.extract_tables():
                rows.extend([c if c is not None else "" for c in row] for row in table)
    return rows, scanned


# --------------------------------------------------------------------------- detection helpers
def detect_meta(rows: list[list[Any]], max_scan: int = 15) -> dict[str, str | None]:
    meta: dict[str, str | None] = {"origin": None, "destination": None, "mode": None}
    for row in rows[:max_scan]:
        for raw in row:
            c = cell_text(raw)
            if not c:
                continue
            if meta["mode"] is None:
                m = re.search(r"\b(LCL|FCL)\b", c, re.I)
                if m:
                    meta["mode"] = m.group(1).upper()
            if meta["origin"] is None:
                m = re.search(r"(?:from|起运港|装货港)\s*[:：]?\s*(.+?)\s*(?:→|->|–>|—>|\bto\b|至|到)\s*[:：]?\s*(.+)", c, re.I)
                if m:
                    origin = re.sub(r"^\s*(?:to|至|到)\s*[:：]?\s*", "", m.group(1), flags=re.I).strip(" ,;")
                    dest = re.sub(r"^\s*(?:to|至|到)\s*[:：]?\s*", "", m.group(2), flags=re.I).strip(" ,;")
                    dest = re.split(r"\s{2,}|\s*\|\s*|\s*,\s*ref", dest, flags=re.I)[0].strip()
                    if origin and dest:
                        meta["origin"], meta["destination"] = origin, dest
    return meta


def head_cells(rows: list[list[Any]], max_scan: int = 15) -> list[str]:
    return [cell_text(c) for r in rows[:max_scan] for c in r if cell_text(c)]
