"""lookup_taric (feature 004, contracts/tools.md §1.7): the four rules and "TARIC not loaded" on the small fixture
snapshot, the suggestion among several subdivisions, absorbed suggestion failures, the audit (data-model §5) and the
adversarial line."""
import json
from pathlib import Path

import pytest

from agent.llm import get_client, set_client_factory
from agent.prompts import fence
from agent.schemas import (Actor, Candidate, ChangeKind, Classification, Cn8Choice, CreatedBy, DescriptionCheck, Flag, FlagKind,
                           LineStatus, ParsedLine, TaricRule, WrittenBy)
from rag.bti import BTIStore
from rag.loader import KnowledgeBase
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from rag.taric import TaricStore
from tests.fakes import FakeRawClient

pytestmark = pytest.mark.integration

SMALL = Path(__file__).resolve().parents[1] / "fixtures" / "taric" / "snapshot_small.jsonl"
SCREWS = ("碳钢十字槽盘头螺钉", "Carbon steel cross-recessed pan head screws M4 x 10")


@pytest.fixture
def make_kb(small_index, fake_embeddings, rules):
    def make(taric=True):
        bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
        vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
        return KnowledgeBase(small_index, HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index), BTIStore([]), rules,
                             {"embedding_model": "fake", "built_at": "2026-10-14T00:00:00"}, fake_embeddings,
                             taric=TaricStore.from_jsonl(SMALL) if taric else None)
    return make


@pytest.fixture
def fake_client():
    """A FakeRawClient with its own SubdivisionOut table, wrapped by the real StructuredCaller."""
    def make(table=None, **kw):
        fake = FakeRawClient(recorded={"SubdivisionOut": table or {}}, **kw)
        set_client_factory(lambda: fake)
        return get_client(), fake

    yield make
    set_client_factory(None)


def screw_line(store, cn8, written=True, text=SCREWS):
    """A checked OK line whose HS-6 7318.15 is auto-decided, with a CN-8 written by rule or suggested."""
    store.add_lines([ParsedLine(text_zh=text[0], text_en=text[1])], CreatedBy.paste)
    n = len(store.lines)
    store.update_check(n, DescriptionCheck(line_no=n, flag=Flag(kind=FlagKind.ok), status=LineStatus.checked))
    store.update_classification(n, Classification(line_no=n, candidates=[
        Candidate(code="7318.15", subheading_text="Screws and bolts", confidence=95, rationale="r")], status=LineStatus.checked))
    store.set_cn8_result(n, Cn8Choice(hs6="7318.15", options=store.index.cn8_lines("7318.15"), cn8=cn8,
                                      confidence=95 if written else 70, written_by=WrittenBy.rule if written else None))
    return n


def key(text=SCREWS):
    return " / ".join(t for t in text if t)


def suggestion(code, confidence=88, visible=True):
    return {"code": code, "confidence": confidence, "attribute_visible": visible, "rationale": "the description states it"}


def last(store, change, n):
    return [r for r in store.shipment.audit if r.change == change and r.line_no == n][-1]


class TestRules:
    def test_a_single_subdivision_is_written_once_the_cn8_is_written(self, fake_client, make_kb, memory_store):
        from tools.lookup_taric import run_taric_step

        client, fake = fake_client()
        s = memory_store
        written, suggested = screw_line(s, "73181595"), screw_line(s, "73181595", written=False)
        run_taric_step(s, make_kb(), client)
        t = s.get_line(written).current.taric
        assert (t.rule, t.subdivisions, t.taric10, t.written_by) == (TaricRule.auto_completed, ["7318159500"], "7318159500",
                                                                     WrittenBy.rule)
        assert (str(t.snapshot_date), t.origin) == ("2026-10-01", "CN")
        rec = last(s, ChangeKind.taric_written, written)
        assert rec.note.startswith("auto-completed, single TARIC subdivision, snapshot 2026-10-01") and "origin CN" in rec.note
        assert (rec.actor, rec.new) == (Actor.routing_rule, "7318159500")
        t = s.get_line(suggested).current.taric
        assert (t.rule, t.taric10, t.written_by) == (TaricRule.auto_completed, None, None)
        assert s.decided_taric10(s.get_line(written)) == "7318159500" and s.decided_taric10(s.get_line(suggested)) is None
        assert fake.prompts_for("SubdivisionOut") == []          # no suggestion call for a single subdivision

    def test_china_has_trade_defence_on_both_subdivisions(self, fake_client, make_kb, memory_store):
        from tools.lookup_taric import run_taric_step

        client, fake = fake_client()
        s = memory_store
        n = screw_line(s, "73181558")
        run_taric_step(s, make_kb(), client)
        t = s.get_line(n).current.taric
        assert (t.rule, t.taric10, t.written_by) == (TaricRule.trade_defence, None, None)
        assert t.subdivisions == ["7318155810", "7318155890"] and t.trade_defence == ["7318155810", "7318155890"]
        assert t.trade_defence_types == ["552"]      # recorded at the CN-8 level, so it applies to both
        rec = last(s, ChangeKind.taric_pending, n)
        assert rec.note.startswith("trade-defence measure 552") and "snapshot 2026-10-01" in rec.note and "origin CN" in rec.note
        assert s.counts()["taric_to_confirm"] == 1
        assert len(fake.prompts_for("SubdivisionOut")) == 1   # several subdivisions: one suggestion call

    def test_for_the_us_the_clerk_chooses_and_a_valid_suggestion_is_highlighted(self, fake_client, make_kb, memory_store):
        from tools.lookup_taric import run_taric_step

        client, fake = fake_client({key(): suggestion("7318155810")})
        s = memory_store
        s.shipment.taric_origin = "US"
        n = screw_line(s, "73181558")
        route_before = s.effective_route(s.get_line(n))
        run_taric_step(s, make_kb(), client)
        v = s.get_line(n).current
        assert (v.taric.rule, v.taric.trade_defence, v.taric.taric10) == (TaricRule.choose, [], None)
        assert (v.taric.suggestion.code, v.taric.suggestion.confidence) == ("7318155810", 88)
        assert v.candidates[0].taric10 == "7318155810"           # the highlighted subdivision, never written
        assert len(fake.prompts_for("SubdivisionOut")) == 1
        assert s.effective_route(s.get_line(n)) == route_before
        rec = last(s, ChangeKind.taric_pending, n)
        assert rec.note.startswith("several subdivisions") and "origin US" in rec.note

    @pytest.mark.parametrize("answer", [suggestion("7318155810", visible=False), suggestion("7318159500"),
                                        suggestion(None, 0)])
    def test_a_suggestion_needs_the_attribute_stated_and_one_of_the_subdivisions(self, fake_client, make_kb, memory_store,
                                                                                answer):
        from tools.lookup_taric import run_taric_step

        client, _ = fake_client({key(): answer})
        s = memory_store
        s.shipment.taric_origin = "US"
        n = screw_line(s, "73181558")
        run_taric_step(s, make_kb(), client)
        v = s.get_line(n).current
        assert (v.taric.rule, v.taric.suggestion, v.taric.suggestion_error) == (TaricRule.choose, None, None)
        assert v.candidates[0].taric10 is None

    @pytest.mark.parametrize("failure", ["invalid output", "API error"])
    def test_a_failed_suggestion_call_is_absorbed(self, fake_client, make_kb, memory_store, failure):
        from tools.lookup_taric import run_taric_step

        kw = {"invalid_first": {("SubdivisionOut", key()): 2}} if failure == "invalid output" else {"fail_on": {key()}}
        client, fake = fake_client({key(): suggestion("7318155810")}, **kw)
        s = memory_store
        s.shipment.taric_origin = "US"
        n = screw_line(s, "73181558")
        route_before = s.effective_route(s.get_line(n))
        [result] = run_taric_step(s, make_kb(), client)
        t = s.get_line(n).current.taric
        assert (t.rule, t.subdivisions) == (TaricRule.choose, ["7318155810", "7318155890"])
        assert t.suggestion is None and t.suggestion_error and t.taric10 is None
        assert result.outcome.suggestion_error == t.suggestion_error
        assert s.effective_route(s.get_line(n)) == route_before
        if failure == "invalid output":
            assert len(fake.prompts_for("SubdivisionOut")) == 2   # the first call and one retry

    def test_the_per_line_timeout_keeps_the_rule_without_a_suggestion(self, fake_client, make_kb, monkeypatch):
        import tools.lookup_taric as lt
        from agent.schemas import TaricInput, TaricLine

        client, _ = fake_client()

        def hangs(*args, **kwargs):
            raise TimeoutError("the line took longer than the per-line timeout")

        monkeypatch.setattr(lt, "taric_outcome", hangs)
        inp = TaricInput(lines=[TaricLine(line_no=1, text_en="screws", cn8="73181558", cn8_written=True)], origin="US")
        [res] = lt.lookup_taric_lines(inp, make_kb(), client, workers=1)
        assert (res.outcome.rule, res.outcome.suggestion, res.outcome.taric10) == (TaricRule.choose, None, None)
        assert "TimeoutError" in res.outcome.suggestion_error

    def test_a_single_subdivision_with_a_570_control_needs_the_clerk_for_china_only(self, fake_client, make_kb, memory_store):
        from tools.lookup_taric import run_taric_step

        client, fake = fake_client()
        s = memory_store
        n = screw_line(s, "73181568")
        run_taric_step(s, make_kb(), client)
        t = s.get_line(n).current.taric
        assert (t.rule, t.taric10, t.trade_defence, t.trade_defence_types) == (TaricRule.trade_defence, None, ["7318156800"],
                                                                              ["570"])
        s.shipment.taric_origin = "US"
        run_taric_step(s, make_kb(), client)                  # no outcome for the US yet
        t = s.get_line(n).current.taric
        assert (t.rule, t.taric10, t.written_by, t.origin) == (TaricRule.auto_completed, "7318156800", WrittenBy.rule, "US")
        assert fake.prompts_for("SubdivisionOut") == []

    def test_a_cn8_without_subdivisions_stops_at_eight_digits(self, fake_client, make_kb, memory_store):
        from tools.lookup_taric import run_taric_step

        client, fake = fake_client()
        s = memory_store
        n = screw_line(s, "73181520")     # fixture only: on the real snapshot every CN-8 has a subdivision (research R-16)
        run_taric_step(s, make_kb(), client)
        t = s.get_line(n).current.taric
        assert (t.rule, t.subdivisions, t.taric10) == (TaricRule.not_available, [], None)
        rec = last(s, ChangeKind.taric_not_available, n)
        assert rec.note.startswith("TARIC not available") and "2026-10-01" in rec.note and "origin CN" in rec.note
        assert fake.prompts_for("SubdivisionOut") == []

    def test_without_a_snapshot_taric_is_not_loaded(self, fake_client, make_kb, memory_store):
        from tools.lookup_taric import run_taric_step

        client, fake = fake_client()
        s = memory_store
        n = screw_line(s, "73181558")
        run_taric_step(s, make_kb(taric=False), client)
        t = s.get_line(n).current.taric
        assert (t.rule, t.snapshot_date, t.subdivisions, t.taric10) == (TaricRule.not_loaded, None, [], None)
        assert last(s, ChangeKind.taric_not_available, n).note.startswith("TARIC not loaded")
        assert fake.prompts_for("SubdivisionOut") == []


class TestTool:
    def test_the_tool_takes_lines_with_a_cn8_and_no_outcome_for_the_origin(self, fake_client, make_kb, memory_store):
        from tools.common import ToolContext, set_context
        from tools.lookup_taric import lookup_taric_tool

        client, _ = fake_client()
        s = memory_store
        a, b = screw_line(s, "73181595"), screw_line(s, "73181558")
        s.add_lines([ParsedLine(text_zh="配件", text_en="Parts")], CreatedBy.paste)   # no CN-8: untouched
        set_context(ToolContext(store=s, kb=make_kb(), client=client, workers=1))
        try:
            out = json.loads(lookup_taric_tool.invoke({}))
            again = json.loads(lookup_taric_tool.invoke({}))
        finally:
            set_context(None)
        assert [line["line_no"] for line in out["lines"]] == [a, b]
        assert out["summary"] == "TARIC for 2 lines: 1 written, 1 to confirm"
        assert out["lines"][0]["taric10"] == "7318159500" and out["lines"][1]["rule"] == "trade_defence"
        assert again == {"summary": "No line needed a TARIC lookup", "lines": []}
        assert s.get_line(3).current.taric is None


class TestAdversarial:
    def test_an_instruction_in_the_line_never_writes_the_taric10(self, fake_client, make_kb, memory_store, adversarial_lines):
        from tools.lookup_taric import run_taric_step

        push = next(line for line in adversarial_lines if line["kind"] == "cn8_taric_push")
        text = (push["text_zh"], push["text_en"])
        client, fake = fake_client({key(text): suggestion("7318155810", 98)})
        s = memory_store
        s.shipment.taric_origin = "US"
        n = screw_line(s, "73181558", text=text)
        run_taric_step(s, make_kb(), client)
        t = s.get_line(n).current.taric
        assert t.rule == TaricRule.choose and t.suggestion.code == "7318155810"
        assert (t.taric10, t.written_by) == (None, None) and s.decided_taric10(s.get_line(n)) is None
        [prompt] = fake.prompts_for("SubdivisionOut")
        assert prompt.count("Ignore the rules") == 1 and fence(key(text), n) in prompt


class TestLineTaricView:
    """US3: the agent's display function; the UI calls it and never reads kb.taric itself."""

    def test_the_view_for_a_line_with_a_cn8_follows_the_shipment_origin(self, fake_client, make_kb, memory_store):
        from agent.agent import line_taric_view
        from tools.lookup_taric import run_taric_step

        client, _ = fake_client()
        s = memory_store
        n = screw_line(s, "73181558")
        kb = make_kb()
        run_taric_step(s, kb, client)
        view = line_taric_view(s, kb, n)
        assert (view.origin, str(view.snapshot_date), view.rule) == ("CN", "2026-10-01", TaricRule.trade_defence)
        assert [sv.code for sv in view.subdivisions] == ["7318155810", "7318155890"]
        assert [m.measure_type for m in view.subdivisions[0].groups["trade_defence"]] == ["552", "552"]
        s.shipment.taric_origin = "US"
        view = line_taric_view(s, kb, n)
        assert view.origin == "US" and all(not sv.groups["trade_defence"] for sv in view.subdivisions)

    def test_no_view_without_a_cn8(self, make_kb, memory_store):
        from agent.agent import line_taric_view

        s = memory_store
        s.add_lines([ParsedLine(text_zh="配件", text_en="Parts")], CreatedBy.paste)
        assert line_taric_view(s, make_kb(), 1) is None

    def test_without_a_snapshot_the_view_has_no_subdivisions(self, make_kb, memory_store):
        from agent.agent import line_taric_view

        s = memory_store
        n = screw_line(s, "73181558")
        view = line_taric_view(s, make_kb(taric=False), n)
        assert view.subdivisions == () and view.snapshot_date is None


class TestOrigin:
    """US4 (FR-017, FR-018): a new origin re-applies the lookup and the rules, with no model call."""

    def test_a_new_origin_reapplies_the_rules_and_keeps_the_clerks_codes(self, fake_client, make_kb, memory_store):
        from agent.agent import apply_taric_origin
        from tools.lookup_taric import run_taric_step

        client, fake = fake_client({key(): suggestion("7318155810")})
        s = memory_store
        bolts = screw_line(s, "73181558")        # CN: trade defence on both subdivisions, with a suggestion
        single = screw_line(s, "73181595")       # CN: auto-completed and written by rule
        confirmed = screw_line(s, "73181568")    # CN: trade defence (570); the clerk confirms it
        s.add_lines([ParsedLine(text_zh="配件", text_en="Parts")], CreatedBy.paste)   # no CN-8
        kb = make_kb()
        run_taric_step(s, kb, client)
        s.confirm_taric10(confirmed, "7318156800")
        calls, before = len(fake.prompts_for("SubdivisionOut")), len(s.shipment.audit)
        assert apply_taric_origin(s, kb, "us") == "Origin US: the TARIC rules re-applied to 3 lines"
        assert s.shipment.taric_origin == "US"
        t = s.get_line(bolts).current.taric
        assert (t.rule, t.origin, t.suggestion.code) == (TaricRule.choose, "US", "7318155810")   # the stored suggestion
        assert len(fake.prompts_for("SubdivisionOut")) == calls                                 # no model call
        t = s.get_line(single).current.taric
        assert (t.rule, t.taric10, t.written_by) == (TaricRule.trade_defence, None, None)   # 552 erga omnes applies to the US
        assert s.taric_pending(s.get_line(single))
        t = s.get_line(confirmed).current.taric
        assert (t.rule, t.taric10, t.written_by) == (TaricRule.auto_completed, "7318156800", WrittenBy.clerk)   # FR-018
        new = [r for r in s.shipment.audit[before:] if r.change.value.startswith("taric_")]
        assert {r.line_no for r in new} == {bolts, single, confirmed}
        assert all(r.note.endswith("origin US") for r in new)
        assert last(s, ChangeKind.taric_pending, single).previous == "7318159500"     # the withdrawn code
        assert s.get_line(4).current.taric is None

    def test_a_refused_origin_changes_nothing(self, fake_client, make_kb, memory_store):
        from agent.agent import apply_taric_origin
        from tools.lookup_taric import run_taric_step

        client, _ = fake_client()
        s = memory_store
        n = screw_line(s, "73181595")
        kb = make_kb()
        run_taric_step(s, kb, client)
        before = len(s.shipment.audit)
        with pytest.raises(ValueError):
            apply_taric_origin(s, kb, "C1")
        assert s.shipment.taric_origin == "CN" and len(s.shipment.audit) == before
        assert s.get_line(n).current.taric.origin == "CN"

    def test_a_line_whose_taric_step_has_not_run_waits_for_it(self, fake_client, make_kb, memory_store):
        from agent.agent import apply_taric_origin
        from tools.lookup_taric import needs_taric

        s = memory_store
        n = screw_line(s, "73181558")
        assert apply_taric_origin(s, make_kb(), "US") == "Origin US: the TARIC rules re-applied to 0 lines"
        assert s.get_line(n).current.taric is None and needs_taric(s, s.get_line(n)) == "73181558"
