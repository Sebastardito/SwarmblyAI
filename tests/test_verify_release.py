"""Release verification: checksums, path safety and a mocked cosign call."""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "verify_release", ROOT / "scripts" / "verify_release.py")
verify_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_release)


def _write_release(directory: Path, files: dict[str, bytes],
                   *, lines: list[str] | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    sums: list[str] = []
    for name, data in files.items():
        (directory / name).write_bytes(data)
        sums.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    text = "\n".join(lines if lines is not None else sums) + "\n"
    sums_path = directory / verify_release.SUMS_NAME
    sums_path.write_text(text, encoding="utf-8")
    return sums_path


def test_a_good_release_passes_and_reports_every_file(tmp_path):
    _write_release(tmp_path, {"a.tar.gz": b"alpha", "b.zip": b"beta"})
    verified, errors = verify_release.verify_checksums(tmp_path)
    assert verified == 2
    assert errors == []


def test_a_tampered_artifact_fails(tmp_path):
    _write_release(tmp_path, {"a.tar.gz": b"alpha"})
    (tmp_path / "a.tar.gz").write_bytes(b"tampered")
    verified, errors = verify_release.verify_checksums(tmp_path)
    assert verified == 0
    assert errors == ["a.tar.gz: checksum mismatch"]


def test_a_missing_artifact_fails(tmp_path):
    _write_release(tmp_path, {"a.tar.gz": b"alpha"})
    (tmp_path / "a.tar.gz").unlink()
    _, errors = verify_release.verify_checksums(tmp_path)
    assert errors == ["a.tar.gz: missing"]


def test_path_traversal_and_absolute_names_are_refused():
    digest = "0" * 64
    for line in (f"{digest}  ../evil", f"{digest}  /etc/passwd",
                 f"{digest}  dir/file"):
        with pytest.raises(verify_release.VerifyError):
            verify_release.parse_checksums(line + "\n")


def test_duplicate_and_malformed_entries_are_refused():
    digest = "a" * 64
    with pytest.raises(verify_release.VerifyError):
        verify_release.parse_checksums(f"{digest}  a\n{digest}  a\n")
    with pytest.raises(verify_release.VerifyError):
        verify_release.parse_checksums("not-a-digest  a\n")
    with pytest.raises(verify_release.VerifyError):
        verify_release.parse_checksums("")


def test_the_signature_command_uses_the_pinned_release_identity(tmp_path):
    sums = tmp_path / verify_release.SUMS_NAME
    bundle = tmp_path / verify_release.BUNDLE_NAME
    sums.write_text("", encoding="utf-8")
    bundle.write_bytes(b"bundle")
    cmd = verify_release.signature_command(sums, bundle)
    assert cmd[:2] == ["cosign", "verify-blob"]
    assert "--bundle" in cmd and str(bundle) in cmd
    assert "--certificate-identity-regexp" in cmd
    assert cmd[cmd.index("--certificate-identity-regexp") + 1] == \
        verify_release.DEFAULT_IDENTITY_REGEXP
    assert cmd[cmd.index("--certificate-oidc-issuer") + 1] == \
        verify_release.DEFAULT_ISSUER
    assert str(sums) == cmd[-1]


def test_a_mocked_cosign_accepts_and_a_failure_is_reported(tmp_path):
    sums = tmp_path / verify_release.SUMS_NAME
    bundle = tmp_path / verify_release.BUNDLE_NAME
    sums.write_text("", encoding="utf-8")
    bundle.write_bytes(b"bundle")
    calls = []

    def good(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "ok", "")

    proc = verify_release.verify_signature(
        tmp_path, identity="https://example.test/release", runner=good)
    assert proc.returncode == 0
    assert calls and calls[0][0][calls[0][0].index("--certificate-identity") + 1] == \
        "https://example.test/release"

    def bad(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "signature rejected")

    with pytest.raises(verify_release.VerifyError) as exc:
        verify_release.verify_signature(tmp_path, runner=bad)
    assert "signature rejected" in str(exc.value)


def test_cli_checksums_only_needs_no_cosign(tmp_path, capsys):
    _write_release(tmp_path, {"a.tar.gz": b"alpha"})
    assert verify_release.main(["--dir", str(tmp_path), "--checksums-only",
                                "--cosign", "/nonexistent/cosign"]) == 0
    out = capsys.readouterr().out
    assert "1 files match" in out
    assert "integrity only" in out


def test_cli_reports_checksum_failure_with_exit_code(tmp_path, capsys):
    _write_release(tmp_path, {"a.tar.gz": b"alpha"})
    (tmp_path / "a.tar.gz").write_bytes(b"tampered")
    assert verify_release.main(["--dir", str(tmp_path), "--checksums-only"]) == 1
    assert "checksum mismatch" in capsys.readouterr().err
