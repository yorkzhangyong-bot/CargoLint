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

    def test_a_threshold_change_never_writes_a_choice_whose_precedent_conflicts(self, cn8_store):
        from agent.schemas import Precedent

        s = cn8_store
        s.set_cn8_result(2, Cn8Choice(hs6="8714.91", options=s.index.cn8_lines("8714.91"), cn8="87149110", confidence=84,
                                      precedent=Precedent(reference="DE-FORK-1", code="8714913000")))
        s.set_threshold(80)
        assert s.get_line(2).current.cn8.written_by is None and s.cn8_pending(s.get_line(2))
