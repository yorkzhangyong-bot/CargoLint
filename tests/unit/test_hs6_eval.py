"""tests/eval/hs6_eval.py offline: a line and its correct HS-6 from the set, the nearest-hit log and its eligible flag,
the HS-6 measures over repeated runs, the cross-layer table against the CN-8 eval, and the report."""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from rag.bti import BTIStore
from tests.eval import hs6_eval as ev
from tests.eval.cn8_eval import expected_sent_share

pytestmark = pytest.mark.unit


def test_the_correct_hs6_is_the_first_six_digits_of_the_cn8():
    assert ev.expected_hs6({"cn8": "39259010"}) == "3925.90"
    rulings = json.loads(ev.SET.read_text(encoding="utf-8"))["rulings"]
    assert len(rulings) == 120
    assert all(ev.expected_hs6(r) == r["hs6"] for r in rulings)   # the set's own HS-6 field agrees: no new labels


def test_a_line_is_the_raw_description_as_a_typed_line():
    english = "Internal mounting bracket for infrared sensor\nThe bracket holds the sensor (ABS plastic)"
    line = ev.line_text(4, {"description": english})
    assert (line.line_no, line.text_zh, line.text_en) == (4, "", english)   # neither split nor cut
    german = "Schutzhülle für Mobiltelefone, aus Silikon"
    assert (ev.line_text(1, {"description": german}).text_en) == german
    assert (ev.line_text(2, {"description": "硅胶手机壳"}).text_zh) == "硅胶手机壳"
    both = ev.line_text(3, {"description": "硅胶手机壳 / Silicone mobile phone cases"})
    assert (both.text_zh, both.text_en) == ("硅胶手机壳", "Silicone mobile phone cases")


def ruling(reference, code, valid_to="2027-12-31", member_state="DE"):
    return {"reference": reference, "code": code, "member_state": member_state, "description": f"goods of {reference}",
            "valid_from": "2025-01-01", "valid_to": valid_to}


def test_nearest_hits_keep_each_ruling_once_nearest_first_with_its_eligibility():
    kb = SimpleNamespace(bti=BTIStore([ruling("OWN", "3926.90"), ruling("A", "3926.90", member_state="FR"),
                                       ruling("OLD", "3923.10", valid_to="2024-12-31"), ruling("GONE", "9999.99")]),
                         index=SimpleNamespace(get=lambda code: object() if code in ("3926.90", "3923.10") else None))
    searches = [[("bti:OWN", 0.98), ("bti:A", 0.90), ("bti:OLD", 0.85)],
                [("bti:A", 0.93), ("bti:GONE", 0.70), ("bti:UNKNOWN", 0.60)]]   # a second query vector
    hits = ev.nearest_hits(searches, "OWN", kb, date(2026, 10, 23))
    assert [(h["reference"], h["hs6"], h["distance"], h["eligible"]) for h in hits] == [
        ("OWN", "3926.90", 0.02, False),    # the line's own ruling
        ("A", "3926.90", 0.07, True),       # once, at its smallest distance
        ("OLD", "3923.10", 0.15, False),    # expired on the set's date
        ("GONE", "9999.99", 0.3, False),    # coded to a subheading the nomenclature does not have
        ("UNKNOWN", "", 0.4, False)]        # not in the store
    assert (hits[1]["country"], hits[4]["country"]) == ("FR", "")
    tie = ev.nearest_hits([[("bti:OLD", 0.9), ("bti:A", 0.9)]], "OWN", kb, date(2026, 10, 23))
    assert [h["reference"] for h in tie] == ["A", "OLD"]   # equal distances by id


def test_nearest_hits_are_capped(monkeypatch):
    monkeypatch.setattr(ev, "HITS_LOGGED", 2)
    kb = SimpleNamespace(bti=BTIStore([]), index=SimpleNamespace(get=lambda code: None))
    hits = ev.nearest_hits([[(f"bti:R{i}", 1 - i / 100) for i in range(5)]], "OWN", kb, date(2026, 10, 23))
    assert [h["reference"] for h in hits] == ["R0", "R1"]


def test_the_logged_search_leaves_the_apps_search_unchanged():
    calls = []

    def search(vector, k, chapter_filter=None, where=None):
        calls.append(k)
        return [(f"bti:R{i}", 1 - i / 100) for i in range(k)]

    wrapped = ev._logged(search)
    ev._rec.searches = []
    try:
        assert wrapped([1.0], 12, None) == search([1.0], 12, None)   # what the precedent search gets
        assert calls == [12, ev.HITS_LOGGED, 12]
        assert [len(s) for s in ev._rec.searches] == [ev.HITS_LOGGED]   # the second search, for the log only
    finally:
        del ev._rec.searches
    wrapped([1.0], 12, None)                                           # outside a line: nothing logged
    assert calls == [12, ev.HITS_LOGGED, 12, 12]


def row(reference, top1, route="review", expected="3926.90", top3=None, confidence=80, own_rank=1):
    top3 = top3 if top3 is not None else ([top1] if top1 else [])
    return {"reference": reference, "chapter": "39", "expected": expected, "top1": top1, "top3": top3,
            "confidence": confidence, "hit": top1 == expected, "in_top3": expected in top3, "route": route,
            "expected_sent": True, "own_rank": own_rank}


def test_hs6_measures_over_three_runs():
    runs = [
        [row("A", "3926.90", "auto_accept", confidence=90), row("B", "3923.10", "auto_accept", confidence=88),
         row("C", "3926.90"), row("D", None, "ask_shipper", confidence=None)],
        [row("A", "3926.90", "auto_accept", confidence=90), row("B", "3923.10", top3=["3923.10", "3926.90"]),
         row("C", "3923.10"), row("D", None, "ask_shipper", confidence=None)],
        [row("A", "3926.90", "auto_accept", confidence=91), row("B", "3923.10", "auto_accept", confidence=86),
         row("C", "3924.10"), row("D", None, "ask_shipper", confidence=None)],
    ]
    m = ev.measures(runs)
    assert m["top1_runs"] == [2, 1, 1]
    assert m["majority_top1"] == 2                                  # A, and C: a three-way tie goes to run 1
    assert m["top3_runs"] == [2, 2, 1]
    assert (m["same_top1"], m["top1_consistency"]) == (3, 0.75)     # A, B and D
    assert (m["same_route"], m["route_consistency"]) == (3, 0.75)   # B went to review once
    assert m["routes_runs"][1] == {"auto_accept": 1, "review": 2, "ask_shipper": 1}
    assert [[w["reference"] for w in run] for run in m["wrong_auto_runs"]] == [["B"], [], ["B"]]
    assert [a["reference"] for a in m["always_wrong"]] == ["B", "D"]
    assert m["always_wrong"][0]["seen"][1] == {"top1": "3923.10", "confidence": 80, "route": "review", "in_top3": True}
    assert [u["reference"] for u in m["unstable"]] == ["C"]


def gated(reference, hit, route, by_confidence, gate):
    return {**row(reference, "3926.90" if hit else "4202.92"), "route": route, "route_by_confidence": by_confidence,
            "gate": gate}


def test_the_vote_gate_measures():
    runs = [[gated("A", True, "auto_accept", "auto_accept", "vote_agrees"),     # right, kept
             gated("B", True, "review", "auto_accept", "vote_disagrees"),      # right, lost to the gate
             gated("C", False, "review", "auto_accept", "vote_disagrees"),     # a wrong auto-accept the gate stopped
             gated("D", True, "review", "review", "no_rulings"),               # below the threshold, no ruling voted
             gated("E", False, "ask_shipper", "ask_shipper", "not_gated")]]    # flagged
    g = ev.gate_measures(runs)
    assert g["gate_runs"] == [{"vote_agrees": 1, "vote_disagrees": 2, "vote_tie": 0, "vote_share_low": 0, "no_rulings": 1,
                               "not_gated": 1}]
    assert (g["no_rulings_review_runs"], g["right_auto_runs"], g["lost_runs"]) == ([1], [1], [1])


class Answers:
    """A raw backend that gives the scripted answers in turn."""

    def __init__(self, *answers):
        self.answers, self.last_usage = list(answers), {}

    def raw_structured(self, schema, system, user):
        return self.answers.pop(0)


def test_an_invalid_answer_is_retried_once_and_counted():
    from agent.llm import StructuredCaller
    from agent.routing import SchemaError
    from agent.schemas import RankOut

    good = {"candidates": [{"code": "3926.90", "confidence": 90, "rationale": "a phone case", "history_only": False}]}
    not_json = {"_invalid": True, "content": "Sure! {code: 3926.90"}
    client = StructuredCaller(raw=Answers(not_json, good, not_json, {"candidates": "none"}, good), model_name="m",
                              prices=None, usd_eur=0.92, max_retries=ev.OTHER_MODEL_RETRIES)
    counts = ev.count_invalid(client)
    assert client.call(RankOut, "s", "u").candidates[0].code == "3926.90"     # not JSON, then right on the retry
    with pytest.raises(SchemaError):
        client.call(RankOut, "s", "u")                                         # not JSON, then not the schema: the call fails
    assert client.call(RankOut, "s", "u").candidates[0].confidence == 90       # a valid answer is passed on as it is
    rows = [{"status": "failed"}, {"status": "checked"}]
    assert ev.parse_counts(counts, rows) == {"retries": 2, "unparseable": 2, "schema_invalid": 1, "failed_calls": 1,
                                             "failed_lines": 1}


def test_the_confidence_table_counts_right_and_wrong_top1_per_value():
    runs = [[{**row("A", "3926.90"), "raw_confidence": 95}, {**row("B", "4202.92"), "raw_confidence": 95},
             {**row("C", "3926.90", confidence=59), "raw_confidence": 90}, {**row("D", None), "raw_confidence": None}],
            [{**row("A", "3926.90"), "raw_confidence": 95}, {**row("B", "4202.92", confidence=85)}]]   # an older row: confidence
    assert ev.confidence_table(runs) == {"95": {"right": 2, "wrong": 1}, "90": {"right": 1, "wrong": 0},
                                         "85": {"right": 0, "wrong": 1}}


def test_where_the_own_ruling_stood():
    runs = [[row("A", "x", own_rank=1), row("B", "x", own_rank=12), row("C", "x", own_rank=13), row("D", "x", own_rank=None)]]
    assert ev.own_ruling(runs) == {"nearest_runs": [1], "searched_runs": [2], "logged_runs": [3], "searched": 12}


def cn8_row(reference, chosen, expected="39269097"):
    return {"reference": reference, "expected": expected, "chosen": chosen, "hit": chosen == expected}


def test_cn8_results_read_every_run_of_the_cn8_eval():
    data = {"summary": {"iteration": 11}, "rows": [cn8_row("A", "39269097")],
            "runs": [[cn8_row("A", "39269097")], [cn8_row("A", "39269050")]]}
    assert ev.cn8_results(data) == {"A": {"expected": "39269097", "chosen": ["39269097", "39269050"], "hits": [True, False]}}
    assert ev.cn8_results({"rows": [cn8_row("A", None)]})["A"]["hits"] == [False]   # a single run


HS6_RUNS = [[row("A", "3926.90"), row("B", "3926.90"), row("C", "3923.10"), row("D", "3923.10")],
            [row("A", "3926.90"), row("B", "3926.90"), row("C", "3923.10"), row("D", "3926.90")],
            [row("A", "3926.90"), row("B", "3923.10"), row("C", "3923.10"), row("D", "3923.10")]]
CN8 = ev.cn8_results({"runs": [
    [cn8_row("A", "39269097"), cn8_row("B", "39269050"), cn8_row("C", "39269097"), cn8_row("D", "39269050")],
    [cn8_row("A", "39269097"), cn8_row("B", "39269097"), cn8_row("C", "39269097"), cn8_row("D", "39269050")],
    [cn8_row("A", "39269050"), cn8_row("B", "39269050"), cn8_row("C", "39269097"), cn8_row("D", "39269050")]]})


def test_cross_layer_on_majority_results_and_run_by_run():
    x = ev.cross_layer(HS6_RUNS, CN8)
    assert x["majority"] == {"hs6_right_cn8_right": 1, "hs6_right_cn8_wrong": 1, "hs6_wrong_cn8_right": 1,
                             "hs6_wrong_cn8_wrong": 1}                        # A, B, C, D in that order
    assert [list(cells.values()) for cells in x["runs"]] == [[1, 1, 1, 1], [2, 1, 1, 0], [0, 1, 1, 2]]
    assert x["end_to_end_runs"] == [1, 2, 0]
    assert x["lines"][1] == {"reference": "B", "quadrant": "hs6_right_cn8_wrong", "hs6_hits": [True, True, False],
                             "cn8_hits": [False, True, False]}
    one_run = ev.cross_layer(HS6_RUNS, ev.cn8_results({"rows": [cn8_row(r, "39269097") for r in "ABCD"]}))
    assert one_run["end_to_end_runs"] == [2]                                  # as many runs as both evals have


def test_wrong_auto_accepts_of_every_run_are_counted_the_others_listed():
    a = {"reference": "A", "expected": "3926.90", "top1": "4202.92", "confidence": 95}
    b = {"reference": "B", "expected": "6404.19", "top1": "6405.20", "confidence": 90}
    assert ev._wrong_auto([[a], [a, b], [a]]) == [
        "Per run: 1 / 2 / 1. In every run: 1 line, each among the lines wrong in every run above.", "",
        "- B (expected 6404.19): run 2: 6405.20 (90)"]
    assert ev._wrong_auto([[], []]) == ["Per run: 0 / 0. In every run: 0 lines, each among the lines wrong in every run above."]


def test_the_report_shows_the_entry():
    m, x = ev.measures(HS6_RUNS), ev.cross_layer(HS6_RUNS, CN8)
    entry = {"iteration": 1, "run_on": "2026-10-25", "tag": "hs6-baseline", "repeat": 3, "n": 4, "model": "m", **m,
             "expected_sent": expected_sent_share(HS6_RUNS), "own_ruling": ev.own_ruling(HS6_RUNS), "cn8_iteration": 11,
             "cross_layer": x, "elapsed_s": 10.0, "cost_usd": 0.01, "cost_eur": 0.0093}
    data = {"built_on": "2026-10-23", "rulings": [{"reference": r, "description": f"goods *{r}*"} for r in "ABCD"]}
    text = ev.render_report([entry], data)
    assert "| 1 | 2026-10-25 | hs6-baseline | 3 | 2 / 3 / 1 of 4 | 2/4 | 2 / 3 / 1 of 4 | 2/4 | 4/4 | 0 / 0 / 0 | 1 / 2 / 0 of 4 |" in text
    assert "| Majority | 1 | 1 | 1 | 1 |" in text and "| Run 2 | 2 | 1 | 1 | 0 |" in text
    assert "On majority results 3 of 4 lines end wrong: 2 from the HS-6 step" in text
    assert ("- C (chapter 39, expected 3926.90): 3923.10 (80, review) · 3923.10 (80, review) · 3923.10 (80, review); "
            "correct in the top 3 in 0 of 3 runs. \"goods \\*C\\*\"") in text
    assert "| 1 / 2 / 0 of 4 | 0 / 0 / 0 | - | $0.0100" in text and "### Vote gate" not in text   # an entry before the gate


def test_each_run_keeps_its_own_results_file_next_to_the_latest(tmp_path):
    out = tmp_path / "hs6_eval.json"
    first = {"summary": {"iteration": 7}, "rows": [{"reference": "A", "nearest_hits": [{"reference": "B"}]}]}
    own = ev.write_results(first, out, "hs6-test")
    assert own == tmp_path / "hs6_eval_hs6-test.json"
    assert own.read_text(encoding="utf-8") == out.read_text(encoding="utf-8")
    assert json.loads(own.read_text(encoding="utf-8"))["rows"][0]["nearest_hits"] == [{"reference": "B"}]
    ev.write_results({"summary": {"iteration": 8}, "rows": []}, out, "iteration8")             # a later run
    assert json.loads(own.read_text(encoding="utf-8"))["summary"]["iteration"] == 7             # left alone
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["iteration"] == 8             # the latest
    assert (tmp_path / "hs6_eval_iteration8.json").exists()


def test_a_tag_must_name_a_file():
    assert all(ev.TAG_RE.fullmatch(t) for t in ("hs6-baseline", "hs6-gemini25-flash", "e2e.v2", "run_3"))
    assert not any(ev.TAG_RE.fullmatch(t) for t in ("a/b", "..\\x", "two words", "", "-x"))
    with pytest.raises(SystemExit):   # before anything runs: the offline guard would fail a test that reached OpenRouter
        ev.main(["--tag", "a/b"])


def test_the_report_shows_the_vote_gate():
    runs = [[{**r, "route_by_confidence": r["route"], "gate": "no_rulings"} for r in run] for run in HS6_RUNS]
    entry = {"iteration": 2, "run_on": "2026-10-26", "tag": "hs6-vote-gate", "repeat": 3, "n": 4, "model": "m",
             **ev.measures(runs), **ev.gate_measures(runs), "expected_sent": expected_sent_share(runs),
             "own_ruling": ev.own_ruling(runs), "cn8_iteration": 11, "cross_layer": ev.cross_layer(runs, CN8),
             "elapsed_s": 10.0, "cost_usd": 0.01, "cost_eur": 0.0093}
    text = ev.render_report([entry], {"built_on": "2026-10-23", "rulings": []})
    assert "| 1 / 2 / 0 of 4 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0100" in text
    assert "| 2 | 0 | 0 | 0 | 0 | 4 | 0 | 4 | 0 | 0 |" in text      # run 2: no ruling voted on any line, all to review


# --------------------------------------------------------------------------- feature 008: the precedent override
TOP3 = ["9503.00", "3926.90", "4202.92"]


def voted(reference, counts, expected="3926.90", top3=TOP3, confidence=90, flag="ok", status="checked"):
    """A row as run_once writes it with the switch off: its top 3, its flag and status, and its vote's counts (most
    first); the vote and the gate are those the product computes from them."""
    from agent.routing import hs6_gate, hs6_ruling_vote

    vote = hs6_ruling_vote([(code, "IE") for code, k in counts for _ in range(k)], top3) if counts else None
    gated = status == "checked" and flag == "ok" and (confidence or 0) > 0
    return {**row(reference, top3[0] if top3 else None, expected=expected, top3=top3, confidence=confidence),
            "confidences": [confidence, 60, 20][:len(top3)], "flag": flag, "status": status,
            "gate": hs6_gate(confidence, 85, vote)[1].value if gated else "not_gated",
            "vote": None if vote is None else {"majority": vote.majority, "share": vote.majority_share,
                                               "voters": sum(k for _, k in counts), "candidate": vote.candidate,
                                               "counts": counts}}


@pytest.mark.parametrize("counts, kw, supported, on", [
    ([["3926.90", 4], ["9503.00", 1]], {}, {"rank": 2, "right": True},
     {"gate": "vote_override", "route": "auto_accept", "rank": 2, "chosen": "3926.90", "hit": True}),
    ([["4202.92", 5]], {}, {"rank": 3, "right": False},
     {"gate": "vote_override", "route": "auto_accept", "rank": 3, "chosen": "4202.92", "hit": False}),
    ([["3926.90", 3], ["9503.00", 2]], {}, {"rank": 2, "right": True},            # 3 of 5: no override
     {"gate": "vote_disagrees", "route": "review", "rank": 1, "chosen": "9503.00", "hit": False}),
    ([["9617.00", 4], ["9503.00", 1]], {}, {"rank": None, "right": None},         # outside the candidates
     {"gate": "vote_disagrees", "route": "review", "rank": 1, "chosen": "9503.00", "hit": False}),
    ([], {"expected": "9503.00"}, {"rank": None, "right": None},                   # no ruling voted: the threshold
     {"gate": "no_rulings", "route": "auto_accept", "rank": 1, "chosen": "9503.00", "hit": True}),
    ([["3926.90", 4], ["9503.00", 1]], {"flag": "vague", "confidence": 55}, {"rank": 2, "right": True},
     {"gate": "not_gated", "route": "review", "rank": 1, "chosen": "9503.00", "hit": False}),
    ([], {"top3": [], "confidence": None}, {"rank": None, "right": None},
     {"gate": "not_gated", "route": "review", "rank": None, "chosen": None, "hit": False})])
def test_feature_008_the_switch_on_from_a_rows_own_fields(counts, kw, supported, on):
    r = voted("A", counts, **kw)
    before = json.dumps(r, sort_keys=True)
    assert ev.override_fields(r, 4) == {"supported": supported, "on": on}
    assert json.dumps(r, sort_keys=True) == before                     # the row's own fields stay the switch off


OVERRIDE_RUNS = [[{**voted("A", [["3926.90", 4], ["9503.00", 1]]), "route": "review"},          # right on, wrong off
                  {**voted("B", [["4202.92", 4], ["9503.00", 1]]), "route": "review"},          # a wrong override
                  {**voted("C", [["9503.00", 5]], expected="9503.00"), "route": "auto_accept"},  # agrees: the same
                  {**voted("D", [["3926.90", 3], ["9503.00", 2]]), "route": "review"}]]         # 3 of 5: the same


def test_feature_008_the_measures_with_the_switch_on():
    runs = [[{**r, **ev.override_fields(r, 4)} for r in run] for run in OVERRIDE_RUNS]
    cn8 = ev.cn8_results({"rows": [cn8_row(r, "39269097") for r in "ABCD"]})                    # every CN-8 right
    o = ev.override_measures(runs, cn8, 4)
    assert o["override_min"] == 4
    assert (o["on"]["top1_runs"], o["on"]["routes_runs"], o["on"]["right_auto_runs"]) == (
        [2], [{"auto_accept": 3, "review": 1, "ask_shipper": 0}], [2])
    assert [w["reference"] for w in o["on"]["wrong_auto_runs"][0]] == ["B"]
    assert o["on"]["cross_layer"]["end_to_end_runs"] == [2]                                     # A and C, on the chosen
    assert ev.cross_layer(runs, cn8)["end_to_end_runs"] == [1]                                  # off: C only
    assert o["overrides_runs"] == [[
        {"reference": "A", "expected": "3926.90", "top1": "9503.00", "chosen": "3926.90", "rank": 2, "hit": True},
        {"reference": "B", "expected": "3926.90", "top1": "9503.00", "chosen": "4202.92", "rank": 3, "hit": False}]]
    assert o["supported_runs"] == [{"lines": 3, "right": 2}]                                    # A, B and D; A and D right


def test_feature_008_the_report_shows_the_switch_off_against_on():
    runs = [[{**r, **ev.override_fields(r, 4), "route_by_confidence": r["route"]} for r in run] for run in OVERRIDE_RUNS]
    cn8 = ev.cn8_results({"rows": [cn8_row(r, "39269097") for r in "ABCD"]})
    entry = {"iteration": 7, "run_on": "2026-10-26", "tag": "hs6-override", "repeat": 1, "n": 4, "model": "m",
             **ev.measures(runs), **ev.gate_measures(runs), "expected_sent": expected_sent_share(runs),
             "own_ruling": ev.own_ruling(runs), "cn8_iteration": 12, "cross_layer": ev.cross_layer(runs, cn8),
             **ev.override_measures(runs, cn8, 4), "elapsed_s": 10.0, "cost_usd": 0.01, "cost_eur": 0.0093}
    text = ev.render_report([entry], {"built_on": "2026-10-23", "rulings": []})
    assert "### Precedent override (feature 008)" in text
    assert "| 1 | off | 1/4 | 1 | 0 | 1 | 1/4 |" in text and "| 1 | on | 2/4 | 3 | 1 | 2 | 2/4 |" in text
    assert "Overrides that fired per run: 2, of which chose the right HS-6: 1." in text
    assert "- run 1: B (expected 3926.90): candidate 3, 4202.92, instead of 9503.00; wrong" in text
    assert "on 3 lines per run; that candidate was the right HS-6 on 2." in text


REPLAYED = OVERRIDE_RUNS[0] + [{**voted("E", [["3926.90", 5]]), "route": "review"}]   # 5 of 5 at candidate 2


def test_feature_008_a_replay_recomputes_the_switch_on_at_another_minimum():
    stored = {"summary": {}, "rows": [{**r, **ev.override_fields(r, 4)} for r in REPLAYED]}
    assert [r["on"]["gate"] for r in stored["rows"]] == [
        "vote_override", "vote_override", "vote_agrees", "vote_disagrees", "vote_override"]
    runs = ev.replay_runs(stored, 5)
    assert [r["on"]["gate"] for r in runs[0]] == [
        "vote_disagrees", "vote_disagrees", "vote_agrees", "vote_disagrees", "vote_override"]   # only 5 of 5 still fires
    assert [r["supported"] for r in runs[0]] == [r["supported"] for r in stored["rows"]]
    assert ev.override_measures(runs, ev.cn8_results({"rows": [cn8_row(r, "39269097") for r in "ABCDE"]}), 5)[
        "override_min"] == 5


def test_feature_008_a_replay_makes_no_model_call_and_writes_its_own_file_only(tmp_path, monkeypatch):
    for name in ("OUT", "HISTORY", "REPORT"):
        monkeypatch.setattr(ev, name, tmp_path / getattr(ev, name).name)
    rows = [{**r, **ev.override_fields(r, 4), "route_by_confidence": r["route"]} for r in REPLAYED]
    source = tmp_path / "hs6_eval_run.json"
    source.write_text(json.dumps({"summary": {"iteration": 7, "tag": "run", "model": "m", "repeat": 1, "n": 5,
                                              "override_min": 4}, "rows": rows}), encoding="utf-8")
    refs = [r["reference"] for r in json.loads(ev.SET.read_text(encoding="utf-8"))["rulings"]] + list("ABCDE")
    cn8 = tmp_path / "cn8.json"
    cn8.write_text(json.dumps({"summary": {"iteration": 12}, "rows": [cn8_row(r, "39269097") for r in refs]}),
                   encoding="utf-8")
    assert ev.main(["--replay", str(source), "--override-min", "5", "--tag", "run-min5", "--cn8", str(cn8)]) == 0
    assert not ev.OUT.exists()                                                  # the latest paid run's file stays
    replayed = json.loads((tmp_path / "hs6_eval_run-min5.json").read_text(encoding="utf-8"))
    assert [r["on"]["gate"] for r in replayed["rows"]][-1] == "vote_override"
    entry = json.loads(ev.HISTORY.read_text(encoding="utf-8"))[-1]
    assert (entry["tag"], entry["replay_of"], entry["override_min"], entry["cost_eur"]) == (
        "run-min5", {"iteration": 7, "tag": "run"}, 5, 0.0)
    assert "Replay of iteration 7 (run) at OVERRIDE_MIN 5" in ev.REPORT.read_text(encoding="utf-8")


def test_feature_008_the_minimum_is_for_a_replay():
    with pytest.raises(SystemExit):
        ev.main(["--override-min", "5"])
