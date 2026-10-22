"""TARIC snapshot file format: record kinds, key order, header reader (feature 002, contracts/snapshot-file.md)."""
import json

import pytest

from rag.taric import (TaricCodeRecord, TaricFileError, TaricMeasureRecord, TaricSnapshotRecord, line_to_record,
                       read_snapshot_header, record_to_line)

pytestmark = pytest.mark.unit

SNAPSHOT_KEYS = ["kind", "schema", "snapshot_date", "batch_id", "export_id", "source_files", "loaded_at", "goods_records",
                 "measure_records", "cn8_mismatches"]
CODE_KEYS = ["kind", "code", "cn8", "description", "valid_from", "valid_to", "declarable", "parent"]
MEASURE_KEYS = ["kind", "sid", "code", "measure_type", "measure_type_label", "trade_movement", "geo_area", "additional_code",
                "duty", "regulation_id", "regulation_ref", "valid_from", "valid_to"]

SNAPSHOT = TaricSnapshotRecord(
    schema=1, snapshot_date="2026-10-01", batch_id="b1", export_id="b1",
    source_files=tuple(f"{obj}_b1_261001.xml.gz.pgp" for obj in
                       ("GoodsNomenclature", "Measure", "MeasureType", "GeographicalArea", "DutyExpression", "Regulation")),
    loaded_at="2026-10-22T14:05:31Z", goods_records=2, measure_records=1, cn8_mismatches=0)
CODE = TaricCodeRecord(code="7318155810", cn8="73181558", description="Für zivile Luftfahrzeuge – ½ Zoll", valid_from="2020-01-01",
                       valid_to=None, declarable=True, parent="7318155800")
MEASURE = TaricMeasureRecord(sid=2345678, code="7318155810", measure_type="552", measure_type_label="Definitive anti-dumping duty",
                             trade_movement="import", geo_area="CN", additional_code="C999", duty="85 %", regulation_id="R2201910",
                             regulation_ref="OJ L 36, p. 1 (2022-02-17)", valid_from="2022-02-18", valid_to="2027-02-17")


class TestRecordLines:
    @pytest.mark.parametrize("record", [SNAPSHOT, CODE, MEASURE])
    def test_round_trip(self, record):
        assert line_to_record(record_to_line(record)) == record

    @pytest.mark.parametrize("record, keys, kind", [(SNAPSHOT, SNAPSHOT_KEYS, "snapshot"), (CODE, CODE_KEYS, "goods_nomenclature"),
                                                     (MEASURE, MEASURE_KEYS, "measure")])
    def test_key_order_and_kind(self, record, keys, kind):
        data = json.loads(record_to_line(record))
        assert list(data) == keys
        assert data["kind"] == kind

    def test_values_compact_and_as_is(self):
        line = record_to_line(CODE)
        assert "\n" not in line
        assert json.dumps(json.loads(line), ensure_ascii=False, separators=(",", ":")) == line   # compact separators
        assert "Für zivile Luftfahrzeuge – ½ Zoll" in line                                        # non-ASCII written as-is
        data = json.loads(line)
        assert data["valid_from"] == "2020-01-01" and data["valid_to"] is None                    # open-ended is null
        assert json.loads(record_to_line(SNAPSHOT))["source_files"] == list(SNAPSHOT.source_files)

    @pytest.mark.parametrize("line", ["not json", "[1, 2]", '{"kind": "unknown"}',
                                      '{"kind": "goods_nomenclature", "code": "7318155810"}'])
    def test_malformed_lines_raise(self, line):
        with pytest.raises(TaricFileError):
            line_to_record(line)


class TestHeaderReader:
    def test_reads_the_first_line_only(self, tmp_path):
        path = tmp_path / "taric.jsonl"
        path.write_text(record_to_line(SNAPSHOT) + "\n" + record_to_line(CODE) + "\n{broken\n", encoding="utf-8")
        assert read_snapshot_header(path) == json.loads(record_to_line(SNAPSHOT))

    def test_absent_file_gives_none(self, tmp_path):
        assert read_snapshot_header(tmp_path / "taric.jsonl") is None

    @pytest.mark.parametrize("first", [record_to_line(CODE), "", record_to_line(SNAPSHOT).replace('"schema":1', '"schema":2')])
    def test_no_snapshot_record_or_other_schema_raises(self, tmp_path, first):
        path = tmp_path / "taric.jsonl"
        path.write_text(first + "\n", encoding="utf-8")
        with pytest.raises(TaricFileError):
            read_snapshot_header(path)
