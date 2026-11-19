"""The spec check of a spec-only pull request (.github/workflows/traceability.yml; docs/qa-platform.md, "Traceability").
Adapted from the Kestrel project's scripts/check_spec.py.

    python scripts/check_spec.py [specs/<feature folder>]

Checks the FR-### and SC-### identifiers of a feature folder. spec.md defines them, one "- **FR-001**" line each; the
same line in another file (a success criterion restated in quickstart.md) defines nothing. The check fails when an
identifier in the folder's markdown files is malformed (FR or SC, a hyphen and three digits) or spec.md defines one
more than once; gaps in the numbering are allowed. Another feature's requirement written with its feature is no
reference of this one: 002/FR-020 (or 002-FR-020), "feature 002's FR-020", "(feature 002, FR-020)" and "feature 002
FR-020". Any other identifier that spec.md does not define is a warning, not a failure: another feature's requirement
written without its feature ("its FR-018"), or a typo. Identifiers in code spans and fenced code blocks are ignored,
so examples there never count. Without an argument the folder is the one of the branch's feature label (branch
014a-retrieval-evidence: specs/014a-*); a branch without a label, or without a folder for it, has nothing to check.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL_RE = re.compile(r"(\d{3}[a-z]?)-")                # a feature label at the start of a branch: 013-, 014a-
DEF_RE = re.compile(r"^- \*\*((?:FR|SC)-\d+)\*\*", re.MULTILINE)
TOKEN_RE = re.compile(r"\b(?:FR|SC)-\d+\b")
WELL_FORMED_RE = re.compile(r"^(?:FR|SC)-\d{3}$")
EXTERNAL_RE = re.compile(r"(?<![\w-])\d{3}[a-z]?[-/](?:FR|SC)-\d+\b"                    # 002/FR-020, 002-FR-020
                         r"|\b[Ff]eature\s+\d{3}[a-z]?(?:['’]s|,)?\s+(?:FR|SC)-\d+\b")  # feature 002's FR-020, …
FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_RE = re.compile(r"`[^`]*`")


def strip_code(text: str) -> str:
    """The text without its fenced code blocks and inline code spans."""
    return INLINE_RE.sub(" ", FENCED_RE.sub(" ", text))


def definitions(feature_dir: Path) -> Counter[str]:
    """How often spec.md defines each identifier; nothing without a spec.md."""
    spec = feature_dir / "spec.md"
    return Counter(DEF_RE.findall(strip_code(spec.read_text(encoding="utf-8")))) if spec.exists() else Counter()


def references(feature_dir: Path) -> dict[str, list[str]]:
    """Each identifier the folder's markdown files mention, with those files; another feature's requirements written
    with their feature left out."""
    found: dict[str, set[str]] = {}
    for md in sorted(feature_dir.rglob("*.md")):
        prose = EXTERNAL_RE.sub(" ", strip_code(md.read_text(encoding="utf-8")))
        for identifier in TOKEN_RE.findall(prose):
            found.setdefault(identifier, set()).add(md.relative_to(feature_dir).as_posix())
    return {identifier: sorted(files) for identifier, files in sorted(found.items())}


def check(feature_dir: Path) -> list[str]:
    """The problems that fail the check: malformed identifiers, and identifiers spec.md defines more than once."""
    defined, mentioned = definitions(feature_dir), references(feature_dir)
    problems = [f"malformed identifier: {i} (expected FR-### or SC-### with three digits)"
                for i in sorted(set(defined) | set(mentioned)) if not WELL_FORMED_RE.match(i)]
    problems += [f"duplicate definition: {i} is defined {n} times in spec.md"
                 for i, n in sorted(defined.items()) if n > 1]
    return problems


def orphans(feature_dir: Path) -> dict[str, list[str]]:
    """The warnings: each well-formed identifier that spec.md does not define, with the files that mention it."""
    defined = definitions(feature_dir)
    return {i: files for i, files in references(feature_dir).items() if WELL_FORMED_RE.match(i) and i not in defined}


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
    warnings = orphans(folder)
    prefix = "::warning title=Spec check::" if os.environ.get("GITHUB_ACTIONS") == "true" else "warning: "
    for i, files in warnings.items():
        print(f"{prefix}{i} is referenced in {', '.join(files)} but not defined in spec.md; write another feature's "
              f"requirement with its feature, as <feature>/{i} or \"feature <feature>'s {i}\"")
    defined = definitions(folder)
    fr = sum(1 for i in defined if i.startswith("FR"))
    note = f"; {len(warnings)} undefined reference(s), see the warnings" if warnings else ""
    print(f"{rel}: {fr} FR and {len(defined) - fr} SC defined in spec.md; all well-formed and unique{note}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
