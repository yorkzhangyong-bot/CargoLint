"""apply_shipper_reply: target resolution, single-line scope, versions, lock, contradiction (FR-036 … FR-039, SC-009)."""
import copy

import pytest

from agent.llm import get_client
from agent.schemas import (
    Candidate,
    Classification,
    CreatedBy,
    Decision,
    DecisionRoute,
    DescriptionCheck,
    Flag,
    FlagKind,
    LineStatus,
    ParsedLine,
    Route,
    RuleSource,
)
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tools.apply_shipper_reply import apply_reply, parse_line_ref

pytestmark = pytest.mark.unit


@pytest.fixture
def kb(small_index, fake_embeddings, rules):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    return KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index), BTIStore([]), rules, {}, fake_embeddings)


@pytest.fixture
def checked(memory_store):
    s = memory_store
    s.add_lines([ParsedLine(text_zh="配件", text_en="Parts", source_ref="r1"),
                 ParsedLine(text_zh="LED台灯 USB供电", text_en="LED desk lamp, USB powered", source_ref="r2"),
                 ParsedLine(text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask, 500 ml", source_ref="r3"),
                 ParsedLine(text_zh="礼品", text_en="Gift", source_ref="r4")], CreatedBy.file)

    def c(code, conf, hist=False):
        return Candidate(code=code, subheading_text="t", confidence=conf, rationale="r", history_only=hist)

    s.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.vague, rule_source=RuleSource.ics2_unacceptable, matched_term="parts", ask_for=["material"])))
    s.update_classification(1, Classification(line_no=1, candidates=[c("8452.90", 31, True), c("8708.99", 24), c("8487.90", 19)]))
    s.update_check(2, DescriptionCheck(line_no=2, flag=Flag(kind=FlagKind.ok)))
    s.update_classification(2, Classification(line_no=2, candidates=[c("9405.21", 72)]))
    s.update_check(3, DescriptionCheck(line_no=3, flag=Flag(kind=FlagKind.ok)))
    s.update_classification(3, Classification(line_no=3, candidates=[c("9617.00", 96)]))
    s.update_check(4, DescriptionCheck(line_no=4, flag=Flag(kind=FlagKind.stop_word, rule_source=RuleSource.firm_stop_words, matched_term="gift", ask_for=["material"], pure_stop_word=True)))
    return s


def _snapshot(store, skip: int):
    return {l.line_no: copy.deepcopy(l.model_dump()) for l in store.lines if l.line_no != skip}


class TestParseLineRef:
    @pytest.mark.parametrize("text,expected", [
        ("line 1 is steel bobbin cases for industrial sewing machines", 1),
        ("Line 12: plastic cups", 12),
        ("第3行是塑料杯", 3),
        ("塑料杯", None),
        ("line 1 and line 2 are both steel bolts", None),  # ambiguous
        ("line 2 is the same as line 2 above", 2),
    ])
    def test_parse(self, text, expected):
        assert parse_line_ref(text) == expected


class TestTargetResolution:
    def test_named_line_is_the_target(self, fake_llm, kb, checked):
        out = apply_reply("line 1 is steel bobbin cases for industrial sewing machines", 1, None, checked, kb, get_client())
        assert out.target_line_no == 1 and out.applied_to_selected is False and out.needs_line is False

    def test_selected_line_is_the_fallback(self, fake_llm, kb, checked):
        out = apply_reply("塑料杯", None, 3, checked, kb, get_client())
        assert out.target_line_no == 3 and out.applied_to_selected is True

    def test_nothing_named_nothing_selected_asks_and_changes_nothing(self, fake_llm, kb, checked):
        before = _snapshot(checked, skip=-1)
        out = apply_reply("塑料杯", None, None, checked, kb, get_client())
        assert out.needs_line is True and out.target_line_no is None
        assert _snapshot(checked, skip=-1) == before and fake_llm.calls == []

    def test_unknown_line_number_asks(self, fake_llm, kb, checked):
        out = apply_reply("line 99 is plastic cups", 99, None, checked, kb, get_client())
        assert out.needs_line is True


class TestApplying:
    def test_only_the_target_line_changes(self, fake_llm, kb, checked):
        before = _snapshot(checked, skip=1)
        out = apply_reply("line 1 is steel bobbin cases for industrial sewing machines", 1, None, checked, kb, get_client())
        assert out.new_version_no == 2
        assert _snapshot(checked, skip=1) == before  # SC-009

    def test_new_version_fields_and_recheck(self, fake_llm, kb, checked):
        apply_reply("line 1 is steel bobbin cases for industrial sewing machines", 1, None, checked, kb, get_client())
        line = checked.get_line(1)
        v = line.current
        assert v.version_no == 2 and v.created_by == CreatedBy.shipper_reply
        assert v.reply_text == "line 1 is steel bobbin cases for industrial sewing machines"
        assert v.extracted.material == "steel" and v.extracted.part_name == "bobbin cases" and v.extracted.use == "industrial sewing machines"
        assert v.text_en == "steel bobbin cases for industrial sewing machines" and v.text_zh == ""
        assert v.flag.kind == FlagKind.ok and v.status == LineStatus.checked
        assert v.candidates[0].code == "8452.90" and v.candidates[0].confidence == 96
        assert v.precedents_checked is True

    def test_previously_flagged_line_becomes_ready_to_accept_not_auto(self, fake_llm, kb, checked):
        apply_reply("line 1 is steel bobbin cases for industrial sewing machines", 1, None, checked, kb, get_client())
        line = checked.get_line(1)
        assert line.current.computed_route == Route.review and "ready to accept" in line.current.route_reason.lower()
        assert checked.ready_to_accept(line) is True
        checked.set_decision(1, Decision(route=DecisionRoute.accepted, decided_code="8452.90"))
        assert checked.effective_route(line) == "accepted"

    def test_reply_to_an_accepted_line_clears_the_decision_and_goes_to_review(self, fake_llm, kb, checked):
        checked.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        apply_reply("line 2 is steel bobbin cases for industrial sewing machines", 2, None, checked, kb, get_client())
        line = checked.get_line(2)
        assert line.current.decision is None and line.current.version_no == 2
        assert checked.effective_route(line) == Route.review

    def test_chapter_change_sets_a_contradiction_note(self, fake_llm, kb, checked):
        out = apply_reply("塑料杯", None, 3, checked, kb, get_client())
        v = checked.get_line(3).current
        assert v.text_zh == "塑料杯" and v.candidates[0].code == "3924.10"
        assert out.contradiction_note and "9617.00" in out.contradiction_note and "3924.10" in out.contradiction_note
        assert v.contradiction_note == out.contradiction_note
        assert checked.effective_route(checked.get_line(3)) == Route.review

    def test_no_previous_candidates_is_never_a_contradiction(self, fake_llm, kb, checked):
        out = apply_reply("line 4 is steel bobbin cases for industrial sewing machines", 4, None, checked, kb, get_client())
        assert out.contradiction_note is None
        line = checked.get_line(4)
        assert line.current.candidates and line.current.computed_route == Route.review  # flagged before → click needed


class TestChineseReply:
    def test_chinese_reply_is_extracted_and_kept_verbatim(self, fake_llm, kb, checked):
        apply_reply("塑料杯", None, 3, checked, kb, get_client())
        v = checked.get_line(3).current
        assert v.reply_text == "塑料杯" and v.extracted.material == "plastic" and v.text_en == "plastic cups for drinking"
        extract_prompts = fake_llm.prompts_for("ExtractOut")
        assert extract_prompts and '<data line="3">塑料杯</data>' in extract_prompts[0]
