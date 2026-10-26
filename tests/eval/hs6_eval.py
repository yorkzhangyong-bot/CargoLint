"""HS-6 evaluation (feature 006): the step before the CN-8 eval, from a raw goods description to the HS-6 the app picks.

    python tests/eval/hs6_eval.py --repeat 3 --tag hs6-baseline
    python tests/eval/hs6_eval.py --limit 3 --repeat 3 --dry-run     # the first three lines; prints, writes nothing

Live: needs OPENROUTER_API_KEY and the full knowledge base, and spends credits, so run it only when the author asks.
The set is the CN-8 eval's (tests/eval/cn8_eval_set.json, 120 EBTI rulings). A line's text is its ruling's goods
description as given, split as the app splits a typed line (tools.parsers.split_mixed: English or German text is the
English field, Chinese text the Chinese one) and not cut, as a typed line is not (an uploaded file cuts a description
at 300 characters). Its correct HS-6 is the first six digits of the ruling's CN-8, so the set needs no new labels.

Each line goes through what the app runs for a new line (agent.agent._finalize): check_descriptions, then
classify_lines for a line that is neither failed nor a pure stop word, with the context context_for_shipment builds for
an unknown shipper (hybrid search, BTI precedents, no history), then the route the store computes for it (route_line,
threshold 85, ask floor 50, no CN-8 input: the HS-6 layer's route). Leakage guard: the line's own ruling is never a BTI
precedent (ClassifyContext.exclude_refs, one line at a time); without it the ruling under test would propose its own
code with its own text. Ruling validity is judged on the set's build date, as in the CN-8 eval.

Each row keeps the top-1 and the top 3 with their confidences, the correct HS-6, the top-1 hit, whether the correct
HS-6 is in the top 3, the description check's flag, the route, the codes the BTI precedents proposed, whether the
correct HS-6 was among the candidates shown to the model (expected_sent), and nearest_hits: the 40 rulings nearest to
the line's query vector, each with reference, HS-6, cosine distance, issuing country and whether it was eligible to
propose a code (valid on the set's date, coded to a subheading of the loaded nomenclature, not the line's own ruling);
own_rank is where the line's own ruling stands among them. The precedent search reads the nearest 12; the 40 come from
a second search with the same vector, for the log only. The results file keeps each row's nearest_hits on one line.

--repeat N runs every line N times, independently: nothing is carried over between runs, the query embedding and the
model calls are drawn anew. The entry in tests/eval/hs6_eval_history.json keeps top-1 per run, the majority top-1 (a
tie goes to the earliest run), correct-in-top-3 per run, the lines with the same top-1 and the same route in all runs,
the routes and the wrong but auto-accepted lines per run, the lines wrong in every run, the cross-layer table against
the CN-8 eval (tests/eval/cn8_eval_iteration11.json: the CN-8 step from the correct HS-6), on majority results and run
by run, whose right-right cell per run is the end-to-end estimate, and the cost. --note keeps a note with the entry.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD, RETRIEVAL_K, get_settings  # noqa: E402
from agent.llm import get_client, set_client_factory  # noqa: E402
from agent.routing import route_line  # noqa: E402
from agent.schemas import FlagKind, LineStatus, SourceKind, Usage  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from rag.retriever import DISTANCE_DECIMALS  # noqa: E402
from rag.translate import clear_cache as clear_translations  # noqa: E402
from tests.eval.cn8_eval import OverriddenClient, dump_results, expected_sent_share, majority  # noqa: E402
from tools.check_description import check_descriptions  # noqa: E402
from tools.classify_hs6 import ClassifyContext, classify_lines  # noqa: E402
from tools.common import LineText, run_per_line  # noqa: E402
from tools.parsers import split_mixed  # noqa: E402

SET = ROOT / "tests" / "eval" / "cn8_eval_set.json"
OUT = ROOT / "tests" / "eval" / "hs6_eval.json"
HISTORY = ROOT / "tests" / "eval" / "hs6_eval_history.json"
REPORT = ROOT / "tests" / "eval" / "hs6_eval.md"
CN8_RESULTS = ROOT / "tests" / "eval" / "cn8_eval_iteration11.json"
HITS_LOGGED = 40
SEARCHED = 2 * RETRIEVAL_K    # the rulings precedent_codes reads per query vector
QUADRANTS = ("hs6_right_cn8_right", "hs6_right_cn8_wrong", "hs6_wrong_cn8_right", "hs6_wrong_cn8_wrong")
_rec = threading.local()       # per worker thread, for the line in hand: the logged ruling searches


def expected_hs6(ruling: dict) -> str:
    """The correct HS-6 of an eval line: the first six digits of its ruling's CN-8, dotted as the nomenclature is."""
    return f"{ruling['cn8'][:4]}.{ruling['cn8'][4:6]}"


def line_text(line_no: int, ruling: dict) -> LineText:
    """The ruling's goods description as the app takes a typed line: split into Chinese and other text, not cut."""
    zh, en = split_mixed(ruling["description"])
    return LineText(line_no=line_no, text_zh=zh, text_en=en)


def _logged(search: Any) -> Any:
    """search_by_vector as the app calls it, unchanged; for the calling thread's line it also keeps the HITS_LOGGED
    rulings nearest to the same vector, from a second search (the log only)."""
    def wrapper(vector: list[float], k: int, chapter_filter: list[str] | None = None, where: dict | None = None) -> Any:
        hits = search(vector, k, chapter_filter, where)
        searches = getattr(_rec, "searches", None)
        if searches is not None:
            searches.append(search(vector, HITS_LOGGED, chapter_filter, where))
        return hits
    return wrapper


def nearest_hits(searches: list[list[tuple[str, float]]], own: str, kb: Any, as_of: date) -> list[dict]:
    """The rulings nearest to a line's query vectors, each once at its smallest cosine distance, nearest first (equal
    distances by id, as rag.retriever.stable_order), at most HITS_LOGGED, with what the store says about each."""
    best: dict[str, float] = {}
    for hits in searches:
        for doc_id, score in hits:
            best[doc_id] = min(best.get(doc_id, float("inf")), 1.0 - score)
    out = []
    for doc_id in sorted(best, key=lambda d: (round(best[d], DISTANCE_DECIMALS), d))[:HITS_LOGGED]:
        record = kb.bti.get(doc_id) or {}
        reference, code = doc_id.removeprefix("bti:"), record.get("code") or ""
        out.append({"reference": reference, "hs6": code, "distance": round(best[doc_id], 6),
                    "country": record.get("member_state") or "",
                    "eligible": (reference != own and bool(code) and kb.index.get(code) is not None
                                 and kb.bti.get(doc_id, as_of) is not None)})
    return out


def run_once(rulings: list[dict], kb: Any, client: Any, as_of: date, workers: int) -> tuple[list[dict], float]:
    """One pass of the app's HS-6 path over the set: one row per ruling, and the elapsed seconds."""
    clear_translations()   # an independent run: no translation carried over (only a Chinese line is translated)
    lines = [line_text(i, r) for i, r in enumerate(rulings, start=1)]
    base = ClassifyContext(hybrid=True, as_of=as_of)   # context_for_shipment for an unknown shipper, on the set's date
    t0 = time.perf_counter()
    checks = check_descriptions(lines, kb.rules, client, workers)
    todo = []
    for line, r, chk in zip(lines, rulings, checks):   # what store.update_check and select_lines pass on
        if chk.flag is not None and not chk.flag.pure_stop_word:
            line.flag_kind, line.flag_reason = chk.flag.kind.value, chk.flag.reason
            todo.append((line, r["reference"]))

    def one(item: tuple[LineText, str]) -> tuple[Any, list]:
        line, reference = item
        _rec.searches = []
        ctx = replace(base, exclude_refs=frozenset({reference}))   # the leakage guard: never the line's own ruling
        return classify_lines([line], ctx, kb, client, workers=1)[0], _rec.searches

    vectors = getattr(kb, "bti_vectors", None)
    own = vectors is not None and "search_by_vector" in vars(vectors)
    if vectors is not None:
        search = vectors.search_by_vector
        vectors.search_by_vector = _logged(search)      # the instance only, for this run
    try:
        done = run_per_line(todo, one, lambda item, exc: None, workers=workers)
    finally:
        if vectors is not None:
            if own:
                vectors.search_by_vector = search
            else:
                del vectors.search_by_vector
    elapsed = time.perf_counter() - t0
    classified = {line.line_no: res for (line, _), res in zip(todo, done)}
    rows = []
    for line, r, chk in zip(lines, rulings, checks):
        res = classified.get(line.line_no)
        cls, searches = res if res is not None else (None, [])
        if chk.status == LineStatus.failed:
            status, error = LineStatus.failed, chk.error_reason
        elif line.line_no not in classified:       # a pure stop word: checked, nothing to classify
            status, error = LineStatus.checked, None
        elif cls is None:
            status, error = LineStatus.failed, "timed out"
        else:
            status, error = cls.status, cls.error_reason
        expected = expected_hs6(r)
        candidates = cls.candidates if cls is not None else []
        codes = [c.code for c in candidates]
        conf = candidates[0].confidence if candidates else None
        kind = chk.flag.kind if chk.flag is not None else None
        route, _ = route_line(kind, conf, status, kind is not None and kind != FlagKind.ok, DEFAULT_THRESHOLD, ASK_FLOOR)
        shown = {s.id for s in cls.sources if s.kind == SourceKind.nomenclature} if cls is not None else set()
        hits = nearest_hits(searches, r["reference"], kb, as_of)
        rows.append({
            "reference": r["reference"], "chapter": r["chapter"], "language": r["language"], "expected": expected,
            "flag": kind.value if kind is not None else "failed", "top1": codes[0] if codes else None, "top3": codes[:3],
            "confidences": [c.confidence for c in candidates[:3]], "confidence": conf,
            "hit": bool(codes) and codes[0] == expected, "in_top3": expected in codes[:3], "route": route.value,
            "status": status.value, "error": error,
            "precedent_codes": cls.retrieval_trace.precedent_codes if cls is not None and cls.retrieval_trace else [],
            "expected_sent": f"hs:{expected}" in shown,
            "own_rank": next((k for k, h in enumerate(hits, start=1) if h["reference"] == r["reference"]), None),
            "nearest_hits": hits})
    return rows, elapsed


def _seen(r: dict) -> dict:
    return {"top1": r["top1"], "confidence": r["confidence"], "route": r["route"], "in_top3": r["in_top3"]}


def measures(runs: list[list[dict]]) -> dict:
    """The HS-6 layer over N runs of the same lines; `runs` holds each run's rows in set order."""
    n = len(runs[0])
    same_top1 = same_route = majority_hits = 0
    always_wrong, unstable = [], []
    for seen in zip(*runs):
        codes = [r["top1"] for r in seen]
        same_top1 += len(set(codes)) == 1
        same_route += len({r["route"] for r in seen}) == 1
        majority_hits += majority(codes) == seen[0]["expected"]
        line = {"reference": seen[0]["reference"], "chapter": seen[0]["chapter"], "expected": seen[0]["expected"],
                "seen": [_seen(r) for r in seen]}
        if not any(r["hit"] for r in seen):
            always_wrong.append(line)
        if len(set(codes)) > 1:
            unstable.append(line)
    return {"top1_runs": [sum(r["hit"] for r in run) for run in runs], "majority_top1": majority_hits,
            "top3_runs": [sum(r["in_top3"] for r in run) for run in runs],
            "same_top1": same_top1, "top1_consistency": round(same_top1 / n, 4),
            "same_route": same_route, "route_consistency": round(same_route / n, 4),
            "routes_runs": [{route: sum(r["route"] == route for r in run) for route in ("auto_accept", "review", "ask_shipper")}
                            for run in runs],
            "wrong_auto_runs": [[{"reference": r["reference"], "expected": r["expected"], "top1": r["top1"],
                                  "confidence": r["confidence"]} for r in run if r["route"] == "auto_accept" and not r["hit"]]
                                for run in runs],
            "always_wrong": always_wrong, "unstable": unstable}


def own_ruling(runs: list[list[dict]]) -> dict:
    """Run by run, how many lines had their own ruling nearest, among the rulings the precedent search reads, and among
    the logged ones: what the leakage guard keeps out."""
    return {"nearest_runs": [sum(r["own_rank"] == 1 for r in run) for run in runs],
            "searched_runs": [sum(r["own_rank"] is not None and r["own_rank"] <= SEARCHED for r in run) for run in runs],
            "logged_runs": [sum(r["own_rank"] is not None for r in run) for run in runs], "searched": SEARCHED}


def cn8_results(data: dict) -> dict[str, dict]:
    """Per line of a CN-8 eval results file: its expected CN-8, and the chosen CN-8 and the top-1 hit of each run."""
    out: dict[str, dict] = {}
    for run in data.get("runs") or [data["rows"]]:
        for row in run:
            line = out.setdefault(row["reference"], {"expected": row["expected"], "chosen": [], "hits": []})
            line["chosen"].append(row["chosen"])
            line["hits"].append(bool(row["hit"]))
    return out


def _quadrant(hs6_right: bool, cn8_right: bool) -> str:
    return f"hs6_{'right' if hs6_right else 'wrong'}_cn8_{'right' if cn8_right else 'wrong'}"


def cross_layer(runs: list[list[dict]], cn8: dict[str, dict]) -> dict:
    """Each line's HS-6 (this eval) right or wrong × its CN-8 (the CN-8 eval, from the correct HS-6) right or wrong: on
    the majority top-1 of each eval (a tie goes to the earliest run), and run by run (run k of both). Both right is the
    end-to-end estimate, as the CN-8 step runs on the HS-6 picked, which is the correct one only when the HS-6 is right."""
    k = min(len(runs), min(len(c["hits"]) for c in cn8.values()))
    by_majority, per_run = dict.fromkeys(QUADRANTS, 0), [dict.fromkeys(QUADRANTS, 0) for _ in range(k)]
    lines = []
    for seen in zip(*runs):
        c = cn8[seen[0]["reference"]]
        hs6_right = majority([r["top1"] for r in seen]) == seen[0]["expected"]
        cn8_right = majority(c["chosen"]) == c["expected"]
        quadrant = _quadrant(hs6_right, cn8_right)
        by_majority[quadrant] += 1
        lines.append({"reference": seen[0]["reference"], "quadrant": quadrant, "hs6_hits": [r["hit"] for r in seen],
                      "cn8_hits": c["hits"]})
        for i, cells in enumerate(per_run):
            cells[_quadrant(seen[i]["hit"], c["hits"][i])] += 1
    return {"majority": by_majority, "runs": per_run, "end_to_end_runs": [cells["hs6_right_cn8_right"] for cells in per_run],
            "lines": lines}


# --------------------------------------------------------------------------- the report
def _md(text: str, limit: int = 80) -> str:
    """A description excerpt for a Markdown list: one line, cut, markup characters escaped."""
    text = " ".join((text or "").split())
    text = text if len(text) <= limit else text[:limit - 1] + "…"
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)


def _runs(values: list) -> str:
    return " / ".join(str(v) for v in values)


def _seen_text(line: dict) -> str:
    return " · ".join(f"{s['top1'] or 'no code'} ({s['confidence']}, {s['route']})" for s in line["seen"])


def _wrong_auto(wrong_auto_runs: list[list[dict]]) -> list[str]:
    """The wrong but auto-accepted lines: those of every run as a count, as each is among the lines wrong in every run,
    and the others one by one with the runs they were in."""
    by_run = [{w["reference"]: w for w in wrong} for wrong in wrong_auto_runs]
    refs = list(dict.fromkeys(ref for found in by_run for ref in found))
    every = [ref for ref in refs if all(ref in found for found in by_run)]
    listed = []
    for ref in refs:
        if ref not in every:
            seen = [(k, found[ref]) for k, found in enumerate(by_run, start=1) if ref in found]
            listed.append(f"- {ref} (expected {seen[0][1]['expected']}): "
                          + "; ".join(f"run {k}: {w['top1']} ({w['confidence']})" for k, w in seen))
    return ([f"Per run: {_runs(len(found) for found in by_run)}. In every run: {len(every)} line{'' if len(every) == 1 else 's'}, "
             "each among the lines wrong in every run above."] + ([""] + listed if listed else []))


def _entry_sections(h: dict, descriptions: dict[str, str]) -> list[str]:
    n, x = h["n"], h["cross_layer"]
    out = ["", f"## Iteration {h['iteration']} ({h.get('tag', '-')}, {h['run_on']})"]
    if h.get("note"):
        out += ["", f"Note: {h['note']}"]
    out += ["", "| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |",
            "|---|---|---|---|---|---|---|"]
    for k, routes in enumerate(h["routes_runs"]):
        out.append(f"| {k + 1} | {h['top1_runs'][k]}/{n} | {h['top3_runs'][k]}/{n} | {routes['auto_accept']} | "
                   f"{routes['review']} | {routes['ask_shipper']} | {len(h['wrong_auto_runs'][k])} |")
    m = x["majority"]
    out += ["", f"### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration {h['cn8_iteration']})", "",
            "The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. "
            "Majority: the majority top-1 of each eval; run k: run k of both.", "",
            "| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | "
            "HS-6 wrong, CN-8 wrong |", "|---|---|---|---|---|",
            "| Majority | " + " | ".join(str(m[q]) for q in QUADRANTS) + " |"]
    out += [f"| Run {k + 1} | " + " | ".join(str(cells[q]) for q in QUADRANTS) + " |" for k, cells in enumerate(x["runs"])]
    step1 = m["hs6_wrong_cn8_right"] + m["hs6_wrong_cn8_wrong"]
    out += ["", f"On majority results {n - m['hs6_right_cn8_right']} of {n} lines end wrong: {step1} from the HS-6 step "
                f"(the CN-8 step would have failed too on {m['hs6_wrong_cn8_wrong']} of them), "
                f"{m['hs6_right_cn8_wrong']} from the CN-8 step alone. End-to-end estimate per run: "
                f"{_runs(x['end_to_end_runs'])} of {n}."]
    s = h["expected_sent"]
    if s["wrong"]:
        out += ["", f"Wrong top-1 results (line × run): {s['wrong']}; the correct HS-6 was among the candidates shown to "
                    f"the model in {s['with_expected']} ({s['share']:.1%})."]
    o = h["own_ruling"]
    out += ["", f"Leakage guard: each line's own ruling was its nearest ruling in {_runs(o['nearest_runs'])} of {n} "
                f"lines (per run), among the {o['searched']} the precedent search reads in {_runs(o['searched_runs'])}; "
                "the guard kept it out of the precedents."]
    wrong = [f"- {a['reference']} (chapter {a['chapter']}, expected {a['expected']}): {_seen_text(a)}; correct in the top 3 "
             f"in {sum(s['in_top3'] for s in a['seen'])} of {len(a['seen'])} runs. \"{_md(descriptions.get(a['reference'], ''))}\""
             for a in h["always_wrong"]]
    differed = [f"- {u['reference']} (expected {u['expected']}): {_seen_text(u)}" for u in h["unstable"]]
    out += ["", f"### Lines wrong in every run ({len(wrong)})"] + ([""] + wrong if wrong else [])
    out += ["", f"### Lines whose top-1 differed between runs ({len(differed)})"] + ([""] + differed if differed else [])
    out += ["", "### Wrong but auto-accepted (the HS-6 layer)", ""] + _wrong_auto(h["wrong_auto_runs"])
    return out


def render_report(history: list[dict], data: dict) -> str:
    descriptions = {r["reference"]: r["description"] for r in data["rulings"]}
    out = [
        "# HS-6 evaluation report (feature 006)",
        "",
        f"- **Set**: `tests/eval/cn8_eval_set.json`, the CN-8 eval's {len(data['rulings'])} EBTI rulings (built "
        f"{data['built_on']}); a line's correct HS-6 is the first six digits of its ruling's CN-8.",
        "- **Method**: each ruling's goods description, as given, is a new line through the app's path: the description "
        "check, the HS-6 step (hybrid search and BTI precedents, no shipper history) and the route the store computes "
        f"(threshold {DEFAULT_THRESHOLD}, ask floor {ASK_FLOOR}). A line's own ruling is never a precedent (leave-one-out); "
        "ruling validity on the set's build date. `python tests/eval/hs6_eval.py --repeat 3`.",
        "- **Top-1** is the first candidate; a line without one (a stop word, a failure) is a miss. **In top 3**: the "
        "correct HS-6 among the candidates the clerk picks from on review. **Majority**: the most frequent top-1 over the "
        "runs (a tie goes to the earliest run). **Wrong, auto-accepted**: routed to auto-accept with a wrong top-1; the "
        "CN-8 step then runs on the wrong HS-6.",
        "",
        "| Iteration | Run on | Tag | Runs | Top-1 per run | Majority top-1 | In top 3 per run | Same top-1 | Same route | "
        "Wrong, auto-accepted per run | End to end per run | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for h in history:
        n = h["n"]
        out.append(f"| {h['iteration']} | {h['run_on']} | {h.get('tag', '-')} | {h['repeat']} | {_runs(h['top1_runs'])} "
                   f"of {n} | {h['majority_top1']}/{n} | {_runs(h['top3_runs'])} of {n} | {h['same_top1']}/{n} | "
                   f"{h['same_route']}/{n} | {_runs(len(w) for w in h['wrong_auto_runs'])} | "
                   f"{_runs(h['cross_layer']['end_to_end_runs'])} of {n} | ${h['cost_usd']:.4f} (€{h['cost_eur']:.4f}), "
                   f"{h['elapsed_s']:.0f} s |")
    for h in history:
        out += _entry_sections(h, descriptions)
    out += ["", f"Model: {history[-1]['model'] if history else '-'}. Line-by-line results of the latest run: "
            "`tests/eval/hs6_eval.json`; earlier runs are in the git history of that file.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # German and Chinese text; a redirected Windows console is cp1252
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iteration", type=int, help="iteration number (default: the next)")
    ap.add_argument("--change", help="what changed since the previous iteration (generated when omitted)")
    ap.add_argument("--repeat", type=int, default=1, help="run every line N times, independently (default 1)")
    ap.add_argument("--temperature", type=float, help="chat-model temperature for this run only")
    ap.add_argument("--seed", type=int, help="chat-model seed for this run only")
    ap.add_argument("--tag", help="tag of the history entry")
    ap.add_argument("--note", help="a note kept with the history entry and shown with it in the report")
    ap.add_argument("--cn8", default=str(CN8_RESULTS), help="the CN-8 eval results the cross-layer table reads")
    ap.add_argument("--limit", type=int, help="only the first N lines of the set (with --dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="print a row, the history entry and the report; write nothing")
    args = ap.parse_args(argv)
    if args.repeat < 1:
        ap.error("--repeat must be 1 or more")
    if args.limit is not None and not args.dry_run:
        ap.error("--limit is for a dry run: the history keeps whole-set runs only")
    data = json.loads(SET.read_text(encoding="utf-8"))
    rulings = data["rulings"][:args.limit] if args.limit else data["rulings"]
    cn8_data = json.loads(Path(args.cn8).read_text(encoding="utf-8"))
    cn8 = cn8_results(cn8_data)
    missing = [r["reference"] for r in rulings if r["reference"] not in cn8]
    if missing:
        ap.error(f"{len(missing)} lines are missing from {args.cn8}, such as {missing[0]}")
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
    change = args.change or (f"{args.repeat} independent run{'s' if args.repeat > 1 else ''}, temperature {temperature}, "
                             f"seed {seed if seed is not None else 'none'}")
    print(f"HS-6 iteration {iteration}: {len(rulings)} lines × {args.repeat} run(s); BTI vectors "
          f"{'loaded' if getattr(kb, 'bti_vectors', None) is not None else 'not loaded'}; model {settings.chat_model}, "
          f"temperature {temperature}, seed {seed}; CN-8 results: iteration {cn8_data['summary'].get('iteration')}")

    runs, elapsed, costs = [], 0.0, []
    for k in range(args.repeat):
        before = usage.cost_eur
        rows, seconds = run_once(rulings, kb, client, as_of, settings.workers)
        runs.append(rows)
        elapsed += seconds
        costs.append(round(usage.cost_eur - before, 4))
        print(f"  run {k + 1}: top-1 {sum(r['hit'] for r in rows)}/{len(rows)}, in top 3 {sum(r['in_top3'] for r in rows)}, "
              f"{seconds:.0f} s, €{costs[-1]:.4f}")
    m, x = measures(runs), cross_layer(runs, cn8)
    entry = {
        "iteration": iteration, "run_on": date.today().isoformat(), "change": change, "model": settings.chat_model,
        "threshold": DEFAULT_THRESHOLD, "ask_floor": ASK_FLOOR, "temperature": temperature, "seed": seed,
        "repeat": args.repeat, "n": len(rulings), **m, "expected_sent": expected_sent_share(runs),
        "own_ruling": own_ruling(runs), "cn8_iteration": cn8_data["summary"].get("iteration"), "cn8_source": Path(args.cn8).name,
        "cross_layer": {key: x[key] for key in ("majority", "runs", "end_to_end_runs")},
        "elapsed_s": round(elapsed, 1), "cost_usd": round(usage.cost_usd, 4), "cost_eur": round(usage.cost_eur, 4),
        "cost_eur_runs": costs}
    if args.tag:
        entry["tag"] = args.tag
    if args.note:
        entry["note"] = args.note
    summary = {**entry, "set_built_on": data["built_on"], "cn8_lines": x["lines"],
               "usage": {"total_tokens": usage.total_tokens, "calls": usage.calls, "cost_usd": round(usage.cost_usd, 4),
                         "cost_eur": round(usage.cost_eur, 4)}}
    report: dict = {"summary": summary, "rows": runs[0]}
    if args.repeat > 1:
        report["runs"] = runs
    history = [h for h in history if h["iteration"] != iteration] + [entry]
    history.sort(key=lambda h: h["iteration"])
    n, mx = len(rulings), x["majority"]
    if args.dry_run:
        first = runs[0][0]
        print("\n== a row (run 1, line 1; nearest_hits: the first 3 of "
              f"{len(first['nearest_hits'])}):\n" + json.dumps({**first, "nearest_hits": first["nearest_hits"][:3]},
                                                                ensure_ascii=False, indent=1))
        print("\n== the summary in tests/eval/hs6_eval.json (the history entry plus cn8_lines and usage):\n"
              + json.dumps(summary, ensure_ascii=False, indent=1))
        print("\n== tests/eval/hs6_eval.md:\n" + render_report(history, data))
        print("dry run: nothing written")
    else:
        OUT.write_text(dump_results(report), encoding="utf-8", newline="\n")
        HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        REPORT.write_text(render_report(history, data), encoding="utf-8", newline="\n")
    print(f"HS-6 top-1 per run {m['top1_runs']} of {n}; majority {m['majority_top1']}/{n}; in top 3 per run {m['top3_runs']}; "
          f"same top-1 in all runs {m['same_top1']}/{n}; same route {m['same_route']}/{n}")
    print(f"  wrong but auto-accepted per run {[len(w) for w in m['wrong_auto_runs']]}; wrong in every run "
          f"{len(m['always_wrong'])}")
    print(f"  cross-layer (majority) {mx}; end to end per run {x['end_to_end_runs']} of {n}")
    print(f"  own ruling nearest per run {entry['own_ruling']['nearest_runs']}")
    print(f"  {elapsed:.0f} s; usage {usage.total_tokens} tokens, {usage.calls} calls, ${usage.cost_usd:.4f} ≈ €{usage.cost_eur:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
