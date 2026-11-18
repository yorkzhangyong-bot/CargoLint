# Contract: settings and the knowledge-base scripts (feature 014a)

## 1. Settings

| Variable | Values | Default | Read by | On a bad value |
|---|---|---|---|---|
| `CARGOLINT_EBTI_CHAPTERS` | `all` in any case (lower-cased, as `CARGOLINT_EBTI_RULINGS` is), or chapters `01`–`99` and ascending ranges, comma-separated (`27,34,38`, `61-64`) | `all` | the EBTI refresh, the loader, `rag.bti` | `ValueError` when the settings are read: the app does not start, the refresh exits 2 ("EBTI refresh not started: …"), the loader exits 2 |
| `CARGOLINT_CUSTOMS_WORDING` | `on`, `off` | `off` | the HS-6 step (`ClassifyContext`), the HS-6 evaluation | the same |
| `CARGOLINT_EBTI_RULINGS` | unchanged (feature 013): a positive integer or `all` | `5000` | the EBTI refresh | unchanged |

`.env.example` lists both new variables with their defaults and one line each on what they do.

## 2. Commands

| Command | Change |
|---|---|
| `python scripts/refresh_ebti.py` | new `--chapters SPEC` (over the setting, for one run); the extract's rulings are filtered by the chapters (all by default); the log names the count of valid rulings and of chapters before anything is embedded; everything else as feature 013 (`--rulings`, `--previous`, `--no-publish`, `--out`, `--extract`, `--force`, `--full-embed`, exit codes) |
| `python -m rag.loader` | `--bti-chapters` defaults to the setting (all) instead of the twelve chapters; `all` is accepted; an existing `data/bti_subset.jsonl` is reused only when its sidecar names the same chapters, and its source version is taken from the sidecar; one cut for other chapters stops the loader with exit 2 and "rerun with --force" (review round 1) |
| `python -m rag.bti` | `--chapters` defaults to the setting and accepts `all` and ranges |

The rebuild of the local store (FR-009) is one refresh run:

```text
python scripts/refresh_ebti.py --no-publish --rulings all --previous <copy of the current store> --out build/ebti-<date>
```

It downloads the current extract into `build/` (or takes `--extract ZIP`), reuses the vectors of the unchanged rulings
of the previous store, embeds the new and changed ones, and writes `build/ebti-<date>/store/` and its archive. It never
writes the repository's `store/`, `data/bti_subset.jsonl` or `data/raw/` (feature 013, FR-008).

## 3. Source version

`ebti_source_version(date, chapters)`: `full extract of <date>, all chapters` when the chapters are all;
`full extract of <date>, chapters 39,42,61-64,73,84,85,94,95,96` for exactly the twelve; otherwise the sorted
comma-separated list. Written to `index_meta.json` and to a release's `metadata.json`, shown by Admin › Data.
