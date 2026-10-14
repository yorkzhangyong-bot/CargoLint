"""File parsers: header detection, splitting, caps, encodings, shipper and meta detection (FR-002, FR-003, FR-006, FR-050)."""
import csv
import io
from pathlib import Path

import pytest

from agent.config import MAX_DESC_CHARS, MAX_FILE_BYTES, MAX_LINES
from rag.rules import load_shippers
from tools.parsers import (
    EmptyFile,
    FileTooLarge,
    NoHeaderRow,
    TooManyLines,
    UnsupportedFileType,
    check_caps,
    detect_meta,
    find_header_row,
    read_table,
    rows_to_lines,
    split_mixed,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ROOT = Path(__file__).resolve().parents[2]
SAMPLE_XLSX = ROOT / "data" / "samples" / "sample_packing_list.xlsx"
SAMPLE_CSV = FIXTURES / "sample_packing_list.csv"


class TestSplitMixed:
    @pytest.mark.parametrize("text,zh,en", [
        ("配件 / Parts", "配件", "Parts"),
        ("LED台灯 USB供电\nLED desk lamp, USB powered", "LED台灯 USB供电", "LED desk lamp, USB powered"),
        ("纯棉针织T恤（Cotton T-shirts, knitted）", "纯棉针织T恤", "Cotton T-shirts, knitted"),
        ("硅胶手机壳 (Silicone mobile phone cases)", "硅胶手机壳", "Silicone mobile phone cases"),
        ("不锈钢保温杯 Stainless steel vacuum flask, 500 ml", "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml"),
        ("Stainless steel vacuum flask / 不锈钢保温杯", "不锈钢保温杯", "Stainless steel vacuum flask"),
        ("Plastic toy cars", "", "Plastic toy cars"),
        ("礼品", "礼品", ""),
    ])
    def test_split(self, text, zh, en):
        assert split_mixed(text) == (zh, en)


class TestCaps:
    def test_file_too_large_is_rejected_before_parsing(self):
        with pytest.raises(FileTooLarge):
            check_caps(b"x" * (MAX_FILE_BYTES + 1), "big.xlsx")

    @pytest.mark.parametrize("name", ["list.docx", "list.xlsm", "list.exe", "list"])
    def test_unsupported_types_are_rejected(self, name):
        with pytest.raises(UnsupportedFileType):
            check_caps(b"PK\x03\x04", name)

    @pytest.mark.parametrize("name,kind", [("a.xlsx", "xlsx"), ("A.CSV", "csv"), ("scan.pdf", "pdf"), ("photo.JPG", "jpg"), ("p.jpeg", "jpg"), ("p.png", "png")])
    def test_supported_kinds(self, name, kind):
        assert check_caps(b"data", name) == kind


class TestHeaderAndRows:
    def _rows(self):
        return [["装箱单 PACKING LIST", "", "", "", ""],
                ["Shipper: Yiwu Hengfa Trading", "", "From: Shanghai → To: Hamburg", "LCL", ""],
                ["序号 No.", "品名 Description", "数量 Qty (CTN)", "毛重 G.W. (kg)", "金额 Amount (USD)"],
                [1, "配件 / Parts", "14 CTN", 312, 4180],
                [2, "不锈钢保温杯 / Stainless steel vacuum flask, 500 ml", "60 CTN", "900 kg", "7,800"],
                [3, "", "", "", ""],
                ["合计 Total", "", "74 CTN", 1212, 11980]]

    def test_header_row_detected_by_bilingual_aliases(self):
        idx, colmap = find_header_row(self._rows())
        assert idx == 2
        assert colmap["description"] == 1 and colmap["qty"] == 2 and colmap["weight"] == 3 and colmap["value"] == 4

    def test_no_header_row_raises(self):
        with pytest.raises(NoHeaderRow):
            find_header_row([["just", "some"], ["cells", "here"]])

    def test_rows_become_lines_and_title_empty_and_totals_are_skipped(self):
        rows = self._rows()
        idx, colmap = find_header_row(rows)
        lines, skipped = rows_to_lines(rows, idx, colmap, source="sheet \"装箱单\"")
        assert [l.line_no for l in lines] == [1, 2]
        assert skipped == 2  # the empty row and the totals row (title rows sit above the header)
        first = lines[0]
        assert first.text_zh == "配件" and first.text_en == "Parts" and first.qty == "14 CTN"
        assert first.weight_kg == 312.0 and first.value is not None and float(first.value.amount) == 4180.0 and first.value.currency == "USD"
        assert first.source_ref == 'sheet "装箱单" row 4'
        assert lines[1].weight_kg == 900.0 and float(lines[1].value.amount) == 7800.0

    def test_long_description_is_truncated_and_marked(self):
        rows = [["Description", "Qty"], ["A" * (MAX_DESC_CHARS + 1), "1"]]
        lines, _ = rows_to_lines(rows, 0, {"description": 0, "qty": 1}, source="csv")
        assert len(lines[0].text_en) == MAX_DESC_CHARS and lines[0].truncated is True

    def test_too_many_lines_rejects_the_whole_file(self):
        rows = [["Description", "Qty"]] + [[f"item {i}", "1"] for i in range(MAX_LINES + 1)]
        with pytest.raises(TooManyLines):
            rows_to_lines(rows, 0, {"description": 0, "qty": 1}, source="csv")

    def test_exactly_max_lines_is_accepted(self):
        rows = [["Description", "Qty"]] + [[f"item {i}", "1"] for i in range(MAX_LINES)]
        lines, _ = rows_to_lines(rows, 0, {"description": 0, "qty": 1}, source="csv")
        assert len(lines) == MAX_LINES


class TestReadTable:
    def test_xlsx_first_sheet_with_header(self):
        rows, sheet = read_table(SAMPLE_XLSX.read_bytes(), "xlsx")
        assert sheet == "装箱单" and len(rows) == 16
        assert rows[2][1].startswith("品名")

    def test_csv_utf8_sig(self):
        rows, sheet = read_table(SAMPLE_CSV.read_bytes(), "csv")
        assert sheet is None and rows[2][1].startswith("品名") and "配件" in rows[3][1]

    def test_csv_gbk(self):
        buf = io.StringIO()
        csv.writer(buf).writerows([["品名 Description", "数量 Qty"], ["配件 / Parts", "14 CTN"]])
        rows, _ = read_table(buf.getvalue().encode("gbk"), "csv")
        assert rows[1][0] == "配件 / Parts"

    def test_empty_file_raises(self):
        with pytest.raises(EmptyFile):
            read_table(b"", "csv")
        with pytest.raises(EmptyFile):
            read_table("\n\n".encode("utf-8"), "csv")


class TestDetection:
    def test_shipper_detected_in_the_first_rows(self):
        from rag.rules import detect_shipper

        rows = [["装箱单"], ["Shipper: YIWU HENGFA TRADING CO., LTD"], ["品名 Description", "数量 Qty"]]
        found = detect_shipper([c for r in rows[:15] for c in r], load_shippers())
        assert found is not None and found.name == "Yiwu Hengfa Trading"

    def test_meta_origin_destination_mode(self):
        rows = [["装箱单 PACKING LIST"], ["Shipper: X", "", "From: Shanghai → To: Hamburg", "LCL"], ["品名 Description", "数量 Qty"]]
        meta = detect_meta(rows)
        assert meta == {"origin": "Shanghai", "destination": "Hamburg", "mode": "LCL"}

    def test_meta_absent(self):
        assert detect_meta([["品名 Description", "数量 Qty"], ["配件", "1"]]) == {"origin": None, "destination": None, "mode": None}
