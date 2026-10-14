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
