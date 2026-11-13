# Implementation Plan: Knowledge Base Refresh

**Branch**: `013-knowledge-base-refresh` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-knowledge-base-refresh/spec.md`, with its four clarifications of
2026-11-13. The source facts (a monthly TARIC full extract, a daily EBTI extract, the `demo-store-v1` release) are in
the spec's Background and in [research.md](research.md).

## Summary

Three new modules under `rag/` carry the logic, and two thin scripts under `scripts/` run it:

- **`rag/refresh.py`** (standard library only, like the fetch path of feature 011): release names and kinds,
  completeness (both assets, not a draft), the metadata file with its `current` block, packing, a `ReleaseService`
  over the `gh` command line tool (the listing through `gh api`, create, upload, mark latest, delete, download) behind
  one runner function that the suite's offline guard replaces, retention of the two newest complete releases, and the
  app's fetch at a cold start: read the latest release's metadata as the pointer to both kinds, else list the
  repository's releases, take the newest complete of each kind or the pinned one, verify the archive against its
  metadata, unpack it, fall back once; a TARIC failure leaves the app running without TARIC.
- **`rag/refresh_taric.py`**: read the Swedish Customs `tot` listing, find the newest complete batch, download its
  six files into a folder of their own, run the existing TARIC load (`rag.loader.load_taric`), pack `data/taric.jsonl`,
  publish `taric-<date>`, prune. No embedding.
- **`rag/refresh_ebti.py`**: download the EBTI full extract into `build/`, read its date, take the previous store (the
  newest complete EBTI release, `demo-store-v1`, or a folder), choose the configured number of rulings (default
  5,000; `all` keeps every valid ruling) with the demo store's rule when a number is used, keeping the previous
  store's rulings first, copy the vectors of unchanged rulings with their metadata rewritten from the new extract,
  embed only new and changed ones, copy the nomenclature index, write the store into a work folder, pack `store/…`,
  publish `ebti-<date>`, prune. `--full-embed` embeds everything afresh.

`app.py` calls the new fetch inside `load_kb()` when `CARGOLINT_RELEASE_REPO` is set, and the feature-011 fetch
otherwise, so the current demo keeps working. A TARIC release that cannot be fetched leaves the app running without
TARIC, with the reason on the page; an EBTI release that cannot be fetched stops it. The Origin box shows both dates
and a native `st.warning` when a part is older than its limit (40 days TARIC, 45 days EBTI, named constants).
Admin › Data names the dates, the source versions and the releases in use. A workflow with two crons stays off until a
repository variable switches it on.

## Technical Context

**Language/Version**: Python 3.11–3.13 (the project's `.venv`; Python 3.13 on Community Cloud and in GitHub Actions)

**Primary Dependencies**: no new package. `requests` (already used by the loader's `download`), `urllib.request`,
`zipfile`, `hashlib`, `subprocess` (for `gh`), `chromadb` 1.5.9 and `langchain_chroma` (already dependencies) for the
vector copy and the embedding of new rulings; Streamlit native elements (`st.caption`, `st.warning`). Two external
tools, as the TARIC loader already needs `gpg`: `gh` (GitHub CLI, signed in on the laptop; preinstalled with the
job's token in Actions) and `gpg`.

**Storage**: as today, `store/` and `data/taric.jsonl`, now unpacked from two releases at a cold start on the cloud;
`build/ebti-<date>/` (git-ignored through the existing `build/` rule) as the EBTI refresh's work folder and
`build/DDS2-EBTI_Full.zip` as its download (the loader's `data/raw/` copy is never touched);
`rag.loader.TARIC_RAW_DIR/<date>/` (normally `data/raw/taric/`, the constant read at call time) for a downloaded batch; `store/release.json` and `data/taric_release.json` for the metadata of the releases in use;
`data/bti_subset.meta.json` for the loader's record of the extract its subset came from. `.gitignore` gains
`data/taric_release.json` and `data/bti_subset.meta.json` (`store/` and `build/` are covered).

**Testing**: pytest, offline. Recorded fixtures: the `tot` listing saved on 2026-11-13, the signed fixture batch of
feature 002 (the TARIC script's end-to-end test needs `gpg` and skips without it, as `test_taric_loader.py` does), a
tiny EBTI extract built as a zip of CSV rows in the test, a tiny previous store with a real Chroma collection of
8-dimensional vectors (the `full_build` fixture pattern of `tests/unit/test_demo_store.py`), `FakeEmbeddings`, a
`FakeReleaseService` that records calls, a release listing in GitHub's JSON shape, and `file:` URLs for the
metadata and archives. The UI is tested through AppTest with `tests/ui/harness.make_kb` extended with dates. The
workflow file is parsed with `yaml.safe_load` (PyYAML 6.0.3 is installed as a dependency of chromadb and
langchain-core; YAML 1.1 reads the `on` key as the boolean `True`), so a test can look inside each job's condition.
The suite's offline guard (`tests/conftest.py`, `_offline`) is extended to the release service's `gh` runner, the
loader's download and any `urlopen` of a non-`file:` URL, with its own test, so that a script test that misses the
fake service or the download copier fails there instead of acting on the maintainer's releases.

**Target Platform**: the maintainer's laptop (Windows, Git for Windows' `gpg`), GitHub Actions (`ubuntu-latest`,
`gh` and `gpg` preinstalled), and Streamlit Community Cloud for the fetch

**Project Type**: the existing single Streamlit project, plus two command-line scripts

**Performance Goals**: TARIC refresh under 10 minutes (34 MB of signed files, a 30 s load, a 2 MB archive); EBTI
refresh under 30 minutes (397 MB extract, the 150 MB previous store, a few hundred embeddings, a 150 MB archive to
pack and upload; estimated 10–15 minutes); the app's cold start adds one small pointer request (the latest
release's metadata, a download address, no API) and a 2 MB TARIC download to today's 150 MB download.

**Constraints**:
- no embedding call in the TARIC refresh; in the EBTI refresh only new and changed rulings are embedded, unless
  `--full-embed`;
- the EBTI refresh never writes `store/` or `data/bti_subset.jsonl`; the TARIC refresh writes only what
  `--taric` writes today;
- the checksum is verified before anything is unpacked; the marker file comes last;
- the app's normal path reads no GitHub API: the pointer and the assets come from the public download addresses;
- nothing changes when the four new settings are unset; the feature-011 settings keep working;
- a test that misses a fake fails in the offline guard before `gh`, a download or a non-`file:` URL is reached; the
  guard does not cover file writes, so no test calls a loader or refresh function against the repository's paths:
  `build_bti` and `build_indexes` take a `store_dir`, and the tests pass a temporary one and monkeypatch
  `rag.loader.STORE_DIR`, `RAW_DIR`, `BTI_SUBSET` and `SUBSET_META` as well;
- native Streamlit, no CSS change (constitution 1.10.0);
- every new file is LF; `tests/integration/test_classify_hs6.py` and the other CRLF files named in CLAUDE.md are not
  touched.

**Scale/Scope**: three new modules in `rag/`, two scripts, two small changes in `rag/demo_store.py` (`keep` in
`select_rulings`, metadata in `copy_vectors`), a few in `rag/loader.py` (the extract date and the subset's sidecar, a
`store_dir` parameter, the release files and `rulings_date` on `KnowledgeBase`), four settings and two constants in
`agent/config.py`, about 20 lines in `app.py`, three functions in `ui/view.py`, a few lines in `ui/main_page.py` and
`ui/admin.py`, one workflow file, a few lines in `tests/conftest.py`, one option in `tests/eval/e2e_eval.py`, two
lines in `.gitignore`, five new test files and additions to seven, three fixture files, the README and
`.env.example`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution 1.10.0.

| Principle | Check | Status |
|---|---|---|
| I. Guardrails live in code | No route, threshold, lock or validation changes. The checksum, path and marker checks of the fetch, the staleness rule and its two limits, and the retention rule are code with named constants (`TARIC_STALE_DAYS`, `EBTI_STALE_DAYS`, `KEEP_RELEASES`); behaviour at exactly a limit is fixed in the spec (no warning) and tested. Every date and release name the UI shows is read from the knowledge base object, which reads it from the data files, never from prose. | Pass |
| II. Untrusted input | The releases are the maintainer's own, published by the maintainer's scripts into the project's repository and read over HTTPS; the archive is verified against the release's metadata before unpacking, only the kind's paths are unpacked, and `..` is refused. The GitHub token exists only in Actions, is not kept in the checkout (`persist-credentials: false`) and is never read by the app, which reads the pointer and the assets from public download addresses; the OpenRouter key stays an environment variable; nothing of either is logged. The scripts read the EU sources as the loader already does (signed TARIC files verified against the pinned key; the EBTI CSV read as data). | Pass |
| III. Grounded, cited | Rulings keep their texts, references, countries and validity; a changed text is embedded again, never served with an old vector. The ruling count is the configured bound (about 5,000 by default, or every valid ruling with `all`), and the demo stays at about 5,000. | Pass |
| IV. Hybrid retrieval | The nomenclature index and BM25 file are copied unchanged from the previous store (or rebuilt with `--full-embed`); the ruling index keeps the same layout. The loader stays scripted and chapter-driven. Admin › Data now states the extract date and source version of the rulings and the TARIC batch, which is what "when it was last updated" means. | Pass |
| V. Typed tools | No tool changes. | Pass |
| VI. Native UI that shows its work | `st.caption` and `st.warning` in the Origin box, `st.markdown` lines in Admin › Data; no CSS, no HTML. The UI Design Contract's Origin box and Data section gain content and lose nothing, so no amendment is needed. | Pass |
| VII. Test-first | The fetch's checks, the staleness rule, retention and the keep-first selection are guardrail-like deterministic code: their tests come first and run offline on recorded fixtures. The offline guard of the suite is extended (the `gh` runner, the download, non-`file:` URLs) and tested, so no test can act on a live source or on the maintainer's releases. The live steps (the first real runs, the eval comparison) are the author's and are listed as such. | Pass |
| Architecture: dependencies and testability | Logic sits in `rag/`, imports no Streamlit, and is driven by `scripts/` and `app.py`; the app fetch imports the standard library and `agent.config` only. | Pass |
| Technology stack | No new package. `gh` is an external tool like `gpg`, with the same kind of path override (`CARGOLINT_GH`). | Pass |
| Out of scope for the MVP | Nothing is sent to a shipper or to customs; no accounts; no persistence beyond the session. | Pass |

**Post-design re-check**: unchanged. The design adds no dependency and no tool, changes no routing, and keeps the
demo's size.

## Project Structure

### Documentation (this feature)

```text
specs/013-knowledge-base-refresh/
├── spec.md              # the feature specification, with the clarifications of 2026-11-13
├── plan.md              # this file
├── research.md          # Phase 0: the source facts and the design decisions with their alternatives
├── data-model.md        # Phase 1: the metadata file, index_meta additions, release files, settings, constants
├── quickstart.md        # Phase 1: how to validate the feature offline and in the author's real runs
├── contracts/
│   ├── refresh-cli.md   # the two commands: options, steps, exit codes, output
│   ├── releases.md      # release names, assets, archive entries, metadata, the app's fetch and retention
│   └── ui.md            # the Origin box captions and warning, Admin › Data lines
├── checklists/
│   └── requirements.md  # the spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
scripts/
├── refresh_taric.py     # new: thin entry point → rag.refresh_taric.main
└── refresh_ebti.py      # new: thin entry point → rag.refresh_ebti.main
rag/
├── refresh.py           # new: kinds, names, metadata, pack_entries, ReleaseService (gh), publish, prune,
│                        #      fetch_releases / fetch_release for the app (standard library only)
├── refresh_taric.py     # new: the tot listing, current_batch, download_batch, main
├── refresh_ebti.py      # new: extract_date, previous_store, check_previous, partition, build_store, main
├── demo_store.py        # select_rulings(..., keep=None): the previous store's rulings first within each code;
│                        #      copy_vectors(..., metadatas=…) for the reused rulings' new metadata
└── loader.py            # build_bti(store_dir=…) returns the extract date and writes data/bti_subset.meta.json;
                         #      build_indexes(store_dir=…, embeddings=…), the new meta fields,
                         #      KnowledgeBase.rulings_date, releases and fetch_failures
agent/
└── config.py            # Settings.release_repo, ebti_release, taric_release; TARIC_STALE_DAYS, EBTI_STALE_DAYS
app.py                   # load_kb(): fetch_releases when the repository setting is set, else the feature-011 fetch;
                         #      a TARIC failure shown with st.error, an EBTI failure stops
.gitignore               # data/taric_release.json, data/bti_subset.meta.json
ui/
├── view.py              # snapshot_caption (both dates), freshness_warning, rulings_statement, release_statement
├── main_page.py         # the warning under the captions of the Origin box
└── admin.py             # Data: the new statements
.github/workflows/
└── refresh.yml          # new: the two scheduled jobs, the manual trigger, the switch
tests/
├── conftest.py                  # _offline extended: the gh runner, rag.loader.download, non-file: urlopen
├── fixtures/refresh/
│   ├── tot_listing.html         # new: the tot folder listing recorded by hand when T001 runs (one batch at a time)
│   ├── tot_listing.json         # new: what that listing holds (batch, snapshot date, file count, recorded on)
│   └── releases.json            # new: a release listing in GitHub's JSON shape, five entries including a draft
├── unit/
│   ├── test_offline_guard.py    # the extended guard: the runner, the download and a non-file: URL are refused
│   ├── test_settings.py         # new: the four settings, a pin of the wrong shape, an invalid ruling count, the two constants
│   ├── test_refresh.py          # new: names, completeness, retention, metadata with current, pack_entries, the
│   │                            #      service's argv, the listing parser, extract_date, partition, the workflow
│   ├── test_release_fetch.py    # new: the app's fetch: pointer, listing, pin, fallbacks, checksum, paths, markers
│   ├── test_loader.py           # build_bti's date and sidecar, the release files, rulings_date, fetch_failures
│   ├── test_view.py             # snapshot_caption, freshness_warning at and past the limits, the statements
│   ├── test_e2e_eval.py         # the --as-of option of the evaluation
│   └── test_demo_store.py       # select_rulings with keep; copy_vectors with metadata
├── integration/
│   ├── test_refresh_taric.py    # new: the TARIC script end to end on the signed fixtures (skips without gpg)
│   └── test_refresh_ebti.py     # new: the EBTI script end to end on a tiny extract and previous store
└── ui/
    ├── harness.py               # make_kb(..., meta=…, releases=…) for dates and releases
    ├── test_main_page.py        # the Origin box's two dates and the warning
    ├── test_admin_page.py       # Data: dates, source versions, releases
    └── test_app_navigation.py   # an EBTI fetch that fails stops the app; a TARIC failure opens without TARIC;
                                 #      the legacy path still runs
tests/eval/e2e_eval.py           # --as-of: the validity date of the rulings (default: the set's build date)
README.md                        # "Knowledge base refresh"; "Demo deployment" follows
.env.example                     # the four settings
```

**Structure Decision**: the user's brief names the two scripts under `scripts/`, so they exist there, but as entry
points only: `scripts/` is not a package (`pyproject.toml` lists `agent`, `tools`, `rag`, `ui`), and the logic must
be importable and testable without Streamlit (constitution, Architecture). The app's fetch lives in `rag/refresh.py`
next to the publish side, since both share the release layout (names, assets, metadata, allowed entries), as feature
011 put the cut and the fetch of the demo store in one module. `rag/refresh.py` imports only the standard library and
`agent.config`, so `app.py` can import it at start-up; chromadb and the embeddings load only in `rag/refresh_ebti.py`.

## Design decisions

The decisions are recorded with their alternatives in [research.md](research.md); the outline here is what the
tasks build.

1. **Kinds and names.** `KINDS = ("ebti", "taric")`; a release name matches `^(ebti|taric)-(\d{4}-\d{2}-\d{2})$`.
   The archive is `cargolint-<kind>-<date>.zip`, the metadata `metadata.json`. The EBTI archive's entries are under
   `store/`; the TARIC archive has the one entry `data/taric.jsonl`. `demo-store-v1` matches no kind.
2. **Release service.** `rag.refresh.ReleaseService(repo=None)` runs `gh` through one module function,
   `_run_gh(argv)` (`subprocess.run` of `CARGOLINT_GH`, else `gh` on `PATH`), which the suite's offline guard replaces
   and the argv test swaps for a recorder (`ReleaseService(run=…)`). Calls: the listing through `gh api
   repos/<repo>/releases?per_page=100`, which returns the same JSON shape the app reads (`tag_name`, `draft`,
   `assets[].name`), so one parser serves both and the scripts see assets and drafts; `release create <tag> <files>`
   (gh uploads the assets before it publishes the release); `release edit <tag> --latest` after the create, so the
   pointer moves to the release just published; `release delete --yes --cleanup-tag`; `release download`. There is
   no `upload --clobber`: `--force` deletes the release and creates it afresh, so its assets always come from one
   build. `--repo OWNER/NAME` is passed through to every call (`gh api` gets it in the path). `check()` runs `gh auth
   status` before any download. A `gh` failure after the build (create, mark latest, delete, prune) raises
   `RefreshError(exit_code=3)` naming the step and what was done before it. A `FakeReleaseService` in the tests
   records the calls, holds the releases in memory and can be told to fail at a call. `--no-publish` skips the
   service entirely.
3. **Completeness and retention.** A release is complete when it carries both assets and is not a draft; only
   complete releases count for "nothing new" (the newest complete of the kind must be older than the source's date),
   for the `current` block and for the app. `publish` deletes an incomplete release of the name before creating it
   afresh, and with `--force` deletes the complete one before creating it afresh. `prune(service, kind)` lists the
   releases, keeps the two complete releases of the kind with the newest dates in their names and deletes every other
   release of the kind, older or incomplete, tag included. Names that do not match the pattern are ignored.
   `current_block(listing, kind, name)` gives the `current` block from a listing the script reads immediately before
   writing the metadata (after the build and the pack: the "nothing new" listing may be ten minutes old by then)
   plus the release about to be published, with retention applied.
4. **The TARIC listing.** `rag.refresh_taric.current_batch(names)` groups the listing's file names with the
   `_FILE` pattern of `rag/taric_extract.py` (the six objects only), picks the newest date that has all six objects
   with one batch id (an incomplete newer batch is passed over), and raises `RefreshError(exit_code=1)` when no batch
   is complete or no object file is listed. The listing is read with `urllib.request.urlopen` called through the
   module, so the offline guard sees it and tests use a `file:` URL to the recorded listing or a generated one; an
   unreadable listing is `RefreshError(exit_code=1)`. The files are downloaded with `rag.loader.download` looked up
   on the module at call time (resume is right for them: they are immutable and named by their batch) into
   `rag.loader.TARIC_RAW_DIR/<date>/` (the constant read at call time, normally `data/raw/taric/`), which keeps batches
   apart so `discover_extract` never sees two files for one object.
5. **The TARIC load.** The script calls `rag.loader.load_taric(folder, force)` unchanged: it verifies, parses,
   writes `data/taric.jsonl` and the register row, and returns the loader's exit code. The script then reads the
   header with `read_snapshot_header` for the metadata. The snapshot lands in the repository's `data/taric.jsonl`,
   as `--taric` does today, so the local app sees it too.
6. **The EBTI extract.** Downloaded afresh to `build/DDS2-EBTI_Full.zip`, never the loader's `data/raw/` copy, so
   the loader's subset stays consistent with its own download; the file and its `.part` are removed first, since
   `rag.loader.download` reuses an existing file and resumes any `.part`, and the extract is regenerated daily under
   one name (a resumed download would splice two extracts). `--extract <zip>` uses a file as it is. `extract_date` is
   the date of the newest `.csv` entry's timestamp inside the zip; a zip without one is refused.
7. **The previous store.** `--previous` is a release name or a local folder holding `store/`; the default is the
   newest `ebti-*` release. A release is downloaded with the service into the work folder's `previous/` and its
   archive verified against its metadata when it has one (`demo-store-v1` has none: its one zip asset is unpacked as
   it is, with a note). `check_previous` refuses a store that lacks a file of the layout (`index_meta.json`,
   `bm25.pkl`, `chroma/`, `chroma-bti/`, `bti_docs.jsonl`), one whose `embedding_model` differs from the settings' or
   whose `nomenclature_chunks` or `edition_year` differ from the committed nomenclature, naming `--full-embed` for the
   last two; all before any embedding call.
8. **The choice.** `select_rulings(records, preferred, n, keep=previous_references)`: within each code the kept
   rulings come first, then the others in the seeded shuffle; everything else is feature 011's rule, so the store is
   bounded at `n` and a kept ruling leaves only when it is gone from the extract or its code's share falls. `n` is the
   `CARGOLINT_EBTI_RULINGS` setting (default 5000), overridden by `--rulings`; the literal `all` bypasses the bound and
   keeps every valid ruling with text.
9. **Reuse and embedding.** `partition(chosen, previous_docs)` splits the chosen rulings into those whose text
   (description and reasoning) equals the previous store's record, whose vectors are copied with
   `rag.demo_store.copy_vectors(..., metadatas=…)`, the metadata (code, cn_code, chapter, member state, language,
   validity, as `BTIStore.chunk_texts` builds it) written from the new extract's record rather than copied, since
   `tools/classify_cn8.py` filters the collection on `code`; and the rest, embedded with
   `ChromaVectorSearch(out/"chroma-bti", emb, "bti").add`. `chroma/` and `bm25.pkl` are copied from the previous
   store. With `--full-embed`, `rag.loader.build_indexes` runs against the work folder (`store_dir` parameter) with
   the chosen rulings and the embeddings `main` was given (`embeddings` parameter; it builds `OpenRouterEmbeddings`
   itself only when none is given, and reads the dimension with `getattr(emb, "dimension", None)` before the probe,
   since `FakeEmbeddings` has no `dimension`) and copies nothing. The work folder: `--out` must be new or empty,
   checked only after the "nothing new" check so a re-run after a successful run exits 0; `--force` empties the
   default `build/ebti-<date>/` first (a retry after a failed embedding or upload), never a folder given with `--out`.
10. **Index metadata.** `index_meta.json` carries over `embedding_model`, `dimension`, `nomenclature_chunks` and
    `edition_year` from the previous store (they describe the copied nomenclature index), recomputes `built_at`,
    `bti_rulings` and `embedding_usage` for this build, drops the previous `demo_store` and `refresh` blocks, and adds
    `ebti_snapshot_date`, `ebti_source_version` and a `refresh` block (requested, extract count, reused, embedded,
    dropped, vectors_from, full_embed). `python -m rag.loader` writes the first two for a build from the extract:
    `build_bti(demo, chapters, force, store_dir=STORE_DIR)` reads the date from the zip when it cuts
    `data/bti_subset.jsonl` and writes it with the source version to `data/bti_subset.meta.json`; when it reuses the
    subset it reads the sidecar, so the date is the extract the subset came from; no sidecar (a subset cut before
    this feature) or `--demo` leaves them unset. It writes `bti_docs.jsonl` into `store_dir`, so a test can point it
    at a temporary folder instead of the repository's `store/`.
    `KnowledgeBase.rulings_date` gives `(date, "extract")` or `(built_at[:10], "built")`; `KnowledgeBase.releases`
    comes from the release files (`read_release_files(root)`), `KnowledgeBase.fetch_failures` (kind → reason, empty
    by default) is set by `load_kb` from the fetch's result.
11. **The app's fetch.** `fetch_releases(settings, root)` does nothing when both markers exist. Otherwise, for each
    missing kind, the candidates are: the pin alone; else the kind's names in the `current` block of the latest
    release's metadata (`LATEST` template, GitHub's fixed download address for the latest release, read once per
    process with `urllib.request.urlopen` through the module; no token, no API); else, when that file cannot be read
    or has no names for the kind, and also when every candidate the pointer named has failed, the listing (`API`
    template, `per_page=50`, read once per process), taking the newest two complete names of the kind not yet tried.
    So a stale pointer, left by two runs that overlapped, costs one listing and never stops the app while a good
    release is listed; pointer and listing both unreadable without a pin is the only "no release found" case, and
    its message names both routes. Each candidate is tried in order: metadata, archive to a temporary file, SHA-256,
    entries, unpack, then the release file. The download URLs come from the `DOWNLOAD` template, never from
    the listing, so a pin works without the pointer or the listing and tests use `file:` templates. A failed pin
    falls back once to the newest resolved as without a pin, with a log line. Failures are collected: the result,
    `FetchResult(unpacked, failed)`, raises `RefreshError` from `fetch_releases` only when the EBTI kind failed;
    `load_kb` shows a failed TARIC kind with `st.error` and goes on, the app opening without TARIC as it does today.
12. **Settings precedence.** `release_repo` set → the release fetch, the feature-011 settings ignored with a log
    note when they are set too; else `demo_store_url` set → the feature-011 fetch; else nothing. The feature-011
    settings stay in `Settings` and in the README's transition note, which says the secrets are switched only once
    both kinds are published.
13. **Freshness.** `freshness_warning(kb, today)` computes whole-day ages from the TARIC snapshot date and the
    rulings date (extract or build); a part is old when its age exceeds its limit; the text names the part, the age
    and the limit, both parts in one warning when both are old; an unparsable date gives "age unknown". The Origin
    box shows it with `st.warning` under the two captions, inside the box's vertical sub-container.
14. **The workflow.** `refresh.yml`: `on: schedule` (two crons) and `workflow_dispatch` (input `kind`: `taric`,
    `ebti`, `both`); `permissions: contents: write`; `concurrency: refresh`; jobs `taric` (timeout 20 min) and
    `ebti` (timeout 60 min), each with `if: github.event_name == 'workflow_dispatch' && (inputs.kind == '<job>' ||
    inputs.kind == 'both') || (github.event_name == 'schedule' && github.event.schedule == '<its cron>' &&
    vars.CARGOLINT_REFRESH == 'on')`, so the daily cron runs only `taric` and the monthly cron only `ebti`; the
    `ebti` job has `needs: taric` and its `if` starts with `!cancelled() &&`, so it runs when `taric` was skipped but
    never beside it (the concurrency group serializes runs, not the jobs of one run), and a manual run of `both`
    publishes one release at a time; steps: checkout with `persist-credentials: false` (as `tests.yml` does, so the `contents: write` token is not in
    `.git/config` during the install), Python 3.13, `pip install -e .`, run the script with `GH_TOKEN: ${{
    github.token }}` and, for `ebti`, `OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}`. A comment at the top
    notes that GitHub disables the schedules after 60 days without repository activity (R-11).
15. **The eval comparison (SC-003).** `tests/eval/e2e_eval.py` gains `--as-of YYYY-MM-DD` (default: the set's
    `built_on`, so every existing run is unchanged), recorded in the history entry; the author runs both stores with
    `--as-of` the run day and `--repeat 3` in one session and compares the majority-right counts (R-14).
16. **The offline guard.** `tests/conftest.py::_offline` also replaces `rag.refresh._run_gh`, `rag.loader.download`
    and `urllib.request.urlopen` (refusing every scheme but `file:`) with functions that raise the guard's
    `RuntimeError`; `tests/unit/test_offline_guard.py` proves each (R-15). The refresh modules therefore call these
    through their modules, never through `from … import`.
17. **The recorded listing.** `tests/fixtures/refresh/tot_listing.html` is whatever the `tot` folder serves on the
    day T001 runs (one batch at a time: the 2026-11-13 state can be recorded only until the next batch replaces it,
    about early December), with `tot_listing.json` written from the same page (batch id, snapshot date, file count,
    the day); the test reads its expectations from the sidecar, so any recording is right (R-12).

## Implementation outline

**A. Tests first (offline)**
- **A0** `tests/unit/test_offline_guard.py` and `tests/unit/test_settings.py`: the extended guard (the `gh` runner,
  the download, a non-`file:` URL refused, `file:` allowed); the four settings, a pin of the wrong shape, an invalid
  ruling count, the constants.
- **A1** `tests/unit/test_refresh.py`: names and kinds; completeness; retention keeps the two newest complete, deletes
  incomplete ones and ignores other names; the metadata file's fields and `current` from a fresh listing;
  `pack_entries`; `publish` with `force` deleting then creating; a `gh` failure in `publish` or `prune` as
  `RefreshError(exit_code=3)` naming the step; the service's argv through a recorder (`gh api`, `--cleanup-tag`,
  `edit --latest`, `--repo`, `CARGOLINT_GH`, the `check` failures); the listing parser on the recorded listing (expectations from the sidecar), on a listing whose
  newest batch is incomplete beside a complete one, and on one with no complete batch; `extract_date`; `partition`
  and the rewritten metadata of a reused ruling; the workflow file through `yaml.safe_load`.
- **A2** `tests/unit/test_demo_store.py`: `select_rulings` with `keep`: kept rulings stay while valid, the bound
  holds, `all` keeps every valid ruling, the choice is deterministic; `copy_vectors` with `metadatas`.
- **A3** `tests/unit/test_release_fetch.py`: nothing fetched when the markers exist or the repository setting is
  empty; the pointer first and no listing; the listing when the pointer is unreadable or has no names for the kind;
  the newest complete of each kind; a pin without pointer or listing; the fallback to the next newest; a failed pin
  falling back to the newest with the log line; a stale pointer whose candidates all fail falling back to the
  listing's newest untried release; no pin with pointer and listing both unreadable (EBTI raises naming both
  routes, TARIC is returned failed); both candidates failing: EBTI raises, TARIC is reported and the app goes on; a
  wrong checksum, a missing asset, an unexpected path, a `..` path; the markers last; the release files written; the
  legacy path untouched and the log note when both settings are set.
- **A4** `tests/unit/test_view.py`: `snapshot_caption` with both dates, "TARIC not loaded", "built"; the warning at
  40, 41, 45 and 46 days, for both parts, for an unparsable and for a future date; the Admin statements.
  `tests/unit/test_loader.py`: `build_bti`'s date and sidecar, `read_release_files`, `rulings_date`,
  `fetch_failures`. `tests/unit/test_e2e_eval.py`: `--as-of`.
- **A5** `tests/integration/test_refresh_taric.py`: the script on a generated listing naming the signed fixture
  batch, with `download` copying from the fixtures and the fake service: publish with `current` from a listing read
  right before the create and marked latest, nothing new (a complete release as new or newer), an incomplete remnant
  rebuilt, `--force` deleting and recreating, a service failure at the create as exit 3, refusal, an unreadable
  listing, no complete batch, `--no-publish`, the service missing, retention. Skips without `gpg`.
- **A6** `tests/integration/test_refresh_ebti.py`: the script on a tiny extract, a tiny previous store and
  `FakeEmbeddings`: the store's files, the carried-over and recomputed fields and counts, only new and changed rulings
  embedded, a reused ruling's new metadata, the fresh download (the file and its `.part` removed first), nothing new
  (also with the work folder left behind), the model check, an incomplete previous store, `--full-embed` on the
  fakes, the ruling setting and `--rulings all`, the work folder with and without `--force`, `--force` deleting and
  recreating, a service failure as exit 3,
  retention, the repository's `store/`, `data/bti_subset.jsonl` and `data/raw/` untouched.
- **A7** `tests/ui/*`: the Origin box's dates and warning; Admin › Data; a failed EBTI fetch stops the app; a failed
  TARIC fetch opens it without TARIC with the error on the page; the legacy path.

**B. Code**
- **B1** `agent/config.py`: the settings and the constants.
- **B2** `rag/refresh.py`; then `tests/conftest.py` (the extended guard) and `.gitignore`.
- **B3** `rag/demo_store.py` (`keep`, `copy_vectors` metadata) and `rag/loader.py` (`store_dir`, the extract date
  and the sidecar, `KnowledgeBase`).
- **B4** `rag/refresh_taric.py` and `scripts/refresh_taric.py`.
- **B5** `rag/refresh_ebti.py` and `scripts/refresh_ebti.py`.
- **B6** `app.py`, `ui/view.py`, `ui/main_page.py`, `ui/admin.py`, `tests/ui/harness.py`.
- **B7** `.github/workflows/refresh.yml`.

**C. Documentation**
- **C1** The README's "Knowledge base refresh" section and the "Demo deployment" update; `.env.example`;
  `tests/eval/e2e_eval.py --as-of`.

**D. Verification**
- **D1** `pytest -q`, offline.
- **D2** The author's steps, outside this feature's runs: the first real TARIC and EBTI runs (SC-001, SC-002), the
  eval comparison with `--as-of` and `--repeat 3` (SC-003), the switch of the demo's secrets once both kinds are
  published (SC-005), the check of the releases (SC-007).

## Complexity Tracking

None. No principle is violated and no dependency is added.
