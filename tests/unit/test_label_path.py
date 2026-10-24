"""NomenclatureIndex.label_path (feature 005 polish): an HS-6 row reads its heading and subheading labels, because the
subheading label alone is often "Other" or "Of cotton". Chunks below copy the real index's text format."""
from __future__ import annotations

import pytest

from rag.nomenclature import NomenclatureChunk, NomenclatureIndex

pytestmark = pytest.mark.unit


def chunk(code: str, heading: str, sub: str, scope: str = "") -> NomenclatureChunk:
    lines = [f"Chapter {code[:2]} — A chapter", f"Heading {code[:4]} — {heading}", f"Subheading {code} — {sub}"]
    lines += [scope] if scope else []
    lines += [f"CN {code[:4]} {code[5:7]} 00 — {sub}"]
    return NomenclatureChunk(id=f"hs:{code}", text="\n".join(lines), metadata={"subheading": code})


@pytest.fixture
def index():
    return NomenclatureIndex([
        chunk("6109.10", "T-shirts, singlets and other vests, knitted or crocheted", "Of cotton",
              "T-shirts, singlets and other vests of cotton, knitted or crocheted"),
        chunk("6105.10", "Men's or boys' shirts, knitted or crocheted", "Of cotton"),
        chunk("8409.99", "Parts suitable for use solely or principally with the engines of heading 8407 or 8408", "Other"),
        chunk("9503.00", "Tricycles, scooters, pedal cars and similar wheeled toys; dolls' carriages; dolls; other toys",
              "Tricycles, scooters, pedal cars and similar wheeled toys; dolls; other toys"),
    ])


def test_the_heading_comes_before_a_bare_subheading_label(index):
    assert index.label_path("6109.10") == ["T-shirts, singlets and other vests, knitted or crocheted", "Of cotton"]
    assert index.label_path("6105.10") == ["Men's or boys' shirts, knitted or crocheted", "Of cotton"]
    assert index.label_path("8409.99") == [
        "Parts suitable for use solely or principally with the engines of heading 8407 or 8408", "Other"]


def test_one_label_when_the_heading_is_not_subdivided(index):
    assert index.label_path("9503.00") == ["Tricycles, scooters, pedal cars and similar wheeled toys; dolls; other toys"]


def test_one_label_when_the_subheading_repeats_its_heading(small_index):
    assert small_index.label_path("6109.10") == ["T-shirts, singlets and other vests, knitted or crocheted, of cotton"]


def test_an_unknown_subheading(index):
    assert index.label_path("0000.00") == []
