"""TARIC extract: file set, parsing, hierarchy, duty text and reconciliation (feature 002, research R-01 to R-09); areas,
names and memberships (feature 003, research R-01, R-02). No gpg needed."""
import gzip
import json
import re
from datetime import date
from pathlib import Path

import pytest

from agent.schemas import NomenclatureChunk
from rag.nomenclature import NomenclatureIndex
from rag.taric import TaricMeasureRecord
from rag.taric_extract import (ExtractError, ExtractFile, ExtractSet, build_snapshot, check_export_ids, discover_extract,
                               national_only_codes, parse_duty_expressions, parse_geographical_areas, parse_goods,
                               parse_measure_types, parse_measures, parse_regulations, reconcile)

pytestmark = pytest.mark.unit

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "taric"
NS = "http://www.arcticgroup.se/tariff/arctictariff/export"
D = date(2026, 10, 1)
BATCH = "11111111-2222-4333-8444-555555555555"
OTHER = "22222222-2222-4333-8444-555555555555"
OBJECTS = ("GoodsNomenclature", "Measure", "MeasureType", "GeographicalArea", "DutyExpression", "Regulation")
CN2026 = frozenset({"73181558", "73181595", "96170000"})
EXPECTED = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))


def payload(obj: str, folder: str = "xml") -> bytes:
    return gzip.compress((FIX / folder / f"{obj}.xml").read_bytes())


def document(*items: str) -> bytes:
    """A gzipped export document holding the given record elements."""
    return gzip.compress(f'<export xmlns="{NS}" xmlns:at="{NS}"><id>x</id><items>{"".join(items)}</items></export>'.encode())


def name(obj: str, batch: str = BATCH, yymmdd: str = "261001") -> str:
    return f"{obj}_{batch}_{yymmdd}.xml.gz.pgp"


def snapshot(log_dir: Path):
    files = tuple(ExtractFile(o, BATCH, D, Path(name(o))) for o in OBJECTS)
    return build_snapshot(ExtractSet(BATCH, D, files), {o: payload(o) for o in OBJECTS}, CN2026, log_dir)


@pytest.fixture(scope="module")
def ref():
    return {"types": parse_measure_types(payload("MeasureType")), "expressions": parse_duty_expressions(payload("DutyExpression")),
            "regulations": parse_regulations(payload("Regulation"))}


@pytest.fixture(scope="module")
def code_list():
    return parse_goods(payload("GoodsNomenclature"), D)


@pytest.fixture(scope="module")
def codes(code_list):
    return {c.code: c for c in code_list}


@pytest.fixture(scope="module")
def measure_list(ref):
    return parse_measures(payload("Measure"), D, ref["types"], ref["expressions"], ref["regulations"])


@pytest.fixture(scope="module")
def measures(measure_list):
    return {m.sid: m for m in measure_list}


@pytest.fixture(scope="module")
def area_list():
    return parse_geographical_areas(payload("GeographicalArea"), D)


@pytest.fixture(scope="module")
def areas(area_list):
    return {a.geo_area: a for a in area_list}


class TestDiscover:
    @staticmethod
    def _touch(folder: Path, *names: str) -> None:
        for n in names:
            (folder / n).write_bytes(b"signed")

    def test_accepts_the_six_files_of_one_batch_and_ignores_the_rest(self, tmp_path):
        names = [name(o) for o in OBJECTS]
        self._touch(tmp_path, *reversed(names), name("AdditionalCode"), "Measure.xml", "GoodsNomenclature.xml", "notes.txt")
        extract = discover_extract(tmp_path)
        assert (extract.batch_id, extract.snapshot_date) == (BATCH, D)
        assert [f.object for f in extract.files] == list(OBJECTS)
        assert [f.path.name for f in extract.files] == names
        assert all(f.batch_id == BATCH and f.snapshot_date == D for f in extract.files)

    def test_a_missing_object_is_named(self, tmp_path):
        self._touch(tmp_path, *(name(o) for o in OBJECTS if o != "Measure"))
        with pytest.raises(ExtractError, match=r"\bMeasure\b"):
            discover_extract(tmp_path)

    def test_an_object_that_appears_twice_names_both_files(self, tmp_path):
        self._touch(tmp_path, *(name(o) for o in OBJECTS), name("MeasureType", OTHER))
        with pytest.raises(ExtractError) as err:
            discover_extract(tmp_path)
        assert name("MeasureType") in str(err.value) and name("MeasureType", OTHER) in str(err.value)

    @pytest.mark.parametrize("odd", [name("Regulation", OTHER), name("Regulation", yymmdd="261002")])
    def test_batch_ids_or_dates_that_differ_name_the_files(self, tmp_path, odd):
        self._touch(tmp_path, *(name(o) for o in OBJECTS if o != "Regulation"), odd)
        with pytest.raises(ExtractError, match=re.escape(odd)):
            discover_extract(tmp_path)


class TestReferenceObjects:
    def test_measure_types_are_eu_only_with_label_and_trade_movement(self, ref):
        assert "SEALK" not in ref["types"]
        assert ref["types"]["103"] == ("Third country duty", "import")
        assert ref["types"]["478"] == ("Export authorization (Dual use)", "export")
        assert ref["types"]["483"][1] == "both"

    def test_export_ids_must_agree(self):
        same = {o: payload(o) for o in OBJECTS}
        assert check_export_ids(same) == BATCH
        odd = gzip.compress((FIX / "xml" / "MeasureType.xml").read_bytes().replace(BATCH.encode(), OTHER.encode()))
        with pytest.raises(ExtractError, match="MeasureType"):
            check_export_ids(dict(same, MeasureType=odd))

    def test_a_payload_that_is_not_gzip_is_named(self):
        with pytest.raises(ExtractError, match="MeasureType"):
            check_export_ids({"MeasureType": (FIX / "xml" / "MeasureType.xml").read_bytes()})


class TestGeographicalAreas:
    def test_eu_areas_valid_on_d_are_kept_in_id_order(self, area_list):
        # not stored: AN (ended before D) and SE-NAT (national)
        assert [a.geo_area for a in area_list] == ["1008", "1011", "4000", "4013", "5001", "5002", "CN", "US", "XK"]

    def test_the_english_name_of_the_description_period_valid_on_d(self, areas):
        assert (areas["CN"].name, areas["1008"].name, areas["XK"].name) == ("China", "All third countries", "")

    def test_only_eu_memberships_valid_on_d_are_kept_as_sorted_group_ids(self, areas):
        # not kept: CN in 5001 (ended before D), in 5002 (starts after D) and in 4000 (a national membership)
        assert areas["CN"].member_of == ("1008", "1011", "4013")
        assert areas["US"].member_of == ("1008", "1011")
        assert areas["4013"].member_of == ("4000",)
        assert areas["1011"].member_of == ()

    def test_a_membership_naming_no_eu_area_is_refused(self):
        member = ('<geographicalArea at:geographicalAreaId="CN" at:national="0" at:SID="439" at:dateStart="1984-01-01">'
                  '<geographicalAreaMembership at:SIDGeographicalAreaGroup="999" at:dateStart="2000-01-01" at:national="0"/>'
                  '</geographicalArea>')
        with pytest.raises(ExtractError, match=r"CN.*999"):
            parse_geographical_areas(document(member), D)

    def test_a_membership_of_a_group_not_valid_on_d_is_not_kept(self):
        group = ('<geographicalArea at:geographicalAreaId="5000" at:national="0" at:SID="1" at:dateStart="1984-01-01" '
                 'at:dateEnd="2020-12-31"/>')
        member = ('<geographicalArea at:geographicalAreaId="CN" at:national="0" at:SID="2" at:dateStart="1984-01-01">'
                  '<geographicalAreaMembership at:SIDGeographicalAreaGroup="1" at:dateStart="2000-01-01" at:national="0"/>'
                  '</geographicalArea>')
        assert [(a.geo_area, a.member_of) for a in parse_geographical_areas(document(group, member), D)] == [("CN", ())]

    def test_the_snapshot_holds_the_areas(self, tmp_path):
        assert len(snapshot(tmp_path).areas) == EXPECTED["area_records"]


class TestGoods:
    def test_only_eu_suffix_80_codes_valid_on_d_are_kept_in_code_order(self, code_list):
        # dropped: national 7318155899, ended 7318156000, future 7318157000, grouping lines 7318110000 and 7318155880
        assert [c.code for c in code_list] == ["7300000000", "7318000000", "7318150000", "7318155800", "7318155810", "7318155890",
                                               "7318159500", "7318159900", "7318159910", "9600000000", "9617000000"]

    def test_fields_and_the_description_of_the_period_valid_on_d(self, codes):
        c = codes["7318155810"]
        assert (c.cn8, c.description, c.valid_from, c.valid_to) == ("73181558", "For use in civil aircraft", "1990-01-01", None)

    @pytest.mark.parametrize("code", ["7318155800", "7318159500", "9617000000", "7318159910"])
    def test_no_description_for_00_codes_or_without_english_text(self, codes, code):
        assert codes[code].description == ""

    def test_hierarchy_from_indents_with_chapters_as_roots(self, codes):
        expected = {  # code: (parent, declarable); grouping lines are never parents
            "7300000000": (None, False), "7318000000": ("7300000000", False), "7318150000": ("7318000000", False),
            "7318155800": ("7318150000", False), "7318155810": ("7318155800", True), "7318155890": ("7318155800", True),
            "7318159500": ("7318150000", True), "7318159900": ("7318150000", False), "7318159910": ("7318159900", True),
            "9600000000": (None, False), "9617000000": ("9600000000", True),
        }
        assert {code: (c.parent, c.declarable) for code, c in codes.items()} == expected

    def test_a_code_stored_twice_is_refused(self):
        rec = (f'<goodsNomenclature at:goodsNomenclatureCode="9617000000" at:productLineSuffix="80" at:national="0" '
               f'at:dateStart="2000-01-01"><goodsNomenclatureIndent at:quantityIndents="00" at:dateStart="2000-01-01"/></goodsNomenclature>')
        xml = f'<export xmlns="{NS}" xmlns:at="{NS}"><id>x</id><items>{rec}{rec}</items></export>'.encode()
        with pytest.raises(ExtractError, match="9617000000"):
            parse_goods(gzip.compress(xml), D)


class TestMeasures:
    def test_only_eu_measures_in_force_on_d_are_kept_once_in_code_and_sid_order(self, measure_list):
        # dropped: 1009 partial stop on D, 1010 open-ended with an ended regulation, 1013 ended, 1014 future, -2001 national;
        # 1002 appears twice, identical; 1016 has its own end date after D, so its ended regulation does not end it.
        # The Meursing measures 1017-1019 and 1020 (on a national-only code) are parsed here and dropped by the snapshot.
        assert [(m.code, m.sid) for m in measure_list] == sorted((m.code, m.sid) for m in measure_list)
        assert sorted(m.sid for m in measure_list) == [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1015, 1016,
                                                       1017, 1018, 1019, 1020, 1021, 1022]

    def test_all_fields(self, measures):
        assert measures[1003] == TaricMeasureRecord(
            sid=1003, code="7318155810", measure_type="552", measure_type_label="Definitive anti-dumping duty", trade_movement="import",
            geo_area="CN", additional_code="C999", duty="85 %", regulation_id="R2201910", regulation_ref="OJ L 36, p. 1 (2022-02-17)",
            valid_from="2020-01-01", valid_to="2030-06-30")

    def test_trade_movement_and_additional_codes(self, measures):
        assert [measures[s].trade_movement for s in (1001, 1005, 1015)] == ["import", "export", "both"]
        assert [measures[s].additional_code for s in (1002, 1003, 1001)] == ["C001", "C999", None]

    @pytest.mark.parametrize("sid, duty", [
        (1002, "22 %"), (1001, "3.7 %"), (1004, "0 %"), (1008, "4.2 EUR / 100 kg + EA"),
        (1007, "6.7 % MIN 1.2 EUR / 100 kg MAX 2.4 EUR / 100 kg"), (1005, ""),
    ])
    def test_duty_text_from_components(self, measures, sid, duty):
        assert measures[sid].duty == duty            # 1002's condition carries no duty, so it adds nothing

    @pytest.mark.parametrize("sid, duty", [
        (1021, "39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %"),
        (1022, "0 EUR / MIL if the net free-at-frontier price is at least 325 EUR / MIL; "
               "otherwise the difference to 325 EUR / MIL"),
    ])
    def test_conditional_anti_dumping_duties_are_display_text_never_evaluated(self, measures, sid, duty):
        assert measures[sid].duty == duty
        assert measures[sid].additional_code in ("C767", "C123")

    def test_regulation_references(self, measures):
        assert measures[1001].regulation_ref == "OJ L 256, p. 1 (1987-09-07)"       # base regulation
        assert measures[1004].regulation_ref == "OJ L 100, p. 5 (2024-01-15)"       # modification regulation
        assert measures[1006].regulation_ref == ""                                  # unknown regulation

    def test_a_conflicting_duplicate_sid_is_refused(self, ref):
        with pytest.raises(ExtractError, match="1002"):
            parse_measures(payload("Measure", "conflict"), D, ref["types"], ref["expressions"], ref["regulations"])

    def test_an_unknown_measure_type_is_refused(self, ref):
        types = {k: v for k, v in ref["types"].items() if k != "552"}
        with pytest.raises(ExtractError, match="552"):
            parse_measures(payload("Measure"), D, types, ref["expressions"], ref["regulations"])


class TestExclusions:
    """Feature 003, FR-002, research R-03: each measure's EU excluded areas, sorted and once each."""

    def test_eu_excluded_areas_are_sorted_and_kept_once(self, measures):
        assert measures[1001].excluded_areas == ("US",)            # its national exclusion of SE-NAT is ignored
        assert measures[1006].excluded_areas == ("CN", "US")       # listed as US, CN and CN again

    def test_measures_without_exclusions_get_an_empty_tuple(self, measures):
        assert all(m.excluded_areas == () for sid, m in measures.items() if sid not in (1001, 1006))

    def test_the_snapshot_counts_the_measures_with_exclusions(self, tmp_path):
        assert sum(bool(m.excluded_areas) for m in snapshot(tmp_path).measures) == EXPECTED["measures_with_exclusions"]


class TestUnusableMeasures:
    def test_codes_held_only_as_national_records(self):
        assert national_only_codes(payload("GoodsNomenclature")) == frozenset({"7318155899"})

    def test_meursing_measures_and_measures_on_national_only_codes_are_dropped_and_counted(self, tmp_path):
        snap = snapshot(tmp_path)
        assert snap.dropped == {"Meursing table, measure types 672, 673, 674": 3, "on a code held only as a national record": 1}
        assert not {1017, 1018, 1019, 1020} & {m.sid for m in snap.measures}
        assert snap.header.measure_records == len(snap.measures) == 12


class TestReconciliation:
    def test_cn8_codes_come_from_the_cn_lines_of_the_chunk_texts(self):
        idx = NomenclatureIndex([
            NomenclatureChunk(id="hs:7318.15", text="Chapter 73 — Articles\nSubheading 7318.15 — Other\nCN 7318 15 58 — With a head\n"
                                                    "CN 7318 15 95 — Other\nSee also CN 7318 15 99", metadata={"subheading": "7318.15"}),
            NomenclatureChunk(id="hs:9617.00", text="Subheading 9617.00 — Vacuum flasks\nCN 9617 00 00 — Vacuum flasks",
                              metadata={"subheading": "9617.00"}),
        ])
        assert idx.cn8_codes() == CN2026

    def test_only_cn8_prefixes_of_declarable_codes_are_compared(self, code_list):
        # parents 7300000000, 7318000000, 7318150000 and 7318159900 lie outside CN2026 too but are never counted
        assert reconcile(code_list, CN2026) == [("73181599", "7318159910")]

    def test_the_count_goes_into_the_snapshot_record_and_the_log(self, tmp_path):
        snap = snapshot(tmp_path)
        h = snap.header
        assert (h.schema, h.snapshot_date, h.batch_id, h.export_id) == (2, "2026-10-01", BATCH, BATCH)
        assert h.source_files == tuple(name(o) for o in OBJECTS)
        assert (h.goods_records, h.measure_records, h.cn8_mismatches) == (11, 12, 1)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", h.loaded_at)
        assert snap.log_path == tmp_path / "taric-cn8-mismatches-2026-10-01.txt"
        assert snap.log_path.read_text(encoding="utf-8") == "73181599 7318159910\n"

    def test_a_file_that_cannot_be_unpacked_is_named(self, tmp_path):
        files = tuple(ExtractFile(o, BATCH, D, Path(name(o))) for o in OBJECTS)
        payloads = {o: payload(o) for o in OBJECTS}
        payloads["MeasureType"] = (FIX / "xml" / "MeasureType.xml").read_bytes()
        with pytest.raises(ExtractError, match=re.escape(name("MeasureType"))):
            build_snapshot(ExtractSet(BATCH, D, files), payloads, CN2026, tmp_path)
