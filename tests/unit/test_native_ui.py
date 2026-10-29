"""Native Streamlit (feature 012, FR-016, SC-004; constitution 1.10.0, Principle VI): no custom HTML, JavaScript or
components in app.py and ui/, and CSS only in ui/theme.py: one <style> block, injected once through
st.markdown(unsafe_allow_html=True), that adjusts only spacing, padding, margins, font sizes, widths and card
heights."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "ui" / "theme.py"
FORBIDDEN = re.compile(r"unsafe_allow_html|st\.html\(|components\.|<style|<div|<span|<script")
NEVER = re.compile(r"st\.html\(|components\.|<div|<span|<script|javascript:|@import|url\(", re.IGNORECASE)
LAYOUT = re.compile(r"(padding|margin)(-(top|right|bottom|left))?|(row-|column-)?gap|font-size|line-height"
                    r"|(min-|max-)?width")
HEIGHT = re.compile(r"(min-|max-)?height")
CARDS = "st-key-count_"                           # the count cards, the one place a height may change


def layout_only(css: str) -> list[str]:
    """The declarations that are not layout: anything but spacing, padding, margins, font sizes and widths, and
    heights outside the count cards."""
    bad = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        for declaration in filter(None, (d.strip() for d in body.split(";"))):
            prop = declaration.split(":", 1)[0].strip().lower()
            if not (LAYOUT.fullmatch(prop) or (HEIGHT.fullmatch(prop) and CARDS in selector)):
                bad.append(f"{selector.strip()} {{ {declaration} }}")
    return bad


def test_no_custom_html_css_or_components_outside_the_theme():
    files = [ROOT / "app.py", *sorted(f for f in (ROOT / "ui").glob("*.py") if f != THEME)]
    found = [f"{f.name}:{n}: {line.strip()}" for f in files
             for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if FORBIDDEN.search(line)]
    assert len(files) > 5 and found == []


def test_the_theme_is_one_layout_only_style_block():
    from ui import theme

    source = THEME.read_text(encoding="utf-8")
    assert not NEVER.search(source)                              # no HTML element, script, component or import
    assert source.count("unsafe_allow_html") == source.count("<style>") == source.count("</style>") == 1
    assert re.findall(r"<\s*([a-zA-Z]+)", source) == ["style"]   # the one tag is the style block
    assert theme.CSS.strip() and layout_only(theme.CSS) == []


def test_the_layout_check_catches_anything_else():
    assert layout_only(".x { display: none; }") == [".x { display: none }"]
    assert layout_only(".x { pointer-events: none }") == [".x { pointer-events: none }"]
    assert layout_only(".x { height: 9px }") == [".x { height: 9px }"]          # a height outside the cards
    assert layout_only('[class*="st-key-count_"] { min-height: 90px; padding-top: 0 }') == []
    assert layout_only("/* a { color: red } */ .x { margin: 0 !important; font-size: 1rem }") == []
