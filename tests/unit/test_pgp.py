"""Signature check of the TARIC files with gpg (feature 002, FR-002, research R-02). Tests that call gpg skip when it is missing."""
import gzip
import json
import shutil
from pathlib import Path

import pytest

from rag.pgp import GpgNotFound, SignatureError, check_key_copy, find_gpg, verify_signed

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "taric"
EXPECTED = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
FIXTURE_KEY, OTHER_KEY = FIX / "keys" / "fixture.asc", FIX / "keys" / "other.asc"
FIXTURE_FPR = EXPECTED["fixture_key_fingerprint"]
REAL_KEY = ROOT / "data" / "Tulltaxan_Fildistribution.asc"
REAL_FPR = "410160CE25CEC2FF322784E7302AC3C1D0E3E1C9"


def _signed(folder: Path, obj: str = "MeasureType") -> bytes:
    return next(folder.glob(f"{obj}_*.xml.gz.pgp")).read_bytes()


try:
    find_gpg()
    HAVE_GPG = True
except GpgNotFound:
    HAVE_GPG = False
needs_gpg = pytest.mark.skipif(not HAVE_GPG, reason="gpg not found")


@needs_gpg
class TestVerifySigned:
    def test_accepts_a_file_signed_by_the_pinned_key(self):
        payload = verify_signed(_signed(FIX / "extract"), FIXTURE_KEY, FIXTURE_FPR)
        assert gzip.decompress(payload) == (FIX / "xml" / "MeasureType.xml").read_bytes()

    @pytest.mark.parametrize("variant", ["tampered", "other_key"])
    def test_refuses_a_tampered_file_or_another_signer(self, variant):
        with pytest.raises(SignatureError):
            verify_signed(_signed(FIX / "bad" / variant), FIXTURE_KEY, FIXTURE_FPR)

    def test_refuses_a_valid_signature_by_a_key_that_is_not_pinned(self):
        with pytest.raises(SignatureError):
            verify_signed(_signed(FIX / "extract"), FIXTURE_KEY, EXPECTED["other_key_fingerprint"])

    def test_real_swedish_customs_file_verifies_against_the_project_key_copy(self):
        payload = verify_signed(_signed(FIX / "real", "DutyExpression"), REAL_KEY, REAL_FPR)
        assert b"<exportType>DutyExpressionObject</exportType>" in gzip.decompress(payload)


@needs_gpg
class TestKeyCopy:
    def test_the_project_key_copy_carries_the_pinned_fingerprint(self):
        check_key_copy(REAL_KEY, REAL_FPR)

    @pytest.mark.parametrize("key", [FIXTURE_KEY, OTHER_KEY])
    def test_a_key_copy_with_another_fingerprint_is_refused(self, key):
        with pytest.raises(SignatureError):
            check_key_copy(key, REAL_FPR)


class TestFindGpg:
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        monkeypatch.delenv("CARGOLINT_GPG", raising=False)

    def test_the_environment_variable_comes_first(self, tmp_path, monkeypatch):
        exe = tmp_path / "gpg.exe"
        exe.write_bytes(b"")
        monkeypatch.setenv("CARGOLINT_GPG", str(exe))
        monkeypatch.setattr(shutil, "which", lambda name: "C:/elsewhere/gpg.exe")
        assert find_gpg() == str(exe)

    def test_an_environment_variable_that_points_nowhere_is_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CARGOLINT_GPG", str(tmp_path / "missing.exe"))
        with pytest.raises(GpgNotFound):
            find_gpg()

    def test_then_path(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "C:/tools/gpg.exe" if name == "gpg" else None)
        assert find_gpg() == "C:/tools/gpg.exe"

    def test_then_git_for_windows(self, tmp_path, monkeypatch):
        git = tmp_path / "Git" / "cmd" / "git.exe"
        gpg = tmp_path / "Git" / "usr" / "bin" / "gpg.exe"
        for f in (git, gpg):
            f.parent.mkdir(parents=True)
            f.write_bytes(b"")
        monkeypatch.setattr(shutil, "which", lambda name: str(git) if name == "git" else None)
        assert Path(find_gpg()) == gpg

    def test_none_found(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(GpgNotFound):
            find_gpg()
