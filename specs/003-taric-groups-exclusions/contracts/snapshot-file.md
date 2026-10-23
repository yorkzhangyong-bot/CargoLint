# Contract: TARIC snapshot file `data/taric.jsonl`, schema 2

Supersedes feature 002's [snapshot-file.md](../../002-taric-snapshot-load/contracts/snapshot-file.md) (schema 1).
Readers: `TaricStore`, `read_snapshot_header` (data-source register row, loader skip check) and the acceptance aid.
Meaning and validation of each field: [data-model.md](../data-model.md).

## Format

- UTF-8 without BOM, LF line endings, final newline; compact JSON (`","` and `":"` separators), non-ASCII characters
  written as-is.
- **Line 1**: the snapshot record, a JSON object with its keys in the order below. `schema` is **2**; a reader MUST
  refuse any other value.
- **Every other line**: a JSON array whose first element is the record kind and whose other elements are the fields in
  the positions below. Order of lines: `geographical_area` by `geo_area`, then `goods_nomenclature` by `code`, then
  `measure` by (`code`, `sid`).
- Dates are `YYYY-MM-DD`; `null` means open-ended. `loaded_at` is `YYYY-MM-DDTHH:MM:SSZ` (UTC).
- The file is generated and git-ignored; it is rebuilt from the signed extract with `python -m rag.loader --taric`.

## Record kinds

| kind | form | keys or positions, in order |
|---|---|---|
| `snapshot` | object | kind, schema, snapshot_date, batch_id, export_id, source_files, loaded_at, goods_records, measure_records, cn8_mismatches |
| `geographical_area` | array of 4 | kind, geo_area, name, member_of |
| `goods_nomenclature` | array of 8 | kind, code, cn8, description, valid_from, valid_to, declarable, parent |
| `measure` | array of 14 | kind, sid, code, measure_type, measure_type_label, trade_movement, geo_area, additional_code, duty, regulation_id, regulation_ref, valid_from, valid_to, excluded_areas |

`member_of` and `excluded_areas` are JSON arrays of area ids (possibly empty). A reader MUST refuse a line that is not a
JSON array, names an unknown kind, or has another number of elements than its kind.

## Example lines

Values are illustrative; angle brackets mark placeholders.

```json
{"kind":"snapshot","schema":2,"snapshot_date":"2026-10-01","batch_id":"<batch>","export_id":"3dc153a8-7542-4d91-8157-b7784f72797b","source_files":["GoodsNomenclature_<batch>_261001.xml.gz.pgp","Measure_<batch>_261001.xml.gz.pgp","MeasureType_<batch>_261001.xml.gz.pgp","GeographicalArea_<batch>_261001.xml.gz.pgp","DutyExpression_<batch>_261001.xml.gz.pgp","Regulation_<batch>_261001.xml.gz.pgp"],"loaded_at":"2026-10-23T14:05:31Z","goods_records":22361,"measure_records":161959,"cn8_mismatches":105}
["geographical_area","1008","All third countries",[]]
["geographical_area","CN","China",["1005","1008","1011","1030","2500","3100","3200","3300","4002","4003","4011","4013","5001","5005","5007","5009"]]
["goods_nomenclature","7318155810","73181558","<English TARIC description>","<date>",null,true,"7318155800"]
["measure",1234567,"7318150000","763","Import control","import","1008",null,"","<regulation id>","OJ <journal>, p. <page> (<published>)","<date>",null,[]]
["measure",2345678,"7307931191","552","Definitive anti-dumping duty","import","1011",null,"58.6 %","<regulation id>","OJ <journal>, p. <page> (<published>)","<date>",null,["CN","KR","MY","RU","TW"]]
```

## Invariants a reader may rely on

- Exactly one snapshot record, on line 1; `goods_records` and `measure_records` equal the numbers of code and measure
  lines.
- `geo_area` is unique among area records, `code` among code records and `sid` among measure records.
- Every id in a `member_of` names an area record in the same file; `member_of` and `excluded_areas` are sorted and hold
  no duplicates. An `excluded_areas` id or a measure's `geo_area` may name an area without a record.
- Every `parent` names a code record in the same file; chapter codes have `parent: null`.
- Every record is valid on `snapshot_date`; no record is national.
- `trade_movement` is one of `import`, `export`, `both`. The file keeps export-only and type-566 measures; lookups never
  return them.
- `description` is empty for every code whose digits 9–10 are `00`.
- `duty` is display text only, as in schema 1; a reader must not parse it to decide which rate applies.
- The same extract always yields the same lines in the same order; only `loaded_at` differs.
