"""Feature 006, constitution Principle I: an answer the model gives as text that is not JSON (the raw client returns it as
{"_invalid": ...}) is an invalid answer. It is retried once, and a call still invalid after that retry fails its line as
an error; it is never taken as a ranking without candidates or as a check without a flag."""
import pytest

from agent.llm import StructuredCaller, get_client
from agent.routing import SchemaError
from agent.schemas import JudgementOut, LineStatus, RankOut
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tools.check_description import check_descriptions
from tools.classify_hs6 import ClassifyContext, classify_lines
from tools.common import LineText

pytestmark = pytest.mark.integration

KEY = "不锈钢保温杯 / Stainless steel vacuum flask, 500 ml"
LINE = LineText(line_no=3, text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask, 500 ml", flag_kind="ok")


@pytest.fixture
def kb(small_index, fake_embeddings, rules):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    return KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index, k=6), BTIStore([]),
                         rules, {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings)


def calls(fake_llm, schema):
    return sum(1 for c in fake_llm.calls if c["schema"] == schema)


def test_a_ranking_that_is_not_json_is_retried_once(fake_llm, kb):
    fake_llm.not_json_first = {("RankOut", KEY): 1}
    out = classify_lines([LINE], ClassifyContext(), kb=kb, client=get_client())[0]
    assert (out.status, out.candidates[0].code, calls(fake_llm, "RankOut")) == (LineStatus.checked, "9617.00", 2)
    assert "not valid JSON" in fake_llm.prompts_for("RankOut")[1]          # the retry says what was wrong


def test_a_ranking_still_not_json_after_the_retry_fails_the_line_never_no_candidates(fake_llm, kb):
    fake_llm.not_json_first = {("RankOut", KEY): 2}
    out = classify_lines([LINE], ClassifyContext(), kb=kb, client=get_client())[0]
    assert out.status == LineStatus.failed and "RankOut" in out.error_reason and "not valid JSON" in out.error_reason
    assert calls(fake_llm, "RankOut") == 2              # one retry, though a wrong schema would get MAX_SCHEMA_RETRIES


def test_the_description_check_behaves_the_same(fake_llm, rules):
    line = LineText(line_no=4, text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask, 500 ml")
    fake_llm.not_json_first = {("JudgementOut", KEY): 1}
    retried = check_descriptions([line], rules, get_client(), workers=1)[0]
    assert (retried.status, retried.flag.kind.value, calls(fake_llm, "JudgementOut")) == (LineStatus.checked, "ok", 2)
    fake_llm.calls.clear()
    fake_llm.not_json_first = {("JudgementOut", KEY): 2}
    failed = check_descriptions([line], rules, get_client(), workers=1)[0]
    assert (failed.status, failed.flag, calls(fake_llm, "JudgementOut")) == (LineStatus.failed, None, 2)
    assert "JudgementOut" in failed.error_reason and "not valid JSON" in failed.error_reason


class Answers:
    """A raw backend that gives the scripted answers in turn."""

    def __init__(self, *answers):
        self.answers, self.last_usage = list(answers), {}

    def raw_structured(self, schema, system, user):
        return self.answers.pop(0)


def test_after_an_answer_that_is_not_json_the_retry_is_the_last_chance():
    not_json, wrong = {"_invalid": True, "content": "Sure!"}, {"candidates": "none"}
    good = {"candidates": [{"code": "9617.00", "confidence": 90, "rationale": "a flask", "history_only": False}]}
    caller = StructuredCaller(raw=Answers(not_json, wrong, good), model_name="m", prices=None, usd_eur=0.92, max_retries=2)
    with pytest.raises(SchemaError):
        caller.call(RankOut, "s", "u")                     # retried once; the retry is invalid too: no third attempt
    assert len(caller.raw.answers) == 1
    caller = StructuredCaller(raw=Answers(wrong, not_json, good), model_name="m", prices=None, usd_eur=0.92, max_retries=2)
    assert caller.call(RankOut, "s", "u").candidates[0].code == "9617.00"   # a wrong schema first keeps its retries
    caller = StructuredCaller(raw=Answers(not_json), model_name="m", prices=None, usd_eur=0.92, max_retries=0)
    with pytest.raises(SchemaError):
        caller.call(JudgementOut, "s", "u")                # no retries asked for: none
