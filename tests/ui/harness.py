"""Page-test harness for feature 005 (tasks T002, T026).

- `make_kb`: a knowledge base on the small index, with the small or the sample TARIC fixture, or none.
- `store_with` / `all_states`: stores holding one line per named state, built only through the store's methods. The
  flags come from the real rule engine (`check_descriptions`); the fake model only judges texts no rule matches.
- `sample_store`: the 12-line sample checked offline, as tests/integration/test_upload_flow.py does.
- `JobRecorder`, `ModelGuard`: record background jobs instead of starting threads, and count model calls.
- `app`: an AppTest of the two pages behind an `st.navigation` like app.py's.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from agent.schemas import (Candidate, Classification, Cn8Choice, CreatedBy, Decision, DecisionRoute, Hs6Vote, LineStatus,
                           LineVersion, ParsedLine, Precedent, TaricOutcome, TaricRule, WrittenBy)
from agent.store import LineStore
from tests.fakes import FakeRawClient, ScriptedChatModel, ai_tool_call

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
TARIC_FIXTURES = {"small": FIXTURES / "taric" / "snapshot_small.jsonl",
                  "sample": FIXTURES / "taric" / "snapshot_sample.jsonl"}
SAMPLE_XLSX = ROOT / "data" / "samples" / "sample_packing_list.xlsx"
SAMPLE_REFERENCE = "HOL-2026-10-0472"
TARIC_QUESTION = ("Please state which of these TARIC subdivisions applies: 7318 15 58 10 (Self-locking bolts and nuts); "
                  "7318 15 58 90 (Other).")

# Recorded outputs the harness keeps for its own texts, on top of tests/fixtures/recorded. The fake client judges any
# unrecorded text as vague and ranks it with no candidate, so clear texts need an OK judgement here.
OK = {"vague": False, "missing": [], "reason": "specific product with material and type"}
VAGUE = {"vague": True, "missing": ["material", "product_name", "use"], "reason": "generic term, no material, product name or use"}
RECORDED: dict[str, dict[str, Any]] = {
    "JudgementOut": {
        "Ceramic coffee mugs": OK, "Wooden chopsticks": OK, "Ceramic dinner plates": OK, "Plastic toy figures": OK,
        "Plastic toy cars": OK, "Cotton T-shirts, knitted": OK, "Wireless Bluetooth earphones": OK,
        "LED desk lamp, USB powered": OK, "Stainless steel hexagon bolts, threaded": OK,
        "Stainless steel vacuum flask, 500 ml": OK, "Steel bobbin cases for industrial sewing machines": OK,
        "Plastic toy cars without a motor": OK, "Brake pads for bicycles, steel": OK,
        "Mixed household articles": VAGUE, "Kitchen things": VAGUE, "Mixed metal articles": VAGUE,
    },
    "TranslateOut": {
        "Steel bobbin cases for industrial sewing machines": {"queries": ["Steel bobbin cases for industrial sewing machines"], "hyde": None},
        "Plastic toy cars without a motor": {"queries": ["Plastic toy cars without a motor"], "hyde": None},
        "Brake pads for bicycles, steel": {"queries": ["Brake pads for bicycles, steel"], "hyde": None},
        "Spare parts": {"queries": ["Spare parts"], "hyde": None},
    },
    "RankOut": {
        "Steel bobbin cases for industrial sewing machines": {"candidates": [
            {"code": "8452.90", "confidence": 95, "rationale": "bobbin cases are parts of sewing machines", "history_only": False}]},
        "Plastic toy cars without a motor": {"candidates": [
            {"code": "9503.00", "confidence": 95, "rationale": "toys, without a motor", "history_only": False}]},
        "Brake pads for bicycles, steel": {"candidates": [
            {"code": "8714.91", "confidence": 90, "rationale": "parts of bicycles", "history_only": False}]},
        "Spare parts": {"candidates": [
            {"code": "8714.91", "confidence": 41, "rationale": "could be bicycle parts", "history_only": False},
            {"code": "8487.90", "confidence": 39, "rationale": "machinery parts", "history_only": False},
            {"code": "8452.90", "confidence": 12, "rationale": "sewing machine parts", "history_only": True}]},
    },
    "Cn8Out": {
        "Plastic toy cars without a motor": {"cn8": "95030095", "confidence": 95, "deciding_attribute": "",
                                              "attribute_visible": True, "evidence": "Plastic toy cars without a motor",
                                              "rationale": "toys of plastics, no motor", "precedent": None},
    },
}

_INDEX: Any = None


def small_index() -> Any:
    global _INDEX
    if _INDEX is None:
        from rag.nomenclature import NomenclatureIndex

        _INDEX = NomenclatureIndex.from_jsonl(FIXTURES / "cn2026_excerpt.jsonl")
    return _INDEX


def fake_client() -> FakeRawClient:
    client = FakeRawClient.from_dir(FIXTURES / "recorded")
    for schema, table in RECORDED.items():
        client.recorded.setdefault(schema, {}).update(copy.deepcopy(table))
    return client


def _ruling(reference: str, code: str, description: str) -> dict:
    from rag.bti import row_to_ruling

    return row_to_ruling({"BTI_REFERENCE": reference, "ISSUING_COUNTRY": reference[:2], "START_DATE_OF_VALIDITY": "2025-01-01",
                          "END_DATE_OF_VALIDITY": "2028-01-01", "NOMENCLATURE_CODE": code + "************",
                          "CLASSIFICATION_JUSTIFICATION": "GIR 1 and 6", "STATUS": "VALID", "LANGUAGE": "en",
                          "NAME_AND_ADDRESS": "x", "DESCRIPTION_OF_GOODS": description, "KEYWORDS": ""})


def make_kb(taric: str | None = "small") -> Any:
    """A KnowledgeBase like the `kb` fixture of tests/integration/test_agent_check_flow.py."""
    from rag.bti import BTIStore
    from rag.embeddings import FakeEmbeddings
    from rag.loader import KnowledgeBase
    from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
    from rag.rules import RuleSet, load_shippers
    from rag.taric import TaricStore

    index = small_index()
    emb = FakeEmbeddings(dim=16)
    retriever = HybridRetriever(bm25=BM25Index([(c.id, c.text) for c in index.chunks]),
                                vectors=InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in index.chunks], emb),
                                chunks=index)
    bti = BTIStore([_ruling("DE-TOY-0001", "9503009590", "plastic toy cars without a motor"),
                    _ruling("NL-BIKE-0002", "8714911000", "aluminium bicycle frames")])
    store = TaricStore.from_jsonl(TARIC_FIXTURES[taric]) if taric else None
    return KnowledgeBase(index, retriever, bti, RuleSet.load(FIXTURES / "rules"),
                         {"embedding_model": "fake", "built_at": "2026-10-15T00:00:00"}, emb, shippers=load_shippers(),
                         taric=store)


# --------------------------------------------------------------------------- stores in every line state
def _store(origin: str = "CN", hs6_override_min: int | None = None) -> LineStore:
    store = LineStore(backend={}, index=small_index())
    store.new_shipment(reference="INV-TEST", threshold=85, hs6_override_min=hs6_override_min)
    if origin != "CN":
        store.set_taric_origin(origin)
    return store


def _add(store: LineStore, text_en: str, text_zh: str = "", **kw: Any) -> int:
    line = store.add_lines([ParsedLine(text_zh=text_zh, text_en=text_en, source_ref="harness", **kw)], CreatedBy.paste)[0]
    return line.line_no


def _check(store: LineStore, kb: Any, n: int) -> None:
    from tools.check_description import check_descriptions
    from tools.common import select_lines

    for result in check_descriptions(select_lines(store, [n]), kb.rules, fake_client_caller(), workers=1):
        store.update_check(n, result)


def fake_client_caller() -> Any:
    from agent.llm import StructuredCaller

    return StructuredCaller(raw=fake_client(), model_name="fake", prices=None, usd_eur=0.92)


def _classify(store: LineStore, n: int, cands: list[tuple[str, int]], no_valid: bool = False,
              rationale: str = "matches the subheading", hs6_vote: Hs6Vote | None = None) -> None:
    index = store.index
    candidates = [Candidate(code=code, subheading_text=index.subheading_text(code), confidence=conf,
                            rationale=f"{rationale} {code}", history_only=(i == 2)) for i, (code, conf) in enumerate(cands)]
    store.update_classification(n, Classification(line_no=n, candidates=candidates, no_valid_candidate=no_valid,
                                                  status=LineStatus.checked, hs6_vote=hs6_vote))
    by_code = {}
    if cands:
        by_code[cands[0][0]] = [Precedent(reference=f"DE-{cands[0][0].replace('.', '')}-01", member_state="DE",
                                          code=cands[0][0].replace(".", "") + "0000", description="a ruling",
                                          valid_from=date(2025, 1, 1), valid_to=date(2028, 1, 1),
                                          url="https://ec.europa.eu/taxation_customs/dds2/ebti/ebti_consultation.jsp")]
    store.update_precedents(n, by_code)


def _cn8(store: LineStore, n: int, hs6: str, cn8: str | None, *, conf: int = 95, written: bool = True,
         question: str | None = None, error: str | None = None, attribute: str = "") -> None:
    options = store.index.cn8_lines(hs6)
    store.set_cn8_result(n, Cn8Choice(hs6=hs6, options=options, cn8=cn8, confidence=conf if cn8 else 0,
                                      evidence="the line text" if cn8 else "", rationale="model estimate" if cn8 else "",
                                      deciding_attribute=attribute, question=question, error=error,
                                      written_by=(WrittenBy.rule if written and cn8 else None)))


def _taric(store: LineStore, kb: Any, n: int) -> None:
    from tools.lookup_taric import rule_outcome

    line = store.get_line(n)
    outcome, _ = rule_outcome(line.current.cn8.cn8, store.decided_cn8(line) is not None, store.shipment.taric_origin, kb)
    store.set_taric_result(n, outcome)


def _clear(store: LineStore, kb: Any, text_en: str, text_zh: str = "") -> int:
    n = _add(store, text_en, text_zh)
    _check(store, kb, n)
    return n


def build_state(store: LineStore, kb: Any, state: str) -> int:
    """Add one line and drive it to the named state through the store's methods; returns its line number."""
    if state == "pending":
        return _add(store, "Ceramic coffee mugs")
    if state == "failed":
        n = _add(store, "Wooden chopsticks")
        store.mark_failed(n, "TimeoutError: the model did not answer")
        return n
    if state == "ics2_term":
        n = _clear(store, kb, "Spare parts")
        _classify(store, n, [("8714.91", 41), ("8487.90", 39), ("8452.90", 12)])
        return n
    if state == "firm_stop_word":
        return _clear(store, kb, "Gift")
    if state in ("vague_close", "vague_apart", "vague_review"):
        text = {"vague_close": "Mixed household articles", "vague_apart": "Kitchen things", "vague_review": "Mixed metal articles"}[state]
        cands = {"vague_close": [("3924.90", 41), ("3924.10", 39), ("9403.60", 12)],
                 "vague_apart": [("3924.90", 40), ("3924.10", 10), ("9403.60", 5)],
                 "vague_review": [("7318.15", 55), ("8708.99", 20)]}[state]
        n = _clear(store, kb, text)
        _classify(store, n, cands)
        return n
    if state == "unreadable":
        return _add(store, "", unreadable=True)
    if state == "cn8_question":
        n = _clear(store, kb, "Plastic toy cars", "塑料玩具车")
        _classify(store, n, [("9503.00", 93)])
        _cn8(store, n, "9503.00", None, attribute="whether the toy cars incorporate a motor",
             question="Ask the shipper for: whether the toy cars incorporate a motor")
        return n
    if state == "sent":
        n = _clear(store, kb, "Ceramic dinner plates")
        _classify(store, n, [("3924.10", 60), ("3924.90", 20)])
        store.set_decision(n, Decision(route=DecisionRoute.ask_shipper))
        return n
    if state == "taric_question":
        n = build_state(store, kb, "taric_two")
        store.ask_shipper_for_taric(n, TARIC_QUESTION)
        return n
    if state == "cn8_error":
        n = _clear(store, kb, "Cotton T-shirts, knitted", "纯棉针织T恤")
        _classify(store, n, [("6109.10", 94)])
        _cn8(store, n, "6109.10", None, error="invalid output after one retry")
        return n
    if state == "review":
        n = _clear(store, kb, "LED desk lamp, USB powered", "LED台灯 USB供电")
        _classify(store, n, [("9405.21", 58), ("8543.70", 20), ("9403.60", 10)])
        return n
    if state == "ready_to_accept":
        n = _clear(store, kb, "Spare parts")
        store.add_version(n, LineVersion(created_by=CreatedBy.shipper_reply, text_en="Steel bobbin cases for industrial sewing machines"))
        _check(store, kb, n)
        _classify(store, n, [("8452.90", 91), ("8452.30", 5)])
        return n
    if state == "no_candidate":
        n = _clear(store, kb, "Wireless Bluetooth earphones", "无线蓝牙耳机")
        _classify(store, n, [], no_valid=True)
        return n
    if state in ("cn8_missing", "cn8_pending", "taric_missing"):
        n = _clear(store, kb, "Plastic toy figures")
        _classify(store, n, [("9503.00", 92)])
        if state == "cn8_pending":
            _cn8(store, n, "9503.00", "95030095", conf=70, written=False)
        elif state == "taric_missing":
            _cn8(store, n, "9503.00", "95030095", conf=95)
        return n
    if state in ("taric_two", "taric_one_td", "ready_taric", "accepted_taric"):
        n = _clear(store, kb, "Stainless steel hexagon bolts, threaded", "不锈钢六角螺栓")
        _classify(store, n, [("7318.15", 92)])
        _cn8(store, n, "7318.15", "73181568" if state in ("taric_one_td", "ready_taric") else "73181558", conf=95)
        _taric(store, kb, n)
        if state == "accepted_taric":
            store.confirm_taric10(n, "7318155810")
        return n
    if state == "taric_many":
        n = _clear(store, kb, "Aluminium alloy bicycle frames", "铝合金自行车架")
        _classify(store, n, [("8714.91", 95)])
        _cn8(store, n, "8714.91", "87149110", conf=95)
        codes = [f"871491100{i}" for i in range(1, 10)]
        store.set_taric_result(n, TaricOutcome(origin=store.shipment.taric_origin, snapshot_date=date(2026, 10, 1),
                                               rule=TaricRule.trade_defence, subdivisions=codes, trade_defence=codes[:3],
                                               trade_defence_types=["552"]))
        return n
    if state in ("ready", "accepted", "ready_not_loaded"):
        n = _clear(store, kb, "Stainless steel vacuum flask, 500 ml", "不锈钢保温杯 500ml")
        _classify(store, n, [("9617.00", 92)])
        _cn8(store, n, "9617.00", "96170000", conf=100)
        if state == "ready_not_loaded":
            store.set_taric_result(n, TaricOutcome(origin=store.shipment.taric_origin, rule=TaricRule.not_loaded))
        else:
            _taric(store, kb, n)
        if state == "accepted":
            store.confirm_cn8(n, "96170000")
        return n
    if state in ("hs6_override", "hs6_override_cn8"):   # feature 008: 4 of 5 nearest rulings at candidate 2; needs a
        n = _clear(store, kb, "LED desk lamp, USB powered", "LED台灯 USB供电")   # store with the switch on
        vote = Hs6Vote(majority="9405.21", majority_share=0.8, candidate=2,
                       competing=[("9405.21", ["IE", "DE", "DE", "FR"]), ("8543.70", ["NL"])])
        _classify(store, n, [("8543.70", 90), ("9405.21", 60), ("9403.60", 20)], hs6_vote=vote)
        if state == "hs6_override_cn8":   # the CN-8 left to confirm: "Pick: CN-8"
            _cn8(store, n, "9405.21", "94052140", conf=70, written=False)
            return n
        _cn8(store, n, "9405.21", "94052140", conf=95)
        _taric(store, kb, n)
        return n
    if state in ("edited_ever_flagged", "edited_never_flagged"):   # T026: a clerk version, re-checked inline
        n = build_state(store, kb, "ics2_term" if state == "edited_ever_flagged" else "cn8_question")
        text = "Brake pads for bicycles, steel" if state == "edited_ever_flagged" else "Plastic toy cars without a motor"
        store.update_description(n, "", text)
        run_inline_recheck(store, kb, n)
        return n
    raise ValueError(f"unknown state {state!r}")


CN_STATES = ("pending", "failed", "ics2_term", "firm_stop_word", "vague_close", "vague_apart", "vague_review", "unreadable",
             "cn8_question", "sent", "taric_question", "cn8_error", "review", "ready_to_accept", "no_candidate",
             "cn8_missing", "cn8_pending", "taric_missing", "taric_two", "taric_many", "taric_one_td", "ready",
             "ready_not_loaded", "accepted", "accepted_taric")


def store_with(*states: str, origin: str = "CN", kb: Any = None,
               hs6_override_min: int | None = None) -> tuple[LineStore, dict[str, int]]:
    """A store with one line per state, and the line number of each state; `hs6_override_min` is the precedent override
    switch of feature 008 (the state "hs6_override" needs it on)."""
    kb = kb or make_kb()
    store = _store(origin, hs6_override_min)
    with ModelGuard():
        numbers = {s: build_state(store, kb, s) for s in states}
    return store, numbers


def all_states(kb: Any = None) -> tuple[tuple[LineStore, dict[str, int]], tuple[LineStore, dict[str, int]]]:
    """The CN store with every state but `ready_taric`, and the US store with `ready_taric`."""
    kb = kb or make_kb()
    return store_with(*CN_STATES, kb=kb), store_with("ready_taric", origin="US", kb=kb)


def run_inline_recheck(store: LineStore, kb: Any, n: int) -> str:
    from agent.agent import recheck_line

    with ModelGuard():
        return recheck_line(store, kb, n)


# --------------------------------------------------------------------------- the 12-line sample
SAMPLE_SCRIPT = [
    ("parse_packing_list", {"file_ref": "f1"}), ("check_description", {"all_pending": True}),
    ("classify_hs6", {"all_pending": True}), ("lookup_precedent", {"all_pending": True}),
    ("classify_cn8", {}), ("lookup_taric", {}),
]


def sample_script(file_ref: str) -> list:
    """The agent's tool calls for checking the sample file, for the scripted chat model."""
    return [ai_tool_call(name, dict(args, **({"file_ref": file_ref} if "file_ref" in args else {})), f"c{i}")
            for i, (name, args) in enumerate(SAMPLE_SCRIPT, 1)] + [AIMessage(content="All 12 lines checked.")]


def sample_store(kb: Any = None) -> LineStore:
    """The 12-line sample checked offline with the recorded outputs and the sample TARIC fixture."""
    from agent.agent import run_turn

    kb = kb or make_kb("sample")
    store = LineStore(backend={}, index=small_index())
    store.new_shipment(reference=SAMPLE_REFERENCE, threshold=85)
    ref = store.register_file(SAMPLE_XLSX.read_bytes(), SAMPLE_XLSX.name)
    with ModelGuard(script=sample_script(ref)):
        run_turn("Check the packing list.", store, kb, file_ref=ref)
    return store


# --------------------------------------------------------------------------- jobs and model calls
class ModelGuard:
    """Installs the fake structured client and a scripted chat model; `.calls` counts both kinds of model call."""

    def __init__(self, script: list | None = None) -> None:
        self.client = fake_client()
        self.model = ScriptedChatModel(responses=list(script or []), seen=[])

    @property
    def calls(self) -> int:
        return len(self.client.calls) + len(self.model.seen)

    def __enter__(self) -> "ModelGuard":
        import agent.llm as llm

        self._previous = (llm._client_factory, llm._chat_model_factory)
        llm.set_client_factory(lambda: self.client)
        llm.set_chat_model_factory(lambda: self.model)
        return self

    def __exit__(self, *exc: Any) -> None:
        import agent.llm as llm

        llm.set_client_factory(self._previous[0])          # restore, never clear: an outer fake stays installed
        llm.set_chat_model_factory(self._previous[1])


@dataclass
class JobRecorder:
    """Replaces `ui.jobs.start` (monkeypatch) so a test records each Job without a thread."""

    jobs: list = field(default_factory=list)
    running: bool = False

    def start(self, job: Any, store: Any, kb: Any) -> Any:
        job.done = not self.running
        self.jobs.append(job)
        return job

    def keep_running(self) -> "JobRecorder":
        self.running = True
        return self

    def run(self, store: Any, kb: Any, job: Any | None = None) -> Any:
        """Run a recorded job's work inline with the fake client, then mark it done."""
        from ui import jobs

        job = job or self.jobs[-1]
        with ModelGuard():
            jobs.run_job(job, store, kb)
        job.done = True
        return job

    def install(self, monkeypatch: Any) -> "JobRecorder":
        from ui import jobs

        monkeypatch.setattr(jobs, "start", self.start)
        return self


# --------------------------------------------------------------------------- the pages
def _app_script(store, kb):   # no annotations: AppTest runs this function's source alone, without the imports
    import streamlit as st

    from ui import admin, main_page

    which = st.session_state.get("_harness_page", "main")
    pages: dict = {}

    def _main() -> None:
        main_page.render(store, kb, pages["admin"])

    def _admin() -> None:
        admin.render(store, kb, pages["main"])

    pages["main"] = st.Page(_main, title="CargoLint", url_path="main", default=which == "main")
    pages["admin"] = st.Page(_admin, title="CargoLint · Admin", url_path="admin", default=which == "admin")
    st.navigation([pages["main"], pages["admin"]], position="hidden").run()


def app(store: Any, kb: Any, page: str = "main") -> Any:
    """An AppTest of both pages; set `at.session_state["_harness_page"]` to "main" or "admin" between runs."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app_script, args=(store, kb), default_timeout=10)
    at.session_state["_harness_page"] = page
    return at
