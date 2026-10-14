"""CSV and JSON export (FR-041, contracts/export.md)."""
import csv
import io
import json
import re

import pytest

from agent.schemas import (
    Candidate,
    Classification,
    CreatedBy,
    Decision,
    DecisionRoute,
    DescriptionCheck,
    Flag,
    FlagKind,
    LineVersion,
    ParsedLine,
    Precedent,
    RetrievalTrace,
    RuleSource,
)
from agent.store import LineStore

pytestmark = pytest.mark.unit

CSV_COLUMNS = ["line_no", "text_zh", "text_en", "qty", "flag", "flag_rule", "hs6_1", "conf_1", "hs6_2", "conf_2", "hs6_3", "conf_3",
               "precedent_1", "route", "route_set_by", "decided_code", "decided_how", "version_no", "last_change", "status", "note"]


@pytest.fixture
def store(small_index):
    s = LineStore(backend={}, index=small_index)
    s.new_shipment(reference="HOL-2026-10-0472", threshold=85)
    s.add_lines([ParsedLine(text_zh="配件", text_en="Parts", qty="14 CTN", source_ref="r4"),
                 ParsedLine(text_zh="LED台灯 USB供电", text_en="LED desk lamp, USB powered", qty="40 CTN", source_ref="r5"),
                 ParsedLine(text_zh="不锈钢保温杯", text_en="Stainless steel vacuum flask, 500 ml", qty="60 CTN", source_ref="r6"),
                 ParsedLine(text_zh="礼品", text_en="Gift", qty="6 CTN", source_ref="r7")], CreatedBy.file)
    prec = Precedent(reference="DE1234/25", member_state="DE", code="8452.90", description="bobbin cases")
    s.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.vague, rule_source=RuleSource.ics2_unacceptable, matched_term="parts", ask_for=["material"])))
    s.update_classification(1, Classification(line_no=1, candidates=[Candidate(code="8452.90", subheading_text="Parts of sewing machines", confidence=31, rationale="r", history_only=True, precedent=prec),
                                                                   Candidate(code="8487.90", subheading_text="Other", confidence=19, rationale="r")],
                                              retrieval_trace=RetrievalTrace(original="配件 / Parts", queries=["parts"])))
    s.update_check(2, DescriptionCheck(line_no=2, flag=Flag(kind=FlagKind.ok)))
    s.update_classification(2, Classification(line_no=2, candidates=[Candidate(code="9405.21", subheading_text="LED lamps", confidence=72, rationale="r")]))
    s.update_check(3, DescriptionCheck(line_no=3, flag=Flag(kind=FlagKind.ok)))
    s.update_classification(3, Classification(line_no=3, candidates=[Candidate(code="9617.00", subheading_text="Vacuum flasks", confidence=96, rationale="r")]))
    s.update_check(4, DescriptionCheck(line_no=4, flag=Flag(kind=FlagKind.stop_word, rule_source=RuleSource.firm_stop_words, matched_term="gift", ask_for=["material"], pure_stop_word=True)))
    s.set_decision(2, Decision(route=DecisionRoute.accepted, decided_code="9405.21"))
    s.add_version(1, LineVersion(created_by=CreatedBy.shipper_reply, text_zh="", text_en="steel bobbin cases", reply_text="line 1 is steel bobbin cases",
                                 contradiction_note=None))
    return s


def test_csv_columns_bom_and_content(store):
    data = store.to_csv_bytes()
    assert data.startswith("﻿".encode("utf-8"))
    text = data.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert list(rows[0].keys()) == CSV_COLUMNS
    assert [r["line_no"] for r in rows] == ["1", "2", "3", "4"]  # every line, in line order
    r1, r2, r3, r4 = rows
    assert r1["text_en"] == "steel bobbin cases" and r1["version_no"] == "2"  # current version only
    assert r1["text_zh"] == "" and r4["text_zh"] == "礼品"  # Chinese intact
    assert r2["route"] == "accepted" and r2["route_set_by"] == "clerk" and r2["decided_code"] == "9405.21" and r2["decided_how"] == "top"
    assert r3["route"] == "auto_accept" and r3["route_set_by"] == "routing_rule" and r3["decided_code"] == "9617.00" and r3["decided_how"] == "auto"
    assert r4["route"] == "ask_shipper" and r4["decided_code"] == "" and r4["decided_how"] == "" and r4["flag_rule"] == "firm_stop_words:gift"
    assert r4["hs6_1"] == "" and r4["conf_1"] == ""
    assert "reply" not in text.lower().replace("precedent", "") or "line 1 is steel bobbin cases" not in text  # reply text not exported
    assert "queries" not in text and "audit" not in text


def test_json_shape(store):
    payload = json.loads(store.to_json_bytes(knowledge_base_updated="2026-10-14").decode("utf-8"))
    assert set(payload) == {"shipment", "lines"}
    sh = payload["shipment"]
    assert sh["reference"] == "HOL-2026-10-0472" and sh["threshold"] == 85 and sh["knowledge_base_updated"] == "2026-10-14"
    assert {"total_tokens", "cost_eur"} <= set(sh["usage"])
    assert len(payload["lines"]) == 4
    l1 = payload["lines"][0]
    assert l1["flag"]["kind"] == "" and l1["version_no"] == 2  # v2 added by a reply, not yet re-checked → no flag
    l2 = payload["lines"][1]
    assert l2["route"] == "accepted" and l2["decided_code"] == "9405.21" and l2["decided_how"] == "top"
    assert l2["candidates"][0] == {"code": "9405.21", "subheading_text": "LED lamps", "confidence": 72, "history_only": False, "precedent": None}
    assert payload["lines"][3]["flag"]["ask_for"] == ["material"]
    for line in payload["lines"]:
        assert "reply_text" not in line and "retrieval_trace" not in line and "audit" not in line


def test_precedent_reference_is_exported_for_the_top_candidate(small_index):
    s = LineStore(backend={}, index=small_index)
    s.new_shipment(reference="X", threshold=85)
    s.add_lines([ParsedLine(text_zh="配件", text_en="Parts", source_ref="r")], CreatedBy.paste)
    s.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.vague, rule_source=RuleSource.ics2_unacceptable, matched_term="parts", ask_for=["material"])))
    s.update_classification(1, Classification(line_no=1, candidates=[Candidate(code="8452.90", subheading_text="t", confidence=31, rationale="r")]))
    s.update_precedents(1, {"8452.90": [Precedent(reference="DE1234/25", member_state="DE", code="8452.90")]})
    row = s.export_rows()[0]
    assert row["precedent_1"] == "DE1234/25"


def test_export_filename_pattern(store):
    assert re.fullmatch(r"cargolint_HOL-2026-10-0472_\d{8}-\d{4}\.csv", store.export_filename("csv"))
    assert store.export_filename("json").endswith(".json")
