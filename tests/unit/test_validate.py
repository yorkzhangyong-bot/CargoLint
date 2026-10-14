"""Code-existence and schema validators (FR-013, FR-044) and the Decision invariant (FR-023)."""
import pytest
from pydantic import ValidationError

from agent.routing import SchemaError, validate_classification, validate_code
from agent.schemas import Decision, DecisionRoute, RankOut

pytestmark = pytest.mark.unit


class TestValidateCode:
    def test_existing_code_passes(self, small_index):
        assert validate_code("9617.00", small_index) is True

    @pytest.mark.parametrize("bad", ["9617.0", "961700", "9617-00", "96170.0", "", "ABCD.EF", "9617.00 "])
    def test_malformed_codes_fail(self, bad, small_index):
        assert validate_code(bad, small_index) is False

    def test_well_formed_but_unknown_code_fails(self, small_index):
        assert validate_code("9999.99", small_index) is False


def _raw(candidates, **extra):
    d = {"candidates": candidates}
    d.update(extra)
    return d


class TestValidateClassification:
    def test_valid_output_is_parsed(self):
        out = validate_classification(_raw([
            {"code": "9617.00", "confidence": 96, "rationale": "vacuum flask", "history_only": False},
            {"code": "3924.10", "confidence": 3, "rationale": "tableware"},
        ]))
        assert isinstance(out, RankOut)
        assert out.candidates[0].code == "9617.00"
        assert out.candidates[1].history_only is False

    def test_more_than_three_candidates_rejected(self):
        with pytest.raises(SchemaError):
            validate_classification(_raw([{"code": f"96{i:02d}.00", "confidence": 10, "rationale": "r"} for i in range(4)]))

    @pytest.mark.parametrize("conf", [-1, 101, "high", 50.5, None])
    def test_confidence_must_be_int_0_100(self, conf):
        with pytest.raises(SchemaError):
            validate_classification(_raw([{"code": "9617.00", "confidence": conf, "rationale": "r"}]))

    @pytest.mark.parametrize("code", ["961700", "9617", "9617.0", "x"])
    def test_code_format_enforced(self, code):
        with pytest.raises(SchemaError):
            validate_classification(_raw([{"code": code, "confidence": 50, "rationale": "r"}]))

    def test_empty_rationale_rejected(self):
        with pytest.raises(SchemaError):
            validate_classification(_raw([{"code": "9617.00", "confidence": 50, "rationale": ""}]))

    def test_unknown_fields_are_stripped_not_trusted(self):
        out = validate_classification(_raw([{"code": "9617.00", "confidence": 50, "rationale": "r"}], route="auto_accept", decided=True))
        assert not hasattr(out, "route")
        assert out.model_dump().get("route") is None

    def test_garbage_is_a_schema_error(self):
        with pytest.raises(SchemaError):
            validate_classification({"garbage": True, "candidates": "not-a-list"})

    def test_empty_candidate_list_is_valid(self):
        assert validate_classification(_raw([])).candidates == []


class TestDecisionInvariant:
    def test_accepted_requires_decided_code(self):
        with pytest.raises(ValidationError):
            Decision(route=DecisionRoute.accepted, decided_code=None)

    def test_accepted_with_code_is_valid(self):
        d = Decision(route=DecisionRoute.accepted, decided_code="9617.00")
        assert d.decided_code == "9617.00"

    def test_review_without_code_is_valid(self):
        assert Decision(route=DecisionRoute.review).decided_code is None
