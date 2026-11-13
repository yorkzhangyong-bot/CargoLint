"""Feature 013, User Story 3: the app's fetch at a cold start (contracts/releases.md, "The app's fetch"; spec FR-013,
FR-015, FR-016). The latest-release pointer, the listing and the download addresses are `file:` templates over a
temporary folder holding, per release, metadata.json and the archive; the suite's offline guard lets `file:` URLs
through and nothing else."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.config import load_settings
from rag import refresh
from rag.refresh import FetchResult, RefreshError, fetch_release, fetch_releases, releases_needed

pytestmark = pytest.mark.unit

EBTI_ENTRIES = {"store/index_meta.json": b'{"embedding_model": "fake"}', "store/bm25.pkl": b"bm25", "store/chroma/chroma.sqlite3": b"db"}
TARIC_ENTRIES = {"data/taric.jsonl": b'{"kind":"snapshot","snapshot_date":"2026-11-02"}\n'}


def settings_for(repo: str = "owner/name", **pins):
    return dataclasses.replace(load_settings({}), release_repo=repo, **pins)


@pytest.fixture
def site(tmp_path, monkeypatch):
    """A folder of releases behind file: URL templates, and an empty root for the app's files."""
    base = tmp_path / "site"
    base.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    uri = base.as_uri()
    monkeypatch.setattr(refresh, "LATEST", uri + "/latest/{asset}")
    monkeypatch.setattr(refresh, "API", uri + "/releases.json")
    monkeypatch.setattr(refresh, "DOWNLOAD", uri + "/{tag}/{asset}")
    return SimpleNamespace(base=base, root=root)


def release(site, name: str, entries: dict[str, bytes] | None = None, *, sha: str | None = None,
            archive: bool = True, metadata: bool = True, drop: str | None = None, stamp: bytes = b"") -> dict:
    """One release on the site: its archive (the kind's default entries, `stamp` appended to the first one so releases
    differ) and its metadata.json; `sha` overrides the checksum, `drop` leaves a metadata field out."""
    kind, day = refresh.parse_release_name(name)
    folder = site.base / name
    folder.mkdir(parents=True, exist_ok=True)
    entries = dict(entries if entries is not None else (EBTI_ENTRIES if kind == "ebti" else TARIC_ENTRIES))
    first = next(iter(entries))
    entries[first] = entries[first] + stamp
    archive_name = refresh.archive_name(kind, day)
    path = folder / archive_name
    with zipfile.ZipFile(path, "w") as z:
        for entry, data in entries.items():
            z.writestr(entry, data)
    fields = {"kind": kind, "release": name, "snapshot_date": day.isoformat(), "source": "https://example.invalid/",
              "source_version": f"test {day}", "built_at": "2026-11-13T10:00:00+00:00", "archive": archive_name,
              "sha256": sha or hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size,
              "entries": sorted(entries), "current": {"ebti": [], "taric": []}}
    if drop:
        del fields[drop]
    if not archive:
        path.unlink()
    if metadata:
        (folder / "metadata.json").write_text(json.dumps(fields), encoding="utf-8")
    return fields


def pointer(site, current: dict[str, list[str]] | None = None, text: str | None = None) -> None:
    """The latest release's metadata.json (a metadata file with a `current` block), or any text."""
    (site.base / "latest").mkdir(exist_ok=True)
    if text is None:
        fields = {"kind": "taric", "release": "taric-2026-11-02", "archive": "cargolint-taric-2026-11-02.zip", "sha256": "0" * 64}
        if current is not None:
            fields["current"] = current
        text = json.dumps(fields)
    (site.base / "latest" / "metadata.json").write_text(text, encoding="utf-8")


def listing(site, releases: list, text: str | None = None) -> None:
    """The release list in GitHub's shape: each item a name (complete) or (name, assets, draft)."""
    items = []
    for item in releases:
        name, assets, draft = (item, None, False) if isinstance(item, str) else item
        parsed = refresh.parse_release_name(name)
        if assets is None:
            assets = [refresh.archive_name(*parsed), "metadata.json"] if parsed else ["something.zip"]
        items.append({"tag_name": name, "draft": draft, "published_at": None if draft else "2026-11-03T05:33:00Z",
                      "assets": [{"name": a} for a in assets]})
    (site.base / "releases.json").write_text(text if text is not None else json.dumps(items), encoding="utf-8")


def reads(monkeypatch) -> list[str]:
    """Counts the URLs opened (on top of the offline guard's file:-only urlopen)."""
    seen: list[str] = []
    real = urllib.request.urlopen

    def counting(url, *args, **kwargs):
        seen.append(url.full_url if isinstance(url, urllib.request.Request) else str(url))
        return real(url, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", counting)
    return seen


def marker(site, kind: str) -> None:
    path = site.root / refresh.MARKER[kind]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"present")


class TestNeeded:
    def test_releases_needed_names_the_kinds_whose_marker_is_missing(self, site):
        assert releases_needed(settings_for(), site.root) == ["ebti", "taric"]
        marker(site, "ebti")
        assert releases_needed(settings_for(), site.root) == ["taric"]
        marker(site, "taric")
        assert releases_needed(settings_for(), site.root) == []
        assert releases_needed(settings_for(repo=""), site.root) == []

    def test_nothing_is_read_when_both_markers_exist(self, site, monkeypatch):
        marker(site, "ebti")
        marker(site, "taric")
        seen = reads(monkeypatch)
        assert fetch_releases(settings_for(), site.root) == FetchResult()
        assert seen == []

    def test_nothing_is_fetched_without_the_repository_setting(self, site, monkeypatch):
        seen = reads(monkeypatch)
        assert fetch_releases(settings_for(repo=""), site.root) == FetchResult()
        assert seen == []


class TestRoutes:
    def test_the_pointer_gives_the_candidates_and_the_listing_is_never_read(self, site, monkeypatch):
        release(site, "ebti-2026-10-14", stamp=b"old")
        release(site, "ebti-2026-11-01", stamp=b"new")
        release(site, "taric-2026-10-01", stamp=b"old")
        release(site, "taric-2026-11-02", stamp=b"new")
        pointer(site, {"ebti": ["ebti-2026-11-01", "ebti-2026-10-14"], "taric": ["taric-2026-11-02", "taric-2026-10-01"]})
        seen = reads(monkeypatch)
        result = fetch_releases(settings_for(), site.root)
        assert result == FetchResult(unpacked={"ebti": "ebti-2026-11-01", "taric": "taric-2026-11-02"}, failed={})
        assert (site.root / "store" / "index_meta.json").read_bytes() == b'{"embedding_model": "fake"}new'
        assert (site.root / "store" / "chroma" / "chroma.sqlite3").read_bytes() == b"db"
        assert (site.root / "data" / "taric.jsonl").read_bytes() == TARIC_ENTRIES["data/taric.jsonl"] + b"new"
        assert sum(u.endswith("/latest/metadata.json") for u in seen) == 1 and not any(u.endswith("releases.json") for u in seen)
        for kind, name in result.unpacked.items():
            fields = json.loads((site.root / refresh.RELEASE_FILE[kind]).read_text(encoding="utf-8"))
            assert fields["release"] == name and fields["fetched_at"][:2] == "20" and fields["sha256"]

    @pytest.mark.parametrize("state", ["missing", "not json", "no current", "other kind only"])
    def test_the_listing_when_the_pointer_is_unusable(self, site, monkeypatch, state):
        if state == "not json":
            pointer(site, text="<html>moved</html>")
        elif state == "no current":
            pointer(site)
        elif state == "other kind only":
            pointer(site, {"taric": ["taric-2026-11-02"]})
        marker(site, "taric")
        for name, stamp in (("ebti-2026-10-14", b"older"), ("ebti-2026-11-01", b"newest"), ("ebti-2026-09-01", b"oldest")):
            release(site, name, stamp=stamp)
        release(site, "ebti-2026-11-05", archive=False)                                      # listed complete, unreachable
        listing(site, [("ebti-2026-11-09", ["cargolint-ebti-2026-11-09.zip", "metadata.json"], True),   # a draft
                       "ebti-2026-10-14", ("ebti-2026-11-07", ["cargolint-ebti-2026-11-07.zip"], False),  # an asset missing
                       "ebti-2026-09-01", "ebti-2026-11-01", "demo-store-v1"])
        seen = reads(monkeypatch)
        result = fetch_releases(settings_for(), site.root)
        assert result.unpacked == {"ebti": "ebti-2026-11-01"}                          # newest complete by name date
        assert (site.root / "store" / "index_meta.json").read_bytes().endswith(b"newest")
        assert sum(u.endswith("releases.json") for u in seen) == 1

    def test_a_pin_is_fetched_by_name_with_pointer_and_listing_unreachable(self, site, monkeypatch):
        release(site, "ebti-2026-10-14", stamp=b"pinned")
        release(site, "ebti-2026-11-01", stamp=b"newest")
        marker(site, "taric")
        seen = reads(monkeypatch)
        result = fetch_releases(settings_for(ebti_release="ebti-2026-10-14"), site.root)
        assert result.unpacked == {"ebti": "ebti-2026-10-14"} and result.failed == {}
        assert (site.root / "store" / "index_meta.json").read_bytes().endswith(b"pinned")
        assert not any(u.endswith(("latest/metadata.json", "releases.json")) for u in seen)

    @pytest.mark.parametrize("fault", ["checksum", "no archive", "bad metadata", "no metadata"])
    def test_a_failing_newest_release_falls_back_to_the_next_newest(self, site, fault):
        marker(site, "taric")
        release(site, "ebti-2026-10-14", stamp=b"fallback")
        if fault == "checksum":
            release(site, "ebti-2026-11-01", sha="0" * 64)
        elif fault == "no archive":
            release(site, "ebti-2026-11-01", archive=False)
        elif fault == "bad metadata":
            release(site, "ebti-2026-11-01", drop="sha256")
        else:
            release(site, "ebti-2026-11-01", metadata=False)
        pointer(site, {"ebti": ["ebti-2026-11-01", "ebti-2026-10-14"]})
        result = fetch_releases(settings_for(), site.root)
        assert result.unpacked == {"ebti": "ebti-2026-10-14"} and result.failed == {}
        assert (site.root / "store" / "index_meta.json").read_bytes().endswith(b"fallback")

    def test_a_failed_pin_falls_back_once_to_the_newest_with_a_log_line(self, site, caplog):
        marker(site, "taric")
        release(site, "ebti-2026-11-01", stamp=b"newest")
        release(site, "ebti-2026-10-14", stamp=b"older")
        pointer(site, {"ebti": ["ebti-2026-11-01", "ebti-2026-10-14"]})
        with caplog.at_level(logging.INFO, logger="rag.refresh"):
            result = fetch_releases(settings_for(ebti_release="ebti-2026-09-01"), site.root)   # deleted by retention
        assert result.unpacked == {"ebti": "ebti-2026-11-01"}
        assert any("pin ebti-2026-09-01 not honoured" in r.getMessage() for r in caplog.records)
        assert (site.root / "store" / "index_meta.json").read_bytes().endswith(b"newest")

    def test_a_failed_pin_and_a_failed_newest_stop_the_ebti_kind(self, site):
        marker(site, "taric")
        release(site, "ebti-2026-11-01", sha="0" * 64)
        release(site, "ebti-2026-10-14", stamp=b"older")                       # not tried: the fallback is once
        pointer(site, {"ebti": ["ebti-2026-11-01", "ebti-2026-10-14"]})
        with pytest.raises(RefreshError, match=r"^ebti: ebti-2026-09-01: .*; ebti-2026-11-01: the archive's SHA-256 is"):
            fetch_releases(settings_for(ebti_release="ebti-2026-09-01"), site.root)
        assert not (site.root / "store").exists()

    def test_both_ebti_candidates_failing_raises_naming_each_with_its_reason(self, site):
        marker(site, "taric")
        release(site, "ebti-2026-11-01", sha="0" * 64)
        release(site, "ebti-2026-10-14", archive=False)
        pointer(site, {"ebti": ["ebti-2026-11-01", "ebti-2026-10-14"]})
        with pytest.raises(RefreshError) as info:
            fetch_releases(settings_for(), site.root)
        text = str(info.value)
        assert text.startswith("ebti: ebti-2026-11-01: the archive's SHA-256 is ") and "not 0000" in text
        assert "; ebti-2026-10-14: the archive could not be downloaded" in text
        assert not (site.root / "store").exists()

    def test_both_taric_candidates_failing_is_returned_when_the_ebti_kind_is_fetched(self, site):
        release(site, "ebti-2026-11-01")
        release(site, "taric-2026-11-02", sha="0" * 64)
        release(site, "taric-2026-10-01", archive=False)
        pointer(site, {"ebti": ["ebti-2026-11-01"], "taric": ["taric-2026-11-02", "taric-2026-10-01"]})
        result = fetch_releases(settings_for(), site.root)
        assert result.unpacked == {"ebti": "ebti-2026-11-01"}
        assert result.failed["taric"].startswith("taric-2026-11-02: the archive's SHA-256 is ")
        assert "; taric-2026-10-01: the archive could not be downloaded" in result.failed["taric"]
        assert not (site.root / "data" / "taric.jsonl").exists() and (site.root / "store" / "index_meta.json").exists()

    @pytest.mark.parametrize("kind", ["ebti", "taric"])
    def test_a_stale_pointer_falls_back_to_the_listings_newest_untried_release(self, site, monkeypatch, kind):
        marker(site, "taric" if kind == "ebti" else "ebti")
        good = "ebti-2026-11-01" if kind == "ebti" else "taric-2026-11-02"
        gone, broken = f"{kind}-2026-11-09", f"{kind}-2026-11-08"
        release(site, good, stamp=b"listed")
        release(site, broken, sha="0" * 64)
        pointer(site, {kind: [gone, broken]})                                   # two overlapping runs left this
        listing(site, [broken, good, gone])
        seen = reads(monkeypatch)
        result = fetch_releases(settings_for(), site.root)
        assert result.unpacked == {kind: good} and result.failed == {}
        assert sum(u.endswith("releases.json") for u in seen) == 1
        assert (site.root / refresh.MARKER[kind]).read_bytes().endswith(b"listed")

    def test_no_pin_with_pointer_and_listing_both_unreadable(self, site):
        with pytest.raises(RefreshError) as info:
            fetch_releases(settings_for(), site.root)
        text = str(info.value)
        assert text.startswith("ebti: no release found: the latest release's metadata could not be read")
        assert "the listing could not be read" in text
        marker(site, "ebti")
        result = fetch_releases(settings_for(), site.root)
        assert result.unpacked == {} and result.failed["taric"].startswith("no release found: the latest release's metadata could not be read")
        assert "the listing could not be read" in result.failed["taric"]

    def test_the_pointer_and_the_listing_are_each_read_at_most_once_for_two_missing_kinds(self, site, monkeypatch):
        pointer(site, {"ebti": ["ebti-2026-11-09"], "taric": []})                 # stale for ebti, nothing for taric
        release(site, "ebti-2026-11-01")
        release(site, "taric-2026-11-02")
        listing(site, ["ebti-2026-11-01", "taric-2026-11-02", "demo-store-v1"])
        seen = reads(monkeypatch)
        result = fetch_releases(settings_for(), site.root)
        assert result.unpacked == {"ebti": "ebti-2026-11-01", "taric": "taric-2026-11-02"}
        assert sum(u.endswith("latest/metadata.json") for u in seen) == 1 and sum(u.endswith("releases.json") for u in seen) == 1


class TestUnpack:
    @pytest.mark.parametrize("kind, entries", [
        ("ebti", {**EBTI_ENTRIES, "data/taric.jsonl": b"x"}),
        ("ebti", {**EBTI_ENTRIES, "store/../app.py": b"x"}),
        ("ebti", {**EBTI_ENTRIES, "app.py": b"x"}),
        ("ebti", {"store/bm25.pkl": b"no marker"}),
        ("taric", {"data/taric.jsonl": b"x", "data/other.jsonl": b"x"}),
        ("taric", {"data/../taric.jsonl": b"x"}),
    ])
    def test_an_entry_outside_the_kinds_paths_is_refused_before_anything_is_written(self, site, kind, entries):
        name = "ebti-2026-11-01" if kind == "ebti" else "taric-2026-11-02"
        release(site, name, entries)
        with pytest.raises(RefreshError, match="unexpected paths|holds no"):
            fetch_release("owner/name", kind, name, site.root)
        assert not any(site.root.iterdir())

    def test_the_taric_snapshot_is_written_through_tmp_and_renamed(self, site, monkeypatch):
        release(site, "taric-2026-11-02")
        replaced: list[tuple[str, str]] = []
        real = os.replace

        def record(src, dst, *args, **kwargs):
            replaced.append((Path(src).name, Path(dst).name))
            return real(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", record)
        fetch_release("owner/name", "taric", "taric-2026-11-02", site.root)
        assert replaced == [("taric.jsonl.tmp", "taric.jsonl")]
        assert (site.root / "data" / "taric.jsonl").exists() and not (site.root / "data" / "taric.jsonl.tmp").exists()

    def test_the_ebti_marker_is_unpacked_last_so_an_interrupted_unpack_leaves_none(self, site, monkeypatch):
        release(site, "ebti-2026-11-01")
        order: list[str] = []
        real = zipfile.ZipFile.extract

        def record(self, member, path=None, pwd=None):
            name = member if isinstance(member, str) else member.filename
            order.append(name)
            return real(self, member, path, pwd)

        monkeypatch.setattr(zipfile.ZipFile, "extract", record)
        fetch_release("owner/name", "ebti", "ebti-2026-11-01", site.root)
        assert order[-1] == "store/index_meta.json" and sorted(order) == sorted(EBTI_ENTRIES)
        import shutil

        shutil.rmtree(site.root / "store")

        def interrupt(self, member, path=None, pwd=None):
            name = member if isinstance(member, str) else member.filename
            if name == "store/index_meta.json":
                raise OSError("disk full")
            return real(self, member, path, pwd)

        monkeypatch.setattr(zipfile.ZipFile, "extract", interrupt)
        with pytest.raises(RefreshError, match="disk full"):
            fetch_release("owner/name", "ebti", "ebti-2026-11-01", site.root)
        assert not (site.root / "store" / "index_meta.json").exists()
        assert releases_needed(settings_for(), site.root) == ["ebti", "taric"]       # the next start fetches again

    def test_fetch_release_checks_the_metadata_names_the_release(self, site):
        fields = release(site, "ebti-2026-11-01")
        (site.base / "ebti-2026-11-01" / "metadata.json").write_text(json.dumps({**fields, "release": "ebti-2026-10-14"}), encoding="utf-8")
        with pytest.raises(RefreshError, match="not ebti ebti-2026-11-01"):
            fetch_release("owner/name", "ebti", "ebti-2026-11-01", site.root)
        with pytest.raises(RefreshError, match="not a taric release name"):
            fetch_release("owner/name", "taric", "ebti-2026-11-01", site.root)
        assert not any(site.root.iterdir())
