"""tests/eval/eval_diff_014a.py offline: the old, unscoped vote rebuilt from a row's nearest rulings, and the cause rules
of the evaluation report's line analysis, on hand-written rows."""
from __future__ import annotations

import pytest

from agent.config import HS6_VOTE_MIN_SIMILARITY
from tests.eval import eval_diff_014a as ed

pytestmark = pytest.mark.unit


def hit(hs6, similarity, eligible=True):
    return {"reference": f"R-{hs6}-{similarity}", "hs6": hs6, "distance": round(1 - similarity, 6), "eligible": eligible}


def row(top3, nearest, confidence=95, flag="ok", route="review"):
    return {"top3": top3, "top1": top3[0] if top3 else None, "confidence": confidence, "flag": flag, "status": "checked",
            "nearest_hits": nearest, "route": route, "gate": "vote_agrees" if flag == "ok" else "not_gated",
            "precedent_codes": [], "expected": "3403.99"}


def test_the_old_vote_reads_the_12_nearest_eligible_rulings_at_or_above_the_floor():
    machinery = [hit("8419.89", 0.9 - k / 100) for k in range(5)]
    assert ed.unscoped_route(row(["3403.99"], machinery)) == "review"                     # the machines disagree
    agreeing = [hit("8419.89", 0.95, eligible=False)] + [hit("3403.99", 0.8 - k / 100) for k in range(5)]
    assert ed.unscoped_route(row(["3403.99"], agreeing)) == "auto_accept"                 # the ineligible one never votes
    far = [hit("8419.89", 0.9)] * 12 + [hit("3403.99", 0.89)] * 5                        # beyond the 12 the search read
    assert ed.unscoped_route(row(["3403.99"], far)) == "review"
    low = [hit("3403.99", HS6_VOTE_MIN_SIMILARITY - 1e-3)]                               # below the floor: no vote, so
    assert ed.unscoped_route(row(["3403.99"], low, confidence=95)) == "auto_accept"       # the estimate decides
    assert ed.unscoped_route(row(["3403.99"], low, confidence=70)) == "review"


def view(top1, routes, props=(), unscoped=None, expected="3403.99", gated=True):
    maj = ed.majority(list(top1))
    return {"expected": expected, "top1": list(top1), "route": list(routes), "outcomes": list(top1), "majority": maj,
            "right": maj == expected, "auto": sum(r == "auto_accept" for r in routes), "props": [list(props)] * 3,
            "wrong_auto": 0, "gated": [gated] * 3, "unscoped": list(unscoped or routes)}


@pytest.mark.parametrize("b, o, causes", [
    (view(["3403.99", "3403.99", "3403.19"], ["review"] * 3),                            # the after majority was among
     view(["3403.19"] * 3, ["review"] * 3), ("run-to-run variation", None)),             # the baseline's runs
    (view(["3403.99"] * 3, ["review"] * 3, props=["3403.99"]),
     view(["8419.89"] * 3, ["review"] * 3, props=["8419.89"]), ("new-chapter proposals", None)),
    (view(["3403.99"] * 3, ["review"] * 3), view(["8419.89"] * 3, ["review"] * 3), ("other", None)),
    (view(["3403.99"] * 3, ["review"] * 3),                                              # the scoped vote auto-accepts
     view(["3403.99"] * 3, ["auto_accept"] * 3, unscoped=["review"] * 3), (None, "vote scope")),   # what the old would not
    (view(["3403.99"] * 3, ["auto_accept"] * 3),                                         # the old vote, on the new store,
     view(["3403.99"] * 3, ["review"] * 3, unscoped=["review"] * 3), (None, "new-chapter rulings in the vote")),
    (view(["3403.99"] * 3, ["auto_accept", "review", "review"]),
     view(["3403.99"] * 3, ["review"] * 3, unscoped=["review"] * 3), (None, "run-to-run variation")),
    (view(["3403.99"] * 3, ["review"] * 3), view(["3403.99"] * 3, ["review"] * 3), (None, None)),   # nothing changed
])
def test_the_cause_rules(b, o, causes):
    assert ed.cause_of(b, o) == causes
