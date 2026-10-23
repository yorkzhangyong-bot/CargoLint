"""SC-004 acceptance aid (feature 003, task T027): the knowledge-base load time at app start, with or without
data/taric.jsonl, measured as feature 002's T037 did. One fresh process per run:

    python tests/eval/kb_load_time.py with
    python tests/eval/kb_load_time.py without

Run `with` and `without` alternately, three times each, and compare each pair: the run with the snapshot may be at most
2 s slower (FR-011). Needs a built knowledge base; makes no model call.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import rag.loader as loader  # noqa: E402
from agent.config import get_settings  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("with", "without"):
        print("usage: python tests/eval/kb_load_time.py with|without", file=sys.stderr)
        return 2
    mode = sys.argv[1]
    if mode == "without":
        loader.TARIC_SNAPSHOT = ROOT / "data" / "no-such-taric.jsonl"
    t0 = time.perf_counter()
    kb = loader.open_knowledge_base(get_settings())
    print(f"{mode:8} snapshot: {time.perf_counter() - t0:5.2f} s, kb.taric loaded: {kb.taric is not None}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
