"""Evidence diagnosis of the CN-8 step (feature 006): why lines go to the shipper, from the rows of a repeated eval run.

    python tests/eval/cn8_evidence_diagnosis.py

Offline: reads tests/eval/cn8_eval.json (tests/eval/cn8_eval.py logs, for every line and run, the model's raw CN-8
output, the evidence check, the route and the rulings sent), the eval set, and the CN 2026 index and EBTI rulings from
disk; no model, embedding or other API call. Writes tests/eval/cn8_evidence_diagnosis.md.

An ask is a row the CN-8 step sent to the shipper. Each ask goes to the first class that fits:
- model-declined: the model set attribute_visible false or cn8 null; the code then checks no quote.
- source-confusion: a fragment of the quote that is not words of the description appears, as a phrase, in a CN-8 label
  path, the HS-6 label or a ruling excerpt sent in the same request.
- near-miss: every such fragment matches the description once case, whitespace, punctuation and line breaks are
  removed, or at a fuzzy partial ratio of 90 or more.
- other.
Fragments are the quote split at ";", as the prompt asks the model to separate them. A fragment is words of the
description when it passes the code's own evidence check (agent.routing.evidence_in_line).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.prompts import CN8_SYSTEM  # noqa: E402
from agent.routing import evidence_in_line  # noqa: E402
from tests.eval.cn8_eval import OUT, SET, majority  # noqa: E402

REPORT = ROOT / "tests" / "eval" / "cn8_evidence_diagnosis.md"
SOURCE_CONFUSION, NEAR_MISS, MODEL_DECLINED, OTHER = "source-confusion", "near-miss", "model-declined", "other"
CLASSES = [SOURCE_CONFUSION, NEAR_MISS, MODEL_DECLINED, OTHER]   # the order of the report; the first match is model-declined
FUZZY = 90
EXCERPT = 400   # characters of a ruling's goods description that cn8_user sends
BINS = [("0", 0, 0), ("1–69", 1, 69), ("70–84", 70, 84), ("85–98", 85, 98), ("99–100", 99, 100)]
_PUNCT = re.compile(r"[^\w\s]")


def phrase(text: str) -> str:
    """Lower case, punctuation as spaces, whitespace collapsed: the evidence check's normalisation, kept as a phrase."""
    return " ".join(_PUNCT.sub(" ", (text or "").lower()).split())


def squash(text: str) -> str:
    """Case, whitespace, punctuation and line breaks removed."""
    return re.sub(r"[\W_]+", "", (text or "").casefold())


def partial_ratio(a: str, b: str) -> float:
    """The best ratio (0-100) of the shorter string against equally long windows of the longer one, aligned on their
    matching blocks (the partial ratio of fuzzywuzzy, on difflib)."""
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if not short:
        return 0.0
    best = 0.0
    for i, j, _ in SequenceMatcher(None, short, long, autojunk=False).get_matching_blocks():
        start = max(j - i, 0)
        best = max(best, SequenceMatcher(None, short, long[start:start + len(short)], autojunk=False).ratio())
    return round(100 * best, 1)


def fragments(evidence: str) -> list[str]:
    return [f.strip() for f in (evidence or "").split(";") if f.strip()]


def in_source(fragment: str, source: str) -> bool:
    p = phrase(fragment)
    return bool(p) and f" {p} " in f" {phrase(source)} "


def near_miss(fragment: str, description: str) -> bool:
    s = squash(fragment)
    return (bool(s) and s in squash(description)) or partial_ratio(phrase(fragment), phrase(description)) >= FUZZY


def classify_quote(evidence: str, description: str, sources: list[str]) -> str:
    """Where a quote's words come from: "no quote", "words of the line", or for the fragments that are not words of the
    line source-confusion, near-miss or other."""
    parts = fragments(evidence)
    if not parts:
        return "no quote"
    failing = [f for f in parts if not evidence_in_line(f, description)]
    if not failing:
        return "words of the line"
    if any(in_source(f, s) for f in failing for s in sources):
        return SOURCE_CONFUSION
    if all(near_miss(f, description) for f in failing):
        return NEAR_MISS
    return OTHER


def classify_ask(raw: dict, description: str, sources: list[str]) -> str:
    """The class of one ask, from the model's raw output and the text of its request."""
    if not raw["attribute_visible"] or raw["cn8"] is None:
        return MODEL_DECLINED
    quote = classify_quote(raw["evidence"], description, sources)
    return quote if quote in (SOURCE_CONFUSION, NEAR_MISS) else OTHER


def request_sources(row: dict, index: Any, bti: Any) -> list[str]:
    """What the request held besides the description: the CN-8 label paths, the HS-6 label and the ruling excerpts."""
    paths = [path for _, path in index.cn8_lines(row["hs6"])]
    excerpts = [((bti.get(f"bti:{s['reference']}") or {}).get("description") or "")[:EXCERPT] for s in row["sent"]]
    return paths + [index.subheading_text(row["hs6"])] + excerpts


def asks_by_class(runs: list[list[dict]], descriptions: dict, index: Any, bti: Any) -> dict:
    out = {c: {"asks": 0, "raw_correct": 0} for c in CLASSES}
    declined_quotes: Counter = Counter()
    others = []
    for k, run in enumerate(runs, start=1):
        for row in run:
            if row["route"] != "ask_shipper":
                continue
            raw, text = row["raw"], descriptions[row["reference"]]
            sources = request_sources(row, index, bti)
            c = classify_ask(raw, text, sources)
            out[c]["asks"] += 1
            out[c]["raw_correct"] += raw["cn8"] == row["expected"]
            if c == MODEL_DECLINED:
                declined_quotes[classify_quote(raw["evidence"], text, sources)] += 1
            if c == OTHER:
                failing = [f for f in fragments(raw["evidence"]) if not evidence_in_line(f, text)]
                others.append({"reference": row["reference"], "run": k, "raw_cn8": raw["cn8"], "expected": row["expected"],
                               "quote": raw["evidence"], "description": text,
                               "from_prompt": any(in_source(f, CN8_SYSTEM) for f in failing)})
    return {"classes": out, "declined_quotes": dict(declined_quotes), "others": others}


def ruling_disagreement(runs: list[list[dict]]) -> dict:
    """Do the rulings sent span several CN-8 lines, and on the lines wrong in the majority result, did the rulings sent
    cover both the expected CN-8 and the model's own pick (the majority of its raw CN-8 outputs)?"""
    n = len(runs[0])
    lines = []
    for i in range(n):
        seen = [run[i] for run in runs]
        final = majority([r["chosen"] for r in seen])
        if final == seen[0]["expected"]:
            continue
        picks = [r["raw"]["cn8"] for r in seen if r["raw"] and r["raw"]["cn8"]]
        pick = majority(picks) if picks else None
        lines.append({"reference": seen[0]["reference"], "expected": seen[0]["expected"], "final": final, "pick": pick,
                      "both_every_run": bool(pick) and all({seen[0]["expected"], pick} <= set(r["sent_cn8"]) for r in seen),
                      "both_some_run": bool(pick) and any({seen[0]["expected"], pick} <= set(r["sent_cn8"]) for r in seen),
                      "sent_cn8": sorted({c for r in seen for c in r["sent_cn8"]})})
    other_pick = [x for x in lines if x["pick"] and x["pick"] != x["expected"]]
    return {"n": n, "span_every_run": sum(all(len(run[i]["sent_cn8"]) > 1 for run in runs) for i in range(n)),
            "span_some_run": sum(any(len(run[i]["sent_cn8"]) > 1 for run in runs) for i in range(n)),
            "wrong_lines": lines, "pick_expected": sum(1 for x in lines if x["pick"] == x["expected"]),
            "no_pick": sum(1 for x in lines if not x["pick"]), "other_pick": len(other_pick),
            "both_every_run": sum(x["both_every_run"] for x in other_pick),
            "both_some_run": sum(x["both_some_run"] for x in other_pick)}


def confidence_table(runs: list[list[dict]]) -> dict:
    """Raw confidences by attribute_visible, and for visible outputs by the evidence check."""
    groups: dict[str, list[int]] = {"visible": [], "passed": [], "rejected": [], "not run": [], "not visible": []}
    for run in runs:
        for r in run:
            raw = r["raw"]
            if raw is None:
                continue
            if raw["attribute_visible"]:
                groups["visible"].append(raw["confidence"])
                groups[r["evidence_check"]].append(raw["confidence"])
            else:
                groups["not visible"].append(raw["confidence"])
    bins = {g: [sum(lo <= v <= hi for v in vals) for _, lo, hi in BINS] for g, vals in groups.items()}
    return {"bins": bins, "values": {g: Counter(vals).most_common() for g, vals in groups.items()}}


def _cell(text: Any) -> str:
    text = str(text or "").replace("\\", "\\\\").replace("<", "&lt;")
    for ch in "|[]_*`":
        text = text.replace(ch, "\\" + ch)
    return "<br>".join(line.rstrip() for line in text.strip().splitlines()) or "—"


def render(summary: dict, rows: int, asks: dict, rulings: dict, conf: dict) -> str:
    total = sum(v["asks"] for v in asks["classes"].values())
    letters = dict(zip(CLASSES, "abcd"))
    out = [
        "# CN-8 evidence diagnosis: why lines go to the shipper",
        "",
        f"Data: iteration {summary['iteration']} (tag \"{summary.get('tag', '-')}\"), {summary.get('repeat', 1)} runs of "
        f"{summary['n']} lines of the fixed EBTI set. Same prompt (prompt-evidence-v2) and settings as iteration 7, run "
        "again because iteration 7 did not log the model's raw output. Offline analysis of `tests/eval/cn8_eval.json` by "
        "`tests/eval/cn8_evidence_diagnosis.py`; no API call.",
        "",
        "## 1. Asks by cause",
        "",
        f"Every row the CN-8 step sent to the shipper: {total} of {rows} (line × run). Each ask goes to the first class "
        "that fits, in this order:",
        "",
        "1. **model-declined**: the model set attribute_visible false or cn8 null. The code then checks no quote.",
        "2. **source-confusion**: a fragment of the quote that is not words of the description appears, as a phrase, in "
        "a CN-8 label path, the HS-6 label or a ruling excerpt sent in the same request.",
        "3. **near-miss**: every such fragment matches the description once case, whitespace, punctuation and line breaks "
        f"are removed, or at a fuzzy partial ratio of {FUZZY} or more.",
        "4. **other**.",
        "",
        "Fragments are the quote split at \";\". A fragment is words of the description when it passes the code's own "
        "evidence check (`agent.routing.evidence_in_line`).",
        "",
        "| Class | Asks | Correct CN-8 in the raw output |",
        "|---|---|---|",
    ]
    for c in CLASSES:
        v = asks["classes"][c]
        out.append(f"| {letters[c]}) {c} | {v['asks']} | {v['raw_correct']} |")
    out.append(f"| All asks | {total} | {sum(v['raw_correct'] for v in asks['classes'].values())} |")
    dq = asks["declined_quotes"]
    if dq:
        out += ["", "Where the quotes of the model-declined asks would fall if checked: "
                + ", ".join(f"{k} {v}" for k, v in sorted(dq.items(), key=lambda kv: -kv[1])) + "."]
    if asks["others"]:
        out += ["", "### d) other: quote and description", "",
                "| Line | Run | Raw CN-8 (expected) | Quote | Description |", "|---|---|---|---|---|"]
        out += [f"| {_cell(o['reference'])} | {o['run']} | {o['raw_cn8'] or '—'} ({o['expected']}) | {_cell(o['quote'])} | "
                f"{_cell(o['description'])} |" for o in asks["others"]]
        prompt = [o for o in asks["others"] if o["from_prompt"]]
        out += ["", f"{len(prompt)} of these {len(asks['others'])} asks quote a phrase of the CN-8 system prompt itself"
                + (": " + ", ".join(f"{o['reference']} (run {o['run']})" for o in prompt) if prompt else "") + "."]
    r = rulings
    out += [
        "",
        "## 2. Ruling disagreement",
        "",
        f"- Lines whose rulings sent span more than one CN-8: {r['span_every_run']} of {r['n']} in every run "
        f"({r['span_some_run']} in at least one run).",
        f"- Lines wrong in the majority result: {len(r['wrong_lines'])}. The model's own pick (the majority of its raw "
        f"CN-8 outputs, before the evidence check) was the expected CN-8 on {r['pick_expected']}, another CN-8 on "
        f"{r['other_pick']}, and none on {r['no_pick']}.",
        f"- Of the {r['other_pick']} lines picked at another CN-8, {r['both_every_run']} had rulings at both the expected "
        f"and the picked CN-8 among those sent in every run ({r['both_some_run']} in at least one run).",
        "",
        "| Line | Expected | Model's pick | Majority result | Rulings at both, every run | CN-8 lines of the rulings sent |",
        "|---|---|---|---|---|---|",
    ]
    out += [f"| {_cell(x['reference'])} | {x['expected']} | {x['pick'] or '—'} | {x['final'] or 'ask'} | "
            f"{'—' if not x['pick'] or x['pick'] == x['expected'] else ('yes' if x['both_every_run'] else 'no')} | "
            f"{', '.join(x['sent_cn8'])} |" for x in r["wrong_lines"]]
    b = conf["bins"]
    out += [
        "",
        "## 3. Confidence of the raw output",
        "",
        "Every raw output, by attribute_visible; the visible ones also by the evidence check. The prompt asks for 85-98 "
        "when the evidence words state the deciding attribute and 70-84 when the choice is inferred, so a level-b answer "
        "(the attribute follows from stated facts) belongs in 70-84.",
        "",
        "| Confidence | Visible: all | Visible, evidence passed | Visible, evidence rejected | Visible, cn8 null "
        "(not checked) | Not visible |",
        "|---|---|---|---|---|---|",
    ]
    for k, (label, _, _) in enumerate(BINS):
        out.append(f"| {label} | {b['visible'][k]} | {b['passed'][k]} | {b['rejected'][k]} | {b['not run'][k]} | "
                   f"{b['not visible'][k]} |")
    out.append(f"| All | {sum(b['visible'])} | {sum(b['passed'])} | {sum(b['rejected'])} | {sum(b['not run'])} | "
               f"{sum(b['not visible'])} |")
    for g, label in (("visible", "visible"), ("not visible", "not visible")):
        values = conf["values"][g]
        if values:
            out.append("")
            out.append(f"Exact values, {label}: " + ", ".join(f"{v} × {c}" for v, c in values) + ".")
    out.append("")
    return "\n".join(out)


def main() -> int:
    from agent.config import STORE_DIR
    from rag.bti import BTIStore
    from rag.loader import NOMENCLATURE_JSONL
    from rag.nomenclature import NomenclatureIndex

    data = json.loads(OUT.read_text(encoding="utf-8"))
    runs = data.get("runs") or [data["rows"]]
    if "raw" not in runs[0][0]:
        print("tests/eval/cn8_eval.json has no raw outputs; run tests/eval/cn8_eval.py first")
        return 1
    descriptions = {r["reference"]: r["description"] for r in json.loads(SET.read_text(encoding="utf-8"))["rulings"]}
    index = NomenclatureIndex.from_jsonl(NOMENCLATURE_JSONL)
    bti = BTIStore.from_jsonl(STORE_DIR / "bti_docs.jsonl")
    history = json.loads((ROOT / "tests" / "eval" / "cn8_eval_history.json").read_text(encoding="utf-8"))
    entry = next((h for h in history if h["iteration"] == data["summary"]["iteration"]), {})
    summary = dict(data["summary"], tag=entry.get("tag"))
    asks = asks_by_class(runs, descriptions, index, bti)
    rulings = ruling_disagreement(runs)
    conf = confidence_table(runs)
    REPORT.write_text(render(summary, sum(len(run) for run in runs), asks, rulings, conf), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    print("asks: " + ", ".join(f"{c} {v['asks']} (raw correct {v['raw_correct']})" for c, v in asks["classes"].items()))
    print(f"declined quotes: {asks['declined_quotes']}")
    print(f"rulings: span >1 CN-8 every run {rulings['span_every_run']}/{rulings['n']} (some run {rulings['span_some_run']}); "
          f"majority-wrong {len(rulings['wrong_lines'])}: pick expected {rulings['pick_expected']}, other "
          f"{rulings['other_pick']} (both every run {rulings['both_every_run']}, some run {rulings['both_some_run']}), "
          f"none {rulings['no_pick']}")
    print(f"confidence bins {[b[0] for b in BINS]}: " + "; ".join(f"{g} {v}" for g, v in conf["bins"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
