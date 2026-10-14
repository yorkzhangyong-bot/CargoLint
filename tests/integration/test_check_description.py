"""check_description: rules first, judgement second, ask_for, per-line isolation, order (FR-007 … FR-011, FR-048)."""
import pytest

from agent.llm import get_client
from agent.schemas import FlagKind, LineStatus, RuleSource
from tools.check_description import check_descriptions
from tools.common import LineText

pytestmark = pytest.mark.integration


def _line(n, zh, en):
    return LineText(line_no=n, text_zh=zh, text_en=en)


def test_firm_stop_word_matches_without_a_model_call(fake_llm, rules, memory_store):
    out = check_descriptions([_line(1, "礼品", "Gift")], rules=rules, client=get_client(), workers=2)
    assert out[0].status == LineStatus.checked
    assert out[0].flag.kind == FlagKind.stop_word and out[0].flag.rule_source == RuleSource.firm_stop_words
    assert out[0].flag.matched_term == "gift" and out[0].flag.pure_stop_word is True
    assert fake_llm.calls == []


def test_ics2_term_is_vague_without_a_model_call(fake_llm, rules):
    out = check_descriptions([_line(1, "配件", "Parts")], rules=rules, client=get_client(), workers=1)
    assert out[0].flag.kind == FlagKind.vague and out[0].flag.rule_source == RuleSource.ics2_unacceptable
    assert out[0].flag.matched_term == "parts" and out[0].flag.pure_stop_word is False
    assert fake_llm.calls == []


def test_clear_line_reaches_the_judgement_call_and_is_ok(fake_llm, rules):
    out = check_descriptions([_line(1, "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml")], rules=rules, client=get_client())
    assert [c["schema"] for c in fake_llm.calls] == ["JudgementOut"]
    assert out[0].flag.kind == FlagKind.ok and out[0].flag.ask_for == []
    prompt = fake_llm.calls[0]["user"]
    assert '<data line="1">不锈钢保温杯 / Stainless steel vacuum flask, 500 ml</data>' in prompt


def test_judgement_vague_cites_judgement_and_missing_items(fake_llm, rules):
    out = check_descriptions([_line(7, "", "mystery goods of some kind")], rules=rules, client=get_client())
    f = out[0].flag
    assert f.kind == FlagKind.vague and f.rule_source == RuleSource.judgement
    assert f.ask_for and {"material", "product_name", "use"} <= set(f.ask_for)


def test_ask_for_is_non_empty_for_every_flagged_line(fake_llm, rules):
    out = check_descriptions([_line(1, "礼品", "Gift"), _line(2, "配件", "Parts"), _line(3, "家具", "Furniture")], rules=rules, client=get_client())
    assert all(o.flag.ask_for for o in out)


def test_one_failing_line_does_not_stop_the_others_and_order_is_kept(fake_llm, rules):
    fake_llm.fail_on = {"LED台灯 USB供电 / LED desk lamp, USB powered"}
    lines = [_line(1, "不锈钢保温杯", "Stainless steel vacuum flask, 500 ml"),
             _line(2, "LED台灯 USB供电", "LED desk lamp, USB powered"),
             _line(3, "纯棉针织T恤", "Cotton T-shirts, knitted")]
    out = check_descriptions(lines, rules=rules, client=get_client(), workers=3)
    assert [o.line_no for o in out] == [1, 2, 3]
    assert out[1].status == LineStatus.failed and out[1].error_reason
    assert out[0].status == LineStatus.checked and out[2].status == LineStatus.checked
    assert out[0].flag.kind == FlagKind.ok and out[2].flag.kind == FlagKind.ok


def test_without_a_client_rules_still_run_and_clear_lines_are_ok(rules):
    out = check_descriptions([_line(1, "礼品", "Gift"), _line(2, "不锈钢保温杯", "Stainless steel vacuum flask")], rules=rules, client=None)
    assert out[0].flag.kind == FlagKind.stop_word
    assert out[1].flag.kind == FlagKind.ok and "rules only" in out[1].flag.reason
