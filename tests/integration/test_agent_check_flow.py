"""The agent check flow with a scripted model: tool order, progress events, the completeness guard,
counts from the store, and the agent never writing routes (contracts/tools.md §4)."""
import pytest

from agent.agent import run_turn
from agent.llm import set_chat_model_factory
from agent.schemas import Actor, CreatedBy, LineStatus, ParsedLine
from rag.bti import BTIStore, row_to_ruling
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tests.fakes import ScriptedChatModel, ai_tool_call
from langchain_core.messages import AIMessage

pytestmark = pytest.mark.integration


@pytest.fixture
def kb(small_index, fake_embeddings, rules):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    bti = BTIStore([row_to_ruling({"BTI_REFERENCE": "DE-FLASK", "ISSUING_COUNTRY": "DE", "START_DATE_OF_VALIDITY": "2025-01-01",
                                   "END_DATE_OF_VALIDITY": "2028-01-01", "NOMENCLATURE_CODE": "9617000000************",
                                   "CLASSIFICATION_JUSTIFICATION": "GIR 1", "STATUS": "VALID", "LANGUAGE": "de",
                                   "NAME_AND_ADDRESS": "x", "DESCRIPTION_OF_GOODS": "vacuum flask", "KEYWORDS": ""})])
    return KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index), bti, rules,
                         {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings)


@pytest.fixture
def store_with_lines(memory_store):
    memory_store.add_lines([
        ParsedLine(line_no=1, text_zh="配件", text_en="Parts", source_ref="pasted line 1"),
        ParsedLine(line_no=2, text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask, 500 ml", source_ref="pasted line 2"),
        ParsedLine(line_no=3, text_zh="礼品", text_en="Gift", source_ref="pasted line 3"),
    ], CreatedBy.paste)
    return memory_store


@pytest.fixture
def scripted():
    created = []

    def make(responses):
        model = ScriptedChatModel(responses=responses, seen=[])
        created.append(model)
        set_chat_model_factory(lambda: model)
        return model

    yield make
    set_chat_model_factory(None)


FULL_SCRIPT = [
    ai_tool_call("check_description", {"line_nos": [1, 2, 3]}, "c1"),
    ai_tool_call("classify_hs6", {"line_nos": [1, 2, 3]}, "c2"),
    ai_tool_call("lookup_precedent", {"line_nos": [1, 2, 3]}, "c3"),
    AIMessage(content="All 3 lines checked."),
]


def test_tools_run_in_order_with_progress_and_counts_from_the_store(fake_llm, kb, store_with_lines, scripted):
    scripted(FULL_SCRIPT)
    events = []
    result = run_turn("Check lines 1–3", store_with_lines, kb, on_progress=events.append)
    starts = [e.tool for e in events if e.phase == "start"]
    assert starts == ["check_description", "classify_hs6", "lookup_precedent"]
    assert [e.tool for e in events if e.phase == "end"] == starts
    assert result.text == "All 3 lines checked."
    assert result.counts == store_with_lines.counts()
    assert result.counts == {"auto_accept": 1, "review": 0, "ask_shipper": 2, "needs_action": 2, "accepted": 1}
    assert all(line.current.status == LineStatus.checked for line in store_with_lines.lines)
    assert [s.tool for s in result.check_run.steps] == starts and all(s.run_by == "agent" for s in result.check_run.steps)
    assert store_with_lines.get_line(2).current.candidates[0].precedent.reference == "DE-FLASK"


def test_completeness_guard_runs_the_skipped_step(fake_llm, kb, store_with_lines, scripted):
    scripted([FULL_SCRIPT[0], FULL_SCRIPT[1], AIMessage(content="Done.")])  # agent skipped lookup_precedent
    result = run_turn("Check lines 1–3", store_with_lines, kb)
    tools = [(s.tool, s.run_by) for s in result.check_run.steps]
    assert ("lookup_precedent", "app") in tools
    assert all(line.current.precedents_checked for line in store_with_lines.lines if line.current.candidates)
    assert all(line.current.status == LineStatus.checked for line in store_with_lines.lines)


def test_guard_fails_lines_the_agent_never_checked(fake_llm, kb, store_with_lines, scripted):
    scripted([ai_tool_call("check_description", {"line_nos": [1]}, "c1"), AIMessage(content="Checked one line.")])
    result = run_turn("Check lines 1–3", store_with_lines, kb)
    assert all(line.current.status == LineStatus.checked for line in store_with_lines.lines)  # the app ran the rest
    assert any(s.run_by == "app" for s in result.check_run.steps)


def test_agent_never_writes_routes_or_decisions(fake_llm, kb, store_with_lines, scripted):
    scripted(FULL_SCRIPT)
    run_turn("Check lines 1–3", store_with_lines, kb)
    actors = {r.actor for r in store_with_lines.shipment.audit}
    assert actors <= {Actor.routing_rule, Actor.system}
    assert all(line.current.decision is None for line in store_with_lines.lines)


def test_context_block_is_in_the_model_input_and_raw_text_is_fenced(fake_llm, kb, store_with_lines, scripted):
    model = scripted(FULL_SCRIPT)
    run_turn("Check lines 1–3", store_with_lines, kb)
    first_input = model.seen[0]
    joined = "\n".join(getattr(m, "content", "") for m in first_input if isinstance(getattr(m, "content", ""), str))
    assert "CONTEXT" in joined
    assert '<data line="1">配件 / Parts</data>' in joined
