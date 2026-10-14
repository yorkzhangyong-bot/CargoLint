"""Knowledge-base loaders: EBTI filtering and SKOS nomenclature parsing (Principle IV, FR-015, FR-046)."""
from datetime import date
from pathlib import Path

import pytest

from rag.bti import BTIStore, filter_rows, hs6_from_code, row_to_ruling
from rag.nomenclature import build_chunks, parse_skos

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TODAY = date(2026, 10, 14)


def _row(code="8452900000************", start="2024-01-10", end="2027-01-09", status="Valid", country="DE", ref="DEBTI12345/24-1"):
    return {
        "BTI_REFERENCE": ref, "ISSUING_COUNTRY": country, "START_DATE_OF_VALIDITY": start, "END_DATE_OF_VALIDITY": end,
        "NOMENCLATURE_CODE": code, "CLASSIFICATION_JUSTIFICATION": "GIR 1 and 6; part solely for sewing machines", "STATUS": status,
        "INVALIDATION_REASON": "", "INVALIDATION_JUSTIFICATION": "", "LANGUAGE": "DE", "PLACE_OF_ISSUE": "Hannover",
        "DATE_OF _ISSUE": "2024-01-10", "NAME_AND_ADDRESS": "Some Company GmbH, Example Str. 1, 30159 Hannover",
        "DESCRIPTION_OF_GOODS": "Steel bobbin cases for industrial sewing machines", "KEYWORDS": "sewing machines; parts",
    }


class TestBTI:
    def test_hs6_from_masked_10_digit_code(self):
        assert hs6_from_code("8716800000************") == "8716.80"
        assert hs6_from_code("9617000000") == "9617.00"
        assert hs6_from_code("8452 90 00 00") == "8452.90"

    def test_filter_keeps_only_valid_rows_in_target_chapters(self):
        rows = [
            _row(),                                                  # keep
            _row(end="2025-12-31", ref="OLD"),                       # expired
            _row(status="Invalidated", ref="INV"),                   # invalidated
            _row(code="3924100000************", ref="CH39"),         # other chapter
            _row(end="", ref="OPEN"),                                # no end date -> keep
        ]
        kept = list(filter_rows(rows, chapters={"84", "96"}, today=TODAY))
        assert [r["BTI_REFERENCE"] for r in kept] == ["DEBTI12345/24-1", "OPEN"]

    def test_row_to_ruling_drops_personal_data_and_derives_fields(self):
        r = row_to_ruling(_row())
        assert "NAME_AND_ADDRESS" not in r and "name_and_address" not in r
        assert r["reference"] == "DEBTI12345/24-1" and r["member_state"] == "DE"
        assert r["code"] == "8452.90" and r["cn_code"] == "8452900000"
        assert r["valid_from"] == "2024-01-10" and r["valid_to"] == "2027-01-09"
        assert r["description"].startswith("Steel bobbin") and r["reasoning"].startswith("GIR 1")
        assert r["language"] == "DE" and r["chapter"] == "84"

    def test_store_lookup_filters_expired_and_orders_newest_first(self):
        store = BTIStore([
            row_to_ruling(_row(ref="A", start="2023-01-01", end="2026-01-01")),      # expired on TODAY
            row_to_ruling(_row(ref="B", start="2024-05-01", end="2027-05-01")),
            row_to_ruling(_row(ref="C", start="2025-02-01", end="2028-06-01")),
            row_to_ruling(_row(ref="D", start="2022-02-01", end="2030-01-01")),
            row_to_ruling(_row(ref="E", start="2025-09-01", end="2029-01-01")),
            row_to_ruling(_row(ref="F", code="9617000000************", start="2025-01-01", end="2028-01-01")),
        ])
        hits = store.lookup("8452.90", as_of=TODAY)
        assert [h.reference for h in hits] == ["E", "C", "B"]       # newest first, max 3, A expired, D older
        assert store.lookup("9617.00", as_of=TODAY)[0].reference == "F"
        assert store.lookup("3924.10", as_of=TODAY) == []
        assert store.lookup("8452.90", as_of=date(2031, 1, 1)) == []


class TestSKOS:
    def test_parse_concepts(self):
        concepts = list(parse_skos(FIXTURES / "cn2026_excerpt.rdf"))
        assert len(concepts) == 9
        by_code = {c.code: c for c in concepts if c.code}
        assert "961700" in by_code and by_code["961700"].depth == 4
        assert by_code["9617"].label_en.startswith("Vacuum flasks")
        assert by_code["96081010"].dashes == "- -"

    def test_build_chunks_one_per_hs6_with_hierarchy_text_and_metadata(self):
        chunks = build_chunks(list(parse_skos(FIXTURES / "cn2026_excerpt.rdf")), source="CN 2026 fixture", edition_year=2026)
        by_id = {c.id: c for c in chunks}
        assert set(by_id) == {"hs:9608.10", "hs:9608.20", "hs:9617.00"}
        vac = by_id["hs:9617.00"]
        assert "Chapter 96" in vac.text and "Miscellaneous manufactured articles" in vac.text
        assert "Heading 9617" in vac.text and "Vacuum flasks" in vac.text
        assert "Subheading 9617.00" in vac.text
        assert "thermos" in vac.text  # scope note included
        assert vac.metadata == {"chapter": "96", "heading": "9617", "subheading": "9617.00", "language": "en",
                                "source": "CN 2026 fixture", "edition_year": 2026}
        pens = by_id["hs:9608.10"]
        assert "9608 10 10" in pens.text and "rolling ball pens" in pens.text   # CN-8 lines folded in
        assert "9608 10 92" in pens.text and "replaceable refill" in pens.text
        assert "9608 20" not in pens.text
