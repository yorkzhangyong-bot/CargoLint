"""classify_cn8 (feature 004, contracts/tools.md §1.6): CN-8 options, EBTI precedent, code checks, the question, the
threshold write rule, fencing and per-line isolation."""
import re
from datetime import date

import pytest

from agent.llm import get_client, set_client_factory
from agent.schemas import (Cn8Input, CreatedBy, DescriptionCheck, Flag, FlagKind, LineStatus, ParsedLine, Classification,
                           Candidate, WrittenBy)
from rag.bti import BTIStore, hs6_from_code
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tests.fakes import FakeRawClient
from tools.common import LineText, ToolContext, set_context

pytestmark = pytest.mark.integration

AS_OF = date(2026, 10, 23)
TOYS = LineText(line_no=6, text_zh="塑料玩具车", text_en="Plastic toy cars")
FRAMES = LineText(line_no=10, text_zh="铝合金自行车架", text_en="Aluminium alloy bicycle frames")
FLASK = LineText(line_no=3, text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask, 500 ml")
MOTOR = "whether the toy cars incorporate a motor"


def ruling(ref, cn_code, valid_from="2024-01-01", valid_to="2030-01-01", description=None):
    return {"reference": ref, "member_state": "DE", "code": hs6_from_code(cn_code), "cn_code": cn_code,
            "chapter": cn_code[:2], "description": description or f"goods of ruling {ref}", "reasoning": "",
            "valid_from": valid_from, "valid_to": valid_to, "language": "EN"}


@pytest.fixture
def make_kb(small_index, fake_embeddings, rules):
    def make(rulings=()):
        bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
        vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
        retriever = HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index, k=6)
        return KnowledgeBase(small_index, retriever, BTIStore(list(rulings)), rules,
                             {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings)
    return make


@pytest.fixture
def fake_client():
    """A FakeRawClient with its own recorded table, wrapped by the real StructuredCaller."""
    made = []

    def make(cn8_table=None, **kw):
        fake = FakeRawClient(recorded={"Cn8Out": cn8_table or {}}, **kw)
        set_client_factory(lambda: fake)
        made.append(fake)
        return get_client(), fake

    yield make
    set_client_factory(None)


def out(cn8, confidence=95, visible=True, attribute="the deciding attribute", precedent=None):
    return {"cn8": cn8, "confidence": confidence, "deciding_attribute": attribute, "attribute_visible": visible,
            "evidence": "the words", "rationale": "because", "precedent": precedent}


def key(line):
    return " / ".join(t for t in (line.text_zh, line.text_en) if t)


class TestChooseCn8:
    def test_a_single_cn8_line_is_taken_without_a_model_call(self, fake_llm, make_kb):
        from tools.classify_cn8 import choose_cn8

        choice = choose_cn8(FLASK, "9617.00", make_kb(), get_client(), 85, AS_OF)
        assert (choice.cn8, choice.confidence, choice.written_by) == ("96170000", 100, WrittenBy.rule)
        assert choice.question is None and choice.error is None
        assert fake_llm.prompts_for("Cn8Out") == []

    def test_written_by_rule_at_or_above_the_threshold_else_a_suggestion(self, fake_llm, make_kb):
        from tools.classify_cn8 import choose_cn8

        written = choose_cn8(FRAMES, "8714.91", make_kb(), get_client(), 85, AS_OF)
        assert (written.cn8, written.confidence, written.written_by) == ("87149110", 95, WrittenBy.rule)
        suggested = choose_cn8(FRAMES, "8714.91", make_kb(), get_client(), 99, AS_OF)
        assert suggested.cn8 == "87149110" and suggested.written_by is None
        assert [c for c, _ in written.options] == ["87149110", "87149130", "87149190"]

    def test_a_missing_attribute_gives_a_question_and_no_cn8(self, fake_llm, make_kb):
        from tools.classify_cn8 import choose_cn8

        choice = choose_cn8(TOYS, "9503.00", make_kb(), get_client(), 85, AS_OF)
        assert choice.cn8 is None and choice.written_by is None and choice.error is None
        assert choice.question == f"Ask the shipper for: {MOTOR}"
        assert choice.deciding_attribute == MOTOR

    def test_a_visible_attribute_with_a_null_code_is_also_a_question(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(TOYS): out(None, visible=True, attribute="a motor")})
        choice = choose_cn8(TOYS, "9503.00", make_kb(), client, 85, AS_OF)
        assert choice.cn8 is None and choice.question == "Ask the shipper for: a motor"

    def test_a_code_outside_the_options_is_discarded(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(TOYS): out("95039999")})
        choice = choose_cn8(TOYS, "9503.00", make_kb(), client, 85, AS_OF)
        assert choice.cn8 is None and choice.written_by is None and choice.question is None
        assert "95039999" in choice.error and "9503.00" in choice.error

    def test_invalid_output_is_retried_once_then_the_step_fails(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        client, fake = fake_client({key(FRAMES): out("87149110")}, invalid_first={("Cn8Out", key(FRAMES)): 2})
        choice = choose_cn8(FRAMES, "8714.91", make_kb(), client, 85, AS_OF)
        assert choice.cn8 is None and choice.error and choice.written_by is None
        assert len(fake.prompts_for("Cn8Out")) == 2   # the first call and one retry

    def test_one_invalid_answer_is_recovered_by_the_retry(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149110")}, invalid_first={("Cn8Out", key(FRAMES)): 1})
        assert choose_cn8(FRAMES, "8714.91", make_kb(), client, 85, AS_OF).cn8 == "87149110"

    def test_a_cited_ruling_must_have_been_sent_and_match_the_cn8(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        kb = make_kb([ruling("DE-FRAME-1", "8714911000"), ruling("DE-FORK-1", "8714913000")])
        client, _ = fake_client({key(FRAMES): out("87149110", precedent="DE-FRAME-1")})
        assert choose_cn8(FRAMES, "8714.91", kb, client, 85, AS_OF).precedent.reference == "DE-FRAME-1"
        for cited in ("XX-NEVER-SENT", "DE-FORK-1"):   # unknown, or a ruling at another CN-8
            client, _ = fake_client({key(FRAMES): out("87149110", precedent=cited)})
            choice = choose_cn8(FRAMES, "8714.91", kb, client, 85, AS_OF)
            assert choice.precedent is None and choice.cn8 == "87149110"

    def test_at_most_two_rulings_per_cn8_line_and_eight_in_all(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        codes = ["9503001000", "9503003000", "9503003500", "9503007500", "9503009500", "9503009900"]
        rulings = [ruling(f"R{c[-4:]}-{i}", c, valid_from=f"202{i}-01-01") for c in codes for i in range(4)]
        rulings += [ruling("OLD-1", "9503007500", valid_from="2019-01-01", valid_to="2022-01-01"),
                    ruling("SKIP-ME", "9503009500", valid_from="2026-01-01")]
        client, fake = fake_client({key(TOYS): out(None, visible=False, attribute=MOTOR)})
        choose_cn8(TOYS, "9503.00", make_kb(rulings), client, 85, AS_OF, exclude_refs=frozenset({"SKIP-ME"}))
        prompt = fake.prompts_for("Cn8Out")[0]
        sent = re.findall(r'line="ruling ([^"]+)"', prompt)
        assert 0 < len(sent) <= 8
        assert all(sum(s.startswith(f"R{c[-4:]}-") for s in sent) <= 2 for c in codes)
        assert "OLD-1" not in sent and "SKIP-ME" not in sent

    def test_untrusted_text_is_fenced_and_comes_first(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        kb = make_kb([ruling("DE-TOY-1", "9503007500", description="Toy car with an electric motor, of plastics")])
        client, fake = fake_client({key(TOYS): out(None, visible=False, attribute=MOTOR)})
        choose_cn8(TOYS, "9503.00", kb, client, 85, AS_OF)
        prompt = fake.prompts_for("Cn8Out")[0]
        assert re.search(r'<data line="6">塑料玩具车 / Plastic toy cars</data>', prompt)
        assert prompt.index('<data line="6">') < prompt.index('<data line="ruling DE-TOY-1">')
        assert re.search(r'<data line="ruling DE-TOY-1">[^<]*Toy car with an electric motor', prompt)


class TestClassifyCn8Lines:
    def test_one_result_per_line_and_a_failure_stays_on_its_line(self, fake_client, make_kb):
        from tools.classify_cn8 import classify_cn8_lines

        client, _ = fake_client({key(FRAMES): out("87149110")}, fail_on={key(TOYS)})
        inp = Cn8Input(lines=[{**TOYS.model_dump(include={"line_no", "text_zh", "text_en"}), "hs6": "9503.00"},
                              {**FRAMES.model_dump(include={"line_no", "text_zh", "text_en"}), "hs6": "8714.91"}],
                       as_of=AS_OF, threshold=85)
        results = classify_cn8_lines(inp, make_kb(), client)
        assert [r.line_no for r in results] == [6, 10]
        failed, ok = results
        assert failed.status == "failed" and failed.choice.error and failed.choice.cn8 is None
        assert failed.choice.hs6 == "9503.00" and len(failed.choice.options) == 19
        assert ok.status == "checked" and ok.choice.cn8 == "87149110"


class TestClassifyCn8Tool:
    def test_the_tool_takes_lines_with_a_decided_hs6_and_no_choice(self, fake_llm, make_kb, memory_store):
        from tools.classify_cn8 import classify_cn8_tool

        s = memory_store
        s.add_lines([ParsedLine(text_zh=FRAMES.text_zh, text_en=FRAMES.text_en),          # line 1
                     ParsedLine(text_zh="配件", text_en="Parts")], CreatedBy.paste)         # line 2
        s.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.ok), status=LineStatus.checked))
        s.update_classification(1, Classification(line_no=1, candidates=[
            Candidate(code="8714.91", subheading_text="t", confidence=95, rationale="r")], status=LineStatus.checked))
        s.update_check(2, DescriptionCheck(line_no=2, flag=Flag(kind=FlagKind.vague, reason="generic"), status=LineStatus.checked))
        s.update_classification(2, Classification(line_no=2, candidates=[
            Candidate(code="8714.91", subheading_text="t", confidence=40, rationale="r")], status=LineStatus.checked))
        set_context(ToolContext(store=s, kb=make_kb(), client=get_client(), workers=1))
        try:
            classify_cn8_tool.invoke({})
        finally:
            set_context(None)
        assert s.get_line(1).current.cn8.cn8 == "87149110"
        assert s.get_line(2).current.cn8 is None           # flagged: its HS-6 is not decided
        prompts = fake_llm.prompts_for("Cn8Out")
        assert len(prompts) == 1 and '<data line="1">' in prompts[0] and '<data line="2">' not in prompts[0]
