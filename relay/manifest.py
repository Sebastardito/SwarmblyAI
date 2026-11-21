# SPDX-License-Identifier: AGPL-3.0-only
"""The relay's minimal, tolerant view of a circle manifest.

The App owns the manifest format (``swarmbly_app/p2p/circles.py``).  The relay
only needs four facts: the circle id, the owner's Ed25519 key that signs the
document, the member node ids, and the relay endpoint (including the
certificate pin the members must use).  Parsing is intentionally forgiving
about field names and about members written as strings or objects, so a
manifest produced by the App can be consumed before the two codebases share a
schema module.  Signature verification is *not* forgiving: a document is
accepted only when the canonical JSON verifies with the owner's key.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .protocol import RelayError, b64url_decode, canonical_bytes

log = logging.getLogger("swarmbly.relay.manifest")


class ManifestError(RelayError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(code, message)


@dataclass(frozen=True)
class RelayEndpoint:
    host: str
    port: int
    tls_fingerprint: str  # SHA-256 over the DER certificate, lowercase hex


@dataclass(frozen=True)
class CircleManifest:
    circle_id: str
    owner_node_id: str
    members: frozenset[str]
    version: int = 0
    expires_at: dt.datetime | None = None
    relay: RelayEndpoint | None = None
    source: str = ""

    def contains(self, node_id: str) -> bool:
        return node_id in self.members

    def expired(self, now: dt.datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = now or dt.datetime.now(dt.timezone.utc)
        return current >= self.expires_at


def _parse_time(value: Any) -> dt.datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    return None


def _payload(document: dict[str, Any]) -> dict[str, Any]:
    for key in ("manifest", "circle", "body"):
        candidate = document.get(key)
        if isinstance(candidate, dict):
            return candidate
    return document


def document_circle_id(document: dict[str, Any]) -> str | None:
    """Circle id from an unverified document, using the parser's tolerant keys.

    This only routes a push to the right held manifest; authority is still
    decided by the held manifest's owner and by the signature check.
    """
    if not isinstance(document, dict):
        return None
    payload = _payload(document)
    value = payload.get("circle_id") or payload.get("id") or payload.get("circle")
    return value if isinstance(value, str) and value else None


def _signature(document: dict[str, Any], payload: dict[str, Any]) -> str:
    for container in (document, payload):
        for key in ("sig", "signature"):
            value = container.get(key)
            if isinstance(value, str) and value:
                return value
    raise ManifestError("unsigned_manifest", "manifest has no signature")


def _owner(payload: dict[str, Any]) -> str:
    value: Any = (payload.get("owner") or payload.get("owner_node_id")
                  or payload.get("owner_key"))
    if isinstance(value, dict):
        value = value.get("node_id") or value.get("public_key") or value.get("key")
    if not isinstance(value, str) or not value:
        raise ManifestError("invalid_manifest", "manifest has no owner key")
    return value


def _members(payload: dict[str, Any]) -> frozenset[str]:
    raw = (payload.get("members") or payload.get("member_node_ids")
           or payload.get("nodes") or [])
    if isinstance(raw, dict):
        raw = list(raw)
    if not isinstance(raw, list):
        raise ManifestError("invalid_manifest", "members must be a list")
    members: set[str] = set()
    for entry in raw:
        if isinstance(entry, str):
            node_id = entry
        elif isinstance(entry, dict):
            node_id = (entry.get("node_id") or entry.get("id")
                       or entry.get("public_key"))
        else:
            node_id = None
        if isinstance(node_id, str) and node_id:
            members.add(node_id)
    return frozenset(members)


def _relay(payload: dict[str, Any]) -> RelayEndpoint | None:
    value: Any = payload.get("relay") or payload.get("rendezvous")
    if not isinstance(value, dict):
        return None
    host = value.get("host") or value.get("address")
    port = value.get("port")
    pin = (value.get("tls_cert_sha256") or value.get("tls_sha256")
           or value.get("cert_fingerprint") or value.get("pin"))
    try:
        port_number = int(port)
    except (TypeError, ValueError):
        return None
    if not isinstance(host, str) or not host or not 0 < port_number < 65536:
        return None
    return RelayEndpoint(host=host, port=port_number,
                         tls_fingerprint=str(pin or "").lower())


def parse_manifest(document: dict[str, Any], *,
                   now: dt.datetime | None = None,
                   require_signature: bool = True,
                   source: str = "") -> CircleManifest:
    """Verify and read one manifest document.

    Raises :class:`ManifestError` when the signature does not verify, when the
    document has no owner/members, or when it has expired.
    """
    if not isinstance(document, dict):
        raise ManifestError("invalid_manifest", "manifest must be a JSON object")
    payload = _payload(document)
    signature = _signature(document, payload)

    signed_payload = {key: value for key, value in payload.items()
                      if key not in ("sig", "signature")}
    owner = _owner(signed_payload)

    if require_signature:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519

        try:
            public = ed25519.Ed25519PublicKey.from_public_bytes(b64url_decode(owner))
            public.verify(b64url_decode(signature), canonical_bytes(signed_payload))
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise ManifestError("bad_manifest_signature",
                                "manifest signature does not verify") from exc

    circle_id = payload.get("circle_id") or payload.get("id") or payload.get("circle")
    if not isinstance(circle_id, str) or not circle_id:
        raise ManifestError("invalid_manifest", "manifest has no circle id")

    try:
        version = int(payload.get("version") or 0)
    except (TypeError, ValueError):
        version = 0

    expiry_value = (payload.get("expires_at") or payload.get("expiry")
                    or payload.get("expires"))
    expires_at = _parse_time(expiry_value)
    if expiry_value not in (None, "") and expires_at is None:
        raise ManifestError("invalid_manifest", "expiry is not a valid time")

    manifest = CircleManifest(
        circle_id=circle_id,
        owner_node_id=owner,
        members=_members(payload),
        version=version,
        expires_at=expires_at,
        relay=_relay(payload),
        source=source,
    )
    if manifest.expired(now):
        raise ManifestError("manifest_expired",
                            f"circle {circle_id} manifest has expired")
    return manifest


class ManifestStore:
    """The manifests a relay holds, reloaded when their files change.

    A path may be a JSON file or a directory of ``*.json`` files.  A document
    that fails validation is logged and skipped; the previous version of an
    already-loaded circle stays in force until a valid replacement arrives,
    so a bad edit cannot silently open the relay.
    """

    def __init__(self, paths: list[str | Path]) -> None:
        self.paths = [Path(path) for path in paths]
        self._manifests: dict[str, CircleManifest] = {}
        self._stamps: dict[Path, tuple[int, int]] = {}

    @staticmethod
    def _files(path: Path) -> list[Path]:
        if path.is_dir():
            return sorted(path.glob("*.json"))
        return [path]

    @staticmethod
    def _stamp(path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def reload(self, *, force: bool = False) -> bool:
        """Read changed files.  Returns True when a valid manifest changed."""
        changed = False
        for path in self.paths:
            for file in self._files(path):
                stamp = self._stamp(file)
                if stamp is None:
                    continue
                if not force and self._stamps.get(file) == stamp:
                    continue
                try:
                    document = json.loads(file.read_text(encoding="utf-8"))
                    manifest = parse_manifest(document, source=str(file))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError,
                        ManifestError) as exc:
                    log.warning("manifest %s ignored: %s", file, exc)
                    self._stamps[file] = stamp
                    continue
                self._stamps[file] = stamp
                current = self._manifests.get(manifest.circle_id)
                if current is None or manifest.version >= current.version:
                    self._manifests[manifest.circle_id] = manifest
                    changed = True
        return changed

    def get(self, circle_id: str) -> CircleManifest | None:
        return self._manifests.get(circle_id)

    def for_member(self, node_id: str) -> list[CircleManifest]:
        return [m for m in self._manifests.values() if m.contains(node_id)]

    def all(self) -> list[CircleManifest]:
        return list(self._manifests.values())

    # -- owner push persistence -------------------------------------------
    @staticmethod
    def _safe_filename(circle_id: str) -> str:
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", circle_id).strip("._")
        return (name or "circle")[:80]

    def target_path(self, circle_id: str) -> Path:
        """Where the authoritative file for ``circle_id`` lives.

        A manifest loaded from a file keeps that file.  A manifest installed
        in memory only (embedded relays, tests) goes to the first directory
        passed to the store, or to the single file path when there is one.
        """
        current = self._manifests.get(circle_id)
        if current is not None and current.source:
            return Path(current.source)
        for path in self.paths:
            if path.is_dir():
                return path / f"{self._safe_filename(circle_id)}.json"
        if len(self.paths) == 1 and not self.paths[0].is_dir():
            return self.paths[0]
        raise ManifestError("not_persistable",
                            f"no writable path for circle {circle_id}")

    def _write_document(self, target: Path, document: dict[str, Any]) -> None:
        """Write one signed document with a same-directory atomic replace."""
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        try:
            mode = target.stat().st_mode & 0o777
        except OSError:
            mode = 0o640
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False,
                          sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, mode)
            os.replace(temp_name, target)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(temp_name)
            raise
        with contextlib.suppress(OSError):
            dir_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def commit(self, manifest: CircleManifest,
               document: dict[str, Any]) -> Path:
        """Persist a verified push, then make it the held manifest.

        The file is replaced first, so a write failure leaves both the file
        and the in-memory view on the previous version.  The caller runs this
        under the server's manifest lock to serialise concurrent pushes.
        """
        target = self.target_path(manifest.circle_id)
        self._write_document(target, document)
        stored = replace(manifest, source=str(target))
        self._manifests[manifest.circle_id] = stored
        stamp = self._stamp(target)
        if stamp is not None:
            self._stamps[target] = stamp
        return target

    def replace(self, manifest: CircleManifest) -> None:
        """Install a manifest directly (used by tests and embedded relays)."""
        self._manifests[manifest.circle_id] = manifest

    def without_member(self, circle_id: str, node_id: str) -> CircleManifest | None:
        """Return a revoked view; convenience for tests, not used at runtime."""
        current = self.get(circle_id)
        if current is None:
            return None
        return replace(current, members=current.members - {node_id},
                       version=current.version + 1)
