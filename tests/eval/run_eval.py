"""Labelled-set evaluation (constitution Principle VII; spec SC-001, SC-002, SC-003, SC-010, SC-011).

    python tests/eval/run_eval.py                     # hybrid and vector_only on data/labelled/lines_20.jsonl
    python tests/eval/run_eval.py --modes hybrid      # one mode
    python tests/eval/run_eval.py --sample            # also run the 12-line sample and check its expected routes

The sample run also takes every line whose HS-6 the routing rule auto-decides through the CN-8 step and the TARIC step
(feature 004), routes it with an open CN-8 question or a failed step, and prints "SC-005: N unconfirmed writes".

Needs OPENROUTER_API_KEY and a built knowledge base (python -m rag.loader --demo). Exits non-zero when a
threshold fails or a labelled code is missing from the nomenclature. Writes tests/eval/results.json.
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

from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD, get_settings  # noqa: E402
from agent.llm import get_client  # noqa: E402
from agent.routing import cn8_precedent_conflict, hs6_auto_decided, route_line  # noqa: E402
from agent.schemas import Cn8Choice, FlagKind, LineStatus, Route, TaricRule, Usage  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from tools.check_description import check_descriptions  # noqa: E402
from tools.classify_hs6 import ClassifyContext, classify_lines  # noqa: E402
from tools.classify_cn8 import choose_cn8  # noqa: E402
from tools.common import LineText, run_per_line  # noqa: E402
from tools.lookup_taric import taric_outcome  # noqa: E402

THRESHOLDS = {"flag_accuracy": 1.0, "top3_min": 10, "top1_min": 8}
ORIGIN = "CN"   # the sample's goods come from Yiwu


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def finer_steps(inputs: list[LineText], checks, classes, kb, client, workers: int) -> dict[int, tuple]:
    """Feature 004 (T059): the CN-8 step, then the TARIC step for a chosen CN-8, for every line whose HS-6 the routing
    rule auto-decides. Returns {index: (Cn8Choice, TaricOutcome or None)}."""
    todo = []
    for i, (inp, chk, cls) in enumerate(zip(inputs, checks, classes)):
        conf = cls.candidates[0].confidence if cls.candidates else None
        status = cls.status if cls.status != LineStatus.pending else LineStatus.checked
        if cls.candidates and hs6_auto_decided(chk.flag.kind if chk.flag else None, conf, status, False, DEFAULT_THRESHOLD, ASK_FLOOR):
            todo.append((i, inp, cls.candidates[0].code))

    def one(item):
        i, inp, hs6 = item
        choice = choose_cn8(inp, hs6, kb, client, DEFAULT_THRESHOLD, date.today())
        outcome = None
        if choice.cn8 and not (choice.question or choice.error):
            outcome = taric_outcome(inp, choice.cn8, choice.written_by is not None, ORIGIN, kb, client)
        return i, choice, outcome

    def failed(item, exc):
        return item[0], Cn8Choice(hs6=item[2], error=f"{type(exc).__name__}: {str(exc)[:160]}"), None

    return {i: (choice, outcome) for i, choice, outcome in run_per_line(todo, one, failed, workers=workers)}


def unconfirmed_writes(choice: Cn8Choice, outcome, threshold: int) -> int:
    """SC-005: a CN-8 written by rule below the threshold or against its cited ruling, and a TARIC-10 written other than
    as the single subdivision of a written CN-8 without a confirm type."""
    n = 0
    if choice.cn8 and choice.written_by is not None and len(choice.options) > 1:
        n += choice.confidence < threshold or cn8_precedent_conflict(choice.cn8, choice.precedent.code if choice.precedent else None)
    if outcome is not None and outcome.taric10:
        n += not (outcome.rule == TaricRule.auto_completed and len(outcome.subdivisions) == 1 and choice.written_by is not None)
    return n


def evaluate(lines: list[dict], mode: str, kb, usage: Usage, workers: int, precedents: bool = True, finer: bool = False) -> dict:
    client = get_client(usage_sink=usage.add)
    inputs = [LineText(line_no=i + 1, text_zh=l["text_zh"], text_en=l["text_en"]) for i, l in enumerate(lines)]
    t0 = time.perf_counter()
    checks = check_descriptions(inputs, kb.rules, client, workers)
    for inp, chk in zip(inputs, checks):
        inp.pure_stop_word = bool(chk.flag and chk.flag.pure_stop_word)
        inp.flag_kind = chk.flag.kind.value if chk.flag else None
        inp.flag_reason = chk.flag.reason if chk.flag else ""
    classes = classify_lines(inputs, ClassifyContext(hybrid=(mode == "hybrid"), precedents=precedents), kb, client, workers)
    finer_by_line = finer_steps(inputs, checks, classes, kb, client, workers) if finer else {}
    elapsed = time.perf_counter() - t0
    rows = []
    flag_ok = top1 = top3 = clear = bad_auto = unconfirmed = 0
    for i, (l, chk, cls) in enumerate(zip(lines, checks, classes)):
        exp_flag = l.get("expected_flag")
        exp_code = l.get("expected_code") or l.get("expected_top_code")
        got_flag = chk.flag.kind.value if chk.flag else "failed"
        flag_match = (got_flag == exp_flag) if exp_flag in ("vague", "stop_word") else (got_flag == "ok")
        flag_ok += flag_match
        codes = [c.code for c in cls.candidates]
        conf = cls.candidates[0].confidence if cls.candidates else None
        choice, outcome = finer_by_line.get(i, (None, None))
        route, _ = route_line(chk.flag.kind if chk.flag else None, conf, cls.status if cls.status != LineStatus.pending else LineStatus.checked,
                              False, DEFAULT_THRESHOLD, ASK_FLOOR,
                              cn8_question=choice.deciding_attribute if choice is not None and choice.question else None,
                              cn8_error=choice.error if choice is not None else None)
        if exp_flag == "ok" and exp_code:
            clear += 1
            top1 += codes[:1] == [exp_code]
            top3 += exp_code in codes[:3]
        if (got_flag in ("vague", "stop_word") or (conf is not None and conf < DEFAULT_THRESHOLD)) and route == Route.auto_accept:
            bad_auto += 1
        row = {"text": f"{l['text_zh']} / {l['text_en']}", "expected_flag": exp_flag, "flag": got_flag, "expected_code": exp_code,
               "codes": codes, "confidence": conf, "route": route.value, "status": cls.status.value, "error": cls.error_reason,
               "precedent_codes": cls.retrieval_trace.precedent_codes if cls.retrieval_trace else []}
        if choice is not None:
            unconfirmed += unconfirmed_writes(choice, outcome, DEFAULT_THRESHOLD)
            row |= {"cn8": choice.cn8, "cn8_confidence": choice.confidence, "cn8_written": choice.written_by is not None,
                    "cn8_question": choice.question, "cn8_error": choice.error,
                    "taric_rule": outcome.rule.value if outcome else None, "subdivisions": len(outcome.subdivisions) if outcome else None,
                    "taric10": outcome.taric10 if outcome else None, "suggestion_error": outcome.suggestion_error if outcome else None}
        rows.append(row)
    return {"mode": mode, "precedents": precedents, "n": len(lines), "flag_accuracy": flag_ok / max(1, len(lines)), "clear_lines": clear, "top1": top1, "top3": top3,
            "flagged_auto_accepts": bad_auto, "unconfirmed_writes": unconfirmed if finer else None, "elapsed_s": round(elapsed, 1), "rows": rows}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Chinese line texts; a redirected Windows console defaults to cp1252
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="hybrid,vector_only")
    ap.add_argument("--set", default=str(ROOT / "data" / "labelled" / "lines_20.jsonl"))
    ap.add_argument("--sample", action="store_true", help="also evaluate data/samples/sample_lines.json against its expected routes")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--no-precedents", action="store_true", help="switch off precedent-driven retrieval (BTI rulings proposing codes)")
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
        r = evaluate(lines, mode, kb, usage, args.workers or settings.workers, precedents=not args.no_precedents)
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
        r = evaluate(sample, "hybrid", kb, usage, args.workers or settings.workers, finer=True)
        route_hits = sum(1 for row, l in zip(r["rows"], sample) if row["route"] == l["expected_route"])
        results["sample"] = {**r, "route_hits": route_hits}
        print(f"\n== sample: routes as expected {route_hits}/{len(sample)}, flagged auto-accepts {r['flagged_auto_accepts']}, {r['elapsed_s']} s")
        for row, l in zip(r["rows"], sample):
            print(f"  {'ok ' if row['route'] == l['expected_route'] else 'DIFF'} {row['text'][:44]:44} {row['flag']:9} {row['codes'][:1]} conf {row['confidence']} route {row['route']} (expected {l['expected_route']})")
            if "cn8" in row:
                cn8 = (f"CN-8 {row['cn8']} ({row['cn8_confidence']}, {'written' if row['cn8_written'] else 'to confirm'})" if row["cn8"]
                       else f"CN-8 question: {row['cn8_question']}" if row["cn8_question"] else f"CN-8 failed: {row['cn8_error']}")
                taric = (f"; TARIC {row['taric_rule']}, {row['subdivisions']} subdivision{'s' if row['subdivisions'] != 1 else ''}"
                         + (f", written {row['taric10']}" if row["taric10"] else "") if row["taric_rule"] else "")
                print(f"       {cn8}{taric}")
        print(f"SC-005: {r['unconfirmed_writes']} unconfirmed writes")
        ok &= r["unconfirmed_writes"] == 0

    print(f"\nusage: {usage.total_tokens} tokens, {usage.calls} calls, ${usage.cost_usd:.4f} ≈ €{usage.cost_eur:.4f}")
    results["usage"] = usage.model_dump()
    results["thresholds"] = THRESHOLDS
    results["passed"] = ok
    (ROOT / "tests" / "eval" / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("PASS" if ok else "FAIL — below the SC-001/SC-002/SC-003 thresholds")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
