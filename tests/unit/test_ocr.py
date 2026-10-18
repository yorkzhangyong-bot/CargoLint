"""OCR handling with a fake engine: scanned-page detection, unreadable lines, photo preparation (FR-004)."""
import numpy as np
import pytest
from PIL import Image

from tools.ocr import is_scanned_page, ocr_lines, prepare_image

pytestmark = pytest.mark.unit


class _Page:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class FakeEngine:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, image):
        self.calls.append(image)
        return self.results


def test_page_with_little_or_no_text_is_scanned():
    assert is_scanned_page(_Page("")) is True
    assert is_scanned_page(_Page(None)) is True
    assert is_scanned_page(_Page("1 2 3")) is True
    assert is_scanned_page(_Page("配件 / Parts 14 CTN 312 kg USD 4,180 LED desk lamp")) is False


def test_low_score_or_empty_lines_are_unreadable():
    engine = FakeEngine([("配件 / Parts", 0.92, None), ("??#", 0.31, None), ("", 0.99, None), ("LED desk lamp", 0.61, None)])
    lines = ocr_lines(np.zeros((10, 10, 3), dtype=np.uint8), engine, min_score=0.6)
    assert [(l.text, l.unreadable) for l in lines] == [("配件 / Parts", False), ("??#", True), ("LED desk lamp", False)]
    assert lines[0].score == pytest.approx(0.92)


def test_prepare_image_converts_rgb_to_bgr_and_applies_exif_transpose():
    img = Image.new("RGB", (4, 2), (255, 0, 0))  # pure red
    arr = prepare_image(img)
    assert arr.shape == (2, 4, 3)
    assert tuple(arr[0, 0]) == (0, 0, 255)  # BGR
    rotated = Image.new("RGB", (4, 2), (0, 255, 0))
    exif = rotated.getexif()
    exif[0x0112] = 6  # orientation: rotate 90° CW on display
    buf = __import__("io").BytesIO()
    rotated.save(buf, format="JPEG", exif=exif.tobytes())
    arr2 = prepare_image(buf.getvalue())
    assert arr2.shape[:2] == (4, 2)  # transposed by EXIF orientation


def test_rapidocr_result_with_array_boxes_is_unpacked(monkeypatch):
    """RapidOCR 3 returns `boxes` as a numpy array; testing it with `or` raised 'truth value of an array is ambiguous'."""
    from tools.ocr import RapidOCREngine

    class _Result:
        txts = ("Short Sleeve T-shirt", "QTY")
        scores = (0.98, 0.91)
        boxes = np.zeros((2, 4, 2), dtype=np.float32)

    engine = RapidOCREngine()
    monkeypatch.setattr(engine, "_load", lambda: (lambda image: _Result()))
    out = engine(np.zeros((10, 10, 3), dtype=np.uint8))
    assert [(t, s) for t, s, _ in out] == [("Short Sleeve T-shirt", 0.98), ("QTY", 0.91)]
    assert all(isinstance(b, np.ndarray) and b.shape == (4, 2) for _, _, b in out)

    class _Empty:
        txts = ()
        scores = ()
        boxes = np.zeros((0, 4, 2), dtype=np.float32)

    monkeypatch.setattr(engine, "_load", lambda: (lambda image: _Empty()))
    assert engine(np.zeros((10, 10, 3), dtype=np.uint8)) == []
