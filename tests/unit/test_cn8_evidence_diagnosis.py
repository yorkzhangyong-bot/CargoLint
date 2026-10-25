"""The ask classifier of tests/eval/cn8_evidence_diagnosis.py, offline on made-up quotes with known answers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.eval import cn8_evidence_diagnosis as dx

pytestmark = pytest.mark.unit

DESCRIPTION = ("Pumps mit Absatz, Riemen aus Kunststoff mit Kunststoffschnallenverschluss.\n"
               "To be worn when doing sports and exercise.")
LABELS = ["Other > With uppers of plastics > Footwear with a vamp made of straps", "Covering the ankle"]
EXCERPT = "Sandalen mit Oberteil aus Kunststoff, destinado a un uso deportivo"
SOURCES = LABELS + ["Other footwear with outer soles and uppers of rubber or plastics", EXCERPT]


def raw(evidence, cn8="64029190", visible=True):
    return {"cn8": cn8, "attribute_visible": visible, "confidence": 85, "evidence": evidence, "precedent": None,
            "rationale": "because"}


@pytest.mark.parametrize("evidence, expected", [
    ("With uppers of plastics > Footwear with a vamp made of straps", "source-confusion"),   # a CN-8 label path
    ("Riemen aus Kunststoff; destinado a un uso deportivo", "source-confusion"),   # one fragment from a ruling excerpt
    # the evidence check (feature 006) accepts whole-word runs at 90 %; what it still rejects can be a near-miss inside
    # a long word: part of a compound, or a compound with a typo
    ("Verschluss", "near-miss"),                      # inside "Kunststoffschnallenverschluss", once spaces are removed
    ("Schnalenverschluss", "near-miss"),              # fuzzy: one "l" short of "...schnallenverschluss"
    ("made of carbon fibre", "other"),
    ("", "other"),                                    # an answer without a quote
])
def test_an_answer_whose_quote_the_check_rejected(evidence, expected):
    assert dx.classify_ask(raw(evidence), DESCRIPTION, SOURCES) == expected


def test_a_model_that_declined_is_counted_as_such_whatever_it_quoted():
    for answer in (raw("With uppers of plastics", cn8=None, visible=False), raw("Riemen aus Kunststoff", visible=False),
                   raw("made of carbon fibre", cn8=None)):
        assert dx.classify_ask(answer, DESCRIPTION, SOURCES) == "model-declined"


def test_source_confusion_comes_before_near_miss():
    sources = SOURCES + ["Pumps mit Verschluss aus Metall"]   # a near-miss that a ruling also says
    assert dx.classify_ask(raw("Verschluss"), DESCRIPTION, sources) == "source-confusion"


def test_a_phrase_must_appear_whole_in_a_source():
    assert dx.in_source("vamp made of straps", LABELS[0]) and not dx.in_source("straps made of vamp", LABELS[0])
    assert not dx.in_source("ankle cover", LABELS[1])                 # words of a label, not its phrase


def test_quotes_of_declined_answers_are_still_placed():
    assert dx.classify_quote("Riemen aus Kunststoff", DESCRIPTION, SOURCES) == "words of the line"
    assert dx.classify_quote("", DESCRIPTION, SOURCES) == "no quote"


def test_the_partial_ratio():
    assert dx.partial_ratio("doing sport and exercise", "to be worn when doing sports and exercise") >= 90
    assert dx.partial_ratio("made of carbon fibre", "to be worn when doing sports and exercise") < 90
    assert dx.partial_ratio("", "anything") == 0


def test_the_request_holds_the_labels_and_the_excerpts_as_sent():
    index = SimpleNamespace(cn8_lines=lambda hs6: [("64029190", LABELS[1]), ("64029110", "Incorporating a protective metal toecap")],
                            subheading_text=lambda hs6: "Covering the ankle")
    bti = SimpleNamespace(get=lambda ruling_id: {"bti:R1": {"description": "x" * 500}}.get(ruling_id))
    row = {"hs6": "6402.91", "sent": [{"reference": "R1", "cn8": "64029190", "rank": 1},
                                      {"reference": "R2", "cn8": "64029110", "rank": 2}]}   # R2 unknown to the store
    assert dx.request_sources(row, index, bti) == [LABELS[1], "Incorporating a protective metal toecap",
                                                   "Covering the ankle", "x" * 400, ""]
