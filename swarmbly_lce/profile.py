"""Cognitive capability block of the node profile (SWIP 8, SPEC 11).

Coarse, optional, at most 1 KiB, and never biographical. A client treats it
as advisory; a node without the LCE ignores it under the protocol's
ignore-unknown-fields rule.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .capsules import KINDS
from .errors import CapsuleCode, CapsuleError
from .params import DEFAULT, Params

__all__ = ["CognitiveBlock", "SHARE_MODES"]

SHARE_MODES = frozenset({"none", "metadata", "pull"})
_BCP47 = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")
_PERSONAL = re.compile(r"\b(age|edad|religion|religi[oó]n|nationality|nacionalidad|employer|empleador|address|direcci[oó]n|politic|pol[ií]tic)\w*", re.I)


@dataclass
class CognitiveBlock:
    share_mode: str = "none"
    capsule_kinds: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    max_capsule_bytes: int = 16_384
    v: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"v": self.v, "share_mode": self.share_mode}
        if self.capsule_kinds:
            d["capsule_kinds"] = list(self.capsule_kinds)
        if self.domains:
            d["domains"] = list(self.domains)
        if self.languages:
            d["languages"] = list(self.languages)
        if self.max_capsule_bytes != 16_384:
            d["max_capsule_bytes"] = self.max_capsule_bytes
        return d

    def validate(self, params: Params = DEFAULT) -> None:
        if self.share_mode not in SHARE_MODES:
            raise CapsuleError(CapsuleCode.UNSUPPORTED, f"share_mode {self.share_mode!r}")
        if any(k not in KINDS for k in self.capsule_kinds):
            raise CapsuleError(CapsuleCode.UNSUPPORTED, "unknown capsule kind")
        for lst in (self.domains, self.languages):
            if len(lst) > params.profile_max_entries or any(len(x.encode("utf-8")) > params.profile_entry_max_bytes for x in lst):
                raise CapsuleError(CapsuleCode.TOO_LARGE, "profile list exceeds bounds")
        if any(_PERSONAL.search(x) for x in self.domains):
            raise CapsuleError(CapsuleCode.FORBIDDEN, "domains must describe capabilities, not personal attributes")
        if any(not _BCP47.match(x) for x in self.languages):
            raise CapsuleError(CapsuleCode.UNSUPPORTED, "languages must be BCP 47 tags")
        if not 512 <= self.max_capsule_bytes <= params.capsule_max_bytes:
            raise CapsuleError(CapsuleCode.TOO_LARGE, "max_capsule_bytes outside [512, 16384]")
        size = len(json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        if size > params.profile_block_max_bytes:
            raise CapsuleError(CapsuleCode.TOO_LARGE, f"cognitive block is {size} bytes (> 1024)")
