"""Rule matching: whole-word English, CJK substring, firm precedence, pure stop-word, ask_for (FR-007 … FR-011)."""
import pytest

from agent.config import RULES_DIR
from agent.schemas import FlagKind, RuleSource
from rag.rules import RuleSet, check_rules, default_ask_for, goods_name, is_pure_stop_word

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def shipped_rules() -> RuleSet:
    """The shipped lists: unlike the test excerpt, their ICS2 lists name cars, metal, box and steel on their own."""
    return RuleSet.load(RULES_DIR)


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
        m = check_rules("", "said to contain goods", rules)   # nothing but listed terms: see TestGoodsNameOnly
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


class TestGoodsNameOnly:
    """Feature 007: a listed term locks a line only when the goods name is nothing but listed terms, as ICS2 rejects a
    general term used as the description, not one that sits in a property or qualifies a named good. Several listed
    terms lock only when nothing else in the description says what the goods are: see TestSeveralListedTerms."""

    def test_a_stop_word_outside_the_goods_name_passes(self, rules):
        assert check_rules("", "T-shirts in various sizes", rules) is None
        assert check_rules("", "Silicone masks, used on various sizes of implants", rules) is None
        assert check_rules("", "Back-pack / Rucksack\nBag for carrying laptop / conveyance of goods or personal effects",
                           rules) is None

    def test_a_goods_name_of_nothing_but_stop_words_is_locked(self, rules):
        m = check_rules("", "various goods", rules)
        assert m.kind == FlagKind.stop_word and m.rule_source == RuleSource.firm_stop_words and m.matched_term == "various"
        assert check_rules("", "Parts and accessories, 20 ctns", rules).matched_term == "accessories"   # a count is no size

    def test_a_qualified_generic_term_passes(self, rules):
        assert check_rules("", "spare parts for pumps", rules) is None   # the model's judgement still follows

    def test_a_generic_term_alone_is_locked(self, rules):
        m = check_rules("", "parts", rules)
        assert m.kind == FlagKind.vague and m.matched_term == "parts"
        assert check_rules("", "Spare parts. These are polyethylene wear strips", rules) is not None   # its first phrase

    def test_an_empty_goods_name_keeps_a_stop_word_locked(self, rules):
        m = check_rules("", "available in various sizes", rules)
        assert m.kind == FlagKind.stop_word and m.matched_term == "various"

    def test_singular_and_plural_forms_are_alike(self, rules):
        assert check_rules("", "Toy", rules).matched_term == "toys"
        assert check_rules("", "Gifts", rules).matched_term == "gift"     # the list's own form, of the two it has

    def test_both_languages_make_one_goods_name(self, rules):
        assert check_rules("配件", "Parts", rules).matched_term == "parts"
        assert check_rules("各种货物", "", rules).matched_term == "各种"           # "various goods"
        assert check_rules("各种尺寸的硅胶面罩", "", rules) is None                # silicone masks of various sizes
        assert check_rules("礼品", "Stainless steel vacuum flask", rules) is None   # a gift, named

    def test_the_goods_name_ends_at_the_first_phrase_boundary(self):
        assert goods_name("Machine parts. These are polyethylene wear strips") == "Machine parts"
        assert goods_name("T-shirts in various sizes") == "T-shirts"
        assert goods_name("available in various sizes") == ""
        assert goods_name("In-ear headphones, black") == "In-ear headphones"
        assert goods_name("spare parts for pumps") == "spare parts for pumps"
        assert goods_name("Steel wire 2.5 mm, galvanised") == "Steel wire 2.5 mm"   # a decimal point is no full stop
        assert goods_name("礼品套装，不锈钢保温杯") == "礼品套装"


class TestSeveralListedTerms:
    """A goods name of two or more listed terms locks only when nothing else in the description says what the goods
    are, as the ICS2 guidance accepts a name that a material, property, size or use makes identifiable; a single listed
    term locks whatever follows it."""

    def test_a_material_size_or_use_after_the_goods_name_lets_the_line_pass(self, shipped_rules, rules):
        assert check_rules("", "Toy cars, plastic, no motor, pull-back, for children 3+", shipped_rules) is None
        assert check_rules("", "metal box, steel, 30x20 cm", shipped_rules) is None
        assert check_rules("", "Parts and accessories, steel", rules) is None

    def test_several_listed_terms_alone_are_locked(self, shipped_rules):
        assert check_rules("", "Toy cars", shipped_rules).matched_term == "cars"
        assert check_rules("", "metal box", shipped_rules).matched_term == "metal"

    def test_a_single_listed_term_is_still_locked(self, shipped_rules):
        m = check_rules("", "Various goods", shipped_rules)
        assert m.kind == FlagKind.stop_word and m.rule_source == RuleSource.firm_stop_words and m.matched_term == "various"
        m = check_rules("", "Parts", shipped_rules)
        assert m.kind == FlagKind.vague and m.rule_source == RuleSource.ics2_unacceptable and m.matched_term == "parts"


class TestEntriesWithoutLetters:
    """The shipped list data/rules/ics2_unacceptable_terms.json holds two entries left over from the PDF extraction,
    "1005" and a row of symbols ending in "12"; an entry with no Latin letter and no Chinese character is skipped, so a
    bare number is no listed term."""

    def test_a_bare_number_is_no_listed_term(self, shipped_rules):
        forms = {t.text for t in shipped_rules.terms} | {" ".join(t.words) for t in shipped_rules.terms}
        assert "12" not in forms and "1005" not in forms
        assert check_rules("", "Steel rods 12 mm", shipped_rules) is None
        assert check_rules("", "Bolts, 1005 pcs", shipped_rules) is None
        m = check_rules("", "Parts", shipped_rules)
        assert m is not None and m.matched_term == "parts"


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
