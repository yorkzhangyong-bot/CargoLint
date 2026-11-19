"""Feature 014a's evaluation report (tasks T046): specs/014a-retrieval-evidence/eval-diff.md, rendered from the HS-6
evaluation's history entries and the logged rows of its runs, with no model call.

    python tests/eval/eval_diff_014a.py            # writes the report
    python tests/eval/eval_diff_014a.py --print    # prints it, writes nothing

Sections: before against after for the 120-line set and the coolant set (baseline, after-runs with the customs-wording
switch off and on); the floor replays; the success criteria; and, for every line whose majority outcome or auto-accepts
changed between the baseline and the switch-off after-run, the facts its cause is read from and the cause. The old,
unscoped vote is rebuilt from each after-row's nearest_hits (the precedent search's nearest rulings over every chapter,
the same query vector the vote used): the 5 nearest eligible rulings among the 12 it read, at or above the floor. Its
routes follow the runs' routing: until the vague rule of 2026-11-19 a vague line at or above the ask floor went to
review (review round 1). Sections 4 and 6 carry a note of 2026-11-19 on the author's decisions and rule (a)'s SC-004.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD, HS6_VOTE_K, HS6_VOTE_MIN_SIMILARITY, OVERRIDE_MIN  # noqa: E402
from agent.routing import hs6_ruling_vote, route_line  # noqa: E402
from agent.schemas import FlagKind, Route  # noqa: E402
from rag.bti import TARGET_CHAPTERS  # noqa: E402

EVAL = ROOT / "tests" / "eval"
OUT = ROOT / "specs" / "014a-retrieval-evidence" / "eval-diff.md"
TWELVE = set(TARGET_CHAPTERS)
SEARCHED = 12                       # the rulings the product's ruling search read per query vector (2 × RETRIEVAL_K)
RUNS = {"baseline": "014a-baseline", "off": "014a-after", "on": "014a-after-fix", "flawed": "014a-after"}
FILES = {"cn8": {"baseline": "hs6_eval_014a-baseline_en_expansion-off.json",
                 "off": "hs6_eval_014a-after_en_expansion-off_wording-off.json",
                 "on": "hs6_eval_014a-after-fix_en_expansion-off_wording-on.json",
                 "flawed": "hs6_eval_014a-after_en_expansion-off_wording-on.json"},
         "coolant": {"baseline": "hs6_eval_coolant_014a-baseline_en_expansion-off.json",
                     "off": "hs6_eval_coolant_014a-after_en_expansion-off_wording-off.json",
                     "on": "hs6_eval_coolant_014a-after_en_expansion-off_wording-on.json"}}


def majority(values: list) -> object:
    """The most frequent value; a tie goes to the value seen first (the earliest run), as the evaluation's."""
    counts = Counter(values)
    return next(v for v in values if counts[v] == max(counts.values()))


def runs_of(set_name: str, which: str) -> list[list[dict]]:
    data = json.loads((EVAL / FILES[set_name][which]).read_text(encoding="utf-8"))
    return data.get("runs") or [data["rows"]]


def entry(history: list[dict], tag: str, wording: str | None, replay: float | None = None) -> dict:
    """The history entry of a run (or of a replay at `replay`) by its tag and customs-wording switch."""
    found = [h for h in history if h.get("tag") == tag and h.get("customs_wording") == wording
             and (h.get("replay") or {}).get("floor") == replay]
    return found[-1]


def unscoped_route(row: dict) -> str:
    """The route the old vote, over every chapter, would give this row: the 5 nearest eligible rulings among the 12 the
    ruling search read, at or above the floor, by the product's vote and routing functions; a vague line at or above
    the ask floor goes to review, as when the runs were made (the vague rule of 2026-11-19 sends it to ask the
    shipper)."""
    voters = [(h["hs6"], "") for h in row["nearest_hits"][:SEARCHED]
              if h["eligible"] and 1 - h["distance"] >= HS6_VOTE_MIN_SIMILARITY]
    vote = hs6_ruling_vote(voters[:HS6_VOTE_K], row["top3"]) if row["top3"] else None
    kind = None if row["flag"] == "failed" else FlagKind(row["flag"])
    route = route_line(kind, row["confidence"], row["status"], kind not in (None, FlagKind.ok), DEFAULT_THRESHOLD,
                       ASK_FLOOR, hs6_vote=vote)[0]
    if kind == FlagKind.vague and row["confidence"] is not None and row["confidence"] >= ASK_FLOOR:   # the runs' rule
        route = Route.review
    return route.value


def outcome(row: dict) -> object:
    """What a row is scored on: its route for a coolant line expecting "ask the shipper", else its top-1."""
    return row["route"] if row.get("expected_route") else row["top1"]


def lines_of(runs: list[list[dict]]) -> dict[str, dict]:
    out = {}
    for seen in zip(*runs):
        first = seen[0]
        expected = first.get("expected_route") or first["expected"]
        maj = majority([outcome(r) for r in seen])
        out[first["reference"]] = {
            "expected": expected, "rows": seen, "top1": [r["top1"] for r in seen], "route": [r["route"] for r in seen],
            "outcomes": [outcome(r) for r in seen], "majority": maj, "right": maj == expected,
            "auto": sum(r["route"] == "auto_accept" for r in seen), "props": [r.get("precedent_codes") or [] for r in seen],
            "wrong_auto": sum(r["route"] == "auto_accept" and outcome(r) != expected for r in seen),
            "gated": [r["gate"] != "not_gated" for r in seen], "unscoped": [unscoped_route(r) for r in seen]}
    return out


CAUSES = ("new-chapter proposals", "new-chapter rulings in the vote", "vote scope", "run-to-run variation", "other")


def cause_of(b: dict, o: dict) -> tuple[str | None, str | None]:
    """The causes of a line's change between the baseline (b) and the switch-off after-run (o), of its majority outcome
    (its top-1) and of its routes, checked in this order. The twelve chapters' rulings and vectors are the same in both
    stores, so what differs is the rulings of the newly indexed chapters and the vote's scope.
    - Top-1: run-to-run variation when the two commands overlap (one's majority among the other's runs); else
      new-chapter proposals when the codes the rulings proposed before the ranking differ; else other.
    - Routes: vote scope when the chapter-scoped vote routes a gated after-row otherwise than the old vote would on the
      same row; else the top-1's cause when the top-1 changed; else new-chapter rulings in the vote when the old vote,
      on the new store, already routes the line otherwise than the baseline (the new rulings changed the vote, not its
      scope); else run-to-run variation when a command's runs disagree; else other."""
    proposals_differ = {c for p in b["props"] for c in p} != {c for p in o["props"] for c in p}
    top1_cause = None
    if b["majority"] != o["majority"] or b["right"] != o["right"]:
        if o["majority"] in b["outcomes"] or b["majority"] in o["outcomes"]:
            top1_cause = "run-to-run variation"
        else:
            top1_cause = "new-chapter proposals" if proposals_differ else "other"
    route_cause = None
    if b["auto"] != o["auto"] or majority(b["route"]) != majority(o["route"]):
        if any(g and r != u for g, r, u in zip(o["gated"], o["route"], o["unscoped"])):
            route_cause = "vote scope"
        elif top1_cause is not None:
            route_cause = top1_cause
        elif majority(o["unscoped"]) != majority(b["route"]):
            route_cause = "new-chapter rulings in the vote"
        elif len(set(b["route"])) > 1 or len(set(o["route"])) > 1:
            route_cause = "run-to-run variation"
        else:
            route_cause = "other"
    return top1_cause, route_cause


def changed_lines(set_name: str) -> list[dict]:
    b_lines, o_lines = lines_of(runs_of(set_name, "baseline")), lines_of(runs_of(set_name, "off"))
    out = []
    for ref, b in b_lines.items():
        o = o_lines[ref]
        if b["right"] == o["right"] and b["auto"] == o["auto"] and majority(b["route"]) == majority(o["route"]):
            continue
        top1_cause, route_cause = cause_of(b, o)
        new_props = sorted({c for p in o["props"] for c in p if c[:2] not in TWELVE})
        top1 = o["majority"] if not o["rows"][0].get("expected_route") else majority(o["top1"])
        out.append({"reference": ref, "expected": b["expected"], "b": b, "o": o, "top1_cause": top1_cause,
                    "route_cause": route_cause, "new_props": new_props,
                    "proposed": sum(r["top1"] in (r.get("precedent_codes") or []) for r in o["rows"]),
                    "top1_chapter": "-" if not top1 else ("newly indexed" if top1[:2] not in TWELVE else "one of the twelve")})
    return out


# --------------------------------------------------------------------------- rendering
def _runs(values) -> str:
    return " / ".join(str(v) for v in values)


def _set_table(rows: list[tuple[str, dict]], n: int, coolant: bool, override: bool = False) -> list[str]:
    """A set's before/after table from the history entries; with `override`, the rows of each entry's `on` block too:
    the same answers routed with the precedent override on, as the app ships (review finding 7)."""
    label = "right" if coolant else "top-1"
    head = "| | " + " | ".join(name for name, _ in rows) + " |"
    out = [head, "|---|" + "---|" * len(rows)]

    def row(title, fn):
        out.append(f"| {title} | " + " | ".join(fn(h) for _, h in rows) + " |")

    row(f"Majority {label}", lambda h: f"{h['majority_top1']}/{n}")
    row(f"{label.capitalize()} per run", lambda h: _runs(h["top1_runs"]))
    row("In top 3 per run", lambda h: _runs(h["top3_runs"]))
    row("Auto-accepted per run", lambda h: _runs(r["auto_accept"] for r in h["routes_runs"]))
    row("Wrong, auto-accepted per run", lambda h: _runs(len(w) for w in h["wrong_auto_runs"]))
    row("Decided without a voting ruling per run", lambda h: _runs(g["no_rulings"] for g in h["gate_runs"]))
    row("HS-6 step failed per run", lambda h: _runs(p["failed_lines"] for p in h["parse"]["runs"]) if "parse" in h else "-")
    if override:
        row(f"Majority {label}, override on", lambda h: f"{h['on']['majority_top1']}/{n}")
        row(f"{label.capitalize()} per run, override on", lambda h: _runs(h["on"]["top1_runs"]))
        row("Auto-accepted per run, override on", lambda h: _runs(r["auto_accept"] for r in h["on"]["routes_runs"]))
        row("Wrong, auto-accepted per run, override on", lambda h: _runs(len(w) for w in h["on"]["wrong_auto_runs"]))
    row("Cost (eval tally)", lambda h: f"${h['cost_usd']:.4f}")
    return out


def _override_moves(set_name: str) -> str:
    """What the precedent override changes in a set's logged rows (their `on` fields against their own route and top-1)."""
    moved = sum(r["on"]["route"] != r["route"] or r["on"]["chosen"] != r["top1"]
                for which in ("baseline", "off", "on") for run in runs_of(set_name, which) for r in run)
    return "no route and no HS-6" if not moved else f"the route or HS-6 of {moved} rows"


def _sc002(set_name: str, which: str) -> tuple[int, int, list[str]]:
    """SC-002 on the coolant set's after-rows: (rows with a voter outside their vote chapters, rows whose vote lists a
    chapter 84 ruling, the codes of chapter 84 seen)."""
    outside = shows_84 = 0
    seen84 = []
    for run in runs_of(set_name, which):
        for r in run:
            codes = [code for code, _ in ((r.get("vote") or {}).get("counts") or [])]
            outside += any(code[:2] not in r["vote_chapters"] for code in codes)
            if any(code.startswith("84") for code in codes):
                shows_84 += 1
                seen84 += [code for code in codes if code.startswith("84")]
    return outside, shows_84, seen84


def render() -> str:
    hist = json.loads((EVAL / "hs6_eval_history.json").read_text(encoding="utf-8"))
    chist = json.loads((EVAL / "hs6_eval_coolant_history.json").read_text(encoding="utf-8"))
    base, off, on, flawed = (entry(hist, RUNS["baseline"], None), entry(hist, RUNS["off"], "off"),
                             entry(hist, RUNS["on"], "on"), entry(hist, RUNS["flawed"], "on"))
    cbase, coff, con = entry(chist, RUNS["baseline"], None), entry(chist, RUNS["off"], "off"), entry(chist, RUNS["off"], "on")
    sum_wrong = lambda h: sum(len(w) for w in h["wrong_auto_runs"])                 # noqa: E731
    out = ["# Feature 014a: the evaluation report", "",
           "Rendered by `tests/eval/eval_diff_014a.py` from `tests/eval/hs6_eval_history.json`, "
           "`tests/eval/hs6_eval_coolant_history.json` and the logged rows of the runs; no model call. Every run used "
           f"Gemini 2.5 Flash with reasoning off, query expansion off, threshold {DEFAULT_THRESHOLD}, ask floor {ASK_FLOOR} "
           "and three independent runs. Majority: a line's most frequent top-1 (for a coolant line expecting \"ask the "
           "shipper\", its route), a tie going to the earliest run.", "",
           f"- Baseline (T006): 120-line iteration {base['iteration']}, coolant iteration {cbase['iteration']}, on the store "
           "of twelve chapters (74,044 rulings) and the code of `main` plus the coolant set.",
           f"- After-runs (T044): 120-line iterations {off['iteration']} (switch off) and {on['iteration']} (switch on), "
           f"coolant iterations {coff['iteration']} and {con['iteration']}, on the rebuilt store of every chapter "
           "(123,531 rulings in 95 chapters, T043).",
           "- The precedent override: each row's route, and every route and auto-accept count below unless marked, has it "
           "off, as the evaluation keeps its history comparable (feature 008), while the app ships with it on "
           f"(`CARGOLINT_HS6_OVERRIDE`, at OVERRIDE_MIN {OVERRIDE_MIN}). Section 1 adds the rows with it on from each "
           "history entry's `on` block: the same model answers routed with the override on, no model call. In the "
           f"coolant rows it changes {_override_moves('coolant')}, so section 2 stands for both settings.",
           f"- Iteration {flawed['iteration']} (120 lines, switch on) is not used: the German rewrite of the longest ruling "
           "descriptions exceeded its 300-character cap, refused inside the call before the retry, so 6 to 7 lines per run "
           f"failed. Commit 290b3f5 retries such an answer once; iteration {on['iteration']} is the re-run (see section 4).",
           "- In the baseline, runs 2 and 3 each lost one line to an OpenRouter rate-limit error (HS-6 step failed).",
           "- Spend: T006 $0.5576 (the evaluation's tally); T043 $0.194 (the refresh's own count, equal to the key's "
           "usage over the run); T044 $1.718 by the key's usage, the provider's charge for its five runs, the discarded "
           f"iteration {flawed['iteration']} among them. The evaluation's own tallies for those runs sum to "
           f"${sum(h['cost_usd'] for h in (off, coff, flawed, on, con)):.4f}: they price tokens from the project's price "
           "table and miss one failed rewrite call of 65,521 output tokens.",
           "- Result files (review round 1): sections 1 to 3 read the history entries of the iterations above and of the "
           "floor replays; sections 4 and 5 also read the runs' own files, "
           + ", ".join(f"`tests/eval/{name}`" for set_name in ("cn8", "coolant") for which, name in FILES[set_name].items()
                       if which != "flawed")
           + ". The evaluation's \"latest run\" files (`tests/eval/hs6_eval.json`, `tests/eval/hs6_eval_coolant.json`) "
           "now hold the rejected option (c) runs (tag 014a-c); no table here reads them.", ""]
    out += ["## 1. The 120-line set", ""] + _set_table(
        [(f"Baseline (it. {base['iteration']})", base), (f"After, switch off (it. {off['iteration']})", off),
         (f"After, switch on (it. {on['iteration']})", on)], 120, coolant=False, override=True)
    out += ["", "## 2. The coolant set", ""] + _set_table(
        [(f"Baseline (it. {cbase['iteration']})", cbase), (f"After, switch off (it. {coff['iteration']})", coff),
         (f"After, switch on (it. {con['iteration']})", con)], 8, coolant=True)
    texts = {l["id"]: l["text"] for l in json.loads((EVAL / "hs6_eval_coolant_set.json").read_text(encoding="utf-8"))["lines"]}
    out += ["", "Each line's majority outcome (its top-1, or its route for a line expecting \"ask the shipper\"):", "",
            "| Line | Text | Expected | Baseline | After, switch off | After, switch on |", "|---|---|---|---|---|---|"]
    for b, o, n in zip(cbase["lines"], coff["lines"], con["lines"]):
        mark = lambda x: f"{x['majority'] or 'no code'} {'✓' if x['right'] else '✗'}"   # noqa: E731
        out.append(f"| {b['id']} | {texts[b['id']]} | {b['expected']} | {mark(b)} | {mark(o)} | {mark(n)} |")
    out += ["", "## 3. Floor replays (no model call)", "",
            "The switch-off after-runs' votes rebuilt from their `vote_hits` at higher floors (`--replay FILE --floor X`); "
            "exact, as each floor is at or above the runs' 0.40.", "",
            "| Set | Floor | Auto-accepted per run | Wrong, auto-accepted per run | Without a voting ruling per run |",
            "|---|---|---|---|---|"]
    for name, history, run in (("120 lines", hist, off), ("coolant", chist, coff)):
        out.append(f"| {name} | 0.40 (the run) | {_runs(r['auto_accept'] for r in run['routes_runs'])} | "
                   f"{_runs(len(w) for w in run['wrong_auto_runs'])} | {_runs(run['no_voter_runs'])} |")
        for floor in (0.45, 0.5, 0.55):
            h = entry(history, f"{RUNS['off']}-floor{floor:.2f}", "off", floor)
            out.append(f"| {name} | {floor:.2f} | {_runs(r['auto_accept'] for r in h['routes_runs'])} | "
                       f"{_runs(len(w) for w in h['wrong_auto_runs'])} | {_runs(h['no_voter_runs'])} |")
    out += ["", "No floor change is made: the 120-line set does not move at any of these floors, and the floor stays "
                f"at {HS6_VOTE_MIN_SIMILARITY:.2f} (the author's decision; no tuning in this feature). The coolant set gains one "
                "right auto-accept per run from 0.50.", ""]
    # ----------------------------------------------------------------- the criteria
    rows = changed_lines("cn8")
    sc004 = [(c["reference"], c["route_cause"], c["o"]["wrong_auto"] - c["b"]["wrong_auto"]) for c in rows
             if c["o"]["wrong_auto"] != c["b"]["wrong_auto"]]
    sc_off, sc_on = _sc002("coolant", "off"), _sc002("coolant", "on")
    wrong_base, wrong_off = sum_wrong(base), sum_wrong(off)
    combined_off, combined_on = off["majority_top1"] + coff["majority_top1"], on["majority_top1"] + con["majority_top1"]
    plain_on = [r["route"] for run in runs_of("coolant", "on") for r in run if r["reference"] == "coolant-8"]
    failed_on = sorted({r["reference"] for run in runs_of("cn8", "on") for r in run if r["status"] == "failed"})
    clean = [seen for seen in zip(*runs_of("cn8", "on")) if seen[0]["reference"] not in failed_on]
    clean_off = [seen for seen in zip(*runs_of("cn8", "off")) if seen[0]["reference"] not in failed_on]
    right_on = sum(majority([r["top1"] for r in s]) == s[0]["expected"] for s in clean)
    right_off = sum(majority([r["top1"] for r in s]) == s[0]["expected"] for s in clean_off)
    rule_a = entry(hist, "014a-rule-a", "off", HS6_VOTE_MIN_SIMILARITY)
    out += ["## 4. The success criteria", "",
            f"**Note of 2026-11-19**: SC-004 passes under rule (a), the author's decision of that day: replayed exactly on "
            f"the switch-off after-run's rows (iteration {rule_a['iteration']} in the history), {sum_wrong(rule_a)} wrong "
            f"auto-accepts against {wrong_base} in the baseline. The verdicts below are of the chapter-scoped "
            "vote as first built (docs/reports/014a-regression-analysis.md, section 5).", "",
            f"- **SC-001** (T043): passed. The rebuild kept every valid ruling of the extract of 2026-11-18, 123,531 in 95 "
            "chapters; its counts show the 74,044 unchanged rulings of the twelve chapters reused and the 49,487 new ones "
            "embedded, none dropped; $0.194 (17,648,924 tokens), 6,333 s, the store 3,454,915,131 bytes.",
            f"- **SC-002**: {'passed' if not any(sc_off[:2]) and not any(sc_on[:2]) else 'failed'}. In the coolant set's "
            f"after-runs no row has a voting ruling outside its vote chapters ({sc_off[0]} switch off, {sc_on[0]} switch on) "
            f"and none lists a chapter 84 ruling ({sc_off[1]} and {sc_on[1]}).",
            "- **SC-003**: this report, every number from the history entries and rows above.",
            f"- **SC-004**: **failed**. Wrong auto-accepts on the 120-line set, summed over three runs: {wrong_off} after "
            f"(switch off, the shipped default) against {wrong_base} in the baseline. The lines (section 5): "
            + "; ".join(f"{ref} {delta:+d} ({cause})" for ref, cause, delta in sc004)
            + ". The vote scope's line is auto-accepted wrong in every run where the old vote, on the same rows, would have "
            "sent it to review. No fallback to the unscoped vote and no switch for it were added; the author decides. "
            f"With the precedent override on, as the app ships: {sum_wrong(off['on'])} against {sum_wrong(base['on'])}, "
            "the same verdict.",
            f"- **FR-026's criterion** for turning the switch on later: **not met**. Majority top-1 of both sets together: "
            f"{combined_on} with the switch on (120 lines {on['majority_top1']}, coolant {con['majority_top1']}) against "
            f"{combined_off} with it off ({off['majority_top1']} and {coff['majority_top1']}); with the precedent override on, "
            f"{on['on']['majority_top1'] + con['majority_top1']} against {off['on']['majority_top1'] + coff['majority_top1']}, "
            "not higher either, and the switch-on after-run then auto-accepts "
            f"{sum_wrong(on['on'])} wrong over its three runs against {sum_wrong(on)} with the override off. The plain 冷却液 routed to "
            f"ask the shipper in every switch-on run ({', '.join(plain_on)}), the second condition, met. The switch stays "
            "off (SC-006). With the switch on, some lines still failed their HS-6 step after the fix "
            f"({_runs(p['failed_lines'] for p in on['parse']['runs'])} per run; {len(failed_on)} lines: the rewrite of a long "
            "ruling description stayed over 300 characters after its retry, and one call ran to 65,521 output tokens); "
            f"on the {120 - len(failed_on)} lines that never failed, the majority top-1 is {right_on} with the switch on "
            f"against {right_off} with it off.",
            "- **SC-005**: every caption state and citation case is covered offline (`pytest -q`).",
            "- **SC-006**: `CARGOLINT_CUSTOMS_WORDING` is off by default; this report records the off/on comparison.", ""]
    # ----------------------------------------------------------------- the analysis
    out += ["## 5. Why the 120-line numbers moved (offline analysis)", "",
            f"Every line whose majority outcome or auto-accepts changed between the baseline (it. {base['iteration']}) and "
            f"the switch-off after-run (it. {off['iteration']}). Proposed: in how many of the three runs the after top-1 was "
            "a code the rulings proposed before the ranking. New-chapter codes: the codes the rulings of newly indexed "
            "chapters proposed in the after-run. Old vote: the routes the unscoped vote would give the same after-rows. "
            "The causes are read as `eval_diff_014a.cause_of` states them.", "",
            "| Line | Expected | Baseline top-1 (routes) | After top-1 (routes) | Proposed | After top-1's chapter | "
            "New-chapter codes proposed | Old vote's routes | Outcome change: cause | Route change: cause |",
            "|---|---|---|---|---|---|---|---|---|---|"]

    def short(route: str) -> str:
        return {"auto_accept": "auto", "review": "review", "ask_shipper": "ask"}[route]

    def change(x: dict, y: dict, what: str) -> str:
        if what == "outcome":
            text = f"{'right' if x['right'] else 'wrong'} → {'right' if y['right'] else 'wrong'}"
            return text if x["right"] != y["right"] else f"top-1 changed, {text}"
        if x["auto"] != y["auto"]:
            return f"auto {x['auto']} → {y['auto']}"
        return f"{short(majority(x['route']))} → {short(majority(y['route']))}"

    for c in rows:
        b, o = c["b"], c["o"]
        out.append(f"| {c['reference']} | {c['expected']} | {_runs(b['top1'])} ({_runs(short(r) for r in b['route'])}) | "
                   f"{_runs(o['top1'])} ({_runs(short(r) for r in o['route'])}) | {c['proposed']}/3 | {c['top1_chapter']} | "
                   f"{', '.join(c['new_props']) or 'none'} | {_runs(short(r) for r in o['unscoped'])} | "
                   + (f"{change(b, o, 'outcome')}: {c['top1_cause']}" if c["top1_cause"] else "unchanged") + " | "
                   + (f"{change(b, o, 'route')}: {c['route_cause']}" if c["route_cause"] else "unchanged") + " |")
    totals: dict[str, Counter] = {}
    for c in rows:
        b, o = c["b"], c["o"]
        if c["top1_cause"] and b["right"] != o["right"]:
            totals.setdefault(c["top1_cause"], Counter())["right → wrong" if b["right"] else "wrong → right"] += 1
        if c["route_cause"]:
            t = totals.setdefault(c["route_cause"], Counter())
            t["wrong auto-accepts"] += o["wrong_auto"] - b["wrong_auto"]
            t["right auto-accepts"] += (o["auto"] - o["wrong_auto"]) - (b["auto"] - b["wrong_auto"])
    out += ["", "Totals per cause (lines whose majority outcome changed; auto-accepts summed over the three runs, after less "
                "before):", "", "| Cause | Majority right → wrong | Majority wrong → right | Wrong auto-accepts | "
                "Right auto-accepts |", "|---|---|---|---|---|"]
    for cause in CAUSES:
        t = totals.get(cause, Counter())
        out.append(f"| {cause} | {t['right → wrong']} | {t['wrong → right']} | {t['wrong auto-accepts']:+d} | "
                   f"{t['right auto-accepts']:+d} |")
    lost = totals.get("new-chapter proposals", Counter())
    varied = totals.get("run-to-run variation", Counter())
    scope_lines = [c["reference"] for c in rows if c["route_cause"] == "vote scope"]
    out += ["", f"The majority top-1 fell from {base['majority_top1']} to {off['majority_top1']}. New-chapter proposals "
                f"account for {lost['right → wrong'] - lost['wrong → right']} of it net ({lost['right → wrong']} lines right "
                f"→ wrong, {lost['wrong → right']} wrong → right): the candidate proposal now reads the rulings of every "
                "chapter, and where rulings of a newly indexed chapter come nearest to a line they propose their codes and "
                f"the model ranks a code of that chapter, or one their tags favour, first. Run-to-run variation accounts for "
                f"{varied['right → wrong'] - varied['wrong → right']} (lines whose baseline runs already disagreed). Where "
                "the top-1 stayed, rulings of the new chapters also entered the vote and turned right auto-accepts into "
                "review (the old vote, on the same rows, would have done the same). The vote scope changed the routes of "
                f"{len(scope_lines)} lines ({', '.join(scope_lines)}): one gained a right auto-accept, the other is "
                "SC-004's wrong auto-accept, in every run.", ""]
    crows = changed_lines("coolant")
    out += ["### The coolant set, and the plain 冷却液", "",
            "| Line | Expected | Baseline top-1 (routes) | After top-1 (routes) | Proposed | New-chapter codes proposed | "
            "Old vote's routes | Outcome change: cause | Route change: cause |", "|---|---|---|---|---|---|---|---|---|"]
    for c in crows:
        b, o = c["b"], c["o"]
        out.append(f"| {c['reference']} ({texts[c['reference']]}) | {c['expected']} | {_runs(b['top1'])} "
                   f"({_runs(short(r) for r in b['route'])}) | {_runs(o['top1'])} ({_runs(short(r) for r in o['route'])}) | "
                   f"{c['proposed']}/3 | {', '.join(c['new_props']) or 'none'} | {_runs(short(r) for r in o['unscoped'])} | "
                   + (f"{change(b, o, 'outcome')}: {c['top1_cause']}" if c["top1_cause"] else "unchanged") + " | "
                   + (f"{change(b, o, 'route')}: {c['route_cause']}" if c["route_cause"] else "unchanged") + " |")
    plain_b = next(seen for seen in zip(*runs_of("coolant", "baseline")) if seen[0]["reference"] == "coolant-8")
    plain_o = next(seen for seen in zip(*runs_of("coolant", "off")) if seen[0]["reference"] == "coolant-8")
    out += ["", f"The plain 冷却液 (coolant-8) is flagged vague in every run, so no vote routes it: its route is the "
                f"model's estimate against the ask floor of {ASK_FLOOR}. In the baseline its top-1 {plain_b[0]['top1']} came at "
                f"{_runs(r['confidence'] for r in plain_b)} (ask the shipper); after, with the rulings of chapter 38 now "
                f"indexed, the proposal added {', '.join(c for c in plain_o[0]['precedent_codes'] if c[:2] not in TWELVE) or 'none'}"
                f" and the same top-1 came at {_runs(r['confidence'] for r in plain_o)}, exactly the floor, so the line "
                "went to review: a new-chapter proposal acting through the model's estimate, not the vote scope. With the "
                "switch on it routed to ask the shipper in every run.", "",
            "## 6. Decisions left to the author", "",
            "**Note of 2026-11-19**: the author decided rule (a) (the unfiltered vote decides the auto-accept, the vote of "
            "the candidates' chapters can only send a line to review), block 3's captions and the vague rule (a vague line "
            "always asks the shipper), and rejected option (c); SC-004 passes under rule (a). See the spec's clarifications "
            "of 2026-11-19 and docs/reports/014a-regression-analysis.md, section 5. The list below is that of 2026-11-18.", "",
            "- SC-004 failed by two wrong auto-accepts: keep the chapter-scoped vote, or change it (the spec forbids a "
            "fallback without the author's decision).",
            "- The new chapters lowered the 120-line majority top-1 through the candidate proposal (section 5); the spec "
            "keeps the proposal over every chapter (clarification 1).",
            "- FR-026's criterion is not met; the customs-wording switch stays off.",
            "- A rewrite still over its 300 characters after its one retry fails the line's HS-6 step, as FR-025 says; "
            "the alternative is a cut at the last word boundary before the switch is ever turned on. Since review round 1 "
            "a runaway answer (65,521 output tokens once) is capped at 512 tokens (tested offline; confirm on the first "
            "live run with the switch on), and every attempt counts in the shipment's cost. Both matter only with the "
            "switch on.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
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
