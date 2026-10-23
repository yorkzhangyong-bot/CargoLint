"""Line store: versions, lock, decided code, threshold recompute, counts, audit (FR-020 … FR-025)."""
import pytest

from agent.schemas import (
    Actor,
    Candidate,
    ChangeKind,
    ChosenHow,
    Classification,
    CreatedBy,
    Decision,
    DecisionRoute,
    DescriptionCheck,
    Flag,
    FlagKind,
    LineStatus,
    LineVersion,
    ParsedLine,
    Route,
    RuleSource,
    Usage,
)
from agent.store import LineStore, LockedError, UnknownCodeError

pytestmark = pytest.mark.unit


def _parsed(n, zh, en):
    return ParsedLine(line_no=n, text_zh=zh, text_en=en, source_ref=f"row {n}")


def _check(n, kind, source=None, term=None, pure=False):
    flag = Flag(kind=kind, rule_source=source, matched_term=term, reason="r",
                ask_for=[] if kind == FlagKind.ok else ["material", "product_name", "use"], pure_stop_word=pure)
    return DescriptionCheck(line_no=n, flag=flag, status=LineStatus.checked)


def _classify(n, codes_confs, failed=False):
    cands = [Candidate(code=c, subheading_text="t", confidence=k, rationale="r") for c, k in codes_confs]
    return Classification(line_no=n, candidates=cands, no_valid_candidate=not cands, retrieval_trace=None,
                          sources=[], status=LineStatus.failed if failed else LineStatus.checked,
                          error_reason="boom" if failed else None)


def _checked_line(store, n, kind, codes_confs, source=RuleSource.ics2_unacceptable):
    store.update_check(n, _check(n, kind, source if kind != FlagKind.ok else None, "parts" if kind != FlagKind.ok else None))
    store.update_classification(n, _classify(n, codes_confs))


@pytest.fixture
def populated(memory_store):
    s = memory_store
    s.add_lines([_parsed(1, "不锈钢保温杯", "Stainless steel vacuum flask"),   # A: ok 88 -> auto
                 _parsed(2, "LED台灯", "LED desk lamp"),                       # B: ok 72 -> review
                 _parsed(3, "家具", "Furniture"),                              # C: vague 58 -> review
                 _parsed(4, "礼品", "Gift"),                                   # E: stop -> ask
                 _parsed(5, "塑料玩具车", "Plastic toy cars")], CreatedBy.paste)  # D: ok 90, clerk decides review
    _checked_line(s, 1, FlagKind.ok, [("9617.00", 88)])
    _checked_line(s, 2, FlagKind.ok, [("9405.21", 72)])
    _checked_line(s, 3, FlagKind.vague, [("9403.60", 58)])
    s.update_check(4, _check(4, FlagKind.stop_word, RuleSource.firm_stop_words, "gift", pure=True))
    _checked_line(s, 5, FlagKind.ok, [("9503.00", 90)])
    s.set_decision(5, Decision(route=DecisionRoute.review))
    return s


class TestShipmentAndLines:
    def test_new_shipment_resets_usage(self, memory_store):
        memory_store.add_usage(Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost_usd=0.5, cost_eur=0.46, calls=1))
        assert memory_store.shipment.usage.total_tokens == 15
        memory_store.new_shipment(reference="TEST-002", threshold=85)
        assert memory_store.shipment.usage.total_tokens == 0
        assert memory_store.shipment.usage.cost_eur == 0

    def test_add_lines_creates_v1_with_created_by_and_consecutive_numbers(self, memory_store):
        lines = memory_store.add_lines([_parsed(1, "a", "b"), _parsed(2, "c", "d")], CreatedBy.paste)
        assert [l.line_no for l in lines] == [1, 2]
        assert lines[0].versions[0].version_no == 1
        assert lines[0].versions[0].created_by == CreatedBy.paste
        assert lines[0].current.status == LineStatus.pending

    def test_add_version_appends_consecutively_and_never_edits_earlier(self, populated):
        line = populated.get_line(1)
        first_text = line.versions[0].text_en
        v = LineVersion(version_no=1, created_by=CreatedBy.shipper_reply, text_zh="", text_en="steel vacuum flask 500 ml")
        populated.add_version(1, v)
        assert [x.version_no for x in populated.get_line(1).versions] == [1, 2]
        assert populated.get_line(1).versions[0].text_en == first_text
        assert populated.get_line(1).current.text_en == "steel vacuum flask 500 ml"


class TestDecisions:
    def test_flagged_line_cannot_be_accepted(self, populated):
        with pytest.raises(LockedError):
            populated.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9403.60"))
        with pytest.raises(LockedError):
            populated.set_decision(4, Decision(route=DecisionRoute.accepted, decided_code="9617.00"))

    def test_unknown_decided_code_is_rejected_and_nothing_changes(self, populated):
        before = populated.effective_route(populated.get_line(2))
        with pytest.raises(UnknownCodeError):
            populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9999.99"))
        assert populated.effective_route(populated.get_line(2)) == before
        assert populated.get_line(2).current.decision is None

    def test_accepting_an_ok_line_records_code_and_how_it_was_chosen(self, populated):
        populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        line = populated.get_line(2)
        assert populated.effective_route(line) == "accepted"
        assert line.current.decision.chosen_how == ChosenHow.top
        populated.set_decision(1, Decision(route=DecisionRoute.accepted, decided_code="3924.10"))
        assert populated.get_line(1).current.decision.chosen_how == ChosenHow.typed

    def test_clerk_can_send_a_line_to_ask_shipper(self, populated):
        populated.set_decision(2, Decision(route=DecisionRoute.ask_shipper))
        assert populated.effective_route(populated.get_line(2)) == Route.ask_shipper


class TestThreshold:
    def test_recompute_touches_only_undecided_ok_lines(self, populated):
        populated.set_threshold(90)
        assert populated.get_line(1).current.computed_route == Route.review      # 88 < 90
        assert populated.get_line(3).current.computed_route == Route.review      # vague unchanged
        assert populated.effective_route(populated.get_line(5)) == Route.review  # clerk decision kept
        assert not any(r.change == ChangeKind.threshold_recomputed and r.line_no == 5 for r in populated.shipment.audit)
        populated.set_threshold(60)
        assert populated.get_line(1).current.computed_route == Route.auto_accept
        assert populated.get_line(2).current.computed_route == Route.auto_accept  # 72 >= 60
        assert populated.get_line(3).current.computed_route == Route.review

    @pytest.mark.parametrize("bad", [59, 100])
    def test_threshold_range_enforced(self, populated, bad):
        with pytest.raises(ValueError):
            populated.set_threshold(bad)

    def test_set_hybrid(self, populated):
        populated.set_hybrid(False)
        assert populated.shipment.hybrid_search is False


class TestCountsAndDerived:
    def test_counts_and_needs_action(self, populated):
        c = populated.counts()
        assert c["auto_accept"] == 1 and c["review"] == 3 and c["ask_shipper"] == 1
        assert c["needs_action"] == 4 and c["accepted"] == 1
        assert populated.needs_action(populated.get_line(2)) is True
        assert populated.needs_action(populated.get_line(1)) is False

    def test_ready_to_accept_after_a_previously_flagged_line_becomes_ok(self, populated):
        v2 = LineVersion(version_no=2, created_by=CreatedBy.shipper_reply, text_zh="", text_en="wooden dining chairs",
                         flag=Flag(kind=FlagKind.ok), status=LineStatus.checked,
                         candidates=[Candidate(code="9401.69", subheading_text="t", confidence=96, rationale="r")])
        populated.add_version(3, v2)
        line = populated.get_line(3)
        assert line.ever_flagged is True
        assert line.current.computed_route == Route.review
        assert "ready to accept" in line.current.route_reason.lower()
        assert populated.ready_to_accept(line) is True
        populated.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9401.69"))
        assert populated.effective_route(populated.get_line(3)) == "accepted"
        assert populated.ready_to_accept(populated.get_line(3)) is False

    def test_finalize_check_fails_pending_lines_and_returns_counts(self, memory_store):
        memory_store.add_lines([_parsed(1, "a", "b"), _parsed(2, "c", "d")], CreatedBy.paste)
        _checked_line(memory_store, 1, FlagKind.ok, [("9617.00", 90)])
        counts = memory_store.finalize_check()
        line2 = memory_store.get_line(2)
        assert line2.current.status == LineStatus.failed
        assert line2.current.computed_route == Route.review
        assert counts["needs_action"] == 1 and counts["auto_accept"] == 1

    def test_failed_classification_routes_to_review_with_reason(self, memory_store):
        memory_store.add_lines([_parsed(1, "a", "b")], CreatedBy.paste)
        memory_store.update_check(1, _check(1, FlagKind.ok))
        memory_store.update_classification(1, _classify(1, [], failed=True))
        v = memory_store.get_line(1).current
        assert v.status == LineStatus.failed and v.error_reason == "boom"
        assert v.computed_route == Route.review


class TestAuditAndRegistries:
    def test_every_mutation_is_recorded_with_an_actor(self, populated):
        populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        populated.set_threshold(90)
        kinds = {r.change for r in populated.shipment.audit}
        actors = {r.actor for r in populated.shipment.audit}
        assert {ChangeKind.route_computed, ChangeKind.clerk_decision, ChangeKind.code_decided, ChangeKind.threshold_recomputed} <= kinds
        assert {Actor.routing_rule, Actor.clerk, Actor.threshold_change} <= actors
        assert all(r.at is not None and r.line_no >= 1 for r in populated.shipment.audit)

    def test_file_and_reply_registries(self, memory_store):
        f = memory_store.register_file(b"abc", "list.xlsx")
        r1 = memory_store.register_reply("line 1 is steel bobbin cases")
        r2 = memory_store.register_reply("塑料杯")
        assert memory_store.get_file(f) == (b"abc", "list.xlsx")
        assert memory_store.get_reply(r1) == "line 1 is steel bobbin cases"
        assert memory_store.get_reply(r2) == "塑料杯" and r1 != r2


# --------------------------------------------------------------------------- feature 004: the CN-8 choice in the store
from agent.schemas import Cn8Choice, WrittenBy  # noqa: E402

MOTOR = "whether the toy cars incorporate a motor"


def _cn8(store, hs6, cn8=None, confidence=0, written_by=None, question=None, error=None, attribute=""):
    return Cn8Choice(hs6=hs6, options=store.index.cn8_lines(hs6), cn8=cn8, confidence=confidence, written_by=written_by,
                     question=question, error=error, deciding_attribute=attribute)


@pytest.fixture
def cn8_store(memory_store):
    s = memory_store
    s.add_lines([_parsed(1, "塑料玩具车", "Plastic toy cars"),                  # ok 93 -> auto
                 _parsed(2, "铝合金自行车架", "Aluminium alloy bicycle frames"),   # ok 95 -> auto
                 _parsed(3, "LED台灯", "LED desk lamp"),                         # ok 72 -> review
                 _parsed(4, "不锈钢保温杯", "Stainless steel vacuum flask"),       # ok 96 -> auto, single CN-8 line
                 _parsed(5, "家具", "Furniture")], CreatedBy.paste)               # vague -> review
    _checked_line(s, 1, FlagKind.ok, [("9503.00", 93)])
    _checked_line(s, 2, FlagKind.ok, [("8714.91", 95)])
    _checked_line(s, 3, FlagKind.ok, [("9405.21", 72)])
    _checked_line(s, 4, FlagKind.ok, [("9617.00", 96)])
    _checked_line(s, 5, FlagKind.vague, [("9403.60", 58)])
    return s


def _last(store, change, line_no):
    return [r for r in store.shipment.audit if r.change == change and r.line_no == line_no][-1]


class TestCn8:
    def test_writing_by_rule_records_and_keeps_the_route(self, cn8_store):
        s = cn8_store
        s.set_cn8_result(2, _cn8(s, "8714.91", "87149110", 95, WrittenBy.rule))
        v = s.get_line(2).current
        assert v.cn8.cn8 == "87149110" and v.computed_route == Route.auto_accept
        assert v.candidates[0].cn8 == "87149110"
        rec = _last(s, ChangeKind.cn8_written, 2)
        assert rec.actor == Actor.routing_rule and rec.new == "87149110"
        assert rec.note == "written by rule (confidence 95 ≥ threshold 85)"
        s.set_cn8_result(4, _cn8(s, "9617.00", "96170000", 100, WrittenBy.rule))
        assert _last(s, ChangeKind.cn8_written, 4).note == "single CN-8 line"

    def test_a_question_routes_to_ask_shipper_and_keeps_the_decided_hs6(self, cn8_store):
        s = cn8_store
        s.set_cn8_result(1, _cn8(s, "9503.00", question=f"Ask the shipper for: {MOTOR}", attribute=MOTOR))
        line = s.get_line(1)
        assert _last(s, ChangeKind.cn8_question, 1).note == f"Ask the shipper for: {MOTOR}"
        assert line.current.computed_route == Route.ask_shipper
        assert line.current.route_reason == f"the CN-8 depends on {MOTOR}, which the description does not state — ask the shipper"
        assert s.decided_code(line) == ("9503.00", "auto")
        assert s.effective_route(line) == "ask_shipper" and s.needs_action(line)

    def test_a_failed_step_routes_to_review_even_over_an_acceptance(self, cn8_store):
        s = cn8_store
        s.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        s.set_cn8_result(3, _cn8(s, "9405.21", error="invalid output after one retry"))
        line = s.get_line(3)
        assert s.effective_route(line) == "review"
        assert line.current.route_reason == "CN-8 step failed: invalid output after one retry — needs a human look"
        assert s.decided_code(line) == ("9405.21", "top")
        s.confirm_cn8(3, "94052140")
        assert line.current.cn8.error is None and s.effective_route(line) == "accepted"

    def test_an_open_question_overrides_an_acceptance_but_not_a_clerk_route(self, cn8_store):
        s = cn8_store
        s.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        s.set_cn8_result(3, _cn8(s, "9405.21", question="Ask the shipper for: the material", attribute="the material"))
        assert s.effective_route(s.get_line(3)) == "ask_shipper"
        s.set_decision(3, Decision(route=DecisionRoute.review))
        assert s.effective_route(s.get_line(3)) == "review"

    def test_confirming_on_an_auto_accepted_line(self, cn8_store):
        s = cn8_store
        s.set_cn8_result(1, _cn8(s, "9503.00", question=f"Ask the shipper for: {MOTOR}", attribute=MOTOR))
        s.confirm_cn8(1, "95030095")
        line = s.get_line(1)
        d = line.current.decision
        assert (d.route, d.decided_code, d.chosen_how, d.decided_cn8) == (DecisionRoute.accepted, "9503.00", ChosenHow.auto, "95030095")
        assert line.current.cn8.cn8 == "95030095" and line.current.cn8.written_by == WrittenBy.clerk
        assert line.current.cn8.question is None
        rec = _last(s, ChangeKind.cn8_written, 1)
        assert rec.actor == Actor.clerk and rec.note == "confirmed by the clerk" and rec.new == "95030095"
        assert s.effective_route(line) == "accepted" and s.decided_code(line) == ("9503.00", "auto")

    def test_confirm_refusals(self, cn8_store):
        s = cn8_store
        s.set_cn8_result(1, _cn8(s, "9503.00", "95030095", 70))
        with pytest.raises(UnknownCodeError):
            s.confirm_cn8(1, "95039999")
        with pytest.raises(LockedError):
            s.confirm_cn8(3, "94052140")          # HS-6 in review, not decided
        with pytest.raises(LockedError):
            s.confirm_cn8(5, "94036010")          # flagged

    def test_decided_cn8(self, cn8_store):
        s = cn8_store
        s.set_cn8_result(2, _cn8(s, "8714.91", "87149110", 95, WrittenBy.rule))
        assert s.decided_cn8(s.get_line(2)) == "87149110"
        s.set_cn8_result(4, _cn8(s, "9617.00", error="timed out"))
        s.set_cn8_result(1, _cn8(s, "9503.00", question=f"Ask the shipper for: {MOTOR}", attribute=MOTOR))
        assert s.decided_cn8(s.get_line(4)) is None and s.decided_cn8(s.get_line(1)) is None
        s.set_decision(2, Decision(route=DecisionRoute.review))
        assert s.decided_cn8(s.get_line(2)) is None
        s.set_cn8_result(3, _cn8(s, "9405.21", "94052140", 70))
        assert s.decided_cn8(s.get_line(3)) is None   # a suggestion

    def test_counts_cn8_to_confirm(self, cn8_store):
        s = cn8_store
        before = {k: v for k, v in s.counts().items() if k != "cn8_to_confirm"}
        s.set_cn8_result(2, _cn8(s, "8714.91", "87149110", 80))                       # suggestion: counted
        s.set_cn8_result(4, _cn8(s, "9617.00", "96170000", 100, WrittenBy.rule))      # written: not counted
        assert s.counts()["cn8_to_confirm"] == 1
        assert {k: v for k, v in s.counts().items() if k != "cn8_to_confirm"} == before
        s.set_cn8_result(1, _cn8(s, "9503.00", question=f"Ask the shipper for: {MOTOR}", attribute=MOTOR))
        s.set_cn8_result(4, _cn8(s, "9617.00", error="timed out"))
        assert s.counts()["cn8_to_confirm"] == 1                                         # questions and failures are routes

    def test_threshold_reevaluates_unconfirmed_choices(self, cn8_store):
        s = cn8_store
        s.set_cn8_result(2, _cn8(s, "8714.91", "87149110", 90, WrittenBy.rule))
        s.set_cn8_result(1, _cn8(s, "9503.00", "95030095", 90, WrittenBy.rule))
        s.confirm_cn8(1, "95030095")
        s.set_threshold(95)
        assert s.get_line(2).current.cn8.written_by is None
        rec = _last(s, ChangeKind.threshold_recomputed, 2)
        assert rec.actor == Actor.threshold_change and "87149110" in (rec.previous or "") + (rec.note or "")
        assert s.get_line(1).current.cn8.written_by == WrittenBy.clerk
        s.set_threshold(90)
        assert s.get_line(2).current.cn8.written_by == WrittenBy.rule
        assert _last(s, ChangeKind.cn8_written, 2).actor == Actor.threshold_change

    def test_accepting_another_hs6_clears_the_cn8_and_taric(self, cn8_store):
        s = cn8_store
        s.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        s.set_cn8_result(3, _cn8(s, "9405.21", "94052140", 95, WrittenBy.rule))
        s.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        assert s.get_line(3).current.cn8 is not None
        s.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9617.00"))
        v = s.get_line(3).current
        assert v.cn8 is None and v.taric is None

    def test_a_clerk_choice_of_another_code_drops_the_models_estimate(self, cn8_store):
        from agent.schemas import Precedent

        s = cn8_store
        s.set_cn8_result(2, Cn8Choice(hs6="8714.91", options=s.index.cn8_lines("8714.91"), cn8="87149110", confidence=70,
                                      evidence="bicycle frames", rationale="r", precedent=Precedent(reference="DE-1", code="8714911000")))
        s.confirm_cn8(2, "87149110")                     # the model's own suggestion: its estimate still describes it
        c = s.get_line(2).current.cn8
        assert (c.confidence, c.evidence, c.precedent.reference) == (70, "bicycle frames", "DE-1")
        s.confirm_cn8(2, "87149130")                     # another line: the estimate, evidence and ruling were for 87149110
        c = s.get_line(2).current.cn8
        assert (c.cn8, c.written_by, c.confidence, c.evidence, c.rationale, c.precedent) == (
            "87149130", WrittenBy.clerk, 0, "", "", None)

    def test_a_threshold_raise_that_undecides_the_hs6_leaves_its_cn8_alone(self, cn8_store):
        s = cn8_store
        _checked_line(s, 2, FlagKind.ok, [("8714.91", 88)])          # the HS-6 is decided at 85 …
        s.set_cn8_result(2, _cn8(s, "8714.91", "87149110", 95, WrittenBy.rule))
        s.set_taric_result(2, TaricOutcome(origin="CN", rule=TaricRule.auto_completed, subdivisions=["8714911000"]))
        line, start = s.get_line(2), len(s.shipment.audit)
        s.set_threshold(96)                                          # … and no longer at 96 (88 < 96)
        s.set_threshold(92)                                          # still undecided; the CN-8 (95) would pass 92
        assert s.decided_code(line) == (None, None) and s.decided_cn8(line) is None
        finer = [r for r in s.shipment.audit[start:] if r.line_no == 2 and (
            r.change in (ChangeKind.cn8_written, ChangeKind.taric_written) or (r.note or "").startswith(("CN-8 ", "TARIC-10 ")))]
        assert finer == []                       # no "written by rule" for a CN-8 that decided_cn8 does not return
        assert (line.current.cn8.written_by, line.current.taric.taric10) == (WrittenBy.rule, "8714911000")   # left as it was
        s.set_threshold(85)                                          # decided again: read again, still written
        assert (s.decided_cn8(line), s.decided_taric10(line)) == ("87149110", "8714911000")

    def test_a_clerk_acceptance_reevaluates_a_cn8_left_alone_while_undecided(self, cn8_store):
        s = cn8_store
        _checked_line(s, 2, FlagKind.ok, [("8714.91", 88)])
        s.set_cn8_result(2, _cn8(s, "8714.91", "87149110", 95, WrittenBy.rule))
        s.set_threshold(96)                                          # undecided: the CN-8 (95) is left as it was
        s.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="8714.91"))   # the clerk decides the HS-6
        line = s.get_line(2)
        assert line.current.cn8.written_by is None and s.decided_cn8(line) is None and s.cn8_pending(line)   # 95 < 96
        assert _last(s, ChangeKind.threshold_recomputed, 2).note == "CN-8 87149110 back to a suggestion (confidence 95 < threshold 96)"

    def test_a_threshold_change_never_writes_a_choice_whose_precedent_conflicts(self, cn8_store):
        from agent.schemas import Precedent

        s = cn8_store
        s.set_cn8_result(2, Cn8Choice(hs6="8714.91", options=s.index.cn8_lines("8714.91"), cn8="87149110", confidence=84,
                                      precedent=Precedent(reference="DE-FORK-1", code="8714913000")))
        s.set_threshold(80)
        assert s.get_line(2).current.cn8.written_by is None and s.cn8_pending(s.get_line(2))


# --------------------------------------------------------------------------- feature 004: the TARIC outcome in the store
from datetime import date  # noqa: E402

from agent.schemas import TaricOutcome, TaricRule, TaricSuggestion  # noqa: E402

SNAP = date(2026, 10, 1)
PAIR = ["7318155810", "7318155890"]


def _outcome(rule, subdivisions=(), origin="CN", trade_defence=(), types=(), suggestion=None):
    return TaricOutcome(origin=origin, snapshot_date=None if rule == TaricRule.not_loaded else SNAP, rule=rule,
                        subdivisions=list(subdivisions), trade_defence=list(trade_defence), trade_defence_types=list(types),
                        suggestion=suggestion)


def _defence(origin="CN"):
    return _outcome(TaricRule.trade_defence, PAIR, origin, trade_defence=PAIR, types=["552"])


@pytest.fixture
def taric_store(memory_store):
    s = memory_store
    s.add_lines([_parsed(1, "内六角螺钉", "Steel screws with hexagon socket heads"),   # ok 95 -> auto
                 _parsed(2, "十字槽螺钉", "Steel screws with cross-recessed heads"),     # ok 95 -> auto
                 _parsed(3, "螺钉", "Steel screws")], CreatedBy.paste)                  # ok 70 -> review
    for n, conf in ((1, 95), (2, 95), (3, 70)):
        _checked_line(s, n, FlagKind.ok, [("7318.15", conf)])
    return s


class TestTaric:
    def test_each_rule_is_recorded_with_the_snapshot_date_and_origin(self, taric_store):
        s = taric_store
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181595", 95, WrittenBy.rule))
        s.set_taric_result(1, _outcome(TaricRule.auto_completed, ["7318159500"]))
        t = s.get_line(1).current.taric
        assert (t.taric10, t.written_by) == ("7318159500", WrittenBy.rule)
        rec = _last(s, ChangeKind.taric_written, 1)
        assert (rec.actor, rec.new) == (Actor.routing_rule, "7318159500")
        assert rec.note == "auto-completed, single TARIC subdivision, snapshot 2026-10-01; origin CN"
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(2, _defence())
        assert _last(s, ChangeKind.taric_pending, 2).note == "trade-defence measure 552; snapshot 2026-10-01; origin CN"
        s.set_taric_result(2, _outcome(TaricRule.choose, PAIR, "US"))
        assert _last(s, ChangeKind.taric_pending, 2).note == "several subdivisions (2); snapshot 2026-10-01; origin US"
        s.set_taric_result(2, _outcome(TaricRule.not_available))
        assert _last(s, ChangeKind.taric_not_available, 2).note == "TARIC not available; snapshot 2026-10-01; origin CN"
        s.set_taric_result(2, _outcome(TaricRule.not_loaded))
        assert _last(s, ChangeKind.taric_not_available, 2).note == "TARIC not loaded; origin CN"

    def test_the_store_writes_only_what_the_rules_allow(self, taric_store):
        s = taric_store
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        forced = _outcome(TaricRule.choose, PAIR).model_copy(update={"taric10": PAIR[0], "written_by": WrittenBy.rule})
        s.set_taric_result(2, forced)
        assert s.get_line(2).current.taric.taric10 is None          # re-derived with code_to_write
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181595", 70))     # a CN-8 suggestion
        s.set_taric_result(1, _outcome(TaricRule.auto_completed, ["7318159500"]))
        assert s.get_line(1).current.taric.taric10 is None
        assert _last(s, ChangeKind.taric_pending, 1).note.startswith("single TARIC subdivision, written once the CN-8 is")

    def test_a_kept_suggestion_marks_the_decided_candidate(self, taric_store):
        s = taric_store
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(2, _outcome(TaricRule.choose, PAIR, suggestion=TaricSuggestion(code=PAIR[0], confidence=88)))
        v = s.get_line(2).current
        assert v.candidates[0].taric10 == PAIR[0] and v.taric.taric10 is None

    def test_confirming_on_an_auto_accepted_line(self, taric_store):
        s = taric_store
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(2, _defence())
        s.confirm_taric10(2, PAIR[0])
        line = s.get_line(2)
        d = line.current.decision
        assert (d.route, d.decided_code, d.chosen_how, d.decided_cn8, d.decided_taric10) == (
            DecisionRoute.accepted, "7318.15", ChosenHow.auto, "73181558", PAIR[0])
        assert (line.current.taric.taric10, line.current.taric.written_by) == (PAIR[0], WrittenBy.clerk)
        assert line.current.cn8.written_by == WrittenBy.clerk          # the TARIC-10 confirms the CN-8 it sits under
        cn8_rec, rec = [r for r in s.shipment.audit if r.line_no == 2 and r.actor == Actor.clerk][-2:]
        assert (cn8_rec.change, cn8_rec.new) == (ChangeKind.cn8_written, "73181558")
        assert cn8_rec.note == f"confirmed by the clerk with TARIC-10 {PAIR[0]}"
        assert (rec.change, rec.new) == (ChangeKind.taric_written, PAIR[0])
        assert rec.note == "confirmed by the clerk; snapshot 2026-10-01; origin CN"
        assert s.decided_taric10(line) == PAIR[0] and s.effective_route(line) == "accepted"
        assert s.decided_code(line) == ("7318.15", "auto") and s.decided_cn8(line) == "73181558"

    def test_a_cn8_the_clerk_confirmed_before_gets_no_second_entry(self, taric_store):
        s = taric_store
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 70))
        s.confirm_cn8(2, "73181558")
        s.set_taric_result(2, _defence())
        before = len([r for r in s.shipment.audit if r.change == ChangeKind.cn8_written and r.line_no == 2])
        s.confirm_taric10(2, PAIR[1])
        assert len([r for r in s.shipment.audit if r.change == ChangeKind.cn8_written and r.line_no == 2]) == before
        assert _last(s, ChangeKind.taric_written, 2).new == PAIR[1]
        assert s.get_line(2).current.decision.decided_cn8 == "73181558"

    def test_confirm_refusals(self, taric_store):
        s = taric_store
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(2, _defence())
        with pytest.raises(UnknownCodeError):
            s.confirm_taric10(2, "7318159500")                      # not one of the subdivisions
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181558", 70))     # the CN-8 is a suggestion
        s.set_taric_result(1, _defence())
        with pytest.raises(LockedError):
            s.confirm_taric10(1, PAIR[0])
        s.set_decision(2, Decision(route=DecisionRoute.review))     # the HS-6 is no longer decided
        with pytest.raises(LockedError):
            s.confirm_taric10(2, PAIR[0])
        assert s.get_line(1).current.taric.taric10 is None and s.get_line(2).current.taric.taric10 is None

    def test_asking_the_shipper_instead_of_confirming(self, taric_store):
        s = taric_store
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(2, _defence())
        s.ask_shipper_for_taric(2, "Are the screws self-locking?")
        line = s.get_line(2)
        assert line.current.decision.route == DecisionRoute.ask_shipper
        assert (line.current.taric.question, line.current.taric.taric10) == ("Are the screws self-locking?", None)
        assert s.effective_route(line) == "ask_shipper" and s.decided_taric10(line) is None
        rec = _last(s, ChangeKind.taric_question, 2)
        assert rec.actor == Actor.clerk
        assert rec.note == "Ask the shipper for: Are the screws self-locking?; snapshot 2026-10-01; origin CN"
        assert s.counts()["taric_to_confirm"] == 0
        with pytest.raises(ValueError):
            s.ask_shipper_for_taric(2, "   ")

    def test_counts_taric_to_confirm(self, taric_store):
        s = taric_store
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(1, _defence())                                       # counted
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 70))                 # the CN-8 is a suggestion: not counted
        s.set_taric_result(2, _defence())
        routes = {k: v for k, v in s.counts().items() if not k.endswith("_to_confirm")}
        assert s.counts()["taric_to_confirm"] == 1
        s.set_taric_result(1, _outcome(TaricRule.choose, PAIR, "US"))             # choose is counted too
        assert s.counts()["taric_to_confirm"] == 1
        assert {k: v for k, v in s.counts().items() if not k.endswith("_to_confirm")} == routes   # never a route
        s.confirm_taric10(1, PAIR[1])
        assert s.counts()["taric_to_confirm"] == 0

    def test_confirming_the_cn8_writes_an_auto_completed_taric10(self, taric_store):
        s = taric_store
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181595", 70))
        s.set_taric_result(1, _outcome(TaricRule.auto_completed, ["7318159500"]))
        s.confirm_cn8(1, "73181595")
        t = s.get_line(1).current.taric
        assert (t.taric10, t.written_by) == ("7318159500", WrittenBy.rule)
        rec = _last(s, ChangeKind.taric_written, 1)
        assert rec.note.startswith("auto-completed, single TARIC subdivision, snapshot 2026-10-01")
        assert rec.actor == Actor.routing_rule                        # a rule outcome, set off by the clerk's CN-8

    def test_confirming_another_cn8_drops_the_taric_outcome(self, taric_store):
        s = taric_store
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181595", 70))
        s.set_taric_result(1, _outcome(TaricRule.auto_completed, ["7318159500"]))
        s.confirm_cn8(1, "73181558")
        assert s.get_line(1).current.taric is None                  # the TARIC step runs again for the new CN-8

    def test_the_threshold_withdraws_and_rewrites_a_rule_written_taric10(self, taric_store):
        s = taric_store
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181595", 90, WrittenBy.rule))
        s.set_taric_result(1, _outcome(TaricRule.auto_completed, ["7318159500"]))
        s.set_cn8_result(2, _cn8(s, "7318.15", "73181558", 90, WrittenBy.rule))
        s.set_taric_result(2, _defence())
        s.confirm_taric10(2, PAIR[0])
        s.set_threshold(95)
        t = s.get_line(1).current.taric
        assert (t.taric10, t.written_by) == (None, None)
        rec = _last(s, ChangeKind.threshold_recomputed, 1)
        assert (rec.previous, rec.actor) == ("7318159500", Actor.threshold_change) and "withdrawn" in rec.note
        assert s.get_line(2).current.taric.taric10 == PAIR[0]       # confirmed by the clerk: stays …
        assert s.get_line(2).current.cn8.written_by == WrittenBy.clerk   # … with its CN-8, which the threshold never touches
        assert s.decided_taric10(s.get_line(2)) == PAIR[0]
        s.set_threshold(90)
        t = s.get_line(1).current.taric
        assert (t.taric10, t.written_by) == ("7318159500", WrittenBy.rule)
        assert _last(s, ChangeKind.taric_written, 1).actor == Actor.threshold_change

    def test_a_new_cn8_result_drops_the_taric_outcome(self, taric_store):
        s = taric_store
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181595", 95, WrittenBy.rule))
        s.set_taric_result(1, _outcome(TaricRule.auto_completed, ["7318159500"]))
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        assert s.get_line(1).current.taric is None


class TestTaricOrigin:
    """US4 (FR-017): the goods' origin for TARIC, per invoice; CN by default."""

    def test_two_letters_upper_cased_and_anything_else_refused(self, memory_store):
        s = memory_store
        assert s.shipment.taric_origin == "CN"
        assert s.set_taric_origin("us") == "US" and s.shipment.taric_origin == "US"
        assert s.set_taric_origin(" cn ") == "CN"
        s.set_taric_origin("US")
        for bad in ("C1", "CHN", "", "  ", None):
            with pytest.raises(ValueError):
                s.set_taric_origin(bad)
            assert s.shipment.taric_origin == "US"   # the previous origin stays


class TestFinerCodeAudit:
    """FR-020: every CN-8 and TARIC-10 outcome leaves a record: the time, the line and version, the change kind, the
    actor (the rule or the clerk) and a note with the rule; TARIC records carry the snapshot date and the origin."""

    def test_every_outcome_is_recorded(self, memory_store):
        s = memory_store
        lines = [("十字槽螺钉", "7318.15"), ("不锈钢保温杯", "9617.00"), ("螺钉", "7318.15"), ("螺钉", "7318.15"),
                 ("塑料玩具车", "9503.00"), ("铝合金自行车架", "8714.91"), ("螺钉", "7318.15"), ("螺钉", "7318.15")]
        s.add_lines([_parsed(n, z, f"goods {n}") for n, (z, _) in enumerate(lines, 1)], CreatedBy.paste)
        for n, (_, code) in enumerate(lines, 1):
            _checked_line(s, n, FlagKind.ok, [(code, 95)])
        s.set_cn8_result(1, _cn8(s, "7318.15", "73181595", 95, WrittenBy.rule))
        s.set_taric_result(1, _outcome(TaricRule.auto_completed, ["7318159500"]))
        s.set_cn8_result(2, _cn8(s, "9617.00", "96170000", 100, WrittenBy.rule))
        s.set_taric_result(2, _outcome(TaricRule.not_available))
        s.set_cn8_result(3, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(3, _defence())
        s.confirm_taric10(3, PAIR[0])
        s.set_cn8_result(4, _cn8(s, "7318.15", "73181558", 70))
        s.confirm_cn8(4, "73181558")
        s.set_taric_result(4, _outcome(TaricRule.choose, PAIR))
        s.ask_shipper_for_taric(4, "Are the screws self-locking?")
        s.set_cn8_result(5, _cn8(s, "9503.00", question=f"Ask the shipper for: {MOTOR}", attribute=MOTOR))
        s.set_cn8_result(6, _cn8(s, "8714.91", error="SchemaError: invalid after 2 attempts"))
        s.set_cn8_result(7, _cn8(s, "7318.15", "73181558", 95, WrittenBy.rule))
        s.set_taric_result(7, _outcome(TaricRule.not_loaded))
        s.set_cn8_result(8, _cn8(s, "7318.15", "73181558", 70))
        expected = [
            (1, ChangeKind.cn8_written, Actor.routing_rule, "written by rule (confidence 95 ≥ threshold 85)"),
            (2, ChangeKind.cn8_written, Actor.routing_rule, "single CN-8 line"),
            (4, ChangeKind.cn8_written, Actor.clerk, "confirmed by the clerk"),
            (5, ChangeKind.cn8_question, Actor.routing_rule, f"Ask the shipper for: {MOTOR}"),
            (8, ChangeKind.cn8_pending, Actor.routing_rule, "to confirm: confidence 70 < threshold 85"),
            (6, ChangeKind.route_computed, Actor.routing_rule,
             "CN-8 step failed: SchemaError: invalid after 2 attempts — needs a human look"),
            (1, ChangeKind.taric_written, Actor.routing_rule, "auto-completed, single TARIC subdivision, snapshot 2026-10-01; origin CN"),
            (3, ChangeKind.cn8_written, Actor.clerk, f"confirmed by the clerk with TARIC-10 {PAIR[0]}"),
            (3, ChangeKind.taric_written, Actor.clerk, "confirmed by the clerk; snapshot 2026-10-01; origin CN"),
            (3, ChangeKind.taric_pending, Actor.routing_rule, "trade-defence measure 552; snapshot 2026-10-01; origin CN"),
            (4, ChangeKind.taric_pending, Actor.routing_rule, "several subdivisions (2); snapshot 2026-10-01; origin CN"),
            (4, ChangeKind.taric_question, Actor.clerk,
             "Ask the shipper for: Are the screws self-locking?; snapshot 2026-10-01; origin CN"),
            (2, ChangeKind.taric_not_available, Actor.routing_rule, "TARIC not available; snapshot 2026-10-01; origin CN"),
            (7, ChangeKind.taric_not_available, Actor.routing_rule, "TARIC not loaded; origin CN"),
        ]
        for n, change, actor, note in expected:
            found = [r for r in s.shipment.audit if (r.line_no, r.change, r.actor, r.note) == (n, change, actor, note)]
            assert found, f"no {change.value} record for line {n}: {note}"
            assert found[-1].at is not None and found[-1].version_no == s.get_line(n).current.version_no

    def test_a_suggestion_names_the_conflicting_ruling(self, cn8_store):
        from agent.schemas import Precedent

        s = cn8_store
        s.set_cn8_result(2, Cn8Choice(hs6="8714.91", options=s.index.cn8_lines("8714.91"), cn8="87149110", confidence=95,
                                      precedent=Precedent(reference="DE-FORK-1", code="8714913000")))
        rec = _last(s, ChangeKind.cn8_pending, 2)
        assert (rec.new, rec.actor) == ("87149110", Actor.routing_rule)
        assert rec.note == "to confirm: the cited ruling DE-FORK-1 classifies under 87149130, not 87149110"
