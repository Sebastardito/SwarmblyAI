"""Micro-level assembly: k replicas of one micro-task, resolved by consensus.

Swarmbly assembles at **two distinct levels**, and they are not the same
operation:

**Macro (``assembler.select_then_splice``)**
    Different *sub-tasks* of one large task, each generated once, joined by
    overlap-and-splice with flanking context. This is the level ``rho`` is
    defined at, and the level the coherence tax is measured at. It is used for
    long generative work that genuinely decomposes.

**Micro (this module)**
    ``k`` **complete replicas of the same micro-task**, produced by nodes of
    deliberately different model families, resolved by multiple alignment over
    semantic units plus a per-unit agreement score. Nothing is split here: each
    replica is a whole answer to the whole micro-task. What varies between
    replicas is the *sampling*, and redundancy is what makes the variance
    visible.

.. warning::
   **Splitting an atomic question into partial sub-questions is explicitly not
   supported, at either level.** "What is the capital of France, and is it in
   the EU?" may be split (two independent facts); "Is the treatment effective
   given this patient's history?" may not, because a fragment that sees only
   half the history is answering a different question. Decomposition that
   removes information *before* sampling destroys information that no amount of
   redundancy afterwards can recover -- averaging ``k`` answers to the wrong
   question yields a confident wrong answer. An atomic request therefore skips
   the macro level entirely (the router refuses to fragment it) and goes
   straight to micro with ``k`` replicas of the *whole* request.

Why alignment rather than voting
--------------------------------
Two nodes answering the same question rarely produce the same units in the same
order: one covers four points, another five, and the shared points appear in
different positions. Positional zipping would therefore compare unit 3 of one
replica against unit 3 of another when they are about different things, and
report disagreement that is really misalignment. So this module does proper
**progressive multiple alignment** -- pairwise similarity matrix, guide order,
progressive profile alignment with gaps -- which is what makes "replica B never
mentioned this at all" distinguishable from "replica B contradicted it".

Thresholds
----------
``alpha_high`` and ``alpha_low`` are **provisional placeholders and must be
calibrated**, exactly as ``tau_sem`` must be (see
:func:`swarmbly_v0.metrics.calibrate_tau` and
:func:`swarmbly_v0.metrics.calibrate_alpha`). They are exposed as parameters
everywhere and are never read from module state at call time.

Scope
-----
Agreement is **not truth**. It measures whether independently sampled replicas
converged, which is a proxy for variance, not for accuracy. Models that share
training data share errors, so agreement among near-identical models is close
to worthless; cross-family diversity is what makes the signal mean anything.
Whether agreement actually predicts correctness is an empirical question this
module makes *measurable* (see the agreement-vs-quality calibration in
:mod:`swarmbly_v0.experiment`) and does not answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .metrics import quality_judge
from .schema import Contract
from .textutil import count_tokens, split_sentences

__all__ = [
    "Unit",
    "Column",
    "ConsensusUnit",
    "LowConfidenceRegion",
    "ConsensusResult",
    "Replica",
    "DEFAULT_ALPHA_HIGH",
    "DEFAULT_ALPHA_LOW",
    "DEFAULT_GAP_PENALTY",
    "DEFAULT_CONSISTENCY",
    "DEFAULT_ACCEPT",
    "LABELS",
    "UNIT_JUDGE_WEIGHTS",
    "unit_judge",
    "segment_units",
    "align_multiple",
    "agreement_score",
    "consensus",
]

DEFAULT_ALPHA_HIGH = 0.80
"""Provisional placeholder. Above this, the medoid unit is taken unjudged.

**Requires calibration**, exactly like ``tau_sem``. The number is a starting
point for the mock harness and carries no evidential weight: it was not fitted
on labelled data, and an agreement score is a function of the embedder, the
consistency threshold and the model families in the pool, none of which are
portable. Use :func:`swarmbly_v0.metrics.calibrate_alpha`.
"""

DEFAULT_ALPHA_LOW = 0.55
"""Provisional placeholder. Below this, the unit is flagged low-confidence.

**Requires calibration** -- see :data:`DEFAULT_ALPHA_HIGH`. The gap between the
two alphas is the band where the judge decides but the result is still trusted;
below ``alpha_low`` the judge decides *and* the region is reported to the user
as unreliable.
"""

DEFAULT_GAP_PENALTY = 0.35
"""Cost of aligning a unit against a gap. Provisional; tune with the embedder.

The value has one consequence worth stating. Two replicas that transpose an
adjacent pair of units can be aligned either as two forced mismatches (cost
``2 - 2 * cross_similarity``) or as two gaps (cost ``2 * gap_penalty``). Below
roughly ``0.4`` the aligner prefers the gaps, which is the correct reading: the
units did not correspond, one replica simply put them in the other order. Above
it, transpositions silently become "disagreement" and the agreement score
reports misalignment as conflict.
"""

DEFAULT_CONSISTENCY = 0.50
"""Mean-pairwise-similarity above which two units count as saying the same thing.

Provisional placeholder on the same footing as the alphas: cosine values are not
portable between embedding models, so this must be re-derived whenever the
embedder changes.
"""

DEFAULT_ACCEPT = 0.40
"""Judge score at or above which a unit counts as acceptable.

**Provisional placeholder**, on exactly the same footing as the alphas. With a
real judge this is a decision boundary that must be set from labelled data;
here it was chosen so that both classes are populated under the mock (whose
unit judge scores have a median near 0.39), which makes the correlation
estimable and makes the number itself worthless as evidence. It affects only
the agreement-vs-quality calibration data, never the routing.
"""

LABELS: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")
"""Confidence labels, in descending order of agreement."""

# Clause boundaries: semicolons, colons, em-dashes, and a comma followed by a
# coordinator. Deliberately conservative -- over-splitting turns one claim into
# several columns and inflates apparent disagreement.
_CLAUSE_SPLIT_RE = re.compile(
    r"(?<=[;:])\s+|\s+--\s+|,\s+(?=(?:and|but|or|so|because|while|whereas|which|although)\b)",
    re.I,
)
_MIN_CLAUSE_TOKENS = 4


UNIT_JUDGE_WEIGHTS: dict[str, float] = {
    "entity_coverage": 0.25,
    "forbidden_clean": 0.15,
    "register_match": 0.20,
    "length_match": 0.0,
    "relevance": 0.40,
}
"""Judge weights for a **unit**, not a whole answer.

``length_match`` is zeroed. The contract's ``target_length_tokens`` describes
the complete reply; scoring one sentence against it would charge every unit for
not being the whole answer, compress every score into the same narrow band, and
make the judge useless precisely where consensus needs it -- choosing *between*
two units of comparable length. The remaining mass goes to relevance.
"""


def unit_judge(text: str, contract: Contract, embedder: Any = None) -> float:
    """Contract-relative quality of a single semantic unit, in ``[0, 1]``.

    A thin wrapper over :func:`swarmbly_v0.metrics.quality_judge` with
    :data:`UNIT_JUDGE_WEIGHTS`. It is a mechanical stand-in for an LLM judge and
    inherits every limitation of one; the point of the agreement-vs-quality
    correlation is that this judge and the agreement score are *independent*
    instruments, so their relationship carries information neither has alone.
    """
    return quality_judge(text, contract, embedder, weights=UNIT_JUDGE_WEIGHTS)


# --------------------------------------------------------------------------
# Types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    """One semantic unit of one replica."""

    text: str
    replica_id: str = ""
    index: int = 0

    @property
    def tokens(self) -> int:
        return count_tokens(self.text)


@dataclass(frozen=True)
class Replica:
    """One complete answer to the whole micro-task, from one node."""

    replica_id: str
    text: str
    family: str = ""
    model: str = ""


@dataclass
class Column:
    """One aligned position: at most one unit per replica, gaps allowed.

    A replica missing from :attr:`units` did not cover this position at all --
    a gap. That is a different observation from covering it and disagreeing,
    and keeping the two distinguishable is the point of aligning rather than
    voting.
    """

    index: int
    replica_ids: tuple[str, ...]
    units: dict[str, Unit] = field(default_factory=dict)
    vectors: dict[str, np.ndarray] = field(default_factory=dict, repr=False)

    @property
    def k(self) -> int:
        """Number of replicas participating in the alignment (present or not)."""
        return len(self.replica_ids)

    @property
    def present(self) -> list[Unit]:
        """Units actually present, in replica order (deterministic)."""
        return [self.units[rid] for rid in self.replica_ids if rid in self.units]

    @property
    def n_present(self) -> int:
        return len(self.present)

    @property
    def n_gaps(self) -> int:
        return self.k - self.n_present

    @property
    def contributing(self) -> tuple[str, ...]:
        return tuple(rid for rid in self.replica_ids if rid in self.units)


@dataclass(frozen=True)
class ConsensusUnit:
    """One resolved unit of the consensus answer, with its confidence."""

    text: str
    label: str
    agreement: float
    contributing: tuple[str, ...]
    judge_score: float = 0.0
    accepted: bool = False
    column_index: int = 0

    @property
    def low_confidence(self) -> bool:
        return self.label == "LOW"


@dataclass(frozen=True)
class LowConfidenceRegion:
    """A maximal run of consecutive LOW units in the consensus answer."""

    start: int
    end: int
    mean_agreement: float
    text: str

    @property
    def n_units(self) -> int:
        return self.end - self.start + 1


@dataclass
class ConsensusResult:
    """Result of micro-level assembly over ``k`` replicas."""

    text: str
    units: list[ConsensusUnit] = field(default_factory=list)
    low_confidence_regions: list[LowConfidenceRegion] = field(default_factory=list)
    k: int = 0
    families: tuple[str, ...] = ()
    alpha_high: float = DEFAULT_ALPHA_HIGH
    alpha_low: float = DEFAULT_ALPHA_LOW

    @property
    def n_families(self) -> int:
        return len(set(self.families))

    @property
    def mean_agreement(self) -> float:
        if not self.units:
            return 0.0
        return sum(u.agreement for u in self.units) / len(self.units)

    def label_fractions(self) -> dict[str, float]:
        """Fraction of consensus units carrying each confidence label."""
        if not self.units:
            return {label: 0.0 for label in LABELS}
        total = len(self.units)
        return {
            label: sum(1 for u in self.units if u.label == label) / total
            for label in LABELS
        }

    def calibration_points(self) -> list[tuple[float, bool]]:
        """``(agreement, judged_acceptable)`` per unit -- the calibration data.

        This is the raw material for the agreement-vs-quality correlation, the
        number that decides whether the agreement score means anything at all.
        """
        return [(u.agreement, u.accepted) for u in self.units]


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------


def segment_units(text: str, granularity: str = "sentence") -> list[Unit]:
    """Split ``text`` into semantic units.

    Args:
        text: One replica's complete reply.
        granularity: ``"sentence"`` (the default; one unit per sentence, using
            the harness' shared sentence splitter), ``"clause"`` (sentences
            split further at semicolons, colons, em-dashes and comma +
            coordinator), or ``"line"`` (one unit per non-empty line, no
            sentence splitting at all). Clause granularity localises
            disagreement more precisely at the cost of splitting single claims
            across columns, which depresses agreement scores; sentence
            granularity is the conservative default.

            ``"line"`` exists for answer sheets, where the layout *is* the
            structure. The V3c ground-truth run of 24 August 2026 lost 73 % of
            its control category to sentence splitting: a reply of
            ``[01] Osaka`` was cut between the label and the answer, leaving one
            unit holding a label with nothing after it and the next holding an
            answer belonging to nobody. Forty-three percent of all units came
            back unlabelled and the task no model should fail read 21 % correct.
            When one line is one answer, splitting inside it destroys the
            observation.

    Returns:
        Units in reading order, indexed from 0. Empty and whitespace-only
        segments are dropped; clause fragments shorter than four tokens are
        merged back into the preceding unit rather than becoming columns of
        their own.
    """
    if granularity not in {"sentence", "clause", "line"}:
        raise ValueError(
            f"granularity must be 'sentence', 'clause' or 'line', got {granularity!r}")

    if granularity == "line":
        pieces = [line.strip() for line in (text or "").splitlines() if line.strip()]
        return [Unit(text=piece, index=i) for i, piece in enumerate(pieces)]

    sentences = split_sentences(text)
    if granularity == "sentence":
        pieces = sentences
    else:
        pieces = []
        for sentence in sentences:
            parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(sentence) if p and p.strip()]
            for part in parts:
                if pieces and count_tokens(part) < _MIN_CLAUSE_TOKENS:
                    pieces[-1] = f"{pieces[-1]} {part}"
                else:
                    pieces.append(part)

    return [Unit(text=piece, index=i) for i, piece in enumerate(p for p in pieces if p.strip())]


# --------------------------------------------------------------------------
# Progressive multiple alignment
# --------------------------------------------------------------------------


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def _embed_units(
    replicas_units: Sequence[Sequence[Unit]], embedder: Any
) -> list[np.ndarray]:
    """Embed every unit of every replica in one call, returned per replica."""
    flat = [unit.text for units in replicas_units for unit in units]
    if not flat:
        return [np.zeros((0, 1)) for _ in replicas_units]
    vectors = _normalize_rows(np.asarray(embedder.embed(flat), dtype=np.float64))
    out: list[np.ndarray] = []
    cursor = 0
    for units in replicas_units:
        out.append(vectors[cursor : cursor + len(units)])
        cursor += len(units)
    return out


def _pairwise_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``(len(a), len(b))`` cosine matrix; both inputs are already unit-norm."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    return a @ b.T


def _needleman_wunsch(
    scores: np.ndarray, gap_penalty: float
) -> tuple[float, list[tuple[int | None, int | None]]]:
    """Global alignment of two ordered item sequences.

    Args:
        scores: ``(n, m)`` match scores; ``scores[i, j]`` is the reward for
            aligning item ``i`` of the first sequence with item ``j`` of the
            second.
        gap_penalty: Cost charged for each item aligned against a gap.

    Returns:
        ``(total_score, path)`` where ``path`` is a list of
        ``(i_or_None, j_or_None)`` pairs in order. Ties break diagonal >
        up > left, which keeps the alignment deterministic.
    """
    n, m = scores.shape
    dp = np.zeros((n + 1, m + 1), dtype=np.float64)
    # 0 = diagonal (match), 1 = up (gap in the second sequence), 2 = left.
    back = np.zeros((n + 1, m + 1), dtype=np.int8)

    for i in range(1, n + 1):
        dp[i, 0] = dp[i - 1, 0] - gap_penalty
        back[i, 0] = 1
    for j in range(1, m + 1):
        dp[0, j] = dp[0, j - 1] - gap_penalty
        back[0, j] = 2

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diagonal = dp[i - 1, j - 1] + scores[i - 1, j - 1]
            up = dp[i - 1, j] - gap_penalty
            left = dp[i, j - 1] - gap_penalty
            best = diagonal
            choice = 0
            if up > best + 1e-12:
                best, choice = up, 1
            if left > best + 1e-12:
                best, choice = left, 2
            dp[i, j] = best
            back[i, j] = choice

    path: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and back[i, j] == 0:
            path.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and (j == 0 or back[i, j] == 1):
            path.append((i - 1, None))
            i -= 1
        else:
            path.append((None, j - 1))
            j -= 1
    path.reverse()
    return float(dp[n, m]), path


def _guide_order(similarity: np.ndarray) -> list[int]:
    """Merge order for progressive alignment: most-similar-first.

    The two most similar replicas seed the profile; thereafter the replica with
    the highest mean similarity to everything already merged is added next.
    Ties break toward the lower index so the order is deterministic.
    """
    n = similarity.shape[0]
    if n <= 1:
        return list(range(n))

    best_pair = (0, 1)
    best_score = -np.inf
    for i in range(n):
        for j in range(i + 1, n):
            if similarity[i, j] > best_score + 1e-12:
                best_score = similarity[i, j]
                best_pair = (i, j)

    order = [best_pair[0], best_pair[1]]
    remaining = [i for i in range(n) if i not in order]
    while remaining:
        best_index = remaining[0]
        best_mean = -np.inf
        for candidate in remaining:
            mean = float(np.mean([similarity[candidate, m] for m in order]))
            if mean > best_mean + 1e-12:
                best_mean, best_index = mean, candidate
        order.append(best_index)
        remaining.remove(best_index)
    return order


def _profile_scores(
    profile: Sequence[dict[int, int]],
    new_vectors: np.ndarray,
    per_replica_vectors: Sequence[np.ndarray],
) -> np.ndarray:
    """Match scores between each profile column and each new unit.

    A column's score against a unit is the **mean** cosine over the units
    actually present in that column; gaps contribute nothing and do not dilute
    the score, so a column held by one replica is not automatically penalised
    at alignment time (it is penalised later, by the agreement score).
    """
    n, m = len(profile), len(new_vectors)
    out = np.zeros((n, m), dtype=np.float64)
    for i, column in enumerate(profile):
        members = [per_replica_vectors[rep][idx] for rep, idx in sorted(column.items())]
        if not members:
            continue
        stacked = np.vstack(members)
        out[i] = np.mean(stacked @ new_vectors.T, axis=0) if m else out[i]
    return out


def align_multiple(
    replicas_units: Sequence[Sequence[Unit]],
    embedder: Any,
    gap_penalty: float = DEFAULT_GAP_PENALTY,
) -> list[Column]:
    """Progressive multiple alignment of semantic units across replicas.

    Three stages, the standard progressive-alignment recipe:

    1. **Pairwise similarity matrix.** Every pair of replicas is aligned with
       Needleman-Wunsch over embedding cosines, and the resulting score is
       length-normalised into a replica-vs-replica similarity.
    2. **Guide order.** The most similar pair seeds the profile; each further
       replica is merged in order of mean similarity to the profile so far.
       (A full guide *tree* would be the textbook choice; a guide *order* is
       its degenerate case and is enough for the ``k <= 9`` this protocol
       dispatches. Ordering by similarity still matters: merging the outlier
       replica first would propagate its idiosyncratic gaps into every
       subsequent column.)
    3. **Progressive profile alignment.** Each replica is aligned against the
       accumulated profile of columns, not against a single reference, so a
       unit two replicas share lands in one column even when a third omitted
       it.

    Args:
        replicas_units: One ordered unit list per replica, as produced by
            :func:`segment_units`.
        embedder: Anything with ``.embed(texts) -> array``; embedding cosine is
            the scoring function.
        gap_penalty: Cost of aligning a unit against a gap. Higher values make
            the aligner prefer to align dissimilar units rather than open a
            gap; lower values make it gap freely.

    Returns:
        Columns in reading order. Every column carries the ``replica_ids`` of
        *all* replicas, so a replica absent from ``column.units`` is visibly a
        gap rather than silently missing.
    """
    replicas_units = [list(units) for units in replicas_units]
    replica_ids = tuple(
        (units[0].replica_id if units and units[0].replica_id else f"r{i}")
        for i, units in enumerate(replicas_units)
    )
    if not replicas_units:
        return []

    vectors = _embed_units(replicas_units, embedder)

    # -- 1. pairwise similarity -------------------------------------------
    n = len(replicas_units)
    similarity = np.eye(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            scores = _pairwise_similarity(vectors[i], vectors[j])
            if scores.size == 0:
                value = 0.0
            else:
                total, _ = _needleman_wunsch(scores, gap_penalty)
                value = total / max(1, min(len(vectors[i]), len(vectors[j])))
            similarity[i, j] = similarity[j, i] = value

    # -- 2. guide order ----------------------------------------------------
    order = _guide_order(similarity)

    # -- 3. progressive profile alignment ----------------------------------
    # A profile column maps replica index -> unit index within that replica.
    first = order[0]
    profile: list[dict[int, int]] = [{first: i} for i in range(len(replicas_units[first]))]

    for replica in order[1:]:
        new_vectors = vectors[replica]
        if len(profile) == 0:
            profile = [{replica: i} for i in range(len(new_vectors))]
            continue
        if len(new_vectors) == 0:
            continue
        scores = _profile_scores(profile, new_vectors, vectors)
        _, path = _needleman_wunsch(scores, gap_penalty)
        merged: list[dict[int, int]] = []
        for column_index, unit_index in path:
            if column_index is not None and unit_index is not None:
                column = dict(profile[column_index])
                column[replica] = unit_index
                merged.append(column)
            elif column_index is not None:
                merged.append(dict(profile[column_index]))
            elif unit_index is not None:
                merged.append({replica: unit_index})
        profile = merged

    columns: list[Column] = []
    for position, column in enumerate(profile):
        units = {
            replica_ids[rep]: replicas_units[rep][idx] for rep, idx in sorted(column.items())
        }
        column_vectors = {
            replica_ids[rep]: vectors[rep][idx] for rep, idx in sorted(column.items())
        }
        columns.append(
            Column(index=position, replica_ids=replica_ids, units=units,
                   vectors=column_vectors)
        )
    return columns


# --------------------------------------------------------------------------
# Agreement
# --------------------------------------------------------------------------


def _column_vectors(column: Column, embedder: Any) -> dict[str, np.ndarray]:
    """Cached unit vectors for a column, embedding on demand if absent."""
    if column.vectors:
        return column.vectors
    present = column.present
    if not present:
        return {}
    matrix = _normalize_rows(
        np.asarray(embedder.embed([u.text for u in present]), dtype=np.float64)
    )
    return {unit.replica_id or f"r{i}": matrix[i] for i, unit in enumerate(present)}


def agreement_score(
    column: Column,
    embedder: Any,
    consistency_threshold: float = DEFAULT_CONSISTENCY,
) -> float:
    """Fraction of the ``k`` replicas that mutually agree at this column.

    A present unit counts as *consistent* when its mean cosine to the other
    present units is at least ``consistency_threshold``; a column with a single
    present unit is trivially consistent with itself. The count of consistent
    units is then normalised by ``k`` -- **every** replica dispatched, not just
    the ones that produced something here.

    That normalisation is the whole design. A column where 1 replica of 5 has
    content scores ``0.2`` however eloquent that one unit is, because four
    nodes looked at the same task and did not say it. A column where all 5
    replicas say the same thing scores ``1.0``. Silence is evidence.

    Returns:
        A value in ``[0, 1]``.
    """
    k = column.k
    if k == 0:
        return 0.0
    present = column.present
    if not present:
        return 0.0
    if len(present) == 1:
        return 1.0 / k

    vectors = _column_vectors(column, embedder)
    matrix = np.vstack([vectors[unit.replica_id] for unit in present])
    similarity = matrix @ matrix.T
    np.fill_diagonal(similarity, np.nan)
    means = np.nanmean(similarity, axis=1)
    consistent = int(np.sum(means >= consistency_threshold))
    return consistent / k


# --------------------------------------------------------------------------
# Consensus
# --------------------------------------------------------------------------


def _medoid(column: Column, embedder: Any) -> Unit:
    """The present unit closest to all the others -- the majority reading.

    With two present units the pair is symmetric and the earlier replica wins;
    that tie-break is deterministic, which matters more here than which of two
    equally central units is picked.
    """
    present = column.present
    if len(present) == 1:
        return present[0]
    vectors = _column_vectors(column, embedder)
    matrix = np.vstack([vectors[unit.replica_id] for unit in present])
    similarity = matrix @ matrix.T
    np.fill_diagonal(similarity, np.nan)
    means = np.nanmean(similarity, axis=1)
    return present[int(np.argmax(means))]


def _judge_select(
    column: Column,
    contract: Contract,
    embed_source: Any,
    judge: Callable[..., float],
) -> tuple[Unit, float]:
    """Pick the present unit the judge scores highest against the contract."""
    present = column.present
    best_unit = present[0]
    best_score = float(judge(present[0].text, contract, embed_source))
    for unit in present[1:]:
        score = float(judge(unit.text, contract, embed_source))
        if score > best_score + 1e-12:  # ties keep the earlier replica
            best_unit, best_score = unit, score
    return best_unit, best_score


def _as_replicas(replicas: Sequence[Any]) -> list[Replica]:
    """Accept ``Replica`` objects, plain strings, or mappings."""
    out: list[Replica] = []
    for i, item in enumerate(replicas):
        if isinstance(item, Replica):
            out.append(item if item.replica_id else Replica(f"r{i}", item.text,
                                                            item.family, item.model))
        elif isinstance(item, str):
            out.append(Replica(replica_id=f"r{i}", text=item))
        elif isinstance(item, Mapping):
            out.append(
                Replica(
                    replica_id=str(item.get("replica_id", f"r{i}")),
                    text=str(item.get("text", "")),
                    family=str(item.get("family", "")),
                    model=str(item.get("model", "")),
                )
            )
        else:
            raise TypeError(f"replica {i} must be a Replica, str or mapping, got {type(item)}")
    return out


def _low_confidence_regions(units: Sequence[ConsensusUnit]) -> list[LowConfidenceRegion]:
    """Merge consecutive LOW units into maximal regions."""
    regions: list[LowConfidenceRegion] = []
    start: int | None = None
    for i, unit in enumerate(units):
        if unit.label == "LOW" and start is None:
            start = i
        elif unit.label != "LOW" and start is not None:
            regions.append(_make_region(units, start, i - 1))
            start = None
    if start is not None:
        regions.append(_make_region(units, start, len(units) - 1))
    return regions


def _make_region(units: Sequence[ConsensusUnit], start: int, end: int) -> LowConfidenceRegion:
    span = units[start : end + 1]
    mean = sum(u.agreement for u in span) / len(span)
    return LowConfidenceRegion(
        start=start, end=end, mean_agreement=mean,
        text=" ".join(u.text for u in span),
    )


def consensus(
    replicas: Sequence[Any],
    contract: Contract,
    embedder: Any,
    backend: Any = None,
    alpha_high: float = DEFAULT_ALPHA_HIGH,
    alpha_low: float = DEFAULT_ALPHA_LOW,
    judge: Callable[..., float] = unit_judge,
    *,
    granularity: str = "sentence",
    gap_penalty: float = DEFAULT_GAP_PENALTY,
    consistency_threshold: float = DEFAULT_CONSISTENCY,
    accept_threshold: float = DEFAULT_ACCEPT,
) -> ConsensusResult:
    """Resolve ``k`` replicas of one micro-task into a single answer.

    Every replica is a *complete* answer to the *same* micro-task; nothing was
    split to produce them (see the module docstring). Replicas are segmented,
    aligned, and each aligned column is routed by its agreement score:

    * ``agreement >= alpha_high`` -- take the medoid unit, label ``HIGH``. The
      replicas converged; no judge call is spent.
    * ``alpha_low <= agreement < alpha_high`` -- the judge selects among the
      column's units against the contract, label ``MEDIUM``.
    * ``agreement < alpha_low`` -- the judge selects, label ``LOW``, and the
      unit is recorded in a low-confidence region so the answer can be
      *reported* as unreliable there instead of silently averaging.

    Args:
        replicas: :class:`Replica` objects (or bare strings, which get
            synthetic ids and no family). Their ``family`` is what makes the
            agreement signal meaningful -- see the module docstring.
        contract: The global contract, used by the judge.
        embedder: Embedding source for alignment and agreement.
        backend: Fallback embedding source when ``embedder`` is ``None``, and
            the generation surface a future synthesising resolver would use.
            The current policy never synthesises at the micro level: selecting
            among replicas is lossless, rewriting is not.
        alpha_high: Upper routing threshold. **Provisional -- calibrate it**
            (:func:`swarmbly_v0.metrics.calibrate_alpha`).
        alpha_low: Lower routing threshold. Same caveat.
        judge: ``judge(text, contract, embedder) -> float`` in ``[0, 1]``.
        granularity: Passed to :func:`segment_units`.
        gap_penalty: Passed to :func:`align_multiple`.
        consistency_threshold: Passed to :func:`agreement_score`.
        accept_threshold: Judge score at or above which a unit is recorded as
            acceptable. Used only for the agreement-vs-quality calibration.

    Returns:
        A :class:`ConsensusResult` -- the assembled text plus the confidence
        map that lets a caller see *where* the swarm disagreed.
    """
    if alpha_low > alpha_high:
        raise ValueError(f"alpha_low ({alpha_low}) must not exceed alpha_high ({alpha_high})")

    items = _as_replicas(replicas)
    embed_source = embedder if embedder is not None else backend
    families = tuple(item.family for item in items)

    if not items:
        return ConsensusResult(text="", k=0, families=(), alpha_high=alpha_high,
                               alpha_low=alpha_low)

    replicas_units: list[list[Unit]] = []
    for item in items:
        units = segment_units(item.text, granularity)
        replicas_units.append(
            [Unit(text=u.text, replica_id=item.replica_id, index=u.index) for u in units]
        )

    columns = align_multiple(replicas_units, embed_source, gap_penalty)

    resolved: list[ConsensusUnit] = []
    for column in columns:
        if not column.present:
            continue
        agreement = agreement_score(column, embed_source, consistency_threshold)
        if agreement >= alpha_high:
            unit = _medoid(column, embed_source)
            label = "HIGH"
            score = float(judge(unit.text, contract, embed_source))
        else:
            unit, score = _judge_select(column, contract, embed_source, judge)
            label = "MEDIUM" if agreement >= alpha_low else "LOW"
        resolved.append(
            ConsensusUnit(
                text=unit.text,
                label=label,
                agreement=float(agreement),
                contributing=column.contributing,
                judge_score=score,
                accepted=score >= accept_threshold,
                column_index=column.index,
            )
        )

    text = " ".join(unit.text for unit in resolved).strip()
    return ConsensusResult(
        text=text,
        units=resolved,
        low_confidence_regions=_low_confidence_regions(resolved),
        k=len(items),
        families=families,
        alpha_high=alpha_high,
        alpha_low=alpha_low,
    )
