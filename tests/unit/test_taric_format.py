"""TARIC snapshot file format, schema 2: the snapshot record as an object, every other kind as a positional array, and the
header reader (features 002 and 003, contracts/snapshot-file.md)."""
import json

import pytest

from rag.taric import (TaricAreaRecord, TaricCodeRecord, TaricFileError, TaricMeasureRecord, TaricSnapshotRecord,
                       line_to_record, read_snapshot_header, record_to_line)

pytestmark = pytest.mark.unit

SNAPSHOT_KEYS = ["kind", "schema", "snapshot_date", "batch_id", "export_id", "source_files", "loaded_at", "goods_records",
                 "measure_records", "cn8_mismatches"]

SNAPSHOT = TaricSnapshotRecord(
    schema=2, snapshot_date="2026-10-01", batch_id="b1", export_id="b1",
    source_files=tuple(f"{obj}_b1_261001.xml.gz.pgp" for obj in
                       ("GoodsNomenclature", "Measure", "MeasureType", "GeographicalArea", "DutyExpression", "Regulation")),
    loaded_at="2026-10-22T14:05:31Z", goods_records=2, measure_records=1, cn8_mismatches=0)
AREA = TaricAreaRecord(geo_area="CN", name="China", member_of=("1008", "1011", "4013"))
CODE = TaricCodeRecord(code="7318155810", cn8="73181558", description="Für zivile Luftfahrzeuge – ½ Zoll", valid_from="2020-01-01",
                       valid_to=None, declarable=True, parent="7318155800")
MEASURE = TaricMeasureRecord(sid=2345678, code="7318155810", measure_type="552", measure_type_label="Definitive anti-dumping duty",
                             trade_movement="import", geo_area="CN", additional_code="C999", duty="85 %", regulation_id="R2201910",
                             regulation_ref="OJ L 36, p. 1 (2022-02-17)", valid_from="2022-02-18", valid_to="2027-02-17",
                             excluded_areas=("KR", "TW"))
PLAIN_MEASURE = TaricMeasureRecord(sid=1, code="7318150000", measure_type="103", measure_type_label="Third country duty",
                                   trade_movement="import", geo_area="1011", additional_code=None, duty="3.7 %",
                                   regulation_id="R8726580", regulation_ref="", valid_from="2026-01-01", valid_to=None)


class TestRecordLines:
    @pytest.mark.parametrize("record", [SNAPSHOT, AREA, CODE, MEASURE, PLAIN_MEASURE])
    def test_round_trip(self, record):
        assert line_to_record(record_to_line(record)) == record

    def test_the_snapshot_record_is_an_object_in_key_order(self):
        data = json.loads(record_to_line(SNAPSHOT))
        assert list(data) == SNAPSHOT_KEYS
        assert (data["kind"], data["schema"]) == ("snapshot", 2)

    @pytest.mark.parametrize("record, expected", [
        (AREA, ["geographical_area", "CN", "China", ["1008", "1011", "4013"]]),
        (CODE, ["goods_nomenclature", "7318155810", "73181558", "Für zivile Luftfahrzeuge – ½ Zoll", "2020-01-01", None, True,
                "7318155800"]),
        (MEASURE, ["measure", 2345678, "7318155810", "552", "Definitive anti-dumping duty", "import", "CN", "C999", "85 %",
                   "R2201910", "OJ L 36, p. 1 (2022-02-17)", "2022-02-18", "2027-02-17", ["KR", "TW"]]),
    ])
    def test_other_kinds_are_positional_arrays_in_contract_order(self, record, expected):
        assert json.loads(record_to_line(record)) == expected

    def test_values_compact_and_as_is(self):
        line = record_to_line(CODE)
        assert "\n" not in line
        assert json.dumps(json.loads(line), ensure_ascii=False, separators=(",", ":")) == line   # compact separators
        assert "Für zivile Luftfahrzeuge – ½ Zoll" in line                                        # non-ASCII written as-is
        assert json.loads(line)[5] is None                                                       # open-ended is null
        assert json.loads(record_to_line(SNAPSHOT))["source_files"] == list(SNAPSHOT.source_files)
        assert json.loads(record_to_line(PLAIN_MEASURE))[-1] == []                               # no exclusions: []

    @pytest.mark.parametrize("line", [
        "not json",
        "[1, 2]",                                                          # no known kind
        '[["measure"], 2]',                                                # a kind that is not a string
        '["measure", 1]',                                                  # too few fields
        '["geographical_area", "CN", "China", [], "extra"]',               # too many fields
        '["geographical_area", "CN", "China", "1008"]',                    # member_of not a list
        '["snapshot", 2]',                                                 # the snapshot record is an object
        '{"kind": "unknown"}',
        '{"kind": "goods_nomenclature", "code": "7318155810"}',           # only the snapshot record is an object
        '"just a string"',
    ])
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

    @pytest.mark.parametrize("first", [record_to_line(CODE), "", record_to_line(SNAPSHOT).replace('"schema":2', '"schema":1')])
    def test_no_snapshot_record_or_other_schema_raises(self, tmp_path, first):
        path = tmp_path / "taric.jsonl"
        path.write_text(first + "\n", encoding="utf-8")
        with pytest.raises(TaricFileError):
            read_snapshot_header(path)
