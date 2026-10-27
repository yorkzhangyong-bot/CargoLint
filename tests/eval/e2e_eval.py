"""End-to-end evaluation (feature 007): each line of the CN-8 eval set through the product pipeline as an upload runs it,
from the goods description to the CN-8 and the route.

    python tests/eval/e2e_eval.py --repeat 3 --tag e2e-baseline
    python tests/eval/e2e_eval.py --limit 3 --dry-run                 # the first three lines; prints, writes nothing
    python tests/eval/e2e_eval.py --repeat 3 --tag e2e-gpt41-mini --model openai/gpt-4.1-mini

Live: needs OPENROUTER_API_KEY and the full knowledge base, and spends credits, so run it only when the author asks.
The set is the CN-8 eval's (tests/eval/cn8_eval_set.json, 120 EBTI rulings): a line is its ruling's goods description,
and its correct HS-6 and CN-8 are the ruling's. The descriptions become lines as an uploaded file's rows do: the
product's parser (tools.parsers.rows_to_lines) splits Chinese from other text and cuts each part at 300 characters, as
every clerk input path does, so a long description is cut, where the HS-6 and CN-8 evals feed the whole text. They
open a new shipment with the store's defaults for an unknown shipper (threshold 85, hybrid search).

The steps are those the upload's completeness guard runs (agent.agent._finalize), through the line store, so the
routes, the two gates and the written codes are the store's: the description check; the HS-6 step (classify_lines with
the context context_for_shipment builds) for each line neither failed nor a pure stop word; the CN-8 step, as
tools.classify_cn8.run_cn8_step runs it, for the lines whose HS-6 the vote gate decided; then finalize_check. Left out:
the agent's own model turn, whose tool calls run these same steps; the BTI precedent lookup, which only marks rulings on
the candidates shown; and the TARIC step. Two changes keep the measure comparable with the layer evals: a line's own
ruling is never a precedent and never votes, at the HS-6 (ClassifyContext.exclude_refs) and at the CN-8
(classify_cn8_lines' exclude_refs), so both steps run one line at a time; and ruling validity is judged on the set's
build date.

The upload leaves a line whose HS-6 went to review without a CN-8: the CN-8 step waits for the clerk. So that each line
the clerk can confirm gets one, the eval then confirms the HS-6 its expanded row opens with (kind a: ui.view.line_status
and preselect, the top candidate), as the row's Confirm does (store.set_decision), and runs the CN-8 step on it, as
agent.after_hs6_decision does. A flagged line stays locked, as in the product: it waits for the shipper.

Per line: the HS-6 top-1, the HS-6 the CN-8 step ran on (decided by the gate, or confirmed by the clerk), the CN-8
picked (written by rule, or to confirm), each with whether it is right, the route the upload left, and for an
auto-accepted line whether the written CN-8 is right. The route is the store's, except that an auto-accepted HS-6 whose
CN-8 is not written counts as review: the clerk still picks the CN-8 (the table's "Pick: CN-8"). A line is right end to
end when its CN-8 pick is the ruling's CN-8. Any other line went wrong at the HS-6 step (a wrong HS-6, or none: the line
was flagged, failed or had no candidate) or at the CN-8 step (a wrong CN-8, a question to the shipper or a failure).

--repeat N runs every line N times, independently: a new shipment each run, query expansions (when on) drawn anew
(query embeddings are cached for the life of the knowledge base). The entry in tests/eval/e2e_eval_history.json keeps per run the lines
right end to end, the routes, the wrong auto-accepts, where the errors arose, the HS-6 layer, the cut and uncut lines
right, the run time and the cost, and over the runs the majority (the most frequent CN-8 pick, a tie to the earliest
run) and the lines with the same CN-8 pick and the same route in all runs. --model names another OpenRouter chat model
for this run only, as in the HS-6 eval (tests/eval/hs6_eval.py), with its invalid-answer counts. The line-by-line
results go to tests/eval/e2e_eval.json, the latest run, and to the run's own
tests/eval/e2e_eval_<tag>_<lang>_expansion-<on|off>.json; the report is tests/eval/e2e_eval.md.

Feature 009: no line is translated; every line is searched with its raw text. `--expansion on|off` sets query
expansion for the run, over CARGOLINT_QUERY_EXPANSION, and `--lang zh` uploads the 30 lines of
tests/eval/hs6_eval_zh.json in Chinese, each with its English line's expected codes and leakage rule (`--lang en`,
the default: the 120 as given). The entry keeps lang and expansion.

Feature 008, the precedent override: every run is made with the switch on (the shipment's hs6_override_min is
OVERRIDE_MIN), so a row's fields and the entry's measures are the switch on. On each line the override decided, the
CN-8 step is also asked under the model's top candidate, as cn8_step asks it but kept out of the store (outside the run
time, inside the cost). A row keeps that answer (cn8_top1); the override (whether it fired, the rank of the HS-6
decided, and for an override its code and its N of M rulings); the candidate the rulings' majority supported and
whether it was the right HS-6; the HS-6 step's route reason (hs6_reason); and `off`, the row replayed with the switch
off: on an override line the HS-6 goes to review, the clerk confirms the top candidate and its CN-8 is cn8_top1, and
every other line is the same in both states. The entry adds override_min, the measures with the switch off, the
overrides with their outcome in each state, and the supported candidates; the report shows the two states side by side.
`--replay FILE --override-min N` replays a results file's stored answers at a higher OVERRIDE_MIN, with no model call:
an override with fewer agreeing rulings no longer fires, and its row becomes its switch-off replay. A lower minimum
cannot be replayed, as the run asked the CN-8 step under no candidate its own minimum did not choose. The replay keeps
its own results file (e2e_eval.json stays the latest paid run) and a history entry marked as a replay.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD, HS6_VOTE_K, OVERRIDE_MIN, get_settings  # noqa: E402
from agent.llm import get_client  # noqa: E402
from agent.schemas import (Classification, Cn8Choice, Cn8Input, Cn8Line, CreatedBy, Decision, DecisionRoute,  # noqa: E402
                           Hs6Gate, LineStatus, ParsedLine, Usage)
from agent.store import LineStore  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from rag.translate import clear_cache as clear_expansions  # noqa: E402
from tests.eval.cn8_eval import dump_results, majority, price_for_run, run_settings  # noqa: E402
from tests.eval.hs6_eval import (OTHER_MODEL_RETRIES, TAG_RE, count_invalid, eval_rulings, expected_hs6,  # noqa: E402
                                 parse_counts, results_name, write_results)
from tools.check_description import check_descriptions  # noqa: E402
from tools.classify_cn8 import classify_cn8_lines, needs_cn8  # noqa: E402
from tools.classify_hs6 import classify_lines, context_for_shipment  # noqa: E402
from tools.common import run_per_line, select_lines  # noqa: E402
from tools.parsers import rows_to_lines  # noqa: E402
from ui import view  # noqa: E402

SET = ROOT / "tests" / "eval" / "cn8_eval_set.json"
OUT = ROOT / "tests" / "eval" / "e2e_eval.json"
HISTORY = ROOT / "tests" / "eval" / "e2e_eval_history.json"
REPORT = ROOT / "tests" / "eval" / "e2e_eval.md"
ROUTES = ("auto_accept", "review", "ask_shipper")
ORIGINS = ("hs6_wrong", "hs6_flagged", "hs6_failed", "hs6_no_candidate", "cn8_wrong", "cn8_asked", "cn8_failed")
ORIGIN_TEXT = {"hs6_wrong": "wrong HS-6", "hs6_flagged": "flagged, waits for the shipper", "hs6_failed": "HS-6 step failed",
               "hs6_no_candidate": "no HS-6 candidate", "cn8_wrong": "wrong CN-8", "cn8_asked": "CN-8 question",
               "cn8_failed": "CN-8 step failed"}
OFF_FIELDS = ("hs6", "hs6_by", "cn8", "written", "question", "cn8_error", "cn8_gate", "route", "hit", "written_hit", "origin")


def upload(rulings: list[dict]) -> list[ParsedLine]:
    """The set as an uploaded file's rows: the product's parser splits each description and cuts it at 300 characters."""
    lines, skipped = rows_to_lines([["Description"]] + [[r["description"]] for r in rulings], 0, {"description": 0},
                                   "eval set")
    if skipped:   # a total or empty row: the lines would no longer match the rulings
        raise ValueError(f"the parser skipped {skipped} of the descriptions")
    return lines


def hs6_step(store: LineStore, kb: Any, client: Any, refs: dict[int, str], as_of: date, workers: int,
             expansion: bool = False) -> None:
    """agent._finalize's HS-6 step for each line neither failed nor a pure stop word, one line at a time so that its own
    ruling stays out of its precedents and its vote, on the set's date, with the run's query expansion."""
    base = replace(context_for_shipment(store.shipment, kb), as_of=as_of, expansion=expansion)
    todo = [line.line_no for line in store.lines if line.current.status == LineStatus.pending and line.current.flag is not None]

    def one(line_no: int) -> Classification:
        ctx = replace(base, exclude_refs=frozenset({refs[line_no]}))
        return classify_lines(select_lines(store, [line_no]), ctx, kb, client, workers=1)[0]

    for line_no, cls in zip(todo, run_per_line(todo, one, lambda line_no, exc: None, workers=workers)):
        store.update_classification(line_no, cls if cls is not None else Classification(
            line_no=line_no, candidates=[], no_valid_candidate=True, status=LineStatus.failed, error_reason="timed out"))


def _cn8_line(line: Any, hs6: str) -> Cn8Line:
    v = line.current
    return Cn8Line(line_no=line.line_no, text_zh=v.text_zh, text_en=v.text_en, extracted=v.extracted, hs6=hs6)


def cn8_choices(store: LineStore, kb: Any, client: Any, refs: dict[int, str], as_of: date, workers: int,
                lines: list[Cn8Line]) -> list[Cn8Choice]:
    """The CN-8 step's answer for each line, one line at a time so that its own ruling stays out of the rulings sent and
    the vote, on the set's date."""
    def one(line: Cn8Line) -> Any:
        inp = Cn8Input(lines=[line], as_of=as_of, threshold=store.shipment.threshold)
        return classify_cn8_lines(inp, kb, client, exclude_refs=frozenset({refs[line.line_no]}), workers=1)[0]

    return [res.choice if res is not None else Cn8Choice(hs6=line.hs6, options=kb.index.cn8_lines(line.hs6), error="timed out")
            for line, res in zip(lines, run_per_line(lines, one, lambda line, exc: None, workers=workers))]


def cn8_step(store: LineStore, kb: Any, client: Any, refs: dict[int, str], as_of: date, workers: int,
             line_nos: list[int] | None = None) -> None:
    """tools.classify_cn8.run_cn8_step for the given lines (None: each line that needs it), through cn8_choices."""
    lines = [_cn8_line(line, hs6) for line in store.lines
             if (line_nos is None or line.line_no in line_nos) and (hs6 := needs_cn8(store, line)) is not None]
    for line, choice in zip(lines, cn8_choices(store, kb, client, refs, as_of, workers, lines)):
        store.set_cn8_result(line.line_no, choice)


def cn8_under_top(store: LineStore, kb: Any, client: Any, refs: dict[int, str], as_of: date,
                  workers: int) -> dict[int, Cn8Choice]:
    """Feature 008: for each line the precedent override decided, the CN-8 step's answer under the model's top
    candidate, asked as cn8_step asks it but kept out of the store: what the switch-off replay needs."""
    lines = [_cn8_line(line, line.current.top_code) for line in store.lines
             if line.current.hs6_gate == Hs6Gate.vote_override]
    return {line.line_no: choice for line, choice in zip(lines, cn8_choices(store, kb, client, refs, as_of, workers, lines))}


def confirm_preselected(store: LineStore) -> list[int]:
    """The clerk confirms the HS-6 each line in review opens with (an expanded row of kind a pre-selects the top
    candidate), as the row's Confirm does. Returns the confirmed lines."""
    confirmed = []
    for line in store.lines:
        if view.line_status(store, line).kind != "a_hs6":
            continue
        code = view.preselect(store, line, "a_hs6", "hs6")[0]
        if code is None:   # "Pick: no candidate"
            continue
        store.set_decision(line.line_no, Decision(route=DecisionRoute.accepted, decided_code=code))
        confirmed.append(line.line_no)
    return confirmed


def final_route(store: LineStore, line: Any) -> str:
    """The route the upload leaves: the store's, except that an auto-accepted HS-6 whose CN-8 is not written counts as
    review, as the clerk still picks the CN-8."""
    route = store.effective_route(line)
    return "review" if route == "auto_accept" and store.decided_cn8(line) is None else route


def origin(row: dict) -> str | None:
    """Where a line that is not right end to end went wrong; None for a right one."""
    if row["hit"]:
        return None
    if row["hs6"] is None:
        if row["status"] == LineStatus.failed.value:
            return "hs6_failed"
        return "hs6_flagged" if row["flag"] != "ok" else "hs6_no_candidate"
    if row["hs6"] != row["expected_hs6"]:
        return "hs6_wrong"
    if row["question"]:
        return "cn8_asked"
    return "cn8_wrong" if row["cn8"] else "cn8_failed"


def line_row(store: LineStore, line: Any, ruling: dict, parsed: ParsedLine, hs6_route: str, route: str,
             hs6_reason: str = "", cn8_top1: Cn8Choice | None = None) -> dict:
    """One line's results once the clerk has confirmed what the upload left to review; feature 008: with the override,
    the supported candidate, the CN-8 step's answer under the top candidate on an override line, and the switch off."""
    v = line.current
    codes = [c.code for c in v.candidates]
    hs6, how = store.decided_code(line)
    c = v.cn8 if v.cn8 is not None and hs6 is not None and v.cn8.hs6 == hs6 else None
    row = {"reference": ruling["reference"], "chapter": ruling["chapter"], "language": ruling["language"],
           "expected_hs6": expected_hs6(ruling), "expected_cn8": ruling["cn8"], "cut": parsed.truncated,
           "flag": v.flag.kind.value if v.flag is not None else "failed", "status": v.status.value, "error": v.error_reason,
           "top1": codes[0] if codes else None, "confidence": v.top_confidence,
           "hs6_hit": bool(codes) and codes[0] == expected_hs6(ruling),
           "hs6_gate": v.hs6_gate.value if v.hs6_gate is not None else "not_gated", "hs6_route": hs6_route,
           "hs6_reason": hs6_reason,
           "hs6": hs6, "hs6_by": None if how is None else ("gate" if how == "auto" else "clerk"),
           "cn8": c.cn8 if c is not None else None, "written": bool(c is not None and c.cn8 and c.written_by),
           "question": c.question if c is not None else None, "cn8_error": c.error if c is not None else None,
           "cn8_gate": c.gate_reason.value if c is not None and c.gate_reason is not None else None, "route": route}
    row["hit"] = row["cn8"] == row["expected_cn8"]
    row["written_hit"] = row["hit"] if route == "auto_accept" else None
    row["origin"] = origin(row)
    vote, fired = v.hs6_vote, v.hs6_gate == Hs6Gate.vote_override
    counts = {code: len(countries) for code, countries in vote.competing} if vote is not None else {}
    supported = vote.candidate if vote is not None else None
    row["override"] = {"fired": fired, "rank": codes.index(hs6) + 1 if hs6 in codes else None,
                       "code": hs6 if fired else None, "n": counts.get(hs6) if fired else None,
                       "m": sum(counts.values()) if fired else None}
    row["supported"] = {"rank": supported, "right": codes[supported - 1] == row["expected_hs6"] if supported else None}
    row["cn8_top1"] = None if cn8_top1 is None else {
        "cn8": cn8_top1.cn8, "written": bool(cn8_top1.cn8 and cn8_top1.written_by), "question": cn8_top1.question,
        "error": cn8_top1.error, "gate": cn8_top1.gate_reason.value if cn8_top1.gate_reason is not None else None}
    row["off"] = off_block(row)
    return row


def off_block(row: dict) -> dict:
    """Feature 008: the row with the switch off, from the same answers. On a line the override decided, the HS-6 goes to
    review, the clerk confirms the top candidate (what the row pre-selects with the switch off) and its CN-8 is the CN-8
    step's answer under it (cn8_top1); the route the upload leaves is review. Any other line is the same in both states."""
    if not row["override"]["fired"]:
        return {k: row[k] for k in OFF_FIELDS}
    t = row["cn8_top1"]
    off = {**row, "hs6": row["top1"], "hs6_by": "clerk", "cn8": t["cn8"], "written": t["written"],
           "question": t["question"], "cn8_error": t["error"], "cn8_gate": t["gate"], "route": "review"}
    off["hit"] = off["cn8"] == off["expected_cn8"]
    off["written_hit"] = None
    off["origin"] = origin(off)
    return {k: off[k] for k in OFF_FIELDS}


def run_once(rulings: list[dict], kb: Any, client: Any, as_of: date, workers: int,
             expansion: bool = False) -> tuple[list[dict], float, float]:
    """One upload of the set through the pipeline, then the clerk's confirmations: one row per line, the seconds the
    upload's steps took and the seconds in all."""
    clear_expansions()   # an independent run
    store = LineStore(backend={}, index=kb.index)
    store.new_shipment(reference="e2e eval", hs6_override_min=OVERRIDE_MIN)   # the defaults ui.upload.open_shipment
                                                                              # opens with, the switch on (feature 008)
    parsed = upload(rulings)
    lines = store.add_lines(parsed, CreatedBy.file)
    refs = {line.line_no: r["reference"] for line, r in zip(lines, rulings)}
    t0 = time.perf_counter()
    for check in check_descriptions(select_lines(store, list(refs)), kb.rules, client, workers):
        store.update_check(check.line_no, check)
    hs6_step(store, kb, client, refs, as_of, workers, expansion)
    hs6_routes = {line.line_no: store.effective_route(line) for line in lines}
    hs6_reasons = {line.line_no: line.current.route_reason for line in lines}
    cn8_step(store, kb, client, refs, as_of, workers)
    store.finalize_check()
    routes = {line.line_no: final_route(store, line) for line in lines}
    upload_s = time.perf_counter() - t0
    cn8_step(store, kb, client, refs, as_of, workers, confirm_preselected(store))
    elapsed = time.perf_counter() - t0
    top1 = cn8_under_top(store, kb, client, refs, as_of, workers)   # feature 008: for the switch-off replay; not timed
    rows = [line_row(store, line, r, p, hs6_routes[line.line_no], routes[line.line_no], hs6_reasons[line.line_no],
                     top1.get(line.line_no)) for line, r, p in zip(lines, rulings, parsed)]
    return rows, upload_s, elapsed


def _wrong(r: dict) -> dict:
    return {"reference": r["reference"], "expected": r["expected_cn8"], "cn8": r["cn8"], "hs6": r["hs6"],
            "origin": r["origin"]}


def measures(runs: list[list[dict]]) -> dict:
    """The pipeline over N runs of the same lines; `runs` holds each run's rows in set order."""
    n = len(runs[0])
    same_cn8 = same_route = majority_right = 0
    majority_origin: Counter = Counter()
    always_wrong = []
    for seen in zip(*runs):
        picks, first = [r["cn8"] for r in seen], seen[0]
        same_cn8 += len(set(picks)) == 1
        same_route += len({r["route"] for r in seen}) == 1
        if majority(picks) == first["expected_cn8"]:
            majority_right += 1
        else:
            majority_origin["hs6" if majority([r["hs6"] for r in seen]) != first["expected_hs6"] else "cn8"] += 1
        if not any(r["hit"] for r in seen):
            always_wrong.append({"reference": first["reference"], "expected": first["expected_cn8"],
                                 "seen": [{"cn8": r["cn8"], "route": r["route"], "origin": r["origin"]} for r in seen]})
    right_hs6 = [[r for r in run if r["hs6"] is not None and r["hs6"] == r["expected_hs6"]] for run in runs]
    return {"right_runs": [sum(r["hit"] for r in run) for run in runs], "majority_right": majority_right,
            "majority_origin": {"hs6": majority_origin["hs6"], "cn8": majority_origin["cn8"]},
            "routes_runs": [{route: sum(r["route"] == route for r in run) for route in ROUTES} for run in runs],
            "right_auto_runs": [sum(r["route"] == "auto_accept" and r["hit"] for r in run) for run in runs],
            "wrong_auto_runs": [[_wrong(r) for r in run if r["route"] == "auto_accept" and not r["hit"]] for run in runs],
            "origin_runs": [{o: sum(r["origin"] == o for r in run) for o in ORIGINS} for run in runs],
            "hs6_top1_runs": [sum(r["hs6_hit"] for r in run) for run in runs],
            "hs6_wrong_auto_runs": [sum(r["hs6_by"] == "gate" and r["hs6"] != r["expected_hs6"] for r in run) for run in runs],
            "cn8_after_right_hs6_runs": [[sum(r["hit"] for r in rows), len(rows)] for rows in right_hs6],
            "cut": sum(r["cut"] for r in runs[0]),
            "cut_right_runs": [sum(r["hit"] for r in run if r["cut"]) for run in runs],
            "uncut_right_runs": [sum(r["hit"] for r in run if not r["cut"]) for run in runs],
            "same_cn8": same_cn8, "same_route": same_route, "n": n, "always_wrong": always_wrong}


def replay_row(r: dict, override_min: int) -> dict:
    """Feature 008: a stored row with the switch on at a higher `override_min`. An override with fewer agreeing rulings
    no longer fires, so the row becomes its switch-off replay: the HS-6 to review, the clerk's top candidate and the CN-8
    step's answer under it. Its route reason is left empty, as it would name the rulings' countries, which the row does
    not keep. Any other row, and every row's switch off, stay as stored."""
    o = r["override"]
    if not o["fired"] or o["n"] >= override_min:
        return r
    return {**r, **r["off"], "hs6_gate": Hs6Gate.vote_disagrees.value, "hs6_route": "review", "hs6_reason": None,
            "override": {"fired": False, "rank": 1, "code": None, "n": None, "m": None}}


def off_rows(run: list[dict]) -> list[dict]:
    """Feature 008: a run's rows with the switch off."""
    return [{**r, **r["off"]} for r in run]


def _override(r: dict) -> dict:
    return {"reference": r["reference"], "expected": r["expected_cn8"], "top1": r["top1"], "chosen": r["hs6"],
            "rank": r["override"]["rank"], "hs6_right": r["hs6"] == r["expected_hs6"],
            "on": {"cn8": r["cn8"], "route": r["route"], "hit": r["hit"]},
            "off": {"cn8": r["off"]["cn8"], "route": r["off"]["route"], "hit": r["off"]["hit"]}}


def override_measures(runs: list[list[dict]], override_min: int = OVERRIDE_MIN) -> dict:
    """Feature 008: the switch off against the run's switch on (at `override_min`): the measures with the switch off, the
    overrides that fired with their outcome in each state, and the lines whose rulings supported the model's candidate
    2 or 3 with how often it was the right HS-6."""
    off = measures([off_rows(run) for run in runs])
    return {"override_min": override_min,
            "off": {key: off[key] for key in ("right_runs", "majority_right", "routes_runs", "right_auto_runs",
                                              "wrong_auto_runs", "origin_runs")},
            "overrides_runs": [[_override(r) for r in run if r["override"]["fired"]] for run in runs],
            "supported_runs": [{"lines": sum(r["supported"]["rank"] is not None for r in run),
                                "right": sum(r["supported"]["right"] is True for r in run)} for run in runs]}


# --------------------------------------------------------------------------- the report
def _runs(values: Any) -> str:
    return " / ".join(str(v) for v in values)


def _origins(o: dict, layer: str) -> str:
    parts = [k for k in ORIGINS if k.startswith(layer)]
    return f"{sum(o[k] for k in parts)} ({' / '.join(str(o[k]) for k in parts)})"


def _wrong_auto_lines(wrong_auto_runs: list[list[dict]]) -> list[str]:
    """Each wrongly auto-accepted line once, with the runs of each outcome."""
    by_ref: dict[str, dict[tuple, list[int]]] = {}
    expected: dict[str, str] = {}
    for k, run in enumerate(wrong_auto_runs, start=1):
        for w in run:
            expected[w["reference"]] = w["expected"]
            by_ref.setdefault(w["reference"], {}).setdefault((w["cn8"], w["hs6"], w["origin"]), []).append(k)
    return [f"- {ref} (expected {expected[ref]}): "
            + "; ".join(f"run{'s' if len(ks) > 1 else ''} {', '.join(map(str, ks))}: {cn8} under {hs6}, {ORIGIN_TEXT[o]}"
                        for (cn8, hs6, o), ks in outcomes.items())
            for ref, outcomes in by_ref.items()]


def _seen_text(seen: list[dict]) -> str:
    """A line's outcome in each run, once when every run gave the same."""
    texts = [f"{s['cn8'] or 'no CN-8'} ({s['route']}, {ORIGIN_TEXT[s['origin']]})" for s in seen]
    return f"{texts[0]} in every run" if len(set(texts)) == 1 else " · ".join(texts)


def _entry_sections(h: dict) -> list[str]:
    n = h["n"]
    run = f", {h['lang']}, query expansion {h['expansion']}" if "lang" in h else ""   # feature 009
    out = ["", f"## Iteration {h['iteration']} ({h.get('tag', '-')}, {h['model']}{run}, {h['run_on']})", ""]
    if h.get("replay_of"):
        r = h["replay_of"]
        out += [f"Replay of iteration {r['iteration']} ({r.get('tag') or '-'}) at OVERRIDE_MIN {h['override_min']}, from "
                "its stored answers: no model call; the CN-8 answers below were asked in that run.", ""]
    out += ["| Run | Right end to end | Auto-accepted | Wrong auto-accepts | Review | Ask the shipper | From the HS-6 step "
            "(wrong / flagged / failed / no candidate) | From the CN-8 step (wrong / question / failed) | Time (upload, in "
            "all) | Cost |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, routes in enumerate(h["routes_runs"]):
        out.append(f"| {k + 1} | {h['right_runs'][k]}/{n} | {routes['auto_accept']} | {len(h['wrong_auto_runs'][k])} | "
                   f"{routes['review']} | {routes['ask_shipper']} | {_origins(h['origin_runs'][k], 'hs6')} | "
                   f"{_origins(h['origin_runs'][k], 'cn8')} | {h['upload_s_runs'][k]:.0f} s, {h['elapsed_s_runs'][k]:.0f} s | "
                   f"€{h['cost_eur_runs'][k]:.4f} |")
    mo = h["majority_origin"]
    out += ["", f"Majority (the most frequent CN-8 pick of each line; a tie goes to the earliest run): {h['majority_right']} "
                f"of {n} right end to end; of the {n - h['majority_right']} others, {mo['hs6']} went wrong at the HS-6 step "
                f"and {mo['cn8']} at the CN-8 step.",
            "", f"By layer, per run: the HS-6 top-1 right in {_runs(h['hs6_top1_runs'])} of {n}; a wrong HS-6 decided by the "
                f"gate in {_runs(h['hs6_wrong_auto_runs'])}; the CN-8 right where the HS-6 it ran on was right in "
                + _runs(f"{a} of {b}" for a, b in h["cn8_after_right_hs6_runs"]) + ".",
            "", f"Cut at 300 characters: {h['cut']} of {n} lines. Right end to end per run: {_runs(h['cut_right_runs'])} of "
                f"the cut lines, {_runs(h['uncut_right_runs'])} of the other {n - h['cut']}.",
            "", f"Same CN-8 pick in all runs: {h['same_cn8']}/{n}; same route: {h['same_route']}/{n}. Right auto-accepts per "
                f"run: {_runs(h['right_auto_runs'])}."]
    if h.get("parse"):
        p = h["parse"]
        out += ["", f"Invalid answers (retried at most {p['retry_limit']} time{'' if p['retry_limit'] == 1 else 's'}): "
                + "; ".join(f"run {k + 1}: {r['retries']} retried, {r['failed_calls']} calls still invalid, "
                            f"{r['failed_lines']} lines failed" for k, r in enumerate(p["runs"])) + "."]
    wrong = _wrong_auto_lines(h["wrong_auto_runs"])
    out += ["", f"### Wrong auto-accepts ({len(wrong)} line{'' if len(wrong) == 1 else 's'})"] + ([""] + wrong if wrong else [])
    always = [f"- {a['reference']} (expected {a['expected']}): {_seen_text(a['seen'])}" for a in h["always_wrong"]]
    out += ["", f"### Lines wrong in every run ({len(always)})"] + ([""] + always if always else [])
    if "off" in h:
        out += _override_section(h)
    return out


def _outcome(o: dict) -> str:
    return f"({o['route']}, {'right' if o['hit'] else 'wrong'})"


def _override_section(h: dict) -> list[str]:
    """Feature 008: the run's switch on (the entry above) against the switch off, replayed from the same answers."""
    n, off = h["n"], h["off"]
    out = ["", "### Precedent override (feature 008)", "",
           f"The run was made with the switch on (OVERRIDE_MIN {h['override_min']}), so the entry above is the switch on. "
           "The switch off is replayed from the same answers: on a line the override decided, the HS-6 goes to review, the "
           "clerk confirms the top candidate, and its CN-8 is the CN-8 step's answer under it, asked in the same run "
           "(outside the run time, inside the cost).", "",
           "| Run | Switch | Right end to end | Auto-accepted | Wrong auto-accepts | Review | Ask the shipper |",
           "|---|---|---|---|---|---|---|"]
    for k in range(len(h["right_runs"])):
        for switch, m in (("off", off), ("on", h)):
            routes = m["routes_runs"][k]
            out.append(f"| {k + 1} | {switch} | {m['right_runs'][k]}/{n} | {routes['auto_accept']} | "
                       f"{len(m['wrong_auto_runs'][k])} | {routes['review']} | {routes['ask_shipper']} |")
    fired = h["overrides_runs"]
    out += ["", f"Overrides that fired per run: {_runs(len(f) for f in fired)}, of which chose the right HS-6: "
                f"{_runs(sum(x['hs6_right'] for x in f) for f in fired)}. The rulings' majority supported the model's "
                f"candidate 2 or 3 on {_runs(s['lines'] for s in h['supported_runs'])} lines per run; that candidate was "
                f"the right HS-6 on {_runs(s['right'] for s in h['supported_runs'])}."]
    differ = [f"- run {k}: {x['reference']} (expected {x['expected']}): off {x['off']['cn8'] or 'no CN-8'} under "
              f"{x['top1']} {_outcome(x['off'])}; on {x['on']['cn8'] or 'no CN-8'} under {x['chosen']}, candidate "
              f"{x['rank']} {_outcome(x['on'])}" for k, f in enumerate(fired, start=1) for x in f if x["on"] != x["off"]]
    return out + ["", f"Lines whose outcome differs between the two states: {len(differ)}."] + ([""] + differ if differ else [])


def render_report(history: list[dict], data: dict) -> str:
    out = [
        "# End-to-end evaluation report (feature 007)",
        "",
        f"- **Set**: `tests/eval/cn8_eval_set.json`, the CN-8 eval's {len(data['rulings'])} EBTI rulings (built "
        f"{data['built_on']}); a line's correct HS-6 and CN-8 are its ruling's.",
        "- **Method**: each ruling's goods description is a row of an uploaded file, cut at 300 characters as the product's "
        "parser cuts it, and the lines run the upload's steps through the line store: the description check, the HS-6 step "
        "and its vote gate, the CN-8 step and its vote gate for the lines whose HS-6 the gate decided, and the routes "
        f"(threshold {DEFAULT_THRESHOLD}, ask floor {ASK_FLOOR}). A line's own ruling is never a precedent and never votes "
        "(leave-one-out); ruling validity on the set's build date. Then the clerk confirms the HS-6 each line in review "
        "opens with (the top candidate) and the CN-8 step runs on it. A flagged line stays locked. TARIC is not run. "
        "`python tests/eval/e2e_eval.py --repeat 3`.",
        "- **Right end to end**: the line's CN-8 pick, written by rule or to confirm, is the ruling's CN-8. "
        "**Auto-accepted**: the HS-6 decided by the gate and the CN-8 written by rule; a CN-8 left to confirm counts as "
        "review. **Wrong auto-accepts**: auto-accepted with a wrong CN-8. The other lines went wrong at the **HS-6 step** "
        "(a wrong HS-6, or none: flagged, failed, no candidate) or at the **CN-8 step** (a wrong CN-8, a question to the "
        "shipper, a failure).",
        "",
        "| Iteration | Run on | Tag | Model | Runs | Right end to end per run | Majority | Auto-accepted per run | "
        "Wrong auto-accepts per run | Review per run | Ask per run | Cost, time |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for h in history:
        n = h["n"]
        out.append(f"| {h['iteration']} | {h['run_on']} | {h.get('tag', '-')} | {h['model']} | {h['repeat']} | "
                   f"{_runs(h['right_runs'])} of {n} | {h['majority_right']}/{n} | "
                   f"{_runs(r['auto_accept'] for r in h['routes_runs'])} | {_runs(len(w) for w in h['wrong_auto_runs'])} | "
                   f"{_runs(r['review'] for r in h['routes_runs'])} | {_runs(r['ask_shipper'] for r in h['routes_runs'])} | "
                   f"${h['cost_usd']:.4f} (€{h['cost_eur']:.4f}), {h['elapsed_s']:.0f} s |")
    for h in history:
        out += _entry_sections(h)
    out += ["", "Line-by-line results of the latest run: `tests/eval/e2e_eval.json`; each run also keeps its own, "
            "`tests/eval/e2e_eval_<tag>.json`.", ""]
    return "\n".join(out)


def replay_main(args: argparse.Namespace, data: dict, source: dict, override_min: int) -> int:
    """Feature 008: a stored run's answers with the switch on at a higher `override_min`, with no model call. The replay
    keeps its own results file (e2e_eval.json stays the latest paid run), a history entry marked as a replay, and the
    report."""
    s = source["summary"]
    runs = [[replay_row(r, override_min) for r in run] for run in (source.get("runs") or [source["rows"]])]
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    iteration = max((h["iteration"] for h in history), default=0) + 1
    m = measures(runs)
    entry = {"iteration": iteration, "run_on": date.today().isoformat(), **({"tag": args.tag} if args.tag else {}),
             **{k: s[k] for k in ("model", "reasoning", "lang", "expansion", "threshold", "ask_floor", "temperature",
                                  "seed", "repeat") if k in s},
             "replay_of": {"iteration": s["iteration"], "tag": s.get("tag")}, **m, **override_measures(runs, override_min),
             **({"parse": s["parse"]} if "parse" in s else {}), "upload_s_runs": [0.0] * len(runs),
             "elapsed_s_runs": [0.0] * len(runs), "elapsed_s": 0.0, "cost_usd": 0.0, "cost_eur": 0.0,
             "cost_eur_runs": [0.0] * len(runs)}
    report: dict = {"summary": {**entry, "set_built_on": data["built_on"]}, "rows": runs[0]}
    if len(runs) > 1:
        report["runs"] = runs
    history = history + [entry]
    if args.dry_run:
        print("\n== tests/eval/e2e_eval.md:\n" + render_report(history, data))
        print("dry run: nothing written")
    else:
        own = OUT.with_name(f"{OUT.stem}_{args.tag or f'iteration{iteration}'}{OUT.suffix}")
        own.write_text(dump_results(report), encoding="utf-8", newline="\n")
        HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        REPORT.write_text(render_report(history, data), encoding="utf-8", newline="\n")
    off, fired, n = entry["off"], entry["overrides_runs"], m["n"]
    print(f"end-to-end replay of iteration {s['iteration']} at OVERRIDE_MIN {override_min}, no model call")
    print(f"  switch off: right end to end per run {off['right_runs']} of {n}; routes {off['routes_runs']}; wrong "
          f"auto-accepts {[len(w) for w in off['wrong_auto_runs']]}")
    print(f"  switch on:  right end to end per run {m['right_runs']} of {n}; routes {m['routes_runs']}; wrong auto-accepts "
          f"{[len(w) for w in m['wrong_auto_runs']]}; overrides {[len(f) for f in fired]}, right HS-6 "
          f"{[sum(x['hs6_right'] for x in f) for f in fired]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # "≈" and "€" in the summary; a redirected Windows console is cp1252
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeat", type=int, default=1, help="run every line N times, independently (default 1)")
    ap.add_argument("--model", help="OpenRouter chat model for this run only (default: the configured one)")
    ap.add_argument("--tag", help="tag of the history entry; it names the run's own results file")
    ap.add_argument("--limit", type=int, help="only the first N lines of the set (with --dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="print a row, the history entry and the report; write nothing")
    ap.add_argument("--replay", help="feature 008: a results file whose stored answers are replayed at a higher "
                                     "--override-min, with no model call")
    ap.add_argument("--override-min", type=int, help=f"the OVERRIDE_MIN of a --replay (default {OVERRIDE_MIN})")
    ap.add_argument("--lang", choices=("en", "zh"), default="en",
                    help="feature 009: en, the 120 lines as given (default); zh, the 30 lines of hs6_eval_zh.json in Chinese")
    ap.add_argument("--expansion", choices=("on", "off"),
                    help="feature 009: query expansion for this run (default: CARGOLINT_QUERY_EXPANSION)")
    args = ap.parse_args(argv)
    if args.repeat < 1:
        ap.error("--repeat must be 1 or more")
    if args.limit is not None and not args.dry_run:
        ap.error("--limit is for a dry run: the history keeps whole-set runs only")
    if args.tag is not None and not TAG_RE.fullmatch(args.tag):
        ap.error("--tag names the run's results file: letters, digits, '.', '_' and '-'")
    if args.override_min is not None and not args.replay:
        ap.error("--override-min is for a --replay: a run is made at OVERRIDE_MIN")
    data = json.loads(SET.read_text(encoding="utf-8"))
    if args.replay:
        source = json.loads(Path(args.replay).read_text(encoding="utf-8"))
        override_min, run_min = args.override_min or OVERRIDE_MIN, source["summary"]["override_min"]
        if not run_min <= override_min <= HS6_VOTE_K:
            ap.error(f"--override-min must be between the run's {run_min} and {HS6_VOTE_K}: the run asked the CN-8 step "
                     "under the top candidate only where its own minimum overrode")
        return replay_main(args, data, source, override_min)
    rulings = eval_rulings(data, args.lang)
    rulings = rulings[:args.limit] if args.limit else rulings
    as_of = date.fromisoformat(data["built_on"])
    settings, found = run_settings(get_settings(), args.model)
    reasoning = {"enabled": False} if settings.reasoning_off else None   # what the calls carry
    usage = Usage()
    kb = open_knowledge_base(settings, usage_sink=usage.add)
    client = get_client(usage_sink=usage.add, settings=settings)
    price_for_run(client, found)
    if found is not None:
        client.max_retries = OTHER_MODEL_RETRIES
    invalid = count_invalid(client)
    model = client.raw._model
    temperature, seed = getattr(model, "temperature", None), getattr(model, "seed", None)   # what the calls carry
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    iteration = max((h["iteration"] for h in history), default=0) + 1
    expansion = settings.query_expansion if args.expansion is None else args.expansion == "on"
    print(f"end-to-end iteration {iteration}: {len(rulings)} lines ({args.lang}, query expansion "
          f"{'on' if expansion else 'off'}) × {args.repeat} run(s); BTI vectors "
          f"{'loaded' if getattr(kb, 'bti_vectors', None) is not None else 'not loaded'}; model {settings.chat_model}, "
          f"reasoning {reasoning}, temperature {temperature}, seed {seed}")

    runs, upload_s, elapsed, costs, parsed = [], [], [], [], []
    for k in range(args.repeat):
        before = usage.cost_eur
        invalid.clear()
        rows, up, seconds = run_once(rulings, kb, client, as_of, settings.workers, expansion)
        runs.append(rows)
        parsed.append(parse_counts(invalid, rows))
        upload_s.append(round(up, 1))
        elapsed.append(round(seconds, 1))
        costs.append(round(usage.cost_eur - before, 4))
        auto = [r for r in rows if r["route"] == "auto_accept"]
        print(f"  run {k + 1}: right end to end {sum(r['hit'] for r in rows)}/{len(rows)}, auto-accepted {len(auto)} "
              f"(wrong {sum(not r['hit'] for r in auto)}), {seconds:.0f} s, €{costs[-1]:.4f}; invalid answers {parsed[-1]}")
    m = measures(runs)
    entry = {"iteration": iteration, "run_on": date.today().isoformat(), **({"tag": args.tag} if args.tag else {}),
             "model": settings.chat_model, "reasoning": reasoning, "lang": args.lang,
             "expansion": "on" if expansion else "off", "threshold": DEFAULT_THRESHOLD, "ask_floor": ASK_FLOOR,
             "temperature": temperature, "seed": seed, "repeat": args.repeat, **m, **override_measures(runs),
             "parse": {"retry_limit": client.max_retries, "runs": parsed}, "upload_s_runs": upload_s,
             "elapsed_s_runs": elapsed, "elapsed_s": round(sum(elapsed), 1), "cost_usd": round(usage.cost_usd, 4),
             "cost_eur": round(usage.cost_eur, 4), "cost_eur_runs": costs}
    summary = {**entry, "set_built_on": data["built_on"],
               "usage": {"total_tokens": usage.total_tokens, "prompt_tokens": usage.prompt_tokens,
                         "completion_tokens": usage.completion_tokens, "calls": usage.calls,
                         "cost_usd": round(usage.cost_usd, 4), "cost_eur": round(usage.cost_eur, 4)}}
    report: dict = {"summary": summary, "rows": runs[0]}
    if args.repeat > 1:
        report["runs"] = runs
    history = history + [entry]
    n = len(rulings)
    if args.dry_run:
        print("\n== a row (run 1, line 1):\n" + json.dumps(runs[0][0], ensure_ascii=False, indent=1))
        print("\n== the history entry:\n" + json.dumps(entry, ensure_ascii=False, indent=1))
        print("\n== tests/eval/e2e_eval.md:\n" + render_report(history, data))
        print("dry run: nothing written")
    else:
        write_results(report, OUT, results_name(args.tag or f"iteration{iteration}", args.lang, expansion))
        HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        REPORT.write_text(render_report(history, data), encoding="utf-8", newline="\n")
    print(f"right end to end per run {m['right_runs']} of {n}; majority {m['majority_right']}/{n} "
          f"(of the others, {m['majority_origin']['hs6']} from the HS-6 step, {m['majority_origin']['cn8']} from the CN-8 step)")
    print(f"  routes per run {m['routes_runs']}; wrong auto-accepts per run {[len(w) for w in m['wrong_auto_runs']]}")
    off, fired = entry["off"], entry["overrides_runs"]
    print(f"  switch off (replayed): right end to end per run {off['right_runs']} of {n}; routes per run "
          f"{off['routes_runs']}; wrong auto-accepts per run {[len(w) for w in off['wrong_auto_runs']]}; overrides per run "
          f"{[len(f) for f in fired]}, right HS-6 {[sum(x['hs6_right'] for x in f) for f in fired]}")
    print(f"  error origins per run {m['origin_runs']}")
    print(f"  HS-6 top-1 per run {m['hs6_top1_runs']}; wrong HS-6 decided by the gate per run {m['hs6_wrong_auto_runs']}; "
          f"CN-8 right where the HS-6 was right {m['cn8_after_right_hs6_runs']}")
    print(f"  cut lines {m['cut']}: right per run {m['cut_right_runs']}; uncut right per run {m['uncut_right_runs']}")
    print(f"  {sum(elapsed):.0f} s (upload steps {sum(upload_s):.0f} s); usage {usage.total_tokens} tokens, {usage.calls} calls, "
          f"${usage.cost_usd:.4f} ≈ €{usage.cost_eur:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
