# SPDX-License-Identifier: AGPL-3.0-only
"""App-side client for the circle relay (3.5, WP3 / D-016, D-023).

This module speaks the **prototype's** relay protocol exactly as it is
implemented in the umbrella ``relay/`` package (``protocol.py``,
``client.py`` and ``tls.py``). It is a deliberate copy of only what the App
needs, because a release of the App must not import the umbrella tree at
runtime. The wire is unchanged:

* outer TLS 1.3 to the relay, certificate pinned by SHA-256 **before** any
  frame is sent;
* ``register`` → signed 32-byte challenge → ``register_proof``;
* ``pair`` / ``pair_incoming`` / ``pair_accept`` / ``paired``;
* after ``paired`` the connection is raw bytes and the nodes run their normal
  TLS 1.3 + channel-bound handshake through the splice;
* owner only: ``manifest_update`` → ``manifest_ack`` / ``manifest_refused``
  on a registered connection, copied from the umbrella's owner push.

No server code is copied: the App never serves a relay. The owner's network
push is the primary update path; :class:`RelayManifestPublisher` writes the
same signed document to the relay's file spool as the operator's bootstrap
copy and the fallback.

Adapted from ``relay/protocol.py``, ``relay/client.py`` and ``relay/tls.py``
in SwarmblyAI (AGPL-3.0-only, the same licence as this App).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import ssl
import struct
import tempfile
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("swarmbly.p2p.relay")

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 64 * 1024
REGISTER_DOMAIN = b"swarmbly-relay-register-v1\n"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


class RelayError(Exception):
    """A relay protocol or transport error with a stable ``code``."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class RelayRefused(RelayError):
    """The relay refused registration or pairing (stable ``code``)."""


def _frame_error(message: str) -> RelayError:
    return RelayError("bad_frame", message)


def encode_frame(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict):
        raise _frame_error("a relay frame must be a JSON object")
    body = json.dumps(message, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_FRAME_BYTES:
        raise _frame_error(f"frame too large: {len(body)} bytes")
    return struct.pack(">I", len(body)) + body


async def read_frame(reader: Any, *, max_bytes: int = MAX_FRAME_BYTES,
                     timeout: float | None = None) -> dict[str, Any]:
    """Read one length-prefixed JSON object and never read past it."""

    async def _read(n: int) -> bytes:
        if timeout is None:
            return await reader.readexactly(n)
        return await asyncio.wait_for(reader.readexactly(n), timeout)

    header = await _read(4)
    (length,) = struct.unpack(">I", header)
    if length == 0:
        raise _frame_error("empty frame")
    if length > max_bytes:
        raise _frame_error(f"frame too large: {length} bytes")
    body = await _read(length)
    try:
        message = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _frame_error("frame is not valid JSON") from exc
    if not isinstance(message, dict):
        raise _frame_error("frame is not a JSON object")
    return message


async def write_frame(writer: Any, message: dict[str, Any]) -> None:
    writer.write(encode_frame(message))
    await writer.drain()


def _register_payload(circle_id: str, node_id: str, nonce: bytes) -> dict[str, str]:
    return {"purpose": "swarmbly-relay-register-v1", "circle_id": circle_id,
            "node_id": node_id, "nonce": b64url(nonce)}


def sign_register_proof(sign: Callable[[bytes], bytes], circle_id: str,
                        node_id: str, nonce: bytes) -> str:
    message = REGISTER_DOMAIN + canonical_bytes(
        _register_payload(circle_id, node_id, nonce))
    return b64url(sign(message))


class RelayAddress:
    """A pinned relay endpoint, from a signed manifest or invitation."""

    __slots__ = ("host", "port", "tls_fingerprint")

    def __init__(self, host: str, port: int, tls_fingerprint: str) -> None:
        self.host = str(host)
        self.port = int(port)
        self.tls_fingerprint = str(tls_fingerprint).lower()

    def __repr__(self) -> str:  # never print the pin in logs by accident
        return f"RelayAddress({self.host!r}, {self.port}, pin=…)"

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, RelayAddress)
                and (self.host, self.port, self.tls_fingerprint)
                == (other.host, other.port, other.tls_fingerprint))

    def key(self) -> tuple[str, int, str]:
        return self.host, self.port, self.tls_fingerprint


def certificate_fingerprint(writer: asyncio.StreamWriter) -> str:
    """SHA-256 over the DER certificate the relay actually presented."""
    try:
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
    except Exception:
        der = None
    return hashlib.sha256(der).hexdigest() if der else ""


class RelayStream:
    """A socket-like view of the raw splice after ``paired``."""

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, role: str,
                 peer_node_id: str) -> None:
        self.reader = reader
        self.writer = writer
        self.role = role
        self.peer_node_id = peer_node_id

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
    """One outbound relay connection, registered with a signed challenge.

    The prototype multiplexes nothing: a connection can either wait for one
    ``pair_incoming`` or initiate one ``pair``, and after ``paired`` it is a
    byte pipe. The App therefore keeps one idle acceptor connection per
    (circle, relay) and opens a short-lived second connection when it needs
    to pair *outbound*. That is the prototype's actual shape, not a change to
    its protocol.
    """

    def __init__(self, address: RelayAddress, circle_id: str, node_id: str,
                 sign: Callable[[bytes], bytes], *, timeout: float = 10.0,
                 pair_timeout: float = 60.0,
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
                                    ssl=context,
                                    server_hostname=self.address.host),
            self.timeout)
        observed = certificate_fingerprint(self.writer)
        if not observed or not hmac.compare_digest(
                observed, self.address.tls_fingerprint.lower()):
            await self.close()
            raise RelayError(
                "relay_certificate_mismatch",
                "the relay certificate does not match the pinned SHA-256")
        return await self.register()

    async def register(self) -> "RelayClient":
        if self.registered:
            return self
        if self.reader is None or self.writer is None:
            raise RelayError("not_connected", "connect() first")
        await self._send({"type": "register", "v": PROTOCOL_VERSION,
                          "circle_id": self.circle_id,
                          "node_id": self.node_id})
        challenge = await self._receive(self.timeout)
        self._raise_on_error(challenge)
        if challenge.get("type") != "challenge":
            raise RelayError("protocol_error",
                             "expected a registration challenge")
        try:
            nonce = b64url_decode(str(challenge.get("nonce") or ""))
        except Exception as exc:
            raise RelayError("protocol_error",
                             "malformed registration challenge") from exc
        if len(nonce) != 32:
            raise RelayError("protocol_error",
                             "malformed registration challenge")
        proof = sign_register_proof(self._sign, self.circle_id,
                                    self.node_id, nonce)
        await self._send({"type": "register_proof", "v": PROTOCOL_VERSION,
                          "signature": proof})
        reply = await self._receive(self.timeout)
        self._raise_on_error(reply)
        if reply.get("type") != "registered":
            raise RelayError("protocol_error", "expected registered")
        if (reply.get("circle_id") != self.circle_id
                or reply.get("node_id") != self.node_id):
            raise RelayError("protocol_error",
                             "relay echoed a different identity")
        self.registered = True
        self.log.info("registered circle=%s node=%s",
                      self.circle_id[:12], self.node_id[:12])
        return self

    async def push_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """Push a complete signed manifest version to the relay (owner only).

        Copied from the umbrella ``relay/client.py``. ``manifest`` is the
        App's signed document (``sig`` inside the payload); the relay verifies
        it and answers ``manifest_ack``. A refusal raises
        :class:`RelayRefused` with the relay's stable code, and the connection
        stays registered for a corrected push.
        """
        if not self.registered or self._in_splice:
            raise RelayError("not_registered",
                             "connect() first, once per stream")
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
            raise RelayError("not_registered",
                             "connect() first, once per stream")
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
            raise RelayError("protocol_error",
                             f"unexpected frame while pairing: {kind}")

    async def accept_pair(self, *,
                          check: Callable[[str, str], bool] | None = None
                          ) -> RelayStream:
        """Wait for a pair request and accept it.

        ``check(peer_node_id, circle_id)`` is the App's own admission check.
        The relay already verified the signed manifest it holds; the App still
        refuses a peer that is not in a valid shared circle on this node. The
        prototype has no ``pair_reject`` frame, so a refusal closes the
        connection (the other side sees ``pair_timeout``/``peer_disconnected``)
        — which is exactly the refusal primitive the protocol offers.
        """
        if not self.registered or self._in_splice:
            raise RelayError("not_registered",
                             "connect() first, once per stream")
        deadline = asyncio.get_running_loop().time() + self.pair_timeout
        pair_id = ""
        peer_node_id = ""
        circle_id = self.circle_id
        while True:
            message = await self._receive(self._remaining(deadline))
            self._raise_on_error(message)
            if message.get("type") != "pair_incoming":
                continue
            pair_id = str(message.get("pair_id") or "")
            peer_node_id = str(message.get("from_node_id") or "")
            circle_id = str(message.get("circle_id") or self.circle_id)
            break
        if check is not None:
            try:
                allowed = bool(check(peer_node_id, circle_id))
            except Exception:
                allowed = False
            if not allowed:
                raise RelayRefused("pair_refused_by_app",
                                   "the peer is not a member of a shared circle")
        await self._send({"type": "pair_accept", "pair_id": pair_id})
        while True:
            message = await self._receive(self._remaining(deadline))
            self._raise_on_error(message)
            if message.get("type") == "paired":
                self._in_splice = True
                return RelayStream(self.reader, self.writer,  # type: ignore[arg-type]
                                   str(message.get("role") or "responder"),
                                   peer_node_id)
            raise RelayError("protocol_error",
                             "expected paired after pair_accept")

    async def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self.registered = False

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
            raise RelayError("relay_closed",
                             "relay closed the connection") from exc

    @staticmethod
    def _remaining(deadline: float) -> float:
        left = asyncio.get_running_loop().time() - deadline
        if left >= 0:
            raise RelayError("pair_timeout")
        return -left

    @staticmethod
    def _raise_on_error(message: dict[str, Any]) -> None:
        if message.get("type") == "error":
            raise RelayRefused(str(message.get("code") or "refused"),
                               str(message.get("message") or ""))


# ---------------------------------------------------------------------------
# The node's inner TLS 1.3 session over the splice (from relay/tls.py)
# ---------------------------------------------------------------------------

class TLSStream:
    """Run the normal node TLS 1.3 over a paired relay stream."""

    def __init__(self, stream: RelayStream, context: ssl.SSLContext, *,
                 server_side: bool,
                 server_hostname: str | None = None) -> None:
        self.stream = stream
        self._incoming = ssl.MemoryBIO()
        self._outgoing = ssl.MemoryBIO()
        self._ssl = context.wrap_bio(
            self._incoming, self._outgoing, server_side=server_side,
            server_hostname=None if server_side else server_hostname)

    def version(self) -> str | None:
        return self._ssl.version()

    def cipher(self) -> tuple[str, str, int] | None:
        return self._ssl.cipher()

    def getpeercert(self, binary_form: bool = False) -> Any:
        return self._ssl.getpeercert(binary_form=binary_form)

    def peer_fingerprint(self) -> str:
        try:
            der = self._ssl.getpeercert(binary_form=True)
        except Exception:
            der = None
        return hashlib.sha256(der).hexdigest() if der else ""

    async def _flush(self) -> None:
        data = self._outgoing.read()
        if data:
            await self.stream.sendall(data)

    async def _receive(self) -> None:
        data = await self.stream.read(64 * 1024)
        if data:
            self._incoming.write(data)
        else:
            self._incoming.write_eof()

    async def do_handshake(self) -> None:
        while True:
            try:
                self._ssl.do_handshake()
                await self._flush()
                return
            except ssl.SSLWantReadError:
                await self._flush()
                await self._receive()
            except ssl.SSLWantWriteError:
                await self._flush()

    async def sendall(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            try:
                written = self._ssl.write(view)
            except ssl.SSLWantWriteError:
                await self._flush()
                continue
            except ssl.SSLWantReadError:
                await self._flush()
                await self._receive()
                continue
            view = view[written:]
            await self._flush()

    async def recv(self, size: int = 65536) -> bytes:
        while True:
            try:
                return self._ssl.read(size)
            except ssl.SSLWantReadError:
                await self._flush()
                await self._receive()
            except ssl.SSLWantWriteError:
                await self._flush()
            except ssl.SSLZeroReturnError:
                return b""

    async def close(self) -> None:
        try:
            self._ssl.unwrap()
            await self._flush()
        except (ssl.SSLError, OSError):
            pass
        self.stream.close()


class TLSReader:
    """``asyncio.StreamReader``-shaped reader over :class:`TLSStream`."""

    def __init__(self, tls: TLSStream) -> None:
        self._tls = tls
        self._buffer = bytearray()
        self._eof = False

    async def _fill(self) -> bool:
        if self._eof:
            return False
        data = await self._tls.recv(64 * 1024)
        if not data:
            self._eof = True
            return False
        self._buffer.extend(data)
        return True

    async def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            while await self._fill():
                pass
            data = bytes(self._buffer)
            self._buffer.clear()
            return data
        while len(self._buffer) < n and await self._fill():
            pass
        data = bytes(self._buffer[:n])
        del self._buffer[:n]
        return data

    async def readexactly(self, n: int) -> bytes:
        while len(self._buffer) < n:
            if not await self._fill():
                raise asyncio.IncompleteReadError(
                    bytes(self._buffer), n)
        data = bytes(self._buffer[:n])
        del self._buffer[:n]
        return data


class TLSWriter:
    """``asyncio.StreamWriter``-shaped writer over :class:`TLSStream`."""

    transport = None

    def __init__(self, tls: TLSStream) -> None:
        self._tls = tls
        self._pending = bytearray()
        self._closed = False

    def write(self, data: bytes) -> None:
        self._pending.extend(data)

    async def drain(self) -> None:
        if self._pending:
            data = bytes(self._pending)
            self._pending.clear()
            await self._tls.sendall(data)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._tls.stream.close()
        except Exception:
            pass

    async def wait_closed(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self._closed

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        if name == "ssl_object":
            return self._tls._ssl
        return default


# ---------------------------------------------------------------------------
# Operator path: publish signed manifests to the relay's file spool
# ---------------------------------------------------------------------------

class RelayManifestPublisher:
    """Write the operator's bootstrap copy and fallback of a signed manifest.

    The network push (:meth:`RelayClient.push_manifest`) is the primary path
    after the operator has installed the first manifest once. This class keeps
    the historical file path: an atomic write of ``<circle_id>.json`` with the
    already signed App manifest, in ``circle.relay_publish_dir``. If the relay
    cannot be reached, the operator can still copy that file into the relay's
    ``circles/`` directory.
    """

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.directory = Path(directory)

    def publish(self, manifest: dict[str, Any]) -> Path:
        circle_id = str(manifest.get("circle_id") or "")
        if not circle_id:
            raise ValueError("manifest has no circle_id")
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{circle_id}.json"
        body = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        fd, tmp = tempfile.mkstemp(prefix=f".{circle_id}.", suffix=".tmp",
                                   dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            # The signed manifest is public (it is the member list the relay
            # already holds); make it readable by the relay service user.
            os.chmod(tmp, 0o644)
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return target
