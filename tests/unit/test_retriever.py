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


class TestPrecedentCodes:
    """Precedent-driven retrieval: matching BTI rulings vote for their HS-6 code (research R-18)."""

    class _Vectors:
        def __init__(self, hits_per_query):
            self.hits = list(hits_per_query)

        def search_by_vector(self, vector, k, chapter_filter=None):
            return [(d, 1.0) for d in self.hits.pop(0)[:k]]

    @staticmethod
    def _store():
        from rag.bti import BTIStore

        return BTIStore([
            {"reference": "NL-1", "code": "3926.90", "member_state": "NL", "valid_from": "2024-01-01", "valid_to": "2027-01-01",
             "description": "Protective  case for a smartphone,   of silicone"},
            {"reference": "DE-2", "code": "3926.90", "member_state": "DE", "valid_from": "2024-01-01", "valid_to": "2027-01-01",
             "description": "Schutzhülle aus Silikon für Mobiltelefone"},
            {"reference": "DE-3", "code": "4202.32", "member_state": "DE", "valid_from": "2024-01-01", "valid_to": "2027-01-01",
             "description": "Etui für ein Mobiltelefon, sog. Bookcase"},
            {"reference": "FR-4", "code": "4202.32", "member_state": "FR", "valid_from": "2020-01-01", "valid_to": "2021-01-01",
             "description": "expired ruling"},
        ])

    def test_codes_backed_by_more_rulings_rank_first_and_keep_their_best_ruling(self):
        from rag.retriever import precedent_codes

        vectors = self._Vectors([["bti:DE-3", "bti:NL-1", "bti:DE-2"], ["bti:NL-1", "bti:DE-3", "bti:DE-2"]])
        out = precedent_codes(vectors, self._store(), [[0.1], [0.2]], k=3)
        assert [e["code"] for e in out] == ["3926.90", "4202.32"]
        assert out[0]["rulings"] == 2 and out[1]["rulings"] == 1
        assert out[0]["reference"] == "NL-1" and out[0]["member_state"] == "NL"
        assert out[0]["excerpt"] == "Protective case for a smartphone, of silicone"   # whitespace collapsed
        assert out[0]["score"] > out[1]["score"]

    def test_expired_and_unknown_rulings_are_skipped(self):
        from datetime import date

        from rag.retriever import precedent_codes

        vectors = self._Vectors([["bti:FR-4", "bti:XX-9", "bti:DE-3"]])
        out = precedent_codes(vectors, self._store(), [[0.1]], k=3, as_of=date(2026, 10, 16))
        assert [e["code"] for e in out] == ["4202.32"] and out[0]["rulings"] == 1 and out[0]["reference"] == "DE-3"
        without_date = precedent_codes(self._Vectors([["bti:FR-4", "bti:DE-3"]]), self._store(), [[0.1]], k=3)
        assert without_date[0]["rulings"] == 2      # validity is only enforced when a date is given

    def test_no_rulings_means_no_codes(self):
        from rag.retriever import precedent_codes

        assert precedent_codes(self._Vectors([[]]), self._store(), [[0.1]], k=3) == []
