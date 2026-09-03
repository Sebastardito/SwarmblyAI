"""The evaluator. Deliberately independent of ``swarmbly_v0.metrics``.

Why the boundary is the point
-----------------------------

The defect that cost this project four documents was a scorer whose behaviour
depended on metadata *about the partition* rather than on the answer: the
monolithic baseline entered by one code path and the fragmented arm by another,
the expected-entity set grew with N, omissions were attributed round-robin across
fragment heads, and seam-local classes could only fire where seams existed.
Scoring one identical sixteen-sentence answer through the two conventions
returned 0.9375 and 0.5000 -- an apparent tax of +46.7 % on text that never
changed.

A benchmark that imports that scorer inherits the risk. So this module imports
nothing from the harness's metrics, and its first test is the invariant that
broke there: **the same answer scores the same however the prompt was cut**.

What it measures, kept separate
-------------------------------

The flat answer key conflated three questions. They are separated here:

``correct``       did the claim match the canonical answer;
``answerable``    did the packet asked for it hold every fact it requires;
``attributed``    which packet should have carried each missing fact.

"Wrong" and "unanswerable" are different failures with different owners -- the
first belongs to the model, the second to the packer -- and six runs were spent
on questions where they were indistinguishable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .graph import Claim, Instance

__all__ = [
    "ClaimVerdict",
    "InstanceReport",
    "evaluate",
    "parse_claims",
]

_LINE = re.compile(r"[\[(]\s*(c[_\w]+|\d{1,3})\s*[\])]\s*[:=]?\s*(-?[\d,]+(?:\.\d+)?)")
_TOLERANCE = 0.005
"""Relative tolerance on a numeric answer. Half a percent: tight enough that a
different computation fails, loose enough that a rounded restatement of the right
one does not."""


def parse_claims(text: str) -> dict[str, float]:
    """Read ``[claim_id] value`` lines out of an answer.

    Accepts ``[c_s1] 1430``, ``(c_s1): 1,430``, ``[c_s1]=1430.0``. Deliberately
    strict about the bracket: a chain step whose prose ends "...from step 3."
    must not be read as an answer to step 3, which is a defect the harness's
    grader carried until it was caught by fault injection.
    """
    out: dict[str, float] = {}
    for match in _LINE.finditer(text):
        key = match.group(1)
        try:
            value = float(match.group(2).replace(",", ""))
        except ValueError:
            continue
        out.setdefault(key, value)
    return out


@dataclass(frozen=True)
class ClaimVerdict:
    """One claim, judged on three separate axes."""

    claim_id: str
    kind: str
    stated: float | None
    expected: float
    correct: bool | None
    answerable: bool
    missing_facts: tuple[str, ...]
    owed_by: tuple[str, ...]

    @property
    def failure(self) -> str:
        """Whose failure this is, in one word."""
        if self.correct is None:
            return "not_stated"
        if self.correct:
            return "none"
        return "unanswerable" if not self.answerable else "wrong"


@dataclass
class InstanceReport:
    """Everything measured for one instance, with the denominators."""

    instance_id: str
    task_class: str
    arm: str
    verdicts: tuple[ClaimVerdict, ...] = field(default_factory=tuple)

    @property
    def n_claims(self) -> int:
        return len(self.verdicts)

    def _rate(self, predicate) -> float | None:
        graded = [v for v in self.verdicts if v.correct is not None]
        if not graded:
            return None
        return sum(1 for v in graded if predicate(v)) / len(graded)

    @property
    def accuracy(self) -> float | None:
        return self._rate(lambda v: v.correct)

    @property
    def coverage(self) -> float:
        """Share of claims the answer stated at all."""
        if not self.verdicts:
            return 0.0
        return sum(1 for v in self.verdicts if v.stated is not None) / len(self.verdicts)

    @property
    def unanswerable_rate(self) -> float:
        """Share of claims whose packet could not have produced them.

        The packer's number, not the model's. A run where this is high has a
        packing problem wearing a capability problem's clothes.
        """
        if not self.verdicts:
            return 0.0
        return sum(1 for v in self.verdicts if not v.answerable) / len(self.verdicts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "task_class": self.task_class,
            "arm": self.arm,
            "n_claims": self.n_claims,
            "n_graded": sum(1 for v in self.verdicts if v.correct is not None),
            "accuracy": self.accuracy,
            "coverage": round(self.coverage, 6),
            "unanswerable_rate": round(self.unanswerable_rate, 6),
            "failures": {
                mode: sum(1 for v in self.verdicts if v.failure == mode)
                for mode in ("none", "wrong", "unanswerable", "not_stated")
            },
            "claims": [
                {"claim_id": v.claim_id, "kind": v.kind, "stated": v.stated,
                 "expected": v.expected, "correct": v.correct,
                 "answerable": v.answerable, "failure": v.failure,
                 "missing_facts": list(v.missing_facts),
                 "owed_by": list(v.owed_by)}
                for v in self.verdicts
            ],
        }


def _matches(stated: float, expected: float) -> bool:
    if expected == 0:
        return abs(stated) <= _TOLERANCE
    return abs(stated - expected) / abs(expected) <= _TOLERANCE


def evaluate(
    instance: Instance,
    answer: str,
    arm: str,
    facts_available: Mapping[str, Sequence[str]] | None = None,
    claim_owner: Mapping[str, str] | None = None,
) -> InstanceReport:
    """Judge one answer against the instance's canonical claims.

    Args:
        instance: The instance, carrying the facts and the canonical answers.
        answer: The assembled text to judge.
        arm: Which arm produced it -- recorded, never used in the judging. That
            separation is the whole point of this module: a scorer that behaves
            differently depending on which arm it is looking at cannot compare
            arms.
        facts_available: ``packet_id -> fact ids that packet held``. Supplied by
            the runner. When absent every fact is treated as available, which is
            the monolithic case.
        claim_owner: ``claim_id -> packet_id`` for the packet that was asked for
            that claim. Used to decide *which* packet had to hold the facts, and
            to attribute a missing fact to the packet that owed it.

    Returns:
        An :class:`InstanceReport`. ``correct`` is ``None`` for a claim the
        answer never stated -- neither right nor wrong, and folding it into
        either verdict would move accuracy toward whichever was chosen.
    """
    stated = parse_claims(answer)
    owner = dict(claim_owner or {})
    available = {k: set(v) for k, v in (facts_available or {}).items()}
    everything = set(instance.facts)

    verdicts: list[ClaimVerdict] = []
    for claim in instance.claims:
        held = available.get(owner.get(claim.claim_id, ""), everything) \
            if available else everything
        missing = tuple(sorted(set(claim.requires) - held))
        value = stated.get(claim.claim_id)
        verdicts.append(ClaimVerdict(
            claim_id=claim.claim_id,
            kind=claim.kind,
            stated=value,
            expected=claim.answer,
            correct=None if value is None else _matches(value, claim.answer),
            answerable=not missing,
            missing_facts=missing,
            owed_by=tuple(sorted({instance.facts[f].section_id
                                  for f in missing if f in instance.facts})),
        ))

    return InstanceReport(instance_id=instance.instance_id,
                          task_class=instance.task_class,
                          arm=arm, verdicts=tuple(verdicts))
