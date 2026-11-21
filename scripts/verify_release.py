#!/usr/bin/env python3
"""Verify the checksums and Sigstore signature of a Swarmbly release.

The release workflow writes ``SHA256SUMS`` over the archives, the installer
bundle, the Docker digest and ``SIGNING.txt``, then signs that checksum file
with Sigstore keyless (GitHub OIDC).  This script checks the files first and
then asks ``cosign`` to verify the signature.

It uses only the Python standard library.  Signature verification needs the
``cosign`` binary; ``--checksums-only`` works fully offline when cosign is not
available (but proves only integrity, not who signed the release).

    python scripts/verify_release.py --dir dist
    python scripts/verify_release.py --dir dist --identity-regexp '...'
    python scripts/verify_release.py --dir dist --trusted-root trusted_root.json
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

SUMS_NAME = "SHA256SUMS"
BUNDLE_NAME = "SHA256SUMS.bundle"
SIGNING_NAME = "SIGNING.txt"
DEFAULT_IDENTITY_REGEXP = (
    r"https://github\.com/Sebastardito/SwarmblyAI/"
    r"\.github/workflows/release\.yml@.*"
)
DEFAULT_ISSUER = "https://token.actions.githubusercontent.com"
_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")


class VerifyError(Exception):
    """A release that cannot be verified; the message is for the volunteer."""


def parse_checksums(text: str) -> list[tuple[str, str]]:
    """Return ``(name, lowercase_hex_digest)`` pairs from a SHA256SUMS file."""
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(None, 1)
        if len(fields) != 2:
            raise VerifyError(f"line {number}: expected '<sha256>  <file>'")
        digest, name = fields
        if not _DIGEST.fullmatch(digest):
            raise VerifyError(f"line {number}: not a SHA-256 digest")
        if name.startswith("*"):
            name = name[1:]
        name = name.strip()
        if not name or name.startswith("/") or "\\" in name or "/" in name:
            raise VerifyError(f"line {number}: unsafe or unsupported file name {name!r}")
        if name in (".", "..") or ".." in Path(name).parts:
            raise VerifyError(f"line {number}: unsafe file name {name!r}")
        if name in seen:
            raise VerifyError(f"line {number}: duplicate entry for {name!r}")
        seen.add(name)
        entries.append((name, digest.lower()))
    if not entries:
        raise VerifyError("SHA256SUMS has no entries")
    return entries


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums(directory: str | Path) -> tuple[int, list[str]]:
    """Check every entry.  Returns ``(verified_count, errors)``."""
    root = Path(directory)
    sums_path = root / SUMS_NAME
    try:
        text = sums_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VerifyError(f"cannot read {sums_path}: {exc}") from exc
    entries = parse_checksums(text)
    errors: list[str] = []
    for name, expected in entries:
        target = root / name
        if not target.is_file():
            errors.append(f"{name}: missing")
            continue
        actual = _sha256(target)
        if actual != expected:
            errors.append(f"{name}: checksum mismatch")
    return len(entries) - len(errors), errors


def signature_command(
    sums_path: Path,
    bundle_path: Path,
    *,
    identity: str | None = None,
    identity_regexp: str | None = None,
    issuer: str = DEFAULT_ISSUER,
    trusted_root: str | None = None,
    cosign: str = "cosign",
) -> list[str]:
    """Build the ``cosign verify-blob`` command (no shell)."""
    cmd = [cosign, "verify-blob", "--bundle", str(bundle_path),
           "--certificate-oidc-issuer", issuer]
    if identity:
        cmd += ["--certificate-identity", identity]
    else:
        cmd += ["--certificate-identity-regexp",
                identity_regexp or DEFAULT_IDENTITY_REGEXP]
    if trusted_root:
        cmd += ["--trusted-root", trusted_root]
    cmd.append(str(sums_path))
    return cmd


def verify_signature(
    directory: str | Path,
    *,
    identity: str | None = None,
    identity_regexp: str | None = None,
    issuer: str = DEFAULT_ISSUER,
    trusted_root: str | None = None,
    cosign: str = "cosign",
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> subprocess.CompletedProcess:
    """Run cosign.  Raises VerifyError with its output when it refuses."""
    root = Path(directory)
    command = signature_command(
        root / SUMS_NAME, root / BUNDLE_NAME, identity=identity,
        identity_regexp=identity_regexp, issuer=issuer,
        trusted_root=trusted_root, cosign=cosign)
    try:
        proc = runner(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise VerifyError(
            "cosign is not installed; install it from https://docs.sigstore.dev/cosign/ "
            "or use --checksums-only (integrity only)") from exc
    except OSError as exc:
        raise VerifyError(f"cannot run cosign: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise VerifyError(f"cosign rejected the signature: {detail[-800:]}")
    return proc


def recorded_signing_identity(directory: str | Path) -> dict[str, str]:
    """Read ``SIGNING.txt`` for display only; it is not used for trust."""
    path = Path(directory) / SIGNING_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip()
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify Swarmbly release checksums and Sigstore signature")
    parser.add_argument("--dir", default=".", help="directory with the release files")
    parser.add_argument("--identity", help="exact cosign certificate identity")
    parser.add_argument("--identity-regexp",
                        help="cosign certificate identity regular expression")
    parser.add_argument("--issuer", default=DEFAULT_ISSUER,
                        help="expected OIDC issuer")
    parser.add_argument("--trusted-root",
                        help="Sigstore TrustedRoot JSON for offline verification")
    parser.add_argument("--cosign", default="cosign", help="cosign executable")
    parser.add_argument("--checksums-only", action="store_true",
                        help="skip the signature check (integrity only)")
    args = parser.parse_args(argv)

    try:
        verified, errors = verify_checksums(args.dir)
    except VerifyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("Checksum verification failed:", file=sys.stderr)
        for error in errors:
            print(f"  ✗ {error}", file=sys.stderr)
        return 1
    print(f"✓ {verified} files match {SUMS_NAME}")

    recorded = recorded_signing_identity(args.dir)
    if recorded.get("signer_identity"):
        print(f"  recorded signer: {recorded['signer_identity']}")
    if args.checksums_only:
        print("! signature not checked (--checksums-only): integrity only, not authenticity")
        return 0
    try:
        verify_signature(
            args.dir, identity=args.identity,
            identity_regexp=args.identity_regexp, issuer=args.issuer,
            trusted_root=args.trusted_root, cosign=args.cosign)
    except VerifyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"✓ {BUNDLE_NAME} signs {SUMS_NAME} for issuer {args.issuer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
