"""Feature 013: the release settings and the freshness limits (spec FR-014, FR-020; data-model §6, §7). A pin of the
wrong shape and an invalid ruling count are refused when the settings are read. Feature 014a: the chapter setting
(spec FR-006), refused the same way when it is neither `all` nor a list of chapters."""
from __future__ import annotations

import pytest

from agent.config import EBTI_STALE_DAYS, TARIC_STALE_DAYS, load_settings, parse_chapter_setting, release_name_ok

pytestmark = pytest.mark.unit


def test_the_release_settings_are_empty_by_default_and_the_bound_is_5000():
    s = load_settings({})
    assert (s.release_repo, s.ebti_release, s.taric_release, s.ebti_rulings) == ("", "", "", "5000")


def test_the_release_settings_are_read_from_the_environment():
    s = load_settings({"CARGOLINT_RELEASE_REPO": " owner/name ", "CARGOLINT_EBTI_RELEASE": "ebti-2026-11-01",
                       "CARGOLINT_TARIC_RELEASE": " taric-2026-11-02 ", "CARGOLINT_EBTI_RULINGS": " 12000 "})
    assert (s.release_repo, s.ebti_release, s.taric_release, s.ebti_rulings) == ("owner/name", "ebti-2026-11-01",
                                                                                 "taric-2026-11-02", "12000")


@pytest.mark.parametrize("value, kept", [("all", "all"), (" ALL ", "all"), ("1", "1"), ("74000", "74000")])
def test_a_ruling_count_is_a_positive_integer_or_all(value, kept):
    assert load_settings({"CARGOLINT_EBTI_RULINGS": value}).ebti_rulings == kept


@pytest.mark.parametrize("value", ["0", "many", "-5", "5000.0", "5,000", "none"])
def test_an_invalid_ruling_count_is_refused(value):
    with pytest.raises(ValueError, match="CARGOLINT_EBTI_RULINGS"):
        load_settings({"CARGOLINT_EBTI_RULINGS": value})


@pytest.mark.parametrize("variable, value", [
    ("CARGOLINT_EBTI_RELEASE", "ebti-latest"),
    ("CARGOLINT_TARIC_RELEASE", "taric-2026-13-01"),            # no such month
    ("CARGOLINT_TARIC_RELEASE", "ebti-2026-11-01"),             # an EBTI name in the TARIC pin
    ("CARGOLINT_EBTI_RELEASE", "demo-store-v1"),                # no kind: never a pin
    ("CARGOLINT_EBTI_RELEASE", "ebti-2026-11-01.zip"),
])
def test_a_pin_of_the_wrong_shape_is_refused(variable, value):
    with pytest.raises(ValueError, match=variable):
        load_settings({variable: value})


def test_release_name_ok():
    assert release_name_ok("ebti-2026-11-01") and release_name_ok("taric-2026-11-02", "taric")
    assert not release_name_ok("taric-2026-11-02", "ebti") and not release_name_ok("ebti-2026-02-30")
    assert not release_name_ok("") and not release_name_ok("demo-store-v1")


def test_the_freshness_limits():
    assert (TARIC_STALE_DAYS, EBTI_STALE_DAYS) == (40, 45)


# --------------------------------------------------------------------------- feature 014a: the chapter setting
# 014a/FR-006
@pytest.mark.parametrize("env", [{}, {"CARGOLINT_EBTI_CHAPTERS": ""}, {"CARGOLINT_EBTI_CHAPTERS": "  "}])
def test_every_chapter_by_default(env):
    assert load_settings(env).ebti_chapters == "all"            # an empty value reads as unset


@pytest.mark.parametrize("value", ["all", "ALL", "All", " all "])
def test_all_in_any_case_is_every_chapter(value):
    assert load_settings({"CARGOLINT_EBTI_CHAPTERS": value}).ebti_chapters == "all"   # lower-cased
    assert parse_chapter_setting(value) is None


@pytest.mark.parametrize("value, chapters", [
    ("27,34,38", {"27", "34", "38"}),
    ("61-64", {"61", "62", "63", "64"}),
    ("1", {"01"}),                                              # a one-digit chapter is padded
    (" 27 , 61-62 ", {"27", "61", "62"}),                       # spaces around items
    ("39,42,61-64,73,84,85,94,95,96", {"39", "42", "61", "62", "63", "64", "73", "84", "85", "94", "95", "96"}),
    ("99,01-02", {"01", "02", "99"}),
])
def test_a_chapter_list_gives_two_digit_chapters(value, chapters):
    assert parse_chapter_setting(value) == frozenset(chapters)
    assert load_settings({"CARGOLINT_EBTI_CHAPTERS": value}).ebti_chapters == value.strip().lower()


@pytest.mark.parametrize("value", ["84,abc", "100", "00", "64-61", "27,,34", ",", "27-", "3a", "1-100", "all,27"])
def test_any_other_chapter_value_is_refused(value):
    with pytest.raises(ValueError):
        parse_chapter_setting(value)
    with pytest.raises(ValueError, match="CARGOLINT_EBTI_CHAPTERS"):
        load_settings({"CARGOLINT_EBTI_CHAPTERS": value})


# --------------------------------------------------------------------------- feature 014a: the customs-wording switch
# 014a/FR-024, 014a/FR-026, 014a/SC-006: off by default; any other value refused
@pytest.mark.parametrize("env, on", [({}, False), ({"CARGOLINT_CUSTOMS_WORDING": ""}, False),
                                     ({"CARGOLINT_CUSTOMS_WORDING": "off"}, False), ({"CARGOLINT_CUSTOMS_WORDING": "OFF"}, False),
                                     ({"CARGOLINT_CUSTOMS_WORDING": "on"}, True), ({"CARGOLINT_CUSTOMS_WORDING": " On "}, True)])
def test_the_customs_wording_switch_is_off_by_default(env, on):
    assert load_settings(env).customs_wording is on


@pytest.mark.parametrize("value", ["yes", "true", "1", "enabled"])
def test_any_other_customs_wording_value_is_refused(value):
    with pytest.raises(ValueError, match="CARGOLINT_CUSTOMS_WORDING"):
        load_settings({"CARGOLINT_CUSTOMS_WORDING": value})
