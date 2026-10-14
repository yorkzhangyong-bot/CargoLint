"""Labelled-set evaluation (constitution Principle VII; spec SC-001, SC-002, SC-003, SC-010, SC-011).

    python tests/eval/run_eval.py                     # hybrid and vector_only on data/labelled/lines_20.jsonl
    python tests/eval/run_eval.py --modes hybrid      # one mode
    python tests/eval/run_eval.py --sample            # also run the 12-line sample and check its expected routes

Needs OPENROUTER_API_KEY and a built knowledge base (python -m rag.loader --demo). Exits non-zero when a
threshold fails or a labelled code is missing from the nomenclature. Writes tests/eval/results.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD, get_settings  # noqa: E402
from agent.llm import get_client  # noqa: E402
from agent.routing import route_line  # noqa: E402
from agent.schemas import FlagKind, LineStatus, Route, Usage  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from tools.check_description import check_descriptions  # noqa: E402
from tools.classify_hs6 import ClassifyContext, classify_lines  # noqa: E402
from tools.common import LineText  # noqa: E402

THRESHOLDS = {"flag_accuracy": 1.0, "top3_min": 10, "top1_min": 8}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def evaluate(lines: list[dict], mode: str, kb, usage: Usage, workers: int) -> dict:
    client = get_client(usage_sink=usage.add)
    inputs = [LineText(line_no=i + 1, text_zh=l["text_zh"], text_en=l["text_en"]) for i, l in enumerate(lines)]
    t0 = time.perf_counter()
    checks = check_descriptions(inputs, kb.rules, client, workers)
    for inp, chk in zip(inputs, checks):
        inp.pure_stop_word = bool(chk.flag and chk.flag.pure_stop_word)
    classes = classify_lines(inputs, ClassifyContext(hybrid=(mode == "hybrid")), kb, client, workers)
    elapsed = time.perf_counter() - t0
    rows = []
    flag_ok = top1 = top3 = clear = bad_auto = 0
    for l, chk, cls in zip(lines, checks, classes):
        exp_flag = l.get("expected_flag")
        exp_code = l.get("expected_code") or l.get("expected_top_code")
        got_flag = chk.flag.kind.value if chk.flag else "failed"
        flag_match = (got_flag == exp_flag) if exp_flag in ("vague", "stop_word") else (got_flag == "ok")
        flag_ok += flag_match
        codes = [c.code for c in cls.candidates]
        conf = cls.candidates[0].confidence if cls.candidates else None
        route, _ = route_line(chk.flag.kind if chk.flag else None, conf, cls.status if cls.status != LineStatus.pending else LineStatus.checked,
                              False, DEFAULT_THRESHOLD, ASK_FLOOR)
        if exp_flag == "ok" and exp_code:
            clear += 1
            top1 += codes[:1] == [exp_code]
            top3 += exp_code in codes[:3]
        if (got_flag in ("vague", "stop_word") or (conf is not None and conf < DEFAULT_THRESHOLD)) and route == Route.auto_accept:
            bad_auto += 1
        rows.append({"text": f"{l['text_zh']} / {l['text_en']}", "expected_flag": exp_flag, "flag": got_flag, "expected_code": exp_code,
                     "codes": codes, "confidence": conf, "route": route.value, "status": cls.status.value, "error": cls.error_reason})
    return {"mode": mode, "n": len(lines), "flag_accuracy": flag_ok / max(1, len(lines)), "clear_lines": clear, "top1": top1, "top3": top3,
            "flagged_auto_accepts": bad_auto, "elapsed_s": round(elapsed, 1), "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="hybrid,vector_only")
    ap.add_argument("--set", default=str(ROOT / "data" / "labelled" / "lines_20.jsonl"))
    ap.add_argument("--sample", action="store_true", help="also evaluate data/samples/sample_lines.json against its expected routes")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args(argv)
    settings = get_settings()
    if not settings.api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2
    kb = open_knowledge_base(settings)
    lines = load_jsonl(Path(args.set))
    missing = [l for l in lines if (l.get("expected_code") and l["expected_code"] not in kb.index)]
    sample = json.loads((ROOT / "data" / "samples" / "sample_lines.json").read_text(encoding="utf-8"))["lines"]
    missing += [l for l in sample if (l.get("expected_top_code") and l["expected_top_code"] not in kb.index)]
    if missing:
        print("LABEL INTEGRITY FAILED — codes not in the nomenclature:", [m.get("expected_code") or m.get("expected_top_code") for m in missing])
        return 3
    print(f"label integrity ok: every expected code exists in the nomenclature ({len(kb.index)} subheadings)")

    usage = Usage()
    results = {}
    ok = True
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        r = evaluate(lines, mode, kb, usage, args.workers or settings.workers)
        results[mode] = r
        print(f"\n== {mode}: flag accuracy {r['flag_accuracy']:.0%} ({int(r['flag_accuracy'] * r['n'])}/{r['n']}), "
              f"top-1 {r['top1']}/{r['clear_lines']}, top-3 {r['top3']}/{r['clear_lines']}, flagged auto-accepts {r['flagged_auto_accepts']}, {r['elapsed_s']} s")
        for row in r["rows"]:
            mark = "ok " if (row["expected_code"] in row["codes"][:3] if row["expected_code"] else row["flag"] == row["expected_flag"]) else "MISS"
            print(f"  {mark} {row['text'][:48]:48} flag {row['flag']:9} exp {str(row['expected_flag']):9} codes {row['codes']} exp {row['expected_code']} route {row['route']}"
                  + (f" ERROR {row['error'][:60]}" if row["error"] else ""))
        if mode == "hybrid":
            ok &= r["flag_accuracy"] >= THRESHOLDS["flag_accuracy"] and r["top3"] >= THRESHOLDS["top3_min"] and r["top1"] >= THRESHOLDS["top1_min"]
        ok &= r["flagged_auto_accepts"] == 0

    if args.sample:
        r = evaluate(sample, "hybrid", kb, usage, args.workers or settings.workers)
        route_hits = sum(1 for row, l in zip(r["rows"], sample) if row["route"] == l["expected_route"])
        results["sample"] = {**r, "route_hits": route_hits}
        print(f"\n== sample: routes as expected {route_hits}/{len(sample)}, flagged auto-accepts {r['flagged_auto_accepts']}")
        for row, l in zip(r["rows"], sample):
            print(f"  {'ok ' if row['route'] == l['expected_route'] else 'DIFF'} {row['text'][:44]:44} {row['flag']:9} {row['codes'][:1]} conf {row['confidence']} route {row['route']} (expected {l['expected_route']})")

    print(f"\nusage: {usage.total_tokens} tokens, {usage.calls} calls, ${usage.cost_usd:.4f} ≈ €{usage.cost_eur:.4f}")
    results["usage"] = usage.model_dump()
    results["thresholds"] = THRESHOLDS
    results["passed"] = ok
    (ROOT / "tests" / "eval" / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("PASS" if ok else "FAIL — below the SC-001/SC-002/SC-003 thresholds")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
