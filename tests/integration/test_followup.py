"""Grounded follow-ups: the context block carries the selected line's stored results and, on request,
the rule lists; the agent answers from it without tool calls (FR-030, FR-031)."""
import pytest
from langchain_core.messages import AIMessage

from agent.agent import run_turn
from agent.llm import set_chat_model_factory
from agent.prompts import SYSTEM_PROMPT, build_context
from agent.schemas import (
    Candidate,
    Classification,
    CreatedBy,
    DescriptionCheck,
    Flag,
    FlagKind,
    ParsedLine,
    RetrievalTrace,
    RuleSource,
    Source,
    SourceKind,
)
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tests.fakes import ScriptedChatModel

pytestmark = pytest.mark.integration


@pytest.fixture
def kb(small_index, fake_embeddings, rules):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    return KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index), BTIStore([]), rules, {}, fake_embeddings)


@pytest.fixture
def checked(memory_store):
    s = memory_store
    s.add_lines([ParsedLine(text_zh="配件", text_en="Parts", source_ref="r1"),
                 ParsedLine(text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask, 500 ml", source_ref="r3")], CreatedBy.file)
    s.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.vague, rule_source=RuleSource.ics2_unacceptable, matched_term="parts", ask_for=["material"])))
    s.update_classification(1, Classification(
        line_no=1,
        candidates=[Candidate(code="8452.90", subheading_text="Parts of sewing machines", confidence=31, rationale="shipper history only", history_only=True)],
        retrieval_trace=RetrievalTrace(original="配件 / Parts", queries=["parts", "accessories", "fittings"], chapter_filter=["84"],
                                       filter_reason="shipper history", bm25_hits=5, vector_hits=8, fused=9, sent_to_model=6),
        sources=[Source(id="hs:8452.90", kind=SourceKind.nomenclature, title="HS chapter 84, subheading 8452.90 — Parts of sewing machines"),
                 Source(id="history:shipper", kind=SourceKind.shipper_history, title="Shipper's past filings", excerpt="8452.90")]))
    s.update_check(2, DescriptionCheck(line_no=2, flag=Flag(kind=FlagKind.ok)))
    s.update_classification(2, Classification(line_no=2, candidates=[Candidate(code="9617.00", subheading_text="Vacuum flasks", confidence=96, rationale="r")]))
    return s


def test_context_has_the_selected_lines_full_result(checked, rules):
    ctx = build_context(checked.shipment, selected_line_no=1, message="why only 31% on line 1?", rules=rules, counts=checked.counts())
    assert "selected line 1 in full" in ctx
    assert "8452.90" in ctx and "31%" in ctx and "[history only]" in ctx
    assert "hs:8452.90" in ctx and "history:shipper" in ctx
    assert "queries ['parts', 'accessories', 'fittings']" in ctx and "chapter filter ['84']" in ctx
    assert "BM25 5 + vectors 8 -> fused 9 -> 6 chunks" in ctx
    assert "rationale: shipper history only" in ctx
    assert "rule lists" not in ctx  # not asked about terms


def test_context_includes_rule_lists_only_when_asked_about_terms(checked, rules):
    ctx = build_context(checked.shipment, None, "Which terms does customs reject?", rules=rules)
    assert "rule lists" in ctx and "ics2_unacceptable" in ctx and "v4.10" in ctx and "firm stop-words" in ctx
    ctx2 = build_context(checked.shipment, None, "What is the weight of line 2?", rules=rules)
    assert "rule lists" not in ctx2


def test_system_prompt_requires_answers_from_stored_results():
    assert "only from the stored results" in SYSTEM_PROMPT and "say so" in SYSTEM_PROMPT.lower()


def test_followup_turn_answers_without_tool_calls(fake_llm, kb, checked):
    model = ScriptedChatModel(responses=[AIMessage(content="The 31% comes entirely from the shipper's history; the text supports no code.")], seen=[])
    set_chat_model_factory(lambda: model)
    try:
        result = run_turn("Why only 31% on line 1?", checked, kb, selected_line_no=1)
    finally:
        set_chat_model_factory(None)
    assert result.tool_calls == 0 and result.text.startswith("The 31%")
    assert result.check_run is not None and result.check_run.steps == []
    joined = "\n".join(getattr(m, "content", "") for m in model.seen[0] if isinstance(getattr(m, "content", ""), str))
    assert "selected line 1 in full" in joined and "SELECTED LINE: 1" in joined
    assert checked.get_line(1).current.retrieval_trace is not None  # the UI reads the Retrieval steps from the store
