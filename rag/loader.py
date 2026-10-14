"""Knowledge-base loader: download → parse → chunk → embed → persist, plus the runtime opener.

    python -m rag.loader --demo                 # nomenclature + rule lists + demo BTI, embeds ~5.6k chunks
    python -m rag.loader --bti-chapters 39,42,61-64,73,84,85,94,95,96   # full BTI subset (needs the 400 MB extract)

Idempotent: existing processed files and a complete Chroma collection are reused unless --force.
Writes data/SOURCES.md with provenance for every dataset (constitution: data and privacy).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from agent.config import DATA_DIR, RULES_DIR, STORE_DIR, Settings, get_settings
from agent.schemas import Usage
from rag import bti as bti_mod
from rag.nomenclature import NomenclatureIndex, build_chunks, parse_skos, write_jsonl
from rag.retriever import BM25Index, ChromaVectorSearch, HybridRetriever, load_index_meta, verify_index_meta, write_index_meta
from rag.rules import RuleSet

RAW_DIR = DATA_DIR / "raw"
NOMENCLATURE_JSONL = DATA_DIR / "nomenclature_2026.jsonl"
BTI_SUBSET = DATA_DIR / "bti_subset.jsonl"
BTI_DEMO = DATA_DIR / "bti_demo.jsonl"
SOURCES_MD = DATA_DIR / "SOURCES.md"

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
    if force and chroma_dir.exists():
        shutil.rmtree(chroma_dir)
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
        bt = ChromaVectorSearch(chroma_dir, emb, "bti")
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
    lines = ["# Data sources and provenance", "", f"Generated by `python -m rag.loader` on {today}.", "",
             "| Dataset | Version | Retrieved | Licence | URL |", "|---|---|---|---|---|"]
    for key, src in SOURCES.items():
        if key == "ebti" and demo:
            continue
        retrieved = today if (RAW_DIR / src["file"]).exists() else "(processed file reused)"
        lines.append(f"| {src['name']} | {src['version']} | {retrieved} | {src['licence']} | {src['url']} |")
    lines += ["", f"- Firm stop-word list: {rules.firm.source_doc} ({rules.firm.source_date}) — synthetic demo data.",
              "- Shipper history (`data/shippers.json`) and the sample packing list are synthetic demo data; no real companies.",
              f"- Embedding model `{meta.get('embedding_model')}`, dimension {meta.get('dimension')}, built {meta.get('built_at')}.",
              f"- Nomenclature chunks: {meta.get('nomenclature_chunks')}; BTI rulings in the document store: {meta.get('bti_rulings')}"
              + (" (demo subset)" if demo else "") + ".", "",
              "EU data reused under the Commission reuse policy (Decision 2011/833/EU, CC BY 4.0). Source: European Commission."]
    SOURCES_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"wrote {SOURCES_MD.name}")


# --------------------------------------------------------------------------- runtime opener
class KnowledgeBase:
    def __init__(self, index: NomenclatureIndex, retriever: HybridRetriever, bti: bti_mod.BTIStore, rules: RuleSet,
                 meta: dict[str, Any], embeddings: Any) -> None:
        self.index = index
        self.retriever = retriever
        self.bti = bti
        self.rules = rules
        self.meta = meta
        self.embeddings = embeddings

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
    return KnowledgeBase(index, retriever, bti_store, rules, meta, emb)


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
    ap = argparse.ArgumentParser(description="Build the CargoLint knowledge base")
    ap.add_argument("--demo", action="store_true", help="use data/bti_demo.jsonl instead of the full EBTI extract")
    ap.add_argument("--bti-chapters", default=",".join(bti_mod.TARGET_CHAPTERS))
    ap.add_argument("--chapters", default="all", help="nomenclature chapters to index (default: all)")
    ap.add_argument("--force", action="store_true", help="rebuild processed files and vectors")
    ap.add_argument("--no-embed", action="store_true", help="skip embedding (BM25 + metadata only)")
    args = ap.parse_args(argv)
    settings = get_settings()
    if not args.no_embed and not settings.api_key:
        print("OPENROUTER_API_KEY is not set; use --no-embed to build without vectors", file=sys.stderr)
        return 2
    index = build_nomenclature(force=args.force)
    if args.chapters != "all":
        keep = parse_chapters(args.chapters)
        index = NomenclatureIndex([c for c in index.chunks if c.metadata.get("chapter") in keep])
        log(f"nomenclature restricted to chapters {sorted(keep)}: {len(index)} chunks")
    rules = build_rules(force=args.force)
    bti_store = build_bti(args.demo, parse_chapters(args.bti_chapters), force=args.force)
    meta = build_indexes(index, bti_store, settings, force=args.force, embed=not args.no_embed)
    write_sources_md(meta, rules, args.demo)
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
