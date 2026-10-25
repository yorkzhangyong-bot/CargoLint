"""The rulings sent to the model, logged per line and run by tests/eval/cn8_eval.py, offline: the real CN-8 step on a
small fake knowledge base (no BTI vectors, so rulings go round-robin in CN-8 order) and a fake model client."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import tools.classify_cn8 as classify_cn8
from agent.schemas import Cn8Out, Precedent
from tests.eval import cn8_eval as ev

pytestmark = pytest.mark.unit

AS_OF = date(2026, 10, 23)
OPTIONS = [("87149110", "Frames"), ("87149130", "Front forks"), ("87149190", "Other")]


class FakeBti:
    """The rulings under 8714.91 grouped by CN-8, as BTIStore.by_cn8 returns them."""

    def by_cn8(self, hs6, as_of):
        return {"87149110": [Precedent(reference="A", code="8714911000")],
                "87149130": [Precedent(reference="X", code="87149130")],
                "87149190": [Precedent(reference="B", code="8714919000")]}


KB = SimpleNamespace(index=SimpleNamespace(cn8_lines=lambda hs6: OPTIONS, subheading_text=lambda hs6: "Frames and forks"),
                     bti=FakeBti(), bti_vectors=None)
CLIENT = SimpleNamespace(call=lambda schema, system, user, max_retries=0: Cn8Out(   # always 87149110, from the line's words
    cn8="87149110", confidence=95, attribute_visible=True, evidence="bicycle frames", rationale="frames"))


def eval_line(reference, cn8):
    return {"reference": reference, "chapter": "87", "hs6": "8714.91", "cn8": cn8, "language": "en",
            "description": f"Bicycle frames, ruling {reference}"}


def test_each_row_keeps_the_rulings_sent_for_its_own_line():
    original = classify_cn8.select_rulings
    rows, _ = ev.run_once([eval_line("A", "87149110"), eval_line("B", "87149190"), eval_line("Q", "87149130")],
                          KB, CLIENT, AS_OF, workers=2)
    assert classify_cn8.select_rulings is original                       # the recording ends with the run
    a, b, q = rows
    assert a["sent"] == [{"reference": "X", "cn8": "87149130", "rank": 1}, {"reference": "B", "cn8": "87149190", "rank": 2}]
    assert (a["hit"], a["expected_sent"]) == (True, False)               # its own ruling A is never sent
    assert b["sent"] == [{"reference": "A", "cn8": "87149110", "rank": 1}, {"reference": "X", "cn8": "87149130", "rank": 2}]
    assert (b["hit"], b["expected_sent"]) == (False, False)
    assert [s["reference"] for s in q["sent"]] == ["A", "X", "B"] and [s["rank"] for s in q["sent"]] == [1, 2, 3]
    assert (q["hit"], q["expected_sent"]) == (False, True)               # X is at the expected 87149130
    assert ev.expected_sent_share([rows]) == {"wrong": 2, "with_expected": 1, "share": 0.5}


def test_the_share_counts_every_wrong_result_of_every_run():
    def run(*pairs):
        return [{"hit": hit, "expected_sent": sent} for hit, sent in pairs]
    runs = [run((True, False), (False, True), (False, False)), run((True, True), (False, True), (True, False))]
    assert ev.expected_sent_share(runs) == {"wrong": 3, "with_expected": 2, "share": 0.6667}
    assert ev.expected_sent_share([run((True, True))]) == {"wrong": 0, "with_expected": 0, "share": None}


def test_the_report_shows_every_repeated_run_with_its_tag_and_the_share():
    base = {"run_on": "2026-10-25", "model": "m", "threshold": 85, "top1": 92, "n": 120, "written": 107, "written_wrong": 15,
            "to_confirm": 1, "questions": 12, "failures": 0, "with_precedent": 103, "per_chapter": {"39": "10/10"},
            "elapsed_s": 300.0, "cost_usd": 0.1139, "cost_eur": 0.1048, "repeat": 3, "temperature": 0.0, "seed": None,
            "top1_runs": [92, 92, 94], "majority_top1": 93, "code_consistency": 0.9167, "decision_consistency": 0.9083,
            "unstable": []}
    history = [dict(base, iteration=5, change="baseline", tag="baseline-stability"),
               dict(base, iteration=7, change="three-level rule", tag="prompt-evidence-v2",
                    expected_sent={"wrong": 84, "with_expected": 63, "share": 0.75})]
    report = ev.render_report(history, {"rulings": [{}] * 120, "per_chapter": 10, "built_on": "2026-10-23", "seed": 7})
    assert "| 5 | 2026-10-25 | baseline-stability | 0.0 | none | 3 |" in report
    assert "| 7 | 2026-10-25 | prompt-evidence-v2 | 0.0 | none | 3 |" in report
    assert "Iteration 7: 63 of 84 wrong results (75.0%)" in report
