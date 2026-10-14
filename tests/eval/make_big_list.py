"""Generate large packing lists for the scale check (SC-005, FR-006).

    python tests/eval/make_big_list.py --lines 100          # tests/eval/big_100.xlsx
    python tests/eval/make_big_list.py --lines 201          # one over the cap, must be rejected whole

Lines cycle through the labelled and sample descriptions with small variations so that every line is
distinct. Synthetic data.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = [("", ""), (" 蓝色", ", blue"), (" 红色", ", red"), (" 大号", ", large"), (" 小号", ", small"), (" 2件装", ", 2-pack"),
            (" 黑色", ", black"), (" 白色", ", white")]


def base_lines() -> list[dict]:
    sample = json.loads((ROOT / "data" / "samples" / "sample_lines.json").read_text(encoding="utf-8"))["lines"]
    labelled = [json.loads(l) for l in (ROOT / "data" / "labelled" / "lines_20.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    seen = set()
    out = []
    for l in labelled + sample:
        key = (l["text_zh"], l["text_en"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"zh": l["text_zh"], "en": l["text_en"]})
    return out


def make(lines: int, out: Path) -> Path:
    base = base_lines()
    wb = Workbook()
    ws = wb.active
    ws.title = "装箱单"
    ws.append(["装箱单 PACKING LIST", "", "", "", ""])
    ws.append(["Shipper: Yiwu Hengfa Trading", "", "From: Shanghai → To: Hamburg", "LCL", f"Ref: BIG-{lines}"])
    ws.append(["序号 No.", "品名 Description", "数量 Qty (CTN)", "毛重 G.W. (kg)", "金额 Amount (USD)"])
    for i in range(lines):
        b = base[i % len(base)]
        vzh, ven = VARIANTS[(i // len(base)) % len(VARIANTS)]
        desc = f"{b['zh']}{vzh} / {b['en']}{ven}" if b["zh"] and b["en"] else (b["zh"] + vzh or b["en"] + ven)
        ws.append([i + 1, desc, f"{10 + i % 40} CTN", 100 + i, 1000 + 10 * i])
    ws.append(["合计 Total", "", "", "", ""])
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=100)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else ROOT / "tests" / "eval" / f"big_{args.lines}.xlsx"
    print("wrote", make(args.lines, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
