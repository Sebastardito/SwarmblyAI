"""Social cache and the prevalence rule (SPEC 10.1, invariant I5).

The social cache records patterns observed in the results of the client's
*own* requests. How many independent nodes and model families repeated a
pattern is a **prevalence label**: it may be displayed and may feed pattern
confidence, but adoption (caching, consolidating, making a pattern eligible
for training) is decided by locally observed utility or explicit user
promotion. If prevalence is used as an adoption factor at all, the adoption
probability must be at most linear in the count; a superlinear rule is
conformist transmission (Boyd & Richerson, 1985), which erases minority
variants, and is rejected here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .canonical import digest16
from .errors import InvariantViolation

__all__ = ["SocialPattern", "SocialCache", "AdoptionRule", "utility_rule", "linear_prevalence_rule", "check_at_most_linear", "identity_violation"]


@dataclass
class SocialPattern:
    statement: str
    nodes: set[str] = field(default_factory=set)
    families: set[str] = field(default_factory=set)
    utility_observations: list[float] = field(default_factory=list)
    factual_status: str = "unverified"  # unverified | anchored | contradicted
    adopted: bool = False
    adoption_reason: str | None = None  # utility_observed | user_promoted
    pattern_id: str = ""

    def __post_init__(self) -> None:
        if not self.pattern_id:
            self.pattern_id = digest16({"statement": " ".join(self.statement.split()).lower()})

    @property
    def independent_nodes(self) -> int:
        return len(self.nodes)

    @property
    def model_families(self) -> int:
        return len(self.families)

    @property
    def prevalence_label(self) -> str:
        return f"observed in {self.independent_nodes} nodes, {self.model_families} families"

    @property
    def mean_utility(self) -> float:
        return sum(self.utility_observations) / len(self.utility_observations) if self.utility_observations else 0.0


#: An adoption rule maps (pattern) -> probability of adoption in [0, 1].
AdoptionRule = Callable[[SocialPattern], float]


def utility_rule(threshold: float = 0.5, min_uses: int = 1) -> AdoptionRule:
    """Default rule: adopt iff observed utility is high enough. Ignores prevalence."""
    def rule(p: SocialPattern) -> float:
        return 1.0 if len(p.utility_observations) >= min_uses and p.mean_utility >= threshold else 0.0
    return rule


def linear_prevalence_rule(slope: float, cap_nodes: int = 50) -> AdoptionRule:
    """Prevalence-weighted rule allowed by I5: linear in the node count."""
    def rule(p: SocialPattern) -> float:
        return min(1.0, slope * min(p.independent_nodes, cap_nodes))
    return rule


def check_at_most_linear(rule_of_n: Callable[[int], float], n_max: int = 50, tol: float = 1e-9) -> None:
    """Raise if ``rule_of_n`` (adoption probability as a function of node count) is superlinear.

    Superlinear here means convex with increasing increments: some second
    difference is positive. Linear and concave rules pass.
    """
    vals = [rule_of_n(n) for n in range(0, n_max + 1)]
    for n in range(1, n_max):
        if vals[n + 1] - 2 * vals[n] + vals[n - 1] > tol:
            raise InvariantViolation("I5", f"adoption rule is superlinear in prevalence near n={n} (conformist transmission)")


_IDENTITY = re.compile(r"\b(soy|i am|i'm|nosotros los|we)\s+(ecuatorian|ecuadorian|japon|japanese|mexican|chilen|argentin|colombian|canadi|peruan|venezolan|español|spanish)\w*", re.I)


def identity_violation(text: str) -> bool:
    """First-person claim of a group identity the model only observed (SPEC 10.1.5)."""
    return bool(_IDENTITY.search(text))


@dataclass
class SocialCache:
    adoption: AdoptionRule = field(default_factory=utility_rule)
    patterns: dict[str, SocialPattern] = field(default_factory=dict)

    def observe(self, statement: str, node: str, family: str, utility: float | None = None) -> SocialPattern:
        if identity_violation(statement):
            raise InvariantViolation("I5", "social patterns may describe a culture, never assert the model's identity")
        p = SocialPattern(statement)
        p = self.patterns.setdefault(p.pattern_id, p)
        p.nodes.add(node)
        p.families.add(family)
        if utility is not None:
            p.utility_observations.append(float(utility))
        return p

    def decide(self, pattern_id: str, rng_value: float) -> bool:
        """Apply the adoption rule with an external uniform draw (testable)."""
        p = self.patterns[pattern_id]
        prob = self.adoption(p)
        if not 0.0 <= prob <= 1.0:
            raise ValueError("adoption probability must be in [0, 1]")
        if not p.adopted and rng_value < prob:
            p.adopted, p.adoption_reason = True, "utility_observed"
        return p.adopted

    def promote(self, pattern_id: str) -> SocialPattern:
        p = self.patterns[pattern_id]
        p.adopted, p.adoption_reason = True, "user_promoted"
        return p
