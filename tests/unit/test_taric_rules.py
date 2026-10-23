"""The TARIC rules (feature 004, research R-06): taric_rule, code_to_write and the confirm types, on subdivisions built
in the test (constitution Principle VII: guardrails are tested first, offline)."""
from datetime import date

import pytest

from agent.schemas import TaricRule
from rag.taric import TaricMeasure, TaricSubdivision

pytestmark = pytest.mark.unit

D = date(2026, 10, 1)


def measure(mtype, sid=1, area="CN", duty="", additional=None):
    return TaricMeasure(sid, "7318150000", mtype, f"type {mtype}", area, "China" if area == "CN" else "", additional, duty,
                        "R2201910", "OJ L 36, p. 1 (2022-02-17)", D, None)


def sub(code, *types):
    return TaricSubdivision(code, f"subdivision {code}", D, None, tuple(measure(t, i) for i, t in enumerate(types, 1)))


class TestTaricRule:
    def test_not_loaded_when_no_snapshot_is_loaded(self):
        from agent.taric_rules import taric_rule

        assert taric_rule([sub("7318159500", "103")], snapshot_loaded=False) == TaricRule.not_loaded
        assert taric_rule([], snapshot_loaded=False) == TaricRule.not_loaded

    def test_not_available_without_subdivisions(self):
        from agent.taric_rules import taric_rule

        assert taric_rule([], snapshot_loaded=True) == TaricRule.not_available

    def test_a_single_subdivision_is_auto_completed(self):
        from agent.taric_rules import taric_rule

        assert taric_rule([sub("7318159500", "103", "763")], True) == TaricRule.auto_completed

    def test_several_without_a_confirm_type_leave_the_choice(self):
        from agent.taric_rules import taric_rule

        assert taric_rule([sub("7318155810", "103"), sub("7318155890", "103", "142")], True) == TaricRule.choose

    @pytest.mark.parametrize("mtype", ["551", "552", "553", "554", "555", "570"])
    def test_a_confirm_type_needs_the_clerk_on_a_single_subdivision_or_one_of_several(self, mtype):
        from agent.taric_rules import taric_rule

        assert taric_rule([sub("7318156800", "103", mtype)], True) == TaricRule.trade_defence
        assert taric_rule([sub("7318155810", "103"), sub("7318155890", "103", mtype)], True) == TaricRule.trade_defence

    @pytest.mark.parametrize("mtype", ["561", "564", "565"])
    def test_other_trade_defence_types_do_not_stop_the_auto_completion(self, mtype):
        from agent.taric_rules import taric_rule

        assert taric_rule([sub("7318159500", "103", mtype)], True) == TaricRule.auto_completed


class TestCodeToWrite:
    def test_only_auto_completed_with_a_written_cn8_writes(self):
        from agent.taric_rules import code_to_write

        single = [sub("7318159500", "103")]
        assert code_to_write(TaricRule.auto_completed, single, cn8_written=True) == "7318159500"
        assert code_to_write(TaricRule.auto_completed, single, cn8_written=False) is None

    @pytest.mark.parametrize("rule", [TaricRule.choose, TaricRule.trade_defence, TaricRule.not_available, TaricRule.not_loaded])
    def test_every_other_rule_writes_nothing(self, rule):
        from agent.taric_rules import code_to_write

        assert code_to_write(rule, [sub("7318155810", "103"), sub("7318155890", "103")], cn8_written=True) is None
        assert code_to_write(rule, [sub("7318156800", "570")], cn8_written=True) is None

    def test_the_codes_of_a_stored_outcome_work_too(self):
        from agent.taric_rules import code_to_write

        assert code_to_write(TaricRule.auto_completed, ["7318159500"], cn8_written=True) == "7318159500"
        assert code_to_write(TaricRule.choose, ["7318155810", "7318155890"], cn8_written=True) is None


class TestConfirmTypes:
    def test_the_types_that_need_the_clerk(self):
        from agent.taric_rules import TRADE_DEFENCE_CONFIRM

        assert TRADE_DEFENCE_CONFIRM == {"551", "552", "553", "554", "555", "570"}

    def test_the_confirm_types_of_one_subdivision_sorted_once_each(self):
        from agent.taric_rules import confirm_types

        assert confirm_types(sub("7318155810", "103", "570", "552", "561", "552")) == ["552", "570"]
        assert confirm_types(sub("7318159500", "103", "564")) == []


# --------------------------------------------------------------------------- US3: measure groups, the view model and the links
SMALL = __import__("pathlib").Path(__file__).resolve().parents[1] / "fixtures" / "taric" / "snapshot_small.jsonl"
DUTY_TYPES = ["103", "105", "106", "107", "112", "115", "117", "119", "122", "123", "141", "142", "143", "145", "146", "147",
              "488", "489", "490", "651", "652", "653", "654", "695", "696"]


@pytest.fixture(scope="module")
def small_taric():
    from rag.taric import TaricStore

    return TaricStore.from_jsonl(SMALL)


class TestMeasureGroups:
    @pytest.mark.parametrize("mtype", DUTY_TYPES)
    def test_research_r07_duties(self, mtype):
        from agent.taric_rules import measure_group

        assert measure_group(mtype) == "duties"

    @pytest.mark.parametrize("mtype", ["551", "552", "553", "554", "555", "561", "564", "565", "570"])
    def test_trade_defence(self, mtype):
        from agent.taric_rules import measure_group

        assert measure_group(mtype) == "trade_defence"

    @pytest.mark.parametrize("mtype", ["109", "277", "410", "705", "775", "999"])
    def test_every_other_type_is_a_requirement(self, mtype):
        from agent.taric_rules import measure_group

        assert measure_group(mtype) == "requirements"


class TestTaricView:
    @pytest.mark.parametrize("cn8,origin", [("73181558", "CN"), ("73181558", "US"), ("73181595", "CN")])
    def test_the_groups_hold_exactly_the_measures_returned(self, small_taric, cn8, origin):
        from agent.taric_rules import GROUPS, measure_group, taric_view

        subs = small_taric.lookup_taric(cn8, origin)
        view = taric_view(subs, origin, small_taric.snapshot.snapshot_date, None)
        assert [s.code for s in view.subdivisions] == [s.code for s in subs]
        for sv, s in zip(view.subdivisions, subs):
            assert sv.description == s.description
            grouped = [m for g in GROUPS for m in sv.groups[g]]
            assert len(grouped) == len(s.measures) and {id(m) for m in grouped} == {id(m) for m in s.measures}   # same objects
            for g in GROUPS:                                       # each in exactly one group, in the returned order
                assert list(sv.groups[g]) == [m for m in s.measures if measure_group(m.measure_type) == g]

    def test_the_view_carries_the_origin_date_rule_and_suggestion(self, small_taric):
        from agent.schemas import TaricOutcome, TaricSuggestion
        from agent.taric_rules import taric_view

        subs = small_taric.lookup_taric("73181558", "CN")
        outcome = TaricOutcome(origin="CN", snapshot_date=D, rule=TaricRule.trade_defence, subdivisions=[s.code for s in subs],
                               trade_defence=[s.code for s in subs], trade_defence_types=["552"],
                               suggestion=TaricSuggestion(code="7318155810", confidence=88))
        view = taric_view(subs, "CN", D, outcome)
        assert (view.origin, view.snapshot_date, view.rule) == ("CN", D, TaricRule.trade_defence)
        assert (view.suggestion.code, view.suggestion.confidence) == ("7318155810", 88)
        assert [sv.trade_defence for sv in view.subdivisions] == [True, True]
        assert [sv.confirm_types for sv in view.subdivisions] == [("552",), ("552",)]

    def test_a_conditional_duty_text_passes_through_unchanged(self):
        from agent.taric_rules import taric_view

        text = "39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %"
        m = measure("552", duty=text, additional="C001")
        view = taric_view([TaricSubdivision("7318155810", "Self-locking", D, None, (m,))], "CN", D, None)
        [shown] = view.subdivisions[0].groups["trade_defence"]
        assert shown is m and shown.duty == text


class TestLinks:
    def test_the_eu_taric_consultation_link(self):
        from agent.taric_rules import eu_taric_url

        assert eu_taric_url("7318155810", "CN", date(2026, 10, 1)) == (
            "https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp?Lang=en&Taric=7318155810&Area=CN&SimDate=20261001"
            "&LangDescr=en")

    def test_the_ezt_online_start_page(self):
        from agent.taric_rules import EZT_ONLINE_URL

        assert EZT_ONLINE_URL == "https://auskunft.ezt-online.de/ezto/Welcome.do"
