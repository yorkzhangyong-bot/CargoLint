"""Knowledge-base loader: download → parse → chunk → embed → persist, plus the runtime opener.

    python -m rag.loader --demo                 # nomenclature + rule lists + demo BTI, embeds ~5.6k chunks
    python -m rag.loader --bti-chapters 39,42,61-64,73,84,85,94,95,96   # full BTI subset (needs the 400 MB extract)
    python -m rag.loader --taric                # TARIC snapshot only (data/raw/taric/, needs gpg); no index is touched

Idempotent: existing processed files and a complete Chroma collection are reused unless --force.
Writes data/SOURCES.md with provenance for every dataset (constitution: data and privacy).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from agent.config import (DATA_DIR, ROOT, RULES_DIR, STORE_DIR, TARIC_KEY, TARIC_KEY_FINGERPRINT, TARIC_LOG_DIR, TARIC_RAW_DIR,
                          TARIC_SNAPSHOT, Settings, get_settings)
from agent.schemas import Usage
from rag import bti as bti_mod
from rag.nomenclature import NomenclatureIndex, build_chunks, parse_skos, write_jsonl
from rag.pgp import GpgNotFound, SignatureError, check_key_copy, find_gpg
from rag.retriever import BM25Index, ChromaVectorSearch, HybridRetriever, load_index_meta, verify_index_meta, write_index_meta
from rag.rules import RuleSet
from rag.taric import TaricFileError, TaricStore, open_taric_store, read_snapshot_header
from rag.taric_extract import ExtractError, discover_extract, load_extract, write_snapshot

RAW_DIR = DATA_DIR / "raw"
NOMENCLATURE_JSONL = DATA_DIR / "nomenclature_2026.jsonl"
BTI_SUBSET = DATA_DIR / "bti_subset.jsonl"
BTI_DEMO = DATA_DIR / "bti_demo.jsonl"
SOURCES_MD = DATA_DIR / "SOURCES.md"
SOURCES_TITLE = "# Data sources and provenance"
SOURCES_TABLE = ("| Dataset | Version | Retrieved | Licence | URL |", "|---|---|---|---|---|")

SOURCES: dict[str, dict[str, str]] = {
    "cn2026": {
        "name": "EU Combined Nomenclature 2026 (SKOS RDF/XML, Publications Office / Eurostat)",
        "url": ("https://op.europa.eu/o/opportal-service/euvoc-download-handler?cellarURI=http%3A%2F%2Fpublications.europa.eu"
                "%2Fresource%2Fcellar%2F79c210b8-c4a3-11f0-8da2-01aa75ed71a1.0001.02%2FDOC_1&fileName=ESTAT-CN2026.rdf"),
        "file": "ESTAT-CN2026.rdf",
        "licence": "CC BY 4.0 (Commission Decision 2011/833/EU); Regulation (EU) 2025/1926, Annex I",
        "version": "CN 2026 (issued 2025-11-19, updated 2026-02-18)",
    },
    "ebti": {
        "name": "EBTI – European Binding Tariff Information, full public extract",
        "url": "https://ec.europa.eu/taxation_customs/dds2/ebti/ebti_export_management.jsp?message=extractFull",
        "file": "DDS2-EBTI_Full.zip",
        "licence": "CC BY 4.0 (Commission Decision 2011/833/EU); holder names and addresses are dropped at load time",
        "version": "daily extract",
    },
    "ics2_guidance": {
        "name": "DG TAXUD guidance on acceptable and unacceptable terms for the description of goods, v4.10",
        "url": ("https://taxation-customs.ec.europa.eu/document/download/ea68a0c7-a2d3-4bc1-9bed-ebc149c920f0_en"
                "?filename=guidance_acceptable_goods_description_en.pdf"),
        "file": "ics2_guidance_v4.10.pdf",
        "licence": "European Commission document, reuse permitted with acknowledgement",
        "version": "v4.10, 2021-03-04 (TAXUD b.1(2021)1688480)",
    },
    "ics2_stop_words": {
        "name": "Introduction of Stop Words/Phrases in the Common Repository (ICS2, CIRCABC)",
        "url": "https://circabc.europa.eu/rest/download/e9bb2d8d-c5a5-4997-a78b-f444fbf424ff",
        "file": "ics2_stop_words.pdf",
        "licence": "European Commission document, reuse permitted with acknowledgement",
        "version": "version in force 2026-08-03",
    },
    "taric": {   # version and retrieval date come from the snapshot record, see taric_sources_row
        "name": "EU TARIC snapshot (Swedish Customs Tariff File Distribution, tot extract)",
        "url": "https://distr.tullverket.se/tulltaxan/",
        "licence": ("Swedish Customs Tariff File Distribution, free of charge, no formal licence published; Swedish Customs "
                    "provides the files without support; underlying data is EU TARIC from the European Commission."),
    },
}


def log(msg: str) -> None:
    print(f"[loader] {msg}", flush=True)


# --------------------------------------------------------------------------- download
def download(url: str, dest: Path, resume: bool = True, timeout: int = 120) -> Path:
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not dest.with_suffix(dest.suffix + ".part").exists():
        log(f"have {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": "CargoLint/0.1 (+knowledge-base loader)"}
    mode = "wb"
    if resume and part.exists():
        headers["Range"] = f"bytes={part.stat().st_size}-"
        mode = "ab"
    log(f"downloading {dest.name} …")
    with requests.get(url, stream=True, allow_redirects=True, timeout=timeout, headers=headers) as r:
        if r.status_code == 416:
            part.rename(dest)
            return dest
        if r.status_code == 200 and mode == "ab":
            mode = "wb"  # server ignored the range
        r.raise_for_status()
        done = 0
        with part.open(mode) as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
    part.rename(dest)
    log(f"saved {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


# --------------------------------------------------------------------------- build steps
def build_nomenclature(force: bool = False) -> NomenclatureIndex:
    if NOMENCLATURE_JSONL.exists() and not force:
        idx = NomenclatureIndex.from_jsonl(NOMENCLATURE_JSONL)
        log(f"nomenclature: {len(idx)} HS-6 chunks from {NOMENCLATURE_JSONL.name}")
        return idx
    src = SOURCES["cn2026"]
    rdf = download(src["url"], RAW_DIR / src["file"])
    t0 = time.time()
    chunks = build_chunks(parse_skos(rdf), source=src["name"], edition_year=2026)
    n = write_jsonl(chunks, NOMENCLATURE_JSONL)
    log(f"nomenclature: parsed {n} HS-6 chunks in {time.time() - t0:.0f}s → {NOMENCLATURE_JSONL.name}")
    return NomenclatureIndex(chunks)


def build_rules(force: bool = False) -> RuleSet:
    from rag import rules as rules_mod

    targets = {"ics2_guidance": RULES_DIR / "ics2_unacceptable_terms.json", "ics2_stop_words": RULES_DIR / "ics2_stop_words.json"}
    for key, out in targets.items():
        if out.exists() and not force:
            continue
        src = SOURCES[key]
        try:
            pdf = download(src["url"], RAW_DIR / src["file"])
        except Exception as exc:  # noqa: BLE001 - a missing PDF must not stop the build
            log(f"WARNING: could not download {src['file']}: {exc}")
            continue
        extractor = getattr(rules_mod, "extract_ics2_guidance" if key == "ics2_guidance" else "extract_ics2_stop_words", None)
        if extractor is None:
            log(f"WARNING: no extractor for {key}; skipping")
            continue
        n = extractor(pdf, out)
        log(f"rules: {out.name} ← {n} terms from {pdf.name}")
    rs = RuleSet.load(RULES_DIR)
    facts = rs.caption_facts()
    log(f"rules: firm {facts['firm_terms']} terms, ICS2 {facts['ics2_terms']} terms in {len(rs.ics2_lists)} lists")
    return rs


def build_bti(demo: bool, chapters: set[str], force: bool = False) -> bti_mod.BTIStore:
    if demo:
        if not BTI_DEMO.exists():
            log(f"WARNING: {BTI_DEMO.name} missing — run `python -m rag.bti --make-demo` after downloading the extract; "
                "continuing with an empty ruling store")
        store = bti_mod.BTIStore.from_jsonl(BTI_DEMO)
    else:
        if not BTI_SUBSET.exists() or force:
            src = SOURCES["ebti"]
            zip_path = download(src["url"], RAW_DIR / src["file"])
            records = list(bti_mod.iter_extract(zip_path, chapters, date.today()))
            bti_mod.write_jsonl(records, BTI_SUBSET)
            log(f"bti: {len(records)} valid rulings for chapters {sorted(chapters)} → {BTI_SUBSET.name}")
        store = bti_mod.BTIStore.from_jsonl(BTI_SUBSET)
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    bti_mod.write_jsonl(store.records, STORE_DIR / "bti_docs.jsonl")
    log(f"bti: {len(store)} rulings in the document store")
    return store


def build_indexes(index: NomenclatureIndex, bti_store: bti_mod.BTIStore, settings: Settings, force: bool = False,
                  embed: bool = True) -> dict[str, Any]:
    from rag.embeddings import OpenRouterEmbeddings

    STORE_DIR.mkdir(parents=True, exist_ok=True)
    usage = Usage()
    bm25 = BM25Index([(c.id, c.text) for c in index.chunks])
    bm25.save(STORE_DIR / "bm25.pkl")
    log(f"bm25: {len(index.chunks)} chunks → bm25.pkl")
    meta: dict[str, Any] = {"embedding_model": settings.embed_model, "dimension": None, "built_at": datetime.now(timezone.utc).isoformat(),
                            "nomenclature_chunks": len(index.chunks), "bti_rulings": len(bti_store), "edition_year": index.edition_year}
    if not embed:
        write_index_meta(STORE_DIR, meta)
        return meta
    emb = OpenRouterEmbeddings(settings=settings, usage_sink=usage.add)
    chroma_dir = STORE_DIR / "chroma"
    bti_dir = STORE_DIR / "chroma-bti"   # the rulings index is large and rebuilt on its own; the app keeps reading store/chroma meanwhile
    if force:
        for d in (chroma_dir, bti_dir):
            if d.exists():
                shutil.rmtree(d)
    cn = ChromaVectorSearch(chroma_dir, emb, "cn2026")
    docs = [(c.id, c.text, {k: v for k, v in c.metadata.items() if k in ("chapter", "heading", "subheading", "language", "edition_year")})
            for c in index.chunks]
    if cn.count() >= len(docs):
        log(f"chroma cn2026: already has {cn.count()} vectors, skipping")
    else:
        t0 = time.time()
        n = cn.add(docs)
        log(f"chroma cn2026: embedded {n} chunks in {time.time() - t0:.0f}s")
    bti_docs = bti_store.chunk_texts()
    if bti_docs:
        bt = ChromaVectorSearch(bti_dir, emb, "bti")
        if bt.count() >= len(bti_docs):
            log(f"chroma bti: already has {bt.count()} vectors, skipping")
        else:
            t0 = time.time()
            n = bt.add(bti_docs)
            log(f"chroma bti: embedded {n} rulings in {time.time() - t0:.0f}s")
    meta["dimension"] = emb.dimension or meta["dimension"]
    if meta["dimension"] is None:
        meta["dimension"] = len(emb.embed_query("dimension probe"))
    meta["embedding_usage"] = usage.model_dump()
    write_index_meta(STORE_DIR, meta)
    log(f"index_meta: model {meta['embedding_model']}, dim {meta['dimension']}, cost ${usage.cost_usd:.3f}")
    return meta


def write_sources_md(meta: dict[str, Any], rules: RuleSet, demo: bool) -> None:
    today = date.today().isoformat()
    lines = [SOURCES_TITLE, "", f"Generated by `python -m rag.loader` on {today}.", "", *SOURCES_TABLE]
    for key, src in SOURCES.items():
        if key == "taric" or (key == "ebti" and demo):
            continue
        raw_file = RAW_DIR / src["file"]
        retrieved = date.fromtimestamp(raw_file.stat().st_mtime).isoformat() if raw_file.exists() else "(processed file reused)"
        lines.append(f"| {src['name']} | {src['version']} | {retrieved} | {src['licence']} | {src['url']} |")
    try:
        taric = read_snapshot_header(TARIC_SNAPSHOT)
    except TaricFileError as exc:
        log(f"WARNING: no TARIC row in {SOURCES_MD.name}: {exc}")
        taric = None
    if taric:
        lines.append(taric_sources_row(taric, TARIC_RAW_DIR))
    lines += ["", f"- Firm stop-word list: {rules.firm.source_doc} ({rules.firm.source_date}) — synthetic demo data.",
              "- Shipper history (`data/shippers.json`) and the sample packing list are synthetic demo data; no real companies.",
              f"- Embedding model `{meta.get('embedding_model')}`, dimension {meta.get('dimension')}, built {meta.get('built_at')}.",
              f"- Nomenclature chunks: {meta.get('nomenclature_chunks')}; BTI rulings in the document store: {meta.get('bti_rulings')}"
              + (" (demo subset)" if demo else "") + ".", "",
              "EU data reused under the Commission reuse policy (Decision 2011/833/EU, CC BY 4.0). Source: European Commission."]
    SOURCES_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    log(f"wrote {SOURCES_MD.name}")


# --------------------------------------------------------------------------- TARIC snapshot (feature 002)
def taric_sources_row(header: dict[str, Any], folder: Path) -> str:
    """The register row for a TARIC snapshot record; retrieved = the newest of its six signed files in `folder` (FR-025)."""
    src = SOURCES["taric"]
    mtimes = [(folder / name).stat().st_mtime for name in header["source_files"] if (folder / name).exists()]
    retrieved = date.fromtimestamp(max(mtimes)).isoformat() if mtimes else "(processed file reused)"
    version = f"snapshot {header['snapshot_date']}, batch {header['batch_id']}"
    return f"| {src['name']} | {version} | {retrieved} | {src['licence']} | {src['url']} |"


def _register_with_taric_row(row: str) -> str:
    """data/SOURCES.md with its TARIC row replaced, or inserted at the end of the table; a minimal register when absent."""
    if not SOURCES_MD.exists():
        return "\n".join([SOURCES_TITLE, "", *SOURCES_TABLE, row]) + "\n"
    lines = SOURCES_MD.read_text(encoding="utf-8").splitlines()
    at = next((i for i, line in enumerate(lines) if line.startswith(f"| {SOURCES['taric']['name']} |")), None)
    if at is not None:
        lines[at] = row
    elif SOURCES_TABLE[1] in lines:
        end = lines.index(SOURCES_TABLE[1]) + 1
        while end < len(lines) and lines[end].startswith("|"):
            end += 1
        lines.insert(end, row)
    else:
        lines += ["", *SOURCES_TABLE, row]
    return "\n".join(lines) + "\n"


def _shown(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def load_taric(folder: Path, force: bool = False) -> int:
    """`--taric`: verify, parse and write the TARIC snapshot only (contracts/loader-cli.md); never builds or reads a
    search index or the index metadata (FR-022, FR-023, FR-025). Exit 0 written or skipped, 1 refused, 2 setup error."""
    t0 = time.time()
    try:
        find_gpg()
        if not TARIC_KEY.exists():
            raise FileNotFoundError(f"the key copy {_shown(TARIC_KEY)} is missing")
        check_key_copy(TARIC_KEY, TARIC_KEY_FINGERPRINT)
        cn2026_cn8 = NomenclatureIndex.from_jsonl(NOMENCLATURE_JSONL).cn8_codes()
    except (GpgNotFound, SignatureError, OSError) as exc:
        print(f"TARIC load not started: {exc}. Nothing was read or written.", file=sys.stderr)
        return 2
    try:
        extract = discover_extract(folder)
    except ExtractError as exc:
        print(f"TARIC load refused: {exc}. Nothing was written.", file=sys.stderr)
        return 1
    try:
        previous = read_snapshot_header(TARIC_SNAPSHOT)
    except TaricFileError as exc:                                     # an older format or a broken file: never a skip
        log(f"taric: {_shown(TARIC_SNAPSHOT)} will be rewritten: {exc}")
        previous = {"snapshot_date": "(older format or unreadable)"}
    if previous and previous["snapshot_date"] == extract.snapshot_date.isoformat() and not force:   # FR-014
        print(f"TARIC snapshot {previous['snapshot_date']} is already loaded in {_shown(TARIC_SNAPSHOT)}; nothing changed. "
              "Use --force to rewrite it.")
        return 0
    try:
        log(f"taric: verifying and parsing the {len(extract.files)} files of batch {extract.batch_id} …")
        snapshot = load_extract(extract, TARIC_KEY, TARIC_KEY_FINGERPRINT, cn2026_cn8, TARIC_LOG_DIR)
    except ExtractError as exc:
        print(f"TARIC load refused: {exc}. Nothing was written.", file=sys.stderr)
        return 1
    log(f"taric: parsed in {time.time() - t0:.0f} s; {len(snapshot.areas)} EU geographical areas")
    for reason, n in snapshot.dropped.items():
        log(f"taric: dropped {n:,} measure{'' if n == 1 else 's'} ({reason})")
    register_tmp = SOURCES_MD.with_name(SOURCES_MD.name + ".tmp")   # built from the new record before the swap (FR-013)
    register_tmp.write_text(_register_with_taric_row(taric_sources_row(asdict(snapshot.header), folder)), encoding="utf-8",
                            newline="\n")
    try:
        write_snapshot(snapshot, TARIC_SNAPSHOT)
    except BaseException:
        register_tmp.unlink(missing_ok=True)
        raise
    os.replace(register_tmp, SOURCES_MD)
    h = snapshot.header
    declarable = sum(c.declarable for c in snapshot.codes)
    print(f"TARIC snapshot {h.snapshot_date} · batch {h.batch_id} · export {h.export_id}")
    print(f"{len(h.source_files)} files verified with key {TARIC_KEY_FINGERPRINT}: {', '.join(h.source_files)}")
    print(f"code records {h.goods_records:,} ({declarable:,} declarable) · measure records {h.measure_records:,}")
    print(f"area names {sum(1 for a in snapshot.areas if a.name):,} · "                      # feature 003, FR-004
          f"group memberships {sum(len(a.member_of) for a in snapshot.areas):,} · "
          f"measures with excluded areas {sum(1 for m in snapshot.measures if m.excluded_areas):,}")
    print(f"CN-8 mismatches {h.cn8_mismatches:,} → {_shown(snapshot.log_path)}")
    print(f"replaced snapshot {previous['snapshot_date']}" if previous else "new snapshot")
    print(f"wrote {_shown(TARIC_SNAPSHOT)} ({TARIC_SNAPSHOT.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f} s")
    return 0


# --------------------------------------------------------------------------- runtime opener
class KnowledgeBase:
    def __init__(self, index: NomenclatureIndex, retriever: HybridRetriever, bti: bti_mod.BTIStore, rules: RuleSet,
                 meta: dict[str, Any], embeddings: Any, shippers: list | None = None, bti_vectors: Any = None,
                 taric: TaricStore | None = None) -> None:
        self.bti_vectors = bti_vectors  # Chroma collection of ruling texts for precedent-driven retrieval; None when empty
        self.index = index
        self.retriever = retriever
        self.bti = bti
        self.rules = rules
        self.meta = meta
        self.embeddings = embeddings
        self.shippers = shippers if shippers is not None else []
        self.taric = taric              # TARIC snapshot for digits 9-10 and measures; None when not loaded (FR-024)

    @property
    def updated(self) -> str:
        built = self.meta.get("built_at") or ""
        return built[:10]


def open_knowledge_base(settings: Settings | None = None, usage_sink: Any = None) -> KnowledgeBase:
    """Open the persisted knowledge base for the app; refuses an index built with another embedding model."""
    from rag.embeddings import OpenRouterEmbeddings

    settings = settings or get_settings()
    meta = load_index_meta(STORE_DIR)
    verify_index_meta(meta, expected_model=settings.embed_model)
    index = NomenclatureIndex.from_jsonl(NOMENCLATURE_JSONL)
    emb = OpenRouterEmbeddings(settings=settings, usage_sink=usage_sink)
    vectors = ChromaVectorSearch(STORE_DIR / "chroma", emb, "cn2026")
    bm25 = BM25Index.load(STORE_DIR / "bm25.pkl")
    retriever = HybridRetriever(bm25=bm25, vectors=vectors, chunks=index)
    bti_store = bti_mod.BTIStore.from_jsonl(STORE_DIR / "bti_docs.jsonl")
    rules = RuleSet.load(RULES_DIR)
    bti_vectors = ChromaVectorSearch(STORE_DIR / "chroma-bti", emb, "bti") if (STORE_DIR / "chroma-bti").exists() else None
    if bti_vectors is not None and bti_vectors.count() == 0:
        bti_vectors = None
    from rag.rules import load_shippers

    return KnowledgeBase(index, retriever, bti_store, rules, meta, emb, shippers=load_shippers(), bti_vectors=bti_vectors,
                         taric=open_taric_store(TARIC_SNAPSHOT))


# --------------------------------------------------------------------------- CLI
def parse_chapters(spec: str) -> set[str]:
    out: set[str] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(f"{i:02d}" for i in range(int(a), int(b) + 1))
        else:
            out.add(f"{int(part):02d}")
    return out


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # progress lines contain arrows; a redirected Windows console defaults to cp1252
    ap = argparse.ArgumentParser(description="Build the CargoLint knowledge base")
    ap.add_argument("--demo", action="store_true", help="use data/bti_demo.jsonl instead of the full EBTI extract")
    ap.add_argument("--bti-chapters", default=None)
    ap.add_argument("--chapters", default=None, help="nomenclature chapters to index (default: all)")
    ap.add_argument("--force", action="store_true", help="rebuild processed files and vectors; with --taric, rewrite data/taric.jsonl")
    ap.add_argument("--no-embed", action="store_true", help="skip embedding (BM25 + metadata only)")
    ap.add_argument("--taric", nargs="?", const=str(TARIC_RAW_DIR), metavar="DIR",
                    help="load only the TARIC snapshot from DIR (default: data/raw/taric/)")
    args = ap.parse_args(argv)
    if args.taric is not None:
        clash = [opt for opt, used in (("--demo", args.demo), ("--chapters", args.chapters is not None),
                                       ("--bti-chapters", args.bti_chapters is not None), ("--no-embed", args.no_embed)) if used]
        if clash:
            print(f"--taric cannot be combined with {', '.join(clash)}", file=sys.stderr)
            return 2
        return load_taric(Path(args.taric), force=args.force)
    settings = get_settings()
    if not args.no_embed and not settings.api_key:
        print("OPENROUTER_API_KEY is not set; use --no-embed to build without vectors", file=sys.stderr)
        return 2
    index = build_nomenclature(force=args.force)
    if args.chapters not in (None, "all"):
        keep = parse_chapters(args.chapters)
        index = NomenclatureIndex([c for c in index.chunks if c.metadata.get("chapter") in keep])
        log(f"nomenclature restricted to chapters {sorted(keep)}: {len(index)} chunks")
    rules = build_rules(force=args.force)
    bti_store = build_bti(args.demo, parse_chapters(args.bti_chapters or ",".join(bti_mod.TARGET_CHAPTERS)), force=args.force)
    meta = build_indexes(index, bti_store, settings, force=args.force, embed=not args.no_embed)
    write_sources_md(meta, rules, args.demo)
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
