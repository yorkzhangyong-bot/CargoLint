---

description: "Task list for TARIC lookup completeness: country groups, exclusions, the 566 filter and startup time"
---

# Tasks: TARIC Lookup Completeness for Country Groups and Exclusions

**Input**: Design documents from `/specs/003-taric-groups-exclusions/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/ (snapshot-file.md, taric-store.md, loader-cli.md), quickstart.md, `.specify/memory/constitution.md` (v1.1.1)

**Tests**: REQUIRED. The spec's constraints ask for tests before code, and the constitution (Principle VII) requires tests first for parsing and validation code. Every test task for new behaviour is written first and must fail before its implementation task starts; T025's regression tests are the one exception. Unit tests run offline: no network, no secret key. Tests that need gpg skip with a stated reason when it is missing. Keep `pytest -q` green at every checkpoint; 391 tests are collected before this feature. Existing tests that encode schema 1 or the old lookup rule are updated, never dropped; T032 records the test count before and after.

**Organization**: tasks are grouped by user story (US1 group measures and names, US2 exclusions, US3 the 566 filter, US4 startup time), so each story is an independently testable increment. The schema-2 file format is the shared foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1 … US4)
- Include exact file paths in descriptions

## Path Conventions

The layout is feature 002's single project at the repository root: `agent/`, `rag/`, `tests/`. Nothing under `rag/` imports Streamlit. Figures quoted below come from research.md, for the extract of 2026-10-01 (batch `3dc153a8-7542-4d91-8157-b7784f72797b`). D is the snapshot date. The lookup stays unconnected to the agent and the UI (feature 002's FR-021 test stays).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the startup measurement and the fixture extract that the new tests need.

- [X] T001 [P] Create tests/eval/kb_load_time.py, committing T037's measurement method (research R-07):
  - usage `python tests/eval/kb_load_time.py with|without`, one fresh process per run;
  - it puts the repository root on `sys.path`, then times `rag.loader.open_knowledge_base(get_settings())`;
  - for `without`, it first sets `rag.loader.TARIC_SNAPSHOT` to a path that does not exist;
  - it prints `<mode> snapshot: <seconds> s, kb.taric loaded: <True|False>`;
  - the docstring states the SC-004 procedure: alternate `with` and `without` three times each and compare each pair.
- [X] T002 [P] Extend tests/fixtures/make_taric_fixtures.py and regenerate tests/fixtures/taric/ by running it (needs gpg; it makes new throwaway keys and writes their fingerprints to expected.json). Keep the real Arctic Group format and every existing record with its expected values.
  - **GeographicalArea** (research R-01, R-02): each area record gets `geographicalAreaCode` (0 country, 1 group) and `geographicalAreaDescriptionPeriod` elements holding `geographicalAreaDescription` (EN and SV). Memberships are `geographicalAreaMembership` children of the *member* record, with `SIDGeographicalAreaGroup`, `dateStart`, an optional `dateEnd` and `national`. Areas:
    - groups `1011` "ERGA OMNES" and `1008` "All third countries";
    - an inner group that is a member of an outer group (for example `4013` in `4000`);
    - CN with an ended English description period ("Old name") and a current one ("China"). Its memberships:
      - valid on D: 1011, 1008 and the inner group;
      - not kept: one that ended before D (group `5001`), one that starts after D (group `5002`), and one with `national="1"`;
    - US in 1011 and 1008;
    - an area with an SV description only;
    - an area whose own `dateEnd` is before D;
    - the existing national area SE-NAT.
  - **Measure** (research R-03): add `measureExcludedGeographicalArea` elements (`geographicalAreaId`, `SIDGeographicalArea`, `national`) to two kept measures:
    - one with a single EU exclusion plus a `national="1"` exclusion element;
    - one listing two areas out of alphabetical order plus a duplicate of one of them.
  - **expected.json**: add `area_records` (EU areas valid on D), `area_names` (those with an English name), `membership_records` (memberships kept) and `measures_with_exclusions`. The existing counts stay: 11 codes, 5 declarable, 12 measures, 1 mismatch, 3 Meursing, 1 national-code drop.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the schema-2 file format (contracts/snapshot-file.md), shared by the loader, the store and the acceptance aid. After this phase the loader writes schema 2, though not yet with area records or exclusions.

**CRITICAL**: no user story work can begin until this phase is complete.

### Tests for the foundation (write FIRST, ensure they FAIL)

- [X] T003 [P] Update tests/unit/test_taric_format.py for schema 2; every schema-1 test is updated to its schema-2 form, none dropped:
  - **Round trip**: all four kinds survive writing and reading.
  - **Forms and positions**, exactly as in contracts/snapshot-file.md:
    - `snapshot`: an object, with keys kind, schema, snapshot_date, batch_id, export_id, source_files, loaded_at, goods_records, measure_records, cn8_mismatches;
    - `geographical_area`: an array of 4, kind, geo_area, name, member_of;
    - `goods_nomenclature`: an array of 8, kind, code, cn8, description, valid_from, valid_to, declarable, parent;
    - `measure`: an array of 14, kind, sid, code, measure_type, measure_type_label, trade_movement, geo_area, additional_code, duty, regulation_id, regulation_ref, valid_from, valid_to, excluded_areas.
  - **Values**: `member_of` and `excluded_areas` are JSON arrays; separators are compact; non-ASCII text is written as-is; open-ended dates are `null`.
  - **Refusals**: `line_to_record` raises TaricFileError for:
    - text that is not JSON;
    - an array whose first element is not a known kind;
    - an array with the wrong number of elements for its kind;
    - a keyed object of any kind other than `snapshot`.
  - **Header reader**: `read_snapshot_header` returns the line-1 object. It raises TaricFileError for a first line that is not a snapshot record, and for `"schema":1`.
- [X] T004 [P] Update the tests that read or write schema-1 lines in tests/integration/test_taric_loader.py, tests/unit/test_taric_extract.py and tests/unit/test_taric_store.py (updated, none dropped), and add the FR-003 test:
  - **tests/integration/test_taric_loader.py**: read snapshot lines with `rag.taric.line_to_record`, not `json.loads(...)["kind"]` (line 1 may still be read as JSON). In `test_the_full_build_register_gets_the_taric_row`, build the header with `schema=TARIC_SCHEMA`.
  - **New test in that file** (FR-003): put a schema-1 snapshot line for 2026-10-01 in place (`record_to_line` of a `TaricSnapshotRecord` with `schema=1`). `loader.main(["--taric"])` without `--force` then:
    - exits 0;
    - writes a schema-2 file;
    - prints `taric.jsonl will be rewritten: schema 1 is not supported (expected 2)` and `replaced snapshot (older format or unreadable)`.
  - **tests/unit/test_taric_extract.py**: the header's `schema` is 2.
  - **tests/unit/test_taric_store.py**: the "another schema" cases in `TestBadFiles` and `TestOpenForTheApp` swap `"schema":2` for `"schema":1`.

### Implementation for the foundation

- [X] T005 Set `TARIC_SCHEMA = 2` in agent/config.py.
- [X] T006 Update the record types and line format in rag/taric.py (contracts/snapshot-file.md, data-model §2, §4):
  - **New** frozen, slotted `TaricAreaRecord` with:
    - `geo_area: str`: "the area id, for example `CN`, `1008`, `1011`; unique in the file";
    - `name: str`: "English text of the description period valid on D; the latest one if several; `""` when none";
    - `member_of: tuple[str, ...]`: "the groups this area belongs to on D … `[]` when none".
  - **`TaricMeasureRecord`** gains a last field `excluded_areas: tuple[str, ...] = ()`, holding a "list of area ids, sorted, no duplicates … `[]` when none; ids are stored as given, even if no area record has that id".
  - **`record_to_line`**: the snapshot record stays a keyed object; every other record becomes `[kind, *fields]`, with tuples written as arrays.
  - **`line_to_record`**: accepts a keyed object only for `snapshot`, and an array only for the other kinds, with the exact width. It returns tuples for `member_of` and `excluded_areas`, and refuses anything else with TaricFileError.
- [X] T007 Rewrite tests/fixtures/taric/snapshot_small.jsonl in schema 2, with the same 7 code lines and 8 measure lines (`excluded_areas` `[]`) and no area lines yet. Make `TaricStore.from_jsonl` in rag/taric.py read schema-2 lines: it accepts `geographical_area` lines and ignores them until US1. Feature 002's store tests pass unchanged apart from T004.
- [X] T008 [P] Log the rewrite reason in `load_taric` in rag/loader.py (FR-003, contracts/loader-cli.md step 4). When `read_snapshot_header` raises TaricFileError:
  - log `taric: <snapshot path> will be rewritten: <reason>`;
  - mark the previous snapshot as `(older format or unreadable)`, so the summary reads `replaced snapshot (older format or unreadable)`.
  The skip rule is otherwise unchanged.

**Checkpoint**: `pytest -q` green. The loader writes schema 2, and a schema-1 file is rewritten without `--force`, with its reason logged.

---

## Phase 3: User Story 1 - Return measures for country groups that contain the origin (Priority: P1) 🎯 MVP

**Goal**: the snapshot holds every EU area valid on D, with its English name and the groups it belongs to. The lookup returns the measures of every group that contains the origin, at any depth. Each measure keeps its own area code and carries the area's name (FR-001, FR-005, FR-006 for areas, FR-008, FR-009).

**Independent Test**: store tests on the small fixture, then quickstart D on the real snapshot: 7318 15 20 gains 763 and 775 for 1008, named "All third countries", and all 14 subdivisions of 3926 90 97 gain 410 for 1008.

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [X] T009 [P] [US1] Add area tests to tests/unit/test_taric_extract.py for `parse_geographical_areas(payload("GeographicalArea"), D)`, which returns `TaricAreaRecord`s for the EU areas valid on D, in id order:
  - **Names**: CN is named "China" (not "Old name"); the SV-only area's name is `""`.
  - **`member_of`**:
    - CN holds 1008, 1011 and the inner group, sorted;
    - US holds 1008 and 1011;
    - the inner group holds the outer group;
    - the ended, future and national memberships are absent.
  - **Not stored**: the area that ended before D and SE-NAT.
  - **Inline XML cases**:
    - a kept membership naming an unknown group SID raises ExtractError naming the member and the SID;
    - a membership whose group is an EU area not valid on D is not kept.
  - **`build_snapshot`**: `len(snapshot.areas) == expected["area_records"]`.
- [X] T010 [P] [US1] Extend tests/fixtures/taric/snapshot_small.jsonl and tests/unit/test_taric_store.py:
  - **Area lines**:
    - `1011` "ERGA OMNES" and `1008` "All third countries";
    - an outer group `4000` and an inner group `4013` (member_of `["4000"]`);
    - `CN` (member_of `["1008","1011","4000","4013"]`: a direct member of 4000 and also one through 4013) and `US` (member_of `["1008","1011"]`);
    - a group with name `""`;
    - two groups that are members of each other, and an area `ZZ` in one of them.
  - **Measure lines**:
    - a 1008 import control 763 on 7318150000;
    - a 4000 veterinary control 410 on 7318155800;
    - one measure for the unnamed group.
  - **Header counts**: keep `goods_records` and `measure_records` equal to the lines, and update `test_snapshot_info`.
  - **Tests**:
    - CN gets the 1008 and 4000 measures, each with its own `geo_area`, the 1008 one with `geo_area_name == "All third countries"`;
    - US gets the 1008 measure but not the 4000 one;
    - an origin without an area record (`JP`) gets only its own and erga omnes measures;
    - the unnamed group's measure carries `geo_area_name == ""`;
    - a lookup for `ZZ` ends despite the cycle;
    - no measure appears twice although CN lists 1011 as a group;
    - the 4000 measure appears once although CN reaches 4000 both directly and through 4013.
  - **Feature 002's tests**: update their expected SID lists where the new group measures now apply, and add `geo_area_name` to `test_measure_fields`; none is dropped. Their order and input rules stay (FR-009).
- [X] T011 [P] [US1] Extend tests/integration/test_taric_loader.py: after the first load, the file holds `expected["area_records"]` area lines, by id, right after line 1 and before the code lines. The CN area line's `member_of` equals the fixture's three groups. The progress log names `expected["area_records"]` EU geographical areas.

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement area parsing in rag/taric_extract.py (research R-01, R-02; data-model §2, §5):
  - **`parse_geographical_areas(payload, d) -> list[TaricAreaRecord]`**: map the SIDs of all EU areas; keep the EU areas valid on D, by id. For each:
    - the English text of the description period valid on D, the latest if several, else `""`;
    - `member_of`: the sorted ids of the groups of its EU memberships valid on D whose group is an EU area valid on D.
  - **Inconsistent data**: "A kept membership (EU, valid on D, member valid on D) whose group SID names no EU area: the load stops and names the member and the SID."
  - **`Snapshot`**: `areas: list[TaricAreaRecord]` replaces `geo_areas`; `build_snapshot` passes D.
  - **`write_snapshot`**: writes the area records by `geo_area` before the codes.
  - **rag/loader.py**: the progress line uses `len(snapshot.areas)`.
- [X] T013 [P] [US1] Implement group resolution and names in rag/taric.py (contracts/taric-store.md; data-model §6):
  - **`TaricMeasure`** gains `geo_area_name: str` right after `geo_area`: "the stored name of the measure's area, or `""` when the area has no name or no record".
  - **The store** keeps each area's name and `member_of`.
  - **Applicable area set**: `{origin, "1011"}` plus every area reached from the origin by following `member_of`, each visited once.
  - **The lookup** keeps import or both measures whose `geo_area` is in that set, and fills `geo_area_name`.
  - **Unchanged**: sort order, inheritance and input checks.
- [X] T014 [US1] Load the real extract into data/taric.jsonl and check US1 (quickstart B in part, D):
  1. Keep the schema-1 file for quickstart J: `cp data/taric.jsonl /tmp/taric-schema1.jsonl`.
  2. Run `python -m rag.loader --taric` without `--force`. The progress log shows the rewrite reason (schema 1) and 314 EU geographical areas.
  3. Look up `73181520` and `39269097` for CN: 7318152000 has 763 and 775 for `1008` "All third countries", and each of the 14 subdivisions of 3926 90 97 has 410 for `1008`.

**Checkpoint**: group measures with their area names come back on real data; `pytest -q` green.

---

## Phase 4: User Story 2 - Leave out measures that exclude the origin (Priority: P1)

**Goal**: each measure in the snapshot carries its excluded areas, and the lookup leaves out a measure when any of them is in the origin's applicable area set. The load summary reports the three counts (FR-002, FR-004, FR-006).

**Independent Test**: store tests on the small fixture, including the group-level exclusion that exists only in fixtures (spec US2 scenario 2, SC-002). Then, on the real snapshot, the erga omnes anti-dumping measures on 7307 93 11 91 and 8427 90 00 11 are absent for CN and present for US.

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [X] T015 [P] [US2] Add exclusion tests to tests/unit/test_taric_extract.py:
  - the measure with one EU and one national exclusion element gets exactly that EU id;
  - the measure listing two areas out of order, plus a duplicate, gets them sorted and once each;
  - every other measure gets `()`;
  - in `build_snapshot`, the number of measures with exclusions equals `expected["measures_with_exclusions"]`.
- [X] T016 [P] [US2] Extend tests/fixtures/taric/snapshot_small.jsonl and tests/unit/test_taric_store.py with these measures (header counts kept equal to the lines):
  - an erga omnes measure excluding CN: not returned for CN, returned for US;
  - an erga omnes measure excluding the inner group 4013, which contains CN: not returned for CN, returned for US. This is the fixture-only case of spec US2 scenario 2 and SC-002;
  - a 1008 measure excluding CN: not returned for CN, returned for US;
  - a measure excluding an area outside CN's applicable set (`JP`): still returned for CN.
- [X] T017 [P] [US2] Extend tests/integration/test_taric_loader.py:
  - the written measure lines carry the fixture's exclusions;
  - the summary contains `area names {area_names} · group memberships {membership_records} · measures with excluded areas {measures_with_exclusions}`, using expected.json's values.

### Implementation for User Story 2

- [X] T018 [P] [US2] Read exclusions in `parse_measures` in rag/taric_extract.py (research R-03): `excluded_areas` holds the `geographicalAreaId` of every EU `measureExcludedGeographicalArea` child. Per data-model §4, it is a "list of area ids, sorted, no duplicates … ids are stored as given".
- [X] T019 [P] [US2] Apply the exclusion rule in rag/taric.py: the store keeps each measure's excluded areas, and the lookup drops a measure when any of them is in the applicable area set (FR-006).
- [X] T020 [P] [US2] Add the summary line in `load_taric` in rag/loader.py (FR-004, contracts/loader-cli.md), right after the `code records …` line: `area names N · group memberships M · measures with excluded areas K`, with thousands separators. N counts the areas with a non-empty name, M the `member_of` entries over all areas, and K the measures with at least one excluded area.
- [X] T021 [US2] Reload the real extract into data/taric.jsonl and check US2:
  1. Run `python -m rag.loader --taric --force`. The summary reads `area names 314 · group memberships 2,805 · measures with excluded areas 10,581`.
  2. Look up `73079311` and `84279000` for CN and US: the erga omnes 552 measures on 7307931191 (58.6 %) and 8427900011 (70.8 %) are absent for CN and present for US.
  3. Look up `07032000` for CN and US: the 1008 tariff quota 122 (9.6 %), which excludes AR, BY, CN, GB and RU, is absent for CN and present for US, a member of 1008 it does not exclude; CN keeps its own quota 122 for CN.

**Checkpoint**: measures that exclude the origin, directly or through a group, are left out; `pytest -q` green.

---

## Phase 5: User Story 3 - Hide statistic measures from lookup results (Priority: P2)

**Goal**: the lookup never returns measure type 566. The records stay in the snapshot file (FR-007).

**Independent Test**: on the real snapshot, 2710 19 11, where type 566 applies to China without an exclusion (spec US3 note, research R-06), shows no 566 measure.

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [X] T022 [US3] Extend tests/fixtures/taric/snapshot_small.jsonl and tests/unit/test_taric_store.py:
  - add a 1011 type-566 measure without exclusions and a CN type-566 measure (header counts kept equal to the lines);
  - neither is returned for CN or US;
  - `store.snapshot.measure_records` still counts both.

### Implementation for User Story 3

- [X] T023 [US3] Filter type 566 in `lookup_taric` in rag/taric.py, next to the import filter (FR-007).
- [X] T024 [US3] Check US3 on the real snapshot data/taric.jsonl:
  - `27101911` for CN shows no 566 on 2710191110, though the file holds one for 1011 and one for CN;
  - none of the six acceptance codes 39249000, 73181542, 73181558, 73181568, 73181582, 73181595 shows 566.

**Checkpoint**: no lookup returns a statistic measure; `pytest -q` green.

---

## Phase 6: User Story 4 - Keep app startup fast with the snapshot (Priority: P2)

**Goal**: the knowledge base opens at most 2 s later with the snapshot than without it. The snapshot is still loaded once at app start (FR-011, clarification Q1, research R-07).

**Independent Test**: quickstart G with tests/eval/kb_load_time.py; the full offline suite still passes.

### Regression tests for User Story 4 (written before T026; they already pass)

- [X] T025 [US4] Add regression tests to tests/unit/test_taric_store.py that pin the read path's refusals before T026 rewrites it:
  - `TaricStore.from_jsonl` raises TaricFileError naming the line number for a line in the middle of the file that has the wrong number of elements, names an unknown kind, or is a keyed object;
  - the existing malformed-line, empty-file and other-schema cases stay.
  These tests already pass on the current read path, since T006 and T007 refuse such lines, and must still pass after T026. Together with the store tests of US1 to US3 they are the safety net for the rewrite.

### Implementation for User Story 4

- [X] T026 [US4] Replace the read path of `TaricStore.from_jsonl` in rag/taric.py (research R-07):
  - **Header**: check it as before.
  - **Each later line**: decode it once with `json.loads` and dispatch on its kind tag with a width check. Use `line_to_record` only to word an error.
  - **In memory**:
    - parents, declarable codes, names and `member_of` go in dictionaries;
    - measures are tuples of strings interned through one dict cache, with no `dataclasses.replace`;
    - export-only and type-566 measures are skipped at load. They stay in the file, and `measure_records` is unchanged.
  - **Filters**: dropping at load becomes the only export-only and type-566 filter. Remove the lookup-time trade-movement and 566 checks (feature 002's import filter and T023's filter); the store tests prove the results are unchanged.
  - **Results**: `lookup_taric` builds the frozen `TaricMeasure` and `TaricSubdivision` results, and parses their dates, only for what it returns.
- [X] T027 [US4] Measure SC-004 with tests/eval/kb_load_time.py on the real snapshot from T021 (quickstart G):
  1. Run `python tests/eval/kb_load_time.py with` and `… without` alternately, three times each, with nothing else heavy running.
  2. Every `with` run is at most 2 s slower than its paired `without` run; about 0.7–0.8 s is expected.
  3. Time ten lookups on the same snapshot, as feature 002's quickstart I did: each answers well under 1 s.
  4. Keep the figures for README.md (T031).

**Checkpoint**: startup target met; `pytest -q` green.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: the acceptance re-run, documentation and the final validation.

- [X] T028 [P] Update tests/eval/taric_acceptance.py (research R-09; FR-012):
  - **Remove the group-gap code**: `load_raw`, `group_gap`, and the gap lines in `measure_cell`, `details` and the Markdown text. The lookup now returns group measures, and the raw reader cannot read schema 2.
  - **Compare every area**: `ezt_check` compares every area found on either side, for each subdivision: CN, 1011, 1008 and any other area in a further column. A new mismatch is listed, not hidden.
  - **Show names**: `measure_line` shows the area name next to the code. Replace the hand-written `CHINA_GROUPS` labels with the names from the snapshot.
  - **New `--counts` option**: it reads area and measure lines with `line_to_record` and prints:
    - the groups containing the origin, with their member counts;
    - the erga omnes measures excluding the origin, and how many the lookup returns;
    - the type-566 records, and how many the lookup returns.
  - **Docstring and steps text**: no longer call group measures a known gap.
- [X] T029 Run tests/eval/taric_acceptance.py (quickstart E, F, H; FR-012, SC-002, SC-003):
  1. `python tests/eval/taric_acceptance.py --counts` lists the 15 groups besides erga omnes, 16 with 1011, with research R-05's member counts, "1,238 … 0 returned" and "968 … 0 returned".
  2. `python tests/eval/taric_acceptance.py --markdown tests/eval/taric_acceptance.md`: the EZT-online check reads "match" for the 1008 rows of 3926 90 97 and the six 7318 15 codes, and no 566 row remains.
  3. Report every remaining difference to the author.
- [X] T030 The author hand-checks one country exclusion against EZT-online, following specs/003-taric-groups-exclusions/quickstart.md scenario I (SC-006), for example 7307 93 11 91. Tick when the author confirms.
- [X] T031 [P] Update the TARIC section of README.md:
  - **Lookup rule**: the origin, every group containing it and erga omnes; measures excluding any of these are left out; export-only and type-566 measures are never returned; each measure carries its area's name.
  - **File and timings**: the schema-2 file size, the full-load time from T021 and the startup figures from T027.
  - **Weaknesses**: drop the group and exclusion gap; keep full temporary stops, unnamed additional-code companies and the Meursing table.
  - **Tests**: the new offline test count.
- [X] T032 Final validation with specs/003-taric-groups-exclusions/quickstart.md:
  - `pytest -q` green offline; record the test count before this feature (391 collected on 2026-10-23) and after, and confirm that no existing test was dropped;
  - quickstart C: a re-run without `--force` is skipped and the hash is unchanged;
  - quickstart J: restart the Streamlit server, since it never reloads `ui/*.py`. The caption reads `TARIC snapshot 2026-10-01 · 105 CN-8 mismatches`. With `/tmp/taric-schema1.jsonl` in place it reads `TARIC not loaded` and the sample check still runs; then put the schema-2 file back;
  - quickstart K: the index hashes are unchanged.
- [X] T033 [P] Make the loader write data/SOURCES.md with LF line endings in rag/loader.py (author's request, 2026-10-23),
  in both places it is written: the TARIC load (`load_taric`) and the full build (`write_sources_md`); `write_text`
  translates newlines to CRLF on Windows unless `newline="
"` is passed. Test first in
  tests/integration/test_taric_loader.py: after a load, the register holds no carriage return. Run before T032.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001 and T002 can run together.
- **Foundational (Phase 2)**: depends on Setup (T002 regenerates the fixtures the format and loader tests read). BLOCKS all user stories.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after US1. The exclusion rule uses US1's applicable area set, and the summary line counts US1's areas and memberships.
- **US3 (Phase 5)**: after Foundational only; it can run alongside US1 and US2. It touches the same `lookup_taric` and `snapshot_small.jsonl`, so coordinate the edits; in priority order it comes third.
- **US4 (Phase 6)**: after US1 to US3. T026 rewrites the read path once the stored content is final, and T027 measures the real schema-2 file from T021.
- **Polish (Phase 7)**: after all stories. T029 needs T028; T030 needs the real snapshot from T021; T033 comes before T032, which comes last.

### Within Each User Story

- Tests are written and seen to FAIL before the implementation task they cover.
- File format before loader and store.
- Extraction (rag/taric_extract.py) and store (rag/taric.py) tasks of one story touch different files and can run in parallel.
- Real-data checks (T014, T021, T024, T027) come after the story's code and its green tests.

### Parallel Opportunities

- T001 ∥ T002 (Setup).
- T003 ∥ T004 (foundation tests); T008 ∥ T006/T007 (different files).
- US1: T009 ∥ T010 ∥ T011, then T012 ∥ T013.
- US2: T015 ∥ T016 ∥ T017, then T018 ∥ T019 ∥ T020.
- Polish: T028 ∥ T031.

---

## Parallel Example: User Story 1

```bash
# Tests first, together:
Task: "Area tests for parse_geographical_areas in tests/unit/test_taric_extract.py"
Task: "Group and name tests on snapshot_small.jsonl in tests/unit/test_taric_store.py"
Task: "Area lines in the written file in tests/integration/test_taric_loader.py"

# Then the two implementation halves, together:
Task: "parse_geographical_areas, Snapshot.areas and area lines first in rag/taric_extract.py"
Task: "Applicable area set and geo_area_name in rag/taric.py"
```

## Parallel Example: User Story 2

```bash
Task: "Exclusion tests in tests/unit/test_taric_extract.py"
Task: "Exclusion tests on snapshot_small.jsonl in tests/unit/test_taric_store.py"
Task: "Exclusion lines and summary line in tests/integration/test_taric_loader.py"

Task: "excluded_areas in parse_measures in rag/taric_extract.py"
Task: "Exclusion rule in rag/taric.py"
Task: "Summary line with the three counts in rag/loader.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup.
2. Phase 2: Foundational. This blocks everything: the schema-2 format and the rewrite reason.
3. Phase 3: US1, with group measures and names on the real snapshot (T014).
4. **STOP and VALIDATE**: quickstart D; `pytest -q` green.

### Incremental Delivery

1. Setup and Foundational: schema 2 in place.
2. US1: group measures returned with names (MVP).
3. US2: exclusions applied. Spec 2 may show measures to the clerk only after US1 and US2 (feature 002's acceptance finding).
4. US3: the 566 filter.
5. US4: startup within 2 s.
6. Polish: the acceptance re-run, the hand check, the README and the final validation.

---

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Each user story is independently testable at its checkpoint.
- Real-data checks use the 2026-10-01 extract in data/raw/taric/ and need gpg. The unit and integration tests need neither the extract nor the network.
- After the first schema-2 load (T014), later loads of the same extract need `--force` (T021).
- Commit only when the author asks.
