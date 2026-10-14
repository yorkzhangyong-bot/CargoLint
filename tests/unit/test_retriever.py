"""Reciprocal rank fusion, BM25 tokenisation, hybrid/vector-only modes, index metadata guard (Principle IV)."""
import pytest

from rag.retriever import (
    BM25Index,
    HybridRetriever,
    IndexMismatchError,
    InMemoryVectorSearch,
    load_index_meta,
    rrf,
    tokenize,
    verify_index_meta,
    write_index_meta,
)

pytestmark = pytest.mark.unit


class TestRRF:
    def test_fuses_rankings_with_k_60(self):
        fused = rrf([["a", "b", "c"], ["a", "d", "b"]], k=60)
        ids = [i for i, _ in fused]
        assert ids == ["a", "b", "d", "c"]
        scores = dict(fused)
        assert scores["a"] == pytest.approx(2 / 61)
        assert scores["b"] == pytest.approx(1 / 62 + 1 / 63)

    def test_single_ranking_keeps_order(self):
        assert [i for i, _ in rrf([["x", "y"]])] == ["x", "y"]

    def test_empty_rankings(self):
        assert rrf([]) == [] and rrf([[], []]) == []


class TestTokenizer:
    def test_keeps_dotted_code_and_adds_compact_form(self):
        toks = tokenize("Vacuum flask 9617.00 (HS code)")
        assert "9617.00" in toks and "961700" in toks
        assert "vacuum" in toks and "flask" in toks
        assert all(t == t.lower() for t in toks)

    def test_compact_code_query_matches_too(self):
        assert "961700" in tokenize("961700")
        assert "9617.00" in tokenize("9617.00")


class TestBM25Index:
    def test_exact_code_query_ranks_the_code_first(self, small_index):
        idx = BM25Index([(c.id, c.text) for c in small_index.chunks])
        hits = idx.search("9617.00", k=3)
        assert hits[0][0] == "hs:9617.00"

    def test_keyword_query(self, small_index):
        idx = BM25Index([(c.id, c.text) for c in small_index.chunks])
        ids = [h[0] for h in idx.search("sewing machine parts", k=3)]
        assert "hs:8452.90" in ids

    def test_roundtrip_pickle(self, small_index, tmp_path):
        idx = BM25Index([(c.id, c.text) for c in small_index.chunks])
        p = tmp_path / "bm25.pkl"
        idx.save(p)
        again = BM25Index.load(p)
        assert again.search("9617.00", k=1)[0][0] == "hs:9617.00"


@pytest.fixture
def hybrid(small_index, fake_embeddings):
    bm25 = BM25Index([(c.id, c.text) for c in small_index.chunks])
    vectors = InMemoryVectorSearch([(c.id, c.text, c.metadata) for c in small_index.chunks], fake_embeddings)
    return HybridRetriever(bm25=bm25, vectors=vectors, chunks=small_index, k=6)


class TestHybridRetriever:
    def test_vector_only_mode_skips_bm25_and_reports_it(self, hybrid):
        chunks, trace = hybrid.search(["vacuum flask"], mode="vector_only")
        assert trace["mode"] == "vector_only"
        assert trace["bm25_hits"] == 0 and trace["vector_hits"] > 0
        assert len(chunks) >= 1

    def test_hybrid_mode_uses_both_and_fuses(self, hybrid):
        chunks, trace = hybrid.search(["9617.00 vacuum flask"], mode="hybrid")
        assert trace["mode"] == "hybrid"
        assert trace["bm25_hits"] > 0 and trace["vector_hits"] > 0
        assert trace["fused"] >= 1 and trace["sent_to_model"] == len(chunks)
        assert chunks[0].id == "hs:9617.00"
        assert "bm25" in chunks[0].ranks or "vector" in chunks[0].ranks

    def test_chapter_filter_restricts_results(self, hybrid):
        chunks, trace = hybrid.search(["parts"], chapter_filter=["84"], mode="hybrid")
        assert chunks and all(c.metadata["chapter"] == "84" for c in chunks)
        assert trace["chapter_filter"] == ["84"]


class TestIndexMeta:
    def test_mismatched_embedding_model_is_refused(self, tmp_path):
        write_index_meta(tmp_path, {"embedding_model": "qwen/qwen3-embedding-8b", "dimension": 4096, "built_at": "2026-10-14"})
        meta = load_index_meta(tmp_path)
        with pytest.raises(IndexMismatchError):
            verify_index_meta(meta, expected_model="openai/text-embedding-3-small", expected_dim=1536)
        with pytest.raises(IndexMismatchError):
            verify_index_meta(meta, expected_model="qwen/qwen3-embedding-8b", expected_dim=16)
        verify_index_meta(meta, expected_model="qwen/qwen3-embedding-8b", expected_dim=4096)

    def test_missing_meta_is_refused(self, tmp_path):
        with pytest.raises(IndexMismatchError):
            load_index_meta(tmp_path)
