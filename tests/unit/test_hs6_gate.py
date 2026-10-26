"""Feature 006: HS-6 auto-accept gated by the vote of the 5 nearest eligible EBTI rulings, as the CN-8 is: the vote and
the gate (agent/routing.py), the rulings that vote and the similarity floor (tools/classify_hs6.hs6_voters), the store's
route, gate reason and audit note, and the clerk's texts. With no eligible ruling the threshold decides, as before."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import agent.routing as R
from agent.config import HS6_VOTE_MIN_SIMILARITY
from agent.schemas import (Candidate, ChangeKind, Classification, CreatedBy, Flag, FlagKind, Hs6Gate, LineStatus,
                           LineVersion, Route)
from rag.bti import BTIStore
from tests.ui import harness as h
from tools.classify_hs6 import hs6_voters
from ui import view

pytestmark = pytest.mark.unit

T, F = 85, 50
TOP3 = ["3926.90", "4202.92", "4202.12"]          # the model's candidates, top first


def vote(*nearest, candidates=TOP3):
    return R.hs6_ruling_vote(list(nearest), candidates)


AGREE = vote(("3926.90", "IE"), ("3926.90", "DE"), ("4202.92", "FR"), ("3926.90", "NL"), ("4202.12", "IE"))   # 3 of 5
FOR_2ND = vote(("4202.92", "IE"), ("4202.92", "DE"), ("4202.92", "FR"), ("3926.90", "NL"), ("3926.90", "IE"))
TIE = vote(("3926.90", "IE"), ("4202.92", "DE"))
SPREAD = vote(("3926.90", "IE"), ("3926.90", "DE"), ("4202.92", "FR"), ("4202.12", "NL"), ("9503.00", "PL"))


class TestVote:
    def test_the_majority_its_share_and_the_countries_of_every_ruling(self):
        assert (AGREE.majority, AGREE.majority_share, AGREE.model_is_majority, AGREE.agrees, AGREE.candidate) == \
            ("3926.90", 0.6, True, True, None)
        assert AGREE.competing == [("3926.90", ["IE", "DE", "NL"]), ("4202.92", ["FR"]), ("4202.12", ["IE"])]

    def test_only_the_five_nearest_vote(self):
        nearest = [("4202.92", "IE")] * 2 + [("3926.90", "DE")] * 3 + [("4202.92", "FR")] * 5
        assert R.hs6_ruling_vote(nearest, TOP3).majority == "3926.90"

    def test_exactly_the_share_agrees_and_a_tie_has_no_majority(self):
        assert vote(("3926.90", "IE"), ("3926.90", "DE"), ("4202.92", "FR"), ("4202.12", "NL")).agrees is True
        assert (TIE.majority, TIE.agrees, TIE.candidate) == (None, False, None)
        assert (SPREAD.majority, SPREAD.majority_share, SPREAD.agrees) == ("3926.90", 0.4, False)

    @pytest.mark.parametrize("majority, candidate", [("4202.92", 2), ("4202.12", 3), ("3926.90", None), ("9503.00", None)])
    def test_the_candidate_the_precedents_support(self, majority, candidate):
        v = vote(*([(majority, "IE")] * 3 + [("8543.70", "DE")] * 2))
        assert (v.majority, v.candidate) == (majority, candidate)

    def test_no_ruling_is_no_vote(self):
        assert R.hs6_ruling_vote([], TOP3) is None

    def test_the_cn8_vote_is_the_same_vote(self):
        v = R.cn8_ruling_vote([("94032080", "XI"), ("94032020", "DE"), ("94032080", "IE")], "94032080")
        assert v.majority == v.majority_cn8 == "94032080" and v.agrees


class TestGate:
    @pytest.mark.parametrize("v, conf, expected", [
        (AGREE, 40, (True, Hs6Gate.vote_agrees)),              # the model estimate is no input
        (FOR_2ND, 99, (False, Hs6Gate.vote_disagrees)),
        (TIE, 99, (False, Hs6Gate.vote_tie)),
        (SPREAD, 99, (False, Hs6Gate.vote_share_low)),
        (None, 85, (True, Hs6Gate.no_rulings)),                # no eligible ruling: the threshold, at it counts
        (None, 84, (False, Hs6Gate.no_rulings))])
    def test_the_gate(self, v, conf, expected):
        assert R.hs6_gate(conf, T, v) == expected

    def test_an_agreeing_vote_auto_accepts_whatever_the_estimate(self):
        assert R.route_line(FlagKind.ok, 40, "checked", False, T, F, hs6_vote=AGREE) == \
            (Route.auto_accept, "3 of 5 nearest EBTI rulings at 3926.90 (IE, DE, NL)")

    @pytest.mark.parametrize("v, reason", [
        (FOR_2ND, "the nearest EBTI rulings point to 4202.92 (3 of 5: IE, DE, FR), the model's candidate 2"),
        (vote(*[("9503.00", "PL")] * 3), "the nearest EBTI rulings point to 9503.00 (3 of 3: PL, PL, PL)"),
        (TIE, "the nearest EBTI rulings are split: 3926.90 (IE), 4202.92 (DE)"),
        (SPREAD, "only 2 of 5 nearest EBTI rulings at 3926.90")])
    def test_a_vote_that_does_not_agree_keeps_a_confident_line_for_the_clerk(self, v, reason):
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, hs6_vote=v) == (Route.review, reason + " — needs a human look")

    def test_an_updated_line_still_needs_the_clerks_click(self):
        route, reason = R.route_line(FlagKind.ok, 40, "checked", True, T, F, hs6_vote=AGREE)
        assert route == Route.review
        assert reason == ("ready to accept — 3 of 5 nearest EBTI rulings at 3926.90 (IE, DE, NL), but the line was flagged "
                          "or updated before; click Accept to confirm")

    def test_flags_failures_and_the_cn8_step_come_before_the_vote(self):
        assert R.route_line(FlagKind.stop_word, 99, "checked", False, T, F, hs6_vote=AGREE)[0] == Route.ask_shipper
        assert R.route_line(FlagKind.vague, 55, "checked", False, T, F, hs6_vote=AGREE)[0] == Route.review
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, cn8_question="the material", hs6_vote=AGREE)[0] == \
            Route.ask_shipper
        assert R.route_line(FlagKind.ok, 99, "checked", False, T, F, cn8_error="boom", hs6_vote=AGREE)[0] == Route.review
        assert R.route_line(FlagKind.ok, 0, "checked", False, T, F, hs6_vote=AGREE)[0] == Route.review   # no valid candidate
        assert R.route_line(None, None, LineStatus.failed, False, T, F, hs6_vote=AGREE)[0] == Route.review

    def test_without_an_eligible_ruling_the_threshold_decides_as_before(self):
        assert R.route_line(FlagKind.ok, 85, "checked", False, T, F) == (Route.auto_accept, "confidence 85 at or above the threshold 85")
        assert R.route_line(FlagKind.ok, 84, "checked", False, T, F, hs6_vote=None) == (Route.review, "below threshold (84 < 85)")

    def test_the_hs6_is_decided_by_the_vote(self):
        assert R.hs6_auto_decided(FlagKind.ok, 40, "checked", False, T, F, hs6_vote=AGREE) is True
        assert R.hs6_auto_decided(FlagKind.ok, 99, "checked", False, T, F, hs6_vote=FOR_2ND) is False


def ruling(reference, code, member_state="DE", valid_to="2027-12-31"):
    return {"reference": reference, "code": code, "member_state": member_state, "valid_from": "2025-01-01",
            "valid_to": valid_to}


RULINGS = BTIStore([ruling("A", "3926.90", "IE"), ruling("B", "4202.92", "FR"), ruling("C", "4202.12"),
                    ruling("OWN", "3926.90", "NL"), ruling("OLD", "3926.90", valid_to="2024-12-31"), ruling("GONE", "9999.99")])
INDEX = SimpleNamespace(get=lambda code: object() if code in ("3926.90", "4202.92", "4202.12") else None)
AS_OF = date(2026, 10, 23)


class TestVoters:
    def test_eligible_rulings_nearest_first_each_once_at_its_highest_similarity(self):
        hits = [[("bti:OWN", 0.97), ("bti:A", 0.90), ("bti:OLD", 0.88), ("bti:GONE", 0.86), ("bti:UNKNOWN", 0.55)],
                [("bti:B", 0.93), ("bti:C", 0.70), ("bti:A", 0.50)]]                  # a second query vector
        assert hs6_voters(hits, RULINGS, INDEX, AS_OF, exclude_refs=frozenset({"OWN"})) == [
            ("4202.92", "FR"), ("3926.90", "IE"), ("4202.12", "DE")]   # not the line's own, expired, unknown or uncoded ones
        assert hs6_voters(hits, RULINGS, INDEX, AS_OF)[0] == ("3926.90", "NL")        # nothing excluded: the product

    def test_a_ruling_below_the_similarity_floor_does_not_vote(self):
        hits = [[("bti:A", HS6_VOTE_MIN_SIMILARITY), ("bti:B", HS6_VOTE_MIN_SIMILARITY - 0.01)]]
        assert hs6_voters(hits, RULINGS, INDEX, AS_OF) == [("3926.90", "IE")]          # exactly the floor votes

    def test_with_every_ruling_below_the_floor_no_ruling_votes_and_the_threshold_decides(self):
        voters = hs6_voters([[("bti:A", 0.39), ("bti:B", 0.2)]], RULINGS, INDEX, AS_OF)
        assert voters == [] and R.hs6_ruling_vote(voters, TOP3) is None
        assert R.route_line(FlagKind.ok, 90, "checked", False, T, F, hs6_vote=None)[0] == Route.auto_accept


# --------------------------------------------------------------------------- the store and the clerk's texts
TOYS = ["9503.00", "9405.21", "8543.70"]
TOYS_AGREE = R.hs6_ruling_vote([("9503.00", "XI"), ("9503.00", "IE"), ("9503.00", "FR"), ("9405.21", "DE"),
                                ("9405.21", "FR")], TOYS)
TOYS_FOR_2ND = R.hs6_ruling_vote([("9405.21", "XI"), ("9405.21", "IE"), ("9405.21", "FR"), ("9503.00", "DE"),
                                  ("9503.00", "FR")], TOYS)


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


def add_voted(store, kb, confidences, hs6_vote, text="Plastic toy figures"):
    """A checked, unflagged line whose candidates are TOYS at `confidences`, with the vote classify_one stored."""
    n = h._clear(store, kb, text)
    cands = [Candidate(code=code, subheading_text=store.index.subheading_text(code), confidence=conf, rationale=f"matches {code}")
             for code, conf in zip(TOYS, confidences)]
    store.update_classification(n, Classification(line_no=n, candidates=cands, status=LineStatus.checked, hs6_vote=hs6_vote))
    return n


def voted_line(kb, confidences, hs6_vote):
    store = h._store()
    n = add_voted(store, kb, confidences, hs6_vote)
    return store, store.get_line(n)


def _note(store, line_no):
    return [r.note for r in store.shipment.audit if r.change == ChangeKind.route_computed and r.line_no == line_no][-1]


class TestStore:
    def test_an_agreeing_vote_auto_accepts_below_the_threshold_and_the_audit_says_why(self, kb):
        store, line = voted_line(kb, [60, 20], TOYS_AGREE)
        assert (line.current.computed_route, line.current.hs6_gate, line.current.hs6_vote) == \
            (Route.auto_accept, Hs6Gate.vote_agrees, TOYS_AGREE)
        assert store.decided_code(line) == ("9503.00", "auto")                    # the CN-8 step runs on it
        assert _note(store, line.line_no) == "3 of 5 nearest EBTI rulings at 9503.00 (XI, IE, FR)"

    def test_a_disagreeing_vote_keeps_a_confident_line_for_the_clerk(self, kb):
        store, line = voted_line(kb, [98, 20, 10], TOYS_FOR_2ND)
        assert (line.current.computed_route, line.current.hs6_gate) == (Route.review, Hs6Gate.vote_disagrees)
        assert store.decided_code(line) == (None, None)
        assert _note(store, line.line_no) == ("the nearest EBTI rulings point to 9405.21 (3 of 5: XI, IE, FR), the model's "
                                              "candidate 2 — needs a human look")

    def test_without_a_ruling_the_threshold_decides_and_only_those_lines_follow_it(self, kb):
        store = h._store()
        by_threshold = add_voted(store, kb, [90], None)
        by_vote = add_voted(store, kb, [60], TOYS_AGREE)
        assert store.get_line(by_threshold).current.hs6_gate == Hs6Gate.no_rulings
        store.set_threshold(95)
        assert store.get_line(by_threshold).current.computed_route == Route.review           # 90 < 95, no ruling voted
        assert store.get_line(by_vote).current.computed_route == Route.auto_accept           # the vote decided

    @pytest.mark.parametrize("confidence, hs6_vote, ready", [(60, TOYS_AGREE, True), (98, TOYS_FOR_2ND, False),
                                                             (90, None, True), (80, None, False)])
    def test_a_line_flagged_before_is_ready_to_accept_when_the_gate_passes(self, kb, confidence, hs6_vote, ready):
        store = h._store()
        n = h._clear(store, kb, "Gift")                                            # a firm stop word: flagged
        cands = [Candidate(code=code, subheading_text=store.index.subheading_text(code), confidence=conf, rationale="r")
                 for code, conf in zip(TOYS, [confidence, 20])]
        store.add_version(n, LineVersion(created_by=CreatedBy.shipper_reply, text_en="Plastic toy figures",
                                         flag=Flag(kind=FlagKind.ok), status=LineStatus.checked, candidates=cands,
                                         hs6_vote=hs6_vote))
        line = store.get_line(n)
        assert line.current.computed_route == Route.review and store.ready_to_accept(line) is ready

    def test_a_failed_classification_drops_the_vote(self, kb):
        store, line = voted_line(kb, [60, 20], TOYS_AGREE)
        store.update_classification(line.line_no, Classification(line_no=line.line_no, status=LineStatus.failed,
                                                                 error_reason="boom"))
        assert (store.get_line(line.line_no).current.hs6_vote, store.get_line(line.line_no).current.hs6_gate) == (None, None)


class TestTexts:
    def test_the_clerk_sees_which_candidate_the_precedents_support(self, kb):
        store, line = voted_line(kb, [98, 20, 10], TOYS_FOR_2ND)
        assert view.explain_a(store, line, "a_hs6")[1] == (
            "Rulings disagree: model 9503 00, nearest rulings 9405 21 (XI, IE, FR), 9503 00 (DE, FR). Precedents support "
            "candidate 2. TARIC runs after your pick.")

    @pytest.mark.parametrize("nearest, text", [
        ([("9405.21", "XI"), ("9503.00", "DE")],
         "Rulings split: model 9503 00, nearest rulings 9405 21 (XI), 9503 00 (DE). TARIC runs after your pick."),
        ([("9503.00", "XI"), ("9503.00", "IE"), ("9405.21", "DE"), ("8543.70", "FR"), ("9617.00", "PL")],
         "Rulings too spread: model 9503 00 has 2 of 5 nearest rulings; 9503 00 (XI, IE), 9405 21 (DE), 8543 70 (FR), "
         "9617 00 (PL). TARIC runs after your pick."),
        ([("9617.00", "PL")] * 3,
         "Rulings disagree: model 9503 00, nearest rulings 9617 00 (PL, PL, PL). TARIC runs after your pick.")])
    def test_the_reason_names_the_nearest_rulings_and_their_countries(self, kb, nearest, text):
        store, line = voted_line(kb, [98, 20, 10], R.hs6_ruling_vote(nearest, TOYS))
        assert view.explain_a(store, line, "a_hs6")[1] == text

    def test_an_hs6_the_vote_accepted_says_how_many_rulings_agree(self, kb):
        store, line = voted_line(kb, [60, 20], TOYS_AGREE)
        assert view.explain_a(store, line, "a_change")[0].startswith(
            "Decided: HS-6 9503 00, auto-accepted, 3 of 5 nearest rulings agree")

    def test_without_a_ruling_the_texts_are_as_before(self, kb):
        store, line = voted_line(kb, [58, 20], None)
        assert view.explain_a(store, line, "a_hs6")[1] == (
            "Top candidate leads (58 %) but is under the 85 % auto-accept threshold, so you decide. TARIC runs after your pick.")
