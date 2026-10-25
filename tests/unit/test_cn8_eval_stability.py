"""The stability measures of tests/eval/cn8_eval.py --repeat N, offline on made-up rows with known answers."""
from __future__ import annotations

import pytest

from tests.eval import cn8_eval as ev

pytestmark = pytest.mark.unit


def row(reference, chosen, confidence=90, written=False, question=None, error=None, expected="39269097"):
    return {"reference": reference, "hs6": "3926.90", "expected": expected, "chosen": chosen, "confidence": confidence,
            "written": written, "question": question, "error": error}


def test_decision_in_route_terms():
    assert ev.decision(row("A", "39269097", written=True)) == "auto_accept"          # written by rule
    assert ev.decision(row("A", "39269097")) == "review"                             # a suggestion to confirm
    assert ev.decision(row("A", None, question="Ask the shipper for: material")) == "ask_shipper"
    assert ev.decision(row("A", None, error="SchemaError: invalid")) == "review"     # route_line: a failed step → review


def test_majority_takes_the_earliest_run_on_a_tie():
    assert ev.majority(["a", "b", "b"]) == "b"
    assert ev.majority(["a", "b", "c"]) == "a"
    assert ev.majority([None, None, "a"]) is None


def test_stability_measures():
    question = "Ask the shipper for: material"
    runs = [
        [row("A", "39269097", written=True), row("B", "39269050", 70), row("C", "39269097", 95, written=True),
         row("D", None, 0, question=question)],
        [row("A", "39269097", written=True), row("B", "39269097", 92, written=True), row("C", "39269097", 80),
         row("D", None, 0, question=question)],
        [row("A", "39269097", written=True), row("B", "39269097", 88, written=True), row("C", "39269097", 96, written=True),
         row("D", None, 0, question=question)],
    ]
    s = ev.stability(runs)
    assert (s["same_code"], s["code_consistency"]) == (3, 0.75)            # A, C and D: the same top-1 in all runs
    assert (s["same_decision"], s["decision_consistency"]) == (2, 0.5)     # A and D: C was once only to confirm
    assert s["majority_top1"] == 3                                          # A, B and C; D asks the shipper: a miss
    assert s["unstable"] == [{"reference": "B", "hs6": "3926.90", "expected": "39269097", "seen": [
        {"cn8": "39269050", "confidence": 70, "decision": "review"},
        {"cn8": "39269097", "confidence": 92, "decision": "auto_accept"},
        {"cn8": "39269097", "confidence": 88, "decision": "auto_accept"}]}]


def test_overrides_reach_the_chat_model_of_this_run(monkeypatch):
    import dataclasses

    import agent.llm as llm
    from agent.config import load_settings

    built = []

    def fake_chat_model(settings=None, **overrides):
        built.append(overrides)
        return object()
    monkeypatch.setattr(llm, "get_chat_model", fake_chat_model)          # the default build inside OpenRouterRawClient
    monkeypatch.setattr(ev, "get_chat_model", fake_chat_model)           # this run's build
    settings = dataclasses.replace(load_settings({}), api_key="test-key-not-real")
    ev.OverriddenClient(settings, {"temperature": 0.0, "seed": 42})
    assert built == [{}, {"temperature": 0.0, "seed": 42}]


def test_a_single_run_still_needs_its_iteration_and_change():
    with pytest.raises(SystemExit):
        ev.main([])
    with pytest.raises(SystemExit):
        ev.main(["--repeat", "0", "--iteration", "9", "--change", "x"])
