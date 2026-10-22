# Data Model: One-Time TARIC Load for Digits 9 to 10

The snapshot file `data/taric.jsonl` holds three record kinds, distinguished by `kind` (author's design constraint). The field-by-field file format is in [contracts/snapshot-file.md](contracts/snapshot-file.md); this document covers meaning, relationships and validation. D is the snapshot date.

## 1. Extract file (input, not stored)

One signed per-object file of the extract.

| Field | Source | Rule |
|---|---|---|
| object | file name | one of GoodsNomenclature, Measure, MeasureType, GeographicalArea, DutyExpression, Regulation |
| batch_id | file name `ObjectName_batchId_YYMMDD.xml.gz.pgp` | identical for all six files (FR-003) |
| snapshot_date | file name YYMMDD → 20YY-MM-DD | identical for all six files (FR-003) |
| export_id | `<id>` of the XML document | identical for all six files (research R-01) |
| signature | gpg check | valid, made by the pinned key `410160CE…D0E3E1C9` (FR-002) |

Exactly one file per object; a missing object or a second file for an object stops the load (FR-004). Files of other objects are ignored (FR-001).

## 2. TARIC Snapshot (`kind: "snapshot"`)

Exactly one, on the first line (FR-010).

| Field | Type | Meaning |
|---|---|---|
| schema | int | file format version, 1 for this feature; the store refuses other values |
| snapshot_date | date | D, from the file names |
| batch_id | string | from the file names |
| export_id | string | from the XML documents |
| source_files | list of 6 strings | the six file names, in the object order above |
| loaded_at | timestamp (UTC, ISO 8601) | time of the load; the only field that differs between two runs on the same extract |
| goods_records | int | number of code records in the file |
| measure_records | int | number of measure records in the file |
| cn8_mismatches | int | CN-8 prefixes of declarable codes missing from CN 2026 (FR-011) |

## 3. TARIC Code (`kind: "goods_nomenclature"`)

A goods record with product-line suffix 80, not national, valid on D (FR-005, FR-006). Grouping lines (other suffixes) and national records are never stored.

| Field | Type | Rule |
|---|---|---|
| code | string, 10 digits | unique in the file (FR-016) |
| cn8 | string, 8 digits | `code[:8]` |
| description | string | English (EN) text of the description period valid on D; `""` when digits 9–10 are `00` (FR-007) |
| valid_from | date | record start date |
| valid_to | date or null | record end date; null = open-ended |
| declarable | bool | true when no stored code lies beneath it (FR-008; derived, research R-06) |
| parent | code or null | nearest enclosing stored code; null for chapter codes (derived, research R-06) |

`declarable` and `parent` are not in the author's field list; FR-008, FR-017 and FR-018 need them, and they are computed once at load from the TARIC indents.

## 4. Measure (`kind: "measure"`)

A non-national measure valid on D, not suspended by a partial temporary stop covering D, and not ended by its regulation's effective end date (FR-005, research R-04, R-05), whatever level of code it is recorded against (FR-009). Measures no lookup can use are dropped and counted: the Meursing-table measures (types 672, 673, 674), which carry no goods code, and measures on a code held only as a national record (research R-14).

| Field | Type | Rule |
|---|---|---|
| sid | int > 0 | TARIC's measure identifier; unique in the file (FR-016) |
| code | string, 10 digits | the code the measure is recorded against (may be a parent: CN-8, subheading, heading, chapter) |
| measure_type | string | TARIC measure type code, for example `103`, `552` |
| measure_type_label | string | English description from MeasureType |
| trade_movement | `import`, `export` or `both` | from the measure type (research R-07) |
| geo_area | string | geographical area id, for example `CN`, `1011` |
| additional_code | string or null | additional code type + id, for example `C999`; null when the measure has none (FR-009, clarification Q1) |
| duty | string | rendered duty expression (research R-08); `""` when the measure has no components |
| regulation_id | string | generating regulation id |
| regulation_ref | string | `OJ {journal}, p. {page} ({published})`; `""` when the regulation file has no such record |
| valid_from | date | measure start date |
| valid_to | date or null | measure end date; null = open-ended |

Validation at load:
- Two measures with the same `sid`: identical → one is kept; different → the load stops and names the SID (spec edge case).
- A non-national measure whose measure type is missing from MeasureType → the load stops and names the type (data inconsistency; should not occur).

## 5. CN-8 Mismatch (log entry, not stored)

`store/logs/taric-cn8-mismatches-<snapshot date>.txt`, one line per CN-8 prefix of a declarable code that the CN 2026 nomenclature lacks: `<cn8> <one declarable code under it>`. The count goes to the snapshot record (FR-011, FR-012). Parents are never counted.

## 6. Runtime shapes (TaricStore)

| Shape | Fields |
|---|---|
| TaricSnapshotInfo | snapshot_date, batch_id, loaded_at, goods_records, measure_records, cn8_mismatches |
| TaricSubdivision | code, description, valid_from, valid_to, measures (tuple of TaricMeasure) |
| TaricMeasure | sid, recorded_on (the code it is recorded against), measure_type, measure_type_label, geo_area, additional_code, duty, regulation_id, regulation_ref, valid_from, valid_to |

Lookup rules ([contracts/taric-store.md](contracts/taric-store.md)):
- subdivisions of a CN-8 = declarable codes with that `cn8` (FR-017), in code order;
- applicable measures of a subdivision = measures recorded against the subdivision or any ancestor in its `parent` chain (FR-018) whose `geo_area` is the origin or `1011` and whose `trade_movement` is `import` or `both` (research R-07); ordered by (measure_type, geo_area, additional_code, sid);
- validity of everything returned is judged on D (clarification Q1 of the clarify session).

## 7. Relationships

```text
TARIC Snapshot 1 ── describes ── * TARIC Code, * Measure
TARIC Code     * ── parent ───── 0..1 TARIC Code         (chapters have no parent)
Measure        * ── recorded on ─ 1 TARIC Code (any level)
Lookup: CN-8 → declarable TARIC Codes (cn8 = CN-8) → Measures on the code and its ancestors
```

## 8. State transitions

Snapshot file `data/taric.jsonl`:

| From | Event | To |
|---|---|---|
| absent | load succeeds | present (date D) |
| present (D) | load of an extract dated D, no force | unchanged; "skip" reported (FR-014) |
| present (D) | load with force | rewritten; same records, new `loaded_at` (FR-015) |
| present (D₁) | load of an extract dated D₂ ≠ D₁ | replaced; summary names D₁ and D₂ |
| any | load fails at any step | unchanged (FR-013) |

App (per server process): at start `kb.taric` becomes a TaricStore, or `None` when the file is absent, unreadable or of another schema version; the caption follows (FR-024). A new snapshot is picked up after a restart.

## 9. Volumes (extract of 2026-10-01)

| Item | Count |
|---|---|
| Code records (suffix 80, EU, valid on D) | 22,361 |
| of which declarable | 16,742 (9,572 with digits 9–10 ≠ 00) |
| Measure records (EU, in force on D, usable) | 161,959 |
| of which for CN or erga omnes | 41,093 |
| of which with an additional code | 24,749 |
| Ended by their regulation (open-ended, research R-04), not stored | 103,738 |
| Dropped: Meursing table / on a national-only code (research R-14) | 23,184 / 1 |
| CN-8 mismatches | 105 (chapters 98 and 99) |
| File size and lines | 55.8 MB, 184,321 lines |
