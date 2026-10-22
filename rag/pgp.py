"""Signature check of the Swedish Customs TARIC files with the GnuPG command-line tool (feature 002, research R-02).

gpg runs in a throwaway home with no file path on its command line, because Git for Windows' gpg treats Windows paths
as relative: the key and the signed data go in on stdin and the payload comes back on stdout. The payload is returned
only after the status lines prove one valid signature by the pinned key, because gpg writes one-pass-signed content
before it has checked the signature. No network access and no secret key are involved.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from agent.config import GPG_ENV

_FAILURES = {"BADSIG", "ERRSIG", "NO_PUBKEY", "EXPKEYSIG", "REVKEYSIG"}


class GpgNotFound(Exception):
    """No gpg executable was found."""


class SignatureError(Exception):
    """A key copy or a signed file failed the check."""


def find_gpg() -> str:
    """CARGOLINT_GPG, then gpg on PATH, then Git for Windows' usr/bin/gpg.exe next to git."""
    explicit = os.environ.get(GPG_ENV)
    if explicit:
        if Path(explicit).is_file():
            return explicit
        raise GpgNotFound(f"{GPG_ENV} points to {explicit}, which does not exist")
    on_path = shutil.which("gpg")
    if on_path:
        return on_path
    git = shutil.which("git")
    if git:
        for folder in list(Path(git).parents)[:3]:      # <Git>/cmd/git.exe, <Git>/bin/git.exe, <Git>/mingw64/bin/git.exe
            candidate = folder / "usr" / "bin" / "gpg.exe"
            if candidate.is_file():
                return str(candidate)
    raise GpgNotFound(f"gpg not found: set {GPG_ENV}, put gpg on PATH or install Git for Windows")


def _gpg(home: str, args: list[str], data: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([find_gpg(), "--homedir", ".", "--batch", "--no-tty", *args], input=data, cwd=home,
                          capture_output=True, timeout=300)


def _primary_fingerprints(colons: str) -> list[str]:
    lines = colons.splitlines()
    return [line.split(":")[9] for i, line in enumerate(lines) if line.startswith("fpr:") and i and lines[i - 1].startswith("pub:")]


def check_key_copy(key_path: Path, fingerprint: str) -> None:
    """The key copy must hold exactly one primary key, with the pinned fingerprint; SignatureError otherwise."""
    key = Path(key_path).read_bytes()
    with tempfile.TemporaryDirectory(prefix="cargolint-gpg-", ignore_cleanup_errors=True) as home:
        r = _gpg(home, ["--with-colons", "--import-options", "show-only", "--import"], key)
    found = _primary_fingerprints(r.stdout.decode("utf-8", "replace"))
    if r.returncode != 0 or found != [fingerprint]:
        raise SignatureError(f"the key copy {Path(key_path).name} holds {', '.join(found) or 'no readable key'}, "
                             f"not the pinned key {fingerprint}")


def verify_signed(data: bytes, key_path: Path, fingerprint: str) -> bytes:
    """The signed content, returned only when gpg reports one valid signature made by the pinned key."""
    key = Path(key_path).read_bytes()
    with tempfile.TemporaryDirectory(prefix="cargolint-gpg-", ignore_cleanup_errors=True) as home:
        imported = _gpg(home, ["--import"], key)
        if imported.returncode != 0:
            raise SignatureError(f"gpg could not import the key copy {Path(key_path).name}")
        r = _gpg(home, ["--no-auto-key-retrieve", "--status-fd", "2", "--output", "-", "--decrypt"], data)
    status = [line[9:].split() for line in r.stderr.decode("utf-8", "replace").splitlines() if line.startswith("[GNUPG:] ")]
    keywords = {s[0] for s in status if s}
    valid = [s for s in status if s and s[0] == "VALIDSIG"]
    if r.returncode != 0 or keywords & _FAILURES or len(valid) != 1 or len(valid[0]) < 11 or valid[0][10] != fingerprint:
        if len(valid) == 1 and len(valid[0]) >= 11 and not keywords & _FAILURES:
            reason = f"signed by key {valid[0][10]}"
        else:
            reason = ", ".join(sorted(keywords & _FAILURES)) or f"gpg exit code {r.returncode}"
        raise SignatureError(f"signature not made by key {fingerprint} ({reason})")
    return r.stdout
