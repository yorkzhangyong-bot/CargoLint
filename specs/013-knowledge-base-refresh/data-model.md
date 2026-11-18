# Data Model: Knowledge Base Refresh (Phase 1)

## 1. Release

| Field | Type | Rule |
|---|---|---|
| `kind` | `"ebti"` or `"taric"` | the two kinds; anything else (for example `demo-store-v1`) is no kind |
| `name` | string | `<kind>-YYYY-MM-DD`; the date is the data's snapshot date (FR-011) |
| `archive` | asset name | `cargolint-<kind>-<date>.zip` |
| `metadata` | asset name | `metadata.json` |

Order within a kind: by the date in the name, newest first. A release is **complete** when it carries both assets and
is not a draft; only complete releases count for "nothing new", for `current`, for retention and for the app. Retention
keeps the newest two complete releases (`KEEP_RELEASES = 2`) and deletes every other release of the kind, older or
incomplete, with their tags; names that do not match the pattern are never touched (FR-010). The release published
last is the repository's **latest** release (`gh release edit <tag> --latest` after every publish), whose
`metadata.json` is the app's pointer. `--force` deletes a complete release and creates it afresh; no asset is ever
patched in place. The listing gives each release's `published_at` (none for a draft) and the service's latest-release
query the name of the release marked latest; `repair_latest` compares the two (FR-010).

## 2. Metadata file (`metadata.json`, one per release; FR-012)

| Field | Type | TARIC value | EBTI value |
|---|---|---|---|
| `kind` | string | `taric` | `ebti` |
| `release` | string | the release name | the release name |
| `snapshot_date` | ISO date | the batch's date from the file names | the extract's date (R-02) |
| `source` | URL | `https://distr.tullverket.se/tulltaxan/` | the EBTI full-extract URL of `rag.loader.SOURCES` |
| `source_version` | string | `batch <id>, extract <date>` | `full extract of <date>, chapters 39,42,61-64,73,84,85,94,95,96` |
| `built_at` | ISO datetime, UTC | the run's time | the run's time |
| `archive` | string | `cargolint-taric-<date>.zip` | `cargolint-ebti-<date>.zip` |
| `sha256` | 64 hex characters, lower case | of the archive | of the archive |
| `size` | integer, bytes | of the archive | of the archive |
| `entries` | list of strings | `["data/taric.jsonl"]` | `["store/"]` |
| `current` | object | `{"ebti": [names], "taric": [names]}`: the complete releases of each kind left after this run's publish and retention, newest first, at most two, computed from a listing read immediately before the metadata is written | the same |
| `embedding_model` | string | absent | the settings' embedding model |
| `rulings` | integer | absent | rulings in the store |
| `extract_rulings` | integer | absent | valid rulings of the chapters the extract held |
| `reused` | integer | absent | rulings whose vectors were copied |
| `embedded` | integer | absent | rulings embedded (new or changed) |
| `dropped` | integer | absent | previous rulings not in the new store (expired, withdrawn or displaced) |
| `vectors_from` | string | absent | the previous store: a release name or `folder` |

Written by `rag.refresh.write_metadata`; read by the app's fetch (`read_metadata`), which requires `kind`,
`release` (equal to the requested name), `archive` and `sha256` and refuses the release otherwise.

## 3. `store/index_meta.json` additions (FR-008, FR-018)

The loader's fields stay (`embedding_model`, `dimension`, `built_at`, `nomenclature_chunks`, `bti_rulings`,
`edition_year`, `embedding_usage`). In a refreshed store `embedding_model`, `dimension`, `nomenclature_chunks` and
`edition_year` are carried over from the previous store (they describe the copied nomenclature index, and
`check_previous` has matched them to the settings and the committed nomenclature); `built_at`, `bti_rulings` and
`embedding_usage` are recomputed for the build; the previous store's `demo_store` and `refresh` blocks are dropped.
New:

| Field | Type | Written by |
|---|---|---|
| `ebti_snapshot_date` | ISO date or absent | `rag.loader` (a build from the extract) and `rag.refresh_ebti`; absent for `--demo` and for `demo-store-v1` |
| `ebti_source_version` | string or absent | the same, as in the metadata file |
| `refresh` | object or absent | `rag.refresh_ebti` only: `rulings_requested`, `extract_rulings`, `reused`, `embedded`, `dropped`, `vectors_from`, `full_embed` (bool) |

`rulings_requested` is the configured number, or the string `all` when the store keeps every valid ruling; the
`CARGOLINT_EBTI_RULINGS` setting (default 5000) is overridden by `--rulings`.

`KnowledgeBase.rulings_date` → `(ebti_snapshot_date, "extract")` when present, else `(built_at[:10], "built")`,
else `(None, "unknown")`.

The loader's source of the two fields is `data/bti_subset.meta.json` (`extract_date`, `source_version`, `cut_at`),
written beside `data/bti_subset.jsonl` when the subset is cut from the extract and read back when the subset is
reused, so the date is the extract's the subset came from; no sidecar (a subset cut before this feature) leaves the
fields unset. Git-ignored with the subset.

## 4. Release files kept beside the data (FR-013)

| File | Written when | Content |
|---|---|---|
| `store/release.json` | the app unpacked an EBTI release | the release's metadata plus `fetched_at` |
| `data/taric_release.json` | the app unpacked a TARIC release | the release's metadata plus `fetched_at` |

`open_knowledge_base` reads both when present (`read_release_files(root)`) into `KnowledgeBase.releases: dict[str,
dict | None]` (keys `ebti`, `taric`); a local build has none, and Admin › Data then shows no release line.
`data/taric_release.json` joins `data/taric.jsonl` in `.gitignore`. `KnowledgeBase.fetch_failures: dict[str, str]`
(kind → the reasons) is empty by default and set by `load_kb` when the TARIC kind could not be fetched; `app.main`
shows each entry with `st.error` and goes on.

## 5. Archive entries (FR-004, FR-009, FR-015)

| Kind | Allowed entries | Marker (unpacked last) |
|---|---|---|
| `ebti` | paths under `store/`, no `..` part | `store/index_meta.json` |
| `taric` | exactly `data/taric.jsonl` | `data/taric.jsonl` itself, written to `data/taric.jsonl.tmp` and renamed |

The app refuses an archive with any other entry before unpacking anything.

## 6. Settings (`agent/config.py`; FR-007, FR-014)

| Setting | Environment variable | Default | Meaning |
|---|---|---|---|
| `release_repo` | `CARGOLINT_RELEASE_REPO` | `""` | `owner/name` of the repository that publishes the releases; empty: no release fetch |
| `ebti_release` | `CARGOLINT_EBTI_RELEASE` | `""` | a pinned EBTI release name; empty: the newest |
| `taric_release` | `CARGOLINT_TARIC_RELEASE` | `""` | a pinned TARIC release name; empty: the newest |
| `ebti_rulings` | `CARGOLINT_EBTI_RULINGS` | `"5000"` | the EBTI store size: a positive integer, or `all`; `--rulings` overrides it |

Precedence in `load_kb()`: `release_repo` set → `fetch_releases` (the feature-011 settings ignored, with a log note
when they are set too); else `demo_store_url` set → `fetch_demo_store` (feature 011, unchanged); else nothing. A pin
must match the release-name pattern of its kind (a valid date, the kind of its setting), else a settings error at
start, as is a ruling count that is neither a positive integer nor `all`. A pinned release that fails falls back
once to the newest of its kind, with a log line; a pin lasts only while retention keeps its release.

## 7. Constants

| Constant | Where | Value | Use |
|---|---|---|---|
| `TARIC_STALE_DAYS` | `agent/config.py` | 40 | the TARIC snapshot's limit (FR-020) |
| `EBTI_STALE_DAYS` | `agent/config.py` | 45 | the rulings' limit (FR-020) |
| `GH_ENV` | `rag/refresh.py` | `"CARGOLINT_GH"` | the `gh` executable's path, like `CARGOLINT_GPG` |
| `KEEP_RELEASES` | `rag/refresh.py` | 2 | retention |
| `KINDS` | `rag/refresh.py` | `("ebti", "taric")` | fetch order and name pattern |
| `LATEST` | `rag/refresh.py` | `https://github.com/{repo}/releases/latest/download/{asset}` | the pointer: the latest release's `metadata.json`; tests point it at a `file:` URL |
| `API` | `rag/refresh.py` | `https://api.github.com/repos/{repo}/releases?per_page=50` | the listing, the second route; tests point it at a `file:` URL |
| `DOWNLOAD` | `rag/refresh.py` | `https://github.com/{repo}/releases/download/{tag}/{asset}` | assets; tests point it at a `file:` template |
| `TOT_URL` | `rag/refresh_taric.py` | `https://distr.tullverket.se/tulltaxan/xml/tot/` | the listing |
| `DEFAULT_RULINGS` | `rag/refresh_ebti.py` | 5000 | the default bound; `all` keeps every valid ruling |
| `EXTRACT_ZIP` | `rag/refresh_ebti.py` | `build/DDS2-EBTI_Full.zip` | the refresh's own download, removed with its `.part` before each download |
| `SUBSET_META` | `rag/loader.py` | `data/bti_subset.meta.json` | the extract date of the loader's subset (§3) |

## 8. Freshness (FR-020)

| Part | Date | Age | Old when |
|---|---|---|---|
| TARIC | `kb.taric.snapshot.snapshot_date` | `(today - date).days` | age > `TARIC_STALE_DAYS` |
| EBTI rulings | `kb.rulings_date[0]` (extract or build date) | `(today - date).days` | age > `EBTI_STALE_DAYS` |

No TARIC snapshot: no age, no warning for that part ("TARIC not loaded" stays a caption). An unparsable date: the
warning says the part's age is unknown. `today` defaults to `date.today()` and is a parameter for the tests.

## 9. Refresh run outcome

| Outcome | Exit code | Published | Local files written |
|---|---|---|---|
| nothing new | 0; 3 when its retention or re-marking fails | no (retention and, when needed, re-marking the latest release from the listing already read; neither runs with `--no-publish`) | none |
| published | 0 | the release (an incomplete one of the name deleted first), marked latest, then retention | TARIC: `data/raw/taric/<date>/`, `data/taric.jsonl`, `data/SOURCES.md`, the mismatch log; EBTI: `build/DDS2-EBTI_Full.zip`, `build/ebti-<date>/` |
| refused (source) | 1 | no, and nothing deleted | TARIC: the downloaded files only; EBTI: the extract only |
| setup or usage error | 2 | no, and nothing deleted | none (an existing default work folder is emptied only by a `--force` run that gets past the checks) |
| service failure after the build | 3 | partly, perhaps: an incomplete remnant (or, with `--force`, the old release) deleted, a release created but not marked latest or not pruned; the message says which | as "published" |
