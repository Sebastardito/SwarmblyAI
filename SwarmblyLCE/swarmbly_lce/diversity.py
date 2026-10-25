"""Diversity instruments (SPEC 15.3, whitepaper 7.4–7.5 and 11.3).

* ``fst`` — Wright's fixation index over variant frequencies across demes,
  F_ST = (H_T − H_S) / H_T with expected heterozygosities.
* ``wright_fst`` / ``wright_nm`` — the island-model relation F_ST ≈ 1/(1+4Nm),
  usable only as a starting point (Whitlock & McCauley, 1999).
* ``conformist_step`` — Boyd & Richerson's Δp = D·p(1−p)(2p−1).
* ``CanarySet`` — tail mass, per-variant frequency and identity violations.
* ``homogeneity`` — mean pairwise cosine similarity, the Infinity-Chat style
  measure used by H-C17.
* ``error_agreement_given_both_wrong`` — the metric of Kim et al. (2025).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

from .social import identity_violation

__all__ = [
    "expected_heterozygosity",
    "fst",
    "wright_fst",
    "wright_nm",
    "conformist_step",
    "generations_to_loss",
    "CanaryItem",
    "CanarySet",
    "homogeneity",
    "error_agreement_given_both_wrong",
    "transmission_shares",
]


def expected_heterozygosity(freqs: Sequence[float]) -> float:
    s = sum(freqs)
    if s <= 0:
        return 0.0
    return 1.0 - sum((f / s) ** 2 for f in freqs)


def fst(demes: Sequence[Mapping[str, float]]) -> float:
    """F_ST from per-deme variant counts or frequencies (equal deme weights)."""
    variants = sorted({v for d in demes for v in d})
    if not variants or len(demes) < 2:
        return 0.0
    mats = []
    for d in demes:
        tot = sum(d.values())
        mats.append([d.get(v, 0.0) / tot if tot else 0.0 for v in variants])
    hs = float(np.mean([expected_heterozygosity(m) for m in mats]))
    pbar = np.mean(np.array(mats), axis=0)
    ht = expected_heterozygosity(list(pbar))
    return 0.0 if ht == 0 else max(0.0, (ht - hs) / ht)


def wright_fst(nm: float) -> float:
    if nm < 0:
        raise ValueError("Nm must be non-negative")
    return 1.0 / (1.0 + 4.0 * nm)


def wright_nm(f: float) -> float:
    if not 0 < f <= 1:
        raise ValueError("F_ST must be in (0, 1]")
    return (1.0 / f - 1.0) / 4.0


def conformist_step(p: float, d: float) -> float:
    return p + d * p * (1 - p) * (2 * p - 1)


def generations_to_loss(p0: float, d: float, threshold: float = 0.01, max_gen: int = 100_000) -> int:
    p, g = p0, 0
    while p > threshold and g < max_gen:
        p = conformist_step(p, d)
        g += 1
    return g


@dataclass(frozen=True)
class CanaryItem:
    variety: str  # e.g. "es-EC"
    term: str
    glosses: tuple[str, ...]  # acceptable gloss keywords
    verified: bool = False  # True only after native-speaker verification


@dataclass
class CanarySet:
    """Regionalisms used ONLY for measurement, never for training or capsules."""

    items: list[CanaryItem] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "CanarySet":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([CanaryItem(i["variety"], i["term"], tuple(i["glosses"]), bool(i.get("verified", False))) for i in data["items"]])

    def terms(self) -> set[str]:
        return {i.term.lower() for i in self.items}

    def guard_training(self, texts: Iterable[str]) -> None:
        """Raise if any canary term appears in candidate training data."""
        import re

        patterns = {term: re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)") for term in self.terms()}
        for t in texts:
            low = t.lower()
            for term, rx in patterns.items():
                if rx.search(low):
                    raise ValueError(f"canary term {term!r} found in training data; the canary set must never be trained on")

    def tail_mass(self, answers: Mapping[str, str]) -> float:
        """Fraction of canary items whose answer contains an acceptable gloss."""
        if not self.items:
            return 0.0
        ok = 0
        for i in self.items:
            a = answers.get(i.term, "").lower()
            if any(g.lower() in a for g in i.glosses):
                ok += 1
        return ok / len(self.items)

    @staticmethod
    def identity_violation_rate(answers: Iterable[str]) -> float:
        answers = list(answers)
        return 0.0 if not answers else sum(identity_violation(a) for a in answers) / len(answers)


def homogeneity(vectors: np.ndarray) -> float:
    """Mean pairwise cosine similarity of unit-norm row vectors."""
    n = len(vectors)
    if n < 2:
        return 1.0
    sims = vectors @ vectors.T
    iu = np.triu_indices(n, k=1)
    return float(np.mean(sims[iu]))


def error_agreement_given_both_wrong(answers_a: Sequence[str], answers_b: Sequence[str], gold: Sequence[str]) -> float | None:
    """P(a == b | a wrong and b wrong); None if the pair is never jointly wrong."""
    both, agree = 0, 0
    for a, b, g in zip(answers_a, answers_b, gold):
        if a != g and b != g:
            both += 1
            agree += int(a == b)
    return None if both == 0 else agree / both


def transmission_shares(paths: Iterable[str]) -> dict[str, float]:
    c = Counter(paths)
    n = sum(c.values())
    return {k: c[k] / n for k in ("vertical", "horizontal", "oblique")} if n else {k: 0.0 for k in ("vertical", "horizontal", "oblique")}
