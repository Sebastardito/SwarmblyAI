"""Cognitive overhead and diversity reports (SPEC 15).

A benefit without its cost is not a result. Every experiment emits these
records; ``backend_kind`` makes it impossible to confuse a mock run with a
real one downstream.
"""

from __future__ import annotations

import json
import platform
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from . import __version__

__all__ = ["OverheadReport", "DiversityReport", "run_header"]


def run_header(backend_kind: str, backend_name: str, **extra: Any) -> dict[str, Any]:
    if backend_kind not in {"mock", "simulation", "real"}:
        raise ValueError("backend_kind must be 'mock', 'simulation' or 'real'")
    out: dict[str, Any] = {
        "lce_version": __version__,
        "backend_kind": backend_kind,
        "backend": backend_name,
        "evidence": backend_kind == "real",
        **extra,
    }
    # Las salidas simuladas/mock son reproducibles y versionadas: sin marca
    # de tiempo ni versión del intérprete (cada run_all las re-escribiría y
    # ensuciaría el árbol). Ambos campos pertenecen a las corridas reales,
    # que son evidencia.
    if backend_kind == "real":
        out["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        out["python"] = platform.python_version()
    return out


@dataclass
class OverheadReport:
    retrieval_ms: float = 0.0
    projection_ms: float = 0.0
    projection_bytes: int = 0
    lane_before: str = ""
    lane_after: str = ""
    digest_ms: float = 0.0
    train_ms: float = 0.0
    claims_proposed: int = 0
    claims_anchored: int = 0
    claims_rejected: int = 0
    candidates_trained: int = 0
    gate_result: str = ""
    capsule_bytes_in: int = 0
    capsule_bytes_out: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass
class DiversityReport:
    transmission_shares: dict[str, float] = field(default_factory=dict)
    fst: float | None = None
    generation_definition: str = "one consolidation cycle"
    canary_tail_mass: float | None = None
    canary_variant_freq: dict[str, float] = field(default_factory=dict)
    identity_violation_rate: float | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)
