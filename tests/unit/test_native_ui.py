"""Native Streamlit only (feature 012, FR-016, SC-004): no custom HTML, CSS or components in app.py and ui/."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = re.compile(r"unsafe_allow_html|st\.html\(|components\.|<style|<div|<span")


def test_no_custom_html_css_or_components():
    files = [ROOT / "app.py", *sorted((ROOT / "ui").glob("*.py"))]
    found = [f"{f.name}:{n}: {line.strip()}" for f in files
             for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if FORBIDDEN.search(line)]
    assert len(files) > 5 and found == []
