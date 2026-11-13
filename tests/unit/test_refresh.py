"""Feature 013: the shared release pieces of rag/refresh.py (contracts/releases.md, data-model §1, §2): names and
kinds, the listing, completeness, retention, the metadata file with its `current` block, packing, publishing and the
latest-release repair on the fake service, and the real service's `gh` argv through a recorder. The later classes
cover the tot listing (T010), the EBTI pieces (T015) and the workflow file (T030)."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from rag import refresh
from rag.refresh import (GhError, RefreshError, ReleaseService, current_block, is_complete, names_of_kind, pack_entries,
                         parse_listing, parse_release_name, prune, publish, read_metadata, repair_latest, write_metadata)
from tests.fakes import FakeReleaseService

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "refresh"


def listing_fixture() -> list[dict]:
    return parse_listing(json.loads((FIXTURES / "releases.json").read_text(encoding="utf-8")))


def complete(kind: str, day: str) -> dict:
    return {"assets": [f"cargolint-{kind}-{day}.zip", "metadata.json"]}


def metadata_fields(**over) -> dict:
    fields = {"kind": "taric", "release": "taric-2026-11-02", "snapshot_date": "2026-11-02",
              "source": "https://distr.tullverket.se/tulltaxan/", "source_version": "batch e14b8e06, extract 2026-11-02",
              "built_at": "2026-11-13T10:00:00+00:00", "archive": "cargolint-taric-2026-11-02.zip", "sha256": "ab" * 32,
              "size": 2_000_000, "entries": ["data/taric.jsonl"],
              "current": {"ebti": ["ebti-2026-11-01", "ebti-2026-10-14"], "taric": ["taric-2026-11-02"]}}
    return {**fields, **over}


def assets_in(tmp_path: Path) -> tuple[Path, Path]:
    archive = tmp_path / "cargolint-taric-2026-11-02.zip"
    archive.write_bytes(b"zip")
    metadata = tmp_path / "metadata.json"
    write_metadata(metadata, metadata_fields())
    return archive, metadata


class TestReleases:
    def test_parse_release_name(self):
        assert parse_release_name("ebti-2026-11-01") == ("ebti", date(2026, 11, 1))
        assert parse_release_name("taric-2026-11-02") == ("taric", date(2026, 11, 2))
        for name in ("demo-store-v1", "ebti-latest", "taric-2026-13-01", "", "ebti-2026-11-01.zip", "EBTI-2026-11-01"):
            assert parse_release_name(name) is None

    def test_parse_listing_on_the_recorded_shape(self):
        by_name = {r["name"]: r for r in listing_fixture()}
        assert list(by_name) == ["taric-2026-11-03", "ebti-2026-10-14", "taric-2026-11-02", "demo-store-v1", "ebti-2026-11-01"]
        assert by_name["taric-2026-11-03"]["draft"] is True and by_name["taric-2026-11-03"]["published_at"] is None
        assert by_name["taric-2026-11-03"]["assets"] == ["cargolint-taric-2026-11-03.zip"]
        assert by_name["demo-store-v1"]["draft"] is False                     # no draft field: false
        assert by_name["ebti-2026-11-01"]["assets"] == ["cargolint-ebti-2026-11-01.zip", "metadata.json"]
        assert by_name["ebti-2026-11-01"]["published_at"] == "2026-11-01T06:20:00Z"
        assert parse_listing([{"id": 1}]) == []                                # an entry without a tag is ignored
        with pytest.raises(ValueError):
            parse_listing({"message": "Not Found"})

    @pytest.mark.parametrize("release, expected", [
        ({"name": "ebti-2026-11-01", "draft": False, "assets": ["cargolint-ebti-2026-11-01.zip", "metadata.json"]}, True),
        ({"name": "ebti-2026-11-01", "draft": True, "assets": ["cargolint-ebti-2026-11-01.zip", "metadata.json"]}, False),
        ({"name": "ebti-2026-11-01", "draft": False, "assets": ["cargolint-ebti-2026-11-01.zip"]}, False),
        ({"name": "ebti-2026-11-01", "draft": False, "assets": ["metadata.json"]}, False),
        ({"name": "ebti-2026-11-01", "draft": False, "assets": ["cargolint-ebti-2026-10-14.zip", "metadata.json"]}, False),
        ({"name": "demo-store-v1", "draft": False, "assets": ["cargolint-demo-store-v1.zip"]}, False),
    ])
    def test_is_complete(self, release, expected):
        assert is_complete(release) is expected

    def test_names_of_kind_newest_first_by_the_date_in_the_name(self):
        listing = listing_fixture()
        assert names_of_kind(listing, "taric") == ["taric-2026-11-03", "taric-2026-11-02"]
        assert names_of_kind(listing, "taric", complete_only=True) == ["taric-2026-11-02"]
        assert names_of_kind(listing, "ebti") == ["ebti-2026-11-01", "ebti-2026-10-14"]
        assert names_of_kind(listing, "ebti", complete_only=True) == ["ebti-2026-11-01", "ebti-2026-10-14"]

    def test_prune_keeps_the_two_newest_complete_of_the_kind_and_deletes_the_rest_of_it(self):
        service = FakeReleaseService({
            "ebti-2026-11-01": complete("ebti", "2026-11-01"), "ebti-2026-10-14": complete("ebti", "2026-10-14"),
            "ebti-2026-09-01": complete("ebti", "2026-09-01"),
            "ebti-2026-11-05": {"assets": ["cargolint-ebti-2026-11-05.zip"], "draft": True},   # a draft: incomplete
            "ebti-2026-08-01": {"assets": ["cargolint-ebti-2026-08-01.zip"]},                  # one asset: incomplete
            "taric-2026-11-02": complete("taric", "2026-11-02"), "taric-2026-09-01": complete("taric", "2026-09-01"),
            "demo-store-v1": {"assets": ["cargolint-demo-store-v1.zip"]}, "ebti-nightly": {"assets": ["x.zip"]}})
        deleted = prune(service, "ebti")
        assert deleted == ["ebti-2026-11-05", "ebti-2026-09-01", "ebti-2026-08-01"]           # newest first
        assert sorted(service.names) == ["demo-store-v1", "ebti-2026-10-14", "ebti-2026-11-01", "ebti-nightly",
                                         "taric-2026-09-01", "taric-2026-11-02"]
        assert service.calls == [("list",), *[("delete", n) for n in deleted]]

    def test_prune_with_a_listing_given_lists_nothing_itself(self):
        service = FakeReleaseService({"taric-2026-11-02": complete("taric", "2026-11-02"),
                                      "taric-2026-10-01": complete("taric", "2026-10-01"),
                                      "taric-2026-09-01": complete("taric", "2026-09-01")})
        listing = service.list()
        service.calls.clear()
        assert prune(service, "taric", listing=listing) == ["taric-2026-09-01"]
        assert service.calls == [("delete", "taric-2026-09-01")]

    def test_prune_deletes_nothing_when_at_most_two_complete_exist(self):
        service = FakeReleaseService({"taric-2026-11-02": complete("taric", "2026-11-02"),
                                      "demo-store-v1": {"assets": ["a.zip"]}})
        assert prune(service, "taric") == [] and service.names == ["taric-2026-11-02", "demo-store-v1"]

    def test_current_block_from_a_listing_plus_the_release_about_to_be_published(self):
        listing = listing_fixture()
        assert current_block(listing, "taric", "taric-2026-11-04") == {
            "ebti": ["ebti-2026-11-01", "ebti-2026-10-14"], "taric": ["taric-2026-11-04", "taric-2026-11-02"]}
        assert current_block(listing, "ebti", "ebti-2026-11-01") == {          # --force on an existing name
            "ebti": ["ebti-2026-11-01", "ebti-2026-10-14"], "taric": ["taric-2026-11-02"]}
        assert current_block(listing, "ebti", "ebti-2026-11-13") == {          # cut to two: the oldest leaves
            "ebti": ["ebti-2026-11-13", "ebti-2026-11-01"], "taric": ["taric-2026-11-02"]}
        assert current_block([], "taric", "taric-2026-11-02") == {"ebti": [], "taric": ["taric-2026-11-02"]}

    def test_repair_latest_re_marks_only_when_the_latest_is_none_incomplete_or_older(self):
        def service(latest):
            return FakeReleaseService({
                "taric-2026-10-01": complete("taric", "2026-10-01"),                   # published first
                "ebti-2026-10-14": complete("ebti", "2026-10-14"),
                "taric-2026-11-02": complete("taric", "2026-11-02"),                   # the newest complete TARIC
                "ebti-2026-11-01": complete("ebti", "2026-11-01"),                     # published after it
                "taric-2026-11-03": {"assets": ["cargolint-taric-2026-11-03.zip"]},    # incomplete, published last
            }, latest=latest)

        for latest in (None, "taric-2026-11-03", "taric-2026-10-01", "ebti-2026-10-14", "demo-store-v1"):
            s = service(latest)
            assert repair_latest(s, "taric") == "taric-2026-11-02", latest
            assert s.latest_name == "taric-2026-11-02" and s.calls[-1] == ("mark_latest", "taric-2026-11-02")
        for latest in ("taric-2026-11-02", "ebti-2026-11-01"):                     # already, or a newer complete one
            s = service(latest)
            assert repair_latest(s, "taric") is None and s.calls_of("mark_latest") == [] and s.latest_name == latest
        s = FakeReleaseService({"demo-store-v1": {"assets": ["a.zip"]}}, latest="demo-store-v1")
        assert repair_latest(s, "taric") is None and s.calls_of("latest") == []    # nothing complete of the kind

    def test_a_failing_mark_latest_in_repair_latest_is_exit_3(self):
        s = FakeReleaseService({"taric-2026-11-02": complete("taric", "2026-11-02")})
        s.fail_at("mark_latest", "gh: HTTP 502 (simulated)")
        with pytest.raises(RefreshError, match="repair latest of taric-2026-11-02: gh: HTTP 502") as info:
            repair_latest(s, "taric")
        assert info.value.exit_code == 3 and "did nothing" in str(info.value)

    def test_write_and_read_metadata(self, tmp_path):
        path = tmp_path / "metadata.json"
        ebti = metadata_fields(kind="ebti", release="ebti-2026-11-13", archive="cargolint-ebti-2026-11-13.zip",
                               entries=["store/"], embedding_model="qwen/qwen3-embedding-8b", rulings=5000,
                               extract_rulings=74312, reused=4787, embedded=213, dropped=210,
                               vectors_from="ebti-2026-10-14")
        write_metadata(path, ebti)
        text = path.read_text(encoding="utf-8")
        assert text.endswith("}\n") and "\r" not in text
        back = read_metadata(path)
        assert back == ebti and read_metadata(path.read_bytes()) == ebti
        assert back["current"] == {"ebti": ["ebti-2026-11-01", "ebti-2026-10-14"], "taric": ["taric-2026-11-02"]}

    @pytest.mark.parametrize("missing", ["kind", "release", "archive", "sha256"])
    def test_read_metadata_refuses_a_file_without_the_required_fields(self, tmp_path, missing):
        path = tmp_path / "metadata.json"
        path.write_text(json.dumps({k: v for k, v in metadata_fields().items() if k != missing}), encoding="utf-8")
        with pytest.raises(RefreshError, match=missing):
            read_metadata(path)
        with pytest.raises(RefreshError, match=missing):
            write_metadata(tmp_path / "other.json", {k: v for k, v in metadata_fields().items() if k != missing})
        (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
        with pytest.raises(RefreshError, match="cannot be read"):
            read_metadata(tmp_path / "bad.json")
        with pytest.raises(RefreshError, match="cannot be read"):
            read_metadata(tmp_path / "absent.json")

    def test_pack_entries(self, tmp_path):
        taric = tmp_path / "taric.jsonl"
        taric.write_bytes(b'{"kind":"snapshot"}\n')
        meta = tmp_path / "index_meta.json"
        meta.write_bytes(b"{}")
        archive = tmp_path / "out" / "cargolint-taric-2026-11-02.zip"
        digest, size = pack_entries(archive, [(taric, "data/taric.jsonl"), (meta, "store/index_meta.json")])
        import zipfile

        with zipfile.ZipFile(archive) as z:
            assert z.namelist() == ["data/taric.jsonl", "store/index_meta.json"]
            assert z.read("data/taric.jsonl") == b'{"kind":"snapshot"}\n'
        assert (digest, size) == (hashlib.sha256(archive.read_bytes()).hexdigest(), archive.stat().st_size)

    def test_publish_creates_then_marks_latest(self, tmp_path):
        archive, metadata = assets_in(tmp_path)
        service = FakeReleaseService({"ebti-2026-11-01": complete("ebti", "2026-11-01")}, latest="ebti-2026-11-01")
        name = publish(service, "taric", date(2026, 11, 2), archive, metadata, notes="batch e14b8e06")
        assert name == "taric-2026-11-02"
        assert service.calls == [("list",), ("create", "taric-2026-11-02", "TARIC snapshot 2026-11-02", "batch e14b8e06",
                                             ["cargolint-taric-2026-11-02.zip", "metadata.json"]),
                                 ("mark_latest", "taric-2026-11-02")]
        assert service.releases["taric-2026-11-02"]["assets"] == ["cargolint-taric-2026-11-02.zip", "metadata.json"]
        assert service.latest_name == "taric-2026-11-02" and "upload" not in {c[0] for c in service.calls}

    def test_publish_with_a_listing_given_deletes_an_incomplete_release_of_the_name_first(self, tmp_path):
        archive, metadata = assets_in(tmp_path)
        service = FakeReleaseService({"taric-2026-11-02": {"assets": ["cargolint-taric-2026-11-02.zip"], "draft": True}})
        listing = service.list()
        service.calls.clear()
        publish(service, "taric", date(2026, 11, 2), archive, metadata, listing=listing)
        assert [c[0] for c in service.calls] == ["delete", "create", "mark_latest"]
        assert service.releases["taric-2026-11-02"]["draft"] is False

    def test_publish_with_force_deletes_the_complete_release_and_creates_it_afresh(self, tmp_path):
        archive, metadata = assets_in(tmp_path)
        service = FakeReleaseService({"taric-2026-11-02": complete("taric", "2026-11-02")})
        publish(service, "taric", date(2026, 11, 2), archive, metadata, force=True)
        assert [c[0] for c in service.calls] == ["list", "delete", "create", "mark_latest"]
        assert service.releases["taric-2026-11-02"]["files"]["metadata.json"] == metadata

    def test_publish_refuses_a_complete_release_without_force(self, tmp_path):
        archive, metadata = assets_in(tmp_path)
        service = FakeReleaseService({"taric-2026-11-02": complete("taric", "2026-11-02")})
        with pytest.raises(RefreshError, match="already published and complete"):
            publish(service, "taric", date(2026, 11, 2), archive, metadata)
        assert [c[0] for c in service.calls] == ["list"]

    @pytest.mark.parametrize("failing, step, before", [
        ("delete", "delete", "did nothing"),
        ("create", "create", "deleted the incomplete taric-2026-11-02"),
        ("mark_latest", "mark latest", "deleted the incomplete taric-2026-11-02, created taric-2026-11-02"),
    ])
    def test_a_service_failure_in_publish_is_exit_3_naming_the_step_and_what_was_done(self, tmp_path, failing, step, before):
        archive, metadata = assets_in(tmp_path)
        service = FakeReleaseService({"taric-2026-11-02": {"assets": ["metadata.json"]}})
        service.fail_at(failing, "gh: HTTP 500 (simulated)")
        with pytest.raises(RefreshError) as info:
            publish(service, "taric", date(2026, 11, 2), archive, metadata)
        message = str(info.value)
        assert info.value.exit_code == 3 and message.startswith(f"the release service failed at the {step} of taric-2026-11-02: gh: HTTP 500")
        assert message.endswith(before)

    def test_a_service_failure_in_prune_is_exit_3(self):
        service = FakeReleaseService({"taric-2026-11-02": complete("taric", "2026-11-02"),
                                      "taric-2026-10-01": complete("taric", "2026-10-01"),
                                      "taric-2026-09-01": complete("taric", "2026-09-01"),
                                      "taric-2026-08-01": {"assets": ["cargolint-taric-2026-08-01.zip"]}})
        service.fail_at("delete", "gh: HTTP 500 (simulated)")
        with pytest.raises(RefreshError, match="prune of taric-2026-09-01: gh: HTTP 500") as info:
            prune(service, "taric")
        assert info.value.exit_code == 3 and str(info.value).endswith("did nothing")
        assert "taric-2026-08-01" in service.names                                 # the run stopped at the failure


class Recorder:
    """Stands in for rag.refresh._run_gh: records every argv and answers from a table keyed by the first two words."""

    def __init__(self, answers: dict[str, str] | None = None, fail: dict[str, str] | None = None) -> None:
        self.argv: list[list[str]] = []
        self.answers = answers or {}
        self.fail = fail or {}

    def __call__(self, argv: list[str]) -> str:
        self.argv.append(list(argv))
        key = " ".join(argv[:2])
        if key in self.fail:
            raise GhError(self.fail[key])
        return self.answers.get(key, "")


class TestReleaseService:
    def test_list_argv_and_parsing(self):
        rec = Recorder({"api repos/o/n/releases?per_page=100": (FIXTURES / "releases.json").read_text(encoding="utf-8")})
        listing = ReleaseService("o/n", run=rec).list()
        assert rec.argv == [["api", "repos/o/n/releases?per_page=100"]]
        assert [r["name"] for r in listing] == [r["name"] for r in listing_fixture()] and listing[0]["draft"] is True

    def test_latest_argv_and_the_404(self):
        rec = Recorder({"api repos/o/n/releases/latest": json.dumps({"tag_name": "ebti-2026-11-01", "draft": False})})
        assert ReleaseService("o/n", run=rec).latest() == "ebti-2026-11-01"
        assert rec.argv == [["api", "repos/o/n/releases/latest"]]
        missing = Recorder(fail={"api repos/o/n/releases/latest": "gh: Not Found (HTTP 404)"})
        assert ReleaseService("o/n", run=missing).latest() is None
        broken = Recorder(fail={"api repos/o/n/releases/latest": "gh: Bad credentials (HTTP 401)"})
        with pytest.raises(GhError, match="401"):
            ReleaseService("o/n", run=broken).latest()

    def test_create_mark_latest_delete_and_download_argv_with_the_repo(self, tmp_path):
        rec = Recorder()
        service = ReleaseService("o/n", run=rec)
        service.create("taric-2026-11-02", "TARIC snapshot 2026-11-02", "batch e14b8e06",
                       [tmp_path / "cargolint-taric-2026-11-02.zip", tmp_path / "metadata.json"])
        service.mark_latest("taric-2026-11-02")
        service.delete("taric-2026-10-01")
        service.download("ebti-2026-11-01", "*", tmp_path / "previous")
        assert rec.argv == [
            ["release", "create", "taric-2026-11-02", str(tmp_path / "cargolint-taric-2026-11-02.zip"),
             str(tmp_path / "metadata.json"), "--title", "TARIC snapshot 2026-11-02", "--notes", "batch e14b8e06",
             "--repo", "o/n"],
            ["release", "edit", "taric-2026-11-02", "--latest", "--repo", "o/n"],
            ["release", "delete", "taric-2026-10-01", "--yes", "--cleanup-tag", "--repo", "o/n"],
            ["release", "download", "ebti-2026-11-01", "--pattern", "*", "--dir", str(tmp_path / "previous"), "--repo", "o/n"],
        ]
        assert (tmp_path / "previous").is_dir() and not hasattr(ReleaseService, "upload")

    def test_without_a_repo_gh_uses_the_checkout_and_no_repo_flag(self):
        rec = Recorder({"api repos/{owner}/{repo}/releases?per_page=100": "[]"})
        service = ReleaseService(run=rec)
        assert service.list() == []
        service.delete("taric-2026-10-01")
        assert rec.argv == [["api", "repos/{owner}/{repo}/releases?per_page=100"],
                            ["release", "delete", "taric-2026-10-01", "--yes", "--cleanup-tag"]]

    def test_check_runs_version_and_auth_status_and_fails_as_exit_2(self):
        rec = Recorder({"--version": "gh version 2.102.0"})
        ReleaseService("o/n", run=rec).check()
        assert rec.argv == [["--version"], ["auth", "status"]]
        for key in ("--version", "auth status"):
            failing = Recorder(fail={key: "gh: not found" if key == "--version" else "You are not logged into any GitHub hosts"})
            with pytest.raises(RefreshError, match="not available") as info:
                ReleaseService("o/n", run=failing).check()
            assert info.value.exit_code == 2

    def test_cargolint_gh_names_the_executable(self, tmp_path, monkeypatch):
        fake = tmp_path / "gh.cmd"
        fake.write_text("@echo off\n", encoding="utf-8")
        monkeypatch.setenv("CARGOLINT_GH", str(fake))
        assert refresh._gh_executable() == str(fake)
        monkeypatch.setenv("CARGOLINT_GH", str(tmp_path / "missing.exe"))
        with pytest.raises(GhError, match="does not exist") as info:
            refresh._gh_executable()
        assert info.value.exit_code == 2


# --------------------------------------------------------------------------- User Story 1: the tot listing (T010)
OBJECTS = ("GoodsNomenclature", "Measure", "MeasureType", "GeographicalArea", "DutyExpression", "Regulation")
BATCH_A, BATCH_B = "11111111-2222-4333-8444-555555555555", "22222222-2222-4333-8444-555555555555"


def tot_names(batch: str, yymmdd: str, objects=OBJECTS) -> list[str]:
    return [f"{o}_{batch}_{yymmdd}.xml.gz.pgp" for o in objects]


class TestTotListing:
    def test_the_recorded_listing_gives_the_sidecars_batch(self):
        from rag.refresh_taric import current_batch, parse_listing_html

        sidecar = json.loads((FIXTURES / "tot_listing.json").read_text(encoding="utf-8"))
        names = parse_listing_html((FIXTURES / "tot_listing.html").read_text(encoding="utf-8"))
        assert len(names) == sidecar["files"] and all(n.endswith(".xml.gz.pgp") for n in names)
        assert len(set(names)) == len(names) and not any("/" in n or "?" in n for n in names)
        batch = current_batch(names)
        assert batch.batch_id == sidecar["batch"] and batch.snapshot_date.isoformat() == sidecar["snapshot_date"]
        assert [n.split("_")[0] for n in batch.files] == list(OBJECTS)
        assert all(n == f"{o}_{sidecar['batch']}_{sidecar['snapshot_date'][2:].replace('-', '')}.xml.gz.pgp"
                   for o, n in zip(OBJECTS, batch.files))

    def test_two_complete_batches_pick_the_newer(self):
        from rag.refresh_taric import current_batch

        batch = current_batch(tot_names(BATCH_A, "261001") + tot_names(BATCH_B, "261102") + ["AdditionalCode_x_261102.xml.gz.pgp"])
        assert (batch.batch_id, batch.snapshot_date) == (BATCH_B, date(2026, 11, 2))
        assert batch.files == tuple(tot_names(BATCH_B, "261102"))

    def test_an_incomplete_newer_batch_is_passed_over_for_the_older_complete_one(self):
        from rag.refresh_taric import current_batch

        names = tot_names(BATCH_A, "261001") + tot_names(BATCH_B, "261102", OBJECTS[:-1])
        batch = current_batch(names)
        assert (batch.batch_id, batch.snapshot_date) == (BATCH_A, date(2026, 10, 1))

    def test_no_complete_batch_and_no_object_file_are_refused(self):
        from rag.refresh_taric import current_batch

        with pytest.raises(RefreshError, match="no batch in the tot listing has all 6 object files") as info:
            current_batch(tot_names(BATCH_A, "261001", OBJECTS[1:]) + tot_names(BATCH_B, "261102", OBJECTS[:3]))
        assert info.value.exit_code == 1
        with pytest.raises(RefreshError, match="names no TARIC object file") as info:
            current_batch(["AdditionalCode_x_261102.xml.gz.pgp", "readme.txt"])
        assert info.value.exit_code == 1
        with pytest.raises(RefreshError, match="no valid date"):
            current_batch(tot_names(BATCH_A, "261301"))

    def test_parse_listing_html_keeps_signed_file_links_only(self):
        from rag.refresh_taric import parse_listing_html

        html = ('<a href="?C=N;O=D">Name</a> <a href="/tulltaxan/xml/">Parent</a> '
                '<a href="Measure_a_261001.xml.gz.pgp">x</a> <a href="Measure_a_261001.xml.gz.pgp">x</a> '
                '<a href="notes.txt">n</a>')
        assert parse_listing_html(html) == ["Measure_a_261001.xml.gz.pgp"]
