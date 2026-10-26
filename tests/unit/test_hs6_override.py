"""Feature 008: the precedent override at the HS-6 (contracts/override.md). With the switch on, a shipment's
hs6_override_min, at least that many of the nearest eligible rulings at the model's candidate 2 or 3 decide that
candidate and auto-accept it, with "rulings overrode the model: N of M agree on <code>"; 3 of 5, or a majority outside
the model's candidates, stays review. With the switch off every gate case is feature 006's."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

import agent.routing as R
from agent.config import HS6_VOTE_K, OVERRIDE_MIN
from agent.llm import StructuredCaller
from agent.schemas import (Actor, Candidate, ChangeKind, Classification, CreatedBy, Decision, DecisionRoute, Flag, FlagKind,
                           Hs6Gate, LineStatus, LineVersion, Route, Shipment)
from agent.store import LineStore
from tests.fakes import FakeRawClient
from tests.ui import harness as h

pytestmark = pytest.mark.unit

T, F = 85, 50
TOP3 = ["9503.00", "3926.90", "4202.92"]          # the model's candidates, top first


def vote(*nearest, candidates=TOP3):
    return R.hs6_ruling_vote(list(nearest), candidates)


def at(code, *countries):
    return [(code, country) for country in countries]


FIVE_AT_2 = vote(*at("3926.90", "IE", "DE", "DE", "FR", "NL"))
FOUR_AT_2 = vote(("3926.90", "IE"), ("3926.90", "DE"), ("9503.00", "NL"), ("3926.90", "DE"), ("3926.90", "FR"))
FIVE_AT_3 = vote(*at("4202.92", "IE", "DE", "FR", "NL", "PL"))
FOUR_OF_FOUR = vote(*at("3926.90", "IE", "DE", "FR", "NL"))                       # only four rulings are eligible
THREE_AT_2 = vote(*at("3926.90", "IE", "DE", "FR"), ("9503.00", "NL"), ("4202.92", "PL"))
FOUR_OUTSIDE = vote(*at("9617.00", "IE", "DE", "FR", "NL"), ("9503.00", "PL"))    # a code the model did not propose
TIE = vote(("9503.00", "IE"), ("3926.90", "DE"))
SPREAD = vote(("9503.00", "IE"), ("9503.00", "DE"), ("3926.90", "FR"), ("4202.92", "NL"), ("9617.00", "PL"))
AGREE = vote(*at("9503.00", "IE", "DE", "NL"), ("3926.90", "FR"), ("4202.92", "PL"))

OVERRIDE = (True, Hs6Gate.vote_override)
DISAGREES = (False, Hs6Gate.vote_disagrees)
ON = {"hs6_override_min": 4}


def cands(*codes):
    return [Candidate(code=code, confidence=90 - 30 * i) for i, code in enumerate(codes)]


class TestGate:
    @pytest.mark.parametrize("v, on, off", [
        (FIVE_AT_2, OVERRIDE, DISAGREES),
        (FOUR_AT_2, OVERRIDE, DISAGREES),                     # exactly OVERRIDE_MIN overrides
        (FIVE_AT_3, OVERRIDE, DISAGREES),
        (FOUR_OF_FOUR, OVERRIDE, DISAGREES),
        (THREE_AT_2, DISAGREES, DISAGREES),                   # one fewer does not
        (FOUR_OUTSIDE, DISAGREES, DISAGREES),                 # never a code the model did not propose
        (TIE, (False, Hs6Gate.vote_tie), (False, Hs6Gate.vote_tie)),
        (SPREAD, (False, Hs6Gate.vote_share_low), (False, Hs6Gate.vote_share_low)),
        (AGREE, (True, Hs6Gate.vote_agrees), (True, Hs6Gate.vote_agrees))])
    def test_the_gate_with_the_switch_on_and_off(self, v, on, off):
        assert R.hs6_gate(40, T, v, override_min=4) == on                    # the model estimate is no input
        assert R.hs6_gate(40, T, v, override_min=None) == R.hs6_gate(40, T, v) == off

    @pytest.mark.parametrize("confidence, passed", [(85, True), (84, False)])
    def test_without_an_eligible_ruling_the_threshold_decides_as_before(self, confidence, passed):
        assert R.hs6_gate(confidence, T, None, override_min=4) == R.hs6_gate(confidence, T, None) == \
            (passed, Hs6Gate.no_rulings)

    def test_the_minimum_counts_at_exactly_its_value(self):
        assert OVERRIDE_MIN == 5                                              # FR-007, T027: the default, 5 of 5
        assert R.hs6_gate(99, T, FIVE_AT_2, override_min=5) == OVERRIDE
        assert R.hs6_gate(99, T, FOUR_AT_2, override_min=5) == DISAGREES


class TestRoute:
    @pytest.mark.parametrize("v, reason", [
        (FOUR_AT_2, "rulings overrode the model: 4 of 5 agree on 3926.90"),
        (FIVE_AT_3, "rulings overrode the model: 5 of 5 agree on 4202.92"),
        (FOUR_OF_FOUR, "rulings overrode the model: 4 of 4 agree on 3926.90")])
    def test_an_override_auto_accepts_with_the_note(self, v, reason):
        assert R.route_line(FlagKind.ok, 40, "checked", False, T, F, hs6_vote=v, **ON) == (Route.auto_accept, reason)

    def test_an_updated_line_still_needs_the_clerks_click(self):
        assert R.route_line(FlagKind.ok, 40, "checked", True, T, F, hs6_vote=FOUR_AT_2, **ON) == (
            Route.review, "ready to accept — rulings overrode the model: 4 of 5 agree on 3926.90, but the line was "
                          "flagged or updated before; click Accept to confirm")

    def test_with_the_switch_off_the_line_goes_to_review_as_today(self):
        today = (Route.review, "the nearest EBTI rulings point to 3926.90 (4 of 5: IE, DE, DE, FR), the model's "
                               "candidate 2 — needs a human look")
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, hs6_vote=FOUR_AT_2) == today
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, hs6_vote=FOUR_AT_2, hs6_override_min=None) == today

    def test_three_of_five_stays_review_and_names_the_candidate(self):
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, hs6_vote=THREE_AT_2, **ON) == (
            Route.review, "the nearest EBTI rulings point to 3926.90 (3 of 5: IE, DE, FR), the model's candidate 2 — "
                          "needs a human look")

    @pytest.mark.parametrize("kind, confidence", [(FlagKind.stop_word, 99), (FlagKind.vague, 55), (FlagKind.vague, 40)])
    def test_a_flagged_line_routes_as_today_and_is_never_auto_accepted(self, kind, confidence):
        on = R.route_line(kind, confidence, "checked", False, T, F, hs6_vote=FIVE_AT_2, **ON)
        assert on == R.route_line(kind, confidence, "checked", False, T, F, hs6_vote=FIVE_AT_2)
        assert on[0] != Route.auto_accept

    def test_failures_and_the_cn8_step_come_before_the_override(self):
        both = {"hs6_vote": FIVE_AT_2, **ON}
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, cn8_question="the material", **both)[0] == \
            Route.ask_shipper
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, cn8_error="boom", **both)[0] == Route.review
        assert R.route_line(FlagKind.ok, 0, "checked", False, T, F, **both)[0] == Route.review    # no valid candidate
        assert R.route_line(None, None, "failed", False, T, F, **both)[0] == Route.review

    def test_the_hs6_is_decided_by_the_override_only_with_the_switch_on(self):
        assert R.hs6_auto_decided(FlagKind.ok, 40, "checked", False, T, F, hs6_vote=FOUR_AT_2, **ON) is True
        assert R.hs6_auto_decided(FlagKind.ok, 40, "checked", False, T, F, hs6_vote=FOUR_AT_2) is False
        assert R.hs6_auto_decided(FlagKind.ok, 40, "checked", True, T, F, hs6_vote=FOUR_AT_2, **ON) is False


class TestChoice:
    def test_the_override_chooses_the_supported_candidate_and_any_other_gate_the_top(self):
        three = cands(*TOP3)
        assert R.hs6_choice(three, FOUR_AT_2, Hs6Gate.vote_override) == (2, "3926.90")
        assert R.hs6_choice(three, FIVE_AT_3, Hs6Gate.vote_override) == (3, "4202.92")
        assert R.hs6_choice(three, FOUR_AT_2, Hs6Gate.vote_disagrees) == (1, "9503.00")     # the switch off
        assert R.hs6_choice(three, AGREE, Hs6Gate.vote_agrees) == (1, "9503.00")
        assert R.hs6_choice(three, None, Hs6Gate.no_rulings) == (1, "9503.00")
        assert R.hs6_choice([], None, None) == (None, None)

    def test_with_two_candidates_only_those_can_be_chosen(self):
        two = TOP3[:2]
        at_2 = vote(*at("3926.90", "IE", "DE", "FR", "NL"), ("9503.00", "PL"), candidates=two)
        assert R.hs6_gate(99, T, at_2, override_min=4) == OVERRIDE
        assert R.hs6_choice(cands(*two), at_2, Hs6Gate.vote_override) == (2, "3926.90")
        third = vote(*at("4202.92", "IE", "DE", "FR", "NL"), ("9503.00", "PL"), candidates=two)   # the model did not
        assert (third.candidate, R.hs6_gate(99, T, third, override_min=4)) == (None, DISAGREES)  # return it


class TestShipment:
    @pytest.mark.parametrize("value", [None, 1, 4, HS6_VOTE_K])
    def test_the_switch_is_none_or_one_to_k_rulings(self, value):
        assert Shipment(id="s", hs6_override_min=value).hs6_override_min == value

    @pytest.mark.parametrize("value", [0, HS6_VOTE_K + 1])
    def test_a_minimum_outside_one_to_k_is_rejected(self, value):
        with pytest.raises(ValidationError):
            Shipment(id="s", hs6_override_min=value)

    def test_the_switch_is_off_by_default(self):
        assert Shipment(id="s").hs6_override_min is None


# --------------------------------------------------------------------------- the store
LAMP = ["8543.70", "9405.21", "9403.60"]          # a desk lamp's candidates: the rulings sit at candidate 2
LAMP_TEXT = "LED desk lamp, USB powered"


def lamp_vote(at_2, candidates=LAMP):
    """`at_2` of the 5 nearest rulings at candidate 2, the rest at the top candidate."""
    countries = ["IE", "DE", "DE", "FR", "NL"]
    return R.hs6_ruling_vote(at("9405.21", *countries[:at_2]) + at("8543.70", *countries[at_2:]), candidates)


def lamp_cands(store, codes=LAMP, confidences=(90, 60, 20)):
    return [Candidate(code=code, subheading_text=store.index.subheading_text(code), confidence=conf,
                      rationale=f"matches {code}") for code, conf in zip(codes, confidences)]


def add_voted(store, kb, hs6_vote, codes=LAMP, text=LAMP_TEXT):
    """A checked line whose candidates are `codes`, with the vote classify_one stored."""
    n = h._clear(store, kb, text)
    store.update_classification(n, Classification(line_no=n, candidates=lamp_cands(store, codes), status=LineStatus.checked,
                                                  hs6_vote=hs6_vote))
    return n


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


class TestStore:
    @pytest.mark.parametrize("override_min, at_2, route, decided", [
        (4, 4, Route.auto_accept, ("9405.21", "auto")),
        (4, 5, Route.auto_accept, ("9405.21", "auto")),
        (None, 4, Route.review, (None, None)),               # the switch off
        (4, 3, Route.review, (None, None))])                 # below the minimum
    def test_the_switch_and_the_minimum(self, kb, override_min, at_2, route, decided):
        store = h._store(hs6_override_min=override_min)
        line = store.get_line(add_voted(store, kb, lamp_vote(at_2)))
        assert (line.current.computed_route, store.decided_code(line)) == (route, decided)

    def test_the_route_reason_is_the_note(self, kb):
        store = h._store(hs6_override_min=4)
        line = store.get_line(add_voted(store, kb, lamp_vote(4)))
        assert (line.current.hs6_gate, line.current.route_reason) == (
            Hs6Gate.vote_override, "rulings overrode the model: 4 of 5 agree on 9405.21")

    @pytest.mark.parametrize("text, route", [("Gift", Route.ask_shipper), ("Mixed household articles", Route.review)])
    def test_a_flagged_line_is_never_auto_accepted(self, kb, text, route):
        store = h._store(hs6_override_min=4)
        line = store.get_line(add_voted(store, kb, lamp_vote(5), text=text))
        assert (line.current.computed_route, store.decided_code(line)) == (route, (None, None))

    def test_a_line_flagged_before_is_ready_to_accept_the_chosen_candidate(self, kb):
        store = h._store(hs6_override_min=4)
        n = h._clear(store, kb, "Gift")                                            # a firm stop word: flagged
        store.add_version(n, LineVersion(created_by=CreatedBy.shipper_reply, text_en=LAMP_TEXT, flag=Flag(kind=FlagKind.ok),
                                         status=LineStatus.checked, candidates=lamp_cands(store), hs6_vote=lamp_vote(4)))
        line = store.get_line(n)
        assert (line.current.computed_route, line.current.hs6_gate) == (Route.review, Hs6Gate.vote_override)
        assert store.ready_to_accept(line) is True and store.decided_code(line) == (None, None)

    def test_the_cn8_step_runs_on_the_chosen_candidate(self, kb):
        from tools.classify_cn8 import run_cn8_step

        store = h._store(hs6_override_min=4)
        n = add_voted(store, kb, lamp_vote(4))
        fake = FakeRawClient(recorded={"Cn8Out": {LAMP_TEXT: {
            "cn8": "94052140", "confidence": 90, "deciding_attribute": "the kind of lamp", "attribute_visible": True,
            "evidence": "LED desk lamp", "rationale": "an electric desk lamp", "precedent": None}}})
        run_cn8_step(store, kb, StructuredCaller(raw=fake, model_name="fake", prices=None, usd_eur=0.92), [n])
        v = store.get_line(n).current
        assert (v.cn8.hs6, v.cn8.cn8) == ("9405.21", "94052140")
        assert [c.cn8 for c in v.candidates] == [None, "94052140", None]
        assert "94052140" in fake.calls[-1]["user"] and "85437000" not in fake.calls[-1]["user"]

    def test_the_export_gives_the_chosen_candidate_in_the_same_columns(self, kb):
        store = h._store(hs6_override_min=4)
        n = add_voted(store, kb, lamp_vote(4))
        row = store.export_rows()[n - 1]
        assert (row["decided_code"], row["decided_how"], row["route"]) == ("9405.21", "auto", "auto_accept")
        assert list(row) == LineStore.CSV_COLUMNS

    def test_a_threshold_move_leaves_the_override(self, kb):
        store = h._store(hs6_override_min=4)
        n = add_voted(store, kb, lamp_vote(4))
        for threshold in (60, 99):
            store.set_threshold(threshold)
            line = store.get_line(n)
            assert (line.current.computed_route, store.decided_code(line)) == (Route.auto_accept, ("9405.21", "auto"))

    def test_with_two_candidates_the_second_is_decided(self, kb):
        store = h._store(hs6_override_min=4)
        line = store.get_line(add_voted(store, kb, lamp_vote(4, candidates=LAMP[:2]), codes=LAMP[:2]))
        assert store.decided_code(line) == ("9405.21", "auto")

    def test_a_shipment_the_file_parse_opens_again_keeps_the_switch(self, kb):
        from tools.common import ToolContext, set_context
        from tools.parse_packing_list import parse_packing_list_tool

        store = h._store(hs6_override_min=4)
        h._add(store, "Ceramic coffee mugs")                       # the shipment has lines, so the parse opens a new one
        ref = store.register_file(b"description,qty\nWooden chopsticks,10\n", "inv.csv")
        set_context(ToolContext(store=store, kb=kb, client=h.fake_client_caller()))
        try:
            parse_packing_list_tool.invoke({"file_ref": ref})
        finally:
            set_context(None)
        assert [line.current.text_en for line in store.lines] == ["Wooden chopsticks"]
        assert store.shipment.hs6_override_min == 4


def entries(store, n, change):
    return [r for r in store.shipment.audit if r.line_no == n and r.change == change]


class TestAudit:
    def test_an_override_writes_its_route_and_its_decided_code_once(self, kb):
        store = h._store(hs6_override_min=4)
        n = add_voted(store, kb, lamp_vote(4))
        store.set_threshold(80)                                            # a later recompute writes nothing again
        note = "rulings overrode the model: 4 of 5 agree on 9405.21"
        assert [(r.new, r.actor) for r in entries(store, n, ChangeKind.route_computed) if r.note == note] == \
            [("auto_accept", Actor.routing_rule)]
        assert [(r.actor, r.previous, r.new, r.note) for r in entries(store, n, ChangeKind.code_decided)] == [
            (Actor.routing_rule, "8543.70", "9405.21", note + "; candidate 2 chosen")]

    def test_no_override_no_decided_code_entry(self, kb):
        for override_min, at_2 in ((None, 4), (4, 3)):
            store = h._store(hs6_override_min=override_min)
            assert entries(store, add_voted(store, kb, lamp_vote(at_2)), ChangeKind.code_decided) == []

    def test_a_clerks_change_records_the_chosen_candidate_as_the_previous_code(self, kb):
        store = h._store(hs6_override_min=4)
        n = add_voted(store, kb, lamp_vote(4))
        store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code="8543.70"))
        assert store.decided_code(store.get_line(n)) == ("8543.70", "top")
        assert [(r.previous, r.new) for r in entries(store, n, ChangeKind.code_decided) if r.actor == Actor.clerk] == \
            [("9405.21", "8543.70")]

    def test_without_an_override_the_previous_code_is_the_top_candidate_as_before(self, kb):
        store = h._store(hs6_override_min=4)
        agreed = add_voted(store, kb, R.hs6_ruling_vote(at("8543.70", "IE", "DE", "FR"), LAMP))   # auto-accepted, top
        review = add_voted(store, kb, lamp_vote(3))                                                 # nothing decided
        for n in (agreed, review):
            store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code="9403.60"))
            assert [r.previous for r in entries(store, n, ChangeKind.code_decided)] == ["8543.70"]
