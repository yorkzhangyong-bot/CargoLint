"""classify_hs6: pipeline trace, code-existence validation, index-sourced text, modes, retries (FR-012 … FR-018)."""
import pytest

from agent.llm import get_client
from agent.schemas import LineStatus, RetrievalMode
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tools.classify_hs6 import ClassifyContext, classify_lines
from tools.common import LineText

pytestmark = pytest.mark.integration


@pytest.fixture
def kb(small_index, fake_embeddings, rules):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    retriever = HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index, k=6)
    return KnowledgeBase(small_index, retriever, BTIStore([]), rules, {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings)


def _line(n, zh, en, **kw):
    return LineText(line_no=n, text_zh=zh, text_en=en, **kw)


def test_pipeline_runs_in_order_and_fills_text_from_the_index(fake_llm, kb):
    out = classify_lines([_line(3, "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml")], ClassifyContext(), kb=kb, client=get_client())
    c = out[0]
    assert c.status == LineStatus.checked and c.candidates[0].code == "9617.00"
    assert "Vacuum flasks" in c.candidates[0].subheading_text and c.candidates[0].chapter == "96"
    t = c.retrieval_trace
    assert t.queries and t.mode == RetrievalMode.hybrid
    assert t.bm25_hits > 0 and t.vector_hits > 0 and t.fused >= 1 and t.sent_to_model >= 1
    assert [call["schema"] for call in fake_llm.calls] == ["RankOut"]   # feature 009: no translation call
    assert any(s.id == "hs:9617.00" for s in c.sources)
    assert c.candidates[0].source_ids and "hs:9617.00" in c.candidates[0].source_ids


def test_unknown_codes_are_dropped_and_history_only_propagates(fake_llm, kb):
    out = classify_lines([_line(1, "配件", "Parts")], ClassifyContext(shipper_history_codes=["8452.90"]), kb=kb, client=get_client())
    codes = [c.code for c in out[0].candidates]
    assert codes == ["8452.90", "8487.90"]          # 9999.99 dropped by the existence check
    assert out[0].candidates[0].history_only is True
    assert out[0].no_valid_candidate is False
    assert out[0].retrieval_trace.chapter_filter == ["84"] and "history" in out[0].retrieval_trace.filter_reason


def test_all_codes_dropped_yields_no_valid_candidate(fake_llm, kb):
    out = classify_lines([_line(9, "X", "Unknown widget")], ClassifyContext(), kb=kb, client=get_client())
    assert out[0].candidates == [] and out[0].no_valid_candidate is True and out[0].status == LineStatus.checked


def test_vector_only_mode_reports_no_bm25_hits(fake_llm, kb):
    out = classify_lines([_line(3, "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml")], ClassifyContext(hybrid=False), kb=kb, client=get_client())
    assert out[0].retrieval_trace.mode == RetrievalMode.vector_only and out[0].retrieval_trace.bm25_hits == 0


def test_pure_stop_word_lines_get_no_candidates_and_no_model_calls(fake_llm, kb):
    out = classify_lines([_line(4, "礼品", "Gift", pure_stop_word=True)], ClassifyContext(), kb=kb, client=get_client())
    assert out[0].candidates == [] and out[0].status == LineStatus.checked
    assert fake_llm.calls == []


def test_schema_failure_is_retried_twice_then_the_line_fails(fake_llm, kb):
    key = "不锈钢保温杯 / Stainless steel vacuum flask, 500 ml"
    fake_llm.invalid_first = {("RankOut", key): 3}
    out = classify_lines([_line(3, "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml")], ClassifyContext(), kb=kb, client=get_client())
    assert out[0].status == LineStatus.failed and "RankOut" in (out[0].error_reason or "")
    assert sum(1 for c in fake_llm.calls if c["schema"] == "RankOut") == 3
    fake_llm.calls.clear()
    fake_llm.invalid_first = {("RankOut", key): 2}
    out = classify_lines([_line(3, "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml")], ClassifyContext(), kb=kb, client=get_client())
    assert out[0].status == LineStatus.checked and out[0].candidates[0].code == "9617.00"


def test_english_only_text_skips_the_translation_call(fake_llm, kb):
    classify_lines([_line(5, "", "Cotton T-shirts, knitted")], ClassifyContext(), kb=kb, client=get_client())
    assert [c["schema"] for c in fake_llm.calls] == ["RankOut"]


def test_per_line_isolation_in_a_batch(fake_llm, kb):
    fake_llm.fail_on = {"X / Unknown widget"}
    out = classify_lines([_line(1, "X", "Unknown widget"), _line(2, "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml")],
                         ClassifyContext(), kb=kb, client=get_client(), workers=2)
    assert out[0].status == LineStatus.failed and out[1].status == LineStatus.checked


def test_history_codes_are_injected_as_candidates(fake_llm, small_index, fake_embeddings, rules):
    # an empty retriever: whatever reaches the ranker must come from the shipper's past codes
    empty = HybridRetriever(bm25=BM25Index([]), vectors=InMemoryVectorSearch([], fake_embeddings), chunks=small_index, k=6)
    kb_empty = KnowledgeBase(small_index, empty, BTIStore([]), rules, {}, fake_embeddings)
    out = classify_lines([_line(1, "配件", "Parts", flag_kind="vague")], ClassifyContext(shipper_history_codes=["8452.90", "8452.30"]),
                         kb=kb_empty, client=get_client())
    assert out[0].retrieval_trace.history_chunks == 2 and out[0].retrieval_trace.sent_to_model == 2
    prompt = fake_llm.prompts_for("RankOut")[0]
    assert "[hs:8452.90] (filed before by this shipper)" in prompt and "Description check: VAGUE" in prompt
    assert out[0].candidates[0].code == "8452.90" and out[0].candidates[0].history_only is True


def test_vague_line_confidence_is_capped_in_code(fake_llm, kb):
    out = classify_lines([_line(5, "五金", "Hardware", flag_kind="vague")], ClassifyContext(), kb=kb, client=get_client())
    assert out[0].candidates[0].code == "7318.15" and out[0].candidates[0].confidence == 59
    out_ok = classify_lines([_line(5, "五金", "Hardware", flag_kind="ok")], ClassifyContext(), kb=kb, client=get_client())
    assert out_ok[0].candidates[0].confidence == 80


# --------------------------------------------------------------------------- precedent-driven retrieval (R-18)
PHONE_CASE_RULING = {"reference": "NL-TEST-1", "code": "3926.90", "cn_code": "3926909700", "chapter": "39", "member_state": "NL",
                     "description": "Protective case for a smartphone, of silicone, fitted to the back of the telephone",
                     "reasoning": "GRI 1 and 6; heading 3926", "valid_from": "2025-01-01", "valid_to": "2027-12-31", "language": "EN"}
PHONE_CASE_KEY = "硅胶手机壳 / Silicone mobile phone cases"


def _with_rulings(kb, fake_embeddings, rulings):
    kb.bti = BTIStore(rulings)
    kb.bti_vectors = InMemoryVectorSearch(kb.bti.chunk_texts(), fake_embeddings)
    return kb


def test_matching_rulings_propose_their_code_and_are_cited(fake_llm, kb, fake_embeddings):
    fake_llm.recorded.setdefault("RankOut", {})[PHONE_CASE_KEY] = {"candidates": [
        {"code": "3926.90", "confidence": 88, "rationale": "BTI NL-TEST-1 classifies silicone phone covers here", "history_only": False}]}
    kb = _with_rulings(kb, fake_embeddings, [PHONE_CASE_RULING])
    out = classify_lines([_line(15, "硅胶手机壳", "Silicone mobile phone cases")], ClassifyContext(), kb=kb, client=get_client())[0]
    t = out.retrieval_trace
    assert t.precedent_codes == ["3926.90"] and t.precedent_chunks in (0, 1)   # 0 when plain retrieval already had the chunk
    prompt = fake_llm.prompts_for("RankOut")[0]
    assert "[hs:3926.90]" in prompt and '(BTI precedent NL-TEST-1, NL: "Protective case for a smartphone' in prompt
    assert out.candidates[0].code == "3926.90" and out.candidates[0].source_ids == ["hs:3926.90", "bti:NL-TEST-1"]
    assert any(s.kind.value == "bti" and s.id == "bti:NL-TEST-1" and "3926.90" in s.title for s in out.sources)


def test_precedents_can_be_switched_off_and_unknown_codes_are_ignored(fake_llm, kb, fake_embeddings):
    kb = _with_rulings(kb, fake_embeddings, [PHONE_CASE_RULING, {**PHONE_CASE_RULING, "reference": "XX-9", "code": "9999.99"}])
    off = classify_lines([_line(15, "硅胶手机壳", "Silicone mobile phone cases")], ClassifyContext(precedents=False), kb=kb,
                         client=get_client())[0]
    assert off.retrieval_trace.precedent_codes == [] and not any(s.kind.value == "bti" for s in off.sources)
    assert "BTI precedent" not in fake_llm.prompts_for("RankOut")[0]
    on = classify_lines([_line(15, "硅胶手机壳", "Silicone mobile phone cases")], ClassifyContext(), kb=kb, client=get_client())[0]
    assert on.retrieval_trace.precedent_codes == ["3926.90"]          # 9999.99 is not in the nomenclature: skipped
