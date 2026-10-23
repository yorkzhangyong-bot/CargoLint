"""Routing table, threshold boundary, lock rule and contradiction rule (constitution Principle I)."""
import pytest

from agent.routing import is_contradiction, route_line
from agent.schemas import Candidate, FlagKind, LineStatus, Route

pytestmark = pytest.mark.unit

T, F = 85, 50  # threshold, ask floor


def _route(flag, conf, status="checked", ever_flagged=False, threshold=T, ask_floor=F):
    route, reason = route_line(flag, conf, status, ever_flagged, threshold, ask_floor)
    return route, reason


class TestRoutingTable:
    def test_stop_word_goes_to_ask_shipper_regardless_of_confidence(self):
        assert _route(FlagKind.stop_word, 99)[0] == Route.ask_shipper
        assert _route(FlagKind.stop_word, 0)[0] == Route.ask_shipper

    def test_vague_below_ask_floor_goes_to_ask_shipper(self):
        assert _route(FlagKind.vague, 31)[0] == Route.ask_shipper
        assert _route(FlagKind.vague, 49)[0] == Route.ask_shipper

    def test_vague_at_or_above_ask_floor_goes_to_review(self):
        assert _route(FlagKind.vague, 50)[0] == Route.review
        assert _route(FlagKind.vague, 58)[0] == Route.review
        assert _route(FlagKind.vague, 96)[0] == Route.review  # flagged lines never auto-accept

    def test_ok_at_or_above_threshold_auto_accepts(self):
        assert _route(FlagKind.ok, 96)[0] == Route.auto_accept
        assert _route(FlagKind.ok, 88)[0] == Route.auto_accept

    def test_boundary_confidence_equal_to_threshold_counts_as_at_or_above(self):
        assert _route(FlagKind.ok, 85)[0] == Route.auto_accept
        assert _route(FlagKind.ok, 84)[0] == Route.review

    def test_ok_below_threshold_goes_to_review_with_reason(self):
        route, reason = _route(FlagKind.ok, 72)
        assert route == Route.review
        assert "72" in reason and "85" in reason

    def test_ever_flagged_line_is_capped_at_review_and_ready_to_accept(self):
        route, reason = _route(FlagKind.ok, 96, ever_flagged=True)
        assert route == Route.review
        assert "ready to accept" in reason.lower()

    def test_no_candidates_unreadable_or_failed_go_to_review(self):
        assert _route(FlagKind.ok, None)[0] == Route.review
        assert _route(None, None, status=LineStatus.failed)[0] == Route.review
        assert _route(FlagKind.ok, 0)[0] == Route.review

    def test_threshold_changes_route(self):
        assert _route(FlagKind.ok, 88, threshold=95)[0] == Route.review
        assert _route(FlagKind.ok, 61, threshold=60)[0] == Route.auto_accept

    def test_string_inputs_are_accepted(self):
        assert _route("stop_word", 10)[0] == Route.ask_shipper
        assert _route("ok", 90, status="checked")[0] == Route.auto_accept

    @pytest.mark.parametrize("bad", [59, 100, 0, -1])
    def test_threshold_outside_60_99_is_rejected(self, bad):
        with pytest.raises(ValueError):
            route_line(FlagKind.ok, 90, "checked", False, bad, F)


def _cand(code, conf=90):
    return Candidate(code=code, subheading_text="x", confidence=conf, rationale="r")


class TestContradiction:
    def test_no_previous_candidates_is_never_a_contradiction(self):
        flag, note = is_contradiction([], _cand("3924.10"))
        assert flag is False and note is None

    def test_same_chapter_is_not_a_contradiction(self):
        prev = [_cand("8452.90"), _cand("8708.99"), _cand("8487.90")]
        flag, note = is_contradiction(prev, _cand("8452.90"))
        assert flag is False and note is None

    def test_chapter_of_any_previous_candidate_counts(self):
        prev = [_cand("8452.90"), _cand("8708.99")]
        assert is_contradiction(prev, _cand("8708.10"))[0] is False

    def test_different_chapter_is_a_contradiction_with_note_naming_both_codes(self):
        prev = [_cand("9617.00")]
        flag, note = is_contradiction(prev, _cand("3924.10"))
        assert flag is True
        assert "9617.00" in note and "3924.10" in note
        assert "96" in note and "39" in note

    def test_no_new_top_candidate_is_not_a_contradiction(self):
        assert is_contradiction([_cand("9617.00")], None) == (False, None)


# --------------------------------------------------------------------------- feature 004: the CN-8 inputs
import agent.routing as R  # noqa: E402  (module access keeps the feature 001 tests collectable while these are red)

MOTOR = "whether the toy cars incorporate a motor"


class TestCn8Routing:
    """Data-model §6: the open CN-8 question and a failed CN-8 step are routing inputs."""

    def test_an_open_question_routes_to_ask_shipper(self):
        route, reason = R.route_line(FlagKind.ok, 95, "checked", False, T, F, cn8_question=MOTOR)
        assert route == Route.ask_shipper
        assert reason == f"the CN-8 depends on {MOTOR}, which the description does not state — ask the shipper"

    @pytest.mark.parametrize("conf,ever", [(70, False), (95, True)])
    def test_the_question_also_applies_below_the_threshold_and_after_a_flag(self, conf, ever):
        assert R.route_line(FlagKind.ok, conf, "checked", ever, T, F, cn8_question=MOTOR)[0] == Route.ask_shipper

    def test_a_failed_step_routes_to_review(self):
        route, reason = R.route_line(FlagKind.ok, 95, "checked", False, T, F, cn8_error="invalid output after one retry")
        assert route == Route.review
        assert reason == "CN-8 step failed: invalid output after one retry — needs a human look"

    @pytest.mark.parametrize("conf,ever", [(70, False), (95, True)])
    def test_the_failure_also_applies_below_the_threshold_and_after_a_flag(self, conf, ever):
        assert R.route_line(FlagKind.ok, conf, "checked", ever, T, F, cn8_error="timeout")[0] == Route.review

    @pytest.mark.parametrize("flag,conf,status", [(FlagKind.vague, 31, "checked"), (FlagKind.stop_word, 99, "checked"),
                                                  (FlagKind.ok, 95, "failed"), (FlagKind.ok, 95, "pending")])
    def test_neither_input_applies_to_failed_pending_or_flagged_lines(self, flag, conf, status):
        plain = R.route_line(flag, conf, status, False, T, F)
        assert R.route_line(flag, conf, status, False, T, F, cn8_question=MOTOR) == plain
        assert R.route_line(flag, conf, status, False, T, F, cn8_error="timeout") == plain

    @pytest.mark.parametrize("flag,conf,status,ever,expected", [
        (FlagKind.ok, 84, "checked", False, False), (FlagKind.ok, 85, "checked", False, True),
        (FlagKind.ok, 95, "checked", False, True), (FlagKind.ok, 95, "checked", True, False),
        (FlagKind.vague, 95, "checked", False, False), (FlagKind.stop_word, 95, "checked", False, False),
        (FlagKind.ok, 95, "failed", False, False), (FlagKind.ok, 95, "pending", False, False)])
    def test_hs6_auto_decided_is_feature_001s_auto_accept(self, flag, conf, status, ever, expected):
        assert R.hs6_auto_decided(flag, conf, status, ever, T, F) is expected
        assert expected is (R.route_line(flag, conf, status, ever, T, F)[0] == Route.auto_accept)

    @pytest.mark.parametrize("conf,single,expected", [(10, True, True), (85, False, True), (84, False, False),
                                                      (99, False, True)])
    def test_cn8_written_by_rule(self, conf, single, expected):
        assert R.cn8_written_by_rule(conf, T, single) is expected


class TestCn8ConfidenceSignal:
    """Iteration 2 of the CN-8 step (2026-10-23): evidence must be words of the line, an agreeing precedent is needed for
    85 and above, and a cited ruling at another CN-8 keeps the choice to confirm."""

    @pytest.mark.parametrize("evidence,expected", [
        ("bicycle frames", True), ("Bicycle  Frames", True), ("aluminium alloy; frames", True), ("自行车架", True),
        ("the goods are frames for bicycles", False), ("", False), ("   ", False), ("frames; carbon fibre", False)])
    def test_evidence_must_be_words_of_the_line(self, evidence, expected):
        assert R.evidence_in_line(evidence, "铝合金自行车架 / Aluminium alloy bicycle frames") is expected

    @pytest.mark.parametrize("conf,evidence,agrees,expected", [(95, True, True, 95), (95, True, False, 84),
                                                               (95, False, True, 84), (84, True, False, 84),
                                                               (70, True, False, 70)])
    def test_85_and_above_needs_evidence_and_an_agreeing_precedent(self, conf, evidence, agrees, expected):
        assert R.cn8_confidence(conf, evidence, agrees) == expected

    @pytest.mark.parametrize("cn8,code,expected", [("87149110", "8714911000", False), ("87149110", "8714913000", True),
                                                   ("87149110", None, False), (None, "8714913000", False)])
    def test_a_precedent_conflicts_when_its_cn_code_differs(self, cn8, code, expected):
        assert R.cn8_precedent_conflict(cn8, code) is expected

    def test_a_conflicting_precedent_is_never_written_by_rule(self):
        assert R.cn8_written_by_rule(98, T, False, precedent_conflict=True) is False
        assert R.cn8_written_by_rule(98, T, False) is True
        assert R.cn8_written_by_rule(10, T, True, precedent_conflict=True) is True   # a single line has nothing to choose
