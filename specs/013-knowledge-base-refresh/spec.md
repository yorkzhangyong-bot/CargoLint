# Feature Specification: Knowledge Base Refresh

**Feature Branch**: `013-knowledge-base-refresh`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Feature 013: knowledge base refresh. Problem: the EBTI rulings and TARIC data the app
uses are frozen in the GitHub release demo-store-v1, built once by hand; a clerk cannot tell how old they are. Goal: the
knowledge base can be refreshed on two schedules, and the clerk always sees how current each part is. Scope: (1)
`scripts/refresh_taric.py` downloads the current TARIC data from the official EU source, rebuilds the TARIC tables only,
no embedding, and publishes a release `taric-YYYY-MM-DD`; designed to run daily. (2) `scripts/refresh_ebti.py` downloads
current EBTI rulings, rebuilds the vector store in demo-store-v1's layout (5,000 rulings by default, or every valid
ruling with the `all` setting), and publishes a release
`ebti-YYYY-MM-DD`; designed to run monthly. (3) Each release carries a metadata file with snapshot date and source
version. The app reads both release names from settings instead of the hard-coded demo-store-v1, and falls back to the
previous release if a download fails. (4) The Origin box shows both snapshot dates; a yellow warning appears when TARIC
is older than 7 days or EBTI older than 45 days. (5) A GitHub Actions workflow with cron schedules for both scripts,
disabled by default; the maintainer runs the scripts manually until the workflow is switched on. (6) Keep the two most
recent releases of each kind, delete older ones. Out of scope: incremental updates, any change to classification logic.
Constraints: must not break the current cloud demo; UI changes native Streamlit only per constitution 1.10.0; do not run
the scripts against the live EU sources during tests, use recorded fixtures. Success: a TARIC refresh completes in under
10 minutes and an EBTI refresh in under 30 minutes on a laptop, the eval set scores within 2 points of the current
store, and both dates appear in the UI."

## Background

Today the cloud demo downloads one archive, `cargolint-demo-store-v1.zip` (150 MB) of the release `demo-store-v1`
(2026-10-27), named by a URL and a checksum in its secrets (feature 011). The archive holds the search indexes, the
ruling document store and the TARIC snapshot together: about 5,000 EBTI rulings cut from the 2026-10-14 extract, and
the TARIC snapshot of 2026-10-01. Nothing in the app says when either was taken: the main page shows only the TARIC
snapshot date, and Admin › Data shows the build date of the indexes.

Two facts about the sources, checked on 2026-11-13, shape this feature:

- The Swedish Customs file distribution publishes one **full** TARIC extract (the `tot` folder) about once a month: the
  folder holds one batch at a time, dated 2026-10-01 and then 2026-11-02. The daily changes are in difference files (the
  `dif` folder, one batch per working day), which this project does not read: incremental updates are out of scope.
- The EBTI full extract is regenerated daily (its files are stamped with the night they were produced); it is 397 MB,
  of which the twelve indexed chapters give about 74,000 valid rulings, and about 2,000 new ones arrive each month.

So "refresh" means: publish the newest full extract of each source as a release, and show the clerk the date of the
data behind each part.

## Clarifications

### Session 2026-11-13

- Q: Which age should the TARIC warning measure, given that the full extract is published only about monthly? → A: The
  snapshot date of the full monthly extract, with a 40-day limit; the 7-day rule is dropped. Daily difference files
  stay out of scope.
- Q: How does the EBTI refresh get its vectors: embed only the chosen rulings, or rebuild the full 74,000-ruling index
  and cut it as demo-store-v1 was cut? → A: Neither re-embeds everything. The rulings kept from the previous store
  reuse their existing vectors; only the rulings new since the previous store, and any whose text changed, are
  embedded. A full re-embed is a separate manual flag, used only when the embedding model changes.
- Q: Do the settings name exact releases, or does the app resolve the newest? → A: The app resolves the newest release
  of each kind (`taric-*`, `ebti-*`) at start-up. An optional setting pins a release name for a rollback. Two
  releases of each kind are kept.
- Q: Does the EBTI store stay at about 5,000 rulings, or grow with every new ruling published since the previous
  store (about 2,000 a month)? → A: The size is a setting: `CARGOLINT_EBTI_RULINGS` (or `--rulings`) defaults to 5000
  for the demo store and may be `all` for a production store, which keeps every valid ruling. A number keeps new
  rulings to the places freed by expired, withdrawn and dropped ones; the demo stays at about 5,000 so its cloud
  memory and refresh time do not change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The maintainer refreshes the TARIC snapshot with one command (Priority: P1)

The maintainer runs one command. It looks up the current full extract on the Swedish Customs file distribution (the
newest batch whose six object files are all there) and, when its snapshot date is newer than the newest complete TARIC
release (one that carries both assets and is not a draft), downloads the six object files the loader needs, verifies
their signatures, writes the TARIC snapshot exactly as `python -m rag.loader --taric` does today, packs the snapshot as
one archive and publishes it as the release `taric-<snapshot date>` with a metadata file, marked as the repository's
latest release. It then keeps the two most recent complete TARIC releases and deletes every other TARIC release. When
the distribution holds nothing newer, the command says so and publishes nothing. No embedding and no model call is
made.

**Why this priority**: TARIC measures change during the year (duty rates, anti-dumping measures, requirements), and
the demo's snapshot is from 2026-10-01. The release is what every other part of this feature reads.

**Independent Test**: run the command on recorded fixtures: a saved copy of the distribution's directory listing, the
signed fixture batch of feature 002, and a fake release service that records what is created, uploaded and deleted.
The published release holds the snapshot archive and a metadata file with the right date and source version, and the
fake service shows the older releases of the kind deleted.

**Acceptance Scenarios**:

1. **Given** the listing shows one complete batch dated D and no complete TARIC release of date D or newer exists,
   **When** the command runs, **Then** it downloads the six files, verifies them against the pinned key, writes
   `data/taric.jsonl` with snapshot date D, and publishes `taric-D` holding `cargolint-taric-D.zip` (one entry,
   `data/taric.jsonl`) and `metadata.json` (kind, snapshot date D, the batch id as the source version, the archive's
   SHA-256 and size, and the `current` block naming the complete releases of both kinds left after this run), and
   marks `taric-D` the repository's latest release.
2. **Given** a complete `taric-D` is the newest TARIC release and the listing's batch is still D (or older), **When**
   the command runs, **Then** it prints that nothing is new, downloads nothing and ends with exit code 0. With
   `--force` it downloads, rebuilds, deletes `taric-D` and publishes it afresh from the new build (assets are never
   replaced one by one). A `taric-D` that lacks an asset or is a draft (an interrupted publish) is not complete: the
   run deletes the remnant and publishes `taric-D` afresh.
3. **Given** three complete TARIC releases exist once the new one is published, and an incomplete one, **When** the
   command finishes, **Then** only the two complete ones with the newest snapshot dates remain, the incomplete one is
   deleted whatever its date, and no release of another kind (`ebti-…`, `demo-store-v1`) is touched.
4. **Given** a file whose signature does not verify, a listing that cannot be read, or a listing in which no batch
   has all six object files, **When** the command runs, **Then** it stops with a message naming the file or the
   problem (exit code 1), writes no snapshot and publishes nothing. A listing whose newest batch is incomplete while
   an older batch is complete takes the older batch.
5. **Given** the release service is not available or not signed in, **When** the command starts, **Then** it stops
   before downloading anything. With `--no-publish` the command builds and packs without the release service.

---

### User Story 2 - The maintainer refreshes the EBTI rulings with one command (Priority: P1)

The maintainer runs one command. It downloads the current EBTI full extract afresh into the work area under `build/`
(never the loader's copy under `data/raw/`) and the previous EBTI store (the newest complete EBTI release;
`demo-store-v1` on the first run), keeps the valid rulings of the twelve indexed chapters, and chooses them by the
demo store's rule up to the configured bound (5,000 by default; `all` keeps every valid ruling), with the previous
store's rulings placed first so that they stay while they are valid. A ruling kept from the previous store reuses its
vector; a ruling that is new, or whose text changed, is embedded; a kept ruling whose code or validity changed keeps its vector but is served with the new values;
expired and withdrawn rulings leave. The nomenclature index and its BM25 file are taken over from the previous store.
The result, in the layout of demo-store-v1, is built in a work folder, packed as one archive of `store/…` and
published as `ebti-<extract date>` with a metadata file, marked as the repository's latest release. A full re-embed,
needed only when the embedding model changes, is the manual flag `--full-embed`. The repository's own `store/`,
`data/bti_subset.jsonl` and `data/raw/` are never touched. The command then keeps the two most recent complete EBTI
releases and deletes every other EBTI release.

**Why this priority**: rulings expire and new ones are issued every day. The demo's rulings are from the 2026-10-14
extract.

**Independent Test**: run the command in a temporary folder on a tiny recorded extract (a zip with a few CSV rows), a
tiny previous store with a real ruling collection of small vectors (as feature 011's tests build one), fake embeddings
that record what they embed, and the fake release service. The work folder holds a complete store, the archive holds
`store/…` only, the metadata carries the extract's date, and only the new and changed rulings were embedded.

**Acceptance Scenarios**:

1. **Given** the recorded extract dated D and a previous store, **When** the command runs, **Then** the work folder
   holds `store/` with the nomenclature index and its BM25 file copied from the previous store, the ruling index,
   `bti_docs.jsonl` and an `index_meta.json` that records D as the rulings' snapshot date, the source version and the
   counts of rulings kept, embedded and dropped, with the loader's fields recomputed for this build (build time,
   ruling count, embedding usage) or carried over from the previous store (model, dimension, nomenclature chunk count,
   edition); the release `ebti-D` holds `cargolint-ebti-D.zip` (entries under `store/` only, no `data/taric.jsonl`)
   and `metadata.json` with the `current` block, and is marked the repository's latest release.
2. **Given** a complete `ebti-D` already exists and the extract is still dated D (or older), **When** the command
   runs, **Then** it says nothing is new and stops before downloading the previous store or making any embedding
   call, exit code 0, whatever the state of the default work folder. With `--force` it rebuilds, emptying the default
   work folder first, deletes `ebti-D` and publishes it afresh from the new build. An incomplete `ebti-D` (an asset
   missing or a draft) is deleted and published afresh.
3. **Given** a previous store whose rulings are partly expired or withdrawn in the extract, partly unchanged and
   partly changed in their text, and an extract with new rulings, **When** the store is built, **Then** the unchanged
   rulings keep their previous vectors, copied not embedded, with their code, chapter and validity written from the
   new extract (a kept ruling whose code changed is found under the new code); the changed and the newly chosen
   rulings are the only ones embedded; the expired and withdrawn ones are absent; and the choice is the demo store's:
   rulings with text, up to half under the preferred codes, the rest spread over the chapters, the previous store's
   rulings first. With `all`, every valid ruling with text enters the store instead of the bounded choice.
4. **Given** a previous store built with another embedding model, **When** the command runs without `--full-embed`,
   **Then** it refuses before any embedding call and names the flag. **With** `--full-embed`, every nomenclature
   chunk and every chosen ruling is embedded afresh and nothing is copied from the previous store.
5. **Given** three complete EBTI releases exist once the new one is published, and an incomplete one, **When** the
   command finishes, **Then** only the two complete ones with the newest snapshot dates remain, the incomplete one is
   deleted, and no release of another kind is touched.
6. **Given** the command ran on a laptop with a full local build, **When** it finishes, **Then** `store/`,
   `data/bti_subset.jsonl`, `data/raw/` and `data/taric.jsonl` are as they were; only the extract and the work folder
   under `build/` are new.
7. **Given** the default work folder `build/ebti-D/` is left from an earlier run (a failed embedding or upload, or a
   `--no-publish` run) and there is something to build, **When** the command runs without `--force`, **Then** it
   stops with exit code 2 naming the folder and the two ways on, `--force` or `--out`; with `--force` the default
   folder is emptied first. A folder given with `--out` is never emptied: it must be new or empty. The folder is
   looked at only after the "nothing new" check, so a same-day re-run after a successful run exits 0 although its
   folder remains.
8. **Given** the release service fails after the build (the create, the marking as latest, a deletion or the
   pruning), **When** the command runs, **Then** it exits 3 with a message naming the step and the release and
   saying what the service did before it failed; the next run of the kind repairs it, and it still prunes and
   re-marks the latest release when needed even when the source has nothing new.

---

### User Story 3 - The demo fetches the newest releases at a cold start and falls back (Priority: P1)

On Streamlit Community Cloud the app finds no store and no TARIC snapshot. Its settings name the repository that
publishes the releases. The app reads one small file: the metadata of the repository's latest release, whose `current`
block names, for each kind, the newest complete release and the one kept before it. Every refresh writes that block
and marks its release the latest, so the file is always the most recent run's view. It is read from the public
download address, not through the GitHub API, so it needs no token and is not subject to the API's rate limit of 60
requests an hour per address, a budget that all Community Cloud apps share through a few outbound addresses. For each
kind the app takes the newest named release (or the release pinned in the settings for a rollback), reads its
metadata, downloads the archive, verifies its checksum against the metadata and unpacks it: the EBTI release gives
`store/…`, the TARIC release gives `data/taric.jsonl`. When the newest release cannot be downloaded or verified, the
app tries the next newest of that kind once; a pinned release that fails falls back to the newest. When the latest
release's metadata cannot be read or names no release of a kind (before the first refresh, or when a release made by
hand is the latest), the app lists the repository's releases through the API as the second route. An EBTI release
that cannot be fetched stops the app; a TARIC release that cannot be fetched does not: the app opens without TARIC, as
it does today when the snapshot is missing, and says so on the page. With the repository setting empty and the
feature-011 settings set, the app behaves exactly as today, so the current demo keeps working until its secrets are
switched, which happens only once both kinds are published.

**Why this priority**: the cloud's filesystem starts empty after every sleep or reboot, so the releases are useless
until the app can fetch them, and the demo must not break on the way.

**Independent Test**: point the latest-release pointer, the listing and the download addresses at `file:` URLs over a
temporary folder of releases (a metadata file and an archive per release) and start the app under AppTest with the
knowledge base replaced by a fake.

**Acceptance Scenarios**:

1. **Given** no `store/index_meta.json` and no `data/taric.jsonl`, the repository setting set, and the latest
   release's metadata naming `ebti-D1` (newer) and `ebti-D0`, `taric-D3` (newer) and `taric-D2`, **When** the app
   starts, **Then** it reads that one file, lists nothing, fetches `ebti-D1` and `taric-D3` with a spinner, verifies
   each archive before unpacking it, unpacks the store and the snapshot, opens the knowledge base, and the Origin box
   shows D3 and D1.
2. **Given** the newest EBTI release's archive fails its checksum or cannot be downloaded, **When** the app starts,
   **Then** it unpacks nothing from that release, fetches `ebti-D0` and opens with it; Admin › Data names the release
   in use.
3. **Given** the newest EBTI release and the next newest both fail, or only one EBTI release exists and it fails,
   **When** the app starts, **Then** it stops with an error naming the releases and the reasons.
4. **Given** `CARGOLINT_EBTI_RELEASE` pins `ebti-D0` while `ebti-D1` is newer, **When** the app starts, **Then** it
   fetches `ebti-D0` by its name, reading neither the pointer nor the listing for that kind. When the pinned release
   fails (deleted by retention, misspelled, unverifiable), the app falls back once to the newest release of the kind,
   resolved as without a pin, logs that the pin was not honoured, and Admin › Data names the release in use.
5. **Given** an existing `store/index_meta.json` and `data/taric.jsonl`, **When** the app starts, **Then** nothing is
   listed or downloaded. Local development is unchanged.
6. **Given** `CARGOLINT_DEMO_STORE_URL` and `CARGOLINT_DEMO_STORE_SHA256` set and the repository setting empty,
   **When** the app starts, **Then** it fetches the demo archive as feature 011 specifies, unchanged.
7. **Given** a release archive holding any path outside its kind's allowed paths, **When** the app fetches it,
   **Then** the archive is refused and nothing is unpacked.
8. **Given** the latest release's metadata cannot be read, or names no release of a kind (for example `demo-store-v1`
   is still the latest release), **When** the app starts, **Then** it lists the repository's releases through the API
   and takes the newest complete releases of the kind from the listing. When the listing cannot be read either, a
   pinned release is still fetched by its name; without a pin the EBTI kind stops the app with the error naming both
   routes and the TARIC kind opens the app without TARIC.
10. **Given** the pointer names releases of a kind that no longer exist or fail (a stale `current` block, left by two
    runs that overlapped), while the listing holds a good complete release of the kind, **When** the app starts,
    **Then** after the pointer's candidates fail it reads the listing, fetches the newest complete release of the
    kind it has not tried, and opens with it.
9. **Given** every TARIC candidate fails while the EBTI release is fetched (or present), **When** the app starts,
   **Then** it opens without a TARIC snapshot: an error message on the page names the TARIC releases and the reasons,
   the Origin box reads "TARIC not loaded", and the next start fetches TARIC again since its marker is missing.

---

### User Story 4 - The clerk sees how current each part is (Priority: P2)

The Origin box shows the TARIC snapshot date and the date of the EBTI rulings. When the TARIC snapshot is older than
40 days or the rulings are older than 45 days, a yellow warning in the box names the old part, its age and the limit.
Admin › Data shows the same dates with their source versions and the releases in use.

**Why this priority**: it is the clerk-facing goal of the feature. It is independent of the scripts: it works on any
store that records its dates, and on the current demo store with its build date.

**Independent Test**: AppTest on fake knowledge bases with chosen dates and a fixed "today".

**Acceptance Scenarios**:

1. **Given** a TARIC snapshot of 2026-11-02 and rulings of 2026-11-01 on 2026-11-13, **When** the main page renders,
   **Then** the Origin box reads "TARIC snapshot 2026-11-02 · EBTI rulings 2026-11-01" and shows no warning.
2. **Given** a TARIC snapshot 41 days old, **When** the page renders, **Then** a yellow warning in the Origin box reads
   "TARIC snapshot is 41 days old (limit 40 days)." A snapshot exactly 40 days old shows no warning.
3. **Given** rulings 46 days old, **When** the page renders, **Then** the warning reads "EBTI rulings are 46 days old
   (limit 45 days)." Rulings exactly 45 days old show no warning.
4. **Given** both parts older than their limits, **When** the page renders, **Then** one warning names both.
5. **Given** no TARIC snapshot, **When** the page renders, **Then** the box reads "TARIC not loaded" for that part, as
   today, and the rulings' date still shows.
6. **Given** a store without a rulings date (demo-store-v1, or a local `--demo` build), **When** the page renders,
   **Then** the box shows the indexes' build date as "EBTI rulings built 2026-10-16", and the age rule uses that date.
7. **Given** any of these states, **When** Admin › Data renders, **Then** it shows for each part the snapshot date,
   the source version and the release in use when the app fetched one.

---

### User Story 5 - The schedules exist but stay off until switched on (Priority: P3)

A GitHub Actions workflow holds two scheduled jobs, the TARIC refresh daily and the EBTI refresh monthly, and a manual
trigger. The scheduled jobs run only once the maintainer switches them on with a repository variable; until then the
maintainer runs the scripts by hand. GitHub disables the schedules of a repository without activity for 60 days; the
README says so and how they are re-enabled.

**Why this priority**: the scripts deliver the value on their own; the workflow only automates them, and the user asks
for it switched off at first.

**Independent Test**: an offline test reads the workflow file and checks the two crons, the manual trigger and the
switch.

**Acceptance Scenarios**:

1. **Given** the workflow file, **When** it is read, **Then** it holds a daily cron for the TARIC job, a monthly cron
   for the EBTI job, a manual trigger that chooses the kind, a switch on both scheduled jobs, and the EBTI job
   waiting for the TARIC job so that a run of both publishes one release at a time.
2. **Given** the switch is not set, **When** a schedule fires, **Then** both jobs are skipped and nothing is
   downloaded or published.
3. **Given** the switch is on, **When** the TARIC schedule fires, **Then** the job checks the repository out without
   keeping the token in the checkout, installs the project, runs the TARIC script with the repository's token and
   publishes as the script does by hand; the EBTI job also reads the `OPENROUTER_API_KEY` repository secret for the
   embeddings.

---

### Edge Cases

- The distribution's folder holds files of two batches (a new batch being published): the newest batch that has all
  six objects is taken, so a newest batch missing an object is passed over for the older complete one (usually
  "nothing new"); when no batch is complete, the run is refused (exit 1), so nothing is published half-way.
- The distribution cannot be reached or its listing cannot be read: the TARIC command stops with the reason (exit 1)
  and publishes nothing; the existing releases stay.
- A download is interrupted: nothing is published. The six TARIC files are immutable and named by their batch, so the
  next run resumes them; the EBTI extract is regenerated daily under one name, so the next run removes the partial
  file and downloads afresh, never splicing two extracts.
- A publish is interrupted (the release created without both assets, or a draft left behind): the release is
  incomplete. It is never "nothing new", never kept by retention and never chosen by the app; the next run of its
  kind deletes the remnant and publishes afresh.
- The EBTI extract has fewer valid rulings than requested: all of them are taken.
- The extract's date cannot be read (an entry without a timestamp): the command refuses it rather than guess.
- No previous EBTI store can be found (no EBTI release yet and no `--previous`): a setup error that names
  `--previous demo-store-v1` and `--full-embed` as the two ways out.
- The previous store cannot be downloaded or is incomplete (a file of the layout missing): a setup error (exit 2)
  before any embedding call.
- A kept ruling's text changed since the previous store: it is embedded again, never served with the old vector.
- A kept ruling's code, chapter or validity changed but its text did not: its vector is reused and its metadata is
  written from the new extract, so the CN-8 precedent filter, which reads the code from the vector store, sees the
  current one.
- The default work folder exists from an earlier run: refused (exit 2) without `--force`, emptied with it; a folder
  given with `--out` is never emptied.
- The previous store's nomenclature index does not match the committed nomenclature (another edition or chunk count):
  the command refuses to copy it and names `--full-embed`.
- A complete release of the right name, or a newer one, already exists when the command would publish without
  `--force`: it is the "nothing new" case, exit 0. An incomplete release of the right name is rebuilt.
- Retention finds a release of the kind whose name is not `<kind>-YYYY-MM-DD`: it is left alone and counted neither
  as kept nor as old.
- Retention deletes a release the settings pin: at the next cold start the pin fails, the app falls back to the newest
  release of the kind and logs it, and Admin › Data names the release in use; the maintainer changes or removes the
  pin. A pin lasts only while its release is among the two newest complete releases of its kind: to hold a rollback
  longer, switch the schedule off.
- A listed release of the kind lacks its archive or its metadata, or is a draft: it is skipped as if it did not
  exist, by the scripts and by the app.
- The repository's latest release is of neither kind (`demo-store-v1` before the first refresh; a release made by
  hand): its metadata is missing or has no `current` block, and the app falls back to the listing.
- The app's fetch reaches the metadata but not the archive, or the archive's checksum differs: nothing is unpacked
  from it; the next newest release of the kind is tried once.
- A TARIC archive holds anything but `data/taric.jsonl`, or an EBTI archive anything outside `store/`, or any `..`
  path: refused, nothing unpacked.
- The unpacking is interrupted: `store/index_meta.json` is written last and `data/taric.jsonl` is written under a
  temporary name and renamed, so the next start fetches again.
- Both the feature-011 settings and the repository setting are set: the repository setting wins and the feature-011
  settings are ignored, with a note in the log; the feature-011 fetch is not run.
- The TARIC kind cannot be fetched while the EBTI store is there: the app opens without TARIC, with the reason on the
  page; the EBTI kind failing stops the app.
- The rulings' snapshot date is missing from the store: the build date stands in, labelled "built".
- A snapshot date that cannot be parsed, or lies in the future: shown as recorded, treated as unknown, and the warning
  says the age is unknown.
- The clock passes midnight while the app runs: the age is computed from the day the page renders.

## Requirements *(mandatory)*

### Functional Requirements

**The TARIC refresh**

- **FR-001**: `python scripts/refresh_taric.py` MUST find the current full extract in the `xml/tot/` folder of the
  Swedish Customs file distribution, read the batch id and the snapshot date from the six object files' names as the
  loader does (GoodsNomenclature, Measure, MeasureType, GeographicalArea, DutyExpression, Regulation), take the newest
  batch whose six object files are all present (an incomplete newer batch is passed over), and refuse a folder in
  which no batch is complete.
- **FR-002**: It MUST compare that snapshot date with the newest complete TARIC release (a release of the kind that
  carries both assets and is not a draft) and, unless the batch's date is newer, stop with "nothing new" before
  downloading anything, exit code 0. An incomplete release of the batch's date (an interrupted publish) does not
  count: the run deletes the remnant and publishes afresh. `--force` downloads, rebuilds and publishes the batch
  regardless: an existing complete release of that date is deleted and created afresh from the new build, never
  patched asset by asset.
- **FR-003**: It MUST download the six files into a folder of their own under `rag.loader.TARIC_RAW_DIR` (normally
  `data/raw/taric/`, the constant read at call time) and run the existing
  TARIC load on that folder: signature verification against the pinned key, parsing, validity on the snapshot date,
  CN-8 reconciliation, the atomic write of `data/taric.jsonl` and the register row in `data/SOURCES.md`, as feature
  002 specifies. It MUST NOT touch any search index, the ruling store or `store/index_meta.json`, and MUST make no
  embedding or model call.
- **FR-004**: It MUST pack `data/taric.jsonl` as the one entry of `cargolint-taric-<date>.zip`, write the metadata
  file (FR-012), publish the release `taric-<date>` with both as its assets, mark it the repository's latest release
  (FR-012), and then apply retention (FR-010).
- **FR-005**: Exit codes: 0 published or nothing new; 1 the source was refused (listing unreadable, no complete
  batch, signature, parse); 2 setup or usage error (gpg or the key copy missing, the release service missing or not
  signed in, bad options); 3 the release service failed after the build (a create, the marking as latest, a deletion
  or the pruning): the message names the step and the release and says what the service did before it failed, since
  such a run may have deleted an incomplete remnant or created a release without marking it latest or pruning; the
  next run of the kind repairs it — it still prunes and re-marks the latest release when needed even when the source
  has nothing new. A run that exits 1 or 2 has published nothing and deleted nothing. `--no-publish` builds and packs
  without the release service. `--repo OWNER/NAME` names the repository for the release service (default: the
  checkout's remote), and `CARGOLINT_GH` names the `gh` executable as `CARGOLINT_GPG` names `gpg`; both commands
  share them.

**The EBTI refresh**

- **FR-006**: `python scripts/refresh_ebti.py` MUST download the current EBTI full extract afresh into the work area
  (`build/DDS2-EBTI_Full.zip`, after removing an earlier file and any partial download of it; never the loader's copy
  under `data/raw/`; `--extract <zip>` names a downloaded file to use instead), read the extract's snapshot date from
  the newest entry inside it, and stop with "nothing new" when a complete release `ebti-<date>` or a newer one exists,
  before downloading the previous store or making any embedding call, exit code 0. An incomplete `ebti-<date>` is
  deleted and published afresh. `--force` rebuilds the extract's date regardless: an existing complete release of
  that date is deleted and created afresh from the new build.
- **FR-007**: It MUST keep the rulings of the twelve indexed chapters that are valid on the run date, with holder names
  and addresses dropped, as the loader does. The store's size MUST be configurable through `CARGOLINT_EBTI_RULINGS`
  (read at start; `--rulings` overrides it): a positive integer, or the literal `all`. The default is `5000` for the
  demo store. With a number it MUST choose that many with the demo store's rule (feature 011, FR-002): rulings with
  text only, up to half under the preferred codes one code in turn, the rest spread over the chapters; within each code
  the previous store's rulings come first, so a kept ruling leaves only when it is no longer in the extract or its
  code's share falls; the store never holds more than the requested number, and new rulings take only the places freed
  by expired, withdrawn and dropped ones. With `all` it MUST keep every valid ruling with text, for a production store.
  A value that is neither a positive integer nor `all` is a setup error (exit 2). The same extract and previous store
  always give the same choice.
- **FR-008**: It MUST take the previous store from the newest complete EBTI release, or from the release or local
  folder named by `--previous` (`demo-store-v1` on the first run), refusing a previous store that lacks a file of the
  layout before any embedding call, and build the store in a work folder (`--out`, default `build/ebti-<date>/`, which
  must be new or empty, checked only after the "nothing new" check so that a re-run after a successful run exits 0;
  with `--force` the default work folder is emptied first, a folder given with `--out` never) in the layout of
  demo-store-v1: the nomenclature index and its BM25 file copied from the previous store; for each
  chosen ruling its vector copied from the previous store when the ruling was there with the same text, with its text
  and metadata (code, chapter, validity) written from the new extract's record, else embedded; `bti_docs.jsonl`; and
  `index_meta.json` with the loader's fields, of which `embedding_model`, `dimension`, `nomenclature_chunks` and
  `edition_year` are carried over from the previous store (they describe the copied nomenclature index) and
  `built_at`, `bti_rulings` and `embedding_usage` are recomputed for this build (the previous store's `demo_store`
  and `refresh` blocks are dropped), plus the rulings' snapshot date, the source version, the rulings requested (the
  number or `all`), the count the extract held, and the counts of rulings reused, embedded and dropped. It MUST
  refuse to reuse a previous store built with another embedding model, or whose nomenclature index does not match the
  committed nomenclature,
  naming `--full-embed`. With `--full-embed` it MUST embed every nomenclature chunk and every chosen ruling afresh and
  copy nothing. The repository's `store/`, `data/bti_subset.jsonl` and `data/raw/` MUST NOT be touched.
- **FR-009**: It MUST pack the work folder's `store/…` (and nothing else) as `cargolint-ebti-<date>.zip`, write the
  metadata file, publish `ebti-<date>` with both as its assets, mark it the latest release, and apply retention. Exit
  codes as FR-005; a missing `OPENROUTER_API_KEY` is a setup error found before the download.

**Releases, retention and metadata**

- **FR-010**: After publishing, each script MUST keep the two complete releases of its kind with the newest snapshot
  dates (by the date in the name) and delete every other release of that kind, older ones and incomplete ones (an
  asset missing or a draft), together with its tag. It MUST never delete a release of another kind or one whose name
  is not `<kind>-YYYY-MM-DD`. A run that publishes nothing still applies that retention and, when the repository's
  latest release is older than the newest complete release of its kind (by publish time) or is incomplete, re-marks
  that release as latest (unless `--no-publish`), so a failed prune or mark-latest repairs itself on the next run even
  when the source has nothing new.
- **FR-011**: Release names are `taric-YYYY-MM-DD` and `ebti-YYYY-MM-DD`, where the date is the data's snapshot date
  (the TARIC batch's date; the EBTI extract's date), never the day of publishing.
- **FR-012**: Every release MUST carry `metadata.json` with: `kind`, `release`, `snapshot_date`, `source` (the source's
  URL), `source_version` (TARIC: the batch id and its date; EBTI: "full extract of <date>" and the chapters),
  `built_at`, `archive`, `sha256`, `size`, `entries` (the archive's root paths) and `current`: for each kind, the
  names of the complete releases that remain after this run's publish and retention, newest first, at most two (the
  script computes it from a listing it reads immediately before writing the metadata, after the build and the pack,
  never from the listing of its "nothing new" check, which may be many minutes old). An EBTI release adds
  `embedding_model`, the counts
  `rulings`, `reused`, `embedded` and `dropped`, and `vectors_from` (the previous store). The release just published
  MUST be marked the repository's latest release, so that the latest release's `metadata.json`, reachable through
  GitHub's fixed download address for the latest release, is the app's pointer to both kinds (FR-015).
- **FR-013**: When the app fetches a release it MUST keep the metadata beside the data (`store/release.json` for the
  EBTI kind, `data/taric_release.json` for the TARIC kind), so that Admin › Data can name the release in use.
  `data/taric_release.json` is git-ignored like `data/taric.jsonl` (`store/` already is).

**Settings and the fetch at a cold start**

- **FR-014**: The settings MUST read from the environment `CARGOLINT_RELEASE_REPO` (the repository that publishes the
  releases, `owner/name`; empty by default: nothing is fetched from releases), the optional pins
  `CARGOLINT_EBTI_RELEASE` and `CARGOLINT_TARIC_RELEASE` (a release name each; empty by default: the newest of the
  kind), and `CARGOLINT_EBTI_RULINGS` (a positive integer or `all`; `5000` by default) for the EBTI store size of
  FR-007.
- **FR-015**: Once per server process, before it opens the knowledge base and only when the repository setting is set,
  for each kind whose files are missing (`store/index_meta.json` for the EBTI kind, `data/taric.jsonl` for the TARIC
  kind), the app MUST resolve the kind's candidates, in this order: the pinned release alone when a pin is set; else
  the names in the `current` block of the latest release's metadata, read once per process from the repository's
  fixed latest-release download address (no listing, no token, outside the API's rate limit); else, when that file
  cannot be read or names no release of the kind, or when every candidate the pointer named has failed, the
  repository's release listing through the API, read once per process, taking the newest complete releases of the
  kind by the date in their names that have not been tried, at most two. Then, for each candidate until one
  succeeds: read its metadata; download the archive to a temporary file; verify its SHA-256
  against the metadata before unpacking anything; refuse any entry outside the kind's allowed paths (`store/…`, or
  exactly `data/taric.jsonl`) or with a `..` part; unpack with the marker last (`store/index_meta.json`;
  `data/taric.jsonl` through a temporary name). A spinner with a short message MUST show while it fetches. Nothing is
  read when neither kind is missing.
- **FR-016**: When a candidate fails at any step, the app MUST try the kind's next candidate once: the next newest
  release, or for a pin the newest release of the kind resolved as without a pin, with a log line that the pin was
  not honoured. When every candidate the pointer named has failed, the app MUST read the listing and try the newest
  complete release of the kind it has not tried, so that a stale pointer (left by two runs that overlapped) never
  stops the app while a good release is listed. When every candidate of the EBTI kind fails, or none can be resolved
  (pointer and listing both unreadable), the app MUST stop with an error naming the releases, the routes and the
  reasons. When every candidate of the TARIC kind fails, the app MUST NOT stop: it opens
  without a TARIC snapshot, as it does today when `data/taric.jsonl` is missing, shows the failure as an error
  message on the page naming the releases and the reasons, and the Origin box reads "TARIC not loaded"; the marker
  stays missing, so the next start fetches again. Nothing of a failed release is ever unpacked.
- **FR-017**: When the repository setting is empty and `CARGOLINT_DEMO_STORE_URL` is set, the feature-011 fetch MUST
  run unchanged. When the repository setting is set, the feature-011 settings are ignored and the feature-011 fetch
  is not run, with a note in the log when they are set too.
- **FR-018**: `python -m rag.loader` MUST record the extract's snapshot date and source version in
  `store/index_meta.json` for a local build from the extract. It reads the date from the extract when it cuts
  `data/bti_subset.jsonl` and keeps it beside the subset (`data/bti_subset.meta.json`, git-ignored with it), so that
  a later build that reuses the subset records the date of the extract the subset came from, not of whatever file is
  on disk. A `--demo` build, which has no extract, and a subset cut before this feature leave them unset.

**What the clerk sees**

- **FR-019**: The Origin box's caption MUST read `TARIC snapshot <date> · EBTI rulings <date>`, with "TARIC not loaded"
  in place of the first part when there is no snapshot, and "EBTI rulings built <date>" when the store records no
  rulings date.
- **FR-020**: When the TARIC snapshot is older than 40 days, or the rulings older than 45 days, counted in whole days
  from the day the page renders, a native yellow warning in the Origin box MUST name the part, its age and the limit.
  At exactly the limit there is no warning. One warning covers both parts when both are old. The limits are named
  configuration constants.
- **FR-021**: Admin › Data MUST show, for each part, the snapshot date, the source version and the release in use when
  the app fetched one. The disabled "Refresh (later)" button stays as it is.
- **FR-022**: All UI changes use native Streamlit elements; no CSS is added (constitution 1.10.0).

**The workflow, the docs and the tests**

- **FR-023**: `.github/workflows/refresh.yml` MUST hold a `taric` job on a daily cron and an `ebti` job on a monthly
  cron, a manual trigger with a choice of kind, and on both scheduled jobs the switch: they run only when the
  repository variable `CARGOLINT_REFRESH` is `on`. The jobs check the repository out without keeping the token in
  the checkout (`persist-credentials: false`, as the test workflow does), and run the two scripts with the
  repository's token, the `ebti` job also with the `OPENROUTER_API_KEY` repository secret, with time limits. Runs
  go one at a time (a concurrency group), and within a run the `ebti` job waits for the `taric` job (`needs`), so a
  manual run of both kinds never publishes two releases at once and each job's `current` block sees the other's
  release.
- **FR-024**: The README MUST gain a "Knowledge base refresh" section: the two commands and their options (`--force`,
  `--no-publish`, `--previous`, `--full-embed`, `--rulings`, `--out`, `--extract`, `--repo`, and `CARGOLINT_GH`), the
  releases, their completeness and retention, the metadata file and the latest-release pointer, the four settings
  and how to switch the demo from the feature-011 settings once both kinds are published, that a pin lasts only while
  retention keeps its release, the exit codes, the warning limits, how the workflow is switched on, that the scripts
  are run by hand only while the schedule is off or after checking the Actions tab (two runs must not publish at
  once), and that GitHub disables the schedules after 60 days without repository activity (re-enabled from the
  Actions tab). `.env.example` MUST list the
  four settings. The "Demo deployment" section follows.
- **FR-025**: Every test MUST run offline on recorded fixtures: a saved directory listing, the signed fixture batch,
  a tiny extract, a tiny previous store, fake embeddings, a fake release service, a release listing and `file:`
  releases. The suite's offline guard (`tests/conftest.py`) MUST refuse, in every test not marked live, besides the
  OpenRouter clients as today: the release service's `gh` runner, the loader's download, and any `urlopen` of a URL
  that is not `file:`, so that a test that misses a fake fails before it can reach a source or act on the
  maintainer's own releases. No test reaches the EU sources, GitHub or OpenRouter.

### Key Entities *(include if feature involves data)*

- **Release**: one published snapshot of one kind. Name `<kind>-YYYY-MM-DD`; assets: the archive and `metadata.json`.
  Complete when it carries both assets and is not a draft; only complete releases count for "nothing new", retention
  and the app. At most two complete ones per kind are kept; the newest is the one the app uses unless a pin names
  another. The release published last is the repository's latest release, and its metadata is the app's pointer.
- **Metadata file**: the release's description (FR-012): snapshot date, source version, checksum, counts, and the
  `current` block naming the complete releases of both kinds.
- **TARIC snapshot**: `data/taric.jsonl` with its snapshot record (date, batch) as feature 002 defines it; the TARIC
  kind's archive holds exactly this file.
- **EBTI store**: `store/…` as feature 011 defines it (`index_meta.json`, `bm25.pkl`, `chroma/`, `chroma-bti/`,
  `bti_docs.jsonl`), now with the rulings' snapshot date, source version and reuse counts in `index_meta.json`; the
  EBTI kind's archive holds exactly this folder.
- **Previous store**: the EBTI store the refresh starts from: the newest EBTI release, `demo-store-v1`, or a local
  folder. Its vectors are reused for the rulings it shares with the new choice.
- **Freshness limit**: 40 days for the TARIC snapshot, 45 days for the rulings; a part older than its limit is "old".
- **Refresh run**: one run of a script: nothing new, published, refused, a setup error, or a service failure after
  the build (exit 3).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A TARIC refresh that finds a new batch completes in under 10 minutes on a laptop, measured by the author
  on the first real run (today's batch: 34 MB of signed files; the load itself takes about 30 s).
- **SC-002**: An EBTI refresh with the default 5,000-ruling bound completes in under 30 minutes on a laptop, measured
  by the author on the first real run (the 397 MB extract and the 150 MB previous store are downloaded; only the new
  and changed rulings are embedded, a few hundred a month, where the full build embedded 79,500 texts in about 90
  minutes). A production refresh with `all` embeds every valid ruling on its first run (about 74,000 texts in the
  twelve chapters, comparable to the full build) and, once that store exists, later runs embed only the new and
  changed rulings and complete within the same 30 minutes.
- **SC-003**: The end-to-end evaluation (`tests/eval/e2e_eval.py`, 120 lines), run against the refreshed EBTI store
  and against demo-store-v1 in one session with the same settings, three runs each (`--repeat 3`, the project's
  method) and the rulings' validity judged on the run day (`--as-of`, a new option of the evaluation: on the set's
  build date, 2026-10-23, a ruling issued later could never vote, so a refreshed store could only lose), gives a
  majority-right count for the refreshed store no more than 2 lines below demo-store-v1's (a better result passes).
  The author runs both.
- **SC-004**: Both dates appear in the Origin box and in Admin › Data, and the warning appears exactly when a part is
  older than its limit. Offline UI tests cover each state of User Story 4.
- **SC-005**: With the three release settings and `CARGOLINT_EBTI_RULINGS` unset, local behaviour is unchanged and
  the current demo's secrets keep working: the offline suite passes, and the demo opens as before on its first
  deployment after the merge. The demo keeps the 5,000-ruling bound.
- **SC-006**: A wrong or missing checksum, an unexpected path, or an unreachable archive unpacks nothing, and the
  fallback to the next newest release works. Offline tests cover this.
- **SC-007**: After a refresh, at most two releases of that kind exist (exactly two from the second refresh on),
  every one of them complete, and releases of other kinds are untouched; an offline test on the fake service covers
  it, and the author checks it on the first real run.
- **SC-008**: No test reaches a live source: the suite's offline guard, extended to the release service's `gh`
  runner, the loader's download and non-`file:` URLs, holds, and the tests use recorded fixtures.

## Assumptions

- The choice of rulings stays the demo store's within the configured bound: the twelve chapters, the eval set's and the
  sample files' codes first. The default is 5,000 for the demo; `all` keeps every valid ruling for a production store.
  About 2,000 new valid rulings a month arrive in the twelve chapters; with a number only the chosen ones enter.
- The previous store on the first run is `demo-store-v1`, named with `--previous`; later runs start from the newest
  EBTI release.
- The release service is GitHub releases of this repository, used through the `gh` command line tool: signed in on
  the maintainer's laptop, and with the job's token in GitHub Actions. The repository is public, so the releases are,
  as demo-store-v1 is. The app reads the latest release's metadata and the release assets from the public download
  addresses without a token, once per cold start; it reads the release list through the API (60 requests an hour
  for every caller behind one address, and Community Cloud apps share a few addresses) only as the second route.
- The demo's secrets are switched only once an EBTI and a TARIC release both exist, since the release fetch replaces
  the feature-011 archive for both parts.
- The archive's checksum comes from the release's metadata file, read from the same place over HTTPS, in place of the
  feature-011 checksum secret.
- The repository setting is empty by default, so a local clone fetches nothing unless the maintainer sets it; the
  cloud demo's secrets set it once, and the demo then follows the schedule on its own.
- The workflow's switch is a repository variable; the crons run at 05:30 UTC daily (TARIC) and at 06:00 UTC on the
  first of the month (EBTI).
- Two runs never publish at the same time: the workflow serializes its runs (the concurrency group) and its jobs
  (`needs`), and the maintainer runs the scripts by hand only while the schedule is off, as the brief says, or after
  checking in the Actions tab that no job is running. Two runs that overlap anyway can leave a stale `current` block
  or delete the other's draft; the app survives a stale pointer through the listing fallback (FR-016), and the next
  publish corrects the pointer.
- `demo-store-v1` stays as it is. It belongs to no kind, so retention never touches it. It is the repository's
  latest release until the first refresh, which is why the app falls back to the listing when the latest release has
  no metadata or no `current` block.
- Publishing the TARIC snapshot in a public release stands as decided for feature 011.
- The evaluation that decides SC-003 is the end-to-end evaluation, three runs per store with the majority compared,
  validity on the run day, run by the author in one session.
- A pin is a rollback for the time until the next refresh of its kind: retention keeps two complete releases and
  does not know the demo's secrets.
