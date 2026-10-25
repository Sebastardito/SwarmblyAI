"""Swarmbly AI — V0 coherence-tax experiment (reference implementation).

V0 answers the project's make-or-break question **without any networking**:
how much output quality is lost by fragmenting a prompt into micro-tasks and
reassembling the answers, as a function of ``rho`` -- the contextual redundancy
ratio, i.e. how much context travels with each fragment.

Pipeline::

    privacy (tier: GLOBAL | TRUSTED | LOCAL, client-side, never networked)
           -> router -> planner (contract + DAG) -> packing (rho control)
           -> backend generation -> consensus (micro: k replicas -> confidence map)
           -> assembler (macro: select-then-splice)
           -> metrics (entity grid, BooookScore-like taxonomy, redundancy)

Assembly happens at **two levels**. The macro level joins different sub-tasks of
one task by overlap-and-splice; the micro level resolves ``k`` *complete*
replicas of the *same* micro-task, produced by different model families, by
multiple alignment and consensus. Splitting an atomic question into partial
sub-questions is supported at neither -- see :mod:`swarmbly_v0.consensus`.

Quick start::

    python -m swarmbly_v0 run --rho 1.0,1.5,2.0 --n 2,4 --k 1,3 --backend mock --out results/
    python -m swarmbly_v0 report results/results.csv --out results/report.html

.. warning::
   The default ``mock`` backend is a **harness-validation** tool. It injects the
   failure modes under study rather than performing inference, so its numbers
   validate the measurement pipeline and are **not evidence about real
   language models**. See :mod:`swarmbly_v0.backends`.
"""

from __future__ import annotations

__version__ = "0.1.0"
__license__ = "AGPL-3.0-or-later"

from .schema import (
    Assembly,
    Contract,
    Fragment,
    Packet,
    Plan,
    RouterDecision,
    SeamRecord,
    Task,
)
from .backends import (
    Backend,
    BackendUnavailable,
    Embedder,
    HashEmbedder,
    MockBackend,
    OpenAICompatBackend,
    SentenceTransformerEmbedder,
    ServerEmbedder,
    get_backend,
    get_embedder,
)
from .router import DEFAULT_THRESHOLD, evaluate_router, is_decomposable
from .planner import global_contract, plan, summarize_fragment
from .packing import build_packet, build_packets, measure_rho, packing_floor
from .assembler import select_then_splice
from .metrics import (
    ERROR_CLASSES,
    calibrate_alpha,
    calibrate_tau,
    effective_coverage,
    entity_grid,
    entity_grid_coherence,
    expected_islands,
    expected_uncovered,
    quality_judge,
    redundancy,
    required_coverage,
    seam_error_taxonomy,
)
from .consensus import (
    Column,
    ConsensusResult,
    Replica,
    Unit,
    agreement_score,
    align_multiple,
    consensus,
    segment_units,
)
from .privacy import (
    GLOBAL,
    LOCAL,
    TRUSTED,
    KDecision,
    PrivacyDecision,
    SwarmRegistry,
    TierViolation,
    UnknownSwarm,
    classify,
    detect_regulated,
    resolve_k,
    routing_metadata,
    select_tier_nodes,
)
from .experiment import PromptSpec, SweepConfig, load_prompts, run_sweep, summarize, write_csv
from .report import render_report

__all__ = [
    "__version__",
    "__license__",
    "Assembly",
    "Backend",
    "BackendUnavailable",
    "Column",
    "ConsensusResult",
    "Contract",
    "DEFAULT_THRESHOLD",
    "GLOBAL",
    "KDecision",
    "LOCAL",
    "PrivacyDecision",
    "SwarmRegistry",
    "TRUSTED",
    "TierViolation",
    "UnknownSwarm",
    "ERROR_CLASSES",
    "Embedder",
    "Fragment",
    "HashEmbedder",
    "MockBackend",
    "OpenAICompatBackend",
    "Packet",
    "Plan",
    "PromptSpec",
    "Replica",
    "RouterDecision",
    "SeamRecord",
    "SentenceTransformerEmbedder",
    "ServerEmbedder",
    "SweepConfig",
    "Task",
    "Unit",
    "agreement_score",
    "align_multiple",
    "build_packet",
    "build_packets",
    "calibrate_alpha",
    "classify",
    "detect_regulated",
    "resolve_k",
    "routing_metadata",
    "select_tier_nodes",
    "calibrate_tau",
    "consensus",
    "effective_coverage",
    "entity_grid",
    "entity_grid_coherence",
    "evaluate_router",
    "expected_islands",
    "expected_uncovered",
    "get_backend",
    "get_embedder",
    "global_contract",
    "is_decomposable",
    "load_prompts",
    "measure_rho",
    "packing_floor",
    "plan",
    "quality_judge",
    "redundancy",
    "render_report",
    "required_coverage",
    "run_sweep",
    "seam_error_taxonomy",
    "segment_units",
    "select_then_splice",
    "summarize",
    "summarize_fragment",
    "write_csv",
]
