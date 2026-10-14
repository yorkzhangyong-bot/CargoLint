"""The upload check flow: sample workbook → four tool calls → 12 lines with the expected routes →
clerk decision (US2 independent test; FR-027, FR-028, FR-033)."""
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from agent.agent import run_turn
from agent.llm import set_chat_model_factory
from agent.schemas import ChosenHow, CreatedBy, Decision, DecisionRoute, LineStatus
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from rag.rules import load_shippers
from tests.fakes import ScriptedChatModel, ai_tool_call
from tools.parse_packing_list import parse_packing_list
from ui.upload import needs_confirmation, start_shipment_from_parsed

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_XLSX = ROOT / "data" / "samples" / "sample_packing_list.xlsx"


@pytest.fixture
def kb(small_index, fake_embeddings, rules):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    return KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index), BTIStore([]), rules,
                         {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings, shippers=load_shippers())


@pytest.fixture
def scripted():
    def make(responses):
        model = ScriptedChatModel(responses=responses, seen=[])
        set_chat_model_factory(lambda: model)
        return model

    yield make
    set_chat_model_factory(None)


def test_upload_flow_end_to_end(fake_llm, kb, memory_store, scripted):
    store = memory_store
    file_ref = store.register_file(SAMPLE_XLSX.read_bytes(), "PL_HF_0472.xlsx")
    scripted([
        ai_tool_call("parse_packing_list", {"file_ref": file_ref}, "c1"),
        ai_tool_call("check_description", {"all_pending": True}, "c2"),
        ai_tool_call("classify_hs6", {"all_pending": True}, "c3"),
        ai_tool_call("lookup_precedent", {"all_pending": True}, "c4"),
        AIMessage(content="All 12 lines checked."),
    ])
    events = []
    result = run_turn("Check the packing list for HF-0472.", store, kb, on_progress=events.append, file_ref=file_ref)
    assert [e.tool for e in events if e.phase == "start"] == ["parse_packing_list", "check_description", "classify_hs6", "lookup_precedent"]
    assert len(store.lines) == 12 and all(l.current.status == LineStatus.checked for l in store.lines)
    assert store.shipment.shipper.name == "Yiwu Hengfa Trading" and store.shipment.shipper.known is True
    assert store.shipment.origin == "Shanghai" and store.shipment.mode == "LCL"
    assert result.counts == {"auto_accept": 7, "review": 2, "ask_shipper": 3, "needs_action": 5, "accepted": 7}
    assert store.get_line(1).current.candidates[0].history_only is True  # shipper history used for "Parts"
    assert all(s.run_by == "agent" for s in result.check_run.steps)
    parse_step = result.check_run.steps[0]
    assert "12 lines" in parse_step.summary and "header row 3" in parse_step.summary

    store.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
    assert store.get_line(2).current.decision.chosen_how == ChosenHow.top
    assert store.counts() == {"auto_accept": 7, "review": 1, "ask_shipper": 3, "needs_action": 4, "accepted": 8}


def test_parsed_file_starts_a_shipment_with_detected_fields(memory_store):
    parsed = parse_packing_list(SAMPLE_XLSX.read_bytes(), "PL_HF_0472.xlsx")
    shipment = start_shipment_from_parsed(memory_store, parsed, "PL_HF_0472.xlsx", len(SAMPLE_XLSX.read_bytes()), load_shippers(),
                                          threshold=85, hybrid=True, reference="HOL-2026-10-0472")
    assert shipment.shipper.name == "Yiwu Hengfa Trading" and shipment.shipper.past_shipment_count == 6
    assert shipment.source.name == "PL_HF_0472.xlsx" and shipment.source.kind == "xlsx"
    assert len(memory_store.lines) == 12 and memory_store.lines[0].current.created_by == CreatedBy.file
    assert memory_store.lines[0].qty == "14 CTN" and memory_store.lines[0].weight_kg == 312.0


def test_second_upload_needs_confirmation_only_when_a_shipment_is_open(memory_store):
    assert needs_confirmation(memory_store) is False
    parsed = parse_packing_list(SAMPLE_XLSX.read_bytes(), "a.xlsx")
    start_shipment_from_parsed(memory_store, parsed, "a.xlsx", 10, load_shippers(), threshold=85, hybrid=True)
    assert needs_confirmation(memory_store) is True
