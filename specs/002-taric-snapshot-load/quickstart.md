# Quickstart: validating the one-time TARIC load

A run guide that proves the feature end to end. Commands are for Git Bash at the repository root, with the project's `.venv`. Formats and guarantees are in [contracts/](contracts/), meanings in [data-model.md](data-model.md).

## Prerequisites

1. **gpg** — `gpg --version` shows 2.4.x (it ships with Git for Windows). In PowerShell, or if `gpg` is not on `PATH`, point to it explicitly, for example `export CARGOLINT_GPG="C:/apps/Git/usr/bin/gpg.exe"`.
2. **Public key copy** — `data/Tulltaxan_Fildistribution.asc`; `gpg --show-keys data/Tulltaxan_Fildistribution.asc` shows fingerprint `4101 60CE 25CE C2FF 3227 84E7 302A C3C1 D0E3 E1C9`.
3. **Extract** — the six object files of one batch from `https://distr.tullverket.se/tulltaxan/xml/tot/` in `data/raw/taric/`, under their original names `ObjectName_batchId_YYMMDD.xml.gz.pgp`. On the author's machine they are in place for batch `3dc153a8-7542-4d91-8157-b7784f72797b`, dated 261001. The unpacked `.xml` files in that folder are ignored.

## Scenarios

| # | Proves | Steps | Expected |
|---|---|---|---|
| A | SC-003 | `pytest -q` | all pass offline; signature tests show "skipped: gpg not found" only on a machine without gpg |
| B | US1, FR-001–FR-012 | `python -m rag.loader --taric` | summary with snapshot date, batch, six verified files, for the 2026-10-01 extract 22,361 code records (all suffix-80 codes valid on the date, parents included), 16,742 of them declarable, and 161,959 measure records, 105 CN-8 mismatches and the log path; the progress log names 23,184 dropped Meursing measures and 1 measure on a national-only code; `head -c 300 data/taric.jsonl` shows the snapshot record first |
| C | SC-002, FR-014 | `sha256sum data/taric.jsonl`; run B again; `sha256sum` again | second run prints "already loaded … nothing changed" and exits 0; both hashes equal |
| D | FR-015 | `cp data/taric.jsonl /tmp/before.jsonl`; `python -m rag.loader --taric --force`; `diff <(tail -n +2 /tmp/before.jsonl) <(tail -n +2 data/taric.jsonl)` | no difference after line 1; line 1 differs only in `loaded_at` |
| E | FR-002–FR-004, FR-013 | copy the folder to `/tmp/taric-bad` three times and (1) delete one object file, (2) add a second Measure file with another batch, (3) flip one byte in a signed file; run `python -m rag.loader --taric /tmp/taric-bad` for each | each run exits 1, names the file and the reason; `data/taric.jsonl` hash unchanged |
| F | SC-005, FR-022, FR-023 | `sha256sum store/bm25.pkl store/chroma/chroma.sqlite3 store/chroma-bti/chroma.sqlite3 data/nomenclature_2026.jsonl` before and after B–D | all hashes unchanged |
| G | US3, FR-017–FR-019 | `python -c "from rag.taric import TaricStore; s = TaricStore.from_jsonl('data/taric.jsonl'); [print(x.code, x.description[:40], len(x.measures)) for x in s.lookup_taric('73181558')]"`; repeat for an unsubdivided CN-8, an unknown CN-8 and `'1234'` | 7318155810, 7318155860, 7318155890, each with China and erga omnes import measures, anti-dumping ones with their additional codes; one code ending in 00; `[]`; `ValueError` |
| H | US4, FR-024, SC-004 | restart the Streamlit server (it never reloads `ui/*.py`); open the sidebar "Knowledge base" expander; then rename `data/taric.jsonl`, restart, run the sample check | caption `TARIC snapshot 2026-10-01 · 105 CN-8 mismatches`; after the rename `TARIC not loaded` and the sample check works as before |
| I | SC-007 | log the knowledge-base load time at app start with and without `data/taric.jsonl`; time ten lookups | difference at most 10 s; each lookup under 1 s |
| J | SC-006 | `time python -m rag.loader --taric --force` | well under 30 minutes (the full load took about 20 s on the 2026-10-01 extract) |

## Acceptance against EZT-online (SC-001)

1. Pick 20 CN-8 codes beneath the labelled set's subheadings 3924.90, 3926.90, 4202.21, 6109.10, 6203.42, 6404.11, 7318.15, 8452.90, 8518.30, 9405.21, 9503.00 and 9617.00, covering at least one CN-8 with several subdivisions and codes with anti-dumping measures for China (for example under 7318.15).
2. For each, compare the subdivisions and the China-origin import measures from `lookup_taric` (measure type, duty, additional code) with EZT-online for the snapshot date, and record the result in the acceptance table that the tasks add.
3. Mark any mismatch caused by the accepted limitation (country groups containing China, erga omnes measures that exclude China, see research R-13) as such; the author then decides whether to pick another code or extend the lookup later.
