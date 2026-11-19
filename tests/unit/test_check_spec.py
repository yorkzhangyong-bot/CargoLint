"""The spec check of a spec-only pull request (scripts/check_spec.py, the traceability job in tests.yml): identifiers
well-formed, defined once and never orphaned, examples in code ignored, the feature folder from the branch's label.
The samples use made-up features (997 to 998z), so they never trace a real feature's requirements."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_spec  # noqa: E402

pytestmark = pytest.mark.unit

CLEAN = ("- **FR-001**: the system does a thing\n"
         "- **FR-002**: the system does another thing\n"
         "- **SC-001**: a measurable outcome\n\n"
         "The body mentions FR-001, FR-002 and SC-001 in prose.\n")


def feature(root: Path, spec: str, name: str = "998-sample", **extra: str) -> Path:
    folder = root / "specs" / name
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text(spec, encoding="utf-8")
    for stem, text in extra.items():
        (folder / f"{stem}.md").write_text(text, encoding="utf-8")
    return folder


def test_a_clean_spec_passes(tmp_path):
    assert check_spec.check(feature(tmp_path, CLEAN)) == []


def test_a_gap_in_the_numbering_is_allowed(tmp_path):
    assert check_spec.check(feature(tmp_path, "- **FR-001**: a\n- **FR-005**: b\n\nFR-001 and FR-005.\n")) == []


def test_a_duplicate_definition_fails(tmp_path):
    problems = check_spec.check(feature(tmp_path, CLEAN + "- **FR-001**: defined again\n"))
    assert problems == ["duplicate definition: FR-001 is defined 2 times"]


def test_an_orphan_reference_fails_also_from_another_file(tmp_path):
    assert check_spec.check(feature(tmp_path, CLEAN + "\nSee FR-404.\n")) == [
        "orphan reference: FR-404 is referenced but never defined"]
    other = tmp_path / "other"
    folder = feature(other, CLEAN, tasks="Work on FR-001 and the undefined SC-777.\n")
    assert check_spec.check(folder) == ["orphan reference: SC-777 is referenced but never defined"]


def test_a_malformed_identifier_fails(tmp_path):
    problems = check_spec.check(feature(tmp_path, "- **FR-1**: bad\n\nSee FR-1.\n"))
    assert problems == ["malformed identifier: FR-1 (expected FR-### or SC-### with three digits)"]


def test_identifiers_in_code_spans_and_fenced_blocks_are_ignored(tmp_path):
    body = CLEAN + "\nA bad id is `FR-7` or `SC-099`.\n\n```text\nmalformed identifier: FR-0001\nSC-404\n```\n"
    assert check_spec.check(feature(tmp_path, body)) == []


@pytest.mark.parametrize("branch, label", [
    ("014a-retrieval-evidence", "014a"), ("013-knowledge-base-refresh", "013"), ("998-x", "998"),
    ("qa-onboarding", None), ("docs/backlog", None), ("auto-heal/12345", None), ("0141-x", None), ("014ab-x", None),
    ("main", None)])
def test_the_feature_label_starts_the_branch_name(branch, label):
    assert check_spec.feature_label(branch) == label


def test_the_feature_folder_matches_the_whole_label(tmp_path):
    lettered = feature(tmp_path, CLEAN, name="998z-lettered")
    assert check_spec.feature_dir("998z", tmp_path) == lettered
    assert check_spec.feature_dir("998", tmp_path) is None             # 998 is not 998z
    assert check_spec.feature_dir("997", tmp_path) is None


def test_main_checks_the_folder_it_is_given(tmp_path, capsys):
    good = feature(tmp_path, CLEAN)
    assert check_spec.main([str(good)]) == 0
    assert "2 FR and 1 SC defined" in capsys.readouterr().out
    bad = feature(tmp_path, CLEAN + "See FR-404.\n", name="998z-bad")
    assert check_spec.main([str(bad)]) == 1
    assert "orphan reference: FR-404" in capsys.readouterr().out
    assert check_spec.main([str(tmp_path / "specs" / "997-missing")]) == 1


def test_main_without_a_folder_takes_the_branch_and_skips_a_branch_without_a_feature(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_HEAD_REF", "qa-onboarding")
    assert check_spec.main([]) == 0
    assert "no spec to check" in capsys.readouterr().out
    monkeypatch.setenv("GITHUB_HEAD_REF", "997-no-such-feature")
    assert check_spec.main([]) == 0
