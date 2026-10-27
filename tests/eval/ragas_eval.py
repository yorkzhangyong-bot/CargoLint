"""Retrieval evaluation on the labelled set, RAGAs-style metrics computed deterministically (stretch, SC-011).

    python tests/eval/ragas_eval.py                 # hybrid and vector_only
    python tests/eval/ragas_eval.py --k 6

For every clear labelled line the reference is the nomenclature chunk of the expected HS-6 code. Metrics per
retrieval mode, before any ranking by the model:
  context recall@k   — the reference chunk is among the k retrieved chunks (fraction of lines)
  context precision  — rank-weighted: 1/rank of the reference chunk when retrieved, else 0 (= MRR)
  chapter hit@k      — a chunk of the expected chapter is among the retrieved chunks
These are the "context recall / context precision" ideas of the RAGAs framework computed against ground-truth
chunk ids instead of with an LLM judge; the ragas library itself is not used. Needs OPENROUTER_API_KEY for the
embeddings of the queries (and the expansion call when CARGOLINT_QUERY_EXPANSION is on). Writes
tests/eval/retrieval_results.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import get_settings  # noqa: E402
from agent.llm import get_client  # noqa: E402
from agent.schemas import Usage  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from rag.retriever import precedent_codes  # noqa: E402
from rag.translate import build_queries  # noqa: E402
from tools.common import LineText  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Chinese line texts; a redirected Windows console defaults to cp1252
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--no-precedents", action="store_true", help="measure plain retrieval only, without the precedent leg")
    ap.add_argument("--modes", default="hybrid,vector_only")
    args = ap.parse_args(argv)
    settings = get_settings()
    if not settings.api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2
    kb = open_knowledge_base(settings)
    usage = Usage()
    client = get_client(usage_sink=usage.add)
    lines = [json.loads(l) for l in (ROOT / "data" / "labelled" / "lines_20.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    clear = [l for l in lines if l.get("expected_flag") == "ok" and l.get("expected_code")]
    results: dict[str, dict] = {}
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        recall = precision = chapter = 0.0
        rows = []
        for i, l in enumerate(clear, start=1):
            text = LineText(line_no=i, text_zh=l["text_zh"], text_en=l["text_en"])
            queries = build_queries(client, text, get_settings().query_expansion)
            vecs = kb.retriever.embed_queries(queries)
            chunks, _trace = kb.retriever.search(queries, chapter_filter=None, mode=mode, k=args.k, query_vectors=vecs)
            ids = [c.id for c in chunks]
            if not args.no_precedents and getattr(kb, "bti_vectors", None) is not None:
                # the precedent leg of classify_hs6 (FR-051): matching rulings propose up to three codes
                for p in precedent_codes(kb.bti_vectors, kb.bti, vecs, k=args.k)[:3]:
                    ch = kb.index.get(p["code"])
                    if ch is not None and ch.id not in ids:
                        chunks.append(ch)
                        ids.append(ch.id)
            ref = f"hs:{l['expected_code']}"
            rank = ids.index(ref) + 1 if ref in ids else None
            recall += 1 if rank else 0
            precision += (1 / rank) if rank else 0
            chapter += 1 if any(c.metadata.get("chapter") == l["expected_code"][:2] for c in chunks) else 0
            rows.append({"text": f"{l['text_zh']} / {l['text_en']}", "expected": l["expected_code"], "rank": rank, "retrieved": ids})
        n = len(clear)
        results[mode] = {"k": args.k, "n": n, "context_recall": round(recall / n, 3), "context_precision_mrr": round(precision / n, 3),
                         "chapter_hit": round(chapter / n, 3), "rows": rows}
        print(f"== {mode} (k={args.k}, n={n}): context recall {recall / n:.0%}, context precision (MRR) {precision / n:.2f}, chapter hit {chapter / n:.0%}")
        for r in rows:
            print(f"  {'ok ' if r['rank'] else 'MISS'} rank {str(r['rank']):4} {r['text'][:46]:46} expected {r['expected']}")
    results["usage"] = usage.model_dump()
    (ROOT / "tests" / "eval" / "retrieval_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"usage: {usage.total_tokens} tokens, ${usage.cost_usd:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
