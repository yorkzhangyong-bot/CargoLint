"""Feature 013: the release settings and the freshness limits (spec FR-014, FR-020; data-model §6, §7). A pin of the
wrong shape and an invalid ruling count are refused when the settings are read."""
from __future__ import annotations

import pytest

from agent.config import EBTI_STALE_DAYS, TARIC_STALE_DAYS, load_settings, release_name_ok

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
