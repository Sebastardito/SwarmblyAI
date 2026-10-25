"""Parameters of SPEC section 19.

Values marked *provisional* in the specification are not measurements of the
LCE: they are starting points derived from the literature or from stated
calculations, and the experiments of the whitepaper (section 11) must fix or
refute them. Normative values are enforced as hard limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

__all__ = ["Params", "DEFAULT"]


@dataclass(frozen=True)
class Params:
    # --- normative ---------------------------------------------------------
    capsule_max_bytes: int = 16_384
    capsule_max_topics: int = 16
    capsule_topic_max_bytes: int = 64
    capsule_statement_max_bytes: int = 8_192
    capsule_max_examples: int = 4
    capsule_example_max_bytes: int = 1_536
    response_max_capsules: int = 4
    request_min_topics: int = 1
    request_max_topics: int = 8
    request_min_bytes: int = 512
    profile_block_max_bytes: int = 1_024
    profile_max_entries: int = 16
    profile_entry_max_bytes: int = 48
    epistemic_max_share_train: int = 1
    social_train_fraction_hard: float = 0.5  # MUST stay strictly below (I3)

    # --- provisional -------------------------------------------------------
    projection_max_bytes: int = 1_024
    social_train_fraction_soft: float = 0.2  # SHOULD
    replay_fraction: float = 0.25
    general_fraction: float = 0.10
    stability_cycles: int = 3
    min_new_examples: int = 32
    n_candidates: int = 3
    gate_min_gain: float = 10.0  # points
    gate_max_loss: float = 2.0  # points
    gate_min_abstain: float = 0.8  # fraction of out-of-memory questions
    forget_max_cycles: int = 1
    affinity_tau_days: float = 30.0
    affinity_eta: float = 1.0
    affinity_beta_max: float = 0.2
    exploration_min_k: int = 3
    nm_band: tuple[float, float] = (0.5, 2.25)
    t_host_days: float = 91.0
    repair_window_days: float = 7.0
    eps_default: float = 1e-3
    eps_rare: float = 1e-4
    rare_holders_max: int = 5
    replica_budget_per_node: int = 64
    plural_min_families: int = 2

    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["nm_band"] = list(self.nm_band)
        return d


DEFAULT = Params()
