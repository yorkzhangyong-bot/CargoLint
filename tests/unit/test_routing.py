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
    """Iteration 3 of the CN-8 step (2026-10-23): every word of the evidence must occur in the line, both sides
    normalised; only a cited ruling at another CN-8 keeps the choice to confirm, and no ruling leaves the threshold rule
    alone."""

    @pytest.mark.parametrize("evidence,expected", [
        ("bicycle frames", True), ("Bicycle  Frames", True), ("aluminium alloy; frames", True), ("自行车架", True),
        ("“Bicycle frames.”", True), ("aluminium-alloy bicycle", True),
        ("frames, bicycle", False),          # feature 006: a fragment is a phrase of the line, so word order counts
        ("aluminium-alloy frames", False),   # words of the line, but not one run of them (ratio 0.76)
        ("cycle frames", True),              # a run of words of the line at a ratio of 0.92 ("bicycle frames")
        ("the goods are frames for bicycles", False), ("", False), ("   ", False), ("…", False),
        ("frames; carbon fibre", False), ("碳纤维", False),
        ("Front forks", False)])   # a CN-8 label (8714 91 30), not words of the line
    def test_every_fragment_of_the_evidence_must_be_found_in_the_line(self, evidence, expected):
        assert R.evidence_in_line(evidence, "铝合金自行车架 / Aluminium alloy bicycle frames") is expected

    @pytest.mark.parametrize("evidence,line", [("99.9% Polyester", "Woven fabric of 99.9 % polyester, dyed"),
                                               ("100 % cotton", "T-shirts (100%cotton)"),
                                               ("toy cars", "塑料玩具车 / Plastic toy cars.")])
    def test_case_punctuation_and_spacing_are_normalised_on_both_sides(self, evidence, line):
        assert R.evidence_in_line(evidence, line) is True

    @pytest.mark.parametrize("evidence,line,rule", [
        ("vetement pour bebes", "Accessoire du vêtement pour bébés", "exact"),             # accents stripped
        ("to be worn when doing sports", "Sports bra\nTo be worn\nwhen doing sports.", "exact"),   # line breaks
        ("aluminium alloy; bicycle frames", "Aluminium alloy bicycle frames", "exact"),
        ("Schnallenverschluss", "Riemen aus Kunststoff mit Schnallen-\nverschluss", "fuzzy"),   # 0.97
        ("gants de protection", "gant de protection pour tous métiers", "fuzzy"),             # 0.97
        ("aluminium alloy; cycle frames", "Aluminium alloy bicycle frames", "fuzzy"),         # one fragment needs it
        ("tin", "tinted glass panels", None),        # a short word inside a longer one is no match
        ("bicycle frames; carbon fibre", "Aluminium alloy bicycle frames", None)])   # every fragment must pass
    def test_feature_006_names_the_rule_that_accepts_a_quote(self, evidence, line, rule):
        assert R.evidence_match(evidence, line) == rule
        assert R.evidence_in_line(evidence, line) is (rule is not None)

    def test_feature_006_a_quote_from_a_cn8_label_or_a_ruling_is_still_rejected(self):
        line = "Seam free wireless sports bra\nTo be worn when doing sports and exercise.\nMade of elastic knitted nylon fabric"
        assert R.evidence_match("Of a weight, per garment, not exceeding 1 kg", line) is None        # a CN-8 label
        assert R.evidence_match("It is made of knitted synthetic fabric", line) is None             # another ruling
        assert R.evidence_match("destinado a un uso deportivo", line) is None                       # a ruling in Spanish
        monitor = "14” portable LCD colour monitor. The monitor does not have TV signal reception capability."
        assert R.evidence_match("Of a kind solely or principally used in an automatic data-processing system "
                                "of heading 8471", monitor) is None                                  # a CN-8 label

    @pytest.mark.parametrize("cn8,code,expected", [("87149110", "8714911000", False), ("87149110", "8714913000", True),
                                                   ("87149110", None, False), (None, "8714913000", False)])
    def test_a_precedent_conflicts_when_its_cn_code_differs(self, cn8, code, expected):
        assert R.cn8_precedent_conflict(cn8, code) is expected

    def test_a_conflicting_precedent_is_never_written_by_rule(self):
        assert R.cn8_written_by_rule(98, T, False, precedent_conflict=True) is False
        assert R.cn8_written_by_rule(98, T, False) is True
        assert R.cn8_written_by_rule(10, T, True, precedent_conflict=True) is True   # a single line has nothing to choose


class TestCn8RulingVote:
    """Feature 006, constitution 1.4.0: the CN-8 is written by rule when the model's CN-8 is the majority of the nearest
    eligible EBTI rulings, each counted once, with a share at or above CN8_VOTE_SHARE; with no eligible ruling the
    model estimate against the threshold decides, as before."""

    def test_the_majority_its_share_and_the_countries_of_every_ruling(self):
        vote = R.cn8_ruling_vote([("94032080", "XI"), ("94032020", "DE"), ("94032080", "IE"), ("94032080", "FR"),
                                  ("94032020", "FR")], "94032080")
        assert (vote.majority_cn8, vote.majority_share, vote.model_is_majority, vote.agrees) == ("94032080", 0.6, True, True)
        assert vote.competing == [("94032080", ["XI", "IE", "FR"]), ("94032020", ["DE", "FR"])]   # most votes first

    def test_only_the_k_nearest_vote(self):
        nearest = [("A0000000", "DE")] * 2 + [("B0000000", "FR")] * 3 + [("A0000000", "DE")] * 5
        assert R.cn8_ruling_vote(nearest, "B0000000").majority_cn8 == "B0000000"     # the first five: 3 B, 2 A
        assert R.cn8_ruling_vote(nearest, "B0000000", k=10).majority_cn8 == "A0000000"

    def test_at_exactly_the_share_the_vote_agrees(self):
        vote = R.cn8_ruling_vote([("A0000000", "DE"), ("A0000000", "FR"), ("B0000000", "IE"), ("C0000000", "XI")], "A0000000")
        assert (vote.majority_share, vote.agrees) == (0.5, True)

    def test_below_the_share_the_majority_is_not_enough(self):
        vote = R.cn8_ruling_vote([("A0000000", "DE"), ("A0000000", "FR"), ("B0000000", "IE"), ("C0000000", "XI"),
                                  ("D0000000", "PL")], "A0000000")
        assert (vote.majority_cn8, vote.majority_share, vote.model_is_majority, vote.agrees) == ("A0000000", 0.4, True, False)

    def test_a_tie_has_no_majority(self):
        vote = R.cn8_ruling_vote([("A0000000", "DE"), ("B0000000", "FR")], "A0000000")
        assert (vote.majority_cn8, vote.model_is_majority, vote.agrees) == (None, False, False)

    def test_a_model_cn8_outside_the_majority_disagrees(self):
        vote = R.cn8_ruling_vote([("A0000000", "DE"), ("A0000000", "FR"), ("B0000000", "IE")], "B0000000")
        assert (vote.majority_cn8, vote.model_is_majority, vote.agrees) == ("A0000000", False, False)

    def test_no_eligible_ruling_is_no_vote(self):
        assert R.cn8_ruling_vote([], "A0000000") is None

    @pytest.mark.parametrize("vote_input,model,conf,expected", [
        ([("A0000000", "DE"), ("A0000000", "FR")], "A0000000", 40, (True, "vote_agrees")),          # confidence is no input
        ([("B0000000", "DE"), ("B0000000", "FR")], "A0000000", 99, (False, "vote_disagrees")),
        ([("A0000000", "DE"), ("B0000000", "FR")], "A0000000", 99, (False, "vote_tie")),
        ([("A0000000", "DE"), ("A0000000", "FR"), ("B0000000", "IE"), ("C0000000", "XI"), ("D0000000", "PL")],
         "A0000000", 99, (False, "vote_share_low")),
        ([], "A0000000", 85, (True, "no_rulings")),                                                  # the fallback at the threshold
        ([], "A0000000", 84, (False, "no_rulings"))])
    def test_the_gate(self, vote_input, model, conf, expected):
        written, gate = R.cn8_gate(conf, T, False, vote=R.cn8_ruling_vote(vote_input, model))
        assert (written, gate.value) == expected
        assert R.cn8_written_by_rule(conf, T, False, vote=R.cn8_ruling_vote(vote_input, model)) is expected[0]

    def test_a_single_line_and_a_conflicting_citation_come_before_the_vote(self):
        agree = R.cn8_ruling_vote([("A0000000", "DE")] * 5, "A0000000")
        assert R.cn8_gate(10, T, True, precedent_conflict=True, vote=agree)[1].value == "single_line"
        assert R.cn8_gate(99, T, False, precedent_conflict=True, vote=agree) == (False, R.Cn8Gate.precedent_conflict)
