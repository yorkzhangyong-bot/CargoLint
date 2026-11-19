"""The traceability check of a pull request (scripts/check_traceability.py, traceability.yml): spec-only against
implementation pull requests, the tests-traceability of the branch's feature in Python and Playwright tests, and the
pull-request body rules (Spec-PR, spec-change). The samples use made-up features (996 to 998z), so they never trace a
real feature's requirements."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import check_traceability as ct  # noqa: E402

pytestmark = pytest.mark.unit

SPEC = ("- **FR-001**: one\n- **FR-002**: two\n- **FR-010**: ten\n- **SC-001**: measured\n\n"
        "Prose mentions FR-001 and another feature's FR-777, and `FR-999` in code.\n")


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_spec_only_means_none_of_the_app_tests_scripts_or_data():
    assert ct.is_spec_only(["specs/998-x/spec.md", "docs/backlog.md", "README.md", ".github/workflows/tests.yml"])
    for code in ("app.py", "agent/config.py", "tools/check.py", "rag/loader.py", "ui/main_page.py",
                 "tests/unit/test_x.py", "tests/e2e-browser/main-page.spec.ts", "scripts/check_spec.py",
                 "data/rules/ics2_stop_words.json"):
        assert not ct.is_spec_only(["specs/998-x/spec.md", code]), code
    assert ct.is_spec_only(["docs/app.py.md", "specs/998-x/ui/notes.md"])     # only the paths themselves count


def test_the_spec_pr_rule_fires_for_app_changes_on_any_branch():
    assert ct.pr_rule_problems(["ui/main_page.py"], "Implements it.") == [
        "a pull request that changes the app (app.py, agent/, tools/, rag/, ui/) needs a 'Spec-PR: #<n>' line in "
        "its description"]
    assert ct.pr_rule_problems(["app.py"], None) != []
    assert ct.pr_rule_problems(["agent/routing.py"], "Implements it.\nSpec-PR: #7\n") == []
    assert ct.pr_rule_problems(["rag/x.py"], "spec-pr:#12") == []                 # case and spacing tolerated
    # tests, scripts, data, workflows and docs alone need no Spec-PR line
    assert ct.pr_rule_problems(["tests/unit/test_x.py", "scripts/check_spec.py", "data/samples/x.csv",
                                ".github/workflows/test-and-heal.yml", "docs/qa-platform.md"], "") == []


def test_the_spec_change_note_is_needed_only_with_a_spec_and_an_app_change():
    both = ["specs/998-x/spec.md", "tools/check.py"]
    assert ct.pr_rule_problems(both, "Spec-PR: #7") == [
        "a pull request that changes a spec file together with the app needs a 'spec-change: <reason>' line in its "
        "description"]
    assert ct.pr_rule_problems(both, "Spec-PR: #7\nspec-change: FR-003 narrowed after review\n") == []
    assert ct.pr_rule_problems(["specs/998-x/spec.md", "tests/unit/test_x.py"], "") == []
    assert ct.pr_rule_problems(both, "Spec-PR: #7\nspec-change:\nNext paragraph.") != []   # a reason on its line


def test_the_spec_ids_are_the_definitions_in_order(tmp_path):
    assert ct.spec_ids(write(tmp_path, "spec.md", SPEC)) == ["FR-001", "FR-002", "FR-010", "SC-001"]


def test_a_test_traces_an_id_by_a_scoped_token_or_a_feature_marker(tmp_path):
    files = [
        write(tmp_path, "a.py", '"""Covers 998/FR-001 and 998-SC-001; 997/FR-002 is another feature."""\n'),
        write(tmp_path, "b.py", 'FEATURE = "998"\n\n\ndef test_x():\n    """FR-010"""\n'),
        write(tmp_path, "c.spec.ts", "const FEATURE = '998z';\n/** Covers FR-002 */\n"),
        write(tmp_path, "d.spec.ts", "/** Covers FR-002, a bare id without a marker */\n"),
    ]
    assert ct.traced_ids("998", files) == {"FR-001", "SC-001", "FR-010"}
    assert ct.traced_ids("998z", files) == {"FR-002"}
    assert ct.traced_ids("997", files) == {"FR-002"}
    export = write(tmp_path, "e.spec.ts", 'export const FEATURE = "996";\ntest("1. x [FR-003]", async () => {});\n')
    assert ct.traced_ids("996", [export]) == {"FR-003"}


def test_a_scoped_token_needs_a_feature_label_of_its_own(tmp_path):
    files = [write(tmp_path, "a.py", '"""SC-998/FR-404 joins two ids of one feature, as SC-997/FR-005 does."""\n'),
             write(tmp_path, "b.spec.ts", "// Covers (998/FR-001) and [998-SC-002]\n")]
    assert ct.traced_ids("998", files) == {"FR-001", "SC-002"}             # 998/FR-404 inside SC-998/FR-404 is no token
    assert ct.traced_ids("997", files) == set()


def test_the_samples_of_the_traceability_tests_trace_no_existing_feature():
    root = Path(__file__).resolve().parents[2]
    samples = [root / "tests" / "unit" / name for name in ("test_check_spec.py", "test_check_traceability.py",
                                                         "test_qa_workflows.py")]
    labels = sorted(ct.check_spec.feature_label(p.name) for p in (root / "specs").iterdir() if p.is_dir())
    assert "014a" in labels and None not in labels
    assert {label: ct.traced_ids(label, samples) for label in labels if ct.traced_ids(label, samples)} == {}


def test_a_justification_names_the_feature(tmp_path):
    text = ("# Traceability\n\n- 998/FR-001: enforced by branch protection\n998-SC-001: a manual check in the "
            "quickstart\n- 997/FR-002: another feature\nFR-010: no feature, not counted\n- 998/FR-002:\nno reason\n")
    assert ct.justified_ids(text, "998") == {"FR-001", "SC-001"}


def test_traceability_is_checked_against_the_python_and_playwright_tests(tmp_path, capsys):
    write(tmp_path, "specs/998-sample/spec.md", SPEC)
    write(tmp_path, "tests/unit/test_sample.py", '"""Covers 998/FR-001."""\n')
    write(tmp_path, "tests/e2e-browser/sample.spec.ts", "const FEATURE = '998';\n/** Covers FR-002, SC-001 */\n")
    write(tmp_path, "tests/fixtures/notes.txt", "998/FR-010 in a file that is no test\n")
    write(tmp_path, "playwright.config.ts", "// 998/FR-010 outside the tests\n")
    assert ct.traceability_problems("998", tmp_path) == [
        'FR-010 of feature 998 is not traced: reference it as 998/FR-010 in a test, or in a test file marked '
        'FEATURE = "998", or justify it in specs/998-*/traceability.md']
    assert "4 requirement(s) defined in specs/998-sample/spec.md, 3 traced" in capsys.readouterr().out
    write(tmp_path, "specs/998-sample/traceability.md", "- 998/FR-010: checked by the evaluation, not a test\n")
    assert ct.traceability_problems("998", tmp_path) == []


def test_a_branch_without_a_feature_skips_traceability_and_a_missing_spec_fails(tmp_path):
    assert ct.traceability_problems(None, tmp_path) == []
    assert ct.traceability_problems("998", tmp_path) == ["no spec for feature 998 (expected specs/998-*/spec.md)"]


def test_main_sends_a_spec_only_pull_request_to_the_spec_check(monkeypatch):
    calls = []
    monkeypatch.setattr(ct, "changed_files", lambda: ["specs/998-x/spec.md"])
    monkeypatch.setattr(ct.check_spec, "main", lambda argv: calls.append(argv) or 0)
    assert ct.main() == 0 and calls == [[]]


def test_main_holds_an_implementation_pull_request_to_the_body_rules(monkeypatch, capsys):
    monkeypatch.setattr(ct, "changed_files", lambda: ["ui/main_page.py"])
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix/something")
    monkeypatch.delenv("PR_BODY", raising=False)
    assert ct.main() == 1
    assert "'Spec-PR: #<n>'" in capsys.readouterr().out
    monkeypatch.setenv("PR_BODY", "Fixes it.\nSpec-PR: #7\n")
    assert ct.main() == 0
    assert "Traceability OK." in capsys.readouterr().out
