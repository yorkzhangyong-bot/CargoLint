# Contract: the two refresh commands

Both scripts are thin entry points (`sys.path` to the repository root, then `main()` of the `rag` module); the
behaviour below is the `rag` module's and is tested there.

## `python scripts/refresh_taric.py`

```text
python scripts/refresh_taric.py [--force] [--no-publish] [--repo OWNER/NAME]
```

### Preconditions

- `gpg` and the key copy, as for `python -m rag.loader --taric` (`CARGOLINT_GPG`, `data/Tulltaxan_Fildistribution.asc`).
- Unless `--no-publish`: `gh` (`CARGOLINT_GH` or on `PATH`) signed in for the repository (`gh auth status`).
- `data/nomenclature_2026.jsonl` (committed) for the CN-8 reconciliation.

### Steps

1. Check the options (usage error → exit 2).
2. Unless `--no-publish`: check `gh` and the sign-in (setup error → exit 2).
3. Read the `tot` listing (`TOT_URL`); find the newest date whose six object files share one batch id
   (`current_batch`; a newer batch missing an object is passed over). Unreadable listing or no complete batch →
   exit 1.
4. Unless `--force`: list the releases; when a complete `taric-<date>` or a complete TARIC release with a newer date
   exists, print the "nothing new" line, apply retention and, when the repository's latest release is older than the
   newest complete TARIC release (by publish time) or is incomplete, re-mark it as latest (the service's
   latest-release query names the latest release, the listing gives the publish times), then exit 0 (an incomplete
   `taric-<date>` does not count: it is deleted in step 8 and published afresh). With `--no-publish` the check reads
   the releases only when `gh` is available, else it is skipped, and it neither prunes nor re-marks.
5. Download the six files into `<rag.loader.TARIC_RAW_DIR>/<date>/` (the loader constant read at call time; normally
   `data/raw/taric/`; resume as the loader does: the files are immutable and named by their batch).
6. Run the TARIC load on that folder (`rag.loader.load_taric(folder, force)`): its exit codes pass through
   (1 refused, 2 setup), nothing is published on either.
7. Pack `data/taric.jsonl` as `cargolint-taric-<date>.zip` (one entry, `data/taric.jsonl`) into the batch folder;
   write `metadata.json` beside it.
8. Unless `--no-publish`: re-read the listing (one `gh api` call) and write `current` into the metadata from it (the
   complete releases of both kinds after this run); delete an incomplete `taric-<date>` if one exists, or with
   `--force` the existing complete one; create the release `taric-<date>` with both assets (title "TARIC snapshot
   <date>", notes with the batch id, the counts and the size); mark it the latest release; then prune: keep the two
   newest complete TARIC releases, delete every other TARIC release with its tag. A service failure in this step →
   exit 3 naming the step and what was done before it.
9. Print the summary; exit 0.

### Output

```text
[refresh] tot listing: batch e14b8e06-f3f6-4ce1-ba9b-1423d07f6b83, snapshot 2026-11-02, 6 files
[refresh] newest TARIC release: taric-2026-10-01
[loader] downloading GoodsNomenclature_…_261102.xml.gz.pgp …
… the loader's own TARIC summary …
[refresh] wrote data/raw/taric/2026-11-02/cargolint-taric-2026-11-02.zip (2.0 MB), sha256 …
[refresh] published taric-2026-11-02 (2 assets), marked latest
[refresh] kept taric-2026-11-02, taric-2026-10-01; deleted taric-2026-09-01
TARIC refresh: taric-2026-11-02 published in 143 s
```

Nothing new:

```text
TARIC refresh: taric-2026-11-02 is already published and complete; nothing new. Use --force to rebuild and replace it.
```

Refused (exit 1) and setup (exit 2) messages start with `TARIC refresh refused:` or `TARIC refresh not started:`
and name the step and the reason; nothing is published.

## `python scripts/refresh_ebti.py`

```text
python scripts/refresh_ebti.py [--rulings N|all] [--out DIR] [--previous RELEASE|DIR] [--full-embed]
                               [--extract ZIP] [--force] [--no-publish] [--repo OWNER/NAME]
```

The store size comes from `CARGOLINT_EBTI_RULINGS` (default 5000; `all` keeps every valid ruling); `--rulings`
overrides it for one run.

### Preconditions

- `OPENROUTER_API_KEY` (setup error → exit 2, before any download).
- Unless `--no-publish`: `gh` signed in.
- `data/nomenclature_2026.jsonl`, `tests/eval/cn8_eval_set.json` and `data/samples/sample_lines.json` (committed) for
  the preferred codes.
- A previous store, unless `--full-embed`: the newest `ebti-*` release, or `--previous`.

### Steps

1. Check the options (usage error → exit 2).
2. Check the key and `gh` (setup error → exit 2); with `--no-publish`, `gh` is checked only when the previous store
   is a release, named by `--previous` or to be resolved from the listing, since it is downloaded through `gh`; a
   local folder needs none.
3. Download the extract afresh to `build/DDS2-EBTI_Full.zip` (the file and its `.part` are removed first; the loader's
   `data/raw/` copy is never touched), or use `--extract ZIP`. Read the extract's date from the newest `.csv` entry;
   none → exit 1.
4. Unless `--force`: when a complete `ebti-<date>` or a complete EBTI release with a newer date exists, print the
   "nothing new" line, apply retention and, when the repository's latest release is older than the newest complete
   EBTI release (by publish time) or is incomplete, re-mark it as latest, then exit 0, whatever the state of the work
   folder. Nothing else has been read or embedded; with `--no-publish` it neither prunes nor re-marks. An incomplete
   `ebti-<date>` does not count: it is deleted in step 12 and published afresh.
5. Resolve `--out` (default `build/ebti-<date>/`): it must be new or empty. With `--force` the default work folder is
   emptied first (a retry after a failed embedding or upload); a folder given with `--out` never is: exit 2 naming
   the folder (and, for the default folder, the two ways on: `--force` or `--out`). This check comes after step 4, so
   a same-day re-run after a successful run exits 0 although its folder remains.
6. Keep the valid rulings of the loader's twelve chapters on the run date, holder data dropped
   (`rag.bti.iter_extract`).
7. Resolve the previous store: `--previous DIR` (a folder holding `store/`), `--previous RELEASE` or the newest
   complete `ebti-*` release, downloaded into `<out>/previous/` and verified against its metadata when it has one
   (`demo-store-v1` has none; its zip is unpacked as it is, with a note). None found and no `--full-embed` →
   exit 2 naming `--previous demo-store-v1` and `--full-embed`. A store that lacks a file of the layout → exit 2.
8. Unless `--full-embed`: refuse a previous store whose `embedding_model` is not the settings' or whose
   `nomenclature_chunks` or `edition_year` differ from the committed nomenclature (exit 2, naming `--full-embed`).
9. Choose N rulings with the demo store's rule, the previous store's references kept first
   (`rag.demo_store.select_rulings(records, preferred, N, keep=…)`); with `all`, keep every valid ruling with text
   instead, with no bound.
10. Build `<out>/store/`:
    - reuse: copy `chroma/` and `bm25.pkl`; copy the vectors of the chosen rulings whose text equals the previous
      record's (`copy_vectors(..., metadatas=…)`, the metadata written from the new record so a changed code or
      validity is served); embed the others (`ChromaVectorSearch.add`); write `bti_docs.jsonl` and `index_meta.json`
      (data-model §3: the index fields carried over, `built_at`, `bti_rulings` and `embedding_usage` recomputed);
    - `--full-embed`: `rag.loader.build_indexes(index, store, settings, store_dir=<out>/store, embeddings=emb)` with
      the chosen rulings and the embeddings `main` was given (the settings' OpenRouter embeddings by default, the
      fakes in the tests; the dimension is read from the embeddings when they have one, else probed), and the same
      metadata fields with `full_embed: true`.
11. Pack `<out>/store/…` as `<out>/cargolint-ebti-<date>.zip`; write `<out>/metadata.json`.
12. Unless `--no-publish`: re-read the listing (one `gh api` call) and write `current` into the metadata from it;
    delete an incomplete `ebti-<date>` if one exists, or with `--force` the existing complete one; create `ebti-<date>`
    (title "EBTI rulings <date>", notes with the counts); mark it the latest release; prune to the two newest complete
    EBTI releases, deleting every other EBTI release. A service failure in this step → exit 3 naming the step and
    what was done before it.
13. Print the summary; exit 0.

### Output

```text
[refresh] extract DDS2-EBTI_Full.zip dated 2026-11-13, 74,312 valid rulings in 12 chapters
[refresh] newest EBTI release: ebti-2026-10-14; previous store: ebti-2026-10-14 (5,000 rulings, qwen/qwen3-embedding-8b)
[refresh] chose 5,000 rulings: 4,790 kept, 210 new; 3 changed texts; 210 dropped from the previous store
[refresh] copied the nomenclature index and 4,787 ruling vectors; embedded 213 rulings ($0.002)
[refresh] wrote build/ebti-2026-11-13/cargolint-ebti-2026-11-13.zip (149.8 MB), sha256 …
[refresh] published ebti-2026-11-13 (2 assets), marked latest
[refresh] kept ebti-2026-11-13, ebti-2026-10-14
EBTI refresh: ebti-2026-11-13 published in 684 s
```

Nothing new:

```text
EBTI refresh: ebti-2026-11-13 is already published and complete; nothing new. Use --force to rebuild and replace it.
```

### Exit codes (both commands)

| Code | Meaning |
|---|---|
| 0 | published, or nothing new |
| 1 | the source was refused: listing unreadable, no complete batch, signature, parse, an extract without a date |
| 2 | setup or usage: options, an invalid ruling count (neither a positive integer nor `all`), `gpg` or the key copy, `gh` missing or not signed in, `OPENROUTER_API_KEY` missing, no previous store, a previous store that is incomplete or of another model or nomenclature without `--full-embed`, `--out` not empty (the default work folder without `--force`, a given folder always), checked only once there is something to build |
| 3 | the release service failed after the build: a create, the marking as latest, a deletion or the pruning; or the retention or re-marking of a nothing-new run failed; the message names the step and the release and says what was done before (an incomplete remnant deleted, a release created but not marked latest or pruned); the next run of the kind repairs it, pruning and re-marking the latest release even when the source has nothing new |

### Guarantees

- The TARIC command writes only what `--taric` writes, plus `<rag.loader.TARIC_RAW_DIR>/<date>/` and the archive and metadata
  in it; it never touches a search index or `store/index_meta.json` and makes no embedding or model call.
- The EBTI command writes only `build/DDS2-EBTI_Full.zip` and `<out>/…`; it never touches the repository's
  `store/`, `data/bti_subset.jsonl`, `data/raw/` or `data/taric.jsonl`.
- A run that exits 1 or 2 has published nothing and deleted nothing; a "nothing new" run still applies retention and,
  when the repository's latest release is older than the newest complete release of its kind or is incomplete,
  re-marks that release as latest (unless `--no-publish`), so a failed prune or mark-latest repairs itself; a run that
  exits 3 names what the service did before it failed.
- `--force` never patches a release asset by asset: the release is deleted and created afresh from the one build, so
  its two assets always come from the same build.
- Retention never deletes a release of another kind or one whose name is not `<kind>-YYYY-MM-DD`; it deletes an
  incomplete release of its own kind.
- No key material is printed; the OpenRouter key and the GitHub token are read from the environment only.
- `--repo OWNER/NAME` and `CARGOLINT_GH` are shared by both commands (spec FR-005).

## In GitHub Actions (`.github/workflows/refresh.yml`)

```yaml
# GitHub disables these schedules after 60 days without repository activity: re-enable them from the Actions tab.
on:
  schedule:
    - cron: "30 5 * * *"     # taric, daily
    - cron: "0 6 1 * *"      # ebti, monthly
  workflow_dispatch:
    inputs:
      kind: { type: choice, options: [taric, ebti, both], default: taric }
permissions: { contents: write }
concurrency: refresh
jobs:
  taric:   # if: a manual run for taric or both, or a schedule with vars.CARGOLINT_REFRESH == 'on'
    timeout-minutes: 20
    steps: checkout (persist-credentials: false) → Python 3.13 → pip install -e . → python scripts/refresh_taric.py   (GH_TOKEN: github.token)
  ebti:    # needs: taric; if: ${{ !cancelled() && (the same gate for ebti) }}; timeout-minutes: 60
    steps: … → python scripts/refresh_ebti.py   (GH_TOKEN; OPENROUTER_API_KEY: secrets.OPENROUTER_API_KEY)
```

A schedule fires both crons' jobs; each job's `if` also checks which cron fired (`github.event.schedule`), so the
daily cron runs only `taric` and the monthly cron only `ebti`. With the variable unset both jobs are skipped. The
`ebti` job `needs` the `taric` job and its `if` starts with `!cancelled()`, so it still runs when `taric` was skipped
but never beside it: a manual run of `both` publishes one release at a time, and each job's `current` block sees the
other's release. The concurrency group serializes runs; it does not serialize jobs, which is why `needs` is there.
A laptop run beside a scheduled one is not serialized by anything: the maintainer runs the scripts by hand only while
the schedule is off, or after checking the Actions tab (spec Assumptions).
