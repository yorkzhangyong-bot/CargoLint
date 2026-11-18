"""Feature 013, User Story 2: the EBTI refresh end to end on a tiny extract, a tiny previous store (a real Chroma
collection of 8-dimensional vectors, the `full_build` pattern of tests/unit/test_demo_store.py), fake embeddings that
record what they embed, and the fake release service (contracts/refresh-cli.md; spec FR-006 to FR-012). The
repository's store/, data/bti_subset.jsonl and data/raw/ are monkeypatched to paths that must stay untouched."""
from __future__ import annotations

import csv
import io
import json
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import rag.loader as loader
import rag.refresh_ebti as re_
from agent.config import get_settings
from rag.bti import BTIStore, row_to_ruling, ruling_text, write_jsonl
from rag.nomenclature import NomenclatureIndex
from rag.embeddings import FakeEmbeddings
from rag.refresh import read_metadata, sha256
from rag.retriever import write_index_meta
from tests.fakes import FakeReleaseService

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
DIM = 8
CHUNKS = len(NomenclatureIndex.from_jsonl(FIXTURES / "cn2026_excerpt.jsonl"))   # the "committed" nomenclature of the tests
DATE = "2026-11-12"
NAME = f"ebti-{DATE}"
ARCHIVE = f"cargolint-ebti-{DATE}.zip"
SOURCE_VERSION = f"full extract of {DATE}, chapters 39,42,61-64,73,84,85,94,95,96"
COLUMNS = ["BTI_REFERENCE", "ISSUING_COUNTRY", "START_DATE_OF_VALIDITY", "END_DATE_OF_VALIDITY", "NOMENCLATURE_CODE",
           "CLASSIFICATION_JUSTIFICATION", "STATUS", "INVALIDATION_REASON", "INVALIDATION_JUSTIFICATION", "LANGUAGE",
           "PLACE_OF_ISSUE", "DATE_OF _ISSUE", "NAME_AND_ADDRESS", "DESCRIPTION_OF_GOODS", "KEYWORDS"]


def row(ref: str, code: str = "8452900000************", description: str = "Steel bobbin cases for sewing machines",
        reasoning: str = "GIR 1 and 6", end: str = "2027-01-09", status: str = "Valid") -> dict:
    return {"BTI_REFERENCE": ref, "ISSUING_COUNTRY": ref[:2], "START_DATE_OF_VALIDITY": "2024-01-10",
            "END_DATE_OF_VALIDITY": end, "NOMENCLATURE_CODE": code, "CLASSIFICATION_JUSTIFICATION": reasoning,
            "STATUS": status, "INVALIDATION_REASON": "", "INVALIDATION_JUSTIFICATION": "", "LANGUAGE": "EN",
            "PLACE_OF_ISSUE": "Hannover", "DATE_OF _ISSUE": "2024-01-10", "NAME_AND_ADDRESS": "Some Company GmbH",
            "DESCRIPTION_OF_GOODS": description, "KEYWORDS": "sewing"}


# The previous store's six rulings as they were, and the extract as it is now: P1 and P6 unchanged, P2 with a new code,
# P3 with a new text, P4 expired, P5 withdrawn; N1 to N3 new.
PREVIOUS_ROWS = [row("DE-P1"), row("DE-P2"), row("DE-P3"), row("DE-P4"), row("DE-P5"), row("FR-P6", code="9617000000************",
                                                                                           description="Vacuum flasks")]
EXTRACT_ROWS = [row("DE-P1"), row("DE-P2", code="8452300000************"), row("DE-P3", description="Bobbin cases, steel"),
                row("DE-P4", end="2025-12-31"), row("DE-P5", status="Invalidated"),
                row("FR-P6", code="9617000000************", description="Vacuum flasks"),
                row("NL-N1"), row("IT-N2", code="9617000000************", description="Vacuum jugs"),
                row("ES-N3", code="8452300000************", description="Needle plates")]
VALID = ["DE-P1", "DE-P2", "DE-P3", "ES-N3", "FR-P6", "IT-N2", "NL-N1"]


def extract_zip(path: Path, rows: list[dict], stamp=(2026, 11, 12, 4, 44, 0)) -> Path:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("EBTI_2026.csv", date_time=stamp), buf.getvalue().encode("utf-8"))
    return path


def chroma(path: Path):
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    return chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))


def vector(k: int) -> list[float]:
    return [1.0 + float((k * 7 + j) % 11) for j in range(DIM)]


def make_previous(folder: Path, rows: list[dict] = PREVIOUS_ROWS, model: str = "fake-hash-8", chunks: int = CHUNKS,
                  year: int = 2026) -> tuple[Path, dict[str, list[float]]]:
    """A tiny store in demo-store-v1's layout under <folder>/store: fake nomenclature files, a real ruling collection."""
    store = folder / "store"
    (store / "chroma" / "segment").mkdir(parents=True)
    (store / "chroma" / "chroma.sqlite3").write_bytes(b"nomenclature index")
    (store / "chroma" / "segment" / "data_level0.bin").write_bytes(b"\x00\x01" * 8)
    (store / "bm25.pkl").write_bytes(b"bm25")
    records = [row_to_ruling(r) for r in rows]
    write_index_meta(store, {"embedding_model": model, "dimension": DIM, "built_at": "2026-10-16T10:11:07+00:00",
                             "nomenclature_chunks": chunks, "bti_rulings": len(records), "edition_year": year,
                             "embedding_usage": {"total_tokens": 99}, "demo_store": {"cut_at": "2026-10-27"}})
    texts = BTIStore(records).chunk_texts()
    vectors = {ruling_id: vector(k) for k, (ruling_id, _, _) in enumerate(texts)}
    with chroma(store / "chroma-bti") as client:
        collection = client.get_or_create_collection("bti", embedding_function=None, metadata={"hnsw:space": "cosine"})
        collection.add(ids=list(vectors), embeddings=list(vectors.values()), documents=[t for _, t, _ in texts],
                       metadatas=[{**m, "id": i} for i, _, m in texts])
    write_jsonl(records, store / "bti_docs.jsonl")
    return folder, vectors


def pack_store(folder: Path, archive: Path, with_taric: bool = False) -> Path:
    with zipfile.ZipFile(archive, "w") as z:
        for p in sorted((folder / "store").rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(folder).as_posix())
        if with_taric:
            z.writestr("data/taric.jsonl", '{"kind":"snapshot"}\n')
    return archive


def signature(root: Path) -> list:
    return sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob("*") if p.is_file())


class RecordingEmbeddings(FakeEmbeddings):
    def __init__(self) -> None:
        super().__init__(dim=DIM)
        self.seen: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.seen.extend(texts)
        return super().embed_documents(texts)


@pytest.fixture
def world(tmp_path, monkeypatch):
    repo = tmp_path / "repo"                                   # the repository's own paths: must stay untouched
    (repo / "store").mkdir(parents=True)
    (repo / "store" / "bti_docs.jsonl").write_bytes(b"the local full build\n")
    (repo / "data" / "raw").mkdir(parents=True)
    (repo / "data" / "raw" / "DDS2-EBTI_Full.zip").write_bytes(b"the loader's own download")
    (repo / "data" / "bti_subset.jsonl").write_bytes(b"the loader's subset\n")
    monkeypatch.setattr(loader, "STORE_DIR", repo / "store")
    monkeypatch.setattr(loader, "BTI_SUBSET", repo / "data" / "bti_subset.jsonl")
    monkeypatch.setattr(loader, "SUBSET_META", repo / "data" / "bti_subset.meta.json")
    monkeypatch.setattr(loader, "RAW_DIR", repo / "data" / "raw")
    monkeypatch.setattr(loader, "NOMENCLATURE_JSONL", FIXTURES / "cn2026_excerpt.jsonl")   # CHUNKS chunks, edition 2026
    build = tmp_path / "build"
    monkeypatch.setattr(re_, "WORK_DIR", build)
    monkeypatch.setattr(re_, "EXTRACT_ZIP", build / "DDS2-EBTI_Full.zip")
    monkeypatch.setenv("CARGOLINT_EMBED_MODEL", "fake-hash-8")
    monkeypatch.delenv("CARGOLINT_EBTI_RULINGS", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    previous, vectors = make_previous(tmp_path / "prev")
    w = SimpleNamespace(repo=repo, build=build, extract=extract_zip(tmp_path / "extract.zip", EXTRACT_ROWS),
                        previous=previous, vectors=vectors, service=FakeReleaseService(), emb=RecordingEmbeddings(),
                        out=tmp_path / "out", before=signature(repo))
    yield w
    get_settings.cache_clear()
    assert signature(repo) == w.before                         # store/, bti_subset.jsonl and data/raw/ as they were


def run(w, *extra: str, extract: bool = True, previous: bool = True, out: bool = True, embeddings: bool = True) -> int:
    argv = list(extra)
    if extract:
        argv += ["--extract", str(w.extract)]
    if previous:
        argv += ["--previous", str(w.previous)]
    if out:
        argv += ["--out", str(w.out)]
    return re_.main(argv, embeddings=w.emb if embeddings else None, service=w.service)


def collection_of(store: Path, langchain: bool = False) -> dict:
    """The ruling collection's content; `langchain` reads it as the app does (the loader's --full-embed build opened it
    with langchain's client settings, and chromadb allows one setting per path in a process)."""
    if langchain:
        from rag.retriever import ChromaVectorSearch

        got = ChromaVectorSearch(store / "chroma-bti", FakeEmbeddings(dim=DIM), "bti").store._collection.get(
            include=["embeddings", "documents", "metadatas"])
    else:
        with chroma(store / "chroma-bti") as client:
            got = client.get_collection("bti", embedding_function=None).get(include=["embeddings", "documents", "metadatas"])
    return {i: (list(v), d, m) for i, v, d, m in zip(got["ids"], got["embeddings"], got["documents"], got["metadatas"])}


def complete(kind: str, day: str) -> dict:
    return {"assets": [f"cargolint-{kind}-{day}.zip", "metadata.json"]}


class SneakyService(FakeReleaseService):
    """Adds a TARIC release between the "nothing new" check and the listing read before the metadata is written."""

    def list(self) -> list[dict]:
        if len(self.calls_of("list")) == 1:
            self.add("taric-2026-11-02", **complete("taric", "2026-11-02"))
        return super().list()


class TestBuild:
    def test_the_store_reuses_the_previous_vectors_and_embeds_only_new_and_changed_rulings(self, world, capsys):
        assert run(world) == 0
        out = capsys.readouterr().out
        store = world.out / "store"
        assert (store / "bm25.pkl").read_bytes() == b"bm25"                                   # copied unchanged
        assert (store / "chroma" / "chroma.sqlite3").read_bytes() == b"nomenclature index"
        assert (store / "chroma" / "segment" / "data_level0.bin").read_bytes() == b"\x00\x01" * 8
        docs = [json.loads(line) for line in (store / "bti_docs.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [d["reference"] for d in docs] == VALID                                        # P4 and P5 are gone
        vectors = collection_of(store)
        assert sorted(vectors) == [f"bti:{r}" for r in VALID]
        for ruling_id in ("bti:DE-P1", "bti:DE-P2", "bti:FR-P6"):                           # kept: the vectors copied
            assert vectors[ruling_id][0] == pytest.approx(world.vectors[ruling_id])
        assert vectors["bti:DE-P2"][2]["code"] == "8452.30" and vectors["bti:DE-P2"][2]["cn_code"] == "8452300000"
        assert vectors["bti:DE-P2"][2]["id"] == "bti:DE-P2" and vectors["bti:DE-P1"][2]["code"] == "8452.90"
        embedded = {d["reference"]: d for d in docs if d["reference"] in ("DE-P3", "NL-N1", "IT-N2", "ES-N3")}
        assert sorted(world.emb.seen) == sorted(ruling_text(d) for d in embedded.values())    # only new and changed
        for ref, d in embedded.items():
            assert vectors[f"bti:{ref}"][0] == pytest.approx(world.emb.embed_query(ruling_text(d)))
        meta = json.loads((store / "index_meta.json").read_text(encoding="utf-8"))
        assert (meta["embedding_model"], meta["dimension"], meta["nomenclature_chunks"], meta["edition_year"]) == ("fake-hash-8", DIM, CHUNKS, 2026)
        assert meta["built_at"] != "2026-10-16T10:11:07+00:00" and meta["bti_rulings"] == 7
        assert meta["embedding_usage"]["total_tokens"] == 0 and "demo_store" not in meta
        assert (meta["ebti_snapshot_date"], meta["ebti_source_version"]) == (DATE, SOURCE_VERSION)
        assert meta["refresh"] == {"rulings_requested": 5000, "extract_rulings": 7, "reused": 3, "embedded": 4, "dropped": 2,
                                   "vectors_from": "folder", "full_embed": False}
        archive = world.out / ARCHIVE
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
        assert all(n.startswith("store/") for n in names) and "store/index_meta.json" in names and "data/taric.jsonl" not in names
        metadata = read_metadata(world.out / "metadata.json")
        assert (metadata["kind"], metadata["release"], metadata["snapshot_date"]) == ("ebti", NAME, DATE)
        assert metadata["source"] == loader.SOURCES["ebti"]["url"] and metadata["source_version"] == SOURCE_VERSION
        assert (metadata["sha256"], metadata["size"]) == (sha256(archive), archive.stat().st_size)
        assert metadata["entries"] == ["store/"] and metadata["embedding_model"] == "fake-hash-8"
        assert {k: metadata[k] for k in ("rulings", "extract_rulings", "reused", "embedded", "dropped", "vectors_from")} == {
            "rulings": 7, "extract_rulings": 7, "reused": 3, "embedded": 4, "dropped": 2, "vectors_from": "folder"}
        assert metadata["current"] == {"ebti": [NAME], "taric": []}
        assert world.service.latest_name == NAME and world.service.releases[NAME]["assets"] == [ARCHIVE, "metadata.json"]
        assert f"[refresh] extract extract.zip dated {DATE}, 7 valid rulings in 12 chapters" in out
        assert "[refresh] chose 7 rulings: 4 kept, 3 new; 1 changed texts; 2 dropped from the previous store" in out
        assert "[refresh] copied the nomenclature index and 3 ruling vectors; embedded 4 rulings ($0.000)" in out
        assert f"[refresh] published {NAME} (2 assets), marked latest" in out
        assert any(line.startswith(f"EBTI refresh: {NAME} published in ") for line in out.splitlines())
        assert not (world.build / "DDS2-EBTI_Full.zip").exists()                             # --extract: no download

    def test_the_extract_is_downloaded_afresh(self, world, monkeypatch):
        world.build.mkdir()
        target = world.build / "DDS2-EBTI_Full.zip"
        target.write_bytes(b"yesterday's extract")
        target.with_suffix(".zip.part").write_bytes(b"a partial download")
        asked: list[str] = []

        def download(url, dest, *args, **kwargs):
            asked.append(url)
            assert dest == target and not dest.exists() and not dest.with_suffix(".zip.part").exists()
            shutil.copy2(world.extract, dest)
            return dest

        monkeypatch.setattr(loader, "download", download)
        assert run(world, extract=False) == 0
        assert asked == [re_.EXTRACT_URL] and target.read_bytes() == world.extract.read_bytes()
        assert (world.repo / "data" / "raw" / "DDS2-EBTI_Full.zip").read_bytes() == b"the loader's own download"

    def test_a_reused_ruling_whose_vector_is_missing_is_embedded_instead(self, world):
        with chroma(world.previous / "store" / "chroma-bti") as client:
            client.get_collection("bti", embedding_function=None).delete(ids=["bti:DE-P1"])
        assert run(world) == 0
        meta = json.loads((world.out / "store" / "index_meta.json").read_text(encoding="utf-8"))
        assert (meta["refresh"]["reused"], meta["refresh"]["embedded"]) == (2, 5)
        assert collection_of(world.out / "store")["bti:DE-P1"][0] == pytest.approx(
            world.emb.embed_query("Steel bobbin cases for sewing machines\nGIR 1 and 6"))


class TestNothingNew:
    @pytest.mark.parametrize("existing", [NAME, "ebti-2026-12-01"])
    def test_a_complete_release_of_the_date_or_newer_is_nothing_new(self, world, capsys, existing):
        world.service = FakeReleaseService({"ebti-2026-08-01": complete("ebti", "2026-08-01"),
                                            "ebti-2026-09-01": complete("ebti", "2026-09-01"),
                                            existing: complete("ebti", existing[5:])}, latest="ebti-2026-08-01")
        (world.build / NAME).mkdir(parents=True)                       # the default work folder left non-empty
        (world.build / NAME / "stale.txt").write_text("x", encoding="utf-8")
        assert run(world, previous=False, out=False) == 0
        out = capsys.readouterr().out
        assert f"EBTI refresh: {existing} is already published and complete; nothing new. Use --force to rebuild and replace it." in out
        assert [c[0] for c in world.service.calls] == ["check", "list", "delete", "latest", "mark_latest"]
        assert sorted(world.service.names) == sorted(["ebti-2026-09-01", existing]) and world.service.latest_name == existing
        assert world.emb.seen == [] and not world.out.exists() and (world.build / NAME / "stale.txt").exists()

    def test_a_nothing_new_run_whose_prune_fails_exits_3(self, world, capsys):
        world.service = FakeReleaseService({"ebti-2026-08-01": complete("ebti", "2026-08-01"),
                                            "ebti-2026-09-01": complete("ebti", "2026-09-01"), NAME: complete("ebti", DATE)})
        world.service.fail_at("delete", "gh: HTTP 502 (simulated)")
        assert run(world) == 3
        assert capsys.readouterr().err.startswith("EBTI refresh failed: the release service failed at the prune of ebti-2026-08-01")


class TestPublish:
    @pytest.mark.parametrize("remnant", [{"assets": [ARCHIVE], "draft": True}, {"assets": ["metadata.json"]}])
    def test_an_incomplete_release_of_the_date_is_deleted_and_published_afresh(self, world, remnant):
        world.service = FakeReleaseService({NAME: remnant})
        assert run(world) == 0
        calls = [c[0] for c in world.service.calls]
        assert calls.index("delete") < calls.index("create") and world.service.calls_of("delete") == [("delete", NAME)]
        assert world.service.releases[NAME]["draft"] is False and world.service.releases[NAME]["assets"] == [ARCHIVE, "metadata.json"]

    def test_force_rebuilds_deletes_and_recreates_with_current_from_a_fresh_listing(self, world):
        world.service = SneakyService({NAME: complete("ebti", DATE)}, latest=NAME)
        assert run(world, "--force") == 0
        calls = [c[0] for c in world.service.calls]
        assert calls[calls.index("delete") - 1] == "list"                  # re-read right before the release is replaced
        assert calls.index("delete") < calls.index("create") < calls.index("mark_latest")
        assert "upload" not in calls and world.service.calls_of("delete") == [("delete", NAME)]
        assert read_metadata(world.out / "metadata.json")["current"] == {"ebti": [NAME], "taric": ["taric-2026-11-02"]}

    def test_a_failing_create_is_exit_3_naming_the_step_and_what_was_deleted(self, world, capsys):
        world.service = FakeReleaseService({NAME: {"assets": [ARCHIVE]}})
        world.service.fail_at("create", "gh: HTTP 500 (simulated)")
        assert run(world) == 3
        err = capsys.readouterr().err
        assert err.startswith(f"EBTI refresh failed: the release service failed at the create of {NAME}: gh: HTTP 500")
        assert err.rstrip().endswith(f"before that it deleted the incomplete {NAME}")

    def test_retention_keeps_the_two_newest_complete_ebti_releases(self, world):
        world.service = FakeReleaseService({"ebti-2026-09-01": complete("ebti", "2026-09-01"),
                                            "ebti-2026-08-01": complete("ebti", "2026-08-01"),
                                            "ebti-2026-09-15": {"assets": ["cargolint-ebti-2026-09-15.zip"]},
                                            "taric-2026-11-02": complete("taric", "2026-11-02"),
                                            "demo-store-v1": {"assets": ["cargolint-demo-store-v1.zip"]}})
        assert run(world) == 0
        assert sorted(world.service.names) == ["demo-store-v1", "ebti-2026-09-01", NAME, "taric-2026-11-02"]
        assert read_metadata(world.out / "metadata.json")["current"] == {"ebti": [NAME, "ebti-2026-09-01"], "taric": ["taric-2026-11-02"]}

    def test_no_publish_builds_without_the_service_for_a_local_previous_store(self, world, capsys):
        assert run(world, "--no-publish") == 0
        assert world.service.calls == [] and (world.out / ARCHIVE).exists()
        assert read_metadata(world.out / "metadata.json")["current"] == {"ebti": [NAME], "taric": []}
        assert f"EBTI refresh: {NAME} built in" in capsys.readouterr().out


class TestPreviousStore:
    def test_another_embedding_model_exits_2_naming_full_embed(self, world, capsys):
        shutil.rmtree(world.previous)
        make_previous(world.previous, model="other/model")
        assert run(world) == 2
        err = capsys.readouterr().err
        assert "other/model" in err and "--full-embed" in err and world.emb.seen == [] and world.service.names == []

    @pytest.mark.parametrize("missing", ["chroma-bti", "bti_docs.jsonl"])
    def test_an_incomplete_previous_store_exits_2_before_any_embedding(self, world, capsys, missing):
        path = world.previous / "store" / missing
        shutil.rmtree(path) if path.is_dir() else path.unlink()
        assert run(world) == 2
        assert f"lacks {missing}" in capsys.readouterr().err and world.emb.seen == []

    def test_another_nomenclature_exits_2_naming_full_embed(self, world, capsys):
        shutil.rmtree(world.previous)
        make_previous(world.previous, chunks=5600)
        assert run(world) == 2
        assert "--full-embed" in capsys.readouterr().err and world.emb.seen == []

    def test_full_embed_embeds_every_chunk_and_ruling_and_copies_nothing(self, world):
        shutil.rmtree(world.previous)
        make_previous(world.previous, model="other/model")
        assert run(world, "--full-embed") == 0
        store = world.out / "store"
        chunk_texts = [c.text for c in NomenclatureIndex.from_jsonl(loader.NOMENCLATURE_JSONL).chunks]
        docs = [json.loads(line) for line in (store / "bti_docs.jsonl").read_text(encoding="utf-8").splitlines()]
        assert sorted(world.emb.seen) == sorted(chunk_texts + [ruling_text(d) for d in docs]) and len(docs) == 7
        assert (store / "chroma" / "chroma.sqlite3").read_bytes() != b"nomenclature index"     # a real index, not a copy
        meta = json.loads((store / "index_meta.json").read_text(encoding="utf-8"))
        assert (meta["embedding_model"], meta["dimension"], meta["nomenclature_chunks"], meta["edition_year"]) == ("fake-hash-8", DIM, CHUNKS, 2026)
        assert meta["refresh"] == {"rulings_requested": 5000, "extract_rulings": 7, "reused": 0, "embedded": 7, "dropped": 2,
                                   "vectors_from": "folder", "full_embed": True}
        assert sorted(collection_of(store, langchain=True)) == [f"bti:{r}" for r in VALID]

    def test_no_previous_store_and_no_full_embed_exits_2_naming_the_two_ways(self, world, capsys):
        assert run(world, previous=False) == 2
        err = capsys.readouterr().err
        assert "--previous demo-store-v1" in err and "--full-embed" in err and world.emb.seen == []
        assert not world.out.exists() or not any(world.out.iterdir())

    def test_a_previous_release_is_downloaded_and_verified(self, world, tmp_path):
        archive = pack_store(world.previous, tmp_path / "cargolint-ebti-2026-10-14.zip")
        metadata = tmp_path / "metadata.json"
        metadata.write_text(json.dumps({"kind": "ebti", "release": "ebti-2026-10-14", "archive": archive.name,
                                        "sha256": sha256(archive)}), encoding="utf-8")
        world.service = FakeReleaseService({"ebti-2026-10-14": {**complete("ebti", "2026-10-14"),
                                                                "files": {archive.name: archive, "metadata.json": metadata}}})
        assert run(world, previous=False) == 0                     # the newest complete EBTI release is the default
        assert (world.out / "previous" / "store" / "bti_docs.jsonl").exists()
        assert world.service.calls_of("download") == [("download", "ebti-2026-10-14", "*", str(world.out / "previous"))]
        meta = json.loads((world.out / "store" / "index_meta.json").read_text(encoding="utf-8"))
        assert meta["refresh"]["vectors_from"] == "ebti-2026-10-14" and meta["refresh"]["reused"] == 3
        assert read_metadata(world.out / "metadata.json")["vectors_from"] == "ebti-2026-10-14"

    def test_a_previous_release_whose_checksum_differs_exits_2(self, world, tmp_path, capsys):
        archive = pack_store(world.previous, tmp_path / "cargolint-ebti-2026-10-14.zip")
        metadata = tmp_path / "metadata.json"
        metadata.write_text(json.dumps({"kind": "ebti", "release": "ebti-2026-10-14", "archive": archive.name, "sha256": "0" * 64}),
                            encoding="utf-8")
        world.service = FakeReleaseService({"ebti-2026-10-14": {**complete("ebti", "2026-10-14"),
                                                                "files": {archive.name: archive, "metadata.json": metadata}}})
        assert run(world, "--previous", "ebti-2026-10-14", previous=False) == 2
        assert "SHA-256" in capsys.readouterr().err and world.emb.seen == []

    def test_demo_store_v1_is_unpacked_as_it_is_with_a_note(self, world, tmp_path, capsys):
        archive = pack_store(world.previous, tmp_path / "cargolint-demo-store-v1.zip", with_taric=True)
        world.service = FakeReleaseService({"demo-store-v1": {"assets": [archive.name], "files": {archive.name: archive}}})
        assert run(world, "--previous", "demo-store-v1", previous=False) == 0
        out = capsys.readouterr().out
        assert "previous store demo-store-v1 has no metadata.json" in out
        assert (world.out / "previous" / "store" / "index_meta.json").exists() and not (world.out / "previous" / "data").exists()
        assert read_metadata(world.out / "metadata.json")["vectors_from"] == "demo-store-v1"

    def test_a_previous_release_needs_gh_also_with_no_publish(self, world, capsys):
        world.service.fail_at("check", "gh not found")
        assert run(world, "--no-publish", "--previous", "ebti-2026-10-14", previous=False) == 2
        assert capsys.readouterr().err.startswith("EBTI refresh not started: the release service is not available")
        assert world.service.calls == [("check",)]


class TestOptions:
    def test_the_default_work_folder_is_refused_when_not_empty_and_emptied_by_force(self, world, capsys):
        folder = world.build / NAME
        folder.mkdir(parents=True)
        (folder / "stale.txt").write_text("x", encoding="utf-8")
        assert run(world, out=False) == 2
        err = capsys.readouterr().err
        assert f"build/{NAME}" in err or str(folder) in err
        assert "--force" in err and "--out" in err and (folder / "stale.txt").exists() and world.emb.seen == []
        assert run(world, "--force", out=False) == 0
        assert not (folder / "stale.txt").exists() and (folder / ARCHIVE).exists()

    def test_a_given_out_folder_is_never_emptied(self, world, capsys):
        world.out.mkdir()
        (world.out / "keep.txt").write_text("x", encoding="utf-8")
        for extra in ((), ("--force",)):
            assert run(world, *extra) == 2
            assert "new or empty" in capsys.readouterr().err and [p.name for p in world.out.iterdir()] == ["keep.txt"]

    def test_a_missing_key_exits_2_before_any_download(self, world, monkeypatch, capsys):
        monkeypatch.setattr(loader, "download", lambda *a, **k: pytest.fail("no download before the key check"))
        assert run(world, extract=False, embeddings=False) == 2
        assert "OPENROUTER_API_KEY" in capsys.readouterr().err

    def test_the_bound_from_the_option_keeps_the_previous_rulings_first(self, world):
        assert run(world, "--rulings", "4") == 0
        docs = [json.loads(line) for line in (world.out / "store" / "bti_docs.jsonl").read_text(encoding="utf-8").splitlines()]
        refs = [d["reference"] for d in docs]
        assert refs == ["DE-P1", "DE-P2", "FR-P6", "IT-N2"]            # the kept rulings first within each code; without
                                                                        # keep the same choice is ES-N3, FR-P6, IT-N2, NL-N1
        meta = json.loads((world.out / "store" / "index_meta.json").read_text(encoding="utf-8"))
        assert meta["refresh"]["rulings_requested"] == 4 and meta["bti_rulings"] == 4

    @pytest.mark.parametrize("how", ["option", "setting"])
    def test_all_keeps_every_valid_ruling(self, world, monkeypatch, how):
        if how == "setting":
            monkeypatch.setenv("CARGOLINT_EBTI_RULINGS", "all")
            get_settings.cache_clear()
            assert run(world) == 0
        else:
            assert run(world, "--rulings", "all") == 0
        docs = [json.loads(line) for line in (world.out / "store" / "bti_docs.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [d["reference"] for d in docs] == VALID
        meta = json.loads((world.out / "store" / "index_meta.json").read_text(encoding="utf-8"))
        assert meta["refresh"]["rulings_requested"] == "all"

    @pytest.mark.parametrize("value, how", [("many", "option"), ("0", "option"), ("bogus", "setting")])
    def test_an_invalid_ruling_count_is_a_setup_error(self, world, monkeypatch, capsys, value, how):
        if how == "setting":
            monkeypatch.setenv("CARGOLINT_EBTI_RULINGS", value)
            get_settings.cache_clear()
            assert run(world) == 2
        else:
            assert run(world, "--rulings", value) == 2
        assert "positive integer or all" in capsys.readouterr().err and world.service.calls == []

    def test_bad_options_exit_2(self, world):
        assert run(world, "--bogus") == 2 and world.service.calls == []


# --------------------------------------------------------------------------- review fix F1
class TestServiceFailuresAfterTheBuild:
    def test_a_listing_failure_for_the_prune_after_the_publish_is_exit_3_naming_the_prune(self, world, capsys):
        world.service = FakeReleaseService({"ebti-2026-09-01": complete("ebti", "2026-09-01"),
                                            "ebti-2026-08-01": complete("ebti", "2026-08-01")})
        world.service.fail_at("list", "gh: HTTP 502 (simulated)", at=3)       # the check, the re-read, then the prune's
        assert run(world) == 3
        err = capsys.readouterr().err
        assert err.startswith(f"EBTI refresh failed: the release service failed at the prune of {NAME}: gh: HTTP 502")
        assert err.rstrip().endswith(f"before that it created {NAME}, marked it latest")
        service = world.service
        assert service.releases[NAME]["assets"] == [ARCHIVE, "metadata.json"] and service.latest_name == NAME
        assert service.calls_of("delete") == [] and "ebti-2026-08-01" in service.names

    def test_a_listing_failure_before_the_metadata_is_exit_3_after_the_build(self, world, capsys):
        world.service.fail_at("list", "gh: HTTP 502 (simulated)", at=2)
        assert run(world) == 3
        err = capsys.readouterr().err
        assert err.startswith(f"EBTI refresh failed: the release service failed at the listing before the metadata of {NAME}")
        assert err.rstrip().endswith("before that it did nothing") and world.service.names == []
        assert (world.out / ARCHIVE).exists() and len(world.emb.seen) == 4                    # the build ran
