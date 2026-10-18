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


# --------------------------------------------------------------------------- the format variants (tests/fixtures/make_sample_variants.py)
SAMPLES = ROOT / "data" / "samples"


def test_gbk_invoice_csv_with_chinese_headers_parses():
    out = parse_packing_list((SAMPLES / "sample_invoice_ningbo.csv").read_bytes(), "sample_invoice_ningbo.csv")
    assert len(out.lines) == 10 and out.header_row == 4 and out.skipped_rows == 4 and out.warnings == []
    assert out.shipper_name_detected == "Ningbo Brightlite Electronics"
    assert out.meta == {"origin": "宁波", "destination": "汉堡", "mode": "LCL"}
    by_no = {l.line_no: l for l in out.lines}
    assert (by_no[2].text_zh, by_no[2].text_en) == ("USB充电器 双口", "USB chargers dual port")   # full-width parentheses
    assert (by_no[4].text_zh, by_no[4].text_en) == ("塑料衣架", "")                               # Chinese only
    assert (by_no[5].text_zh, by_no[5].text_en) == ("", "Cotton canvas tote bags")               # English only
    assert by_no[1].qty == "300" and by_no[1].weight_kg == pytest.approx(540.0) and by_no[1].volume_cbm == pytest.approx(1.8)
    assert float(by_no[1].value.amount) == pytest.approx(2400.0) and by_no[1].value.currency == "USD"
    assert by_no[8].text_zh == "样品"                                                            # firm stop-word line


def test_english_text_pdf_table_parses_without_ocr():
    out = parse_packing_list((SAMPLES / "sample_packing_list_foshan.pdf").read_bytes(), "sample_packing_list_foshan.pdf")
    assert len(out.lines) == 8 and out.header_row == 3 and out.skipped_rows == 3 and out.warnings == []
    assert out.shipper_name_detected is None                                                      # a shipper the demo history does not know
    assert out.meta == {"origin": "Foshan", "destination": "Hamburg", "mode": "LCL"}
    first, last = out.lines[0], out.lines[-1]
    assert first.text_en.startswith("LED ceiling panel lights") and first.text_zh == ""
    assert first.qty == "120" and first.weight_kg == pytest.approx(540.0) and first.volume_cbm == pytest.approx(2.4)
    assert float(first.value.amount) == pytest.approx(3600.0) and first.value.currency == "USD"
    assert last.text_en == "Lamp holders E27, phenolic resin"


def test_photo_sample_is_a_valid_image_for_the_ocr_path():
    from tools.ocr import prepare_image
    from tools.parsers import check_caps

    data = (SAMPLES / "sample_packing_list_photo.jpg").read_bytes()
    assert check_caps(data, "sample_packing_list_photo.jpg") == "jpg"
    assert prepare_image(data).shape == (1000, 1240, 3)   # OCR itself is exercised manually: it needs the RapidOCR models
