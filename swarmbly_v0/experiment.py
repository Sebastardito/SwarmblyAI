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

import csv
import json
import math
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
from .grading import grade_units
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
from .packing import build_monolithic_prompt, build_packets, packing_floor
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
]

DEFAULT_PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "prompts.json"

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
    "coherence_tax_entity_grid",
    "quality_tax_judge",
    "baseline_booook",
    "baseline_entity_grid",
    "baseline_judge",
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
    "prompt_id", "category", "level", "condition", "rho_target", "n_tasks", "k", "task_id",
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


def load_prompts(path: str | Path | None = None) -> list[PromptSpec]:
    """Load the labelled prompt corpus (defaults to the bundled ``prompts/``)."""
    target = Path(path) if path is not None else DEFAULT_PROMPTS_PATH
    with open(target, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    entries = payload["prompts"] if isinstance(payload, dict) else payload
    return [PromptSpec.from_dict(entry) for entry in entries]


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


def _fill_metric_row(row: dict[str, Any], text: str, plan: Plan | None,
                     contract: Contract, embedder: Embedder,
                     offsets: Sequence[int] | None = None,
                     fragments: Sequence[str] | None = None) -> dict[str, Any]:
    """Populate every coherence/quality column for one produced answer."""
    taxonomy = seam_error_taxonomy(text, plan, offsets, contract)
    row["booook_like_score"] = round(taxonomy.booook_like_score, 6)
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
    mean_agreement = (sum(u.agreement for u in units) / n_units) if n_units else 0.0
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
    """One sentence of the baseline, shaped like a consensus unit.

    The baseline is a single reply, so nothing about it was agreed with anything:
    ``agreement`` is 0.0 and stays out of every calibration by construction, the
    same way the item-corpus baseline already does. What it contributes is the
    *accuracy* denominator -- the number that separates "assembly broke this"
    from "the model could never do it".
    """

    index: int
    text: str
    label: str = ""
    agreement: float = 0.0
    judge_score: float = 0.0
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
                "rho_target": row.get("rho_target", ""), "n_tasks": row.get("n_tasks", ""),
                "k": result.k, "task_id": task_id, "unit_index": index,
                "item_id": "", "label": unit.label,
                "agreement": round(float(unit.agreement), 6),
                "judge_score": round(float(unit.judge_score), 6),
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


def _truth_records(
    spec: PromptSpec,
    row: Mapping[str, Any],
    results: Sequence[tuple[str, "ConsensusResult"]],
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
        for rec in graded:
            entry = (spec.key or {}).get(str(rec.get("item_id", "")), {})
            records.append({
                "prompt_id": spec.prompt_id,
                "category": spec.category,
                "level": entry.get("level", "") if isinstance(entry, dict) else "",
                "condition": row.get("condition", "fragmented"),
                "rho_target": row.get("rho_target", ""),
                "n_tasks": row.get("n_tasks", ""),
                "k": result.k,
                "task_id": task_id,
                **rec,
            })
        d = report.as_dict()
        for field_name in totals:
            totals[field_name] += int(d.get(field_name) or 0)
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
    _fill_metric_row(row, text, None, gamma, embedder)

    # Grade the baseline too, when there is a key. Without this the run cannot
    # separate "a 3B model cannot do this task" from "fragmenting it destroyed
    # the task", and after the 24 August run -- one correct answer in
    # sixty-four on two-step arithmetic -- that is the more interesting of the
    # two questions. The baseline is a single reply, so its units carry no
    # agreement; the records are excluded from the calibration by construction
    # and counted as such.
    if spec.is_composition:
        row["_trace"] = build_trace(spec.prompt_id, "monolithic", text, spec.constraints or [])

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
            "condition": "monolithic", "rho_target": 1.0, "n_tasks": 1,
            "k": 1, "task_id": "monolithic", **rec,
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
    plan = build_plan(spec.text, backend, n_tasks=n_tasks, contract=gamma)

    per_task_target = max(24, round(gamma.target_length_tokens / max(len(plan.tasks), 1)))
    packing_contract = replace(gamma, target_length_tokens=per_task_target)

    k = max(1, int(k))
    nodes = replica_backends(backend, k) if k > 1 else [backend]

    summaries: dict[str, str] = {}
    fragments: list[Fragment] = []
    packet_tokens_total = 0
    order_index = {tid: i for i, tid in enumerate(plan.topological_order())}
    consensus_results: list[tuple[str, ConsensusResult]] = []

    for level in plan.topological_levels():
        packing = build_packets(packing_contract, plan, rho_target, summaries)
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
            fragments.append(
                Fragment(task_id=task_id, candidates=candidates,
                         order=order_index.get(task_id, len(fragments)),
                         packet_tokens=packet.token_count)
            )
            summaries[task_id] = summarize_fragment(candidates[0], typed=typed_carry)

    final_packing = build_packets(packing_contract, plan, rho_target, summaries)
    rho_achieved = packet_tokens_total / max(count_tokens(spec.text), 1)

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
        "rho_target": rho_target,
        "rho_achieved": round(rho_achieved, 6),
        "rho_floor": round(packing_floor(packing_contract, plan), 6),
        "rho_reachable": final_packing.reachable,
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
                     assembly.fragment_sentence_offsets, selected_texts)
    if spec.is_composition:
        label = f"fragmented k={k}" + (" +editor" if use_editor else "")
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

    row["_unit_records"] = _unit_records(spec, row, consensus_results)
    truth_records, truth_report = _truth_records(spec, row, consensus_results)
    if truth_records or truth_report:
        row["_truth_records"] = truth_records
        row["_truth_report"] = truth_report

    if baseline:
        row["coherence_tax_booook"] = _relative_tax(
            baseline["booook_like_score"], row["booook_like_score"])
        row["coherence_tax_entity_grid"] = _relative_tax(
            baseline["entity_grid"], row["entity_grid"])
        row["quality_tax_judge"] = _relative_tax(
            baseline["judge_score"], row["judge_score"])
        # The denominators travel with the ratios. A tax without its baseline
        # cannot be checked for the instability MIN_BASELINE documents.
        row["baseline_booook"] = round(float(baseline["booook_like_score"]), 6)
        row["baseline_entity_grid"] = round(float(baseline["entity_grid"]), 6)
        row["baseline_judge"] = round(float(baseline["judge_score"]), 6)
    else:
        row["coherence_tax_booook"] = ""
        row["coherence_tax_entity_grid"] = ""
        row["quality_tax_judge"] = ""
        row["baseline_booook"] = ""
        row["baseline_entity_grid"] = ""
        row["baseline_judge"] = ""
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
            spec.text, engine, target_length_tokens=cfg.answer_tokens
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
        return {
            "n_compositions": len(group),
            "mean_constraint_score": round(sum(scored) / len(scored), 6) if scored else None,
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

    return {"truth_calibration": {
        "pooled": pooled,
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
    return result


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

    for rec in records:
        correct = rec.get("correct")
        agreement = rec.get("agreement")
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
            hits = sum(1 for _, y in sorted(pairs, key=lambda p: p[0])[:cut] if y == 0)
            flagged += cut
            caught += hits
            # What flagging at random inside this category would have caught.
            expected += cut * (n_wrong / n)
            per_stratum[name] = {"n_flagged": cut, "errors_caught": hits,
                                 "precision": round(hits / cut, 6),
                                 "lift": round((hits / cut) / (n_wrong / n), 6)}
        out.append({
            "flag_rate": rate,
            "n_flagged": flagged,
            "errors_caught": caught,
            "precision": round(caught / flagged, 6) if flagged else None,
            "lift": round(caught / expected, 6) if expected > 0 else None,
            "by_stratum": per_stratum,
        })
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
    baselines = {str(r.get("prompt_id")): r for r in rows
                 if r.get("condition") == "monolithic"}
    by_n: dict[int, list[Mapping[str, Any]]] = {}
    for row in rows:
        if str(row.get("condition", "")).startswith("fragmented"):
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
        "common_categories": sorted(common),
        "tax_monotone_in_n": _monotone("tax_balanced"),
        "tax_common_monotone_in_n": _monotone("tax_common"),
        "comparable_across_n": len({tuple(p["categories"]) for p in points}) == 1,
        "planner_constant_tokens_per_task": 60,
        "note": (
            "tokens_per_fragment is the baseline prompt's token count divided by N -- one "
            "fragment's share of the problem. Read tax_balanced and accuracy_balanced: the "
            "pooled columns beside them weight whichever category contributed most cells. "
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
        return (str(row.get("prompt_id")), row.get("rho_target"),
                row.get("n_tasks"), row.get("k"))

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
    """
    cells = [r for r in rows
             if str(r.get("condition", "")).startswith("fragmented")
             and str(r.get("category")) == category
             and _close(r.get("rho_target"), rho)
             and isinstance(r.get("coherence_tax_booook"), (int, float))]
    examined = len({(str(r.get("category")), r.get("rho_target")) for r in rows
                    if str(r.get("condition", "")).startswith("fragmented")})

    if len(cells) < 2:
        return {"declared_cell": {"category": category, "rho": rho},
                "passed": None, "n_observations": len(cells),
                "n_cells_examined": examined,
                "note": "too few observations in the declared cell to form an interval"}

    values = np.asarray([float(r["coherence_tax_booook"]) for r in cells], dtype=np.float64)
    rng = np.random.default_rng(0)
    draws = rng.choice(values, size=(4000, values.size), replace=True).mean(axis=1)
    lo, hi = (float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)))

    return {
        "declared_cell": {"category": category, "rho": rho},
        "n_observations": int(values.size),
        "n_cells_examined": examined,
        "point_estimate": round(float(values.mean()), 6),
        "ci95": [round(lo, 6), round(hi, 6)],
        "threshold": threshold,
        "passed": bool(hi < threshold),
        "note": (
            "Passes only when the upper bound of the interval clears the threshold, on a cell "
            "named before the run. The point estimate alone is what made the old criterion "
            "unfalsifiable; n_cells_examined states how many chances were available."
        ),
    }


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
    fragmented_all = [r for r in rows if r.get("condition") == "fragmented"]

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
