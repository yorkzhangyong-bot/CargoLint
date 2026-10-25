"""The gate replay of tests/eval/cn8_vote_analysis.py, offline on made-up rows with known answers."""
from __future__ import annotations

import pytest

from tests.eval import cn8_vote_analysis as va

pytestmark = pytest.mark.unit


def hit(ref, cn8, distance, country="FR", eligible=True):
    return {"reference": ref, "cn8": cn8, "distance": distance, "country": country, "eligible": eligible}


def row(chosen, expected="11111111", route="auto_accept", hits=(), question=None, precedent_code=None):
    return {"chosen": chosen, "expected": expected, "route": route, "hit": chosen == expected, "question": question,
            "error": None, "precedent_code": precedent_code, "nearest_hits": list(hits)}


def test_only_eligible_hits_count_nearest_first_by_rounded_distance_then_reference():
    hits = [hit("OWN", "22222222", 0.0, eligible=False), hit("Z", "11111111", 0.10003), hit("A", "22222222", 0.10001),
            hit("B", "33333333", 0.05)]
    assert [h["reference"] for h in va.eligible_hits(row("11111111", hits=hits))] == ["B", "A", "Z"]


@pytest.mark.parametrize("hits,weighted,expected", [
    ([hit("A", "1", 0.1, "DE"), hit("B", "2", 0.2), hit("C", "2", 0.3)], True, ("1", 0.6)),    # DE weighs 3
    ([hit("A", "1", 0.1, "DE"), hit("B", "2", 0.2), hit("C", "2", 0.3)], False, ("2", 2 / 3)),
    ([hit("A", "1", 0.1), hit("B", "2", 0.2)], True, (None, 0.5))])                                # a tie: no majority
def test_the_vote(hits, weighted, expected):
    top, share = va.vote(hits, weighted)
    assert (top, round(share, 4)) == (expected[0], round(expected[1], 4))


def test_the_gate_of_each_kind():
    hits = [hit("A", "11111111", 0.1), hit("B", "22222222", 0.2, "DE"), hit("C", "22222222", 0.3)]
    nearest, vote3 = va.Variant("nearest-1"), va.Variant("vote", 3, 0.6, True)
    assert va.route(row("11111111", hits=hits), nearest) == "auto_accept"
    assert va.route(row("22222222", hits=hits), nearest) == "review"
    assert va.route(row("22222222", hits=hits), vote3) == "auto_accept"            # 4 of 5
    assert va.route(row("11111111", hits=hits), vote3) == "review"
    assert va.route(row("22222222", hits=hits, route="review"), vote3) == "auto_accept"   # confidence plays no part
    assert va.route(row("22222222", hits=hits, precedent_code="1111111100"), vote3) == "review"   # a conflicting citation
    assert va.route(row(None, route="ask_shipper", question="Ask the shipper for: x", hits=hits), vote3) == "ask_shipper"
    assert va.route(row("22222222", route="auto_accept"), vote3) == "auto_accept"   # no eligible hit: today's route


def test_the_measures_and_the_target():
    good = [hit("A", "11111111", 0.1)]
    runs = [[row("11111111", hits=good), row("99999999", expected="22222222", hits=[hit("B", "22222222", 0.1)])]
            for _ in range(3)]
    base = va.baseline(runs)
    assert (base["wrong_aa"], base["always_right"], base["wrong_rows"], base["right_rows"]) == ([1], [0], [1, 1, 1], 3)
    m = va.measure(runs, va.Variant("nearest-1"), base)
    assert (m["wrong_rows"], m["blocked"], m["right_lost"], m["to_review"], m["meets"]) == ([0, 0, 0], 1, 0, 0, True)
