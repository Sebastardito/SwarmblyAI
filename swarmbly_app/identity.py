"""Persistent Ed25519 node identity (SPEC v0.2 §4).

``node_id`` is the Ed25519 public key, base64url without padding. The identity
is generated once and stored with 0600 permissions in the data directory.
The node is never identified by its IP address.
"""

from __future__ import annotations

import base64
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def b64url(data: bytes) -> str:
    """base64url without padding — the SPEC encoding for node_id."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    public_bytes: bytes

    def short_id(self, length: int = 8) -> str:
        return self.node_id[:length]


class IdentityManager:
    """Loads or creates the node key pair."""

    def __init__(self, key_path: str | Path):
        self._path = Path(key_path)
        self._lock = threading.Lock()

    def load_or_create(self) -> NodeIdentity:
        with self._lock:
            if self._path.exists():
                return self._load()
            return self._create()

    def _load(self) -> NodeIdentity:
        raw = self._path.read_bytes()
        private = serialization.load_ssh_private_key(raw, password=None)
        if not isinstance(private, ed25519.Ed25519PrivateKey):
            raise ValueError("stored key is not Ed25519")
        public = private.public_key()
        public_bytes = public.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return NodeIdentity(node_id=b64url(public_bytes),
                            public_bytes=public_bytes)

    def _create(self) -> NodeIdentity:
        private = ed25519.Ed25519PrivateKey.generate()
        public = private.public_key()
        public_bytes = public.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        ssh = private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption())
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(ssh)
        return NodeIdentity(node_id=b64url(public_bytes),
                            public_bytes=public_bytes)

    def sign(self, message: bytes) -> bytes:
        raw = self._path.read_bytes()
        private = serialization.load_ssh_private_key(raw, password=None)
        return private.sign(message)

    def public_bytes(self) -> bytes:
        return self.load_or_create().public_bytes


def verify_signature(node_id: str, message: bytes, signature: bytes) -> bool:
    """Verify a signature against a peer's advertised node_id (public key)."""
    try:
        public = ed25519.Ed25519PublicKey.from_public_bytes(
            b64url_decode(node_id))
        public.verify(signature, message)
        return True
    except Exception:
        return False
