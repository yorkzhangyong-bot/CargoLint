"""Build the fixed CN-8 evaluation set (feature 004, SC-002; data-model §9, research R-12). Run once, before any tuning:

    python tests/eval/make_cn8_eval_set.py

Draws 10 valid EBTI rulings from each of the 12 target chapters, only under subheadings with at least two CN 2026 CN-8
lines and only where the ruling's CN-8 is one of them; English first, then German, then other languages; fixed seed.
Needs the full EBTI build (store/bti_docs.jsonl) and data/nomenclature_2026.jsonl; no key. Writes
tests/eval/cn8_eval_set.json and refuses when a chapter has fewer than 10 eligible rulings (the --demo build).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rag.bti import TARGET_CHAPTERS, parse_date  # noqa: E402
from rag.nomenclature import NomenclatureIndex  # noqa: E402

SOURCE = ROOT / "store" / "bti_docs.jsonl"
OUT = ROOT / "tests" / "eval" / "cn8_eval_set.json"
PER_CHAPTER = 10
SEED = 2026


def language_rank(language: str) -> int:
    return {"en": 0, "de": 1}.get((language or "").lower(), 2)


def eligible(r: dict, index: NomenclatureIndex, built_on: date) -> bool:
    cn = r.get("cn_code") or ""
    if len(cn) < 8 or r.get("chapter") not in TARGET_CHAPTERS or not (r.get("description") or "").strip():
        return False
    start, end = parse_date(r.get("valid_from")), parse_date(r.get("valid_to"))
    if (end is not None and end < built_on) or (start is not None and start > built_on):
        return False
    lines = [code for code, _ in index.cn8_lines(r.get("code", ""))]
    return len(lines) >= 2 and cn[:8] in lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    if not SOURCE.exists():
        print(f"{SOURCE} not found: build the EBTI index first (python -m rag.loader)")
        return 2
    index = NomenclatureIndex.from_jsonl(ROOT / "data" / "nomenclature_2026.jsonl")
    built_on = date.today()
    by_chapter: dict[str, list[dict]] = {c: [] for c in TARGET_CHAPTERS}
    with SOURCE.open(encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            if eligible(r, index, built_on):
                by_chapter[r["chapter"]].append(r)
    short = {c: len(rs) for c, rs in by_chapter.items() if len(rs) < PER_CHAPTER}
    if short:
        print(f"refused: fewer than {PER_CHAPTER} eligible rulings in chapter(s) {short} (the demo build is too small)")
        return 1
    rng = random.Random(SEED)
    rulings = []
    for chapter in TARGET_CHAPTERS:
        tiers: dict[int, list[dict]] = {}
        for r in sorted(by_chapter[chapter], key=lambda r: r["reference"]):
            tiers.setdefault(language_rank(r.get("language", "")), []).append(r)
        ordered = []
        for rank in sorted(tiers):
            rng.shuffle(tiers[rank])
            ordered += tiers[rank]
        for r in ordered[:PER_CHAPTER]:
            rulings.append({"reference": r["reference"], "chapter": chapter, "hs6": r["code"], "cn8": r["cn_code"][:8],
                            "language": r.get("language", ""), "description": r["description"]})
    payload = {"built_on": built_on.isoformat(), "seed": SEED, "per_chapter": PER_CHAPTER,
               "source": "store/bti_docs.jsonl (full EBTI build) and data/nomenclature_2026.jsonl (CN 2026)",
               "rulings": rulings}
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    langs = {}
    for r in rulings:
        langs[r["language"]] = langs.get(r["language"], 0) + 1
    print(f"wrote {len(rulings)} rulings to {args.out.relative_to(ROOT)}: "
          + ", ".join(f"{c} {sum(1 for r in rulings if r['chapter'] == c)}" for c in TARGET_CHAPTERS)
          + f"; languages {langs}; eligible per chapter {({c: len(rs) for c, rs in by_chapter.items()})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
