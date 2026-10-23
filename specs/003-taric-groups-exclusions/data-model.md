# Data Model: TARIC Lookup Completeness for Country Groups and Exclusions

This feature extends feature 002's model ([002 data-model](../002-taric-snapshot-load/data-model.md)). Sections not
named here are unchanged. The line format is in [contracts/snapshot-file.md](contracts/snapshot-file.md); this
document covers meaning, relationships and validation. D is the snapshot date.

## 1. TARIC Snapshot (`kind: "snapshot"`)

Unchanged fields; `schema` is **2**. Readers refuse any other value, so a schema-1 file written by feature 002 is
refused by the app and rewritten by the next load (FR-003, research R-08). `goods_records` and `measure_records` still
count every code and measure line in the file, including the export-only and type-566 measures that lookups never
return.

## 2. Geographical Area (`kind: "geographical_area"`, new)

An EU geographical area (country, group or region) valid on D. National areas and areas not valid on D are never stored.

| Field | Type | Rule |
|---|---|---|
| geo_area | string | the area id, for example `CN`, `1008`, `1011`; unique in the file |
| name | string | English text of the description period valid on D; the latest one if several; `""` when none (research R-02) |
| member_of | list of area ids, sorted | the groups this area belongs to on D: EU memberships valid on D whose group is an EU area valid on D (FR-001, research R-01); `[]` when none |

`member_of` is derived from the membership records nested in the member's record; each names its group by SID, which the
loader maps to the group's id. A member may itself be a group.

## 3. TARIC Code (`kind: "goods_nomenclature"`)

Unchanged.

## 4. Measure (`kind: "measure"`)

Feature 002's fields plus one:

| Field | Type | Rule |
|---|---|---|
| excluded_areas | list of area ids, sorted, no duplicates | the EU excluded geographical areas listed for this measure in the Measure file (FR-002, research R-03); `[]` when none; ids are stored as given, even if no area record has that id |

## 5. Validation at load (additions)

- A kept membership (EU, valid on D, member valid on D) whose group SID names no EU area: the load stops and names the
  member and the SID. This is a data inconsistency that should not occur; none occurs on D.
- A kept membership whose group is an EU area not valid on D: not kept. None occurs on D.

## 6. Runtime shapes (TaricStore)

| Shape | Fields |
|---|---|
| TaricSnapshotInfo | unchanged |
| TaricSubdivision | unchanged |
| TaricMeasure | sid, recorded_on, measure_type, measure_type_label, geo_area, **geo_area_name**, additional_code, duty, regulation_id, regulation_ref, valid_from, valid_to |

`geo_area_name` is the stored name of the measure's area, or `""` when the area has no name or no record (FR-008).

Internally the store keeps, built once when the file is read (research R-07):
- the parent of every code, and the declarable codes of every CN-8;
- the name and `member_of` of every area;
- the measures by the code they are recorded on, as tuples of interned strings, without export-only and type-566 measures
  (they stay in the file).

Frozen `TaricMeasure` and `TaricSubdivision` objects are built only for what a lookup returns.

**Applicable Area Set** of an origin O (FR-005): `{O, 1011}` plus every area reached from O by following `member_of`
repeatedly; each area is visited once, so a cycle ends the walk. It is computed per lookup; for China it holds 17 ids: CN, and
the 15 groups besides erga omnes, 16 with 1011 (research R-05).

Lookup rules ([contracts/taric-store.md](contracts/taric-store.md)):
- subdivisions of a CN-8: unchanged (feature 002);
- applicable measures of a subdivision: recorded against the subdivision or any ancestor in its `parent` chain, and
  - `geo_area` in the applicable area set, and
  - no `excluded_areas` entry in the applicable area set, and
  - `trade_movement` is `import` or `both`, and
  - `measure_type` is not `566` (FR-006, FR-007);
- order: unchanged, (measure_type, geo_area, additional_code or "", sid).

## 7. Relationships

```text
TARIC Snapshot    1 ── describes ── * Geographical Area, * TARIC Code, * Measure
Geographical Area * ── member_of ── * Geographical Area      (a group; on D no group is a member of a group)
Measure           * ── geo_area ─── 1 Geographical Area      (by id; the area record may be missing, then no name)
Measure           * ── excludes ─── * Geographical Area      (by id)
Lookup: CN-8 → declarable TARIC Codes → Measures on the code and its ancestors
        → kept when geo_area ∈ Applicable Area Set(origin) and excluded_areas ∩ Applicable Area Set(origin) = ∅
```

## 8. State transitions (additions)

| From | Event | To |
|---|---|---|
| present, schema 1 | load of any extract, with or without force | rewritten as schema 2; the run logs the reason (FR-003) |
| present, schema 1 | app start | `kb.taric = None`, reason logged, caption "TARIC not loaded" until the next load and a restart |

All of feature 002's transitions still hold for schema-2 files.

## 9. Volumes (extract of 2026-10-01)

| Item | Count |
|---|---|
| Geographical area records (EU, valid on D) | 314, all with an English name |
| Group memberships kept | 2,805 (246 members); none is a group |
| Measures with excluded areas | 10,581 of 161,959 |
| Measures kept in memory by the store | 142,898: the 161,959 less 18,093 export-only and 968 type-566 |
| Lines | 184,635 (1 + 314 + 22,361 + 161,959) |
| File size | about 28 MB (27.3 MB measured for the positional layout before areas and exclusions) |
