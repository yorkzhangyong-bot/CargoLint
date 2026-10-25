"""CN-8 evaluation (feature 004, SC-002): run the CN-8 step on the fixed EBTI set and count top-1 hits.

    python tests/eval/cn8_eval.py --iteration 2 --change "what changed since the last iteration"
    python tests/eval/cn8_eval.py --repeat 3                               # stability: 3 independent runs
    python tests/eval/cn8_eval.py --repeat 3 --temperature 0 --seed 42     # the same with model overrides

Live: needs OPENROUTER_API_KEY and the full knowledge base, and spends credits, so run it only when the author asks.
Each ruling's goods description is the line text and its HS-6 the decided HS-6; its own reference is never a precedent
(leave-one-out); ruling validity is judged on the set's build date. Top-1 is the chosen CN-8, written by rule or to
confirm; a question or a failure counts as a miss. Writes tests/eval/cn8_eval.json (this run, line by line), records
the iteration in tests/eval/cn8_eval_history.json, renders the report tests/eval/cn8_eval.md, and exits non-zero below
60 of 120.

Every row also keeps the rulings sent to the model for its line: reference, CN-8 and rank (the order they were sent,
nearest first by embedding when the BTI vectors are loaded), recorded around tools.classify_cn8.select_rulings for the
run only, and whether one of them is at the expected CN-8. The report gives for each entry the share of wrong results
(line × run) in which a ruling at the expected CN-8 was among those sent. Each row also keeps the model's raw CN-8 output
before the code's checks (cn8, attribute_visible, confidence, evidence, precedent, rationale), the outcome of the evidence
check (passed; rejected; not run, when the model declined) and the final route, recorded around the client and
tools.classify_cn8.evidence_in_line the same way; tests/eval/cn8_evidence_diagnosis.py reads them.

--repeat N (N > 1) classifies every line N times, independently, and adds the stability of the CN-8 step. The HS-6 is
fixed by the set, so top-1 means the CN-8. Measures: the share of lines whose top-1 is the same in all N runs; the share
whose decision is the same (auto_accept: written by rule; review: to confirm, or failed, as route_line routes a failed
CN-8 step; ask_shipper: a question); the accuracy of the majority top-1 (a tie goes to the earliest run); and the lines
whose top-1 differed. The entry is appended to the history with "repeat": N and a tag, "baseline-stability" unless
--tag names another; its usual fields describe run 1. Without --iteration it takes the next number, as the validation
run did. --temperature and --seed override the chat model for this run only; agent/llm.py and agent/config.py stay as
they are.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import get_settings  # noqa: E402
from agent.llm import OpenRouterRawClient, get_chat_model, get_client, set_client_factory  # noqa: E402
from agent.schemas import Cn8Line, Usage  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
import tools.classify_cn8 as classify_cn8  # noqa: E402
from tools.classify_cn8 import choose_cn8  # noqa: E402
from tools.common import run_per_line  # noqa: E402

SET = ROOT / "tests" / "eval" / "cn8_eval_set.json"
OUT = ROOT / "tests" / "eval" / "cn8_eval.json"
HISTORY = ROOT / "tests" / "eval" / "cn8_eval_history.json"
REPORT = ROOT / "tests" / "eval" / "cn8_eval.md"
THRESHOLD = 85
TARGET = 60
TAG = "baseline-stability"
_rec = threading.local()   # per worker thread, for the line in hand: the rulings sent, the raw output, the evidence check
CHECK = {True: "passed", False: "rejected", None: "not run"}   # not run: the model declined, so the code checks no quote


class OverriddenClient(OpenRouterRawClient):
    """The real OpenRouter backend whose chat model carries this run's temperature or seed."""

    def __init__(self, settings: Any, overrides: dict) -> None:
        super().__init__(settings)
        self._model = get_chat_model(settings, **overrides)


def decision(row: dict) -> str:
    """The CN-8 step's decision for one line, in route terms."""
    if row["question"]:
        return "ask_shipper"
    return "auto_accept" if row["written"] else "review"


def majority(values: list) -> Any:
    """The most frequent value; a tie goes to the value seen first."""
    counts = Counter(values)
    return next(v for v in values if counts[v] == max(counts.values()))


def stability(runs: list[list[dict]]) -> dict:
    """Consistency across N runs of the same lines; `runs` holds each run's rows in set order."""
    n = len(runs[0])
    same_code = same_decision = majority_hits = 0
    unstable = []
    for seen in zip(*runs):
        codes = [r["chosen"] for r in seen]
        same_code += len(set(codes)) == 1
        same_decision += len({decision(r) for r in seen}) == 1
        majority_hits += majority(codes) == seen[0]["expected"]
        if len(set(codes)) > 1:
            unstable.append({"reference": seen[0]["reference"], "hs6": seen[0]["hs6"], "expected": seen[0]["expected"],
                             "seen": [{"cn8": r["chosen"], "confidence": r["confidence"], "decision": decision(r)}
                                      for r in seen]})
    return {"same_code": same_code, "code_consistency": round(same_code / n, 4), "same_decision": same_decision,
            "decision_consistency": round(same_decision / n, 4), "majority_top1": majority_hits, "unstable": unstable}


def _recording(fn: Any, slot: str) -> Any:
    """fn, also keeping for the calling thread what it returns, as _rec.<slot>."""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = fn(*args, **kwargs)
        setattr(_rec, slot, result)
        return result
    return wrapper


def _raw(out: Any) -> dict | None:
    """The CN-8 output as the model returned it, before the code's checks."""
    if out is None:
        return None
    return {"cn8": out.cn8, "attribute_visible": out.attribute_visible, "confidence": out.confidence,
            "evidence": out.evidence, "precedent": out.precedent, "rationale": out.rationale}


def run_once(rulings: list[dict], kb: Any, client: Any, as_of: date, workers: int) -> tuple[list[dict], float]:
    """One pass of the CN-8 step over the set: one row per ruling, with the rulings sent to the model, its raw output,
    the evidence check and the route, and the elapsed seconds."""
    recorder = SimpleNamespace(call=_recording(client.call, "raw")) if client is not None else None

    def one(item):
        i, r = item
        _rec.rulings, _rec.raw, _rec.check = [], None, None   # a subheading with one CN-8 line sends none
        line = Cn8Line(line_no=i, text_en=r["description"], hs6=r["hs6"])
        choice = choose_cn8(line, r["hs6"], kb, recorder, THRESHOLD, as_of, exclude_refs=frozenset({r["reference"]}))
        return choice, _rec.rulings, _rec.raw, _rec.check

    saved = classify_cn8.select_rulings, classify_cn8.evidence_in_line
    classify_cn8.select_rulings = _recording(saved[0], "rulings")   # choose_cn8 looks both up on every call;
    classify_cn8.evidence_in_line = _recording(saved[1], "check")   # recorded for this run only
    t0 = time.perf_counter()
    try:
        results = run_per_line(list(enumerate(rulings, start=1)), one, lambda item, exc: None, workers=workers)
    finally:
        classify_cn8.select_rulings, classify_cn8.evidence_in_line = saved
    elapsed = time.perf_counter() - t0
    rows = []
    for r, res in zip(rulings, results):
        c, sent, raw, check = res if res is not None else (None, [], None, None)
        row = {"reference": r["reference"], "chapter": r["chapter"], "hs6": r["hs6"], "expected": r["cn8"],
               "language": r["language"], "options": len(c.options) if c else None,
               "chosen": c.cn8 if c else None, "confidence": c.confidence if c else None,
               "written": bool(c and c.cn8 and c.written_by), "question": c.question if c else None,
               "error": (c.error if c else "timed out"), "precedent": c.precedent.reference if c and c.precedent else None,
               "precedent_code": c.precedent.code if c and c.precedent else None,
               "evidence": c.evidence if c else None, "hit": bool(c and c.cn8 == r["cn8"]),
               "sent": [{"reference": p.reference, "cn8": p.code[:8], "rank": k} for k, p in enumerate(sent, start=1)],
               "sent_cn8": sorted({p.code[:8] for p in sent}), "expected_sent": any(p.code[:8] == r["cn8"] for p in sent),
               "raw": _raw(raw), "evidence_check": CHECK[check]}
        row["route"] = decision(row)
        rows.append(row)
    return rows, elapsed


def expected_sent_share(runs: list[list[dict]]) -> dict:
    """Over every wrong result (line × run; a question is a miss): how many had a ruling at the expected CN-8 among the
    rulings sent to the model."""
    wrong = [r for run in runs for r in run if not r["hit"]]
    with_expected = sum(1 for r in wrong if r["expected_sent"])
    return {"wrong": len(wrong), "with_expected": with_expected,
            "share": round(with_expected / len(wrong), 4) if wrong else None}


def _seen(entry: dict) -> str:
    return " · ".join(f"{s['cn8'] or 'no code'} ({s['confidence']}, {s['decision']})" for s in entry["seen"])


def render_report(history: list[dict], data: dict) -> str:
    chapters = list(history[-1]["per_chapter"]) if history else []
    out = [
        "# CN-8 evaluation report (feature 004, SC-002)",
        "",
        f"- **Set**: `tests/eval/cn8_eval_set.json`, fixed before any tuning: {len(data['rulings'])} valid EBTI rulings, "
        f"{data['per_chapter']} from each of the 12 target chapters, all under subheadings with at least two CN 2026 CN-8 "
        f"lines (built {data['built_on']}, seed {data['seed']}).",
        "- **Method**: each ruling's goods description is the line text and its HS-6 the decided HS-6; its own ruling is "
        "never a precedent; auto-accept threshold 85; `python tests/eval/cn8_eval.py`.",
        "- **Top-1** counts the chosen CN-8, written by rule or to confirm; a question or a failure is a miss. The target is "
        f"{TARGET} of {len(data['rulings'])}.",
        "",
        "| Iteration | Run on | Change | Top-1 | Written by rule | Written, wrong | To confirm | Asked the shipper | Failures | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for h in history:
        out.append(f"| {h['iteration']} | {h['run_on']} | {h['change']} | {h['top1']}/{h['n']} | {h['written']} | "
                   f"{h['written_wrong']} | {h['to_confirm']} | {h['questions']} | {h['failures']} | "
                   f"${h['cost_usd']:.4f} (€{h['cost_eur']:.4f}), {h['elapsed_s']:.0f} s |")
    out += ["", "## Top-1 per chapter", "", "| Iteration | " + " | ".join(chapters) + " |",
            "|---|" + "---|" * len(chapters)]
    for h in history:
        out.append(f"| {h['iteration']} | " + " | ".join(h["per_chapter"].get(c, "-") for c in chapters) + " |")
    stable = [h for h in history if h.get("repeat", 1) > 1]
    if stable:
        out += ["", "## Stability (repeated runs)", "",
                "Each line classified N times, independently. Same CN-8: the top-1 is identical in all runs. Same "
                "decision: written by rule (auto_accept), to confirm or failed (review), or a question (ask_shipper) in "
                "all runs. Majority: the most frequent top-1 taken as the answer (a tie goes to the earliest run). The "
                "rows above show run 1 of these entries.", "",
                "| Iteration | Run on | Tag | Temperature | Seed | Runs | Top-1 per run | Majority top-1 | Same CN-8 | "
                "Same decision | Cost |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for h in stable:
            n = h["n"]
            seed = h["seed"] if h["seed"] is not None else "none"
            out.append(f"| {h['iteration']} | {h['run_on']} | {h.get('tag', '-')} | {h['temperature']} | {seed} | {h['repeat']} | "
                       f"{' / '.join(str(t) for t in h['top1_runs'])} of {n} | {h['majority_top1']}/{n} | "
                       f"{h['code_consistency']:.1%} | {h['decision_consistency']:.1%} | "
                       f"${h['cost_usd']:.4f} (€{h['cost_eur']:.4f}) |")
        for h in stable:
            k = len(h["unstable"])
            out += ["", f"Iteration {h['iteration']}: {k} line{'' if k == 1 else 's'} whose top-1 differed between runs"
                        + (" (chosen CN-8, confidence, decision per run):" if k else "."), ""]
            out += [f"- {u['reference']} (HS-6 {u['hs6']}, expected {u['expected']}): {_seen(u)}" for u in h["unstable"]]
    logged = [h for h in history if h.get("expected_sent")]
    if logged:
        out += ["", "## Rulings sent to the model", "",
                "Wrong results (line × run; a question to the shipper is a miss) in which a ruling at the expected CN-8 was "
                f"among the rulings sent to the model. Logged since iteration {logged[0]['iteration']}.", ""]
        for h in logged:
            s = h["expected_sent"]
            share = f" ({s['share']:.1%})" if s["share"] is not None else ""
            out.append(f"- Iteration {h['iteration']}: {s['with_expected']} of {s['wrong']} wrong results{share}.")
    out += ["", f"Model: {history[-1]['model'] if history else '-'}. Line-by-line results of the latest run: "
            "`tests/eval/cn8_eval.json`; earlier runs are in the git history of that file.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iteration", type=int, help="iteration number against the fixed set (a repeated run takes the next)")
    ap.add_argument("--change", help="what changed since the previous iteration (generated for a repeated run)")
    ap.add_argument("--repeat", type=int, default=1, help="classify every line N times, independently (default 1)")
    ap.add_argument("--temperature", type=float, help="chat-model temperature for this run only")
    ap.add_argument("--seed", type=int, help="chat-model seed for this run only")
    ap.add_argument("--tag", help=f"tag of the history entry (a repeated run defaults to {TAG})")
    args = ap.parse_args(argv)
    if args.repeat < 1:
        ap.error("--repeat must be 1 or more")
    if args.repeat == 1 and (args.iteration is None or args.change is None):
        ap.error("a single run needs --iteration and --change")
    data = json.loads(SET.read_text(encoding="utf-8"))
    rulings = data["rulings"]
    as_of = date.fromisoformat(data["built_on"])
    settings = get_settings()
    usage = Usage()
    kb = open_knowledge_base(settings, usage_sink=usage.add)
    overrides = {k: v for k, v in (("temperature", args.temperature), ("seed", args.seed)) if v is not None}
    if overrides:
        set_client_factory(lambda: OverriddenClient(settings, overrides))
    client = get_client(usage_sink=usage.add, settings=settings)
    model = client.raw._model
    temperature, seed = getattr(model, "temperature", None), getattr(model, "seed", None)   # what the calls carry
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    iteration = args.iteration if args.iteration is not None else max((h["iteration"] for h in history), default=0) + 1
    change = args.change or (f"stability baseline: {args.repeat} independent runs, temperature {temperature}, "
                             f"seed {seed if seed is not None else 'none'}; the row shows run 1")
    print(f"iteration {iteration}: {len(rulings)} rulings × {args.repeat} run(s); BTI vectors "
          f"{'loaded' if getattr(kb, 'bti_vectors', None) is not None else 'not loaded'}; model {settings.chat_model}, "
          f"temperature {temperature}, seed {seed}")

    runs, elapsed, costs = [], 0.0, []
    for k in range(args.repeat):
        before = usage.cost_eur
        rows, seconds = run_once(rulings, kb, client, as_of, settings.workers)
        runs.append(rows)
        elapsed += seconds
        costs.append(round(usage.cost_eur - before, 4))
        if args.repeat > 1:
            print(f"  run {k + 1}: top-1 {sum(r['hit'] for r in rows)}/{len(rows)}, {seconds:.0f} s, €{costs[-1]:.4f}")
    rows = runs[0]
    hits = sum(r["hit"] for r in rows)
    written = [r for r in rows if r["written"]]
    per_chapter: dict[str, dict] = {}
    for r in rows:
        ch = per_chapter.setdefault(r["chapter"], {"n": 0, "hits": 0})
        ch["n"] += 1
        ch["hits"] += r["hit"]
    summary = {
        "iteration": iteration, "change": change, "top1": hits, "n": len(rows), "target": TARGET,
        "passed": hits >= TARGET, "questions": sum(1 for r in rows if r["question"]),
        "failures": sum(1 for r in rows if r["error"]), "written": len(written),
        "written_correct": sum(r["hit"] for r in written), "to_confirm": sum(1 for r in rows if r["chosen"] and not r["written"]),
        "with_precedent": sum(1 for r in rows if r["precedent"]), "per_chapter": per_chapter,
        "elapsed_s": round(elapsed, 1), "threshold": THRESHOLD, "set_built_on": data["built_on"], "model": settings.chat_model,
        "usage": {"total_tokens": usage.total_tokens, "calls": usage.calls, "cost_usd": round(usage.cost_usd, 4),
                  "cost_eur": round(usage.cost_eur, 4)},
    }
    entry = {
        "iteration": iteration, "run_on": date.today().isoformat(), "change": change, "model": settings.chat_model,
        "threshold": THRESHOLD, "top1": hits, "n": len(rows), "written": len(written),
        "written_wrong": len(written) - summary["written_correct"], "to_confirm": summary["to_confirm"],
        "questions": summary["questions"], "failures": summary["failures"], "with_precedent": summary["with_precedent"],
        "per_chapter": {c: f"{v['hits']}/{v['n']}" for c, v in per_chapter.items()}, "elapsed_s": round(elapsed, 1),
        "cost_usd": round(usage.cost_usd, 4), "cost_eur": round(usage.cost_eur, 4)}
    report: dict = {"summary": summary, "rows": rows}
    sent = summary["expected_sent"] = entry["expected_sent"] = expected_sent_share(runs)
    tag = args.tag or (TAG if args.repeat > 1 else None)
    if tag:
        entry["tag"] = tag
    if overrides or args.repeat > 1:
        entry.update({"temperature": temperature, "seed": seed})
    if args.repeat > 1:
        st = stability(runs)
        summary.update({"repeat": args.repeat, "top1_runs": [sum(r["hit"] for r in run) for run in runs],
                        "cost_eur_runs": costs, **st})
        entry.update({"repeat": args.repeat, "top1_runs": summary["top1_runs"],
                      "majority_top1": st["majority_top1"], "code_consistency": st["code_consistency"],
                      "decision_consistency": st["decision_consistency"], "unstable": st["unstable"]})
        report["runs"] = runs
        history.append(entry)        # appended: a stability run never replaces an iteration
    else:
        history = [h for h in history if h["iteration"] != iteration] + [entry]
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    history.sort(key=lambda h: h["iteration"])
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(render_report(history, data), encoding="utf-8", newline="\n")
    print(f"CN-8 top-1: {hits}/{len(rows)} (target {TARGET})" + (" — run 1" if args.repeat > 1 else ""))
    print(f"  written by rule {summary['written']} (wrong {summary['written'] - summary['written_correct']}), "
          f"to confirm {summary['to_confirm']}, asked the shipper {summary['questions']}, failures {summary['failures']}, "
          f"with precedent {summary['with_precedent']}")
    print("  per chapter: " + ", ".join(f"{c} {v['hits']}/{v['n']}" for c, v in per_chapter.items()))
    if args.repeat > 1:
        n = len(rows)
        print(f"stability over {args.repeat} runs: top-1 per run {summary['top1_runs']}; majority top-1 "
              f"{st['majority_top1']}/{n}; same CN-8 in all runs {st['same_code']}/{n} ({st['code_consistency']:.1%}); "
              f"same decision {st['same_decision']}/{n} ({st['decision_consistency']:.1%})")
        for u in st["unstable"]:
            print(f"  {u['reference']} (HS-6 {u['hs6']}, expected {u['expected']}): {_seen(u)}")
    print(f"expected CN-8 among the rulings sent: {sent['with_expected']} of {sent['wrong']} wrong results"
          + (f" ({sent['share']:.1%})" if sent["share"] is not None else ""))
    print(f"  {elapsed:.0f} s; usage {usage.total_tokens} tokens, {usage.calls} calls, ${usage.cost_usd:.4f} ≈ €{usage.cost_eur:.4f}")
    return 0 if hits >= TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
