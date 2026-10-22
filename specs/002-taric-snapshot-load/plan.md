# Implementation Plan: One-Time TARIC Load for Digits 9 to 10

**Branch**: `002-taric-snapshot-load` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-taric-snapshot-load/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The operator downloads the six signed object files of one TARIC extract from the Swedish Customs distribution and runs `python -m rag.loader --taric`. The loader checks each file's signature against a pinned copy of the Swedish Customs key, streams the XML, keeps the EU records valid on the snapshot date, derives declarable codes and parent links from the TARIC indents, renders duty expressions, reconciles CN-8 prefixes against CN 2026, and writes `data/taric.jsonl` atomically and deterministically. An in-memory, read-only `TaricStore` loads that file at app start and offers `lookup_taric(cn8, origin="CN")` for Spec 2; the sidebar shows one TARIC caption.

Technical approach, from [research.md](research.md):
- **Signature check (R-02)**: GnuPG runs in a throwaway home with no file paths passed.
- **Parsing (R-03)**: `lxml` streams the files.
- **Filters**:
  - EU records only (R-05);
  - validity on the snapshot date, including partial temporary stops (R-04);
  - no measures that a lookup cannot use: the Meursing table and measures on national-only codes, dropped and counted (R-14);
  - import-relevant measures only (R-07).
- **Hierarchy (R-06)**: worked out from indents.
- **Snapshot file (R-10)**: JSONL, following the `BTIStore` pattern.

Measured on the 2026-10-01 extract, the full load takes about 20 s. The result is 22,361 codes (16,742 declarable), 161,959 measures in force and 105 CN-8 mismatches, all chapter-98 and chapter-99 special codes.

## Technical Context

**Language/Version**: Python 3.13 (project range `>=3.11,<3.14`)

**Primary Dependencies**: `lxml` (already a dependency) for streaming XML; standard library `gzip`, `json`, `subprocess`, `tempfile`, `re`; the GnuPG 2.4 command-line tool, which ships with Git for Windows, for signature checks — a new system dependency (Complexity Tracking #1). No new Python package.

**Storage**: input `data/raw/taric/` (six `*.xml.gz.pgp` files, git-ignored); output `data/taric.jsonl` (generated, about 57 MB, git-ignored, replaced atomically); public key copy `data/Tulltaxan_Fildistribution.asc` (committed); mismatch log `store/logs/taric-cn8-mismatches-<date>.txt`. No change to `store/chroma`, `store/chroma-bti`, `store/bm25.pkl` or `data/nomenclature_2026.jsonl`.

**Testing**: pytest, offline.
- **Parser tests** use plain fixture XML.
- **Signature tests** use tiny fixture extracts signed with a throwaway key, a tampered file, a file signed by another key, and one real 2.8 KB `DutyExpression` file checked against the real key copy. They skip with a reason when gpg is missing.
- **An integration test** runs the loader on a temporary folder and proves the search indexes are never touched.

**Target Platform**: the Windows 11 developer machine; the loader runs from Git Bash or PowerShell; the Streamlit app is otherwise unchanged.

**Project Type**: single Python project (Streamlit app with importable packages), as in feature 001.

**Performance Goals**:
- **Full load (SC-006)**: under 30 minutes; measured load time about 20 s (T021).
- **App startup with the snapshot (SC-007)**: at most 10 s longer, for about 184,000 lines read once per process.
- **Lookup**: under 1 s, served by dictionaries keyed by CN-8 and by code.

**Constraints**: no network and no secret during load; the CN 2026 and BTI indexes unchanged (FR-022, FR-023); deterministic output (FR-015); atomic replace (FR-013); EU records only.

**Scale/Scope**, for the 2026-10-01 extract:
- **Goods**: 34,323 records, of which 25,866 EU records are valid on the date. Of those, 22,361 are suffix-80 codes and 16,742 are declarable.
- **Measures**: 813,746 records, of which 161,959 EU measures are in force and usable; 41,093 of these are for China or erga omnes.
- **Reconciliation**: the 9,896 TARIC CN-8 prefixes are compared with 9,791 CN 2026 CN-8 codes.

No NEEDS CLARIFICATION remain; [research.md](research.md) resolves R-01 to R-13.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.1.1 (2026-10-22).

| # | Principle | Gate | Pre-research | Post-design evidence |
|---|---|---|---|---|
| I | Guardrails live in code | Filtering, validity, reconciliation and lookup are deterministic code; no model involved; invalid lookup input is rejected | PASS | `rag/taric_extract.py` and `rag/taric.py` are pure functions; `lookup_taric` raises `ValueError` on a bad CN-8 (FR-019). No TARIC code is shown to a clerk in this feature. Principle I's code rules still name HS-6 only, so Spec 2 will need an amendment before it shows TARIC codes |
| II | Untrusted input, end to end | Downloaded files are third-party data: authenticity checked before reading; parsing reads content only; no secret | PASS | The signature is checked against the pinned key before parsing (FR-002, research R-02). XML is parsed with entities, DTDs and network access off (R-03). No API key is involved; the committed key is public |
| III | Grounded, cited, never guessed | Codes, descriptions, duties and references come from the extract only | PASS | Duty text is rendered from the components in code (R-08); the regulation reference comes from the Regulation file. Nothing is model-generated |
| IV | Hybrid, structure-aware retrieval | CN 2026 stays the retrieval source; TARIC never embedded; scripted loader; truthful sidebar | PASS | The `--taric` mode never calls the index builders (R-11; integration test for SC-005). The constitution's sources line (1.1.1) is honoured. The TARIC caption states the snapshot date and mismatch count (FR-024). The loader's chapter-list clause is met: `--taric` always loads every chapter of the extract, so wider coverage never needs a code change; the chapter options configure the search-index build, which this mode never runs, so they are rejected with `--taric` |
| V | Single-purpose, schema-typed tools | The plan lists tools added or changed (amended 1.1.0) | PASS | No agent tool is added or changed. The lookup is a plain function, testable without a model or Streamlit; Spec 2 decides how the agent reaches it |
| VI | Native Streamlit UI | Native components only; the knowledge-base statement is truthful | PASS | One `st.caption` in the existing "Knowledge base" expander; no HTML or CSS |
| VII | Test-first and measured | Parsing, signature and lookup tests written first and seen to fail; offline | PASS | `tests/unit/test_taric_extract.py`, `test_taric_store.py`, `test_pgp.py` and `tests/integration/test_taric_loader.py` come before the code they cover (R-12) |
| — | Technology stack | Stack as listed; deviations recorded | PASS with one deviation | GnuPG command-line tool → Complexity Tracking #1 |
| — | Out of scope | No ATLAS flow, nothing sent anywhere | PASS | No filing, export or messaging change |
| — | Data and privacy | Every dataset recorded with source, version and retrieval date | PASS | TARIC row in `data/SOURCES.md` (FR-025, R-11); the extract contains no shipper data |
| — | Code organisation | `app.py` → `agent/` → `tools/` → `rag/` and the line store | PASS | New modules sit in `rag/`; the sidebar only reads `kb.taric`, as it already reads `kb.bti` for its caption. Lookup results are frozen dataclasses like the store's compact records (about 184,000 lines), not Pydantic models; the Pydantic boundary is the agent tool that Spec 2 adds, as Principle V requires |

**Post-design re-check (after Phase 1)**: all gates still PASS, with the single recorded deviation. The author confirmed two design interpretations on 2026-10-22, and both are recorded in the spec's assumptions:
- **Origin means import**: lookups return only import-relevant measures (research R-07).
- **EU records only**: Swedish national records in the Swedish export are dropped (research R-05).

## Project Structure

### Documentation (this feature)

```text
specs/002-taric-snapshot-load/
├── spec.md              # Feature specification (with clarifications)
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: R-01 … R-13
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output: validation scenarios A–J and the EZT-online acceptance
├── contracts/
│   ├── loader-cli.md    # the --taric command, exit codes, output, guarantees
│   ├── snapshot-file.md # data/taric.jsonl format and invariants
│   └── taric-store.md   # TaricStore, lookup_taric, KB wiring, caption
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
agent/
└── config.py                     # + TARIC paths, pinned key fingerprint, the six object names, CARGOLINT_GPG
rag/
├── pgp.py                        # NEW: find_gpg, check_key_copy, verify_signed (no-path gpg in a throwaway home)
├── taric_extract.py              # NEW: discover the file set, stream-parse, filter, hierarchy, duty text, reconcile, write
├── taric.py                      # NEW: record types, snapshot reader, TaricStore, lookup_taric
├── nomenclature.py               # + NomenclatureIndex.cn8_codes()
└── loader.py                     # + --taric [DIR] mode; SOURCES "taric" row; KnowledgeBase.taric; open_knowledge_base loads it
ui/
└── sidebar.py                    # + taric_caption(kb) under the knowledge-base caption
data/
├── Tulltaxan_Fildistribution.asc # pinned public key copy (committed)
├── taric.jsonl                   # generated snapshot (git-ignored)
└── raw/taric/                    # downloaded *.xml.gz.pgp (git-ignored, as data/raw/ already is)
tests/
├── fixtures/
│   ├── make_taric_fixtures.py    # NEW: builds the fixture extracts and bad copies; keys made in a temporary gpg home
│   └── taric/                    # NEW: signed fixture set, throwaway public keys only (no secret key), expected.json,
│                                 #      snapshot_small.jsonl, conflict/ and bad/ variants, one real signed DutyExpression file
├── unit/
│   ├── test_taric_format.py      # record kinds, key order, header reader, schema refusal
│   ├── test_pgp.py               # good, tampered, other key, real file, wrong key copy; skips without gpg
│   ├── test_taric_extract.py     # file set rules, EU-only, validity, stops, grouping lines, indents, duty text, reconciliation, SIDs
│   ├── test_taric_store.py       # single / multiple / no subdivision, inheritance, origins, trade movement, additional codes,
│   │                             # bad input, no rag.taric import under agent/ or tools/
│   └── test_sidebar_caption.py   # TARIC caption loaded / not loaded
├── integration/
│   └── test_taric_loader.py      # end-to-end load, skip, force, failure keeps the file, no index metadata, indexes untouched
└── eval/
    ├── taric_acceptance.py       # NEW: prints lookup results for the SC-001 comparison
    └── taric_acceptance.md       # NEW: 20-row comparison table, filled in against EZT-online
.gitignore                        # + data/taric.jsonl
```

**Structure Decision**: the existing single-project layout from feature 001 is kept. The three new modules in `rag/` follow `rag/bti.py`'s extraction-plus-store pattern, split so that the security-relevant signature check and the large streaming parser can be tested on their own. Documentation to update with the code: `README.md` (how to load TARIC), `CLAUDE.md` (command list) and `data/SOURCES.md` (generated row).

## Design notes (how the pieces fit)

- **Loader mode**: `--taric` runs only the TARIC load. `--force` then rewrites only `data/taric.jsonl`; today's `--force` would delete both search indexes, so the modes must stay separate (R-11). Combining `--taric` with the knowledge-base options is a usage error.
- **Order of work**:
  1. options;
  2. gpg and key copy;
  3. file set;
  4. skip check, before any expensive step;
  5. signatures;
  6. export ids;
  7. parsing and derivation;
  8. reconciliation;
  9. prepare the snapshot file and the updated register text, both as temporary files;
  10. replace the snapshot, then the register; the TARIC row never depends on the index metadata;
  11. summary.
- **Derived fields**: code records carry `declarable` and `parent` in addition to the author's field list (data-model §3). Measure records carry `sid`, `additional_code` (clarifications) and `trade_movement` (R-07).
- **Lookup**: declarable codes by CN-8. Measures are gathered along the `parent` chain, filtered to origin or 1011 and to import or both, and sorted deterministically. Results are frozen dataclasses.
- **App start**: `open_knowledge_base` builds the store once; `st.cache_resource` keeps it for the process. A missing or unreadable file or a wrong schema gives `kb.taric = None` and a logged reason. The caption follows; a restart picks up a new snapshot.
- **Known limitations** (spec; sized in R-13):
  - erga omnes measures that exclude China are returned, 1,238 import measures;
  - measures for country groups containing China are not returned, 1,549 import measures;
  - Meursing agricultural components and sugar and flour additional duties are not represented (R-14);
  - companies behind additional codes are not named;
  - full temporary stops are not applied (R-04).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| The GnuPG command-line tool is used for signature checks; the constitution's technology stack does not list it | The extract can only be trusted after checking its Swedish Customs signature (FR-002). Every file is DSA/SHA-1 signed, and gpg 2.4.9, already installed with Git for Windows, verified the real files. It is called without file paths (stdin, stdout, `cwd`), which works with Git's and native Windows builds alike | **PGPy**: unmaintained since 2022 and not verified on Python 3.13. **pysequoia**: its standard policy rejects SHA-1 data signatures. **A hand-written OpenPGP parser on `cryptography`**: security-sensitive code with no gain over a mature verifier. Only the loader needs gpg; the app and the parser tests do not |
