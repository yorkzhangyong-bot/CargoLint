"""The email to the shipper (feature 005, contracts/view.md §7), with no Streamlit import: string templates in English
or Chinese for the red lines with a question, to copy and send by hand. No model call; nothing is sent or stored."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ui import view

PLACEHOLDER_SHIPPER = "New shipper"


@dataclass(frozen=True)
class EmailDraft:
    """data-model §1."""

    lang: str                        # "en" or "zh"
    subject: str
    body: str
    line_nos: list[int]              # the red lines with a question, in file order
    text: str                        # the subject, a blank line and the body: what "Copy email" copies


def _items(store: Any, kb: Any, lang: str) -> list[tuple[int, str, str]]:
    """(line number, the first version's text, the question) of each red line with a question; a failed check has
    none."""
    items = []
    for line in store.lines:
        if view.line_status(store, line).colour != "red":
            continue
        question = view.question(store, line, lang, kb)
        if question:
            items.append((line.line_no, line.versions[0].display_text, question))
    return items


def draft(store: Any, kb: Any, lang: str = "en") -> EmailDraft:
    items = _items(store, kb, lang)
    c = len(items)
    invoice = view.invoice_id(store)
    name = store.shipment.shipper.name
    named = bool(name) and name != PLACEHOLDER_SHIPPER
    if lang == "zh":
        subject = f"主题：发票 {invoice}：{c} 行货物描述需补充信息后方可报关"
        head = [f"{name}，您好！" if named else "您好！", "",
                f"感谢您提供发票 {invoice} 的单据。在向欧盟海关提交 ICS2 入境摘要申报之前，我们需要您就以下 {c} 项货物描述补充信息："]
        numbered = [f"{i}. 第 {n} 行“{text}”— {question}" for i, (n, text, question) in enumerate(items, 1)]
        tail = ["请按编号逐项回复。收到您的信息后，我们将尽快完成申报。", "", "顺颂商祺！", "[经办人姓名] — [货代公司名称]，汉堡"]
    else:
        lines = "1 line needs" if c == 1 else f"{c} lines need"
        subject = f"Subject: Invoice {invoice} — {lines} more detail before customs filing"
        which = "the following goods description" if c == 1 else f"the following {c} goods descriptions"
        head = [f"Dear {name}," if named else "Dear Sir or Madam,", "",
                f"Thank you for your documents for invoice {invoice}. Before we can file the ICS2 entry summary "
                f"declaration with EU customs, we need more detail on {which}:"]
        numbered = [f"{i}. Line {n} “{text}” — {question}" for i, (n, text, question) in enumerate(items, 1)]
        tail = ["Please reply with the details for each numbered line. We will file as soon as we have them.", "",
                "Kind regards,", "[Your name] — [Forwarder name], Hamburg"]
    body = "\n".join([*head, "", *numbered, "", *tail])
    return EmailDraft(lang=lang, subject=subject, body=body, line_nos=[n for n, _, _ in items],
                      text=f"{subject}\n\n{body}")
