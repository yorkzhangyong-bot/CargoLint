"""CN-8 evaluation (feature 004, SC-002): run the CN-8 step on the fixed EBTI set and count top-1 hits.

    python tests/eval/cn8_eval.py --iteration 2 --change "what changed since the last iteration"

Live: needs OPENROUTER_API_KEY and the full knowledge base, and spends credits, so run it only when the author asks.
Each ruling's goods description is the line text and its HS-6 the decided HS-6; its own reference is never a precedent
(leave-one-out); ruling validity is judged on the set's build date. Top-1 is the chosen CN-8, written by rule or to
confirm; a question or a failure counts as a miss. Writes tests/eval/cn8_eval.json (this run, line by line), records
the iteration in tests/eval/cn8_eval_history.json, renders the report tests/eval/cn8_eval.md, and exits non-zero below
60 of 120.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import get_settings  # noqa: E402
from agent.llm import get_client  # noqa: E402
from agent.schemas import Cn8Line, Usage  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from tools.classify_cn8 import choose_cn8  # noqa: E402
from tools.common import run_per_line  # noqa: E402

SET = ROOT / "tests" / "eval" / "cn8_eval_set.json"
OUT = ROOT / "tests" / "eval" / "cn8_eval.json"
HISTORY = ROOT / "tests" / "eval" / "cn8_eval_history.json"
REPORT = ROOT / "tests" / "eval" / "cn8_eval.md"
THRESHOLD = 85
TARGET = 60


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
    out += ["", f"Model: {history[-1]['model'] if history else '-'}. Line-by-line results of the latest run: "
            "`tests/eval/cn8_eval.json`; earlier runs are in the git history of that file.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iteration", type=int, required=True, help="iteration number against the fixed set")
    ap.add_argument("--change", required=True, help="what changed since the previous iteration")
    args = ap.parse_args(argv)
    data = json.loads(SET.read_text(encoding="utf-8"))
    rulings = data["rulings"]
    as_of = date.fromisoformat(data["built_on"])
    settings = get_settings()
    usage = Usage()
    kb = open_knowledge_base(settings, usage_sink=usage.add)
    client = get_client(usage_sink=usage.add, settings=settings)
    print(f"iteration {args.iteration}: {len(rulings)} rulings; BTI vectors "
          f"{'loaded' if getattr(kb, 'bti_vectors', None) is not None else 'not loaded'}; model {settings.chat_model}")

    def one(item):
        i, r = item
        line = Cn8Line(line_no=i, text_en=r["description"], hs6=r["hs6"])
        return choose_cn8(line, r["hs6"], kb, client, THRESHOLD, as_of, exclude_refs=frozenset({r["reference"]}))

    t0 = time.perf_counter()
    choices = run_per_line(list(enumerate(rulings, start=1)), one, lambda item, exc: None, workers=settings.workers)
    elapsed = time.perf_counter() - t0
    rows = []
    for r, c in zip(rulings, choices):
        rows.append({"reference": r["reference"], "chapter": r["chapter"], "hs6": r["hs6"], "expected": r["cn8"],
                     "language": r["language"], "options": len(c.options) if c else None,
                     "chosen": c.cn8 if c else None, "confidence": c.confidence if c else None,
                     "written": bool(c and c.cn8 and c.written_by), "question": c.question if c else None,
                     "error": (c.error if c else "timed out"), "precedent": c.precedent.reference if c and c.precedent else None,
                     "precedent_code": c.precedent.code if c and c.precedent else None,
                     "evidence": c.evidence if c else None, "hit": bool(c and c.cn8 == r["cn8"])})
    hits = sum(r["hit"] for r in rows)
    written = [r for r in rows if r["written"]]
    per_chapter: dict[str, dict] = {}
    for r in rows:
        ch = per_chapter.setdefault(r["chapter"], {"n": 0, "hits": 0})
        ch["n"] += 1
        ch["hits"] += r["hit"]
    summary = {
        "iteration": args.iteration, "change": args.change, "top1": hits, "n": len(rows), "target": TARGET,
        "passed": hits >= TARGET, "questions": sum(1 for r in rows if r["question"]),
        "failures": sum(1 for r in rows if r["error"]), "written": len(written),
        "written_correct": sum(r["hit"] for r in written), "to_confirm": sum(1 for r in rows if r["chosen"] and not r["written"]),
        "with_precedent": sum(1 for r in rows if r["precedent"]), "per_chapter": per_chapter,
        "elapsed_s": round(elapsed, 1), "threshold": THRESHOLD, "set_built_on": data["built_on"], "model": settings.chat_model,
        "usage": {"total_tokens": usage.total_tokens, "calls": usage.calls, "cost_usd": round(usage.cost_usd, 4),
                  "cost_eur": round(usage.cost_eur, 4)},
    }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                   newline="\n")
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    history = [h for h in history if h["iteration"] != args.iteration] + [{
        "iteration": args.iteration, "run_on": date.today().isoformat(), "change": args.change, "model": settings.chat_model,
        "threshold": THRESHOLD, "top1": hits, "n": len(rows), "written": len(written),
        "written_wrong": len(written) - summary["written_correct"], "to_confirm": summary["to_confirm"],
        "questions": summary["questions"], "failures": summary["failures"], "with_precedent": summary["with_precedent"],
        "per_chapter": {c: f"{v['hits']}/{v['n']}" for c, v in per_chapter.items()}, "elapsed_s": round(elapsed, 1),
        "cost_usd": round(usage.cost_usd, 4), "cost_eur": round(usage.cost_eur, 4)}]
    history.sort(key=lambda h: h["iteration"])
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(render_report(history, data), encoding="utf-8", newline="\n")
    print(f"CN-8 top-1: {hits}/{len(rows)} (target {TARGET})")
    print(f"  written by rule {summary['written']} (wrong {summary['written'] - summary['written_correct']}), "
          f"to confirm {summary['to_confirm']}, asked the shipper {summary['questions']}, failures {summary['failures']}, "
          f"with precedent {summary['with_precedent']}")
    print("  per chapter: " + ", ".join(f"{c} {v['hits']}/{v['n']}" for c, v in per_chapter.items()))
    print(f"  {elapsed:.0f} s; usage {usage.total_tokens} tokens, {usage.calls} calls, ${usage.cost_usd:.4f} ≈ €{usage.cost_eur:.4f}")
    return 0 if hits >= TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
