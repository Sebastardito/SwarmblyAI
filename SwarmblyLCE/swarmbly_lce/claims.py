"""Claims: the minimal unit of the wiki (SPEC 6.2–6.6).

A claim carries four attributes that together form the *epistemic layer*:
an **anchor** to the exact source span it was extracted from, a **type**
that decides where it may go, a **maturity state** that gates the passage from
memory to behaviour, and a **provenance** record (epistemic distance and
transmission path).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Iterable

from .canonical import digest16
from .errors import InvariantViolation, TransitionError
from .params import DEFAULT, Params

__all__ = [
    "ClaimType",
    "Maturity",
    "Transmission",
    "Status",
    "Anchor",
    "Provenance",
    "Position",
    "Claim",
    "BEHAVIOURAL",
    "ATTRIBUTED",
    "advance",
    "regress",
    "derived_distance",
]


class ClaimType(str, Enum):
    FACT = "fact"
    USER_CLAIM = "user_claim"
    OPINION = "opinion"
    BELIEF = "belief"
    HYPOTHESIS = "hypothesis"
    EXPERIENCE = "experience"
    PREFERENCE = "preference"
    STYLE = "style"
    PROCEDURE = "procedure"


#: Only these types may ever reach TRAINABLE (invariant I1).
BEHAVIOURAL = frozenset({ClaimType.PREFERENCE, ClaimType.STYLE, ClaimType.PROCEDURE})
#: These must always be retrieved with explicit attribution (SPEC 6.4).
ATTRIBUTED = frozenset({ClaimType.USER_CLAIM, ClaimType.OPINION, ClaimType.BELIEF})


class Maturity(str, Enum):
    RAW = "RAW"
    DIGESTED = "DIGESTED"
    ANCHORED = "ANCHORED"
    CONNECTED = "CONNECTED"
    CORROBORATED = "CORROBORATED"
    CONSOLIDATED = "CONSOLIDATED"
    TRAINABLE = "TRAINABLE"

    @property
    def rank(self) -> int:
        return _ORDER[self]


_ORDER = {m: i for i, m in enumerate(Maturity)}


class Transmission(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    OBLIQUE = "oblique"


class Status(str, Enum):
    ACTIVE = "active"
    CONTESTED = "contested"
    RETRACTED = "retracted"


@dataclass(frozen=True)
class Anchor:
    """Reference to the exact source span a claim was extracted from."""

    source: str
    start: int
    end: int
    source_hash: str
    human_source: str = "self"  # "self", an origin node id, or a description
    verified: bool = False

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("anchor span must satisfy 0 <= start < end")


@dataclass
class Provenance:
    epistemic_distance: int = 1
    transmission_path: Transmission = Transmission.VERTICAL
    origin_capsule: str | None = None


@dataclass
class Position:
    """One stance of a contested claim (SPEC 14.3)."""

    stance: str
    support: list[str] = field(default_factory=list)
    families: list[str] = field(default_factory=list)


@dataclass
class Claim:
    text: str
    type: ClaimType
    anchors: list[Anchor] = field(default_factory=list)
    maturity: Maturity = Maturity.RAW
    provenance: Provenance = field(default_factory=Provenance)
    status: Status = Status.ACTIVE
    positions: list[Position] = field(default_factory=list)
    links: set[str] = field(default_factory=set)
    cycles_observed: int = 0
    clean_review_cycles: int = 0
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    claim_id: str = ""

    def __post_init__(self) -> None:
        self.type = ClaimType(self.type)
        self.maturity = Maturity(self.maturity)
        self.status = Status(self.status)
        if not self.claim_id:
            self.claim_id = digest16({"text": " ".join(self.text.split()).lower(), "type": self.type.value})

    # -- predicates -------------------------------------------------------------
    @property
    def behavioural(self) -> bool:
        return self.type in BEHAVIOURAL

    @property
    def attributed(self) -> bool:
        return self.type in ATTRIBUTED

    @property
    def anchored(self) -> bool:
        return any(a.verified for a in self.anchors)

    def independent_human_sources(self) -> int:
        return len({(a.source, a.human_source) for a in self.anchors if a.verified})

    def render_for_retrieval(self) -> str:
        """Text as it may be shown to a model; attributed types keep attribution."""
        if self.attributed:
            return f"[{self.type.value} — attributed to the user, not a fact] The user holds that: {self.text}"
        if self.type == ClaimType.HYPOTHESIS:
            return f"[hypothesis — unverified] {self.text}"
        return self.text

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        d["maturity"] = self.maturity.value
        d["status"] = self.status.value
        d["provenance"]["transmission_path"] = self.provenance.transmission_path.value
        d["links"] = sorted(self.links)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Claim":
        d = dict(d)
        d["anchors"] = [Anchor(**a) for a in d.get("anchors", [])]
        p = d.get("provenance", {}) or {}
        d["provenance"] = Provenance(
            epistemic_distance=int(p.get("epistemic_distance", 1)),
            transmission_path=Transmission(p.get("transmission_path", "vertical")),
            origin_capsule=p.get("origin_capsule"),
        )
        d["positions"] = [Position(**x) for x in d.get("positions", [])]
        d["links"] = set(d.get("links", []))
        return cls(**d)


def derived_distance(parents: Iterable[Claim], *, new_human_evidence: bool) -> int:
    """Epistemic distance of a claim derived from ``parents`` (SPEC 6.6)."""
    if new_human_evidence:
        return 1
    ds = [p.provenance.epistemic_distance for p in parents]
    if not ds:
        raise ValueError("a derived claim needs at least one parent")
    return max(ds) + 1


# ---------------------------------------------------------------------------
# State machine (SPEC 6.5)
# ---------------------------------------------------------------------------

def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise TransitionError(msg)


def advance(claim: Claim, *, policy_allows_training: bool = False, params: Params = DEFAULT) -> Maturity:
    """Advance ``claim`` by one maturity step if, and only if, its condition holds.

    Returns the new state. Raises :class:`TransitionError` when the condition
    for the next state does not hold, and :class:`InvariantViolation` when a
    non-behavioural claim would reach TRAINABLE.
    """
    m = claim.maturity
    if claim.status == Status.RETRACTED:
        raise TransitionError("retracted claims do not advance")
    if m == Maturity.RAW:
        nxt = Maturity.DIGESTED
    elif m == Maturity.DIGESTED:
        _require(claim.anchored, "DIGESTED → ANCHORED requires a verified anchor")
        nxt = Maturity.ANCHORED
    elif m == Maturity.ANCHORED:
        _require(len(claim.links) >= 1, "ANCHORED → CONNECTED requires at least one link")
        nxt = Maturity.CONNECTED
    elif m == Maturity.CONNECTED:
        if claim.type == ClaimType.FACT:
            _require(claim.independent_human_sources() >= 2, "fact: CORROBORATED requires two independent human sources")
        elif claim.behavioural:
            _require(claim.cycles_observed >= params.stability_cycles,
                     f"behavioural: CORROBORATED requires observation in >= {params.stability_cycles} cycles")
        else:
            _require(claim.independent_human_sources() >= 2, "CORROBORATED requires two independent sources")
        nxt = Maturity.CORROBORATED
    elif m == Maturity.CORROBORATED:
        _require(claim.status == Status.ACTIVE and claim.clean_review_cycles >= 1,
                 "CONSOLIDATED requires one review cycle without active contradiction")
        nxt = Maturity.CONSOLIDATED
    elif m == Maturity.CONSOLIDATED:
        if not claim.behavioural:
            raise InvariantViolation("I1", f"claim of type {claim.type.value!r} can never be TRAINABLE")
        _require(policy_allows_training, "TRAINABLE requires the learning policy to allow this type (I8)")
        _require(claim.provenance.epistemic_distance <= params.epistemic_max_share_train,
                 "TRAINABLE requires epistemic distance <= 1 (I3)")
        nxt = Maturity.TRAINABLE
    else:
        raise TransitionError("TRAINABLE is terminal")
    claim.maturity = nxt
    claim.updated = time.time()
    return nxt


def regress(claim: Claim, reason: str) -> Maturity:
    """Apply the regressions of SPEC 6.5.

    ``reason`` is ``"contradiction"`` (→ CONNECTED, marked contested) or
    ``"anchor_lost"`` (→ DIGESTED).
    """
    if reason == "contradiction":
        if claim.maturity.rank > Maturity.CONNECTED.rank:
            claim.maturity = Maturity.CONNECTED
        claim.status = Status.CONTESTED
        claim.clean_review_cycles = 0
    elif reason == "anchor_lost":
        claim.anchors = [replace_verified(a, False) for a in claim.anchors]
        if claim.maturity.rank > Maturity.DIGESTED.rank:
            claim.maturity = Maturity.DIGESTED
    else:
        raise ValueError(f"unknown regression reason {reason!r}")
    claim.updated = time.time()
    return claim.maturity


def replace_verified(a: Anchor, verified: bool) -> Anchor:
    return Anchor(a.source, a.start, a.end, a.source_hash, a.human_source, verified)
