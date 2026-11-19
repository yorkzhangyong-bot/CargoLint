"""Feature 014a, User Story 6: with the customs-wording switch on, the rewrite's vector joins the HS-6 step's two ruling
searches only (the candidate proposal and the vote), beside the raw-text vectors, and their hits merge; the
nomenclature search, the ranking prompt and the CN-8 step keep the raw text; everything is embedded in one request;
with the switch off nothing changes (spec FR-025, FR-026; contracts/classify-hs6.md steps 3 to 9).

Traceability: 014a/FR-025, 014a/FR-026."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

import tools.classify_cn8 as cn8_mod
from agent.llm import get_client
from agent.schemas import (Cn8Line, CreatedBy, CustomsWording, DescriptionCheck, Flag, FlagKind, LineStatus,
                           NomenclatureChunk, ParsedLine)
from agent.store import LineStore
from rag.bti import BTIStore
from rag.embeddings import FakeEmbeddings
from rag.loader import KnowledgeBase
from rag.nomenclature import NomenclatureIndex
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tools.classify_hs6 import ClassifyContext, classify_lines
from tools.common import LineText

pytestmark = pytest.mark.integration

TEXT = "金属加工用的冷却液，不含矿物油"
REWRITE = "Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl"
EXPANDED = "metal working coolant"
LINE = LineText(line_no=1, text_zh=TEXT, flag_kind="ok", flag_reason="specific")


class CountingEmbeddings(FakeEmbeddings):
    def __init__(self) -> None:
        super().__init__(dim=16)
        self.requests = 0

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        self.requests += 1
        return super().embed_queries(texts)


class Recording:
    """A vector search that records each (vector, chapter filter) it is given and answers as the search it wraps."""

    def __init__(self, inner) -> None:
        self.inner, self.calls = inner, []

    def search_by_vector(self, vector, k, chapter_filter=None, where=None):
        self.calls.append((tuple(vector), chapter_filter))
        return self.inner.search_by_vector(vector, k, chapter_filter, where)

    def __getattr__(self, name):
        return getattr(self.inner, name)


class ByText:
    """A ruling search whose hits depend on the query vector: the raw text's vector finds DEBTI1001, the rewrite's
    FRBTI2002; it records each (vector, chapter filter)."""

    def __init__(self, emb, found: dict[str, list[tuple[str, float]]]) -> None:
        self.found = {tuple(emb.embed_query(text)): hits for text, hits in found.items()}
        self.calls = []

    def search_by_vector(self, vector, k, chapter_filter=None, where=None):
        self.calls.append((tuple(vector), chapter_filter))
        return self.found.get(tuple(vector), [])[:k]


def chunk(code: str, label: str, cn8: tuple[str, ...]) -> NomenclatureChunk:
    lines = "\n".join(f"CN {c[:4]} {c[4:6]} {c[6:]} — {label}, {c}" for c in cn8)
    return NomenclatureChunk(id=f"hs:{code}", text=f"Chapter {code[:2]}\nHeading {code[:4]} — {label}\nSubheading {code} — "
                                                    f"{label}\n{lines}",
                             metadata={"chapter": code[:2], "heading": code[:4], "subheading": code, "language": "en",
                                       "edition_year": 2026})


def ruling(reference: str, code: str) -> dict:
    return {"reference": reference, "code": code, "cn_code": code.replace(".", "") + "1000", "chapter": code[:2],
            "member_state": reference[:2], "description": f"goods of {reference}", "reasoning": "", "language": "de",
            "valid_from": "2025-01-01", "valid_to": "2027-12-31"}


@pytest.fixture
def kb(rules, fake_llm):
    fake_llm.recorded.setdefault("RankOut", {})[TEXT] = {"candidates": [
        {"code": "3403.99", "confidence": 90, "rationale": "a lubricating preparation", "history_only": False}]}
    fake_llm.recorded.setdefault("WordingOut", {})[TEXT] = {"text": REWRITE}
    fake_llm.recorded.setdefault("ExpandOut", {})[TEXT] = {"queries": [EXPANDED], "hyde": None}
    index = NomenclatureIndex([chunk("3403.99", "Other lubricating preparations", ("34039910", "34039990")),
                               chunk("8419.89", "Other machinery for cooling", ("84198998",))])
    emb = CountingEmbeddings()
    vectors = Recording(InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in index.chunks], emb))
    bti = BTIStore([ruling("DEBTI1001", "3403.99"), ruling("FRBTI2002", "3403.99")])
    base = KnowledgeBase(index, HybridRetriever(bm25=BM25Index([(c.id, c.text) for c in index.chunks]), vectors=vectors,
                                                chunks=index, k=6), bti, rules,
                         {"embedding_model": "fake", "built_at": "2026-11-18T00:00:00"}, emb)
    base.bti_vectors = ByText(emb, {TEXT: [("bti:DEBTI1001", 0.90)], REWRITE: [("bti:FRBTI2002", 0.95)],
                                    EXPANDED: [("bti:DEBTI1001", 0.80)]})
    return base


def classify(kb, **ctx):
    return classify_lines([LINE], ClassifyContext(as_of=date(2026, 11, 18), **ctx), kb=kb, client=get_client())[0]


def vec(kb, text: str) -> tuple:
    return tuple(kb.embeddings.embed_query(text))


def test_the_rewrite_joins_the_ruling_searches_only_and_their_hits_merge(kb, fake_llm):
    out = classify(kb, customs_wording=True, expansion=False)
    raw, rewrite = vec(kb, TEXT), vec(kb, REWRITE)
    assert kb.bti_vectors.calls == [(raw, None), (rewrite, None), (raw, ["34"]), (rewrite, ["34"])]   # proposal, vote
    assert {v for v, _ in kb.retriever.vectors.calls} == {raw}                                       # nomenclature: raw only
    assert out.hs6_vote.competing == [("3403.99", ["FR", "DE"])]          # merged: DEBTI1001 only the raw text finds
    assert out.retrieval_trace.precedent_codes == ["3403.99"] and out.retrieval_trace.queries == [TEXT]
    rank = fake_llm.prompts_for("RankOut")
    assert len(rank) == 1 and TEXT in rank[0] and REWRITE not in rank[0]                             # the raw text only
    assert kb.embeddings.requests == 1                                                               # one request
    assert out.customs_wording == CustomsWording(text=REWRITE, language="de", glossary_terms=[])
    assert out.retrieval_trace.customs_wording == REWRITE


def test_with_query_expansion_its_queries_search_everything_and_the_rewrite_the_rulings(kb):
    classify(kb, customs_wording=True, expansion=True)
    raw, extra, rewrite = vec(kb, TEXT), vec(kb, EXPANDED), vec(kb, REWRITE)
    assert {v for v, _ in kb.retriever.vectors.calls} == {raw, extra}                                # no rewrite
    assert [v for v, f in kb.bti_vectors.calls if f is None] == [raw, extra, rewrite]
    assert [v for v, f in kb.bti_vectors.calls if f is not None] == [raw, extra, rewrite]
    assert kb.embeddings.requests == 1


def test_with_the_switch_off_nothing_changes(kb, fake_llm):
    out = classify(kb, customs_wording=False, expansion=False)
    raw = vec(kb, TEXT)
    assert kb.bti_vectors.calls == [(raw, None), (raw, ["34"])] and fake_llm.prompts_for("WordingOut") == []
    assert out.customs_wording is None and out.retrieval_trace.customs_wording is None
    assert out.hs6_vote.competing == [("3403.99", ["DE"])]


def test_a_store_without_a_main_language_makes_no_rewrite(kb, fake_llm):
    kb.main_language = None
    out = classify(kb, customs_wording=True, expansion=False)
    assert out.customs_wording is None and fake_llm.prompts_for("WordingOut") == []


def test_the_line_version_keeps_the_raw_text_for_the_cn8_step(kb, monkeypatch):
    out = classify(kb, customs_wording=True, expansion=False)
    store = LineStore(backend={}, index=kb.index, clock=lambda: datetime(2026, 11, 18, tzinfo=timezone.utc))
    store.new_shipment(reference="TEST-014A", threshold=85)
    store.add_lines([ParsedLine(line_no=1, text_zh=TEXT, source_ref="row 1")], CreatedBy.paste)
    store.update_check(1, DescriptionCheck(line_no=1, flag=Flag(kind=FlagKind.ok, reason="specific"), status=LineStatus.checked))
    store.update_classification(1, out)
    v = store.get_line(1).current
    assert v.customs_wording.text == REWRITE and (v.text_zh, v.text_en, v.display_text) == (TEXT, "", TEXT)
    seen = []
    monkeypatch.setattr(cn8_mod, "select_rulings", lambda text, *a, **k: seen.append(text) or cn8_mod.Rulings([], []))
    cn8_mod.choose_cn8(Cn8Line(line_no=1, text_zh=v.text_zh, text_en=v.text_en, hs6="3403.99"), "3403.99", kb, get_client(),
                       85, date(2026, 11, 18))
    assert seen == [TEXT]                                                                            # never the rewrite
