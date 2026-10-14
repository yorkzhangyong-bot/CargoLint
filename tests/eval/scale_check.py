"""Scale check (SC-005, FR-006): a 100-line list must complete within 5 minutes with the first progress step
visible within 2 seconds, and a 201-line file must be rejected whole before any model call.

    python tests/eval/make_big_list.py --lines 100 && python tests/eval/make_big_list.py --lines 201
    python tests/eval/scale_check.py

Needs OPENROUTER_API_KEY and a built knowledge base. Writes tests/eval/scale.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.agent import run_turn  # noqa: E402
from agent.config import get_settings  # noqa: E402
from agent.store import LineStore  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from tools.parse_packing_list import parse_packing_list  # noqa: E402
from tools.parsers import TooManyLines  # noqa: E402

BIG = ROOT / "tests" / "eval" / "big_100.xlsx"
OVER = ROOT / "tests" / "eval" / "big_201.xlsx"


def main() -> int:
    settings = get_settings()
    if not settings.api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2
    kb = open_knowledge_base(settings)
    try:
        parse_packing_list(OVER.read_bytes(), OVER.name)
        rejected = False
        print("201-line file: NOT rejected (unexpected)")
    except TooManyLines as exc:
        rejected = True
        print("201-line file rejected whole:", exc)
    store = LineStore(backend={}, index=kb.index)
    store.new_shipment(reference="BIG-100", threshold=85)
    ref = store.register_file(BIG.read_bytes(), BIG.name)
    first: dict[str, float] = {}
    t0 = time.perf_counter()

    def on_progress(ev) -> None:
        if ev.phase == "start" and "first_step_s" not in first:
            first["first_step_s"] = round(time.perf_counter() - t0, 2)

    res = run_turn("Check the packing list for BIG-100.", store, kb, on_progress=on_progress, file_ref=ref)
    elapsed = round(time.perf_counter() - t0, 1)
    statuses = [l.current.status.value for l in store.lines]
    report = {"lines": len(store.lines), "elapsed_s": elapsed, "first_step_s": first.get("first_step_s"), "workers": settings.workers,
              "checked": statuses.count("checked"), "failed": statuses.count("failed"), "counts": store.counts(), "tool_calls": res.tool_calls,
              "steps": [(s.tool, s.run_by, s.elapsed_s) for s in res.check_run.steps], "usage": store.shipment.usage.model_dump(),
              "rejected_201": rejected, "passed": elapsed <= 300 and (first.get("first_step_s") or 99) <= 2 and rejected and statuses.count("failed") == 0}
    (ROOT / "tests" / "eval" / "scale.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "usage"}, indent=1))
    print(f"cost €{report['usage']['cost_eur']:.4f}")
    print("PASS" if report["passed"] else "FAIL")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
