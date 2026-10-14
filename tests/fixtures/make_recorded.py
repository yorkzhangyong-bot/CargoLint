"""Regenerate the recorded structured outputs replayed by tests.fakes.FakeRawClient.

    python tests/fixtures/make_recorded.py

Keys are the fenced description text ("zh / en"). Entries derived from the 12-line sample
(with explicit confidences and routes) take precedence over the labelled set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "fixtures" / "recorded"


def key(zh: str, en: str) -> str:
    return " / ".join(t for t in (zh, en) if t)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sample = json.loads((ROOT / "data" / "samples" / "sample_lines.json").read_text(encoding="utf-8"))["lines"]
    labelled = [json.loads(l) for l in (ROOT / "data" / "labelled" / "lines_20.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    judgement: dict[str, dict] = {}
    translate: dict[str, dict] = {}
    rank: dict[str, dict] = {}
    for line in labelled + sample:  # sample last so its explicit values win
        k = key(line["text_zh"], line["text_en"])
        flag = line.get("expected_flag")
        judgement[k] = {"vague": flag != "ok", "missing": [] if flag == "ok" else ["material", "product_name", "use"],
                        "reason": "specific product with material and type" if flag == "ok" else "generic term, no material, product name or use"}
        translate[k] = {"queries": [line["text_en"]] if line["text_en"] else ["unknown goods"], "hyde": None}
        code = line.get("expected_top_code") or line.get("expected_code")
        conf = line.get("expected_confidence", 90)
        rank[k] = {"candidates": [{"code": code, "confidence": conf, "rationale": f"matches subheading {code}", "history_only": False}]} if code else {"candidates": []}
    # special cases used by the tests
    rank["配件 / Parts"] = {"candidates": [
        {"code": "8452.90", "confidence": 31, "rationale": "shipper history: 6 of 6 past shipments were 8452.xx", "history_only": True},
        {"code": "9999.99", "confidence": 24, "rationale": "made-up code that must be dropped", "history_only": False},
        {"code": "8487.90", "confidence": 19, "rationale": "fallback heading for machinery parts", "history_only": False}]}
    rank["X / Unknown widget"] = {"candidates": [{"code": "9999.99", "confidence": 70, "rationale": "nonexistent", "history_only": False}]}
    rank["steel bobbin cases for industrial sewing machines"] = {"candidates": [
        {"code": "8452.90", "confidence": 96, "rationale": "bobbin cases are parts of sewing machines", "history_only": False}]}
    rank["塑料杯 / plastic cups"] = {"candidates": [{"code": "3924.10", "confidence": 90, "rationale": "plastic tableware", "history_only": False}]}
    judgement["steel bobbin cases for industrial sewing machines"] = {"vague": False, "missing": [], "reason": "material, part name and host machine given"}
    judgement["塑料杯 / plastic cups"] = {"vague": False, "missing": [], "reason": "material and product named"}
    translate["塑料杯 / plastic cups"] = {"queries": ["plastic cups", "plastic tableware"], "hyde": None}
    extract = {
        "line 1 is steel bobbin cases for industrial sewing machines": {"material": "steel", "part_name": "bobbin cases", "use": "industrial sewing machines"},
        "steel bobbin cases for industrial sewing machines": {"material": "steel", "part_name": "bobbin cases", "use": "industrial sewing machines"},
        "塑料杯": {"material": "plastic", "part_name": "cups", "use": "drinking"},
        "line 3 is plastic cups": {"material": "plastic", "part_name": "cups", "use": "drinking"},
    }
    for name, data in (("JudgementOut", judgement), ("TranslateOut", translate), ("RankOut", rank), ("ExtractOut", extract)):
        (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {len(data)} recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
