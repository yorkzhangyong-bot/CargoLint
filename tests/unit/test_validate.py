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


# --------------------------------------------------------------------------- feature 004: CN-8 and TARIC-10 schemas
import agent.schemas as S  # noqa: E402  (module access keeps the feature 001 tests above collectable while these are red)
from datetime import date  # noqa: E402

TOY_OPTIONS = [("95030075", "Other toys and models, incorporating a motor > Of plastics"),
               ("95030095", "Other > Other > Of plastics")]


def _choice(**kw):
    base = dict(hs6="9503.00", options=TOY_OPTIONS, cn8=None, confidence=0, question="Ask the shipper for: a motor",
                deciding_attribute="whether the toy cars incorporate a motor")
    base.update(kw)
    return S.Cn8Choice(**base)


def _outcome(**kw):
    base = dict(origin="US", snapshot_date=date(2026, 10, 1), rule="choose", subdivisions=["7318155810", "7318155890"])
    base.update(kw)
    return S.TaricOutcome(**base)


class TestFinerCodeSchemas:
    """Data-model §1–§5 of feature 004. The HS-6 CODE_PATTERN is unchanged."""

    @pytest.mark.parametrize("cn8,taric10", [("73181558", "7318155810"), (None, None)])
    def test_candidate_carries_cn8_and_taric10(self, cn8, taric10):
        c = S.Candidate(code="7318.15", confidence=90, cn8=cn8, taric10=taric10)
        assert (c.cn8, c.taric10) == (cn8, taric10)

    def test_candidate_finer_codes_default_to_none(self):
        c = S.Candidate(code="7318.15", confidence=90)
        assert c.cn8 is None and c.taric10 is None

    @pytest.mark.parametrize("bad", ["7318.15", "7318155", "731815581", "73181558100", "7318155a"])
    def test_candidate_cn8_is_eight_digits(self, bad):
        with pytest.raises(ValidationError):
            S.Candidate(code="7318.15", confidence=90, cn8=bad)

    @pytest.mark.parametrize("bad", ["73181558", "731815581", "73181558100", "7318.15.58.10"])
    def test_candidate_taric10_is_ten_digits(self, bad):
        with pytest.raises(ValidationError):
            S.Candidate(code="7318.15", confidence=90, taric10=bad)

    def test_candidate_code_keeps_the_hs6_pattern(self):
        assert S.CODE_PATTERN == r"^\d{4}\.\d{2}$"
        with pytest.raises(ValidationError):
            S.Candidate(code="73181558", confidence=90)

    def test_decision_carries_decided_cn8_and_taric10(self):
        d = S.Decision(route=S.DecisionRoute.accepted, decided_code="7318.15", decided_cn8="73181558",
                       decided_taric10="7318155810")
        assert (d.decided_cn8, d.decided_taric10) == ("73181558", "7318155810")
        r = S.Decision(route=S.DecisionRoute.review)
        assert r.decided_cn8 is None and r.decided_taric10 is None

    @pytest.mark.parametrize("field,bad", [("decided_cn8", "7318.15"), ("decided_cn8", "7318155810"),
                                           ("decided_taric10", "73181558")])
    def test_decision_finer_codes_are_pattern_checked(self, field, bad):
        with pytest.raises(ValidationError):
            S.Decision(route=S.DecisionRoute.accepted, decided_code="7318.15", **{field: bad})

    def test_an_accepted_decision_still_needs_a_decided_code(self):
        with pytest.raises(ValidationError):
            S.Decision(route=S.DecisionRoute.accepted, decided_cn8="73181558")

    def test_cn8_out_parses_a_choice_and_a_question(self):
        out = S.Cn8Out.model_validate({"cn8": "87149110", "confidence": 95, "deciding_attribute": "frame or fork",
                                       "attribute_visible": True, "evidence": "bicycle frames", "rationale": "frames",
                                       "precedent": None, "route": "auto_accept"})
        assert out.cn8 == "87149110" and out.model_dump().get("route") is None
        q = S.Cn8Out.model_validate({"cn8": None, "confidence": 0, "deciding_attribute": "a motor",
                                     "attribute_visible": False, "evidence": "", "rationale": "not stated", "precedent": None})
        assert q.cn8 is None and q.attribute_visible is False

    @pytest.mark.parametrize("patch", [{"cn8": "8714.91"}, {"cn8": "871491100"}, {"confidence": 101}, {"confidence": -1},
                                       {"confidence": "95"}, {"attribute_visible": "maybe"}])
    def test_cn8_out_rejects_bad_fields(self, patch):
        raw = {"cn8": "87149110", "confidence": 95, "deciding_attribute": "frame", "attribute_visible": True,
               "evidence": "frames", "rationale": "frames", "precedent": None}
        raw.update(patch)
        with pytest.raises(ValidationError):
            S.Cn8Out.model_validate(raw)

    def test_subdivision_out(self):
        assert S.SubdivisionOut.model_validate({"code": "7318155810", "confidence": 70, "attribute_visible": True,
                                                "rationale": "self-locking"}).code == "7318155810"
        assert S.SubdivisionOut.model_validate({"code": None, "confidence": 0, "attribute_visible": False,
                                                "rationale": "not stated"}).code is None

    @pytest.mark.parametrize("patch", [{"code": "73181558"}, {"confidence": 101}, {"confidence": "70"}])
    def test_subdivision_out_rejects_bad_fields(self, patch):
        raw = {"code": "7318155810", "confidence": 70, "attribute_visible": True, "rationale": "x"}
        raw.update(patch)
        with pytest.raises(ValidationError):
            S.SubdivisionOut.model_validate(raw)

    def test_cn8_choice_fields(self):
        c = _choice(precedent=S.Precedent(reference="DEBTI1", code="9503007500"), written_by=None, error=None)
        assert c.options[0] == ("95030075", "Other toys and models, incorporating a motor > Of plastics")
        assert c.cn8 is None and c.precedent.reference == "DEBTI1"
        assert _choice(cn8="95030095", confidence=95, question=None, written_by="rule").written_by == S.WrittenBy.rule
        assert _choice(error="invalid output after one retry").error.startswith("invalid")

    @pytest.mark.parametrize("patch", [{"hs6": "9503"}, {"cn8": "9503.00.75"}, {"written_by": "machine"},
                                       {"confidence": 101}, {"options": [("9503007", "short code")]}])
    def test_cn8_choice_rejects_bad_fields(self, patch):
        with pytest.raises(ValidationError):
            _choice(**patch)

    def test_taric_outcome_fields(self):
        o = _outcome(suggestion={"code": "7318155810", "confidence": 70}, trade_defence=[], taric10=None)
        assert o.rule == S.TaricRule.choose and o.suggestion.code == "7318155810"
        assert o.written_by is None and o.question is None and o.suggestion_error is None
        assert {r.value for r in S.TaricRule} == {"auto_completed", "choose", "trade_defence", "not_available", "not_loaded"}

    @pytest.mark.parametrize("patch", [{"rule": "maybe"}, {"subdivisions": ["73181558"]}, {"taric10": "73181558"},
                                       {"suggestion": {"code": "73181558", "confidence": 70}},
                                       {"suggestion": {"code": "7318155810", "confidence": 101}}])
    def test_taric_outcome_rejects_bad_fields(self, patch):
        with pytest.raises(ValidationError):
            _outcome(**patch)

    def test_line_version_finer_fields_default_to_none(self):
        v = S.LineVersion()
        assert v.cn8 is None and v.taric is None

    def test_shipment_taric_origin(self):
        assert S.Shipment(id="s1").taric_origin == "CN"
        assert S.Shipment(id="s1", taric_origin="us").taric_origin == "US"

    @pytest.mark.parametrize("bad", ["C1", "CHN", "", "1"])
    def test_shipment_taric_origin_is_two_letters(self, bad):
        with pytest.raises(ValidationError):
            S.Shipment(id="s1", taric_origin=bad)

    def test_change_kinds(self):
        names = {k.value for k in S.ChangeKind}
        assert {"cn8_written", "cn8_question", "taric_written", "taric_pending", "taric_question",
                "taric_not_available"} <= names

    def test_cn8_input_and_result(self):
        inp = S.Cn8Input(lines=[{"line_no": 6, "text_zh": "塑料玩具车", "text_en": "Plastic toy cars", "hs6": "9503.00"}],
                         as_of=date(2026, 10, 23), threshold=85)
        assert inp.lines[0].hs6 == "9503.00" and inp.lines[0].extracted is None
        res = S.Cn8Result(line_no=6, choice=_choice(error="timed out"), status="failed", error_reason="timed out")
        assert res.status == "failed"

    @pytest.mark.parametrize("patch", [{"lines": [{"line_no": 1, "text_en": "x", "hs6": "9503"}]}, {"threshold": 50},
                                       {"threshold": 100}])
    def test_cn8_input_rejects_bad_fields(self, patch):
        raw = {"lines": [{"line_no": 1, "text_en": "x", "hs6": "9503.00"}], "as_of": date(2026, 10, 23), "threshold": 85}
        raw.update(patch)
        with pytest.raises(ValidationError):
            S.Cn8Input(**raw)

    def test_cn8_result_status_is_checked_or_failed(self):
        with pytest.raises(ValidationError):
            S.Cn8Result(line_no=6, choice=_choice(), status="pending")

    def test_taric_input_and_result(self):
        inp = S.TaricInput(lines=[{"line_no": 9, "text_en": "screws", "cn8": "73181558", "cn8_written": True}], origin="CN")
        assert inp.lines[0].cn8_written is True
        res = S.TaricResult(line_no=9, outcome=_outcome())
        assert res.outcome.rule == S.TaricRule.choose
        assert "status" not in S.TaricResult.model_fields   # suggestion failures are absorbed; the step never fails

    @pytest.mark.parametrize("patch", [{"lines": [{"line_no": 1, "text_en": "x", "cn8": "7318.15"}]}, {"origin": "C1"}])
    def test_taric_input_rejects_bad_fields(self, patch):
        raw = {"lines": [{"line_no": 1, "text_en": "x", "cn8": "73181558"}], "origin": "CN"}
        raw.update(patch)
        with pytest.raises(ValidationError):
            S.TaricInput(**raw)


class TestValidateCn8:
    """FR-002: a CN-8 is shown or written only when it is one of the decided HS-6's CN 2026 lines."""

    def test_a_code_among_the_options_passes(self):
        from agent.routing import validate_cn8

        assert validate_cn8("95030095", TOY_OPTIONS) is True

    @pytest.mark.parametrize("bad", ["9503.00", "9503009", "95039999", None, 95030095, ""])
    def test_anything_else_fails(self, bad):
        from agent.routing import validate_cn8

        assert validate_cn8(bad, TOY_OPTIONS) is False

    def test_no_options_means_no_valid_code(self):
        from agent.routing import validate_cn8

        assert validate_cn8("95030095", []) is False
