"""Privacy classification and tier routing (specification section 15c).

This module is the reference implementation of the **second routing axis**.
:mod:`swarmbly_v0.router` decides *whether* a prompt survives fragmentation;
this module decides *which population of machines* the resulting packets are
allowed to reach. The two are orthogonal on purpose: ``lane`` classifies the
content, ``tier`` classifies the destination.

Three tiers
-----------
``GLOBAL``
    The open volunteer mesh. Any conformant worker. Full verification stack,
    full redundancy. This is the default and it is what the rest of the
    package assumes.

``TRUSTED``
    A permissioned sub-mesh. Membership is a whitelist of node public keys
    held by a registry under a declared operator, and every link carries
    mutual TLS. Same protocol, restricted population.

``LOCAL``
    The requesting device only. Nothing is serialised as a packet at all.

Two design constraints that this file exists to enforce
-------------------------------------------------------
**The classifier runs on the client.** A privacy classifier that asks the
network whether a prompt is private has already disclosed the prompt. There
is no configuration flag for this; :func:`classify` is pure, local and
network-free, and it is a deliberate property of the reference implementation
that it *cannot* be given a remote backend.

**Reducing ``k`` inside a trusted swarm is not free, and is never silent.**
``k`` has been doing two jobs throughout this project. *Adversarial*
redundancy defends against a worker that lies -- and a cryptographic
whitelist genuinely removes that threat at the identity layer. *Epistemic*
redundancy is what gives :mod:`swarmbly_v0.consensus` something to align, and
a whitelist does nothing for it whatsoever. Dropping to ``k = 1`` in a
trusted swarm buys throughput and pays for it with the confidence map.
:func:`resolve_k` therefore returns the reason alongside the number, and
:func:`routing_metadata` refuses to emit a consensus block that was never
computed.

.. warning::
   The entity patterns in :data:`REGULATED_PATTERNS` are a **recall-oriented
   placeholder**, not a validated NER model. They over-flag by construction,
   which is the correct direction for this decision, but their recall on real
   regulated data is **unmeasured** -- which is exactly why the manual flag
   exists and takes precedence. See specification section 21, question 9.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .metrics import effective_coverage

__all__ = [
    "GLOBAL",
    "TRUSTED",
    "LOCAL",
    "TIERS",
    "REGULATED_PATTERNS",
    "PrivacyDecision",
    "SwarmRegistry",
    "UnknownSwarm",
    "TierViolation",
    "classify",
    "resolve_k",
    "select_tier_nodes",
    "routing_metadata",
]

GLOBAL = "GLOBAL"
TRUSTED = "TRUSTED"
LOCAL = "LOCAL"

TIERS: tuple[str, ...] = (GLOBAL, TRUSTED, LOCAL)
"""Ordered by increasing restriction. Triage may move right, never left."""

_TIER_RANK = {GLOBAL: 0, TRUSTED: 1, LOCAL: 2}


# --------------------------------------------------------------------------
# Local triage
# --------------------------------------------------------------------------

REGULATED_PATTERNS: dict[str, tuple[str, ...]] = {
    "personal_identifier": (
        r"\b\d{3}-\d{2}-\d{4}\b",                       # US SSN shape
        r"\b\d{3}\s?\d{3}\s?\d{3}\b",                   # SIN / national-id shape
        r"\bpassport\s*(?:no\.?|number)\b",
        r"\b(?:date of birth|fecha de nacimiento)\b",
        r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",                 # email address
        r"\b(?:\+?\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b",
    ),
    "health": (
        r"\b(?:patient|paciente|diagnosis|diagn[oó]stico|prognosis)\b",
        r"\b(?:medical record|historia cl[ií]nica|ICD-?10|HIPAA)\b",
        r"\b(?:prescription|receta m[eé]dica|biopsy|biopsia)\b",
    ),
    "financial": (
        r"\b(?:\d[ -]?){13,19}\b",                      # card-number shape
        r"\b(?:IBAN|SWIFT|routing number)\b",
        r"\b(?:account|cuenta)\s+(?:no\.?|number|n[uú]mero)\b",
        r"\b(?:salary|salario|payroll|n[oó]mina)\b",
    ),
    "credential": (
        r"\b(?:api[_ -]?key|secret[_ -]?key|access[_ -]?token|private key)\b",
        r"\b(?:password|contrase[nñ]a|passphrase)\b",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ),
    "legal": (
        r"\b(?:under seal|privileged and confidential|attorney[- ]client)\b",
        r"\b(?:NDA|non-disclosure agreement|acuerdo de confidencialidad)\b",
        r"\b(?:case no\.?|expediente)\b",
    ),
    "internal_project": (
        r"\b(?:internal only|confidential|uso interno|propietario)\b",
        r"\bproject\s+[A-Z][a-z]+\b",
        r"\bpre[- ]release\b",
    ),
}
"""Recall-oriented cues per regulated class. Over-flagging is the design intent."""

_COMPILED: dict[str, tuple[re.Pattern[str], ...]] = {
    label: tuple(re.compile(p, re.IGNORECASE) for p in pats)
    for label, pats in REGULATED_PATTERNS.items()
}


@dataclass(frozen=True)
class PrivacyDecision:
    """The outcome of tier classification for one request.

    Attributes:
        tier: One of :data:`TIERS`.
        source: ``"manual"`` when a hard flag decided it, ``"auto"`` when local
            triage did, ``"default"`` when neither fired.
        entity_classes: Regulated classes detected by triage, sorted. Empty on
            a manual decision that skipped triage.
        swarm_id: Required and non-empty when ``tier`` is ``TRUSTED``.
        rationale: One human-readable line. The interface is expected to show
            this rather than assert an unexplained tier.
    """

    tier: str
    source: str
    entity_classes: tuple[str, ...] = ()
    swarm_id: str | None = None
    rationale: str = ""

    @property
    def routable(self) -> bool:
        """``False`` for ``LOCAL``: nothing may be serialised as a packet."""
        return self.tier != LOCAL

    def as_dict(self) -> dict[str, object]:
        return {
            "tier": self.tier,
            "classifier": self.source,
            "swarm_id": self.swarm_id,
            "entity_classes": list(self.entity_classes),
            "rationale": self.rationale,
        }


def detect_regulated(text: str) -> tuple[str, ...]:
    """Return the regulated entity classes matched in ``text``, sorted.

    Pure and local. No network, no model download, no state.
    """
    hits = {
        label
        for label, patterns in _COMPILED.items()
        if any(p.search(text) for p in patterns)
    }
    return tuple(sorted(hits))


def classify(
    prompt: str,
    manual: str | None = None,
    swarm_id: str | None = None,
    auto_triage: bool = True,
) -> PrivacyDecision:
    """Assign a tier to ``prompt`` before planning.

    Args:
        prompt: The complete user request. Never leaves this process.
        manual: A hard flag -- ``"trusted"``, ``"local"``, or ``"global"``
            (case-insensitive), or ``None``. Authoritative when given.
        swarm_id: The trusted swarm to use. Required when the resulting tier
            is ``TRUSTED``.
        auto_triage: Run local entity triage. Disabling it does not disable
            the manual flag, and does not lower an already-manual tier.

    Returns:
        A :class:`PrivacyDecision`.

    Raises:
        ValueError: If ``manual`` is not a recognised flag, or if the decision
            is ``TRUSTED`` without a ``swarm_id``.

    The precedence rule is the whole point and is not configurable: a manual
    flag is never overridden or downgraded by triage. A user who says a
    document is confidential is not asking for a second opinion. Triage may
    only move the tier *rightwards* along :data:`TIERS`.
    """
    if manual is not None:
        flag = manual.strip().lower()
        if flag not in {"global", "trusted", "local"}:
            raise ValueError(
                f"unknown privacy flag {manual!r}; expected global|trusted|local"
            )
        tier = {"global": GLOBAL, "trusted": TRUSTED, "local": LOCAL}[flag]
        decision = PrivacyDecision(
            tier=tier,
            source="manual",
            swarm_id=swarm_id if tier == TRUSTED else None,
            rationale=f"user declared --privacy={flag}",
        )
    else:
        classes = detect_regulated(prompt) if auto_triage else ()
        if classes:
            tier = TRUSTED
            decision = PrivacyDecision(
                tier=tier,
                source="auto",
                entity_classes=classes,
                swarm_id=swarm_id,
                rationale=(
                    "local triage matched regulated classes: "
                    + ", ".join(classes)
                    + " (raises the tier; does not certify anything)"
                ),
            )
        else:
            decision = PrivacyDecision(
                tier=GLOBAL,
                source="default",
                rationale="no regulated entity class matched local triage",
            )

    if decision.tier == TRUSTED and not decision.swarm_id:
        raise ValueError(
            "tier TRUSTED requires a swarm_id; refusing to fall back to GLOBAL "
            "(specification section 15c, error E_SWARM_UNKNOWN)"
        )
    return decision


# --------------------------------------------------------------------------
# Swarm membership
# --------------------------------------------------------------------------


class UnknownSwarm(LookupError):
    """Raised instead of silently degrading to the global mesh."""


class TierViolation(PermissionError):
    """A packet was offered to a node outside its tier's population."""


@dataclass(frozen=True)
class SwarmRegistry:
    """A permissioned sub-mesh: whitelist plus transport requirement.

    Attributes:
        swarm_id: Stable identifier referenced by packets.
        operator: The declared party that administers the whitelist. Naming it
            is the point -- a trusted swarm relocates trust to whoever holds
            this list, and an unnamed operator is an unnamed trust boundary.
        members: Node public keys permitted to serve. Self-declaration by a
            node confers nothing; only presence here does.
        require_mtls: Mutual TLS on every link. ``True`` is the only
            conformant value and the field exists so that a test can prove the
            non-conformant case is rejected.
        loss_rate: Measured intra-swarm packet-loss rate ``p``, which bounds
            how far ``k`` may be reduced.
    """

    swarm_id: str
    operator: str
    members: frozenset[str]
    require_mtls: bool = True
    loss_rate: float = 0.0

    def __post_init__(self) -> None:
        if not self.swarm_id:
            raise ValueError("swarm_id must be non-empty")
        if not self.operator:
            raise ValueError(
                "a trusted swarm must name its operator: the whitelist holder "
                "is the trust boundary, and an anonymous one is not a boundary"
            )
        if not 0.0 <= self.loss_rate < 1.0:
            raise ValueError("loss_rate must lie in [0, 1)")

    def admits(self, node_id: str, mtls: bool) -> bool:
        """Whether ``node_id`` may serve, over a channel with ``mtls``."""
        if self.require_mtls and not mtls:
            return False
        return node_id in self.members


def select_tier_nodes(
    nodes: Sequence[Mapping[str, object]],
    decision: PrivacyDecision,
    registries: Mapping[str, SwarmRegistry] | None = None,
) -> list[Mapping[str, object]]:
    """Filter a candidate pool by tier, *before* any capability filtering.

    Args:
        nodes: Candidate node advertisements. Each needs ``node_id`` and, for
            the trusted path, a truthy ``mtls`` key.
        decision: The output of :func:`classify`.
        registries: ``swarm_id -> SwarmRegistry``.

    Returns:
        The admissible subset, order preserved.

    Raises:
        UnknownSwarm: The decision names a swarm no registry resolves. The
            specification forbids falling back to the global mesh here, so
            this raises rather than returning ``[]``.
        TierViolation: ``decision.tier`` is ``LOCAL``; nothing is routable and
            a caller reaching this function has a control-flow defect.
    """
    if decision.tier == LOCAL:
        raise TierViolation(
            "a LOCAL request is never serialised as a packet; no node may be "
            "selected for it"
        )
    if decision.tier == GLOBAL:
        return list(nodes)

    registries = registries or {}
    registry = registries.get(decision.swarm_id or "")
    if registry is None:
        raise UnknownSwarm(
            f"swarm {decision.swarm_id!r} is not resolvable in any configured "
            "registry; aborting rather than falling back to GLOBAL"
        )
    return [
        node
        for node in nodes
        if registry.admits(str(node.get("node_id", "")), bool(node.get("mtls", False)))
    ]


# --------------------------------------------------------------------------
# Redundancy inside a trusted swarm
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class KDecision:
    """Resolved replica count and the reason it is what it is."""

    k: int
    requested_k: int
    consensus_available: bool
    waived_reason: str | None
    rationale: str

    def as_dict(self) -> dict[str, object]:
        return {
            "k": self.k,
            "requested_k": self.requested_k,
            "consensus_available": self.consensus_available,
            "consensus_waived_reason": self.waived_reason,
            "rationale": self.rationale,
        }


def resolve_k(
    requested_k: int,
    decision: PrivacyDecision,
    registry: SwarmRegistry | None = None,
    epsilon: float = 0.01,
) -> KDecision:
    """Decide the replica count for a tier, and say what it costs.

    A trusted swarm MAY drop to ``k = 1``: the adversarial redundancy that
    ``k > 1`` was buying is genuinely redundant once membership is an
    authenticated whitelist. What it MAY NOT do is drop to ``k = 1`` and still
    present a confidence map, because there is nothing to align. This function
    returns ``consensus_available=False`` and a machine-readable
    ``waived_reason`` in that case, and :func:`routing_metadata` propagates
    both into the response.

    The coverage floor of specification section 15c rule 6 is enforced here and
    is not waivable: with ``c_eff = c(1 - p)`` and ``c = 1`` there is no margin
    against loss at all, so a swarm whose measured ``p`` exceeds the tolerance
    ``epsilon`` gets ``k = 2`` regardless of what it asked for.

    Args:
        requested_k: What the caller asked for. Must be >= 1.
        decision: The output of :func:`classify`.
        registry: The swarm, when ``decision.tier`` is ``TRUSTED``.
        epsilon: Tolerated fraction of uncovered semantic units.

    Returns:
        A :class:`KDecision`.

    Raises:
        ValueError: ``requested_k`` below 1, or a trusted decision with no
            registry to measure loss against.
    """
    if requested_k < 1:
        raise ValueError("requested_k must be at least 1")

    if decision.tier != TRUSTED:
        return KDecision(
            k=requested_k,
            requested_k=requested_k,
            consensus_available=requested_k > 1,
            waived_reason=None if requested_k > 1 else "k=1_requested",
            rationale=f"tier {decision.tier}: replica count unchanged",
        )

    if registry is None:
        raise ValueError(
            "a TRUSTED decision needs its registry to check the loss floor"
        )

    if requested_k > 1:
        return KDecision(
            k=requested_k,
            requested_k=requested_k,
            consensus_available=True,
            waived_reason=None,
            rationale=(
                "trusted swarm retains k>1: adversarial redundancy is "
                "unnecessary here, epistemic redundancy is not"
            ),
        )

    # requested_k == 1 inside a trusted swarm.
    if effective_coverage(1.0, registry.loss_rate) < 1.0 - epsilon:
        return KDecision(
            k=2,
            requested_k=1,
            consensus_available=True,
            waived_reason=None,
            rationale=(
                f"k raised to 2: measured swarm loss p={registry.loss_rate:.4f} "
                f"exceeds tolerance epsilon={epsilon:.4f}, and c=1 leaves no "
                "margin (specification section 15c rule 6)"
            ),
        )

    return KDecision(
        k=1,
        requested_k=1,
        consensus_available=False,
        waived_reason="trusted_swarm_k1",
        rationale=(
            "k=1 permitted inside an authenticated swarm; the confidence map "
            "is forfeited with it, and the response says so"
        ),
    )


def routing_metadata(
    decision: PrivacyDecision,
    k_decision: KDecision,
    registry: SwarmRegistry | None = None,
    mtls: bool | None = None,
) -> dict[str, object]:
    """Build the ``routing`` block of the response (specification section 19).

    Omitting this block is non-conformant, and so is reporting a consensus
    block that was never computed -- which is why ``consensus_waived_reason``
    travels with the routing information rather than being inferable from a
    missing key.
    """
    if mtls is None:
        mtls = bool(registry.require_mtls) if registry is not None else False
    return {
        "tier": decision.tier,
        "swarm_id": decision.swarm_id,
        "swarm_operator": registry.operator if registry is not None else None,
        "classifier": decision.source,
        "entity_classes": list(decision.entity_classes),
        "mtls": bool(mtls),
        "k": k_decision.k,
        "consensus_available": k_decision.consensus_available,
        "consensus_waived_reason": k_decision.waived_reason,
        "rationale": [decision.rationale, k_decision.rationale],
    }
