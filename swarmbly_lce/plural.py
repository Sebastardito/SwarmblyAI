"""Plural responses from replica agreement (SPEC 14).

Given, for each unit of an answer, the stance produced by each replica and
its model family, the ensemble presents the majority position and — only
when supported by at least ``PLURAL_MIN_FAMILIES`` families or by anchored
evidence — an alternative, every position labelled with its replica share.
Agreement across families is not evidence of truth (Kim et al., 2025), and
disagreement is not evidence of controversy.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .params import DEFAULT, Params

__all__ = ["ReplicaAnswer", "Position", "UnitPlural", "build_plural", "NOTE"]

NOTE = "agreement_is_not_truth"


@dataclass(frozen=True)
class ReplicaAnswer:
    unit: int
    stance: str
    family: str
    anchored_evidence: bool = False


@dataclass
class Position:
    stance: str
    share: float
    families: list[str]
    anchored: bool = False


@dataclass
class UnitPlural:
    unit: int
    positions: list[Position] = field(default_factory=list)

    @property
    def disagreement(self) -> bool:
        return len(self.positions) > 1


def build_plural(answers: Iterable[ReplicaAnswer], params: Params = DEFAULT) -> dict:
    by_unit: dict[int, list[ReplicaAnswer]] = defaultdict(list)
    for a in answers:
        by_unit[a.unit].append(a)
    units: list[UnitPlural] = []
    for unit in sorted(by_unit):
        rs = by_unit[unit]
        n = len(rs)
        groups: dict[str, list[ReplicaAnswer]] = defaultdict(list)
        for a in rs:
            groups[a.stance].append(a)
        ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        up = UnitPlural(unit)
        for i, (stance, members) in enumerate(ordered):
            fams = sorted({m.family for m in members})
            anchored = any(m.anchored_evidence for m in members)
            if i > 0 and not (len(fams) >= params.plural_min_families or anchored):
                continue  # an unsupported minority is not shown (false-balance guard)
            up.positions.append(Position(stance, round(len(members) / n, 4), fams, anchored))
        units.append(up)
    return {
        "units": [{"unit": u.unit, "positions": [p.__dict__ for p in u.positions]} for u in units if u.disagreement],
        "note": NOTE,
    }
