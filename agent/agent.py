"""The LangChain agent: wiring, progress callbacks, usage capture and the completeness guard
(contracts/tools.md §4, research.md R-01/R-05)."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.config import MAX_TOOL_CALLS, get_settings
from agent.llm import get_chat_model, get_client, load_prices, usage_from_tokens
from agent.prompts import SYSTEM_PROMPT, build_context
from agent.schemas import CheckRun, CheckStep, LineStatus, Usage, now
from tools import TOOLS, load_all
from tools.common import ToolContext, set_context

log = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    phase: str                 # start | end | error
    tool: str
    summary: str = ""
    elapsed_s: float = 0.0
    run_by: str = "agent"


@dataclass
class TurnResult:
    text: str
    check_run: CheckRun | None
    counts: dict[str, int]
    usage: Usage = field(default_factory=Usage)
    tool_calls: int = 0


class ProgressCallbackHandler(BaseCallbackHandler):
    """Turns LangChain tool start/end callbacks into ProgressEvents and CheckSteps."""

    def __init__(self, on_event: Callable[[ProgressEvent], None] | None, check_run: CheckRun) -> None:
        super().__init__()
        self.on_event = on_event
        self.check_run = check_run
        self._open: dict[Any, tuple[str, float]] = {}

    def _emit(self, ev: ProgressEvent) -> None:
        if self.on_event is not None:
            try:
                self.on_event(ev)
            except Exception:  # noqa: BLE001 - UI problems must not break the check
                log.exception("progress callback failed")

    def on_tool_start(self, serialized: dict, input_str: str, *, run_id: Any = None, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "tool"
        self._open[run_id] = (name, time.perf_counter())
        self._emit(ProgressEvent("start", name))

    def on_tool_end(self, output: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        name, t0 = self._open.pop(run_id, ("tool", time.perf_counter()))
        elapsed = time.perf_counter() - t0
        summary = _summary_of(output)
        self.check_run.steps.append(CheckStep(tool=name, summary=summary, elapsed_s=round(elapsed, 2), ok=True, run_by="agent"))
        self.check_run.tool_calls += 1
        self._emit(ProgressEvent("end", name, summary, elapsed))

    def on_tool_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        name, t0 = self._open.pop(run_id, ("tool", time.perf_counter()))
        elapsed = time.perf_counter() - t0
        summary = f"{type(error).__name__}: {str(error)[:120]}"
        self.check_run.steps.append(CheckStep(tool=name, summary=summary, elapsed_s=round(elapsed, 2), ok=False, run_by="agent"))
        self.check_run.tool_calls += 1
        self._emit(ProgressEvent("error", name, summary, elapsed))


def _summary_of(output: Any) -> str:
    import json

    content = getattr(output, "content", output)
    if isinstance(content, str):
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "summary" in data:
                return str(data["summary"])
        except (ValueError, TypeError):
            pass
        return content[:160]
    return str(content)[:160]


def _text_of(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def build_agent(model: Any, tools: list[Any]) -> Any:
    from langchain.agents import create_agent

    return create_agent(model, tools=tools, system_prompt=SYSTEM_PROMPT)


def turn_tools(reply_ref: str | None) -> list[Any]:
    """A reply turn offers only apply_shipper_reply: it re-checks the line itself, so the check tools would only redo
    that work and could outdate the contradiction note. Every other turn offers all seven tools."""
    if reply_ref:
        return [t for t in TOOLS if t.name == "apply_shipper_reply"]
    return list(TOOLS)


def run_turn(
    message: str,
    store: Any,
    kb: Any,
    selected_line_no: int | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
    file_ref: str | None = None,
    reply_ref: str | None = None,
    reply_line_no: int | None = None,
    history: list[tuple[str, str]] | None = None,
    is_check: bool | None = None,
) -> TurnResult:
    """One clerk turn: context block + code-built request → agent with tools → completeness guard → counts."""
    settings = get_settings()
    load_all()
    if reply_ref and reply_line_no is not None:
        selected_line_no = reply_line_no   # a reply turn is about its target line; the table selection must not compete with it
    ctx = ToolContext(store=store, kb=kb, settings=settings, selected_line_no=selected_line_no, reply_ref=reply_ref, reply_line_no=reply_line_no)
    set_context(ctx)
    has_shipment = store.has_shipment()
    shipment = store.shipment if has_shipment else None
    counts_before = store.counts() if has_shipment else {}
    pending_at_start = [l.line_no for l in store.lines if l.current.status == LineStatus.pending] if has_shipment else []
    if is_check is None:
        is_check = bool(pending_at_start) or message.lower().startswith("check") or bool(file_ref) or bool(reply_ref)

    context = build_context(shipment, selected_line_no, message, rules=kb.rules, counts=counts_before)
    request = [context, "", f"CLERK REQUEST: {message}"]
    if file_ref:
        request.append(f"FILE REFERENCE: {file_ref} (pass it to parse_packing_list)")
    if reply_ref:
        target = f" for line {reply_line_no}" if reply_line_no is not None else ""
        request.append(f"REPLY REFERENCE: {reply_ref}{target} (pass it to apply_shipper_reply, once)")
    if pending_at_start:
        request.append(f"PENDING LINES: {pending_at_start}")
    if selected_line_no is not None:
        request.append(f"SELECTED LINE: {selected_line_no}")
    messages: list[Any] = []
    for role, content in (history or [])[-10:]:
        messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    messages.append(HumanMessage(content="\n".join(request)))

    check_run = CheckRun(id=uuid4().hex[:8], started_at=now(), line_count=len(store.lines) if has_shipment else 0)
    handler = ProgressCallbackHandler(on_progress, check_run)
    usage_cb = UsageMetadataCallbackHandler()
    t0 = time.perf_counter()
    agent = build_agent(get_chat_model(settings), turn_tools(reply_ref))
    result = agent.invoke({"messages": messages}, config={"callbacks": [handler, usage_cb], "recursion_limit": 2 * MAX_TOOL_CALLS + 4})
    final = result.get("messages", [])[-1] if isinstance(result, dict) and result.get("messages") else None
    text = _text_of(final) if final is not None else ""

    usage = _usage_from_callback(usage_cb, settings)
    if usage.total_tokens and has_shipment:
        store.add_usage(usage)

    if is_check and has_shipment:
        _finalize(store, kb, ctx, check_run, on_progress)
    if reply_ref and reply_line_no is not None and reply_ref not in ctx.applied_replies:
        _finalize_reply(ctx, check_run, on_progress)
    check_run.elapsed_s = round(time.perf_counter() - t0, 2)
    if has_shipment:
        store.shipment.check_runs.append(check_run)
    counts = store.counts() if has_shipment else {}
    return TurnResult(text=text, check_run=check_run, counts=counts, usage=usage, tool_calls=check_run.tool_calls)


def _usage_from_callback(usage_cb: UsageMetadataCallbackHandler, settings) -> Usage:
    total = Usage()
    try:
        prices = load_prices()
    except Exception:  # noqa: BLE001
        prices = None
    for _model, meta in (usage_cb.usage_metadata or {}).items():
        prompt = int(meta.get("input_tokens", 0) or 0)
        completion = int(meta.get("output_tokens", 0) or 0)
        if prices is not None and settings.chat_model in prices.models:
            total.add(usage_from_tokens(settings.chat_model, prompt, completion, prices, settings.usd_eur))
        else:
            total.add(Usage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion, calls=1))
    return total


def _app_step(name: str, fn: Callable[[], str], check_run: CheckRun, on_progress: Callable[[ProgressEvent], None] | None) -> None:
    """Run one step on the agent's behalf and record it like a tool call, marked as run by the app."""
    t0 = time.perf_counter()
    if on_progress:
        on_progress(ProgressEvent("start", name, run_by="app"))
    try:
        summary = fn()
        ok = True
    except Exception as exc:  # noqa: BLE001
        summary, ok = f"{type(exc).__name__}: {str(exc)[:120]}", False
    elapsed = time.perf_counter() - t0
    check_run.steps.append(CheckStep(tool=name, summary=summary + " (run by the app)", elapsed_s=round(elapsed, 2), ok=ok, run_by="app"))
    if on_progress:
        on_progress(ProgressEvent("end" if ok else "error", name, summary, elapsed, run_by="app"))


def _finalize_reply(ctx: ToolContext, check_run: CheckRun, on_progress: Callable[[ProgressEvent], None] | None) -> None:
    """Completeness guard for a reply turn: when the agent finished without applying the reply, the app applies it."""
    from tools.apply_shipper_reply import apply_by_reference

    def _apply() -> str:
        out = apply_by_reference(ctx)
        return f"Applied to line {out.target_line_no}: version {out.new_version_no}"

    _app_step("apply_shipper_reply", _apply, check_run, on_progress)


def _finalize(store: Any, kb: Any, ctx: ToolContext, check_run: CheckRun, on_progress: Callable[[ProgressEvent], None] | None) -> None:
    """Completeness guard: run any step the agent skipped, then fail whatever is still pending."""
    from tools.check_description import check_descriptions, summarize as check_summary
    from tools.classify_hs6 import classify_lines, context_for_shipment, summarize as classify_summary
    from tools.common import select_lines
    from tools.lookup_precedent import lookup_precedents

    def step(name: str, fn: Callable[[], str]) -> None:
        _app_step(name, fn, check_run, on_progress)

    unchecked = [l.line_no for l in store.lines if l.current.status == LineStatus.pending and l.current.flag is None]
    if unchecked:
        def _check() -> str:
            results = check_descriptions(select_lines(store, unchecked), kb.rules, ctx.client, ctx.workers or 4)
            for r in results:
                store.update_check(r.line_no, r)
            return check_summary(results)
        step("check_description", _check)

    unclassified = [l.line_no for l in store.lines if l.current.status == LineStatus.pending and l.current.flag is not None]
    if unclassified:
        def _classify() -> str:
            cctx = context_for_shipment(store.shipment, kb)
            results = classify_lines(select_lines(store, unclassified), cctx, kb, ctx.client, ctx.workers or 4)
            for r in results:
                store.update_classification(r.line_no, r)
            return classify_summary(results, "hybrid" if cctx.hybrid else "vector_only")
        step("classify_hs6", _classify)

    no_precedent = [l for l in store.lines if l.current.candidates and not l.current.precedents_checked]
    if no_precedent:
        def _precedent() -> str:
            codes = [c.code for l in no_precedent for c in l.current.candidates]
            out = lookup_precedents(codes, kb.bti, date.today())
            matched = 0
            for l in no_precedent:
                store.update_precedents(l.line_no, out.by_code)
                matched += sum(1 for c in l.current.candidates if c.precedent is not None)
            return f"{matched} BTI rulings matched"
        step("lookup_precedent", _precedent)

    # feature 004: the CN-8 step for decided lines without a CN-8 choice for that HS-6
    no_cn8 = [l.line_no for l in store.lines
              if (hs6 := store.decided_code(l)[0]) and (l.current.cn8 is None or l.current.cn8.hs6 != hs6)]
    if no_cn8:
        from tools.classify_cn8 import run_cn8_step, summarize as cn8_summary

        step("classify_cn8", lambda: cn8_summary(run_cn8_step(store, kb, ctx.client, no_cn8, workers=ctx.workers or 4)))

    # feature 004: the TARIC step for lines with a CN-8 and no outcome for the shipment's origin
    from tools.lookup_taric import needs_taric, run_taric_step, summarize as taric_summary

    no_taric = [l.line_no for l in store.lines if needs_taric(store, l)]
    if no_taric:
        step("lookup_taric", lambda: taric_summary(run_taric_step(store, kb, ctx.client, no_taric, workers=ctx.workers or 4)))

    store.finalize_check()


def after_hs6_decision(store: Any, kb: Any, line_no: int, taric_only: bool = False) -> str:
    """Feature 004: the CN-8 step and then the TARIC step for one line once the clerk accepts or chooses its HS-6, or
    the TARIC step alone after a CN-8 confirmation (`taric_only`). The UI runs it as a background job. Its calls go
    through the usage-recording client, so the shipment's tokens and cost include them."""
    from tools.classify_cn8 import run_cn8_step, summarize as cn8_summary
    from tools.lookup_taric import run_taric_step, summarize as taric_summary

    client = get_client(usage_sink=store.add_usage, settings=get_settings())
    parts = [] if taric_only else [cn8_summary(run_cn8_step(store, kb, client, [line_no], workers=1))]
    parts.append(taric_summary(run_taric_step(store, kb, client, [line_no], workers=1)))
    return "; ".join(parts)


def recheck_line(store: Any, kb: Any, line_no: int) -> str:
    """Feature 005 (FR-017, contracts/backend.md §2): check one line's current version from the stop-word check
    onwards, with no agent turn, then run the CN-8 and TARIC steps when its HS-6 is decided. The same tool functions as
    `_finalize` and `apply_reply`; calls go through the usage-recording client. Returns a one-line summary."""
    from tools.check_description import check_descriptions, summarize as check_summary
    from tools.classify_cn8 import run_cn8_step, summarize as cn8_summary
    from tools.classify_hs6 import classify_lines, context_for_shipment, summarize as classify_summary
    from tools.common import select_lines
    from tools.lookup_precedent import lookup_precedents
    from tools.lookup_taric import needs_taric, run_taric_step, summarize as taric_summary

    if store.get_line(line_no).current.status != LineStatus.pending:
        raise ValueError(f"line {line_no} has no new description to re-check")
    client = get_client(usage_sink=store.add_usage, settings=get_settings())
    checks = check_descriptions(select_lines(store, [line_no]), kb.rules, client, workers=1)
    for r in checks:
        store.update_check(line_no, r)
    parts = [check_summary(checks)]
    if store.get_line(line_no).current.status == LineStatus.pending:   # neither failed nor a pure stop word
        cctx = context_for_shipment(store.shipment, kb)
        results = classify_lines(select_lines(store, [line_no]), cctx, kb, client, workers=1)
        for r in results:
            store.update_classification(line_no, r)
        parts.append(classify_summary(results, "hybrid" if cctx.hybrid else "vector_only"))
    if store.get_line(line_no).current.candidates:
        found = lookup_precedents([c.code for c in store.get_line(line_no).current.candidates], kb.bti, date.today())
        store.update_precedents(line_no, found.by_code)
        matched = sum(1 for c in store.get_line(line_no).current.candidates if c.precedent is not None)
        parts.append(f"{matched} BTI rulings matched")
    if store.decided_code(store.get_line(line_no))[0]:
        parts.append(cn8_summary(run_cn8_step(store, kb, client, [line_no], workers=1)))
    if needs_taric(store, store.get_line(line_no)):
        parts.append(taric_summary(run_taric_step(store, kb, client, [line_no], workers=1)))
    if store.get_line(line_no).current.status == LineStatus.pending:
        store.mark_failed(line_no, "not checked — a step did not run")
    return "; ".join(parts)


def apply_taric_origin(store: Any, kb: Any, code: str) -> str:
    """Feature 004 (FR-017, FR-018, contracts/tools.md §4): set the shipment's TARIC origin, then re-apply the lookup
    and the rules to every line with a CN-8 and a TARIC outcome. Subdivision codes do not depend on the origin, so the
    stored suggestions are reused and no model is called; the store keeps the TARIC-10 codes the clerk confirmed. A
    line whose TARIC step has not run yet is left to it. A refused origin raises ValueError and changes nothing."""
    from tools.lookup_taric import rule_outcome

    before = store.shipment.taric_origin
    origin = store.set_taric_origin(code)
    n = 0
    for line in store.lines if origin != before else []:
        c, prev = line.current.cn8, line.current.taric
        if c is None or not c.cn8 or c.question or c.error or prev is None:
            continue
        outcome, _ = rule_outcome(c.cn8, store.decided_cn8(line) is not None, origin, kb)
        if prev.subdivisions == outcome.subdivisions:
            outcome = outcome.model_copy(update={"suggestion": prev.suggestion, "suggestion_error": prev.suggestion_error})
        store.set_taric_result(line.line_no, outcome)
        n += 1
    return f"Origin {origin}: the TARIC rules re-applied to {n} line{'s' if n != 1 else ''}"


def line_taric_view(store: Any, kb: Any, line_no: int) -> Any:
    """Feature 004 (contracts/tools.md §4, Display): the line's CN-8 looked up for the shipment's origin, as
    `taric_view` groups it; None without a CN-8. The UI calls this and never reads `kb.taric` itself. Measures are
    never stored, so what the clerk sees always equals the snapshot (FR-013)."""
    from agent.taric_rules import taric_view

    line = store.get_line(line_no)
    c = line.current.cn8
    if c is None or not c.cn8:
        return None
    origin = store.shipment.taric_origin
    t = line.current.taric
    outcome = t if t is not None and t.origin == origin else None
    taric = getattr(kb, "taric", None)
    if taric is None:
        return taric_view([], origin, None, outcome)
    return taric_view(taric.lookup_taric(c.cn8, origin), origin, taric.snapshot.snapshot_date, outcome)
