# SPDX-License-Identifier: AGPL-3.0-only
"""Outer relay framing and the signed registration challenge.

Everything in this module is deliberately small and stdlib-only apart from
the Ed25519 verification in :func:`verify_register_proof`.  The task plane's
own TLS session starts *after* the relay has stopped speaking this protocol;
the relay never touches those bytes (see ``server.py``).
"""

from __future__ import annotations

import asyncio
import base64
import json
import struct
from typing import Any, Callable

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 64 * 1024
REGISTER_DOMAIN = b"swarmbly-relay-register-v1\n"


def b64url(data: bytes) -> str:
    """base64url without padding, the encoding used for node ids."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def canonical_bytes(obj: Any) -> bytes:
    """Canonical JSON for signatures (sorted keys, compact, UTF-8).

    This is the same rule as ``messages.canonical_bytes`` in the App, so a
    value signed by the App verifies here without a translation step.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


class RelayError(Exception):
    """A protocol error with a stable code for the error frame."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class FrameError(RelayError):
    def __init__(self, message: str) -> None:
        super().__init__("bad_frame", message)


def encode_frame(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict):
        raise FrameError("a relay frame must be a JSON object")
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_FRAME_BYTES:
        raise FrameError(f"frame too large: {len(body)} bytes")
    return struct.pack(">I", len(body)) + body


async def read_frame(reader: asyncio.StreamReader, *,
                     max_bytes: int = MAX_FRAME_BYTES,
                     timeout: float | None = None) -> dict[str, Any]:
    """Read one length-prefixed JSON object.

    ``read_frame`` never reads past the frame, so any bytes the peer sent
    after the last control frame stay available for the raw splice.
    """

    async def _read(n: int) -> bytes:
        if timeout is None:
            return await reader.readexactly(n)
        return await asyncio.wait_for(reader.readexactly(n), timeout)

    header = await _read(4)
    (length,) = struct.unpack(">I", header)
    if length == 0:
        raise FrameError("empty frame")
    if length > max_bytes:
        raise FrameError(f"frame too large: {length} bytes")
    body = await _read(length)
    try:
        message = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrameError("frame is not valid JSON") from exc
    if not isinstance(message, dict):
        raise FrameError("frame is not a JSON object")
    return message


async def write_frame(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
    writer.write(encode_frame(message))
    await writer.drain()


def _register_payload(circle_id: str, node_id: str, nonce: bytes) -> dict[str, str]:
    return {
        "purpose": "swarmbly-relay-register-v1",
        "circle_id": circle_id,
        "node_id": node_id,
        "nonce": b64url(nonce),
    }


def sign_register_proof(sign: Callable[[bytes], bytes], circle_id: str,
                        node_id: str, nonce: bytes) -> str:
    """Sign the server's fresh challenge with the node's Ed25519 key."""
    message = REGISTER_DOMAIN + canonical_bytes(
        _register_payload(circle_id, node_id, nonce))
    return b64url(sign(message))


def verify_register_proof(circle_id: str, node_id: str, nonce: bytes,
                          signature: str) -> bool:
    """Verify a registration proof against the public key in ``node_id``."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ed25519

    try:
        public = ed25519.Ed25519PublicKey.from_public_bytes(b64url_decode(node_id))
        message = REGISTER_DOMAIN + canonical_bytes(
            _register_payload(circle_id, node_id, nonce))
        public.verify(b64url_decode(signature), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def error_frame(code: str, message: str = "") -> dict[str, str]:
    frame = {"type": "error", "code": code}
    if message:
        frame["message"] = message
    return frame


def challenge_frame(nonce: bytes) -> dict[str, Any]:
    return {"type": "challenge", "v": PROTOCOL_VERSION, "nonce": b64url(nonce)}


def registered_frame(circle_id: str, node_id: str) -> dict[str, Any]:
    return {"type": "registered", "v": PROTOCOL_VERSION,
            "circle_id": circle_id, "node_id": node_id}
