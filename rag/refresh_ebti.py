"""The EBTI refresh (feature 013, User Story 2): `python scripts/refresh_ebti.py [--rulings N|all] [--out DIR]
[--previous RELEASE|DIR] [--full-embed] [--extract ZIP] [--force] [--no-publish] [--repo OWNER/NAME]`.

It downloads the current EBTI full extract afresh into the work area under build/ (never the loader's data/raw/ copy),
reads the extract's date, takes the previous store (the newest complete EBTI release, `demo-store-v1`, or a folder),
chooses the configured number of rulings with the demo store's rule (the previous store's rulings first; `all` keeps
every valid ruling), copies the vectors of the unchanged rulings with their metadata rewritten from the new extract,
embeds only the new and changed ones, copies the nomenclature index, writes the store in the layout of demo-store-v1
into a work folder, packs `store/…`, publishes `ebti-<date>` with its metadata, marks it the latest release and keeps
the two newest complete EBTI releases. `--full-embed` embeds everything afresh (a change of embedding model). The
repository's store/, data/bti_subset.jsonl and data/raw/ are never touched (contracts/refresh-cli.md).
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import rag.loader as loader_mod
from agent.config import ROOT, Settings, get_settings
from agent.schemas import Usage
from rag import bti as bti_mod
from rag import demo_store, refresh
from rag.embeddings import get_embeddings
from rag.nomenclature import NomenclatureIndex
from rag.refresh import (GhError, RefreshError, ReleaseService, current_block, pack_entries, prune, publish, read_metadata,
                         repair_latest, sha256, write_metadata)
from rag.retriever import load_index_meta, write_index_meta

KIND = "ebti"
EXTRACT_URL = loader_mod.SOURCES["ebti"]["url"]
WORK_DIR = ROOT / "build"                            # the work area: the extract and the work folders (git-ignored)
EXTRACT_ZIP = WORK_DIR / "DDS2-EBTI_Full.zip"        # the refresh's own download, never the loader's data/raw/ copy
DEFAULT_RULINGS = 5000                               # the settings' default (CARGOLINT_EBTI_RULINGS); `all`: no bound
LAYOUT = ("index_meta.json", "bm25.pkl", "chroma", "chroma-bti", "bti_docs.jsonl")
LABELS = {1: "EBTI refresh refused", 2: "EBTI refresh not started", 3: "EBTI refresh failed"}


@dataclass
class Partition:
    """The chosen rulings split by where their vector comes from (spec FR-008)."""

    reuse: list[tuple[str, str, dict]]      # (id, text, metadata from the new record): the previous vector is copied
    embed: list[tuple[str, str, dict]]      # (id, text, metadata): new, or changed in its text: embedded
    dropped: int                            # previous rulings not in the new store: expired, withdrawn or displaced


# --------------------------------------------------------------------------- the pieces
def rulings_bound(value: str | int | None) -> int | None:
    """`CARGOLINT_EBTI_RULINGS` or `--rulings`: a positive integer, or `all` (None, no bound); else a setup error."""
    text = str(DEFAULT_RULINGS if value is None else value).strip().lower()
    if text == "all":
        return None
    if re.fullmatch(r"[0-9]+", text) and int(text) > 0:
        return int(text)
    raise RefreshError(f"the ruling count must be a positive integer or all, not {value!r}", exit_code=2)


def download_extract(dest: Path | None = None) -> Path:
    """The extract afresh: the file and its .part are removed first, since the loader's download reuses a file and
    resumes a .part, and the extract is regenerated daily under one name (research R-10)."""
    dest = Path(dest or EXTRACT_ZIP)
    dest.parent.mkdir(parents=True, exist_ok=True)
    for stale in (dest, dest.with_suffix(dest.suffix + ".part")):
        stale.unlink(missing_ok=True)
    return loader_mod.download(EXTRACT_URL, dest)


def extract_date(zip_path: Path | str) -> date:
    """The extract's snapshot date (research R-02); an extract without a dated csv entry is refused (exit 1)."""
    try:
        found = bti_mod.extract_date(zip_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise RefreshError(f"the extract {zip_path} cannot be read: {exc}", exit_code=1) from exc
    if found is None:
        raise RefreshError(f"the extract {zip_path} holds no csv entry, so its date cannot be read", exit_code=1)
    return found


def previous_docs(store_dir: Path) -> dict[str, dict]:
    """The previous store's rulings by reference (its bti_docs.jsonl)."""
    return {r["reference"]: r for r in bti_mod.BTIStore.from_jsonl(Path(store_dir) / "bti_docs.jsonl").records if r.get("reference")}


def check_previous(store_dir: Path, settings: Settings, index: NomenclatureIndex) -> dict[str, Any]:
    """The previous store must have the layout, the settings' embedding model and the committed nomenclature's index
    (chunk count and edition), else exit 2 naming --full-embed; all before any embedding call."""
    store_dir = Path(store_dir)
    missing = [name for name in LAYOUT if not (store_dir / name).exists()]
    if missing:
        raise RefreshError(f"the previous store {store_dir} is incomplete: it lacks {', '.join(missing)}", exit_code=2)
    meta = load_index_meta(store_dir)
    model = meta.get("embedding_model")
    if model != settings.embed_model:
        raise RefreshError(f"the previous store was built with the embedding model {model!r}, not {settings.embed_model!r}, "
                           "so its vectors cannot be reused: embed everything afresh with --full-embed", exit_code=2)
    chunks, year = meta.get("nomenclature_chunks"), meta.get("edition_year")
    if chunks != len(index.chunks) or year != index.edition_year:      # chunks, as build_indexes counts them
        raise RefreshError(f"the previous store's nomenclature index ({chunks} chunks, edition {year}) does not match the "
                           f"committed nomenclature ({len(index.chunks)} chunks, edition {index.edition_year}): rebuild it "
                           "with --full-embed", exit_code=2)
    return meta


def partition(chosen: list[dict], previous: dict[str, dict]) -> Partition:
    """A chosen ruling whose text equals the previous store's record reuses its vector, with the metadata built from
    the new record (a changed code or validity is served); the others are embedded; the previous rulings not chosen
    are dropped."""
    reuse: list[tuple[str, str, dict]] = []
    embed: list[tuple[str, str, dict]] = []
    chosen_refs: set[str] = set()
    for ruling_id, text, meta in bti_mod.BTIStore(chosen).chunk_texts():
        ref = ruling_id[len("bti:"):]
        chosen_refs.add(ref)
        old = previous.get(ref)
        if old is not None and bti_mod.ruling_text(old) == text:
            reuse.append((ruling_id, text, {**meta, "id": ruling_id}))   # "id" as ChromaVectorSearch.add writes it
        else:
            embed.append((ruling_id, text, meta))
    return Partition(reuse, embed, sum(1 for ref in previous if ref not in chosen_refs))


def build_store(store: Path, chosen: list[dict], part: Partition, emb: Any, *, previous_dir: Path | None,
                previous_meta: dict[str, Any] | None, full_embed: bool, index: NomenclatureIndex,
                settings: Settings) -> tuple[dict[str, Any], int, int]:
    """The store in `store` (the layout of demo-store-v1). Reuse: the nomenclature index and BM25 file copied, the
    reused rulings' vectors copied with their new metadata, the rest embedded. --full-embed: the loader's own build
    against the work folder with the given embeddings. Returns the index fields and the counts reused and embedded."""
    if full_embed:
        meta = loader_mod.build_indexes(index, bti_mod.BTIStore(chosen), settings, force=True, embed=True,
                                        store_dir=store, embeddings=emb)
        meta = {k: meta.get(k) for k in ("embedding_model", "dimension", "nomenclature_chunks", "edition_year")}
        reused, embedded = 0, len(part.reuse) + len(part.embed)
    else:
        assert previous_dir is not None and previous_meta is not None
        store.mkdir(parents=True, exist_ok=True)
        shutil.copytree(previous_dir / "chroma", store / "chroma")
        shutil.copy2(previous_dir / "bm25.pkl", store / "bm25.pkl")
        found: set[str] = set()
        if part.reuse:
            found = demo_store.copy_vectors(previous_dir / "chroma-bti", store / "chroma-bti",
                                            [ruling_id for ruling_id, _, _ in part.reuse],
                                            metadatas={ruling_id: meta for ruling_id, _, meta in part.reuse})
        to_embed = part.embed + [(i, t, {k: v for k, v in m.items() if k != "id"}) for i, t, m in part.reuse if i not in found]
        if to_embed:   # through the same client as copy_vectors: chromadb allows one client setting per path in a process
            demo_store.add_vectors(store / "chroma-bti", to_embed, emb)
        reused, embedded = len(found), len(to_embed)
        meta = {k: previous_meta.get(k) for k in ("embedding_model", "dimension", "nomenclature_chunks", "edition_year")}
    bti_mod.write_jsonl(chosen, store / "bti_docs.jsonl")
    return meta, reused, embedded


# --------------------------------------------------------------------------- the previous store
def _listing(service: Any) -> list[dict]:
    try:
        return service.list()
    except GhError as exc:
        raise RefreshError(f"the release listing failed: {exc}", exit_code=2) from exc


def _download_previous(service: Any, tag: str, work: Path) -> Path:
    """A release's archive into <work>/previous/, verified against its metadata when it has one (demo-store-v1 has
    none: unpacked as it is, with a note); only its store/… entries are unpacked."""
    if service is None:
        raise RefreshError(f"the previous store {tag} is a release, which needs gh", exit_code=2)
    target = work / "previous"
    try:
        service.download(tag, "*", target)
    except GhError as exc:
        raise RefreshError(f"the previous store {tag} could not be downloaded: {exc}", exit_code=2) from exc
    archives = sorted(target.glob("*.zip"))
    if not archives:
        raise RefreshError(f"the previous store {tag} holds no archive", exit_code=2)
    archive = archives[0]
    metadata = target / refresh.METADATA
    if metadata.exists():
        try:
            fields = read_metadata(metadata)
        except RefreshError as exc:
            raise RefreshError(f"the previous store {tag}: {exc}", exit_code=2) from exc
        if fields.get("archive") != archive.name or sha256(archive) != str(fields.get("sha256", "")).lower():
            raise RefreshError(f"the previous store {tag}: the archive's SHA-256 does not match its metadata", exit_code=2)
    else:
        refresh.log(f"previous store {tag} has no metadata.json: its archive {archive.name} is unpacked unverified")
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.startswith("store/") and ".." not in name.split("/"):
                z.extract(name, target)
    return target / "store"


def previous_store(spec: str | None, service: Any, work: Path, listing: list[dict] | None = None) -> tuple[Path | None, str]:
    """The previous store's store/ folder and its label: a local folder (`--previous DIR`, holding store/ or being it),
    a release downloaded into <work>/previous/ (`--previous RELEASE`, which needs gh also with --no-publish), or the
    newest complete EBTI release of the listing; (None, "none") when there is none."""
    if spec:
        local = Path(spec)
        if local.is_dir():
            store = local / "store" if (local / "store").is_dir() else local
            return store, "folder"
        return _download_previous(service, spec, work), spec
    if service is None:
        return None, "none"
    complete = refresh.names_of_kind(listing if listing is not None else _listing(service), KIND, complete_only=True)
    if not complete:
        return None, "none"
    return _download_previous(service, complete[0], work), complete[0]


# --------------------------------------------------------------------------- the command
def _shown(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _nothing_new(service: Any, listing: list[dict], newest: str) -> int:
    deleted = prune(service, KIND, listing=listing)
    if deleted:
        refresh.log(f"deleted {', '.join(deleted)}")
    remarked = repair_latest(service, KIND, listing=listing)
    if remarked:
        refresh.log(f"marked {remarked} latest")
    print(f"EBTI refresh: {newest} is already published and complete; nothing new. Use --force to rebuild and replace it.")
    return 0


def _work_folder(out: Path | None, name: str, force: bool) -> Path:
    """`--out` must be new or empty; the default work folder is emptied by --force, a given folder never."""
    folder = Path(out) if out else WORK_DIR / name
    if folder.exists() and any(folder.iterdir()):
        if out is None and force:
            shutil.rmtree(folder)
        elif out is None:
            raise RefreshError(f"the work folder {_shown(folder)} is not empty, left from an earlier run: use --force to "
                               "empty it, or --out to build in another folder", exit_code=2)
        else:
            raise RefreshError(f"{_shown(folder)} is not empty: --out must name a new or empty folder", exit_code=2)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _notes(name: str, counts: dict[str, Any], size: int) -> str:
    return (f"EBTI rulings of the full extract of {name[len(KIND) + 1:]}: {counts['rulings']:,} rulings in the store "
            f"({counts['reused']:,} vectors reused, {counts['embedded']:,} embedded, {counts['dropped']:,} dropped from "
            f"{counts['vectors_from']}); archive {size / 1e6:.1f} MB. Published by scripts/refresh_ebti.py (feature 013).")


def _run(args: argparse.Namespace, embeddings: Any, service: Any, t0: float) -> int:
    try:
        settings = get_settings()
    except ValueError as exc:
        raise RefreshError(str(exc), exit_code=2) from exc
    bound = rulings_bound(args.rulings if args.rulings is not None else settings.ebti_rulings)
    requested: int | str = "all" if bound is None else bound
    if embeddings is None and not settings.api_key:
        raise RefreshError("OPENROUTER_API_KEY is not set (the embeddings need it)", exit_code=2)
    previous_is_release = bool(args.previous) and not Path(args.previous).is_dir()
    needs_service = not args.no_publish or previous_is_release or (not args.previous and not args.full_embed)
    if needs_service:
        service = service or ReleaseService(args.repo)
        service.check()
    else:
        service = None
    zip_path = Path(args.extract) if args.extract else download_extract(EXTRACT_ZIP)
    snapshot = extract_date(zip_path)
    name = refresh.release_name(KIND, snapshot)
    listing: list[dict] | None = None
    if service is not None and not args.no_publish:
        listing = _listing(service)
        complete = refresh.names_of_kind(listing, KIND, complete_only=True)
        refresh.log(f"newest EBTI release: {complete[0] if complete else 'none'}")
        if complete and not args.force and refresh.parse_release_name(complete[0])[1] >= snapshot:
            return _nothing_new(service, listing, complete[0])
    out = _work_folder(args.out, name, args.force)
    today = date.today()
    records = list(bti_mod.iter_extract(zip_path, set(bti_mod.TARGET_CHAPTERS), today))
    refresh.log(f"extract {zip_path.name} dated {snapshot}, {len(records):,} valid rulings in {len(bti_mod.TARGET_CHAPTERS)} chapters")
    index = NomenclatureIndex.from_jsonl(loader_mod.NOMENCLATURE_JSONL)
    previous_dir, vectors_from = previous_store(args.previous, service, out, listing)
    previous_meta: dict[str, Any] | None = None
    old_docs: dict[str, dict] = {}
    if previous_dir is not None:
        if args.full_embed:
            old_docs = previous_docs(previous_dir) if (previous_dir / "bti_docs.jsonl").exists() else {}
        else:
            previous_meta = check_previous(previous_dir, settings, index)
            old_docs = previous_docs(previous_dir)
        refresh.log(f"previous store: {vectors_from} ({len(old_docs):,} rulings"
                    f"{', ' + str(previous_meta.get('embedding_model')) if previous_meta else ''})")
    elif not args.full_embed:
        raise RefreshError("no previous EBTI store: no complete ebti-* release exists and --previous names none. Start from "
                           "the demo store with --previous demo-store-v1, or embed everything afresh with --full-embed",
                           exit_code=2)
    chosen = demo_store.select_rulings(records, demo_store.preferred_codes(), bound, keep=set(old_docs) or None)
    part = partition(chosen, old_docs)
    kept = sum(1 for r in chosen if r["reference"] in old_docs)
    changed = sum(1 for ruling_id, _, _ in part.embed if ruling_id[len("bti:"):] in old_docs)
    refresh.log(f"chose {len(chosen):,} rulings: {kept:,} kept, {len(chosen) - kept:,} new; {changed:,} changed texts; "
                f"{part.dropped:,} dropped from the previous store")
    usage = Usage()
    emb = embeddings if embeddings is not None else get_embeddings(settings, usage_sink=usage.add)
    store = out / "store"
    meta, reused, embedded = build_store(store, chosen, part, emb, previous_dir=previous_dir, previous_meta=previous_meta,
                                         full_embed=args.full_embed, index=index, settings=settings)
    refresh.log(f"{'embedded the nomenclature index' if args.full_embed else 'copied the nomenclature index'} and "
                f"{reused:,} ruling vectors; embedded {embedded:,} rulings (${usage.cost_usd:.3f})")
    counts = {"rulings": len(chosen), "extract_rulings": len(records), "reused": reused, "embedded": embedded,
              "dropped": part.dropped, "vectors_from": vectors_from}
    meta.update({"built_at": refresh.now_iso(), "bti_rulings": len(chosen), "embedding_usage": usage.model_dump(),
                 "ebti_snapshot_date": snapshot.isoformat(), "ebti_source_version": loader_mod.ebti_source_version(snapshot.isoformat()),
                 "refresh": {"rulings_requested": requested, **{k: counts[k] for k in ("extract_rulings", "reused", "embedded", "dropped", "vectors_from")},
                             "full_embed": bool(args.full_embed)}})
    write_index_meta(store, meta)
    archive = out / refresh.archive_name(KIND, snapshot)
    entries = sorted((p, p.relative_to(out).as_posix()) for p in store.rglob("*") if p.is_file())
    digest, size = pack_entries(archive, entries)
    refresh.log(f"wrote {_shown(archive)} ({size / 1e6:.1f} MB), sha256 {digest}")
    publishing = service is not None and not args.no_publish
    if publishing:
        try:
            listing = service.list()                  # re-read right before the metadata is written (FR-012)
        except GhError as exc:                        # after the build: exit 3, naming the step (FR-005)
            raise refresh.service_failure("listing before the metadata", name, exc, []) from exc
    current = current_block(listing, KIND, name) if publishing else {KIND: [name], "taric": []}
    metadata = out / refresh.METADATA
    write_metadata(metadata, {
        "kind": KIND, "release": name, "snapshot_date": snapshot.isoformat(), "source": EXTRACT_URL,
        "source_version": meta["ebti_source_version"], "built_at": meta["built_at"], "archive": archive.name,
        "sha256": digest, "size": size, "entries": ["store/"], "current": current, "embedding_model": meta.get("embedding_model"),
        **counts})
    if not publishing:
        print(f"EBTI refresh: {name} built in {time.time() - t0:.0f} s, not published (--no-publish)")
        return 0
    publish(service, KIND, snapshot, archive, metadata, force=args.force, listing=listing, notes=_notes(name, counts, size))
    refresh.log(f"published {name} (2 assets), marked latest")
    try:
        after = service.list()
    except GhError as exc:                            # the prune's listing: exit 3, the release stays published
        raise refresh.service_failure("prune", name, exc, [f"created {name}", "marked it latest"]) from exc
    deleted = prune(service, KIND, listing=after)
    kept_names = [n for n in refresh.names_of_kind(after, KIND, complete_only=True) if n not in deleted]
    refresh.log(f"kept {', '.join(kept_names)}; deleted {', '.join(deleted) if deleted else 'nothing'}")
    print(f"EBTI refresh: {name} published in {time.time() - t0:.0f} s")
    return 0


def main(argv: list[str] | None = None, embeddings: Any = None, service: Any = None) -> int:
    """Exit 0 published or nothing new; 1 the source was refused; 2 setup or usage; 3 the release service failed after
    the build or in a nothing-new run's retention (contracts/refresh-cli.md). `embeddings` and `service` are injected
    by the tests (fakes); the settings' OpenRouter embeddings and the gh service are built otherwise."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Refresh the EBTI rulings from the full extract, reusing the previous store's "
                                             "vectors, and publish the store as the release ebti-<date>")
    ap.add_argument("--rulings", metavar="N|all", help=f"the store size: a positive integer or all (default: "
                                                       f"CARGOLINT_EBTI_RULINGS, {DEFAULT_RULINGS})")
    ap.add_argument("--out", type=Path, metavar="DIR", help="the work folder, new or empty (default: build/ebti-<date>/)")
    ap.add_argument("--previous", metavar="RELEASE|DIR",
                    help="the previous store: a release name (demo-store-v1 on the first run) or a folder holding store/ "
                         "(default: the newest complete ebti-* release)")
    ap.add_argument("--full-embed", action="store_true", help="embed every nomenclature chunk and chosen ruling afresh "
                                                              "(a change of embedding model); nothing is copied")
    ap.add_argument("--extract", type=Path, metavar="ZIP", help="a downloaded full extract to use instead of downloading")
    ap.add_argument("--force", action="store_true",
                    help="rebuild and publish the extract's date even when its release exists; empties the default work folder")
    ap.add_argument("--no-publish", action="store_true", help="build and pack without publishing")
    ap.add_argument("--repo", metavar="OWNER/NAME", help="the repository of the releases (default: the checkout's remote)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    t0 = time.time()
    try:
        return _run(args, embeddings, service, t0)
    except RefreshError as exc:
        print(f"{LABELS.get(exc.exit_code, LABELS[3])}: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
