# Implementation Plan: TARIC Lookup Completeness for Country Groups and Exclusions

**Branch**: `003-taric-groups-exclusions` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-taric-groups-exclusions/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The TARIC loader reads three more things from files it already verifies:
- from GeographicalArea, the EU areas valid on the snapshot date, with their English names and the groups each belongs to;
- from Measure, each kept measure's excluded areas.

It writes them into a schema-2 `data/taric.jsonl`. Without `--force`, the next `--taric` run rewrites a schema-1 file and logs why.

`lookup_taric(cn8, origin)` keeps its signature:
- **Applicable areas**: it resolves the origin, every group that contains it at any depth, and erga omnes.
- **Returned measures**: those whose area is applicable and none of whose excluded areas is.
- **Never returned**: export-only and type-566 measures.
- **Names**: each measure carries its area's name.

App startup gets cheaper. The snapshot is still read once at app start (clarification Q1), but:
- the bulk lines become positional JSON arrays;
- the store reads them into tuples;
- it builds result objects only for what a lookup returns;
- it holds no export-only or type-566 measures.

Technical approach, from [research.md](research.md):
- **Memberships (R-01)**: nested under each member area, groups named by SID; 2,805 kept on D. Resolution is transitive, although no group is a member of another group on D.
- **Names (R-02)**: the English description valid on D; all 314 areas have one.
- **Exclusions (R-03)**: `measureExcludedGeographicalArea` ids; 10,581 kept measures have them.
- **Lookup rule (R-04)**: for China on D, 1,512 group measures are added, 1,238 erga omnes measures that exclude China and 75 other type-566 measures are removed, and 37 group measures that exclude China stay out.
- **Startup (R-07)**: a prototype of the chosen read path cut the knowledge-base opening time with the snapshot from +2.35–2.71 s to +0.66–0.80 s over the time without it.
- **Format (R-08)**: line 1 stays a keyed object; the other lines are positional arrays. The file shrinks from 57 MB to about 28 MB.

## Technical Context

**Language/Version**: Python 3.13 (project range `>=3.11,<3.14`)

**Primary Dependencies**: unchanged: `lxml` for streaming XML, standard-library `json`, and the GnuPG command-line tool for signatures (feature 002's recorded deviation). No new package.

**Storage**: `data/taric.jsonl` becomes schema 2: about 28 MB, git-ignored, replaced atomically as before. No other file changes format. `store/chroma`, `store/chroma-bti`, `store/bm25.pkl`, `store/bti_docs.jsonl`, `store/index_meta.json` and `data/nomenclature_2026.jsonl` are untouched (FR-013).

**Testing**: pytest, offline, tests first (R-10).
- **Fixtures**: the fixture extract is regenerated with areas, names, memberships and exclusions; the hand-written `snapshot_small.jsonl` is rewritten in schema 2.
- **Integration**: an integration test covers the schema-1 rewrite and the new summary line.
- **By hand**: the acceptance aid and the timing script run against the real snapshot.

**Target Platform**: the Windows 11 developer machine; loader from Git Bash or PowerShell; Streamlit app unchanged.

**Project Type**: single Python project, as in features 001 and 002.

**Performance Goals**:
- **App startup (SC-004, FR-011)**: the knowledge base opens at most 2 s later with the snapshot than without it; the prototype measured +0.66 to +0.80 s.
- **Lookup**: well under 1 s; today under 1 ms, and the applicable-area walk adds microseconds.
- **Full load**: feature 002's 20–42 s plus the membership and exclusion parsing; it still streams the same files once.

**Constraints**:
- The loader reads only the six object files, with no network access and no secret.
- The CN 2026 and EBTI indexes are untouched (FR-013).
- Output is deterministic and replaced atomically.
- The `lookup_taric` signature and parent-chain inheritance are unchanged (FR-009).
- The snapshot is loaded once at app start (Q1).

**Scale/Scope**, for the 2026-10-01 extract:
- **Areas**: 314 area records, 2,805 memberships.
- **Codes**: 22,361 code records.
- **Measures**: 161,959 measure records, 10,581 of them with excluded areas; the store keeps 142,898 of them in memory.
- **File**: 184,635 lines.

No NEEDS CLARIFICATION remain; [research.md](research.md) resolves R-01 to R-10.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.1.1 (2026-10-22).

| # | Principle | Gate | Pre-research | Post-design evidence |
|---|---|---|---|---|
| I | Guardrails live in code | Membership resolution, exclusions and the type filter are deterministic code; no model involved; invalid input still rejected | PASS | The lookup rule is a pure function of the snapshot and the origin (data-model §6). `lookup_taric` keeps feature 002's `ValueError` input checks. No TARIC code is shown to a clerk in this feature |
| II | Untrusted input, end to end | Downloaded files stay third-party data: signatures checked before reading; parsing reads attributes only; no secret | PASS | The new data comes from the two files already verified (GeographicalArea, Measure). It is parsed by the same streaming reader, with entities, DTDs and network access off. Membership, name and exclusion values are stored as data and never used as paths or commands |
| III | Grounded, cited, never guessed | Names, memberships and exclusions come from the extract only | PASS | Area names are the published English texts, typos kept (R-02). Group measures keep their own area code, so the source of every measure stays visible (FR-008). Nothing is model-generated |
| IV | Hybrid, structure-aware retrieval | CN 2026 stays the retrieval source; TARIC never embedded; scripted loader; truthful sidebar | PASS | `--taric` still never calls an index builder (FR-013; feature 002's integration test stays). The caption is unchanged and still states the snapshot date and mismatch count. A schema-1 file reads "TARIC not loaded", which is true until it is reloaded |
| V | Single-purpose, schema-typed tools | Tools added or changed are listed | PASS | No agent tool is added or changed; `lookup_taric` stays a plain function for Spec 2 (feature 002's FR-021 test stays) |
| VI | Native Streamlit UI | Native components only | PASS | No UI change |
| VII | Test-first and measured | Parsing and lookup-rule tests written first and seen to fail; offline | PASS | `test_taric_format.py`, `test_taric_extract.py`, `test_taric_store.py` and `test_taric_loader.py` gain failing tests before each change (R-10). The startup target is measured with a committed script (`tests/eval/kb_load_time.py`) |
| — | Technology stack | Stack as listed; deviations recorded | PASS | No new dependency. Feature 002's GnuPG deviation is unchanged |
| — | Out of scope | Nothing sent anywhere; no ATLAS flow | PASS | No filing, export or messaging change |
| — | Data and privacy | Every dataset recorded with source, version and retrieval date | PASS | Same dataset and register row; the extract contains no shipper data |
| — | Code organisation | `app.py` → `agent/` → `tools/` → `rag/` | PASS | Changes stay in `rag/`, `agent/config.py` (schema constant), tests and eval scripts. Lookup results stay frozen dataclasses; the Pydantic boundary is Spec 2's tool, as in feature 002 |

**Post-design re-check (after Phase 1)**: all gates still PASS; no new deviation. Three research findings bore on the spec's acceptance wording; at the author's request the spec now states all three (2026-10-23):
- **No real example of a group exclusion**: no measure on the 2026-10-01 snapshot excludes a group that contains China. US2 scenario 2 and the second half of SC-002 can only be shown with fixtures (R-04).
- **The six 566 codes**: their type-566 measures are erga omnes measures that exclude China, so the exclusion rule alone removes them. US3 is shown on its own with 2710 19 11, where 566 applies to China (R-06).
- **Group measures that exclude China**: 37 measures for China's groups exclude China and stay out. The net gain is 1,512 group measures, not the 1,549 that feature 002's R-13 sized (R-04).

## Project Structure

### Documentation (this feature)

```text
specs/003-taric-groups-exclusions/
├── spec.md              # Feature specification (with clarifications)
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: R-01 … R-10
├── data-model.md        # Phase 1 output: schema-2 additions and the lookup rule
├── quickstart.md        # Phase 1 output: scenarios A–K and the hand check
├── contracts/
│   ├── snapshot-file.md # schema 2, supersedes feature 002's
│   ├── taric-store.md   # changes to TaricMeasure and lookup_taric
│   └── loader-cli.md    # changes to the skip check, parsing and summary
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
agent/
└── config.py                     # TARIC_SCHEMA = 2
rag/
├── taric.py                      # TaricAreaRecord; TaricMeasureRecord.excluded_areas; header object + positional lines;
│                                 # lean read path; applicable-area set; exclusion and 566 rules; TaricMeasure.geo_area_name
├── taric_extract.py              # parse_geographical_areas → areas with names and member_of; exclusions in parse_measures;
│                                 # Snapshot.areas; areas written first
└── loader.py                     # rewrite reason for an unreadable or older file; summary line with the three counts
tests/
├── fixtures/
│   ├── make_taric_fixtures.py    # areas with description periods and memberships; measures with exclusions; new counts
│   └── taric/                    # regenerated (throwaway keys), expected.json with the new counts;
│                                 # snapshot_small.jsonl rewritten in schema 2
├── unit/
│   ├── test_taric_format.py      # schema-2 kinds and positions, header object, refusals
│   ├── test_taric_extract.py     # names, memberships, group mapping, exclusions
│   └── test_taric_store.py       # groups (nested), exclusions, 566, names, no duplicates
├── integration/
│   └── test_taric_loader.py      # schema-1 file rewritten without --force, reason logged; summary counts
└── eval/
    ├── taric_acceptance.py       # no group gap; every area compared; names; --counts
    ├── taric_acceptance.md       # regenerated by the re-run (FR-012)
    └── kb_load_time.py           # NEW: T037's startup measurement, committed (SC-004)
README.md                         # TARIC section: lookup rule, file size, timings, weaknesses
```

**Structure Decision**: feature 002's layout is kept; no module is added under `rag/`. The format, store and extraction
changes stay in the modules that own them. The timing script moves from a temporary folder into `tests/eval/`, so
"measured as in T037" is repeatable.

## Design notes (how the pieces fit)

- **Extraction**:
  - `parse_geographical_areas(payload, d)` maps the SIDs of the EU areas, then builds one `TaricAreaRecord` per EU area valid on D: its name valid on D, and the sorted ids of the groups it belongs to on D (R-01, R-02).
  - `parse_measures` adds `excluded_areas` (R-03).
  - `Snapshot.areas` replaces `Snapshot.geo_areas`.
  - `write_snapshot` writes the header, then areas by id, codes by code and measures by (code, SID).
- **Format**:
  - `record_to_line` writes the snapshot record as an object and every other record as `[kind, …fields]`.
  - `line_to_record` reads both forms and refuses wrong widths and unknown kinds with `TaricFileError` (contracts/snapshot-file.md).
- **Store read path (R-07)**:
  - `from_jsonl` checks the header as before.
  - It then decodes each line once, dispatching on the kind tag with a width check. It falls back to `line_to_record` only to word an error.
  - It keeps parents, declarable codes, names and `member_of` in dictionaries.
  - It keeps measures as tuples of interned strings, skipping export-only and type 566.
  - `lookup_taric` builds frozen results and parses their dates for what it returns.
- **Lookup rule (R-04)**:
  - The applicable set is the origin, `1011`, and every group reached from the origin through `member_of`, with a visited set.
  - A measure passes when its area is in the set and none of its excluded areas is.
  - Export-only and type-566 measures are dropped when the store reads the file (R-07), the only place they are filtered; the sort order is as before.
- **Old files (R-08)**:
  - **Loader**: `load_taric` catches the header reader's `TaricFileError` as before. It now logs `taric: data/taric.jsonl will be rewritten: <reason>` and reports `replaced snapshot (older format or unreadable)`.
  - **App**: `open_taric_store` refuses the file as before.
- **Acceptance aid (R-09)**:
  - The group-gap code goes, and every area is compared with the stored EZT-online rows.
  - Measure lines show the area name.
  - `--counts` prints the groups containing the origin, the erga omnes measures excluding it (and how many are returned), and the type-566 records (and how many are returned).
- **Documentation**:
  - **`README.md`**: the TARIC section states the new lookup rule, the schema-2 file size and the new timings. Its weaknesses list drops the group and exclusion gap and keeps full temporary stops, unnamed additional-code companies and the Meursing table.
  - **`CLAUDE.md`**: the commands are unchanged.
  - **Feature 002's documents**: they stay as the record of schema 1. This spec states what it supersedes.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

None. The GnuPG command-line tool remains the one recorded deviation, justified in feature 002's plan; this feature adds
no other.
