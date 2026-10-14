"""Generate the bundled sample packing list (xlsx + csv twin) from data/samples/sample_lines.json.

    python tests/fixtures/make_sample_xlsx.py

The workbook mimics a real consolidation list: a title block, a header row on row 3 with bilingual
headers, mixed Chinese/English description cells (slash, newline and parentheses variants) and a
totals row. Synthetic data; no real companies.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_JSON = ROOT / "data" / "samples" / "sample_lines.json"
XLSX_OUT = ROOT / "data" / "samples" / "sample_packing_list.xlsx"
CSV_OUT = ROOT / "tests" / "fixtures" / "sample_packing_list.csv"

HEADER = ["序号 No.", "品名 Description", "数量 Qty (CTN)", "毛重 G.W. (kg)", "金额 Amount (USD)"]


def description_cell(line: dict) -> str:
    zh, en, n = line["text_zh"], line["text_en"], line["line_no"]
    if n == 2:
        return f"{zh}\n{en}"
    if n == 5:
        return f"{zh}（{en}）"
    return f"{zh} / {en}"


def rows_from_sample() -> tuple[str, list[list]]:
    data = json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))
    s = data["shipment"]
    rows: list[list] = [
        ["装箱单 PACKING LIST", "", "", "", ""],
        [f"Shipper: {s['shipper']} (义乌恒发贸易)", "", f"From: {s['origin']} → To: {s['destination']}", s["mode"], f"Ref: {s['reference']}"],
        HEADER,
    ]
    total_qty = total_w = total_v = 0.0
    for line in data["lines"]:
        qty_n = float(line["qty"].split()[0])
        rows.append([line["line_no"], description_cell(line), line["qty"], line["weight_kg"], line["value_usd"]])
        total_qty += qty_n
        total_w += line["weight_kg"]
        total_v += line["value_usd"]
    rows.append(["合计 Total", "", f"{int(total_qty)} CTN", total_w, total_v])
    return s["sheet"], rows


def main() -> int:
    sheet, rows = rows_from_sample()
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for row in rows:
        ws.append(row)
    XLSX_OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(XLSX_OUT)
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    print(f"wrote {XLSX_OUT} ({len(rows)} rows, sheet {sheet!r}) and {CSV_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
