"""Feature 014a, User Story 3: the indexed chapters of the store the app opened, and the ruling scope a line's HS-6 step
records: the chapters of the model's validated candidates, searched by the vote, and those of them with no ruling in the
store (spec FR-014, FR-016, FR-017; data-model §3, §4)."""
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
