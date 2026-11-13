"""Knowledge base releases (feature 013): release names and kinds, completeness, the metadata file with its `current`
block, packing, the release service over the GitHub CLI, publishing, retention and the latest-release repair, and the
app's fetch at a cold start. Standard library and `agent.config` only, so `app.py` can import it at start-up
(plan, Structure Decision); chromadb and the embeddings load only in rag/refresh_ebti.py.

The two refresh commands (rag/refresh_taric.py, rag/refresh_ebti.py) publish `<kind>-YYYY-MM-DD` releases with two
assets, the archive and `metadata.json`. A release is complete when it carries both and is not a draft; only complete
releases count for "nothing new", for `current`, for retention and for the app (contracts/releases.md). Every `gh`
call runs through `_run_gh`, which the suite's offline guard replaces.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from agent.config import RELEASE_KINDS, RELEASE_NAME_RE, ROOT

KINDS = RELEASE_KINDS                   # fetch order and name pattern: ("ebti", "taric")
KEEP_RELEASES = 2                       # retention: the complete releases of a kind kept, newest first (spec FR-010)
GH_ENV = "CARGOLINT_GH"                 # optional full path to gh, as CARGOLINT_GPG names gpg
METADATA = "metadata.json"
ARCHIVE = {"ebti": "cargolint-ebti-{date}.zip", "taric": "cargolint-taric-{date}.zip"}
TITLE = {"ebti": "EBTI rulings {date}", "taric": "TARIC snapshot {date}"}
MARKER = {"ebti": "store/index_meta.json", "taric": "data/taric.jsonl"}      # unpacked last; present means complete
RELEASE_FILE = {"ebti": "store/release.json", "taric": "data/taric_release.json"}   # the metadata kept beside the data
ALLOWED = {"ebti": lambda name: name.startswith("store/") and len(name) > len("store/"),
           "taric": lambda name: name == "data/taric.jsonl"}                 # data-model §5
LATEST = "https://github.com/{repo}/releases/latest/download/{asset}"       # the pointer: no API, no token
API = "https://api.github.com/repos/{repo}/releases?per_page=50"             # the listing, the second route
DOWNLOAD = "https://github.com/{repo}/releases/download/{tag}/{asset}"
REQUIRED_FIELDS = ("kind", "release", "archive", "sha256")
POINTER_TIMEOUT = 30
ARCHIVE_TIMEOUT = 600


class RefreshError(Exception):
    """A refresh cannot go on; `exit_code` is the command's exit code (contracts/refresh-cli.md)."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class GhError(RefreshError):
    """A `gh` call failed. Exit code 3 (a service failure) unless the caller says otherwise."""

    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message, exit_code)


def log(msg: str) -> None:
    print(f"[refresh] {msg}", flush=True)


# --------------------------------------------------------------------------- names, kinds and the listing
def parse_release_name(name: str) -> tuple[str, date] | None:
    """`ebti-2026-11-01` → ("ebti", 2026-11-01); None for any other name (`demo-store-v1`, `ebti-latest`, a bad date)."""
    m = RELEASE_NAME_RE.match(name or "")
    if m is None:
        return None
    try:
        return m["kind"], date.fromisoformat(m["date"])
    except ValueError:
        return None


def release_name(kind: str, snapshot_date: date) -> str:
    return f"{kind}-{snapshot_date.isoformat()}"


def archive_name(kind: str, snapshot_date: date) -> str:
    return ARCHIVE[kind].format(date=snapshot_date.isoformat())


def parse_listing(data: Any) -> list[dict]:
    """GitHub's release list, as the API and `gh api` return it, reduced to name, draft, published_at and asset names.
    A missing `draft` reads as false, a missing `published_at` (a draft) as None; entries without a tag are ignored."""
    if not isinstance(data, list):
        raise ValueError("the release listing is not a list")
    out = []
    for entry in data:
        if not isinstance(entry, dict) or not entry.get("tag_name"):
            continue
        out.append({"name": entry["tag_name"], "draft": bool(entry.get("draft", False)),
                    "published_at": entry.get("published_at") or None,
                    "assets": [a["name"] for a in entry.get("assets") or [] if isinstance(a, dict) and a.get("name")]})
    return out


def is_complete(release: dict) -> bool:
    """Both assets (the kind's archive and metadata.json) and not a draft; a name of no kind is never complete."""
    parsed = parse_release_name(release.get("name", ""))
    if parsed is None or release.get("draft"):
        return False
    assets = release.get("assets") or []
    return archive_name(*parsed) in assets and METADATA in assets


def names_of_kind(listing: list[dict], kind: str, complete_only: bool = False) -> list[str]:
    """The releases of a kind, newest first by the date in the name (not by listing order)."""
    found = []
    for release in listing:
        parsed = parse_release_name(release.get("name", ""))
        if parsed is None or parsed[0] != kind or (complete_only and not is_complete(release)):
            continue
        found.append((parsed[1], release["name"]))
    return [name for _, name in sorted(found, reverse=True)]


def listed(listing: list[dict], name: str | None) -> dict | None:
    return next((r for r in listing if r.get("name") == name), None) if name else None


def current_block(listing: list[dict], kind: str, name: str, keep: int = KEEP_RELEASES) -> dict[str, list[str]]:
    """The metadata's `current`: per kind the complete releases left after this run's publish and retention, newest
    first, at most `keep`; computed from a listing read right before the metadata is written plus the release about
    to be published (contracts/releases.md)."""
    out: dict[str, list[str]] = {}
    for k in KINDS:
        names = names_of_kind(listing, k, complete_only=True)
        if k == kind and name not in names:
            names = names_of_kind([*listing, {"name": name, "draft": False, "assets": [archive_name(k, parse_release_name(name)[1]), METADATA]}],
                                  k, complete_only=True)
        out[k] = names[:keep]
    return out


# --------------------------------------------------------------------------- the archive and the metadata file
def sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pack_entries(archive: Path | str, entries: list[tuple[Path | str, str]]) -> tuple[str, int]:
    """Packs the given files under the given archive paths, in the order given; returns the SHA-256 and the size."""
    archive = Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path, name in entries:
            z.write(Path(path), name)
    return sha256(archive), archive.stat().st_size


def write_metadata(path: Path | str, fields: dict[str, Any]) -> dict[str, Any]:
    """The release's metadata.json (data-model §2); the required fields must be there."""
    missing = [k for k in REQUIRED_FIELDS if not fields.get(k)]
    if missing:
        raise RefreshError(f"the metadata lacks {', '.join(missing)}", exit_code=2)
    Path(path).write_text(json.dumps(fields, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return fields


def read_metadata(source: Path | str | bytes) -> dict[str, Any]:
    """A metadata file (a path or its bytes), refused without `kind`, `release`, `archive` and `sha256`."""
    try:
        text = source.decode("utf-8") if isinstance(source, bytes) else Path(source).read_text(encoding="utf-8")
        fields = json.loads(text)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise RefreshError(f"the metadata cannot be read: {exc}") from exc
    if not isinstance(fields, dict):
        raise RefreshError("the metadata is not an object")
    missing = [k for k in REQUIRED_FIELDS if not fields.get(k)]
    if missing:
        raise RefreshError(f"the metadata lacks {', '.join(missing)}")
    return fields


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------- the release service (gh)
def _gh_executable() -> str:
    """CARGOLINT_GH, else gh on PATH (as rag.pgp.find_gpg finds gpg)."""
    explicit = os.environ.get(GH_ENV)
    if explicit:
        if Path(explicit).is_file():
            return explicit
        raise GhError(f"{GH_ENV} points to {explicit}, which does not exist", exit_code=2)
    found = shutil.which("gh")
    if found:
        return found
    raise GhError(f"gh not found: set {GH_ENV} or put the GitHub CLI on PATH", exit_code=2)


def _run_gh(argv: list[str]) -> str:
    """The one function that runs the GitHub CLI; the suite's offline guard replaces it. Returns gh's stdout."""
    try:
        done = subprocess.run([_gh_executable(), *argv], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=3600)
    except (OSError, subprocess.SubprocessError) as exc:
        raise GhError(f"gh {' '.join(argv[:2])}: {exc}") from exc
    if done.returncode != 0:
        lines = [line for line in (done.stderr or done.stdout or "").splitlines() if line.strip()]
        raise GhError(f"gh {' '.join(argv[:2])} failed (exit {done.returncode}): {lines[-1] if lines else 'no output'}")
    return done.stdout


class ReleaseService:
    """GitHub releases of one repository through `gh` (contracts/releases.md). `repo` is OWNER/NAME, else the
    checkout's remote; `run` replaces the runner (a recorder in the tests), else `_run_gh` is looked up at each call so
    the offline guard sees it. The tests use FakeReleaseService, which implements the same calls in memory."""

    def __init__(self, repo: str | None = None, run: Callable[[list[str]], str] | None = None) -> None:
        self.repo = (repo or "").strip() or None
        self._run = run

    def _call(self, argv: list[str]) -> str:
        return (self._run or _run_gh)(argv)

    def _repo_flag(self) -> list[str]:
        return ["--repo", self.repo] if self.repo else []

    def _api(self, tail: str) -> str:
        return f"repos/{self.repo or '{owner}/{repo}'}/{tail}"

    def check(self) -> None:
        """gh present and signed in; RefreshError(exit_code=2) otherwise."""
        try:
            self._call(["--version"])
            self._call(["auth", "status"])
        except GhError as exc:
            raise RefreshError(f"the release service is not available: {exc}", exit_code=2) from exc

    def list(self) -> list[dict]:
        return parse_listing(json.loads(self._call(["api", self._api("releases?per_page=100")]) or "[]"))

    def latest(self) -> str | None:
        """The name of the release marked latest; None when the repository has none (HTTP 404)."""
        try:
            out = self._call(["api", self._api("releases/latest")])
        except GhError as exc:
            if "404" in str(exc):
                return None
            raise
        data = json.loads(out or "{}")
        return (data.get("tag_name") or None) if isinstance(data, dict) else None

    def create(self, tag: str, title: str, notes: str, files: list[Path | str]) -> None:
        self._call(["release", "create", tag, *[str(f) for f in files], "--title", title, "--notes", notes,
                    *self._repo_flag()])

    def mark_latest(self, tag: str) -> None:
        self._call(["release", "edit", tag, "--latest", *self._repo_flag()])

    def delete(self, tag: str) -> None:
        self._call(["release", "delete", tag, "--yes", "--cleanup-tag", *self._repo_flag()])

    def download(self, tag: str, pattern: str, dir: Path | str) -> None:
        Path(dir).mkdir(parents=True, exist_ok=True)
        self._call(["release", "download", tag, "--pattern", pattern, "--dir", str(dir), *self._repo_flag()])


# --------------------------------------------------------------------------- publishing, retention, the latest release
def _failure(step: str, name: str, exc: Exception, done: list[str]) -> RefreshError:
    before = f"before that it {', '.join(done)}" if done else "before that it did nothing"
    return RefreshError(f"the release service failed at the {step} of {name}: {exc}; {before}", exit_code=3)


def publish(service: Any, kind: str, snapshot_date: date, archive: Path | str, metadata: Path | str,
            force: bool = False, listing: list[dict] | None = None, notes: str = "") -> str:
    """Creates `<kind>-<date>` with the two assets and marks it the repository's latest release. An incomplete release
    of the name is deleted first; with `force` the complete one is deleted and created afresh (never patched asset by
    asset); without `force` a complete one is refused. A `gh` failure is RefreshError(exit_code=3) naming the step and
    what was done before it. Returns the release name."""
    name = release_name(kind, snapshot_date)
    listing = listing if listing is not None else service.list()
    existing = listed(listing, name)
    done: list[str] = []
    step = "delete"
    try:
        if existing is not None:
            if is_complete(existing) and not force:
                raise RefreshError(f"{name} is already published and complete; use --force to replace it", exit_code=2)
            service.delete(name)
            done.append(f"deleted the {'complete' if is_complete(existing) else 'incomplete'} {name}")
        step = "create"
        service.create(name, TITLE[kind].format(date=snapshot_date.isoformat()), notes, [Path(archive), Path(metadata)])
        done.append(f"created {name}")
        step = "mark latest"
        service.mark_latest(name)
    except GhError as exc:
        raise _failure(step, name, exc, done) from exc
    return name


def prune(service: Any, kind: str, keep: int = KEEP_RELEASES, listing: list[dict] | None = None) -> list[str]:
    """Keeps the `keep` newest complete releases of the kind and deletes every other release of the kind, older or
    incomplete, with its tag; other names are untouched. Returns the deleted names."""
    listing = listing if listing is not None else service.list()
    kept = names_of_kind(listing, kind, complete_only=True)[:keep]
    deleted: list[str] = []
    for name in names_of_kind(listing, kind):
        if name in kept:
            continue
        try:
            service.delete(name)
        except GhError as exc:
            raise _failure("prune", name, exc, [f"deleted {d}" for d in deleted]) from exc
        deleted.append(name)
    return deleted


def _published(release: dict | None) -> str:
    return (release or {}).get("published_at") or ""


def repair_latest(service: Any, kind: str, listing: list[dict] | None = None) -> str | None:
    """Re-marks the newest complete release of the kind as the repository's latest when the release marked latest is
    none, incomplete, or published before it; a complete release published later (of either kind) stays latest.
    Returns the name re-marked, or None."""
    listing = listing if listing is not None else service.list()
    complete = names_of_kind(listing, kind, complete_only=True)
    if not complete:
        return None
    newest = complete[0]
    try:
        latest = service.latest()
        if latest == newest:
            return None
        current = listed(listing, latest)
        if current is not None and is_complete(current) and _published(current) >= _published(listed(listing, newest)):
            return None
        service.mark_latest(newest)
    except GhError as exc:
        raise _failure("repair latest", newest, exc, []) from exc
    return newest
