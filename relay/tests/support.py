# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helpers for the relay tests: keys, certificates, manifests, relay."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID

from relay.client import RelayAddress
from relay.protocol import b64url, b64url_decode, canonical_bytes
from relay.server import RelayConfig, RelayServer


@dataclass
class TestIdentity:
    node_id: str
    key: ed25519.Ed25519PrivateKey

    def sign(self, data: bytes) -> bytes:
        return self.key.sign(data)


def make_identity() -> TestIdentity:
    key = ed25519.Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return TestIdentity(node_id=b64url(public), key=key)


def make_cert(directory: Path, name: str) -> tuple[Path, Path, str]:
    """Create a self-signed ECDSA certificate and return cert, key, SHA-256 pin."""
    directory.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Swarmbly test"),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                           critical=True)
            .sign(key, hashes.SHA256()))
    cert_path = directory / f"{name}.pem"
    key_path = directory / f"{name}-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    pin = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    return cert_path, key_path, pin


def server_tls_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(str(cert_path), str(key_path))
    return context


def client_tls_context(cert_path: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(str(cert_path))
    return context


def raw_client_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def manifest_payload(owner: TestIdentity, members: list[TestIdentity] | list[str],
                     *, circle_id: str = "circle-test", version: int = 1,
                     relay: RelayAddress | None = None,
                     expires_in_days: int = 30) -> dict[str, Any]:
    member_ids = [m.node_id if isinstance(m, TestIdentity) else m for m in members]
    payload: dict[str, Any] = {
        "circle_id": circle_id,
        "version": version,
        "owner": owner.node_id,
        "members": member_ids,
        "expires_at": (dt.datetime.now(dt.timezone.utc)
                       + dt.timedelta(days=expires_in_days)).isoformat(),
    }
    if relay is not None:
        payload["relay"] = {
            "host": relay.host,
            "port": relay.port,
            "tls_cert_sha256": relay.tls_fingerprint,
        }
    return payload


def sign_manifest(payload: dict[str, Any], owner: TestIdentity) -> dict[str, Any]:
    return {"manifest": payload, "sig": b64url(owner.sign(canonical_bytes(payload)))}


def write_manifest(path: Path, payload: dict[str, Any],
                   owner: TestIdentity) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sign_manifest(payload, owner)), encoding="utf-8")
    return path


class CapturingRelay(RelayServer):
    """Relay that keeps a test-only copy of forwarded bytes."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.forwarded = bytearray()

    def _record_forwarded(self, data: bytes) -> None:
        self.forwarded.extend(data)


async def start_relay(tmp_path: Path, owner: TestIdentity,
                      members: list[TestIdentity] | list[str],
                      *, circle_id: str = "circle-test",
                      **config: Any) -> tuple[CapturingRelay, RelayAddress]:
    cert, key, pin = make_cert(tmp_path, "relay")
    manifest = tmp_path / "circles" / "circle.json"
    config.setdefault("host", "127.0.0.1")
    config.setdefault("port", 0)
    server = CapturingRelay(RelayConfig(
        manifests=(manifest,), certfile=cert, keyfile=key, **config))
    await server.start()
    address = RelayAddress("127.0.0.1", server.port, pin)
    write_manifest(manifest, manifest_payload(owner, members,
                                              circle_id=circle_id, relay=address),
                   owner)
    server.store.reload(force=True)
    return server, address


async def raw_connection(address: RelayAddress):
    reader, writer = await asyncio.open_connection(
        address.host, address.port, ssl=raw_client_context(),
        server_hostname=address.host)
    return reader, writer


async def close_writer(writer: asyncio.StreamWriter) -> None:
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


def decode_nonce(message: dict[str, Any]) -> bytes:
    return b64url_decode(str(message.get("nonce") or ""))
