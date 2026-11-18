"""Feature 014a, User Story 3: after the ranking, the rulings that vote on a line's HS-6 are searched only within the
chapters of the model's validated candidates, with the line's query vectors and no new embedding call; the candidate
proposal before the ranking still searches every indexed chapter, and the vote's rules are those of feature 006 (spec
FR-011 to FR-014; contracts/classify-hs6.md, steps 6 to 9).

The rulings sit in an in-memory index over fake embeddings: for the line below, five cooling machines (chapter 84) are
the nearest rulings over all chapters, the lubricating preparations of chapter 34 follow, then one ruling of chapter 27
and one of chapter 38. The boundary cases use a search double with exact similarities that honours the chapter filter
as Chroma's `$in` does."""
from __future__ import annotations

from datetime import date

import pytest

from agent.config import HS6_VOTE_MIN_SIMILARITY, OVERRIDE_MIN
from agent.llm import get_client
from agent.routing import hs6_gate
from agent.schemas import NomenclatureChunk, RulingScope
from rag.bti import BTIStore
from rag.embeddings import FakeEmbeddings
from rag.loader import KnowledgeBase
from rag.nomenclature import NomenclatureIndex
from rag.retriever import BM25Index, HybridRetriever, InMemoryVectorSearch
from tools.classify_hs6 import RANK_SYSTEM, ClassifyContext, classify_lines
from tools.common import LineText

pytestmark = pytest.mark.integration

TEXT = "metal working coolant without mineral oil"
SHIRTS = "cotton t-shirts, knitted"
AS_OF = date(2026, 11, 18)
LABELS = {"2710.19": "Other petroleum oils", "3403.91": "Other lubricating preparations, for leather",
          "3403.99": "Other lubricating preparations", "3403.19": "Lubricating preparations containing petroleum oils",
          "3820.00": "Anti-freezing preparations", "8419.89": "Other machinery for cooling",
          "6109.10": "T-shirts, knitted, of cotton", "6109.90": "T-shirts, knitted, of other textiles",
          "6110.20": "Jerseys, knitted, of cotton", "6205.20": "Men's shirts of cotton, not knitted"}
# (reference, HS-6, the ruling's text): for TEXT nearest first, similarity 0.95 down to 0.48 with FakeEmbeddings(64)
RULINGS = [("XI-M1", "8419.89", "metal working coolant pump without mineral oil"),
           ("XI-M2", "8419.89", "metal working coolant without mineral oil chiller"),
           ("XI-M3", "8419.89", "metal working coolant circulation unit without mineral oil"),
           ("XI-M4", "8419.89", "coolant chiller for metal working, without mineral oil"),
           ("XI-M5", "8419.89", "metal working coolant cooling machine without mineral oil"),
           ("DE-L1", "3403.99", "lubricating preparation, coolant, without mineral oil"),
           ("AT-L2", "3403.99", "cutting fluid without mineral oil for metal working"),
           ("BE-L3", "3403.99", "water based coolant lubricant without mineral oil"),
           ("FR-L4", "3403.19", "cutting oil with mineral oil for metal working"),
           ("LU-L5", "3403.19", "lubricant containing mineral oil"),
           ("NL-O1", "2710.19", "mineral oil preparation more than 70 percent"),
           ("IT-A1", "3820.00", "antifreeze coolant for engines"),
           ("PL-T1", "6109.10", "t-shirts of cotton, knitted"),
           ("CZ-T2", "6109.90", "t-shirts of synthetic fibres, knitted"),
           ("SE-T3", "6110.20", "pullovers of cotton, knitted"),
           ("RO-W1", "6205.20", "cotton t-shirts, woven")]           # for SHIRTS: 0.91, 0.65, 0.60 and the woven 0.76
COOLANT_RANKING = [("3403.99", 95), ("2710.19", 60), ("3820.00", 40)]
SHIRT_RANKING = [("6109.10", 95), ("6109.90", 60), ("6110.20", 40)]


def chunk(code: str) -> NomenclatureChunk:
    return NomenclatureChunk(id=f"hs:{code}", text=f"Chapter {code[:2]}\nHeading {code[:4]} — {LABELS[code]}\n"
                                                    f"Subheading {code} — {LABELS[code]}",
                             metadata={"chapter": code[:2], "heading": code[:4], "subheading": code, "language": "en",
                                       "edition_year": 2026})


def record(reference: str, code: str, text: str) -> dict:
    return {"reference": reference, "code": code, "cn_code": code.replace(".", "") + "0000", "chapter": code[:2],
            "member_state": reference[:2], "description": text, "reasoning": "", "valid_from": "2025-01-01",
            "valid_to": "2027-12-31", "language": "de"}


class CountingEmbeddings(FakeEmbeddings):
    """FakeEmbeddings that count the embedding requests made for queries."""

    def __init__(self) -> None:
        super().__init__(dim=64)
        self.requests = 0

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        self.requests += 1
        return super().embed_queries(texts)

    def embed_query(self, text: str) -> list[float]:
        self.requests += 1
        return super().embed_query(text)


class ScopedHits:
    """A ruling search over given (ruling id, similarity) hits, nearest first, that keeps only the hits of the chapters
    in its filter, from each ruling's chapter in the store, and records the filters it was given."""

    def __init__(self, hits: list[tuple[str, float]], store: BTIStore) -> None:
        self.hits, self.store, self.filters = list(hits), store, []

    def search_by_vector(self, vector, k, chapter_filter=None, where=None):
        self.filters.append(chapter_filter)
        return [(i, s) for i, s in self.hits
                if chapter_filter is None or (self.store.get(i) or {}).get("chapter") in chapter_filter][:k]


def ranked(codes: list[tuple[str, int]]) -> dict:
    return {"candidates": [{"code": c, "confidence": n, "rationale": "r", "history_only": False} for c, n in codes]}


@pytest.fixture
def kb(rules, fake_llm):
    fake_llm.recorded.setdefault("RankOut", {}).update({TEXT: ranked(COOLANT_RANKING), SHIRTS: ranked(SHIRT_RANKING)})
    index = NomenclatureIndex([chunk(code) for code in LABELS])
    emb = CountingEmbeddings()
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in index.chunks], emb)
    bti = BTIStore([record(*r) for r in RULINGS])
    rulings = InMemoryVectorSearch([(f"bti:{ref}", text, {"chapter": code[:2], "code": code}) for ref, code, text in RULINGS],
                                   emb)
    base = KnowledgeBase(index, HybridRetriever(bm25=BM25Index([(c.id, c.text) for c in index.chunks]), vectors=vectors,
                                                chunks=index, k=6), bti, rules,
                         {"embedding_model": "fake", "built_at": "2026-11-18T00:00:00"}, emb, bti_vectors=rulings)
    emb.requests = 0
    return base


def classify(kb, text: str = TEXT, **ctx):
    line = LineText(line_no=1, text_en=text, flag_kind="ok", flag_reason="specific enough")
    return classify_lines([line], ClassifyContext(as_of=AS_OF, **ctx), kb=kb, client=get_client())[0]


def test_machinery_is_nearest_over_all_chapters(kb):
    vector = kb.embeddings.embed_query(TEXT)
    assert [i for i, _ in kb.bti_vectors.search_by_vector(vector, 5, None)] == [f"bti:XI-M{n}" for n in (1, 2, 3, 4, 5)]


def test_only_the_candidates_chapters_vote(kb, fake_llm):
    out = classify(kb)
    assert [c.code for c in out.candidates] == ["3403.99", "2710.19", "3820.00"]
    assert out.ruling_scope == RulingScope(chapters=["27", "34", "38"], not_indexed=[])
    v = out.hs6_vote
    assert v.competing == [("3403.99", ["DE", "AT", "BE"]), ("3403.19", ["FR", "LU"])]   # no ruling of chapter 84
    assert (v.majority, v.majority_share, v.agrees) == ("3403.99", 0.6, True)
    assert out.retrieval_trace.precedent_codes[0] == "8419.89"                            # the proposal saw every chapter
    calls = [c for c in fake_llm.calls if c["schema"] == "RankOut"]
    assert len(calls) == 1 and calls[0]["system"] == RANK_SYSTEM                          # the ranking prompt as before
    assert "(BTI precedent XI-M1, XI" in calls[0]["user"] and TEXT in calls[0]["user"]
    assert kb.embeddings.requests == 1                                                    # one embedding request: no new call


def test_candidates_of_one_chapter_search_that_chapter_only(kb):
    vector = kb.embeddings.embed_query(SHIRTS)
    assert "bti:RO-W1" in [i for i, _ in kb.bti_vectors.search_by_vector(vector, 5, None)]   # chapter 62, near
    out = classify(kb, SHIRTS)
    assert out.ruling_scope == RulingScope(chapters=["61"], not_indexed=[])
    assert {code[:2] for code, _ in out.hs6_vote.competing} == {"61"}


def test_the_lines_own_ruling_neither_votes_nor_is_listed(kb):
    out = classify(kb, exclude_refs=frozenset({"DE-L1"}))
    countries = [k for _, found in out.hs6_vote.competing for k in found]
    assert "DE" not in countries and sorted(countries) == ["AT", "BE", "FR", "LU", "NL"]
    assert out.hs6_vote.majority is None                                                  # 2 and 2 at the top: a tie


def scoped(kb, hits: list[tuple[str, float]], ranking: list[tuple[str, int]] = COOLANT_RANKING, fake=None, **ctx):
    kb.bti_vectors = ScopedHits(hits, kb.bti)
    if fake is not None:
        fake.recorded["RankOut"][TEXT] = ranked(ranking)
    return classify(kb, **ctx)


def test_the_proposal_searches_every_chapter_and_the_vote_the_candidates(kb):
    out = scoped(kb, [("bti:XI-M1", 0.95), ("bti:DE-L1", 0.80)])
    assert kb.bti_vectors.filters == [None, ["27", "34", "38"]]                            # one query vector, two searches
    assert out.hs6_vote.competing == [("3403.99", ["DE"])]


def test_exactly_the_floor_votes_on_the_scoped_rulings(kb):
    at_floor = scoped(kb, [("bti:XI-M1", 0.95), ("bti:DE-L1", HS6_VOTE_MIN_SIMILARITY)])
    assert at_floor.hs6_vote.competing == [("3403.99", ["DE"])] and at_floor.hs6_vote.agrees
    below = scoped(kb, [("bti:XI-M1", 0.95), ("bti:DE-L1", HS6_VOTE_MIN_SIMILARITY - 1e-4)])
    assert below.hs6_vote is None and below.ruling_scope == RulingScope(chapters=["27", "34", "38"], not_indexed=[])


def test_exactly_the_share_passes_on_the_scoped_rulings(kb, fake_llm):
    kb.bti.records.append(record("PT-L6", "3403.91", "lubricating preparation for leather"))
    kb.bti = BTIStore(kb.bti.records)
    out = scoped(kb, [("bti:XI-M1", 0.95), ("bti:XI-M2", 0.94), ("bti:DE-L1", 0.80), ("bti:AT-L2", 0.78),
                      ("bti:FR-L4", 0.70), ("bti:PT-L6", 0.65)])
    assert out.hs6_vote.majority_share == 0.5 and out.hs6_vote.agrees                    # 2 of 4 at the model's top


@pytest.mark.parametrize("at_second, gate", [(OVERRIDE_MIN, "vote_override"), (OVERRIDE_MIN - 1, "vote_disagrees")])
def test_the_override_needs_override_min_scoped_rulings(kb, fake_llm, at_second, gate):
    hits = [("bti:XI-M1", 0.96), ("bti:XI-M2", 0.95)]                                      # chapter 84: never counted
    hits += [(f"bti:{ref}", 0.9 - n / 100) for n, ref in enumerate(["DE-L1", "AT-L2", "BE-L3", "FR-L4", "LU-L5"][:at_second])]
    hits += [("bti:NL-O1", 0.5)] * (OVERRIDE_MIN - at_second)
    ranking = [("2710.19", 95), ("3403.99", 60), ("3820.00", 40)]
    for ref in ("FR-L4", "LU-L5"):                                                        # all five sit at 3403.99 here
        kb.bti.records[[r["reference"] for r in kb.bti.records].index(ref)]["code"] = "3403.99"
    kb.bti = BTIStore(kb.bti.records)
    out = scoped(kb, hits, ranking, fake=fake_llm)
    assert out.hs6_vote.candidate == 2
    assert hs6_gate(95, 85, out.hs6_vote, OVERRIDE_MIN)[1].value == gate
