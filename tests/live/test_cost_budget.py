"""Live budget check (SC-010): the sample shipment plus two follow-up questions against the real model and
the built knowledge base must cost under EUR 0.10. Also an end-to-end smoke test of the agent flow.
Writes tests/eval/budget.json for the README."""
import json
from pathlib import Path

import pytest

from agent.agent import run_turn
from agent.config import get_settings
from agent.schemas import LineStatus
from agent.store import LineStore
from rag.loader import open_knowledge_base

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "samples" / "sample_packing_list.xlsx"


def test_sample_shipment_plus_two_followups_stays_under_budget():
    kb = open_knowledge_base(get_settings())
    store = LineStore(backend={}, index=kb.index)
    store.new_shipment(reference="HOL-2026-10-0472", threshold=85)
    file_ref = store.register_file(SAMPLE.read_bytes(), "sample_packing_list.xlsx")
    events = []
    r1 = run_turn("Check the packing list for HOL-2026-10-0472.", store, kb, on_progress=events.append, file_ref=file_ref)
    assert len(store.lines) == 12
    assert all(l.current.status == LineStatus.checked for l in store.lines), [l.current.error_reason for l in store.lines]
    tools_called = [e.tool for e in events if e.phase == "start"]
    assert "check_description" in tools_called and "classify_hs6" in tools_called
    counts = store.counts()
    r2 = run_turn("Why only 31% on line 1? Last time their parts were all filed as 8452.90.", store, kb, selected_line_no=1)
    r3 = run_turn("Which lines need me to ask the shipper, and what exactly should I ask for?", store, kb)
    usage = store.shipment.usage
    report = {"tokens": usage.total_tokens, "calls": usage.calls, "cost_usd": round(usage.cost_usd, 4), "cost_eur": round(usage.cost_eur, 4),
              "counts": counts, "tool_calls_check": r1.tool_calls, "elapsed_check_s": r1.check_run.elapsed_s if r1.check_run else None,
              "answers": {"why_31": r2.text[:400], "what_to_ask": r3.text[:400]},
              "lines": [{"line_no": l.line_no, "text": l.current.display_text, "flag": l.current.flag.kind.value if l.current.flag else None,
                         "top": l.current.top_code, "confidence": l.current.top_confidence, "route": store.effective_route(l)} for l in store.lines]}
    (ROOT / "tests" / "eval" / "budget.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False)[:1500])
    assert usage.total_tokens > 0 and usage.calls > 0
    assert usage.cost_eur < 0.10, f"cost €{usage.cost_eur:.4f} exceeds the €0.10 budget"
