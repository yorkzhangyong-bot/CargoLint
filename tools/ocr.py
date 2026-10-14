"""OCR for scanned PDFs and photos: RapidOCR behind a small interface, scanned-page detection,
image preparation and the unreadable cut-off (FR-004, research.md R-10)."""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from PIL import Image, ImageOps

from agent.config import get_settings

SCANNED_TEXT_CHARS = 20


@dataclass
class OCRLine:
    text: str
    score: float
    unreadable: bool
    box: Any = None
    page: int | None = None


class OCREngine(Protocol):
    def __call__(self, image: np.ndarray) -> list[tuple[str, float, Any]]: ...


class RapidOCREngine:
    """RapidOCR (PP-OCR models via onnxruntime); Chinese + English + digits by default."""

    def __init__(self) -> None:
        self._engine: Any = None

    def _load(self) -> Any:
        if self._engine is None:
            from rapidocr import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def __call__(self, image: np.ndarray) -> list[tuple[str, float, Any]]:
        result = self._load()(image)
        txts = getattr(result, "txts", None)
        if not txts:
            return []
        scores = getattr(result, "scores", None) or [0.0] * len(txts)
        boxes = getattr(result, "boxes", None) or [None] * len(txts)
        return list(zip(txts, [float(s) for s in scores], boxes))


def is_scanned_page(page: Any) -> bool:
    """A PDF page with (almost) no extractable text is treated as scanned and goes through OCR."""
    text = page.extract_text() or ""
    return len(text.strip()) < SCANNED_TEXT_CHARS


def prepare_image(source: Image.Image | bytes | str | Path | np.ndarray) -> np.ndarray:
    """EXIF-transposed RGB image as a BGR ndarray (RapidOCR follows the OpenCV convention)."""
    if isinstance(source, np.ndarray):
        return source[:, :, ::-1].copy() if source.ndim == 3 and source.shape[2] == 3 else source
    if isinstance(source, (bytes, bytearray)):
        img = Image.open(io.BytesIO(source))
    elif isinstance(source, (str, Path)):
        img = Image.open(source)
    else:
        img = source
    img = ImageOps.exif_transpose(img) or img
    arr = np.asarray(img.convert("RGB"))
    return arr[:, :, ::-1].copy()


def page_image(page: Any, dpi: int = 200) -> np.ndarray:
    return prepare_image(page.to_image(resolution=dpi).original)


def ocr_lines(image: np.ndarray, engine: OCREngine, min_score: float | None = None, page: int | None = None) -> list[OCRLine]:
    cutoff = get_settings().ocr_min_score if min_score is None else min_score
    out: list[OCRLine] = []
    for text, score, box in engine(image):
        t = (text or "").strip()
        if not t:
            continue
        out.append(OCRLine(text=t, score=float(score), unreadable=float(score) < cutoff, box=box, page=page))
    return out


def ocr_pdf(data: bytes, engine: OCREngine, min_score: float | None = None, pages: list[int] | None = None) -> list[OCRLine]:
    import pdfplumber

    out: list[OCRLine] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            if pages and pno not in pages:
                continue
            out.extend(ocr_lines(page_image(page), engine, min_score, page=pno))
    return out


def ocr_image(data: bytes, engine: OCREngine, min_score: float | None = None) -> list[OCRLine]:
    return ocr_lines(prepare_image(data), engine, min_score, page=1)
