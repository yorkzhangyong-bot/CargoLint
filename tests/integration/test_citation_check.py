"""Feature 014a, User Story 5: classify_one checks each candidate's reasoning against the rulings retrieved for the line
in that run and stores the notes on the candidate; the route, the vote and the candidates' order are those of the same
run without the notes, and neither export carries them (spec FR-022, FR-023).

Traceability: 014a/FR-022, 014a/FR-023."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from agent.llm import get_client
from agent.schemas import CitationNote, CreatedBy, DescriptionCheck, Flag, FlagKind, LineStatus, ParsedLine
from agent.store import LineStore
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tools.classify_hs6 import ClassifyContext, classify_lines
from tools.common import LineText

pytestmark = pytest.mark.integration

TEXT = "Silicone mobile phone cases"
RANKING = [("3926.90", 95, "Fitted silicone covers are articles of plastics."),
           ("4202.21", 60, "A case that holds the phone, as in IEBTI1001."),       # IEBTI1001 sits at 3926.90
           ("3924.90", 30, "A household article of plastics, cf. FRBTI0404/26.")]   # never retrieved


def ruling(reference: str, code: str) -> dict:
    return {"reference": reference, "code": code, "cn_code": code.replace(".", "") + "0000", "chapter": code[:2],
            "member_state": reference[:2], "description": f"goods of {reference}", "reasoning": "GRI 1 and 6",
            "valid_from": "2025-01-01", "valid_to": "2027-12-31", "language": "en"}


class FixedHits:
    """A ruling search that returns the given hits, nearest first, whatever its filter."""

    def __init__(self, hits):
        self.hits = list(hits)

    def search_by_vector(self, vector, k, chapter_filter=None, where=None):
        return self.hits[:k]


@pytest.fixture
def kb(small_index, fake_embeddings, rules, fake_llm):
    fake_llm.recorded.setdefault("RankOut", {})[TEXT] = {"candidates": [
        {"code": code, "confidence": conf, "rationale": why, "history_only": False} for code, conf, why in RANKING]}
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    base = KnowledgeBase(small_index, HybridRetriever(bm25=BM25Index([(c.id, c.text) for c in small_index.chunks]),
                                                      vectors=vectors, chunks=small_index, k=6),
                         BTIStore([ruling("IEBTI1001", "3926.90"), ruling("DEBTI2002", "3926.90"), ruling("FRBTI3003", "4202.21"),
                                   ruling("FRBTI0404/26", "3924.90")]),
                         rules, {"embedding_model": "fake", "built_at": "2026-11-18T00:00:00"}, fake_embeddings)
    base.bti_vectors = FixedHits([("bti:IEBTI1001", 0.92), ("bti:DEBTI2002", 0.90), ("bti:FRBTI3003", 0.70)])
    return base


def stored(cls) -> LineStore:
    store = LineStore(backend={}, index=None, clock=lambda: datetime(2026, 11, 18, tzinfo=timezone.utc))
    store.new_shipment(reference="TEST-014A", threshold=85)
    store.add_lines([ParsedLine(line_no=1, text_en=TEXT, source_ref="row 1")], CreatedBy.paste)
    store.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.ok, reason="specific"),
                                           status=LineStatus.checked))
    store.update_classification(1, cls)
    return store


def test_the_notes_are_stored_on_the_candidates_and_change_nothing_else(kb):
    line = LineText(line_no=1, text_en=TEXT, flag_kind="ok", flag_reason="specific")
    out = classify_lines([line], ClassifyContext(as_of=date(2026, 11, 18)), kb=kb, client=get_client())[0]
    assert [c.code for c in out.candidates] == ["3926.90", "4202.21", "3924.90"]
    assert [c.citation_notes for c in out.candidates] == [
        [], [CitationNote(reference="IEBTI1001", kind="other_code", ruling_hs6="3926.90")],
        [CitationNote(reference="FRBTI0404/26", kind="not_retrieved", ruling_hs6=None)]]   # stored, never retrieved
    assert out.candidates[1].rationale == RANKING[1][2]                                    # the reasoning as written
    bare = out.model_copy(update={"candidates": [c.model_copy(update={"citation_notes": []}) for c in out.candidates]})
    with_notes, without = stored(out).get_line(1).current, stored(bare).get_line(1).current
    assert (with_notes.computed_route, with_notes.route_reason, with_notes.hs6_gate) == (
        without.computed_route, without.route_reason, without.hs6_gate)
    assert with_notes.hs6_vote == without.hs6_vote and [c.code for c in with_notes.candidates] == [c.code for c in without.candidates]
    for blob in (stored(out).to_csv_bytes(), stored(out).to_json_bytes()):
        assert b"IEBTI1001" not in blob and b"FRBTI0404" not in blob and b"Cited ruling" not in blob
