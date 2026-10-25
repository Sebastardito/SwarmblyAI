"""SPEC v0.2 wire messages (codec) — new in Swarmbly App.

SwarmblyAI ships no networking code; its packed prompts are plain text and its
internal schema differs from the normative wire format. This module implements
the wire messages of ``docs/SPEC_EN.md`` (v0.2) faithfully:

- identity: Ed25519, ``node_id`` = public key base64url without padding (§4)
- ``session_id``: 128-bit CSPRNG, generated per request and **never serialized
  on the wire** (§4 — the audit found swarmbly_v0 embeds it in packed prompts;
  the wire codec omits it by design)
- task ids: one-way BLAKE2b derivation (§4)
- signatures over the RFC 8785 JSON Canonicalization Scheme (§4)
- version field ``v``: MAJOR rejection, MINOR tolerance (§3)
- packet / result / advertisement / error shapes (§8, §10, §12, §20)

The Layer-1 commitment (``lsh-activation-v1``) has no normative construction
yet (SPEC §21.1): packets never request it and results carry
``commitment: null``. Verification is reported as *not available* — never
simulated.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from typing import Any

from ..identity import b64url_decode, verify_signature

WIRE_VERSION = "0.2"
MAX_MESSAGE_BYTES = 4 * 1024 * 1024          # 4 MiB hard cap
FRAME_HEADER = struct.Struct(">I")            # 4-byte big-endian length prefix
HELLO_TIMEOUT_S = 10.0
DEFAULT_DEADLINE_MS = 60_000


class WireError(ValueError):
    """Malformed or non-conformant wire message."""


class VersionMismatch(WireError):
    pass


def canonical_bytes(obj: Any) -> bytes:
    """RFC 8785 JCS-compatible canonicalization for our JSON value subset.

    Keys sorted, compact separators, UTF-8 without escaping guarantees. The
    payloads here contain only strings, integers, booleans, nulls, arrays and
    objects, for which this matches RFC 8785.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def new_session_id() -> bytes:
    """128 bits from the OS CSPRNG. Never leaves the orchestrator."""
    return os.urandom(16)


def task_id_for(session_id: bytes, level: int, index: int) -> str:
    """One-way derivation: BLAKE2b(session_id || u16(level) || u16(index))."""
    payload = session_id + struct.pack(">HH", level, index)
    digest = hashlib.blake2b(payload, digest_size=16).hexdigest()
    return digest


def attempt_id_for(task_id: str, attempt: int) -> str:
    return f"{task_id}:{attempt}"


# --------------------------------------------------------------------------
# Frames
# --------------------------------------------------------------------------

def encode_frame(message: dict[str, Any]) -> bytes:
    body = canonical_bytes(message)
    if len(body) > MAX_MESSAGE_BYTES:
        raise WireError(f"message too large: {len(body)} bytes")
    return FRAME_HEADER.pack(len(body)) + body


def decode_frame(data: bytes) -> dict[str, Any]:
    if len(data) < FRAME_HEADER.size:
        raise WireError("frame too short")
    (length,) = FRAME_HEADER.unpack(data[: FRAME_HEADER.size])
    if length > MAX_MESSAGE_BYTES:
        raise WireError(f"declared length {length} exceeds cap")
    if len(data) != FRAME_HEADER.size + length:
        raise WireError("truncated frame")
    try:
        obj = json.loads(data[FRAME_HEADER.size:].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WireError("invalid JSON frame") from exc
    if not isinstance(obj, dict):
        raise WireError("frame payload must be an object")
    check_version(obj)
    return obj


def check_version(message: dict[str, Any]) -> None:
    version = str(message.get("v", ""))
    if not version:
        raise WireError("missing protocol version field 'v'")
    if version.split(".")[0] != WIRE_VERSION.split(".")[0]:
        raise VersionMismatch(
            f"unsupported MAJOR version {version!r} (wire {WIRE_VERSION})")
    # MINOR additions are tolerated: unknown fields are ignored by callers.


# --------------------------------------------------------------------------
# Signatures
# --------------------------------------------------------------------------

def sign_message(node_signer, message: dict[str, Any]) -> bytes:
    """Sign the canonical serialization of everything before ``sig``."""
    unsigned = {k: v for k, v in message.items() if k != "sig"}
    return node_signer.sign(canonical_bytes(unsigned))


def verify_signed(node_id: str, message: dict[str, Any]) -> bool:
    sig = message.get("sig")
    if not sig:
        return False
    if isinstance(sig, str):
        raw_sig = b64url_decode(sig)
    else:
        return False
    unsigned = {k: v for k, v in message.items() if k != "sig"}
    return verify_signature(node_id, canonical_bytes(unsigned), raw_sig)


# --------------------------------------------------------------------------
# Handshake messages (app-level, over the encrypted channel)
# --------------------------------------------------------------------------

def hello(node_id: str, nonce: bytes, advertisement: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": WIRE_VERSION,
        "type": "hello",
        "node_id": node_id,
        "nonce": _b64(nonce),
        "advertisement": advertisement,
    }


def hello_ack(node_id: str, peer_nonce: bytes, own_nonce: bytes,
              advertisement: dict[str, Any], sig: bytes) -> dict[str, Any]:
    return {
        "v": WIRE_VERSION,
        "type": "hello_ack",
        "node_id": node_id,
        "peer_nonce": _b64(peer_nonce),
        "nonce": _b64(own_nonce),
        "advertisement": advertisement,
        "sig": _b64(sig),
    }


def ack(node_id: str, peer_nonce: bytes, sig: bytes) -> dict[str, Any]:
    return {
        "v": WIRE_VERSION,
        "type": "ack",
        "node_id": node_id,
        "nonce": _b64(peer_nonce),
        "sig": _b64(sig),
    }


def _b64(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def handshake_ack_unsigned_fields(message: dict[str, Any]) -> dict[str, Any]:
    """The fields the hello_ack signature covers."""
    return {k: message[k] for k in ("v", "node_id", "peer_nonce", "nonce")}


def ack_unsigned_fields(message: dict[str, Any]) -> dict[str, Any]:
    return {k: message[k] for k in ("v", "node_id", "nonce")}


# --------------------------------------------------------------------------
# Protocol messages (§7 plan, §8 packet, §10 result, §12 advertisement, §20 errors)
# --------------------------------------------------------------------------

def packet(attempt_id: str, contract: dict[str, Any],
           predecessors: list[dict[str, Any]], task: dict[str, Any],
           *, deadline_ms: int = DEFAULT_DEADLINE_MS, lane: str = "PUBLIC",
           tier: str = "GLOBAL", swarm_id: str | None = None,
           constraints: dict[str, Any] | None = None,
           commitment_request: dict[str, Any] | None = None) -> dict[str, Any]:
    """SPEC §8 packet. ``commitment_request`` is always None in v0.1:
    the commitment scheme has no normative construction (SPEC §21.1)."""
    return {
        "v": WIRE_VERSION,
        "type": "task",
        "attempt_id": attempt_id,
        "contract": contract,
        "predecessors": predecessors,
        "task": task,
        "constraints": constraints or {},
        "commitment_request": commitment_request,
        "deadline_ms": deadline_ms,
        "lane": lane,
        "tier": tier,
        "swarm_id": swarm_id,
    }


def result(attempt_id: str, text: str, profile: dict[str, Any],
           telemetry: dict[str, Any], sig: bytes,
           commitment: dict[str, Any] | None = None) -> dict[str, Any]:
    """SPEC §10 result. ``commitment`` is null: not available, not simulated."""
    return {
        "v": WIRE_VERSION,
        "type": "result",
        "attempt_id": attempt_id,
        "text": text,
        "profile": profile,
        "commitment": commitment,
        "telemetry": telemetry,
        "sig": _b64(sig),
    }


def error(code: str, detail: str, attempt_id: str | None = None) -> dict[str, Any]:
    return {
        "v": WIRE_VERSION,
        "type": "error",
        "code": code,
        "detail": detail,
        "attempt_id": attempt_id,
    }


def advertisement(node_id: str, models: list[dict[str, Any]],
                  capabilities: dict[str, Any],
                  resources: dict[str, Any],
                  policy: dict[str, Any],
                  swarm: dict[str, Any] | None = None,
                  reputation: dict[str, Any] | None = None) -> dict[str, Any]:
    """SPEC §12 node profile. Reputation is advisory; a node's self-reported
    reputation MUST NOT be trusted (§12)."""
    return {
        "v": WIRE_VERSION,
        "type": "advertisement",
        "node_id": node_id,
        "models": models,
        "capabilities": capabilities,
        "swarm": swarm,
        "resources": resources,
        "policy": policy,
        "reputation": reputation,
    }
