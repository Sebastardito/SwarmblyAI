"""Dataclasses shared across the V0 pipeline.

These types are the contract between stages:

``router -> planner -> packing -> backend -> assembler -> metrics``

Everything is a plain dataclass so that the whole run is trivially
serialisable and diffable, which matters for a reproducibility experiment.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Mapping, Sequence

__all__ = [
    "Contract",
    "Task",
    "Plan",
    "Packet",
    "Fragment",
    "SeamRecord",
    "Assembly",
    "RouterDecision",
]


@dataclass(frozen=True)
class Contract:
    """The global contract ``Gamma`` handed to every micro-task.

    This is the object whose size drives ``rho``: every token of the contract
    replicated into every packet is a token paid ``N`` times. It is also the
    object that makes decontextualisation privacy leakage concrete (master
    document section 7), which is why its fields are explicit and few.
    """

    objective: str
    audience: str
    register: str
    output_format: str
    target_length_tokens: int
    forbidden_terms: tuple[str, ...] = ()
    canonical_entities: tuple[str, ...] = ()
    session_id: str = ""
    prompt_tokens: int = 0

    def glossary_lines(self) -> list[str]:
        """One deterministic glossary line per canonical entity."""
        return [
            f"- {entity}: canonical name; use this exact surface form."
            for entity in self.canonical_entities
        ]


@dataclass(frozen=True)
class Task:
    """A single micro-task (a node of the plan DAG)."""

    task_id: str
    instruction: str
    depends_on: tuple[str, ...] = ()
    expected_entities: tuple[str, ...] = ()
    kind: str = "section"

    @property
    def order_hint(self) -> int:
        """Numeric suffix of ``task_id`` (``t3`` -> 3), used for stable sorts."""
        digits = "".join(ch for ch in self.task_id if ch.isdigit())
        return int(digits) if digits else 0


@dataclass
class Plan:
    """A DAG of micro-tasks derived from a prompt."""

    prompt: str
    tasks: list[Task]
    sequential: bool = False

    def __post_init__(self) -> None:
        self.validate()

    @property
    def task_ids(self) -> list[str]:
        return [t.task_id for t in self.tasks]

    def by_id(self, task_id: str) -> Task:
        """Look up a task by id, raising ``KeyError`` when unknown."""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(task_id)

    def validate(self) -> None:
        """Raise ``ValueError`` on duplicate ids, unknown deps or cycles."""
        seen: set[str] = set()
        for task in self.tasks:
            if task.task_id in seen:
                raise ValueError(f"duplicate task id: {task.task_id}")
            seen.add(task.task_id)
        for task in self.tasks:
            for dep in task.depends_on:
                if dep not in seen:
                    raise ValueError(f"task {task.task_id} depends on unknown {dep}")
        # Cycle detection falls out of the level decomposition.
        self._levels(strict=True)

    def _levels(self, strict: bool) -> list[list[str]]:
        indegree = {t.task_id: len(t.depends_on) for t in self.tasks}
        dependents: dict[str, list[str]] = {t.task_id: [] for t in self.tasks}
        for task in self.tasks:
            for dep in task.depends_on:
                dependents[dep].append(task.task_id)

        order_index = {t.task_id: i for i, t in enumerate(self.tasks)}
        levels: list[list[str]] = []
        remaining = dict(indegree)
        ready = sorted([tid for tid, deg in remaining.items() if deg == 0],
                       key=lambda t: order_index[t])
        placed = 0
        while ready:
            levels.append(list(ready))
            placed += len(ready)
            nxt: list[str] = []
            for tid in ready:
                for child in dependents[tid]:
                    remaining[child] -= 1
                    if remaining[child] == 0:
                        nxt.append(child)
            ready = sorted(nxt, key=lambda t: order_index[t])
        if placed != len(self.tasks) and strict:
            raise ValueError("plan DAG contains a cycle")
        return levels

    def topological_levels(self) -> list[list[str]]:
        """Task ids grouped into dependency levels.

        Level ``k`` contains every task whose dependencies are all satisfied by
        levels ``< k``. Tasks inside a level are mutually independent and would
        be dispatched to the swarm in parallel; the number of levels is the
        critical path length that bounds achievable speedup.
        """
        return self._levels(strict=True)

    def topological_order(self) -> list[str]:
        """Flat topological order (levels concatenated, stable within level)."""
        return [tid for level in self.topological_levels() for tid in level]


@dataclass(frozen=True)
class Packet:
    """A dispatched packet ``K_i``: contract + predecessor context + task."""

    task_id: str
    text: str
    token_count: int
    context_tokens: int
    task_tokens: int
    blocks_included: tuple[str, ...] = ()
    truncated: bool = False


@dataclass
class Fragment:
    """One or more candidate generations for a single micro-task."""

    task_id: str
    candidates: list[str]
    order: int = 0
    packet_tokens: int = 0

    @property
    def best_default(self) -> str:
        return self.candidates[0] if self.candidates else ""


@dataclass(frozen=True)
class SeamRecord:
    """Diagnostics for one junction between two consecutive fragments."""

    index: int
    left_task: str
    right_task: str
    similarity: float
    tau_sem: float
    bridged: bool
    bridge_text: str = ""


@dataclass
class Assembly:
    """Result of ``select_then_splice``."""

    text: str
    seams: list[SeamRecord]
    selected: dict[str, str] = field(default_factory=dict)
    judge_scores: dict[str, float] = field(default_factory=dict)
    fragment_sentence_offsets: list[int] = field(default_factory=list)
    order: list[str] = field(default_factory=list)

    @property
    def n_bridges(self) -> int:
        return sum(1 for s in self.seams if s.bridged)

    @property
    def mean_seam_similarity(self) -> float:
        if not self.seams:
            return 1.0
        return sum(s.similarity for s in self.seams) / len(self.seams)


@dataclass(frozen=True)
class RouterDecision:
    """Output of the "is this prompt decomposable?" gate."""

    decomposable: bool
    score: float
    threshold: float
    features: Mapping[str, float]
    rationale: str

    def as_row(self) -> dict[str, object]:
        row: dict[str, object] = {
            "decomposable": self.decomposable,
            "score": round(self.score, 4),
            "threshold": self.threshold,
        }
        for key, value in self.features.items():
            row[f"feat_{key}"] = round(float(value), 4)
        return row


def summarize_ids(ids: Sequence[str], limit: int = 6) -> str:
    """Compact ``t0, t1, ... (+3 more)`` rendering used in log lines."""
    if len(ids) <= limit:
        return ", ".join(ids)
    return ", ".join(ids[:limit]) + f" (+{len(ids) - limit} more)"


# ---------------------------------------------------------------------------
# Provenance: which code produced a result
# ---------------------------------------------------------------------------

def _source_files() -> list[Path]:
    """Every .py file of the package, sorted — the thing that does the measuring.

    Only the package. Tests do not change a measurement, and scripts are entry
    points whose effect is already recorded by the arguments in the metadata.
    """
    package = Path(__file__).resolve().parent
    return sorted(p for p in package.glob("*.py") if p.name != "__pycache__")


def source_fingerprint() -> str:
    """SHA-256 over the package's source, for the run's metadata.

    A results directory that does not say what produced it cannot be trusted
    once the code moves. On 27 August three ``tables-*`` runs sat side by side --
    two scored by an arm-neutral coherence metric, one by the defective
    predecessor -- and nothing in any of them said which. The directory
    timestamp against a memory of when the fix landed was the only evidence, and
    that is not evidence.

    Hashing name-and-content in sorted order means a comment change moves the
    digest too. That is the correct trade: a digest that only moved on
    "important" changes would need someone to decide what is important, which is
    exactly the judgement this is meant to remove.
    """
    digest = hashlib.sha256()
    for path in _source_files():
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()
