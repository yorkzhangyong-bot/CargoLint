"""Generate three more sample packing lists in different file formats (data/samples/).

    python tests/fixtures/make_sample_variants.py

- sample_invoice_ningbo.csv       GBK-encoded ERP export: Chinese headers, a unit column, mixed cells with full-width
                                  parentheses, a Chinese-only and an English-only line, a 合计 total row, a known shipper
- sample_packing_list_foshan.pdf  text PDF with a ruled table, English only, a new shipper, metadata in the title rows
                                  (hand-written PDF: no PDF library is installed; pdfplumber reads the table)
- sample_packing_list_photo.jpg   bilingual list rendered as a slightly rotated, noisy phone photo (OCR path), known shipper

Synthetic data; no real companies. The sibling make_sample_xlsx.py generates the original XLSX sample.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"
FONT = Path("C:/Windows/Fonts/msyh.ttc")   # Microsoft YaHei: Chinese + Latin; any CJK-capable TTF works

# --------------------------------------------------------------------------- A. CSV (GBK, Chinese headers)
CSV_ROWS: list[list[str]] = [
    ["商业发票 COMMERCIAL INVOICE", "", "", "", "", "", "", ""],
    ["卖方 Seller: 宁波亮光电子 NINGBO BRIGHTLITE ELECTRONICS CO., LTD", "", "", "", "", "", "", ""],
    ["起运港: 宁波 至 汉堡  LCL", "", "", "", "发票号 Invoice No.: NBE-2026-1107", "", "", ""],
    ["序号", "品名/Description", "数量", "单位", "毛重(KG)", "体积(CBM)", "单价", "金额(USD)"],
    ["1", "LED吸顶灯 / LED ceiling lights, 24 W", "300", "PCS", "540", "1.8", "8.00", "2400.00"],
    ["2", "USB充电器（双口）/ USB chargers (dual port)", "1200", "PCS", "180", "0.6", "2.10", "2520.00"],
    ["3", "蓝牙音箱 / Bluetooth speakers, portable", "400", "PCS", "260", "1.1", "6.50", "2600.00"],
    ["4", "塑料衣架", "6000", "PCS", "420", "3.2", "0.12", "720.00"],
    ["5", "Cotton canvas tote bags", "2000", "PCS", "300", "1.5", "1.40", "2800.00"],
    ["6", "电子产品 / Electronic products", "150", "PCS", "95", "0.4", "9.00", "1350.00"],
    ["7", "配件 / Accessories", "800", "PCS", "120", "0.5", "0.90", "720.00"],
    ["8", "样品 / Samples", "20", "PCS", "6", "0.05", "0.00", "0.00"],
    ["9", "不锈钢厨房剪刀 / Stainless steel kitchen scissors", "1500", "PCS", "330", "0.9", "1.20", "1800.00"],
    ["10", "智能手表表带 硅胶 / Silicone smart-watch straps", "3000", "PCS", "90", "0.4", "0.80", "2400.00"],
    ["", "合计 Total", "15370", "PCS", "2341", "10.45", "", "17310.00"],
]


def write_csv(path: Path) -> None:
    with path.open("w", encoding="gbk", newline="") as f:
        writer = csv.writer(f)
        for row in CSV_ROWS:
            writer.writerow(row)


# --------------------------------------------------------------------------- B. PDF (text table, English only)
PDF_INFO = ["PACKING LIST  -  Shipper: Foshan Brightway Lighting Co., Ltd.",
            "From: Foshan to Hamburg | LCL | Invoice FBL-2026-0918 | Date 2026-10-12"]
PDF_HEADER = ["No.", "Description of Goods", "Quantity", "Unit", "G.W. (kg)", "Measurement (CBM)", "Amount (USD)"]
PDF_LINES = [
    ["1", "LED ceiling panel lights, 40 W, 600 x 600 mm", "120", "PCS", "540", "2.40", "3600.00"],
    ["2", "Aluminium profiles for LED strips, 2 m", "500", "PCS", "610", "1.90", "2250.00"],
    ["3", "Garden solar lamps, plastic housing", "800", "PCS", "720", "3.10", "4000.00"],
    ["4", "Electrical parts", "60", "CTN", "480", "1.60", "2100.00"],
    ["5", "Spare parts for machines", "12", "CTN", "310", "0.80", "1500.00"],
    ["6", "Power banks 10000 mAh, lithium-ion", "1000", "PCS", "260", "0.70", "6500.00"],
    ["7", "Christmas decorations, plastic", "900", "PCS", "350", "4.20", "1800.00"],
    ["8", "Lamp holders E27, phenolic resin", "5000", "PCS", "210", "0.60", "1250.00"],
]
PDF_TOTAL = ["", "TOTAL", "", "", "3480", "15.30", "23000.00"]
COL_WIDTHS = [28, 232, 52, 36, 56, 72, 69]          # points; sums to 545
PAGE_W, PAGE_H, LEFT, TOP, ROW_H = 595, 842, 25, 790, 19


def _pdf_text(s: str) -> str:
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_content() -> str:
    ops: list[str] = ["0.6 w 0 0 0 RG 0 0 0 rg"]
    xs = [LEFT]
    for w in COL_WIDTHS:
        xs.append(xs[-1] + w)
    right = xs[-1]
    rows = [[t] for t in PDF_INFO] + [PDF_HEADER] + PDF_LINES + [PDF_TOTAL]
    y = TOP
    for i, row in enumerate(rows):
        top, bottom = y, y - ROW_H
        ops.append(f"{LEFT} {top} m {right} {top} l S")
        if i == len(rows) - 1:
            ops.append(f"{LEFT} {bottom} m {right} {bottom} l S")
        ops.append(f"{LEFT} {top} m {LEFT} {bottom} l S")
        ops.append(f"{right} {top} m {right} {bottom} l S")
        font = "/F2" if i in (0, len(PDF_INFO)) else "/F1"
        if len(row) == 1:                                    # title rows span the table width
            ops.append(f"BT {font} 10 Tf 1 0 0 1 {LEFT + 4} {top - 13} Tm ({_pdf_text(row[0])}) Tj ET")
        else:
            for j, cell in enumerate(row):
                ops.append(f"{xs[j]} {top} m {xs[j]} {bottom} l S")
                ops.append(f"BT {font} 8.5 Tf 1 0 0 1 {xs[j] + 3} {top - 13} Tm ({_pdf_text(cell)}) Tj ET")
        y = bottom
    ops.append(f"BT /F1 8 Tf 1 0 0 1 {LEFT} {y - 18} Tm ({_pdf_text('Synthetic demo document generated for CargoLint tests; no real companies.')}) Tj ET")
    return "\n".join(ops)


def pdf_bytes() -> bytes:
    stream = pdf_content()
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        f"<< /Length {len(stream.encode('cp1252'))} >>\nstream\n{stream}\nendstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out.encode("cp1252")))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out.encode("cp1252"))
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("cp1252")


# --------------------------------------------------------------------------- C. photo (bilingual, OCR path)
PHOTO_INFO = ["装箱单 PACKING LIST", "Shipper: 深圳凯达玩具 SHENZHEN KAIDA TOYS CO., LTD", "From: Shenzhen → Hamburg · LCL  Ref: SKT-2026-0233"]
PHOTO_HEADER = ["序号 No.", "货物描述 Description", "数量 Qty (CTN)", "毛重 G.W. (kg)"]
PHOTO_LINES = [
    ["1", "塑料玩具车 / Plastic toy cars", "22", "264"],
    ["2", "毛绒玩具熊 / Plush teddy bears", "35", "280"],
    ["3", "儿童拼图 纸板 / Children's jigsaw puzzles, cardboard", "18", "216"],
    ["4", "遥控玩具飞机 / Remote-control toy aircraft", "10", "150"],
    ["5", "礼品 / Gift", "4", "48"],
    ["6", "玩具配件 / Toy accessories", "8", "72"],
    ["7", "儿童滑板车 / Children's kick scooters", "16", "320"],
    ["8", "塑料积木 / Plastic building blocks", "30", "390"],
]
PHOTO_TOTAL = ["", "合计 Total", "143", "1740"]


def write_photo(path: Path) -> None:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    w, h = 1240, 1000
    img = Image.new("RGB", (w, h), (252, 252, 250))
    draw = ImageDraw.Draw(img)
    title_font = ImageFont.truetype(str(FONT), 40)
    text_font = ImageFont.truetype(str(FONT), 24)
    small_font = ImageFont.truetype(str(FONT), 22)
    draw.text((w // 2, 60), PHOTO_INFO[0], fill=(20, 20, 20), font=title_font, anchor="mm")
    draw.text((90, 120), PHOTO_INFO[1], fill=(30, 30, 30), font=small_font)
    draw.text((90, 160), PHOTO_INFO[2], fill=(30, 30, 30), font=small_font)
    col_x = [90, 190, 790, 980, 1150]
    row_h, top = 54, 220
    rows = [PHOTO_HEADER] + PHOTO_LINES + [PHOTO_TOTAL]
    for i, row in enumerate(rows):
        y0, y1 = top + i * row_h, top + (i + 1) * row_h
        draw.rectangle([col_x[0], y0, col_x[-1], y1], outline=(60, 60, 60), width=2)
        for x in col_x[1:-1]:
            draw.line([(x, y0), (x, y1)], fill=(60, 60, 60), width=2)
        for j, cell in enumerate(row):
            draw.text((col_x[j] + 12, y0 + 13), cell, fill=(25, 25, 25), font=text_font)
    draw.text((90, top + len(rows) * row_h + 30), "Synthetic demo document generated for CargoLint tests; no real companies.",
              fill=(90, 90, 90), font=small_font)
    img = img.rotate(1.3, resample=Image.BICUBIC, expand=False, fillcolor=(248, 248, 246))
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(7)
    arr = np.clip(arr + rng.normal(0, 4, arr.shape), 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path, format="JPEG", quality=82)


def main() -> int:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    write_csv(SAMPLES / "sample_invoice_ningbo.csv")
    (SAMPLES / "sample_packing_list_foshan.pdf").write_bytes(pdf_bytes())
    write_photo(SAMPLES / "sample_packing_list_photo.jpg")
    for name in ("sample_invoice_ningbo.csv", "sample_packing_list_foshan.pdf", "sample_packing_list_photo.jpg"):
        print(f"wrote {SAMPLES / name} ({(SAMPLES / name).stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
