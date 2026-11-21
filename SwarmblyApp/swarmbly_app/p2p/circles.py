"""Trusted circles: signed membership manifests and invitations (D-015).

A circle is a membership manifest signed with the owner's Ed25519 key over
canonical JSON. The invitation is a short signed token that can travel as a
text code or a QR; accepting it sends a signed join request to the owner over
the existing TLS session. The owner approves, signs a new manifest version and
the newcomer receives it. Members fetch newer versions with the MINOR-safe
``circle_manifest_get`` / ``circle_manifest`` control messages (D-021).

Admission is enforced twice: when a peer finishes the handshake
(``NodeManager._register``) and again when a task reaches the worker. In
``circle`` mode a peer is admitted only when both nodes are listed by a valid,
unexpired manifest. The 3.4 LAN behaviour remains available as the explicit
``own_devices`` mode; new installs default to ``circle``.

The task plane stays wire 0.2. Control message types are new ``type`` values
on the same TLS session, so an older node ignores them (SPEC §3).

Limits, deliberately: no mutual TLS, no circle CA, no relay (WP3). Credit
receipts (D-020) live in ``credits.py`` and reuse this control plane; a stolen
node key can impersonate a member until the owner signs a new version without
it (R-010).
"""

from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Iterable

from .. import egress, qr
from ..identity import IdentityManager, b64url, b64url_decode
from .messages import WIRE_VERSION, canonical_bytes, error, verify_signed

# Error codes of the circle layer. They are stable and shown by the API/UI.
E_CIRCLE_REQUIRED = "E_CIRCLE_REQUIRED"
E_CIRCLE_MANIFEST_STALE = "E_CIRCLE_MANIFEST_STALE"
E_CIRCLE_NOT_MEMBER = "E_CIRCLE_NOT_MEMBER"
E_CIRCLE_UNKNOWN = "E_CIRCLE_UNKNOWN"
E_CIRCLE_OWNER_ONLY = "E_CIRCLE_OWNER_ONLY"
E_CIRCLE_OWNER_UNREACHABLE = "E_CIRCLE_OWNER_UNREACHABLE"
E_CIRCLE_SIGNATURE = "E_CIRCLE_SIGNATURE"
E_CIRCLE_SCHEMA = "E_CIRCLE_SCHEMA"
E_CIRCLE_EXPIRED = "E_CIRCLE_EXPIRED"
E_CIRCLE_VERSION_ROLLBACK = "E_CIRCLE_VERSION_ROLLBACK"
E_CIRCLE_NO_REQUEST = "E_CIRCLE_NO_REQUEST"
E_INVITATION_INVALID = "E_INVITATION_INVALID"
E_INVITATION_EXPIRED = "E_INVITATION_EXPIRED"
E_INVITATION_USED = "E_INVITATION_USED"
# 3.5, WP3 / D-016: the circle relay. A relay address is usable only with the
# SHA-256 pin of the certificate the relay presents; an address without a pin
# is refused rather than trusted on first use.
E_CIRCLE_RELAY = "E_CIRCLE_RELAY"
E_CIRCLE_RELAY_PIN = "E_CIRCLE_RELAY_PIN"

CONTROL_TYPES = frozenset({
    "circle_manifest_get", "circle_manifest", "circle_manifest_ack",
    "circle_join_request", "circle_join_ack", "circle_leave",
    # 3.5, D-020/D-021: reciprocity credits. They are MINOR-safe additions to
    # the same control plane; older nodes ignore an unknown type (SPEC §3).
    "credit_receipt", "credit_spend", "credit_spent",
})

INVITATION_PREFIX = "SWC1."
MAX_TOKEN_TEXT = 8192
MAX_DECOMPRESSED = 16384
MAX_MEMBERS = 256
MAX_JOINS = 64
MAX_ENDPOINTS = 4
MAX_NAME = 64
_KEEP_RELAY = object()


class CircleError(RuntimeError):
    """A circle operation refused with a stable code."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# Validation and signing
# ---------------------------------------------------------------------------

_CIRCLE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_ENDPOINT_RE = re.compile(r"^\[?[A-Za-z0-9._:%-]+\]?:\d{1,5}$")
_RELAY_PIN_RE = re.compile(r"^[0-9a-f]{64}$")
_RELAY_HOST_RE = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?|"
                            r"[0-9A-Fa-f:.]{2,45})$")


def _normalise_name(value: Any, field: str = "name") -> str:
    text = str(value or "").strip()
    if not text or len(text) > MAX_NAME:
        raise CircleError(E_CIRCLE_SCHEMA,
                          f"{field} must be between 1 and {MAX_NAME} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise CircleError(E_CIRCLE_SCHEMA, f"{field} contains control characters")
    return text


def _valid_circle_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_CIRCLE_ID_RE.fullmatch(value))


def _valid_node_id(value: Any) -> bool:
    if not isinstance(value, str) or not 20 <= len(value) <= 64:
        return False
    try:
        return len(b64url_decode(value)) == 32
    except Exception:
        return False


def _normalise_endpoint(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 255 or not _ENDPOINT_RE.fullmatch(text):
        raise CircleError(E_CIRCLE_SCHEMA, f"invalid endpoint {text!r}")
    if text.startswith("["):
        host, rest = text[1:].split("]", 1)
        port_text = rest[1:]
    else:
        host, _, port_text = text.rpartition(":")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise CircleError(E_CIRCLE_SCHEMA, f"invalid endpoint {text!r}") from exc
    if not host or not 1 <= port <= 65535:
        raise CircleError(E_CIRCLE_SCHEMA, f"invalid endpoint {text!r}")
    return f"[{host.lower()}]:{port}" if ":" in host else f"{host.lower()}:{port}"


def _normalise_endpoints(value: Any, *, required: bool = False) -> list[str]:
    if value is None:
        value = []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise CircleError(E_CIRCLE_SCHEMA, "endpoints must be a list")
    if len(value) > MAX_ENDPOINTS:
        raise CircleError(E_CIRCLE_SCHEMA,
                          f"at most {MAX_ENDPOINTS} endpoints are allowed")
    out: list[str] = []
    for item in value:
        endpoint = _normalise_endpoint(item)
        if endpoint not in out:
            out.append(endpoint)
    if required and not out:
        raise CircleError(E_CIRCLE_SCHEMA, "at least one endpoint is required")
    return out


def _endpoints_arg(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def normalise_relay(value: Any, *, field: str = "relay") -> dict[str, Any] | None:
    """The circle relay endpoint: ``host:port`` plus its certificate pin.

    The pin is **mandatory** with an address (D-016/D-023): a relay whose
    certificate is not pinned would let a network attacker terminate the
    outer TLS. ``None``/empty removes the relay. A malformed or unpinned relay
    is refused, never stored.
    """
    if value is None or value == "" or value == {}:
        return None
    if not isinstance(value, dict):
        raise CircleError(E_CIRCLE_RELAY, f"{field} must be an object")
    host = str(value.get("host") or value.get("address") or "").strip().lower()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    port_value = value.get("port")
    pin = str(value.get("tls_cert_sha256") or value.get("tls_sha256")
              or value.get("pin") or "").strip().lower()
    if not host or len(host) > 255 or not _RELAY_HOST_RE.fullmatch(host):
        raise CircleError(E_CIRCLE_RELAY, f"invalid {field} host {host!r}")
    try:
        port = int(port_value)
    except (TypeError, ValueError) as exc:
        raise CircleError(E_CIRCLE_RELAY,
                          f"{field} port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise CircleError(E_CIRCLE_RELAY, f"invalid {field} port {port}")
    if not pin:
        raise CircleError(E_CIRCLE_RELAY_PIN,
                          f"{field} needs the relay certificate's SHA-256 pin")
    if not _RELAY_PIN_RE.fullmatch(pin):
        raise CircleError(E_CIRCLE_RELAY_PIN,
                          f"{field} pin must be 64 lowercase hex characters "
                          "(SHA-256 of the certificate DER)")
    return {"host": host, "port": port, "tls_cert_sha256": pin}


def validate_relay(value: Any, *, field: str = "relay") -> dict[str, Any] | None:
    """Validate an optional relay block, raising ``CircleError``."""
    return normalise_relay(value, field=field)


def endpoint_host_port(endpoint: str) -> tuple[str, int]:
    text = _normalise_endpoint(endpoint)
    if text.startswith("["):
        host, rest = text[1:].split("]", 1)
        return host, int(rest[1:])
    host, _, port = text.rpartition(":")
    return host, int(port)


def _member_ids(manifest: dict[str, Any]) -> list[str]:
    return [str(m.get("node_id", "")) for m in manifest.get("members") or []]


def _sign(identity_manager: IdentityManager, payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = {k: v for k, v in payload.items() if k != "sig"}
    signature = identity_manager.sign(canonical_bytes(unsigned))
    return {**unsigned, "sig": b64url(signature)}


def validate_manifest(manifest: dict[str, Any], *, verify: bool = True,
                      now: int | None = None) -> dict[str, Any]:
    """Structural, signature and expiry validation. Raises ``CircleError``."""
    if not isinstance(manifest, dict):
        raise CircleError(E_CIRCLE_SCHEMA, "manifest must be an object")
    if manifest.get("type") != "circle_manifest":
        raise CircleError(E_CIRCLE_SCHEMA, "not a circle manifest")
    circle_id = manifest.get("circle_id")
    if not _valid_circle_id(circle_id):
        raise CircleError(E_CIRCLE_SCHEMA, "invalid circle_id")
    _normalise_name(manifest.get("name"), "circle name")
    owner = manifest.get("owner")
    if not _valid_node_id(owner):
        raise CircleError(E_CIRCLE_SCHEMA, "invalid owner node_id")
    members = manifest.get("members")
    if not isinstance(members, list) or not 1 <= len(members) <= MAX_MEMBERS:
        raise CircleError(E_CIRCLE_SCHEMA,
                          f"members must be a list of 1..{MAX_MEMBERS}")
    seen: set[str] = set()
    for member in members:
        if not isinstance(member, dict):
            raise CircleError(E_CIRCLE_SCHEMA, "each member must be an object")
        node_id = member.get("node_id")
        if not _valid_node_id(node_id):
            raise CircleError(E_CIRCLE_SCHEMA, "invalid member node_id")
        if node_id in seen:
            raise CircleError(E_CIRCLE_SCHEMA, "duplicate member node_id")
        seen.add(node_id)
        _normalise_name(member.get("name"), "member name")
        _normalise_endpoints(member.get("endpoints"))
    validate_relay(manifest.get("relay"))
    if owner not in seen:
        raise CircleError(E_CIRCLE_SCHEMA, "the owner must be a member")
    version = manifest.get("version")
    if isinstance(version, bool) or not isinstance(version, int) \
            or not 1 <= version <= 1_000_000_000:
        raise CircleError(E_CIRCLE_SCHEMA, "version must be a positive integer")
    issued = manifest.get("issued_at")
    expires = manifest.get("expires_at")
    if isinstance(issued, bool) or not isinstance(issued, int) \
            or isinstance(expires, bool) or not isinstance(expires, int):
        raise CircleError(E_CIRCLE_SCHEMA, "issued_at/expires_at must be integers")
    if expires <= issued:
        raise CircleError(E_CIRCLE_SCHEMA, "expires_at must be after issued_at")
    if verify:
        if not verify_signed(owner, manifest):
            raise CircleError(E_CIRCLE_SIGNATURE,
                              "manifest signature is not the owner's")
    if now is not None and expires <= now:
        raise CircleError(E_CIRCLE_EXPIRED, "circle manifest has expired")
    return manifest


def validate_invitation(invitation: dict[str, Any], *, verify: bool = True,
                        now: int | None = None) -> dict[str, Any]:
    if not isinstance(invitation, dict):
        raise CircleError(E_INVITATION_INVALID, "invitation must be an object")
    if invitation.get("type") != "circle_invitation":
        raise CircleError(E_INVITATION_INVALID, "not a circle invitation")
    if not _valid_circle_id(invitation.get("circle_id")):
        raise CircleError(E_INVITATION_INVALID, "invalid circle_id")
    owner = invitation.get("owner")
    if not _valid_node_id(owner):
        raise CircleError(E_INVITATION_INVALID, "invalid owner node_id")
    nonce = invitation.get("nonce")
    if not isinstance(nonce, str) or not _valid_circle_id(nonce):
        raise CircleError(E_INVITATION_INVALID, "invalid nonce")
    expires = invitation.get("expires_at")
    if isinstance(expires, bool) or not isinstance(expires, int):
        raise CircleError(E_INVITATION_INVALID, "invalid expiry")
    _normalise_endpoints(invitation.get("endpoints"))
    try:
        validate_relay(invitation.get("relay"))
    except CircleError as exc:
        raise CircleError(E_INVITATION_INVALID, exc.detail) from exc
    if verify and not verify_signed(owner, invitation):
        raise CircleError(E_INVITATION_INVALID, "invitation signature is invalid")
    if now is not None and expires <= now:
        raise CircleError(E_INVITATION_EXPIRED, "invitation has expired")
    return invitation


def build_manifest(*, identity_manager: IdentityManager, circle_id: str,
                   name: str, owner: str, members: list[dict[str, Any]],
                   version: int, issued_at: int, expires_at: int,
                   relay: dict[str, Any] | None = None) -> dict[str, Any]:
    unsigned = {
        "v": WIRE_VERSION,
        "type": "circle_manifest",
        "circle_id": circle_id,
        "name": name,
        "owner": owner,
        "members": members,
        "version": int(version),
        "issued_at": int(issued_at),
        "expires_at": int(expires_at),
    }
    # MINOR-safe optional field: older nodes ignore it, current nodes validate
    # it together with the rest of the signed document.
    clean_relay = normalise_relay(relay)
    if clean_relay is not None:
        unsigned["relay"] = clean_relay
    manifest = _sign(identity_manager, unsigned)
    return validate_manifest(manifest, now=None)


def encode_invitation(invitation: dict[str, Any]) -> str:
    validate_invitation(invitation)
    body = canonical_bytes(invitation)
    if len(body) > MAX_TOKEN_TEXT:
        raise CircleError(E_INVITATION_INVALID, "invitation is too large")
    return INVITATION_PREFIX + b64url(zlib.compress(body, 9))


def decode_invitation(text: str, *, now: int | None = None) -> dict[str, Any]:
    raw_text = str(text or "").strip()
    if len(raw_text) > MAX_TOKEN_TEXT or not raw_text.startswith(INVITATION_PREFIX):
        raise CircleError(E_INVITATION_INVALID, "not a Swarmbly circle invitation")
    try:
        packed = b64url_decode(raw_text[len(INVITATION_PREFIX):])
    except Exception as exc:
        raise CircleError(E_INVITATION_INVALID,
                          "invitation text is not base64url") from exc
    try:
        decomp = zlib.decompressobj()
        body = decomp.decompress(packed, MAX_DECOMPRESSED + 1)
        if len(body) > MAX_DECOMPRESSED or decomp.unconsumed_tail:
            raise CircleError(E_INVITATION_INVALID, "invitation is too large")
        body += decomp.flush()
        if not decomp.eof or decomp.unused_data:
            raise CircleError(E_INVITATION_INVALID, "invitation is truncated")
    except CircleError:
        raise
    except zlib.error as exc:
        raise CircleError(E_INVITATION_INVALID,
                          "invitation is not compressed data") from exc
    try:
        invitation = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CircleError(E_INVITATION_INVALID,
                          "invitation is not valid JSON") from exc
    return validate_invitation(invitation, now=now)


def invitation_svg(text: str) -> str:
    try:
        return qr.encode_svg(text)
    except qr.QrError as exc:
        raise CircleError(E_INVITATION_INVALID,
                          f"invitation does not fit a QR code: {exc}") from exc


# ---------------------------------------------------------------------------
# Storage: only JSON files under <data>/circles, written atomically
# ---------------------------------------------------------------------------

class CircleStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _dir(self, name: str) -> Path:
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)       # membership metadata is local-only
        except OSError:
            pass
        return path

    @staticmethod
    def _atomic_write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)

    @staticmethod
    def _read(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def load_manifests(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for path in sorted(self._dir("manifests").glob("*.json")):
            data = self._read(path, None)
            if isinstance(data, dict):
                out[path.stem] = data
        return out

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        self._atomic_write(self._dir("manifests") / f"{manifest['circle_id']}.json",
                           manifest)

    def delete_manifest(self, circle_id: str) -> None:
        path = self._dir("manifests") / f"{circle_id}.json"
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def load_invitations(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for path in sorted(self._dir("invitations").glob("*.json")):
            data = self._read(path, None)
            if isinstance(data, dict) and data.get("nonce"):
                out[str(data["nonce"])] = data
        return out

    def save_invitation(self, record: dict[str, Any]) -> None:
        self._atomic_write(self._dir("invitations") / f"{record['nonce']}.json",
                           record)

    def load_joins(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for path in sorted(self._dir("joins").glob("*.json")):
            data = self._read(path, None)
            if isinstance(data, list):
                out[path.stem] = [item for item in data if isinstance(item, dict)]
        return out

    def save_joins(self, circle_id: str,
                   records: list[dict[str, Any]]) -> None:
        self._atomic_write(self._dir("joins") / f"{circle_id}.json", records)

    def load_outgoing(self) -> dict[str, dict[str, Any]]:
        data = self._read(self._dir("outgoing") / "requests.json", {})
        return data if isinstance(data, dict) else {}

    def save_outgoing(self, records: dict[str, dict[str, Any]]) -> None:
        self._atomic_write(self._dir("outgoing") / "requests.json", records)

    def load_settings(self) -> dict[str, Any]:
        data = self._read(self._dir("settings") / "circle.json", {})
        return data if isinstance(data, dict) else {}

    def save_settings(self, settings: dict[str, Any]) -> None:
        self._atomic_write(self._dir("settings") / "circle.json", settings)


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------

class CircleService:
    def __init__(self, identity_manager: IdentityManager, config: Any,
                 dirs: Any, bus: Any):
        self.identity_manager = identity_manager
        self.config = config
        self.bus = bus
        self.store = CircleStore(Path(dirs.root) / "circles")
        self.node = None
        self._lock = threading.RLock()
        self._node_id: str | None = None
        self.manifests: dict[str, dict[str, Any]] = {}
        self.invitations: dict[str, dict[str, Any]] = {}
        self.joins: dict[str, list[dict[str, Any]]] = {}
        self.outgoing: dict[str, dict[str, Any]] = {}
        # 3.5, D-017: per-circle switches stored with the circle on this node,
        # never inside the signed manifest (the owner's signature must not
        # change when a member turns passages on). They default to off, so an
        # existing privacy.third_party_passages=true never enables them.
        self._settings: dict[str, bool] = {}
        # 3.5, D-020: set by AppState; None keeps circles usable alone.
        self.credits: Any = None
        self._load()

    # -- identity and configuration -----------------------------------------
    @property
    def node_id(self) -> str:
        if self._node_id is None:
            self._node_id = self.identity_manager.load_or_create().node_id
        return self._node_id

    def attach(self, nodes: Any) -> None:
        self.node = nodes
        if self.credits is not None:
            self.credits.node = nodes

    def mode(self) -> str:
        mode = str(self.config.get("circle.admission_mode") or "circle")
        return mode if mode in ("circle", "own_devices") else "circle"

    # -- D-017: destination class and passages to a circle -------------------
    def circle_passages(self, circle_id: str) -> bool:
        """Whether this node may attach document passages for this circle."""
        with self._lock:
            return bool(self._settings.get(circle_id, False))

    def set_circle_passages(self, circle_id: str, enabled: bool) -> dict[str, Any]:
        manifest = self._manifest(circle_id)
        if not self._is_member(manifest, self.node_id):
            raise CircleError(E_CIRCLE_NOT_MEMBER,
                              "only a member of the circle can change its setting")
        validate_manifest(manifest, now=int(time.time()))
        with self._lock:
            self._settings[circle_id] = bool(enabled)
            self.store.save_settings({"passages": dict(self._settings)})
        self.bus.publish("circle.passages", circle_id=circle_id,
                         enabled=bool(enabled))
        return {"circle_id": circle_id, "circle_passages": bool(enabled)}

    def classify_peer(self, peer_node_id: str) -> dict[str, Any]:
        """Classify one outbound task send for the egress gate (D-017).

        In the explicit *my own devices* mode the 3.4 LAN rule is the
        authorisation: ``OWN_NETWORK``. In circle-only mode the peer must be
        listed by a valid shared manifest; it is then ``CIRCLE`` with the
        circle and the member named. Anything else raises: a peer outside
        every circle is refused, never labelled.
        """
        short = peer_node_id[:12]
        if self.mode() == "own_devices":
            return {"clase": egress.OWN_NETWORK, "circle_id": "",
                    "circle_name": "", "member_name": "", "member_node": short}
        if not _valid_node_id(peer_node_id):
            raise CircleError(E_CIRCLE_SCHEMA, "invalid peer node_id")
        candidates = self._local_candidates(peer_node_id)
        if not candidates:
            raise CircleError(E_CIRCLE_REQUIRED,
                              "no valid, unexpired circle manifest lists both nodes")
        # A peer may share more than one circle. Prefer a circle whose
        # passages switch is on, so the receipt names the circle that
        # governed the send; otherwise the first by name.
        chosen = sorted(candidates, key=lambda m: (
            not self.circle_passages(str(m["circle_id"])),
            str(m.get("name") or "").casefold(), str(m["circle_id"])))[0]
        member = self._member(chosen, peer_node_id) or {}
        return {"clase": egress.CIRCLE,
                "circle_id": str(chosen["circle_id"]),
                "circle_name": str(chosen.get("name") or ""),
                "member_name": str(member.get("name") or ""),
                "member_node": short}

    def own_devices_passages(self) -> bool:
        return bool(self.config.get("circle.own_devices_passages"))

    def peer_passages_allowed(self, peer_node_id: str) -> tuple[bool, str]:
        """Whether passages may be attached to a send to this peer."""
        if self.mode() == "own_devices":
            if self.own_devices_passages():
                return True, ""
            return False, ("the my-own-devices passages switch is off")
        candidates = self._local_candidates(peer_node_id)
        for manifest in sorted(candidates, key=lambda m: (
                str(m.get("name") or "").casefold(), str(m["circle_id"]))):
            if self.circle_passages(str(manifest["circle_id"])):
                return True, ""
        return False, "no shared circle has circle_passages on"

    def swarm_passages_allowed(self, peer_ids: Iterable[str]) -> tuple[bool, str]:
        """Conservative check for a wave that one prompt may send to all peers.

        Passages are attached only when every remote destination is allowed to
        receive them. A wave with no remote destination stays local and is
        always fine.
        """
        ids = [str(pid) for pid in peer_ids if str(pid)]
        if not ids:
            return True, "no remote destination"
        for peer_id in ids:
            allowed, why = self.peer_passages_allowed(peer_id)
            if not allowed:
                return False, why
        return True, ""

    def set_own_devices_passages(self, enabled: bool) -> dict[str, Any]:
        if self.mode() != "own_devices":
            raise CircleError(E_CIRCLE_SCHEMA,
                              "the my-own-devices switch only applies in that mode")
        self.config.update({"circle.own_devices_passages": bool(enabled)})
        return {"own_devices_passages": bool(enabled)}

    def display_name(self) -> str:
        configured = str(self.config.get("circle.node_name") or "").strip()
        if configured:
            try:
                return _normalise_name(configured)
            except CircleError:
                pass
        try:
            host = socket.gethostname().strip() or "Swarmbly node"
        except Exception:
            host = "Swarmbly node"
        host = re.sub(r"[^\w .'()-]+", "-", host, flags=re.UNICODE).strip(" -")
        return (host or "Swarmbly node")[:MAX_NAME]

    def endpoints(self) -> list[str]:
        node = self.node
        port = getattr(node, "listen_port", None) if node is not None else None
        if not port:
            try:
                port = int(self.config.get("swarm.p2p_port") or 9765)
            except (TypeError, ValueError):
                port = 9765
        host = str(self.config.get("swarm.p2p_host") or "0.0.0.0")
        if host in ("0.0.0.0", "::", "[::]"):
            host = "127.0.0.1"
            try:
                candidate = socket.gethostbyname(socket.gethostname())
                if candidate and not candidate.startswith("127."):
                    host = candidate
            except OSError:
                pass
        try:
            return [_normalise_endpoint(f"{host}:{int(port)}")]
        except CircleError:
            return []

    # -- loading -------------------------------------------------------------
    def _load(self) -> None:
        loaded = self.store.load_manifests()
        for circle_id, manifest in loaded.items():
            try:
                validate_manifest(manifest)
                if manifest.get("circle_id") != circle_id:
                    raise CircleError(E_CIRCLE_SCHEMA, "file and circle_id differ")
                self.manifests[circle_id] = manifest
            except CircleError as exc:
                self.bus.publish("circle.invalid_record", circle=circle_id,
                                 reason=str(exc))
        self.invitations = self.store.load_invitations()
        self.joins = self.store.load_joins()
        self.outgoing = self.store.load_outgoing()
        settings = self.store.load_settings()
        passages = settings.get("passages") if isinstance(settings, dict) else {}
        if isinstance(passages, dict):
            self._settings = {str(cid): bool(value) for cid, value in passages.items()
                              if isinstance(value, bool)}
        # A setting for a circle this node no longer holds is dead weight.
        for circle_id in list(self._settings):
            if circle_id not in self.manifests:
                self._settings.pop(circle_id, None)
        for circle_id, records in list(self.joins.items()):
            if not isinstance(records, list):
                self.joins[circle_id] = []
        # A manifest that already lists us makes the pending join obsolete.
        changed = False
        for circle_id, manifest in self.manifests.items():
            if self._is_member(manifest, self.node_id) \
                    and circle_id in self.outgoing:
                self.outgoing.pop(circle_id, None)
                changed = True
        if changed:
            self.store.save_outgoing(self.outgoing)

    # -- helpers -------------------------------------------------------------
    def _valid(self, manifest: dict[str, Any], now: int | None = None) -> bool:
        try:
            validate_manifest(manifest, now=int(time.time()) if now is None else now)
            return True
        except CircleError:
            return False

    def _manifest(self, circle_id: str) -> dict[str, Any]:
        with self._lock:
            manifest = self.manifests.get(circle_id)
        if manifest is None:
            raise CircleError(E_CIRCLE_UNKNOWN, "unknown circle")
        return manifest

    def _require_owner(self, manifest: dict[str, Any]) -> None:
        if manifest.get("owner") != self.node_id:
            raise CircleError(E_CIRCLE_OWNER_ONLY,
                              "only the circle owner can do that")

    def _member(self, manifest: dict[str, Any], node_id: str
                ) -> dict[str, Any] | None:
        for member in manifest.get("members") or []:
            if member.get("node_id") == node_id:
                return member
        return None

    def _is_member(self, manifest: dict[str, Any], node_id: str) -> bool:
        return self._member(manifest, node_id) is not None

    def _new_circle_id(self) -> str:
        return b64url(os.urandom(16))

    def _ttl_seconds(self) -> int:
        try:
            days = int(self.config.get("circle.manifest_ttl_days") or 30)
        except (TypeError, ValueError):
            days = 30
        return max(1, min(days, 365)) * 86400

    # -- creation and invitation --------------------------------------------
    def create_circle(self, name: str) -> dict[str, Any]:
        name = _normalise_name(name, "circle name")
        now = int(time.time())
        circle_id = self._new_circle_id()
        manifest = build_manifest(
            identity_manager=self.identity_manager,
            circle_id=circle_id,
            name=name,
            owner=self.node_id,
            members=[{"node_id": self.node_id, "name": self.display_name(),
                      "endpoints": self.endpoints()}],
            version=1, issued_at=now, expires_at=now + self._ttl_seconds())
        self._store_manifest(manifest)
        self.bus.publish("circle.created", circle_id=circle_id, name=name)
        return manifest

    def invite(self, circle_id: str, *, endpoints: Iterable[str] | None = None,
               ttl_s: int | None = None) -> dict[str, Any]:
        manifest = self._manifest(circle_id)
        self._require_owner(manifest)
        validate_manifest(manifest, now=int(time.time()))
        if ttl_s is None:
            ttl_s = int(self.config.get("circle.invitation_ttl_s") or 604800)
        ttl_s = max(300, min(int(ttl_s), 2592000))
        now = int(time.time())
        chosen = _normalise_endpoints(
            _endpoints_arg(endpoints) if endpoints is not None
            else self.endpoints(), required=True)
        relay = normalise_relay(manifest.get("relay"))
        unsigned = {
            "v": WIRE_VERSION,
            "type": "circle_invitation",
            "circle_id": circle_id,
            "owner": self.node_id,
            "nonce": b64url(os.urandom(16)),
            "expires_at": now + ttl_s,
            "endpoints": chosen,
        }
        # MINOR-safe optional field, inside the signature so it cannot be
        # swapped on the way to the invitee.
        if relay is not None:
            unsigned["relay"] = relay
        invitation = _sign(self.identity_manager, unsigned)
        validate_invitation(invitation)
        code = encode_invitation(invitation)
        with self._lock:
            self.invitations[invitation["nonce"]] = {
                "nonce": invitation["nonce"],
                "circle_id": circle_id,
                "owner": self.node_id,
                "expires_at": invitation["expires_at"],
                "endpoints": chosen,
                "relay": relay,
                "created_at": now,
                "used_by": None,
            }
            self.store.save_invitation(self.invitations[invitation["nonce"]])
        self.bus.publish("circle.invited", circle_id=circle_id,
                         expires_at=invitation["expires_at"])
        return {"code": code, "qr_svg": invitation_svg(code),
                "circle_id": circle_id, "circle_name": manifest["name"],
                "expires_at": invitation["expires_at"], "endpoints": chosen}

    # -- joining -------------------------------------------------------------
    def pending_join_token(self, host: str, port: int) -> str:
        """The invitation for the endpoint being dialed, if any.

        The hello may carry it so the owner can open a control-only bootstrap
        session for a newcomer that is not a member yet. Matching on the
        endpoint keeps one circle's token from being shown to another peer.
        """
        host = str(host or "").lower()
        try:
            port = int(port)
        except (TypeError, ValueError):
            return ""
        with self._lock:
            records = [dict(r) for r in self.outgoing.values()]
        fallback = ""
        for record in records:
            try:
                invitation = decode_invitation(str(record.get("token") or ""),
                                               now=int(time.time()))
            except CircleError:
                continue
            fallback = str(record.get("token") or "")
            for endpoint in invitation.get("endpoints") or []:
                try:
                    endpoint_host, endpoint_port = endpoint_host_port(endpoint)
                except CircleError:
                    continue
                if endpoint_port != port:
                    continue
                if endpoint_host == host or (
                        endpoint_host in ("127.0.0.1", "localhost", "::1")
                        and host in ("127.0.0.1", "localhost", "::1")):
                    return fallback
        # One pending invitation and no matching endpoint (a host name that
        # resolved differently): still send it; the owner verifies it.
        return fallback if len(records) == 1 else ""

    def bootstrap_allowed(self, peer_node_id: str, join_token: str = "") -> bool:
        """A control-only session for a valid invitation or pending join.

        This never admits a peer for tasks: ``Peer.admitted`` stays false
        until a manifest lists both nodes.
        """
        if join_token:
            try:
                invitation = decode_invitation(join_token, now=int(time.time()))
            except CircleError:
                invitation = None
            if invitation is not None and invitation.get("owner") == self.node_id:
                with self._lock:
                    record = self.invitations.get(str(invitation["nonce"]))
                if record is not None \
                        and str(record.get("circle_id")) == invitation["circle_id"] \
                        and record.get("used_by") in (None, peer_node_id) \
                        and int(record.get("expires_at") or 0) > time.time():
                    return True
        with self._lock:
            if any(record.get("owner") == peer_node_id
                   for record in self.outgoing.values()):
                return True
            return any(
                record.get("node_id") == peer_node_id
                for records in self.joins.values() for record in records)

    def stale_bootstrap_allowed(self, peer_node_id: str,
                                advertisement: dict[str, Any] | None = None
                                ) -> bool:
        """A member whose local manifest is older may connect control-only.

        It cannot receive tasks until it fetches and acknowledges the current
        version. Without this window the manifest could never be updated on a
        reconnecting member (the handshake would refuse the session that is
        needed to carry the update).
        """
        if advertisement is None:
            return False
        claimed = self._claimed_versions(advertisement)
        now = int(time.time())
        with self._lock:
            manifests = list(self.manifests.values())
        for manifest in manifests:
            if not self._valid(manifest, now):
                continue
            ids = _member_ids(manifest)
            if self.node_id not in ids or peer_node_id not in ids:
                continue
            if claimed.get(manifest["circle_id"], 0) < int(manifest["version"]):
                return True
        return False

    def accept_invitation(self, code: str, *, name: str | None = None,
                          endpoints: Iterable[str] | None = None) -> dict[str, Any]:
        invitation = decode_invitation(code, now=int(time.time()))
        owner = invitation["owner"]
        circle_id = invitation["circle_id"]
        if owner == self.node_id:
            raise CircleError(E_INVITATION_INVALID, "this invitation is yours")
        with self._lock:
            current = self.manifests.get(circle_id)
        if current is not None and self._is_member(current, self.node_id):
            return {"status": "already_member", "circle_id": circle_id,
                    "owner": owner}
        now = int(time.time())
        chosen = _normalise_endpoints(
            _endpoints_arg(endpoints) if endpoints is not None
            else self.endpoints())
        request = _sign(self.identity_manager, {
            "v": WIRE_VERSION,
            "type": "circle_join_request",
            "circle_id": circle_id,
            "node_id": self.node_id,
            "name": _normalise_name(name) if name else self.display_name(),
            "endpoints": chosen,
            "token": code,
            "issued_at": now,
        })
        record = {"circle_id": circle_id, "owner": owner, "token": code,
                  "relay": normalise_relay(invitation.get("relay")),
                  "request": request, "status": "pending", "created_at": now}
        with self._lock:
            self.outgoing[circle_id] = record
            self.store.save_outgoing(self.outgoing)
        sent = self._send_join_sync(record)
        if sent:
            with self._lock:
                self.outgoing[circle_id]["status"] = "sent"
                self.store.save_outgoing(self.outgoing)
        self.bus.publish("circle.join_sent", circle_id=circle_id, owner=owner,
                         sent=sent)
        return {"status": "sent" if sent else "pending", "circle_id": circle_id,
                "owner": owner, "expires_at": invitation["expires_at"]}

    def _send_join_sync(self, record: dict[str, Any]) -> bool:
        node = self.node
        if node is None:
            return False
        owner = str(record.get("owner") or "")
        try:
            peer = node.peers.get(owner)
            if peer is not None and getattr(peer, "connected", False):
                return bool(node.send_control(owner, record["request"]))
        except Exception:
            return False
        endpoints: list[str] = []
        try:
            endpoints = decode_invitation(str(record.get("token") or ""))["endpoints"]
        except CircleError:
            return False
        own_port = getattr(node, "listen_port", None)
        for endpoint in endpoints:
            try:
                host, port = endpoint_host_port(endpoint)
                if host in ("127.0.0.1", "localhost", "::1") and port == own_port:
                    continue
                peer = node.connect_manual(host, port, wait=True)
                if peer:
                    return bool(node.send_control(owner, record["request"]))
            except Exception:
                continue
        return False

    async def _send_join_async(self, record: dict[str, Any]) -> bool:
        node = self.node
        if node is None:
            return False
        owner = str(record.get("owner") or "")
        try:
            if not await node.send_control_async(owner, record["request"]):
                return False
            with self._lock:
                entry = self.outgoing.get(str(record.get("circle_id") or ""))
                if entry is not None:
                    entry["status"] = "sent"
                    self.store.save_outgoing(self.outgoing)
            return True
        except Exception:
            return False

    # -- admission -----------------------------------------------------------
    def _local_candidates(self, peer_node_id: str,
                          now: int | None = None) -> list[dict[str, Any]]:
        now = int(time.time()) if now is None else now
        out = []
        with self._lock:
            manifests = list(self.manifests.values())
        for manifest in manifests:
            if not self._valid(manifest, now):
                continue
            ids = _member_ids(manifest)
            if self.node_id in ids and peer_node_id in ids:
                out.append(manifest)
        return out

    def admit(self, peer_node_id: str,
              advertisement: dict[str, Any] | None = None
              ) -> tuple[bool, str, str]:
        """Check both sides hold a current manifest. Returns (ok, code, detail)."""
        if self.mode() == "own_devices":
            return True, "", ""
        if not _valid_node_id(peer_node_id):
            return False, E_CIRCLE_SCHEMA, "invalid peer node_id"
        candidates = self._local_candidates(peer_node_id)
        if not candidates:
            return (False, E_CIRCLE_REQUIRED,
                    "no valid, unexpired circle manifest lists both nodes")
        if advertisement is not None:
            claimed = self._claimed_versions(advertisement)
            if any(claimed.get(m["circle_id"], 0) >= int(m["version"])
                   for m in candidates):
                return True, "", ""
            return (False, E_CIRCLE_MANIFEST_STALE,
                    "the peer does not hold the current circle manifest")
        return True, "", ""

    def admits_local(self, peer_node_id: str) -> tuple[bool, str, str]:
        """The worker gate: the manifest on this node lists the sender."""
        if self.mode() == "own_devices":
            return True, "", ""
        if not _valid_node_id(peer_node_id):
            return False, E_CIRCLE_SCHEMA, "invalid peer node_id"
        if not self._local_candidates(peer_node_id):
            return (False, E_CIRCLE_REQUIRED,
                    "sender is not in a valid, unexpired circle manifest")
        return True, "", ""

    def enforce_admission(self) -> None:
        """When the user switches to circles, drop admitted peers outside them.

        Bootstrap sessions (``admitted is False``) are left alone: they are
        how a pending join is delivered, and they still cannot receive tasks.
        """
        node = self.node
        if node is None or self.mode() != "circle":
            return
        for peer in list(node.peers.values()):
            if not getattr(peer, "connected", False) \
                    or not getattr(peer, "admitted", False):
                continue
            allowed, _, _ = self.admits_local(peer.node_id)
            if not allowed:
                try:
                    node.drop_peer(peer.node_id, "not a member of a circle")
                except Exception:
                    pass

    @staticmethod
    def _claimed_versions(advertisement: dict[str, Any]) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in advertisement.get("circle_versions") or []:
            if not isinstance(item, dict):
                continue
            circle_id = item.get("circle_id")
            version = item.get("version")
            if _valid_circle_id(circle_id) and isinstance(version, int) \
                    and not isinstance(version, bool):
                out[circle_id] = version
        return out

    def advertised_versions(self) -> list[dict[str, Any]]:
        out = []
        now = int(time.time())
        with self._lock:
            manifests = list(self.manifests.values())
        for manifest in manifests:
            if not self._valid(manifest, now):
                continue
            if not self._is_member(manifest, self.node_id):
                continue
            out.append({"circle_id": manifest["circle_id"],
                        "owner": manifest["owner"],
                        "version": int(manifest["version"])})
        return out

    # -- manifest updates ----------------------------------------------------
    def _store_manifest(self, manifest: dict[str, Any],
                        now: int | None = None) -> bool:
        now = int(time.time()) if now is None else now
        validate_manifest(manifest, now=now)
        circle_id = manifest["circle_id"]
        previous: dict[str, Any] | None = None
        with self._lock:
            existing = self.manifests.get(circle_id)
            previous = existing
            if existing is not None:
                if manifest["owner"] != existing["owner"]:
                    raise CircleError(E_CIRCLE_SCHEMA,
                                      "a manifest cannot change its owner")
                if int(manifest["version"]) < int(existing["version"]):
                    raise CircleError(E_CIRCLE_VERSION_ROLLBACK,
                                      "older manifest version refused")
                if int(manifest["version"]) == int(existing["version"]):
                    if canonical_bytes(manifest) == canonical_bytes(existing):
                        return False
                    raise CircleError(E_CIRCLE_VERSION_ROLLBACK,
                                      "same version with different content")
            self.manifests[circle_id] = manifest
            self.store.save_manifest(manifest)
            if self._is_member(manifest, self.node_id):
                self.outgoing.pop(circle_id, None)
                self.store.save_outgoing(self.outgoing)
                # Pending joins are the owner's inbox, not a newcomer's
                # pending request: signing a version (relay change, renewal)
                # must not discard them. A non-owner clears its own stale
                # records once the owner lists it.
                if manifest.get("owner") != self.node_id \
                        and circle_id in self.joins:
                    self.joins.pop(circle_id, None)
                    self.store.save_joins(circle_id, [])
        # Publish outside the lock: the writer performs filesystem I/O and
        # emits events that UI listeners may handle.
        self._publish_relay(manifest)
        self._queue_relay_pushes(previous, manifest)
        self.bus.publish("circle.updated", circle_id=circle_id,
                         version=int(manifest["version"]),
                         owner=manifest["owner"])
        self._mark_admitted(manifest)
        self._notify_relays()
        return True

    # -- relay (3.5, WP3 / D-016, D-023) ------------------------------------
    def _relay_publish_dir(self) -> Path:
        """Where the owner keeps the bootstrap copy and fallback.

        The network push is the primary path after the operator installs the
        first manifest. This directory still receives every signed version
        atomically, so the operator can copy the first file once and has a
        fallback if the push cannot run; see the P2P testing guide.
        """
        configured = str(self.config.get("circle.relay_publish_dir") or "").strip()
        path = Path(configured) if configured else self.store.root / "relay-publish"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _publish_relay(self, manifest: dict[str, Any]) -> None:
        """Write the signed version to the bootstrap/fallback spool.

        Only the owner signs manifests, so only the owner writes it. The
        network push is primary; this file lets the operator bootstrap a new
        relay once and remains the fallback if the push cannot run.
        """
        if manifest.get("owner") != self.node_id:
            return
        try:
            from .relay_client import RelayManifestPublisher
            path = RelayManifestPublisher(self._relay_publish_dir()).publish(
                manifest)
        except Exception as exc:
            self.bus.publish("relay.publish_failed",
                             circle_id=str(manifest.get("circle_id") or ""),
                             reason=str(exc)[:160])
            return
        self.bus.publish("relay.manifest_published",
                         circle_id=str(manifest.get("circle_id") or ""),
                         version=int(manifest.get("version") or 0),
                         path=str(path))

    def _queue_relay_pushes(self, previous: dict[str, Any] | None,
                            manifest: dict[str, Any]) -> int:
        """Queue the new signed version for the relay(s), owner only.

        The file spool above remains the operator's bootstrap copy and the
        fallback. On a relay change the same version goes to the *previous*
        relay first, so that relay stops admitting members the new version
        removed, and then to the new endpoint.
        """
        node = self.node
        if node is None or manifest.get("owner") != self.node_id:
            return 0
        targets: list[dict[str, Any]] = []
        old = normalise_relay((previous or {}).get("relay"))
        new = normalise_relay(manifest.get("relay"))
        if old is not None:
            targets.append(old)
        if new is not None and new not in targets:
            targets.append(new)
        if not targets:
            return 0
        try:
            return int(node.queue_relay_push(
                str(manifest["circle_id"]), manifest, targets))
        except Exception as exc:
            self.bus.publish("relay.push_queue_failed",
                             circle_id=str(manifest.get("circle_id") or ""),
                             reason=str(exc)[:160])
            return 0

    def _notify_relays(self) -> None:
        node = self.node
        if node is not None:
            try:
                node.refresh_relays()
            except Exception:
                pass

    def set_relay(self, circle_id: str,
                  relay: dict[str, Any] | None) -> dict[str, Any]:
        """Owner: set or remove the circle relay (address + certificate pin).

        A new manifest version is signed and published to the relay spool;
        members receive it on the control plane and start (or stop) their
        registration. Removing the relay is the same operation with ``None``.
        """
        manifest = self._manifest(circle_id)
        self._require_owner(manifest)
        validate_manifest(manifest, now=int(time.time()))
        clean = normalise_relay(relay)
        if clean == normalise_relay(manifest.get("relay")):
            return manifest
        members = [dict(m) for m in manifest["members"]]
        updated = self._next_manifest(manifest, members, relay=clean)
        self._store_manifest(updated)
        # Members learn the new endpoint/pin on the existing control plane;
        # older nodes ignore the optional field.
        self._broadcast_manifest_sync(updated)
        self.bus.publish("circle.relay_changed", circle_id=circle_id,
                         version=int(updated["version"]),
                         relay=dict(clean) if clean else None)
        return updated

    def renew(self, circle_id: str) -> dict[str, Any]:
        """Owner: sign a fresh version with the same members and relay.

        Renewal extends the expiry and, like every other owner-signed version,
        is queued for the relay push (and written to the operator spool).
        """
        manifest = self._manifest(circle_id)
        self._require_owner(manifest)
        validate_manifest(manifest, now=int(time.time()))
        members = [dict(m) for m in manifest["members"]]
        updated = self._next_manifest(manifest, members)
        self._store_manifest(updated)
        self._broadcast_manifest_sync(updated)
        self.bus.publish("circle.renewed", circle_id=circle_id,
                         version=int(updated["version"]))
        return updated

    def _mark_admitted(self, manifest: dict[str, Any]) -> None:
        """Both nodes are listed now: a bootstrap session becomes admitted."""
        node = self.node
        if node is None or not self._is_member(manifest, self.node_id):
            return
        members = set(_member_ids(manifest))
        for peer in list(node.peers.values()):
            if getattr(peer, "connected", False) and peer.node_id in members:
                try:
                    node.mark_admitted(peer.node_id)
                except Exception:
                    pass

    def _removed_members(self, old: dict[str, Any] | None,
                         new: dict[str, Any]) -> list[str]:
        if old is None:
            return []
        old_ids = set(_member_ids(old))
        new_ids = set(_member_ids(new))
        return sorted((old_ids - new_ids) - {self.node_id})

    async def _drop_removed_async(self, old: dict[str, Any] | None,
                                  new: dict[str, Any]) -> None:
        if self.node is None:
            return
        for node_id in self._removed_members(old, new):
            try:
                await self.node.drop_peer_async(node_id, "removed from circle")
            except Exception:
                pass

    def _drop_removed_sync(self, old: dict[str, Any] | None,
                           new: dict[str, Any]) -> None:
        if self.node is None:
            return
        for node_id in self._removed_members(old, new):
            try:
                self.node.drop_peer(node_id, "removed from circle")
            except Exception:
                pass

    def _manifest_message(self, manifest: dict[str, Any]) -> dict[str, Any]:
        return {"v": WIRE_VERSION, "type": "circle_manifest",
                "manifest": manifest}

    async def _broadcast_manifest_async(self, manifest: dict[str, Any],
                                        exclude: str = "") -> None:
        node = self.node
        if node is None:
            return
        members = set(_member_ids(manifest))
        for peer in list(node.peers.values()):
            if not getattr(peer, "connected", False) or peer.node_id == exclude:
                continue
            if peer.node_id in members:
                try:
                    await node.send_control_async(
                        peer.node_id, self._manifest_message(manifest))
                except Exception:
                    pass

    def _broadcast_manifest_sync(self, manifest: dict[str, Any],
                                 exclude: str = "") -> None:
        node = self.node
        if node is None:
            return
        members = set(_member_ids(manifest))
        for peer in list(node.peers.values()):
            if not getattr(peer, "connected", False) or peer.node_id == exclude:
                continue
            if peer.node_id in members:
                try:
                    node.send_control(peer.node_id,
                                      self._manifest_message(manifest))
                except Exception:
                    pass

    async def on_peer_connected(self, peer: Any) -> None:
        """After a handshake: retry pending joins and fetch newer manifests."""
        node_id = str(getattr(peer, "node_id", "") or "")
        if not node_id:
            return
        if self.credits is not None:
            try:
                await self.credits.on_peer_connected(peer)
            except Exception:
                pass
        with self._lock:
            pending = []
            for record in self.outgoing.values():
                if record.get("owner") != node_id:
                    continue
                circle_id = str(record.get("circle_id") or "")
                manifest = self.manifests.get(circle_id)
                if manifest is None or not self._is_member(manifest, self.node_id):
                    pending.append(dict(record))
        for record in pending:
            await self._send_join_async(record)
        advertisement = getattr(peer, "advertisement", {}) or {}
        claimed = self._claimed_versions(advertisement)
        with self._lock:
            manifests = list(self.manifests.values())
        for manifest in manifests:
            if not self._valid(manifest):
                continue
            if not self._is_member(manifest, self.node_id):
                continue
            if node_id not in _member_ids(manifest):
                continue
            version = int(manifest["version"])
            other = claimed.get(manifest["circle_id"])
            if other is None or other > version:
                try:
                    await self.node.send_control_async(node_id, {
                        "v": WIRE_VERSION, "type": "circle_manifest_get",
                        "circle_id": manifest["circle_id"]})
                except Exception:
                    pass
            elif other < version:
                try:
                    await self.node.send_control_async(
                        node_id, self._manifest_message(manifest))
                except Exception:
                    pass

    # -- control messages ----------------------------------------------------
    async def handle_control(self, node_id: str,
                             message: dict[str, Any]) -> dict[str, Any] | None:
        mtype = message.get("type")
        if mtype == "circle_manifest_get":
            return self._on_manifest_get(node_id, message)
        if mtype == "circle_manifest":
            return await self._on_manifest(node_id, message)
        if mtype == "circle_manifest_ack":
            self._on_manifest_ack(node_id, message)
            return None
        if mtype == "circle_join_request":
            return self._on_join_request(node_id, message)
        if mtype == "circle_join_ack":
            self._on_join_ack(node_id, message)
            return None
        if mtype == "circle_leave":
            await self._on_leave(node_id, message)
            return None
        if mtype in ("credit_receipt", "credit_spend", "credit_spent"):
            if self.credits is not None:
                return await self.credits.handle_control(node_id, message)
            return None
        return None

    def _on_manifest_get(self, node_id: str,
                         message: dict[str, Any]) -> dict[str, Any]:
        circle_id = str(message.get("circle_id") or "")
        manifest = self._manifest(circle_id)
        validate_manifest(manifest, now=int(time.time()))
        if not self._is_member(manifest, node_id):
            raise CircleError(E_CIRCLE_NOT_MEMBER,
                              "the requester is not a member of this circle")
        return self._manifest_message(manifest)

    async def _on_manifest(self, node_id: str,
                           message: dict[str, Any]) -> dict[str, Any] | None:
        manifest = message.get("manifest")
        if not isinstance(manifest, dict):
            raise CircleError(E_CIRCLE_SCHEMA, "manifest missing")
        circle_id = str(manifest.get("circle_id") or "")
        with self._lock:
            current = self.manifests.get(circle_id)
            pending = self.outgoing.get(circle_id)
        if current is None:
            # Membership never comes from someone else's say-so: a circle this
            # node does not hold yet is accepted only from the owner of an
            # invitation this node accepted (a pending join), never because a
            # peer signed a manifest that happens to list this node. Without
            # this, any connected peer could forge a circle of its own that
            # lists this node and itself, and be admitted.
            if pending is None or manifest.get("owner") != pending.get("owner"):
                return None
        try:
            changed = self._store_manifest(manifest, now=int(time.time()))
        except CircleError as exc:
            if exc.code == E_CIRCLE_VERSION_ROLLBACK and current is not None:
                # Tell a node that is behind which version is current.
                return self._manifest_message(current)
            raise
        if self._is_member(manifest, self.node_id):
            # The sender learns that this node now holds the version, which
            # closes a stale-member control-only bootstrap session.
            try:
                await self.node.send_control_async(node_id, {
                    "v": WIRE_VERSION, "type": "circle_manifest_ack",
                    "circle_id": manifest["circle_id"],
                    "version": int(manifest["version"])})
            except Exception:
                pass
        if changed:
            await self._drop_removed_async(current, manifest)
            await self._broadcast_manifest_async(manifest, exclude=node_id)
            if not self._is_member(manifest, self.node_id):
                self.bus.publish("circle.removed", circle_id=manifest["circle_id"],
                                 owner=manifest["owner"])
        return None

    def _on_manifest_ack(self, node_id: str, message: dict[str, Any]) -> None:
        circle_id = str(message.get("circle_id") or "")
        version = message.get("version")
        if not isinstance(version, int) or isinstance(version, bool):
            return
        with self._lock:
            manifest = self.manifests.get(circle_id)
        if manifest is None or not self._valid(manifest):
            return
        if not self._is_member(manifest, node_id):
            return
        if version >= int(manifest["version"]) and self.node is not None:
            self.node.mark_admitted(node_id)
            self.bus.publish("circle.manifest_ack", circle_id=circle_id,
                             node_id=node_id, version=version)

    def _on_join_request(self, node_id: str,
                         message: dict[str, Any]) -> dict[str, Any]:
        if message.get("node_id") != node_id:
            raise CircleError(E_CIRCLE_SCHEMA, "join request node_id mismatch")
        if not verify_signed(node_id, message):
            raise CircleError(E_CIRCLE_SIGNATURE, "join request signature invalid")
        token = str(message.get("token") or "")
        invitation = decode_invitation(token, now=int(time.time()))
        if invitation["owner"] != self.node_id:
            raise CircleError(E_CIRCLE_OWNER_ONLY,
                              "this invitation belongs to another owner")
        manifest = self._manifest(invitation["circle_id"])
        self._require_owner(manifest)
        validate_manifest(manifest, now=int(time.time()))
        with self._lock:
            record = self.invitations.get(invitation["nonce"])
        if record is None:
            raise CircleError(E_INVITATION_INVALID,
                              "invitation was not issued by this node")
        if str(record.get("circle_id")) != invitation["circle_id"]:
            raise CircleError(E_INVITATION_INVALID, "invitation circle mismatch")
        used_by = record.get("used_by")
        if used_by and used_by != node_id:
            raise CircleError(E_INVITATION_USED,
                              "this invitation was already used")
        name = _normalise_name(message.get("name") or node_id[:12], "member name")
        endpoints = _normalise_endpoints(message.get("endpoints"))
        with self._lock:
            records = [r for r in self.joins.get(invitation["circle_id"], [])
                       if r.get("node_id") != node_id]
            records.append({"node_id": node_id, "name": name,
                            "endpoints": endpoints,
                            "requested_at": int(time.time())})
            if len(records) > MAX_JOINS:
                records = records[-MAX_JOINS:]
            self.joins[invitation["circle_id"]] = records
            self.store.save_joins(invitation["circle_id"], records)
            record["used_by"] = node_id
            record["used_at"] = int(time.time())
            self.invitations[invitation["nonce"]] = record
            self.store.save_invitation(record)
        self.bus.publish("circle.join_requested",
                         circle_id=invitation["circle_id"], node_id=node_id,
                         name=name)
        return {"v": WIRE_VERSION, "type": "circle_join_ack",
                "circle_id": invitation["circle_id"], "status": "pending",
                "circle_name": manifest.get("name", ""),
                "detail": "waiting for the owner's approval"}

    def _on_join_ack(self, node_id: str, message: dict[str, Any]) -> None:
        circle_id = str(message.get("circle_id") or "")
        status = str(message.get("status") or "pending")
        with self._lock:
            record = self.outgoing.get(circle_id)
            if record is not None and record.get("owner") == node_id:
                if status == "rejected":
                    self.outgoing.pop(circle_id, None)
                else:
                    record["status"] = status
                self.store.save_outgoing(self.outgoing)
        self.bus.publish("circle.join_ack", circle_id=circle_id,
                         status=status)

    async def _on_leave(self, node_id: str, message: dict[str, Any]) -> None:
        if message.get("node_id") != node_id:
            raise CircleError(E_CIRCLE_SCHEMA, "leave node_id mismatch")
        if not verify_signed(node_id, message):
            raise CircleError(E_CIRCLE_SIGNATURE, "leave signature invalid")
        circle_id = str(message.get("circle_id") or "")
        with self._lock:
            manifest = self.manifests.get(circle_id)
        if manifest is None:
            return
        if node_id == manifest["owner"]:
            # The owner dissolved the circle.
            with self._lock:
                self.manifests.pop(circle_id, None)
                self.store.delete_manifest(circle_id)
                self._settings.pop(circle_id, None)
                self.store.save_settings({"passages": dict(self._settings)})
            self.bus.publish("circle.dissolved", circle_id=circle_id)
            return
        if manifest["owner"] != self.node_id:
            self.bus.publish("circle.leave_notice", circle_id=circle_id,
                             node_id=node_id)
            return
        member = self._member(manifest, node_id)
        if member is None:
            return
        updated = self._next_manifest(manifest, [
            m for m in manifest["members"] if m.get("node_id") != node_id])
        self._store_manifest(updated)
        await self._drop_removed_async(manifest, updated)
        await self._broadcast_manifest_async(updated, exclude=node_id)
        self.bus.publish("circle.member_left", circle_id=circle_id,
                         node_id=node_id)

    # -- owner actions -------------------------------------------------------
    def _next_manifest(self, manifest: dict[str, Any],
                       members: list[dict[str, Any]],
                       *, relay: Any = _KEEP_RELAY) -> dict[str, Any]:
        now = int(time.time())
        relay_value = (normalise_relay(manifest.get("relay"))
                       if relay is _KEEP_RELAY else relay)
        return build_manifest(
            identity_manager=self.identity_manager,
            circle_id=manifest["circle_id"], name=manifest["name"],
            owner=manifest["owner"], members=members,
            version=int(manifest["version"]) + 1,
            issued_at=now, expires_at=now + self._ttl_seconds(),
            relay=relay_value)

    def approve(self, circle_id: str, node_id: str,
                name: str | None = None) -> dict[str, Any]:
        manifest = self._manifest(circle_id)
        self._require_owner(manifest)
        validate_manifest(manifest, now=int(time.time()))
        with self._lock:
            records = list(self.joins.get(circle_id, []))
            record = next((r for r in records if r.get("node_id") == node_id), None)
        if record is None:
            if self._is_member(manifest, node_id):
                return manifest
            raise CircleError(E_CIRCLE_NO_REQUEST,
                              "no pending join request from that node")
        member_name = _normalise_name(name or record.get("name") or node_id[:12],
                                      "member name")
        endpoints = _normalise_endpoints(record.get("endpoints"))
        members = [m for m in manifest["members"]
                   if m.get("node_id") != node_id]
        members.append({"node_id": node_id, "name": member_name,
                        "endpoints": endpoints})
        updated = self._next_manifest(manifest, members)
        self._store_manifest(updated)
        with self._lock:
            remaining = [r for r in records if r.get("node_id") != node_id]
            self.joins[circle_id] = remaining
            self.store.save_joins(circle_id, remaining)
        node = self.node
        if node is not None:
            try:
                node.send_control(node_id, self._manifest_message(updated))
            except Exception:
                pass
        self._broadcast_manifest_sync(updated)
        self.bus.publish("circle.member_approved", circle_id=circle_id,
                         node_id=node_id, version=int(updated["version"]))
        return updated

    def reject(self, circle_id: str, node_id: str) -> dict[str, Any]:
        manifest = self._manifest(circle_id)
        self._require_owner(manifest)
        with self._lock:
            records = [r for r in self.joins.get(circle_id, [])
                       if r.get("node_id") != node_id]
            self.joins[circle_id] = records
            self.store.save_joins(circle_id, records)
        node = self.node
        if node is not None:
            try:
                node.send_control(node_id, {
                    "v": WIRE_VERSION, "type": "circle_join_ack",
                    "circle_id": circle_id, "status": "rejected",
                    "detail": "the owner rejected the join request"})
            except Exception:
                pass
            try:
                node.drop_peer(node_id, "join request rejected")
            except Exception:
                pass
        self.bus.publish("circle.join_rejected", circle_id=circle_id,
                         node_id=node_id)
        return {"rejected": node_id}

    def revoke(self, circle_id: str, node_id: str) -> dict[str, Any]:
        manifest = self._manifest(circle_id)
        self._require_owner(manifest)
        if node_id == manifest["owner"]:
            raise CircleError(E_CIRCLE_OWNER_ONLY,
                              "the owner cannot revoke itself")
        if not self._is_member(manifest, node_id):
            return manifest
        validate_manifest(manifest, now=int(time.time()))
        members = [m for m in manifest["members"]
                   if m.get("node_id") != node_id]
        updated = self._next_manifest(manifest, members)
        self._store_manifest(updated)
        with self._lock:
            remaining = [r for r in self.joins.get(circle_id, [])
                         if r.get("node_id") != node_id]
            self.joins[circle_id] = remaining
            self.store.save_joins(circle_id, remaining)
        self._broadcast_manifest_sync(updated)
        self._drop_removed_sync(manifest, updated)
        self.bus.publish("circle.member_revoked", circle_id=circle_id,
                         node_id=node_id, version=int(updated["version"]))
        return updated

    def leave(self, circle_id: str) -> dict[str, Any]:
        manifest = self._manifest(circle_id)
        if manifest["owner"] == self.node_id:
            # Dissolving: tell the members while the manifest still exists.
            # Also publish a last signed version with only the owner, so a
            # relay does not keep admitting the old members from its spool.
            try:
                owner_only = self._next_manifest(manifest, [
                    m for m in manifest["members"]
                    if m.get("node_id") == self.node_id])
                self._publish_relay(owner_only)
                self._queue_relay_pushes(manifest, owner_only)
            except Exception:
                pass
            dissolved = _sign(self.identity_manager, {
                "v": WIRE_VERSION, "type": "circle_leave",
                "circle_id": circle_id, "node_id": self.node_id,
            })
            node = self.node
            if node is not None:
                for peer in list(node.peers.values()):
                    if getattr(peer, "connected", False) and \
                            self._is_member(manifest, peer.node_id):
                        try:
                            node.send_control(peer.node_id, dissolved)
                        except Exception:
                            pass
            with self._lock:
                self.manifests.pop(circle_id, None)
                self.store.delete_manifest(circle_id)
                self.outgoing.pop(circle_id, None)
                self.store.save_outgoing(self.outgoing)
                self._settings.pop(circle_id, None)
                self.store.save_settings({"passages": dict(self._settings)})
                for nonce, record in list(self.invitations.items()):
                    if record.get("circle_id") == circle_id:
                        self.invitations.pop(nonce, None)
                self.joins.pop(circle_id, None)
            self.bus.publish("circle.deleted", circle_id=circle_id)
            return {"deleted": circle_id}
        message = _sign(self.identity_manager, {
            "v": WIRE_VERSION, "type": "circle_leave",
            "circle_id": circle_id, "node_id": self.node_id,
        })
        node = self.node
        if node is not None:
            try:
                node.send_control(manifest["owner"], message)
            except Exception:
                pass
        with self._lock:
            self.manifests.pop(circle_id, None)
            self.store.delete_manifest(circle_id)
            self.outgoing.pop(circle_id, None)
            self.store.save_outgoing(self.outgoing)
            self._settings.pop(circle_id, None)
            self.store.save_settings({"passages": dict(self._settings)})
            self.joins.pop(circle_id, None)
        self.bus.publish("circle.left", circle_id=circle_id)
        return {"left": circle_id}

    # -- API payloads --------------------------------------------------------
    def list_payload(self) -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            manifests = list(self.manifests.values())
            outgoing = [{"circle_id": str(r.get("circle_id") or ""),
                         "owner": str(r.get("owner") or ""),
                         "status": str(r.get("status") or "pending"),
                         "created_at": int(r.get("created_at") or 0)}
                        for r in self.outgoing.values()]
            joins = {cid: [{"node_id": str(r.get("node_id") or ""),
                            "name": str(r.get("name") or ""),
                            "endpoints": list(r.get("endpoints") or []),
                            "requested_at": int(r.get("requested_at") or 0)}
                           for r in records]
                     for cid, records in self.joins.items()}
        circles = []
        for manifest in manifests:
            if not self._valid(manifest, now):
                continue
            if not self._is_member(manifest, self.node_id):
                continue
            is_owner = manifest["owner"] == self.node_id
            circles.append({
                "circle_id": manifest["circle_id"],
                "name": manifest["name"],
                "owner": manifest["owner"],
                "is_owner": is_owner,
                "version": int(manifest["version"]),
                "issued_at": int(manifest["issued_at"]),
                "expires_at": int(manifest["expires_at"]),
                "members": [dict(m) for m in manifest["members"]],
                "circle_passages": self.circle_passages(manifest["circle_id"]),
                "relay": normalise_relay(manifest.get("relay")),
                "relay_status": (
                    self.node.relay_status(manifest["circle_id"])
                    if self.node is not None
                    and hasattr(self.node, "relay_status") else None),
                "pending_joins": joins.get(manifest["circle_id"], [])
                if is_owner else [],
            })
        circles.sort(key=lambda c: c["name"].lower())
        return {
            "admission_mode": self.mode(),
            "own_devices_passages": bool(
                self.config.get("circle.own_devices_passages")),
            "notice_pending": bool(self.config.get("circle.notice_pending")),
            "own_devices_notice": bool(
                self.config.get("circle.notice_pending"))
            and self.mode() == "own_devices",
            "node_id": self.node_id,
            "node_name": self.display_name(),
            "circles": circles,
            "outgoing_joins": outgoing,
        }

    def summary(self) -> dict[str, Any]:
        with self._lock:
            manifests = list(self.manifests.values())
        active = [m for m in manifests
                  if self._valid(m) and self._is_member(m, self.node_id)]
        return {"admission_mode": self.mode(),
                "circles": len(active),
                "notice_pending": bool(self.config.get("circle.notice_pending"))}
