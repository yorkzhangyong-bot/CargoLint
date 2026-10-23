"""Background agent turns: the agent runs in a worker thread, the script thread polls the job and
renders live progress (FR-027) and the filling review table. The worker never calls Streamlit."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from agent.agent import ProgressEvent, TurnResult, after_hs6_decision, run_turn
from agent.llm import classify_error


@dataclass
class Job:
    kind: str                                  # check | reply | question | finer_codes (feature 004)
    message: str
    is_check: bool
    file_ref: str | None = None
    reply_ref: str | None = None
    new_line_nos: list[int] | None = None
    label_prefix: str | None = None
    selected_line_no: int | None = None
    history: list[tuple[str, str]] = field(default_factory=list)
    note: str | None = None                    # prepended to the assistant text (e.g. "Applied to line 3 (selected).")
    events: list[ProgressEvent] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)
    done: bool = False
    result: TurnResult | None = None
    error: str | None = None
    thread: threading.Thread | None = None
    line_no: int | None = None                 # finer_codes: the line whose CN-8 and TARIC steps run
    taric_only: bool = False                   # finer_codes after a CN-8 confirmation: the TARIC step alone

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    @property
    def current_tool(self) -> str | None:
        running = [e.tool for e in self.events if e.phase == "start"]
        finished = [e.tool for e in self.events if e.phase in ("end", "error")]
        for t in running:
            if t not in finished:
                return t
        return None

    def step_lines(self) -> list[str]:
        out = []
        for ev in self.events:
            if ev.phase == "start":
                continue
            who = " (app)" if ev.run_by == "app" else ""
            mark = "✓" if ev.phase == "end" else "✗"
            out.append(f"{mark} **{ev.tool}**{who} — {ev.summary} · {ev.elapsed_s:.1f} s")
        return out


def start(job: Job, store: Any, kb: Any) -> Job:
    def target() -> None:
        try:
            if job.kind == "finer_codes":   # feature 004: no agent turn, just the steps for one line
                job.note = after_hs6_decision(store, kb, job.line_no, taric_only=job.taric_only)
                return
            job.result = run_turn(job.message, store, kb, selected_line_no=job.selected_line_no, on_progress=job.events.append,
                                  file_ref=job.file_ref, reply_ref=job.reply_ref, history=job.history, is_check=job.is_check,
                                  reply_line_no=job.new_line_nos[0] if job.reply_ref and job.new_line_nos else None)
        except Exception as exc:  # noqa: BLE001 - surfaced to the clerk, never swallowed
            _retry, message = classify_error(exc)
            job.error = f"{message} ({type(exc).__name__}: {str(exc)[:160]})"
        finally:
            job.done = True

    job.thread = threading.Thread(target=target, daemon=True, name=f"cargolint-{job.kind}")
    job.thread.start()
    return job


def finish_label(job: Job, store: Any) -> str:
    if job.kind == "finer_codes":
        return f"Line {job.line_no}: {'TARIC' if job.taric_only else 'CN-8 and TARIC'} updated · {job.elapsed:.0f} s"
    tools = job.result.tool_calls if job.result else sum(1 for e in job.events if e.phase in ("end", "error"))
    tools_txt = f"{tools} tool{'s' if tools != 1 else ''}"
    if job.is_check:
        n = len(store.lines) if store.has_shipment() else 0
        return f"{n} line{'s' if n != 1 else ''} checked · {tools_txt} · {job.elapsed:.0f} s"
    return f"{job.label_prefix or 'Answered'} · {tools_txt} · {job.elapsed:.0f} s"


def running_label(job: Job, store: Any) -> str:
    if job.kind == "finer_codes":
        return f"{'Looking up TARIC' if job.taric_only else 'Choosing the CN-8'} for line {job.line_no}… · {job.elapsed:.0f} s"
    tool = job.current_tool
    if job.is_check:
        n = len(store.lines) if store.has_shipment() else 0
        base = f"Checking {n} line{'s' if n != 1 else ''}" if n else "Checking"
    else:
        base = job.label_prefix.replace(" updated", "") + " — updating" if job.label_prefix else "Thinking"
    return f"{base} · {tool}… · {job.elapsed:.0f} s" if tool else f"{base}… · {job.elapsed:.0f} s"
