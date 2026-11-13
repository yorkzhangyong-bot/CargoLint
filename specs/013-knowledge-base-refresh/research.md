# Research: Knowledge Base Refresh (Phase 0)

The facts below were checked on 2026-11-13 against the live sources, the `demo-store-v1` release and the code. Every
decision records what was chosen, why, and what else was considered.

## R-01 The TARIC full extract is monthly

**Fact**: `https://distr.tullverket.se/tulltaxan/xml/tot/` is an Apache-style index. On 2026-11-13 it listed 38
signed files of one batch, `*_e14b8e06-f3f6-4ce1-ba9b-1423d07f6b83_261102.xml.gz.pgp`, all stamped 2026-11-02 23:00.
The batch the author loaded on 2026-10-22 was dated 261001. The `xml/dif/` folder holds one batch per working day
(261103, 261104, … 261112). So the full extract the loader reads (feature 002) appears about monthly, and the daily
changes are in the difference files, which are out of scope.

**Decision**: the TARIC script checks daily and publishes only when the date of the newest complete batch (all six
object files present; an incomplete newer batch is passed over, and a folder with no complete batch is refused) is
newer than the newest complete TARIC release; the warning limit is 40 days on the snapshot date (clarification Q1).

**Alternatives considered**: a 7-day limit on the snapshot date (yellow about three weeks of each month); a
"checked on" stamp re-uploaded daily (measures the process, not the data); reading the difference files (incremental
updates, out of scope).

## R-02 The EBTI extract and its date

**Fact**: the full extract (`DDS2-EBTI_Full.zip`, 397 MB) holds one CSV per year (`EBTI_2004.csv` …), each entry
stamped with the night the extract was produced (the local copy: 2026-10-14 04:44). The loader filters it to the
twelve chapters and validity on the run date: 73,899 rulings on 2026-10-14. With a three-year validity, about 2,000
new valid rulings arrive in these chapters each month.

**Decision**: the extract's snapshot date is the date of the newest `.csv` entry's timestamp; an extract without one
is refused. The store's size is the `CARGOLINT_EBTI_RULINGS` setting (clarification Q4): 5000 by default for the demo
store, or `all` for every valid ruling in a production store; the setting does not change the snapshot-date rule.

**Alternatives considered**: the HTTP `Last-Modified` header (not guaranteed, and not available for a file given with
`--extract`); the download day (wrong after a reused download).

## R-03 How demo-store-v1 was built, and what "exactly as" means now

**Fact**: `demo-store-v1` (`cargolint-demo-store-v1.zip`, 150,089,212 bytes, 2026-10-27) was cut by
`python -m rag.demo_store --out … --rulings 5000 --zip …` from the full local build (73,899 rulings embedded in
about 90 minutes for about $0.27): the nomenclature index and BM25 file copied, 5,000 rulings chosen (half under the
eval set's and sample files' codes, the rest spread over the chapters, seeded), their vectors copied out of the full
collection, `index_meta.json` with a `demo_store` block, plus `data/taric.jsonl`.

**Decision** (clarification Q2): the refresh keeps the layout and the choice rule, but takes its vectors from the
previous store: unchanged rulings are copied, new and changed rulings are embedded, the nomenclature index is copied.
`--full-embed` rebuilds everything with the loader's own `build_indexes` against the work folder, for a change of
embedding model. The script refuses to reuse a store built with another model or another nomenclature. The size is the
setting of R-02: the default 5,000 keeps the 30-minute target; `all` embeds the full build once (about 90 minutes)
for a production store, then later runs reuse its vectors.

**Alternatives considered**: the full build then the cut (90 minutes, $0.27, 1.8 GB; the first `all` run does this
once, while the demo's default bound never does); embedding all chosen rulings afresh each month (about 10,600 texts,
about 15 minutes, $0.04; simpler, but the user asked for reuse).

## R-04 Keeping the previous store's rulings

**Fact**: `select_rulings` shuffles each code's rulings with a fixed seed and takes them in turn; a new ruling in a
code changes that code's order, so re-running the rule on a new extract would swap many still-valid rulings for
others and embed them for nothing.

**Decision**: `select_rulings(..., keep=set_of_references)` puts the kept rulings first within each code, before the
seeded shuffle of the others. The rule is otherwise unchanged, so the existing tests hold with `keep=None`, the bound
`n` holds, and a kept ruling leaves only when it is no longer in the extract or its code's share falls (fewer places
for its code).

**Alternatives considered**: keeping every previous ruling regardless of the per-code shares (drifts from the demo
rule over time); a separate "sticky" selection function (duplicates the rule).

## R-05 The release service

**Fact**: the maintainer's laptop has `gh` 2.102 signed in with `repo` scope; GitHub-hosted runners have `gh` with
the job's token in `GH_TOKEN`. The repository is public, so release assets download without a token from
`https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>`, and the latest release's assets from the fixed
address `https://github.com/<owner>/<repo>/releases/latest/download/<asset>` (GitHub's documented permalink; the
latest release is the one published last, since a new release is marked latest by default and `gh release edit
--latest` can mark any). The release list is public at `https://api.github.com/repos/<owner>/<repo>/releases`, but
unauthenticated API calls are limited to 60 requests an hour per address, and Streamlit Community Cloud sends every
app's traffic through a handful of published outbound addresses, so that budget is shared with every other app on
the platform that calls the API without a token: a cold start that depended on it could fail at any time.

**Decision**: the scripts use `gh` through `subprocess` (`api repos/<repo>/releases?per_page=100` for the listing,
with assets and drafts, in the same JSON shape the app reads; `release create`; `release edit --latest`; `release
delete --yes --cleanup-tag`; `release download`; no `upload --clobber`, see R-16), found through `CARGOLINT_GH` or `PATH`,
with `gh auth status` checked before any download, all through one runner function that the suite's offline guard
replaces. The app reads the latest release's metadata and the download URLs with `urllib.request`, no token and no
API; the API listing is its second route only (R-06).

**Alternatives considered**: the REST API with a token from the scripts (an upload client to write and test, a token
to manage on the laptop); `gh release list --json` for the scripts (no asset names, so completeness would need one
`release view` per release).

## R-06 Where the app finds the release

**Decision** (clarification Q3): every release's `metadata.json` carries a `current` block, the complete releases of
both kinds left after that run (newest first, at most two per kind), and the release just published is marked the
repository's latest. The app reads the latest release's metadata once per cold start from the fixed latest-release
address (no API, no token), takes each kind's candidates from `current`, and falls back once to the next newest. When
that file cannot be read or names no release of a kind (`demo-store-v1` is the latest until the first refresh; a
release made by hand), the app lists the repository's releases through the API and takes the newest complete releases
of the kind. A pin (`CARGOLINT_EBTI_RELEASE`, `CARGOLINT_TARIC_RELEASE`) names one release and is fetched by its name
without pointer or listing; a pinned release that fails falls back once to the newest of the kind, with a log line,
since a dead demo is worse than an unhonoured pin, and Admin › Data names the release in use. An EBTI kind that cannot
be fetched stops the app; a TARIC kind that cannot be fetched does not: the app opens without TARIC, as it does today
when `open_taric_store` finds no file, with the reason on the page.

When every candidate the pointer named fails (a stale `current` block, which two overlapping runs can leave: each
computes `current` for the other kind from its own listing, and the one marked latest last may omit the other's new
release or name one the other's prune deleted), the app reads the listing and tries the newest complete release it
has not tried. The pointer is therefore an optimisation with a safety net, not a single point of truth. The scripts
shrink the window on their side: `current` is computed from a listing read immediately before the metadata is
written, after the build and the pack, never from the "nothing new" listing of minutes earlier; the workflow runs
its two jobs one after the other (`needs`) and its runs one at a time; and the maintainer runs the scripts by hand
only while the schedule is off, as the brief says, or after checking the Actions tab.

**Rationale**: the demo follows the schedule without a secrets change; the newest publish of either kind always
carries the names of both kinds (any later publish would itself be the latest), so one small file replaces the
listing; with only two releases kept, "the previous release" is the other kept one; a pin gives the rollback the user
asked for, lasts until retention deletes its release (the next refresh of its kind), and never leaves the demo dead.

**Alternatives considered**: the API listing as the only route (the shared 60-an-hour budget, see R-05); a GitHub
token in the app's secrets (a secret to manage and renew, and the app reads no GitHub token); the releases Atom feed
(not documented for this use, no asset names); a fixed pointer release updated with every run (a moving release of
its own; the latest release already is one); exact names in the settings with `previous` in the metadata (a secrets
edit and a reboot after every refresh); a pin without fallback (a rollback pin is deleted by the very next refresh of
its kind, and the next cold start would stop).

## R-07 The checksum's home

**Decision**: the archive's SHA-256 is in the release's `metadata.json`, published with the archive, and the app
verifies the archive against it before unpacking. The feature-011 `CARGOLINT_DEMO_STORE_SHA256` secret keeps its role
for the legacy path only.

**Rationale**: the metadata and the archive come from the same place, the project's own release; the check still
catches a truncated or corrupted download, which is what a cold start can meet. A checksum in the secrets would need
a secrets change per release, which clarification Q3 rules out.

## R-08 Two archives instead of one

**Decision**: the EBTI archive holds `store/…` only and the TARIC archive holds `data/taric.jsonl` only, each
unpacked when its marker is missing. The app fetches the EBTI kind first, then TARIC.

**Rationale**: the two refresh on different schedules; a TARIC release of 2 MB would otherwise drag 150 MB of
unchanged indexes with it. The legacy archive keeps both, which is why the legacy path stays separate.

## R-09 The TARIC download folder

**Fact**: `discover_extract` refuses a folder with two files for one object, and `data/raw/taric/` holds the
2026-10-01 batch on the author's machine.

**Decision**: the script downloads into `<rag.loader.TARIC_RAW_DIR>/<YYYY-MM-DD>/`, reading the loader's constant at
call time (normally `data/raw/taric/`), and runs the load on that folder. The default folder stays for manual loads.

## R-10 The EBTI work folder and the repository's store

**Decision**: the EBTI refresh builds in `--out` (default `build/ebti-<date>/`), which must be new or empty, as
`rag.demo_store` requires of `--out`; with `--force` the default work folder is emptied first (the retry after a
failed embedding or upload is a `--force` run), a folder given with `--out` never; the `build/` rule in `.gitignore`
already covers it. The extract is downloaded to `build/DDS2-EBTI_Full.zip`, not to the loader's `data/raw/` copy:
the loader reuses `data/bti_subset.jsonl` unless `--force`, and a refresh that replaced the loader's zip would let a
later local build stamp an old subset with a new date. For the same reason the loader records the extract date of
the subset it cuts in `data/bti_subset.meta.json` and reads it back when it reuses the subset. `rag.loader.build_indexes`
gains a `store_dir` parameter (default `STORE_DIR`) for `--full-embed`; the reuse path writes with
`rag.demo_store.copy_vectors` and `ChromaVectorSearch`, both pointed at the work folder; for `--full-embed` it also
gains an `embeddings` parameter (it builds `OpenRouterEmbeddings` itself only when none is given, which the suite's
guard refuses, and reads the dimension with `getattr` before the probe, since `FakeEmbeddings` has no `dimension`),
so the script's `main(argv, embeddings=…)` reaches that path too. The work-folder check comes after the "nothing
new" check: a successful run leaves `build/ebti-<date>/` behind, and a same-day re-run must exit 0, not 2. A reused
ruling's vector is
copied but its metadata is written from the new extract (`copy_vectors(..., metadatas=…)`): `copy_vectors` copies the
source collection's metadata, and `tools/classify_cn8.py` filters the ruling collection on `code`, so a ruling whose
text is unchanged but whose code changed would otherwise be served under the old code. `index_meta.json` carries
over the fields that describe the copied nomenclature index and recomputes `built_at`, `bti_rulings` and
`embedding_usage`, since `cut_demo_store`'s `{**meta}` pattern would keep the previous store's build time. The
repository's `store/`, `data/bti_subset.jsonl` and `data/raw/` are never targets.

## R-11 The workflow's switch

**Fact**: GitHub runs a committed `schedule` as soon as the workflow is on the default branch, disables scheduled
workflows after 60 days without repository activity, and exposes repository variables as `vars.*`.

**Decision**: each scheduled job carries `if: … vars.CARGOLINT_REFRESH == 'on' …`; a manual `workflow_dispatch` runs
regardless, since it is the maintainer's deliberate act. Crons: `30 5 * * *` (TARIC, after the distribution's
23:00 stamp) and `0 6 1 * *` (EBTI). `permissions: contents: write` for the releases; `concurrency: refresh` so two
Actions runs never publish together, and `needs: taric` on the `ebti` job (with `!cancelled()` at the front of its
`if`, so it still runs when `taric` was skipped) so the two jobs of one run never publish together either: a
concurrency group serializes runs, not the jobs inside one run, and a manual run of `both` would otherwise publish
two releases at once and compute each `current` block without the other's release. A laptop run beside a scheduled
one is serialized by nothing: the operating rule (spec Assumptions, README) is to run the scripts by hand only while
the schedule is off, as the brief says, or after checking the Actions tab. Checkout with `persist-credentials:
false`, as `tests.yml` does, so the write token is not left in `.git/config` while `pip install` runs. The 60-day
auto-disable is named in the workflow's comment and in the README's switch-on text: the schedules are re-enabled
from the Actions tab.

**Alternatives considered**: committing the workflow and running `gh workflow disable` (a state outside the file,
easy to lose); commenting the crons out (a code change to switch on).

## R-12 Test strategy and fixtures

- **Recorded listing**: `tests/fixtures/refresh/tot_listing.html`, the `tot` index as served on the day it is
  recorded by hand (the folder holds one batch at a time, so the 2026-11-13 state, batch `e14b8e06-…`, 261102, 38
  hrefs, can be recorded only until the next batch replaces it, about early December; a later recording is as good),
  with `tot_listing.json` noted from the same page: `batch`, `snapshot_date`, `files`, `recorded_on`. The unit test
  of `parse_listing` and `current_batch` reads its expectations from the sidecar; the batch rule (an incomplete
  newer batch passed over, no complete batch refused) is tested on generated name lists. The script's end-to-end
  test generates a small listing naming the signed fixture batch (`tests/fixtures/taric/extract`, batch
  `11111111-…`, 261001) and monkeypatches `rag.loader.download` to copy from the fixtures, with `gpg` required as in
  `test_taric_loader.py`.
- **Release listing**: `tests/fixtures/refresh/releases.json`, GitHub's shape (`tag_name`, `draft`, `assets[].name`)
  with `ebti-2026-11-01`, `ebti-2026-10-14`, `taric-2026-11-02`, `demo-store-v1` and a draft `taric-2026-11-03` with
  one asset (incomplete); the same shape is what `gh api` returns to the scripts, so one parser and one fixture serve
  both sides. The fetch tests also generate listings and latest-release metadata in temporary folders and point the
  `LATEST`, `API` and `DOWNLOAD` templates at `file:` URLs.
- **Tiny extract**: a zip of one CSV with a few rows written in the test with the loader's column names (as
  `tests/unit/test_loader.py` builds rows), entry timestamps set to the wanted date.
- **Tiny previous store**: the `full_build` pattern of `tests/unit/test_demo_store.py` (a Chroma collection of
  8-dimensional vectors, `index_meta.json` with `embedding_model` `fake-hash-8`), with `FakeEmbeddings(dim=8)`
  injected into `main(argv, embeddings=…)` and the settings' `embed_model` set to match.
- **Fake release service**: `FakeReleaseService` in `tests/fakes.py` records `check`, `list`, `create`,
  `mark_latest`, `delete` and `download` calls in order (so a test can see the listing re-read right before the
  create), holds the releases with their asset names and draft flag, serves archives from a folder, and can be told
  to fail at a call. The real service's argv is tested separately with a recorder in place of the runner.
- **Workflow**: `yaml.safe_load` on `refresh.yml`. PyYAML 6.0.3 is installed as a dependency of chromadb and
  langchain-core (`pip show pyyaml`), so no package is added; YAML 1.1 reads the unquoted `on` key as the boolean
  `True`, which the test allows for. A parsed file lets the test assert the switch in both jobs' conditions and the
  key in the `ebti` job only, which a grep cannot.
- **The offline guard**: `tests/conftest.py::_offline` today replaces only the OpenRouter clients. The scripts'
  `main(argv, service=None)` defaults to the real `ReleaseService`, which acts on the checkout's remote with the
  maintainer's signed-in `gh`, so a test that forgot the fake could create or delete real releases. The guard is
  extended to `rag.refresh._run_gh`, `rag.loader.download` and `urllib.request.urlopen` for every scheme but `file:`,
  each raising the guard's `RuntimeError`, and `tests/unit/test_offline_guard.py` proves it (R-15).

## R-13 Time budget

| Step | TARIC | EBTI |
|---|---|---|
| Listing or `gh` checks | seconds | seconds |
| Download | 34 MB (six signed files) | 397 MB extract (into `build/`) + 150 MB previous store |
| Load or parse | about 30 s (`--taric`, measured 2026-10-23) | about 2–3 minutes for the CSVs |
| Vectors | none | copy about 4,800 vectors; embed a few hundred texts |
| Pack and upload | 2 MB | 150 MB |
| Estimate | 2–4 minutes | 10–15 minutes |

Both sit under the targets (10 and 30 minutes); the author measures the first real runs.

## R-14 The eval comparison (SC-003)

**Fact**: `tests/eval/e2e_eval.py` judges ruling validity on the set's `built_on` date (2026-10-23), so a ruling
issued after it never votes: a refreshed store, which swaps rulings that expired for rulings issued since, could only
lose against demo-store-v1 on that date. The project's measure is three runs (`--repeat 3`) and the majority (the
recorded baselines are 64/64/65 and 68 after the stop-word change), not one run.

**Decision**: the evaluation gains `--as-of YYYY-MM-DD` (default: the set's `built_on`, so existing runs are
unchanged; the value is recorded in the history entry), and SC-003 compares the majority-right counts of three runs
per store, both run in one session with the same settings and `--as-of` the run day, within 2 of 120 lines. The
eval set's own rulings are excluded from their vote as before, so the comparison measures the other rulings.

**Alternatives considered**: one run per store on the build date (noise of a few lines per run, and the bias above);
comparing against an old recorded baseline (another day, possibly other settings).

## R-15 The offline guard

**Decision**: see R-12. The three new refusals sit in the same autouse fixture as the OpenRouter ones; the refresh
modules call `rag.loader.download` and `urllib.request.urlopen` through their modules so the monkeypatch is seen,
and `ReleaseService` runs `gh` only through `rag.refresh._run_gh`, which a test replaces with a recorder to check
the argv. Blocking `subprocess.run` itself was rejected: `test_taric_loader.py` runs `gpg` through it. The guard
covers the network and `gh`, not file writes: `build_bti` writes `bti_docs.jsonl` into its store folder whatever
else is patched, so `build_bti` and `build_indexes` take a `store_dir` and every loader call in a test passes a
temporary one and monkeypatches `rag.loader.STORE_DIR`, `RAW_DIR`, `BTI_SUBSET` and `SUBSET_META`; otherwise
`pytest -q` on the laptop would overwrite the full build's `store/bti_docs.jsonl` with test rulings.

## R-16 Complete releases

**Fact**: `gh release create <tag> <files>` uploads the assets before it publishes the release, but an interrupted
run can leave a draft or a release with one asset. Replacing the two assets of an existing release one after the
other (`upload --clobber`) would add a worse case: a run stopped between the two uploads leaves an archive and a
`metadata.json` from different builds, which "both assets present" would call complete and nothing would repair.

**Decision**: a release is complete when it carries both assets and is not a draft. Only complete releases count for
"nothing new" (the source's date must be newer than the newest complete release of the kind), for the `current`
block, for retention (the two newest complete are kept, every other release of the kind is deleted) and for the app.
An incomplete release of the name about to be published is deleted and created afresh; `--force` deletes the
existing complete release and creates it afresh from the one build, so a release's two assets always come from the
same build and no asset is ever patched. Between the delete and the create the release does not exist for a few
minutes (the EBTI upload); a cold start in that window falls back to the next newest release or to the listing. A
run that publishes nothing still prunes and, when the repository's latest release is older than the newest complete
release of its kind or is incomplete, re-marks it latest, so a failed prune or mark-latest repairs itself on the next
run; a run whose service call fails after the build exits 3 and says what it did before (spec FR-005).

**Alternatives considered**: comparing the listed archive size with the metadata's `size` to detect a mixed release
(one more download per check, and only a partial test); `upload --clobber` with a marker asset (a third asset to
keep consistent).
