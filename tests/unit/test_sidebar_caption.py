"""The TARIC caption in the sidebar's knowledge-base expander (feature 002, US4, FR-024). No Streamlit session needed."""
from datetime import date
from types import SimpleNamespace

import pytest

from ui.sidebar import taric_caption

pytestmark = pytest.mark.unit


def kb(mismatches: int = 105, loaded: bool = True):
    snapshot = SimpleNamespace(snapshot_date=date(2026, 10, 1), cn8_mismatches=mismatches)
    return SimpleNamespace(taric=SimpleNamespace(snapshot=snapshot) if loaded else None)


@pytest.mark.parametrize("count, text", [
    (105, "TARIC snapshot 2026-10-01 · 105 CN-8 mismatches"),
    (1, "TARIC snapshot 2026-10-01 · 1 CN-8 mismatch"),
    (0, "TARIC snapshot 2026-10-01 · 0 CN-8 mismatches"),
])
def test_a_loaded_snapshot_shows_its_date_and_mismatch_count(count, text):
    assert taric_caption(kb(count)) == text


def test_no_snapshot_reads_taric_not_loaded():
    assert taric_caption(kb(loaded=False)) == "TARIC not loaded"
