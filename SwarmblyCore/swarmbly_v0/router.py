"""The decomposability gate: "does this prompt survive fragmentation?".

The master document's architecture v0.2 grants the orchestrator **the right to
refuse to fragment**. This module is that right, implemented as a transparent
linear model over hand-written features rather than a learned classifier, so
that every decision can be explained in one line of text.

Asymmetry
---------
A *false positive* (fragmenting a prompt that should have stayed monolithic)
costs a degraded answer that the user actually receives. A *false negative*
(declining to fragment something that would have been fine) costs only the
speedup that fragmentation would have bought. The two are not symmetric, and
so the decision threshold is **not 0.5**: it defaults to
:data:`DEFAULT_THRESHOLD` = 0.62, i.e. the router must be clearly convinced
before it fragments. This mirrors the Tversky-loss asymmetry of the
Skeleton-of-Thought router cited in the master document.

The threshold is a parameter, not a constant, precisely because V1 of the
experimental plan is supposed to *tune* it against the criterion "recover
>=80% of the available gain with <5% false positives".
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .schema import RouterDecision
from .textutil import count_tokens

__all__ = [
    "DEFAULT_THRESHOLD",
    "FEATURE_WEIGHTS",
    "is_decomposable",
    "extract_features",
    "evaluate_router",
    "RouterEvaluation",
]

DEFAULT_THRESHOLD: float = 0.62
"""Decision threshold. Above 0.5 because false-positive fragmentation is worse."""

# Surface cues that a prompt is a bag of independent units.
_PARALLEL_CUES = (
    r"\bfor each\b", r"\beach of\b", r"\blist \d+\b", r"\bgenerate \d+\b",
    r"\bextract\b", r"\benumerate\b", r"\bbullet\b", r"\bone per\b",
    r"\bindependently\b", r"\bin parallel\b", r"\bseparately\b",
    r"\bsections?\b", r"\bchapters?\b", r"\bper (?:row|record|item|entry|file)\b",
    r"\bsummari[sz]e each\b", r"\brate each\b", r"\bscore each\b",
    r"\bsynthetic (?:data|records|examples)\b", r"\bsamples?\b",
)

# Surface cues that step i cannot start before step i-1 finished.
_SEQUENTIAL_CUES = (
    r"\bthen\b", r"\bafter (?:that|which)\b", r"\busing the (?:result|output|answer)\b",
    r"\bbased on the above\b", r"\bbuild(?:ing)? on\b", r"\bfrom the previous\b",
    r"\bstep[- ]by[- ]step\b", r"\bderive\b", r"\bprove\b", r"\btherefore\b",
    r"\bfeed[s]? into\b", r"\biterat", r"\bcarry (?:over|forward)\b",
    r"\bfinally\b", r"\bsubsequently\b", r"\bchain\b",
)

# Cues that a single continuous voice/state must be preserved end to end.
_CONTINUITY_CUES = (
    r"\bstory\b", r"\bnarrative\b", r"\bpoem\b", r"\bnovel\b", r"\bcharacter\b",
    r"\bvoice\b", r"\bfirst[- ]person\b", r"\bshared state\b", r"\bsame class\b",
    r"\bglobal variable\b", r"\brefactor\b", r"\bmutual(?:ly)? recursive\b",
    r"\bmaintain(?:ing)? consistency\b", r"\bsingle (?:coherent|continuous)\b",
    r"\bplot\b", r"\btone\b",
)

FEATURE_WEIGHTS: Mapping[str, float] = {
    "bias": -0.35,
    "parallel_cues": 1.55,
    "explicit_count": 1.20,
    "length": 1.05,
    "enumeration_structure": 0.85,
    "sequential_cues": -1.85,
    "continuity_cues": -1.70,
    "math_chain": -1.25,
}
"""Logistic weights. Positive => pushes toward fragmenting."""

_COUNT_RE = re.compile(r"\b(\d{1,4})\s+(?:items?|records?|rows?|examples?|sections?|"
                       r"questions?|bullets?|samples?|entries|paragraphs?|tests?)\b", re.I)
_ENUM_RE = re.compile(r"(^\s*(?:[-*•]|\d+[.)])\s+)", re.M)
_MATH_RE = re.compile(
    r"\b(?:solve|compute|calculate|prove|integral|derivative|equation|multi[- ]hop|"
    r"substitut|simultaneous|modulo|remainder)\b", re.I
)


def _count_hits(text: str, patterns: Iterable[str]) -> int:
    """Number of distinct cue patterns that match ``text``."""
    lowered = text.lower()
    return sum(1 for pattern in patterns if re.search(pattern, lowered))


def _saturate(count: int, scale: float) -> float:
    """Map a non-negative count into [0, 1) with diminishing returns."""
    return 1.0 - math.exp(-count / scale)


def extract_features(prompt: str) -> dict[str, float]:
    """Compute the router's feature vector for ``prompt``.

    All features are in ``[0, 1]`` (except the constant ``bias``) so that the
    weights in :data:`FEATURE_WEIGHTS` are directly comparable as importances.
    """
    n_tokens = count_tokens(prompt)
    parallel = _count_hits(prompt, _PARALLEL_CUES)
    sequential = _count_hits(prompt, _SEQUENTIAL_CUES)
    continuity = _count_hits(prompt, _CONTINUITY_CUES)
    explicit_counts = _COUNT_RE.findall(prompt)
    enum_markers = len(_ENUM_RE.findall(prompt))
    math_hits = len(_MATH_RE.findall(prompt))

    return {
        "bias": 1.0,
        "parallel_cues": _saturate(parallel, 1.8),
        "explicit_count": 1.0 if explicit_counts else 0.0,
        # Fragmentation only pays off once the prompt is big enough to split.
        "length": _saturate(max(0, n_tokens - 25), 90.0),
        "enumeration_structure": _saturate(enum_markers, 2.5),
        "sequential_cues": _saturate(sequential, 1.5),
        "continuity_cues": _saturate(continuity, 1.3),
        "math_chain": _saturate(math_hits, 2.0),
    }


def _logistic(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _rationale(features: Mapping[str, float], score: float, threshold: float,
               decomposable: bool) -> str:
    """One-sentence, human-auditable justification of the decision."""
    contributions = {
        name: FEATURE_WEIGHTS[name] * value
        for name, value in features.items()
        if name != "bias" and value != 0.0
    }
    ranked = sorted(contributions.items(), key=lambda kv: -abs(kv[1]))[:3]
    drivers = ", ".join(f"{name}={value:+.2f}" for name, value in ranked) or "no strong cues"
    verdict = "fragment" if decomposable else "keep monolithic"
    return (f"score {score:.3f} vs asymmetric threshold {threshold:.2f} -> {verdict}; "
            f"top drivers: {drivers}")


def is_decomposable(prompt: str, threshold: float = DEFAULT_THRESHOLD) -> RouterDecision:
    """Decide whether ``prompt`` should be fragmented.

    Args:
        prompt: The raw user prompt.
        threshold: Decision threshold in ``(0, 1)``. Raising it makes the
            router more conservative (fewer false-positive fragmentations).

    Returns:
        A :class:`~swarmbly_v0.schema.RouterDecision` carrying the boolean, the
        calibrated score, the full feature vector and a readable rationale.
    """
    if not 0.0 < threshold < 1.0:
        raise ValueError(f"threshold must be in (0, 1), got {threshold}")
    features = extract_features(prompt)
    logit = sum(FEATURE_WEIGHTS[name] * value for name, value in features.items())
    score = _logistic(logit)
    decomposable = score >= threshold
    return RouterDecision(
        decomposable=decomposable,
        score=score,
        threshold=threshold,
        features=features,
        rationale=_rationale(features, score, threshold, decomposable),
    )


@dataclass(frozen=True)
class RouterEvaluation:
    """Confusion-matrix summary of the router over a labelled prompt set."""

    threshold: float
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.true_negative + self.false_negative

    @property
    def accuracy(self) -> float:
        return (self.true_positive + self.true_negative) / self.total if self.total else 0.0

    @property
    def false_positive_rate(self) -> float:
        negatives = self.false_positive + self.true_negative
        return self.false_positive / negatives if negatives else 0.0

    @property
    def precision(self) -> float:
        predicted = self.true_positive + self.false_positive
        return self.true_positive / predicted if predicted else 0.0

    @property
    def recall(self) -> float:
        actual = self.true_positive + self.false_negative
        return self.true_positive / actual if actual else 0.0


def evaluate_router(
    labelled: Sequence[tuple[str, bool]],
    threshold: float = DEFAULT_THRESHOLD,
) -> RouterEvaluation:
    """Score the router against ``(prompt, expected_decomposable)`` pairs.

    The ``prompts/`` corpus shipped with this package doubles as this
    evaluation set, which is what V1 of the experimental plan needs.
    """
    tp = fp = tn = fn = 0
    for prompt, expected in labelled:
        predicted = is_decomposable(prompt, threshold).decomposable
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
        elif not predicted and not expected:
            tn += 1
        else:
            fn += 1
    return RouterEvaluation(threshold=threshold, true_positive=tp, false_positive=fp,
                            true_negative=tn, false_negative=fn)
