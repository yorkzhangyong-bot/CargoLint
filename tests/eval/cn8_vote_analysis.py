"""Feature 006: k-nearest ruling votes as the CN-8 auto-accept gate, replayed offline on the rows of a repeated eval.

    python tests/eval/cn8_vote_analysis.py

Reads tests/eval/cn8_eval.json (tests/eval/cn8_eval.py logs, per line and run, the top-40 vector hits as nearest_hits)
and writes tests/eval/cn8_vote_analysis.md. No model, embedding or other API call; no product code is changed or used
for routing. Definitions follow specs/006-stability-baseline/plan-ruling-vote.md section 3, over the runs of that eval:

- Only eligible hits count (valid on the set's date, at a CN-8 line of the HS-6, not the line's own ruling), nearest
  first by (distance rounded to 4 decimals, reference), as select_rulings ranks them.
- A variant sends a row with a CN-8 (its quote passed the evidence check) to auto-accept when no cited ruling conflicts
  and the variant's rule holds, and to review otherwise; model confidence plays no part. Rows that ask the shipper or
  failed keep their route, and so do rows without an eligible hit.
- Always-right lines are right in every run; wrong auto-accept lines are wrong in the majority result and auto-accepted
  in the majority route. A line is blocked, or sent to review, when its majority route under the variant is not
  auto-accept.
- The target: at most 3 wrong auto-accept rows in every run, and at most 10 % of today's right auto-accept rows lost.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.eval.cn8_eval import OUT, VOTE_ENTRY_COUNTRY, VOTE_ENTRY_WEIGHT, majority  # noqa: E402

REPORT = ROOT / "tests" / "eval" / "cn8_vote_analysis.md"
KS = (3, 5, 10, 20)
SHARES = (0.5, 0.6, 0.67)
MAX_WRONG_PER_RUN = 3
MAX_RIGHT_LOST = 0.10


@dataclass(frozen=True)
class Variant:
    name: str
    k: int = 1                 # nearest-1 when k == 1 and no share
    share: float | None = None
    weighted: bool = True


VARIANTS = [Variant("nearest-1")] + [
    Variant(f"{k}-nearest vote, {'weighted' if weighted else 'unweighted'}, share ≥ {t}", k, t, weighted)
    for weighted in (True, False) for k in KS for t in SHARES]


def eligible_hits(row: dict) -> list[dict]:
    hits = [h for h in row.get("nearest_hits") or [] if h["eligible"]]
    return sorted(hits, key=lambda h: (round(h["distance"], 4), h["reference"]))


def vote(hits: list[dict], weighted: bool) -> tuple[str | None, float]:
    """The majority CN-8 of the hits (none on a tie) and its share of the weight; weighted: the entry country
    VOTE_ENTRY_WEIGHT, any other 1."""
    weight: Counter = Counter()
    for h in hits:
        weight[h["cn8"]] += VOTE_ENTRY_WEIGHT if weighted and h["country"] == VOTE_ENTRY_COUNTRY else 1
    if not weight:
        return None, 0.0
    top = max(weight.values())
    leaders = [code for code, w in weight.items() if w == top]
    return (leaders[0] if len(leaders) == 1 else None), top / sum(weight.values())


def route(row: dict, v: Variant) -> str:
    """The route the variant gives one row."""
    if row["question"] or row["error"] or not row["chosen"]:
        return row["route"]
    hits = eligible_hits(row)
    if not hits:
        return row["route"]
    if row["precedent_code"] and row["precedent_code"][:8] != row["chosen"]:
        return "review"
    if v.share is None:
        return "auto_accept" if hits[0]["cn8"] == row["chosen"] else "review"
    top, share = vote(hits[:v.k], v.weighted)
    return "auto_accept" if top == row["chosen"] and share >= v.share else "review"


def baseline(runs: list[list[dict]]) -> dict:
    n = len(runs[0])
    today = [majority([run[i]["route"] for run in runs]) for i in range(n)]
    wrong = [i for i in range(n) if majority([run[i]["chosen"] for run in runs]) != runs[0][i]["expected"]]
    return {"n": n, "today": today, "majority_wrong": wrong,
            "wrong_aa": [i for i in wrong if today[i] == "auto_accept"],
            "always_right": [i for i in range(n) if all(run[i]["hit"] for run in runs)],
            "wrong_rows": [sum(r["route"] == "auto_accept" and not r["hit"] for r in run) for run in runs],
            "right_rows": sum(r["route"] == "auto_accept" and r["hit"] for run in runs for r in run)}


def measure(runs: list[list[dict]], v: Variant, base: dict) -> dict:
    n = base["n"]
    routes = [[route(run[i], v) for i in range(n)] for run in runs]
    line_route = [majority([routes[k][i] for k in range(len(runs))]) for i in range(n)]
    wrong_rows = [sum(routes[k][i] == "auto_accept" and not runs[k][i]["hit"] for i in range(n)) for k in range(len(runs))]
    right_lost = sum(1 for k, run in enumerate(runs) for i in range(n)
                     if run[i]["route"] == "auto_accept" and run[i]["hit"] and routes[k][i] != "auto_accept")
    m = {"variant": v, "routes": routes, "wrong_rows": wrong_rows, "right_lost": right_lost,
         "blocked": sum(line_route[i] != "auto_accept" for i in base["wrong_aa"]),
         "to_review": sum(base["today"][i] == "auto_accept" and line_route[i] != "auto_accept"
                          for i in base["always_right"])}
    m["meets"] = max(wrong_rows) <= MAX_WRONG_PER_RUN and right_lost <= MAX_RIGHT_LOST * base["right_rows"]
    return m


def best(results: list[dict], right_rows: int) -> tuple[dict, str]:
    """The variant to look at closely, and why it was picked."""
    meeting = [m for m in results if m["meets"]]
    if meeting:
        return min(meeting, key=lambda m: (sum(m["wrong_rows"]), m["right_lost"])), \
            "it meets the target with the fewest wrong auto-accept rows"
    affordable = [m for m in results if m["right_lost"] <= MAX_RIGHT_LOST * right_rows]
    if affordable:
        return min(affordable, key=lambda m: (sum(m["wrong_rows"]), m["right_lost"])), \
            "no variant meets the target; it has the fewest wrong auto-accept rows among those losing at most 10 %"
    return min(results, key=lambda m: sum(m["wrong_rows"]) + m["right_lost"]), \
        "no variant meets the target or loses at most 10 %; it has the fewest wrong rows plus right rows lost"


def same_rulings(runs: list[list[dict]]) -> int:
    """Lines whose rulings sent and vector hits are the same, in order, in every run."""
    def key(row):
        return [s["reference"] for s in row["sent"]], [(h["reference"], h["distance"]) for h in row.get("nearest_hits") or []]
    return sum(all(key(run[i]) == key(runs[0][i]) for run in runs) for i in range(len(runs[0])))


def render(summary: dict, runs: list[list[dict]], base: dict, results: list[dict]) -> str:
    pick, why = best(results, base["right_rows"])
    right = base["right_rows"]
    today = base["wrong_rows"]
    out = [
        "# CN-8 vote analysis: the nearest EBTI rulings as the auto-accept gate",
        "",
        f"Data: iteration {summary['iteration']} (tag \"{summary.get('tag', '-')}\"), {len(runs)} runs of {base['n']} lines; "
        f"{summary['change']}. Offline replay of `tests/eval/cn8_eval.json` by `tests/eval/cn8_vote_analysis.py`; no API call. "
        f"Definitions: `specs/006-stability-baseline/plan-ruling-vote.md` section 3 and the script's docstring.",
        "",
        f"- Rulings sent and vector hits identical in every run: {same_rulings(runs)} of {base['n']} lines.",
        f"- Today: {sum(today)} wrong auto-accept rows ({' / '.join(map(str, today))} per run) and {right} right ones; "
        f"{len(base['wrong_aa'])} wrong auto-accept lines of {len(base['majority_wrong'])} lines wrong in the majority "
        f"result; {len(base['always_right'])} always-right lines, {sum(base['today'][i] == 'auto_accept' for i in base['always_right'])} "
        "of them auto-accepted today.",
        f"- Target: at most {MAX_WRONG_PER_RUN} wrong auto-accept rows in every run and at most "
        f"{MAX_RIGHT_LOST:.0%} ({MAX_RIGHT_LOST * right:.1f}) of the {right} right auto-accept rows lost. Variants that meet "
        "it are in bold.",
        "",
        "| Variant | Wrong auto-accept rows (per run) | Wrong lines blocked | Right auto-accept rows lost | "
        "Always-right lines sent to review |",
        "|---|---|---|---|---|",
        f"| today: model confidence ≥ 85 | {sum(today)} ({' / '.join(map(str, today))}) | — | — | — |",
    ]
    for m in results:
        name = f"**{m['variant'].name}**" if m["meets"] else m["variant"].name
        out.append(f"| {name} | {sum(today)} → {sum(m['wrong_rows'])} ({' / '.join(map(str, m['wrong_rows']))}) | "
                   f"{m['blocked']} of {len(base['wrong_aa'])} | {m['right_lost']} of {right} "
                   f"({m['right_lost'] / right:.1%}) | {m['to_review']} of {len(base['always_right'])} |")
    out += ["", "## The wrong lines the best variant still lets through", "",
            f"Best variant: **{pick['variant'].name}**, because {why}.", "",
            "| Line | Auto-accepted wrong in runs | Model's CN-8 | Expected | Nearest eligible hit (country) |",
            "|---|---|---|---|---|"]
    through = 0
    for i in range(base["n"]):
        bad = [k for k in range(len(runs)) if pick["routes"][k][i] == "auto_accept" and not runs[k][i]["hit"]]
        if not bad:
            continue
        through += 1
        row = runs[bad[0]][i]
        hits = eligible_hits(row)
        nearest = f"{hits[0]['cn8']} ({hits[0]['country'] or '?'})" if hits else "—"
        codes = ", ".join(sorted({runs[k][i]["chosen"] for k in bad}))
        out.append(f"| {row['reference']} | {len(bad)} of {len(runs)} | {codes} | {row['expected']} | {nearest} |")
    if not through:
        out.append("| none | | | | |")
    out.append("")
    return "\n".join(out)


def main() -> int:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    runs = data.get("runs") or [data["rows"]]
    if "nearest_hits" not in runs[0][0]:
        print("tests/eval/cn8_eval.json has no nearest_hits; run tests/eval/cn8_eval.py first")
        return 1
    history = json.loads((ROOT / "tests" / "eval" / "cn8_eval_history.json").read_text(encoding="utf-8"))
    entry = next((h for h in history if h["iteration"] == data["summary"]["iteration"]), {})
    base = baseline(runs)
    results = [measure(runs, v, base) for v in VARIANTS]
    REPORT.write_text(render(dict(data["summary"], tag=entry.get("tag")), runs, base, results), encoding="utf-8",
                      newline="\n")
    print(f"wrote {REPORT}")
    for m in results:
        print(f"{'*' if m['meets'] else ' '} {m['variant'].name:44} wrong {m['wrong_rows']} blocked {m['blocked']} "
              f"right lost {m['right_lost']} to review {m['to_review']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
