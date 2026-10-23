# Quickstart: validating group measures, exclusions, the 566 filter and startup time

A run guide that proves the feature end to end. Commands are for Git Bash at the repository root, with the project's
`.venv`. Prerequisites are those of feature 002's [quickstart](../002-taric-snapshot-load/quickstart.md): gpg, the key
copy, and the six files of the 2026-10-01 extract in `data/raw/taric/`. Formats and guarantees are in
[contracts/](contracts/), meanings in [data-model.md](data-model.md), the expected figures in [research.md](research.md).

Start from the schema-1 `data/taric.jsonl` that feature 002 wrote, so scenario B exercises the rewrite, and keep a copy
for scenario J: `cp data/taric.jsonl /tmp/taric-schema1.jsonl`.

## Scenarios

| # | Proves | Steps | Expected |
|---|---|---|---|
| A | SC-005 | `pytest -q` | all pass offline: the 391 existing tests, as updated by this feature, and the new ones |
| B | FR-001–FR-004, FR-003 | `python -m rag.loader --taric` (no `--force`), with the schema-1 file in place | the progress log shows `taric: data/taric.jsonl will be rewritten: schema 1 is not supported (expected 2)`; summary as in [loader-cli.md](contracts/loader-cli.md) with `area names 314 · group memberships 2,805 · measures with excluded areas 10,581`, 22,361 code records and 161,959 measure records; `head -c 120 data/taric.jsonl` shows `"schema":2`; the file is about 28 MB |
| C | FR-014 still holds | run B again | "already loaded … nothing changed", exit 0, file hash unchanged |
| D | US1, SC-001, FR-008 | look up `73181520` and `39269097` for `CN` with `TaricStore.from_jsonl('data/taric.jsonl')` and print each measure's type, area and area name | 7318 15 20 00 has 763 and 775 for `1008`, named "All third countries"; all 14 subdivisions of 3926 90 97 have 410 for `1008` |
| E | US2, SC-002, FR-006 | `python tests/eval/taric_acceptance.py --counts`; then look up `73079311` and `84279000` for `CN` and for `US` | `--counts` lists the 15 groups besides erga omnes, 16 with 1011, that contain CN, with the member counts of research R-05, and reports 1,238 erga omnes measures excluding CN, 0 of them returned. The 552 anti-dumping erga omnes measure on 7307 93 11 91 (58.6 %) and the one on 8427 90 00 11 (70.8 %) are absent for CN and present for US. The 1008 tariff quota 122 on 0703 20 00 00, which excludes AR, BY, CN, GB and RU, is absent for CN and present for US |
| F | US3, FR-007 | `--counts` from E; look up `27101911` for `CN` and the six codes 39249000, 73181542, 73181558, 73181568, 73181582, 73181595 | `--counts` reports 968 type-566 records in the file and 0 returned; no 566 measure on 2710 19 11 10 or on the six codes |
| G | US4, SC-004, FR-011 | run `python tests/eval/kb_load_time.py with` and `… without` alternately, three times each, with nothing else heavy running | every "with" run at most 2 s slower than the "without" run next to it (about 0.7–0.8 s expected, research R-07); `kb.taric loaded: True` for "with" |
| H | FR-012, SC-003 | `python tests/eval/taric_acceptance.py --markdown tests/eval/taric_acceptance.md` | the EZT-online check reads "match" for the 1008 rows of 3926 90 97 and the six 7318 15 codes; no 566 row remains; any other difference is listed in its row, not hidden |
| I | SC-006 | the hand check below | CargoLint and EZT-online agree |
| J | spec edge case, FR-024 | restart the Streamlit server (it never reloads `ui/*.py`); open the sidebar "Knowledge base" expander; then move the new file aside, copy `/tmp/taric-schema1.jsonl` to `data/taric.jsonl` and restart; afterwards put the new file back | caption `TARIC snapshot 2026-10-01 · 105 CN-8 mismatches`; with the schema-1 file `TARIC not loaded`, and the app still checks the sample list |
| K | FR-013 | `sha256sum store/bm25.pkl store/chroma/chroma.sqlite3 store/chroma-bti/chroma.sqlite3 data/nomenclature_2026.jsonl` before and after B and C | all hashes unchanged |

## Hand check of a country exclusion (SC-006)

1. Open https://auskunft.ezt-online.de/ezto/Welcome.do, set **maßgeb. Zeitpunkt** to `01.10.2026`, click **ändern**,
   then **zur Einfuhr**.
2. On **Suchkriterien** enter `7307931191` in **Codenummer** and leave **Ursprungsland** empty; on **Maßnahmen und
   Hinweise** find the erga omnes (`1011`) anti-dumping row (MN-Schl. `552`, 58.6 %) and check that its country exclusion
   (Länderausschluss) lists CN.
3. Repeat with **Ursprungsland** `CN`: the row is no longer listed.
4. Compare with CargoLint: `lookup_taric("73079311", "CN")` does not return that measure, and `lookup_taric("73079311",
   "US")` does.

If 7307 93 11 91 is inconvenient, 8427 90 00 11 (552, 70.8 %, excluding CN only) and 7301 10 00 00 (tariff quota 122,
excluding AE, CN, GB, IS, LI, NO) work the same way (research R-09).
