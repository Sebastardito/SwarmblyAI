"""P2P transport: TLS 1.3 (stdlib ssl) with length-prefixed JSON frames.

The channel is encrypted with a per-node self-signed certificate; node
identity is authenticated at the application layer by Ed25519 signatures over
the handshake transcript (SPEC §4: TLS 1.3 or Noise + Ed25519 identity).
Mutual TLS arrives with the TRUSTED tier (Phase 2.1); the identity signature
exchange already authenticates both endpoints on every link.

The P2P listener is independent of the admin API: separate socket, separate
access limits (product spec §3.2).
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import os
import ssl
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from ..identity import IdentityManager
from .messages import (HELLO_TIMEOUT_S, encode_frame, decode_frame, WireError)

FrameHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]


def generate_cert(cert_path: Path, key_path: Path) -> None:
    """Self-signed per-node certificate (ECDSA P-256), cached on disk."""
    if cert_path.exists() and key_path.exists():
        return
    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "swarmbly-node"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Swarmbly"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(int.from_bytes(uuid.uuid4().bytes[:8], "big"))
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # The TLS private key gets the same 0600 treatment as the Ed25519 key.
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))


def cert_fingerprint(cert_path: Path) -> str:
    """SHA-256 over the DER certificate, hex. Signed into the handshake."""
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def peer_fingerprint(writer: asyncio.StreamWriter) -> str:
    """Fingerprint of the certificate the remote endpoint actually presented."""
    try:
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
    except Exception:
        der = None
    return hashlib.sha256(der).hexdigest() if der else ""


def server_ssl_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(str(cert_path), str(key_path))
    return context


def client_ssl_context() -> ssl.SSLContext:
    """No CA in P2P: the certificate is not validated by TLS. Instead its
    fingerprint is bound to the peer's Ed25519 identity in the handshake
    (see handshake.py), so a substituted certificate is rejected."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


@dataclass
class PeerSession:
    """One authenticated connection to a peer."""

    node_id: str
    address: str
    port: int
    advertisement: dict[str, Any]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    initiator: bool = False
    connected_at: float = 0.0
    last_seen: float = 0.0
    write_lock: asyncio.Lock | None = None

    def close(self) -> None:
        try:
            self.writer.close()
        except Exception:
            pass
        try:  # abort the transport so pending reads end immediately
            transport = self.writer.transport
            if transport is not None:
                transport.abort()
        except Exception:
            pass


async def read_frame(reader: asyncio.StreamReader) -> dict[str, Any]:
    header = await reader.readexactly(4)
    (length,) = struct.unpack(">I", header)
    if length > 4 * 1024 * 1024:
        raise WireError(f"frame too large: {length}")
    body = await reader.readexactly(length)
    return decode_frame(header + body)


async def write_frame(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
    writer.write(encode_frame(message))
    await writer.drain()


async def read_frame_with_timeout(reader: asyncio.StreamReader,
                                  timeout: float) -> dict[str, Any]:
    return await asyncio.wait_for(read_frame(reader), timeout=timeout)


class TLSServer:
    """Accepts TLS connections and hands authenticated sessions to the node."""

    def __init__(self, host: str, port: int, cert_path: Path, key_path: Path,
                 on_session: Callable[[PeerSession, bool], Awaitable[None]]):
        self.host = host
        self.port = port
        self._ctx = server_ssl_context(cert_path, key_path)
        self._on_session = on_session
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle, self.host, self.port, ssl=self._ctx)

    async def _handle(self, reader: asyncio.StreamReader,
                      writer: asyncio.StreamWriter) -> None:
        try:
            # The first message must be a HELLO within the handshake window.
            hello = await read_frame_with_timeout(reader, HELLO_TIMEOUT_S)
            if hello.get("type") != "hello":
                writer.close()
                return
            peer_address = ""
            peer_port = 0
            try:
                sock = writer.get_extra_info("socket")
                peer_address = sock.getpeername()[0]  # type: ignore[index]
                peer_port = sock.getpeername()[1]  # type: ignore[index]
            except Exception:
                pass
            session = PeerSession(
                node_id=str(hello.get("node_id", "")),
                address=peer_address, port=peer_port,
                advertisement=hello.get("advertisement") or {},
                reader=reader, writer=writer, initiator=False)
            # The hello has already been consumed; pass it to the node manager
            # so the handshake continues from hello_ack.
            await self._on_session(session, hello)  # inbound
        except Exception:
            writer.close()

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()


async def dial(host: str, port: int, hello_message: dict[str, Any],
               timeout: float = HELLO_TIMEOUT_S
               ) -> tuple[PeerSession, dict[str, Any], str]:
    """Initiate: TLS → HELLO → HELLO_ACK. Returns session, ack and the
    fingerprint of the certificate the responder presented."""
    ctx = client_ssl_context()
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port, ssl=ctx), timeout=timeout)
    observed = peer_fingerprint(writer)
    session = PeerSession(
        node_id="", address=host, port=port, advertisement={},
        reader=reader, writer=writer, initiator=True)
    await write_frame(writer, hello_message)
    ack_message = await read_frame_with_timeout(reader, timeout)
    if ack_message.get("type") != "hello_ack":
        writer.close()
        raise WireError("expected hello_ack")
    session.node_id = str(ack_message.get("node_id", ""))
    session.advertisement = ack_message.get("advertisement") or {}
    return session, ack_message, observed
