"""EBTI full extract → chapter- and validity-filtered rulings, document store and lookup
(research.md R-12, FR-015, FR-046)."""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator

from agent.config import DATA_DIR, STORE_DIR
from agent.schemas import Precedent

TARGET_CHAPTERS = ["39", "42", "61", "62", "63", "64", "73", "84", "85", "94", "95", "96"]
DROP_FIELDS = ("NAME_AND_ADDRESS",)
_INVALID = re.compile(r"invalid|withdraw|revok|annul|cancel", re.I)


def hs6_from_code(code: str) -> str:
    digits = re.sub(r"\D", "", code or "")
    digits = (digits + "000000")[:6]
    return f"{digits[:4]}.{digits[4:6]}"


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    v = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(v[:10], fmt).date()
        except ValueError:
            continue
    return None


def is_valid_status(status: str | None) -> bool:
    return not status or _INVALID.search(status) is None


def filter_rows(rows: Iterable[dict], chapters: set[str] | None, today: date) -> Iterator[dict]:
    for row in rows:
        digits = re.sub(r"\D", "", row.get("NOMENCLATURE_CODE", "") or "")
        if len(digits) < 6:
            continue
        if chapters and digits[:2] not in chapters:
            continue
        if not is_valid_status(row.get("STATUS")):
            continue
        end = parse_date(row.get("END_DATE_OF_VALIDITY"))
        if end is not None and end < today:
            continue
        yield row


def row_to_ruling(row: dict) -> dict:
    """Keep what the clerk may see; personal data of the holder is dropped (FR-046)."""
    digits = re.sub(r"\D", "", row.get("NOMENCLATURE_CODE", "") or "")
    start = parse_date(row.get("START_DATE_OF_VALIDITY"))
    end = parse_date(row.get("END_DATE_OF_VALIDITY"))
    return {
        "reference": (row.get("BTI_REFERENCE") or "").strip(),
        "member_state": (row.get("ISSUING_COUNTRY") or "").strip(),
        "code": hs6_from_code(digits),
        "cn_code": digits[:10],
        "chapter": digits[:2],
        "description": (row.get("DESCRIPTION_OF_GOODS") or "").strip(),
        "reasoning": (row.get("CLASSIFICATION_JUSTIFICATION") or "").strip(),
        "keywords": (row.get("KEYWORDS") or "").strip(),
        "valid_from": start.isoformat() if start else None,
        "valid_to": end.isoformat() if end else None,
        "language": (row.get("LANGUAGE") or "").strip(),
        "status": (row.get("STATUS") or "").strip(),
    }


def ruling_url(reference: str) -> str:
    from urllib.parse import quote

    return f"https://ec.europa.eu/taxation_customs/dds2/ebti/ebti_details.jsp?Lang=en&reference={quote(reference, safe='')}"


class BTIStore:
    """In-memory document store over the filtered rulings, keyed by HS-6 code."""

    def __init__(self, records: Iterable[dict]) -> None:
        self.records = list(records)
        self._by_code: dict[str, list[dict]] = {}
        for r in self.records:
            self._by_code.setdefault(r.get("code", ""), []).append(r)

    @classmethod
    def from_jsonl(cls, path: Path | str) -> "BTIStore":
        p = Path(path)
        if not p.exists():
            return cls([])
        with p.open(encoding="utf-8") as f:
            return cls(json.loads(line) for line in f if line.strip())

    def __len__(self) -> int:
        return len(self.records)

    def lookup(self, code: str, as_of: date, limit: int = 3) -> list[Precedent]:
        hits = []
        for r in self._by_code.get(code, []):
            start = parse_date(r.get("valid_from"))
            end = parse_date(r.get("valid_to"))
            if end is not None and end < as_of:
                continue
            if start is not None and start > as_of:
                continue
            hits.append((start or date.min, r))
        hits.sort(key=lambda t: t[0], reverse=True)
        out = []
        for start, r in hits[:limit]:
            out.append(Precedent(reference=r["reference"], member_state=r.get("member_state", ""), code=r.get("code", ""),
                                 description=r.get("description", ""), reasoning=r.get("reasoning", ""),
                                 valid_from=parse_date(r.get("valid_from")), valid_to=parse_date(r.get("valid_to")),
                                 url=ruling_url(r["reference"]) if r.get("reference") else None, language=r.get("language", "")))
        return out

    def chunk_texts(self) -> list[tuple[str, str, dict]]:
        """(id, text, metadata) for embedding: description + reasoning only."""
        out = []
        for r in self.records:
            text = (r.get("description", "") + "\n" + r.get("reasoning", "")).strip()
            if not text:
                continue
            out.append((f"bti:{r['reference']}", text, {"code": r.get("code"), "cn_code": r.get("cn_code"), "chapter": r.get("chapter"),
                                                       "member_state": r.get("member_state"), "language": r.get("language"),
                                                       "valid_from": r.get("valid_from") or "", "valid_to": r.get("valid_to") or ""}))
        return out


# --------------------------------------------------------------------------- extract processing
def iter_extract(zip_path: Path | str, chapters: set[str] | None, today: date) -> Iterator[dict]:
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist()):
            if not name.lower().endswith(".csv"):
                continue
            with zf.open(name) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                for row in filter_rows(csv.DictReader(text), chapters, today):
                    yield row_to_ruling(row)


def write_jsonl(records: Iterable[dict], path: Path | str) -> int:
    n = 0
    with Path(path).open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def make_demo(records: list[dict], n: int = 200, seed: int = 7) -> list[dict]:
    """Sample about n rulings spread across chapters, preferring English/German descriptions."""
    rng = random.Random(seed)
    by_chapter: dict[str, list[dict]] = {}
    for r in records:
        by_chapter.setdefault(r.get("chapter", ""), []).append(r)
    per = max(1, n // max(1, len(by_chapter)))
    out: list[dict] = []
    for ch, items in sorted(by_chapter.items()):
        items = sorted(items, key=lambda r: ((r.get("language") or "").upper() not in ("EN", "DE"), r.get("valid_from") or ""), reverse=False)
        rng.shuffle(items)
        items.sort(key=lambda r: (r.get("language") or "").upper() not in ("EN", "DE"))
        out.extend(items[:per])
    return out[:n]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="EBTI extract → filtered rulings")
    ap.add_argument("--zip", default=str(DATA_DIR / "raw" / "DDS2-EBTI_Full.zip"))
    ap.add_argument("--chapters", default=",".join(TARGET_CHAPTERS))
    ap.add_argument("--out", default=str(DATA_DIR / "bti_subset.jsonl"))
    ap.add_argument("--make-demo", action="store_true", help="also write data/bti_demo.jsonl (~200 rulings)")
    ap.add_argument("--demo-size", type=int, default=200)
    args = ap.parse_args(argv)
    chapters = {c.strip() for c in args.chapters.split(",") if c.strip()}
    today = date.today()
    records = list(iter_extract(args.zip, chapters, today))
    n = write_jsonl(records, args.out)
    print(f"wrote {n} valid rulings for chapters {sorted(chapters)} to {args.out}")
    if args.make_demo:
        demo = make_demo(records, args.demo_size)
        m = write_jsonl(demo, DATA_DIR / "bti_demo.jsonl")
        print(f"wrote {m} demo rulings to {DATA_DIR / 'bti_demo.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
