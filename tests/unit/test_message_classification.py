"""Chat message classification in code: reply vs pasted lines vs question (FR-001, FR-036)."""
import pytest

from agent.schemas import CreatedBy, ParsedLine

pytestmark = pytest.mark.unit


@pytest.fixture
def store_with_lines(memory_store):
    memory_store.add_lines([ParsedLine(text_zh="配件", text_en="Parts", source_ref="pasted line 1"),
                            ParsedLine(text_zh="LED台灯", text_en="LED desk lamp", source_ref="pasted line 2")], CreatedBy.paste)
    return memory_store


def test_after_a_check_only_replies_update_and_everything_else_is_answered(store_with_lines):
    from ui.chat import classify_message

    assert classify_message("line 1 is steel bobbin cases for industrial sewing machines", store_with_lines) == (
        "reply", (1, "line 1 is steel bobbin cases for industrial sewing machines"))
    assert classify_message("the material is stainless steel", store_with_lines) == ("reply", (None, "the material is stainless steel"))
    assert classify_message("please explain line 1", store_with_lines) == ("question", "please explain line 1")
    assert classify_message("line 2 looks wrong", store_with_lines) == ("question", "line 2 looks wrong")
    assert classify_message("stainless steel vacuum flask 500ml", store_with_lines) == ("question", "stainless steel vacuum flask 500ml")
    assert classify_message("status", store_with_lines) == ("question", "status")


def test_explicit_pastes_still_add_lines_after_a_check(store_with_lines):
    from ui.chat import classify_message

    two = "塑料玩具车 / Plastic toy cars\n无线蓝牙耳机 / Wireless Bluetooth earphones"
    assert classify_message(two, store_with_lines) == ("lines", ["塑料玩具车 / Plastic toy cars", "无线蓝牙耳机 / Wireless Bluetooth earphones"])
    assert classify_message("add: 不锈钢保温杯 500ml", store_with_lines) == ("lines", ["不锈钢保温杯 500ml"])
    assert classify_message("检查：塑料玩具车\n毛绒玩具熊", store_with_lines) == ("lines", ["塑料玩具车", "毛绒玩具熊"])
    # a multi-line paste is a reply only when it names the line
    assert classify_message("line 1 is steel bobbin cases\nfor industrial sewing machines", store_with_lines)[0] == "reply"
    assert classify_message("Parts: steel\nLED desk lamp", store_with_lines)[0] == "lines"


def test_start_screen_keeps_pasting_as_the_default(memory_store):
    from ui.chat import classify_message

    assert classify_message("不锈钢保温杯 500ml", memory_store) == ("lines", ["不锈钢保温杯 500ml"])
    assert classify_message("Which terms does customs reject?", memory_store) == ("question", "Which terms does customs reject?")
    assert classify_message("line 1 is steel bobbin cases", memory_store)[0] == "lines"   # nothing to update yet


def test_hint_only_when_the_text_could_have_been_a_reply(store_with_lines):
    from ui.chat import NOT_APPLIED_HINT, _not_applied_hint

    assert _not_applied_hint("line 2 looks wrong", store_with_lines) == NOT_APPLIED_HINT
    assert _not_applied_hint("stainless steel vacuum flask 500ml", store_with_lines) == NOT_APPLIED_HINT
    assert _not_applied_hint("status", store_with_lines) is None
    assert _not_applied_hint("Why only 31% on line 1?", store_with_lines) is None
