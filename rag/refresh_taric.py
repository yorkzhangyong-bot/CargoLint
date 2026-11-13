"""The TARIC refresh (feature 013, User Story 1): `python scripts/refresh_taric.py [--force] [--no-publish] [--repo
OWNER/NAME]`. It finds the newest complete full extract in the Swedish Customs `tot` folder, downloads its six object
files into a folder of their own, runs the loader's TARIC load (signature verification, parsing, data/taric.jsonl and
the register row, exactly as `python -m rag.loader --taric`), packs the snapshot, publishes `taric-<date>` with its
metadata, marks it the repository's latest release and keeps the two newest complete TARIC releases. No embedding and
no model call (contracts/refresh-cli.md). The listing, the download and `gh` are reached through their modules, so the
suite's offline guard sees them and the tests point them at files and a fake service.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import rag.loader as loader_mod
from agent.config import ROOT, TARIC_OBJECTS
from rag import refresh
from rag.pgp import GpgNotFound, SignatureError, check_key_copy, find_gpg
from rag.refresh import (GhError, RefreshError, ReleaseService, current_block, pack_entries, prune, publish, repair_latest,
                         write_metadata)
from rag.taric import TaricFileError, read_snapshot_header
from rag.taric_extract import _FILE

KIND = "taric"
TOT_URL = "https://distr.tullverket.se/tulltaxan/xml/tot/"     # the full extracts, one batch at a time (research R-01)
SOURCE_URL = "https://distr.tullverket.se/tulltaxan/"           # the metadata's `source`
_HREF = re.compile(r'href="([^"?/\\]+\.xml\.gz\.pgp)"')   # plain file names: no path separators of either kind
_BATCH_ID = re.compile(r"[0-9A-Fa-f-]+")                      # the distribution's batch ids: hex digits and dashes
LABELS = {1: "TARIC refresh refused", 2: "TARIC refresh not started", 3: "TARIC refresh failed"}


@dataclass(frozen=True)
class Batch:
    batch_id: str
    snapshot_date: date
    files: tuple[str, ...]          # the six object file names, in TARIC_OBJECTS order


# --------------------------------------------------------------------------- the tot listing
def read_listing(url: str) -> str:
    """The folder's index page; unreadable → exit 1 (nothing downloaded, nothing published)."""
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read().decode("utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        raise RefreshError(f"the tot listing {url} cannot be read: {exc}", exit_code=1) from exc


def parse_listing_html(html: str) -> list[str]:
    """The signed file names linked from the index page, in page order, each once."""
    return list(dict.fromkeys(_HREF.findall(html)))


def current_batch(names: list[str]) -> Batch:
    """The newest batch whose six object files are all listed (spec FR-001). A newer batch missing an object is passed
    over for the older complete one; no complete batch, or no object file at all, is refused (exit 1)."""
    groups: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for name in names:
        m = _FILE.match(name)
        if m and _BATCH_ID.fullmatch(m["batch"]):          # a name with path parts in its batch is no object file
            groups[(m["yymmdd"], m["batch"])][m["object"]] = name
    if not groups:
        raise RefreshError("the tot listing names no TARIC object file", exit_code=1)
    complete = [(key, found) for key, found in groups.items() if all(o in found for o in TARIC_OBJECTS)]
    if not complete:
        seen = "; ".join(f"batch {b} ({d}): {len(f)} of {len(TARIC_OBJECTS)} object files" for (d, b), f in sorted(groups.items()))
        raise RefreshError(f"no batch in the tot listing has all {len(TARIC_OBJECTS)} object files: {seen}", exit_code=1)
    (yymmdd, batch_id), found = max(complete, key=lambda item: item[0])
    try:
        snapshot = date(2000 + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:]))
    except ValueError as exc:
        raise RefreshError(f"{found[TARIC_OBJECTS[0]]}: the name holds no valid date", exit_code=1) from exc
    return Batch(batch_id, snapshot, tuple(found[o] for o in TARIC_OBJECTS))


def download_batch(url: str, files: tuple[str, ...], folder: Path) -> Path:
    """The six files into `folder` through the loader's download (resumable: the files are immutable and named by their
    batch), looked up on the module at call time."""
    for name in files:                                   # never a path: the file lands in the batch folder only
        if Path(name).name != name or "/" in name or "\\" in name or name in (".", ".."):
            raise RefreshError(f"unsafe file name in the listing: {name!r}", exit_code=1)
    folder.mkdir(parents=True, exist_ok=True)
    base = url.rstrip("/") + "/"
    for name in files:
        loader_mod.download(base + name, folder / name)
    return folder


# --------------------------------------------------------------------------- the command
def _shown(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _check_gpg() -> None:
    """The loader's preconditions, checked before anything is downloaded (setup error → exit 2)."""
    try:
        find_gpg()
        key = Path(loader_mod.TARIC_KEY)
        if not key.exists():
            raise FileNotFoundError(f"the key copy {_shown(key)} is missing")
        check_key_copy(key, loader_mod.TARIC_KEY_FINGERPRINT)
    except (GpgNotFound, SignatureError, OSError) as exc:
        raise RefreshError(str(exc), exit_code=2) from exc


def _listing(service: Any) -> list[dict]:
    try:
        return service.list()
    except GhError as exc:
        raise RefreshError(f"the release listing failed: {exc}", exit_code=2) from exc


def _notes(batch: Batch, header: dict[str, Any], size: int) -> str:
    return (f"TARIC snapshot {batch.snapshot_date} from the Swedish Customs Tariff File Distribution, batch "
            f"{batch.batch_id}: {header['goods_records']:,} code records, {header['measure_records']:,} measure records, "
            f"{header['cn8_mismatches']:,} CN-8 mismatches; archive {size / 1e6:.1f} MB. Published by "
            "scripts/refresh_taric.py (feature 013).")


def _nothing_new(service: Any, listing: list[dict], newest: str) -> int:
    """Retention and the latest-release repair still run (spec FR-010); a failure in them is exit 3."""
    deleted = prune(service, KIND, listing=listing)
    if deleted:
        refresh.log(f"deleted {', '.join(deleted)}")
    remarked = repair_latest(service, KIND, listing=listing)
    if remarked:
        refresh.log(f"marked {remarked} latest")
    print(f"TARIC refresh: {newest} is already published and complete; nothing new. Use --force to rebuild and replace it.")
    return 0


def _run(args: argparse.Namespace, service: Any, t0: float) -> int:
    _check_gpg()
    if args.no_publish:
        service = None
    else:
        service = service or ReleaseService(args.repo)
        service.check()
    batch = current_batch(parse_listing_html(read_listing(TOT_URL)))
    refresh.log(f"tot listing: batch {batch.batch_id}, snapshot {batch.snapshot_date}, {len(batch.files)} files")
    name = refresh.release_name(KIND, batch.snapshot_date)
    listing: list[dict] = []
    if service is not None:
        listing = _listing(service)
        complete = refresh.names_of_kind(listing, KIND, complete_only=True)
        refresh.log(f"newest TARIC release: {complete[0] if complete else 'none'}")
        if complete and not args.force and refresh.parse_release_name(complete[0])[1] >= batch.snapshot_date:
            return _nothing_new(service, listing, complete[0])
    folder = Path(loader_mod.TARIC_RAW_DIR) / batch.snapshot_date.isoformat()
    download_batch(TOT_URL, batch.files, folder)
    code = loader_mod.load_taric(folder, force=args.force)
    if code != 0:
        return code                                   # the loader printed its refusal (1) or setup message (2)
    try:
        header = read_snapshot_header(loader_mod.TARIC_SNAPSHOT)
    except TaricFileError as exc:
        raise RefreshError(f"{_shown(Path(loader_mod.TARIC_SNAPSHOT))} cannot be read after the load: {exc}") from exc
    if not header or header.get("snapshot_date") != batch.snapshot_date.isoformat() or header.get("batch_id") != batch.batch_id:
        raise RefreshError(f"{_shown(Path(loader_mod.TARIC_SNAPSHOT))} does not hold batch {batch.batch_id} of "
                           f"{batch.snapshot_date} after the load")
    archive = folder / refresh.archive_name(KIND, batch.snapshot_date)
    digest, size = pack_entries(archive, [(Path(loader_mod.TARIC_SNAPSHOT), "data/taric.jsonl")])
    refresh.log(f"wrote {_shown(archive)} ({size / 1e6:.1f} MB), sha256 {digest}")
    if service is not None:
        try:
            listing = service.list()                  # re-read right before the metadata is written (FR-012)
        except GhError as exc:                        # after the build: exit 3, naming the step (FR-005)
            raise refresh.service_failure("listing before the metadata", name, exc, []) from exc
    current = current_block(listing, KIND, name) if service is not None else {"ebti": [], KIND: [name]}
    metadata = folder / refresh.METADATA
    write_metadata(metadata, {
        "kind": KIND, "release": name, "snapshot_date": batch.snapshot_date.isoformat(), "source": SOURCE_URL,
        "source_version": f"batch {batch.batch_id}, extract {batch.snapshot_date}", "built_at": refresh.now_iso(),
        "archive": archive.name, "sha256": digest, "size": size, "entries": ["data/taric.jsonl"], "current": current})
    if service is None:
        print(f"TARIC refresh: {name} built in {time.time() - t0:.0f} s, not published (--no-publish)")
        return 0
    publish(service, KIND, batch.snapshot_date, archive, metadata, force=args.force, listing=listing,
            notes=_notes(batch, header, size))
    refresh.log(f"published {name} (2 assets), marked latest")
    try:
        after = service.list()
    except GhError as exc:                            # the prune's listing: exit 3, the release stays published
        raise refresh.service_failure("prune", name, exc, [f"created {name}", "marked it latest"]) from exc
    deleted = prune(service, KIND, listing=after)
    kept = [n for n in refresh.names_of_kind(after, KIND, complete_only=True) if n not in deleted]
    refresh.log(f"kept {', '.join(kept)}; deleted {', '.join(deleted) if deleted else 'nothing'}")
    print(f"TARIC refresh: {name} published in {time.time() - t0:.0f} s")
    return 0


def main(argv: list[str] | None = None, service: Any = None) -> int:
    """Exit 0 published or nothing new; 1 the source was refused; 2 setup or usage; 3 the release service failed after
    the build or in a nothing-new run's retention (contracts/refresh-cli.md)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Refresh the TARIC snapshot from the Swedish Customs full extract and publish "
                                             "it as the release taric-<date>")
    ap.add_argument("--force", action="store_true", help="download, rebuild and publish the batch even when its release exists")
    ap.add_argument("--no-publish", action="store_true", help="build and pack without the release service")
    ap.add_argument("--repo", metavar="OWNER/NAME", help="the repository of the releases (default: the checkout's remote)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    t0 = time.time()
    try:
        return _run(args, service, t0)
    except RefreshError as exc:
        print(f"{LABELS.get(exc.exit_code, LABELS[3])}: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
