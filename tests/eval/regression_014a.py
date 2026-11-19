"""The 014a regression analysis, docs/reports/014a-regression-analysis.md: the numbers of its tables, read from the
logged rows and history entries of the baseline (120-line iteration 12, coolant 1), the switch-off after-run (13,
coolant 2) and the ablation (the vote over every chapter, --vote-scope all: 19, coolant 7), with no model call.

    python tests/eval/regression_014a.py            # prints every table of the report

Every route is recomputed by the product's routing functions (route_line, hs6_gate, hs6_choice) from what a row keeps:
its flag, status, confidence, top 3 and a vote. The vote is the row's own (replayed from its counts), the unscoped
5-nearest vote rebuilt from its nearest_hits (the vote before feature 014a), or a proposal's rule. The logged votes'
measures are checked against the history entries before anything is printed. Sections 1 to 4 route as the runs did:
until the vague rule of 2026-11-19 a vague line at or above the ask floor went to review. Section 5, the measurement
of rule (a) and option (c) decided that day, routes by today's rules and reads its numbers from the history entries of
the replays and runs it names, after checking the replays against its own (rule_a_now).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import (ASK_FLOOR, DEFAULT_THRESHOLD, HS6_VOTE_K, HS6_VOTE_MIN_SIMILARITY,  # noqa: E402
                          OVERRIDE_MIN)
from agent.routing import hs6_choice, hs6_gate, hs6_ruling_vote, route_line  # noqa: E402
from agent.schemas import FlagKind, Route  # noqa: E402
from rag.bti import TARGET_CHAPTERS  # noqa: E402

EVAL = ROOT / "tests" / "eval"
TWELVE = set(TARGET_CHAPTERS)
SEARCHED = 12                       # the rulings a ruling search reads per query vector (2 × RETRIEVAL_K)
FILES = {"cn8": {"baseline": "hs6_eval_014a-baseline_en_expansion-off.json",
                 "after": "hs6_eval_014a-after_en_expansion-off_wording-off.json",
                 "ablation": "hs6_eval_014a-ablation_en_expansion-off_wording-off.json"},
         "coolant": {"baseline": "hs6_eval_coolant_014a-baseline_en_expansion-off.json",
                     "after": "hs6_eval_coolant_014a-after_en_expansion-off_wording-off.json",
                     "ablation": "hs6_eval_coolant_014a-ablation_en_expansion-off_wording-off.json"}}
HISTORY = {"cn8": "hs6_eval_history.json", "coolant": "hs6_eval_coolant_history.json"}
TAGS = {"baseline": ("014a-baseline", None), "after": ("014a-after", "off"), "ablation": ("014a-ablation", "off")}
SETS = ("cn8", "coolant")
WHICH = ("baseline", "after", "ablation")


# --------------------------------------------------------------------------- loading
def runs_of(set_name: str, which: str) -> list[list[dict]]:
    data = json.loads((EVAL / FILES[set_name][which]).read_text(encoding="utf-8"))
    return data.get("runs") or [data["rows"]]


def entry_of(set_name: str, which: str) -> dict:
    tag, wording = TAGS[which]
    history = json.loads((EVAL / HISTORY[set_name]).read_text(encoding="utf-8"))
    return [h for h in history if h.get("tag") == tag and h.get("customs_wording") == wording and not h.get("replay")][-1]


def majority(values: list) -> object:
    """The most frequent value; a tie goes to the value seen first (the earliest run), as the evaluation's."""
    counts = Counter(values)
    return next(v for v in values if counts[v] == max(counts.values()))


# --------------------------------------------------------------------------- votes and routes
def logged_vote(row: dict):
    """The row's own vote, from its counts, as the routing functions take it (the rulings' countries do not route)."""
    v = row["vote"]
    return None if v is None else hs6_ruling_vote([(code, "") for code, k in v["counts"] for _ in range(k)], row["top3"])


def unscoped_voters(row: dict) -> list[dict]:
    """The rulings of the vote before feature 014a: the 5 nearest eligible ones at or above the floor among the 12 the
    unfiltered ruling search read, from the row's nearest_hits (the same query vector, nearest first)."""
    return [h for h in row["nearest_hits"][:SEARCHED]
            if h["eligible"] and 1 - h["distance"] >= HS6_VOTE_MIN_SIMILARITY][:HS6_VOTE_K]


def unscoped_vote(row: dict):
    return hs6_ruling_vote([(h["hs6"], "") for h in unscoped_voters(row)], row["top3"]) if row["top3"] else None


def scoped_voters_from_nearest(row: dict) -> list[dict]:
    """The scoped vote's rulings as the nearest_hits (the 40 nearest over every chapter) give them: the 5 nearest
    eligible ones at or above the floor within the row's vote chapters (a check of the logged scoped vote)."""
    chapters = set(row.get("vote_chapters") or [])
    return [h for h in row["nearest_hits"] if h["hs6"][:2] in chapters and h["eligible"]
            and 1 - h["distance"] >= HS6_VOTE_MIN_SIMILARITY][:HS6_VOTE_K]


def decide(row: dict, vote, override: bool) -> tuple[str, str | None]:
    """(route, decided HS-6) of a row under `vote`, by the product's routing functions; the precedent override on or
    off. Without an auto-accept the decided code is the top-1, as the clerk sees it. A vague line at or above the ask
    floor goes to review, as when the runs were made (the vague rule of 2026-11-19 sends it to ask the shipper)."""
    kind = None if row["flag"] == "failed" else FlagKind(row["flag"])
    conf = row["confidence"]
    omin = OVERRIDE_MIN if override else None
    route, _ = route_line(kind, conf, row["status"], kind not in (None, FlagKind.ok), DEFAULT_THRESHOLD, ASK_FLOOR,
                          hs6_vote=vote, hs6_override_min=omin)
    if kind == FlagKind.vague and conf is not None and conf >= ASK_FLOOR:   # the runs' routing until 2026-11-19
        route = Route.review
    gated = row["status"] == "checked" and kind == FlagKind.ok and (conf or 0) > 0
    gate = hs6_gate(conf, DEFAULT_THRESHOLD, vote, omin)[1] if gated else None
    _, chosen = hs6_choice([SimpleNamespace(code=c) for c in row["top3"]], vote, gate)
    return route.value, chosen


def expected(row: dict) -> str | None:
    return row.get("expected_route") or row["expected"]


def outcome(row: dict, route: str, chosen: str | None) -> object:
    """What a row is scored on: its route for a coolant line expecting "ask the shipper", else its decided HS-6."""
    return route if row.get("expected_route") else chosen


def measures(runs: list[list[dict]], rule) -> dict:
    """Majority right, right per run, auto-accepted and wrong auto-accepted per run, with `rule(row)` giving each row's
    (route, decided HS-6)."""
    decided = [[(r, *rule(r)) for r in run] for run in runs]
    right_runs = [sum(outcome(r, route, chosen) == expected(r) for r, route, chosen in run) for run in decided]
    auto_runs = [sum(route == "auto_accept" for _, route, _ in run) for run in decided]
    wrong_runs = [sum(route == "auto_accept" and outcome(r, route, chosen) != expected(r) for r, route, chosen in run)
                  for run in decided]
    maj = sum(majority([outcome(r, route, chosen) for r, route, chosen in seen]) == expected(seen[0][0])
              for seen in zip(*decided))
    return {"majority": maj, "right_runs": right_runs, "auto_runs": auto_runs, "wrong_runs": wrong_runs}


def logged(override: bool):
    return lambda row: decide(row, logged_vote(row), override)


def unscoped(override: bool):
    return lambda row: decide(row, unscoped_vote(row), override)


def check_against_history() -> None:
    """The logged votes' measures equal the history entries' (switch off; and on, where an entry has its `on` block)."""
    for set_name in SETS:
        for which in WHICH:
            e, runs = entry_of(set_name, which), runs_of(set_name, which)
            m = measures(runs, logged(False))
            assert m["majority"] == e["majority_top1"] and m["right_runs"] == e["top1_runs"], (set_name, which)
            assert m["auto_runs"] == [r["auto_accept"] for r in e["routes_runs"]], (set_name, which)
            assert m["wrong_runs"] == [len(w) for w in e["wrong_auto_runs"]], (set_name, which)
            if "on" in e:
                m = measures(runs, logged(True))
                assert m["majority"] == e["on"]["majority_top1"] and m["right_runs"] == e["on"]["top1_runs"], which
                assert m["auto_runs"] == [r["auto_accept"] for r in e["on"]["routes_runs"]], which
                assert m["wrong_runs"] == [len(w) for w in e["on"]["wrong_auto_runs"]], which


# --------------------------------------------------------------------------- section 1: the changed lines
def lines_of(runs: list[list[dict]]) -> dict[str, dict]:
    out = {}
    for seen in zip(*runs):
        first = seen[0]
        exp = expected(first)
        outs = [outcome(r, r["route"], r["top1"]) for r in seen]
        maj = majority(outs)
        out[first["reference"]] = {
            "expected": exp, "rows": seen, "top1": [r["top1"] for r in seen], "route": [r["route"] for r in seen],
            "outcomes": outs, "majority": maj, "right": maj == exp,
            "right_auto": sum(r["route"] == "auto_accept" and o == exp for r, o in zip(seen, outs)),
            "wrong_auto": sum(r["route"] == "auto_accept" and o != exp for r, o in zip(seen, outs)),
            "props": [r.get("precedent_codes") or [] for r in seen],
            "unscoped": [decide(r, unscoped_vote(r), False)[0] for r in seen],
            "gated": [r["gate"] != "not_gated" for r in seen]}
    return out


CAUSES = ("new store (proposal)", "new store (vote)", "chapter-filtered vote", "run noise", "unexplained")


def causes(b: dict, o: dict) -> tuple[str | None, str | None]:
    """The causes of a line's change between the baseline (b) and the after-run (o), in three categories (the new
    store, through the proposal or the vote; the chapter-filtered vote; run noise), checked in this order.
    - Majority outcome: run noise when the two commands overlap (one's majority among the other's runs); else the new
      store's proposal when the codes the rulings proposed before the ranking differ (the twelve chapters' rulings are
      the same in both stores, so the difference is the rulings of the new chapters and the rebuilt index); else
      unexplained.
    - Auto-accepts: the chapter-filtered vote when the scoped vote routes a gated after-row otherwise than the unscoped
      vote on the same row; else the new store's proposal when that caused the outcome's change; else run noise when a
      command's runs disagree on the top-1; else the new store's vote when the unscoped vote on the after-rows routes the
      line otherwise than the baseline did; else run noise when a command's runs disagree on the route."""
    proposals_differ = {c for p in b["props"] for c in p} != {c for p in o["props"] for c in p}
    outcome_cause = None
    if b["majority"] != o["majority"] or b["right"] != o["right"]:
        if o["majority"] in b["outcomes"] or b["majority"] in o["outcomes"]:
            outcome_cause = "run noise"
        else:
            outcome_cause = "new store (proposal)" if proposals_differ else "unexplained"
    route_cause = None
    if b["right_auto"] != o["right_auto"] or b["wrong_auto"] != o["wrong_auto"]:
        if any(g and r != u for g, r, u in zip(o["gated"], o["route"], o["unscoped"])):
            route_cause = "chapter-filtered vote"
        elif outcome_cause == "new store (proposal)":
            route_cause = outcome_cause
        elif len(set(b["top1"])) > 1 or len(set(o["top1"])) > 1:
            route_cause = "run noise"
        elif majority(o["unscoped"]) != majority(b["route"]):
            route_cause = "new store (vote)"
        elif len(set(b["route"])) > 1 or len(set(o["route"])) > 1:
            route_cause = "run noise"
        else:
            route_cause = "unexplained"
    return outcome_cause, route_cause


def changed_lines(set_name: str) -> list[dict]:
    b_lines, o_lines = lines_of(runs_of(set_name, "baseline")), lines_of(runs_of(set_name, "after"))
    out = []
    for ref, b in b_lines.items():
        o = o_lines[ref]
        if b["right"] == o["right"] and b["majority"] == o["majority"] and b["right_auto"] == o["right_auto"] \
                and b["wrong_auto"] == o["wrong_auto"]:
            continue
        outcome_cause, route_cause = causes(b, o)
        window = o["rows"][0]["nearest_hits"][:SEARCHED]
        logged_before = b["rows"][0]["nearest_hits"]                # the baseline's 40 nearest
        before, last = {h["reference"] for h in logged_before}, 1 - logged_before[-1]["distance"]
        out.append({
            "reference": ref, "expected": b["expected"], "b": b, "o": o,
            "outcome_cause": outcome_cause, "route_cause": route_cause,
            "new_chapter": [h for h in window if h["hs6"][:2] not in TWELVE],
            # a ruling of the twelve chapters (all in both stores) nearer than the baseline's 40th, yet not among them:
            # the twelve-chapter store's approximate index missed it
            "newly_found": [h for h in window if h["hs6"][:2] in TWELVE and h["reference"] not in before
                            and 1 - h["distance"] > last],
            "sent": ([r.get("expected_sent") for r in b["rows"]], [r.get("expected_sent") for r in o["rows"]])})
    return out


def totals(lines: list[dict]) -> dict[str, dict[str, int]]:
    out = {c: {"right_to_wrong": 0, "wrong_to_right": 0, "right_auto": 0, "wrong_auto": 0} for c in CAUSES}
    for c in lines:
        b, o = c["b"], c["o"]
        if c["outcome_cause"] and b["right"] != o["right"]:
            out[c["outcome_cause"]]["right_to_wrong" if b["right"] else "wrong_to_right"] += 1
        if c["route_cause"]:
            out[c["route_cause"]]["right_auto"] += o["right_auto"] - b["right_auto"]
            out[c["route_cause"]]["wrong_auto"] += o["wrong_auto"] - b["wrong_auto"]
    return out


# --------------------------------------------------------------------------- the replay's exactness
def replay_matches(runs: list[list[dict]]) -> tuple[int, int, int]:
    """(rows whose unscoped replay equals the logged vote, rows that differ, rows within 1e-5 of the floor) over the rows
    with candidates, for runs whose logged vote is itself unscoped (the baseline and the ablation)."""
    same = differ = near = 0
    for run in runs:
        for r in run:
            if not r["top3"]:
                continue
            near += sum(abs((1 - h["distance"]) - HS6_VOTE_MIN_SIMILARITY) < 1e-5 for h in r["nearest_hits"][:SEARCHED])
            v = unscoped_vote(r)
            replay = None if v is None else sorted([code, len(c)] for code, c in v.competing)
            logged_counts = None if r["vote"] is None else sorted(r["vote"]["counts"])
            same, differ = (same + 1, differ) if replay == logged_counts else (same, differ + 1)
    return same, differ, near


def scoped_matches(runs: list[list[dict]]) -> tuple[int, int, int]:
    """(rows whose scoped vote, rebuilt from the 40 nearest_hits within the vote chapters, equals the logged one; rows that
    differ; rows with fewer than 5 such voters in the 40) for the after-run."""
    same = differ = short = 0
    for run in runs:
        for r in run:
            if not r["top3"]:
                continue
            voters = scoped_voters_from_nearest(r)
            if len(voters) < HS6_VOTE_K:
                short += 1
                continue
            v = hs6_ruling_vote([(h["hs6"], "") for h in voters], r["top3"])
            rebuilt = sorted([code, len(c)] for code, c in v.competing)
            same, differ = (same + 1, differ) if rebuilt == sorted(r["vote"]["counts"]) else (same, differ + 1)
    return same, differ, short


# --------------------------------------------------------------------------- section 3: the proposals' rules
# On the after-run's rows both votes are exact: the scoped vote is logged, the unscoped one replayed (1.5). The ablation
# logs only the unscoped vote; its scoped vote cannot be rebuilt reliably from the 40 logged hits (scoped_matches), so
# the rules that need it are estimated on the after-run's rows, and (a) and (b) on the ablation's rows are its own routes
# (when the unscoped vote agrees, the scoped one does too, so neither rule changes them).
def rule_a(override: bool):
    """(a) The unfiltered vote decides as before 014a; the filtered vote may only send a line to review: an auto-accept
    also needs the filtered vote, when it has voters, to auto-accept the same code. After-run rows."""
    def rule(row):
        f, u = logged_vote(row), unscoped_vote(row)
        route, chosen = decide(row, u, override)
        if route == "auto_accept" and f is not None and decide(row, f, override) != (route, chosen):
            return "review", row["top1"]
        return route, chosen
    return rule


def rule_b(override: bool):
    """(b) An auto-accept needs the filtered and the unfiltered vote both to auto-accept the same code; with only one
    vote the line goes to review; with neither, the confidence decides as today. After-run rows."""
    def rule(row):
        f, u = logged_vote(row), unscoped_vote(row)
        if (f is None) != (u is None):
            route, chosen = decide(row, f or u, override)
            return ("review", row["top1"]) if route == "auto_accept" else (route, chosen)
        return rule_a(override)(row)
    return rule


def rule_share(override: bool, share: float):
    """(d1) The filtered vote with a higher share: the majority needs `share` of the 5 voters. After-run rows."""
    def rule(row):
        counts = (row["vote"] or {}).get("counts")
        vote = (hs6_ruling_vote([(code, "") for code, k in counts for _ in range(k)], row["top3"], share=share)
                if counts else None)
        return decide(row, vote, override)
    return rule


def vague_rule(rule):
    """Section 4: a line flagged vague always goes to ask the shipper; anything else as `rule` routes it."""
    return lambda row: ("ask_shipper", row["top1"]) if row["flag"] == "vague" else rule(row)


# --------------------------------------------------------------------------- section 5: rule (a) and option (c)
NOW_SETS = ("cn8", "coolant", "outside")
NOW_HISTORY = {**HISTORY, "outside": "hs6_eval_outside_history.json"}
NOW_TAGS = {"cn8": ("014a-rule-a", "014a-c"), "coolant": ("014a-rule-a", "014a-c"), "outside": ("014a-a", "014a-c")}
NOW_FILES = {"cn8": ("hs6_eval_014a-rule-a.json", "hs6_eval_014a-c_en_expansion-off_wording-off.json"),
             "coolant": ("hs6_eval_coolant_014a-rule-a.json", "hs6_eval_coolant_014a-c_en_expansion-off_wording-off.json"),
             "outside": ("hs6_eval_outside_014a-a_en_expansion-off_wording-off.json",
                         "hs6_eval_outside_014a-c_en_expansion-off_wording-off.json")}
KEY_USAGE = 0.5544   # the paid runs of section 5 by the key's usage, read once OpenRouter had settled it


def rule_a_now(override: bool):
    """Rule (a) and the vague rule as the product routes since 2026-11-19: the gate's vote rebuilt from a row's
    nearest_hits (the unscoped vote), the second vote the row's own (the after-run's search within the candidates'
    chapters), both through route_line, hs6_gate and hs6_choice."""
    def rule(row):
        kind = None if row["flag"] == "failed" else FlagKind(row["flag"])
        conf, omin = row["confidence"], OVERRIDE_MIN if override else None
        gate_vote, second = unscoped_vote(row), logged_vote(row)
        route, _ = route_line(kind, conf, row["status"], kind not in (None, FlagKind.ok), DEFAULT_THRESHOLD, ASK_FLOOR,
                              hs6_vote=gate_vote, hs6_override_min=omin, hs6_scoped_vote=second)
        gated = row["status"] == "checked" and kind == FlagKind.ok and (conf or 0) > 0
        gate = hs6_gate(conf, DEFAULT_THRESHOLD, gate_vote, omin, second)[1] if gated else None
        _, chosen = hs6_choice([SimpleNamespace(code=c) for c in row["top3"]], gate_vote, gate)
        return route.value, chosen
    return rule


def tagged(set_name: str, tag: str) -> dict:
    history = json.loads((EVAL / NOW_HISTORY[set_name]).read_text(encoding="utf-8"))
    return [h for h in history if h.get("tag") == tag][-1]


def now_runs(set_name: str, k: int) -> list[list[dict]]:
    """The rows of section 5's (a) (k = 0) or (c) (k = 1) for a set."""
    data = json.loads((EVAL / NOW_FILES[set_name][k]).read_text(encoding="utf-8"))
    return data.get("runs") or [data["rows"]]


def from_entry(e: dict) -> dict:
    """A history entry's measures, or those of its `on` block, as measures() gives them."""
    return {"majority": e["majority_top1"], "right_runs": e["top1_runs"],
            "auto_runs": [r["auto_accept"] for r in e["routes_runs"]], "wrong_runs": [len(w) for w in e["wrong_auto_runs"]]}


def check_rule_a_replay() -> None:
    """The replays of rule (a) in the history (hs6_eval.py --replay --floor 0.40, through floor_fields) are of the
    after-runs and equal rule_a_now on their rows, the override off and on."""
    for s in SETS:
        e = tagged(s, NOW_TAGS[s][0])
        assert e["replay_of"]["iteration"] == entry_of(s, "after")["iteration"] and e["replay"]["exact"], s
        for override, block in ((False, e), (True, e["on"])):
            assert measures(runs_of(s, "after"), rule_a_now(override)) == from_entry(block), (s, override)


def line_majorities(runs: list[list[dict]]) -> dict[str, tuple]:
    """Each line's expected outcome, majority outcome (top-1, or route for an "ask the shipper" line) and whether it is
    right, with the override off."""
    out = {}
    for seen in zip(*runs):
        found = majority([outcome(r, r["route"], r["top1"]) for r in seen])
        out[seen[0]["reference"]] = (expected(seen[0]), found, found == expected(seen[0]))
    return out


# --------------------------------------------------------------------------- rendering
OUT = ROOT / "docs" / "reports" / "014a-regression-analysis.md"
SHORT = {"auto_accept": "auto", "review": "review", "ask_shipper": "ask"}


def _runs(values) -> str:
    return " / ".join(str(v) for v in values)


def _sim(h: dict) -> str:
    return f"{1 - h['distance']:.3f}" if "distance" in h else f"{h['similarity']:.3f}"


def _top1_routes(x: dict) -> str:
    return f"{_runs(t or 'none' for t in x['top1'])} ({_runs(SHORT[r] for r in x['route'])})"


def _change(c: dict) -> str:
    b, o, parts = c["b"], c["o"], []
    if b["right"] != o["right"]:
        parts.append(f"majority {'right → wrong' if b['right'] else 'wrong → right'}")
    elif b["majority"] != o["majority"]:
        parts.append("majority stays wrong, another code")
    if b["right_auto"] != o["right_auto"]:
        parts.append(f"right auto {b['right_auto']} → {o['right_auto']}")
    if b["wrong_auto"] != o["wrong_auto"]:
        parts.append(f"wrong auto {b['wrong_auto']} → {o['wrong_auto']}")
    return "; ".join(parts)


def _evidence(c: dict) -> str:
    b, o, bits = c["b"], c["o"], []
    if c["outcome_cause"] == "new store (proposal)":
        bits.append(f"proposed {', '.join(b['props'][0]) or 'none'} → {', '.join(o['props'][0]) or 'none'}")
        if c["new_chapter"]:
            codes = Counter(h["hs6"] for h in c["new_chapter"])
            best = {}
            for h in c["new_chapter"]:
                best[h["hs6"]] = max(best.get(h["hs6"], 0.0), 1 - h["distance"])
            bits.append("new-chapter rulings in the window: " + ", ".join(
                f"{code}{f' ×{n}' if n > 1 else ''} ({best[code]:.3f})" for code, n in codes.most_common()))
        if c["newly_found"]:
            bits.append("twelve-chapter rulings the rebuilt index now returns: "
                        + ", ".join(f"{h['reference']} {h['hs6']} ({_sim(h)})" for h in c["newly_found"]))
        sb, so = (sum(bool(s) for s in side) for side in c["sent"])
        if sb != so:
            bits.append(f"expected code shown to the model {sb}/3 → {so}/3")
    if c["route_cause"] == "chapter-filtered vote":
        row = next(r for r, g, rt, u in zip(o["rows"], o["gated"], o["route"], o["unscoped"]) if g and rt != u)
        bits.append(f"scoped vote ({', '.join(row['vote_chapters'])}): {_counts(row['vote']['counts'])} → "
                    f"{SHORT[row['route']]}; unscoped vote on the same row: "
                    f"{_counts(_voter_counts(unscoped_voters(row)))} → {SHORT[decide(row, unscoped_vote(row), False)[0]]}")
    if c["route_cause"] == "new store (vote)":
        row, before = o["rows"][0], b["rows"][0]
        new = [h for h in unscoped_voters(row) if h["hs6"][:2] not in TWELVE]
        bits.append(f"baseline vote {_counts(before['vote']['counts'])}; after-run's scoped vote "
                    f"({', '.join(row['vote_chapters'])}) {_counts(row['vote']['counts'])}; unscoped "
                    f"{_counts(_voter_counts(unscoped_voters(row)))}" + (f"; voters of new chapters {_voters_text(new)}" if new else ""))
    if c["outcome_cause"] == "run noise" or c["route_cause"] == "run noise":
        bits.append("the runs of a command disagree (top-1 or route per run in the columns)")
    return "; ".join(bits)


def _voters_text(hits: list[dict], country: dict | None = None) -> str:
    """Rulings as "HS-6 (similarity)", or "HS-6 similarity country" given the countries by reference."""
    if country is None:
        return ", ".join(f"{h['hs6']} ({_sim(h)})" for h in hits)
    return "; ".join(f"{h['hs6']} {_sim(h)} {country.get(h['reference'], '?')}" for h in hits)


def _voter_counts(voters: list[dict]) -> list[list]:
    return [[code, n] for code, n in Counter(h["hs6"] for h in voters).most_common()]


def _counts(counts: list[list]) -> str:
    return ", ".join(f"{code} {n}" for code, n in counts) if counts else "no voter"


def _set_table(set_name: str) -> tuple[list[str], list[dict]]:
    lines = changed_lines(set_name)
    out = ["| Line | Expected | Change | Baseline top-1 (routes) | After-run top-1 (routes) | Cause | Evidence |",
           "|---|---|---|---|---|---|---|"]
    for c in lines:
        cause = "; ".join(dict.fromkeys(x for x in (c["outcome_cause"], c["route_cause"]) if x))
        out.append(f"| {c['reference']} | {c['expected']} | {_change(c)} | {_top1_routes(c['b'])} | "
                   f"{_top1_routes(c['o'])} | {cause} | {_evidence(c)} |")
    return out, lines


def _totals_table(lines_by_set: dict[str, list[dict]]) -> list[str]:
    out = ["| Set | Cause | Majority right → wrong | Majority wrong → right | Right auto-accepts (3 runs) | "
           "Wrong auto-accepts (3 runs) |", "|---|---|---|---|---|---|"]
    for set_name, lines in lines_by_set.items():
        for cause, t in totals(lines).items():
            if any(t.values()):
                out.append(f"| {'120 lines' if set_name == 'cn8' else 'coolant'} | {cause} | {t['right_to_wrong']} | "
                           f"{t['wrong_to_right']} | {t['right_auto']:+d} | {t['wrong_auto']:+d} |")
    return out


def _measure_rows(set_name: str) -> list[tuple[str, dict, dict]]:
    """(label, override off, override on) for the baseline, the ablation, the after-run and the replay."""
    rows = []
    for label, which, rule in (("Baseline: 12 chapters, unscoped vote (it. {b})", "baseline", logged),
                               ("Ablation: every chapter, unscoped vote (it. {a})", "ablation", logged),
                               ("After-run: every chapter, scoped vote (it. {o})", "after", logged),
                               ("Replay: the unscoped vote on the after-run's rows", "after", unscoped)):
        runs = runs_of(set_name, which)
        rows.append((label, measures(runs, rule(False)), measures(runs, rule(True))))
    return rows


def _ablation_table(set_name: str) -> list[str]:
    n = len(runs_of(set_name, "baseline")[0])
    it = {k: entry_of(set_name, k)["iteration"] for k in WHICH}
    label = "right" if set_name == "coolant" else "top-1"
    out = [f"| Run | Override | Majority {label} | {label.capitalize()} per run | Auto-accepted per run | "
           "Wrong auto-accepted per run |", "|---|---|---|---|---|---|"]
    for name, off, on in _measure_rows(set_name):
        name = name.format(b=it["baseline"], a=it["ablation"], o=it["after"])
        for override, m in (("off", off), ("on", on)):
            out.append(f"| {name} | {override} | {m['majority']}/{n} | {_runs(m['right_runs'])} | {_runs(m['auto_runs'])} | "
                       f"{_runs(m['wrong_runs'])} ({sum(m['wrong_runs'])}) |")
    return out


def _filter_rows(set_name: str) -> list[str]:
    out = ["| Line | Run | Expected | Top-1 | Scoped vote (chapters) | Route | Unscoped vote, same row | Route |",
           "|---|---|---|---|---|---|---|---|"]
    for k, run in enumerate(runs_of(set_name, "after"), 1):
        for r in run:
            u = decide(r, unscoped_vote(r), False)[0]
            if r["gate"] != "not_gated" and r["route"] != u:
                out.append(f"| {r['reference']} | {k} | {expected(r)} | {r['top1']} | {_counts(r['vote']['counts'])} "
                           f"({', '.join(r['vote_chapters'])}) | {SHORT[r['route']]} | "
                           f"{_voters_text(unscoped_voters(r))} | {SHORT[u]} |")
    return out


def _bti208() -> list[str]:
    ref = "IEBTIIENEN004-2024-BTI208"
    item = next(x for x in json.loads((EVAL / "cn8_eval_set.json").read_text(encoding="utf-8"))["rulings"]
                if x["reference"] == ref)
    rows = {w: [next(x for x in run if x["reference"] == ref) for run in runs_of("cn8", w)] for w in WHICH}
    text = " / ".join(item["description"].split("\n"))
    out = [f"**The line**: \"{text}\". Expected HS-6 {item['hs6']} (CN-8 {item['cn8']}).", "",
           "| Run | Baseline top 3 (confidence) | After-run top 3 (confidence) | Ablation top 3 (confidence) |",
           "|---|---|---|---|"]
    for k in range(3):
        cells = [", ".join(f"{c} ({p})" for c, p in zip(rows[w][k]["top3"], rows[w][k]["confidences"])) for w in WHICH]
        out.append(f"| {k + 1} | {cells[0]} | {cells[1]} | {cells[2]} |")
    b1, o1 = rows["baseline"][0], rows["after"][0]
    out += ["", "**What the rulings proposed** (the codes the precedent proposal added to the candidates, the same in "
            "all three runs of each command), and the 12 rulings it read, in RRF order (1 is the line's own ruling, "
            "kept out):", "",
            "| # | Baseline: ruling | HS-6 | Similarity | After-run: ruling | HS-6 | Similarity |", "|---|---|---|---|---|---|---|"]
    for k, (hb, ho) in enumerate(zip(b1["nearest_hits"][:SEARCHED], o1["nearest_hits"][:SEARCHED]), 1):
        mark = lambda h: (" (new chapter)" if h["hs6"][:2] not in TWELVE else "") + (" (own)" if not h["eligible"]  # noqa: E731
                                                                                        and h["reference"] == ref else "")
        out.append(f"| {k} | {hb['reference']}{mark(hb)} | {hb['hs6']} | {_sim(hb)} | {ho['reference']}{mark(ho)} | "
                   f"{ho['hs6']} | {_sim(ho)} |")
    out += ["", f"Proposed: baseline {', '.join(b1['precedent_codes'])}; after-run {', '.join(o1['precedent_codes'])}. "
            f"The expected code was among the subheadings shown to the model in "
            f"{sum(r['expected_sent'] for r in rows['baseline'])}/3 baseline runs and "
            f"{sum(r['expected_sent'] for r in rows['after'])}/3 after-runs.", "",
            "**The votes on the after-run's rows**:", "",
            "| Run | Scoped vote: chapters, the 5 voters (HS-6, similarity, country) | Route | Unscoped vote on the same row: "
            "the 5 voters | Route |", "|---|---|---|---|---|"]
    for k, r in enumerate(rows["after"], 1):
        country = {h["reference"]: h["country"] for h in r["nearest_hits"]}
        scoped = [h for h in r["vote_hits"] if h["eligible"] and h["similarity"] >= HS6_VOTE_MIN_SIMILARITY][:HS6_VOTE_K]
        out.append(f"| {k} | {', '.join(r['vote_chapters'])}: "
                   f"{_voters_text(scoped, country)} | "
                   f"{SHORT[r['route']]} ({_counts(r['vote']['counts'])}) | "
                   f"{_voters_text(unscoped_voters(r), country)} | "
                   f"{SHORT[decide(r, unscoped_vote(r), False)[0]]} "
                   f"({_counts(_voter_counts(unscoped_voters(r)))}) |")
    return out


def _new_chapter_proposals() -> list[str]:
    """(d2) The new-chapter codes the after-run's rulings proposed on the lines whose majority the proposal changed, with
    their best ruling's similarity and their rulings in the window, and what two stricter rules would keep."""
    out = ["| Set | Line | Effect of the proposal | New-chapter codes proposed: best similarity, rulings in the window | "
           "Kept at a 0.65 floor | Kept with 2 rulings or more |", "|---|---|---|---|---|---|"]
    for s in SETS:
        for c in changed_lines(s):
            if c["outcome_cause"] != "new store (proposal)":
                continue
            row = c["o"]["rows"][0]
            window = [h for h in row["nearest_hits"][:SEARCHED] if h["eligible"]]
            codes = [code for code in row["precedent_codes"] if code[:2] not in TWELVE]
            facts = {code: (max(1 - h["distance"] for h in window if h["hs6"] == code),
                            sum(h["hs6"] == code for h in window)) for code in codes if any(h["hs6"] == code for h in window)}
            effect = ("right → wrong" if c["b"]["right"] and not c["o"]["right"] else
                      "wrong → right" if c["o"]["right"] and not c["b"]["right"] else "wrong → another wrong code")
            cell = "; ".join(f"{code}: {sim:.3f}, {n}" for code, (sim, n) in facts.items()) or "none (displacement)"
            keep_floor = ", ".join(code for code, (sim, _) in facts.items() if sim >= 0.65) or "none"
            keep_two = ", ".join(code for code, (_, n) in facts.items() if n >= 2) or "none"
            out.append(f"| {'120 lines' if s == 'cn8' else 'coolant'} | {c['reference']} | {effect} | {cell} | {keep_floor} | "
                       f"{keep_two} |")
    return out


def _proposal_table(proposals: dict) -> list[str]:
    out = ["| Rule | Set | Rows | Majority, override off / on | Auto-accepted per run, off | Wrong auto-accepted, off | "
           "Auto-accepted per run, on | Wrong auto-accepted, on |", "|---|---|---|---|---|---|---|---|"]
    for s in SETS:
        n = len(runs_of(s, "baseline")[0])
        for which in ("after", "ablation"):
            for name, label in (("today", "Today (the scoped vote)"), ("(a)", "(a) filtered vote may only send to review"),
                                ("(b)", "(b) both votes must agree"), ("(d1)", "(d1) filtered vote, share 0.8")):
                if name not in proposals[(s, which, False)]:
                    continue
                off, on = proposals[(s, which, False)][name], proposals[(s, which, True)][name]
                out.append(f"| {label} | {'120 lines' if s == 'cn8' else 'coolant'} | {which} | {off['majority']} / "
                           f"{on['majority']} of {n} | {_runs(off['auto_runs'])} | {_runs(off['wrong_runs'])} "
                           f"({sum(off['wrong_runs'])}) | {_runs(on['auto_runs'])} | {_runs(on['wrong_runs'])} "
                           f"({sum(on['wrong_runs'])}) |")
    return out


def _vague_lines() -> list[str]:
    out = ["| Set | Line | Expected | Baseline routes (confidence) | After-run | Ablation | With the rule |",
           "|---|---|---|---|---|---|---|"]
    for s in SETS:
        rows = {w: runs_of(s, w) for w in WHICH}
        refs = []
        for w in WHICH:
            for run in rows[w]:
                refs += [r["reference"] for r in run if r["flag"] == "vague" and r["reference"] not in refs]
        for ref in refs:
            cells = []
            for w in WHICH:
                seen = [next(x for x in run if x["reference"] == ref) for run in rows[w]]
                cells.append(" / ".join(f"{SHORT[r['route']]} ({r['confidence']})" if r["flag"] == "vague"
                                        else f"{SHORT[r['route']]}, not vague" for r in seen))
            exp = expected(next(x for x in rows["baseline"][0] if x["reference"] == ref))
            out.append(f"| {'120 lines' if s == 'cn8' else 'coolant'} | {ref} | {exp} | {cells[0]} | {cells[1]} | {cells[2]} | "
                       "ask / ask / ask |")
    return out


def _vague_table(vague: dict) -> list[str]:
    out = ["| Set | Run | Override | Majority today | With the rule | Vague rows to review today | With the rule |",
           "|---|---|---|---|---|---|---|"]
    for s in SETS:
        n = len(runs_of(s, "baseline")[0])
        for w in WHICH:
            to_review = sum(r["flag"] == "vague" and r["route"] == "review" for run in runs_of(s, w) for r in run)
            for o in (False, True):
                today, rule = vague[(s, w, o)]
                out.append(f"| {'120 lines' if s == 'cn8' else 'coolant'} | {w} | {'on' if o else 'off'} | {today['majority']}/{n} | "
                           f"{rule['majority']}/{n} | {to_review} | 0 |")
    return out


def _document(table: dict, m: dict, exact: dict, scoped_check: dict, proposals: dict, vague: dict) -> list[str]:
    it = {s: {w: entry_of(s, w)["iteration"] for w in WHICH} for s in SETS}
    cn = m["cn8"]
    base, abl, aft, rep = (cn[k][0] for k in ("Baseline", "Ablation", "After-run", "Replay"))
    base_on, abl_on, aft_on, rep_on = (cn[k][1] for k in ("Baseline", "Ablation", "After-run", "Replay"))
    co = m["coolant"]
    cbase, cabl, caft, crep = (co[k][0] for k in ("Baseline", "Ablation", "After-run", "Replay"))
    w = lambda x: sum(x["wrong_runs"])          # noqa: E731
    a = lambda x: sum(x["auto_runs"])           # noqa: E731
    lines = {s: table[s][1] for s in SETS}
    tot = totals(lines["cn8"])
    p_after = proposals[("cn8", "after", False)]
    p_abl = proposals[("cn8", "ablation", False)]
    p_cool = proposals[("coolant", "after", False)]
    out = ["# Feature 014a: why the 120-line evaluation regressed", "",
           f"**Note of 2026-11-19**: after this analysis the author decided rule (a) (the unfiltered vote decides the "
           "auto-accept, the vote of the candidates' chapters can only send a line to review), block 3's captions and the "
           "vague rule (a vague line always asks the shipper), and rejected option (c). Under rule (a) SC-004 passes, "
           f"{sum(from_entry(tagged('cn8', NOW_TAGS['cn8'][0]))['wrong_runs'])} wrong auto-accepts against {w(base)}. "
           "Section 5 measures them; sections 1 to 4 are the analysis as written before the decisions (their \"today\" "
           "is the chapter-scoped vote).", "",
           "The author is holding the feature: on the 120-line evaluation the majority top-1 fell from 84 to 77 and wrong "
           "auto-accepts rose from 10 to 12, so SC-004 failed. This report separates the causes. Everything is read from "
           "the logged rows and history entries of the runs, with no model call, except the ablation of section 2 (one paid "
           "run of both sets). The twelve chapters' rulings are the same in both stores (the rebuild reused all 74,044 and "
           "added none in those chapters). The tables are rendered by `tests/eval/regression_014a.py`, which first checks that its "
           "routes reproduce every history entry it uses; the product's routing functions recompute every route.", "",
           f"- **Baseline**: 120-line iteration {it['cn8']['baseline']}, coolant iteration {it['coolant']['baseline']}. The "
           "store of the twelve chapters (74,044 rulings); the vote over every chapter, as before 014a.",
           f"- **After-run**: iterations {it['cn8']['after']} and {it['coolant']['after']}. The rebuilt store of every chapter "
           "(123,531 rulings); the vote within the candidates' chapters, as 014a ships.",
           f"- **Ablation**: iterations {it['cn8']['ablation']} and {it['coolant']['ablation']}. The rebuilt store; the vote "
           "over every chapter (`--vote-scope all`, eval only).",
           "- All three: Gemini 2.5 Flash with reasoning off, query expansion off, customs wording off, three runs, "
           "threshold 85, ask floor 50. The eval's route has the precedent override off; the app ships with it on, so "
           "section 2 shows both.",
           "- Result files (review round 1): every table of sections 1 to 4 reads these runs' own files, "
           + "; ".join(f"{which}: " + " and ".join(f"`tests/eval/{FILES[s][which]}`" for s in SETS) for which in WHICH)
           + ", and checks them against their history entries. The evaluation's \"latest run\" files "
           "(`tests/eval/hs6_eval.json`, `hs6_eval_coolant.json`, `hs6_eval_outside.json`) now hold the rejected option (c) "
           "runs (tag 014a-c); only section 5 reads those runs, from their own files.", "",
           "**Headline** (120 lines, precedent override off):", "",
           f"- **Store effect** (baseline → ablation, the same unscoped vote): majority top-1 {base['majority']} → "
           f"{abl['majority']}; wrong auto-accepts {w(base)} → {w(abl)}; auto-accepted per run {_runs(base['auto_runs'])} → "
           f"{_runs(abl['auto_runs'])}.",
           f"- **Filter effect** (the unscoped vote replayed on the after-run's rows → the after-run: the same model answers): "
           f"majority top-1 {rep['majority']} → {aft['majority']} (with the override off the vote never changes a top-1); "
           f"auto-accepted per run {_runs(rep['auto_runs'])} → {_runs(aft['auto_runs'])}: {w(aft) - w(rep)} more wrong "
           f"(IEBTIIENEN004-2024-BTI208 in every run) and {a(aft) - a(rep) - (w(aft) - w(rep))} more right ones "
           "(IEBTIIENEN004-2025-BTI173 in every run, IEBTIIENEN004-2026-BTI118 once).",
           f"- **Noise** (the ablation against the replay: the same store, prompt and vote, other model answers): majority "
           f"top-1 {abl['majority']} against {rep['majority']}; top-1 per run {_runs(abl['right_runs'])} against "
           f"{_runs(rep['right_runs'])}; auto-accepted and wrong auto-accepted per run identical.",
           f"- So the fall of the majority from {base['majority']} to {aft['majority']} is the new store (through the "
           "candidate proposal, section 1) with a line of noise, and the rise of wrong auto-accepts from "
           f"{w(base)} to {w(aft)} is the chapter filter (+3, BTI208) less a line of baseline noise (−1, BTI284). With the "
           f"override on: majority {base_on['majority']} → {abl_on['majority']} (store) and {rep_on['majority']} → "
           f"{aft_on['majority']} (filter); wrong auto-accepts {w(base_on)} → {w(abl_on)} → {w(aft_on)}.", "",
           "## 1. What changed between the baseline and the after-run (no model call)", "",
           "Every line whose majority outcome or auto-accepts changed, on both sets, with its cause in one of three "
           "categories: the **new store** (the rulings of the newly indexed chapters, or the rebuilt index, changed the "
           "candidate proposal, the codes the rulings propose before the model ranks, or the vote); the **chapter-filtered "
           "vote** (the scoped vote routes a row otherwise than the unscoped vote would on the same row); **run noise** "
           "(the runs of the baseline or of the after-run disagree among themselves). The rules, in the order checked, "
           "are `causes()` in the script. The window: the 12 rulings the proposal read, the same 12 the unscoped vote "
           "takes its 5 voters from; the evidence is the first after-run's.", "",
           "### 1.1 The 120-line set", "", *table["cn8"][0], "",
           "### 1.2 The coolant set", "", *table["coolant"][0], "",
           "### 1.3 Totals per cause", "", *_totals_table(lines), "",
           f"On the 120 lines the majority fell by {base['majority'] - aft['majority']}: the new store's proposal cost "
           f"{tot['new store (proposal)']['right_to_wrong']} lines and won {tot['new store (proposal)']['wrong_to_right']}, "
           f"noise cost {tot['run noise']['right_to_wrong']}. In five of the six lines the model chose a code that rulings "
           "of a newly indexed chapter proposed, or one next to it (4016.99; 9111.80 beside the proposed 9113.90; "
           "8609.00; 5808.90; 9026.90); in BTI208 rulings of the new store displaced the right code from the proposal "
           "(1.4). The new rulings in the vote cost 6 right auto-accepts (BTI245, BTI258: rulings of chapter 90, newly "
           "indexed, now vote, and for BTI245 also of chapters 28 and 82; as a chapter-90 code is among the model's "
           "candidates, the scoped vote searches chapter 90 too, so the filter does not keep them out). The filter "
           "added 3 wrong (BTI208) and 1 right (BTI118) auto-accept among the changed lines; with BTI173, whose "
           "auto-accepts it keeps against new rulings that would otherwise vote it to review, it adds 4 right ones "
           "(section 2). On the coolant set the new store's proposal brought the right code to coolant-1 and coolant-6 "
           "(2710.19 and 3403.99, proposed by rulings of chapters 27 and 34) and moved the plain 冷却液 from ask to "
           "review (section 4); the new rulings in the vote auto-accept coolant-5, and the filter coolant-4 and coolant-7.",
           "", "### 1.4 IEBTIIENEN004-2024-BTI208", "", *_bti208(), "",
           "**Why the top-1 moved from 6109.90 to 6114.30.** No code of a new chapter was proposed, but two rulings the "
           "baseline's window did not hold entered the after-run's: IEBTIIENEN004-2025-BTI81 (5806.31, chapter 58, newly "
           "indexed) at 4 and DEBTI36199/24-1 (6307.90, chapter 63) at 7. DEBTI36199/24-1 is in both stores with the same "
           "text and vector: the twelve-chapter store's approximate index did not return it, the rebuilt index does. "
           "Together they pushed two of the three 6109.90 rulings out of the window, so 6109.90 fell from the second "
           "proposed code to none, the precedent leg no longer added its subheading, and the model, shown 6114.30 tagged "
           "with three rulings and no 6109.90 at all, chose 6114.30 at 95 in every run. The ablation, with the same "
           "proposal, chose it too. The evaluation report's label for it, \"new-chapter proposals\", comes from its rule "
           "(the proposed codes differ) but names the wrong mechanism: here the new store displaced the right code; no "
           "new-chapter code was proposed.", "",
           "**Why it is auto-accepted wrong in every after-run.** The model's three candidates are all in chapter 61, so "
           "the scoped vote searched chapter 61 only. Its 5 nearest eligible rulings hold 6114.30 three times, a 3-of-5 "
           "majority for the model's code: agree, auto-accept. The unscoped vote on the same rows reads two chapter-62 "
           "rulings at 6212.10 first, then the new chapter-58 ruling, one 6114.30 and a 6212.90: majority 6212.10 at 2 of "
           "5, review, which is what the ablation's real vote did in all three runs. The filter removed the rulings that "
           "disagreed and left a chapter-61 majority for the wrong code. In the baseline the right top-1 was never "
           "auto-accepted either: the same unscoped vote tied or disagreed.", "",
           "### 1.5 Is the evaluation report's replay of the old vote exact?", "",
           "The column \"Old vote's routes\" of eval-diff.md replays the vote of before 014a from each after-row's "
           "nearest_hits: the 5 nearest eligible rulings at or above 0.40 among the first 12. That is exact when (1) a "
           "line has one query vector, so the vote's 12 rulings are one search's (true here: query expansion off, no "
           "shipper answer, customs wording off); (2) eligibility and floor are the product's (the logged flag is: not "
           "the line's own ruling, valid on the set's date, coded to the nomenclature; no logged hit lies within 1e-5 of "
           "the floor); and (3) the first 12 of the logged search (k = 40) are the product's k = 12 search, which an "
           "approximate index does not promise. (3) was tested where the logged vote is itself unscoped: the replay "
           f"equals the logged vote in {exact['cn8']['baseline'][0]} of {sum(exact['cn8']['baseline'][:2])} baseline rows "
           f"with candidates (coolant {exact['coolant']['baseline'][0]} of {sum(exact['coolant']['baseline'][:2])}) and, "
           f"on the rebuilt store, in {exact['cn8']['ablation'][0]} of {sum(exact['cn8']['ablation'][:2])} ablation rows "
           f"(coolant {exact['coolant']['ablation'][0]} of {sum(exact['coolant']['ablation'][:2])}). **The replay is "
           "exact.** One limit, which does not touch it: the approximate index can miss near rulings in an unfiltered "
           "search that a filtered search finds (XIBTI505060394: five 8301.50 rulings at 0.70 found by the scoped "
           "search, absent from the 40 nearest). So the scoped vote rebuilt from the 40 logged hits equals the logged one "
           f"in {scoped_check['cn8'][0]} of 360 rows ({scoped_check['cn8'][1]} differ, {scoped_check['cn8'][2]} have fewer "
           "than 5 in-chapter rulings among the 40), none of them a row whose route changes. That is also why section 3 "
           "does not rebuild the scoped vote on the ablation's rows.", "",
           "## 2. The ablation: the vote over every chapter on the rebuilt store", "",
           "`--vote-scope all` (tests/eval/hs6_eval.py, eval only) runs the vote's ruling search without its chapter "
           "filter: the vote is the unscoped 5-nearest vote of before 014a, on the same store, prompt and candidate "
           "proposal as the after-run. It cost $0.5075 by the key's usage, read once OpenRouter had settled it ($0.4751 "
           "right after the runs), and $0.5608 by the evaluation's tallies (120 lines $0.5260, coolant $0.0348; they "
           "price tokens from the project's table and run high): within the approved $0.55.", "", "**The 120-line set**:", "", *_ablation_table("cn8"), "",
           "**The coolant set**:", "", *_ablation_table("coolant"), "",
           "What the ablation separates:", "",
           f"- **The store effect** is the baseline against the ablation (the same unscoped vote): {base['majority']} → "
           f"{abl['majority']} majority, wrong auto-accepts {w(base)} → {w(abl)}, auto-accepted {a(base)} → {a(abl)} over "
           f"three runs; coolant {cbase['majority']} → {cabl['majority']} majority, auto-accepted {a(cbase)} → {a(cabl)}. "
           "The new store costs top-1s through the proposal, and right auto-accepts through rulings that now vote, but no "
           "wrong auto-accept.",
           f"- **The filter effect** is the ablation against the after-run, and exactly the replay against the after-run "
           f"(the same answers): auto-accepted {a(rep)} → {a(aft)}, wrong {w(rep)} → {w(aft)}; coolant auto-accepted "
           f"{a(crep)} → {a(caft)}, wrong {w(crep)} → {w(caft)}. It never changes a top-1 with the override off.",
           f"- **Noise** is the ablation against the replay (everything equal but the model's answers): majority "
           f"{abl['majority']} against {rep['majority']}, coolant {cabl['majority']} against {crep['majority']} "
           "(coolant-6 is right in one ablation run of three); routes identical per run on the 120 lines.",
           f"- The line-level causes of section 1 (the new store's proposal {tot['new store (proposal)']['wrong_to_right'] - tot['new store (proposal)']['right_to_wrong']:+d} "
           f"net, noise {-tot['run noise']['right_to_wrong']:+d}) and the ablation's split (store "
           f"{abl['majority'] - base['majority']:+d}, noise {aft['majority'] - abl['majority']:+d}) both add up to "
           f"{aft['majority'] - base['majority']:+d}; they differ in how much of the run noise falls on each comparison.", "",
           "The rows where the filter changes the route (after-run):", "", *_filter_rows("cn8"), *_filter_rows("coolant")[2:],
           "", "## 3. Fix proposals (not implemented)", "",
           "A fact frames (a) and (b): with the current rules, when the unfiltered vote agrees with the model's top code, "
           "the filtered vote agrees too. The rulings the unfiltered vote reads in the top code's chapter are also the "
           "nearest of that chapter, so they are among the filtered vote's 5; the filter only removes rulings of other "
           "chapters, which can only disagree. So the filter can turn a review into an auto-accept (BTI208 wrongly; "
           "BTI173, BTI118, coolant-4 and coolant-7 rightly) and never the reverse.", "",
           "**(a) The filtered vote may support a review, never trigger an auto-accept on its own.** The unfiltered vote "
           "decides as before 014a; an auto-accept also needs the filtered vote, when it has voters, to auto-accept the "
           "same code. Guardrail: the gate stays code-computed agreement with the 5 nearest eligible rulings "
           "(Principle I), the rule of constitution 1.5.0 word for word; the filtered vote adds a stricter check. No "
           f"amendment. By the fact above it equals the unscoped gate: after-run, wrong auto-accepts {w(p_after['today'])} → "
           f"{w(p_after['(a)'])} and auto-accepted {a(p_after['today'])} → {a(p_after['(a)'])} (4 right ones lost: BTI173, "
           f"BTI118); coolant auto-accepted {a(p_cool['today'])} → {a(p_cool['(a)'])} (coolant-4 and coolant-7 back to "
           "review); majority top-1 unchanged. On the ablation's rows it leaves the unscoped vote's routes as they are, "
           f"{a(p_abl['(a)'])} auto-accepted with {w(p_abl['(a)'])} wrong, which is the same estimate on other model "
           "answers. The filtered vote keeps its use in block 3 (the captions).", "",
           "**(b) An auto-accept needs both votes to agree.** As (a), and a line with only one vote goes to review; with "
           "neither, the confidence decides as today. Same guardrail, no amendment. It differs from (a) only when exactly "
           "one vote has no voter, which no row of either run had, so its effect is (a)'s.", "",
           "**(c) The candidate proposal limited to the chapters of the nomenclature search's top subheadings** (option B "
           "of clarification 1). Guardrail: none touched; Principle IV's pipeline is unchanged (the proposal is part of "
           "retrieval), so no amendment, but it reverses the author's clarification 1 (the proposal searches every "
           "chapter) and needs the spec changed. Effect: needs a paid run (about $0.56 for both sets, as the ablation). "
           "The proposal changes the candidates and the precedent tags in the ranking prompt, so the model's choice "
           "cannot be replayed, and the rows do not log the nomenclature search's subheadings. Bounds: it can win back "
           "at most the 6 lines the new store's proposal cost (5 through new-chapter codes, 1 through displacement) and "
           "may lose what new-chapter proposals won (BTI222; coolant-1 and coolant-6, whose right codes rulings of "
           "chapters 27 and 34 proposed).", "",
           f"**(d1) The filtered vote with a share of 0.8** (4 of 5). Guardrail: HS6_VOTE_SHARE is a named constant "
           "whose value Principle I leaves to the spec, so no amendment, but the spec and its boundary tests change. "
           f"After-run: wrong auto-accepts {w(p_after['today'])} → {w(p_after['(d1)'])}, auto-accepted "
           f"{a(p_after['today'])} → {a(p_after['(d1)'])}, so {a(p_after['today']) - a(p_after['(d1)']) - (w(p_after['today']) - w(p_after['(d1)']))} "
           f"right auto-accepts lost; coolant auto-accepted {a(p_cool['today'])} → {a(p_cool['(d1)'])}. It halves the "
           "wrong auto-accepts at a high price.", "",
           "**(d2) Stricter proposals from newly indexed chapters** (a similarity floor, or two rulings in the window). "
           "Guardrail: none touched, no amendment; a retrieval rule in the spec. Effect: needs a paid run, as (c). "
           "Offline, the rulings behind the proposals that changed a majority show that neither rule separates harm from "
           "help: the harmful proposals sit at 0.61 to 0.75 similarity, the helpful ones at 0.53 to 0.69 (the coolant "
           "lines are short, so their similarities are low).", "", *_new_chapter_proposals(), "",
           "The effects at a glance (offline; (c) and (d2) need a paid run). Today's rule and (d1) need the scoped vote, "
           "which the ablation does not log and which cannot be rebuilt reliably from its 40 logged hits: rebuilt, it "
           "would add 6 wrong auto-accepts that the real filtered search does not give (BTI132 with no in-chapter ruling "
           "among the 40, BTI284 and BTI463 with other rulings). So they are estimated on the after-run's rows, where "
           "both votes are exact:", "",
           *_proposal_table(proposals), "",
           "## 4. Plain 冷却液: a vague line always asks the shipper", "",
           "**The rule**: a line flagged vague goes to ask the shipper, whatever its confidence. Today it goes to ask the "
           "shipper only below the ask floor of 50, and to review otherwise; a vague line's confidence is capped at 59 in "
           "code, so only 50 to 59 reach review.", "",
           "**Constitution and spec**: Principle I already forbids auto-accepting a flagged line (kept, and the flagged-line "
           "lock is unchanged). Principle III requires that, when a description is flagged, the assistant tell the clerk "
           "what to ask the shipper rather than present a confident code; the rule follows it more strictly. The ask "
           "floor is not in the constitution: it is feature 001's FR-020 and the author's clarification of 2026-10-14 "
           "(below 50 ask, otherwise review). So no amendment, but a spec change to feature 001 (FR-020, its clarification "
           "and its assumption) for the author, and the 12-line sample's routes and the tests that pin them change.", "",
           "**The lines flagged vague** (routes and confidence per run):", "", *_vague_lines(), "",
           "**The effect**:", "", *_vague_table(vague), "",
           "On the coolant set the rule makes the plain 冷却液 right in every run: majority after-run 7 → 8, ablation "
           "6 → 7, baseline 6 (it asked already). On the 120 lines it moves the 5 vague lines' 15 rows per command from "
           "review to ask the shipper and changes no top-1 and no auto-accept. The trade-off: coolant-1 and coolant-3 are "
           "flagged vague but have a code the model gets right (2710.19 and 3403.99); the rule would ask the shipper "
           "about them too."]
    return out


def _now_table(set_name: str) -> list[str]:
    n = len(now_runs(set_name, 0)[0])
    label = "top-1" if set_name == "cn8" else "right"
    out = [f"| Run | Override | Majority {label} | {label.capitalize()} per run | Auto-accepted per run | "
           "Wrong auto-accepted per run |", "|---|---|---|---|---|---|"]
    rows = []
    if set_name in SETS:
        b = entry_of(set_name, "baseline")
        runs = runs_of(set_name, "baseline")
        rows.append((f"Baseline (it. {b['iteration']}): 12 chapters, unscoped vote, the runs' routing",
                     measures(runs, logged(False)), measures(runs, logged(True))))
    a, c = (tagged(set_name, tag) for tag in NOW_TAGS[set_name])
    a_name = (f"(a): replay of it. {a['replay_of']['iteration']} (it. {a['iteration']})" if set_name in SETS
              else f"(a) (it. {a['iteration']})")
    rows += [(a_name, from_entry(a), from_entry(a["on"])),
             (f"(c) with (a) (it. {c['iteration']})", from_entry(c), from_entry(c["on"]))]
    for name, off, on in rows:
        for override, m in (("off", off), ("on", on)):
            out.append(f"| {name} | {override} | {m['majority']}/{n} | {_runs(m['right_runs'])} | {_runs(m['auto_runs'])} | "
                       f"{_runs(m['wrong_runs'])} ({sum(m['wrong_runs'])}) |")
    return out


def _now_lines(set_name: str) -> tuple[list[str], dict]:
    """The lines whose majority outcome differs between (a) and (c), with whether the expected chapter was among the
    chapters of the nomenclature search's subheadings that (c)'s proposal read (its first run)."""
    a, c = line_majorities(now_runs(set_name, 0)), line_majorities(now_runs(set_name, 1))
    first_a = {r["reference"]: r for r in now_runs(set_name, 0)[0]}
    first_c = {r["reference"]: r for r in now_runs(set_name, 1)[0]}
    out = ["| Line | Expected | (a) majority | (c) majority | Expected chapter among (c)'s chapters | Proposed (a) → (c), run 1 |",
           "|---|---|---|---|---|---|"]
    count = {"lost": 0, "won": 0, "lost_outside": 0}
    for ref, (exp, found_a, right_a) in a.items():
        _, found_c, right_c = c[ref]
        if found_a == found_c:
            continue
        chapters = first_c[ref].get("proposal_chapters") or []
        inside = exp[:2] in chapters if exp and exp[0].isdigit() else None
        if right_a and not right_c:
            count["lost"] += 1
            count["lost_outside"] += inside is False
        if right_c and not right_a:
            count["won"] += 1
        out.append(f"| {ref} | {exp} | {found_a or 'no code'} | {found_c or 'no code'} | "
                   f"{'-' if inside is None else ('yes' if inside else 'no')} ({', '.join(chapters)}) | "
                   f"{', '.join(first_a[ref]['precedent_codes']) or 'none'} → {', '.join(first_c[ref]['precedent_codes']) or 'none'} |")
    return out, count


def _neardup_section() -> list[str]:
    """Section 5.1: the outside set's near-duplicate check of 2026-11-19, from its committed record."""
    rec = json.loads((EVAL / "hs6_eval_outside_neardup.json").read_text(encoding="utf-8"))

    def hit(h: dict, own: str) -> str:
        return f"{h['similarity']:.4f} {h['reference']} ({h['hs6']}){' = source' if h['reference'] == own else ''}"

    out = ["### 5.1 The outside set's lines: the near-duplicate check of 2026-11-19", "",
           f"Before the paid runs each line was checked ({rec['method']}). Limit {rec['limit']}: {rec['flags']}. "
           f"Approval: {rec['approved']}. The record: `tests/eval/hs6_eval_outside_neardup.json`; the lines: "
           "`tests/eval/hs6_eval_outside_set.json` (`original` and `text`).", "",
           "| Line | Code | Original: top | Final: top | Final: top other than the source | Source rank, final | "
           "Flags |", "|---|---|---|---|---|---|---|"]
    for line in rec["lines"]:
        o, f = line["original"], line["final"]
        flags = ["source ruling in the store"] if line["source_in_store"] else []
        flags += [f"over {rec['limit']} before" for _ in [0] if o["over_limit"]] + [f"over {rec['limit']} after" for _ in [0] if f["over_limit"]]
        out.append(f"| {line['id']} | {line['expected_hs6']} | {hit(o['top'], line['id'])} | {hit(f['top'], line['id'])} | "
                   f"{hit(f['top_other_than_source'], line['id'])} | {f['source_rank'] or 'not in the 6'} | "
                   f"{'; '.join(flags)}; rewritten |")
    tops = [line["final"]["top"]["similarity"] for line in rec["lines"]]
    over = [line["id"] for line in rec["lines"] if line["original"]["over_limit"]]
    return out + ["", f"Every source ruling is in the store, so all {len(rec['lines'])} lines were flagged and rewritten; "
                      f"{len(over)} original was above the limit ({', '.join(over)}). The final texts' top similarities run "
                      f"from {min(tops):.4f} to {max(tops):.4f}; no final text is above the limit, and a line's own source "
                      "ruling is kept out of its runs (leave-one-out)."]


def _section5() -> list[str]:
    e = {s: [tagged(s, tag) for tag in NOW_TAGS[s]] for s in NOW_SETS}
    label = {"cn8": "120 lines", "coolant": "coolant", "outside": "outside"}
    paid = [(f"{label[s]} {name}", x["cost_usd"]) for s in NOW_SETS for name, x in zip(("(a)", "(c)"), e[s])
            if not x.get("replay")]
    lock = "FRBTIFR-BTI-2026-00308"     # the outside set's bike U-lock
    wrong_lock = [sum(r["reference"] == lock and r["route"] == "auto_accept" and not r["right"] for run in now_runs("outside", k)
                      for r in run) for k in (0, 1)]
    wrong_out = [sum(r["route"] == "auto_accept" and not r["right"] for run in now_runs("outside", k) for r in run)
                 for k in (0, 1)]
    w = lambda m: sum(m["wrong_runs"])          # noqa: E731
    base = {o: measures(runs_of("cn8", "baseline"), logged(o)) for o in (False, True)}
    a120 = {False: from_entry(e["cn8"][0]), True: from_entry(e["cn8"][0]["on"])}
    c120 = {False: from_entry(e["cn8"][1]), True: from_entry(e["cn8"][1]["on"])}
    lines120, n120 = _now_lines("cn8")
    lines_cool, _ = _now_lines("coolant")
    lines_out, _ = _now_lines("outside")
    passed = w(a120[False]) <= w(base[False])
    return [
        "## 5. Rule (a) and option (c): the measurement of 2026-11-19", "",
        "The author's decisions of 2026-11-19 (spec, clarifications of that day): the app now routes by **rule (a)**, "
        "the unfiltered 5-nearest vote of constitution 1.5.0 deciding the auto-accept while the vote within the "
        "candidates' chapters can only send a line to review, and by the **vague rule**, every vague line to ask the "
        "shipper. **Option (c)** limits the candidate proposal to the chapters of the nomenclature search's subheadings; "
        "it was measured with rule (a) through `--proposal-scope nomenclature` (tests/eval/hs6_eval.py, evaluation only, "
        "no product code or setting), against (a):", "",
        f"- **(a) on the 120-line and coolant sets** is the exact replay of the after-runs' rows (iterations "
        f"{e['cn8'][0]['replay_of']['iteration']} and {e['coolant'][0]['replay_of']['iteration']}) by the product's "
        "routing functions under rule (a) and the vague rule: `hs6_eval.py --replay <after-run file> --floor 0.40`, no "
        f"model call (history iterations {e['cn8'][0]['iteration']} and {e['coolant'][0]['iteration']}). This script "
        "checks that its own replay of rule (a) (`rule_a_now`) gives the same measures, the override off and on.",
        f"- **(a) on the outside set** is three runs of its own (iteration {e['outside'][0]['iteration']}), the control "
        "of (c). The set: 14 lines approved by the author (tests/eval/hs6_eval_outside_set.json), whose expected HS-6 "
        "lies outside the twelve chapters of the old store, each from an EBTI ruling valid on 2026-11-19 and rewritten in "
        "plain shipper wording; each line's source ruling is kept out (leave-one-out).",
        f"- **(c)**: three runs on each set (iterations {e['cn8'][1]['iteration']}, {e['coolant'][1]['iteration']} and "
        f"{e['outside'][1]['iteration']}). Every run: Gemini 2.5 Flash with reasoning off, query expansion off, customs "
        "wording off, three runs, threshold 85, the rebuilt store of every chapter.",
        "- **Result files**: the history entries named above, and the runs' own files for the line tables: "
        + "; ".join(f"{label[s]}: (a) `tests/eval/{NOW_FILES[s][0]}`, (c) `tests/eval/{NOW_FILES[s][1]}`" for s in NOW_SETS)
        + ". The near-duplicate check of the outside set's lines: `tests/eval/hs6_eval_outside_neardup.json` (5.1).",
        f"- **Cost**: ${KEY_USAGE:.4f} by the key's usage, read once OpenRouter had settled it; "
        f"${sum(c for _, c in paid):.4f} by the evaluation's tallies ("
        + ", ".join(f"{name} ${c:.4f}" for name, c in paid) + "): within the approved $1.10.", "",
        "**The 120-line set**:", "", *_now_table("cn8"), "",
        "**The coolant set**:", "", *_now_table("coolant"), "",
        "**The outside set**:", "", *_now_table("outside"), "",
        f"**SC-004 under rule (a)**: wrong auto-accepts summed over the three replayed after-runs, {w(a120[False])}, "
        f"against {w(base[False])} over the three baseline runs: **{'passes' if passed else 'fails'}** (override on: "
        f"{w(a120[True])} against {w(base[True])}). Judged on the chapter-filtered vote as first built it failed, 12 "
        "against 10 (eval-diff.md, section 4); rule (a) keeps the after-run's top-1s (the vote never changes a top-1 with "
        f"the override off: majority {a120[False]['majority']}, as the after-run's) and removes the 3 wrong auto-accepts "
        "of IEBTIIENEN004-2024-BTI208.", "",
        f"**(c) against (a)**: on the 120 lines (c) has a majority top-1 of {c120[False]['majority']} against "
        f"{a120[False]['majority']} and the same wrong auto-accepts ({w(c120[False])} against {w(a120[False])}), with "
        f"fewer auto-accepts ({_runs(c120[False]['auto_runs'])} against {_runs(a120[False]['auto_runs'])} per run). It "
        f"loses {n120['lost']} lines that (a) gets right on majority and wins {n120['won']}; in {n120['lost_outside']} of "
        "the lost lines the expected chapter is not among the chapters of the nomenclature search's subheadings, so "
        "(c)'s proposal could not bring the right code in, which is what the proposal does today (it lifted the labelled "
        "set's top-3 from 11 of 12 to 12 of 12). On the coolant set (c) loses coolant-1 (2710.19, proposed today by "
        "rulings of chapter 27); on the outside set it loses the chilli seasoning (2103.90 → 0904.22). "
        + (f"The outside set's wrong auto-accepts are all the bike U-lock ({lock}), {wrong_lock[0]} under (a) and "
           f"{wrong_lock[1]} under (c): its source ruling gives 8301.10, while the model chose 8301.40, where 4 of its 5 "
           "nearest rulings sit. " if wrong_lock == wrong_out else "")
        + "The author rejected (c) on 2026-11-19: it is not implemented in the app, and the evaluation-only "
        "`--proposal-scope nomenclature` stays for later experiments.", "",
        "The 120-line set's lines whose majority outcome differs between (a) and (c):", "", *lines120, "",
        "The coolant set's:", "", *lines_cool, "",
        "The outside set's:", "", *lines_out, "", *_neardup_section()]


def render() -> str:
    check_against_history()
    check_rule_a_replay()
    table = {s: _set_table(s) for s in SETS}
    m = {s: dict((name.split(":")[0], (off, on)) for name, off, on in _measure_rows(s)) for s in SETS}
    exact = {s: {w: replay_matches(runs_of(s, w)) for w in ("baseline", "ablation")} for s in SETS}
    scoped_check = {s: scoped_matches(runs_of(s, "after")) for s in SETS}
    proposals = {}
    for s in SETS:
        runs, ablation = runs_of(s, "after"), runs_of(s, "ablation")
        for override in (False, True):
            proposals[(s, "after", override)] = {
                "today": measures(runs, logged(override)), "(a)": measures(runs, rule_a(override)),
                "(b)": measures(runs, rule_b(override)), "(d1)": measures(runs, rule_share(override, 0.8))}
            own = measures(ablation, logged(override))      # (a) and (b) leave the unscoped vote's routes as they are
            proposals[(s, "ablation", override)] = {"(a)": own, "(b)": own}
    vague = {(s, w, o): (measures(runs_of(s, w), logged(o)), measures(runs_of(s, w), vague_rule(logged(o))))
             for s in SETS for w in WHICH for o in (False, True)}
    return "\n".join(_document(table, m, exact, scoped_check, proposals, vague) + ["", *_section5()]) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--print", action="store_true", help="print the report, write nothing")
    args = ap.parse_args(argv)
    text = render()
    if args.print:
        print(text)
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
