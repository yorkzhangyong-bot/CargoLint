"""The spec check of a spec-only pull request (the traceability job in .github/workflows/tests.yml; docs/qa-platform.md).
Adapted from the Kestrel project's scripts/check_spec.py.

    python scripts/check_spec.py [specs/<feature folder>]

Checks the FR-### and SC-### identifiers of a feature folder across all its markdown files (spec.md, plan.md, tasks.md,
contracts/, checklists/ …): each is well-formed (FR or SC, a hyphen and three digits), each is defined at most once (a
"- **FR-001**" line), and each one referenced is defined somewhere in the folder. Gaps in the numbering are allowed.
Identifiers in code spans and fenced code blocks are ignored, so examples there never count. Without an argument the
folder is the one of the branch's feature label (branch 014a-retrieval-evidence: specs/014a-*); a branch without a
label, or without a folder for it, has nothing to check.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL_RE = re.compile(r"(\d{3}[a-z]?)-")                # a feature label at the start of a branch: 013-, 014a-
DEF_RE = re.compile(r"^- \*\*((?:FR|SC)-\d+)\*\*", re.MULTILINE)
TOKEN_RE = re.compile(r"\b(?:FR|SC)-\d+\b")
WELL_FORMED_RE = re.compile(r"^(?:FR|SC)-\d{3}$")
FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_RE = re.compile(r"`[^`]*`")


def strip_code(text: str) -> str:
    """The text without its fenced code blocks and inline code spans."""
    return INLINE_RE.sub(" ", FENCED_RE.sub(" ", text))


def scan(feature_dir: Path) -> tuple[dict[str, int], set[str]]:
    """How often each identifier is defined, and every identifier mentioned, in the folder's markdown files."""
    definitions: dict[str, int] = {}
    references: set[str] = set()
    for md in sorted(feature_dir.rglob("*.md")):
        prose = strip_code(md.read_text(encoding="utf-8"))
        for match in DEF_RE.finditer(prose):
            definitions[match.group(1)] = definitions.get(match.group(1), 0) + 1
        references.update(TOKEN_RE.findall(prose))
    return definitions, references


def check(feature_dir: Path) -> list[str]:
    """The problems with a feature folder's identifiers; [] means valid."""
    definitions, references = scan(feature_dir)
    problems = [f"malformed identifier: {i} (expected FR-### or SC-### with three digits)"
                for i in sorted(set(definitions) | references) if not WELL_FORMED_RE.match(i)]
    problems += [f"duplicate definition: {i} is defined {n} times" for i, n in sorted(definitions.items()) if n > 1]
    problems += [f"orphan reference: {i} is referenced but never defined"
                 for i in sorted(references) if WELL_FORMED_RE.match(i) and i not in definitions]
    return problems


def branch_name() -> str:
    """The pull request's source branch in CI (GITHUB_HEAD_REF), else the current git branch."""
    ref = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if ref:
        return ref
    done = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return done.stdout.strip()


def feature_label(branch: str) -> str | None:
    """The feature label a branch starts with ("014a" for 014a-retrieval-evidence), or None."""
    match = LABEL_RE.match(branch)
    return match.group(1) if match else None


def feature_dir(label: str, root: Path = ROOT) -> Path | None:
    """The feature's folder, specs/<label>-*, or None."""
    matches = sorted(p for p in root.glob(f"specs/{label}-*") if p.is_dir())
    return matches[0] if matches else None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        folder = Path(args[0]) if Path(args[0]).is_absolute() else ROOT / args[0]
    else:
        label = feature_label(branch_name())
        folder = feature_dir(label) if label else None
        if folder is None:
            print("The branch names no feature with a folder under specs/; no spec to check.")
            return 0
    if not folder.is_dir():
        print(f"Feature folder not found: {folder}")
        return 1
    rel = folder.relative_to(ROOT).as_posix() if folder.is_relative_to(ROOT) else str(folder)
    problems = check(folder)
    if problems:
        print(f"Spec check failed for {rel}:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    definitions, _ = scan(folder)
    fr = sum(1 for i in definitions if i.startswith("FR"))
    print(f"{rel}: {fr} FR and {len(definitions) - fr} SC defined; all well-formed, unique, no orphan references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
