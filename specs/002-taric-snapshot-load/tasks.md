---

description: "Task list for the one-time TARIC load for digits 9 to 10"
---

# Tasks: One-Time TARIC Load for Digits 9 to 10

**Input**: Design documents from `/specs/002-taric-snapshot-load/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/ (loader-cli.md, snapshot-file.md, taric-store.md), quickstart.md, `.specify/memory/constitution.md` (v1.1.1)

**Tests**: REQUIRED. The spec's SC-003 asks for automated checks, and the constitution (Principle VII) requires tests first for parsing and validation code. Every test task is written first and must fail before its implementation task starts. Unit tests run offline: no network, no secret key. Tests that need gpg skip with a stated reason when it is missing.

**Organization**: tasks are grouped by user story (US1 load, US2 re-run, US3 lookup, US4 caption), so each story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1 … US4)
- Include exact file paths in descriptions

## Path Conventions

The layout is the single project at the repository root from plan.md: `agent/`, `rag/`, `ui/`, `data/`, `store/`, `tests/`. Nothing under `rag/` imports Streamlit. Figures quoted below come from research.md, for the extract of 2026-10-01 (batch `3dc153a8-7542-4d91-8157-b7784f72797b`). D is the snapshot date.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: configuration constants, git hygiene and the fixture extract every test needs.

- [X] T001 Add the TARIC constants to agent/config.py:
  - `TARIC_RAW_DIR = DATA_DIR / "raw" / "taric"`, `TARIC_SNAPSHOT = DATA_DIR / "taric.jsonl"`, `TARIC_KEY = DATA_DIR / "Tulltaxan_Fildistribution.asc"`, `TARIC_KEY_FINGERPRINT = "410160CE25CEC2FF322784E7302AC3C1D0E3E1C9"`;
  - `TARIC_OBJECTS = ("GoodsNomenclature", "Measure", "MeasureType", "GeographicalArea", "DutyExpression", "Regulation")`. This tuple is also the order of `source_files`;
  - `TARIC_SCHEMA = 1`, `TARIC_LOG_DIR = STORE_DIR / "logs"`, and `GPG_ENV = "CARGOLINT_GPG"`, the name of the optional variable holding a full path to gpg;
  - no Streamlit import.
- [X] T002 [P] Add `data/taric.jsonl` to .gitignore; its temporary files `data/taric.jsonl.tmp` and `data/SOURCES.md.tmp` are already covered by the existing `*.tmp` rule, and `data/raw/` is already ignored. Keep data/Tulltaxan_Fildistribution.asc tracked, since it is a public key (research R-02).
- [X] T003 [P] Create tests/fixtures/make_taric_fixtures.py, which writes the fixture extract into tests/fixtures/taric/. Running it needs gpg; run it once and keep its output with the script.
  - **Format**: six tiny XML documents in the real Arctic Group format.
    - Namespace `http://www.arcticgroup.se/tariff/arctictariff/export`.
    - The root `<export>` holds one fixed `<id>` (export id), `<exportType>`, `<parameters><queryDateStart>2014-01-01</queryDateStart></parameters>` and `<items>`.
    - Values are `at:` attributes, with EN and SV descriptions.
    - The snapshot date is 2026-10-01, and the batch ID equals the export id.
  - **Content**, which must cover research R-12:
    - **Goods**:
      - a `national="1"` goods record;
      - a grouping line with suffix 10;
      - a record that ended before D and one that starts after D;
      - chapter, heading and subheading records;
      - an unsubdivided CN-8, whose own 00 code is declarable;
      - a subdivided CN-8, whose 00 code is the parent of two declarable children, one of them under an intermediate grouping line;
      - a CN-8 that is absent from the CN-8 set the tests pass in;
      - an old and a current description period;
      - a subdivision, digits 9–10 not 00, with only an SV description.
    - **Measures**:
      - a `national="1"` measure;
      - a measure recorded on the HS-6 parent;
      - measures for CN, 1011 and US;
      - an export-only erga omnes measure, whose type has `tradeMovementCode` 1;
      - two type-552 anti-dumping measures for CN, with additional codes C001 and C999;
      - a measure covered by a `measurePartialTemporaryStop` on D;
      - an open-ended measure whose base regulation's `effectiveEndDate` is before D;
      - an identical duplicate measure SID;
      - a measure without components;
      - three Meursing-table measures (types 672, 673, 674) without a goods code;
      - an EU measure on 7318155899, a code held only as a national record.
    - **Duty components**: 01 percent (22.0), 01 specific (EUR, DTN), 15 MIN, 17 MAX, and 12 agricultural component.
    - **Regulation**: one with `officialJournalId`, `journalPage` and `datePublished`.
  - **Outputs**:
    - plain `.xml` copies for the parser tests;
    - gzipped copies signed as `ObjectName_<batch>_261001.xml.gz.pgp`. Use a throwaway key that the script creates in a temporary gpg home with `--batch --quick-gen-key`. Use `gpg --sign` on the gzip, so the packets match the real files: compressed, one-pass signature, literal, signature;
    - only the throwaway public keys in tests/fixtures/taric/keys/. The script creates both key pairs in a temporary gpg home, signs there and deletes the home, so no secret key is ever written to the repository. Nothing outside the tests trusts these public keys;
    - tests/fixtures/taric/conflict/, where two measures share one SID with different content;
    - in tests/fixtures/taric/bad/, a tampered signed copy with one flipped byte, a file signed by a second throwaway key, and a correctly signed MeasureType file whose payload is not gzip;
    - a copy of the real data/raw/taric/DutyExpression_3dc153a8-7542-4d91-8157-b7784f72797b_261001.xml.gz.pgp (2.8 KB) in tests/fixtures/taric/real/;
    - tests/fixtures/taric/expected.json, holding the exact counts that T010 asserts. They are `suffix80_codes` (all stored code records, parents included), `declarable_codes`, `measure_records`, `cn8_mismatches` (against the CN-8 set the tests pass in), `dropped_meursing` and `dropped_national_code`. It also holds `fixture_key_fingerprint` and `other_key_fingerprint`, the fingerprints of the two throwaway keys; the script makes new keys on every run, so T006 and T010 read them from here.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the snapshot file format, shared by the loader (US1, US2), the store (US3) and the caption (US4).

**CRITICAL**: no user story work can begin until this phase is complete.

### Tests for the foundation (write FIRST, ensure they FAIL)

- [X] T004 [P] Write tests/unit/test_taric_format.py for rag/taric.py:
  - **Round trip**: all three record kinds survive writing and reading.
  - **Key order** is exactly as in contracts/snapshot-file.md:
    - `snapshot`: kind, schema, snapshot_date, batch_id, export_id, source_files, loaded_at, goods_records, measure_records, cn8_mismatches;
    - `goods_nomenclature`: kind, code, cn8, description, valid_from, valid_to, declarable, parent;
    - `measure`: kind, sid, code, measure_type, measure_type_label, trade_movement, geo_area, additional_code, duty, regulation_id, regulation_ref, valid_from, valid_to.
  - **Values**: dates are `YYYY-MM-DD`, open-ended is `null`, and non-ASCII text is written as-is.
  - **Header reader**: `read_snapshot_header(path)` returns the first line's snapshot record, or None when the file is absent.
  - **Errors**: a first line that is not a snapshot record, or a schema other than 1, raises TaricFileError.

### Implementation for the foundation

- [X] T005 Create rag/taric.py with:
  - `TaricFileError`;
  - frozen, slotted record dataclasses `TaricSnapshotRecord`, `TaricCodeRecord` and `TaricMeasureRecord`, matching data-model §2–4. Quote these constraints from the data model:
    - code "string, 10 digits";
    - cn8 "`code[:8]`";
    - description "`""` when digits 9–10 are `00`";
    - trade_movement "`import`, `export` or `both`";
    - additional_code "string or null";
    - sid "int > 0";
  - `record_to_line(record) -> str`, with fixed key order, `ensure_ascii=False` and compact separators;
  - `line_to_record(line)`;
  - `read_snapshot_header(path) -> dict | None`, which reads only the first line;
  - no Streamlit import.

**Checkpoint**: format tests green; user stories can begin.

---

## Phase 3: User Story 1 - Load a TARIC snapshot from one full extract (Priority: P1) 🎯 MVP

**Goal**: one command turns the six signed files of one batch into `data/taric.jsonl`, with the codes, measures and one snapshot record, after verifying every signature. It ends with a summary (FR-001 to FR-013, FR-022, FR-023, FR-025).

**Independent Test**: run `python -m rag.loader --taric` on data/raw/taric/ and compare the summary with the file (quickstart B, E, F).

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [X] T006 [P] [US1] Write tests/unit/test_pgp.py for rag/pgp.py. Skip the module with the reason "gpg not found" when `find_gpg` raises GpgNotFound. Cover:
  - **Accepted**: a fixture file signed by the throwaway key verifies against the throwaway public key, pinned to `fixture_key_fingerprint` from expected.json, and returns the gzip payload.
  - **Refused**: the tampered copy and the file signed by the second key raise SignatureError and return no payload.
  - **Real file**: tests/fixtures/taric/real/ verifies against data/Tulltaxan_Fildistribution.asc with fingerprint `410160CE25CEC2FF322784E7302AC3C1D0E3E1C9`.
  - **Key copy**: `check_key_copy` raises SignatureError for a key copy with another fingerprint.
  - **Finding gpg**: `find_gpg` honours `CARGOLINT_GPG`, then `PATH`, then Git for Windows' `usr\bin\gpg.exe`, and raises GpgNotFound when none exists.
- [X] T007 [P] [US1] Write tests/unit/test_taric_extract.py, file-set part:
  - `discover_extract` on a temporary folder accepts exactly the six names matching `^(GoodsNomenclature|Measure|MeasureType|GeographicalArea|DutyExpression|Regulation)_(?P<batch>[^_]+)_(?P<yymmdd>\d{6})\.xml\.gz\.pgp$`.
  - It derives the snapshot date 2026-10-01 from `261001`.
  - It ignores other files and unpacked `.xml` copies.
  - It raises ExtractError, naming the files, when an object is missing, appears twice, or the batch IDs or dates differ (FR-003, FR-004).
- [X] T008 [US1] Write tests/unit/test_taric_extract.py, parsing part, on the plain fixture XML with no gpg:
  - **National records**: records with `national="1"` never appear (research R-05).
  - **Goods**:
    - kept only when the suffix is 80 and the record is valid on D: `dateStart` ≤ D and `dateEnd` missing or ≥ D;
    - indent and EN description come from the latest period valid on D;
    - the description is `""` for codes whose digits 9–10 are `00` (FR-007), and for the subdivision that has only an SV description.
  - **Hierarchy**: `declarable` and `parent` come from the indent walk, with chapter codes as roots and grouping lines never parents (FR-008, research R-06). This includes the subdivided CN-8 whose 00 code is a parent.
  - **Measures**:
    - only those valid on D, excluding one covered by a partial temporary stop and one whose base regulation has ended (research R-04);
    - `trade_movement` comes from the measure type;
    - `additional_code` is "C001" or "C999", and null when absent.
  - **Duty text** per research R-08: "22 %", "<amount> EUR / 100 kg", "MIN …", "MAX …", "+ EA", and "" when there are no components.
  - **Regulation reference**: in the style "OJ L 299, p. 1 (2007-11-16)", and "" when the regulation is unknown.
  - **Duplicates and inconsistencies**:
    - an identical duplicate SID is kept once;
    - the conflict folder raises ExtractError naming the SID;
    - a measure type missing from MeasureType raises ExtractError naming the type;
    - the six export ids must agree.
  - **Unusable measures** (research R-14): `national_only_codes` finds 7318155899, and the snapshot drops the three Meursing measures and the measure on that code, counting them by reason.
- [X] T009 [US1] Write tests/unit/test_taric_extract.py, reconciliation part:
  - **CN-8 codes**: `NomenclatureIndex.cn8_codes()` returns the 8-digit codes of the `CN dddd dd dd` lines in all chunk texts. Build a tiny index in the test.
  - **Comparison**: reconciliation compares only CN-8 prefixes of declarable codes with the given CN 2026 set, never parents (FR-011).
  - **Count**: the number of mismatches goes into the snapshot record.
  - **Log**: `taric-cn8-mismatches-2026-10-01.txt` holds one line `<cn8> <one declarable code under it>` per missing prefix.
- [X] T010 [US1] Write tests/integration/test_taric_loader.py, first-load part.
  - **Setup**:
    - patch the names as imported in rag/loader.py: the TARIC raw folder becomes a temporary copy of the signed fixtures; the snapshot, log folder and SOURCES file move to tmp, and the temporary SOURCES file starts as a small register without a TARIC row; the key becomes the throwaway public key with `fixture_key_fingerprint` from expected.json;
    - run `rag.loader.main(["--taric"])`;
    - skip with a reason when gpg is missing.
  - **Success**:
    - exit 0;
    - line 1 is the snapshot record, with the six `source_files`;
    - `goods_records` equals the number of `goods_nomenclature` lines, and both equal the fixture's suffix-80 code count, parents included, from tests/fixtures/taric/expected.json;
    - the number of lines with `declarable: true` equals the fixture's declarable count from the same file;
    - `measure_records` and `cn8_mismatches` equal their expected values from that file;
    - the summary lines match contracts/loader-cli.md, and the progress log gives the dropped-measure counts from expected.json;
    - the mismatch log is written, and the TARIC row is inserted under the register's table header with the other rows unchanged.
  - **No index metadata**: with the store folder patched to an empty temporary folder, so that no `index_meta.json` exists, and with no SOURCES file, the load still exits 0, writes the snapshot and creates a minimal register holding the TARIC row (FR-025).
  - **Refusals**: a missing object, a duplicate object, a mixed batch, a tampered file, a correctly signed file that cannot be unpacked, or an export-id mismatch each exits 1, names the file, and leaves an existing snapshot file byte-identical (FR-013).
  - **Usage errors**:
    - `--taric` with `--demo`, `--chapters`, `--bti-chapters` or `--no-embed` exits 2;
    - a missing key copy, or one with another fingerprint, exits 2 before any file is read.
  - **Indexes**: `build_nomenclature`, `build_bti`, `build_indexes` and `ChromaVectorSearch` are patched to raise and are never called (SC-005, FR-022, FR-023).

### Implementation for User Story 1

- [X] T011 [P] [US1] Create rag/pgp.py per research R-02 and contracts/loader-cli.md:
  - **Errors**: `GpgNotFound` and `SignatureError`.
  - **`find_gpg()`**: `CARGOLINT_GPG`, then `shutil.which("gpg")`, then Git for Windows' `usr\bin\gpg.exe`, located next to `shutil.which("git")`.
  - **`check_key_copy(key_path, fingerprint)`**: `--with-colons --import-options show-only --import`, with the key on stdin; the primary `fpr` must equal the pin.
  - **`verify_signed(data, key_path, fingerprint) -> bytes`**:
    - a temporary home from `tempfile`, `cwd` set to it, `--homedir .`;
    - key and data on stdin; `--batch --status-fd 2 --output - --decrypt`;
    - accept only exit 0 with exactly one `VALIDSIG` whose primary-key fingerprint, field 11, equals the pin, and no `BADSIG`, `ERRSIG`, `NO_PUBKEY`, `EXPKEYSIG` or `REVKEYSIG`;
    - return the payload only after this check, because gpg writes one-pass-signed content before it checks the signature;
    - never pass Windows paths to gpg.
- [X] T012 [P] [US1] Add `NomenclatureIndex.cn8_codes() -> frozenset[str]` to rag/nomenclature.py. It returns the 8-digit codes from the lines matching `^CN (\d{4}) (\d{2}) (\d{2})\b` in all chunk texts: 9,791 codes for CN 2026 (research R-09).
- [X] T013 [P] [US1] Create rag/taric_extract.py, file-set part:
  - `ExtractError`;
  - `ExtractFile` and `ExtractSet` dataclasses (object, batch_id, snapshot_date, path);
  - `discover_extract(folder)` with the pattern from research R-01: one file per object, one batch, one date (FR-003, FR-004). Other objects and other extensions are ignored (FR-001).
- [X] T014 [US1] Add streaming parse helpers and the reference objects to rag/taric_extract.py:
  - **Streaming**: iterparse over `gzip.GzipFile(fileobj=io.BytesIO(payload))` with `tag=`, `resolve_entities=False`, `no_network=True` and `load_dtd=False`, freeing each element after use (research R-03).
  - **Export id**: read from `<id>`.
  - **MeasureType**: EN label, and trade movement 0, 1, 2 mapped to import, export, both.
  - **DutyExpression**: EN descriptions.
  - **Regulation**: base, modification and full-stop regulations by id, with OJ id, page, publication date and effective end date.
  - **GeographicalArea**: ids.
  - **EU only**: keep only records with `national="0"` (research R-05).
- [X] T015 [US1] Add goods parsing and the hierarchy walk to rag/taric_extract.py:
  - **Records**: keep EU records valid on D.
  - **Indent**: the latest `goodsNomenclatureIndent` with `dateStart` ≤ D.
  - **Description**: the EN text of the latest description period valid on D; `""` when digits 9–10 are `00` (FR-007).
  - **Walk**: per chapter, sort by (code, suffix) and walk with an indent stack, with chapters as roots at indent −1 (research R-06):
    - `parent` is the nearest enclosing suffix-80 record;
    - `declarable` is true for a suffix-80 record with nothing beneath it.
  - **Stored**: suffix-80 records only (FR-006). A 10-digit code that appears twice raises ExtractError (FR-016).
- [X] T016 [US1] Add measure parsing and duty rendering to rag/taric_extract.py.
  - **Which measures**: EU measures valid on D, minus those covered by a `measurePartialTemporaryStop` on D. An open-ended measure ends at its regulation's effective end date when that date is before D (research R-04).
  - **Fields**, per data-model §4. Quote these constraints from the data model:
    - sid "int > 0; unique in the file";
    - additional_code "additional code type + id, for example `C999`; null when the measure has none";
    - regulation_ref "`OJ {journal}, p. {page} ({published})`; `""` when the regulation file has no such record";
    - trade_movement comes from the measure type.
  - **Duty text**, per research R-08:
    - components ascending by `dutyExpressionId`;
    - prefixes: 02 "−", 04/19/20 "+", 15 "MIN", 17/35 "MAX";
    - trailing zeros dropped;
    - "%" when there is no monetary unit;
    - otherwise "{amount} {currency} / {unit}", with DTN=100 kg, KGM=kg, TNE=1000 kg, LTR=l, HLT=hl, MTQ=m³, MTK=m², NAR=p/st, and unknown codes kept as codes;
    - components without an amount by their EN short form;
    - "" when there are no components.
  - **Duplicates**: an identical duplicate SID is kept once. A conflicting SID or an unknown measure type raises ExtractError naming it.
- [X] T017 [US1] Add `load_extract(extract, key_path, fingerprint, cn2026_cn8, log_dir)` to rag/taric_extract.py; after the signature checks it hands the payloads to `build_snapshot`. In order:
  1. run `check_key_copy`;
  2. verify all six files with `rag.pgp.verify_signed`, keeping payloads in memory;
  3. require equal export ids;
  4. parse the reference objects, goods and measures;
  5. drop the Meursing-table measures (types 672, 673, 674) and the measures on codes held only as national records, counting both by reason (research R-14);
  6. reconcile the CN-8 prefixes of declarable codes against `cn2026_cn8`, excluding parents (FR-011);
  7. write the mismatch log to `TARIC_LOG_DIR / f"taric-cn8-mismatches-{snapshot_date}.txt"`;
  8. return a Snapshot whose snapshot record follows data-model §2: schema 1, `source_files` in `TARIC_OBJECTS` order, `loaded_at` in UTC, and the counts.
- [X] T018 [US1] Add `write_snapshot(snapshot, path)` to rag/taric_extract.py (FR-013, FR-015):
  - **Order**: line 1 is the snapshot record, then code records sorted by code, then measure records sorted by (code, sid).
  - **Encoding**: via `rag.taric.record_to_line`; UTF-8, LF, final newline.
  - **Atomic replace**: write to `<path>.tmp`, then `os.replace`.
- [X] T019 [US1] Add the `--taric [DIR]` mode to `main()` in rag/loader.py.
  - **Argument**: `ap.add_argument("--taric", nargs="?", const=str(TARIC_RAW_DIR), metavar="DIR")`.
  - **Run only the TARIC load** when the option is set, in the order of contracts/loader-cli.md:
    1. options;
    2. gpg and key copy;
    3. discover;
    4. verify, parse and reconcile;
    5. write;
    6. SOURCES;
    7. summary.
  - **Never** call `build_nomenclature`, `build_rules`, `build_bti` or `build_indexes`. Return exit code 0, 1 or 2.
  - **Conflicts**: reject `--demo`, `--chapters`, `--bti-chapters` and `--no-embed` with exit 2.
  - **CN 2026 set**: `cn2026_cn8` comes from `NomenclatureIndex.from_jsonl(NOMENCLATURE_JSONL).cn8_codes()`.
  - **Output**: print the summary lines of contracts/loader-cli.md (FR-012). A refusal is one line naming the step, the file and the reason, ending "Nothing was written."
  - **Logging**: use the module's existing `log()`, with one line per dropped-measure reason (research R-14).
- [X] T020 [US1] Add the TARIC row to data/SOURCES.md via rag/loader.py (FR-025).
  - **Row**: add a `taric` entry to `SOURCES`, and one helper that builds the row from a snapshot record and the folder holding the signed files:
    - dataset "EU TARIC snapshot (Swedish Customs Tariff File Distribution, tot extract)";
    - version "snapshot <date>, batch <batch>";
    - retrieved = the modification date of the newest of the six signed files named in the record, or "(processed file reused)" when they are gone, as for the other datasets;
    - licence per contracts/loader-cli.md;
    - URL `https://distr.tullverket.se/tulltaxan/`.
  - **Full build**: `write_sources_md` calls the helper with `read_snapshot_header(TARIC_SNAPSHOT)` and data/raw/taric/ when the snapshot exists.
  - **Register update without index metadata**: the `--taric` mode never calls `load_index_meta`.
    - It calls the helper with the new snapshot record in memory, never with data/taric.jsonl, because the register text is prepared before the new snapshot file exists.
    - It replaces the TARIC row in the existing data/SOURCES.md, inserts it under the table header when the row is missing, or creates a minimal register (title, table header, TARIC row) when the file does not exist.
    - The new register text is written to data/SOURCES.md.tmp before the snapshot is replaced, and the register is replaced right after the snapshot (FR-013, FR-025).
- [X] T021 [US1] Run the real load on data/raw/taric/ per specs/002-taric-snapshot-load/quickstart.md scenario B.
  - **Expected**, asserted as four separate counts:
    - `goods_records` in the snapshot record is 22,361. This is every suffix-80 code that is EU and valid on D, parents included, and it equals the number of `goods_nomenclature` lines.
    - Of those lines, exactly 16,742 have `declarable: true`. These are the leaf codes that lookups return and reconciliation compares; the other 5,619 are parents.
    - `measure_records` is 161,959: the EU measures in force on D. Research R-04's rules end 103,738 open-ended measures with their regulation, and the progress log names 23,184 Meursing-table measures and 1 measure on a national-only code as dropped (research R-14).
    - `cn8_mismatches` is 105, all in chapters 98 and 99.
  - **Also**: run scenarios E and F, and note the load time for SC-006.
  - **Parser limits**: confirm that the real files parse with lxml's default limits. If they do not, enable `huge_tree` for the Measure file only. Record the outcome in research R-03.
  - **Outcome (2026-10-22)**: the four counts above; scenarios E and F passed; the load took 20 s; lxml's default limits sufficed (research R-03).

**Checkpoint**: User Story 1 works on its own: `pytest -q` green offline, quickstart B, E and F pass.

---

## Phase 4: User Story 2 - Re-run the load safely (Priority: P2)

**Goal**:
- the same extract leads to a skip;
- an extract with another date replaces the snapshot;
- `--force` rewrites the whole file;
- no run ever leaves duplicates (FR-014 to FR-016).

**Independent Test**: run the command twice, then with `--force`, on the same folder and compare hashes (quickstart C, D).

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [X] T022 [US2] Extend tests/integration/test_taric_loader.py:
  - **Skip**: a second run on the same fixture extract prints the skip message of contracts/loader-cli.md, exits 0 and leaves the file byte-identical, without calling `verify_signed`, which is patched to raise.
  - **Force**: `--force` rewrites the file so that every line after line 1 is identical, and line 1 differs only in `loaded_at`.
  - **New date**: a fixture extract renamed to another date replaces the file, the summary names both dates, and data/SOURCES.md holds exactly one TARIC row, naming the new date.
  - **Failed rewrite**: a forced rewrite that fails after writing `<path>.tmp`, with `os.replace` patched to raise, leaves the old file byte-identical (FR-013).
  - **No duplicates**: no code or measure line appears twice after any sequence of runs (FR-016).

### Implementation for User Story 2

- [X] T023 [US2] Add the skip check and force handling to the `--taric` mode in rag/loader.py.
  - **When**: after discovery and before any signature check.
  - **Compare**: `read_snapshot_header(TARIC_SNAPSHOT)["snapshot_date"]` with the extract's date.
  - **Equal and no `--force`**: print the skip message and exit 0 (FR-014).
  - **Otherwise**: load and replace, printing "new snapshot" or "replaced snapshot <previous date>" (FR-012).
- [X] T024 [US2] Run quickstart scenarios C and D from specs/002-taric-snapshot-load/quickstart.md on the real snapshot, and confirm the hashes.

**Checkpoint**: User Stories 1 and 2 work independently.

---

## Phase 5: User Story 3 - Look up the subdivisions and measures of a CN-8 code (Priority: P3)

**Goal**: `TaricStore.lookup_taric(cn8, origin="CN")` as specified in contracts/taric-store.md (FR-017 to FR-021).

**Independent Test**: load a small snapshot file, then look up an unsubdivided, a subdivided and an unknown CN-8 (quickstart G).

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [X] T025 [P] [US3] Write tests/unit/test_taric_store.py against a small hand-written snapshot file, tests/fixtures/taric/snapshot_small.jsonl. Create it in this task, in the format of contracts/snapshot-file.md. Cover:
  - **Subdivisions**:
    - an unsubdivided CN-8 gives one subdivision, its own 00 code;
    - a subdivided CN-8 gives its declarable children in code order, never its own 00 code;
    - an unknown CN-8 gives `[]`.
  - **Inheritance**: measures recorded on the CN-8, subheading, heading and chapter appear, with `recorded_on` set to that code.
  - **Origin**: "CN" returns CN and 1011 measures but not US ones; "US" returns US and 1011 measures.
  - **Trade movement**: export-only measures are never returned; "both" measures are.
  - **Additional codes**: the anti-dumping measures carry C001 and C999.
  - **Order**: by (measure_type, geo_area, additional_code or "", sid).
  - **Input handling**:
    - "7318 15 58" and "7318.15.58" are accepted;
    - "1234", "73181558X" and an empty origin raise ValueError.
  - **Read-only**: results are frozen and equal across calls.
  - **Bad files**: a file with schema 2, or without a snapshot record, raises TaricFileError.
  - **Scope (FR-021)**: a static check that no module under agent/ or tools/ imports `rag.taric` or `rag.taric_extract`, and that `lookup_taric` appears nowhere under ui/ or in app.py.

### Implementation for User Story 3

- [X] T026 [US3] Add the read side to rag/taric.py:
  - frozen, slotted `TaricSnapshotInfo`, `TaricMeasure` and `TaricSubdivision`;
  - `TaricStore.from_jsonl(path)`, which reads all lines once and refuses a schema other than 1 with TaricFileError;
  - compact records with interned repeated strings;
  - indexes of declarable codes by cn8, measures by code and parent links by code;
  - a `snapshot` property (research R-10).
- [X] T027 [US3] Add `TaricStore.lookup_taric(cn8, origin="CN")` to rag/taric.py per contracts/taric-store.md:
  - **Input**: remove spaces and dots, then require 8 digits and a non-empty alphanumeric origin, else ValueError (FR-019).
  - **Subdivisions**: the declarable codes with that cn8, in code order (FR-017).
  - **Measures**: gathered along the parent chain, with `geo_area` equal to the origin or "1011" and `trade_movement` import or both (FR-018, research R-07). Ordered by (measure_type, geo_area, additional_code or "", sid).
  - **Read-only**: never changes the store (FR-020).
- [X] T028 [US3] Run quickstart scenario G from specs/002-taric-snapshot-load/quickstart.md on the real snapshot.
  - **Expected**: `lookup_taric("73181558")` lists 7318155810, 7318155860 and 7318155890, with China and erga omnes import measures. The anti-dumping ones carry their additional codes.
  - **Timing**: time ten lookups; each must take under 1 s (SC-007).

**Checkpoint**: User Story 3 works on its own against any snapshot file.

---

## Phase 6: User Story 4 - See whether TARIC is loaded (Priority: P4)

**Goal**: `kb.taric` is loaded at app start, and the sidebar shows the TARIC caption (FR-020, FR-024).

**Independent Test**: start the app with and without data/taric.jsonl (quickstart H).

### Tests for User Story 4 (write FIRST, ensure they FAIL)

- [X] T029 [P] [US4] Write tests/unit/test_sidebar_caption.py. Use a SimpleNamespace kb; no Streamlit session is needed. `taric_caption(kb)` returns:
  - "TARIC snapshot 2026-10-01 · 105 CN-8 mismatches" when `kb.taric.snapshot` has that date and count;
  - "TARIC snapshot 2026-10-01 · 1 CN-8 mismatch" for a count of 1;
  - "TARIC not loaded" when `kb.taric` is None.
- [X] T030 [P] [US4] Add tests for `open_taric_store(path)` to tests/unit/test_taric_store.py. It returns a TaricStore for a valid file. It returns None, with a logged reason, when the file is absent, unreadable or has another schema (FR-024).

### Implementation for User Story 4

- [X] T031 [US4] Load the store at app start in rag/taric.py and rag/loader.py (FR-020, FR-024):
  - **rag/taric.py**: add `open_taric_store(path) -> TaricStore | None`. It catches FileNotFoundError and TaricFileError, logs the reason and returns None.
  - **rag/loader.py**: add `taric: TaricStore | None = None` to KnowledgeBase, as a new keyword argument with default None. Set it in `open_knowledge_base` from `open_taric_store(TARIC_SNAPSHOT)`. It loads once per process, because app.py's `st.cache_resource` caches the knowledge base.
- [X] T032 [US4] Add `taric_caption(kb)` to ui/sidebar.py per contracts/taric-store.md. Render it with `st.caption` inside the existing "Knowledge base" expander, directly under the existing knowledge-base caption. No other UI change (FR-024).
- [X] T033 [US4] Run quickstart scenarios H and I from specs/002-taric-snapshot-load/quickstart.md:
  1. restart the Streamlit server, since it never reloads ui/*.py, and check the caption;
  2. rename data/taric.jsonl, restart, and check that the caption reads "TARIC not loaded" and the sample check still works;
  3. log the knowledge-base load time with and without the snapshot; the difference must stay at or under 10 s (SC-007).

**Checkpoint**: all four user stories work independently.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: documentation, the acceptance aid and the final validation.

- [X] T034 [P] Update README.md:
  - how to load TARIC: download the six object files of one batch from https://distr.tullverket.se/tulltaxan/xml/tot/ into data/raw/taric/ under their original names; get gpg via Git for Windows or `CARGOLINT_GPG`; run `python -m rag.loader --taric`, or add `--force`;
  - what the caption shows;
  - the EU-only and import-only rules;
  - the known limitations, in the weaknesses list: country groups, erga omnes exclusions, full temporary stops and unnamed additional-code companies.
- [X] T035 [P] Update CLAUDE.md with the TARIC snapshot: add `python -m rag.loader --taric` to its command list, a one-time TARIC snapshot that takes about a minute and needs gpg.
- [ ] T036 [P] Create the SC-001 acceptance aids tests/eval/taric_acceptance.py and tests/eval/taric_acceptance.md:
  - **tests/eval/taric_acceptance.py**: prints, for a list of CN-8 codes, the subdivisions and China-origin import measures from `lookup_taric`, with type, label, duty, additional code and regulation.
  - **tests/eval/taric_acceptance.md**: a 20-row table with the columns CN-8 · CargoLint subdivisions · EZT-online subdivisions · CargoLint measures · EZT-online measures · match · note.
    - Rows hold codes beneath 3924.90, 3926.90, 4202.21, 6109.10, 6203.42, 6404.11, 7318.15, 8452.90, 8518.30, 9405.21, 9503.00 and 9617.00.
    - The author fills in the EZT-online columns.
- [ ] T037 Run the full validation from specs/002-taric-snapshot-load/quickstart.md: `pytest -q` green offline, then scenarios A to J. Record the SC-006 and SC-007 timings in README.md's TARIC section.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup, and blocks all user stories. It provides the snapshot format.
- **User Story 1 (Phase 3)**: depends on Foundational.
- **User Story 2 (Phase 4)**: depends on User Story 1, because it extends the `--taric` mode.
- **User Story 3 (Phase 5)**: depends on Foundational only. Its tests use a hand-written snapshot file, so it can run alongside User Story 1.
- **User Story 4 (Phase 6)**: depends on User Story 3, because it needs `TaricStore` and `open_taric_store`.
- **Polish (Phase 7)**: depends on all four stories.

### Within Each User Story

- Tests are written first and must fail before implementation starts.
- **US1**: T013 → T014 → T015 → T016 → T017 → T018 share rag/taric_extract.py and run in order. T011 and T012 run in parallel with them. T017 needs T011 and T012. T019 → T020 share rag/loader.py.
- **US2**: T023 extends T019.
- **US3**: T026 → T027 share rag/taric.py.
- **US4**: T031 → T032.
- Each story ends with its run-and-check task (T021, T024, T028, T033).

### Parallel Opportunities

- **Setup**: T002 and T003.
- **Foundational**: T004 starts as soon as T001 is done.
- **US1 tests**: T006 and T007, which are in different files.
- **US1 implementation**: T011, T012 and T013, which are in different files.
- **Across stories**: US3 (T025 to T027) alongside US1, once Phase 2 is done.
- **US4 tests**: T029 and T030.
- **Polish**: T034, T035 and T036.

---

## Parallel Example: User Story 1

```bash
# Tests first, in parallel (different files):
Task: "T006 Write tests/unit/test_pgp.py for rag/pgp.py (good, tampered, other key, real file, key copy, find_gpg)"
Task: "T007 Write tests/unit/test_taric_extract.py, file-set part (discover_extract)"

# Then the independent modules, in parallel:
Task: "T011 Create rag/pgp.py (find_gpg, check_key_copy, verify_signed with the no-path invocation)"
Task: "T012 Add NomenclatureIndex.cn8_codes() to rag/nomenclature.py"
Task: "T013 Create rag/taric_extract.py, file-set part (ExtractError, ExtractSet, discover_extract)"
```

## Parallel Example: User Story 3 alongside User Story 1

```bash
# After Phase 2, one stream works on the loader while another builds the lookup:
Task: "T014 … T018 rag/taric_extract.py parsing, hierarchy, measures, load and write (US1)"
Task: "T025 tests/unit/test_taric_store.py, then T026 and T027 in rag/taric.py (US3)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1): a verified snapshot file built from the real 2026-10-01 extract.
3. **STOP and VALIDATE**: quickstart B, E and F, then compare the counts with research.md.

### Incremental Delivery

1. Setup and Foundational: the format is ready.
2. User Story 1: the snapshot loads (MVP).
3. User Story 2: re-runs are safe.
4. User Story 3: the lookup is ready for Spec 2.
5. User Story 4: the caption is visible to clerks.
6. Polish: documentation, acceptance aid, full validation, and the SC-001 comparison by the author.

---

## Notes

- **Commits**: commit and push only when the author asks (CLAUDE.md).
- **Tests**: keep `pytest -q` green after every task. Use the existing `unit` and `integration` markers through `pytestmark`; do not add new markers, because pyproject sets `--strict-markers`.
- **gpg tests** skip with a reason when `find_gpg` raises GpgNotFound. Parser tests never need gpg.
- **Line endings**: match each edited file's existing line endings; `ui/*.py` files are CRLF.
- **Browser checks**: restart the Streamlit server first.
- **Indexes and data**: never touch `store/chroma`, `store/chroma-bti`, `store/bm25.pkl` or `data/nomenclature_2026.jsonl` in this feature (FR-022, FR-023).
