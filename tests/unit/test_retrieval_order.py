"""Feature 006, retrieval determinism: one order for near-equal vector distances, and one embedding per normalised
query text for the life of a vector search."""
from __future__ import annotations

import itertools

import pytest

from rag.retriever import InMemoryVectorSearch, stable_order

pytestmark = pytest.mark.unit

# distances on 4-decimal values, so a jitter of up to ±4e-5 (a spread under 1e-4) stays in the same rounded value
DISTANCES = [("bti:C", 0.1000), ("bti:A", 0.1000), ("bti:D", 0.1003), ("bti:B", 0.2500)]
EXPECTED = ["bti:A", "bti:C", "bti:D", "bti:B"]   # nearest first; an equal rounded distance goes by reference


def test_jittered_distances_keep_one_order():
    for jitter in itertools.product((-4e-5, 0.0, 4e-5), repeat=len(DISTANCES)):
        hits = [(doc_id, 1.0 - (d + j)) for (doc_id, d), j in zip(DISTANCES, jitter)]   # relevance = 1 - distance
        assert stable_order(hits) == EXPECTED, jitter
        assert stable_order(hits[::-1]) == EXPECTED, jitter


def test_a_clearly_nearer_hit_comes_first_whatever_its_reference():
    assert stable_order([("bti:A", 0.70), ("bti:Z", 0.90)]) == ["bti:Z", "bti:A"]


class FixedEmbeddings:
    """Two-dimensional vectors, so the nearest document is known."""

    VECTORS = {"near": [1.0, 0.0], "mid": [0.8, 0.6], "far": [0.0, 1.0]}

    def embed_documents(self, texts):
        return [self.VECTORS[t] for t in texts]

    def embed_query(self, text):
        return self.VECTORS[text]


@pytest.mark.integration
def test_both_vector_searches_score_higher_for_nearer_hits_and_keep_them_first(tmp_path):
    """Regression: langchain_chroma returns cosine distances from similarity_search_by_vector_with_relevance_scores,
    and stable_order once ranked the farthest of 40 hits first."""
    from rag.retriever import ChromaVectorSearch

    docs = [("bti:FAR", "far", {"code": "8714.91"}), ("bti:NEAR", "near", {"code": "8714.91"}),
            ("bti:MID", "mid", {"code": "8714.91"})]
    chroma = ChromaVectorSearch(tmp_path / "chroma", FixedEmbeddings(), "regression")
    chroma.add(docs)
    for vectors in (chroma, InMemoryVectorSearch(docs, FixedEmbeddings())):
        hits = vectors.search_by_vector([1.0, 0.0], 3, None, where={"code": "8714.91"})
        assert [doc_id for doc_id, _ in hits] == ["bti:NEAR", "bti:MID", "bti:FAR"], type(vectors).__name__
        assert hits[0][1] > hits[1][1] > hits[2][1], type(vectors).__name__        # relevance: higher is nearer
        assert stable_order(hits) == ["bti:NEAR", "bti:MID", "bti:FAR"], type(vectors).__name__


class CountingEmbeddings:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_queries(self, texts):
        self.calls.append(list(texts))
        return [[float(len(t)), float(len(self.calls))] for t in texts]


def test_the_same_normalised_text_is_embedded_once():
    emb = CountingEmbeddings()
    vectors = InMemoryVectorSearch([], emb)
    first = vectors.embed_query_cached("Bicycle  frames\nof aluminium")
    again = vectors.embed_query_cached("  Bicycle frames of aluminium ")      # whitespace and line breaks only
    other = vectors.embed_query_cached("BICYCLE frames of aluminium")         # case is kept: embedding models see it
    assert first == again != other
    assert emb.calls == [["Bicycle frames of aluminium"], ["BICYCLE frames of aluminium"]]   # the normalised text is embedded


def test_the_cache_keeps_the_most_recently_used_texts():
    emb = CountingEmbeddings()
    vectors = InMemoryVectorSearch([], emb)
    vectors.query_cache_size = 2
    for text in ("a", "b", "a", "c", "a", "b"):      # "b" falls out when "c" arrives; "a" stays in use
        vectors.embed_query_cached(text)
    assert emb.calls == [["a"], ["b"], ["c"], ["b"]]


def test_each_vector_search_keeps_its_own_cache():
    emb = CountingEmbeddings()
    one, two = InMemoryVectorSearch([], emb), InMemoryVectorSearch([], emb)
    one.embed_query_cached("frames")
    two.embed_query_cached("frames")
    assert emb.calls == [["frames"], ["frames"]]
