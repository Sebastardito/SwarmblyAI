"""Replica counts derived from a churn tolerance (SPEC 13).

For exponential node lifetimes with mean ``T_host`` and a repair window ``W``,
the probability that a given holder leaves within one window is
``q = 1 − exp(−W / T_host)``. With independent departures and repair every
window, losing all ``r`` copies within one window has probability ``q**r``,
so a tolerance ``ε`` per window needs ``r = ⌈ln(1/ε) / ln(1/q)⌉``.

Rarity weighting applies a stricter ε to preserved capsules held by few nodes
(negative frequency-dependent selection, Ayala & Campbell 1974), only for
preserved, anchored capsules with distance ≤ 1, under a per-node budget.
Placement prefers distinct operators because the independence assumption is
broken by host concentration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .capsules import Capsule
from .params import DEFAULT, Params

__all__ = ["window_loss_q", "replicas_for", "annual_loss", "target_replicas", "Holder", "place_copies"]


def window_loss_q(t_host_days: float = DEFAULT.t_host_days, window_days: float = DEFAULT.repair_window_days) -> float:
    if t_host_days <= 0 or window_days <= 0:
        raise ValueError("lifetimes and windows must be positive")
    return 1.0 - math.exp(-window_days / t_host_days)


def replicas_for(eps: float, q: float) -> int:
    if not 0 < eps < 1 or not 0 < q < 1:
        raise ValueError("eps and q must be in (0, 1)")
    return max(1, math.ceil(math.log(1 / eps) / math.log(1 / q) - 1e-12))


def annual_loss(r: int, q: float, windows_per_year: float = 365.0 / 7.0) -> float:
    """Probability of losing a preserved capsule within a year (independent departures)."""
    p = q ** r
    return 1.0 - (1.0 - p) ** windows_per_year


def target_replicas(capsule: Capsule, estimated_holders: int, params: Params = DEFAULT) -> int:
    """Replica target for a capsule, or 0 if it is not eligible for preservation."""
    if not capsule.preserve or capsule.epistemic_distance > 1 or not capsule.anchor:
        return 0
    q = window_loss_q(params.t_host_days, params.repair_window_days)
    eps = params.eps_rare if estimated_holders < params.rare_holders_max else params.eps_default
    return replicas_for(eps, q)


@dataclass(frozen=True)
class Holder:
    node: str
    operator: str
    load: int = 0  # copies already hosted for third parties


def place_copies(r: int, holders: Sequence[Holder], params: Params = DEFAULT) -> list[Holder]:
    """Choose up to ``r`` holders on distinct operators, respecting the replica budget."""
    eligible = sorted((h for h in holders if h.load < params.replica_budget_per_node), key=lambda h: (h.load, h.node))
    chosen: list[Holder] = []
    ops: set[str] = set()
    for h in eligible:
        if len(chosen) >= r:
            break
        if h.operator not in ops:
            chosen.append(h)
            ops.add(h.operator)
    return chosen
