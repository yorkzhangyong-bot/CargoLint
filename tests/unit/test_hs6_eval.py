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
     {"gate": "not_gated", "route": "ask_shipper", "rank": 1, "chosen": "9503.00", "hit": False}),   # vague: always ask
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


# --------------------------------------------------------------------------- feature 014a: the coolant set
# 014a/FR-001, 014a/FR-002
def coolant_set_copy(tmp_path, monkeypatch):
    """A temporary copy of the coolant set (tasks T003) that the eval reads instead of the repository's file."""
    copy = tmp_path / "hs6_eval_coolant_set.json"
    copy.write_bytes(ev.COOLANT_SET.read_bytes())
    monkeypatch.setattr(ev, "COOLANT_SET", copy)
    return copy


def test_feature_014a_the_coolant_set_loads_as_typed_lines(tmp_path, monkeypatch):
    copy = coolant_set_copy(tmp_path, monkeypatch)
    data = json.loads(copy.read_text(encoding="utf-8"))
    assert data["built_on"] == "2026-11-18" and len(data["lines"]) == 8
    assert all(("expected_hs6" in line) != ("expected_route" in line) for line in data["lines"])   # exactly one of them
    items = ev.coolant_items(data)
    assert [i["reference"] for i in items] == [f"coolant-{k}" for k in range(1, 9)]
    assert [i.get("expected_hs6") or i["expected_route"] for i in items] == [
        "2710.19", "ask_shipper", "3403.99", "3403.99", "2710.19", "3403.99", "3403.99", "ask_shipper"]
    assert [ev.expected_of(i) for i in items][:2] == ["2710.19", None]                     # an "ask the shipper" line
    fifth = ev.line_text(5, items[4])                                                       # split as a typed line
    assert (fifth.text_zh, fifth.text_en) == ("金属加工冷却液，矿物油含量大于70%",
                                              "Metal-working coolant, petroleum mineral oil content more than 70% by weight")
    assert ev.line_text(7, items[6]).text_en == "Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl"
    assert (ev.line_text(8, items[7]).text_zh, ev.line_text(8, items[7]).text_en) == ("冷却液", "")


def coolant_row(reference, top1, route, expected="2710.19", expected_route=None, top3=None, confidence=90):
    """A coolant row as run_once writes it, scored by coolant_score."""
    top3 = top3 if top3 is not None else ([top1] if top1 else [])
    r = {**row(reference, top1, route, expected=expected, top3=top3, confidence=confidence),
         "route_by_confidence": route, "gate": "no_rulings", "nearest_hits": [], "status": "checked"}
    if expected_route:
        r.update(expected=None, hit=False, in_top3=False)
    item = {"reference": reference, **({"expected_route": expected_route} if expected_route else {"expected_hs6": expected})}
    return {**r, **ev.coolant_score(r, item)}


def test_feature_014a_a_coolant_line_is_right_on_its_code_or_on_its_route():
    coded = {"reference": "C1", "expected_hs6": "2710.19"}
    ask = {"reference": "C2", "expected_route": "ask_shipper"}
    assert ev.coolant_score({"hit": True, "route": "review"}, coded) == {"expected_route": None, "right": True}
    assert ev.coolant_score({"hit": False, "route": "ask_shipper"}, coded)["right"] is False
    assert ev.coolant_score({"hit": False, "route": "ask_shipper"}, ask) == {"expected_route": "ask_shipper", "right": True}
    assert ev.coolant_score({"hit": False, "route": "review"}, ask)["right"] is False      # whatever codes it shows


def coolant_runs():
    """Three runs of three lines: C1 and C3 expect a code, C2 asks the shipper."""
    ask = {"expected_route": "ask_shipper"}
    return [
        [coolant_row("C1", "2710.19", "auto_accept"), coolant_row("C2", "3820.00", "ask_shipper", **ask),
         coolant_row("C3", "3403.19", "review", expected="3403.99", top3=["3403.19", "3403.99"])],
        [coolant_row("C1", "3403.99", "auto_accept"), coolant_row("C2", "3820.00", "review", **ask),
         coolant_row("C3", "3403.99", "review", expected="3403.99")],
        [coolant_row("C1", "2710.19", "review"), coolant_row("C2", "3820.00", "auto_accept", **ask),
         coolant_row("C3", "3403.19", "review", expected="3403.99", top3=["3403.19"])]]


def test_feature_014a_the_coolant_measures():
    m = ev.coolant_measures(coolant_runs())
    assert m["top1_runs"] == [2, 1, 1]                       # right per run
    assert m["majority_top1"] == 2                           # C1 on its code; C2's three routes tie: run 1's route
    assert m["top3_runs"] == [2, 1, 1]                       # lines with an expected HS-6 only
    assert m["routes_runs"][2] == {"auto_accept": 1, "review": 2, "ask_shipper": 0}
    assert [[w["reference"] for w in run] for run in m["wrong_auto_runs"]] == [[], ["C1"], ["C2"]]
    assert m["wrong_auto_runs"][2][0]["top1"] == "3820.00"   # an "ask the shipper" line auto-accepted is wrong
    assert [(line["id"], line["expected"], line["majority"], line["right"]) for line in m["lines"]] == [
        ("C1", "2710.19", "2710.19", True), ("C2", "ask_shipper", "ask_shipper", True), ("C3", "3403.99", "3403.19", False)]
    assert m["lines"][1]["seen"] == [{"top1": "3820.00", "route": r} for r in ("ask_shipper", "review", "auto_accept")]


def test_feature_014a_the_coolant_report_shows_each_lines_majority_outcome():
    entry = {"iteration": 1, "run_on": "2026-11-18", "tag": "014a-baseline", "set": "coolant", "repeat": 3, "n": 3,
             "model": "m", "expansion": "off", **ev.coolant_measures(coolant_runs()), **ev.gate_measures(coolant_runs()),
             "elapsed_s": 12.0, "cost_usd": 0.01, "cost_eur": 0.0093}
    data = {"built_on": "2026-11-18", "source": "a test", "lines": [
        {"id": "C1", "text": "冷却液 矿物油含量大于70%"}, {"id": "C2", "text": "没有矿物基础油的冷却液"}, {"id": "C3", "text": "*cool*"}]}
    text = ev.render_coolant_report([entry], data)
    assert ("| 1 | 2026-11-18 | 014a-baseline | 3 | off | - | - | 2 / 1 / 1 of 3 | 2/3 | 2 / 1 / 1 | 1 / 1 / 1 | 0 / 1 / 1 | "
            "3 / 3 / 3 |") in text                                       # no customs wording and no floor before them
    assert ("| C2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (review) | 3820.00 (auto_accept) | "
            "ask_shipper | yes |") in text
    assert "| C3 | \\*cool\\* | 3403.99 |" in text and "| 3403.19 | no |" in text


def stub_live_run(monkeypatch, runs):
    """The live parts of a run replaced, so main() runs offline: no store, no model; run_once returns `runs` in turn."""
    from collections import Counter

    client = SimpleNamespace(raw=SimpleNamespace(_model=SimpleNamespace(temperature=None, seed=None)), max_retries=2)
    monkeypatch.setattr(ev, "open_knowledge_base", lambda settings, usage_sink=None: SimpleNamespace(bti_vectors=None))
    monkeypatch.setattr(ev, "get_client", lambda usage_sink=None, settings=None: client)
    monkeypatch.setattr(ev, "price_for_run", lambda client, found: None)
    monkeypatch.setattr(ev, "count_invalid", lambda client: Counter())
    calls = []
    queue = iter(runs)

    def run_once(rulings, kb, client, as_of, workers, expansion=False, leave_one_out=True, customs_wording=False,
                 vote_scope="candidates"):
        calls.append({"references": [r["reference"] for r in rulings], "as_of": as_of, "leave_one_out": leave_one_out,
                      "customs_wording": customs_wording, "vote_scope": vote_scope})
        return next(queue), 1.0

    monkeypatch.setattr(ev, "run_once", run_once)
    return calls


def eval_files_in(tmp_path, monkeypatch):
    for name in ("OUT", "HISTORY", "REPORT", "COOLANT_OUT", "COOLANT_HISTORY", "COOLANT_REPORT", "OUTSIDE_OUT",
                 "OUTSIDE_HISTORY", "OUTSIDE_REPORT"):
        monkeypatch.setattr(ev, name, tmp_path / getattr(ev, name).name)


def test_feature_014a_a_coolant_run_writes_its_own_files_only(tmp_path, monkeypatch):
    copy = coolant_set_copy(tmp_path, monkeypatch)
    before = copy.read_bytes()
    eval_files_in(tmp_path, monkeypatch)
    items = ev.coolant_items(json.loads(before.decode("utf-8")))
    runs = [[coolant_row(i["reference"], "2710.19", "review", expected=i.get("expected_hs6") or "2710.19",
                         expected_route=i.get("expected_route")) for i in items] for _ in range(3)]
    calls = stub_live_run(monkeypatch, runs)
    assert ev.main(["--set", "coolant", "--repeat", "3", "--tag", "t1", "--expansion", "off"]) == 0
    assert [c["leave_one_out"] for c in calls] == [False] * 3                 # no line is a ruling: no leakage guard
    assert calls[0]["as_of"] == date(2026, 11, 18) and calls[0]["references"][0] == "coolant-1"   # on the set's date
    assert ev.COOLANT_OUT.exists() and (tmp_path / "hs6_eval_coolant_t1_en_expansion-off_wording-off.json").exists()
    entry = json.loads(ev.COOLANT_HISTORY.read_text(encoding="utf-8"))[-1]
    assert (entry["iteration"], entry["set"], entry["tag"], entry["n"], entry["repeat"]) == (1, "coolant", "t1", 8, 3)
    assert entry["top1_runs"] == [2, 2, 2] and entry["majority_top1"] == 2   # the two 2710.19 lines
    assert "cross_layer" not in entry                                         # no CN-8 results for these lines
    assert "| coolant-8 | 冷却液 | ask_shipper |" in ev.COOLANT_REPORT.read_text(encoding="utf-8")
    assert not any(p.exists() for p in (ev.OUT, ev.HISTORY, ev.REPORT))      # the 120-line set's files
    assert copy.read_bytes() == before                                        # the set itself is never written


def test_feature_014a_a_coolant_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    coolant_set_copy(tmp_path, monkeypatch)
    eval_files_in(tmp_path, monkeypatch)
    items = ev.coolant_items(json.loads(ev.COOLANT_SET.read_text(encoding="utf-8")))
    stub_live_run(monkeypatch, [[coolant_row(i["reference"], None, "ask_shipper", expected_route="ask_shipper")
                                 for i in items]])
    assert ev.main(["--set", "coolant", "--dry-run"]) == 0
    assert "dry run: nothing written" in capsys.readouterr().out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hs6_eval_coolant_set.json"]


def test_feature_014a_the_120_line_set_stays_the_default_and_names_its_set(tmp_path, monkeypatch):
    eval_files_in(tmp_path, monkeypatch)
    rulings = [{"reference": r, "chapter": "39", "hs6": "3926.90", "cn8": "39269097", "language": "en",
                "description": f"goods {r}"} for r in ("A", "B")]
    test_set = tmp_path / "set.json"
    test_set.write_text(json.dumps({"built_on": "2026-10-23", "rulings": rulings}), encoding="utf-8")
    monkeypatch.setattr(ev, "SET", test_set)
    cn8 = tmp_path / "cn8.json"
    cn8.write_text(json.dumps({"summary": {"iteration": 12}, "rows": [cn8_row(r, "39269097") for r in "AB"]}),
                   encoding="utf-8")
    calls = stub_live_run(monkeypatch, [[{**voted(r, [], top3=["3926.90"]), "route": "review",
                                          "route_by_confidence": "review", "raw_confidence": 90,
                                          **ev.override_fields(voted(r, [], top3=["3926.90"]))} for r in "AB"]])
    assert ev.main(["--tag", "t2", "--cn8", str(cn8)]) == 0
    assert calls[0]["leave_one_out"] is True                                  # each line's own ruling kept out
    entry = json.loads(ev.HISTORY.read_text(encoding="utf-8"))[-1]
    assert (entry["set"], entry["majority_top1"], entry["cross_layer"]["majority"]["hs6_right_cn8_right"]) == ("cn8", 2, 2)
    assert (tmp_path / "hs6_eval_t2_en_expansion-off_wording-off.json").exists()   # since Phase 8: the switch named
    assert not any(p.exists() for p in (ev.COOLANT_OUT, ev.COOLANT_HISTORY, ev.COOLANT_REPORT))


def test_feature_014a_run_once_scores_coolant_lines_with_no_leakage_guard(small_index, fake_embeddings, rules, fake_llm,
                                                                          monkeypatch):
    from agent.llm import get_client
    from rag.loader import KnowledgeBase
    from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch

    coded, plain = "coolant without mineral base oil, for metal working", "冷却液"
    fake_llm.recorded.setdefault("JudgementOut", {})[coded] = {"vague": False, "missing": [], "reason": "specific"}
    fake_llm.recorded.setdefault("RankOut", {})[coded] = {"candidates": [
        {"code": "3926.90", "confidence": 95, "rationale": "r", "history_only": False}]}   # an unrecorded line is vague
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    kb = KnowledgeBase(small_index, HybridRetriever(bm25=BM25Index([(c.id, c.text) for c in small_index.chunks]),
                                                    vectors=vectors, chunks=small_index), BTIStore([]), rules,
                       {"embedding_model": "fake", "built_at": "2026-11-18T00:00:00"}, fake_embeddings)
    guards = []
    classify = ev.classify_lines
    monkeypatch.setattr(ev, "classify_lines", lambda lines, ctx, *a, **k: guards.append(ctx.exclude_refs)
                        or classify(lines, ctx, *a, **k))
    items = ev.coolant_items({"lines": [{"id": "coolant-1", "text": coded, "expected_hs6": "3926.90"},
                                        {"id": "coolant-2", "text": plain, "expected_route": "ask_shipper"}]})
    rows, _ = ev.run_once(items, kb, get_client(), date(2026, 11, 18), workers=1, leave_one_out=False)
    assert guards == [None, None]                                              # nothing is kept out
    assert (rows[0]["top1"], rows[0]["route"], rows[0]["expected_route"], rows[0]["right"]) == (
        "3926.90", "auto_accept", None, True)                                   # no ruling votes: the estimate decides
    assert (rows[1]["flag"], rows[1]["route"], rows[1]["expected"], rows[1]["right"]) == (
        "vague", "ask_shipper", None, True)                                     # right on its route


def test_feature_014a_lang_is_for_the_120_line_set():
    with pytest.raises(SystemExit):
        ev.main(["--set", "coolant", "--lang", "zh", "--dry-run"])


# --------------------------------------------------------------------------- feature 014a: the outside set (2026-11-19)
# 014a/FR-032
TWELVE = {"39", "42", "61", "62", "63", "64", "73", "84", "85", "94", "95", "96"}   # the old store's chapters


def test_feature_014a_the_outside_set_is_coded_sourced_and_outside_the_twelve_chapters():
    raw = ev.OUTSIDE_SET.read_bytes()
    assert b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf")              # LF, UTF-8 without a byte-order mark
    data = json.loads(raw.decode("utf-8"))
    lines = data["lines"]
    assert data["built_on"] == "2026-11-19" and 10 <= len(lines) <= 15
    assert len({line["id"] for line in lines}) == len(lines)
    for line in lines:
        assert len(line["expected_hs6"]) == 7 and line["expected_hs6"][4] == "." and "expected_route" not in line
        assert line["chapter"] == line["expected_hs6"][:2] and line["chapter"] not in TWELVE
        assert line["text"].strip() and line["source"]
        if "ebti" in line["source"]:                       # a line from a ruling: its id is the ruling's reference, which
            assert line["source"]["ebti"] == line["id"]    # the run keeps out (leave-one-out)
            assert line["source"]["valid_from"] <= data["built_on"] <= line["source"]["valid_to"]
    assert len({line["chapter"] for line in lines}) >= 10                             # spread over chapters


def outside_set_copy(tmp_path, monkeypatch):
    """A temporary copy of the outside set that the eval reads instead of the repository's file."""
    copy = tmp_path / "hs6_eval_outside_set.json"
    copy.write_bytes(ev.OUTSIDE_SET.read_bytes())
    monkeypatch.setattr(ev, "OUTSIDE_SET", copy)
    return copy


def test_feature_014a_an_outside_run_keeps_each_source_ruling_out_and_writes_its_own_files(tmp_path, monkeypatch):
    copy = outside_set_copy(tmp_path, monkeypatch)
    before = copy.read_bytes()
    eval_files_in(tmp_path, monkeypatch)
    items = ev.coolant_items(json.loads(before.decode("utf-8")))
    runs = [[coolant_row(i["reference"], i["expected_hs6"], "review", expected=i["expected_hs6"]) for i in items]
            for _ in range(3)]
    calls = stub_live_run(monkeypatch, runs)
    assert ev.main(["--set", "outside", "--repeat", "3", "--tag", "t3", "--expansion", "off"]) == 0
    assert [c["leave_one_out"] for c in calls] == [True] * 3                  # each line's source ruling kept out
    assert calls[0]["references"] == [i["reference"] for i in items] and calls[0]["as_of"] == date(2026, 11, 19)
    assert ev.OUTSIDE_OUT.exists() and (tmp_path / "hs6_eval_outside_t3_en_expansion-off_wording-off.json").exists()
    entry = json.loads(ev.OUTSIDE_HISTORY.read_text(encoding="utf-8"))[-1]
    assert (entry["set"], entry["tag"], entry["n"], entry["majority_top1"]) == ("outside", "t3", len(items), len(items))
    report = ev.OUTSIDE_REPORT.read_text(encoding="utf-8")
    assert report.startswith("# HS-6 evaluation report: the outside set (feature 014a)")
    assert "each line's source ruling is kept out (leave-one-out)" in report and "--set outside" in report
    assert not any(p.exists() for p in (ev.OUT, ev.HISTORY, ev.REPORT, ev.COOLANT_OUT, ev.COOLANT_HISTORY,
                                        ev.COOLANT_REPORT))                    # the other sets' files
    assert copy.read_bytes() == before                                        # the set itself is never written


def test_feature_014a_lang_is_not_for_the_outside_set():
    with pytest.raises(SystemExit):
        ev.main(["--set", "outside", "--lang", "zh", "--dry-run"])


# --------------------------------------------------------------------------- feature 014a: the after-runs' fields and replays
# 014a/FR-005 (the rows' fields), 014a/FR-012 (the floor replay)
def test_feature_014a_vote_hits_keep_each_ruling_once_with_its_similarity_and_eligibility():
    kb = SimpleNamespace(bti=BTIStore([ruling("OWN", "3403.99"), ruling("A", "3403.99"), ruling("LOW", "3403.19"),
                                       ruling("OLD", "3403.19", valid_to="2024-12-31"), ruling("GONE", "9999.99")]),
                         index=SimpleNamespace(get=lambda code: object() if code in ("3403.99", "3403.19") else None))
    searches = [[("bti:OWN", 0.9), ("bti:A", 0.62), ("bti:OLD", 0.41)],
                [("bti:A", 0.70), ("bti:GONE", 0.39), ("bti:LOW", 0.30)]]                # a second query vector
    hits = ev.vote_hits(searches, "OWN", kb, date(2026, 11, 18))
    assert [(h["reference"], h["hs6"], h["similarity"], h["eligible"]) for h in hits] == [
        ("OWN", "3403.99", 0.9, False),        # the line's own ruling
        ("A", "3403.99", 0.7, True),           # once, at its highest similarity
        ("OLD", "3403.19", 0.41, False),       # expired on the day
        ("GONE", "9999.99", 0.39, False),      # coded to a subheading the nomenclature does not have
        ("LOW", "3403.19", 0.3, True)]         # below the floor, still eligible: a replay applies any floor
    assert ev.vote_hits(searches, None, kb, date(2026, 11, 18))[0]["eligible"]            # no line kept out


def test_feature_014a_a_row_keeps_the_scope_the_vote_hits_the_rewrite_and_the_notes(small_index, fake_embeddings, rules,
                                                                                   fake_llm):
    from agent.llm import get_client
    from rag.loader import KnowledgeBase
    from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch

    text = "Silicone mobile phone cases"
    fake_llm.recorded.setdefault("JudgementOut", {})[text] = {"vague": False, "missing": [], "reason": "specific"}
    fake_llm.recorded.setdefault("WordingOut", {})[text] = {"text": "Schutzhüllen für Mobiltelefone, aus Silikon"}
    fake_llm.recorded.setdefault("RankOut", {})[text] = {"candidates": [
        {"code": "3926.90", "confidence": 90, "rationale": "Like FRBTI3, a fitted cover.", "history_only": False},
        {"code": "4202.21", "confidence": 40, "rationale": "a case", "history_only": False}]}
    records = [{**ruling(ref, code), "chapter": code[:2], "language": "de"} for ref, code in
               (("IEBTI1", "3926.90"), ("DEBTI2", "3926.90"), ("FRBTI3", "4202.21"), ("XIBTI4", "8452.90"))]
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    kb = KnowledgeBase(small_index, HybridRetriever(bm25=BM25Index([(c.id, c.text) for c in small_index.chunks]),
                                                    vectors=vectors, chunks=small_index), BTIStore(records), rules,
                       {"embedding_model": "fake", "built_at": "2026-11-18T00:00:00"}, fake_embeddings)

    class Scoped:
        hits = [("bti:XIBTI4", 0.95), ("bti:IEBTI1", 0.80), ("bti:DEBTI2", 0.70), ("bti:FRBTI3", 0.60)]

        def search_by_vector(self, vector, k, chapter_filter=None, where=None):
            return [(i, s) for i, s in self.hits if not chapter_filter or kb.bti.get(i)["chapter"] in chapter_filter][:k]

    kb.bti_vectors = Scoped()
    item = {"reference": "coolant-x", "chapter": "39", "language": "", "description": text, "expected_hs6": "3926.90"}
    row = ev.run_once([item], kb, get_client(), date(2026, 11, 18), workers=1, leave_one_out=False, customs_wording=True)[0][0]
    assert (row["vote_chapters"], row["not_indexed"]) == (["39", "42"], [])
    assert [h["reference"] for h in row["vote_hits"]] == ["IEBTI1", "DEBTI2", "FRBTI3"]           # never the machine
    assert all(h["eligible"] for h in row["vote_hits"]) and row["vote_hits"][0]["similarity"] == 0.8
    assert row["customs_wording"] == "Schutzhüllen für Mobiltelefone, aus Silikon"
    assert row["citation_notes"] == [{"code": "3926.90", "notes": [
        {"reference": "FRBTI3", "kind": "other_code", "ruling_hs6": "4202.21"}]}]
    assert row["nearest_hits"][0]["reference"] == "XIBTI4"                     # the proposal's search over every chapter


def test_feature_014a_the_customs_wording_option_is_kept_in_the_entry_and_the_file_name(tmp_path, monkeypatch):
    from agent.config import HS6_VOTE_MIN_SIMILARITY

    coolant_set_copy(tmp_path, monkeypatch)
    eval_files_in(tmp_path, monkeypatch)
    items = ev.coolant_items(json.loads(ev.COOLANT_SET.read_text(encoding="utf-8")))
    rows = [coolant_row(i["reference"], "3403.99", "review", expected=i.get("expected_hs6") or "3403.99",
                        expected_route=i.get("expected_route")) for i in items]
    calls = stub_live_run(monkeypatch, [rows, rows])
    assert ev.main(["--set", "coolant", "--tag", "t3", "--expansion", "off", "--customs-wording", "on"]) == 0
    assert calls[0]["customs_wording"] is True
    entry = json.loads(ev.COOLANT_HISTORY.read_text(encoding="utf-8"))[-1]
    assert (entry["customs_wording"], entry["floor"]) == ("on", HS6_VOTE_MIN_SIMILARITY)
    assert (tmp_path / "hs6_eval_coolant_t3_en_expansion-off_wording-on.json").exists()
    assert ev.main(["--set", "coolant", "--tag", "t4", "--expansion", "off", "--customs-wording", "off"]) == 0
    assert calls[1]["customs_wording"] is False and (tmp_path / "hs6_eval_coolant_t4_en_expansion-off_wording-off.json").exists()


def hit(reference, hs6, similarity, eligible=True):
    return {"reference": reference, "hs6": hs6, "similarity": similarity, "eligible": eligible}


def replayable(reference, hits, confidence=90, expected="3403.99"):
    """A coolant row as an after-run writes it, its route the run's (floor 0.40), with its vote_hits and the same rulings
    as its nearest_hits (rule (a): the gate's vote reads those)."""
    nearest = [{"reference": h["reference"], "hs6": h["hs6"], "distance": round(1 - h["similarity"], 6), "country": "",
                "eligible": h["eligible"]} for h in hits]
    r = {**coolant_row(reference, "3403.99", "review", expected=expected, top3=["3403.99", "2710.19"], confidence=confidence),
         "flag": "ok", "vote_hits": hits, "nearest_hits": nearest, "vote": None}
    return r


def write_source(tmp_path, rows, set_name="coolant", **summary) -> str:
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"summary": {"iteration": 3, "tag": "014a-after", "model": "m", "set": set_name, "repeat": 1,
                                              "n": len(rows), "floor": 0.40, "customs_wording": "off", **summary},
                                  "rows": rows}), encoding="utf-8")
    return str(source)


def no_model(monkeypatch):
    from agent.llm import set_client_factory

    def refuse():
        raise AssertionError("a replay makes no model call")

    set_client_factory(refuse)
    monkeypatch.setattr(ev, "open_knowledge_base", lambda *a, **k: pytest.fail("a replay opens no knowledge base"))


def test_feature_014a_a_floor_replay_rebuilds_each_vote_with_no_model_call(tmp_path, monkeypatch, capsys):
    from agent.llm import set_client_factory

    coolant_set_copy(tmp_path, monkeypatch)
    eval_files_in(tmp_path, monkeypatch)
    no_model(monkeypatch)
    rows = [replayable("A", [hit("R1", "3403.99", 0.60), hit("R2", "2710.19", 0.44)]),    # a tie at 0.40, agrees at 0.45
            replayable("B", [hit("R3", "3403.99", 0.42)], confidence=70)]                  # no voter left at 0.45
    try:
        source = write_source(tmp_path, rows)
        assert ev.main(["--replay", source, "--floor", "0.45", "--tag", "floor045"]) == 0
    finally:
        set_client_factory(None)
    replayed = json.loads((tmp_path / "hs6_eval_coolant_floor045.json").read_text(encoding="utf-8"))["rows"]
    assert [(r["route"], r["gate"]) for r in replayed] == [("auto_accept", "vote_agrees"), ("review", "no_rulings")]
    assert replayed[0]["vote"]["counts"] == [["3403.99", 1]] and replayed[1]["vote"] is None   # 0.44 and 0.42 dropped
    assert replayed[0]["scoped_vote"]["counts"] == [["3403.99", 1]] and replayed[1]["scoped_vote"] is None
    entry = json.loads(ev.COOLANT_HISTORY.read_text(encoding="utf-8"))[-1]                     # the coolant set's history
    assert (entry["set"], entry["floor"], entry["replay"]) == ("coolant", 0.45, {"of": "source.json", "floor": 0.45,
                                                                                 "exact": True})
    assert (entry["routes_runs"], [len(w) for w in entry["wrong_auto_runs"]]) == (
        [{"auto_accept": 1, "review": 1, "ask_shipper": 0}], [0])
    assert entry["no_voter_runs"] == [1] and entry["cost_eur"] == 0.0 and entry["customs_wording"] == "off"
    assert not ev.HISTORY.exists() and not ev.COOLANT_OUT.exists()            # no 120-line file, no latest paid run
    assert "floor 0.45" in ev.COOLANT_REPORT.read_text(encoding="utf-8")


def test_feature_014a_a_replay_below_the_runs_floor_is_marked_not_exact(tmp_path, monkeypatch):
    coolant_set_copy(tmp_path, monkeypatch)
    eval_files_in(tmp_path, monkeypatch)
    no_model(monkeypatch)
    source = write_source(tmp_path, [replayable("A", [hit("R1", "3403.99", 0.60)])])
    assert ev.main(["--replay", source, "--floor", "0.35", "--override-min", "4"]) == 0
    entry = json.loads(ev.COOLANT_HISTORY.read_text(encoding="utf-8"))[-1]
    assert entry["replay"]["exact"] is False and entry["override_min"] == 4                 # combined with --override-min


def test_feature_014a_a_120_line_replay_writes_the_120_line_history(tmp_path, monkeypatch):
    eval_files_in(tmp_path, monkeypatch)
    no_model(monkeypatch)
    rows = [{**r, "route_by_confidence": r["route"], "vote_hits": [hit("R1", "3926.90", 0.6)], "nearest_hits": []}
            for r in REPLAYED]
    source = write_source(tmp_path, rows, set_name="cn8")
    refs = [r["reference"] for r in json.loads(ev.SET.read_text(encoding="utf-8"))["rulings"]] + list("ABCDE")
    cn8 = tmp_path / "cn8.json"
    cn8.write_text(json.dumps({"summary": {"iteration": 12}, "rows": [cn8_row(r, "39269097") for r in refs]}), encoding="utf-8")
    assert ev.main(["--replay", source, "--floor", "0.5", "--cn8", str(cn8)]) == 0
    entry = json.loads(ev.HISTORY.read_text(encoding="utf-8"))[-1]
    assert (entry["set"], entry["floor"], entry["replay"]["of"]) == ("cn8", 0.5, "source.json")
    assert "cross_layer" in entry and not ev.COOLANT_HISTORY.exists()


def test_feature_014a_a_file_without_vote_hits_is_refused(tmp_path, monkeypatch):
    eval_files_in(tmp_path, monkeypatch)
    no_model(monkeypatch)
    source = write_source(tmp_path, [coolant_row("A", "3403.99", "review")])               # a baseline row
    with pytest.raises(SystemExit):
        ev.main(["--replay", source, "--floor", "0.45"])
    with pytest.raises(SystemExit):
        ev.main(["--floor", "0.45"])                                                       # a floor is for a replay


# --------------------------------------------------------------------------- the 014a regression ablation (eval only)
# 014a/FR-005, 014a/FR-011: the rows keep both votes of rule (a), and the gate's vote reads every chapter
def test_the_unscoped_vote_drops_only_the_vote_searchs_chapter_filter():
    calls = []

    def search(vector, k, chapter_filter=None, where=None):
        calls.append((k, chapter_filter))
        return [(f"bti:R{i}", 1 - i / 100) for i in range(k)]

    ev._rec.searches, ev._rec.vote_searches = [], []
    try:
        ev._logged(search, unscoped=True)([1.0], 12, ["61"])                 # the vote's search: over every chapter
        ev._logged(search, unscoped=True)([1.0], 12, None)                   # the proposal's search, as before
        assert calls == [(12, None), (12, None), (ev.HITS_LOGGED, None)]
        assert [len(s) for s in ev._rec.vote_searches] == [12]               # still logged as the vote's rulings
        ev._logged(search)([1.0], 12, ["61"])                                # the product's scope by default
        assert calls[-1] == (12, ["61"])
    finally:
        del ev._rec.searches, ev._rec.vote_searches


def test_the_gate_votes_over_every_chapter_and_the_vote_scope_option_widens_the_second_vote(small_index, fake_embeddings,
                                                                                            rules, fake_llm):
    from agent.llm import get_client
    from rag.loader import KnowledgeBase
    from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch

    text = "Silicone mobile phone cases"
    fake_llm.recorded.setdefault("JudgementOut", {})[text] = {"vague": False, "missing": [], "reason": "specific"}
    fake_llm.recorded.setdefault("RankOut", {})[text] = {"candidates": [
        {"code": "3926.90", "confidence": 90, "rationale": "a fitted cover", "history_only": False}]}
    records = [{**ruling(ref, code), "chapter": code[:2], "language": "de"} for ref, code in
               (("XIBTI4", "8452.90"), ("XIBTI5", "8452.90"), ("XIBTI6", "8452.90"), ("IEBTI1", "3926.90"))]
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    kb = KnowledgeBase(small_index, HybridRetriever(bm25=BM25Index([(c.id, c.text) for c in small_index.chunks]),
                                                    vectors=vectors, chunks=small_index), BTIStore(records), rules,
                       {"embedding_model": "fake", "built_at": "2026-11-18T00:00:00"}, fake_embeddings)

    class Scoped:
        hits = [("bti:XIBTI4", 0.95), ("bti:XIBTI5", 0.94), ("bti:XIBTI6", 0.93), ("bti:IEBTI1", 0.80)]

        def search_by_vector(self, vector, k, chapter_filter=None, where=None):
            return [(i, s) for i, s in self.hits if not chapter_filter or kb.bti.get(i)["chapter"] in chapter_filter][:k]

    kb.bti_vectors = Scoped()
    item = {"reference": "coolant-x", "chapter": "39", "language": "", "description": text, "expected_hs6": "3926.90"}
    scoped = ev.run_once([item], kb, get_client(), date(2026, 11, 18), workers=1, leave_one_out=False)[0][0]
    unscoped = ev.run_once([item], kb, get_client(), date(2026, 11, 18), workers=1, leave_one_out=False,
                           vote_scope="all")[0][0]
    assert scoped["vote"]["counts"] == [["8452.90", 3], ["3926.90", 1]] and scoped["route"] == "review"   # rule (a)
    assert scoped["scoped_vote"]["counts"] == [["3926.90", 1]]                       # the second vote, which cannot accept
    assert unscoped["scoped_vote"]["counts"] == [["8452.90", 3], ["3926.90", 1]] and unscoped["route"] == "review"
    assert [h["reference"] for h in unscoped["vote_hits"]] == ["XIBTI4", "XIBTI5", "XIBTI6", "IEBTI1"]
    assert unscoped["vote_chapters"] == ["39"]                                # the candidates' chapters, as computed


def test_the_vote_scope_option_reaches_the_run_and_the_entry(tmp_path, monkeypatch):
    coolant_set_copy(tmp_path, monkeypatch)
    eval_files_in(tmp_path, monkeypatch)
    items = ev.coolant_items(json.loads(ev.COOLANT_SET.read_text(encoding="utf-8")))
    rows = [coolant_row(i["reference"], "3403.99", "review", expected=i.get("expected_hs6") or "3403.99",
                        expected_route=i.get("expected_route")) for i in items]
    calls = stub_live_run(monkeypatch, [rows, rows])
    assert ev.main(["--set", "coolant", "--tag", "t5", "--expansion", "off", "--vote-scope", "all"]) == 0
    assert ev.main(["--set", "coolant", "--tag", "t6", "--expansion", "off"]) == 0
    assert [c["vote_scope"] for c in calls] == ["all", "candidates"]
    history = json.loads(ev.COOLANT_HISTORY.read_text(encoding="utf-8"))
    assert history[0]["vote_scope"] == "all" and "vote_scope" not in history[1]   # the product's scope keeps no field
    with pytest.raises(SystemExit):
        ev.main(["--replay", str(tmp_path / "any.json"), "--vote-scope", "all"])
