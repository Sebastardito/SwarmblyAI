"""Canonical JSON and content digests.

Capsule identifiers and signatures are computed over a canonical
serialisation (SWIP 9.3–9.4 cite RFC 8785, the JSON Canonicalization Scheme).
This module implements the subset of RFC 8785 that LCE objects need:

* object members sorted by key (UTF-16 code-unit order, as RFC 8785 requires);
* no insignificant whitespace;
* strings escaped minimally, non-ASCII characters emitted as UTF-8;
* numbers restricted to integers and finite floats with an exact shortest
  representation; ``NaN`` and infinities are rejected.

LCE objects deliberately avoid floats on the wire (shares and confidences are
local), so the float branch only has to be correct, not elegant.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

__all__ = ["canonical_json", "canonical_bytes", "digest16", "sha256_hex", "text_digest"]


def _sort_key(key: str) -> list[int]:
    # RFC 8785 sorts member names by their UTF-16 code units.
    return list(key.encode("utf-16-be"))


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON forbids NaN and infinities")
        if value.is_integer() and abs(value) < 2**53:
            return str(int(value))
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(v) for v in value) + "]"
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise TypeError("canonical JSON object keys must be strings")
        items = sorted(value.items(), key=lambda kv: _sort_key(kv[0]))
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + _encode(v) for k, v in items) + "}"
    raise TypeError(f"type {type(value).__name__} is not JSON-serialisable")


def canonical_json(value: Any) -> str:
    """Return the canonical JSON text of ``value``."""
    return _encode(value)


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical JSON of ``value`` encoded as UTF-8."""
    return canonical_json(value).encode("utf-8")


def digest16(value: Any) -> str:
    """BLAKE2b with a 16-byte digest over the canonical JSON (SWIP 9.3)."""
    return hashlib.blake2b(canonical_bytes(value), digest_size=16).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_digest(text: str) -> str:
    """Digest of a text span, used for anchors (SPEC 6.2, 12.1)."""
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
