"""Line store: versions, lock, decided code, threshold recompute, counts, audit (FR-020 … FR-025)."""
import pytest

from agent.schemas import (
    Actor,
    Candidate,
    ChangeKind,
    ChosenHow,
    Classification,
    CreatedBy,
    Decision,
    DecisionRoute,
    DescriptionCheck,
    Flag,
    FlagKind,
    LineStatus,
    LineVersion,
    ParsedLine,
    Route,
    RuleSource,
    Usage,
)
from agent.store import LineStore, LockedError, UnknownCodeError

pytestmark = pytest.mark.unit


def _parsed(n, zh, en):
    return ParsedLine(line_no=n, text_zh=zh, text_en=en, source_ref=f"row {n}")


def _check(n, kind, source=None, term=None, pure=False):
    flag = Flag(kind=kind, rule_source=source, matched_term=term, reason="r",
                ask_for=[] if kind == FlagKind.ok else ["material", "product_name", "use"], pure_stop_word=pure)
    return DescriptionCheck(line_no=n, flag=flag, status=LineStatus.checked)


def _classify(n, codes_confs, failed=False):
    cands = [Candidate(code=c, subheading_text="t", confidence=k, rationale="r") for c, k in codes_confs]
    return Classification(line_no=n, candidates=cands, no_valid_candidate=not cands, retrieval_trace=None,
                          sources=[], status=LineStatus.failed if failed else LineStatus.checked,
                          error_reason="boom" if failed else None)


def _checked_line(store, n, kind, codes_confs, source=RuleSource.ics2_unacceptable):
    store.update_check(n, _check(n, kind, source if kind != FlagKind.ok else None, "parts" if kind != FlagKind.ok else None))
    store.update_classification(n, _classify(n, codes_confs))


@pytest.fixture
def populated(memory_store):
    s = memory_store
    s.add_lines([_parsed(1, "不锈钢保温杯", "Stainless steel vacuum flask"),   # A: ok 88 -> auto
                 _parsed(2, "LED台灯", "LED desk lamp"),                       # B: ok 72 -> review
                 _parsed(3, "家具", "Furniture"),                              # C: vague 58 -> review
                 _parsed(4, "礼品", "Gift"),                                   # E: stop -> ask
                 _parsed(5, "塑料玩具车", "Plastic toy cars")], CreatedBy.paste)  # D: ok 90, clerk decides review
    _checked_line(s, 1, FlagKind.ok, [("9617.00", 88)])
    _checked_line(s, 2, FlagKind.ok, [("9405.21", 72)])
    _checked_line(s, 3, FlagKind.vague, [("9403.60", 58)])
    s.update_check(4, _check(4, FlagKind.stop_word, RuleSource.firm_stop_words, "gift", pure=True))
    _checked_line(s, 5, FlagKind.ok, [("9503.00", 90)])
    s.set_decision(5, Decision(route=DecisionRoute.review))
    return s


class TestShipmentAndLines:
    def test_new_shipment_resets_usage(self, memory_store):
        memory_store.add_usage(Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost_usd=0.5, cost_eur=0.46, calls=1))
        assert memory_store.shipment.usage.total_tokens == 15
        memory_store.new_shipment(reference="TEST-002", threshold=85)
        assert memory_store.shipment.usage.total_tokens == 0
        assert memory_store.shipment.usage.cost_eur == 0

    def test_add_lines_creates_v1_with_created_by_and_consecutive_numbers(self, memory_store):
        lines = memory_store.add_lines([_parsed(1, "a", "b"), _parsed(2, "c", "d")], CreatedBy.paste)
        assert [l.line_no for l in lines] == [1, 2]
        assert lines[0].versions[0].version_no == 1
        assert lines[0].versions[0].created_by == CreatedBy.paste
        assert lines[0].current.status == LineStatus.pending

    def test_add_version_appends_consecutively_and_never_edits_earlier(self, populated):
        line = populated.get_line(1)
        first_text = line.versions[0].text_en
        v = LineVersion(version_no=1, created_by=CreatedBy.shipper_reply, text_zh="", text_en="steel vacuum flask 500 ml")
        populated.add_version(1, v)
        assert [x.version_no for x in populated.get_line(1).versions] == [1, 2]
        assert populated.get_line(1).versions[0].text_en == first_text
        assert populated.get_line(1).current.text_en == "steel vacuum flask 500 ml"


class TestDecisions:
    def test_flagged_line_cannot_be_accepted(self, populated):
        with pytest.raises(LockedError):
            populated.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9403.60"))
        with pytest.raises(LockedError):
            populated.set_decision(4, Decision(route=DecisionRoute.accepted, decided_code="9617.00"))

    def test_unknown_decided_code_is_rejected_and_nothing_changes(self, populated):
        before = populated.effective_route(populated.get_line(2))
        with pytest.raises(UnknownCodeError):
            populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9999.99"))
        assert populated.effective_route(populated.get_line(2)) == before
        assert populated.get_line(2).current.decision is None

    def test_accepting_an_ok_line_records_code_and_how_it_was_chosen(self, populated):
        populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        line = populated.get_line(2)
        assert populated.effective_route(line) == "accepted"
        assert line.current.decision.chosen_how == ChosenHow.top
        populated.set_decision(1, Decision(route=DecisionRoute.accepted, decided_code="3924.10"))
        assert populated.get_line(1).current.decision.chosen_how == ChosenHow.typed

    def test_clerk_can_send_a_line_to_ask_shipper(self, populated):
        populated.set_decision(2, Decision(route=DecisionRoute.ask_shipper))
        assert populated.effective_route(populated.get_line(2)) == Route.ask_shipper


class TestThreshold:
    def test_recompute_touches_only_undecided_ok_lines(self, populated):
        populated.set_threshold(90)
        assert populated.get_line(1).current.computed_route == Route.review      # 88 < 90
        assert populated.get_line(3).current.computed_route == Route.review      # vague unchanged
        assert populated.effective_route(populated.get_line(5)) == Route.review  # clerk decision kept
        assert not any(r.change == ChangeKind.threshold_recomputed and r.line_no == 5 for r in populated.shipment.audit)
        populated.set_threshold(60)
        assert populated.get_line(1).current.computed_route == Route.auto_accept
        assert populated.get_line(2).current.computed_route == Route.auto_accept  # 72 >= 60
        assert populated.get_line(3).current.computed_route == Route.review

    @pytest.mark.parametrize("bad", [59, 100])
    def test_threshold_range_enforced(self, populated, bad):
        with pytest.raises(ValueError):
            populated.set_threshold(bad)

    def test_set_hybrid(self, populated):
        populated.set_hybrid(False)
        assert populated.shipment.hybrid_search is False


class TestCountsAndDerived:
    def test_counts_and_needs_action(self, populated):
        c = populated.counts()
        assert c["auto_accept"] == 1 and c["review"] == 3 and c["ask_shipper"] == 1
        assert c["needs_action"] == 4 and c["accepted"] == 1
        assert populated.needs_action(populated.get_line(2)) is True
        assert populated.needs_action(populated.get_line(1)) is False

    def test_ready_to_accept_after_a_previously_flagged_line_becomes_ok(self, populated):
        v2 = LineVersion(version_no=2, created_by=CreatedBy.shipper_reply, text_zh="", text_en="wooden dining chairs",
                         flag=Flag(kind=FlagKind.ok), status=LineStatus.checked,
                         candidates=[Candidate(code="9401.69", subheading_text="t", confidence=96, rationale="r")])
        populated.add_version(3, v2)
        line = populated.get_line(3)
        assert line.ever_flagged is True
        assert line.current.computed_route == Route.review
        assert "ready to accept" in line.current.route_reason.lower()
        assert populated.ready_to_accept(line) is True
        populated.set_decision(3, Decision(route=DecisionRoute.accepted, decided_code="9401.69"))
        assert populated.effective_route(populated.get_line(3)) == "accepted"
        assert populated.ready_to_accept(populated.get_line(3)) is False

    def test_finalize_check_fails_pending_lines_and_returns_counts(self, memory_store):
        memory_store.add_lines([_parsed(1, "a", "b"), _parsed(2, "c", "d")], CreatedBy.paste)
        _checked_line(memory_store, 1, FlagKind.ok, [("9617.00", 90)])
        counts = memory_store.finalize_check()
        line2 = memory_store.get_line(2)
        assert line2.current.status == LineStatus.failed
        assert line2.current.computed_route == Route.review
        assert counts["needs_action"] == 1 and counts["auto_accept"] == 1

    def test_failed_classification_routes_to_review_with_reason(self, memory_store):
        memory_store.add_lines([_parsed(1, "a", "b")], CreatedBy.paste)
        memory_store.update_check(1, _check(1, FlagKind.ok))
        memory_store.update_classification(1, _classify(1, [], failed=True))
        v = memory_store.get_line(1).current
        assert v.status == LineStatus.failed and v.error_reason == "boom"
        assert v.computed_route == Route.review


class TestAuditAndRegistries:
    def test_every_mutation_is_recorded_with_an_actor(self, populated):
        populated.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
        populated.set_threshold(90)
        kinds = {r.change for r in populated.shipment.audit}
        actors = {r.actor for r in populated.shipment.audit}
        assert {ChangeKind.route_computed, ChangeKind.clerk_decision, ChangeKind.code_decided, ChangeKind.threshold_recomputed} <= kinds
        assert {Actor.routing_rule, Actor.clerk, Actor.threshold_change} <= actors
        assert all(r.at is not None and r.line_no >= 1 for r in populated.shipment.audit)

    def test_file_and_reply_registries(self, memory_store):
        f = memory_store.register_file(b"abc", "list.xlsx")
        r1 = memory_store.register_reply("line 1 is steel bobbin cases")
        r2 = memory_store.register_reply("塑料杯")
        assert memory_store.get_file(f) == (b"abc", "list.xlsx")
        assert memory_store.get_reply(r1) == "line 1 is steel bobbin cases"
        assert memory_store.get_reply(r2) == "塑料杯" and r1 != r2
