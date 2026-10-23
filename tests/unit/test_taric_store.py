"""TaricStore and lookup_taric (feature 002, US3, FR-017 to FR-021; feature 003: groups that contain the origin, area
names), against the hand-written tests/fixtures/taric/snapshot_small.jsonl."""
import dataclasses
import logging
import re
from datetime import date
from pathlib import Path

import pytest

from rag.taric import TaricFileError, TaricSnapshotInfo, TaricStore, open_taric_store

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SMALL = ROOT / "tests" / "fixtures" / "taric" / "snapshot_small.jsonl"


@pytest.fixture(scope="module")
def store():
    return TaricStore.from_jsonl(SMALL)


def sids(subdivision):
    return [m.sid for m in subdivision.measures]


class TestSubdivisions:
    def test_an_unsubdivided_cn8_gives_its_own_00_code(self, store):
        result = store.lookup_taric("73181595")
        assert [(s.code, s.description, s.valid_from, s.valid_to) for s in result] == [("7318159500", "", date(2007, 1, 1), None)]

    def test_a_subdivided_cn8_gives_its_declarable_children_in_code_order_never_its_00_code(self, store):
        result = store.lookup_taric("73181558")
        assert [(s.code, s.description, s.valid_to) for s in result] == [
            ("7318155810", "Self-locking bolts and nuts", None), ("7318155890", "Other", date(2027, 12, 31))]

    def test_an_unknown_cn8_gives_an_empty_list(self, store):
        assert store.lookup_taric("73181599") == []


class TestMeasures:
    def test_measures_are_inherited_along_the_parent_chain_with_the_code_they_are_recorded_on(self, store):
        first = store.lookup_taric("73181558")[0]
        assert [(m.sid, m.recorded_on) for m in first.measures] == [
            (3, "7318150000"), (10, "7318155800"), (5, "7318155810"), (4, "7318155800"), (1, "7300000000"), (2, "7318000000"),
            (9, "7318150000")]

    def test_china_and_the_us_each_get_their_own_their_groups_and_erga_omnes_measures(self, store):
        assert sids(store.lookup_taric("73181558", "CN")[0]) == [3, 10, 5, 4, 1, 2, 9]   # not the US preference 6
        assert sids(store.lookup_taric("73181558", "US")[0]) == [3, 6, 1, 2, 9]          # not CN's duties, not 4000's control

    def test_export_only_measures_are_never_returned_and_both_ways_measures_are(self, store):
        assert 7 not in sids(store.lookup_taric("73181595")[0])                   # export authorisation on the HS-6 parent
        assert sids(store.lookup_taric("73181558")[1]) == [3, 10, 8, 4, 1, 2, 9]   # 8 is a both-ways measure

    def test_anti_dumping_measures_carry_their_additional_codes(self, store):
        first = store.lookup_taric("73181558")[0]
        assert [(m.measure_type, m.additional_code, m.duty) for m in first.measures if m.measure_type == "552"] == [
            ("552", "C001", "22 %"), ("552", "C999", "85 %")]

    def test_measure_fields(self, store):
        m = next(m for m in store.lookup_taric("73181558")[0].measures if m.sid == 4)
        assert (m.sid, m.measure_type_label, m.geo_area, m.geo_area_name, m.regulation_id, m.regulation_ref, m.valid_from,
                m.valid_to) == (4, "Definitive anti-dumping duty", "CN", "China", "R2201910", "OJ L 36, p. 1 (2022-02-17)",
                                date(2022, 2, 18), date(2027, 2, 17))


class TestGroups:
    """Feature 003, US1: measures of every group that contains the origin, at any depth, each with its area's name."""

    def test_each_measure_keeps_its_own_area_and_carries_its_name(self, store):
        first = store.lookup_taric("73181558", "CN")[0]
        assert {m.sid: (m.geo_area, m.geo_area_name) for m in first.measures} == {
            3: ("1011", "ERGA OMNES"), 10: ("4000", "Fixture outer group"), 5: ("CN", "China"), 4: ("CN", "China"),
            1: ("1011", "ERGA OMNES"), 2: ("1011", "ERGA OMNES"), 9: ("1008", "All third countries")}

    def test_a_group_reached_directly_and_through_another_group_counts_once(self, store):
        found = sids(store.lookup_taric("73181558", "CN")[0])     # CN is in 4000 directly and through 4013, and lists 1011
        assert len(found) == len(set(found)) and found.count(10) == 1

    def test_the_us_gets_the_groups_it_is_in_and_not_the_others(self, store):
        found = sids(store.lookup_taric("73181558", "US")[0])
        assert 9 in found and 10 not in found

    def test_an_origin_without_an_area_record_gets_its_own_and_erga_omnes_measures(self, store):
        assert sids(store.lookup_taric("73181558", "JP")[0]) == [3, 1, 2]

    def test_a_measure_of_an_area_without_a_name_carries_an_empty_name(self, store):
        m = next(m for m in store.lookup_taric("73181558", "ZZ")[0].measures if m.sid == 11)
        assert (m.geo_area, m.geo_area_name) == ("9999", "")

    def test_memberships_that_form_a_cycle_end_the_walk(self, store):
        assert 12 in sids(store.lookup_taric("73181558", "ZZ")[0])     # 9002, reached from ZZ through 9001


class TestExclusions:
    """Feature 003, US2, FR-006: a measure is left out when any of its excluded areas applies to the origin. The
    measures 13-16 sit on 7318159500."""

    def test_an_erga_omnes_measure_excluding_china_is_left_out_for_china_only(self, store):
        assert 13 not in sids(store.lookup_taric("73181595", "CN")[0])
        assert 13 in sids(store.lookup_taric("73181595", "US")[0])

    def test_a_measure_excluding_a_group_that_contains_china_is_left_out(self, store):
        # the fixture-only case of spec US2 scenario 2 and SC-002: no such measure exists on the 2026-10-01 snapshot
        assert 14 not in sids(store.lookup_taric("73181595", "CN")[0])     # excludes 4013, which contains CN
        assert 14 in sids(store.lookup_taric("73181595", "US")[0])

    def test_a_group_measure_excluding_china_is_left_out_for_china(self, store):
        assert 15 not in sids(store.lookup_taric("73181595", "CN")[0])     # for 1008, excluding AR and CN
        assert 15 in sids(store.lookup_taric("73181595", "US")[0])

    def test_a_measure_excluding_an_area_outside_the_origins_set_is_still_returned(self, store):
        assert 16 in sids(store.lookup_taric("73181595", "CN")[0])         # excludes JP only
        assert 16 not in sids(store.lookup_taric("73181595", "JP")[0])

    def test_the_whole_result_for_china_and_the_us(self, store):
        assert sids(store.lookup_taric("73181595", "CN")[0]) == [3, 1, 2, 16, 9]
        assert sids(store.lookup_taric("73181595", "US")[0]) == [3, 15, 14, 13, 1, 2, 16, 9]


class TestStatisticMeasures:
    """Feature 003, US3, FR-007: measure type 566 stays in the file but is never returned (measures 17 and 18)."""

    @pytest.mark.parametrize("origin", ["CN", "US"])
    def test_type_566_is_never_returned(self, store, origin):
        assert not {17, 18} & set(sids(store.lookup_taric("73181595", origin)[0]))

    def test_the_snapshot_record_still_counts_them(self, store):
        assert store.snapshot.measure_records == 18


class TestInput:
    @pytest.mark.parametrize("cn8", ["7318 15 58", "7318.15.58", " 73181558 "])
    def test_spaces_and_dots_are_removed(self, store, cn8):
        assert store.lookup_taric(cn8) == store.lookup_taric("73181558")

    def test_the_origin_is_upper_cased(self, store):
        assert store.lookup_taric("73181558", "cn") == store.lookup_taric("73181558", "CN")

    @pytest.mark.parametrize("cn8, origin", [("1234", "CN"), ("73181558X", "CN"), ("731815580", "CN"), ("", "CN"),
                                             ("73181558", ""), ("73181558", "C-N")])
    def test_bad_input_raises_instead_of_answering_empty(self, store, cn8, origin):
        with pytest.raises(ValueError):
            store.lookup_taric(cn8, origin)


class TestReadOnly:
    def test_results_are_frozen_and_equal_across_calls(self, store):
        first = store.lookup_taric("73181558")
        assert first == store.lookup_taric("73181558")
        with pytest.raises(dataclasses.FrozenInstanceError):
            first[0].code = "0000000000"
        assert isinstance(first[0].measures, tuple)

    def test_snapshot_info(self, store):
        assert store.snapshot == TaricSnapshotInfo(snapshot_date=date(2026, 10, 1), batch_id="small",
                                                   loaded_at="2026-10-22T14:05:31Z", goods_records=7, measure_records=18,
                                                   cn8_mismatches=0)


class TestBadFiles:
    @pytest.mark.parametrize("change", [
        lambda lines: [lines[0].replace('"schema":2', '"schema":1')] + lines[1:],     # another schema
        lambda lines: lines[1:],                                                     # no snapshot record
        lambda lines: lines[:3] + ["{broken"] + lines[3:],                           # a malformed line
        lambda lines: [],                                                            # empty file
    ])
    def test_a_bad_file_raises(self, tmp_path, change):
        path = tmp_path / "taric.jsonl"
        path.write_text("".join(line + "\n" for line in change(SMALL.read_text(encoding="utf-8").splitlines())), encoding="utf-8")
        with pytest.raises(TaricFileError):
            TaricStore.from_jsonl(path)

    @pytest.mark.parametrize("bad, reason", [
        ('["measure", 1]', "fields"),                                  # wrong number of elements
        ('["no_such_kind", 1, 2]', "no known record kind"),
        ('{"kind": "measure", "sid": 1}', "only the snapshot record is a JSON object"),
        (None, "a second snapshot record"),                            # None: the snapshot line again
    ])
    def test_a_bad_line_in_the_middle_names_its_line_number(self, tmp_path, bad, reason):
        """Regression test for feature 003's read path (T025): it passed before T026 rewrote the reader and must still."""
        lines = SMALL.read_text(encoding="utf-8").splitlines()
        path = tmp_path / "taric.jsonl"
        path.write_text("".join(line + "\n" for line in lines[:5] + [bad or lines[0]] + lines[5:]), encoding="utf-8")
        with pytest.raises(TaricFileError, match=rf"^line 6: .*{reason}"):
            TaricStore.from_jsonl(path)

    def test_an_absent_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            TaricStore.from_jsonl(tmp_path / "taric.jsonl")


class TestOpenForTheApp:
    def test_a_valid_file_gives_a_store(self):
        assert isinstance(open_taric_store(SMALL), TaricStore)

    @pytest.mark.parametrize("content", [None, b"{broken\n", b"\xff\xfe not utf-8\n",
                                         SMALL.read_bytes().replace(b'"schema":2', b'"schema":1')])
    def test_an_absent_unreadable_or_other_schema_file_gives_none_and_logs_why(self, tmp_path, caplog, content):
        path = tmp_path / "taric.jsonl"
        if content is not None:
            path.write_bytes(content)
        with caplog.at_level(logging.WARNING, logger="rag.taric"):
            assert open_taric_store(path) is None
        assert "TARIC not loaded" in caplog.text


def test_the_lookup_is_not_connected_to_the_assistant_or_the_screen():
    """FR-021: Spec 2 connects the lookup; this feature must not."""
    for pkg in ("agent", "tools"):
        for path in (ROOT / pkg).rglob("*.py"):
            assert not re.search(r"\brag\.taric|from rag import [^\n]*\btaric", path.read_text(encoding="utf-8")), path
    for path in (ROOT / "app.py", *(ROOT / "ui").rglob("*.py")):
        assert "lookup_taric" not in path.read_text(encoding="utf-8"), path
