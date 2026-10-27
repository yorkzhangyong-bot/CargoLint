"""The demo knowledge base for a hosted deployment (feature 011): cut out of the local full build without any API call,
packed as one archive, and fetched by the app at its first start when the store is missing.

    python -m rag.demo_store --out <new folder> --rulings 5000 [--zip <archive>]

The archive holds store/… (index_meta.json, bm25.pkl, chroma/, chroma-bti/, bti_docs.jsonl) and data/taric.jsonl. The
fetch path imports only the standard library; chromadb and the ruling store load only when cutting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any

from agent.config import ROOT, STORE_DIR, TARIC_SNAPSHOT

EVAL_SET = ROOT / "tests" / "eval" / "cn8_eval_set.json"
SAMPLE_LINES = ROOT / "data" / "samples" / "sample_lines.json"   # the lines of sample_packing_list.xlsx and their codes
# The expected HS-6 of the two other sample files, which store no codes. Classified by hand on 2026-10-27 from the line
# texts in tests/fixtures/make_sample_variants.py. Each code exists in CN 2026 and, where its chapter is indexed, is the
# code most of the matching EBTI rulings of the full build carry. Chapters 82 and 91 are not indexed, so 8213.00 and
# 9113.90 add no ruling. Vague lines (accessories, samples, electrical parts, spare parts) have no expected code;
# "Electronic products" gets 8543.70, as in sample_lines.json.
SAMPLE_VARIANT_HS6 = {
    "sample_invoice_ningbo.csv": {
        "LED ceiling lights, 24 W": "9405.11",
        "USB chargers (dual port)": "8504.40",
        "Bluetooth speakers, portable": "8518.22",
        "塑料衣架 (plastic clothes hangers)": "3924.90",
        "Cotton canvas tote bags": "4202.92",
        "Electronic products": "8543.70",
        "Stainless steel kitchen scissors": "8213.00",
        "Silicone smart-watch straps": "9113.90",
    },
    "sample_packing_list_foshan.pdf": {
        "LED ceiling panel lights, 40 W, 600 x 600 mm": "9405.11",
        "Aluminium profiles for LED strips, 2 m": "9405.99",
        "Garden solar lamps, plastic housing": "9405.41",
        "Power banks 10000 mAh, lithium-ion": "8507.60",
        "Christmas decorations, plastic": "9505.10",
        "Lamp holders E27, phenolic resin": "8536.61",
    },
}
BTI_COLLECTION = "bti"
PREFERRED_SHARE = 0.5          # at most this share of the rulings comes from the preferred HS-6 codes
SEED = 2026
BATCH = 500                    # vectors read and written per Chroma call
META = "store/index_meta.json"  # unpacked last: its presence means a complete store


class DemoStoreError(RuntimeError):
    """The demo store cannot be cut, verified or unpacked."""


def _log(msg: str) -> None:
    print(f"[demo_store] {msg}", flush=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- the choice of rulings
def preferred_codes(eval_set: Path | str = EVAL_SET, sample_lines: Path | str = SAMPLE_LINES) -> set[str]:
    """The HS-6 codes whose rulings come first: those of the CN-8 eval set, and every code the sample files are expected
    to produce (sample_lines.json for the xlsx sample, SAMPLE_VARIANT_HS6 for the csv and pdf samples)."""
    codes = {r["hs6"] for r in json.loads(Path(eval_set).read_text(encoding="utf-8"))["rulings"]}
    codes |= {line["expected_top_code"] for line in json.loads(Path(sample_lines).read_text(encoding="utf-8"))["lines"]
              if line.get("expected_top_code")}
    return codes | {code for lines in SAMPLE_VARIANT_HS6.values() for code in lines.values()}


def _interleave(groups: list[list[dict]]) -> list[dict]:
    """One item from each group in turn, until every group is used up."""
    return [r for row in zip_longest(*groups) for r in row if r is not None]


def select_rulings(records: list[dict], preferred_hs6: set[str], n: int, seed: int = SEED) -> list[dict]:
    """About n rulings with an embedded text, sorted by reference (spec FR-002). Up to half of n come from the HS-6 codes
    in `preferred_hs6` (preferred_codes), one per code in turn, so each code gets the same number, or all it has if
    fewer. The rest are spread evenly over the
    chapters, one per HS-6 code in turn, the most common codes first; the preferred codes' remaining rulings come only
    after a chapter's other codes. The same records and seed always give the same choice."""
    from rag.bti import BTIStore

    embedded = {ruling_id for ruling_id, _, _ in BTIStore(records).chunk_texts()}
    by_code: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(records, key=lambda r: r["reference"]):
        if f"bti:{r['reference']}" in embedded:
            by_code[r.get("code") or ""].append(r)
    rng = random.Random(seed)
    for code in sorted(by_code):
        rng.shuffle(by_code[code])
    first = _interleave([by_code[c] for c in sorted(by_code) if c in preferred_hs6])[:int(n * PREFERRED_SHARE)]
    taken = {r["reference"] for r in first}
    left = {c: [r for r in rs if r["reference"] not in taken] for c, rs in by_code.items()}
    by_chapter: dict[str, list[str]] = defaultdict(list)
    for code, rs in left.items():
        if rs:
            by_chapter[rs[0].get("chapter") or ""].append(code)
    turns = []
    for chapter in sorted(by_chapter):
        codes = sorted(by_chapter[chapter], key=lambda c: (-len(left[c]), c))
        turns.append(_interleave([left[c] for c in codes if c not in preferred_hs6])
                     + _interleave([left[c] for c in codes if c in preferred_hs6]))
    rest = _interleave(turns)[:max(0, n - len(first))]
    return sorted(first + rest, key=lambda r: r["reference"])


# --------------------------------------------------------------------------- the cut
def _chroma(path: Path) -> Any:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    return chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))


def copy_vectors(source_dir: Path, target_dir: Path, ids: list[str]) -> set[str]:
    """Copies the vectors, texts and metadata of `ids` from the full ruling collection into a new one, created as
    langchain_chroma creates it (cosine space, no embedding function). Returns the ids found; makes no embedding call.
    Both clients are closed, which releases the database files."""
    found: set[str] = set()
    with _chroma(source_dir) as source_client, _chroma(target_dir) as target_client:
        source = source_client.get_collection(BTI_COLLECTION, embedding_function=None)
        target = target_client.get_or_create_collection(BTI_COLLECTION, embedding_function=None,
                                                        metadata={"hnsw:space": "cosine"})
        step = min(BATCH, target_client.get_max_batch_size())
        for i in range(0, len(ids), step):
            got = source.get(ids=ids[i:i + step], include=["embeddings", "documents", "metadatas"])
            if got["ids"]:
                target.add(ids=got["ids"], embeddings=got["embeddings"], documents=got["documents"],
                           metadatas=got["metadatas"])
                found.update(got["ids"])
    return found


def cut_demo_store(out: Path | str, rulings: int, *, store_dir: Path | str = STORE_DIR, bti_path: Path | str | None = None,
                   eval_set: Path | str = EVAL_SET, sample_lines: Path | str = SAMPLE_LINES,
                   taric: Path | str = TARIC_SNAPSHOT) -> dict[str, Any]:
    """Cuts a demo store into `out`, a new or empty folder, from the full build in `store_dir` (spec FR-001 … FR-004).
    It holds the nomenclature index and BM25 file copied unchanged, about `rulings` rulings with their existing
    vectors, an index_meta.json with the new count, and the TARIC snapshot. Makes no model or embedding call."""
    from rag.bti import write_jsonl
    from rag.loader import BTI_SUBSET
    from rag.retriever import load_index_meta, write_index_meta

    out, store_dir = Path(out), Path(store_dir)
    bti_path, eval_set, sample_lines, taric = Path(bti_path or BTI_SUBSET), Path(eval_set), Path(sample_lines), Path(taric)
    if out.exists() and any(out.iterdir()):
        raise DemoStoreError(f"{out} is not empty; give a new folder")
    missing = [str(p) for p in (store_dir / "index_meta.json", store_dir / "chroma", store_dir / "bm25.pkl",
                                store_dir / "chroma-bti", bti_path, eval_set, sample_lines, taric) if not p.exists()]
    if missing:
        raise DemoStoreError(f"the full build is incomplete, missing: {', '.join(missing)}")
    meta = load_index_meta(store_dir)
    preferred = preferred_codes(eval_set, sample_lines)
    with bti_path.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    chosen = select_rulings(records, preferred, rulings)
    target = out / "store"
    target.mkdir(parents=True)
    _log(f"copying the nomenclature index and BM25 from {store_dir}")
    shutil.copytree(store_dir / "chroma", target / "chroma")
    shutil.copy2(store_dir / "bm25.pkl", target / "bm25.pkl")
    _log(f"copying the vectors of {len(chosen)} rulings")
    found = copy_vectors(store_dir / "chroma-bti", target / "chroma-bti", [f"bti:{r['reference']}" for r in chosen])
    kept = [r for r in chosen if f"bti:{r['reference']}" in found]
    under_preferred = sum(r.get("code") in preferred for r in kept)
    write_jsonl(kept, target / "bti_docs.jsonl")
    write_index_meta(target, {**meta, "bti_rulings": len(kept), "demo_store": {
        "cut_at": datetime.now(timezone.utc).isoformat(), "rulings_requested": rulings,
        "under_preferred_codes": under_preferred, "source_bti_rulings": meta.get("bti_rulings")}})
    (out / "data").mkdir()
    shutil.copy2(taric, out / "data" / "taric.jsonl")
    return {"rulings": len(kept), "missing": len(chosen) - len(kept), "under_preferred_codes": under_preferred,
            "chapters": dict(sorted(Counter(r.get("chapter") for r in kept).items()))}


def pack(out: Path | str, archive: Path | str) -> tuple[str, int]:
    """Packs the demo store in `out` into one archive whose entries are store/… and data/taric.jsonl (spec FR-005).
    Returns its SHA-256 and its size in bytes."""
    out, archive = Path(out), Path(archive)
    files = sorted(p for p in (out / "store").rglob("*") if p.is_file()) + [out / "data" / "taric.jsonl"]
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(out).as_posix())
    return _sha256(archive), archive.stat().st_size


# --------------------------------------------------------------------------- the fetch at first start
def demo_store_needed(url: str, root: Path | None = None) -> bool:
    """True when a demo store URL is set and the store has no index_meta.json yet."""
    return bool(url) and not ((root or ROOT) / META).exists()


def fetch_demo_store(url: str, sha256: str, root: Path | None = None) -> None:
    """Downloads the demo archive to a temporary file, verifies its SHA-256 before anything is unpacked, and unpacks it
    into `root` (the repository root), store/index_meta.json last, so an interrupted start fetches again (spec FR-007,
    FR-008). Raises DemoStoreError and writes nothing when the archive is unreachable, unverified or not a demo store."""
    root = root or ROOT
    expected = sha256.strip().lower()
    if not expected:
        raise DemoStoreError("CARGOLINT_DEMO_STORE_SHA256 is not set, so the archive cannot be verified")
    with tempfile.TemporaryDirectory(prefix="cargolint-demo-") as tmp:
        archive = Path(tmp) / "demo-store.zip"
        try:
            with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as f:
                shutil.copyfileobj(response, f, 1 << 20)
        except OSError as exc:
            raise DemoStoreError(f"the archive could not be downloaded: {exc}") from exc
        digest = _sha256(archive)
        if digest != expected:
            raise DemoStoreError(f"the archive's SHA-256 is {digest}, not {expected} as set in CARGOLINT_DEMO_STORE_SHA256")
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            unexpected = [n for n in names if ".." in n.split("/") or not (n.startswith("store/") or n == "data/taric.jsonl")]
            if unexpected:
                raise DemoStoreError(f"the archive holds unexpected paths: {', '.join(unexpected[:3])}")
            if META not in names:
                raise DemoStoreError(f"the archive holds no {META}")
            for name in sorted(names, key=lambda n: n == META):
                z.extract(name, root)


# --------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Cut a demo knowledge base out of the local full build, with no API call")
    ap.add_argument("--out", required=True, type=Path, help="a new or empty folder for store/ and data/taric.jsonl")
    ap.add_argument("--rulings", type=int, default=5000, help="about this many rulings (default 5000)")
    ap.add_argument("--zip", type=Path, help="also pack the demo store into this archive and print its SHA-256 and size")
    args = ap.parse_args(argv)
    try:
        summary = cut_demo_store(args.out, args.rulings)
    except DemoStoreError as exc:
        print(f"demo store: {exc}", file=sys.stderr)
        return 2
    _log(f"{summary['rulings']} rulings ({summary['under_preferred_codes']} under the eval set's and the samples' HS-6 "
         f"codes), {summary['missing']} dropped without a vector; per chapter {summary['chapters']}")
    _log(f"wrote {args.out}")
    if args.zip:
        digest, size = pack(args.out, args.zip)
        print(f"wrote {args.zip} ({size / 1e6:.1f} MB)\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
