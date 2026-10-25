"""Handshake (8 steps of the product spec §7.3), bound to the TLS channel.

Steps 1 (endpoint discovery) and 2 (encrypted channel) live in discovery.py
and transport.py. This module implements steps 3–8 on top of TLS 1.3:

  3. identity authentication (Ed25519 over the transcript)
  4. version negotiation (MAJOR checked in the codec; ``hs`` revision here)
  5. capability exchange (SPEC §12 advertisement, signed by its owner)
  6. compatibility check (structural validation with size/charset bounds)
  7. participation policy application (worker gates, see worker.py)
  8. connection state confirmation

**Channel binding.** P2P nodes have no CA, so TLS alone cannot tell who is on
the other end. The responder signs the SHA-256 fingerprint of the TLS
certificate it presented; the initiator checks that fingerprint against the
certificate it actually received before revealing anything, and its own
final acknowledgement signs that same fingerprint. A man in the middle that
terminates TLS presents a different certificate and is detected before the
initiator signs or sends any task. This is the SSH host-key model; it gives
mutually authenticated identities over a server-authenticated channel. It is
**not** the mutual TLS that SPEC §15c requires for the TRUSTED tier, which
stays refused until implemented.

An unknown node is never automatically authorized for anything: a completed
handshake records an *authenticated* peer; the worker applies its own
participation policies before accepting any task.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Any

from ..identity import IdentityManager
from .messages import WIRE_VERSION, canonical_bytes, hello, hello_ack, WireError

HANDSHAKE_REVISION = 2


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass
class HandshakeResult:
    node_id: str
    advertisement: dict[str, Any]
    version: str
    inbound: bool


class Handshake:
    def __init__(self, identity: IdentityManager, advertisement: dict[str, Any],
                 tls_fingerprint: str = ""):
        self.identity = identity
        self.advertisement = advertisement
        self.tls_fingerprint = tls_fingerprint  # of OUR certificate

    # -- initiator side --------------------------------------------------------
    def build_hello(self) -> tuple[dict[str, Any], bytes]:
        nonce = os.urandom(16)
        ident = self.identity.load_or_create()
        message = hello(ident.node_id, nonce, self.advertisement)
        message["hs"] = HANDSHAKE_REVISION
        return message, nonce

    def verify_ack(self, ack_message: dict[str, Any], my_nonce: bytes,
                   observed_fingerprint: str) -> HandshakeResult:
        """Check the responder's signed hello_ack against the TLS channel."""
        if ack_message.get("type") != "hello_ack":
            raise WireError("expected hello_ack")
        peer_id = str(ack_message.get("node_id", ""))
        if not peer_id:
            raise WireError("hello_ack missing node_id")
        if int(ack_message.get("hs", 0) or 0) < HANDSHAKE_REVISION:
            raise WireError("peer uses an unbound handshake (upgrade required)")
        # Replay protection: the ack must echo our fresh nonce.
        if ack_message.get("peer_nonce") != _b64(my_nonce):
            raise WireError("hello_ack nonce mismatch (possible replay)")
        if not observed_fingerprint or ack_message.get("tls_fp") != observed_fingerprint:
            raise WireError("TLS certificate does not match the signed "
                            "fingerprint (possible man in the middle)")
        if not verify_over_fields(peer_id, ack_message,
                                  ("v", "hs", "node_id", "peer_nonce", "nonce",
                                   "tls_fp", "advertisement")):
            raise WireError("hello_ack signature invalid")
        return HandshakeResult(
            node_id=peer_id,
            advertisement=ack_message.get("advertisement") or {},
            version=str(ack_message.get("v", "")), inbound=False)

    def build_final_ack(self, peer_nonce: bytes, bound_fingerprint: str,
                        advertisement: dict[str, Any]) -> dict[str, Any]:
        """Initiator's ack: signs the responder nonce, the verified TLS
        fingerprint and its own advertisement (authenticating the hello)."""
        ident = self.identity.load_or_create()
        unsigned = {"v": WIRE_VERSION, "hs": HANDSHAKE_REVISION,
                    "node_id": ident.node_id, "nonce": _b64(peer_nonce),
                    "tls_fp": bound_fingerprint, "advertisement": advertisement}
        sig = self.identity.sign(canonical_bytes(unsigned))
        return {"type": "ack", **unsigned, "sig": _b64(sig)}

    # -- responder side ---------------------------------------------------------
    def build_hello_ack(self, hello_message: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        peer_id = str(hello_message.get("node_id", ""))
        if not peer_id:
            raise WireError("hello missing node_id")
        if int(hello_message.get("hs", 0) or 0) < HANDSHAKE_REVISION:
            raise WireError("peer uses an unbound handshake (upgrade required)")
        nonce_field = hello_message.get("nonce", "")
        peer_nonce = _b64d(str(nonce_field)) if nonce_field else b""
        if len(peer_nonce) != 16:
            raise WireError("hello nonce malformed")
        if not self.tls_fingerprint:
            raise WireError("responder has no TLS fingerprint to bind")
        own_nonce = os.urandom(16)
        ident = self.identity.load_or_create()
        unsigned = {"v": WIRE_VERSION, "hs": HANDSHAKE_REVISION,
                    "node_id": ident.node_id, "peer_nonce": _b64(peer_nonce),
                    "nonce": _b64(own_nonce), "tls_fp": self.tls_fingerprint,
                    "advertisement": self.advertisement}
        sig = self.identity.sign(canonical_bytes(unsigned))
        message = hello_ack(ident.node_id, peer_nonce, own_nonce,
                            self.advertisement, sig)
        message["hs"] = HANDSHAKE_REVISION
        message["tls_fp"] = self.tls_fingerprint
        return message, own_nonce

    def verify_final_ack(self, ack_message: dict[str, Any],
                         expected_peer_id: str, own_nonce: bytes) -> HandshakeResult:
        if ack_message.get("type") != "ack":
            raise WireError("expected ack")
        if ack_message.get("node_id") != expected_peer_id:
            raise WireError("ack node_id mismatch")
        if ack_message.get("nonce") != _b64(own_nonce):
            raise WireError("ack nonce mismatch (possible replay)")
        if ack_message.get("tls_fp") != self.tls_fingerprint:
            raise WireError("ack bound to a different TLS channel")
        if not verify_over_fields(expected_peer_id, ack_message,
                                  ("v", "hs", "node_id", "nonce", "tls_fp",
                                   "advertisement")):
            raise WireError("ack signature invalid")
        return HandshakeResult(node_id=expected_peer_id,
                               advertisement=ack_message.get("advertisement") or {},
                               version=str(ack_message.get("v", "")),
                               inbound=True)


def verify_over_fields(node_id: str, message: dict[str, Any],
                       fields: tuple[str, ...]) -> bool:
    """Verify a signature over an explicit subset of message fields."""
    sig = message.get("sig")
    if not isinstance(sig, str):
        return False
    subset = {field: message[field] for field in fields if field in message}
    from ..identity import b64url_decode, verify_signature
    try:
        raw_sig = b64url_decode(sig)
    except Exception:
        return False
    return verify_signature(node_id, canonical_bytes(subset), raw_sig)


def sign_advertisement_update(identity: IdentityManager,
                              advertisement: dict[str, Any], seq: int) -> dict[str, Any]:
    """A signed, sequenced advertisement refresh sent on a live session."""
    ident = identity.load_or_create()
    unsigned = {"v": WIRE_VERSION, "type": "advertisement_update",
                "node_id": ident.node_id, "seq": int(seq),
                "advertisement": advertisement}
    return {**unsigned, "sig": _b64(identity.sign(canonical_bytes(unsigned)))}


def verify_advertisement_update(node_id: str, message: dict[str, Any]) -> bool:
    if message.get("node_id") != node_id:
        return False
    return verify_over_fields(node_id, message,
                              ("v", "type", "node_id", "seq", "advertisement"))


# -- step 6: structural validation ------------------------------------------------

_SAFE_TEXT = re.compile(r"^[\w .:/@+\-]{0,96}$", re.UNICODE)
_ALLOWED_KINDS = {"extract", "classify", "generate", "summarize", "transform", "judge"}
MAX_MODELS = 16


def _safe(value: Any) -> bool:
    return value is None or (isinstance(value, str) and bool(_SAFE_TEXT.match(value)))


def validate_advertisement(adv: dict[str, Any], expected_node_id: str | None = None
                           ) -> list[str]:
    """Structural validation with strict bounds. Returns a list of problems.

    Advertisements are untrusted remote input: every string shown in the UI
    is restricted to a conservative charset and length, and the UI escapes it
    again. A self-declared ``swarm_id`` confers nothing (SPEC §12).
    """
    problems: list[str] = []
    if not isinstance(adv, dict):
        return ["advertisement must be an object"]
    node_id = adv.get("node_id", "")
    if not isinstance(node_id, str) or not node_id or len(node_id) > 64:
        problems.append("missing or malformed node_id")
    elif expected_node_id and node_id != expected_node_id:
        problems.append("advertisement node_id differs from the authenticated id")
    models = adv.get("models", [])
    if not isinstance(models, list) or len(models) > MAX_MODELS:
        problems.append("models must be a list of at most 16 entries")
        models = []
    for model in models:
        if not isinstance(model, dict) or not model.get("family"):
            problems.append("each model entry needs a family")
            continue
        for key in ("family", "version", "quantization"):
            if not _safe(model.get(key)):
                problems.append(f"model {key} has disallowed characters or length")
    policy = adv.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            problems.append("policy must be an object")
        else:
            kinds = policy.get("kinds", [])
            if not isinstance(kinds, list) or any(k not in _ALLOWED_KINDS for k in kinds):
                problems.append("policy.kinds contains unknown kinds")
    return problems
