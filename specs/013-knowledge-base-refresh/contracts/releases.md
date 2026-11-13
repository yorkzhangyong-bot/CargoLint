# Contract: releases, retention and the app's fetch

## Layout

| | EBTI | TARIC |
|---|---|---|
| Release name | `ebti-YYYY-MM-DD` (the extract's date) | `taric-YYYY-MM-DD` (the batch's date) |
| Archive asset | `cargolint-ebti-<date>.zip` | `cargolint-taric-<date>.zip` |
| Archive entries | `store/index_meta.json`, `store/bm25.pkl`, `store/bti_docs.jsonl`, `store/chroma/…`, `store/chroma-bti/…` | `data/taric.jsonl` |
| Metadata asset | `metadata.json` (data-model §2) | `metadata.json` |
| Marker | `store/index_meta.json`, unpacked last | `data/taric.jsonl`, written through `data/taric.jsonl.tmp` |
| Complete | both assets present and not a draft | the same |
| Kept by retention | the two newest complete by date; every other EBTI release is deleted | the same for TARIC |
| Title | `EBTI rulings <date>` | `TARIC snapshot <date>` |
| Pointer | the release published last is marked the repository's latest; its `metadata.json` has `current`, the complete releases of both kinds | the same |

`demo-store-v1` (`cargolint-demo-store-v1.zip`, `store/…` and `data/taric.jsonl`, no metadata) belongs to no kind:
retention never lists it, the app never resolves it, and only `--previous demo-store-v1` reads it. It is the latest
release until the first refresh, so the app's pointer route finds no metadata then and the listing route is taken.

## Publishing (`rag.refresh.publish`)

```python
def publish(service: ReleaseService, kind: str, snapshot_date: date, archive: Path, metadata: Path,
            force: bool = False) -> str:            # returns the release name
def prune(service: ReleaseService, kind: str, keep: int = KEEP_RELEASES) -> list[str]:   # the deleted names
```

- `publish` creates `<kind>-<date>` with the two assets, deleting first an incomplete release of that name (an
  asset missing or a draft) or, when `force` is set, the existing complete one: a release is never patched asset by
  asset, so its two assets always come from one build. When a complete release of the name exists and `force` is
  not set it raises `RefreshError` (the scripts check this earlier and exit 0 with "nothing new"). After the create
  it marks the release the repository's latest (`gh release edit <tag> --latest`), so the pointer moves to it.
- `current_block(listing, kind, name)` computes the metadata's `current` from a listing the script reads immediately
  before writing the metadata (after the build and the pack, one `gh api` call; never the "nothing new" listing of
  minutes earlier) plus the release about to be published: per kind the complete names, newest first, cut to `keep`.
- `prune` lists all releases, keeps the `keep` newest complete names of the kind by their date and deletes every
  other release of the kind, older or incomplete, with `--cleanup-tag`; other names are untouched. It runs after a
  successful publish and after a "nothing new" run (from the listing that run read), so a failed prune repairs itself
  on the next run; a run that exits 1 or 2 deletes nothing.
- A `gh` failure inside `publish` or `prune` raises `RefreshError(exit_code=3)` whose message names the step
  (`delete`, `create`, `mark latest`, `prune`), the release and what was done before it; the scripts exit 3 with it.
  The next run of the kind repairs it, pruning and re-marking the latest release even when the source has nothing new.

## The release service (`rag.refresh.ReleaseService`)

| Method | `gh` call |
|---|---|
| `check()` | `gh auth status` (and `gh --version`); raises `RefreshError(exit_code=2)` when missing or not signed in |
| `list()` | `gh api repos/<repo>/releases?per_page=100` → `[{name, draft, assets: [asset names]}]`, parsed by the same function as the app's listing (`tag_name`, `draft`, `assets[].name`) |
| `create(tag, title, notes, files)` | `gh release create <tag> <files…> --title … --notes …` (gh uploads the files before it publishes) |
| `mark_latest(tag)` | `gh release edit <tag> --latest` |
| `delete(tag)` | `gh release delete <tag> --yes --cleanup-tag` |
| `download(tag, pattern, dir)` | `gh release download <tag> --pattern <pattern> --dir <dir>` |

Every call goes through `rag.refresh._run_gh(argv)`, the one function that runs the executable (`CARGOLINT_GH`, else
`gh` on `PATH`); the suite's offline guard replaces it, and the argv test constructs `ReleaseService(run=recorder)`.
`--repo OWNER/NAME` is passed through when given (`--repo` on the `release` calls, the path of the `api` call);
otherwise `gh` uses the checkout's remote (`{owner}/{repo}` in the `api` path). The tests use `FakeReleaseService`,
which implements the same methods in memory.

## The app's fetch (`rag.refresh.fetch_releases`)

```python
def releases_needed(settings, root: Path = ROOT) -> list[str]:        # the kinds whose marker is missing, [] when none
def fetch_releases(settings, root: Path = ROOT) -> FetchResult:       # unpacked: kind → name; failed: kind → reasons
```

Steps, once per server process from `app.load_kb()`, only when `settings.release_repo` is set:

1. `releases_needed`: `ebti` when `store/index_meta.json` is missing, `taric` when `data/taric.jsonl` is missing.
   Nothing missing → return an empty result without any request.
2. For each missing kind, in the order `ebti`, `taric`, the candidates, newest first, at most two:
   - the pin, when set, alone;
   - else the kind's names in the `current` block of the latest release's metadata
     (`LATEST.format(repo=…, asset="metadata.json")`, read once per process with `urllib.request.urlopen`, 30 s
     timeout; the fixed download address of the latest release, no API, no token);
   - else, when that file cannot be read, is not a metadata file, or has no names for the kind, and also when every
     candidate the pointer named has failed in step 3: the names of the kind in the listing (`API.format(repo=…)`,
     read once per process) that are complete (both assets, not a draft) and not yet tried, newest first, at most
     two. So a stale pointer (two runs that overlapped) costs one listing, never the demo.
   - A pointer or listing that cannot be read is logged, not fatal in itself: a kind without any candidate fails as
     below, the message naming both routes.
3. For each candidate until one succeeds: read `metadata.json` from `DOWNLOAD.format(repo, tag, asset)`; check
   `kind`, `release` (equal to the candidate), `archive`, `sha256`; download the archive to a temporary file;
   compare its SHA-256 (case-insensitive); check the entries (data-model §5); unpack, marker last; write the
   release file (data-model §4) with `fetched_at`. A pinned candidate that fails is followed once by the newest
   resolved as without a pin, with the log line `pin <name> not honoured: <reason>`.
4. A kind whose candidates all failed is recorded in `failed` with every candidate and its reason, for example
   `ebti-2026-11-13: the archive's SHA-256 is …, not …; ebti-2026-10-14: the archive could not be downloaded: …`, or
   `no release found: the latest release's metadata could not be read (…); the listing could not be read (…)`.
   `fetch_releases` raises `RefreshError` with that text only for the `ebti` kind; a failed `taric` kind is returned.
5. `app.load_kb()` stops with `st.error("Knowledge base release: ebti: …")` on `RefreshError`; a failed `taric` kind
   goes into `KnowledgeBase.fetch_failures`, `app.main` shows it with `st.error("Knowledge base release: taric: …")`
   above the page, and the app runs without TARIC as it does today when the snapshot is absent.

Guarantees:

- nothing is unpacked before the checksum and the entries are checked; nothing of a failed candidate is written;
- an interrupted unpack leaves the marker missing, so the next start fetches again;
- the normal path reads one small file from a download address and no API; the pointer and the listing are each read
  at most once per process and never when both markers exist;
- the feature-011 fetch runs only when `release_repo` is empty and `demo_store_url` is set, unchanged; when both are
  set the release fetch runs and a log line says the feature-011 settings are ignored.

## The listing's shape

Both the app (the API) and the scripts (`gh api`) read GitHub's release list (`application/json`): a list of objects
with `tag_name`, `draft` and `assets`, each asset with `name`. Other fields are ignored; a missing `draft` reads as
false. One parser serves both. `tests/fixtures/refresh/releases.json` holds one in this shape, with a draft entry.
