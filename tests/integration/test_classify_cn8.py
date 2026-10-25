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


def ruling(ref, cn_code, valid_from="2024-01-01", valid_to="2030-01-01", description=None, member_state="DE"):
    return {"reference": ref, "member_state": member_state, "code": hs6_from_code(cn_code), "cn_code": cn_code,
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


def out(cn8, confidence=95, visible=True, attribute="the deciding attribute", precedent=None, evidence=""):
    return {"cn8": cn8, "confidence": confidence, "deciding_attribute": attribute, "attribute_visible": visible,
            "evidence": evidence, "rationale": "because", "precedent": precedent}


def key(line):
    return " / ".join(t for t in (line.text_zh, line.text_en) if t)


class TestChooseCn8:
    def test_a_single_cn8_line_is_taken_without_a_model_call(self, fake_llm, make_kb):
        from tools.classify_cn8 import choose_cn8

        choice = choose_cn8(FLASK, "9617.00", make_kb(), get_client(), 85, AS_OF)
        assert (choice.cn8, choice.confidence, choice.written_by) == ("96170000", 100, WrittenBy.rule)
        assert choice.question is None and choice.error is None
        assert fake_llm.prompts_for("Cn8Out") == []

    def test_written_by_rule_with_evidence_an_agreeing_precedent_and_the_threshold(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        kb = make_kb([ruling("DE-FRAME-1", "8714911000")])
        client, _ = fake_client({key(FRAMES): out("87149110", precedent="DE-FRAME-1", evidence="bicycle frames")})
        written = choose_cn8(FRAMES, "8714.91", kb, client, 85, AS_OF)
        assert (written.cn8, written.confidence, written.written_by) == ("87149110", 95, WrittenBy.rule)
        assert written.precedent.reference == "DE-FRAME-1"
        suggested = choose_cn8(FRAMES, "8714.91", kb, client, 99, AS_OF)
        assert suggested.cn8 == "87149110" and suggested.written_by is None
        assert [c for c, _ in written.options] == ["87149110", "87149130", "87149190"]

    def test_without_a_precedent_the_threshold_rule_alone_decides(self, fake_llm, make_kb):
        from tools.classify_cn8 import choose_cn8

        choice = choose_cn8(FRAMES, "8714.91", make_kb(), get_client(), 85, AS_OF)   # recorded: 95, no precedent
        assert (choice.cn8, choice.confidence, choice.written_by, choice.precedent) == ("87149110", 95, WrittenBy.rule, None)
        assert choose_cn8(FRAMES, "8714.91", make_kb(), get_client(), 96, AS_OF).written_by is None

    @pytest.mark.parametrize("evidence", ["", "the goods are frames for bicycles", "carbon fibre frames", "Front forks"])
    def test_without_words_of_the_line_as_evidence_the_step_asks_the_shipper(self, fake_client, make_kb, evidence):
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149110", attribute="frame, fork or other part", evidence=evidence)})
        choice = choose_cn8(FRAMES, "8714.91", make_kb(), client, 85, AS_OF)
        assert choice.cn8 is None and choice.written_by is None
        assert choice.question == "Ask the shipper for: frame, fork or other part"

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

        client, _ = fake_client({key(TOYS): out("95039999", evidence="toy cars")})
        choice = choose_cn8(TOYS, "9503.00", make_kb(), client, 85, AS_OF)
        assert choice.cn8 is None and choice.written_by is None and choice.question is None
        assert "95039999" in choice.error and "9503.00" in choice.error

    def test_invalid_output_is_retried_once_then_the_step_fails(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        client, fake = fake_client({key(FRAMES): out("87149110", evidence="bicycle frames")},
                                   invalid_first={("Cn8Out", key(FRAMES)): 2})
        choice = choose_cn8(FRAMES, "8714.91", make_kb(), client, 85, AS_OF)
        assert choice.cn8 is None and choice.error and choice.written_by is None
        assert len(fake.prompts_for("Cn8Out")) == 2   # the first call and one retry

    def test_one_invalid_answer_is_recovered_by_the_retry(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149110", evidence="bicycle frames")},
                                invalid_first={("Cn8Out", key(FRAMES)): 1})
        assert choose_cn8(FRAMES, "8714.91", make_kb(), client, 85, AS_OF).cn8 == "87149110"

    def test_a_cited_ruling_must_have_been_sent(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        kb = make_kb([ruling("DE-FRAME-1", "8714911000")])
        client, _ = fake_client({key(FRAMES): out("87149110", precedent="XX-NEVER-SENT", evidence="bicycle frames")})
        choice = choose_cn8(FRAMES, "8714.91", kb, client, 85, AS_OF)
        assert choice.precedent is None and choice.cn8 == "87149110"
        assert choice.confidence == 95 and choice.written_by == WrittenBy.rule   # counts as no ruling: the threshold decides

    def test_a_cited_ruling_at_another_cn8_keeps_the_choice_to_confirm(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        kb = make_kb([ruling("DE-FRAME-1", "8714911000"), ruling("DE-FORK-1", "8714913000")])
        client, _ = fake_client({key(FRAMES): out("87149110", 98, precedent="DE-FORK-1", evidence="bicycle frames")})
        for threshold in (85, 60):
            choice = choose_cn8(FRAMES, "8714.91", kb, client, threshold, AS_OF)
            assert choice.cn8 == "87149110" and choice.written_by is None and choice.confidence == 98
            assert choice.precedent.reference == "DE-FORK-1"   # shown, so the clerk sees the disagreement

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
        assert re.search(r'<goods line="6">塑料玩具车 / Plastic toy cars</goods>', prompt)   # feature 006: its own tag
        assert prompt.index('<goods line="6">') < prompt.index('<data line="ruling DE-TOY-1">')
        assert re.search(r'<data line="ruling DE-TOY-1">[^<]*Toy car with an electric motor', prompt)

    def test_the_cn8_lines_and_the_hs6_label_stay_untagged_and_the_shipper_facts_are_goods_too(self, fake_client,
                                                                                               make_kb):
        from agent.schemas import Cn8Line, Extracted
        from tools.classify_cn8 import choose_cn8

        line = Cn8Line(line_no=6, text_zh=TOYS.text_zh, text_en=TOYS.text_en, hs6="9503.00",
                       extracted=Extracted(material="plastics", use="toy <motor>"))
        client, fake = fake_client({key(TOYS): out(None, visible=False, attribute=MOTOR)})
        choose_cn8(line, "9503.00", make_kb(), client, 85, AS_OF)
        prompt = fake.prompts_for("Cn8Out")[0]
        assert prompt.index("<goods") == prompt.index('<goods line="6">塑料玩具车')            # the description comes first
        assert 'Confirmed by the shipper: <goods line="6">material: plastics; part: ; use: toy &lt;motor&gt;</goods>' in prompt
        assert "Decided HS-6 subheading: 9503.00 - " in prompt and "- 95030075 - " in prompt   # no tag around them
        assert re.search(r"^- 95030075 - [^<]+$", prompt, re.M)

    @pytest.mark.parametrize("evidence,rule", [("bicycle frames", "exact"), ("cycle frames", "fuzzy")])
    def test_the_choice_keeps_the_rule_that_accepted_the_quote(self, fake_client, make_kb, evidence, rule):
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149110", evidence=evidence)})
        choice = choose_cn8(FRAMES, "8714.91", make_kb(), client, 85, AS_OF)
        assert (choice.cn8, choice.evidence_rule) == ("87149110", rule)

    def test_a_quote_from_a_ruling_sent_with_the_line_still_asks_the_shipper(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        kb = make_kb([ruling("DE-FORK-1", "8714913000", description="Front forks for racing bicycles, of carbon")])
        client, fake = fake_client({key(FRAMES): out("87149110", evidence="Front forks for racing bicycles")})
        choice = choose_cn8(FRAMES, "8714.91", kb, client, 85, AS_OF)
        assert "Front forks for racing bicycles" in fake.prompts_for("Cn8Out")[0]   # the quote was in the request
        assert choice.cn8 is None and choice.question and choice.evidence_rule is None


class TestClassifyCn8Lines:
    def test_one_result_per_line_and_a_failure_stays_on_its_line(self, fake_client, make_kb):
        from tools.classify_cn8 import classify_cn8_lines

        client, _ = fake_client({key(FRAMES): out("87149110", evidence="bicycle frames")}, fail_on={key(TOYS)})
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
        assert len(prompts) == 1 and '<goods line="1">' in prompts[0] and '<goods line="2">' not in prompts[0]


class FixedHits:
    """The BTI vector search with fixed hits, nearest first: (doc id, relevance)."""

    def __init__(self, hits):
        self.hits = hits

    def embed_query_cached(self, text):
        return [1.0]

    def search_by_vector(self, vector, k, chapter_filter=None, where=None):
        return list(self.hits)


FRAME_RULINGS = [ruling("R1", "8714911000", member_state="DE"), ruling("R2", "8714911000", member_state="FR"),
                 ruling("R3", "8714913000", member_state="IE"), ruling("R4", "8714919000", member_state="PL")]


class TestCn8RulingVoteGate:
    """Feature 006, constitution 1.4.0: the nearest eligible rulings vote; the model estimate is no routing input."""

    def kb(self, make_kb, hits=(("bti:R1", 0.9), ("bti:R2", 0.8), ("bti:R3", 0.7))):
        kb = make_kb(FRAME_RULINGS)
        kb.bti_vectors = FixedHits(list(hits))
        return kb

    def test_the_majority_writes_the_cn8_whatever_the_model_estimate(self, fake_client, make_kb):
        from agent.schemas import Cn8Gate, VoteCode
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149110", 60, evidence="bicycle frames")})
        choice = choose_cn8(FRAMES, "8714.91", self.kb(make_kb), client, 85, AS_OF)
        assert (choice.cn8, choice.written_by, choice.gate_reason) == ("87149110", WrittenBy.rule, Cn8Gate.vote_agrees)
        assert (choice.majority_cn8, choice.majority_share, choice.confidence) == ("87149110", 0.6667, 60)
        # R4 is in the pool but not among the nearest hits: it was sent to the model (if room) but does not vote
        assert choice.competing == [VoteCode(cn8="87149110", countries=["DE", "FR"]), VoteCode(cn8="87149130", countries=["IE"])]

    def test_a_majority_at_another_cn8_keeps_a_confident_pick_to_confirm(self, fake_client, make_kb):
        from agent.schemas import Cn8Gate
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149130", 98, evidence="bicycle frames")})
        choice = choose_cn8(FRAMES, "8714.91", self.kb(make_kb), client, 85, AS_OF)
        assert (choice.cn8, choice.written_by, choice.gate_reason) == ("87149130", None, Cn8Gate.vote_disagrees)

    def test_the_lines_own_ruling_and_rulings_out_of_the_pool_never_vote(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        hits = (("bti:R3", 0.95), ("bti:XX", 0.9), ("bti:R1", 0.8), ("bti:R2", 0.7))   # XX: unknown to the store
        client, _ = fake_client({key(FRAMES): out("87149110", 90, evidence="bicycle frames")})
        choice = choose_cn8(FRAMES, "8714.91", self.kb(make_kb, hits), client, 85, AS_OF, exclude_refs=frozenset({"R3"}))
        assert (choice.majority_cn8, choice.majority_share, choice.written_by) == ("87149110", 1.0, WrittenBy.rule)

    def test_without_eligible_rulings_the_model_estimate_meets_the_threshold(self, fake_client, make_kb):
        from agent.schemas import Cn8Gate
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149110", 85, evidence="bicycle frames")})
        choice = choose_cn8(FRAMES, "8714.91", make_kb(FRAME_RULINGS), client, 85, AS_OF)   # no BTI vectors: no vote
        assert (choice.written_by, choice.gate_reason, choice.majority_cn8) == (WrittenBy.rule, Cn8Gate.no_rulings, None)
        assert choose_cn8(FRAMES, "8714.91", make_kb(FRAME_RULINGS), client, 86, AS_OF).written_by is None

    def test_a_question_keeps_the_vote_for_the_record_and_no_gate(self, fake_client, make_kb):
        from tools.classify_cn8 import choose_cn8

        client, _ = fake_client({key(FRAMES): out("87149110", 90, evidence="carbon fibre")})   # not words of the line
        choice = choose_cn8(FRAMES, "8714.91", self.kb(make_kb), client, 85, AS_OF)
        assert choice.question and choice.cn8 is None and choice.gate_reason is None
        assert choice.majority_cn8 == "87149110"
