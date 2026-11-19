"""The spec check of a spec-only pull request (scripts/check_spec.py, the traceability workflow): identifiers
well-formed, defined once in spec.md, examples in code ignored, another feature's requirements recognised when written
with their feature, any other undefined reference a warning, and the feature folder from the branch's label. The
regression cases are built from the wording of the existing specs 003, 004, 008 and 012. The samples use made-up
features (996 to 998z), so they never trace a real feature's requirements."""
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


def feature(root: Path, spec: str, name: str = "998-sample", files: dict[str, str] | None = None) -> Path:
    folder = root / "specs" / name
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text(spec, encoding="utf-8")
    for rel, text in (files or {}).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text, encoding="utf-8")
    return folder


def test_a_clean_spec_passes(tmp_path):
    folder = feature(tmp_path, CLEAN)
    assert check_spec.check(folder) == [] and check_spec.orphans(folder) == {}


def test_a_gap_in_the_numbering_is_allowed(tmp_path):
    folder = feature(tmp_path, "- **FR-001**: a\n- **FR-005**: b\n\nFR-001 and FR-005.\n")
    assert check_spec.check(folder) == [] and check_spec.orphans(folder) == {}


def test_a_duplicate_definition_in_spec_md_fails(tmp_path):
    problems = check_spec.check(feature(tmp_path, CLEAN + "- **FR-001**: defined again\n"))
    assert problems == ["duplicate definition: FR-001 is defined 2 times in spec.md"]


def test_definitions_count_in_spec_md_only(tmp_path):
    folder = feature(tmp_path, CLEAN, files={"quickstart.md": "- **SC-001**: a measurable outcome, restated\n",
                                             "plan.md": "- **FR-009**: a bullet that only looks like a definition\n"})
    assert check_spec.check(folder) == []                                   # the restated SC-001 is no duplicate
    assert check_spec.orphans(folder) == {"FR-009": ["plan.md"]}            # and FR-009 is defined nowhere


def test_an_undefined_reference_is_a_warning_not_a_failure(tmp_path):
    folder = feature(tmp_path, CLEAN + "\nSee FR-404.\n", files={"tasks.md": "Work on FR-001 and SC-777; FR-404.\n"})
    assert check_spec.check(folder) == []
    assert check_spec.orphans(folder) == {"FR-404": ["spec.md", "tasks.md"], "SC-777": ["tasks.md"]}


@pytest.mark.parametrize("prose", [
    "The 10 s figure in the description is feature 997's SC-007, which allows startup within 10 s.",   # 003
    "Results are frozen; equal calls return equal results (feature 997, FR-020).",                     # 003
    "The app offers no JSON download anywhere; feature 996's FR-041 and constitution 1.9.0 follow.",  # 012
    "The constitution 1.6.0 amendment and the feature 996 FR-020 correction are tasks.",              # 008
    "Feature 997's FR-018 is superseded.",
    "As in feature 997’s SC-007.",                                                          # a curly apostrophe
    "Cites 997/FR-020, 997-FR-021 and 998z/SC-004.",
])
def test_another_features_requirement_written_with_its_feature_is_not_an_orphan(tmp_path, prose):
    folder = feature(tmp_path, CLEAN + "\n" + prose + "\n")
    assert check_spec.check(folder) == [] and check_spec.orphans(folder) == {}


def test_a_scoped_token_needs_a_feature_label_of_its_own(tmp_path):
    folder = feature(tmp_path, CLEAN + "\nSC-998/FR-404 joins two ids.\n")
    # FR-404 is still reported: the 998 in SC-998/FR-404 is no feature label (SC-998 itself is undefined too)
    assert check_spec.orphans(folder) == {"FR-404": ["spec.md"], "SC-998": ["spec.md"]}


@pytest.mark.parametrize("name, spec, files, warnings", [
    ("003-cites-another",
     CLEAN + "This feature supersedes three parts of feature 997: the last sentence of its FR-018.\n"
             "The 10 s figure in the description is feature 997's SC-007, which allows startup within 10 s.\n",
     {"contracts/taric-store.md": "Equal calls return equal results (feature 997, FR-020).\n",
      "plan.md": "| V | stays a plain function for Spec 2 (feature 997's FR-021 test stays) |\n",
      "quickstart.md": "| C | FR-014 still holds | run B again |\n"},
     {"FR-014": ["quickstart.md"], "FR-018": ["spec.md"]}),
    ("004-its-limits",
     CLEAN + "- **SC-005**: a twelve-line list completes\n\n"
             "The time and cost limits still hold with the CN-8 step included (its SC-005 and SC-010).\n",
     {},
     {"SC-010": ["spec.md"]}),
    ("008-quickstart-restates",
     CLEAN + "- **SC-002**: a second outcome\n\nThe decided code is its top candidate (its vocabulary and FR-020).\n",
     {"quickstart.md": "- **SC-001**: a measurable outcome\n- **SC-002**: a second outcome\n",
      "plan.md": "The constitution 1.6.0 amendment and the feature 996 FR-020 correction are tasks.\n"},
     {"FR-020": ["spec.md"]}),
    ("012-cites-another",
     CLEAN + "The app offers no JSON download anywhere; feature 996's FR-041 and constitution 1.9.0 follow.\n",
     {"tasks.md": "Update ui/main_page.py, the tests, feature 996's FR-041 and README.md.\n"},
     {}),
])
def test_the_wording_of_the_existing_specs_passes(tmp_path, name, spec, files, warnings):
    folder = feature(tmp_path, spec, name=f"998-{name}", files=files)
    assert check_spec.check(folder) == []
    assert check_spec.orphans(folder) == warnings


def test_a_malformed_identifier_fails(tmp_path):
    problems = check_spec.check(feature(tmp_path, "- **FR-1**: bad\n\nSee FR-1.\n"))
    assert problems == ["malformed identifier: FR-1 (expected FR-### or SC-### with three digits)"]


def test_identifiers_in_code_spans_and_fenced_blocks_are_ignored(tmp_path):
    body = CLEAN + "\nA bad id is `FR-7` or `SC-099`.\n\n```text\nmalformed identifier: FR-0001\nSC-404\n```\n"
    folder = feature(tmp_path, body)
    assert check_spec.check(folder) == [] and check_spec.orphans(folder) == {}


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


def test_main_fails_on_a_problem_and_only_warns_on_an_undefined_reference(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert check_spec.main([str(feature(tmp_path, CLEAN))]) == 0
    assert "2 FR and 1 SC defined in spec.md" in capsys.readouterr().out
    assert check_spec.main([str(feature(tmp_path, CLEAN + "See FR-404.\n", name="998z-warns"))]) == 0
    out = capsys.readouterr().out
    assert "warning: FR-404 is referenced in spec.md but not defined in spec.md" in out and "2 FR and 1 SC" in out
    assert check_spec.main([str(feature(tmp_path, CLEAN + "- **SC-001**: again\n", name="997-fails"))]) == 1
    assert "duplicate definition: SC-001" in capsys.readouterr().out
    assert check_spec.main([str(tmp_path / "specs" / "997-missing")]) == 1


def test_main_marks_a_warning_as_an_annotation_in_github_actions(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert check_spec.main([str(feature(tmp_path, CLEAN + "See FR-404.\n"))]) == 0
    assert "::warning title=Spec check::FR-404 is referenced in spec.md" in capsys.readouterr().out


def test_main_without_a_folder_takes_the_branch_and_skips_a_branch_without_a_feature(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_HEAD_REF", "qa-onboarding")
    assert check_spec.main([]) == 0
    assert "no spec to check" in capsys.readouterr().out
    monkeypatch.setenv("GITHUB_HEAD_REF", "997-no-such-feature")
    assert check_spec.main([]) == 0
