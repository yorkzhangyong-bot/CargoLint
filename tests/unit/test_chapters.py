"""Feature 014a, User Story 2: the chapter setting reaches the loader and rag.bti, and the source version names the
chapters (spec FR-006, FR-008; contracts/settings-and-scripts.md). Every test runs on temporary paths: the loader's
store, raw, subset and sidecar paths are monkeypatched, so no repository path is written.

Traceability: 014a/FR-006, 014a/FR-008."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import rag.bti as bti
import rag.loader as loader
from agent.config import get_settings, parse_chapter_setting

pytestmark = pytest.mark.unit

TWELVE = set(bti.TARGET_CHAPTERS)


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """The loader's paths in a temporary folder and the chapter setting unset."""
    monkeypatch.setattr(loader, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(loader, "RAW_DIR", tmp_path / "data" / "raw")
    monkeypatch.setattr(loader, "BTI_SUBSET", tmp_path / "data" / "bti_subset.jsonl")
    monkeypatch.setattr(loader, "SUBSET_META", tmp_path / "data" / "bti_subset.meta.json")
    monkeypatch.delenv("CARGOLINT_EBTI_CHAPTERS", raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def setting(monkeypatch, value: str) -> None:
    monkeypatch.setenv("CARGOLINT_EBTI_CHAPTERS", value)
    get_settings.cache_clear()


@pytest.mark.parametrize("spec", ["all", "ALL", "61-64", "27,34,38", "1", "39,42,61-64,73,84,85,94,95,96"])
def test_the_loaders_parser_is_the_settings_parser(spec):
    assert loader.parse_chapters(spec) == parse_chapter_setting(spec)
    with pytest.raises(ValueError):
        loader.parse_chapters("84,abc")


def test_the_source_version_names_all_chapters_or_the_list():
    assert bti.chapters_spec(None) == "all chapters"
    assert bti.chapters_spec(TWELVE) == "39,42,61-64,73,84,85,94,95,96"           # the twelve as today
    assert bti.chapters_spec({"34", "27", "38"}) == "27,34,38"
    assert loader.ebti_source_version("2026-11-18", None) == "full extract of 2026-11-18, all chapters"
    assert loader.ebti_source_version("2026-11-18", TWELVE) == (
        "full extract of 2026-11-18, chapters 39,42,61-64,73,84,85,94,95,96")
    assert loader.ebti_source_version("2026-11-18", frozenset({"84", "39"})) == "full extract of 2026-11-18, chapters 39,84"


def run_loader(monkeypatch, argv: list[str]) -> list:
    """rag.loader.main with its build steps replaced: returns the chapters each build_bti call received."""
    seen = []

    def build_bti(demo, chapters, force=False, store_dir=None):
        seen.append(chapters)
        return bti.BTIStore([]), None

    monkeypatch.setattr(loader, "build_nomenclature", lambda force=False: SimpleNamespace(chunks=[]))
    monkeypatch.setattr(loader, "build_rules", lambda force=False: None)
    monkeypatch.setattr(loader, "build_bti", build_bti)
    monkeypatch.setattr(loader, "build_indexes", lambda *a, **k: {})
    monkeypatch.setattr(loader, "write_sources_md", lambda *a, **k: None)
    assert loader.main(argv) == 0
    return seen


def test_the_loader_takes_its_bti_chapters_from_the_setting(paths, monkeypatch):
    assert run_loader(monkeypatch, ["--no-embed"]) == [None]                      # unset: every chapter
    setting(monkeypatch, "27,34")
    assert run_loader(monkeypatch, ["--no-embed"]) == [frozenset({"27", "34"})]
    assert run_loader(monkeypatch, ["--no-embed", "--bti-chapters", "61-62"]) == [frozenset({"61", "62"})]   # the option wins
    assert run_loader(monkeypatch, ["--no-embed", "--bti-chapters", "all"]) == [None]


def test_a_bad_chapter_setting_stops_the_loader_with_exit_2(paths, monkeypatch, capsys):
    setting(monkeypatch, "84,abc")
    monkeypatch.setattr(loader, "build_nomenclature", lambda force=False: pytest.fail("nothing is built"))
    assert loader.main(["--no-embed"]) == 2
    assert "CARGOLINT_EBTI_CHAPTERS" in capsys.readouterr().err
    assert not (paths / "store").exists() and not (paths / "data").exists()


def run_bti(monkeypatch, tmp_path, argv: list[str]) -> list:
    """rag.bti.main on a stubbed extract reader: returns the chapters each iter_extract call received."""
    seen = []

    def iter_extract(zip_path, chapters, today):
        seen.append(chapters)
        return iter([])

    monkeypatch.setattr(bti, "iter_extract", iter_extract)
    assert bti.main(["--zip", str(tmp_path / "extract.zip"), "--out", str(tmp_path / "subset.jsonl"), *argv]) == 0
    return seen


def test_rag_bti_accepts_all_and_ranges_and_defaults_to_the_setting(paths, monkeypatch):
    assert run_bti(monkeypatch, paths, ["--chapters", "all"]) == [None]
    assert run_bti(monkeypatch, paths, ["--chapters", "61-62,84"]) == [frozenset({"61", "62", "84"})]
    assert run_bti(monkeypatch, paths, []) == [None]                              # the setting, all by default
    setting(monkeypatch, "39,42,61-64,73,84,85,94,95,96")
    assert run_bti(monkeypatch, paths, []) == [frozenset(TWELVE)]
