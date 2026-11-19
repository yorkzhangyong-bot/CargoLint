"""Feature 014a, User Story 3: the indexed chapters of the store the app opened, and the ruling scope a line's HS-6 step
records: the chapters of the model's validated candidates, searched by the vote, and those of them with no ruling in the
store (spec FR-014, FR-016, FR-017; data-model §3, §4).

Traceability: 014a/FR-014, 014a/FR-015, 014a/FR-016, 014a/FR-017, 014a/FR-019."""
from __future__ import annotations

import pytest

from agent.schemas import RulingScope
from rag.bti import BTIStore, indexed_chapters
from rag.loader import KnowledgeBase
from tools.classify_hs6 import ruling_scope

pytestmark = pytest.mark.unit


def ruling(reference: str, code: str) -> dict:
    return {"reference": reference, "code": code, "chapter": code[:2], "member_state": reference[:2],
            "valid_from": "2025-01-01", "valid_to": "2027-12-31", "language": "de"}


def test_the_indexed_chapters_are_those_of_the_stored_rulings():
    records = [ruling("DE-1", "3403.99"), ruling("FR-2", "3403.19"), ruling("XI-3", "8419.89")]
    assert indexed_chapters(records) == frozenset({"34", "84"})
    assert indexed_chapters([]) == frozenset()


def test_the_knowledge_base_counts_its_indexed_chapters_when_it_opens():
    kb = KnowledgeBase(None, None, BTIStore([ruling("NL-1", "2710.19"), ruling("DE-2", "3403.99")]), None, {}, None)
    assert kb.indexed_chapters == frozenset({"27", "34"})
    assert KnowledgeBase(None, None, BTIStore([]), None, {}, None).indexed_chapters == frozenset()
    assert KnowledgeBase(None, None, None, None, {}, None).indexed_chapters == frozenset()   # no ruling store at all


def test_the_scope_is_the_candidates_chapters_sorted_with_those_not_indexed():
    scope = ruling_scope(["3403.99", "2710.19", "3820.00"], frozenset({"27", "34", "84"}))
    assert scope == RulingScope(chapters=["27", "34", "38"], not_indexed=["38"])
    assert ruling_scope(["6109.10", "6109.90", "6110.20"], frozenset({"61"})) == RulingScope(chapters=["61"], not_indexed=[])
    assert ruling_scope(["3403.99"], frozenset()) == RulingScope(chapters=["34"], not_indexed=["34"])
    assert ruling_scope([], frozenset({"34"})) is None                                      # no candidate: no vote


# --------------------------------------------------------------------------- User Story 4: relevant means eligible to vote
def test_a_ruling_at_exactly_the_floor_is_relevant_and_one_just_below_is_not():
    from datetime import date
    from types import SimpleNamespace

    from agent.config import HS6_VOTE_MIN_SIMILARITY
    from agent.routing import hs6_ruling_vote
    from agent.schemas import Candidate, Line, LineVersion
    from tools.classify_hs6 import hs6_voters
    from ui import view

    store = BTIStore([ruling("DE-1", "3403.99")])
    index = SimpleNamespace(get=lambda code: object() if code == "3403.99" else None)
    on_the_day = date(2026, 11, 18)
    assert hs6_voters([[("bti:DE-1", HS6_VOTE_MIN_SIMILARITY)]], store, index, on_the_day) == [("3403.99", "DE")]
    below = hs6_voters([[("bti:DE-1", HS6_VOTE_MIN_SIMILARITY - 1e-4)]], store, index, on_the_day)
    assert below == [] and hs6_ruling_vote(below, ["3403.99"]) is None                    # as the only hit: no vote
    line = Line(line_no=1, versions=[LineVersion(text_en="coolant", candidates=[Candidate(code="3403.99", confidence=90)],
                                                 hs6_vote=None, ruling_scope=RulingScope(chapters=["34"], not_indexed=[]))])
    assert view.rulings_captions(line, "3403.99") == ["No relevant rulings found."]


@pytest.mark.parametrize("below, passes", [(0, True), (1, False)])            # exactly the threshold, and one below
def test_with_no_relevant_ruling_the_estimate_decides_against_the_threshold_as_before(below, passes):
    from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD
    from agent.routing import hs6_gate, route_line
    from agent.schemas import FlagKind, Hs6Gate, LineStatus, Route

    estimate = DEFAULT_THRESHOLD - below
    assert hs6_gate(estimate, DEFAULT_THRESHOLD, None) == (passes, Hs6Gate.no_rulings)
    route, _ = route_line(FlagKind.ok, estimate, LineStatus.checked, False, DEFAULT_THRESHOLD, ASK_FLOOR, hs6_vote=None)
    assert route == (Route.auto_accept if passes else Route.review)
