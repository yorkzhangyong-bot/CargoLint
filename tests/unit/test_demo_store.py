"""Feature 011: the demo store. The choice of rulings, the cut from a full build without any API call, the archive, and
the fetch at first start (spec FR-001 … FR-008)."""
from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter

import pytest

from agent.config import ROOT
from rag.demo_store import (DemoStoreError, cut_demo_store, demo_store_needed, fetch_demo_store, pack, preferred_codes,
                            select_rulings)

pytestmark = pytest.mark.unit

DIM = 8
EVAL_CODES = {"3926.90", "4202.92"}
CODES = {"39": ["3926.90", "3924.10", "3923.10"], "42": ["4202.92", "4202.12", "4203.10"],
         "61": ["6109.10", "6110.20", "6104.62"]}


def _ruling(ref: str, chapter: str, code: str, text: bool = True) -> dict:
    return {"reference": ref, "chapter": chapter, "code": code, "cn_code": code.replace(".", "") + "00",
            "description": f"goods {ref}" if text else "", "reasoning": "", "member_state": "IE", "language": "en"}


def _rulings() -> list[dict]:
    """3 chapters × 3 HS-6 codes × 4 rulings; 3926.90 and 4202.92 are the eval set's codes."""
    return [_ruling(f"{code}-{i}", chapter, code) for chapter, codes in CODES.items() for code in codes for i in range(4)]


def _client(path):
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    return chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))


class TestSelection:
    def test_the_preferred_codes_are_the_eval_sets_and_every_sample_files(self):
        codes = preferred_codes()                           # the tracked eval set and data/samples/sample_lines.json
        eval_codes = {r["hs6"] for r in json.loads((ROOT / "tests" / "eval" / "cn8_eval_set.json")
                                                   .read_text(encoding="utf-8"))["rulings"]}
        assert eval_codes <= codes
        assert {"8518.30", "8543.70", "9405.21", "9617.00", "6109.10"} <= codes      # sample_packing_list.xlsx
        assert {"9405.11", "8504.40", "8518.22", "3924.90"} <= codes                 # sample_invoice_ningbo.csv
        assert {"9405.99", "9405.41", "8507.60", "8536.61"} <= codes                 # sample_packing_list_foshan.pdf
        assert None not in codes

    def test_every_preferred_code_gets_at_least_five_when_the_budget_allows(self):
        preferred = {f"85{i:02d}.30" for i in range(10)}
        records = [_ruling(f"{code}-{i}", "85", code) for code in sorted(preferred) for i in range(8)]
        records += [_ruling(f"8501.10-{i}", "85", "8501.10") for i in range(100)]
        chosen = Counter(r["code"] for r in select_rulings(records, preferred, 120))
        assert min(chosen[c] for c in preferred) >= 5

    def test_the_eval_codes_take_at_most_half_one_code_in_turn(self):
        chosen = select_rulings(_rulings(), EVAL_CODES, 10)
        assert len(chosen) == 10
        first = Counter(r["code"] for r in chosen if r["code"] in EVAL_CODES)
        assert sum(first.values()) == 5 and sorted(first.values()) == [2, 3]

    def test_the_rest_is_spread_over_the_chapters_one_code_in_turn(self):
        rest = [r for r in select_rulings(_rulings(), EVAL_CODES, 10) if r["code"] not in EVAL_CODES]
        per_chapter = Counter(r["chapter"] for r in rest)
        assert set(per_chapter) == set(CODES) and max(per_chapter.values()) - min(per_chapter.values()) <= 1
        assert len({r["code"] for r in rest}) == len(rest)        # no code twice before every code had one

    def test_the_choice_is_the_same_whatever_the_order_of_the_records(self):
        records = _rulings()
        once = [r["reference"] for r in select_rulings(records, EVAL_CODES, 10)]
        assert [r["reference"] for r in select_rulings(list(reversed(records)), EVAL_CODES, 10)] == once

    def test_rulings_without_text_are_never_chosen_and_a_large_request_takes_all(self):
        records = _rulings() + [_ruling("3923.10-blank", "39", "3923.10", text=False)]
        chosen = select_rulings(records, EVAL_CODES, 1000)
        assert len(chosen) == 36 and all(r["description"] for r in chosen)


@pytest.fixture
def full_build(tmp_path):
    """A tiny full build: store/ with a nomenclature folder, bm25.pkl, index_meta.json and a real Chroma collection of
    the rulings' vectors; the ruling extract, an eval set and a TARIC snapshot."""
    from rag.retriever import write_index_meta

    store = tmp_path / "full" / "store"
    (store / "chroma" / "segment").mkdir(parents=True)
    (store / "chroma" / "chroma.sqlite3").write_bytes(b"nomenclature index")
    (store / "chroma" / "segment" / "data_level0.bin").write_bytes(b"\x00\x01" * 8)
    (store / "bm25.pkl").write_bytes(b"bm25")
    write_index_meta(store, {"embedding_model": "test/embed", "dimension": DIM, "built_at": "2026-10-16T10:11:07+00:00",
                             "nomenclature_chunks": 3, "bti_rulings": 36, "edition_year": 2026})
    records = _rulings()
    vectors = {f"bti:{r['reference']}": [float((i * 7 + j) % 11) + 1.0 for j in range(DIM)] for i, r in enumerate(records)}
    with _client(store / "chroma-bti") as client:
        collection = client.get_or_create_collection("bti", embedding_function=None, metadata={"hnsw:space": "cosine"})
        collection.add(ids=list(vectors), embeddings=list(vectors.values()),
                       documents=[f"goods {r['reference']}" for r in records],
                       metadatas=[{"code": r["code"], "chapter": r["chapter"]} for r in records])
    data = tmp_path / "full" / "data"
    data.mkdir()
    (data / "bti_subset.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    (data / "taric.jsonl").write_text('{"kind":"snapshot"}\n', encoding="utf-8")
    eval_set = tmp_path / "full" / "eval_set.json"
    eval_set.write_text(json.dumps({"rulings": [{"hs6": code} for code in sorted(EVAL_CODES)]}), encoding="utf-8")
    sample_lines = tmp_path / "full" / "sample_lines.json"
    sample_lines.write_text(json.dumps({"lines": [{"expected_top_code": "6109.10"}, {"expected_top_code": None}]}),
                            encoding="utf-8")
    return {"store_dir": store, "bti_path": data / "bti_subset.jsonl", "eval_set": eval_set,
            "sample_lines": sample_lines, "taric": data / "taric.jsonl", "vectors": vectors}


def _sources(build: dict) -> dict:
    return {k: build[k] for k in ("store_dir", "bti_path", "eval_set", "sample_lines", "taric")}


class TestCut:
    def test_the_indexes_are_copied_and_the_chosen_rulings_keep_their_vectors(self, full_build, tmp_path):
        out = tmp_path / "demo"
        summary = cut_demo_store(out, 10, **_sources(full_build))
        store = out / "store"
        assert (store / "chroma" / "chroma.sqlite3").read_bytes() == b"nomenclature index"
        assert (store / "chroma" / "segment" / "data_level0.bin").read_bytes() == b"\x00\x01" * 8
        assert (store / "bm25.pkl").read_bytes() == b"bm25"
        assert (out / "data" / "taric.jsonl").read_text(encoding="utf-8") == '{"kind":"snapshot"}\n'
        docs = [json.loads(line) for line in (store / "bti_docs.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(docs) == summary["rulings"] == 10 and summary["missing"] == 0
        meta = json.loads((store / "index_meta.json").read_text(encoding="utf-8"))
        assert (meta["bti_rulings"], meta["nomenclature_chunks"], meta["embedding_model"], meta["dimension"]) == (
            10, 3, "test/embed", DIM)
        assert meta["built_at"] == "2026-10-16T10:11:07+00:00"
        with _client(store / "chroma-bti") as client:
            collection = client.get_collection("bti", embedding_function=None)
            got = collection.get(include=["embeddings"])
            space = (collection.metadata or {}).get("hnsw:space")
        assert sorted(got["ids"]) == sorted(f"bti:{d['reference']}" for d in docs)
        for ruling_id, vector in zip(got["ids"], got["embeddings"]):
            assert list(vector) == pytest.approx(full_build["vectors"][ruling_id])
        assert space == "cosine"

    def test_the_samples_codes_are_preferred_like_the_eval_sets(self, full_build, tmp_path):
        summary = cut_demo_store(tmp_path / "demo", 10, **_sources(full_build))
        docs = (tmp_path / "demo" / "store" / "bti_docs.jsonl").read_text(encoding="utf-8")
        assert summary["under_preferred_codes"] == 5 and '"code": "6109.10"' in docs

    def test_a_ruling_whose_vector_is_missing_is_dropped_and_counted(self, full_build, tmp_path):
        with _client(full_build["store_dir"] / "chroma-bti") as client:
            client.get_collection("bti", embedding_function=None).delete(ids=["bti:3923.10-0"])
        summary = cut_demo_store(tmp_path / "demo", 1000, **_sources(full_build))
        assert (summary["rulings"], summary["missing"]) == (35, 1)
        docs = (tmp_path / "demo" / "store" / "bti_docs.jsonl").read_text(encoding="utf-8")
        assert "3923.10-0" not in docs

    def test_an_incomplete_full_build_is_refused_before_anything_is_written(self, full_build, tmp_path):
        (full_build["store_dir"] / "index_meta.json").unlink()
        out = tmp_path / "demo"
        with pytest.raises(DemoStoreError, match="index_meta.json"):
            cut_demo_store(out, 10, **_sources(full_build))
        assert not out.exists()

    def test_a_folder_that_is_not_empty_is_refused(self, full_build, tmp_path):
        out = tmp_path / "demo"
        out.mkdir()
        (out / "keep.txt").write_text("x", encoding="utf-8")
        with pytest.raises(DemoStoreError, match="not empty"):
            cut_demo_store(out, 10, **_sources(full_build))
        assert [p.name for p in out.iterdir()] == ["keep.txt"]

    def test_the_archive_holds_the_store_and_taric_and_reports_its_checksum(self, full_build, tmp_path):
        out = tmp_path / "demo"
        cut_demo_store(out, 10, **_sources(full_build))
        archive = tmp_path / "demo.zip"
        digest, size = pack(out, archive)
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
        assert "store/index_meta.json" in names and "store/chroma/chroma.sqlite3" in names and "data/taric.jsonl" in names
        assert all(n.startswith("store/") or n == "data/taric.jsonl" for n in names)
        assert (digest, size) == (hashlib.sha256(archive.read_bytes()).hexdigest(), archive.stat().st_size)


GOOD = {"store/bm25.pkl": b"bm25", "store/chroma/chroma.sqlite3": b"db", "data/taric.jsonl": b"{}\n",
        "store/index_meta.json": b'{"embedding_model": "test/embed"}'}


def _archive(tmp_path, entries: dict[str, bytes]) -> tuple[str, str]:
    path = tmp_path / "demo.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return path.as_uri(), hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    return path


class TestFetch:
    def test_a_verified_archive_is_unpacked_into_the_root(self, tmp_path, root):
        url, sha = _archive(tmp_path, GOOD)
        assert demo_store_needed(url, root)
        fetch_demo_store(url, sha.upper(), root)                     # the checksum's case does not matter
        assert (root / "store" / "index_meta.json").read_bytes() == GOOD["store/index_meta.json"]
        assert (root / "store" / "chroma" / "chroma.sqlite3").read_bytes() == b"db"
        assert (root / "data" / "taric.jsonl").read_bytes() == b"{}\n"
        assert not demo_store_needed(url, root)

    def test_a_wrong_checksum_unpacks_nothing(self, tmp_path, root):
        url, _ = _archive(tmp_path, GOOD)
        with pytest.raises(DemoStoreError, match="SHA-256"):
            fetch_demo_store(url, "0" * 64, root)
        assert not any(root.iterdir())

    def test_a_missing_checksum_unpacks_nothing(self, tmp_path, root):
        url, _ = _archive(tmp_path, GOOD)
        with pytest.raises(DemoStoreError, match="CARGOLINT_DEMO_STORE_SHA256"):
            fetch_demo_store(url, "", root)
        assert not any(root.iterdir())

    def test_an_archive_without_the_index_meta_is_refused(self, tmp_path, root):
        url, sha = _archive(tmp_path, {k: v for k, v in GOOD.items() if k != "store/index_meta.json"})
        with pytest.raises(DemoStoreError, match="index_meta.json"):
            fetch_demo_store(url, sha, root)
        assert not any(root.iterdir())

    @pytest.mark.parametrize("name", ["app.py", "../outside.txt", "data/other.jsonl", "store/../app.py"])
    def test_an_archive_with_another_path_is_refused(self, tmp_path, root, name):
        url, sha = _archive(tmp_path, {**GOOD, name: b"x"})
        with pytest.raises(DemoStoreError, match="unexpected"):
            fetch_demo_store(url, sha, root)
        assert not any(root.iterdir())

    def test_an_unreachable_archive_is_a_clear_error(self, tmp_path, root):
        with pytest.raises(DemoStoreError, match="could not be downloaded"):
            fetch_demo_store((tmp_path / "missing.zip").as_uri(), "0" * 64, root)

    def test_nothing_is_fetched_without_a_url_or_with_a_store(self, root):
        assert not demo_store_needed("", root)
        (root / "store").mkdir()
        (root / "store" / "index_meta.json").write_text("{}", encoding="utf-8")
        assert not demo_store_needed("https://example.org/demo.zip", root)
