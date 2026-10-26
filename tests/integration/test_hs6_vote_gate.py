"""Feature 006: classify_one stores the HS-6 vote of the nearest eligible EBTI rulings, read from the same ruling search
that proposes precedent codes: the rulings below the similarity floor and the line's own ruling (exclude_refs) do not
vote, and a majority at the model's 2nd or 3rd candidate is recorded."""
from datetime import date

import pytest

from agent.llm import get_client
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tests.eval import hs6_eval   # at collection: the offline guard replaces the OpenRouter client inside a test
from tools.classify_hs6 import ClassifyContext, classify_lines
from tools.common import LineText

pytestmark = pytest.mark.integration

TEXT = "Silicone mobile phone cases"
LINE = LineText(line_no=1, text_en=TEXT, flag_kind="ok", flag_reason="specific enough")
TOP3 = [("3926.90", 95), ("4202.21", 60), ("3924.90", 30)]          # the model's ranking


def ruling(reference, code, member_state):
    return {"reference": reference, "code": code, "cn_code": code.replace(".", "") + "0000", "chapter": code[:2],
            "member_state": member_state, "description": f"goods of {reference}", "reasoning": "GRI 1 and 6",
            "valid_from": "2025-01-01", "valid_to": "2027-12-31", "language": "EN"}


RULINGS = [ruling("IE-1", "3926.90", "IE"), ruling("DE-2", "3926.90", "DE"), ruling("FR-3", "4202.21", "FR"),
           ruling("NL-4", "4202.21", "NL"), ruling("PL-5", "4202.21", "PL"), ruling("XI-6", "3924.90", "XI")]


class FixedHits:
    """A ruling search that returns the given hits, nearest first, and counts its calls."""

    def __init__(self, hits):
        self.hits, self.calls = list(hits), 0

    def search_by_vector(self, vector, k, chapter_filter=None, where=None):
        self.calls += 1
        return self.hits[:k]


@pytest.fixture
def kb(small_index, fake_embeddings, rules, fake_llm):
    fake_llm.recorded.setdefault("RankOut", {})[TEXT] = {"candidates": [
        {"code": code, "confidence": conf, "rationale": "r", "history_only": False} for code, conf in TOP3]}
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    return KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index, k=6), BTIStore(RULINGS),
                         rules, {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings)


def classify(kb, hits, **ctx):
    kb.bti_vectors = FixedHits(hits)
    return classify_lines([LINE], ClassifyContext(as_of=date(2026, 10, 23), **ctx), kb=kb, client=get_client())[0]


def test_the_vote_reads_the_rulings_the_precedent_search_found(kb):
    out = classify(kb, [("bti:IE-1", 0.92), ("bti:DE-2", 0.90), ("bti:FR-3", 0.70), ("bti:XI-6", 0.60)])
    v = out.hs6_vote
    assert (v.majority, v.majority_share, v.agrees, v.candidate) == ("3926.90", 0.5, True, None)
    assert v.competing == [("3926.90", ["IE", "DE"]), ("4202.21", ["FR"]), ("3924.90", ["XI"])]
    assert out.retrieval_trace.precedent_codes[0] == "3926.90" and kb.bti_vectors.calls == 1   # one search for both


def test_a_majority_at_the_second_candidate_is_recorded(kb):
    out = classify(kb, [("bti:FR-3", 0.92), ("bti:NL-4", 0.90), ("bti:IE-1", 0.80), ("bti:PL-5", 0.70)])
    assert (out.hs6_vote.majority, out.hs6_vote.agrees, out.hs6_vote.candidate) == ("4202.21", False, 2)


def test_rulings_below_the_similarity_floor_leave_no_vote(kb):
    out = classify(kb, [("bti:IE-1", 0.39), ("bti:DE-2", 0.30)])
    assert out.hs6_vote is None and out.retrieval_trace.precedent_codes == ["3926.90"]   # they still propose codes


def test_the_lines_own_ruling_does_not_vote(kb):
    out = classify(kb, [("bti:FR-3", 0.99), ("bti:IE-1", 0.92), ("bti:DE-2", 0.90)], exclude_refs=frozenset({"FR-3"}))
    assert (out.hs6_vote.majority, out.hs6_vote.majority_share, out.hs6_vote.agrees) == ("3926.90", 1.0, True)


def test_the_vote_does_not_depend_on_precedents_proposing_codes(kb):
    out = classify(kb, [("bti:IE-1", 0.92), ("bti:DE-2", 0.90)], precedents=False)
    assert out.retrieval_trace.precedent_codes == [] and out.hs6_vote.agrees is True


def test_the_hs6_eval_keeps_the_models_own_confidence_before_the_vague_cap(kb):
    kb.bti_vectors = FixedHits([("bti:IE-1", 0.92), ("bti:DE-2", 0.90)])
    line = {"reference": "XX-0", "chapter": "39", "hs6": "3926.90", "cn8": "39269097", "language": "en", "description": TEXT}
    row = hs6_eval.run_once([line], kb, get_client(), date(2026, 10, 23), workers=1)[0][0]
    assert (row["flag"], row["top1"], row["confidence"], row["raw_confidence"]) == ("vague", "3926.90", 59, 95)
    assert row["raw"] == [{"code": code, "confidence": conf} for code, conf in TOP3]       # as the model ranked them
