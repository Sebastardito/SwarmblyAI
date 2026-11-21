# SPDX-License-Identifier: AGPL-3.0-only
"""Client helper the App calls to reach its circle relay.

Typical use (inside the App's asyncio transport)::

    client = RelayClient(address, circle_id, node_id, identity.sign)
    await client.connect()                 # TLS to the relay, registered
    ack = await client.push_manifest(signed_manifest)  # owner only
    stream = await client.pair(peer_node_id)
    # stream is a socket-like byte stream; wrap it in the node TLS 1.3 layer

The relay leg is TLS 1.3 with a pinned certificate (SHA-256 of the DER
certificate, taken from the manifest or the invitation).  The pin is checked
before the registration frame is sent.  The returned :class:`RelayStream`
exposes ``read``/``write``/``drain`` plus the underlying ``reader``/``writer``
for an ``ssl.MemoryBIO`` adapter or ``loop.start_tls``.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .protocol import (PROTOCOL_VERSION, RelayError, b64url_decode, read_frame,
                       sign_register_proof, write_frame)

log = logging.getLogger("swarmbly.relay.client")


class RelayRefused(RelayError):
    """The relay refused registration or pairing (stable ``code``)."""


@dataclass(frozen=True)
class RelayAddress:
    host: str
    port: int
    tls_fingerprint: str  # SHA-256 over the DER certificate, lowercase hex


def certificate_fingerprint(writer: asyncio.StreamWriter) -> str:
    """Fingerprint of the certificate the relay actually presented."""
    try:
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
    except Exception:
        der = None
    return hashlib.sha256(der).hexdigest() if der else ""


def fingerprint_from_pem(path: str | Path) -> str:
    """SHA-256 pin for a PEM certificate (what the manifest records)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    cert = x509.load_pem_x509_certificate(Path(path).read_bytes())
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


@dataclass
class RelayStream:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    role: str
    peer_node_id: str

    async def read(self, n: int = -1) -> bytes:
        return await self.reader.read(n)

    async def readexactly(self, n: int) -> bytes:
        return await self.reader.readexactly(n)

    def write(self, data: bytes) -> None:
        self.writer.write(data)

    async def drain(self) -> None:
        await self.writer.drain()

    async def sendall(self, data: bytes) -> None:
        self.write(data)
        await self.drain()

    def close(self) -> None:
        self.writer.close()

    async def wait_closed(self) -> None:
        await self.writer.wait_closed()

    def is_closing(self) -> bool:
        return self.writer.is_closing()


class RelayClient:
    def __init__(self, address: RelayAddress, circle_id: str, node_id: str,
                 sign: Callable[[bytes], bytes], *,
                 timeout: float = 10.0, pair_timeout: float = 60.0,
                 logger: logging.Logger | None = None) -> None:
        self.address = address
        self.circle_id = circle_id
        self.node_id = node_id
        self._sign = sign
        self.timeout = timeout
        self.pair_timeout = pair_timeout
        self.log = logger or log
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.registered = False
        self._in_splice = False

    async def connect(self) -> "RelayClient":
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.address.host, self.address.port,
                                    ssl=context, server_hostname=self.address.host),
            self.timeout)
        observed = certificate_fingerprint(self.writer)
        if not observed or not hmac.compare_digest(
                observed, self.address.tls_fingerprint.lower()):
            await self.close()
            raise RelayError("relay_certificate_mismatch",
                             "the relay certificate does not match the pinned SHA-256")
        return await self.register()

    async def register(self) -> "RelayClient":
        """Prove the node key with the relay's signed challenge."""
        if self.registered:
            return self
        if self.reader is None or self.writer is None:
            raise RelayError("not_connected", "connect() first")
        await self._send({"type": "register", "v": PROTOCOL_VERSION,
                          "circle_id": self.circle_id, "node_id": self.node_id})
        challenge = await self._receive(self.timeout)
        self._raise_on_error(challenge)
        if challenge.get("type") != "challenge":
            raise RelayError("protocol_error", "expected a registration challenge")
        nonce = b64url_decode(str(challenge.get("nonce") or ""))
        if len(nonce) != 32:
            raise RelayError("protocol_error", "malformed registration challenge")
        proof = sign_register_proof(self._sign, self.circle_id, self.node_id, nonce)
        await self._send({"type": "register_proof", "v": PROTOCOL_VERSION,
                          "signature": proof})
        reply = await self._receive(self.timeout)
        self._raise_on_error(reply)
        if reply.get("type") != "registered":
            raise RelayError("protocol_error", "expected registered")
        if (reply.get("circle_id") != self.circle_id
                or reply.get("node_id") != self.node_id):
            raise RelayError("protocol_error", "relay echoed a different identity")
        self.registered = True
        self.log.info("registered circle=%s node=%s",
                      self._short(self.circle_id), self._short(self.node_id))
        return self

    async def push_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """Push a complete signed manifest version to the relay (owner only).

        ``manifest`` is the App's signed document, either the
        ``{"manifest": {...}, "sig": "..."}`` envelope or the payload with a
        ``sig`` field.  Returns the relay's ``manifest_ack`` frame; a refusal
        raises :class:`RelayRefused` with the relay's stable code.
        """
        if not self.registered or self._in_splice:
            raise RelayError("not_registered", "connect() first, once per stream")
        await self._send({"type": "manifest_update", "v": PROTOCOL_VERSION,
                          "manifest": manifest})
        reply = await self._receive(self.timeout)
        if reply.get("type") == "manifest_refused":
            raise RelayRefused(str(reply.get("code") or "refused"),
                               str(reply.get("message") or ""))
        self._raise_on_error(reply)
        if reply.get("type") != "manifest_ack":
            raise RelayError("protocol_error", "expected manifest_ack")
        return reply

    async def pair(self, peer_node_id: str) -> RelayStream:
        if not self.registered or self._in_splice:
            raise RelayError("not_registered", "connect() first, once per stream")
        await self._send({"type": "pair", "circle_id": self.circle_id,
                          "peer_node_id": peer_node_id})
        deadline = asyncio.get_running_loop().time() + self.pair_timeout
        while True:
            message = await self._receive(self._remaining(deadline))
            self._raise_on_error(message)
            kind = message.get("type")
            if kind == "pair_wait":
                continue
            if kind == "paired":
                self._in_splice = True
                return RelayStream(self.reader, self.writer,  # type: ignore[arg-type]
                                   str(message.get("role") or "initiator"),
                                   peer_node_id)
            raise RelayError("protocol_error", f"unexpected frame while pairing: {kind}")

    async def accept_pair(self) -> RelayStream:
        """Wait for a member's pair request, accept it, and return the stream."""
        if not self.registered or self._in_splice:
            raise RelayError("not_registered", "connect() first, once per stream")
        deadline = asyncio.get_running_loop().time() + self.pair_timeout
        pair_id = ""
        peer_node_id = ""
        while True:
            message = await self._receive(self._remaining(deadline))
            self._raise_on_error(message)
            kind = message.get("type")
            if kind != "pair_incoming":
                continue
            pair_id = str(message.get("pair_id") or "")
            peer_node_id = str(message.get("from_node_id") or "")
            break
        await self._send({"type": "pair_accept", "pair_id": pair_id})
        while True:
            message = await self._receive(self._remaining(deadline))
            self._raise_on_error(message)
            if message.get("type") == "paired":
                self._in_splice = True
                return RelayStream(self.reader, self.writer,  # type: ignore[arg-type]
                                   str(message.get("role") or "responder"),
                                   peer_node_id)
            raise RelayError("protocol_error", "expected paired after pair_accept")

    async def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self.registered = False

    # -- internals ---------------------------------------------------------
    async def _send(self, message: dict[str, Any]) -> None:
        if self.writer is None:
            raise RelayError("not_connected")
        await write_frame(self.writer, message)

    async def _receive(self, timeout: float) -> dict[str, Any]:
        if self.reader is None:
            raise RelayError("not_connected")
        try:
            return await read_frame(self.reader, timeout=timeout)
        except asyncio.IncompleteReadError as exc:
            raise RelayError("relay_closed", "relay closed the connection") from exc

    @staticmethod
    def _remaining(deadline: float) -> float:
        left = deadline - asyncio.get_running_loop().time()
        if left <= 0:
            raise RelayError("pair_timeout")
        return left

    @staticmethod
    def _raise_on_error(message: dict[str, Any]) -> None:
        if message.get("type") == "error":
            raise RelayRefused(str(message.get("code") or "refused"),
                               str(message.get("message") or ""))

    @staticmethod
    def _short(value: str) -> str:
        return value[:12]
