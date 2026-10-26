"""Feature 006, the HS-6 eval's leakage guard: a line's own ruling can be kept out of the BTI precedents that propose
HS-6 codes and are shown to the ranking model (ClassifyContext.exclude_refs). The default excludes nothing, as before."""
from datetime import date
from types import SimpleNamespace

import pytest

from agent.llm import get_client
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch, precedent_codes
from tests.eval import hs6_eval   # at collection: the offline guard replaces the OpenRouter client inside a test
from tools.classify_hs6 import ClassifyContext, classify_lines
from tools.common import LineText

pytestmark = pytest.mark.integration

OWN = {"reference": "NL-TEST-1", "code": "3926.90", "cn_code": "3926909700", "chapter": "39", "member_state": "NL",
       "description": "Protective case for a smartphone, of silicone, fitted to the back of the telephone",
       "reasoning": "GRI 1 and 6; heading 3926", "valid_from": "2025-01-01", "valid_to": "2027-12-31", "language": "EN"}
LINE = LineText(line_no=15, text_zh="硅胶手机壳", text_en="Silicone mobile phone cases")


@pytest.fixture
def kb(small_index, fake_embeddings, rules):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    retriever = HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index, k=6)
    kb = KnowledgeBase(small_index, retriever, BTIStore([OWN]), rules,
                       {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings)
    kb.bti_vectors = InMemoryVectorSearch(kb.bti.chunk_texts(), fake_embeddings)
    return kb


def test_precedent_codes_leave_an_excluded_ruling_out():
    vectors = SimpleNamespace(search_by_vector=lambda vec, k, chapter_filter=None: [("bti:OWN", 0.99), ("bti:B", 0.8)])
    records = {"bti:OWN": {"reference": "OWN", "code": "4202.12", "member_state": "IE", "description": "the line itself"},
               "bti:B": {"reference": "B", "code": "3926.90", "member_state": "DE", "description": "a similar case"}}
    store = SimpleNamespace(get=lambda ruling_id, as_of=None: records.get(ruling_id))
    assert [p["code"] for p in precedent_codes(vectors, store, [[1.0]], k=3)] == ["4202.12", "3926.90"]   # as before
    kept = precedent_codes(vectors, store, [[1.0]], k=3, exclude_refs=frozenset({"OWN"}))
    assert [(p["code"], p["reference"]) for p in kept] == [("3926.90", "B")]


def test_without_the_guard_the_lines_own_ruling_reaches_the_ranking_model(fake_llm, kb):
    out = classify_lines([LINE], ClassifyContext(), kb=kb, client=get_client())[0]
    assert out.retrieval_trace.precedent_codes == ["3926.90"]
    assert "BTI precedent NL-TEST-1" in fake_llm.prompts_for("RankOut")[0]     # its code and its own excerpt


def test_with_the_guard_the_lines_own_ruling_is_kept_out(fake_llm, kb):
    out = classify_lines([LINE], ClassifyContext(exclude_refs=frozenset({"NL-TEST-1"})), kb=kb, client=get_client())[0]
    assert out.retrieval_trace.precedent_codes == []
    assert "NL-TEST-1" not in fake_llm.prompts_for("RankOut")[0]
    assert not any(s.id == "bti:NL-TEST-1" for s in out.sources)


def test_the_hs6_eval_keeps_each_lines_own_ruling_out(fake_llm, kb):
    """tests/eval/hs6_eval.run_once: the line's own ruling is logged as its nearest hit, not eligible, and never reaches
    the model; another ruling at the same code still proposes it."""
    other ={**OWN, "reference": "DE-TEST-2", "member_state": "DE", "description": "Smartphone case of silicone rubber"}
    kb.bti = BTIStore([OWN, other])
    kb.bti_vectors = InMemoryVectorSearch(kb.bti.chunk_texts(), kb.embeddings)
    line = {"reference": "NL-TEST-1", "chapter": "39", "hs6": "3926.90", "cn8": "39269097", "language": "en",
            "description": OWN["description"]}
    rows, _ = hs6_eval.run_once([line], kb, get_client(), date(2026, 10, 23), workers=1)
    row = rows[0]
    assert (row["own_rank"], row["nearest_hits"][0]["reference"], row["nearest_hits"][0]["eligible"]) == (1, "NL-TEST-1", False)
    assert [h["eligible"] for h in row["nearest_hits"][1:]] == [True]
    assert row["precedent_codes"] == ["3926.90"] and row["expected"] == "3926.90"
    prompt = fake_llm.prompts_for("RankOut")[0]
    assert "BTI precedent DE-TEST-2" in prompt and "NL-TEST-1" not in prompt
    assert "search_by_vector" not in vars(kb.bti_vectors)   # the logging search is gone after the run
