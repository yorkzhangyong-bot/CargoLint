"""lookup_precedent: current rulings only, newest first, none_found (FR-015)."""
from datetime import date

import pytest

from rag.bti import BTIStore, row_to_ruling
from tools.lookup_precedent import lookup_precedents

pytestmark = pytest.mark.integration


def _row(ref, code, start, end, country="DE"):
    return {"BTI_REFERENCE": ref, "ISSUING_COUNTRY": country, "START_DATE_OF_VALIDITY": start, "END_DATE_OF_VALIDITY": end,
            "NOMENCLATURE_CODE": code, "CLASSIFICATION_JUSTIFICATION": "GIR 1 and 6", "STATUS": "VALID", "LANGUAGE": "de",
            "NAME_AND_ADDRESS": "x", "DESCRIPTION_OF_GOODS": f"goods for {ref}", "KEYWORDS": ""}


@pytest.fixture
def bti():
    return BTIStore([
        row_to_ruling(_row("DE-OLD", "8452900000************", "2021-01-01", "2024-01-01")),
        row_to_ruling(_row("DE-NEW", "8452900000************", "2025-03-01", "2028-03-01")),
        row_to_ruling(_row("FR-MID", "8452900000************", "2024-06-01", "2027-06-01", "FR")),
        row_to_ruling(_row("NL-A", "8452900000************", "2023-01-01", "2026-12-31", "NL")),
        row_to_ruling(_row("DE-FLASK", "9617000000************", "2025-01-01", "2028-01-01")),
    ])


def test_lookup_filters_expired_orders_newest_first_and_caps_at_three(bti):
    out = lookup_precedents(["8452.90", "9617.00", "3924.10"], bti, as_of=date(2026, 10, 14))
    assert [p.reference for p in out.by_code["8452.90"]] == ["DE-NEW", "FR-MID", "NL-A"]
    assert out.by_code["9617.00"][0].reference == "DE-FLASK"
    assert out.by_code["9617.00"][0].url and "DE-FLASK" in out.by_code["9617.00"][0].url
    assert out.none_found == ["3924.10"]


def test_codes_are_deduplicated(bti):
    out = lookup_precedents(["9617.00", "9617.00"], bti, as_of=date(2026, 10, 14))
    assert list(out.by_code) == ["9617.00"]
