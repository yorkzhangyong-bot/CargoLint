"""tests/eval/e2e_eval.py offline: the set as an uploaded file's rows, where a line that is not right end to end went
wrong, the measures over repeated runs and the report."""
from __future__ import annotations

import json

import pytest

from tests.eval import e2e_eval as ev

pytestmark = pytest.mark.unit


def test_the_set_enters_as_an_uploaded_files_rows():
    rulings = json.loads(ev.SET.read_text(encoding="utf-8"))["rulings"]
    lines = ev.upload(rulings)
    assert len(lines) == 120 and sum(line.truncated for line in lines) == 71   # every clerk input path cuts at 300
    assert all(line.text_en == r["description"][:300] and line.text_zh == "" for line, r in zip(lines, rulings))
    mixed, long = ev.upload([{"description": "硅胶手机壳 / Silicone mobile phone cases"}, {"description": "x" * 301}])
    assert (mixed.text_zh, mixed.text_en, mixed.truncated) == ("硅胶手机壳", "Silicone mobile phone cases", False)
    assert (len(long.text_en), long.truncated) == (300, True)


def outcome(**fields):
    row = {"hit": False, "hs6": "3926.90", "expected_hs6": "3926.90", "status": "checked", "flag": "ok", "question": None,
           "cn8": "39269097"}
    return ev.origin({**row, **fields})


def test_where_a_line_went_wrong():
    assert outcome(hit=True) is None
    assert outcome(hs6=None, status="failed", flag="failed") == "hs6_failed"
    assert outcome(hs6=None, flag="vague") == "hs6_flagged"
    assert outcome(hs6=None) == "hs6_no_candidate"
    assert outcome(hs6="9503.00") == "hs6_wrong"           # whatever the CN-8 step did under it
    assert outcome(cn8=None, question="Ask the shipper for: the material") == "cn8_asked"
    assert outcome(cn8="39269050") == "cn8_wrong"
    assert outcome(cn8=None) == "cn8_failed"


def row(reference, cn8, route, hs6="3926.90", hs6_by="gate", cut=False, expected="39269097"):
    r = {"reference": reference, "expected_cn8": expected, "expected_hs6": f"{expected[:4]}.{expected[4:6]}", "cn8": cn8,
         "hs6": hs6, "hs6_by": hs6_by, "route": route, "cut": cut, "status": "checked",
         "flag": "ok" if hs6 or route != "ask_shipper" else "vague", "question": None}
    r["hs6_hit"] = hs6 == r["expected_hs6"]
    r["hit"] = cn8 == expected
    r["origin"] = ev.origin(r)
    return r


A = [row("A", "39269097", "auto_accept")] * 3                                # right, auto-accepted, in every run
B = [row("B", "95030010", "auto_accept", hs6="9503.00"),                     # a wrong HS-6 auto-accepted ...
     row("B", "39269097", "review", hs6_by="clerk"),                         # ... right once, after the clerk's pick
     row("B", "95030010", "auto_accept", hs6="9503.00")]
C = [row("C", None, "ask_shipper", hs6=None, hs6_by=None)] * 3               # flagged in every run
D = [row("D", "39269050", "review", cut=True), row("D", "39269050", "review", cut=True),   # a wrong CN-8 twice
     row("D", "39269097", "review", cut=True)]
RUNS = [list(seen) for seen in zip(A, B, C, D)]


def test_measures_over_three_runs():
    m = ev.measures(RUNS)
    assert (m["right_runs"], m["majority_right"], m["majority_origin"]) == ([1, 2, 2], 1, {"hs6": 2, "cn8": 1})
    assert m["routes_runs"] == [{"auto_accept": 2, "review": 1, "ask_shipper": 1},
                                {"auto_accept": 1, "review": 2, "ask_shipper": 1},
                                {"auto_accept": 2, "review": 1, "ask_shipper": 1}]
    assert [[w["reference"] for w in run] for run in m["wrong_auto_runs"]] == [["B"], [], ["B"]]
    assert m["wrong_auto_runs"][0][0] == {"reference": "B", "expected": "39269097", "cn8": "95030010", "hs6": "9503.00",
                                          "origin": "hs6_wrong"}
    assert m["right_auto_runs"] == [1, 1, 1]
    assert [{k: v for k, v in o.items() if v} for o in m["origin_runs"]] == [
        {"hs6_wrong": 1, "hs6_flagged": 1, "cn8_wrong": 1}, {"hs6_flagged": 1, "cn8_wrong": 1},
        {"hs6_wrong": 1, "hs6_flagged": 1}]
    assert (m["hs6_top1_runs"], m["hs6_wrong_auto_runs"]) == ([2, 3, 2], [1, 0, 1])
    assert m["cn8_after_right_hs6_runs"] == [[1, 2], [2, 3], [2, 2]]   # right CN-8 of the lines whose HS-6 was right
    assert (m["cut"], m["cut_right_runs"], m["uncut_right_runs"]) == (1, [0, 0, 1], [1, 2, 1])
    assert (m["same_cn8"], m["same_route"], m["n"]) == (2, 3, 4)          # A and C; A, C and D
    assert m["always_wrong"] == [{"reference": "C", "expected": "39269097", "seen": [
        {"cn8": None, "route": "ask_shipper", "origin": "hs6_flagged"}] * 3}]


def test_the_report_shows_the_entry():
    entry = {"iteration": 1, "run_on": "2026-10-26", "tag": "e2e-test", "model": "m", "repeat": 3, **ev.measures(RUNS),
             "parse": {"retry_limit": 2, "runs": [{"retries": 1, "failed_calls": 0, "failed_lines": 0}] * 3},
             "upload_s_runs": [100.0, 110.0, 105.0], "elapsed_s_runs": [130.0, 140.0, 135.0], "elapsed_s": 405.0,
             "cost_usd": 0.9, "cost_eur": 0.8, "cost_eur_runs": [0.27, 0.27, 0.26]}
    text = ev.render_report([entry], {"built_on": "2026-10-23", "rulings": [{}] * 4})
    assert ("| 1 | 2026-10-26 | e2e-test | m | 3 | 1 / 2 / 2 of 4 | 1/4 | 2 / 1 / 2 | 1 / 0 / 1 | 1 / 2 / 1 | 1 / 1 / 1 | "
            "$0.9000 (€0.8000), 405 s |") in text
    assert "| 1 | 1/4 | 2 | 1 | 1 | 1 | 2 (1 / 1 / 0 / 0) | 1 (1 / 0 / 0) | 100 s, 130 s | €0.2700 |" in text
    assert "1 of 4 right end to end; of the 3 others, 2 went wrong at the HS-6 step and 1 at the CN-8 step" in text
    assert "the CN-8 right where the HS-6 it ran on was right in 1 of 2 / 2 of 3 / 2 of 2" in text
    assert "- B (expected 39269097): runs 1, 3: 95030010 under 9503.00, wrong HS-6\n" in text
    assert "### Lines wrong in every run (1)" in text
    assert "- C (expected 39269097): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run\n" in text


@pytest.mark.parametrize("argv", [["--tag", "a/b"], ["--tag", "two words"], ["--limit", "3"], ["--repeat", "0"]])
def test_bad_arguments_stop_before_anything_runs(argv):
    with pytest.raises(SystemExit):   # the offline guard would fail a test that reached OpenRouter
        ev.main(argv)
