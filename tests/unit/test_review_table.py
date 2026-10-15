"""Review-table shaping and decision flow (FR-023, FR-024, FR-033, FR-034)."""
import pytest

from agent.schemas import (
    Candidate,
    ChosenHow,
    Classification,
    CreatedBy,
    Decision,
    DecisionRoute,
    DescriptionCheck,
    Flag,
    FlagKind,
    LineStatus,
    ParsedLine,
    RuleSource,
)
from agent.store import LockedError, UnknownCodeError
from ui.review import FILTERS, FLAG_LABEL, ROUTE_LABEL, filter_rows, table_rows

pytestmark = pytest.mark.unit


@pytest.fixture
def populated(memory_store):
    s = memory_store
    s.add_lines([ParsedLine(text_zh="配件", text_en="Parts", qty="14 CTN", source_ref="r4"),
                 ParsedLine(text_zh="LED台灯", text_en="LED desk lamp", qty="40 CTN", source_ref="r5"),
                 ParsedLine(text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask", qty="60 CTN", source_ref="r6"),
                 ParsedLine(text_zh="礼品", text_en="Gift", qty="6 CTN", source_ref="r7")], CreatedBy.file)

    def cands(*cc):
        return [Candidate(code=c, subheading_text="t", confidence=k, rationale="r") for c, k in cc]

    s.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.vague, rule_source=RuleSource.ics2_unacceptable, matched_term="parts", ask_for=["material"])))
    s.update_classification(1, Classification(line_no=1, candidates=cands(("8452.90", 31), ("8487.90", 19))))
    s.update_check(2, DescriptionCheck(line_no=2, flag=Flag(kind=FlagKind.ok)))
    s.update_classification(2, Classification(line_no=2, candidates=cands(("9405.21", 72), ("9403.60", 20))))
    s.update_check(3, DescriptionCheck(line_no=3, flag=Flag(kind=FlagKind.ok)))
    s.update_classification(3, Classification(line_no=3, candidates=cands(("9617.00", 96))))
    s.update_check(4, DescriptionCheck(line_no=4, flag=Flag(kind=FlagKind.stop_word, rule_source=RuleSource.firm_stop_words, matched_term="gift", ask_for=["material"], pure_stop_word=True)))
    return s


class TestShaping:
    def test_rows_are_needs_action_first_then_line_order(self, populated):
        rows = table_rows(populated)
        assert [r["line_no"] for r in rows] == [1, 2, 4, 3]
        assert rows[0]["flag"] == FLAG_LABEL["vague"] and rows[0]["route"] == ROUTE_LABEL["ask_shipper"]
        assert rows[-1]["route"] == ROUTE_LABEL["auto_accept"] and rows[-1]["hs6"] == "9617.00"

    def test_confidence_is_a_0_1_float_for_the_progress_column(self, populated):
        rows = table_rows(populated)
        by_no = {r["line_no"]: r for r in rows}
        assert by_no[3]["confidence"] == pytest.approx(0.96)
        assert by_no[4]["confidence"] == 0.0 and by_no[4]["hs6"] == "—"

    def test_description_as_filed_combines_zh_en_with_qty_in_its_own_column(self, populated):
        row = next(r for r in table_rows(populated) if r["line_no"] == 1)
        assert "配件" in row["description"] and "Parts" in row["description"] and row["qty"] == "14 CTN"
        assert row["pending"] is False and row["version"] == 1

    def test_filters_with_counts(self, populated):
        rows = table_rows(populated)
        assert [r["line_no"] for r in filter_rows(rows, "Needs action")] == [1, 2, 4]
        assert [r["line_no"] for r in filter_rows(rows, "Accepted")] == [3]
        assert len(filter_rows(rows, "All")) == 4
        assert FILTERS == ["All", "Needs action", "Accepted"]


class TestDecisionFlow:
    def test_accept_with_top_other_and_typed_codes(self, populated):
        populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        assert populated.get_line(2).current.decision.chosen_how == ChosenHow.top
        populated.clear_decision(2)
        populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9403.60"))
        assert populated.get_line(2).current.decision.chosen_how == ChosenHow.other_candidate
        populated.clear_decision(2)
        populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="3924.10"))
        assert populated.get_line(2).current.decision.chosen_how == ChosenHow.typed
        row = next(r for r in table_rows(populated) if r["line_no"] == 2)
        assert row["route"] == ROUTE_LABEL["accepted"]

    def test_typed_unknown_code_is_rejected_and_nothing_changes(self, populated):
        before = [r["route"] for r in table_rows(populated)]
        with pytest.raises(UnknownCodeError):
            populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9999.99"))
        assert [r["route"] for r in table_rows(populated)] == before

    def test_accept_is_locked_while_flagged_with_a_reason(self, populated):
        line = populated.get_line(1)
        reason = populated.accept_lock_reason(line)
        assert reason and "flagged" in reason.lower()
        with pytest.raises(LockedError):
            populated.set_decision(1, Decision(route=DecisionRoute.accepted, decided_code="8452.90"))
        assert populated.accept_lock_reason(populated.get_line(2)) is None
