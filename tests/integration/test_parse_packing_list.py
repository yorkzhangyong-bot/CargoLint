"""parse_packing_list on the bundled sample workbook and its CSV twin (FR-002 … FR-006, FR-042)."""
from pathlib import Path

import pytest

from tools.parse_packing_list import parse_packing_list

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_XLSX = ROOT / "data" / "samples" / "sample_packing_list.xlsx"
SAMPLE_CSV = ROOT / "tests" / "fixtures" / "sample_packing_list.csv"


@pytest.mark.parametrize("path,name", [(SAMPLE_XLSX, "PL_HF_0472.xlsx"), (SAMPLE_CSV, "PL_HF_0472.csv")])
def test_sample_parses_into_12_lines(path, name, sample_lines):
    out = parse_packing_list(path.read_bytes(), name)
    assert len(out.lines) == 12
    assert out.header_row == 3 and out.skipped_rows == 3
    assert out.sheet == ("装箱单" if name.endswith("xlsx") else None)
    assert out.shipper_name_detected == "Yiwu Hengfa Trading"
    assert out.meta == {"origin": "Shanghai", "destination": "Hamburg", "mode": "LCL"}
    for got, exp in zip(out.lines, sample_lines["lines"]):
        assert (got.text_zh, got.text_en) == (exp["text_zh"], exp["text_en"]), got
        assert got.qty == exp["qty"]
        assert got.weight_kg == pytest.approx(exp["weight_kg"])
        assert float(got.value.amount) == pytest.approx(exp["value_usd"]) and got.value.currency == "USD"
    assert out.lines[0].source_ref.endswith("row 4")
    assert out.warnings == []


def test_unsupported_and_oversize_files_are_rejected_before_parsing():
    from tools.parsers import FileTooLarge, UnsupportedFileType

    with pytest.raises(UnsupportedFileType):
        parse_packing_list(b"hello", "list.docx")
    with pytest.raises(FileTooLarge):
        parse_packing_list(b"x" * 21_000_000, "list.csv")


def test_csv_without_header_row_is_an_error():
    from tools.parsers import NoHeaderRow

    with pytest.raises(NoHeaderRow):
        parse_packing_list("a,b\nc,d\n".encode("utf-8"), "x.csv")
