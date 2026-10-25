"""Ed25519 signatures for capsules (SWIP 9.4).

The ``cryptography`` package is an optional dependency. Everything that only
reads, validates bounds or computes identifiers works without it; signing and
signature verification raise :class:`CryptoUnavailable` when it is missing,
instead of silently accepting unsigned data.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from .errors import CryptoUnavailable

__all__ = ["Keypair", "generate_keypair", "keypair_from_seed", "sign", "verify", "crypto_available", "b64u", "unb64u"]

try:  # pragma: no cover - import guard
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover
    _HAVE_CRYPTO = False


def crypto_available() -> bool:
    return _HAVE_CRYPTO


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64u(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _require() -> None:
    if not _HAVE_CRYPTO:
        raise CryptoUnavailable("install the 'crypto' extra: pip install 'swarmbly-lce[crypto]'")


@dataclass(frozen=True)
class Keypair:
    """An Ed25519 keypair. ``public`` is the base64url node identifier."""

    private_bytes: bytes
    public: str

    def __repr__(self) -> str:  # never print private material
        return f"Keypair(public={self.public!r})"


def keypair_from_seed(seed: bytes) -> Keypair:
    """Deterministic keypair from a 32-byte seed (tests and simulations)."""
    _require()
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    pk = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return Keypair(private_bytes=seed, public=b64u(pk))


def generate_keypair() -> Keypair:
    _require()
    sk = Ed25519PrivateKey.generate()
    seed = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return keypair_from_seed(seed)


def sign(keypair: Keypair, message: bytes) -> str:
    _require()
    sk = Ed25519PrivateKey.from_private_bytes(keypair.private_bytes)
    return b64u(sk.sign(message))


def verify(public: str, message: bytes, signature: str) -> bool:
    """Return True iff ``signature`` is a valid Ed25519 signature by ``public``."""
    _require()
    try:
        pk = Ed25519PublicKey.from_public_bytes(unb64u(public))
        pk.verify(unb64u(signature), message)
        return True
    except (InvalidSignature, ValueError):
        return False
