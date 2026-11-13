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
import http.client
import json
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
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
RELEASE_FILE_NAME = {"ebti": "release.json", "taric": "taric_release.json"}          # the metadata kept beside the data
RELEASE_FILE = {"ebti": f"store/{RELEASE_FILE_NAME['ebti']}", "taric": f"data/{RELEASE_FILE_NAME['taric']}"}
ALLOWED = {"ebti": lambda name: name.startswith("store/") and len(name) > len("store/"),
           "taric": lambda name: name == "data/taric.jsonl"}                 # data-model §5
LATEST = "https://github.com/{repo}/releases/latest/download/{asset}"       # the pointer: no API, no token
API = "https://api.github.com/repos/{repo}/releases?per_page=50"             # the listing, the second route
DOWNLOAD = "https://github.com/{repo}/releases/download/{tag}/{asset}"
REQUIRED_FIELDS = ("kind", "release", "archive", "sha256")
POINTER_TIMEOUT = 30
ARCHIVE_TIMEOUT = 600
_FETCH_ERRORS = (OSError, http.client.HTTPException, ValueError)   # a route or download that fails to read


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
def service_failure(step: str, name: str, exc: Exception, done: list[str]) -> RefreshError:
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
        raise service_failure(step, name, exc, done) from exc
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
            raise service_failure("prune", name, exc, [f"deleted {d}" for d in deleted]) from exc
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
        raise service_failure("repair latest", newest, exc, []) from exc
    return newest


# --------------------------------------------------------------------------- the app's fetch at a cold start
logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    unpacked: dict[str, str] = field(default_factory=dict)     # kind → the release unpacked
    failed: dict[str, str] = field(default_factory=dict)       # kind → every candidate and its reason


def releases_needed(settings: Any, root: Path | None = None) -> list[str]:
    """The kinds whose marker is missing, in fetch order; [] when the repository setting is empty or nothing is missing
    (then nothing is read, not even the pointer)."""
    if not getattr(settings, "release_repo", ""):
        return []
    base = root or ROOT
    return [kind for kind in KINDS if not (base / MARKER[kind]).exists()]


def _open(url: str, timeout: int) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def _read_pointer(repo: str) -> dict[str, Any]:
    """The latest release's metadata.json from GitHub's fixed download address: no API, no token (research R-06)."""
    return read_metadata(_open(LATEST.format(repo=repo, asset=METADATA), POINTER_TIMEOUT))


def _read_listing(repo: str) -> list[dict]:
    """The repository's release list through the API: the second route."""
    return parse_listing(json.loads(_open(API.format(repo=repo), POINTER_TIMEOUT)))


class _Routes:
    """The two routes to the release names, each read at most once per fetch (once per process, as the app fetches
    once); an unreadable route is noted, not fatal in itself."""

    def __init__(self, repo: str) -> None:
        self.repo = repo
        self._pointer: dict[str, Any] | None = None
        self._listing: list[dict] | None = None
        self.read = {"pointer": False, "listing": False}
        self.notes: dict[str, str] = {}

    def pointer(self) -> dict[str, Any] | None:
        if not self.read["pointer"]:
            self.read["pointer"] = True
            try:
                self._pointer = _read_pointer(self.repo)
            except (*_FETCH_ERRORS, RefreshError) as exc:
                self.notes["pointer"] = f"the latest release's metadata could not be read ({exc})"
                logger.info("knowledge base releases: %s", self.notes["pointer"])
        return self._pointer

    def listing(self) -> list[dict] | None:
        if not self.read["listing"]:
            self.read["listing"] = True
            try:
                self._listing = _read_listing(self.repo)
            except _FETCH_ERRORS as exc:
                self.notes["listing"] = f"the listing could not be read ({exc})"
                logger.info("knowledge base releases: %s", self.notes["listing"])
        return self._listing

    def route_text(self, kind: str) -> str:
        parts = [self.notes.get("pointer") or f"the latest release's metadata names no {kind} release",
                 self.notes.get("listing") or f"the listing names no complete {kind} release"]
        return "no release found: " + "; ".join(parts)


def _unpinned(kind: str, routes: _Routes, tried: list[str]) -> Iterator[str]:
    """The candidates resolved as without a pin, newest first: the pointer's names for the kind (at most two), then,
    once those are exhausted or when the pointer is unusable, the listing's complete releases not yet tried (at most
    two). The listing is read only when a candidate is asked for beyond the pointer's."""
    pointer = routes.pointer()
    named = []
    current = pointer.get("current") if pointer is not None else None
    listed_names = current.get(kind) if isinstance(current, dict) else None     # a malformed block names nothing
    for name in listed_names if isinstance(listed_names, list) else []:
        parsed = parse_release_name(name) if isinstance(name, str) else None
        if parsed is not None and parsed[0] == kind:
            named.append(name)
    for name in named[:KEEP_RELEASES]:
        if name not in tried:
            yield name
    listing = routes.listing()
    if listing is not None:
        untried = [n for n in names_of_kind(listing, kind, complete_only=True) if n not in tried and n not in named]
        yield from untried[:KEEP_RELEASES]


def _unpack(z: zipfile.ZipFile, names: list[str], kind: str, base: Path) -> None:
    """The entries into `base`, the marker last: store/index_meta.json for the EBTI kind; data/taric.jsonl through a
    temporary name and a rename for the TARIC kind."""
    if kind == "taric":
        target = base / MARKER["taric"]
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        with z.open(MARKER["taric"]) as src, tmp.open("wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
        os.replace(tmp, target)
        return
    for name in sorted(names, key=lambda n: n == MARKER[kind]):
        z.extract(name, base)


def fetch_release(repo: str, kind: str, name: str, root: Path | None = None) -> dict[str, Any]:
    """One release: its metadata, the archive to a temporary file, the SHA-256 against the metadata, the entries
    against the kind's allowed paths, the unpack with the marker last, then the release file beside the data
    (data-model §4). RefreshError with the reason at any step; nothing is unpacked before the checks pass."""
    base = root or ROOT
    parsed = parse_release_name(name)
    if parsed is None or parsed[0] != kind:
        raise RefreshError(f"{name} is not a {kind} release name")
    try:
        fields = read_metadata(_open(DOWNLOAD.format(repo=repo, tag=name, asset=METADATA), POINTER_TIMEOUT))
    except (OSError, http.client.HTTPException) as exc:
        raise RefreshError(f"the metadata could not be downloaded: {exc}") from exc
    if fields["kind"] != kind or fields["release"] != name:
        raise RefreshError(f"the metadata is for {fields['kind']} {fields['release']}, not {kind} {name}")
    if fields["archive"] != archive_name(kind, parsed[1]):
        raise RefreshError(f"the metadata names the archive {fields['archive']}, not {archive_name(kind, parsed[1])}")
    expected = str(fields["sha256"]).strip().lower()
    with tempfile.TemporaryDirectory(prefix="cargolint-release-") as tmp:
        archive = Path(tmp) / "release.zip"
        try:
            with urllib.request.urlopen(DOWNLOAD.format(repo=repo, tag=name, asset=fields["archive"]),
                                        timeout=ARCHIVE_TIMEOUT) as response, archive.open("wb") as f:
                shutil.copyfileobj(response, f, 1 << 20)
        except (OSError, http.client.HTTPException) as exc:
            raise RefreshError(f"the archive could not be downloaded: {exc}") from exc
        digest = sha256(archive)
        if digest != expected:
            raise RefreshError(f"the archive's SHA-256 is {digest}, not {expected} as its metadata says")
        try:
            with zipfile.ZipFile(archive) as z:
                names = z.namelist()
                unexpected = [n for n in names if ".." in n.split("/") or not ALLOWED[kind](n)]
                if unexpected:
                    raise RefreshError(f"the archive holds unexpected paths: {', '.join(unexpected[:3])}")
                if MARKER[kind] not in names:
                    raise RefreshError(f"the archive holds no {MARKER[kind]}")
                _unpack(z, names, kind, base)
        except (OSError, zipfile.BadZipFile) as exc:
            raise RefreshError(f"the archive could not be unpacked: {exc}") from exc
    release_file = base / RELEASE_FILE[kind]
    release_file.parent.mkdir(parents=True, exist_ok=True)
    release_file.write_text(json.dumps({**fields, "fetched_at": now_iso()}, indent=2) + "\n", encoding="utf-8")
    return fields


def _try(repo: str, kind: str, name: str, base: Path) -> str | None:
    """None when the release was fetched, else the reason. Whatever one candidate throws, the fallback goes on."""
    try:
        fetch_release(repo, kind, name, base)
    except RefreshError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 - a cold start must fall back, never crash on one candidate (FR-016)
        logger.warning("knowledge base release %s: unexpected %s: %s", name, type(exc).__name__, exc)
        return f"unexpected {type(exc).__name__}: {exc}"
    return None


def fetch_releases(settings: Any, root: Path | None = None) -> FetchResult:
    """The app's fetch (contracts/releases.md): for each kind whose marker is missing, the pinned release alone, else
    the pointer's candidates, else the listing's; each candidate verified and unpacked in turn; a failed pin falls back
    once to the newest resolved as without a pin, with a log line. Raises RefreshError only when the EBTI kind
    fails; a failed TARIC kind is returned in `failed` and the app opens without TARIC."""
    base = root or ROOT
    result = FetchResult()
    needed = releases_needed(settings, base)
    if not needed:
        return result
    repo = settings.release_repo
    routes = _Routes(repo)
    for kind in needed:
        reasons: list[str] = []
        tried: list[str] = []
        pin = (getattr(settings, f"{kind}_release", "") or "").strip()
        if pin:
            tried.append(pin)
            reason = _try(repo, kind, pin, base)
            if reason is None:
                result.unpacked[kind] = pin
                continue
            reasons.append(f"{pin}: {reason}")
            logger.warning("pin %s not honoured: %s", pin, reason)
            first = next(_unpinned(kind, routes, tried), None)   # the fallback, once; the listing only when the
            candidates: Iterator[str] = iter([first] if first else [])   # pointer names nothing (not drained)
        else:
            candidates = _unpinned(kind, routes, tried)
        resolved = False
        for name in candidates:
            resolved = True
            tried.append(name)
            reason = _try(repo, kind, name, base)
            if reason is None:
                result.unpacked[kind] = name
                break
            reasons.append(f"{name}: {reason}")
        else:
            if not resolved:
                reasons.append(routes.route_text(kind))             # neither route gave a candidate: say why
            elif routes.notes.get("listing"):
                reasons.append(routes.notes["listing"])
            text = "; ".join(reasons)
            if kind == "ebti":
                raise RefreshError(f"{kind}: {text}")
            result.failed[kind] = text
            logger.warning("knowledge base release %s not fetched: %s", kind, text)
    return result
