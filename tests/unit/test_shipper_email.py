"""The shipper email (feature 005, contracts/view.md §7, SC-006): drafted from string templates in English or Chinese,
for the red lines with a question, with no model call."""
from __future__ import annotations

import re

import pytest

from agent.schemas import Decision, DecisionRoute
from tests.ui import harness as h
from ui import shipper_email, view

pytestmark = pytest.mark.unit

RED = ("ics2_term", "firm_stop_word", "vague_close", "unreadable", "cn8_question", "sent", "taric_question")
FACTS = "Please state the exact product name, the material and the intended use."
FACTS_ZH = "请说明确切的产品名称、材质和用途。"


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


@pytest.fixture
def store(kb):
    s, nos = h.store_with("ready", *RED[:3], "failed", *RED[3:], "accepted", kb=kb)
    s.set_shipper("Yiwu Bright Trading Co.")
    return s, nos


def test_the_english_draft(store, kb):
    s, nos = store
    with h.ModelGuard() as guard:
        d = shipper_email.draft(s, kb, "en")
    assert guard.calls == 0
    assert d.lang == "en" and d.line_nos == [nos[name] for name in RED]          # file order; the failed line left out
    assert d.text == d.subject + "\n\n" + d.body
    assert d.text.split("\n") == [
        "Subject: Invoice INV-TEST — 7 lines need more detail before customs filing",
        "",
        "Dear Yiwu Bright Trading Co.,",
        "",
        "Thank you for your documents for invoice INV-TEST. Before we can file the ICS2 entry summary declaration with EU "
        "customs, we need more detail on the following 7 goods descriptions:",
        "",
        f"1. Line {nos['ics2_term']} “Spare parts” — “spare parts” is not accepted as a goods description. {FACTS}",
        f"2. Line {nos['firm_stop_word']} “Gift” — “gift” is not accepted as a goods description. {FACTS}",
        f"3. Line {nos['vague_close']} “Mixed household articles” — The description is too general for customs. {FACTS}",
        f"4. Line {nos['unreadable']} “” — We could not read this line of your document. {FACTS}",
        f"5. Line {nos['cn8_question']} “塑料玩具车 / Plastic toy cars” — Please confirm whether the toy cars incorporate a "
        "motor.",
        f"6. Line {nos['sent']} “Ceramic dinner plates” — {FACTS}",
        f"7. Line {nos['taric_question']} “不锈钢六角螺栓 / Stainless steel hexagon bolts, threaded” — {h.TARIC_QUESTION}",
        "",
        "Please reply with the details for each numbered line. We will file as soon as we have them.",
        "",
        "Kind regards,",
        "[Your name] — [Forwarder name], Hamburg",
    ]


def test_each_description_is_the_first_versions_text(kb):
    s, nos = h.store_with("edited_ever_flagged", "sent", kb=kb)
    s.set_decision(nos["edited_ever_flagged"], Decision(route=DecisionRoute.ask_shipper))
    d = shipper_email.draft(s, kb, "en")
    assert f"Line {nos['edited_ever_flagged']} “Spare parts” — " in d.text                # not the clerk's edit


def test_greeting_and_singular(kb):
    s, nos = h.store_with("sent", "ready", kb=kb)
    for name in (None, "New shipper"):
        if name:
            s.set_shipper(name)
        d = shipper_email.draft(s, kb, "en")
        lines = d.text.split("\n")
        assert lines[0] == "Subject: Invoice INV-TEST — 1 line needs more detail before customs filing"
        assert lines[2] == "Dear Sir or Madam,"
        assert lines[4].endswith("we need more detail on the following goods description:")
        assert shipper_email.draft(s, kb, "zh").text.split("\n")[2] == "您好！"


def test_the_chinese_draft(store, kb):
    s, nos = store
    d = shipper_email.draft(s, kb, "zh")
    assert d.lang == "zh" and d.line_nos == [nos[name] for name in RED]
    assert d.text.split("\n") == [
        "主题：发票 INV-TEST：7 行货物描述需补充信息后方可报关",
        "",
        "Yiwu Bright Trading Co.，您好！",
        "",
        "感谢您提供发票 INV-TEST 的单据。在向欧盟海关提交 ICS2 入境摘要申报之前，我们需要您就以下 7 项货物描述补充信息：",
        "",
        f"1. 第 {nos['ics2_term']} 行“Spare parts”— “spare parts”不能作为货物描述。{FACTS_ZH}",
        f"2. 第 {nos['firm_stop_word']} 行“Gift”— “gift”不能作为货物描述。{FACTS_ZH}",
        f"3. 第 {nos['vague_close']} 行“Mixed household articles”— 该描述过于笼统，无法用于海关申报。{FACTS_ZH}",
        f"4. 第 {nos['unreadable']} 行“”— 我们无法读取您单据中的这一行。{FACTS_ZH}",
        f"5. 第 {nos['cn8_question']} 行“塑料玩具车 / Plastic toy cars”— 请确认以下信息：whether the toy cars incorporate a motor",
        f"6. 第 {nos['sent']} 行“Ceramic dinner plates”— {FACTS_ZH}",
        f"7. 第 {nos['taric_question']} 行“不锈钢六角螺栓 / Stainless steel hexagon bolts, threaded”— 请说明以下哪一个 TARIC "
        "细分适用：7318 15 58 10（Self-locking bolts and nuts）；7318 15 58 90（Other）。",
        "",
        "请按编号逐项回复。收到您的信息后，我们将尽快完成申报。",
        "",
        "顺颂商祺！",
        "[经办人姓名] — [货代公司名称]，汉堡",
    ]
    data = ["Yiwu Bright Trading Co.", "INV-TEST", "ICS2", "TARIC", "spare parts", "gift",
            "whether the toy cars incorporate a motor", "Self-locking bolts and nuts", "Other"]
    data += [s.get_line(nos[name]).versions[0].display_text for name in RED]
    rest = d.text
    for item in sorted(data, key=len, reverse=True):
        rest = rest.replace(item, "")
    assert not re.search(r"[A-Za-z]", rest)                          # English only in data (SC-006)


def test_the_sample(kb):
    kb2 = h.make_kb("sample")
    s = h.sample_store(kb2)
    red = [l.line_no for l in s.lines if view.line_status(s, l).colour == "red" and view.question(s, l, "en", kb2)]
    assert red
    for lang in ("en", "zh"):
        d = shipper_email.draft(s, kb2, lang)
        assert d.line_nos == red
        numbered = [x for x in d.body.split("\n") if re.match(r"\d+\. ", x)]
        assert len(numbered) == len(red)
