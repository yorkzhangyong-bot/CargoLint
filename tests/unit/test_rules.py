"""Rule matching: whole-word English, CJK substring, firm precedence, pure stop-word, ask_for (FR-007 … FR-011)."""
import pytest

from agent.schemas import FlagKind, RuleSource
from rag.rules import RuleSet, check_rules, default_ask_for, is_pure_stop_word

pytestmark = pytest.mark.unit


class TestLoading:
    def test_lists_load_with_source_and_date(self, rules: RuleSet):
        assert rules.firm.source_doc and rules.firm.source_date
        assert len(rules.firm.entries) == 32
        names = {l.list for l in rules.ics2_lists}
        assert names == {"ics2_unacceptable", "ics2_stop_words"}
        assert all(l.source_doc and l.source_date for l in rules.ics2_lists)
        assert len(rules.aliases) > 10

    def test_knowledge_base_caption_facts(self, rules: RuleSet):
        facts = rules.caption_facts()
        assert facts["firm_terms"] == 32 and facts["ics2_terms"] > 20


class TestMatching:
    def test_english_whole_word_case_insensitive(self, rules):
        m = check_rules("", "Gift box", rules)
        assert m.kind == FlagKind.stop_word and m.rule_source == RuleSource.firm_stop_words and m.matched_term == "gift"
        assert check_rules("", "GIFT", rules).matched_term == "gift"

    def test_partial_word_does_not_match(self, rules):
        assert check_rules("", "gifted artisan lamps, brass", rules) is None
        assert check_rules("", "spare-tooth gears", rules) is None  # 'spare parts' needs both words

    def test_cjk_substring_match(self, rules):
        m = check_rules("礼品套装", "", rules)
        assert m.kind == FlagKind.stop_word and m.matched_term == "礼品"

    def test_firm_list_takes_precedence_over_ics2(self, rules):
        m = check_rules("", "gift", rules)  # 'gift' is on the firm list and both ICS2 lists
        assert m.rule_source == RuleSource.firm_stop_words and m.kind == FlagKind.stop_word

    def test_ics2_unacceptable_term_is_vague(self, rules):
        m = check_rules("", "Parts", rules)
        assert m.kind == FlagKind.vague and m.rule_source == RuleSource.ics2_unacceptable and m.matched_term == "parts"
        assert "v4.10" in m.source_doc

    def test_ics2_stop_word_only_term_is_vague_citing_that_list(self, rules):
        m = check_rules("", "said to contain electrical items", rules)
        assert m.kind == FlagKind.vague and m.rule_source == RuleSource.ics2_stop_words and m.matched_term == "said to contain"

    def test_chinese_alias_resolves_to_canonical_ics2_term(self, rules):
        m = check_rules("电子产品", "", rules)
        assert m.kind == FlagKind.vague and m.matched_term == "electronics" and m.rule_source == RuleSource.ics2_unacceptable
        assert check_rules("配件", "", rules).matched_term == "parts"

    def test_english_alias_resolves_to_canonical_term(self, rules):
        assert check_rules("", "Electronic products", rules).matched_term == "electronics"

    def test_clear_description_has_no_rule_match(self, rules):
        assert check_rules("不锈钢保温杯", "Stainless steel vacuum flask, 500 ml", rules) is None
        assert check_rules("纯棉针织T恤", "Cotton T-shirts, knitted", rules) is None


class TestPureStopWordAndAskFor:
    def test_pure_stop_word_when_nothing_else_remains(self, rules):
        m = check_rules("礼品", "Gift", rules)
        assert is_pure_stop_word("礼品", "Gift", m, rules) is True

    def test_not_pure_when_real_product_information_remains(self, rules):
        m = check_rules("", "gift box, stainless steel vacuum flask 500 ml", rules)
        assert m.kind == FlagKind.stop_word
        assert is_pure_stop_word("", "gift box, stainless steel vacuum flask 500 ml", m, rules) is False

    def test_ask_for_is_non_empty_for_every_flag_kind(self, rules):
        for kind in (FlagKind.vague, FlagKind.stop_word):
            assert default_ask_for(kind)
        assert default_ask_for(FlagKind.ok) == []
        m = check_rules("", "Parts", rules)
        assert m.ask_for and {"material", "product_name", "use"} <= set(m.ask_for)
