"""Feature 014a, the author's decision of 2026-11-19 (rule (a)): the HS-6 auto-accept is the unfiltered gate of
constitution 1.5.0 again, the 5 nearest eligible rulings over every indexed chapter; the vote of the candidates'
chapters can only send a line to review. When it has voters and does not agree on the code the gate would decide (the
top candidate, or the precedent override's candidate), the line goes to review; it never auto-accepts on its own. The
gate (agent/routing.py) and the store's route, gate and audit note.

Traceability: 014a/FR-011, 014a/FR-019."""
from __future__ import annotations

import pytest

import agent.routing as R
from agent.config import OVERRIDE_MIN
from agent.schemas import Candidate, ChangeKind, Classification, Hs6Gate, LineStatus, Route
from tests.ui import harness as h

pytestmark = pytest.mark.unit

T, F = 85, 50
TOP3 = ["3403.99", "2710.19", "3820.00"]


def vote(*nearest):
    return R.hs6_ruling_vote(list(nearest), TOP3)


AGREE = vote(("3403.99", "DE"), ("3403.99", "AT"), ("8419.89", "XI"), ("3403.99", "BE"), ("3403.19", "FR"))   # 3 of 5
MACHINES = vote(*[("8419.89", "XI")] * 5)                                                    # another code: disagrees
IN_CHAPTER_AGREE = vote(("3403.99", "DE"), ("3403.99", "AT"), ("3403.99", "BE"), ("3403.19", "FR"), ("3403.19", "LU"))
IN_CHAPTER_OTHER = vote(("3403.19", "FR"), ("3403.19", "LU"), ("3403.19", "NL"), ("3403.99", "DE"), ("3403.99", "AT"))
IN_CHAPTER_TIE = vote(("3403.99", "DE"), ("3403.19", "FR"))
IN_CHAPTER_LOW = vote(("3403.99", "DE"), ("3403.99", "AT"), ("3403.19", "FR"), ("2710.19", "NL"), ("3820.00", "IT"))
FOR_2ND = vote(*[("2710.19", "NL")] * OVERRIDE_MIN)                                         # all five at candidate 2
IN_CHAPTER_FOR_2ND = vote(*[("2710.19", "NL")] * 3, ("3403.99", "DE"), ("3403.99", "AT"))
IN_CHAPTER_FOR_TOP = vote(*[("3403.99", "DE")] * 3, ("2710.19", "NL"), ("2710.19", "NL"))


class TestGate:
    @pytest.mark.parametrize("scoped", [None, IN_CHAPTER_AGREE])
    def test_the_unfiltered_gate_decides_when_the_chapters_vote_agrees_or_has_no_voter(self, scoped):
        assert R.hs6_gate(60, T, AGREE, None, scoped) == (True, Hs6Gate.vote_agrees)

    @pytest.mark.parametrize("scoped", [IN_CHAPTER_OTHER, IN_CHAPTER_TIE, IN_CHAPTER_LOW])
    def test_the_chapters_vote_sends_an_agreeing_line_to_review_when_it_does_not_agree(self, scoped):
        assert R.hs6_gate(95, T, AGREE, None, scoped) == (False, Hs6Gate.scoped_veto)

    def test_the_chapters_vote_never_auto_accepts_on_its_own(self):
        assert R.hs6_gate(95, T, MACHINES, None, IN_CHAPTER_AGREE) == (False, Hs6Gate.vote_disagrees)

    def test_without_unfiltered_voters_the_threshold_decides_and_the_chapters_vote_can_stop_it(self):
        assert R.hs6_gate(90, T, None, None, None) == (True, Hs6Gate.no_rulings)
        assert R.hs6_gate(90, T, None, None, IN_CHAPTER_AGREE) == (True, Hs6Gate.no_rulings)
        assert R.hs6_gate(90, T, None, None, IN_CHAPTER_OTHER) == (False, Hs6Gate.scoped_veto)
        assert R.hs6_gate(80, T, None, None, IN_CHAPTER_AGREE) == (False, Hs6Gate.no_rulings)   # below the threshold

    def test_the_override_works_on_the_unfiltered_vote_and_the_chapters_vote_checks_its_candidate(self):
        assert R.hs6_gate(95, T, FOR_2ND, OVERRIDE_MIN, None) == (True, Hs6Gate.vote_override)
        assert R.hs6_gate(95, T, FOR_2ND, OVERRIDE_MIN, IN_CHAPTER_FOR_2ND) == (True, Hs6Gate.vote_override)
        assert R.hs6_gate(95, T, FOR_2ND, OVERRIDE_MIN, IN_CHAPTER_FOR_TOP) == (False, Hs6Gate.scoped_veto)
        assert R.hs6_gate(95, T, FOR_2ND, None, IN_CHAPTER_FOR_2ND) == (False, Hs6Gate.vote_disagrees)   # switch off


class TestRoute:
    def test_a_veto_routes_to_review_and_names_the_chapters_vote(self):
        route, reason = R.route_line("ok", 95, "checked", False, T, F, hs6_vote=AGREE, hs6_scoped_vote=IN_CHAPTER_OTHER)
        assert route == Route.review
        assert reason == ("the EBTI rulings of the candidates' chapters do not agree: 3 of 5 at 3403.19 (FR, LU, NL) — "
                          "needs a human look")

    def test_a_split_chapters_vote_is_named_as_split(self):
        route, reason = R.route_line("ok", 95, "checked", False, T, F, hs6_vote=AGREE, hs6_scoped_vote=IN_CHAPTER_TIE)
        assert route == Route.review
        assert reason == ("the EBTI rulings of the candidates' chapters are split: 3403.99 (DE), 3403.19 (FR) — needs a "
                          "human look")

    def test_without_a_veto_the_route_is_the_unfiltered_gates(self):
        assert R.route_line("ok", 60, "checked", False, T, F, hs6_vote=AGREE,
                            hs6_scoped_vote=IN_CHAPTER_AGREE)[0] == Route.auto_accept
        assert R.route_line("ok", 95, "checked", False, T, F, hs6_vote=MACHINES,
                            hs6_scoped_vote=IN_CHAPTER_AGREE)[0] == Route.review

    def test_the_hs6_is_not_decided_by_rule_after_a_veto(self):
        assert R.hs6_auto_decided("ok", 95, "checked", False, T, F, hs6_vote=AGREE, hs6_scoped_vote=IN_CHAPTER_OTHER) is False
        assert R.hs6_auto_decided("ok", 95, "checked", False, T, F, hs6_vote=AGREE, hs6_scoped_vote=None) is True


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


TOYS = ["9503.00", "9405.21", "8543.70"]                       # codes of the harness's nomenclature
TOYS_AGREE = R.hs6_ruling_vote([("9503.00", "XI"), ("9503.00", "IE"), ("9503.00", "FR"), ("9405.21", "DE"),
                                ("9405.21", "FR")], TOYS)
TOYS_IN_CHAPTER_OTHER = R.hs6_ruling_vote([("9405.21", "DE"), ("9405.21", "FR"), ("9405.21", "NL"), ("9503.00", "XI"),
                                           ("9503.00", "IE")], TOYS)


def add_voted(store, kb, hs6_vote, scoped_vote, confidences=(95, 40, 20)):
    """A checked, unflagged line whose candidates are TOYS, with the two votes classify_one stored."""
    n = h._clear(store, kb, "Plastic toy figures")
    cands = [Candidate(code=code, subheading_text=store.index.subheading_text(code), confidence=conf,
                       rationale=f"matches {code}") for code, conf in zip(TOYS, confidences)]
    store.update_classification(n, Classification(line_no=n, candidates=cands, status=LineStatus.checked,
                                                  hs6_vote=hs6_vote, hs6_scoped_vote=scoped_vote))
    return n


class TestStore:
    def test_the_store_keeps_both_votes_and_routes_a_veto_to_review(self, kb):
        store = h._store()
        n = add_voted(store, kb, TOYS_AGREE, TOYS_IN_CHAPTER_OTHER)
        v = store.get_line(n).current
        assert (v.hs6_vote, v.hs6_scoped_vote) == (TOYS_AGREE, TOYS_IN_CHAPTER_OTHER)
        assert (v.computed_route, v.hs6_gate) == (Route.review, Hs6Gate.scoped_veto)
        assert store.decided_code(store.get_line(n)) == (None, None)
        assert store.ready_to_accept(store.get_line(n)) is False
        note = [r.note for r in store.shipment.audit if r.change == ChangeKind.route_computed and r.line_no == n][-1]
        assert note == ("the EBTI rulings of the candidates' chapters do not agree: 3 of 5 at 9405.21 (DE, FR, NL) — "
                        "needs a human look")

    def test_an_agreeing_chapters_vote_leaves_the_auto_accept(self, kb):
        store = h._store()
        n = add_voted(store, kb, TOYS_AGREE, TOYS_AGREE)
        assert (store.get_line(n).current.computed_route, store.get_line(n).current.hs6_gate) ==             (Route.auto_accept, Hs6Gate.vote_agrees)

    def test_a_failed_classification_drops_both_votes(self, kb):
        store = h._store()
        n = add_voted(store, kb, TOYS_AGREE, TOYS_AGREE)
        store.update_classification(n, Classification(line_no=n, status=LineStatus.failed, error_reason="boom"))
        v = store.get_line(n).current
        assert (v.hs6_vote, v.hs6_scoped_vote, v.hs6_gate) == (None, None, None)
