"""Scripted walkthrough of the 12-line sample (feature 005, SC-001, quickstart §2).

It drives the main page with AppTest, as a clerk would:
1. open the sample, and accept the ready lines;
2. choose and confirm each yellow line, including the TARIC-10 picks;
3. draft the email in both languages, while the red lines wait for the shipper;
4. for each red line, copy the question, write the shipper's scripted answer and re-check; then confirm the line;
5. accept the lines that became ready, and export CSV and JSON.

Each action's machine time goes to tests/eval/walkthrough.json, with the action count and the total. The script
measures machine time only: a first-time clerk's reading time is the author's timed run in the browser (T051).

    python -m tests.eval.walkthrough            # offline: recorded outputs and the sample TARIC fixture
    python -m tests.eval.walkthrough --live     # the real model; spends credits, run only when asked

The exit code is 1 when an action that does not wait for the model takes 1 s or more, or when the walk fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "eval" / "walkthrough.json"
LIMIT_S = 1.0

# The shipper's answers for the red lines of the sample, which the clerk types before "Re-check this line".
ANSWERS = {
    1: "Steel bobbin cases for industrial sewing machines",       # 配件 / Parts
    2: "LED desk lamp, USB powered, plastic housing",             # its CN-8 depends on the material, once its HS-6 is chosen
    4: "Plastic photo frames",                                    # 礼品 / Gift
    6: "Plastic toy cars without a motor",                        # 塑料玩具车: the CN-8 asks about a motor
    7: "Wired stereo headphones with microphone",                 # 电子产品 / Electronic products
    9: "Solid wood bookshelves",                                  # 家具 / Furniture
}
OK = {"vague": False, "missing": [], "reason": "specific product with material and type"}
# The model's recorded outputs for the answers that tests/ui/harness.py does not record already (offline mode).
RECORDED = {
    "JudgementOut": {ANSWERS[2]: OK, ANSWERS[4]: OK, ANSWERS[7]: OK, ANSWERS[9]: OK},
    "RankOut": {
        ANSWERS[2]: {"candidates": [{"code": "9405.21", "confidence": 92, "rationale": "electric desk luminaires",
                                     "history_only": False}]},
        ANSWERS[4]: {"candidates": [{"code": "3926.90", "confidence": 92, "rationale": "other articles of plastics",
                                     "history_only": False}]},
        ANSWERS[7]: {"candidates": [{"code": "8518.30", "confidence": 93, "rationale": "headphones combined with a "
                                     "microphone", "history_only": False}]},
        ANSWERS[9]: {"candidates": [{"code": "9403.60", "confidence": 92, "rationale": "other wooden furniture",
                                     "history_only": False}]},
    },
    "Cn8Out": {
        ANSWERS[2]: {"cn8": "94052140", "confidence": 95, "deciding_attribute": "", "attribute_visible": True,
                     "evidence": "plastic housing", "rationale": "of plastics", "precedent": None},
        ANSWERS[4]: {"cn8": "39269097", "confidence": 95, "deciding_attribute": "", "attribute_visible": True,
                     "evidence": ANSWERS[4], "rationale": "other articles of plastics", "precedent": None},
    },
}


class Walk:
    """One clerk's way through the sample, on one AppTest of both pages."""

    def __init__(self, live: bool) -> None:
        from agent.store import LineStore
        from tests.ui import harness as h

        self.h, self.live = h, live
        if live:
            from agent.config import get_settings
            from rag.loader import open_knowledge_base

            self.kb = open_knowledge_base(get_settings())
            index = self.kb.index
        else:
            self.kb = h.make_kb("sample")
            index = h.small_index()
        self.store = LineStore(backend={}, index=index)
        self.at = h.app(self.store, self.kb)
        self.actions: list[dict] = []

    # ----------------------------------------------------------------- recording
    def act(self, step: str, action: str, fn: Any, line: int | None = None, kind: str = "click") -> None:
        start = time.perf_counter()
        fn()
        seconds = time.perf_counter() - start
        if self.at.exception:
            raise RuntimeError(f"{action}: {self.at.exception[0].message}")
        self.actions.append({"step": step, "action": action, "line": line, "kind": kind, "seconds": round(seconds, 3)})

    def job(self) -> Any:
        try:
            return self.at.session_state["job"]
        except KeyError:
            return None

    def run_jobs(self, step: str) -> None:
        """Run what the last action started, and what waited behind it, as the background would."""
        while (job := self.job()) is not None:
            start = time.perf_counter()
            if self.live:
                while not job.done:
                    time.sleep(0.25)
            else:
                self._run_offline(job)
            seconds = time.perf_counter() - start
            label = f"{job.kind} job" + (f", line {job.line_no}" if job.line_no else "")
            self.actions.append({"step": step, "action": label, "line": job.line_no, "kind": "job",
                                 "seconds": round(seconds, 3), "error": job.error})
            self.at.run()                                            # the page finishes it and starts the next

    def _run_offline(self, job: Any) -> None:
        from ui import jobs

        script = self.h.sample_script(job.file_ref) if job.kind == "check" and job.file_ref else None
        with self.h.ModelGuard(script=script) as guard:
            for schema, table in RECORDED.items():
                guard.client.recorded.setdefault(schema, {}).update(table)
            try:
                jobs.run_job(job, self.store, self.kb)
            except Exception as exc:  # noqa: BLE001 - the page shows it, as for a real job
                job.error = f"{type(exc).__name__}: {exc}"
        job.done = True

    # ----------------------------------------------------------------- the clerk's steps
    def statuses(self) -> dict[int, Any]:
        from ui import view

        return {line.line_no: view.line_status(self.store, line) for line in self.store.lines}

    def accept_ready(self, step: str) -> None:
        if any(b.key == "accept_all" for b in self.at.button):
            label = self.at.button(key="accept_all").label
            self.act(step, label, lambda: self.at.button(key="accept_all").click().run())

    def resolve_yellow(self, step: str, limit: int = 40) -> None:
        """Open each yellow line, keep the pre-selected code and confirm it; then run the steps it starts."""
        for _ in range(limit):
            yellow = [(n, s) for n, s in self.statuses().items() if s.colour == "yellow"]
            if not yellow:
                return
            n, status = yellow[0]
            self.act(step, f"open line {n} ({status.text})", lambda: self.at.button(key=f"open_{n}").click().run(), n)
            accept = f"accept_{n}_{self.store.get_line(n).current.version_no}"
            self.act(step, f"Accept (line {n})", lambda: self.at.button(key=accept).click().run(), n)
            self.run_jobs(step)
        raise RuntimeError("yellow lines did not settle")

    def draft_email(self, step: str) -> None:
        if not any(s.key == "email_lang" for s in self.at.segmented_control):   # no line asks the shipper
            return
        self.act(step, "中文", lambda: self.at.segmented_control(key="email_lang").set_value("中文").run())

    def answer_red(self, step: str) -> None:
        for n in [n for n, s in self.statuses().items() if s.colour == "red"]:
            answer = ANSWERS.get(n)
            if answer is None:
                continue
            vn = self.store.get_line(n).current.version_no
            self.act(step, f"open line {n}", lambda: self.at.button(key=f"open_{n}").click().run(), n)
            self.actions.append({"step": step, "action": f"Copy question (line {n})", "line": n, "kind": "browser",
                                 "seconds": 0.0})
            self.act(step, f"type the shipper's answer (line {n})",
                     lambda: self.at.text_area(key=f"edit_{n}_{vn}").set_value(answer).run(), n, kind="input")
            self.act(step, f"Re-check this line (line {n})", lambda: self.at.button(key=f"recheck_{n}_{vn}").click().run(), n)
            self.run_jobs(step)

    def export(self, step: str) -> None:
        for key in ("export_csv", "export_json"):
            button = next(b for b in self.at.get("download_button") if b.key == key)
            self.act(step, button.label, lambda: button.click().run())

    def walk(self) -> None:
        self.at.run()
        self.act("1 open the sample", "Load sample invoice", lambda: self.at.button(key="sample").click().run())
        self.act("1 open the sample", "Check all lines", lambda: self.at.button(key="check_all").click().run())
        self.run_jobs("1 open the sample")
        self.accept_ready("1 accept the ready lines")
        self.resolve_yellow("2 choose and confirm the yellow lines")
        self.draft_email("3 draft the email to the shipper")
        self.answer_red("4 answer and re-check the red lines")
        self.resolve_yellow("4 confirm the re-checked lines")
        self.accept_ready("5 accept the lines that became ready")
        self.export("5 export")

    # ----------------------------------------------------------------- the report
    def report(self) -> dict:
        from collections import Counter

        clerk = [a for a in self.actions if a["kind"] != "job"]
        timed = [a for a in clerk if a["kind"] != "browser"]
        slow = [a for a in timed if a["seconds"] >= LIMIT_S]
        colours = Counter(s.colour for s in self.statuses().values())
        accepted = sum(1 for s in self.statuses().values() if s.accepted)
        return {
            "mode": "live" if self.live else "offline",
            "run_on": date.today().isoformat(),
            "lines": len(self.store.lines),
            "clerk_actions": len(clerk),
            "jobs": sum(1 for a in self.actions if a["kind"] == "job"),
            "ui_seconds": round(sum(a["seconds"] for a in timed), 2),
            "ui_max_seconds": max((a["seconds"] for a in timed), default=0.0),
            "job_seconds": round(sum(a["seconds"] for a in self.actions if a["kind"] == "job"), 2),
            "total_machine_seconds": round(sum(a["seconds"] for a in self.actions), 2),
            "limit_seconds": LIMIT_S,
            "over_limit": [a["action"] for a in slow],
            "final": {"accepted": accepted, "green": colours["green"], "yellow": colours["yellow"],
                      "red": colours["red"], "grey": colours["grey"]},
            "note": "Machine time only. The email is drafted while the red lines wait for the shipper; the answers "
                    "are scripted. The clerk's reading time is the author's timed run in the browser (T051).",
            "actions": self.actions,
        }


def _offline_guard() -> list:
    """Offline means offline: the real clients refuse, as in the test suite (tests/conftest.py)."""
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("the offline walkthrough tried to reach OpenRouter")
    return [mock.patch("agent.llm.OpenRouterRawClient", refuse), mock.patch("langchain_openai.ChatOpenAI", refuse),
            mock.patch("rag.embeddings.OpenRouterEmbeddings", refuse)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scripted walkthrough of the 12-line sample (SC-001).")
    parser.add_argument("--live", action="store_true", help="use the real model (spends credits)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    from tests.ui import harness as h
    from ui import jobs

    patches = [] if args.live else _offline_guard() + [mock.patch.object(jobs, "start", h.JobRecorder().keep_running().start)]
    for p in patches:
        p.start()
    try:
        walk = Walk(live=args.live)
        failure = None
        try:
            walk.walk()
        except Exception as exc:  # noqa: BLE001 - reported in the JSON and the exit code
            failure = f"{type(exc).__name__}: {exc}"
        report = walk.report()
    finally:
        for p in reversed(patches):
            p.stop()
    report["failure"] = failure
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{report['mode']}: {report['clerk_actions']} clerk actions, {report['jobs']} jobs, UI {report['ui_seconds']} s "
          f"(max {report['ui_max_seconds']} s), jobs {report['job_seconds']} s, total {report['total_machine_seconds']} s; "
          f"final {report['final']}; over the limit: {report['over_limit'] or 'none'}; failure: {failure or 'none'}")
    print(f"written: {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")
    return 1 if failure or report["over_limit"] else 0


if __name__ == "__main__":
    sys.exit(main())
