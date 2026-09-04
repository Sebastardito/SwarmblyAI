"""The V0 sweep: coherence tax as a function of ``rho`` and ``N``.

The question V0 exists to answer::

    How much output quality is lost by fragmenting and reassembling,
    as a function of how much context travels with each fragment?

and the headline number it produces::

    coherence_tax = (monolithic_score - fragmented_score) / monolithic_score

measured separately on two instruments (the BooookScore-style taxonomy and the
entity grid), for every cell of the ``rho x N`` grid, for every prompt
category.

Go / no-go
----------
The master document's continuation criterion: **there must exist a ``rho`` at
which coherence degradation is <5% relative to monolithic generation, in at
least one task category.** :func:`summarize` evaluates exactly that and returns
a verdict. With ``MockBackend`` the verdict is meaningless as evidence -- see
the warning in :mod:`swarmbly_v0.backends` -- but the machinery that computes it
is the machinery a real run will use unchanged.
"""

from __future__ import annotations

from functools import lru_cache

import csv
import json
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .assembler import boundary_windows, select_then_splice
from .backends import Backend, Embedder, HashEmbedder, get_backend, get_embedder, replica_backends
from .consensus import (
    ConsensusResult,
    DEFAULT_ACCEPT,
    DEFAULT_ALPHA_HIGH,
    DEFAULT_ALPHA_LOW,
    LABELS,
    Replica,
    consensus,
    segment_units,
)
from .composition_trace import build_trace, render_trace
from .constraints import asserts_an_aggregate, check_numeric_fidelity, is_source_table_row
from .editor import EditorReport, edit_assembled
from .stats import cluster_bootstrap
from .grading import _optional_score, grade_units
from .metrics import (
    ERROR_CLASSES,
    TauCalibration,
    calibrate_tau,
    entity_grid_coherence,
    quality_judge,
    redundancy,
    redundancy_between,
    seam_error_taxonomy,
)
from .packing import (PacketInvariantError, assert_packet_invariants,
                      build_monolithic_prompt, build_packets, packing_floor,
                      task_budget_floors as _task_budget_floors,
                      task_budget_weights as _task_budget_weights)
from .planner import (BASELINE_FORMAT_DIRECTIVE, carry_values, requested_paragraphs,
                      global_contract, plan as build_plan, split_enumerated,
                      summarize_fragment)
from .router import DEFAULT_THRESHOLD, evaluate_router, is_decomposable
from .schema import Contract, Fragment, Plan
from .textutil import count_tokens, split_sentences

__all__ = [
    "PromptSpec",
    "SweepConfig",
    "load_prompts",
    "DEFAULT_PROMPTS_PATH",
    "run_monolithic",
    "run_fragmented",
    "run_sweep",
    "write_csv",
    "write_unit_csv",
    "read_unit_rows",
    "agreement_quality_correlation",
    "agreement_truth_calibration",
    "summarize",
    "make_calibration_pairs",
    "CSV_COLUMNS",
    "UNIT_CSV_COLUMNS",
    "UNIT_CSV_NAME",
    "TRUTH_CSV_NAME",
    "TRACE_NAME",
    "write_traces",
    "TRUTH_CSV_COLUMNS",
    "write_truth_csv",
    "AGREEMENT_BINS",
    "ASSEMBLER_ENFORCED",
    "fill_constraint_columns",
    "composition_criterion",
    "COMPOSITION_THRESHOLD_POINTS",
    "MIN_CLUSTERS_FOR_A_VERDICT",
    "falsifiable_go_no_go",
    "paired_absolute_effect",
    "is_reachable",
    "publishable",
]

DEFAULT_PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "prompts.json"

ASSEMBLER_ENFORCED: frozenset[str] = frozenset({
    "paragraph_count",
    "words_per_paragraph",
})
"""Constraint kinds the ASSEMBLER satisfies for the fragmented arm.

`select_then_splice` is handed `paragraph_join=requested_paragraphs(prompt)` and
deterministically buckets the pieces into exactly that many paragraphs;
`run_monolithic` is a bare generate with no post-processing. So on every prompt
that names a paragraph count these two checks are a guaranteed pass for one arm
and something the other has to earn from the model -- two of seven checks on the
table corpus. Where a prompt describes its structure without naming a count the
bias inverts: the pieces are spliced into one paragraph and the fragmented arm
fails by construction.

Excluded from `mean_constraint_score_comparable`, which is the figure to read
across arms. `mean_constraint_score` keeps every check so the record stays
comparable with what was published."""


def fill_constraint_columns(row: dict[str, Any], trace: Any) -> dict[str, Any]:
    """Put one composition's constraint score into the row, per prompt.

    Until this existed the constraint score lived only inside ``_trace`` and was
    reported as a **mean over a condition** by :func:`_composition_summary`. A
    mean over a condition cannot be paired, cannot be clustered by prompt and
    cannot carry an interval, so the strongest measurement this project has --
    monolithic 1.000 against fragmented 0.864 on prose composition, counted from
    the text with no judge in the loop -- had no apparatus behind it. The
    coherence tax had one; the better instrument did not.

    Four columns. ``constraint_score`` keeps every check so the record stays
    comparable with what was published; ``constraint_score_comparable`` drops
    :data:`ASSEMBLER_ENFORCED` and is the only one that may appear in a
    cross-arm figure. ``n_constraints_checked`` travels with them because a
    score of 1.000 over two checks and over nine are different facts, and a
    reader cannot tell them apart from the score.

    Blank rather than zero when a prompt is not a composition: a row with no
    constraints has no score, and a zero would read as "every check failed".
    """
    report = getattr(trace, "report", None)
    if report is None:
        row["constraint_score"] = ""
        row["constraint_score_comparable"] = ""
        row["n_constraints_checked"] = ""
        return row
    raw = report.score
    comparable = report.score_excluding(ASSEMBLER_ENFORCED)
    row["constraint_score"] = round(float(raw), 6) if raw is not None else ""
    row["constraint_score_comparable"] = (
        round(float(comparable), 6) if comparable is not None else "")
    row["n_constraints_checked"] = len(getattr(report, "results", ()) or ())
    return row


def is_reachable(row: Mapping[str, Any]) -> bool:
    """Did this cell's rho target sit at or above its own honest packing floor?

    A row is a *measurement of rho* only if rho could vary. Below the floor,
    ``build_packet`` sets ``budget = max(mandatory_tokens, ...)`` and every packet
    collapses to its bare task, so a cell at rho=1.0 and a cell at rho=1.25
    produce byte-identical output and the axis the figure is plotted against
    never moved.

    A row with no ``rho_reachable`` column is treated as reachable: CSVs written
    before the column existed must not be silently emptied by this guard. That is
    a deliberate asymmetry -- it fails open on old data and closed on new.

    ``plan_refused`` is the second reason a row is not a measurement, added 4
    September 2026 with the fused segmenter repair. When a prompt states its
    questions apart from its material and the link between them is not
    recoverable, ``plan`` returns a SINGLE task rather than mis-packing it (see
    :func:`~swarmbly_v0.planner.references_are_recoverable`). Such a row is
    labelled ``fragmented`` and holds the whole prompt in one packet, so its
    coherence tax is near zero -- it would enter a cross-arm figure as evidence
    that fragmentation is cheap, on a prompt that was never fragmented. That is
    the wrong direction, and it is the direction all twelve instrument defects
    in ``REVISION_2026-08-12.md`` leaned.
    """
    return _flag(row, "rho_reachable") and not _flag(row, "plan_refused",
                                                      default=False)


def _flag(row: Mapping[str, Any], column: str, default: bool = True) -> bool:
    """One column read as a boolean, tolerant of a CSV round trip.

    ``default`` is what a MISSING column means, and the two callers need
    opposite answers. ``rho_reachable`` fails open, so a CSV written before the
    column existed is not silently emptied. ``plan_refused`` also fails open --
    default ``False`` means "not refused" -- for the same reason.
    """
    value = row.get(column, default)
    if isinstance(value, bool):
        return value
    if value in ("", None):
        return default
    return str(value).strip().lower() in ("true", "1", "yes")


def publishable(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The rows a figure may be computed from, and the single place that decides.

    Until this existed, ``rho_reachable`` was written to every row and read by
    exactly ONE function in the whole analysis -- ``fragment_size_curve``, which
    used it to pick a slice and then fell back to the full set when no reachable
    slice existed. ``summarize``, ``falsifiable_go_no_go``,
    ``paired_absolute_effect``, ``flag_effect``, ``discrete_calibration``,
    ``go_no_go`` and everything in ``report.py`` ignored it.

    That is the shape of the V0 failure, exactly. On V0's corpus at N=4 the
    honest floor was 1.85 to 2.35 while the sweep ran rho 1.0 to 2.0, so nearly
    every fragmented cell was below floor; the rows were written with
    ``rho_reachable: False``, no gate read that field, and a coherence-tax curve
    was published against an axis that had never moved. The flag was not missing.
    Nothing consulted it.

    Dropping the rows rather than annotating them is the point. A note beside a
    printed number is the shape of failure this project has already had four
    times -- the number gets quoted and the note does not travel with it.
    """
    return [r for r in rows if is_reachable(r)]


SATURATION_LIMIT = 0.90
"""Acceptance rate above which a judge is reported as saturated, not measured.

Ninety percent, not ninety-nine, because the point is not to catch a degenerate
judge but a useless one: at 93.3 % on 14 August the correlation was already
uninterpretable, and nobody said so for three more runs."""

RHO_TOLERANCE = 0.05
"""How far achieved rho may sit from its target before the run is refused.

Five percent is loose enough to absorb atomic-block granularity -- a packet
cannot be sliced finer than its contract header -- and tight enough to have
caught the 11.7 % drift that four consecutive runs carried as a warning nobody
acted on."""

CSV_COLUMNS: list[str] = [
    "prompt_id",
    "category",
    "expected_decomposable",
    "router_decomposable",
    "router_score",
    "condition",
    "backend",
    "seed",
    "n_tasks",
    "n_levels",
    "sequential_plan",
    "rho_target",
    "rho_achieved",
    "rho_floor",
    "rho_reachable",
    "plan_refused",
    "tau_sem",
    "k",
    "n_families",
    "consensus_used",
    "mean_agreement",
    "frac_high",
    "frac_medium",
    "frac_low",
    "n_low_conf_regions",
    "booook_like_score",
    "booook_comparable",
    "seam_error_rate",
    "entity_grid",
    "judge_score",
    "redundancy_self",
    "redundancy_between",
    "n_sentences",
    "n_seams",
    "n_bridges",
    "mean_seam_similarity",
    "input_tokens",
    "output_tokens",
    "coherence_tax_booook",
    "coherence_tax_booook_full",
    "seam_error_rate_delta",
    "coherence_tax_entity_grid",
    "quality_tax_judge",
    "baseline_booook",
    "baseline_booook_comparable",
    "baseline_entity_grid",
    "baseline_judge",
    "constraint_score",
    "constraint_score_comparable",
    "n_constraints_checked",
    "baseline_constraint_score",
    "baseline_constraint_score_comparable",
    "typed_carry",
    "editor_applied",
    "editor_reason",
    "editor_score_before",
    "editor_score_after",
    "editor_gain",
    "editor_input_tokens",
    "editor_output_tokens",
    "editor_calls",
] + [f"err_{cls}" for cls in ERROR_CLASSES]

UNIT_CSV_NAME = "agreement_units.csv"

TRACE_NAME = "composition_traces.md"
"""Human-readable construction record for the composition prompts.

Written only when the corpus has constraint sets. It is the artefact a reader
opens: the generated text, which micro-task wrote each sentence, the seams and
their similarities, and any sentence written twice -- with the tasks that wrote
it. A score says whether the text passed; this says how it was built.
"""

TRUTH_CSV_NAME = "ground_truth_items.csv"
"""Per-item sidecar for the V3c ground-truth calibration.

Written only when the corpus carries answer keys, so a coherence-tax run does
not gain an empty file. One row per *item occurrence*, each carrying the
agreement of the unit it appeared in -- items are the observations, agreement is
the predictor.
"""

TRUTH_CSV_COLUMNS: tuple[str, ...] = (
    "prompt_id", "category", "level", "condition", "typed_carry", "rho_target", "n_tasks", "k", "task_id",
    "unit_index", "item_id", "label", "agreement", "judge_score", "accepted",
    "mode", "expected", "given", "correct", "graded", "unknown_item", "echoed", "claim",
)
"""Sidecar written next to ``results.csv`` holding one row per consensus unit.

The sweep CSV is one row per *condition*; the agreement-vs-quality calibration
needs one row per *unit*, which is a different grain and does not belong in the
same table. Keeping it as a tidy long-format sidecar (the same pattern
``run_metadata.json`` already uses) avoids packing a histogram into a cell and
keeps both files readable on their own.
"""

UNIT_CSV_COLUMNS: list[str] = [
    "prompt_id",
    "typed_carry",
    "category",
    "condition",
    "rho_target",
    "n_tasks",
    "k",
    "task_id",
    "unit_index",
    "label",
    "agreement",
    "judge_score",
    "accepted",
]

AGREEMENT_BINS: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0001)
"""Bin edges for the agreement-vs-acceptability curve (last edge is inclusive)."""


@dataclass(frozen=True)
class PromptSpec:
    """One labelled prompt from the corpus."""

    prompt_id: str
    category: str
    expected_decomposable: bool
    text: str
    key: Mapping[str, Any] | None = None
    numeric_facts: Mapping[str, Any] | None = None
    """Figures a grounded summary may legitimately state.

    Present on the grounded-prose prompts. Each consensus unit is a sentence
    with an agreement score; its figures either come from the enclosed table, or
    are an aggregate of it, or were invented. That pairs a predictor with spread
    against a verdict with spread, which no earlier corpus managed at once.
    """
    constraints: Sequence[Mapping[str, Any]] | None = None
    """Mechanical checks for a composition prompt, graded by :mod:`swarmbly_v0.constraints`.

    Present instead of ``key`` on the composition prompts: prose has no answer
    key, but it has facts -- paragraph count, words per paragraph, required and
    forbidden terms, and above all repetition, which is what assembly from
    fragments produces and monolithic generation almost never does.
    """
    """Answer key, present only in the ground-truth corpus.

    When this is set the sweep grades units against it (see
    :mod:`swarmbly_v0.grading`) *in addition to* judging them, so one run yields
    both the judge-based calibration and the ground-truth one. That is
    deliberate: the difference between the two numbers is the measurement of how
    much the peer-class judge was distorting the V3c result.
    """

    split: str = ""
    """``"dev"``, ``"final"``, or empty for a corpus that declares no split.

    Carried on the spec rather than left in the JSON because a split that only
    exists in a file is a note, not a control. Every threshold this project has
    used -- ``tau_sem`` most visibly, but also the go/no-go threshold, the
    agreement bin edges and the flagging rate -- was fitted on the same data it
    then evaluated. Reading the field here lets the runner refuse to evaluate the
    final half while anything is still being chosen.

    Empty is not "dev". A corpus with no split is run whole, as before; only a
    corpus that declares one can be filtered by one.
    """

    @property
    def has_ground_truth(self) -> bool:
        return bool(self.key)

    @property
    def is_composition(self) -> bool:
        return bool(self.constraints)

    @property
    def is_grounded(self) -> bool:
        return bool(self.numeric_facts)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptSpec":
        return cls(
            prompt_id=str(data["id"]),
            category=str(data["category"]),
            expected_decomposable=bool(data["expected_decomposable"]),
            text=str(data["prompt"]).strip(),
            key=data.get("key") or None,
            constraints=data.get("constraints") or None,
            numeric_facts=data.get("numeric_facts") or None,
            split=str(data.get("split") or ""),
        )


@dataclass
class SweepConfig:
    """Everything that defines a reproducible sweep."""

    rhos: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0)
    ns: tuple[int, ...] = (2, 4, 8)
    carries: tuple[bool, ...] = (False,)
    """Whether a predecessor's labelled values travel verbatim, swept as a condition.

    The dependency axis. With a prose summary the value a successor needs is
    paraphrased and rationed; with a typed carry it is four tokens that cannot be
    truncated away. Swept rather than switched on, so every typed cell has an
    untyped twin at the same prompt, N and k.
    """
    editors: tuple[bool, ...] = (False,)
    """Whether the post-processing editor runs, swept as a condition of its own.

    A third arm rather than a flag, because the only interesting question about
    the editor is comparative: the same prompt, the same N, the same k, assembled
    the same way, differing only in whether one pass was made over the finished
    answer. Sweeping it means every editor row has an unedited twin.
    """
    ks: tuple[int, ...] = (1,)
    """Replica counts for **micro-level** assembly, swept alongside rho and N.

    ``k = 1`` is the macro-only condition and reproduces the pre-consensus
    pipeline exactly: one generation per micro-task, no alignment, no agreement
    map. ``k > 1`` dispatches ``k`` complete replicas of *the same* micro-task
    to nodes of different families and resolves them by consensus. The two
    levels are orthogonal -- ``rho`` controls how much context each fragment
    carries, ``k`` controls how many times each fragment is attempted -- which
    is why they are swept as a grid rather than traded off.
    """
    seed: int = 0
    backend_name: str = "mock"
    embedder_name: str = "hash"
    n_candidates: int = 2
    beta: float = 0.5
    router_threshold: float = DEFAULT_THRESHOLD
    tau_sem: float | None = None  # None => calibrate from the corpus
    alpha_high: float = DEFAULT_ALPHA_HIGH
    alpha_low: float = DEFAULT_ALPHA_LOW
    """Consensus routing thresholds. **Provisional placeholders.**

    They are exposed here for the same reason ``tau_sem`` is: so that a run
    records which value it used and a calibrated value can replace the default
    without touching the pipeline. See
    :func:`swarmbly_v0.metrics.calibrate_alpha`.
    """
    accept_threshold: float = DEFAULT_ACCEPT
    """Judge score at or above which a unit counts as acceptable. Provisional."""
    max_prompts: int | None = None
    answer_tokens: int = 420
    """Answer budget shared by both conditions.

    Both the monolithic baseline and the sum of the fragments target this many
    tokens, so the two conditions are compared at equal output length. Length
    must be held fixed: every sentence is an opportunity for a detected error,
    so a baseline that is three times longer than the fragmented condition
    would lose on the taxonomy for reasons that have nothing to do with
    fragmentation.
    """


def load_prompts(path: str | Path | None = None,
                 split: str | None = None) -> list[PromptSpec]:
    """Load the labelled prompt corpus (defaults to the bundled ``prompts/``).

    Args:
        path: Corpus file. A dict payload's ``prompts`` list, or a bare list.
        split: ``"dev"`` or ``"final"`` to load only that half of a corpus that
            declares one. ``None`` loads everything, which is the behaviour for
            every corpus that predates the split.

    Raises:
        ValueError: If a split is requested and no prompt carries it. Returning
            an empty list would let a calibration run on nothing and report its
            thresholds as if they had been fitted -- the failure mode the split
            exists to prevent, arriving through the mechanism meant to prevent
            it.
    """
    target = Path(path) if path is not None else DEFAULT_PROMPTS_PATH
    with open(target, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    entries = payload["prompts"] if isinstance(payload, dict) else payload
    specs = [PromptSpec.from_dict(entry) for entry in entries]
    if split is None:
        return specs
    chosen = [s for s in specs if s.split == split]
    if not chosen:
        declared = sorted({s.split for s in specs if s.split}) or ["(none)"]
        raise ValueError(
            f"no prompt in {target} carries split={split!r}; the corpus declares "
            f"{declared}. Refusing to run a calibration on an empty corpus.")
    return chosen


# --------------------------------------------------------------------------
# Conditions
# --------------------------------------------------------------------------


def _base_row(spec: PromptSpec, config: SweepConfig, backend: Backend) -> dict[str, Any]:
    decision = is_decomposable(spec.text, config.router_threshold)
    return {
        "prompt_id": spec.prompt_id,
        "category": spec.category,
        "expected_decomposable": spec.expected_decomposable,
        "router_decomposable": decision.decomposable,
        "router_score": round(decision.score, 4),
        "backend": getattr(backend, "name", "unknown"),
        "seed": config.seed,
    }


@lru_cache(maxsize=256)
def _expected_from_prompt(text: str, canonical: tuple[str, ...]) -> tuple[str, ...]:
    """Entities a correct answer must mention, derived from the PROMPT alone.

    The partition must not change the standard. Segmenting the prompt into one
    task and reading its expected entities gives the same answer whatever N the
    run is sweeping, which is the property the plan-derived set lacked.
    """
    from .planner import expected_entities_for
    return tuple(dict.fromkeys(list(expected_entities_for(text)) + list(canonical)))


def prompt_expected_entities(spec: "PromptSpec", contract: Contract,
                             backend: Backend) -> list[str]:
    """The arm-independent expected-entity set for one prompt.

    Both arms are handed this. ``backend`` is accepted for symmetry with the
    other per-prompt helpers and is unused: deriving the standard from a model
    would make it a function of which model happened to answer.
    """
    return list(_expected_from_prompt(spec.text, tuple(contract.canonical_entities)))


def _fill_metric_row(row: dict[str, Any], text: str, plan: Plan | None,
                     contract: Contract, embedder: Embedder,
                     offsets: Sequence[int] | None = None,
                     fragments: Sequence[str] | None = None,
                     expected_entities: Sequence[str] | None = None) -> dict[str, Any]:
    """Populate every coherence/quality column for one produced answer.

    ``expected_entities`` is passed explicitly and identically for both arms.
    Left to default, the omission detector takes its standard from the plan, and
    the plan is a function of N -- which made the baseline's standard smaller
    than the fragmented arm's and made the fragmented arm's grow with the
    partition. See :func:`swarmbly_v0.metrics.seam_error_taxonomy`.
    """
    taxonomy = seam_error_taxonomy(text, plan, offsets, contract,
                                   expected_entities=expected_entities)
    row["booook_like_score"] = round(taxonomy.booook_like_score, 6)
    # The arm-comparable score and the seam cost, side by side. The headline tax
    # is computed on the comparable one because the baseline cannot incur a seam
    # error however bad it is; the seam rate is the cost specific to assembly and
    # belongs in its own column rather than inside that ratio.
    row["booook_comparable"] = round(taxonomy.comparable_score, 6)
    row["seam_error_rate"] = round(taxonomy.seam_error_rate, 6)
    row["entity_grid"] = round(entity_grid_coherence(text), 6)
    row["judge_score"] = round(quality_judge(text, contract, embedder), 6)
    row["redundancy_self"] = round(float(redundancy(text)), 6)
    row["redundancy_between"] = round(
        float(redundancy_between(list(fragments))) if fragments else 0.0, 6
    )
    row["n_sentences"] = taxonomy.n_sentences
    row["output_tokens"] = count_tokens(text)
    for cls in ERROR_CLASSES:
        row[f"err_{cls}"] = taxonomy.counts.get(cls, 0)
    return row


def _consensus_columns(
    k: int,
    nodes: Sequence[Any],
    results: Sequence[tuple[str, ConsensusResult]],
) -> dict[str, Any]:
    """Aggregate the per-task confidence maps into one row's worth of columns.

    Everything is averaged over **units**, not over tasks, so a task that
    produced ten units weighs ten times a task that produced one. That is the
    right grain: the confidence map is per unit, and a task-weighted mean would
    let a one-sentence fragment cancel a ten-sentence one.
    """
    families = {getattr(node, "family", "") or f"node{i}" for i, node in enumerate(nodes)}
    if k <= 1 or not results:
        return {
            "k": k,
            "n_families": len(families),
            "consensus_used": False,
            "mean_agreement": "",
            "frac_high": "",
            "frac_medium": "",
            "frac_low": "",
            "n_low_conf_regions": "",
        }

    units = [unit for _, result in results for unit in result.units]
    n_units = len(units)
    counts = {label: sum(1 for u in units if u.label == label) for label in LABELS}
    # Units with no agreement are skipped rather than counted as zero. The k<=1
    # guard above already keeps them out of this branch; the filter is here so
    # that a future path reaching it cannot reintroduce a mean pulled toward
    # zero by units that were never measured. See ``_MonolithicUnit``.
    scored = [float(u.agreement) for u in units if u.agreement is not None]
    mean_agreement = (sum(scored) / len(scored)) if scored else 0.0
    return {
        "k": k,
        "n_families": len({f for _, result in results for f in result.families} or families),
        "consensus_used": True,
        "mean_agreement": round(mean_agreement, 6),
        "frac_high": round(counts["HIGH"] / n_units, 6) if n_units else 0.0,
        "frac_medium": round(counts["MEDIUM"] / n_units, 6) if n_units else 0.0,
        "frac_low": round(counts["LOW"] / n_units, 6) if n_units else 0.0,
        "n_low_conf_regions": sum(len(r.low_confidence_regions) for _, r in results),
    }


def _unit_records(
    spec: PromptSpec,
    row: dict[str, Any],
    results: Sequence[tuple[str, ConsensusResult]],
) -> list[dict[str, Any]]:
    """One long-format record per consensus unit: agreement against acceptability.

    This is the raw material of the headline calibration number. Each record
    pairs an agreement score, computed with no reference to quality, with a
    judge verdict, computed with no reference to agreement. Whether those two
    move together is the question; assuming they do is the error.
    """
    records: list[dict[str, Any]] = []
    for task_id, result in results:
        for index, unit in enumerate(result.units):
            records.append({
                "prompt_id": spec.prompt_id,
                "typed_carry": row.get("typed_carry", ""),
                "category": spec.category,
                "condition": row.get("condition", "fragmented"),
                "rho_target": row.get("rho_target", ""),
                "n_tasks": row.get("n_tasks", ""),
                "k": result.k,
                "task_id": task_id,
                "unit_index": index,
                "label": unit.label,
                "agreement": round(unit.agreement, 6),
                "judge_score": round(unit.judge_score, 6),
                "accepted": bool(unit.accepted),
            })
    return records


@dataclass(frozen=True)
class _MonolithicUnit:
    """One sentence of a single-replica reply, shaped like a consensus unit.

    ``agreement`` is ``None``, and the previous value -- 0.0, with a comment
    claiming it "stays out of every calibration by construction" -- is the
    defect this class is now the record of. Nothing filtered on it. 0.0 is a
    legal agreement score, so single-replica units entered the calibration as
    the *least confident* items in the dataset.

    In the run of 26 August that was 8 984 rows, 45 % of the graded mass, all
    pinned at 0.0. It produced two headline numbers, both false: mean agreement
    read 0.392 for aggregate claims and 0.391 for local ones -- two populations
    whose accuracy differs by 37 points reading the same value to three
    decimals, which is a constant announcing itself -- and the local AUC came
    out at 0.477, below chance. That below-chance figure was not a failed
    calibration either: the tied-at-zero group is 95.8 % correct against 92.2 %
    for the k=3 group, so a block of correct items pinned at the bottom of the
    agreement scale dragged the statistic under 0.5. The same pooling artefact
    as the other four, on a variable introduced by the fix that created these
    rows.

    Restricted to k=3, the same run gives 0.813 and 0.736 -- V5's 0.836 and
    0.699, replicated. What did not replicate is the aggregate AUC, and that is
    a real finding rather than an artefact: see ``docs/RESULTS_V6.md``.

    What a single-replica unit contributes is the *accuracy* denominator -- the
    number that separates "assembly broke this" from "the model could never do
    it". It contributes nothing about agreement, and now says so.
    """

    index: int
    text: str
    label: str = ""
    agreement: float | None = None
    judge_score: float | None = None
    accepted: bool = True


@dataclass(frozen=True)
class _MonolithicConsensus:
    """A one-replica stand-in for ConsensusResult, so the baseline and the
    fragmented arms are scored by exactly the same function."""

    units: Sequence[_MonolithicUnit]
    k: int = 1


def _numeric_records(
    spec: PromptSpec,
    row: Mapping[str, Any],
    results: Sequence[tuple[str, "ConsensusResult"]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Grade each consensus unit of a grounded summary for numeric fidelity.

    One record per unit, carrying that unit's agreement next to whether its
    figures came from the data. A unit with no figure is recorded with
    ``correct`` None and counted: it is neither right nor wrong on this measure,
    and folding it into either verdict would move the accuracy toward whichever
    was chosen.
    """
    allowed = [float(v) for v in (spec.numeric_facts or {}).get("allowed", [])]
    records: list[dict[str, Any]] = []
    n_units = n_graded = n_correct = n_no_figures = n_table_rows = 0

    for task_id, result in results:
        for index, unit in enumerate(result.units):
            n_units += 1
            # A reproduced table row is not prose and its figures are trivially
            # faithful; grading it here would name the defect wrongly and inflate
            # the denominator with units that cannot discriminate.
            copied = is_source_table_row(unit.text)
            verdict = None if copied else check_numeric_fidelity(unit.text, allowed)
            if copied:
                n_table_rows += 1
            elif verdict is None:
                n_no_figures += 1
            else:
                n_graded += 1
                n_correct += int(verdict)
            records.append({
                "prompt_id": spec.prompt_id, "category": spec.category, "level": 3,
                "condition": row.get("condition", "fragmented"),
                "typed_carry": row.get("typed_carry", ""),
                "rho_target": row.get("rho_target", ""), "n_tasks": row.get("n_tasks", ""),
                "k": result.k, "task_id": task_id, "unit_index": index,
                "item_id": "", "label": unit.label,
                "agreement": _optional_score(unit, "agreement"),
                "judge_score": _optional_score(unit, "judge_score"),
                "accepted": bool(unit.accepted), "mode": "numeric_fidelity",
                "expected": "figures from the table or an aggregate of it",
                "given": unit.text[:200], "correct": verdict,
                "graded": verdict is not None, "unknown_item": False,
                "echoed": copied,
                "claim": "aggregate" if asserts_an_aggregate(unit.text) else "local",
            })

    return records, {
        "units_total": n_units, "units_with_no_label": 0, "items_seen": n_units,
        "items_graded": n_graded, "items_correct": n_correct,
        "items_unintelligible": n_no_figures, "items_echoed": n_table_rows,
        "items_unknown_id": 0,
        "accuracy": round(n_correct / n_graded, 6) if n_graded else None,
    }


_TASK_ITEM_RE = re.compile(r"(?:^|\s)[\[(](\d{1,3})[\])]", re.MULTILINE)
r"""An item label in a task's text -- **bracketed only**.

The bracket is not optional and the reason is a defect this regex had on its
first outing. Written as ``[\[(]?(\d{1,3})[\]).:]\s+`` it also matched a bare
``NN.``, and a chain step whose text ends "...to the weekly figure from step 3."
therefore claimed item 03 as well as its own 04. At N=4 that credited a successor
with its predecessor's item -- reintroducing exactly the inflation the scope
filter exists to remove, in the arm built to measure the carry.

Every corpus writes its items as ``[NN]`` and its prose references as "step 3",
so requiring the bracket separates the two cleanly. Caught by
``tests/test_instrument.py`` on the first run of the fault-injection suite, which
is the argument for that file existing."""


def task_item_scope(plan: Any) -> dict[str, set[str]]:
    """Which item ids each task was actually asked for.

    Without this the grader credits a fragment for every item it names, and the
    typed carry hands a successor its predecessors' answers formatted exactly
    like answer lines -- ``[01]=480 [02]=428 [03]=107 [04]=257``. A fragment
    responsible for items 5 to 8 that restates its inputs is then graded on eight
    items and scores eight, four of them free and correct by construction because
    a carried value *is* the answer. Measured: 8 records and 8 correct where the
    key holds 4 for that packet, against 5 and 5 for the untyped arm.

    That inflates ``carry_effect.accuracy_delta`` -- the headline the carry arm
    exists to produce -- in the carry's favour regardless of whether the carry
    changed any reasoning. It is the "379 items against a key of 150" artifact
    returning in a form the earlier gate does not catch, and it is only visible
    at all because the scope is recoverable from the task text.

    Returns an empty mapping when no task names an item, which is every prose
    corpus, so the caller can filter unconditionally.
    """
    scope: dict[str, set[str]] = {}
    for task in getattr(plan, "tasks", []) or []:
        text = getattr(task, "instruction", "") or ""
        found = {m.group(1).zfill(2) for m in _TASK_ITEM_RE.finditer(text)}
        if found:
            scope[str(task.task_id)] = found
    return scope


def _truth_records(
    spec: PromptSpec,
    row: Mapping[str, Any],
    results: Sequence[tuple[str, "ConsensusResult"]],
    scope: Mapping[str, set[str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Grade consensus units against the prompt's answer key.

    Returns ``(records, report)``. The report carries the denominators -- how
    many units held no parsable item label, how many answers were
    unintelligible -- without which the accuracy in the records cannot be read
    honestly. Empty for a prompt with no key, which is every prompt in the
    coherence-tax corpus.
    """
    if spec.is_grounded:
        return _numeric_records(spec, row, results)
    if not spec.has_ground_truth:
        return [], {}

    records: list[dict[str, Any]] = []
    totals = {"units_total": 0, "units_with_no_label": 0, "items_seen": 0,
              "items_graded": 0, "items_correct": 0, "items_unintelligible": 0,
              "items_echoed": 0, "items_unknown_id": 0}
    for task_id, result in results:
        graded, report = grade_units(result.units, spec.key or {})
        allowed = (scope or {}).get(str(task_id))
        if allowed is not None:
            graded = [rec for rec in graded
                      if str(rec.get("item_id", "")).zfill(2) in allowed]
        for rec in graded:
            entry = (spec.key or {}).get(str(rec.get("item_id", "")), {})
            records.append({
                "prompt_id": spec.prompt_id,
                "category": spec.category,
                "level": entry.get("level", "") if isinstance(entry, dict) else "",
                "condition": row.get("condition", "fragmented"),
                "typed_carry": row.get("typed_carry", ""),
                "rho_target": row.get("rho_target", ""),
                "n_tasks": row.get("n_tasks", ""),
                "k": result.k,
                "task_id": task_id,
                **rec,
            })
        # The unit-level counters come from the report, which is about UNITS and
        # is unaffected by which items were in scope.
        d = report.as_dict()
        for field_name in ("units_total", "units_with_no_label"):
            totals[field_name] += int(d.get(field_name) or 0)

        # The ITEM counters must come from the filtered records, not from the
        # report. `report` is computed by grade_units BEFORE the scope filter
        # runs, so it counts every item the fragment named -- including the ones
        # it was never asked for.
        #
        # That is exactly what task_item_scope exists to remove. The typed carry
        # hands a successor its predecessors' answers formatted as answer lines,
        # `[01]=480 [02]=428`, and a fragment that restates them scored those
        # items for free: one enumerated corpus reported 379 graded items against
        # a key holding 150. The filter fixed the records and left the report
        # alone, so one run emitted two different accuracies from the same units
        # and the published `grading` block carried the inflated one.
        #
        # The bias is one-sided -- a restated answer is correct by construction --
        # it grows with N, and it is larger in the typed-carry arm than in its
        # control, which is to say it points the same way as the headline that
        # arm exists to produce. The monolithic baseline has no scope and is
        # unaffected, so the arm comparison was skewed too.
        for rec in graded:
            totals["items_seen"] += 1
            if rec.get("graded"):
                totals["items_graded"] += 1
                totals["items_correct"] += int(bool(rec.get("correct")))
            elif rec.get("correct") is None:
                totals["items_unintelligible"] += 1
            totals["items_echoed"] += int(bool(rec.get("echoed")))
            totals["items_unknown_id"] += int(bool(rec.get("unknown_item")))

    totals["accuracy"] = (
        round(totals["items_correct"] / totals["items_graded"], 6)
        if totals["items_graded"] else None
    )
    return records, totals


def run_monolithic(
    spec: PromptSpec,
    backend: Backend,
    embedder: Embedder,
    config: SweepConfig,
    contract: Contract | None = None,
) -> dict[str, Any]:
    """The mandatory baseline: one packet, one generation, no assembly.

    Everything the fragmented condition is measured against comes from here,
    so it uses the same contract, the same target length and the same metric
    code path -- only the fragmentation is removed.
    """
    gamma = contract or global_contract(spec.text, backend)
    prompt = build_monolithic_prompt(gamma, spec.text)
    # Hold the answer format equal across conditions. Only the partition is the
    # independent variable; the shape the answer is asked for is not, and when it
    # differed the baseline answered in prose, the grader required a bare value,
    # and the control scored zero against a fragmented condition scoring 66 %.
    if spec.has_ground_truth and split_enumerated(spec.text):
        prompt = f"{prompt}\n\n{BASELINE_FORMAT_DIRECTIVE}"
    text = backend.generate(prompt, max_tokens=gamma.target_length_tokens)

    row = _base_row(spec, config, backend)
    row.update({
        "condition": "monolithic",
        "typed_carry": "",
        "n_tasks": 1,
        "n_levels": 1,
        "sequential_plan": False,
        "rho_target": 1.0,
        "rho_achieved": round(count_tokens(prompt) / max(gamma.prompt_tokens, 1), 6),
        "rho_floor": 1.0,
        "rho_reachable": True,
        "tau_sem": "",
        # The baseline is deliberately single-replica: it is the denominator of
        # every coherence-tax number in the run, so it must vary with nothing.
        "k": 1,
        "n_families": 1,
        "consensus_used": False,
        "mean_agreement": "",
        "frac_high": "",
        "frac_medium": "",
        "frac_low": "",
        "n_low_conf_regions": "",
        "n_seams": 0,
        "n_bridges": 0,
        "mean_seam_similarity": "",
        "input_tokens": count_tokens(prompt),
        "coherence_tax_booook": 0.0,
        "coherence_tax_entity_grid": 0.0,
        "quality_tax_judge": 0.0,
    })
    _fill_metric_row(row, text, None, gamma, embedder,
                     expected_entities=prompt_expected_entities(spec, gamma, backend))

    # Grade the baseline too, when there is a key. Without this the run cannot
    # separate "a 3B model cannot do this task" from "fragmenting it destroyed
    # the task", and after the 24 August run -- one correct answer in
    # sixty-four on two-step arithmetic -- that is the more interesting of the
    # two questions. The baseline is a single reply, so its units carry no
    # agreement; the records are excluded from the calibration by construction
    # and counted as such.
    if spec.is_composition:
        row["_trace"] = build_trace(spec.prompt_id, "monolithic", text, spec.constraints or [])
        fill_constraint_columns(row, row["_trace"])
    else:
        fill_constraint_columns(row, None)

    if spec.is_grounded:
        # Grounded prose was graded in the fragmented arms only, because the gate
        # here asked for a key and a grounded prompt carries allowed figures
        # instead. So the one corpus built to make correctness vary had no
        # control: its 27.3 % on 24 August could not be told apart from a 2B
        # model simply being unable to summarise a table without inventing a
        # number. The baseline is scored on the same units, by the same code.
        baseline_units = [
            _MonolithicUnit(index, sentence)
            for index, sentence in enumerate(
                s.strip() for s in split_sentences(text) if s.strip())
        ]
        records, report = _numeric_records(
            spec, {"condition": "monolithic", "rho_target": 1.0, "n_tasks": 1},
            [("monolithic", _MonolithicConsensus(baseline_units))])
        row["_truth_records"] = records
        row["_truth_report"] = report
    elif spec.has_ground_truth:
        units = segment_units(text, "line")
        graded, report = grade_units(units, spec.key or {})
        row["_truth_records"] = [{
            "prompt_id": spec.prompt_id, "category": spec.category,
            "level": ((spec.key or {}).get(str(rec.get("item_id", "")), {}) or {}).get("level", ""),
            "condition": "monolithic", "typed_carry": "", "rho_target": 1.0,
            "n_tasks": 1, "k": 1, "task_id": "monolithic", **rec,
        } for rec in graded]
        row["_truth_report"] = report.as_dict()

    # Retained for tau calibration; dropped by write_csv (not in CSV_COLUMNS).
    row["_text"] = text
    return row


def run_fragmented(
    spec: PromptSpec,
    backend: Backend,
    embedder: Embedder,
    config: SweepConfig,
    rho_target: float,
    n_tasks: int,
    tau_sem: float,
    baseline: dict[str, Any] | None = None,
    contract: Contract | None = None,
    k: int = 1,
    use_editor: bool = False,
    typed_carry: bool = False,
) -> dict[str, Any]:
    """One cell of the sweep: plan, pack at ``rho_target``, generate, assemble.

    Both levels of assembly run here, in the order the architecture requires:

    * **Micro first.** When ``k > 1``, each micro-task is dispatched ``k`` times
      to nodes of different model families and the replicas are resolved by
      :func:`swarmbly_v0.consensus.consensus` into one fragment plus a confidence
      map. Nothing is split to make the replicas -- each is a complete answer to
      the whole micro-task.
    * **Macro second.** The resolved fragments are spliced by
      :func:`swarmbly_v0.assembler.select_then_splice`.

    At ``k = 1`` the micro level is skipped entirely and the behaviour is
    identical to the pre-consensus pipeline, which is what makes ``k`` a clean
    controlled variable rather than a change of code path for every run.

    Generation walks the DAG **level by level**, because a task's packet can
    only carry summaries of predecessors that have actually been produced.
    That is also why ``rho`` is not free: the summaries are the tokens.
    """
    gamma = contract or global_contract(spec.text, backend)

    # A prompt that demands "exactly two paragraphs" has stated the shape of its
    # own answer. Planning three fragments for it guarantees a structural failure
    # the context budget cannot repair, so the stated count wins over the sweep's
    # N for composition prompts and the fragments are joined by paragraph breaks
    # rather than spaces.
    # N is the independent variable of the sweep and must reach the planner
    # intact. The requested paragraph count is a property of the *answer*, not of
    # the partition, and conflating them froze N at the prompt's paragraph count
    # -- the sweep asked for 2, 4, 8, 16 and every cell came back at 6.
    wanted_paragraphs = requested_paragraphs(spec.text) if spec.is_composition else None
    # A composition's own format block IS its contract; only an answer sheet's
    # postamble is boilerplate that may be replaced by the compressed directive.
    plan = build_plan(spec.text, backend, n_tasks=n_tasks, contract=gamma,
                      answer_sheet=spec.has_ground_truth)
    # The planner may REFUSE to fragment. It does so when the prompt states its
    # questions apart from its material and the link between the two cannot be
    # recovered -- see `planner.references_are_recoverable`. The alternative,
    # measured on 4 September, is one packet holding four questions and no data
    # while three hold the data and are asked nothing.
    #
    # A refused row is labelled `fragmented` and holds the whole prompt in one
    # packet, so its coherence tax is near zero. Left in a cross-arm figure it
    # would read as evidence that fragmentation is cheap, on a prompt that was
    # never fragmented -- the wrong direction, and the direction all twelve
    # instrument defects leaned. `is_reachable` drops it, at the same
    # chokepoint as a below-floor row.
    plan_refused = bool(n_tasks > 1 and len(plan.tasks) < n_tasks)

    per_task_target = max(24, round(gamma.target_length_tokens / max(len(plan.tasks), 1)))
    packing_contract = replace(gamma, target_length_tokens=per_task_target)

    k = max(1, int(k))
    nodes = replica_backends(backend, k) if k > 1 else [backend]

    summaries: dict[str, str] = {}
    fragments: list[Fragment] = []
    packet_tokens_total = 0
    order_index = {tid: i for i, tid in enumerate(plan.topological_order())}
    consensus_results: list[tuple[str, ConsensusResult]] = []
    # Grading and consensus are different questions and need different inputs.
    # `consensus_results` is what the agreement sidecar is *about*, so a k=1 unit
    # -- which agrees with nothing and carries no confidence band -- must stay out
    # of it or it arrives with a blank label. `single_results` carries the same
    # units to the grader, which only needs the text and the item label.
    single_results: list[tuple[str, Any]] = []

    # The budget is global and consumed across levels, not restored at each one.
    #
    # This loop used to call build_packets once per topological level with the
    # FULL budget every time, while dispatching only that level's packets. On a
    # plan of seven sections plus one integration node the integration node was
    # therefore budgeted twice, and on the second pass its `desired` had grown --
    # seven predecessor summaries now existed for it to want -- so it took a
    # larger share of the slack than the first pass had reserved. Achieved rho
    # came out at 3.90 against a target of 3.5 in four consecutive runs, and
    # nothing but a rho_fidelity warning ever said so.
    # Each level receives its FAIR SHARE of what is left, not all of it. Handing
    # a level the whole remaining budget is the same error in the other
    # direction: a first level of one task would spend everything and starve the
    # rest.
    # The allocation is computed ONCE, up front, and does not depend on the
    # order levels happen to run in: every task gets its floor -- its own block
    # plus one contract header -- and the slack above that is divided in
    # proportion to what each task would consume unrationed.
    #
    # A purely proportional split does not work, and the way it fails is quiet.
    # On `bulk_extraction_invoices` at rho 1.25, N=4, the global floor is 1.163
    # so the cell is reachable; but proportionally the first level of three tasks
    # drew 155 tokens against its own mandatory 157, so all three collapsed to
    # bare task blocks with no contract header at all. Reachable in aggregate,
    # unreachable per level.
    total_budget = rho_target * max(count_tokens(spec.text), 1)
    weights = _task_budget_weights(packing_contract, plan)
    floors = _task_budget_floors(packing_contract, plan)
    total_floor = sum(floors.values())
    total_weight = sum(weights.values()) or 1.0
    global_slack = max(0.0, total_budget - total_floor)

    for level in plan.topological_levels():
        level_ids = [str(t) for t in level]
        share = (sum(floors.get(t, 0.0) for t in level_ids)
                 + global_slack * sum(weights.get(t, 1.0) for t in level_ids) / total_weight)
        packing = build_packets(
            packing_contract, plan, rho_target, summaries,
            budget_tokens=share, only_tasks=level_ids)
        # Refuse before spending tokens, not after. Contract present, carry
        # delivered where the task consumes one; rho is checked once at the end
        # over the whole dispatched set, because a single level's share is not
        # the run's budget.
        assert_packet_invariants(
            packing.packets, plan, packing_contract,
            rho_target=0.0, prompt=spec.text, summaries=summaries,
            reachable=packing.reachable)
        by_task = {p.task_id: p for p in packing.packets}
        for task_id in level:
            packet = by_task[task_id]
            # rho stays the *contextual* redundancy ratio: tokens per distinct
            # packet, not per dispatch. Replica redundancy is a second,
            # orthogonal cost reported by k and by input_tokens below. Folding
            # k into rho would make the two indistinguishable in the results.
            packet_tokens_total += packet.token_count
            if k > 1:
                # n_candidates is deliberately not applied here: at the micro
                # level the k replicas *are* the candidate set, and consensus is
                # the selection mechanism. Generating variants per replica as
                # well would confound sampling diversity with family diversity.
                replicas = [
                    Replica(
                        replica_id=f"{task_id}:r{i}",
                        text=node.generate(packet.text, max_tokens=per_task_target, variant=0),
                        family=getattr(node, "family", "") or f"node{i}",
                        model=getattr(node, "model", ""),
                    )
                    for i, node in enumerate(nodes)
                ]
                result = consensus(
                    replicas, gamma, embedder, backend,
                    config.alpha_high, config.alpha_low,
                    accept_threshold=config.accept_threshold,
                    # An answer sheet is segmented by line, not by sentence. The
                    # run of 24 August lost 73 % of its control category because
                    # a reply of "1. Osaka" splits at the full stop into "1." and
                    # "Osaka": a label with no answer, then an answer with no
                    # label. One line is one answer, so the line is the unit.
                    granularity="line" if spec.has_ground_truth else "sentence",
                )
                consensus_results.append((task_id, result))
                candidates = [result.text] if result.text.strip() else [replicas[0].text]
            else:
                candidates = [
                    backend.generate(packet.text, max_tokens=per_task_target, variant=v)
                    for v in range(max(1, config.n_candidates))
                ]
                # k=1 has no consensus, and until now it also produced no
                # per-item records at all -- so the fragmented arm was graded
                # only at k=3 while the monolithic baseline is a single
                # generation at k=1. Every accuracy comparison in the run was
                # therefore fragmentation *plus consensus* against monolithic,
                # with the two axes inseparable, and the coherence tax headline
                # (taken from k=1) came from the half of the grid the accuracy
                # did not. A single generation is segmented and graded the same
                # way the baseline is; agreement is 0.0 because one reply agrees
                # with nothing, which keeps it out of every calibration by
                # construction exactly as the baseline's records are.
                units = segment_units(
                    candidates[0], "line" if spec.has_ground_truth else "sentence")
                single_results.append((task_id, _MonolithicConsensus([
                    _MonolithicUnit(index=i, text=getattr(u, "text", str(u)),
                                    label=getattr(u, "label", ""))
                    for i, u in enumerate(units)
                ])))
            fragments.append(
                Fragment(task_id=task_id, candidates=candidates,
                         order=order_index.get(task_id, len(fragments)),
                         packet_tokens=packet.token_count)
            )
            summaries[task_id] = summarize_fragment(candidates[0], typed=typed_carry)

    final_packing = build_packets(packing_contract, plan, rho_target, summaries)
    rho_achieved = packet_tokens_total / max(count_tokens(spec.text), 1)
    # The budget check, on the whole dispatched set. Only meaningful when the
    # target was reachable at all: a target below the floor cannot be hit, and
    # `rho_reachable` already records that as a property of the cell.
    # The floor computed WITH the summaries, which is the truthful one. A
    # mandatory carry is added to the floor rather than funded from slack -- a
    # packet that cannot state the value its task consumes is unanswerable, and
    # answerability outranks the budget. So a chain whose carries exceed the
    # target overshoots BY DESIGN, and that is a property of the cell, not a
    # violation. `packing_floor` has always accepted summaries for exactly this;
    # the check has to use it, or it refuses a run for doing the right thing.
    # A REFUSED plan cannot honour rho either, and for a reason that is not a
    # violation: one packet holding the whole prompt has rho near 1 whatever the
    # target says. Raising here would turn a deliberate refusal to fragment into
    # a crash, and an operator would read the traceback as a harness fault
    # rather than as the planner declining a prompt it cannot partition. The row
    # is already marked `plan_refused` and dropped by `is_reachable`, which is
    # the honest handling: not a measurement, not an error.
    truthful_floor = packing_floor(packing_contract, plan, summaries)
    if not plan_refused and rho_target >= truthful_floor and rho_target > 0:
        deviation = (rho_achieved - rho_target) / rho_target
        if abs(deviation) > RHO_TOLERANCE:
            raise PacketInvariantError(
                f"{spec.prompt_id} at N={len(plan.tasks)}: achieved rho "
                f"{rho_achieved:.3f} against a target of {rho_target:.3f} "
                f"({deviation:+.1%}, tolerance {RHO_TOLERANCE:.0%}). rho is the "
                f"independent variable; this cell would not measure what its "
                f"label says, and four consecutive runs completed with exactly "
                f"this drift because it was only a warning.")

    assembly = select_then_splice(
        fragments, gamma, backend, tau_sem, plan=plan, embedder=embedder,
        paragraph_join=wanted_paragraphs or False,
    )

    # -- the post-processing pass, before anything is measured ---------------
    # The editor must run here rather than after the row is filled, because the
    # whole question it answers is what the *delivered* answer looks like. An
    # edited answer measured with the unedited answer's numbers would be the
    # nicest-looking bug in the file.
    assembled_text = assembly.text
    editor_report = None
    if use_editor and not spec.constraints:
        # The arm was requested and there is nothing mechanically checkable to
        # act on -- a dependency chain has an answer key, not constraints. The
        # pair still exists and still shows zero effect, so it is labelled rather
        # than left blank: "not applicable" and "ran and did nothing" are
        # different facts and the reasons histogram has to keep them apart.
        editor_report = EditorReport(
            text=assembled_text, applied=False,
            reason="no constraints on this prompt")
    elif use_editor:
        editor_report = edit_assembled(
            assembled_text,
            spec.constraints,
            backend,
            objective=gamma.objective,
            numeric_allowed=[float(v) for v in (spec.numeric_facts or {}).get("allowed", [])],
            max_tokens=gamma.target_length_tokens,
        )
        assembled_text = editor_report.text

    row = _base_row(spec, config, backend)
    row.update({
        "condition": "fragmented+editor" if use_editor else "fragmented",
        "typed_carry": bool(typed_carry),
        "n_tasks": len(plan.tasks),
        "n_levels": len(plan.topological_levels()),
        "sequential_plan": plan.sequential,
        # True when the planner refused to fragment: see above, and
        # `is_reachable`, which drops such a row from every figure.
        "plan_refused": plan_refused,
        "rho_target": rho_target,
        "rho_achieved": round(rho_achieved, 6),
        # The floor computed WITH the summaries. The optimistic floor -- taken
        # before generation, when no carry exists yet -- let a cell announce
        # rho_reachable=true and then overshoot, which is what packing_floor's
        # own docstring warns about.
        "rho_floor": round(truthful_floor, 6),
        "rho_reachable": bool(rho_target >= truthful_floor),
        "tau_sem": round(tau_sem, 6),
        "n_seams": len(assembly.seams),
        "n_bridges": assembly.n_bridges,
        "mean_seam_similarity": round(assembly.mean_seam_similarity, 6),
        # Dispatched tokens, not distinct packet tokens: k replicas of a packet
        # really are k packets on the wire.
        "input_tokens": packet_tokens_total * k,
    })
    row.update(_consensus_columns(k, nodes, consensus_results))
    row.update(editor_report.as_dict() if editor_report else _EMPTY_EDITOR_COLUMNS)
    selected_texts = [assembly.selected[f.task_id] for f in fragments]
    _fill_metric_row(row, assembled_text, plan, gamma, embedder,
                     assembly.fragment_sentence_offsets, selected_texts,
                     expected_entities=prompt_expected_entities(spec, gamma, backend))
    if spec.is_composition:
        # N and the carry arm belong in the label. Without them the traces of a
        # run that sweeps N carry two sections per prompt with identical
        # headings, and any tool re-reading them has to infer the cell from file
        # order -- which is exactly the kind of implicit join that goes wrong
        # silently. scripts/rescore.py verifies its join against results.csv for
        # this reason; the label makes the check unnecessary for future runs.
        label = (f"fragmented N={n_tasks} k={k}"
                 + (" +carry" if typed_carry else "")
                 + (" +editor" if use_editor else ""))
        row["_trace"] = build_trace(
            spec.prompt_id, label, assembled_text, spec.constraints or [],
            # Sentence offsets describe the *assembled* text. An editor that
            # merged paragraphs has invalidated them, so provenance is dropped
            # rather than reported wrongly -- a trace that misattributes a
            # sentence is worse than a trace that admits it cannot attribute it.
            order=None if (editor_report and editor_report.applied) else assembly.order,
            offsets=None if (editor_report and editor_report.applied)
            else assembly.fragment_sentence_offsets,
            seams=assembly.seams,
        )
        fill_constraint_columns(row, row["_trace"])
    else:
        fill_constraint_columns(row, None)

    # The arm's own output, recoverable from the row, exactly as `run_monolithic`
    # has always kept it.
    #
    # It was missing here, and the asymmetry is the kind this project keeps
    # withdrawing results for: the monolithic arm's text could be re-read from a
    # completed row and the fragmented arm's could not. On a composition corpus
    # `_trace` carried it, which hid the gap -- and `_trace` exists only when the
    # prompt has constraints, so on every answer-key or fact-graph corpus the
    # fragmented output was unrecoverable. Any INDEPENDENT scorer -- which is the
    # entire purpose of benchmark_v7 and of ADR-001 -- could therefore see one
    # arm and not the other, and would have scored the fragmented arm as having
    # produced nothing at all.
    #
    # Dropped by write_csv, like `_text` on the baseline: not in CSV_COLUMNS.
    row["_text"] = assembled_text
    row["_unit_records"] = _unit_records(spec, row, consensus_results)
    truth_records, truth_report = _truth_records(
        spec, row, consensus_results or single_results, scope=task_item_scope(plan))
    if truth_records or truth_report:
        row["_truth_records"] = truth_records
        row["_truth_report"] = truth_report

    if baseline:
        # The headline. Computed on the arm-comparable score: the baseline has no
        # seams and so cannot incur missing_transition or a seam-anchored
        # dangling_reference, and the number of seams is N-1, so including those
        # classes charged the fragmented arm more the more it was fragmented. On
        # the table run of 26 August that alone accounted for 5.7 points at N=2
        # and 10.1 at N=8.
        row["coherence_tax_booook"] = _relative_tax(
            baseline.get("booook_comparable", baseline["booook_like_score"]),
            row["booook_comparable"])
        # The old figure, kept so every run stays comparable with the record.
        row["coherence_tax_booook_full"] = _relative_tax(
            baseline["booook_like_score"], row["booook_like_score"])
        row["seam_error_rate_delta"] = round(
            float(row["seam_error_rate"])
            - float(baseline.get("seam_error_rate", 0.0)), 6)
        row["coherence_tax_entity_grid"] = _relative_tax(
            baseline["entity_grid"], row["entity_grid"])
        row["quality_tax_judge"] = _relative_tax(
            baseline["judge_score"], row["judge_score"])
        # The denominators travel with the ratios. A tax without its baseline
        # cannot be checked for the instability MIN_BASELINE documents.
        row["baseline_booook"] = round(float(baseline["booook_like_score"]), 6)
        row["baseline_booook_comparable"] = round(
            float(baseline.get("booook_comparable", baseline["booook_like_score"])), 6)
        row["baseline_entity_grid"] = round(float(baseline["entity_grid"]), 6)
        row["baseline_judge"] = round(float(baseline["judge_score"]), 6)
        # The constraint score's denominator, for the same reason and one
        # instrument later. Without it the strongest figure this project has --
        # a mechanical count, no judge, monolithic 1.000 against fragmented
        # 0.864 -- could only be reported as two means over two conditions.
        # Two means cannot be paired, and unpaired is how the coherence tax
        # spent four runs being sensitive to prompt difficulty rather than to
        # fragmentation. `constraint_score_comparable` is the cross-arm figure;
        # the raw one is carried so the record stays readable.
        for src, dest in (("constraint_score", "baseline_constraint_score"),
                          ("constraint_score_comparable",
                           "baseline_constraint_score_comparable")):
            value = baseline.get(src)
            row[dest] = (round(float(value), 6)
                         if isinstance(value, (int, float)) else "")
    else:
        for field_name in ("coherence_tax_booook", "coherence_tax_booook_full",
                           "seam_error_rate_delta", "coherence_tax_entity_grid",
                           "quality_tax_judge", "baseline_booook",
                           "baseline_booook_comparable", "baseline_entity_grid",
                           "baseline_judge", "baseline_constraint_score",
                           "baseline_constraint_score_comparable"):
            row[field_name] = ""
    return row


_EMPTY_EDITOR_COLUMNS: dict[str, Any] = {
    "editor_applied": "", "editor_reason": "", "editor_score_before": "",
    "editor_score_after": "", "editor_gain": "", "editor_violations_before": "",
    "editor_violations_after": "", "editor_input_tokens": "",
    "editor_output_tokens": "", "editor_calls": "",
}
"""Blank, not zero. A row where the editor did not run has no editor cost; a
zero would read as "it ran and cost nothing", which is a different fact."""


MIN_BASELINE: float = 0.15
"""Denominator floor below which a *relative* tax stops being a statistic.

The headline number is a ratio, ``(baseline - fragmented) / baseline``, and its
denominator is a coherence score that is legitimately allowed to be small. The
entity grid in particular returns near zero for a short answer with few repeated
entities, and at ``baseline = 0.05`` an absolute difference of 0.09 becomes a
*-180 %* "tax" -- a number that says almost nothing about the architecture and
everything about the denominator.

Cells below this floor are therefore excluded from the aggregate means and
**counted in the output** rather than dropped quietly, and the mean absolute
difference is reported alongside every ratio because it is stable regardless of
the denominator. The per-cell ratio itself is never clipped: clipping would bias
the headline, which is the opposite failure.
"""


def _relative_tax(baseline: float, fragmented: float) -> float:
    """Relative degradation ``(baseline - fragmented) / baseline``.

    Negative values mean fragmentation *helped* on that instrument, which does
    happen and must not be clipped away -- clipping would bias the headline.

    The value is unstable for small ``baseline``; :data:`MIN_BASELINE` and the
    ``*_unstable_cells`` counters in :func:`summarize` are how that instability
    is made visible instead of being averaged into the headline.
    """
    if not baseline:
        return 0.0
    return round((baseline - fragmented) / baseline, 6)


# --------------------------------------------------------------------------
# tau_sem calibration set
# --------------------------------------------------------------------------


def make_calibration_pairs(
    monolithic_texts: Sequence[str],
    window_tokens: int = 40,
    max_per_doc: int = 6,
) -> list[tuple[str, str, bool]]:
    """Build labelled ``(left, right, is_seam)`` pairs for tau calibration.

    * **Negative (``is_seam=False``)**: two adjacent windows *inside* one
      continuously generated answer. Whatever happens at that junction is by
      construction not a seam -- no assembly occurred there.
    * **Positive (``is_seam=True``)**: the tail of one answer against the head
      of a *different* answer. That is a genuine discontinuity.

    The set is balanced by truncation so the F-beta optimum is not an artefact
    of class imbalance.
    """
    negatives: list[tuple[str, str, bool]] = []
    positives: list[tuple[str, str, bool]] = []

    for text in monolithic_texts:
        sentences = split_sentences(text)
        if len(sentences) < 4:
            continue
        for cut in range(1, min(len(sentences) - 1, max_per_doc + 1)):
            left = " ".join(sentences[:cut])
            right = " ".join(sentences[cut:])
            lw, rw = boundary_windows(left, right, window_tokens)
            if lw.strip() and rw.strip():
                negatives.append((lw, rw, False))

    for i, text in enumerate(monolithic_texts):
        for j, other in enumerate(monolithic_texts):
            if i == j:
                continue
            lw, rw = boundary_windows(text, other, window_tokens)
            if lw.strip() and rw.strip():
                positives.append((lw, rw, True))

    size = min(len(negatives), len(positives))
    if size == 0:
        return negatives + positives
    return negatives[:size] + positives[:size]


# --------------------------------------------------------------------------
# Sweep driver
# --------------------------------------------------------------------------


def _answer_budget(spec: PromptSpec, default_tokens: int) -> int:
    """How long the answer is allowed to be, read from what the prompt demands.

    A flat budget cannot serve a corpus whose prompts ask for different lengths.
    The V5 long_prose briefs demand eight paragraphs of 70 to 130 words -- 560 to
    1040 words -- against a default of 420 tokens, and ``count_tokens`` is
    word-equivalent. So the baseline was cut off at 420 and each fragment got
    ``max(24, 420/N)``: 53 tokens at N=8, for a paragraph required to be at least
    70 words. ``paragraph_count`` and ``words_per_paragraph`` were unsatisfiable
    in *every* arm, and the two conditions were compared on a metric neither
    could move.

    When the prompt states its own shape, that is the budget, with a margin for
    the model to land inside the band rather than exactly on its ceiling.
    """
    paragraphs = words = 0
    for spec_item in spec.constraints or []:
        kind = str(spec_item.get("kind", ""))
        if kind == "paragraph_count":
            paragraphs = max(paragraphs, int(spec_item.get("count", 0)))
        elif kind == "words_per_paragraph":
            words = max(words, int(spec_item.get("max", 0)))
    if paragraphs and words:
        return max(default_tokens, int(paragraphs * words * 1.2))
    return default_tokens


def run_sweep(
    prompts: Sequence[PromptSpec],
    config: SweepConfig | None = None,
    backend: Backend | None = None,
    embedder: Embedder | None = None,
    progress: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the full ``rho x N`` sweep and return ``(rows, run_metadata)``.

    The monolithic baseline is generated once per prompt and reused for every
    cell, so the tax numbers in a row all share a denominator.
    """
    cfg = config or SweepConfig()
    used_prompts = list(prompts)[: cfg.max_prompts] if cfg.max_prompts else list(prompts)
    engine = backend or get_backend(cfg.backend_name, seed=cfg.seed)
    embed = embedder or get_embedder(cfg.embedder_name)

    contracts = {
        spec.prompt_id: global_contract(
            spec.text, engine,
            target_length_tokens=_answer_budget(spec, cfg.answer_tokens),
        )
        for spec in used_prompts
    }

    rows: list[dict[str, Any]] = []
    baselines: dict[str, dict[str, Any]] = {}
    for spec in used_prompts:
        baseline = run_monolithic(spec, engine, embed, cfg, contracts[spec.prompt_id])
        baselines[spec.prompt_id] = baseline
        rows.append(baseline)
        if progress:
            progress(f"baseline  {spec.prompt_id:<28} booook={baseline['booook_like_score']:.3f}")

    # -- calibrate tau_sem instead of hardcoding it ------------------------
    if cfg.tau_sem is not None:
        tau = float(cfg.tau_sem)
        calibration: TauCalibration | None = None
    else:
        texts = [str(baselines[s.prompt_id].get("_text", "")) for s in used_prompts]
        pairs = make_calibration_pairs(texts)
        calibration = calibrate_tau(pairs, embed, beta=cfg.beta)
        tau = calibration.tau
        if progress:
            progress(
                f"tau_sem calibrated to {tau:.3f} "
                f"(F{cfg.beta}={calibration.f_beta:.3f}, P={calibration.precision:.3f}, "
                f"R={calibration.recall:.3f}, n={calibration.n_pairs})"
            )

    for spec in used_prompts:
        for rho in cfg.rhos:
            for n in cfg.ns:
                for k in cfg.ks:
                    for use_editor in cfg.editors:
                      for carry in cfg.carries:
                        row = run_fragmented(
                            spec, engine, embed, cfg, rho, n, tau,
                            baseline=baselines[spec.prompt_id],
                            contract=contracts[spec.prompt_id],
                            k=k,
                            use_editor=use_editor,
                            typed_carry=carry,
                        )
                        rows.append(row)
                        if progress:
                            agreement = row.get("mean_agreement", "")
                            agreement_text = (f"agree={agreement:.3f}"
                                              if isinstance(agreement, float) else "agree=n/a")
                            edited = (" +ed" if use_editor else "    ") + ("+c" if carry else "  ")
                            progress(
                                f"sweep     {spec.prompt_id:<28} rho={rho:<5} N={n:<3} "
                                f"k={k:<3}{edited} rho_hat={row['rho_achieved']:.2f} "
                                f"tax_booook={row['coherence_tax_booook']:+.3f} {agreement_text}"
                            )

    metadata: dict[str, Any] = {
        "backend": getattr(engine, "name", "unknown"),
        "embedder": getattr(embed, "name", type(embed).__name__),
        "seed": cfg.seed,
        "rhos": list(cfg.rhos),
        "ns": list(cfg.ns),
        "ks": list(cfg.ks),
        "n_prompts": len(used_prompts),
        "n_candidates": cfg.n_candidates,
        "tau_sem": tau,
        "beta": cfg.beta,
        "alpha_high": cfg.alpha_high,
        "alpha_low": cfg.alpha_low,
        "accept_threshold": cfg.accept_threshold,
        "alphas_calibrated": False,
        "router_threshold": cfg.router_threshold,
        "tau_calibration": calibration.as_dict() if calibration else None,
        "harness_validation_only": getattr(engine, "name", "") == "mock",
        "transport": str(getattr(engine, "transport", "") or cfg.backend_name),
        "transport_retries": int(getattr(engine, "retries", 0)),
        "embeddings_degraded": bool(
            getattr(engine, "embed_degraded", "")
            or "degraded" in str(getattr(embed, "name", ""))
        ),
    }
    if metadata["embeddings_degraded"]:
        # tau calibrated on hashed vectors is a number, not a threshold. Say so
        # in the artifact rather than leaving it to be inferred from a name.
        metadata["tau_sem_warning"] = (
            "tau_sem was calibrated on hashed embeddings because the embedding "
            "route degraded; it carries no semantic meaning and MUST NOT be "
            "quoted as a calibrated threshold."
        )
    return rows, metadata


def write_csv(rows: Sequence[dict[str, Any]], path: str | Path) -> Path:
    """Write ``rows`` as a tidy CSV with the canonical column order.

    When any row carries consensus units, the per-unit sidecar
    (:data:`UNIT_CSV_NAME`) is written alongside it, so the agreement-vs-quality
    calibration survives the round trip through disk and ``report`` can render
    it from a bare CSV path.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})
    write_unit_csv(rows, target.with_name(UNIT_CSV_NAME))
    write_truth_csv(rows, target.with_name(TRUTH_CSV_NAME))
    write_traces(rows, target.with_name(TRACE_NAME))
    return target


def write_traces(rows: Sequence[dict[str, Any]], path: str | Path) -> Path | None:
    """Write the composition traces. ``None`` when the corpus has no compositions."""
    traces = [row["_trace"] for row in rows if row.get("_trace") is not None]
    if not traces:
        return None
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_trace(traces), encoding="utf-8")
    return target


def write_truth_csv(rows: Sequence[dict[str, Any]], path: str | Path) -> Path | None:
    """Write the per-item ground-truth sidecar. ``None`` when the corpus has no keys.

    This is the audit surface for the V3c calibration: every graded item with
    its expected answer, the text it was graded against, and the agreement of
    the unit it came from. The headline AUC is a summary of this file, and a
    reader who distrusts the summary can recompute it from here.
    """
    records = [record for row in rows for record in row.get("_truth_records", [])]
    if not records:
        return None
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRUTH_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({col: ("" if record.get(col) is None else record.get(col, ""))
                             for col in TRUTH_CSV_COLUMNS})
    return target


def write_unit_csv(rows: Sequence[dict[str, Any]], path: str | Path) -> Path | None:
    """Write the per-consensus-unit sidecar. Returns ``None`` when there is none."""
    records = [record for row in rows for record in row.get("_unit_records", [])]
    if not records:
        return None
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UNIT_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({col: record.get(col, "") for col in UNIT_CSV_COLUMNS})
    return target


def read_unit_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read the per-unit sidecar back, with numbers and booleans parsed."""
    target = Path(path)
    if not target.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(target, "r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            record = dict(raw)
            for key in ("agreement", "judge_score"):
                try:
                    record[key] = float(record.get(key, "") or 0.0)
                except ValueError:
                    record[key] = 0.0
            record["accepted"] = str(record.get("accepted", "")).lower() == "true"
            for key in ("k", "unit_index", "n_tasks"):
                try:
                    record[key] = int(float(record.get(key, "") or 0))
                except ValueError:
                    record[key] = 0
            out.append(record)
    return out


def _composition_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Constraint scores by condition, and the repetition count that separates them.

    ``repeated_sentences_cross_task`` is the number that matters. A sentence
    written twice by *one* worker is a model tic; the same sentence written by
    two different workers is the architecture failing to tell them about each
    other, and it is invisible to a coherence score computed on transitions
    because each copy reads perfectly well where it sits.
    """
    traces = [row["_trace"] for row in rows if row.get("_trace") is not None]
    if not traces:
        return {}

    by_condition: dict[str, list[Any]] = {}
    for trace in traces:
        by_condition.setdefault(trace.condition, []).append(trace)

    def _summarise(group: Sequence[Any]) -> dict[str, Any]:
        scored = [t.report.score for t in group if t.report.score is not None]
        cross = sum(1 for t in group for d in t.duplicated if d["cross_task"])
        # The score over the checks NEITHER arm gets for free.
        #
        # `paragraph_count` and `words_per_paragraph` are satisfied by the
        # assembler in the fragmented arm and by the model alone in the baseline:
        # `select_then_splice` is handed `paragraph_join=requested_paragraphs(...)`
        # and deterministically emits exactly that many paragraphs, while
        # `run_monolithic` is a bare generate with no post-processing at all. On
        # the table corpus that is a guaranteed pass for one arm against a
        # near-certain fail for the other, on two of seven checks -- and the sign
        # flips by corpus: where a prompt says "one paragraph to each" rather
        # than naming a count, `requested_paragraphs` returns None, the pieces
        # are spliced into a single paragraph, and the fragmented arm is
        # guaranteed to FAIL instead. Same instrument, opposite bias, decided by
        # prompt wording.
        #
        # `mean_constraint_score` is kept so the record stays comparable, and
        # `mean_constraint_score_comparable` is the one to read across arms.
        comparable = [t.report.score_excluding(ASSEMBLER_ENFORCED)
                      for t in group if t.report.score is not None]
        comparable = [s for s in comparable if s is not None]
        return {
            "n_compositions": len(group),
            "mean_constraint_score": round(sum(scored) / len(scored), 6) if scored else None,
            "mean_constraint_score_comparable": (
                round(sum(comparable) / len(comparable), 6) if comparable else None),
            "assembler_enforced_checks": sorted(ASSEMBLER_ENFORCED),
            "constraints_failed": sorted({f.constraint_id for t in group for f in t.report.failed}),
            "repeated_sentences": sum(len(t.duplicated) for t in group),
            "repeated_sentences_cross_task": cross,
            "mean_paragraphs": round(
                sum(t.report.n_paragraphs for t in group) / len(group), 3) if group else None,
        }

    return {"composition": {
        "by_condition": {cond: _summarise(group) for cond, group in sorted(by_condition.items())},
        "trace_file": TRACE_NAME,
        "note": (
            "Constraint scores are counted from the text, not judged. Compare the fragmented "
            "conditions against monolithic: a lower score under fragmentation is the cost of "
            "assembly, and repeated_sentences_cross_task localises it -- two workers writing the "
            "same sentence is the architecture failing to tell them about each other, and a "
            "transition-based coherence score cannot see it because each copy reads well in place."
        ),
    }}


def _truth_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The V3c ground-truth block, or nothing at all.

    Absent rather than empty when the corpus has no answer keys: a coherence-tax
    run should not carry a calibration section full of nulls that a reader has to
    decide how to interpret.

    Section 11.4 asks for calibration curves *per task category*, so the block
    carries one calibration per category next to the pooled one. The pooled
    number can look like a signal purely because easy categories both agree more
    and are more often right; the per-category split is what separates that
    artefact from a real effect.
    """
    records = [r for row in rows for r in row.get("_truth_records", [])]
    reports = [row.get("_truth_report") for row in rows if row.get("_truth_report")]
    if not records and not reports:
        return {}

    grading_report = {"units_total": 0, "units_with_no_label": 0, "items_seen": 0,
                      "items_graded": 0, "items_correct": 0, "items_unintelligible": 0,
                      "items_echoed": 0, "items_unknown_id": 0}
    for row in rows:
        rep = row.get("_truth_report") or {}
        for field_name in grading_report:
            grading_report[field_name] += int(rep.get(field_name) or 0)

    # The monolithic baseline is a single reply, so its units carry no agreement
    # and it contributes nothing to a calibration. It is kept out of the pooled
    # figures and reported on its own, because the comparison it enables --
    # can the model do this task at all, unfragmented? -- is what separates a
    # model failure from a fragmentation failure.
    fragmented = [r for r in records if r.get("condition") != "monolithic"]
    baseline = [r for r in records if r.get("condition") == "monolithic"]

    by_category: dict[str, list[Mapping[str, Any]]] = {}
    by_k: dict[int, list[Mapping[str, Any]]] = {}
    by_level: dict[str, list[Mapping[str, Any]]] = {}
    for rec in fragmented:
        by_category.setdefault(str(rec.get("category", "")), []).append(rec)
        by_level.setdefault(str(rec.get("level", "")), []).append(rec)
        try:
            by_k.setdefault(int(rec.get("k", 1)), []).append(rec)
        except (TypeError, ValueError):
            pass

    def _accuracy(recs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        graded = [r for r in recs if r.get("correct") is not None]
        n = len(graded)
        return {"n_items": n,
                "accuracy": round(sum(1 for r in graded if r["correct"]) / n, 6) if n else None}

    if not records:
        # The corpus had keys and nothing came back gradable. That is a result --
        # small models ignoring the output format -- and it has to be visible,
        # not an absent file the reader has to notice for themselves.
        return {"truth_calibration": {
            "pooled": agreement_truth_calibration([]),
            "by_category": {},
            "by_k": {},
            "grading": grading_report,
            "note": (
                "No item label was parsable in any unit, so nothing could be graded. This is a "
                "finding about output-format compliance, not a missing measurement: see "
                "units_with_no_label against units_total. The calibration cannot be computed and "
                "is reported as absent rather than as zero."
            ),
        }}

    pooled = agreement_truth_calibration(fragmented)
    stratified = stratified_auc(fragmented, key="category")
    pooled_auc, strat_auc = pooled.get("auc"), stratified.get("auc")
    stratified["confounded"] = (
        pooled_auc is not None and strat_auc is not None
        and abs(pooled_auc - strat_auc) > 0.05
    )
    stratified["note"] = (
        "Pairs counted within a category only. When this differs from the pooled AUC, the "
        "pooled figure is separating categories rather than right answers from wrong ones, "
        "and the stratified figure is the one that answers the V3c question."
    )
    stratified["flagging"] = stratified_flagging(fragmented, key="category")
    lifts = [
        s["lift"] for row in stratified["flagging"]
        for s in row["by_stratum"].values() if s.get("lift") is not None
    ]
    stratified["flagging_note"] = (
        "Flagging lift computed inside each category against that category's own base error "
        "rate. Read by_stratum before the pooled lift: a confidence map that earns its cost in "
        "one category out of four is a narrower claim than the pooled figure makes it look."
        + (f" Per-category lift ranges {min(lifts):.2f} to {max(lifts):.2f}." if lifts else "")
    )

    # The same discipline on the claim class, and on this corpus it is the
    # stratification that changes the answer. The run of 26 August, table
    # prompts, k=3: pooled flagging lift reads 1.05, 0.70 and 0.88 -- at or
    # below random, which reads as "the confidence map does not work". Inside
    # the aggregate class it reads 2.15, 1.75 and 1.48: flag the lowest-
    # agreement tenth and 78 % of what is flagged is an error, against a base
    # rate of 36 %.
    #
    # The cause is that the two classes sit at opposite corners. Aggregate
    # claims carry HIGH agreement (0.78) and LOW accuracy (0.64); local claims
    # carry LOW agreement (0.68) and HIGH accuracy (0.90). Pooled, the
    # high-agreement items are disproportionately the wrong ones and the
    # statistic inverts. Replicas agree readily on a total or an average because
    # those are formulaic to phrase, not because they got the arithmetic right.
    #
    # This is the sixth pooling artefact in this project and the first that ran
    # the other way: the previous five made a null look like a result, this one
    # made a result look like a null.
    stratified_claim = stratified_auc(fragmented, key="claim")
    stratified_claim["flagging"] = stratified_flagging(fragmented, key="claim")
    claim_lifts = [
        s["lift"] for row in stratified_claim["flagging"]
        for s in row["by_stratum"].values() if s.get("lift") is not None
    ]
    stratified_claim["confounded"] = (
        pooled_auc is not None and stratified_claim.get("auc") is not None
        and abs(pooled_auc - stratified_claim["auc"]) > 0.05
    )
    stratified_claim["note"] = (
        "Pairs and flags counted inside a claim class only. Read this before the pooled "
        "figures: aggregate and local claims differ in BOTH agreement and accuracy, and in "
        "opposite directions, so pooling them measures the difference between the classes "
        "rather than between right and wrong answers. When `confounded` is true the pooled "
        "AUC is not answering the confidence-map question at all."
        + (f" Per-class lift ranges {min(claim_lifts):.2f} to {max(claim_lifts):.2f}."
           if claim_lifts else "")
    )

    return {"truth_calibration": {
        "pooled": pooled,
        "discrete_calibration_by_claim": discrete_calibration(fragmented, key="claim"),
        # The declared successor hypothesis, computed for each claim class:
        # aggregate is the one under test, local is its failing control. If the
        # flag works equally in both, it is not tracking claim-specific error and
        # the result is void -- dev says local is flat (span 0.11, non-monotone).
        "flag_effect_by_claim": {
            claim: flag_effect(
                [r for r in fragmented if str(r.get("claim", "")) == claim])
            for claim in ("aggregate", "local")
            if any(str(r.get("claim", "")) == claim for r in fragmented)
        },
        "stratified_by_claim": stratified_claim,
        "stratified_by_category": stratified,
        "by_category": {cat: agreement_truth_calibration(recs)
                        for cat, recs in sorted(by_category.items())},
        "by_level": {lvl: agreement_truth_calibration(recs)
                     for lvl, recs in sorted(by_level.items())},
        "by_k": {str(k): agreement_truth_calibration(recs)
                 for k, recs in sorted(by_k.items())},
        "by_claim": {
            claim: agreement_truth_calibration(
                [r for r in fragmented if str(r.get("claim", "")) == claim])
            for claim in ("aggregate", "local")
            if any(str(r.get("claim", "")) == claim for r in fragmented)
        },
        "claim_note": (
            "Split by whether the unit asserts something requiring sight of rows the "
            "fragment may not hold. On 24 August aggregate claims were wrong 47.7% of the "
            "time against 31.7% for local ones (Fisher p = 0.014), which is the first split "
            "in this project where the two classes differ in correctness rather than only "
            "in agreement. Six calibration attempts failed because the predictor saturated; "
            "this is the other half a calibration needs, and reading it within each class "
            "rather than across the mixture is what keeps it from repeating the pooling "
            "artifact that has produced a wrong headline three times."
        ),
        "fragmentation_cost": {
            "monolithic": _accuracy(baseline),
            "fragmented": _accuracy(fragmented),
            "adjusted": standardised_cost(baseline, fragmented, key="category"),
            "by_category": {
                cat: {"monolithic": _accuracy([r for r in baseline if r.get("category") == cat]),
                      "fragmented": _accuracy(recs)}
                for cat, recs in sorted(by_category.items())},
            "note": (
                "Accuracy of the unfragmented baseline against the fragmented conditions, on the "
                "same items. This is what separates 'a 3B model cannot do this task' from "
                "'fragmenting it destroyed the task'. If the baseline is high and the fragmented "
                "arms are low, the calibration above is measuring the damage rather than the "
                "confidence map."
            ),
        },
        "grading": grading_report,
        "note": (
            "Verdicts come from prompts/ground_truth.json, not from a judge. Read auc before "
            "pearson_r when accuracy is far from 50 percent, and read flagging before either: "
            "lift near 1.0 means flagging the lowest-agreement items is no better than flagging "
            "at random, which is the result that would retire the confidence map."
        ),
    }}


def agreement_quality_correlation(
    units: Sequence[Mapping[str, Any]],
    bins: Sequence[float] = AGREEMENT_BINS,
) -> dict[str, Any]:
    """Does the agreement score predict judged acceptability?

    The headline micro-level number, and the one the whole confidence map
    stands or falls on. Agreement is cheap and needs no judge; acceptability
    needs a judge (or a human). If the two are uncorrelated, then routing on
    agreement is routing on noise and the ``HIGH`` label is a lie -- so this is
    reported rather than assumed, and it is reported even when it is bad.

    Args:
        units: Records with ``agreement`` (float) and ``accepted`` (bool).
        bins: Bin edges over ``[0, 1]`` for the binned curve.

    Returns:
        ``pearson_r`` (point-biserial, ``None`` when either variable is
        constant and the coefficient is undefined), the pooled acceptance rate,
        the unit count, and one entry per bin with its midpoint, unit count and
        acceptability rate. Bins holding no units are kept with a ``None`` rate
        rather than dropped, so a sparse region is visibly sparse.
    """
    xs = [float(u["agreement"]) for u in units if "agreement" in u]
    ys = [1.0 if u.get("accepted") else 0.0 for u in units if "agreement" in u]
    n = len(xs)

    result: dict[str, Any] = {
        "n_units": n,
        "acceptance_rate": round(sum(ys) / n, 6) if n else 0.0,
        "mean_agreement": round(sum(xs) / n, 6) if n else 0.0,
        "pearson_r": None,
        "bins": [],
    }
    if n >= 2:
        x_arr = np.asarray(xs, dtype=np.float64)
        y_arr = np.asarray(ys, dtype=np.float64)
        if x_arr.std() > 1e-12 and y_arr.std() > 1e-12:
            result["pearson_r"] = round(float(np.corrcoef(x_arr, y_arr)[0, 1]), 6)

    edges = list(bins)
    for low, high in zip(edges, edges[1:]):
        members = [(x, y) for x, y in zip(xs, ys) if low <= x < high]
        rate = (sum(y for _, y in members) / len(members)) if members else None
        result["bins"].append({
            "low": round(low, 4),
            "high": round(min(high, 1.0), 4),
            "midpoint": round((low + min(high, 1.0)) / 2, 4),
            "n_units": len(members),
            "acceptability_rate": round(rate, 6) if rate is not None else None,
        })

    # A judge that accepts (or rejects) nearly everything is not an instrument,
    # and this correlation cannot be computed from it whether or not the signal
    # exists. The record: 93.3 % acceptance on 14 August left the first V3c
    # result uninterpretable, and it has run at 100.0 % for four consecutive
    # runs since -- 1 502 units on the last one, every single one accepted.
    #
    # Reported as saturated rather than as a number. `pearson_r` is already None
    # when a variable is constant; this says WHY, so a reader does not read an
    # absent correlation as a measured null.
    rate = result["acceptance_rate"]
    saturated = n > 0 and (rate >= SATURATION_LIMIT or rate <= 1 - SATURATION_LIMIT)
    result["saturated"] = bool(saturated)
    if saturated:
        result["pearson_r"] = None
        result["note"] = (
            f"judge saturated at {rate:.1%} acceptance over {n} units. The "
            f"correlation is not computable from a verdict that does not vary, "
            f"and this is the fourth consecutive run in that state. Treat every "
            f"judge-based figure on this corpus as ABSENT, not as null. Ground "
            f"truth is unaffected and is what Section 11.4 specifies anyway."
        )
    return result


def paired_absolute_effect(
    rows: Sequence[Mapping[str, Any]],
    category: str,
    rho: float,
    n_tasks: int | None = None,
    k: int | None = None,
    score: str = "booook_comparable",
    baseline: str = "baseline_booook_comparable",
) -> dict[str, Any]:
    """The same cell, as a paired difference in raw score rather than a ratio.

    Reported **beside** :func:`falsifiable_go_no_go`, never instead of it. The
    declared criterion is a relative degradation and it stays that way, because
    changing an estimator after it returned an unwelcome answer is how a project
    talks itself out of a result.

    Why it is worth having anyway. A ratio ``(baseline - fragmented) / baseline``
    is maximally sensitive exactly where the baseline is best: at a baseline of
    1.000 a single lost sentence is the whole numerator. On the final run of
    27 August one prompt -- ``bonded``, baseline 1.000 -- contributed 1.3 of the
    3.3 points, and the cell missed its threshold on the upper bound by 1.9.
    A paired absolute difference has no denominator to be sensitive to.

    Neither is the "right" estimator in the abstract. A relative figure is what a
    threshold expressed as a percentage needs; an absolute one is what a reader
    comparing two corpora needs. **The point is that a future study declares
    which one before it runs**, and having both computed means that declaration
    can be made from evidence rather than from preference.

    Returns:
        The mean and median paired difference with prompt-clustered intervals,
        and the per-prompt pairs so a reader can see the distribution rather than
        a summary of it.
    """
    # Below-floor rows cannot enter a published figure; see `publishable`.
    rows = publishable(rows)
    cells = [r for r in rows
             if str(r.get("condition", "")).startswith("fragmented")
             and str(r.get("category")) == category
             and _close(r.get("rho_target"), rho)
             and (n_tasks is None or _same_number(r.get("n_tasks"), n_tasks))
             and (k is None or _same_number(r.get("k"), k))
             and isinstance(r.get(score), (int, float))
             and isinstance(r.get(baseline), (int, float))]

    pairs = [{"prompt_id": str(r.get("prompt_id", "")),
              "delta": float(r[baseline]) - float(r[score]),
              "baseline": float(r[baseline])}
             for r in cells]
    if not pairs:
        return {"declared_cell": {"category": category, "rho": rho,
                                  "n_tasks": n_tasks, "k": k},
                "n_observations": 0, "note": "no rows in this cell"}

    deltas = sorted(p["delta"] for p in pairs)
    mean_ci = cluster_bootstrap(
        pairs, lambda rs: sum(x["delta"] for x in rs) / len(rs) if rs else None)
    median_ci = cluster_bootstrap(
        pairs, lambda rs: float(np.median([x["delta"] for x in rs])) if rs else None)

    return {
        "declared_cell": {"category": category, "rho": rho,
                          "n_tasks": n_tasks, "k": k},
        "n_observations": len(pairs),
        "n_prompts": mean_ci.get("n_clusters"),
        "mean_delta": round(sum(deltas) / len(deltas), 6),
        "mean_ci95": mean_ci.get("ci95"),
        "median_delta": round(float(np.median(deltas)), 6),
        "median_ci95": median_ci.get("ci95"),
        "n_at_or_below_zero": sum(1 for d in deltas if d <= 0),
        "baseline_at_ceiling": sum(1 for p in pairs if p["baseline"] >= 0.999),
        "pairs": sorted(pairs, key=lambda p: p["delta"]),
        "note": (
            "A paired difference in raw score: positive means the fragmented arm "
            "scored lower. Reported beside the declared relative criterion, not "
            "in place of it. baseline_at_ceiling counts prompts whose baseline "
            "scored 1.000, where a ratio has no room and one lost sentence is the "
            "entire numerator."
        ),
    }


def _same_number(value: Any, target: int) -> bool:
    """Numeric equality for a cell filter, not string equality.

    ``str(r["n_tasks"]) == str(n_tasks)`` was the old form and it works exactly
    as long as the rows are the ones the run held in memory. Read back from
    ``results.csv`` the same field is a float, ``"2.0" != "2"``, and every cell
    filter silently matches nothing -- so a criterion re-run over a finished
    run's own artefacts reports no cells at all rather than an error. Found by
    ``scripts/reanalyse.py`` on its first use.
    """
    try:
        return float(value) == float(target)
    except (TypeError, ValueError):
        return False


def _single_replica(record: Mapping[str, Any]) -> bool:
    """True when the record came from one generation, so agreement is undefined.

    Reads ``k``. A record with no ``k`` at all is *not* treated as single: the
    item corpora predate the field and excluding them would silently empty the
    calibration. A record with an unparsable ``k`` is treated as single, because
    the safe default when the replica count is unknown is to leave it out of a
    statistic that only means something when there were several replicas.
    """
    if "k" not in record:
        return False
    try:
        return int(float(record["k"])) <= 1
    except (TypeError, ValueError):
        return True


def agreement_truth_calibration(
    records: Sequence[Mapping[str, Any]],
    bins: Sequence[float] = AGREEMENT_BINS,
    flag_rates: Sequence[float] = (0.10, 0.20, 0.30),
) -> dict[str, Any]:
    """Does agreement predict *correctness* -- the V3c question, against truth.

    :func:`agreement_quality_correlation` answers the same question against a
    judge, and in the run of 14 August 2026 the judge accepted 93.3 % of
    everything, leaving the correlation uninterpretable. This function takes
    records graded by :mod:`swarmbly_v0.grading`, where the verdict comes from
    an answer key instead of a model.

    Three statistics, because the pre-registered one is not the decisive one.

    * ``pearson_r`` -- the point-biserial correlation Section 11.4 committed to
      reporting. Reported first because it was promised first, not because it is
      the most informative.

    * ``auc`` -- the probability that a randomly chosen correct item carries
      higher agreement than a randomly chosen incorrect one, ties counted as
      half. Scale-free, insensitive to how lopsided accuracy is, and 0.5 exactly
      when agreement carries no information. This is the number to read when
      accuracy is far from 50 %, which is precisely the condition that made the
      judge-based measurement unreadable.

    * ``flagging`` -- what the confidence map is actually *for*. Flag the lowest
      ``rate`` share of items by agreement and ask how many errors that catches
      (recall) and how much of what it caught was really an error (precision).
      A confidence map that costs 17 to 20 points of quality has to earn that
      back here, in errors surfaced, not in a correlation coefficient.

    ``lift`` states the same thing as a ratio a reader can argue with: precision
    divided by the base error rate. At 1.0 the flag is picking items at random.

    Args:
        records: Graded records carrying ``agreement`` (float) and ``correct``
            (bool). Records with either missing, or with ``correct`` None
            (unintelligible answers), are excluded and counted -- an
            unintelligible answer is not evidence about agreement.
        bins: Bin edges over ``[0, 1]`` for the calibration curve.
        flag_rates: Share of items to flag, lowest agreement first.

    Returns:
        A dict with the three statistics, the denominators behind them, and the
        exclusion counts. Every rate is ``None`` rather than 0.0 when its
        denominator is empty, so an absent measurement never reads as a zero.
    """
    usable: list[tuple[float, int]] = []
    excluded_no_agreement = 0
    excluded_unintelligible = 0
    excluded_single_replica = 0

    for rec in records:
        correct = rec.get("correct")
        agreement = rec.get("agreement")
        # A single replica has nothing to agree with, so whatever sits in the
        # agreement field is not a measurement. This filter is deliberately on
        # k rather than on the value: the run of 26 August carried a 0.0
        # sentinel there, which is a legal score, and 8 984 such rows -- 45 % of
        # the graded mass -- entered the calibration as its least confident
        # items. That produced a mean agreement identical to three decimals
        # across two classes 37 accuracy points apart, and an AUC below chance.
        # Filtering on the value would have missed it; filtering on k cannot.
        #
        # Checked *before* intelligibility so that the count is complete. Tested
        # second it read 0 on a run full of single-replica rows, because those
        # rows were mostly unintelligible too and the other counter claimed them
        # first -- a diagnostic that reports zero when the thing it watches for
        # is present is worse than no diagnostic.
        if _single_replica(rec):
            excluded_single_replica += 1
            continue
        if correct is None:
            excluded_unintelligible += 1
            continue
        if agreement is None:
            excluded_no_agreement += 1
            continue
        usable.append((float(agreement), 1 if correct else 0))

    n = len(usable)
    n_correct = sum(y for _, y in usable)
    n_wrong = n - n_correct
    result: dict[str, Any] = {
        "n_items": n,
        "n_correct": n_correct,
        "n_wrong": n_wrong,
        "accuracy": round(n_correct / n, 6) if n else None,
        "mean_agreement": round(sum(x for x, _ in usable) / n, 6) if n else None,
        "excluded_unintelligible": excluded_unintelligible,
        "excluded_no_agreement": excluded_no_agreement,
        "excluded_single_replica": excluded_single_replica,
        "pearson_r": None,
        "auc": None,
        "bins": [],
        "flagging": [],
    }
    if n == 0:
        return result

    xs = np.asarray([x for x, _ in usable], dtype=np.float64)
    ys = np.asarray([y for _, y in usable], dtype=np.float64)
    if xs.std() > 1e-12 and ys.std() > 1e-12:
        result["pearson_r"] = round(float(np.corrcoef(xs, ys)[0, 1]), 6)

    # AUC by rank (Mann-Whitney U), ties at half. Undefined without both classes.
    if n_correct and n_wrong:
        order = np.argsort(xs, kind="mergesort")
        ranks = np.empty(n, dtype=np.float64)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
            i = j + 1
        rank_sum_correct = float(ranks[ys == 1].sum())
        u = rank_sum_correct - n_correct * (n_correct + 1) / 2.0
        result["auc"] = round(u / (n_correct * n_wrong), 6)

    edges = list(bins)
    for low, high in zip(edges, edges[1:]):
        members = [y for x, y in usable if low <= x < high]
        result["bins"].append({
            "low": round(low, 4),
            "high": round(min(high, 1.0), 4),
            "midpoint": round((low + min(high, 1.0)) / 2, 4),
            "n_items": len(members),
            "accuracy": round(sum(members) / len(members), 6) if members else None,
        })

    base_error = n_wrong / n
    ordered = sorted(usable, key=lambda pair: pair[0])
    for rate in flag_rates:
        cut = int(round(rate * n))
        if cut <= 0 or not n_wrong:
            result["flagging"].append({
                "flag_rate": rate, "n_flagged": cut,
                "errors_caught": None, "recall": None, "precision": None, "lift": None,
            })
            continue
        flagged = ordered[:cut]
        caught = sum(1 for _, y in flagged if y == 0)
        precision = caught / cut
        result["flagging"].append({
            "flag_rate": rate,
            "n_flagged": cut,
            "errors_caught": caught,
            "recall": round(caught / n_wrong, 6),
            "precision": round(precision, 6),
            "lift": round(precision / base_error, 6) if base_error > 0 else None,
        })

    return result


def stratified_auc(
    records: Sequence[Mapping[str, Any]],
    key: str = "category",
) -> dict[str, Any]:
    """AUC counting only pairs drawn from the *same* stratum.

    The pooled AUC answers "does higher agreement mean more likely correct?"
    across every item in the run at once. When the run mixes populations with
    different base rates *and* different agreement levels, that question has a
    cheap wrong answer available: rank the populations, not the items.

    The run of 24 August is the worked example. Grounded prose sat at mean
    agreement 0.65 with almost nothing correct; the item corpora sat at 0.95+
    with roughly two answers in three correct. Pooled, agreement separates
    correct from incorrect at AUC 0.72 -- and every bit of that separation is the
    gap *between* the two corpora. Within them, the same records give 0.49, 0.53
    and 0.66: chance, chance, and slightly better than chance.

    So this function pools the pairs, not the items: every correct/incorrect pair
    it counts comes from one stratum, and a difference between populations can no
    longer be read as a difference between right and wrong answers. Reported
    beside the pooled figure rather than instead of it, with ``confounded`` set
    when they disagree by more than 0.05 -- the reader is owed both numbers and
    the fact that they diverged.

    Returns:
        ``auc``, the ``n_pairs`` behind it, the per-stratum breakdown, and
        ``strata_dropped`` for strata holding only one class, which contribute no
        pairs and are counted so their absence is visible.
    """
    by_stratum: dict[str, list[tuple[float, int]]] = {}
    for rec in records:
        correct, agreement = rec.get("correct"), rec.get("agreement")
        if correct is None or agreement is None:
            continue
        by_stratum.setdefault(str(rec.get(key, "")), []).append(
            (float(agreement), 1 if correct else 0))

    concordant = 0.0
    total_pairs = 0
    per_stratum: dict[str, Any] = {}
    dropped: list[str] = []
    for name, pairs in sorted(by_stratum.items()):
        pos = [x for x, y in pairs if y == 1]
        neg = [x for x, y in pairs if y == 0]
        if not pos or not neg:
            dropped.append(name)
            continue
        agree = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
        n_pairs = len(pos) * len(neg)
        concordant += agree
        total_pairs += n_pairs
        per_stratum[name] = {
            "auc": round(agree / n_pairs, 6), "n_pairs": n_pairs,
            "n_correct": len(pos), "n_wrong": len(neg),
        }

    return {
        "auc": round(concordant / total_pairs, 6) if total_pairs else None,
        "n_pairs": total_pairs,
        "by_stratum": per_stratum,
        "strata_dropped": dropped,
    }


def rho_fidelity(
    rows: Sequence[Mapping[str, Any]],
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Did each cell actually run at the context budget it was asked for?

    rho is the independent variable of every fragmentation comparison, so a cell
    that overshot its target is not the cell the comparison names. Nothing
    checked this, and the table run of 26 August shows why it must: at N=8 the
    achieved rho was **3.91** against a target of 3.5 -- 11.6 % over -- while
    rho_floor was only 1.13, so the packer was not being forced up by the floor.
    The N=8 arm therefore received *more* context than N=2 and still did far
    worse, which happens to be conservative for the conclusion drawn from it, but
    the direction was luck rather than design.

    Reported per (rho_target, N) rather than pooled, because the drift is a
    function of N: at N=2 the same run sits at 3.48 against 3.5, inside a
    percent.

    Args:
        rows: Fragmented rows carrying ``rho_target`` and ``rho_achieved``.
        tolerance: Relative deviation above which a cell is flagged. 5 % is
            tight enough to catch the N=8 case and loose enough to ignore the
            rounding that packing a whole number of tokens produces.

    Returns:
        ``cells`` with the per-cell deviation, ``worst``, and ``within_tolerance``
        -- false when any cell drifted. A run with ``within_tolerance: false``
        has not measured what its axis labels say it measured, and the cells that
        drifted should be named in any write-up rather than quietly averaged in.
    """
    groups: dict[tuple[float, int], list[tuple[float, float]]] = {}
    for row in rows:
        try:
            target = float(row["rho_target"])
            achieved = float(row["rho_achieved"])
            n_tasks = int(row["n_tasks"])
        except (KeyError, TypeError, ValueError):
            continue
        if target <= 0:
            continue
        groups.setdefault((target, n_tasks), []).append((target, achieved))

    cells: list[dict[str, Any]] = []
    for (target, n_tasks), pairs in sorted(groups.items()):
        mean_achieved = sum(a for _, a in pairs) / len(pairs)
        deviation = (mean_achieved - target) / target
        cells.append({
            "rho_target": target,
            "n_tasks": n_tasks,
            "rho_achieved_mean": round(mean_achieved, 4),
            "relative_deviation": round(deviation, 4),
            "within_tolerance": abs(deviation) <= tolerance,
            "n_rows": len(pairs),
        })

    drifted = [c for c in cells if not c["within_tolerance"]]
    worst = max(cells, key=lambda c: abs(c["relative_deviation"]), default=None)
    return {
        "tolerance": tolerance,
        "cells": cells,
        "n_cells_out_of_tolerance": len(drifted),
        "worst": worst,
        "within_tolerance": not drifted,
        "note": (
            "rho is the independent variable, so a cell that did not run at its target is "
            "not the cell its label names. Deviation is reported per (rho_target, N) because "
            "it is a function of N: the table run of 26 August sat at 3.48 against 3.5 at "
            "N=2 and at 3.91 at N=8. Compare tax across N only among cells that are within "
            "tolerance, or say plainly which one was not."
        ),
    }


def stratified_flagging(
    records: Sequence[Mapping[str, Any]],
    key: str = "category",
    flag_rates: Sequence[float] = (0.10, 0.20, 0.30),
) -> list[dict[str, Any]]:
    """Flagging lift computed *inside* each category, then pooled by weight.

    The AUC was guarded against the pooling artifact before the flagging was, and
    half a guard is worse than none: on 25 August the stratified AUC came back an
    honest 0.56 while the pooled flagging beside it still advertised a lift of
    1.88 at a 10 % flag rate. Within categories that same run gives 0.63, 0.92,
    1.13 and 2.93 -- three categories at or below chance and one carrying the
    entire effect.

    So the same discipline: flag the lowest-agreement share *of each category*,
    against *that category's* base error rate, and pool the counts afterwards.
    A reader can then see whether the confidence map works generally or works in
    one place, which is a different claim and a much smaller one.
    """
    by_stratum: dict[str, list[tuple[float, int]]] = {}
    for rec in records:
        correct, agreement = rec.get("correct"), rec.get("agreement")
        if correct is None or agreement is None:
            continue
        by_stratum.setdefault(str(rec.get(key, "")), []).append(
            (float(agreement), 1 if correct else 0))

    out: list[dict[str, Any]] = []
    for rate in flag_rates:
        flagged = caught = expected = 0
        per_stratum: dict[str, Any] = {}
        for name, pairs in sorted(by_stratum.items()):
            n = len(pairs)
            n_wrong = sum(1 for _, y in pairs if y == 0)
            cut = int(round(rate * n))
            if cut <= 0 or not n_wrong:
                continue
            picked = _flag_whole_ties(pairs, cut)
            taken = len(picked)
            hits = sum(1 for _, y in picked if y == 0)
            flagged += taken
            caught += hits
            # What flagging at random inside this category would have caught.
            expected += taken * (n_wrong / n)
            per_stratum[name] = {"n_flagged": taken,
                                 "achieved_rate": round(taken / n, 6),
                                 "errors_caught": hits,
                                 "precision": round(hits / taken, 6),
                                 "lift": round((hits / taken) / (n_wrong / n), 6)}
        out.append({
            "flag_rate": rate,
            "n_flagged": flagged,
            "errors_caught": caught,
            "precision": round(caught / flagged, 6) if flagged else None,
            "lift": round(caught / expected, 6) if expected > 0 else None,
            "by_stratum": per_stratum,
        })
    return out


def _flag_whole_ties(
    pairs: Sequence[tuple[float, int]],
    cut: int,
) -> list[tuple[float, int]]:
    """Take the lowest-agreement items, never splitting a tie group.

    Agreement at k replicas takes exactly k+1 values. At k=3 that is
    ``{0, 1/3, 2/3, 1}``, and on the table run of 26 August those four values
    held 8, 82, 87 and 141 items. "Flag the lowest 20 %" then asks for 64 items
    out of a group of 82 that are *indistinguishable to the predictor*, so which
    64 depends entirely on the sort's tie order -- and two correct
    implementations disagreed by 0.6 in lift because of it.

    A flag that cannot be acted on is not a measurement. So a tie group is taken
    whole or not at all, and ``achieved_rate`` reports what fraction that came
    to. When the achieved rate is far from the requested one, the requested rate
    was not expressible on this predictor and the calibration table -- accuracy
    at each distinct value -- is the honest statistic.
    """
    ordered = sorted(pairs, key=lambda p: p[0])
    picked: list[tuple[float, int]] = []
    index = 0
    while index < len(ordered):
        value = ordered[index][0]
        group = [p for p in ordered[index:] if p[0] == value]
        # Take the group only if doing so does not overshoot further than
        # stopping short would undershoot.
        if picked and abs(len(picked) + len(group) - cut) > abs(len(picked) - cut):
            break
        picked.extend(group)
        index += len(group)
        if len(picked) >= cut:
            break
    return picked or ordered[:cut]


FLAG_CUT = 2.0 / 3.0
"""Agreement below which a claim is flagged for review.

Read as "fewer than two of three replicas agreed". Frozen on the dev half of
``prompts/tables24.json`` on 26 August, before the final half was run, and
deliberately expressed as a fraction of k rather than as a percentile: agreement
takes k+1 values, so a percentile cut lands inside a tie group the predictor
cannot resolve and its result depends on sort order."""


def flag_effect(
    records: Sequence[Mapping[str, Any]],
    cut: float = FLAG_CUT,
    cluster_key: str = "prompt_id",
    draws: int = 4000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, Any]:
    """Does flagging low-agreement claims catch errors *within* a prompt?

    The confidence map's whole proposition is per-claim triage: told which of its
    own outputs to distrust, a reviewer reads a tenth of them and catches a
    disproportionate share of the errors. The naive way to measure that is a
    lift -- precision among flagged items over the base error rate -- and on the
    dev half of the table corpus it reads **2.21**, with a prompt-clustered
    interval of [1.32, 3.83].

    That number is not trustworthy, and the reason is visible in the data: of
    eight prompts, three contributed no flagged item at all, and the three with
    the most flagged items were also the three with the most errors. A lift
    computed across prompts cannot separate "this claim is wrong" from "this
    prompt is hard" -- and only the first is worth anything, because the second
    is already available from the error rate itself.

    So the estimator is a **Mantel-Haenszel common odds ratio with the prompt as
    the stratum**, which never compares an item in one prompt against an item in
    another. On the same dev data it gives **3.47**, so the effect does survive
    removing the between-prompt component -- but its clustered interval is
    **[0.80, 10.67]**, which does not exclude "no effect". The honest reading of
    dev is a strong point estimate that eight prompts cannot establish.

    Args:
        records: Graded records carrying ``agreement``, ``correct`` and
            ``cluster_key``. Single-replica records are excluded: agreement is
            undefined for them.
        cut: Flag when ``agreement < cut``. Defaults to :data:`FLAG_CUT`.
        cluster_key: The stratum, and also what the bootstrap resamples. The
            prompt, not the item -- items from one prompt share its difficulty.
        draws: Bootstrap resamples over clusters.
        alpha: 1 - coverage.
        seed: Fixed, so a reported interval reproduces.

    Returns:
        ``odds_ratio`` with ``ci95``, the unstratified ``lift`` beside it for
        comparison, the per-stratum 2x2 tables, and
        ``n_strata_contributing`` -- the number of prompts that had at least one
        flagged item *and* at least one unflagged one. A stratum with none of
        one is uninformative and contributes zero to the estimate, so a run
        where that count is small has less evidence than its item count implies.
    """
    usable = [r for r in records
              if r.get("correct") is not None and r.get("agreement") is not None
              and not _single_replica(r)]

    def _tables(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[int, int, int, int]]:
        out: dict[str, list[int]] = {}
        for row in rows:
            flagged = float(row["agreement"]) < cut
            wrong = not bool(row["correct"])
            cell = out.setdefault(str(row.get(cluster_key, "")), [0, 0, 0, 0])
            cell[(0 if flagged else 2) + (0 if wrong else 1)] += 1
        return {name: tuple(cell) for name, cell in out.items()}

    def _mh(rows: Sequence[Mapping[str, Any]]) -> float | None:
        numerator = denominator = 0.0
        for a, b, c, d in _tables(rows).values():
            total = a + b + c + d
            if not total:
                continue
            numerator += a * d / total
            denominator += b * c / total
        # A zero denominator has two quite different causes and they must not be
        # returned as the same None. Either no stratum had both a flagged and an
        # unflagged item -- nothing is estimable -- or the flag separated errors
        # perfectly, which is an infinite odds ratio and the best possible
        # outcome. `unestimable_reason` below says which.
        return (numerator / denominator) if denominator > 0 else None

    tables = _tables(usable)
    n_flagged = sum(a + b for a, b, _, _ in tables.values())
    n_wrong = sum(a + c for a, _, c, _ in tables.values())
    contributing = sum(1 for a, b, c, d in tables.values()
                       if (a + b) > 0 and (c + d) > 0)

    base = n_wrong / len(usable) if usable else None
    flagged_wrong = sum(a for a, _, _, _ in tables.values())
    lift = ((flagged_wrong / n_flagged) / base) if n_flagged and base else None

    interval = cluster_bootstrap(usable, _mh, cluster_key=cluster_key,
                                 draws=draws, alpha=alpha, seed=seed)

    odds_ratio = _mh(usable)
    unestimable = None
    if odds_ratio is None:
        discordant = sum(1 for a, b, c, d in tables.values() if b or c)
        unestimable = ("perfect separation: every flagged item is an error and every "
                       "unflagged one is correct, so the odds ratio is unbounded above"
                       if contributing and not discordant else
                       "no stratum holds both a flagged and an unflagged item, so nothing "
                       "is estimable within prompts")

    return {
        "cut": round(cut, 6),
        "odds_ratio": round(odds_ratio, 6) if odds_ratio is not None else None,
        "unestimable_reason": unestimable,
        "ci95": interval.get("ci95"),
        "n_clusters": interval.get("n_clusters"),
        "n_strata_contributing": contributing,
        "draws_unusable": interval.get("draws_unusable"),
        "n_items": len(usable),
        "n_flagged": n_flagged,
        "n_errors": n_wrong,
        "base_error_rate": round(base, 6) if base is not None else None,
        "precision_flagged": round(flagged_wrong / n_flagged, 6) if n_flagged else None,
        "lift_unstratified": round(lift, 6) if lift is not None else None,
        "by_stratum": {name: {"flagged_wrong": a, "flagged_right": b,
                              "unflagged_wrong": c, "unflagged_right": d}
                       for name, (a, b, c, d) in sorted(tables.items())},
        "note": (
            "Mantel-Haenszel common odds ratio with the prompt as the stratum, so no item is "
            "ever compared against an item from another prompt. lift_unstratified is reported "
            "beside it and is the larger number for a reason: it borrows the between-prompt "
            "signal, and 'this prompt is hard' is not what a per-claim confidence map is for. "
            "Read n_strata_contributing before the interval -- a prompt with no flagged item, "
            "or with no unflagged one, contributes nothing at all."
        ),
    }


def discrete_calibration(
    records: Sequence[Mapping[str, Any]],
    key: str | None = None,
    max_values: int = 12,
) -> dict[str, Any]:
    """Accuracy at each distinct agreement value -- the statistic a k-replica
    predictor can actually support.

    An AUC and a percentile flag both assume the predictor is finely graded.
    Agreement is not: it is ``consistent / k``, so k=3 gives four values. On the
    table run of 26 August that table is the clearest result the project has
    produced, and both summary statistics obscured it.

    Aggregate claims, accuracy by agreement: **0.00, 0.25, 0.625, 0.75** at
    n = 2, 8, 40, 44. Monotone across 75 accuracy points -- a working confidence
    map. Local claims: 0.833, 0.946, 0.936, 0.845 -- flat, non-monotone, and
    inverted at the top. Pooled the two give 0.625, 0.878, 0.793, 0.816, which
    is neither, and it was the pooled figure that got reported.

    Args:
        records: Graded records with ``agreement`` and ``correct``.
        key: Field to stratify by -- ``"claim"`` is the one that matters here.
            ``None`` pools, which this function exists to argue against.
        max_values: Above this many distinct values the predictor is continuous
            enough that a table is not the right summary, and ``discrete`` comes
            back false.

    Returns:
        Per stratum, a list of ``{agreement, n, accuracy}`` in ascending order,
        plus ``monotone`` and the accuracy ``span`` -- the two things that decide
        whether a confidence map is worth its cost.
    """
    groups: dict[str, list[tuple[float, int]]] = {}
    for record in records:
        correct, agreement = record.get("correct"), record.get("agreement")
        if correct is None or agreement is None or _single_replica(record):
            continue
        name = str(record.get(key, "")) if key else "all"
        groups.setdefault(name, []).append((float(agreement), 1 if correct else 0))

    distinct = {value for pairs in groups.values() for value, _ in pairs}
    out: dict[str, Any] = {
        "stratified_by": key,
        "n_distinct_values": len(distinct),
        "discrete": 0 < len(distinct) <= max_values,
        "by_stratum": {},
        "note": (
            "Agreement is consistent/k, so it takes k+1 values and no more. An AUC and a "
            "percentile flag both assume a finely graded predictor; this table does not. "
            "Read `monotone` and `span`: a confidence map earns its cost by separating "
            "accuracy across its range, and a map that is monotone in one claim class and "
            "flat in the other is a much narrower claim than a single pooled number makes "
            "it look."
        ),
    }
    for name, pairs in sorted(groups.items()):
        table = []
        for value in sorted({v for v, _ in pairs}):
            bucket = [y for v, y in pairs if v == value]
            table.append({"agreement": round(value, 6), "n": len(bucket),
                          "accuracy": round(sum(bucket) / len(bucket), 6)})
        accuracies = [entry["accuracy"] for entry in table]
        out["by_stratum"][name] = {
            "points": table,
            "n": len(pairs),
            "monotone": all(a <= b for a, b in zip(accuracies, accuracies[1:])),
            "span": round(max(accuracies) - min(accuracies), 6) if accuracies else None,
        }
    return out


def standardised_cost(
    baseline: Sequence[Mapping[str, Any]],
    fragmented: Sequence[Mapping[str, Any]],
    key: str = "category",
) -> dict[str, Any]:
    """The fragmentation cost with the category mix held equal, plus its test.

    The third place the same pooling artifact turned up, and the one that was
    reporting the headline. On 25 August the raw comparison read 79.1 % against
    58.3 % -- but the baseline's graded items were 10 % grounded prose and the
    fragmented arms' were 24 %, and grounded prose is by far the hardest
    category. Part of the gap was the arms not being made of the same thing.

    Two corrections, reported side by side with the raw figure rather than
    replacing it:

    * ``standardised`` weights every category equally in both arms, which on that
      run takes the gap from 20.8 points to 15.2;
    * ``mantel_haenszel`` gives the common odds ratio across categories and its
      chi-square test, so the reader gets an effect size that never pools across
      strata at all (OR 2.29, p = 0.038 -- real, and a good deal less certain
      than the raw p = 0.003 suggested).

    A category present in only one arm contributes to neither, and is named in
    ``strata_dropped``.
    """
    def _tally(records: Sequence[Mapping[str, Any]]) -> dict[str, tuple[int, int]]:
        out: dict[str, list[int]] = {}
        for rec in records:
            if rec.get("correct") is None:
                continue
            entry = out.setdefault(str(rec.get(key, "")), [0, 0])
            entry[0] += 1 if rec["correct"] else 0
            entry[1] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}

    mono, frag = _tally(baseline), _tally(fragmented)
    shared = sorted(set(mono) & set(frag))
    dropped = sorted(set(mono) ^ set(frag))
    if not shared:
        return {"standardised": None, "mantel_haenszel": None,
                "strata_dropped": dropped, "n_strata": 0}

    mono_rate = sum(mono[s][0] / mono[s][1] for s in shared) / len(shared)
    frag_rate = sum(frag[s][0] / frag[s][1] for s in shared) / len(shared)

    num = den = observed = expected = variance = 0.0
    per_stratum: dict[str, Any] = {}
    for s in shared:
        a, n1 = mono[s]
        c, n2 = frag[s]
        b, d = n1 - a, n2 - c
        n = n1 + n2
        num += a * d / n
        den += b * c / n
        m1 = a + c
        observed += a
        expected += n1 * m1 / n
        if n > 1:
            variance += n1 * n2 * m1 * (n - m1) / (n * n * (n - 1))
        per_stratum[s] = {"monolithic": round(a / n1, 6), "fragmented": round(c / n2, 6),
                          "n_monolithic": n1, "n_fragmented": n2}

    chi_square = ((abs(observed - expected) - 0.5) ** 2 / variance) if variance > 0 else None
    p_value = math.erfc(math.sqrt(chi_square / 2)) if chi_square is not None else None

    return {
        "standardised": {
            "monolithic": round(mono_rate, 6),
            "fragmented": round(frag_rate, 6),
            "cost_points": round((mono_rate - frag_rate) * 100, 4),
        },
        "mantel_haenszel": {
            "odds_ratio": round(num / den, 6) if den > 0 else None,
            "chi_square": round(chi_square, 6) if chi_square is not None else None,
            "p_value": round(p_value, 6) if p_value is not None else None,
        },
        "by_stratum": per_stratum,
        "n_strata": len(shared),
        "strata_dropped": dropped,
        "note": (
            "The raw comparison beside this one pools arms whose category mix differs, and the "
            "hardest category is the one they differ on most. Read cost_points and the "
            "Mantel-Haenszel odds ratio -- neither ever compares an item to an item of another "
            "category. An odds ratio above 1 means the unfragmented baseline is more often right."
        ),
    }


def fragment_size_curve(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Cost as a function of how much context a fragment carries.

    The question this answers -- *what is the effective size of a semantic
    fragment?* -- is the one the project had never asked directly, and re-reading
    the V0 run says it dominates everything else measured so far: excluding a
    degenerate category and weighting categories equally, the coherence tax runs
    +6.7 % at ~133 tokens per fragment, +14.0 % at ~66, and +35.1 % at ~33,
    monotone in 7 of 8 categories. Every V3c run then fixed N at 3 or 4 and swept
    ``k`` instead, so the whole truth-calibration arc sat on one point of this
    curve without saying so.

    Two things make this function more than a groupby.

    **It reports both axes.** V0 measured coherence proxies with no answer key;
    V3c measured accuracy at a single fragment size. Neither has ever been seen
    against the other, so "the cost of fragmentation" names two unrelated
    numbers. Here they share a row.

    **It weights categories equally.** Pooling arms whose category mix differs
    has now produced a wrong headline three times in this file -- in the AUC, in
    the flagging lift, and in the fragmentation cost. The mean of per-category
    means is reported as ``tax_balanced``, and the naive pooled mean beside it,
    so a divergence between them is visible rather than latent.

    The size reported is ``prompt_tokens / n_tasks``: what one fragment's share
    of the problem actually is, which is the quantity a planner would need to
    choose N. ``suggest_n_tasks`` currently hardcodes one micro-task per 60
    canonical tokens, a constant that has never been validated against anything.
    """
    # Below-floor rows cannot enter a published figure; see `publishable`. This
    # function used to be the ONLY reader of `rho_reachable` in the whole
    # analysis, and it read it to pick a slice, then fell back to the full set
    # when no reachable slice existed:
    #
    #     slice_rho = reachable_rhos[0] if reachable_rhos else (rhos[0] ...)
    #
    # On a sweep entirely below floor -- V0's, at N=4 -- `reachable_rhos` is
    # empty and the fallback silently builds the project's declared primary
    # result out of exactly the cells the flag was raised about. Filtering first
    # means the curve is either computed from cells where rho could vary, or
    # reported as empty. There is no third answer that is worth printing.
    rows = publishable(rows)
    baselines = {str(r.get("prompt_id")): r for r in rows
                 if r.get("condition") == "monolithic"}

    # Fix every axis that is not N. The curve is this project's declared primary
    # result and it was averaging rho, k, the editor and the carry into each
    # point -- 320 cells where the grid holds 20 prompts x 2 rho x 2 k x 2 editor
    # x 2 carry x 1 N. The run script's own guidance says to compare tax across N
    # *within one rho, never across*, and `summarize` refuses to average k for
    # the same reason. A curve that pools all four is not comparable to either.
    fragmented = [r for r in rows if str(r.get("condition", "")) == "fragmented"
                  and not r.get("typed_carry")]
    # An axis absent from the rows is not filtered on: a caller passing rows
    # without rho or k means those axes do not vary, not that they are all zero.
    rhos = sorted({float(r["rho_target"]) for r in fragmented
                   if isinstance(r.get("rho_target"), (int, float))})
    ks = sorted({int(r["k"]) for r in fragmented if str(r.get("k", "")).isdigit()})

    # Prefer a rho at which *every* N is reachable. The packing floor grows with
    # N -- the preamble is paid N times -- so the lowest swept rho is the one
    # most likely to be below the floor at the finest partition, and a cell below
    # its floor overshoots rho_target. Slicing there would build the curve out of
    # cells whose actual rho rises with N, making the trend partly an artifact of
    # the very axis it holds fixed.
    def _all_reachable(rho: float) -> bool:
        cells = [r for r in fragmented if _close(r.get("rho_target"), rho)]
        return bool(cells) and all(
            str(r.get("rho_reachable", "")).lower() in ("true", "1") for r in cells)

    reachable_rhos = [rho for rho in rhos if _all_reachable(rho)]
    slice_rho = (reachable_rhos[0] if reachable_rhos else (rhos[0] if rhos else None))
    slice_k = ks[0] if ks else None
    fragmented = [
        r for r in fragmented
        if (slice_rho is None or _close(r.get("rho_target"), slice_rho))
        and (slice_k is None or str(r.get("k")) == str(slice_k))
    ]

    by_n: dict[int, list[Mapping[str, Any]]] = {}
    for row in fragmented:
        try:
            by_n.setdefault(int(row["n_tasks"]), []).append(row)
        except (KeyError, TypeError, ValueError):
            continue

    # N is capped by the number of divisible units a prompt has -- six aspects,
    # seven chain steps, twenty table rows -- so the high-N points are made of
    # fewer prompt shapes than the low-N ones. Comparing them directly is the
    # same pooling artifact that has produced a wrong headline three times in
    # this file, arriving now in the curve built to replace those headlines.
    categories_at_n = {
        n: {str(r.get("category", "")) for r in group}
        for n, group in by_n.items()
    }
    common = set.intersection(*categories_at_n.values()) if categories_at_n else set()

    points: list[dict[str, Any]] = []
    for n_tasks, group in sorted(by_n.items()):
        sizes = [
            float(baselines[str(r["prompt_id"])].get("input_tokens", 0)) / max(n_tasks, 1)
            for r in group if str(r.get("prompt_id")) in baselines
        ]
        taxes = [float(r["coherence_tax_booook"]) for r in group
                 if isinstance(r.get("coherence_tax_booook"), (int, float))]
        by_category: dict[str, list[float]] = {}
        for r in group:
            if isinstance(r.get("coherence_tax_booook"), (int, float)):
                by_category.setdefault(str(r.get("category", "")), []).append(
                    float(r["coherence_tax_booook"]))
        balanced = [sum(v) / len(v) for v in by_category.values() if v]

        graded = [rec for r in group for rec in (r.get("_truth_records") or [])
                  if rec.get("correct") is not None]
        accuracy_by_cat: dict[str, list[int]] = {}
        for rec in graded:
            accuracy_by_cat.setdefault(str(rec.get("category", "")), []).append(
                1 if rec["correct"] else 0)
        acc_balanced = [sum(v) / len(v) for v in accuracy_by_cat.values() if v]

        shared = [sum(v) / len(v) for c, v in by_category.items() if c in common and v]
        points.append({
            "n_tasks": n_tasks,
            "tokens_per_fragment": round(sum(sizes) / len(sizes), 2) if sizes else None,
            "n_cells": len(group),
            "tax_pooled": round(sum(taxes) / len(taxes), 6) if taxes else None,
            "tax_balanced": round(sum(balanced) / len(balanced), 6) if balanced else None,
            "tax_common": round(sum(shared) / len(shared), 6) if shared else None,
            # Per shape, because the claim under test is that S* is a semantic
            # unit rather than a token count: a topic, a row group and a
            # dependency step should not have the same effective size, and
            # dependency_chain -- whose units are ordered -- should degrade
            # fastest as the partition cuts between steps that carry values.
            "tax_by_category": {c: round(sum(v) / len(v), 6)
                                for c, v in sorted(by_category.items())},
            "accuracy_by_category": {c: round(sum(v) / len(v), 6)
                                     for c, v in sorted(accuracy_by_cat.items())},
            "categories": sorted(by_category),
            "n_categories": len(by_category),
            "accuracy_pooled": round(sum(1 for r in graded if r["correct"]) / len(graded), 6)
            if graded else None,
            "accuracy_balanced": round(sum(acc_balanced) / len(acc_balanced), 6)
            if acc_balanced else None,
            "n_items_graded": len(graded),
        })

    def _monotone(field: str) -> bool | None:
        values = [p[field] for p in points if p[field] is not None]
        return all(a <= b for a, b in zip(values, values[1:])) if len(values) > 1 else None

    return {
        "points": points,
        "slice": {"rho_target": slice_rho, "k": slice_k,
                  "condition": "fragmented", "typed_carry": False,
                  "every_n_reachable": bool(reachable_rhos)},
        "rhos_available": rhos,
        "rhos_fully_reachable": reachable_rhos,
        "ks_available": ks,
        "common_categories": sorted(common),
        "tax_monotone_in_n": _monotone("tax_balanced"),
        "tax_common_monotone_in_n": _monotone("tax_common"),
        "comparable_across_n": len({tuple(p["categories"]) for p in points}) == 1,
        "planner_constant_tokens_per_task": 60,
        "note": (
            "tokens_per_fragment is the baseline prompt's token count divided by N -- one "
            "fragment's share of the problem. Read tax_balanced and accuracy_balanced: the "
            "pooled columns beside them weight whichever category contributed most cells. "
            "Every axis but N is fixed, and `slice` names the cell: the lowest rho, the "
            "lowest k, no editor, no typed carry. Pooling them would average conditions the "
            "rest of this file refuses to average. "
            "planner_constant_tokens_per_task is what suggest_n_tasks currently assumes and "
            "has never been validated; this curve is what would validate or replace it. "
            "When comparable_across_n is false the points are made of different prompt "
            "shapes -- N is capped by how many divisible units a prompt has -- and only "
            "tax_common, restricted to the categories present at every N, compares like "
            "with like."
        ),
    }


def editor_effect(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What the post-processing pass bought, and what it cost.

    Paired by construction: the editor is swept as a condition, so every edited
    row has an unedited twin at the same prompt, N and k, and the comparison
    never crosses cells.

    The prediction this exists to test is a *refusal*. The editor holds the
    assembled answer and the contract, and it does not hold the source material,
    so it can restore a dropped term, merge a duplicated definition and repair
    the shape -- and it cannot know that 830 kg should have been 840. Constraint
    scores should rise; item accuracy should not. ``accuracy_delta`` materially
    above zero means the editor is answering from its own knowledge rather than
    editing, and the arm is contaminated rather than good.
    """
    def _key(row: Mapping[str, Any]) -> tuple:
        # typed_carry belongs in the key. Without it two rows collapse onto one
        # and the last wins, so with both arms running the editor was measured on
        # 160 of 320 pairs -- all of them typed -- and reported `n_pairs: 160` as
        # though that were the whole grid.
        return (str(row.get("prompt_id")), row.get("rho_target"),
                row.get("n_tasks"), row.get("k"), bool(row.get("typed_carry")))

    plain = {_key(r): r for r in rows if r.get("condition") == "fragmented"}
    edited = {_key(r): r for r in rows if r.get("condition") == "fragmented+editor"}
    pairs = [(plain[key], edited[key]) for key in sorted(edited.keys() & plain.keys())]
    if not pairs:
        return {"n_pairs": 0, "note": "the editor arm was not run"}

    applied = [e for _, e in pairs if e.get("editor_applied") is True]
    gains = [float(e["editor_gain"]) for _, e in pairs
             if isinstance(e.get("editor_gain"), (int, float))]
    tokens = [float(e["editor_input_tokens"]) + float(e["editor_output_tokens"])
              for _, e in pairs
              if isinstance(e.get("editor_input_tokens"), (int, float))]
    tax_delta = [float(e["coherence_tax_booook"]) - float(p["coherence_tax_booook"])
                 for p, e in pairs
                 if isinstance(e.get("coherence_tax_booook"), (int, float))
                 and isinstance(p.get("coherence_tax_booook"), (int, float))]

    def _accuracy(rows_side: Sequence[Mapping[str, Any]]) -> float | None:
        graded = [rec for r in rows_side for rec in (r.get("_truth_records") or [])
                  if rec.get("correct") is not None]
        return (sum(1 for r in graded if r["correct"]) / len(graded)) if graded else None

    acc_plain = _accuracy([p for p, _ in pairs])
    acc_edited = _accuracy([e for _, e in pairs])
    reasons: dict[str, int] = {}
    for _, e in pairs:
        reasons[str(e.get("editor_reason", ""))] = reasons.get(str(e.get("editor_reason", "")), 0) + 1

    return {
        "n_pairs": len(pairs),
        "n_applied": len(applied),
        "apply_rate": round(len(applied) / len(pairs), 6),
        "mean_constraint_gain": round(sum(gains) / len(gains), 6) if gains else None,
        "mean_tokens_per_edit": round(sum(tokens) / len(tokens), 1) if tokens else None,
        "mean_tax_delta": round(sum(tax_delta) / len(tax_delta), 6) if tax_delta else None,
        "accuracy_plain": round(acc_plain, 6) if acc_plain is not None else None,
        "accuracy_edited": round(acc_edited, 6) if acc_edited is not None else None,
        "accuracy_delta": round(acc_edited - acc_plain, 6)
        if (acc_plain is not None and acc_edited is not None) else None,
        "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "note": (
            "Paired: every edited row has an unedited twin at the same prompt, N and k. "
            "mean_constraint_gain is the share of mechanical checks recovered. rho is "
            "unchanged by construction -- the editor never sees the problem prompt -- so "
            "mean_tokens_per_edit is reported as its own budget line rather than folded in. "
            "accuracy_delta is a guard, not a goal: the editor has no access to the source "
            "material, so a rise in item accuracy means it is answering rather than editing."
        ),
    }


def carry_effect(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What a typed carry bought on the dependency axis, and what it cost in rho.

    Paired: the carry is swept as a condition, so every typed cell has an untyped
    twin at the same prompt, rho, N, k and editor setting.

    V4 measured the problem this addresses. At the widest fragment the ordered
    chain cost +47.2 % where prose cost +5.1 % and tables +3.3 % on fragments of
    identical size, with accuracy falling monotonically 0.259 -> 0.091 and the
    tax then saturating near +76 % -- what a broken chain looks like once the
    carried value is gone. No fragment size in the tested range made it
    affordable, which is why this is a mechanism rather than a parameter.

    The prediction is one-sided on accuracy and explicit about its price:

    * ``accuracy_delta`` should be **positive and large on dependency_chain**,
      because the successor now receives every value its predecessor produced
      rather than the lead sentence and an entity list;
    * ``rho_delta`` is expected to be **slightly positive**, and is reported so
      the trade is visible. An earlier draft predicted it would be negative on
      the grounds that a carried number is cheaper than prose. Measurement said
      otherwise: the prose summary is cheap precisely *because* it is
      incomplete, keeping only the first value of however many the fragment
      produced. Delivering three values costs more than delivering one. What the
      carry buys is completeness, and it is worth stating that it is bought
      rather than found.

    ``accuracy_delta_by_category`` is reported because a typed carry should do
    nothing at all where there is nothing to type. Prose fragments produce no
    labelled items, :func:`~swarmbly_v0.planner.carry_values` returns empty, and
    the summary falls back to prose unchanged. A gain appearing there would mean
    the two arms differ for some reason other than the carry.
    """
    def _key(row: Mapping[str, Any]) -> tuple:
        return (str(row.get("prompt_id")), row.get("rho_target"), row.get("n_tasks"),
                row.get("k"), str(row.get("condition")))

    plain = {_key(r): r for r in rows
             if str(r.get("condition", "")).startswith("fragmented")
             and r.get("typed_carry") is not True}
    typed = {_key(r): r for r in rows
             if str(r.get("condition", "")).startswith("fragmented")
             and r.get("typed_carry") is True}
    pairs = [(plain[key], typed[key]) for key in sorted(typed.keys() & plain.keys())]
    if not pairs:
        return {"n_pairs": 0, "note": "the typed-carry arm was not run"}

    def _accuracy(side: Sequence[Mapping[str, Any]], category: str = "") -> float | None:
        graded = [rec for r in side for rec in (r.get("_truth_records") or [])
                  if rec.get("correct") is not None
                  and (not category or str(rec.get("category")) == category)]
        return (sum(1 for r in graded if r["correct"]) / len(graded)) if graded else None

    categories = sorted({str(rec.get("category")) for _, t in pairs
                         for rec in (t.get("_truth_records") or [])})
    by_category: dict[str, Any] = {}
    for category in categories:
        before = _accuracy([p for p, _ in pairs], category)
        after = _accuracy([t for _, t in pairs], category)
        if before is None or after is None:
            continue
        by_category[category] = {
            "accuracy_plain": round(before, 6), "accuracy_typed": round(after, 6),
            "delta": round(after - before, 6),
        }

    def _mean_of(field: str, side: int) -> float | None:
        values = [float(pair[side][field]) for pair in pairs
                  if isinstance(pair[side].get(field), (int, float))]
        return (sum(values) / len(values)) if values else None

    rho_plain, rho_typed = _mean_of("rho_achieved", 0), _mean_of("rho_achieved", 1)
    tax_plain, tax_typed = _mean_of("coherence_tax_booook", 0), _mean_of("coherence_tax_booook", 1)
    acc_plain, acc_typed = _accuracy([p for p, _ in pairs]), _accuracy([t for _, t in pairs])

    return {
        "n_pairs": len(pairs),
        "accuracy_plain": round(acc_plain, 6) if acc_plain is not None else None,
        "accuracy_typed": round(acc_typed, 6) if acc_typed is not None else None,
        "accuracy_delta": round(acc_typed - acc_plain, 6)
        if (acc_plain is not None and acc_typed is not None) else None,
        "accuracy_delta_by_category": by_category,
        "rho_plain": round(rho_plain, 6) if rho_plain is not None else None,
        "rho_typed": round(rho_typed, 6) if rho_typed is not None else None,
        "rho_delta": round(rho_typed - rho_plain, 6)
        if (rho_plain is not None and rho_typed is not None) else None,
        "tax_delta": round(tax_typed - tax_plain, 6)
        if (tax_plain is not None and tax_typed is not None) else None,
        "note": (
            "A typed carry replaces the extractive prose summary -- lead sentence plus "
            "entity list -- with every labelled value the fragment produced. Read rho_delta "
            "beside accuracy_delta: the carry buys completeness and pays a small amount of "
            "context for it, and both halves belong in the report. Categories with no "
            "labelled items should show no change at all: the carry falls back to prose "
            "wherever there is nothing to type."
        ),
    }


def falsifiable_go_no_go(
    rows: Sequence[Mapping[str, Any]],
    category: str,
    rho: float,
    threshold: float = 0.05,
    n_tasks: int | None = None,
    k: int | None = None,
) -> dict[str, Any]:
    """The pre-registered criterion, restated so that it can fail.

    V0's criterion read "exists (category, rho) with relative degradation < 5 %"
    and reported ``passed: true``. Simulating its own null -- no cell genuinely
    different, observations shuffled between the 32 cells of n=3 -- gives
    P(some cell under 5 %) = 100 %. It is a maximum statistic over many noisy
    cells with no multiple-comparison control, and it would have passed on random
    data. Its passing was never evidence.

    Three changes, each of which can produce a failure:

    * the cell is **named in advance** and passed in as an argument, so the
      result cannot be chosen after seeing the data;
    * the threshold must be cleared by the **upper bound** of a bootstrap
      interval, not by the point estimate;
    * ``n_cells_examined`` is reported, so a reader can see how many chances the
      criterion had even when only one was declared.

    ``n_tasks`` must be named too, and the run of 26 August is why. Filtering on
    category and rho alone averages N -- and N is the axis with by far the
    largest effect. Pooled over N, ``table_summary`` at rho 3.5 reads +20.9 %,
    comfortably failing; at N=2, the fragment size the threshold question is
    actually about, the same cells read **+5.8 %** with an interval spanning the
    threshold. The criterion written to stop a maximum statistic from passing on
    noise was itself hiding the one live candidate inside a mean.

    ``k`` must be named for the same reason, one axis later, and the table run of
    26 August is why. Filtered on category, rho and N but not k, the declared
    cell read **+18.3 %** -- a mean of +20.6 % at k=1 and +16.0 % at k=3, a
    number belonging to neither arm. The rest of this file already refuses to
    average k: ``headline_restricted_to_k`` exists precisely because consensus is
    a separate mechanism from fragmentation. The criterion was the one place
    still doing it.

    On that run the omission did not change the verdict -- both arms fail by a
    wide margin -- but it would have at N=8, where k=1 costs +25.3 % and k=3
    costs +63.7 %. A mean of those two describes no arm that was run.
    """
    # Below-floor rows cannot enter a published figure; see `publishable`.
    rows = publishable(rows)
    cells = [r for r in rows
             if str(r.get("condition", "")).startswith("fragmented")
             and str(r.get("category")) == category
             and _close(r.get("rho_target"), rho)
             and (n_tasks is None or _same_number(r.get("n_tasks"), n_tasks))
             and (k is None or _same_number(r.get("k"), k))
             and isinstance(r.get("coherence_tax_booook"), (int, float))]
    examined = len({(str(r.get("category")), r.get("rho_target")) for r in rows
                    if str(r.get("condition", "")).startswith("fragmented")})

    if len(cells) < 2:
        return {"declared_cell": {"category": category, "rho": rho, "n_tasks": n_tasks, "k": k},
                "passed": None, "n_observations": len(cells),
                "n_cells_examined": examined,
                "note": "too few observations in the declared cell to form an interval"}

    # Resample whole PROMPTS, not rows. Rows from one prompt share its
    # difficulty, its contract and its source material, so treating them as
    # independent draws narrows the interval by roughly the square root of the
    # rows per prompt. On the current corpus a cell is nearly a prompt and the
    # damage is small -- but "nearly" is not a property to rely on, and it stops
    # being true the moment a sweep varies anything inside a prompt.
    interval = cluster_bootstrap(
        [{"prompt_id": str(r.get("prompt_id", "")),
          "value": float(r["coherence_tax_booook"])} for r in cells],
        lambda rows: (sum(x["value"] for x in rows) / len(rows)) if rows else None,
        cluster_key="prompt_id",
    )
    values = np.asarray([float(r["coherence_tax_booook"]) for r in cells], dtype=np.float64)
    if interval.get("ci95") is None:
        return {"declared_cell": {"category": category, "rho": rho, "n_tasks": n_tasks, "k": k},
                "passed": None, "n_observations": int(values.size),
                "n_prompts": interval["n_clusters"], "n_cells_examined": examined,
                "point_estimate": round(float(values.mean()), 6),
                "note": interval.get("note", "no interval estimable")}
    lo, hi = interval["ci95"]

    return {
        "declared_cell": {"category": category, "rho": rho, "n_tasks": n_tasks, "k": k},
        "n_observations": int(values.size),
        "n_prompts": interval["n_clusters"],
        "n_cells_examined": examined,
        "point_estimate": round(float(values.mean()), 6),
        "ci95": [round(lo, 6), round(hi, 6)],
        "threshold": threshold,
        "passed": bool(hi < threshold),
        "note": (
            "Passes only when the upper bound of the interval clears the threshold, on a cell "
            "named before the run. The point estimate alone is what made the old criterion "
            "unfalsifiable; n_cells_examined states how many chances were available. The "
            "interval is a cluster bootstrap over prompts -- n_prompts, not n_observations, is "
            "the sample size that matters, because rows from one prompt share its difficulty."
        ),
    }


COMPOSITION_THRESHOLD_POINTS: float = 0.05
"""The declared cost ceiling for prose composition, in points, frozen here.

It is the existing criterion translated onto the better metric, not a new one
chosen for it: SPEC's go/no-go says fragmentation must cost under 5 % of
coherence, and this says it must cost under 5 points of the constraints a text
either satisfies or does not. Same number, a metric that is counted rather than
judged.

**It is declared against data that fails it.** The free-form pilot of
3 September put the gap at 14 to 21 points -- three to four times this ceiling
-- and the threshold is written down anyway, at the value the old criterion
implies, precisely so that nobody can later say it was set where the result
happened to land. A threshold chosen after seeing 14 points would have been
0.25, and a criterion that passes because its threshold was fitted to its own
outcome is the maximum statistic wearing different clothes.

Frozen against the dev half of the corpus. Moving it after the final half has
been seen invalidates the split, and the number is here rather than on the
command line so that moving it shows up in a diff."""

MIN_CLUSTERS_FOR_A_VERDICT: int = 20
"""Prompts below which this file refuses to publish a bootstrap verdict.

Not a convention borrowed from a textbook -- a number this project paid for. On
3 September the free-form run reported the first non-null measurement of the
confidence map in six attempts: AUC 0.602, a clustered 95 % interval of
[0.5014, 0.7243], and a permutation p of 0.0026. The lower bound excluded chance
by 0.0014 **on eight clusters**, where a cluster bootstrap's coverage is not
close to nominal and the interval is an ornament. The result was published with
its own caveat attached, and a caveat beside a number does not travel with the
number: what a reader takes away is 0.602.

So the refusal is in the code, and it returns ``passed: None`` with the count in
the note rather than a bound a reader can quote. A criterion that reports a
verdict on eight prompts has the same defect the maximum statistic had -- it
cannot fail for the right reason."""


def composition_criterion(
    rows: Sequence[Mapping[str, Any]],
    category: str,
    rho: float,
    threshold_points: float,
    n_tasks: int | None = None,
    k: int | None = None,
    min_clusters: int = MIN_CLUSTERS_FOR_A_VERDICT,
    score: str = "constraint_score_comparable",
    baseline: str = "baseline_constraint_score_comparable",
) -> dict[str, Any]:
    """The declared criterion for prose composition, in points not per cent.

    This is the apparatus ``tables-final`` has and the constraint score lacked.
    The composition run of 3 September produced the project's strongest
    measurement -- a monolithic arm satisfying **every** checkable constraint,
    a three-way fragmentation losing 14 to 21 points, counted from the text with
    no model in the verdict -- and it had no pre-registered cell, no control and
    no corpus split behind it. It was therefore a description of three prompts,
    not evidence about a workload.

    Four ways this differs from :func:`falsifiable_go_no_go`, each forced by
    something that went wrong:

    * **Absolute, not relative.** Ten of eleven monolithic baselines on that run
      scored exactly 1.000. A ratio ``(baseline - fragmented) / baseline``
      against a denominator pinned at the ceiling can only be non-negative, has
      almost no resolution, and makes one lost check the entire numerator. The
      paired difference in points has no denominator to be sensitive to.
    * **Paired within prompt.** The two arms answer the *same* prompt, so the
      prompt's difficulty cancels. Comparing two condition means -- which is all
      ``_composition_summary`` could do before ``constraint_score_comparable``
      existed as a column -- leaves that difficulty in the estimate.
    * **A cluster floor.** See :data:`MIN_CLUSTERS_FOR_A_VERDICT`. Three
      compositions cannot support an interval and this function says so instead
      of printing one.
    * **The comparable score only.** ``paragraph_count`` and
      ``words_per_paragraph`` are decided by the assembler in one arm and by the
      model in the other, and the sign of that bias is set by prompt wording:
      +23 points in favour of the fragmented arm on the free-form corpus, the
      other way on the table corpus. They cannot appear in a cross-arm figure at
      all, so the default ``score`` excludes them.

    The verdict is on the **upper** bound: the claim under test is that
    fragmentation costs at most ``threshold_points``, so the interval must clear
    the threshold from above, exactly as the relative criterion requires.

    Args:
        threshold_points: The declared cost ceiling, in points of constraint
            satisfaction (0.05 is five points, not five per cent of the
            baseline). Must be declared before the run; it is an argument rather
            than a constant so the declaration lives in the invocation.

    Returns:
        The verdict, the interval, the per-prompt pairs, and the two counts that
        say whether the verdict may be read: ``n_prompts`` and
        ``baseline_at_ceiling``.
    """
    rows = publishable(rows)
    cells = [r for r in rows
             if str(r.get("condition", "")).startswith("fragmented")
             and str(r.get("category")) == category
             and _close(r.get("rho_target"), rho)
             and (n_tasks is None or _same_number(r.get("n_tasks"), n_tasks))
             and (k is None or _same_number(r.get("k"), k))
             and isinstance(r.get(score), (int, float))
             and isinstance(r.get(baseline), (int, float))]
    examined = len({(str(r.get("category")), r.get("rho_target"),
                     r.get("n_tasks"), r.get("k")) for r in rows
                    if str(r.get("condition", "")).startswith("fragmented")
                    and isinstance(r.get(score), (int, float))})
    declared = {"category": category, "rho": rho, "n_tasks": n_tasks, "k": k,
                "threshold_points": threshold_points, "score": score,
                "min_clusters": min_clusters}

    pairs = [{"prompt_id": str(r.get("prompt_id", "")),
              "delta": float(r[baseline]) - float(r[score]),
              "fragmented": float(r[score]),
              "baseline": float(r[baseline]),
              "n_checks": r.get("n_constraints_checked", "")}
             for r in cells]
    if not pairs:
        return {"declared_cell": declared, "passed": None, "n_observations": 0,
                "n_cells_examined": examined,
                "note": "no rows in the declared cell; this run has no verdict"}

    deltas = [p["delta"] for p in pairs]
    mean_ci = cluster_bootstrap(
        pairs, lambda rs: sum(x["delta"] for x in rs) / len(rs) if rs else None,
        cluster_key="prompt_id")
    median_ci = cluster_bootstrap(
        pairs, lambda rs: float(np.median([x["delta"] for x in rs])) if rs else None,
        cluster_key="prompt_id")
    n_prompts = int(mean_ci.get("n_clusters") or 0)
    at_ceiling = sum(1 for p in pairs if p["baseline"] >= 0.999)

    result: dict[str, Any] = {
        "declared_cell": declared,
        "n_observations": len(pairs),
        "n_prompts": n_prompts,
        "n_cells_examined": examined,
        "mean_delta": round(sum(deltas) / len(deltas), 6),
        "mean_ci95": mean_ci.get("ci95"),
        "median_delta": round(float(np.median(deltas)), 6),
        "median_ci95": median_ci.get("ci95"),
        "mean_baseline": round(sum(p["baseline"] for p in pairs) / len(pairs), 6),
        "mean_fragmented": round(sum(p["fragmented"] for p in pairs) / len(pairs), 6),
        "baseline_at_ceiling": at_ceiling,
        "n_at_or_below_zero": sum(1 for d in deltas if d <= 0),
        "pairs": sorted(pairs, key=lambda p: -p["delta"]),
    }

    if n_prompts < min_clusters:
        result["passed"] = None
        result["note"] = (
            f"{n_prompts} prompts against a floor of {min_clusters}: no verdict. "
            f"A cluster bootstrap on this few clusters does not have its nominal "
            f"coverage, and the free-form run of 3 September is why the floor is "
            f"enforced here rather than noted -- it excluded chance by 0.0014 on "
            f"eight clusters and the caveat did not travel with the number. The "
            f"point estimate and the pairs are reported so the cell can be read "
            f"as a description; the interval must not be quoted as a bound.")
        return result

    ci = mean_ci.get("ci95")
    if ci is None:
        result["passed"] = None
        result["note"] = mean_ci.get("note", "no interval estimable")
        return result

    lo, hi = ci
    result["passed"] = bool(hi < threshold_points)
    result["short_by_points"] = round(float(hi) - float(threshold_points), 6)
    result["note"] = (
        f"Fragmentation is claimed to cost at most {threshold_points:.3f} of "
        f"constraint satisfaction; the verdict is on the UPPER bound of a "
        f"bootstrap clustered by prompt, so the cell passes only when the "
        f"interval clears the threshold from above. baseline_at_ceiling="
        f"{at_ceiling} of {len(pairs)} says how much room the metric had: where "
        f"the baseline is 1.000 the paired difference can only be non-negative, "
        f"so a pass is a real bound on the cost and a fail cannot be read as "
        f"fragmentation helping. n_cells_examined={examined} states how many "
        f"chances the run had even though one cell was declared.")
    return result


def _close(value: Any, target: float, tol: float = 1e-9) -> bool:
    try:
        return abs(float(value) - float(target)) <= tol
    except (TypeError, ValueError):
        return False


def _mean(values: Iterable[float]) -> float:
    items = [v for v in values]
    return sum(items) / len(items) if items else 0.0


def summarize(
    rows: Sequence[dict[str, Any]],
    prompts: Sequence[PromptSpec] | None = None,
    router_threshold: float = DEFAULT_THRESHOLD,
    unit_records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute the headline numbers and the go/no-go verdict.

    Returns a dict with the coherence tax averaged by ``rho``, by ``(rho, N)``
    and by ``(category, rho)``, the best operating point, whether any
    ``(category, rho)`` cell clears the <5% relative degradation criterion, and
    -- when the run used ``k > 1`` -- the micro-level consensus curve plus the
    agreement-vs-quality calibration.

    Args:
        rows: Sweep rows, from :func:`run_sweep` or :func:`read_rows`.
        prompts: Optional corpus, enabling the router evaluation block.
        router_threshold: Threshold for that evaluation.
        unit_records: Per-consensus-unit records. Defaults to whatever the rows
            carry in ``_unit_records``; pass the sidecar (:func:`read_unit_rows`)
            when summarising rows that came back from disk.
    """
    # Below-floor rows never enter a published figure. See `publishable`.
    n_unreachable = len(rows) - len(publishable(rows))
    rows = publishable(rows)
    fragmented_all = [r for r in rows if r.get("condition") == "fragmented"]
    # The tax headline already refuses to average k, on the stated grounds that a
    # mean of k=1 and k=3 "belongs to neither". The carry is the same kind of
    # axis and was not guarded: with both arms running, every tax figure was the
    # midpoint of a broken chain and a repaired one. Restrict to the untyped arm,
    # which is the condition every earlier run was measured in, and say so.
    carries_present = sorted({bool(r.get("typed_carry")) for r in fragmented_all})
    if len(carries_present) > 1:
        fragmented_all = [r for r in fragmented_all if not r.get("typed_carry")]

    def _f(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
        value = row.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def tax(row: dict[str, Any], key: str = "coherence_tax_booook") -> float:
        return _f(row, key)

    def _stable(row: Mapping[str, Any], baseline_key: str) -> bool:
        """Is this cell's ratio built on a denominator large enough to mean anything?"""
        if baseline_key not in row or row.get(baseline_key) in ("", None):
            return True   # older CSVs carry no denominator; do not silently drop them
        return _f(row, baseline_key) >= MIN_BASELINE

    # The coherence tax (H1) is measured against the monolithic baseline for the
    # *assembly* pipeline. k is a separate axis (E16) and, as the first real run
    # showed, a large one: averaging k=1 and k=3 cells into one "tax" reports a
    # number that belongs to neither. When a run spans several k, the headline is
    # taken from k=1 and the choice is recorded rather than assumed.
    ks = sorted({int(_f(r, "k", 1)) for r in fragmented_all})
    headline_k = min(ks) if len(ks) > 1 else (ks[0] if ks else 1)
    fragmented = ([r for r in fragmented_all if int(_f(r, "k", 1)) == headline_k]
                  if len(ks) > 1 else fragmented_all)

    by_rho: dict[float, list[float]] = {}
    by_rho_grid: dict[float, list[float]] = {}
    by_rho_n: dict[tuple[float, int], list[float]] = {}
    by_cat_rho: dict[tuple[str, float], list[float]] = {}
    rho_achieved: dict[float, list[float]] = {}

    abs_booook: dict[float, list[float]] = {}
    abs_grid: dict[float, list[float]] = {}
    unstable = {"booook": 0, "entity_grid": 0}

    for row in fragmented:
        rho = float(row["rho_target"])
        n = int(row["n_tasks"])
        category = str(row["category"])
        rho_achieved.setdefault(rho, []).append(float(row["rho_achieved"]))

        base_b = _f(row, "baseline_booook")
        base_g = _f(row, "baseline_entity_grid")
        # Absolute differences are stable whatever the denominator does.
        abs_booook.setdefault(rho, []).append(base_b - _f(row, "booook_like_score"))
        abs_grid.setdefault(rho, []).append(base_g - _f(row, "entity_grid"))

        if _stable(row, "baseline_booook"):
            by_rho.setdefault(rho, []).append(tax(row))
            by_rho_n.setdefault((rho, n), []).append(tax(row))
            by_cat_rho.setdefault((category, rho), []).append(tax(row))
        else:
            unstable["booook"] += 1
            by_rho.setdefault(rho, [])
        if _stable(row, "baseline_entity_grid"):
            by_rho_grid.setdefault(rho, []).append(tax(row, "coherence_tax_entity_grid"))
        else:
            unstable["entity_grid"] += 1
            by_rho_grid.setdefault(rho, [])

    curve = [
        {
            "rho": rho,
            "rho_achieved_mean": round(_mean(rho_achieved[rho]), 4),
            # None, not 0.0: a mean over zero surviving cells is "not measured",
            # and printing +0.00% there would read as "no degradation".
            "coherence_tax_booook": round(_mean(values), 6) if values else None,
            "coherence_tax_entity_grid": (
                round(_mean(by_rho_grid.get(rho, [])), 6) if by_rho_grid.get(rho) else None),
            "abs_delta_booook": round(_mean(abs_booook.get(rho, [])), 6),
            "abs_delta_entity_grid": round(_mean(abs_grid.get(rho, [])), 6),
            "n_cells": len(values),
            "n_cells_entity_grid": len(by_rho_grid.get(rho, [])),
        }
        for rho, values in sorted(by_rho.items())
    ]

    category_curve = [
        {
            "category": category,
            "rho": rho,
            "coherence_tax_booook": round(_mean(values), 6) if values else None,
            "n_cells": len(values),
        }
        for (category, rho), values in sorted(by_cat_rho.items())
    ]

    # A cell with no surviving measurement cannot pass a criterion, and must not
    # be able to fail one either: it is absent, not zero.
    _measured = [c for c in category_curve if c["coherence_tax_booook"] is not None]
    _measured_curve = [c for c in curve if c["coherence_tax_booook"] is not None]
    passing = [c for c in _measured if c["coherence_tax_booook"] < 0.05]
    best_overall = (min(_measured_curve, key=lambda c: c["coherence_tax_booook"])
                    if _measured_curve else None)
    best_cell = (min(_measured, key=lambda c: c["coherence_tax_booook"])
                 if _measured else None)

    # -- micro level: consensus over k replicas ----------------------------
    # Deliberately over *every* k, not the headline subset: this curve is what
    # the k axis is for, and restricting it to the headline k would delete it.
    by_k: dict[int, list[dict[str, Any]]] = {}
    for row in fragmented_all:
        try:
            k_value = int(float(row.get("k", 1) or 1))
        except (TypeError, ValueError):
            k_value = 1
        by_k.setdefault(k_value, []).append(row)

    def _numeric(values: Iterable[Any]) -> list[float]:
        out: list[float] = []
        for value in values:
            try:
                out.append(float(value))
            except (TypeError, ValueError):
                continue
        return out

    consensus_curve = [
        {
            "k": k_value,
            "n_cells": len(cells),
            "n_families_mean": round(_mean(_numeric(c.get("n_families") for c in cells)), 4),
            "mean_agreement": round(_mean(_numeric(c.get("mean_agreement") for c in cells)), 6),
            "frac_high": round(_mean(_numeric(c.get("frac_high") for c in cells)), 6),
            "frac_medium": round(_mean(_numeric(c.get("frac_medium") for c in cells)), 6),
            "frac_low": round(_mean(_numeric(c.get("frac_low") for c in cells)), 6),
            "n_low_conf_regions": sum(int(v) for v in
                                      _numeric(c.get("n_low_conf_regions") for c in cells)),
            "coherence_tax_booook": round(_mean([tax(c) for c in cells]), 6),
        }
        for k_value, cells in sorted(by_k.items())
    ]

    units = list(unit_records) if unit_records is not None else [
        record for row in rows for record in row.get("_unit_records", [])
    ]

    summary: dict[str, Any] = {
        "rows_excluded_below_floor": n_unreachable,
        "rows_excluded_note": (
            "Rows whose rho_target sat below their own packing floor. Below the "
            "floor every packet collapses to its bare task, so the rho axis does "
            "not move and two different rho labels produce byte-identical cells. "
            "They are dropped from every figure in this summary rather than "
            "flagged, because a note beside a number does not travel with the "
            "number. Read them in results.csv where rho_reachable is false."
            if n_unreachable else
            "Every row was at or above its packing floor."),
        "curve": curve,
        "category_curve": category_curve,
        "consensus_curve": consensus_curve,
        "agreement_quality_correlation": agreement_quality_correlation(units),
        **_truth_summary(rows),
        **_composition_summary(rows),
        "by_rho_n": [
            {"rho": rho, "n_tasks": n, "coherence_tax_booook": round(_mean(values), 6)}
            for (rho, n), values in sorted(by_rho_n.items())
        ],
        "best_overall": best_overall,
        "best_category_cell": best_cell,
        "fragment_size_curve": fragment_size_curve(rows),
        "falsifiable_go_no_go": {
            f"{cat}@rho={rho}@N={n}@k={k}": falsifiable_go_no_go(
                fragmented_all, category=cat, rho=rho, n_tasks=n, k=k)
            for cat in sorted({str(r.get("category", "")) for r in fragmented_all})
            for rho in sorted({float(r["rho_target"]) for r in fragmented_all
                               if isinstance(r.get("rho_target"), (int, float))})
            for n in sorted({int(r["n_tasks"]) for r in fragmented_all
                             if str(r.get("n_tasks", "")).isdigit()})
            for k in sorted({int(r["k"]) for r in fragmented_all
                             if str(r.get("k", "")).isdigit()})
        },
        "rho_fidelity": rho_fidelity(fragmented_all),
        # The same cells as an absolute paired difference. Beside the declared
        # relative criterion, never instead of it -- see paired_absolute_effect.
        "paired_absolute": {
            f"{cat}@rho={rho}@N={n}@k={k}": paired_absolute_effect(
                fragmented_all, category=cat, rho=rho, n_tasks=n, k=k)
            for cat in sorted({str(r.get("category", "")) for r in fragmented_all})
            for rho in sorted({float(r["rho_target"]) for r in fragmented_all
                               if isinstance(r.get("rho_target"), (int, float))})
            for n in sorted({int(r["n_tasks"]) for r in fragmented_all
                             if str(r.get("n_tasks", "")).isdigit()})
            for k in sorted({int(r["k"]) for r in fragmented_all
                             if str(r.get("k", "")).isdigit()})
        },
        # The same discipline, on the better instrument. The constraint score is
        # mechanical -- no judge, no model in the verdict -- and on prose
        # composition the coherence tax read +0.000 on texts where this one
        # found a 14-point failure. Until `constraint_score_comparable` became a
        # column it could only be reported as two condition means, which is why
        # the stronger measurement had the weaker apparatus.
        "composition_criterion": {
            f"{cat}@rho={rho}@N={n}@k={k}": composition_criterion(
                fragmented_all, category=cat, rho=rho, n_tasks=n, k=k,
                threshold_points=COMPOSITION_THRESHOLD_POINTS)
            # Categories with a constraint score only. Every other category
            # would contribute an entry saying "no rows in the declared cell",
            # and a summary padded with empty verdicts is one a reader skims.
            for cat in sorted({str(r.get("category", "")) for r in fragmented_all
                               if isinstance(r.get("constraint_score_comparable"),
                                             (int, float))})
            for rho in sorted({float(r["rho_target"]) for r in fragmented_all
                               if isinstance(r.get("rho_target"), (int, float))})
            for n in sorted({int(r["n_tasks"]) for r in fragmented_all
                             if str(r.get("n_tasks", "")).isdigit()})
            for k in sorted({int(r["k"]) for r in fragmented_all
                             if str(r.get("k", "")).isdigit()})
        },
        "falsifiable_go_no_go_note": (
            "Every cell is reported because a run cannot know which one was declared in "
            "advance -- but declaring afterwards is not declaring, and n_cells_examined in "
            "each entry states how many chances were available. N is part of the cell: "
            "pooling it averages the axis with the largest effect and hid a candidate at "
            "+5.8% inside a mean of +20.9%. So is k, and this note used to claim the cells "
            "were computed at 'headline k' while nothing restricted k at all: on the table "
            "run of 26 August the declared cell read +18.3%, the midpoint of +20.6% at k=1 "
            "and +16.0% at k=3, a number belonging to neither arm. At N=8 the same omission "
            "would have averaged +25.3% with +63.7%. A pass here counts only for a cell "
            "named before the run, and the cell is (category, rho, N, k)."
        ),
        "editor_effect": editor_effect(rows),
        "carry_effect": carry_effect(rows),
        "go_no_go": {
            "criterion": "exists (category, rho) with relative coherence degradation < 5%",
            "passed": bool(passing),
            "passing_cells": passing,
            "WARNING": (
                "This criterion cannot fail. Simulating its own null -- no cell genuinely "
                "different, observations shuffled between cells -- gives P(some cell under 5%) "
                "= 100%. It is a maximum statistic over many noisy cells with no "
                "multiple-comparison control and would pass on random data. Retained only so "
                "that runs remain comparable with the record of 14 August; read "
                "falsifiable_go_no_go() instead, which requires the cell to be named in "
                "advance and cleared by the upper bound of a bootstrap interval."
            ),
        },
        "n_rows": len(rows),
        "n_fragmented_cells": len(fragmented),
        "headline_k": headline_k,
        "ks_present": ks,
        "headline_restricted_to_k": len(ks) > 1,
        "unstable_cells": {
            "min_baseline": MIN_BASELINE,
            "excluded_booook": unstable["booook"],
            "excluded_entity_grid": unstable["entity_grid"],
            "note": (
                "cells whose monolithic baseline fell below min_baseline are "
                "excluded from the relative means: a ratio over a near-zero "
                "denominator is not a measurement. They are counted here rather "
                "than dropped quietly, and abs_delta_* in the curve is the "
                "denominator-free version of the same comparison."
            ),
        },
    }

    if prompts:
        evaluation = evaluate_router(
            [(p.text, p.expected_decomposable) for p in prompts], router_threshold
        )
        summary["router"] = {
            "threshold": evaluation.threshold,
            "accuracy": round(evaluation.accuracy, 4),
            "precision": round(evaluation.precision, 4),
            "recall": round(evaluation.recall, 4),
            "false_positive_rate": round(evaluation.false_positive_rate, 4),
            "confusion": {
                "tp": evaluation.true_positive, "fp": evaluation.false_positive,
                "tn": evaluation.true_negative, "fn": evaluation.false_negative,
            },
        }
    return summary
