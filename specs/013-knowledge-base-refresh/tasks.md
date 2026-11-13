---

description: "Task list for feature 013, the knowledge base refresh"
---

# Tasks: Knowledge Base Refresh

**Input**: Design documents from `specs/013-knowledge-base-refresh/`

**Prerequisites**: plan.md, spec.md (with the clarifications of 2026-11-13 and the fixes after review round 1),
research.md, data-model.md, contracts/refresh-cli.md, contracts/releases.md, contracts/ui.md, quickstart.md.

**Tests**: included and written first, offline. Constitution Principle VII asks this for the deterministic code that
carries guardrails: the fetch's checksum, entry and marker checks, the staleness rule and its limits, retention and
the keep-first selection. No test reaches the EU sources, GitHub or OpenRouter (spec FR-025): the fixtures are
recorded, the embeddings and the release service are fakes, the archives come from `file:` URLs, and the suite's
offline guard, extended in Phase 2, refuses the `gh` runner, the loader's download and non-`file:` URLs in every
test that misses a fake.

**Organization**: tasks are grouped by user story (US1 the TARIC refresh, US2 the EBTI refresh, US3 the app's fetch,
US4 what the clerk sees, US5 the workflow). Every file created or changed here is LF; the CRLF files named in
CLAUDE.md are not touched. The author's real runs (publishing, spending credits, the demo switch) are listed at the
end and are not part of these tasks. The tasks were renumbered after review round 1; the mapping is at the end.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task). The tasks that add classes to
  one file (tests/unit/test_refresh.py: T005, T010, T015, T030) are not `[P]`: they are written one after another.
- **[Story]**: the user story the task belongs to

---

## Phase 1: Setup

- [ ] T001 Record the fixtures in tests/fixtures/refresh/ by hand, never by a test: `tot_listing.html`, the
  `xml/tot/` index of distr.tullverket.se as served on the day this task runs (fetched once with curl; the folder
  holds one batch at a time, so the state of 2026-11-13, batch `e14b8e06-f3f6-4ce1-ba9b-1423d07f6b83`, 261102, 38
  files, can be recorded only until the next batch replaces it, about early December, and a later batch is as good),
  with `tot_listing.json` noted from the same page: `batch`, `snapshot_date`, `files`, `recorded_on`; and
  `releases.json`, a release listing in GitHub's shape (`tag_name`, `draft`, `assets[].name`) with
  `ebti-2026-11-01`, `ebti-2026-10-14` and `taric-2026-11-02` complete, `demo-store-v1` with its one zip, and a
  draft `taric-2026-11-03` with the archive only (incomplete)
- [ ] T002 [P] Add `FakeReleaseService` to tests/fakes.py: releases held in memory (name → asset names, draft flag,
  files), the calls `check`, `list` (the listing shape of contracts/releases.md), `create`, `mark_latest`, `delete`
  and `download` recorded in order, archives served from a folder; `check` can be told to fail (not installed, not
  signed in) and any other call can be told to fail at its turn, as a `gh` error would

---

## Phase 2: Foundational (blocks every story)

- [ ] T003 [P] Tests in tests/unit/test_settings.py: `release_repo`, `ebti_release` and `taric_release` read from
  `CARGOLINT_RELEASE_REPO`, `CARGOLINT_EBTI_RELEASE` and `CARGOLINT_TARIC_RELEASE`, empty by default; `ebti_rulings`
  read from `CARGOLINT_EBTI_RULINGS`, `"5000"` by default, `"all"` and a positive integer accepted, `"0"` and
  `"many"` raising `ValueError`; a pin that does
  not match its kind's name pattern (`ebti-latest`, `taric-2026-13-01`, an EBTI name in the TARIC pin) raises
  `ValueError` in `load_settings`; `TARIC_STALE_DAYS == 40` and `EBTI_STALE_DAYS == 45`
- [ ] T004 `agent/config.py`: the four settings in `Settings` (the three release ones empty by default, `ebti_rulings`
  `"5000"`), the pin and ruling-count checks in `load_settings`,
  and the constants `TARIC_STALE_DAYS = 40` and `EBTI_STALE_DAYS = 45` with the comment that fixes "older than" as
  age > limit
- [ ] T005 Tests in tests/unit/test_refresh.py, class `TestReleases`, for the shared pieces of rag/refresh.py:
  `parse_release_name` (`ebti-2026-11-01` → kind and date; `demo-store-v1`, `ebti-latest` and `taric-2026-13-01` →
  none); `parse_listing` on tests/fixtures/refresh/releases.json (names, asset names, the draft flag; a missing
  `draft` reads as false); `is_complete` (both assets and not a draft); `names_of_kind` newest first by the date in
  the name, not by listing order, complete ones only when asked; `prune` on the fake service keeps the two newest
  complete of the kind, deletes the older ones and the incomplete ones with their tags, and never touches the other
  kind, `demo-store-v1` or a name that does not match; `current_block` from a listing plus the release about to be
  published; `write_metadata` and `read_metadata` (data-model §2: the fields, `current`, the EBTI-only counts; a
  file without `kind`, `release`, `archive` or `sha256` is refused); `pack_entries` (the entries given, their order,
  the SHA-256 and size returned); `publish` on the fake service: creates then marks latest, deletes an incomplete
  release of the name first, with `force` deletes the complete one and creates afresh (never an upload), raises
  without `force` on a complete one; a failing `create`, `mark_latest` or `delete` in `publish`, or a failing
  `delete` in `prune`, raises `RefreshError(exit_code=3)` whose message names the step, the release and what was
  done before it. Class `TestReleaseService`, with `ReleaseService(run=recorder)` so no `gh` runs: the argv of
  `list` (`gh api repos/<repo>/releases?per_page=100`, parsed into the listing shape), `create` (files, `--title`,
  `--notes`), `mark_latest` (`release edit <tag> --latest`), `delete` (`--yes --cleanup-tag`), `download`
  (`--pattern`, `--dir`); no `upload` call exists; `--repo` passed through to every call and absent otherwise;
  `CARGOLINT_GH` replacing the executable; `check` raising `RefreshError(exit_code=2)` when the recorder reports
  `gh` missing or `auth status` failing
- [ ] T006 `rag/refresh.py` (standard library and `agent.config` only): `KINDS`, the name pattern, `KEEP_RELEASES`,
  the tables `ARCHIVE`, `METADATA`, `ALLOWED`, `MARKER` and `RELEASE_FILE` (data-model §1, §4, §5),
  `RefreshError(exit_code)`, `parse_release_name`, `parse_listing`, `is_complete`, `names_of_kind`, `sha256`,
  `pack_entries`, `write_metadata`, `read_metadata`, `current_block`, `_run_gh` (the one function that runs the
  executable from `CARGOLINT_GH` or `PATH`), `ReleaseService(repo=None, run=None)` with the calls of
  contracts/releases.md (no `upload`), `publish` (an incomplete release of the name deleted first, the complete one
  on `force`; create; `mark_latest`; a `gh` failure as `RefreshError(exit_code=3)` naming the step) and `prune`
- [ ] T007 Test in tests/unit/test_offline_guard.py: without a fake, `rag.refresh.ReleaseService().check()`,
  `rag.loader.download(url, dest)` and `urllib.request.urlopen("https://example.invalid/")` raise the guard's
  `RuntimeError` ("offline test") before anything runs or connects, and `urllib.request.urlopen` of a `file:` URL
  still works
- [ ] T008 tests/conftest.py: `_offline` also replaces `rag.refresh._run_gh`, `rag.loader.download` and
  `urllib.request.urlopen` (every scheme but `file:`) with the refusing function; the refresh modules call these
  through their modules, so the replacement is seen
- [ ] T009 [P] .gitignore: `data/taric_release.json` and `data/bti_subset.meta.json` under the knowledge-base rules

**Checkpoint**: T003, T005 and T007 green; with the four settings at their defaults nothing changes.

---

## Phase 3: User Story 1 - The maintainer refreshes the TARIC snapshot with one command (Priority: P1) 🎯 MVP

**Goal**: one command finds the newest complete full extract, loads it as `--taric` does, publishes `taric-<date>`
with its metadata and marks it latest, keeps two complete releases, and says "nothing new" when there is nothing new.

**Independent Test**: the command on a generated listing naming the signed fixture batch, with the download copying
from the fixtures and the fake release service.

### Tests for User Story 1

- [ ] T010 [US1] Tests in tests/unit/test_refresh.py, class `TestTotListing`: `parse_listing_html` returns as many
  names as `tot_listing.json` says for the recorded listing, and `current_batch` on them gives the sidecar's batch
  id and snapshot date and the six object files; on generated name lists: two batches where the newer has all six
  objects picks the newer; two batches where the newer lacks an object picks the older complete one; no complete
  batch, or no object file at all, is refused with `RefreshError(exit_code=1)`
- [ ] T011 [US1] Tests in tests/integration/test_refresh_taric.py (skipped without `gpg`, as
  tests/integration/test_taric_loader.py), with the loader's TARIC paths and key monkeypatched into a temporary
  folder as that file's `taric` fixture does (and the repository's `rag.loader.TARIC_RAW_DIR` and `data/taric.jsonl`
  asserted unchanged before and after, as T016 does for `store/bti_docs.jsonl`), `rag.refresh_taric.TOT_URL` pointed
  at a generated listing that names
  the six files of tests/fixtures/taric/extract (batch `11111111-…`, 261001), `rag.loader.download` monkeypatched
  to copy them, the index builders forbidden, and a `FakeReleaseService`:
  - a first run publishes `taric-2026-10-01` with `cargolint-taric-2026-10-01.zip` (one entry, `data/taric.jsonl`,
    equal to the snapshot written) and `metadata.json` (kind, release, snapshot date, `batch 11111111-…, extract
    2026-10-01`, the archive's SHA-256 and size, entries, `current` with both kinds), marks it latest, and prints
    the summary lines of contracts/refresh-cli.md; the fake service's call order shows a `list` immediately before
    the `create` (after the download and the load), and `current` reflects a release the fake adds between the
    "nothing new" check and that second listing;
  - when a complete `taric-2026-10-01`, or a complete `taric-2026-11-02`, exists, the run prints "nothing new",
    downloads nothing, applies retention and re-marks the newest complete TARIC release as latest when the
    repository's latest is older or incomplete (no re-mark when it already is), and exits 0; a listing with an extra
    older TARIC release shows it deleted by this run; with `--force`
    it downloads, rebuilds, deletes `taric-2026-10-01` and creates it afresh (no upload call), and marks the release
    latest;
  - a service whose `create` fails exits 3 with a message naming the create, the release and the remnant deleted
    before it; nothing else is deleted and no prune runs;
  - when `taric-2026-10-01` exists with one asset, or as a draft, the run deletes it and publishes afresh;
  - a refused batch (the tampered file of tests/fixtures/taric/bad) exits 1 and publishes nothing;
  - `TOT_URL` at a `file:` path that does not exist exits 1 before any download; a listing with no complete batch
    exits 1;
  - `--no-publish` builds the archive and metadata without touching the service;
  - a service that is missing or not signed in exits 2 before any download;
  - after publishing with `taric-2026-09-01`, `taric-2026-08-01`, a one-asset `taric-2026-09-15`, `ebti-2026-10-14`
    and `demo-store-v1` present, only `taric-2026-10-01` and `taric-2026-09-01` remain of the TARIC kind and the
    others are untouched

### Implementation for User Story 1

- [ ] T012 [US1] `rag/refresh_taric.py`: `TOT_URL`, `read_listing(url)` with `urllib.request.urlopen` through the
  module (unreadable → `RefreshError(exit_code=1)`), `parse_listing_html(html)`, `current_batch(names)` using the
  `_FILE` pattern of rag/taric_extract.py (the newest complete batch), `download_batch(url, files, folder)` with
  `rag.loader.download` looked up on the module into `<rag.loader.TARIC_RAW_DIR>/<date>/` (the constant read at
  call time), and `main(argv, service=None)`
  following contracts/refresh-cli.md: the option and service checks, the listing, the "nothing new" check against
  the newest complete release, the download, `rag.loader.load_taric(folder, force)` with its exit codes passed
  through, `pack_entries`, the listing re-read immediately before the metadata is written, the metadata with
  `current`, `publish` (`force` deletes and recreates), `prune`, exit 3 for a service failure after the build, the
  summary; messages start with `TARIC refresh`
- [ ] T013 [US1] `scripts/refresh_taric.py`: the entry point (the repository root on `sys.path`,
  `sys.exit(rag.refresh_taric.main())`)

**Checkpoint**: User Story 1 works on its own; the first real run is the author's step.

---

## Phase 4: User Story 2 - The maintainer refreshes the EBTI rulings with one command (Priority: P1)

**Goal**: one command downloads the extract into `build/`, reuses the previous store's vectors, embeds only new and
changed rulings, builds the store in a work folder in demo-store-v1's layout, publishes `ebti-<date>` marked latest,
keeps two complete releases.

**Independent Test**: the command in a temporary folder on a tiny extract, a tiny previous store, fake embeddings
and the fake release service.

### Tests for User Story 2

- [ ] T014 [P] [US2] Tests in tests/unit/test_demo_store.py, class `TestSelection`: `select_rulings(..., keep=…)`
  puts the kept rulings first within each code; the bound `n` holds with `keep` larger than a code's share; `all`
  keeps every valid ruling with text; a kept
  reference absent from the records is not chosen; a kept ruling leaves when its code's share falls; the same
  records, keep set and seed give the same choice; the existing tests pass unchanged with `keep=None`. Class
  `TestCopyVectors`: `copy_vectors(..., metadatas=…)` writes the given metadata (a changed `code`) with the copied
  vectors and documents, and copies the source's metadata when none is given
- [ ] T015 [US2] Tests in tests/unit/test_refresh.py, class `TestEbtiPieces`: `extract_date` is the date of the
  newest `.csv` entry's timestamp, non-csv entries are ignored, a zip without a csv is refused; `partition` sends a
  chosen ruling with the previous record's text to reuse, with its metadata built from the new record (so a changed
  code is in the reuse set with the new code), one with a changed description or reasoning to embed, a new one to
  embed, and counts the previous rulings not chosen as dropped; `check_previous` refuses a store that lacks a file
  of the layout, another `embedding_model`, another `nomenclature_chunks` count or another `edition_year` with a
  message naming `--full-embed` for the last three, and accepts a matching store
- [ ] T016 [P] [US2] Tests in tests/unit/test_loader.py: `build_bti` on a tiny extract zip (`rag.loader.STORE_DIR`,
  `RAW_DIR`, `BTI_SUBSET` and `SUBSET_META` all monkeypatched into a temporary folder and `store_dir=tmp_path /
  "store"` passed as well, since `build_bti` writes `bti_docs.jsonl` into its store folder whatever else is patched
  and the guard does not cover file writes; `rag.loader.download` monkeypatched to copy the zip) returns the store
  and the extract's date, writes `bti_docs.jsonl` into the temporary store only (the repository's
  `store/bti_docs.jsonl`, when present, is byte-identical before and after) and writes `data/bti_subset.meta.json`
  (`extract_date`, `source_version`, `cut_at`); a second call that reuses the subset returns the sidecar's date
  without the zip; no sidecar → `None`; the `demo` path, with `BTI_DEMO` patched too → `None`; `read_release_files(root)` gives `{"ebti": …, "taric": …}` from the two
  release files, `None` for a missing one; `KnowledgeBase.rulings_date` on a constructed knowledge base (as
  tests/ui/harness.make_kb builds one) for an extract date, a build date only, and neither;
  `KnowledgeBase.fetch_failures` is empty by default
- [ ] T017 [US2] Tests in tests/integration/test_refresh_ebti.py on a tiny extract (one csv of rows in the
  loader's column names, as tests/unit/test_loader.py builds them, entry timestamps at the wanted date, written as a
  zip), a tiny previous store (the `full_build` pattern of tests/unit/test_demo_store.py: `chroma/` files,
  `bm25.pkl`, `index_meta.json` with `embedding_model` `fake-hash-8`, a `chroma-bti` collection of 8-dimensional
  vectors, `bti_docs.jsonl`), `FakeEmbeddings(dim=8)` injected through `main(argv, embeddings=…)`, the settings'
  `embed_model` set to `fake-hash-8`, the repository's `store/`, `data/bti_subset.jsonl` and `data/raw/`
  monkeypatched to paths that must stay untouched, `rag.refresh_ebti.EXTRACT_ZIP` and the default work folder
  pointed into the temporary folder, and a `FakeReleaseService`:
  - a run with `--extract`, `--previous <folder>` and `--out <new folder>` writes `<out>/store/` with `chroma/` and
    `bm25.pkl` byte-identical to the previous store's, `chroma-bti` holding the kept rulings' vectors unchanged plus
    the new ones, a kept ruling whose code changed carrying the new code in its metadata, `bti_docs.jsonl`, and
    `index_meta.json` with `embedding_model`, `dimension`, `nomenclature_chunks` and `edition_year` equal to the
    previous store's, `built_at` of this run, `bti_rulings` the new count, `embedding_usage` of this run, no
    `demo_store` block, `ebti_snapshot_date`, `ebti_source_version` and the `refresh` block; the fake embeddings saw
    only the new and changed rulings; the expired and withdrawn rulings are absent; the archive holds `store/…`
    only; `metadata.json` carries the counts and `current`; the release is marked latest;
  - without `--extract`, with `rag.loader.download` monkeypatched to a recorder that copies the tiny zip: an existing
    `EXTRACT_ZIP` and its `.part` are removed before the download and the download is asked for once;
  - a complete `ebti-<date>`, or a complete newer EBTI release, already published: "nothing new", exit 0, the
    previous store not read, nothing embedded, retention applied and the newest complete EBTI release re-marked as
    latest when the repository's latest is older or incomplete (a listing with an extra older EBTI release shows it
    deleted), and the same exit 0 with the
    default work folder left non-empty from an earlier run (the folder is checked only when there is something to
    build); an incomplete
    `ebti-<date>` is deleted and published afresh; `--force` rebuilds, deletes the release and creates it afresh
    (no upload call); the fake service's call order shows a `list` immediately before the `create`, after the
    build, and `current` reflects a release the fake adds after the "nothing new" check; a service whose `create`
    fails exits 3 naming the step and what was deleted before it;
  - a previous store of another model: exit 2 naming `--full-embed`; a previous store missing `chroma-bti/` or
    `bti_docs.jsonl`: exit 2 before any embedding call; with `--full-embed` every nomenclature chunk and chosen
    ruling is embedded by the injected `FakeEmbeddings` (which reach `build_indexes` through its `embeddings`
    parameter; no `OpenRouterEmbeddings` is built, the guard would refuse it) and nothing is copied;
  - no previous store and no `--full-embed`: exit 2 naming `--previous demo-store-v1` and `--full-embed`;
  - `--previous <release>` downloads the release through the service into `<out>/previous/` and verifies it against
    its metadata; `demo-store-v1` (no metadata) is unpacked as it is with a note;
  - the default work folder left non-empty: exit 2 naming it, `--force` and `--out`; with `--force` it is emptied
    and the run goes on; a non-empty folder given with `--out` is refused with and without `--force`; a missing key
    exits 2 before any download;
  - retention keeps the two newest complete EBTI releases, deletes an incomplete one, and touches no other name

### Implementation for User Story 2

- [ ] T018 [US2] `rag/demo_store.py`: `select_rulings(records, preferred_hs6, n, seed=SEED, keep=None)`, the kept
  references first within each code before the seeded shuffle of the others; `copy_vectors(source_dir, target_dir,
  ids, metadatas=None)`, the given metadata (id → dict) written in place of the source's; everything else unchanged
- [ ] T019 [US2] `rag/loader.py`: `SUBSET_META`; `build_indexes(..., store_dir=STORE_DIR, embeddings=None)`, which
  builds `OpenRouterEmbeddings` only when none is given and reads the dimension with `getattr(emb, "dimension",
  None)` before the probe (`FakeEmbeddings` has none); `build_bti(demo, chapters, force=False, store_dir=STORE_DIR)`
  writes `bti_docs.jsonl` into `store_dir` and returns the store and the extract's date (read from the newest csv entry when it cuts the subset and written with the source
  version to `data/bti_subset.meta.json`; read from the sidecar when it reuses the subset; `None` without one or for
  `--demo`) and `main` writes `ebti_snapshot_date` and `ebti_source_version` into the index metadata when known;
  `read_release_files(root)`; `KnowledgeBase.rulings_date` (data-model §3), `KnowledgeBase.releases` read by
  `open_knowledge_base`, and `KnowledgeBase.fetch_failures` (empty by default)
- [ ] T020 [US2] `rag/refresh_ebti.py`: `EXTRACT_URL`, `EXTRACT_ZIP`, `DEFAULT_RULINGS`, the ruling count from
  `load_settings().ebti_rulings` overridden by `--rulings` (a positive integer or `all`; invalid → exit 2),
  `download_extract` (the
  file and its `.part` removed first, `rag.loader.download` looked up on the module), `extract_date`,
  `previous_store(spec, service, work)`, `check_previous` (the layout, the model, the nomenclature), `partition`,
  `build_store` (reuse: copy `chroma/` and `bm25.pkl`, `rag.demo_store.copy_vectors(..., metadatas=…)` for the
  reused rulings with metadata from `BTIStore.chunk_texts` of the new records, `ChromaVectorSearch(out /
  "chroma-bti", emb, "bti").add` for the rest, `bti_docs.jsonl`, the index metadata of data-model §3;
  `--full-embed`: `rag.loader.build_indexes(..., store_dir=out / "store", embeddings=emb)` with the embeddings
  `main` was given), the work-folder rule (checked after the "nothing new" check; `--force` empties the default
  folder only), the listing re-read immediately before the metadata is written, and `main(argv, embeddings=None,
  service=None)` following contracts/refresh-cli.md with its exit codes (3 for a service failure after the build)
  and summary; with `all`, every valid ruling with text is chosen and `rulings_requested` is `"all"`; messages start
  with `EBTI refresh`
- [ ] T021 [US2] `scripts/refresh_ebti.py`: the entry point

**Checkpoint**: User Stories 1 and 2 publish the two kinds; the first real EBTI run from `demo-store-v1` is the
author's step.

---

## Phase 5: User Story 3 - The demo fetches the newest releases at a cold start and falls back (Priority: P1)

**Goal**: with the repository setting set and a marker missing, the app reads the latest release's metadata as the
pointer (the listing only when the pointer is unusable), fetches the newest complete release of each kind or the
pinned one, verifies it before unpacking, falls back once, opens without TARIC when only TARIC fails, and leaves the
feature-011 path untouched.

**Independent Test**: `LATEST`, `API` and `DOWNLOAD` pointed at `file:` URLs over a temporary folder of releases;
AppTest for the app's start.

### Tests for User Story 3

- [ ] T022 [P] [US3] Tests in tests/unit/test_release_fetch.py with `rag.refresh.LATEST`, `rag.refresh.API` and
  `rag.refresh.DOWNLOAD` monkeypatched to `file:` templates over a temporary folder holding, per release,
  `metadata.json` and the archive, a latest-release `metadata.json` with a `current` block, and a listing in the
  shape of tests/fixtures/refresh/releases.json:
  - `releases_needed` names the kinds whose marker is missing; with both present nothing is read, not even the
    pointer;
  - with a usable pointer the candidates of each kind are its `current` names, newest first, and the listing is
    never read (the `API` file may be absent);
  - with the pointer unreadable, not a metadata file, or without names for a kind, the listing is read once and the
    newest complete of the kind is chosen by the date in the name, not by listing order, skipping a draft and a
    release missing an asset;
  - a pin is fetched by its name with the pointer and the listing both unreachable;
  - a bad checksum, an unreachable archive and metadata without the required fields each fall back to the next
    newest; a pinned release that fails falls back once to the newest resolved as without a pin, and the log holds
    `pin <name> not honoured`;
  - both EBTI candidates failing raises `RefreshError` naming each with its reason; both TARIC candidates failing
    with the EBTI kind fetched returns `FetchResult` with `failed["taric"]` naming each and raises nothing;
  - a stale pointer: its `current` names releases of a kind that are missing or fail their checksum while the
    listing holds a good complete one; after the pointer's candidates fail the listing is read once and the newest
    complete release not yet tried is fetched, for the EBTI and for the TARIC kind;
  - no pin, pointer and listing both unreadable: the EBTI kind raises `RefreshError` naming both routes and their
    reasons; the TARIC kind, with the EBTI kind present, is returned in `failed` with the same text;
  - an entry outside the kind's paths and a `..` entry are refused before anything is written;
  - `data/taric.jsonl` is written through `.tmp` and renamed, `store/index_meta.json` is the last entry unpacked
    (an interrupted unpack leaves no marker);
  - `store/release.json` and `data/taric_release.json` hold the metadata plus `fetched_at`;
  - the pointer and the listing are each read at most once for two missing kinds;
  - tests/unit/test_demo_store.py's fetch tests pass unchanged
- [ ] T023 [P] [US3] Tests in tests/ui/test_app_navigation.py: with `release_repo` set, a pointer whose only EBTI
  release fails its checksum stops the app with one error starting "Knowledge base release: ebti:" and opens no
  knowledge base; with the EBTI release good and every TARIC candidate failing, the app opens, `at.error` holds one
  message starting "Knowledge base release: taric:" and the Origin box reads "TARIC not loaded"; with `release_repo`
  and `demo_store_url` both set, the release fetch runs, the feature-011 fetch is not called and the log holds the
  note; with `release_repo` empty and `demo_store_url` set, the existing demo-store test still passes

### Implementation for User Story 3

- [ ] T024 [US3] `rag/refresh.py`: `LATEST`, `API`, `DOWNLOAD`, `FetchResult`, `releases_needed`, `_read_pointer`,
  `_read_listing` (each once per process, `urllib.request.urlopen` through the module), `fetch_release(repo, kind,
  name, root)` (metadata, archive to a temporary file, SHA-256, entries, unpack with the marker last, the release
  file) and `fetch_releases(settings, root)` (the candidates in the order of contracts/releases.md, the fallback,
  the listing after every pointer-named candidate failed, the pin's fallback with its log line, the collected
  failures naming the routes, `RefreshError` for the EBTI kind only)
- [ ] T025 [US3] `app.py`: in `load_kb()`, `fetch_releases` with a spinner when `settings.release_repo` is set (a
  log note when the feature-011 settings are set too), else the feature-011 fetch as today; `RefreshError` →
  `st.error(f"Knowledge base release: {exc}")` and stop; a failed TARIC kind kept in `kb.fetch_failures`; in
  `main()`, one `st.error("Knowledge base release: taric: …")` per entry above the page, the app going on

**Checkpoint**: a fresh clone with the repository setting opens from the releases; the current demo's secrets still
work; the demo switch itself waits for both kinds to be published (the author's step).

---

## Phase 6: User Story 4 - The clerk sees how current each part is (Priority: P2)

**Goal**: the Origin box shows both dates and a yellow warning when a part is older than its limit; Admin › Data
shows the dates, the source versions and the releases in use.

**Independent Test**: AppTest on fake knowledge bases with chosen dates and a fixed today.

### Tests for User Story 4

- [ ] T026 [P] [US4] Tests in tests/unit/test_view.py on small fakes: `snapshot_caption` with both dates, with
  "TARIC not loaded", with "EBTI rulings built <date>" and with "date unknown"; `freshness_warning(kb, today)` is
  None at 40 and 45 days, the TARIC text at 41, the EBTI text at 46, both texts in one warning when both are old,
  the "age unknown" text for an unparsable date and for a date in the future (shown as recorded, age unknown), no
  TARIC part when TARIC is not loaded; `rulings_statement`, `taric_statement` with the batch id,
  `release_statement` with one, two and no release files (contracts/ui.md)
- [ ] T027 [P] [US4] tests/ui/harness.py: `make_kb(taric=…, meta=None, releases=None)` so a test can set the
  dates and the release files; tests/ui/test_main_page.py: the caption with both dates in the Origin box, an
  `at.warning` with the expected text when a part is old (today injected through `view.freshness_warning`), none
  when both are fresh, the existing frame test updated to the new caption; tests/ui/test_admin_page.py: the Data
  lines with and without release files, `test_data` updated

### Implementation for User Story 4

- [ ] T028 [US4] `ui/view.py`: `snapshot_caption`, `freshness_warning(kb, today=None)` with the two constants of
  agent/config.py, `rulings_statement`, `release_statement`, the batch id in `taric_statement`, the extract date in
  `kb_statement`'s `updated` when present
- [ ] T029 [US4] `ui/main_page.py::_header`: `st.warning` under the two captions inside the Origin box's vertical
  sub-container when `freshness_warning` returns a text; `ui/admin.py::_data`: the statements of contracts/ui.md,
  the "Refresh (later)" button unchanged

**Checkpoint**: tests/unit/test_native_ui.py still green; the demo-store-v1 store shows its build date.

---

## Phase 7: User Story 5 - The schedules exist but stay off until switched on (Priority: P3)

### Tests for User Story 5

- [ ] T030 [US5] Tests in tests/unit/test_refresh.py, class `TestWorkflow`, on `yaml.safe_load` of
  .github/workflows/refresh.yml (PyYAML is installed with chromadb; the `on` key loads as the boolean `True`): the
  two crons (`30 5 * * *`, `0 6 1 * *`), `workflow_dispatch` with the `kind` choice (`taric`, `ebti`, `both`), the
  jobs `taric` and `ebti`, `vars.CARGOLINT_REFRESH == 'on'` and `github.event.schedule` inside each job's `if`,
  `needs: taric` on the `ebti` job and `!cancelled()` at the front of its `if`, `permissions` with `contents:
  write`, `concurrency`, the checkout step with `persist-credentials: false` in both
  jobs, the two script commands, `OPENROUTER_API_KEY` in the `ebti` job's `env` and not in the `taric` job's,
  `timeout-minutes` in both, and the 60-day comment at the top of the file

### Implementation for User Story 5

- [ ] T031 [US5] `.github/workflows/refresh.yml` per contracts/refresh-cli.md: the comment on the 60-day
  auto-disable, the schedules, the manual trigger, the switch on both scheduled jobs, the per-cron gate, `needs:
  taric` with `!cancelled()` on the `ebti` job, checkout with `persist-credentials: false`, Python 3.13, `pip install
  -e .`, the two scripts with `GH_TOKEN` and, for `ebti`, the `OPENROUTER_API_KEY` secret

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T032 [P] README.md: the "Knowledge base refresh" section (spec FR-024: the two commands and their options
  including `--repo` and `CARGOLINT_GH`, the releases, completeness, retention, the metadata file and the
  latest-release pointer, the exit codes including 3, the four settings, the switch from the feature-011 secrets
  once both kinds are published, a pin lasting only while retention keeps its release, the warning limits, the
  workflow switch, the rule that the scripts are run by hand only while the schedule is off or after checking the
  Actions tab, and the 60-day auto-disable) and the "Demo deployment" section updated to the repository setting;
  `scripts/` and `refresh*` in the repository layout
- [ ] T033 [P] .env.example: `CARGOLINT_RELEASE_REPO`, `CARGOLINT_EBTI_RELEASE`, `CARGOLINT_TARIC_RELEASE` and
  `CARGOLINT_EBTI_RULINGS` with one-line comments (spec FR-024)
- [ ] T034 [P] tests/eval/e2e_eval.py: `--as-of YYYY-MM-DD`, the rulings' validity date (default: the set's
  `built_on`), recorded in the history entry and the report; a test in tests/unit/test_e2e_eval.py that the default
  is the set's build date and that a given date is used and recorded (spec SC-003, research R-14)
- [ ] T035 `pytest -q`, offline, green; every touched file checked for LF (`git ls-files --eol`)
- [ ] T036 Hand over quickstart.md's "author's real runs" list: the first TARIC and EBTI runs (SC-001, SC-002), the
  eval comparison with `--as-of` and `--repeat 3` (SC-003), the demo switch once both kinds exist (SC-005), the
  release check (SC-007). Not run in this feature.

---

## Not in this feature: the author's steps

- Run `python scripts/refresh_taric.py` and `python scripts/refresh_ebti.py --previous demo-store-v1` for the first
  time, timed (SC-001, SC-002), and check the releases with `gh release list` (SC-007: at most two of a kind, all
  complete, the one published last marked Latest).
- Run the end-to-end evaluation against the refreshed store and against `demo-store-v1`, three repeats each with
  `--as-of` the run day, in one session (SC-003, about $1.60).
- Switch the Community Cloud secrets to `CARGOLINT_RELEASE_REPO` and reboot the demo (SC-005), only once both kinds
  are published.
- Set the repository variable `CARGOLINT_REFRESH` to `on` when the schedules should start, and the
  `OPENROUTER_API_KEY` repository secret for the `ebti` job; re-enable the schedules from the Actions tab when
  GitHub has disabled them after 60 quiet days.

## Dependencies & Execution Order

- T001 and T002 come first; T003 (tests) before T004; T005 (tests) before T006; T004 before T006, T024, T025 and
  T028; T006 before T007 and T008 (the guard replaces `rag.refresh._run_gh`); T007 before T008; T008 before every
  test that calls a script's `main` or the fetch (T011, T017, T022, T023).
- Each story's tests come before its implementation: T010–T011 before T012–T013; T014–T017 before T018–T021;
  T022–T023 before T024–T025; T026–T027 before T028–T029; T030 before T031. A test task is written first and fails
  until its implementation task; T023's app test passes after T025.
- T006 comes before T012, T020 and T024. T018 and T019 come before T020. T019 (`KnowledgeBase.rulings_date`,
  `releases`, `fetch_failures`) comes before T025 and T028.
- T005, T010, T015 and T030 add classes to tests/unit/test_refresh.py and are written one after another; every
  other test task is in its own file.
- US1, US2 and US3 are independent of each other after Phase 2; US4 needs T019; US5 is independent.
- T032–T036 come last.

## Parallel Example: after Phase 2

```text
Own files, in parallel:  T014 (test_demo_store), T016 (test_loader), T022 (test_release_fetch),
                         T023 (test_app_navigation), T026 (test_view), T027 (the ui tests)
One after another:       T010, T015, T030 (the classes of test_refresh.py), then T011 and T017
```

## Implementation Strategy

1. Phase 1 and Phase 2: the fixtures, the fake service, the settings, the shared release module, the extended
   offline guard, `.gitignore`.
2. US1 (TARIC) end to end: the smallest publishable release; validate with its tests and, when the author asks,
   the first real run.
3. US2 (EBTI) next, then US3 (the app's fetch): the demo switch needs both kinds published, since the release
   fetch replaces the feature-011 archive for both parts, and a pin cannot name `demo-store-v1`.
4. US4 (the clerk's view) once the knowledge base object carries the dates; US5 (the workflow) at any time.
5. Polish, the full offline suite, the hand-over of the author's steps.

## Renumbering after review round 1

Old → new: T001 → T001, T002 → T002, T003 → T005, T004 → T004, T005 → T006, T006 → T010, T007 → T011, T008 → T012,
T009 → T013, T010 → T014, T011 → T015, T012 → T017, T013 → T018, T014 → T019, T015 → T020, T016 → T021, T017 → T022,
T018 → T023, T019 → T024, T020 → T025, T021 → T026, T022 → T027, T023 → T028, T024 → T029, T025 → T030, T026 → T031,
T027 → T032, T028 → T033, T029 → T035, T030 → T036. New: T003 (the settings tests), T007 (the guard test), T008 (the
guard), T009 (.gitignore), T016 (the loader tests), T034 (the evaluation's `--as-of`).
