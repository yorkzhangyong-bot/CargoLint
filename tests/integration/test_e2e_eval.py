"""Feature 007, tests/eval/e2e_eval.run_once offline: five set lines through the upload's steps and the line store, one
for each path a line can take: auto-accepted and right; HS-6 in review, confirmed by the clerk, then its CN-8; flagged;
HS-6 auto-accepted with its CN-8 left to confirm; and a wrong HS-6 auto-accepted with a written CN-8. Each line's own
ruling stays out at both layers."""
import re
from datetime import date

import pytest

from agent.llm import get_client, set_client_factory
from rag.bti import BTIStore
from rag.embeddings import FakeEmbeddings
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tests.eval import e2e_eval   # at collection: the offline guard replaces the OpenRouter client inside a test
from tests.fakes import FakeRawClient

pytestmark = pytest.mark.integration

AS_OF = date(2026, 10, 23)
FRAME = "Aluminium alloy bicycle frames, welded and painted, road racing model. " * 5   # over 300 characters: cut
CASE = "Silicone mobile phone cases"
SPARE = "spare parts"
TOYCAR = "Plastic toy cars without motor"
STORE = "Polypropylene storage boxes for household use"


def line(reference, cn8, description):
    return {"reference": reference, "chapter": cn8[:2], "hs6": f"{cn8[:4]}.{cn8[4:6]}", "cn8": cn8, "language": "en",
            "description": description}


SET = [line("FRAME-OWN", "87149110", FRAME), line("CASE-OWN", "39269097", CASE), line("SPARE-OWN", "87149190", SPARE),
       line("TOYCAR-OWN", "95030035", TOYCAR), line("STORE-OWN", "39269097", STORE)]


def ruling(reference, cn_code, description, member_state="DE"):
    return {"reference": reference, "member_state": member_state, "code": f"{cn_code[:4]}.{cn_code[4:6]}",
            "cn_code": cn_code, "chapter": cn_code[:2], "description": description, "reasoning": "",
            "valid_from": "2025-01-01", "valid_to": "2027-12-31", "language": "EN"}


RULINGS = [ruling("FRAME-OWN", "8714911000", FRAME), ruling("FRAME-2", "8714911000", FRAME),
           ruling("FRAME-3", "8714911000", FRAME, "IE"),
           ruling("CASE-OWN", "3926909700", CASE), ruling("CASE-2", "9503003500", CASE), ruling("CASE-3", "9503003500", CASE),
           ruling("TOYCAR-OWN", "9503003500", TOYCAR), ruling("TOYCAR-2", "9503003500", TOYCAR),
           ruling("TOYCAR-3", "9503003500", TOYCAR),
           ruling("STORE-OWN", "3926909700", STORE), ruling("STORE-2", "9503001000", STORE),
           ruling("STORE-3", "9503001000", STORE), ruling("STORE-4", "9503001000", STORE)]


def rank(*codes):
    return {"candidates": [{"code": code, "confidence": conf, "rationale": "r", "history_only": False} for code, conf in codes]}


def cn8(code, evidence):
    return {"cn8": code, "confidence": 95, "deciding_attribute": "the use", "attribute_visible": True,
            "evidence": evidence, "rationale": "because", "precedent": None}


def make_kb(small_index, rules, rulings):
    embeddings = FakeEmbeddings(dim=256)   # wide enough that lines with no words in common are far apart
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], embeddings)
    kb = KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index, k=6), BTIStore(rulings),
                       rules, {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, embeddings)
    kb.bti_vectors = InMemoryVectorSearch(kb.bti.chunk_texts(), embeddings)
    return kb


@pytest.fixture
def kb(small_index, rules):
    return make_kb(small_index, rules, RULINGS)


@pytest.fixture
def fake():
    frame = e2e_eval.upload([SET[0]])[0].text_en.strip()   # cut at 300 characters; the fake's keys are stripped
    judged = {"vague": False, "missing": [], "reason": "specific enough"}
    client = FakeRawClient(recorded={
        "JudgementOut": {text: judged for text in (frame, CASE, TOYCAR, STORE)},
        "RankOut": {frame: rank(("8714.91", 95)), CASE: rank(("3926.90", 95), ("9503.00", 40)),
                    TOYCAR: rank(("9503.00", 95)), STORE: rank(("9503.00", 95))},   # the storage boxes: a wrong HS-6
        "Cn8Out": {frame: cn8("87149110", "bicycle frames"), CASE: cn8("39269097", "silicone mobile phone cases"),
                   TOYCAR: cn8("95030030", "toy cars"), STORE: cn8("95030010", "storage boxes")}})
    set_client_factory(lambda: client)
    yield client
    set_client_factory(None)


def test_each_path_through_the_upload_and_the_clerks_confirmation(kb, fake):
    rows, upload_s, elapsed = e2e_eval.run_once(SET, kb, get_client(), AS_OF, workers=2)
    by = {r["reference"]: r for r in rows}
    assert [r["reference"] for r in rows] == [s["reference"] for s in SET] and 0 <= upload_s <= elapsed

    frame = by["FRAME-OWN"]   # both gates agree with the nearest rulings: written by rule, auto-accepted, right
    assert (frame["cut"], frame["hs6_gate"], frame["hs6_route"], frame["hs6_by"], frame["cn8"], frame["written"],
            frame["cn8_gate"], frame["route"], frame["hit"], frame["written_hit"]) == (
        True, "vote_agrees", "auto_accept", "gate", "87149110", True, "vote_agrees", "auto_accept", True, True)

    case = by["CASE-OWN"]     # the nearest rulings sit at another HS-6: review; the clerk confirms the top candidate
    assert (case["hs6_gate"], case["hs6_route"], case["hs6"], case["hs6_by"], case["cn8"], case["route"], case["hit"],
            case["written_hit"], case["origin"]) == (
        "vote_disagrees", "review", "3926.90", "clerk", "39269097", "review", True, None, None)

    spare = by["SPARE-OWN"]   # flagged: locked, no code, waits for the shipper
    assert (spare["flag"], spare["hs6"], spare["cn8"], spare["route"], spare["hit"], spare["origin"]) == (
        "vague", None, None, "ask_shipper", False, "hs6_flagged")

    toycar = by["TOYCAR-OWN"]  # the HS-6 auto-accepted, the CN-8 left to confirm: the clerk still picks it
    assert (toycar["hs6_route"], toycar["hs6_by"], toycar["cn8"], toycar["written"], toycar["cn8_gate"], toycar["route"],
            toycar["origin"]) == ("auto_accept", "gate", "95030030", False, "vote_disagrees", "review", "cn8_wrong")

    store = by["STORE-OWN"]   # the rulings agree with a wrong HS-6 and then a CN-8 under it: a wrong auto-accept
    assert (store["hs6"], store["hs6_hit"], store["hs6_by"], store["cn8"], store["written"], store["route"],
            store["written_hit"], store["origin"]) == ("9503.00", False, "gate", "95030010", True, "auto_accept", False,
                                                       "hs6_wrong")

    m = e2e_eval.measures([rows])
    assert (m["right_runs"], m["routes_runs"], m["hs6_wrong_auto_runs"]) == (
        [2], [{"auto_accept": 2, "review": 2, "ask_shipper": 1}], [1])
    assert [w["reference"] for w in m["wrong_auto_runs"][0]] == ["STORE-OWN"]
    assert {k: v for k, v in m["origin_runs"][0].items() if v} == {"hs6_wrong": 1, "hs6_flagged": 1, "cn8_wrong": 1}


def test_a_lines_own_ruling_never_reaches_the_model(kb, fake):
    e2e_eval.run_once(SET, kb, get_client(), AS_OF, workers=2)
    owner = {e2e_eval.upload([s])[0].text_en.strip(): s["reference"] for s in SET}
    calls = [c for c in fake.calls if c["schema"] in ("RankOut", "Cn8Out")]
    assert {c["schema"] for c in calls} == {"RankOut", "Cn8Out"}
    assert not [c for c in calls if owner[c["key"]] in c["user"]]
    frame_cn8 = next(c["user"] for c in calls if c["schema"] == "Cn8Out" and owner[c["key"]] == "FRAME-OWN")
    assert "FRAME-2" in frame_cn8 and "FRAME-3" in frame_cn8   # the other rulings at the same CN-8 are sent


# --------------------------------------------------------------------------- feature 008: the precedent override
FIGS = "Plastic figurines of animals"
FIG_SET = [line("FIG-OWN", "95030035", FIGS)]
FIG_RULINGS = [ruling("FIG-OWN", "9503003500", FIGS), ruling("FIG-2", "3926909700", FIGS, "IE"),
               ruling("FIG-3", "3926909700", FIGS), ruling("FIG-4", "3926909700", FIGS),
               ruling("FIG-5", "3926909700", FIGS, "FR"), ruling("FIG-6", "3926909700", FIGS, "NL"),
               ruling("FIG-7", "9503003500", "Toy animals of plastics", "PL")]   # less near: it does not vote


class ByHs6(FakeRawClient):
    """Answers the CN-8 step by the HS-6 its request names, as the eval asks one line under two HS-6 codes."""

    def __init__(self, cn8_by_hs6, **kw):
        super().__init__(**kw)
        self.cn8_by_hs6 = cn8_by_hs6

    def raw_structured(self, schema, system, user):
        out = super().raw_structured(schema, system, user)
        if schema.__name__ != "Cn8Out":
            return out
        return self.cn8_by_hs6[re.search(r"Decided HS-6 subheading: (\d{4}\.\d{2})", user).group(1)]


def test_an_override_line_and_its_switch_off_replay(small_index, rules):
    """The model's top candidate, 9503.00, is the ruling's HS-6, but all 5 nearest other rulings sit at its candidate
    2: with the switch on at OVERRIDE_MIN the override chooses 3926.90, a wrong auto-accept; the switch off, replayed
    from the CN-8 step's answer under 9503.00, leaves the line in review with the right CN-8 to confirm."""
    kb = make_kb(small_index, rules, FIG_RULINGS)
    fake = ByHs6({"3926.90": cn8("39269097", "plastic figurines"), "9503.00": cn8("95030035", "plastic figurines")},
                 recorded={"JudgementOut": {FIGS: {"vague": False, "missing": [], "reason": "specific enough"}},
                           "RankOut": {FIGS: rank(("9503.00", 95), ("3926.90", 60))}})
    set_client_factory(lambda: fake)
    try:
        r = e2e_eval.run_once(FIG_SET, kb, get_client(), AS_OF, workers=1)[0][0]
    finally:
        set_client_factory(None)
    assert (r["hs6_gate"], r["hs6_reason"], r["hs6"], r["hs6_by"], r["cn8"], r["route"], r["hit"], r["origin"]) == (
        "vote_override", "rulings overrode the model: 5 of 5 agree on 3926.90", "3926.90", "gate", "39269097",
        "auto_accept", False, "hs6_wrong")
    assert r["override"] == {"fired": True, "rank": 2, "code": "3926.90", "n": 5, "m": 5}
    assert r["supported"] == {"rank": 2, "right": False}
    assert r["cn8_top1"] == {"cn8": "95030035", "written": True, "question": None, "error": None, "gate": "vote_agrees"}
    assert r["off"] == {"hs6": "9503.00", "hs6_by": "clerk", "cn8": "95030035", "written": True, "question": None,
                        "cn8_error": None, "cn8_gate": "vote_agrees", "route": "review", "hit": True, "written_hit": None,
                        "origin": None}
    extra = [c["user"] for c in fake.calls if c["schema"] == "Cn8Out" and "Decided HS-6 subheading: 9503.00" in c["user"]]
    assert len(extra) == 1 and "FIG-7" in extra[0] and "FIG-OWN" not in extra[0]   # never the line's own ruling
