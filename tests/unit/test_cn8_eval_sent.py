"""The rulings sent to the model, logged per line and run by tests/eval/cn8_eval.py, offline: the real CN-8 step on a
small fake knowledge base (no BTI vectors, so rulings go round-robin in CN-8 order) and a fake model client."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import tools.classify_cn8 as classify_cn8
from agent.schemas import Cn8Out, Precedent
from tests.eval import cn8_eval as ev

pytestmark = pytest.mark.unit

AS_OF = date(2026, 10, 23)
OPTIONS = [("87149110", "Frames"), ("87149130", "Front forks"), ("87149190", "Other")]


class FakeBti:
    """The rulings under 8714.91 grouped by CN-8, as BTIStore.by_cn8 returns them."""

    def by_cn8(self, hs6, as_of):
        return {"87149110": [Precedent(reference="A", code="8714911000")],
                "87149130": [Precedent(reference="X", code="87149130")],
                "87149190": [Precedent(reference="B", code="8714919000")]}


KB = SimpleNamespace(index=SimpleNamespace(cn8_lines=lambda hs6: OPTIONS, subheading_text=lambda hs6: "Frames and forks"),
                     bti=FakeBti(), bti_vectors=None)
CLIENT = SimpleNamespace(call=lambda schema, system, user, max_retries=0: Cn8Out(   # always 87149110, from the line's words
    cn8="87149110", confidence=95, attribute_visible=True, evidence="bicycle frames", rationale="frames"))


def eval_line(reference, cn8):
    return {"reference": reference, "chapter": "87", "hs6": "8714.91", "cn8": cn8, "language": "en",
            "description": f"Bicycle frames, ruling {reference}"}


def test_each_row_keeps_the_rulings_sent_for_its_own_line():
    original = classify_cn8.select_rulings
    rows, _ = ev.run_once([eval_line("A", "87149110"), eval_line("B", "87149190"), eval_line("Q", "87149130")],
                          KB, CLIENT, AS_OF, workers=2)
    assert classify_cn8.select_rulings is original                       # the recording ends with the run
    a, b, q = rows
    assert a["sent"] == [{"reference": "X", "cn8": "87149130", "rank": 1, "country": ""},          # the store gives none
                         {"reference": "B", "cn8": "87149190", "rank": 2, "country": ""}]
    assert (a["hit"], a["expected_sent"]) == (True, False)               # its own ruling A is never sent
    assert b["sent"] == [{"reference": "A", "cn8": "87149110", "rank": 1, "country": ""},
                         {"reference": "X", "cn8": "87149130", "rank": 2, "country": ""}]
    assert (b["hit"], b["expected_sent"]) == (False, False)
    assert [s["reference"] for s in q["sent"]] == ["A", "X", "B"] and [s["rank"] for s in q["sent"]] == [1, 2, 3]
    assert (q["hit"], q["expected_sent"]) == (False, True)               # X is at the expected 87149130
    assert ev.expected_sent_share([rows]) == {"wrong": 2, "with_expected": 1, "share": 0.5}


def answer_by_line(schema, system, user, max_retries=0):
    """The raw CN-8 output for each line of the next test, keyed on words of its description."""
    if "Aluminium" in user:   # evidence: words of the line
        return Cn8Out(cn8="87149110", confidence=95, attribute_visible=True, evidence="bicycle frames", rationale="frames")
    if "Steel" in user:       # evidence: a CN-8 label, not words of the line
        return Cn8Out(cn8="87149130", confidence=85, attribute_visible=True, evidence="Front forks", precedent="X",
                      rationale="forks")
    return Cn8Out(cn8=None, confidence=0, attribute_visible=False, deciding_attribute="the part", rationale="not stated")


def test_each_row_keeps_the_raw_output_the_evidence_check_and_the_route():
    lines = [dict(eval_line(ref, "87149110"), description=text)
             for ref, text in (("A", "Aluminium bicycle frames"), ("B", "Steel bicycle frames"), ("Q", "Bicycle parts"))]
    original = classify_cn8.evidence_match
    a, b, q = ev.run_once(lines, KB, SimpleNamespace(call=answer_by_line), AS_OF, workers=2)[0]
    assert classify_cn8.evidence_match is original                       # the recording ends with the run
    assert (a["evidence_rule"], b["evidence_rule"], q["evidence_rule"]) == ("exact", None, None)
    assert a["raw"] == {"cn8": "87149110", "attribute_visible": True, "confidence": 95, "evidence": "bicycle frames",
                        "precedent": None, "rationale": "frames"}
    assert (a["evidence_check"], a["route"], a["chosen"]) == ("passed", "auto_accept", "87149110")
    assert b["raw"]["cn8"] == "87149130" and b["raw"]["precedent"] == "X"   # what the model said before the check
    assert (b["evidence_check"], b["route"], b["chosen"]) == ("rejected", "ask_shipper", None)
    assert (q["raw"]["attribute_visible"], q["raw"]["cn8"]) == (False, None)
    assert (q["evidence_check"], q["route"]) == ("not run", "ask_shipper")   # the code checks no quote the model withheld
    assert a["sent_cn8"] == ["87149130", "87149190"] and q["sent_cn8"] == ["87149110", "87149130", "87149190"]


RECORDS = {   # reference: (CN code, issuing country, valid to); the store behind the fake vector search below
    "Q": ("8714913000", "IE", "2030-01-01"), "X": ("87149130", "FR", "2030-01-01"), "OLD": ("8714911000", "DE", "2024-01-01"),
    "A": ("8714911000", "DE", "2030-01-01"), "B": ("8714919000", "FR", "2030-01-01")}


class VectorBti:
    """by_cn8 and get as BTIStore has them, over RECORDS: valid rulings only for by_cn8, validity checked by get(as_of)."""

    def _valid(self, ref, as_of):
        return as_of is None or date.fromisoformat(RECORDS[ref][2]) >= as_of

    def by_cn8(self, hs6, as_of):
        out = {}
        for ref, (code, country, _) in RECORDS.items():
            if self._valid(ref, as_of):
                out.setdefault(code[:8], []).append(Precedent(reference=ref, code=code, member_state=country))
        return out

    def get(self, ruling_id, as_of=None):
        ref = ruling_id.removeprefix("bti:")
        if ref not in RECORDS or not self._valid(ref, as_of):
            return None
        code, country, valid_to = RECORDS[ref]
        return {"reference": ref, "cn_code": code, "member_state": country, "valid_to": valid_to}


class FakeVectors:
    """The BTI vector search: the same hits, nearest first, for every query (relevance = 1 - distance)."""

    def __init__(self, hits):
        self.hits, self.texts = hits, []

    def embed_query_cached(self, text):
        self.texts.append(text)
        return [1.0]

    def search_by_vector(self, vector, k, chapter_filter=None, where=None):
        return list(self.hits)


def test_each_row_keeps_the_nearest_hits_and_the_vote_of_the_rulings_sent():
    vectors = FakeVectors([("bti:Q", 0.99), ("bti:X", 0.90), ("bti:OLD", 0.85), ("bti:A", 0.80), ("bti:B", 0.70)])
    kb = SimpleNamespace(index=KB.index, bti=VectorBti(), bti_vectors=vectors)
    original = vectors.search_by_vector
    (q,), _ = ev.run_once([eval_line("Q", "87149130")], kb, CLIENT, AS_OF, workers=1)
    assert vectors.search_by_vector == original and "search_by_vector" not in vars(vectors)   # recorded for the run only
    assert q["nearest_hits"] == [
        {"reference": "Q", "cn8": "87149130", "distance": 0.01, "country": "IE", "eligible": False},   # its own ruling
        {"reference": "X", "cn8": "87149130", "distance": 0.1, "country": "FR", "eligible": True},
        {"reference": "OLD", "cn8": "87149110", "distance": 0.15, "country": "DE", "eligible": False},  # expired
        {"reference": "A", "cn8": "87149110", "distance": 0.2, "country": "DE", "eligible": True},
        {"reference": "B", "cn8": "87149190", "distance": 0.3, "country": "FR", "eligible": True}]
    assert [(s["reference"], s["country"]) for s in q["sent"]] == [("X", "FR"), ("A", "DE"), ("B", "FR")]   # nearest first
    # the vote of the rulings sent: DE weighs 3, FR 1 each; the model (always 87149110) agrees with the majority
    assert (q["majority_cn8"], q["majority_share"], q["model_agrees_with_majority"]) == ("87149110", 0.6, True)


@pytest.mark.parametrize("sent,expected", [
    ([], (None, None)),
    ([("87149110", "FR"), ("87149130", "FR")], (None, 0.5)),                   # a tie has no majority
    ([("87149110", "DE"), ("87149130", "FR"), ("87149130", "FR")], ("87149110", 0.6)),
    ([("87149130", "XI"), ("87149130", "IE")], ("87149130", 1.0))])
def test_the_vote_weighs_the_entry_country_three_times(sent, expected):
    assert ev.ruling_vote([{"cn8": c, "country": k} for c, k in sent]) == expected


def test_the_share_counts_every_wrong_result_of_every_run():
    def run(*pairs):
        return [{"hit": hit, "expected_sent": sent} for hit, sent in pairs]
    runs = [run((True, False), (False, True), (False, False)), run((True, True), (False, True), (True, False))]
    assert ev.expected_sent_share(runs) == {"wrong": 3, "with_expected": 2, "share": 0.6667}
    assert ev.expected_sent_share([run((True, True))]) == {"wrong": 0, "with_expected": 0, "share": None}


def test_the_report_shows_every_repeated_run_with_its_tag_and_the_share():
    base = {"run_on": "2026-10-25", "model": "m", "threshold": 85, "top1": 92, "n": 120, "written": 107, "written_wrong": 15,
            "to_confirm": 1, "questions": 12, "failures": 0, "with_precedent": 103, "per_chapter": {"39": "10/10"},
            "elapsed_s": 300.0, "cost_usd": 0.1139, "cost_eur": 0.1048, "repeat": 3, "temperature": 0.0, "seed": None,
            "top1_runs": [92, 92, 94], "majority_top1": 93, "code_consistency": 0.9167, "decision_consistency": 0.9083,
            "unstable": []}
    history = [dict(base, iteration=5, change="baseline", tag="baseline-stability"),
               dict(base, iteration=7, change="three-level rule", tag="prompt-evidence-v2",
                    expected_sent={"wrong": 84, "with_expected": 63, "share": 0.75})]
    report = ev.render_report(history, {"rulings": [{}] * 120, "per_chapter": 10, "built_on": "2026-10-23", "seed": 7})
    assert "| 5 | 2026-10-25 | baseline-stability | 0.0 | none | 3 |" in report
    assert "| 7 | 2026-10-25 | prompt-evidence-v2 | 0.0 | none | 3 |" in report
    assert "Iteration 7: 63 of 84 wrong results (75.0%)" in report
