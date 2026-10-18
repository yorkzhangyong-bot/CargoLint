"""Named error scenarios (constitution Principle VII; FR-004, FR-048, FR-049, FR-050).

Scenarios already covered elsewhere: a code that does not exist (test_classify_hs6), a model returning the
wrong schema (test_classify_hs6), a contradicting reply (test_apply_reply), unsupported and oversize files
(test_parsers, test_parse_packing_list), mixed-language cells (test_parsers). Here: scanned PDFs and photos
through OCR, and the transport-error policy.
"""
import io

import pytest
from PIL import Image

from agent.llm import classify_error
from tools.parse_packing_list import parse_packing_list
from tools.parsers import EmptyFile, split_mixed

pytestmark = pytest.mark.integration


class FakeOCR:
    def __init__(self, lines):
        self.lines = lines
        self.calls = 0

    def __call__(self, image):
        self.calls += 1
        return self.lines


def _image_only_pdf() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (600, 300), "white").save(buf, format="PDF")
    return buf.getvalue()


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 200), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_scanned_pdf_lines_below_the_ocr_cutoff_are_marked_unreadable_not_guessed():
    engine = FakeOCR([("配件 / Parts", 0.93, None), ("LED desk lamp, USB powered", 0.88, None), ("Plastc toy crs", 0.41, None), ("12", 0.9, None)])
    out = parse_packing_list(_image_only_pdf(), "scan.pdf", ocr_engine=engine, min_score=0.6)
    assert engine.calls == 1
    assert [(l.text_zh, l.text_en, l.unreadable) for l in out.lines] == [
        ("配件", "Parts", False), ("", "LED desk lamp, USB powered", False), ("", "Plastc toy crs", True)]
    assert any("OCR" in w for w in out.warnings) and any("unreadable" in w or "read reliably" in w for w in out.warnings)
    assert out.lines[2].source_ref.startswith("page 1")


def test_photo_goes_through_ocr_with_a_warning_and_no_quantities():
    engine = FakeOCR([("不锈钢保温杯 Stainless steel vacuum flask 500 ml", 0.9, None)])
    out = parse_packing_list(_png(), "photo.png", ocr_engine=engine)
    assert out.lines[0].text_zh == "不锈钢保温杯" and out.lines[0].text_en.startswith("Stainless steel")
    assert out.lines[0].qty is None and any("photo" in w.lower() for w in out.warnings)


def test_scan_with_nothing_readable_is_an_error_not_an_empty_shipment():
    with pytest.raises(EmptyFile):
        parse_packing_list(_image_only_pdf(), "blank.pdf", ocr_engine=FakeOCR([]))


def test_mixed_language_cell_variants():
    assert split_mixed("LED台灯 USB供电\nLED desk lamp, USB powered") == ("LED台灯 USB供电", "LED desk lamp, USB powered")
    assert split_mixed("硅胶手机壳（Silicone mobile phone cases）") == ("硅胶手机壳", "Silicone mobile phone cases")


class _Err(Exception):
    def __init__(self, status, msg="x"):
        super().__init__(msg)
        self.status_code = status


def test_transport_error_policy_retries_transient_but_not_credit_errors():
    assert classify_error(_Err(429, "rate limit")) == (True, "The model is rate-limited; retrying shortly.")
    assert classify_error(_Err(503, "no provider"))[0] is True
    retry, msg = classify_error(_Err(402, "insufficient credits"))
    assert retry is False and "credits" in msg.lower()
    assert classify_error(_Err(403))[0] is False


def test_internal_errors_are_not_reported_as_model_problems():
    retry, msg = classify_error(ValueError("The truth value of an array with more than one element is ambiguous"))
    assert retry is False and "internal error" in msg and "model" in msg
    assert classify_error(ConnectionError("boom"))[0] is True   # transport errors keep the retry message
