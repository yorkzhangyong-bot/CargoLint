"""Tool 7 — lookup_taric: the TARIC subdivisions and measures for each line's CN-8 and the shipment's origin, with the
rules applied in code (feature 004, contracts/tools.md §1.7).

The lookup and the rules are deterministic (`kb.taric.lookup_taric`, `agent.taric_rules`). The only model call is the
optional suggestion among several subdivisions; every failure of it is absorbed: the rule and the subdivisions stay as
looked up, nothing is written and the route is unchanged (step 3)."""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agent.llm import StructuredCaller
from agent.prompts import SUBDIVISION_SYSTEM, subdivision_user
from agent.routing import validate_taric10
from agent.schemas import (SubdivisionOut, TaricInput, TaricLine, TaricOutcome, TaricResult, TaricRule, TaricSuggestion,
                           WrittenBy)
from agent.taric_rules import code_to_write, confirm_types, taric_rule
from tools import register
from tools.common import get_context, run_per_line

log = logging.getLogger(__name__)

SUGGEST_RETRIES = 1    # one retry on invalid output, then the suggestion is unavailable


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def rule_outcome(cn8: str, cn8_written: bool, origin: str, kb: Any) -> tuple[TaricOutcome, list[Any]]:
    """Steps 1 and 2: the lookup for the CN-8 and origin, the rule, and the code the rule writes; no model call.
    Returns the outcome and the subdivisions looked up ([] when no snapshot is loaded)."""
    taric = getattr(kb, "taric", None)
    if taric is None:
        return TaricOutcome(origin=origin, rule=TaricRule.not_loaded), []
    subdivisions = taric.lookup_taric(cn8, origin)
    rule = taric_rule(subdivisions, snapshot_loaded=True)
    code = code_to_write(rule, subdivisions, cn8_written)
    outcome = TaricOutcome(origin=origin, snapshot_date=taric.snapshot.snapshot_date, rule=rule,
                           subdivisions=[s.code for s in subdivisions],
                           trade_defence=[s.code for s in subdivisions if confirm_types(s)],
                           trade_defence_types=sorted({t for s in subdivisions for t in confirm_types(s)}),
                           taric10=code, written_by=WrittenBy.rule if code else None)
    return outcome, subdivisions


def suggest_subdivision(line: Any, cn8: str, subdivisions: list[Any], client: StructuredCaller | None) -> TaricSuggestion | None:
    """Step 3: one validated call; a suggestion is kept only when the separating attribute is stated and the code is one
    of the subdivisions (FR-009). Raises on failure; the caller absorbs it."""
    if client is None:
        raise RuntimeError("no model client available")
    out = client.call(SubdivisionOut, SUBDIVISION_SYSTEM, subdivision_user(line, cn8, subdivisions), max_retries=SUGGEST_RETRIES)
    if not out.attribute_visible or not validate_taric10(out.code, [s.code for s in subdivisions]):
        return None
    return TaricSuggestion(code=out.code, confidence=out.confidence)


def taric_outcome(line: Any, cn8: str, cn8_written: bool, origin: str, kb: Any, client: StructuredCaller | None) -> TaricOutcome:
    """The TARIC step for one line. `line` has line_no, text_zh and text_en. Never raises for a suggestion failure."""
    outcome, subdivisions = rule_outcome(cn8, cn8_written, origin, kb)
    if len(subdivisions) < 2:   # one subdivision or none: nothing to suggest
        return outcome
    try:
        return outcome.model_copy(update={"suggestion": suggest_subdivision(line, cn8, subdivisions, client)})
    except Exception as exc:  # noqa: BLE001 - absorbed: the rule and the subdivisions stand, nothing is written
        log.warning("TARIC suggestion failed for line %s: %s", line.line_no, type(exc).__name__)
        return outcome.model_copy(update={"suggestion_error": _error(exc)})


def lookup_taric_lines(inp: TaricInput, kb: Any, client: StructuredCaller | None, workers: int = 4) -> list[TaricResult]:
    def one(line: TaricLine) -> TaricResult:
        return TaricResult(line_no=line.line_no, outcome=taric_outcome(line, line.cn8, line.cn8_written, inp.origin, kb, client))

    def on_error(line: TaricLine, exc: BaseException) -> TaricResult:   # only the per-line timeout gets here
        outcome, _ = rule_outcome(line.cn8, line.cn8_written, inp.origin, kb)
        return TaricResult(line_no=line.line_no, outcome=outcome.model_copy(update={"suggestion_error": _error(exc)}))

    return run_per_line(inp.lines, one, on_error, workers=workers)


def needs_taric(store: Any, line: Any) -> str | None:
    """The CN-8 of a line that needs the TARIC step: a chosen CN-8 under the decided HS-6 and no outcome for the
    shipment's origin; else None."""
    c = line.current.cn8
    if c is None or not c.cn8 or c.question or c.error or c.hs6 != store.decided_code(line)[0]:
        return None
    t = line.current.taric
    if t is not None and t.origin == store.shipment.taric_origin:
        return None
    return c.cn8


def run_taric_step(store: Any, kb: Any, client: StructuredCaller | None, line_nos: list[int] | None = None,
                   workers: int = 4) -> list[TaricResult]:
    """Run the step for the given lines (or every line that needs it) and write the outcomes through the store."""
    lines = []
    for line in store.lines:
        if line_nos and line.line_no not in line_nos:
            continue
        cn8 = needs_taric(store, line)
        if cn8 is None:
            continue
        v = line.current
        lines.append(TaricLine(line_no=line.line_no, text_zh=v.text_zh, text_en=v.text_en, cn8=cn8,
                               cn8_written=store.decided_cn8(line) is not None))
    if not lines:
        return []
    results = lookup_taric_lines(TaricInput(lines=lines, origin=store.shipment.taric_origin), kb, client, workers=workers)
    for r in results:
        store.set_taric_result(r.line_no, r.outcome)
    return results


def summarize(results: list[TaricResult]) -> str:
    if not results:
        return "No line needed a TARIC lookup"
    rules = [r.outcome.rule for r in results]
    written = sum(1 for r in results if r.outcome.taric10)
    to_confirm = sum(1 for rule in rules if rule in (TaricRule.choose, TaricRule.trade_defence))
    waiting = sum(1 for r in results if r.outcome.rule == TaricRule.auto_completed and not r.outcome.taric10)
    missing = rules.count(TaricRule.not_available)
    unloaded = rules.count(TaricRule.not_loaded)
    failed = sum(1 for r in results if r.outcome.suggestion_error)
    parts = [f"{written} written"] + ([f"{to_confirm} to confirm"] if to_confirm else []) \
        + ([f"{waiting} waiting for the CN-8"] if waiting else []) + ([f"{missing} not available"] if missing else []) \
        + ([f"{unloaded} not loaded"] if unloaded else []) + ([f"{failed} without a suggestion (call failed)"] if failed else [])
    return f"TARIC for {len(results)} line{'s' if len(results) != 1 else ''}: " + ", ".join(parts)


class TaricArgs(BaseModel):
    line_nos: list[int] | None = Field(default=None, description="Line numbers; omit for every line with a CN-8 and no TARIC "
                                                                 "outcome for the shipment's origin")


@tool("lookup_taric", args_schema=TaricArgs)
def lookup_taric_tool(line_nos: list[int] | None = None) -> str:
    """Look up the TARIC subdivisions and measures for each line's CN-8 and the shipment's origin, and apply the rules:
    auto-complete a single subdivision, leave several or trade-defence measures to the clerk, or stop at 8 digits when
    TARIC has none. Call after classify_cn8."""
    ctx = get_context()
    results = run_taric_step(ctx.store, ctx.kb, ctx.client, line_nos, workers=ctx.workers or 4)
    payload = {
        "summary": summarize(results),
        "lines": [{"line_no": r.line_no, "rule": r.outcome.rule.value, "taric10": r.outcome.taric10,
                   "subdivisions": len(r.outcome.subdivisions),
                   "suggestion": r.outcome.suggestion.code if r.outcome.suggestion else None,
                   "suggestion_error": r.outcome.suggestion_error} for r in results],
    }
    return json.dumps(payload, ensure_ascii=False)


register(lookup_taric_tool)
