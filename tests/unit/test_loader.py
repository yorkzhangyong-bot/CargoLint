"""Knowledge-base loaders: EBTI filtering and SKOS nomenclature parsing (Principle IV, FR-015, FR-046)."""
from datetime import date
from pathlib import Path

import pytest

from rag.bti import BTIStore, filter_rows, hs6_from_code, row_to_ruling
from rag.nomenclature import build_chunks, parse_skos

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TODAY = date(2026, 10, 14)


def _row(code="8452900000************", start="2024-01-10", end="2027-01-09", status="Valid", country="DE", ref="DEBTI12345/24-1"):
    return {
        "BTI_REFERENCE": ref, "ISSUING_COUNTRY": country, "START_DATE_OF_VALIDITY": start, "END_DATE_OF_VALIDITY": end,
        "NOMENCLATURE_CODE": code, "CLASSIFICATION_JUSTIFICATION": "GIR 1 and 6; part solely for sewing machines", "STATUS": status,
        "INVALIDATION_REASON": "", "INVALIDATION_JUSTIFICATION": "", "LANGUAGE": "DE", "PLACE_OF_ISSUE": "Hannover",
        "DATE_OF _ISSUE": "2024-01-10", "NAME_AND_ADDRESS": "Some Company GmbH, Example Str. 1, 30159 Hannover",
        "DESCRIPTION_OF_GOODS": "Steel bobbin cases for industrial sewing machines", "KEYWORDS": "sewing machines; parts",
    }


class TestBTI:
    def test_hs6_from_masked_10_digit_code(self):
        assert hs6_from_code("8716800000************") == "8716.80"
        assert hs6_from_code("9617000000") == "9617.00"
        assert hs6_from_code("8452 90 00 00") == "8452.90"

    def test_filter_keeps_only_valid_rows_in_target_chapters(self):
        rows = [
            _row(),                                                  # keep
            _row(end="2025-12-31", ref="OLD"),                       # expired
            _row(status="Invalidated", ref="INV"),                   # invalidated
            _row(code="3924100000************", ref="CH39"),         # other chapter
            _row(end="", ref="OPEN"),                                # no end date -> keep
        ]
        kept = list(filter_rows(rows, chapters={"84", "96"}, today=TODAY))
        assert [r["BTI_REFERENCE"] for r in kept] == ["DEBTI12345/24-1", "OPEN"]

    def test_row_to_ruling_drops_personal_data_and_derives_fields(self):
        r = row_to_ruling(_row())
        assert "NAME_AND_ADDRESS" not in r and "name_and_address" not in r
        assert r["reference"] == "DEBTI12345/24-1" and r["member_state"] == "DE"
        assert r["code"] == "8452.90" and r["cn_code"] == "8452900000"
        assert r["valid_from"] == "2024-01-10" and r["valid_to"] == "2027-01-09"
        assert r["description"].startswith("Steel bobbin") and r["reasoning"].startswith("GIR 1")
        assert r["language"] == "DE" and r["chapter"] == "84"

    def test_store_lookup_filters_expired_and_orders_newest_first(self):
        store = BTIStore([
            row_to_ruling(_row(ref="A", start="2023-01-01", end="2026-01-01")),      # expired on TODAY
            row_to_ruling(_row(ref="B", start="2024-05-01", end="2027-05-01")),
            row_to_ruling(_row(ref="C", start="2025-02-01", end="2028-06-01")),
            row_to_ruling(_row(ref="D", start="2022-02-01", end="2030-01-01")),
            row_to_ruling(_row(ref="E", start="2025-09-01", end="2029-01-01")),
            row_to_ruling(_row(ref="F", code="9617000000************", start="2025-01-01", end="2028-01-01")),
        ])
        hits = store.lookup("8452.90", as_of=TODAY)
        assert [h.reference for h in hits] == ["E", "C", "B"]       # newest first, max 3, A expired, D older
        assert store.lookup("9617.00", as_of=TODAY)[0].reference == "F"
        assert store.lookup("3924.10", as_of=TODAY) == []
        assert store.lookup("8452.90", as_of=date(2031, 1, 1)) == []


class TestSKOS:
    def test_parse_concepts(self):
        concepts = list(parse_skos(FIXTURES / "cn2026_excerpt.rdf"))
        assert len(concepts) == 9
        by_code = {c.code: c for c in concepts if c.code}
        assert "961700" in by_code and by_code["961700"].depth == 4
        assert by_code["9617"].label_en.startswith("Vacuum flasks")
        assert by_code["96081010"].dashes == "- -"

    def test_build_chunks_one_per_hs6_with_hierarchy_text_and_metadata(self):
        chunks = build_chunks(list(parse_skos(FIXTURES / "cn2026_excerpt.rdf")), source="CN 2026 fixture", edition_year=2026)
        by_id = {c.id: c for c in chunks}
        assert set(by_id) == {"hs:9608.10", "hs:9608.20", "hs:9617.00"}
        vac = by_id["hs:9617.00"]
        assert "Chapter 96" in vac.text and "Miscellaneous manufactured articles" in vac.text
        assert "Heading 9617" in vac.text and "Vacuum flasks" in vac.text
        assert "Subheading 9617.00" in vac.text
        assert "thermos" in vac.text  # scope note included
        assert vac.metadata == {"chapter": "96", "heading": "9617", "subheading": "9617.00", "language": "en",
                                "source": "CN 2026 fixture", "edition_year": 2026}
        pens = by_id["hs:9608.10"]
        assert "9608 10 10" in pens.text and "rolling ball pens" in pens.text   # CN-8 lines folded in
        assert "9608 10 92" in pens.text and "replaceable refill" in pens.text
        assert "9608 20" not in pens.text


# --------------------------------------------------------------------------- feature 013: the extract date, the release files (T016)
import csv  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import zipfile  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import rag.loader as loader_mod  # noqa: E402
from agent.config import ROOT  # noqa: E402

COLUMNS = list(_row().keys())


def extract_zip(path, rows, stamp=(2026, 11, 12, 4, 44, 0)):
    """A tiny EBTI full extract: one csv in the loader's column names, its entry stamped with the extract's night."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("EBTI_2026.csv", date_time=stamp), buf.getvalue().encode("utf-8"))
        z.writestr(zipfile.ZipInfo("readme.txt", date_time=(2027, 1, 1, 0, 0, 0)), b"later, but not a csv")
    return path


def _forbidden(*args, **kwargs):
    raise AssertionError("the download must not run")


@pytest.fixture
def loader_paths(tmp_path, monkeypatch):
    """The loader's data and store paths in a temporary folder: no test writes the repository's own."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(loader_mod, "RAW_DIR", data / "raw")
    monkeypatch.setattr(loader_mod, "BTI_SUBSET", data / "bti_subset.jsonl")
    monkeypatch.setattr(loader_mod, "SUBSET_META", data / "bti_subset.meta.json")
    monkeypatch.setattr(loader_mod, "BTI_DEMO", data / "bti_demo.jsonl")
    monkeypatch.setattr(loader_mod, "STORE_DIR", tmp_path / "patched-store")
    zip_path = extract_zip(tmp_path / "DDS2-EBTI_Full.zip", [_row(), _row(ref="DEBTI99/26-1", code="9617000000************")])

    def copy(url, dest, *args, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, dest)
        return dest

    monkeypatch.setattr(loader_mod, "download", copy)
    return SimpleNamespace(data=data, zip=zip_path, store=tmp_path / "store")


class TestBuildBti:
    def test_the_extract_date_is_returned_and_kept_beside_the_subset(self, loader_paths):
        repo_docs = ROOT / "store" / "bti_docs.jsonl"
        before = repo_docs.read_bytes() if repo_docs.exists() else None
        store, extract = loader_mod.build_bti(False, {"84", "96"}, store_dir=loader_paths.store)
        assert extract == "2026-11-12" and len(store) == 2
        assert (loader_paths.store / "bti_docs.jsonl").exists() and not loader_mod.STORE_DIR.exists()
        assert (repo_docs.read_bytes() if repo_docs.exists() else None) == before     # the repository's store untouched
        meta = json.loads(loader_mod.SUBSET_META.read_text(encoding="utf-8"))
        assert meta["extract_date"] == "2026-11-12" and meta["cut_at"]
        assert meta["source_version"] == "full extract of 2026-11-12, chapters 84,96"
        assert loader_mod.ebti_source_version("2026-11-12") == "full extract of 2026-11-12, chapters 39,42,61-64,73,84,85,94,95,96"

    def test_a_reused_subset_gives_the_sidecars_date_without_the_zip(self, loader_paths, monkeypatch):
        loader_mod.build_bti(False, {"84", "96"}, store_dir=loader_paths.store)
        monkeypatch.setattr(loader_mod, "download", _forbidden)
        store, extract = loader_mod.build_bti(False, {"84", "96"}, store_dir=loader_paths.store)
        assert extract == "2026-11-12" and len(store) == 2
        loader_mod.SUBSET_META.unlink()                                             # a subset cut before feature 013
        assert loader_mod.build_bti(False, {"84", "96"}, store_dir=loader_paths.store)[1] is None

    def test_the_demo_path_has_no_extract_date(self, loader_paths, monkeypatch):
        monkeypatch.setattr(loader_mod, "download", _forbidden)
        loader_mod.BTI_DEMO.write_text(json.dumps(row_to_ruling(_row())) + "\n", encoding="utf-8")
        store, extract = loader_mod.build_bti(True, {"84"}, store_dir=loader_paths.store)
        assert (len(store), extract) == (1, None) and not loader_mod.SUBSET_META.exists()


class TestKnowledgeBaseDates:
    def test_read_release_files(self, tmp_path):
        root = tmp_path / "root"
        (root / "store").mkdir(parents=True)
        (root / "data").mkdir()
        assert loader_mod.read_release_files(root) == {"ebti": None, "taric": None}
        (root / "store" / "release.json").write_text(json.dumps({"release": "ebti-2026-11-01", "fetched_at": "2026-11-13"}), encoding="utf-8")
        (root / "data" / "taric_release.json").write_text("not json", encoding="utf-8")
        assert loader_mod.read_release_files(root) == {"ebti": {"release": "ebti-2026-11-01", "fetched_at": "2026-11-13"}, "taric": None}

    @pytest.mark.parametrize("meta, expected", [
        ({"built_at": "2026-10-16T10:11:07+00:00", "ebti_snapshot_date": "2026-11-01"}, ("2026-11-01", "extract")),
        ({"built_at": "2026-10-16T10:11:07+00:00"}, ("2026-10-16", "built")),
        ({}, (None, "unknown")),
    ])
    def test_rulings_date(self, meta, expected):
        kb = loader_mod.KnowledgeBase(None, None, None, None, meta, None)
        assert kb.rulings_date == expected

    def test_releases_and_fetch_failures_are_empty_by_default(self):
        kb = loader_mod.KnowledgeBase(None, None, None, None, {}, None)
        assert kb.releases == {"ebti": None, "taric": None} and kb.fetch_failures == {}
