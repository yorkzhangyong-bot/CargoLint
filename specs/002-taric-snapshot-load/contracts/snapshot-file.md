# Contract: TARIC snapshot file `data/taric.jsonl`

Readers: `TaricStore` (this feature) and Spec 2. Meaning and validation of each field: [data-model.md](../data-model.md).

## Format

- UTF-8 without BOM, LF line endings, final newline; one JSON object per line, non-ASCII characters written as-is.
- Line 1 is the snapshot record. Then the `goods_nomenclature` records sorted by `code`, then the `measure` records sorted by (`code`, `sid`).
- Keys appear in the order listed below. Dates are `YYYY-MM-DD`; `null` means open-ended. `loaded_at` is `YYYY-MM-DDTHH:MM:SSZ` (UTC).
- `schema` is 1. A reader MUST refuse any other value.
- The file is generated and git-ignored; it is rebuilt from the signed extract with `python -m rag.loader --taric`.

## Record kinds and key order

| kind | keys, in order |
|---|---|
| `snapshot` | kind, schema, snapshot_date, batch_id, export_id, source_files, loaded_at, goods_records, measure_records, cn8_mismatches |
| `goods_nomenclature` | kind, code, cn8, description, valid_from, valid_to, declarable, parent |
| `measure` | kind, sid, code, measure_type, measure_type_label, trade_movement, geo_area, additional_code, duty, regulation_id, regulation_ref, valid_from, valid_to |

## Example lines

Values are illustrative; angle brackets mark placeholders.

```json
{"kind": "snapshot", "schema": 1, "snapshot_date": "2026-10-01", "batch_id": "<batch>", "export_id": "3dc153a8-7542-4d91-8157-b7784f72797b", "source_files": ["GoodsNomenclature_<batch>_261001.xml.gz.pgp", "Measure_<batch>_261001.xml.gz.pgp", "MeasureType_<batch>_261001.xml.gz.pgp", "GeographicalArea_<batch>_261001.xml.gz.pgp", "DutyExpression_<batch>_261001.xml.gz.pgp", "Regulation_<batch>_261001.xml.gz.pgp"], "loaded_at": "2026-10-22T14:05:31Z", "goods_records": 22361, "measure_records": 161959, "cn8_mismatches": 105}
{"kind": "goods_nomenclature", "code": "7318155800", "cn8": "73181558", "description": "", "valid_from": "<date>", "valid_to": null, "declarable": false, "parent": "<parent code>"}
{"kind": "goods_nomenclature", "code": "7318155810", "cn8": "73181558", "description": "<English TARIC description>", "valid_from": "<date>", "valid_to": null, "declarable": true, "parent": "7318155800"}
{"kind": "measure", "sid": 1234567, "code": "7318155800", "measure_type": "103", "measure_type_label": "Third country duty", "trade_movement": "import", "geo_area": "1011", "additional_code": null, "duty": "<duty text>", "regulation_id": "<regulation id>", "regulation_ref": "OJ <journal>, p. <page> (<published>)", "valid_from": "<date>", "valid_to": null}
{"kind": "measure", "sid": 2345678, "code": "7318155810", "measure_type": "552", "measure_type_label": "Definitive anti-dumping duty", "trade_movement": "import", "geo_area": "CN", "additional_code": "C767", "duty": "39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %", "regulation_id": "<regulation id>", "regulation_ref": "OJ <journal>, p. <page> (<published>)", "valid_from": "<date>", "valid_to": null}
```

## Invariants a reader may rely on

- Exactly one snapshot record, on line 1; its counts equal the numbers of code and measure lines.
- `code` is unique among code records; `sid` is unique among measure records.
- Every `parent` names a code record in the same file; chapter codes have `parent: null`.
- Every record is valid on `snapshot_date`; no record is national.
- `trade_movement` is one of `import`, `export`, `both`.
- `description` is empty for every code whose digits 9–10 are `00`.
- `duty` is display text only: the duty components, then the conditional duties (`<duty> with <document>`, `<duty> if <price> is at least <threshold>`, and `otherwise <duty>` last). A reader must not parse it to decide which rate applies.
