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


# --------------------------------------------------------------------------- feature 008: the precedent override
def full(r, top1="3926.90", supported=None, fired=False, chosen_rank=1, cn8_top1=None):
    """A row with every field line_row writes; `fired`: the override chose the row's HS-6 over `top1`."""
    r = {**r, "top1": top1, "written": r["route"] == "auto_accept", "cn8_error": None,
         "cn8_gate": "vote_agrees" if r["cn8"] else None, "written_hit": r["hit"] if r["route"] == "auto_accept" else None,
         "supported": {"rank": supported, "right": None if supported is None else r["hs6"] == r["expected_hs6"]},
         "override": {"fired": fired, "rank": chosen_rank if r["hs6"] else None, "code": r["hs6"] if fired else None,
                      "n": 4 if fired else None, "m": 5 if fired else None}, "cn8_top1": cn8_top1}
    r["hs6_hit"] = top1 == r["expected_hs6"]
    return {**r, "off": ev.off_block(r)}


TOP1_TOY = {"cn8": "95030035", "written": True, "question": None, "error": None, "gate": "vote_agrees"}
A8 = full(row("A", "39269097", "auto_accept"), top1="9503.00", supported=2, fired=True, chosen_rank=2, cn8_top1=TOP1_TOY)
B8 = full(row("B", "39269097", "auto_accept", expected="95030035", hs6="3926.90"), top1="9503.00", supported=2, fired=True,
          chosen_rank=2, cn8_top1=TOP1_TOY)                                    # the override chose the wrong HS-6
C8 = full(row("C", "39269097", "auto_accept"))                                  # no override


def test_feature_008_the_switch_off_replays_an_override_row_from_the_same_answers():
    assert A8["off"] == {"hs6": "9503.00", "hs6_by": "clerk", "cn8": "95030035", "written": True, "question": None,
                         "cn8_error": None, "cn8_gate": "vote_agrees", "route": "review", "hit": False, "written_hit": None,
                         "origin": "hs6_wrong"}
    assert (B8["origin"], B8["off"]["hit"], B8["off"]["origin"]) == ("hs6_wrong", True, None)
    asked = full(row("D", "39269097", "auto_accept"), top1="9503.00", supported=2, fired=True, chosen_rank=2,
                 cn8_top1={**TOP1_TOY, "cn8": None, "written": False, "question": "Ask the shipper for: the use"})
    assert (asked["off"]["cn8"], asked["off"]["route"], asked["off"]["origin"]) == (None, "review", "hs6_wrong")


def test_feature_008_a_row_without_an_override_is_the_same_in_both_states():
    assert C8["off"] == {k: C8[k] for k in ev.OFF_FIELDS}


def test_feature_008_the_measures_and_the_report_show_the_switch_off_against_on():
    runs = [[A8, B8, C8]]
    o = ev.override_measures(runs, 4)
    assert o["override_min"] == 4
    assert (o["off"]["right_runs"], o["off"]["routes_runs"], o["off"]["wrong_auto_runs"]) == (
        [2], [{"auto_accept": 1, "review": 2, "ask_shipper": 0}], [[]])
    assert [(x["reference"], x["chosen"], x["rank"], x["hs6_right"]) for x in o["overrides_runs"][0]] == [
        ("A", "3926.90", 2, True), ("B", "3926.90", 2, False)]
    assert o["supported_runs"] == [{"lines": 2, "right": 1}]
    entry = {"iteration": 2, "run_on": "2026-10-26", "tag": "e2e-override", "model": "m", "repeat": 1, **ev.measures(runs),
             **o, "upload_s_runs": [100.0], "elapsed_s_runs": [130.0], "elapsed_s": 130.0, "cost_usd": 0.3,
             "cost_eur": 0.28, "cost_eur_runs": [0.28]}
    text = ev.render_report([entry], {"built_on": "2026-10-23", "rulings": [{}] * 3})
    assert "### Precedent override (feature 008)" in text
    assert "| 1 | off | 2/3 | 1 | 0 | 2 | 0 |" in text and "| 1 | on | 2/3 | 3 | 1 | 0 | 0 |" in text
    assert "Overrides that fired per run: 2, of which chose the right HS-6: 1." in text
    assert "on 2 lines per run; that candidate was the right HS-6 on 1." in text
    assert ("- run 1: A (expected 39269097): off 95030035 under 9503.00 (review, wrong); on 39269097 under 3926.90, "
            "candidate 2 (auto_accept, right)") in text


E8 = full(row("E", "39269097", "auto_accept"), top1="9503.00", supported=2, fired=True, chosen_rank=2, cn8_top1=TOP1_TOY)
E8 = {**E8, "override": {**E8["override"], "n": 5}}                           # 5 of 5: it fires at 5 too


def test_feature_008_a_replay_at_a_higher_minimum_turns_the_weaker_overrides_off():
    a, b, c, e = (ev.replay_row(r, 5) for r in (A8, B8, C8, E8))
    assert a == {**A8, **A8["off"], "hs6_gate": "vote_disagrees", "hs6_route": "review", "hs6_reason": None,
                 "override": {"fired": False, "rank": 1, "code": None, "n": None, "m": None}}
    assert (b["hit"], b["route"], b["origin"]) == (True, "review", None)       # B's wrong override is gone
    assert c is C8 and e is E8
    o = ev.override_measures([[a, b, c, e]], 5)
    assert o["override_min"] == 5 and [x["reference"] for x in o["overrides_runs"][0]] == ["E"]
    assert o["off"] == ev.override_measures([[A8, B8, C8, E8]])["off"]          # the switch off stays as stored


def test_feature_008_a_replay_makes_no_model_call_and_can_only_raise_the_minimum(tmp_path, monkeypatch):
    for name in ("OUT", "HISTORY", "REPORT"):
        monkeypatch.setattr(ev, name, tmp_path / getattr(ev, name).name)
    source = tmp_path / "e2e_eval_run.json"
    source.write_text(json.dumps({"summary": {"iteration": 3, "tag": "run", "model": "m", "repeat": 1, "override_min": 4,
                                              "parse": {"retry_limit": 2, "runs": [{"retries": 0, "failed_calls": 0,
                                                                                    "failed_lines": 0}]}},
                                  "rows": [A8, B8, C8, E8]}), encoding="utf-8")
    with pytest.raises(SystemExit):   # the run asked the CN-8 step under the top candidate only where 4 overrode
        ev.main(["--replay", str(source), "--override-min", "3"])
    assert ev.main(["--replay", str(source), "--override-min", "5", "--tag", "run-min5"]) == 0
    assert not ev.OUT.exists()                                                  # the latest paid run's file stays
    replayed = json.loads((tmp_path / "e2e_eval_run-min5.json").read_text(encoding="utf-8"))
    assert [r["override"]["fired"] for r in replayed["rows"]] == [False, False, False, True]
    entry = json.loads(ev.HISTORY.read_text(encoding="utf-8"))[-1]
    assert (entry["tag"], entry["replay_of"], entry["override_min"], entry["right_runs"], entry["off"]["right_runs"],
            entry["cost_eur"]) == ("run-min5", {"iteration": 3, "tag": "run"}, 5, [3], [2], 0.0)
    assert "Replay of iteration 3 (run) at OVERRIDE_MIN 5" in ev.REPORT.read_text(encoding="utf-8")


def test_feature_008_the_minimum_is_for_a_replay():
    with pytest.raises(SystemExit):
        ev.main(["--override-min", "5"])
