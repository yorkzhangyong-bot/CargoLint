"""Write tests/fixtures/taric/snapshot_sample.jsonl from data/taric.jsonl (feature 005, research R-13).

The 12-line sample reaches TARIC only through the CN-8 codes under its HS-6 candidates. This script copies, in schema 2:
the snapshot record, every geographical_area record (the lookup needs them for country groups and area names), and for
every CN-8 line under the HS-6 codes below, its goods_nomenclature records with their ancestors and every measure
recorded on them. The fixture is committed, so the tests never need data/taric.jsonl.

    python tests/fixtures/make_taric_sample.py [path/to/taric.jsonl]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rag.nomenclature import NomenclatureIndex  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
OUT = FIXTURES / "taric" / "snapshot_sample.jsonl"
# The HS-6 codes among the sample's candidates after the offline check (tests/fixtures/recorded), and those the
# walkthrough's scripted answers reach.
HS6_CODES = ("3926.90", "4016.93", "6109.10", "8452.90", "8487.90", "8518.30", "8543.70", "8714.91", "9403.60",
             "9405.21", "9503.00", "9617.00")


def main(source: Path) -> None:
    index = NomenclatureIndex.from_jsonl(FIXTURES / "cn2026_excerpt.jsonl")
    wanted_cn8 = {cn8 for hs6 in HS6_CODES for cn8, _ in index.cn8_lines(hs6)}
    with source.open(encoding="utf-8") as f:
        header = f.readline()
        rows = [json.loads(line) for line in f]
    goods = {r[1]: r for r in rows if r[0] == "goods_nomenclature"}
    codes: set[str] = set()
    for r in goods.values():
        if r[2] in wanted_cn8:
            node: str | None = r[1]
            while node is not None and node not in codes and node in goods:
                codes.add(node)
                node = goods[node][7]
    areas = [r for r in rows if r[0] == "geographical_area"]
    measures = [r for r in rows if r[0] == "measure" and r[2] in codes]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as out:
        out.write(header if header.endswith("\n") else header + "\n")
        for r in areas + [goods[c] for c in sorted(codes)] + measures:
            out.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    found = sorted({goods[c][2] for c in codes if goods[c][6]})
    print(f"{OUT.relative_to(ROOT)}: {len(areas)} areas, {len(codes)} codes, {len(measures)} measures; "
          f"declarable CN-8 codes {len(found)} of {len(wanted_cn8)} wanted")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "taric.jsonl")
