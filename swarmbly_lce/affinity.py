"""Peer affinity with Hebbian control (SPEC 10.2).

Affinity records the locally observed utility of a peer for a domain. The
neuronal homology contributes only its failure mode: unnormalised Hebbian
reinforcement grows without bound, which in a network is an echo chamber.
So affinity decays with time and is normalised per domain (Oja; synaptic
scaling), its influence on candidate scoring is capped, it never overrides
the family diversity of E12, and with enough replicas one goes to a
low-affinity peer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from .params import DEFAULT, Params

__all__ = ["AffinityCache", "Candidate", "select_with_affinity"]


@dataclass
class AffinityCache:
    params: Params = DEFAULT
    raw: dict[tuple[str, str], float] = field(default_factory=dict)
    stamp: dict[tuple[str, str], float] = field(default_factory=dict)

    def _decayed(self, key: tuple[str, str], now: float) -> float:
        a = self.raw.get(key, 0.0)
        t0 = self.stamp.get(key, now)
        return a * math.exp(-(now - t0) / self.params.affinity_tau_days)

    def update(self, peer: str, domain: str, utility: float, now: float) -> float:
        if not 0.0 <= utility <= 1.0:
            raise ValueError("utility must be in [0, 1]")
        key = (peer, domain)
        a = self._decayed(key, now) + self.params.affinity_eta * utility
        self.raw[key], self.stamp[key] = a, now
        return a

    def normalised(self, domain: str, now: float) -> dict[str, float]:
        vals = {p: self._decayed((p, d), now) for (p, d) in self.raw if d == domain}
        total = sum(vals.values())
        return {p: (v / total if total > 0 else 0.0) for p, v in vals.items()}

    def adjust(self, score: float, peer: str, domain: str, now: float, beta: float | None = None) -> float:
        b = self.params.affinity_beta_max if beta is None else beta
        if b > self.params.affinity_beta_max:
            raise ValueError(f"beta {b} exceeds AFFINITY_BETA_MAX {self.params.affinity_beta_max}")
        return score * (1.0 + b * self.normalised(domain, now).get(peer, 0.0))


@dataclass(frozen=True)
class Candidate:
    peer: str
    family: str
    score: float


def select_with_affinity(cands: Sequence[Candidate], k: int, domain: str, aff: AffinityCache, now: float) -> list[Candidate]:
    """Pick ``k`` replicas: distinct families first (E12), affinity as a capped
    tie-breaker, and one exploration slot for a low-affinity peer when k >= 3."""
    norm = aff.normalised(domain, now)
    ranked = sorted(cands, key=lambda c: (-aff.adjust(c.score, c.peer, domain, now), c.peer))
    chosen: list[Candidate] = []
    families: set[str] = set()
    explore = k >= aff.params.exploration_min_k
    slots = k - (1 if explore else 0)
    for c in ranked:  # family diversity is a hard pass
        if len(chosen) >= slots:
            break
        if c.family not in families:
            chosen.append(c)
            families.add(c.family)
    for c in ranked:  # fill remaining slots if families ran out
        if len(chosen) >= slots:
            break
        if c not in chosen:
            chosen.append(c)
    if explore:
        rest = [c for c in cands if c not in chosen]
        if rest:
            rest.sort(key=lambda c: (norm.get(c.peer, 0.0), c.family in families, -c.score, c.peer))
            chosen.append(rest[0])
    return chosen[:k]
