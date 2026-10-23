"""Read-only helpers for the CN-8 step (feature 004, research R-01 and R-02): the CN-8 lines of a subheading, EBTI
rulings grouped by CN-8, and a metadata filter for the BTI vector search."""
from datetime import date

import pytest

from rag.bti import BTIStore, hs6_from_code
from rag.retriever import InMemoryVectorSearch

pytestmark = pytest.mark.unit

AS_OF = date(2026, 10, 23)


def ruling(ref, cn_code, valid_from="2024-01-01", valid_to="2030-01-01", description="goods"):
    return {"reference": ref, "member_state": "DE", "code": hs6_from_code(cn_code), "cn_code": cn_code,
            "chapter": cn_code[:2], "description": description, "reasoning": "", "valid_from": valid_from,
            "valid_to": valid_to, "language": "EN"}


class TestCn8Lines:
    def test_a_subheading_with_several_lines(self, small_index):
        lines = small_index.cn8_lines("9503.00")
        assert len(lines) == 19
        assert [c for c, _ in lines] == sorted(c for c, _ in lines)
        assert ("95030075", "Other toys and models, incorporating a motor > Of plastics") in lines

    def test_a_single_line(self, small_index):
        assert small_index.cn8_lines("9617.00") == [
            ("96170000", "Vacuum flasks and other vacuum vessels, complete with cases; parts thereof other than glass inners")]

    def test_an_unknown_subheading(self, small_index):
        assert small_index.cn8_lines("0000.00") == []


class TestBtiByCn8:
    def test_valid_rulings_grouped_by_cn8_newest_first(self):
        store = BTIStore([ruling("A", "9503007500", valid_from="2023-05-01"),
                          ruling("B", "9503007500", valid_from="2025-02-01"),
                          ruling("C", "9503009500", valid_from="2024-01-01"),
                          ruling("D", "9503009500", valid_from="2020-01-01", valid_to="2023-01-01"),   # expired
                          ruling("E", "9503009500", valid_from="2027-01-01"),                         # not yet valid
                          ruling("F", "950300", valid_from="2025-01-01"),                             # six digits only
                          ruling("G", "9617000000")])                                                  # other subheading
        found = store.by_cn8("9503.00", AS_OF)
        assert set(found) == {"95030075", "95030095"}
        assert [p.reference for p in found["95030075"]] == ["B", "A"]
        assert [p.reference for p in found["95030095"]] == ["C"]
        assert found["95030075"][0].code == "9503007500"   # the ruling's own CN code, not the HS-6

    def test_no_rulings(self):
        assert BTIStore([]).by_cn8("9503.00", AS_OF) == {}


class TestWhereFilter:
    def test_where_keeps_only_matching_metadata(self, fake_embeddings):
        docs = [("bti:A", "plastic toy car with motor", {"code": "9503.00", "chapter": "95"}),
                ("bti:B", "plastic toy car", {"code": "9503.00", "chapter": "95"}),
                ("bti:C", "toy car stand", {"code": "9403.60", "chapter": "94"})]
        vs = InMemoryVectorSearch(docs, fake_embeddings)
        vec = fake_embeddings.embed_query("plastic toy car")
        hits = vs.search_by_vector(vec, 10, None, where={"code": "9503.00"})
        assert {d for d, _ in hits} == {"bti:A", "bti:B"}
        assert {d for d, _ in vs.search_by_vector(vec, 10, None)} == {"bti:A", "bti:B", "bti:C"}
