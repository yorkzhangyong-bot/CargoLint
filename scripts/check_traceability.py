"""The traceability check of a pull request (.github/workflows/traceability.yml; docs/qa-platform.md). Adapted from
the Kestrel project's scripts/check_traceability.py.

    python scripts/check_traceability.py

The changed files decide the pull request's kind. A spec-only pull request, one that changes none of the app, its
tests, scripts and data, gets the spec check of scripts/check_spec.py. An implementation pull request gets two checks:

1. Tests-traceability for the feature the branch names (014a-retrieval-evidence: feature 014a). Every FR-### and SC-###
   defined in specs/<label>-*/spec.md is referenced by a test that names the feature: a scoped token such as
   014a/FR-001 (or 014a-FR-001) anywhere in a test, or a bare FR-001 in a test file with a module-level marker
   FEATURE = "014a" (const FEATURE = '014a' in TypeScript). Or it is justified in specs/<label>-*/traceability.md by a
   line "014a/FR-001: <reason>". The tests are tests/**/*.py and the Playwright tests, tests/e2e-browser/**/*.ts. A
   branch without a feature label skips this check.
2. The pull-request body rules: a pull request that changes the app (app.py, agent/, tools/, rag/, ui/) carries a
   "Spec-PR: #<n>" line, whatever its branch; one that also changes a file under specs/ carries a
   "spec-change: <reason>" line.

The base branch comes from GITHUB_BASE_REF, the branch from GITHUB_HEAD_REF and the description from PR_BODY. Outside a
pull request (no GITHUB_BASE_REF) nothing has changed, and only tests-traceability runs, for the current branch.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import check_spec

ROOT = check_spec.ROOT
PLAYWRIGHT_DIR = "tests/e2e-browser"
APP_PATHS = ("app.py", "agent/", "tools/", "rag/", "ui/")      # the app: a change needs a Spec-PR line
CODE_PATHS = APP_PATHS + ("tests/", "scripts/", "data/")       # a pull request that changes none of these is spec-only
SPEC_PR_RE = re.compile(r"(?im)^Spec-PR:[ \t]*#\d+")
SPEC_CHANGE_RE = re.compile(r"(?im)^spec-change:[ \t]*\S")      # the reason on the same line


def _under(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p if not p.endswith("/") else path.startswith(p) for p in prefixes)


def is_spec_only(files: list[str]) -> bool:
    """True when the pull request changes none of the app, its tests, scripts and data."""
    return not any(_under(f, CODE_PATHS) for f in files)


def changes_app(files: list[str]) -> bool:
    return any(_under(f, APP_PATHS) for f in files)


def pr_rule_problems(files: list[str], body: str | None) -> list[str]:
    """The pull-request body rules for an implementation pull request's changed files and description."""
    problems = []
    if changes_app(files) and not SPEC_PR_RE.search(body or ""):
        problems.append("a pull request that changes the app (app.py, agent/, tools/, rag/, ui/) needs a "
                        "'Spec-PR: #<n>' line in its description")
    if changes_app(files) and any(f.startswith("specs/") for f in files) and not SPEC_CHANGE_RE.search(body or ""):
        problems.append("a pull request that changes a spec file together with the app needs a "
                        "'spec-change: <reason>' line in its description")
    return problems


def spec_ids(spec: Path) -> list[str]:
    """The FR and SC identifiers spec.md defines ("- **FR-001**" lines), in order."""
    found = set(check_spec.DEF_RE.findall(check_spec.strip_code(spec.read_text(encoding="utf-8"))))
    return sorted(found, key=lambda i: (i[:2], int(i[3:])))


def scanned_files(root: Path = ROOT) -> list[Path]:
    """The Python tests under tests/ and the Playwright tests."""
    return sorted((root / "tests").rglob("*.py")) + sorted((root / PLAYWRIGHT_DIR).rglob("*.ts"))


def traced_ids(label: str, files: list[Path]) -> set[str]:
    """The identifiers the files reference for the feature: scoped tokens, and bare ones in a file with its marker."""
    scoped = re.compile(rf"\b{re.escape(label)}[-/]((?:FR|SC)-\d+)\b")
    marker = re.compile(rf"(?m)^\s*(?:export\s+)?(?:(?:const|let|var)\s+)?FEATURE\s*=\s*[\"']{re.escape(label)}[\"']")
    traced: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        traced.update(scoped.findall(text))
        if marker.search(text):
            traced.update(check_spec.TOKEN_RE.findall(text))
    return traced


def justified_ids(text: str, label: str) -> set[str]:
    """The identifiers a traceability.md justifies, as lines "<label>/FR-001: <reason>"."""
    return set(re.findall(rf"(?m)^[ \t]*-?[ \t]*{re.escape(label)}[-/]((?:FR|SC)-\d+):[ \t]*\S", text))


def traceability_problems(label: str | None, root: Path = ROOT) -> list[str]:
    if label is None:
        print("No feature label at the start of the branch name; tests-traceability skipped.")
        return []
    folder = check_spec.feature_dir(label, root)
    if folder is None or not (folder / "spec.md").exists():
        return [f"no spec for feature {label} (expected specs/{label}-*/spec.md)"]
    ids = spec_ids(folder / "spec.md")
    traced = traced_ids(label, scanned_files(root))
    if (folder / "traceability.md").exists():
        traced |= justified_ids((folder / "traceability.md").read_text(encoding="utf-8"), label)
    untraced = [i for i in ids if i not in traced]
    print(f"Feature {label}: {len(ids)} requirement(s) defined in {folder.relative_to(root).as_posix()}/spec.md, "
          f"{len(ids) - len(untraced)} traced by a test or traceability.md.")
    return [f"{i} of feature {label} is not traced: reference it as {label}/{i} in a test, or in a test file marked "
            f"FEATURE = \"{label}\", or justify it in specs/{label}-*/traceability.md" for i in untraced]


def changed_files() -> list[str]:
    """The pull request's changed files against its base branch; none outside a pull request."""
    base = os.environ.get("GITHUB_BASE_REF")
    if not base:
        return []
    subprocess.run(["git", "fetch", "--quiet", "origin", base], cwd=ROOT, capture_output=True, text=True)
    done = subprocess.run(["git", "diff", "--name-only", f"origin/{base}...HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True)
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def main() -> int:
    files = changed_files()
    if files and is_spec_only(files):
        print("Spec-only pull request: the spec check.")
        return check_spec.main([])
    print("Implementation pull request: tests-traceability and the pull-request body rules." if files
          else "No pull request: tests-traceability only.")
    problems = pr_rule_problems(files, os.environ.get("PR_BODY")) + \
        traceability_problems(check_spec.feature_label(check_spec.branch_name()))
    if problems:
        print("Traceability check failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Traceability OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
