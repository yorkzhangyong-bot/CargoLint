# Quickstart: validating the knowledge base refresh

## Offline, in the suite (no key, no network)

```bash
pytest -q                                   # the whole suite stays green
pytest -q tests/unit/test_offline_guard.py tests/unit/test_settings.py     # the extended guard, the settings
pytest -q tests/unit/test_refresh.py tests/unit/test_release_fetch.py tests/unit/test_view.py tests/unit/test_loader.py
pytest -q tests/integration/test_refresh_taric.py      # needs gpg (Git for Windows has it); skips without
pytest -q tests/integration/test_refresh_ebti.py
pytest -q tests/ui                                     # the Origin box, Admin › Data, the app's start
```

What each proves:

| Test file | Proves |
|---|---|
| `tests/unit/test_offline_guard.py` | without a fake, a test cannot reach OpenRouter, run `gh`, download, or open a non-`file:` URL |
| `tests/unit/test_settings.py` | the four settings, a pin of the wrong shape refused, an invalid ruling count refused, the two limits |
| `tests/unit/test_refresh.py` | release names, kinds and completeness; retention keeps the two newest complete of a kind and deletes the rest of it, nothing else; the metadata fields and `current`; the service's `gh` argv through a recorder; the `tot` listing parser on the recorded listing (`tests/fixtures/refresh/tot_listing.html`, expectations from `tot_listing.json`); an incomplete newest batch passed over, no complete batch refused; the extract date; the reuse partition and a reused ruling's new metadata; the workflow file parsed |
| `tests/unit/test_demo_store.py` | `select_rulings(..., keep=…)` keeps the previous store's rulings first, within the bound, deterministically, and `all` keeps every valid ruling; `copy_vectors` with metadata; the existing tests unchanged |
| `tests/unit/test_release_fetch.py` | the pointer first and no listing; the listing when the pointer is unusable or when every pointer-named candidate failed (a stale pointer); the newest complete of each kind; a pin and its fallback; the fallback to the next newest; both failing (EBTI raises, TARIC is returned); pointer and listing both unreadable without a pin; checksum, entries, `..`, markers last, release files written, nothing read when the markers exist, the legacy path untouched and the log note |
| `tests/unit/test_loader.py` | `build_bti` records the extract date beside the subset and reads it back; the release files into `KnowledgeBase.releases`; `rulings_date`; `fetch_failures` empty by default |
| `tests/integration/test_refresh_taric.py` | the TARIC command end to end on the signed fixture batch with a fake service: publish (with `current`, marked latest), nothing new, an incomplete remnant rebuilt, `--force`, a refused batch, an unreadable listing, no complete batch, `--no-publish`, retention; the loader's snapshot and register unchanged in form |
| `tests/integration/test_refresh_ebti.py` | the EBTI command end to end on a tiny extract and previous store with fake embeddings: the store's files, fields and counts, only new and changed rulings embedded, the fresh download, nothing new, the model check, an incomplete previous store, `--full-embed`, the ruling setting and `--rulings all`, the work folder with and without `--force`, retention, the repository's `store/`, subset and `data/raw/` untouched |
| `tests/ui/*` | the Origin box's caption and warning at and past the limits; Admin › Data; a failed EBTI fetch stops the app with its message, a failed TARIC fetch opens it without TARIC; the feature-011 path still runs |
| `tests/unit/test_e2e_eval.py` | the evaluation's `--as-of` option defaults to the set's build date and is recorded |

## Store size: demo versus production

The EBTI store size is a setting, `CARGOLINT_EBTI_RULINGS`; `--rulings` overrides it for one run.

- `5000` (the default) keeps the demo store's bound: about 5,000 valid rulings, the previous store's rulings first.
  The cloud demo uses this bound; its memory use and the 30-minute target (SC-002) assume it.
- `all` keeps every valid ruling with text in the twelve indexed chapters (about 74,000 today) for a production store.
  The first `all` run embeds them all, so expect about 90 minutes and about $0.27; later monthly runs start from that
  store and embed only new or changed rulings.

```bash
python scripts/refresh_ebti.py --previous demo-store-v1                     # demo: 5,000
python scripts/refresh_ebti.py --previous demo-store-v1 --rulings all       # production: every valid ruling
CARGOLINT_EBTI_RULINGS=all python scripts/refresh_ebti.py --previous demo-store-v1
CARGOLINT_EBTI_RULINGS=10000 python scripts/refresh_ebti.py --previous demo-store-v1
```

A value that is neither a positive integer nor `all` is a setup error (exit 2). `--full-embed` is separate: it
re-embeds the chosen rulings and the nomenclature when the embedding model changes; with `all` it re-embeds every
valid ruling.

## The author's real runs (spend credits or publish; run only when asked)

1. **TARIC** (SC-001, SC-007):

   ```bash
   python scripts/refresh_taric.py                       # publishes taric-2026-11-02 the first time
   python scripts/refresh_taric.py                       # "nothing new"
   gh release list                                       # taric-2026-11-02 (Latest) beside demo-store-v1
   ```

   Time the first run; under 10 minutes is the target. After the first run one TARIC release exists, two from the
   second batch on (SC-007 says at most two, every one complete).
2. **EBTI** (SC-002, SC-007), the first run from `demo-store-v1`:

   ```bash
   python scripts/refresh_ebti.py --previous demo-store-v1
   gh release list                                       # ebti-<date> beside taric-… and demo-store-v1
   ```

   Time it; under 30 minutes is the target. The summary prints the kept, embedded and dropped counts and the cost.
   Add `--rulings all` (or set `CARGOLINT_EBTI_RULINGS=all`) for a production store; the first such run takes about
   90 minutes and embeds every valid ruling.
3. **The eval comparison** (SC-003), two runs of three repeats, about $0.80 each: unpack `cargolint-ebti-<date>.zip`
   and a TARIC snapshot into a second clone (or point a scratch checkout's `store/` at the work folder's `store/`)
   and run, on the same day and with the same settings,

   ```bash
   python tests/eval/e2e_eval.py --repeat 3 --as-of <today> --tag e2e-ebti-<date>
   ```

   then the same with `demo-store-v1` unpacked (`--tag e2e-demo-store-v1-asof-<today>`). `--as-of` judges the
   rulings' validity on the run day instead of the set's build date (2026-10-23), so the rulings issued since can
   vote; without it the refreshed store could only lose. The majority right end to end of the two runs must be
   within 2 lines of each other.
4. **The demo switch** (SC-005), only once steps 1 and 2 have published both kinds (the release fetch replaces the
   feature-011 archive for both parts): in the Community Cloud secrets, add `CARGOLINT_RELEASE_REPO =
   "yorkzhangyong-bot/CargoLint"` and remove `CARGOLINT_DEMO_STORE_URL` and `CARGOLINT_DEMO_STORE_SHA256`; reboot.
   The Origin box shows both dates; Admin › Data names the releases. Before the switch, the deployed app with the
   old secrets must still open as before (the legacy path).
5. **The workflow**: it is off until the repository variable `CARGOLINT_REFRESH` is `on`. A manual run from the
   Actions tab (`kind: taric`) exercises the job with the job's token; the `ebti` job needs the
   `OPENROUTER_API_KEY` repository secret. GitHub disables the schedules after 60 days without repository activity;
   the Actions tab shows the notice and the button that re-enables them.
