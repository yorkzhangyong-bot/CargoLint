# Contract: TARIC load command

## Synopsis

```text
python -m rag.loader --taric [DIR] [--force]
```

`DIR` is the folder holding the extract; default `data/raw/taric/`. With `--taric` the loader runs the TARIC load only; nothing else in the knowledge base is built or touched.

## Preconditions

- A gpg executable: `CARGOLINT_GPG` (full path), else `gpg` on `PATH`, else Git for Windows' `usr\bin\gpg.exe`.
- The project copy of the Swedish Customs public key, `data/Tulltaxan_Fildistribution.asc`, whose primary fingerprint is `410160CE25CEC2FF322784E7302AC3C1D0E3E1C9` (key ID 302AC3C1D0E3E1C9).
- In `DIR`, the six object files of one batch under their original names `ObjectName_batchId_YYMMDD.xml.gz.pgp`: GoodsNomenclature, Measure, MeasureType, GeographicalArea, DutyExpression, Regulation. Other files in `DIR` are ignored.
- `data/nomenclature_2026.jsonl` (committed) for the CN-8 reconciliation.

## Steps

Any failure stops the run before anything is written.

1. Check the options (usage error → exit 2).
2. Find gpg and check the key copy's fingerprint against the pin (setup error → exit 2).
3. Find the six files: exactly one per object, one batch ID, one date (FR-003, FR-004 → exit 1).
4. If `data/taric.jsonl` exists, its snapshot date equals the date in the file names and `--force` is absent: print the skip message, exit 0 (FR-014).
5. Verify every signature against the pinned key; keep payloads in memory (FR-002 → exit 1).
6. Check that the six XML documents carry the same export id (exit 1).
7. Parse MeasureType, DutyExpression, Regulation and GeographicalArea, then goods, then measures; keep EU records valid on the snapshot date; derive `declarable` and `parent`; render duty texts; check measure SIDs and measure types ([data-model.md](../data-model.md) §3–4 → exit 1 on conflicts); drop the Meursing-table measures and the measures on codes held only as national records, logging both counts (research R-14).
8. Reconcile the CN-8 prefixes of declarable codes with CN 2026; write the mismatch log (FR-011).
9. Write `data/taric.jsonl.tmp` and the updated register to `data/SOURCES.md.tmp` (FR-013).
10. Replace `data/taric.jsonl`, then `data/SOURCES.md` (FR-025). The TARIC row never depends on `store/index_meta.json`.
11. Print the summary (FR-012); exit 0.

## Options

| Option | Meaning |
|---|---|
| `--taric [DIR]` | run the TARIC load from `DIR` (default `data/raw/taric/`) |
| `--force` | with `--taric`: rewrite `data/taric.jsonl` even when the snapshot date is unchanged. It never deletes or rebuilds a search index |
| `--demo`, `--chapters`, `--bti-chapters`, `--no-embed` | not allowed together with `--taric` (exit 2) |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | snapshot written, or skipped because it is already loaded |
| 1 | the extract was refused or could not be loaded; nothing written |
| 2 | usage or setup error (options, gpg missing, key copy missing or with another fingerprint); nothing read or written |

## Output

Summary on success (values from the 2026-10-01 extract; batch shown as a placeholder):

```text
TARIC snapshot 2026-10-01 · batch <batch> · export 3dc153a8-7542-4d91-8157-b7784f72797b
6 files verified with key 410160CE25CEC2FF322784E7302AC3C1D0E3E1C9: GoodsNomenclature_<batch>_261001.xml.gz.pgp, …
code records 22,361 (16,742 declarable) · measure records 161,959
CN-8 mismatches 105 → store/logs/taric-cn8-mismatches-2026-10-01.txt
new snapshot (or: replaced snapshot 2026-09-01)
wrote data/taric.jsonl (<size> MB) in <seconds> s
```

"code records" counts every stored suffix-80 code, parents included; it is the snapshot record's `goods_records`. "declarable" counts the leaf codes among them, which lookups return and reconciliation compares.

Progress lines from the loader's log come first; two of them give the dropped measures, for example `[loader] taric: dropped 23,184 measures (Meursing table, measure types 672, 673, 674)`.

Skip:

```text
TARIC snapshot 2026-10-01 is already loaded in data/taric.jsonl; nothing changed. Use --force to rewrite it.
```

Failure, one line naming the step, the file and the reason, for example:

```text
TARIC load refused: Measure_<batch>_261001.xml.gz.pgp: signature not made by key 410160CE25CEC2FF322784E7302AC3C1D0E3E1C9. Nothing was written.
```

## Guarantees

- Writes only `data/taric.jsonl` (via `data/taric.jsonl.tmp`), `store/logs/taric-cn8-mismatches-<date>.txt` and `data/SOURCES.md` (via `data/SOURCES.md.tmp`).
- Never touches `store/chroma`, `store/chroma-bti`, `store/bm25.pkl`, `store/bti_docs.jsonl`, `store/index_meta.json` or `data/nomenclature_2026.jsonl` (FR-022, FR-023, SC-005).
- Needs no network and no secret; prints no key material other than the public fingerprint.
- The same extract always yields the same records in the same order; only `loaded_at` differs (FR-015).

## Data-source register row

`data/SOURCES.md` gains one row: dataset "EU TARIC snapshot (Swedish Customs Tariff File Distribution, tot extract)", version "snapshot <date>, batch <batch>", retrieved = modification date of the newest of the six signed files, licence "Swedish Customs Tariff File Distribution, free of charge, no formal licence published; Swedish Customs provides the files without support; underlying data is EU TARIC from the European Commission." (confirmed by the author on 2026-10-22), URL `https://distr.tullverket.se/tulltaxan/`.

The command replaces this row in the existing register, inserts it under the table header when it is missing, or creates a minimal register (title, table header and this row) when `data/SOURCES.md` does not exist. It never reads `store/index_meta.json`, so it works on a machine where the knowledge base was never built.

## Internal interfaces used by the command

```python
# rag/pgp.py
class GpgNotFound(Exception): ...
class SignatureError(Exception): ...
def find_gpg() -> str: ...
def check_key_copy(key_path: Path, fingerprint: str) -> None: ...          # SignatureError when the copy has another fingerprint
def verify_signed(data: bytes, key_path: Path, fingerprint: str) -> bytes: ...  # returns the verified payload, else SignatureError

# rag/taric_extract.py
class ExtractError(Exception): ...
def discover_extract(folder: Path) -> ExtractSet: ...                        # six files, one batch, one date, else ExtractError
def load_extract(extract: ExtractSet, key_path: Path, fingerprint: str, cn2026_cn8: frozenset[str], log_dir: Path) -> Snapshot: ...
def write_snapshot(snapshot: Snapshot, path: Path) -> None: ...             # deterministic, atomic
def read_snapshot_header(path: Path) -> dict | None: ...                    # first line only; None when the file is absent
```
