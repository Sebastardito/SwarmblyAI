"""Asynchronous micro-task scheduler (SPEC §7, §11, §13).

Runs on the P2P event loop. Responsibilities:

- **Parallel dispatch.** Every task whose *consumed* predecessors are done is
  dispatched at once (bounded by ``max_concurrency``). Edges a task does not
  consume are ``statement`` edges and do not delay it (SPEC §7).
- **Family diversity.** Replicas of one task go to distinct (node, family)
  pairs, preferring families not yet used for that task, then the least
  loaded node (SPEC §11.2 MUST).
- **Redundancy bounds.** ``k_min`` replicas are dispatched up front (the
  epistemic redundancy that feeds the divergence map); hedges and retries add
  attempts up to the ceiling ``k_max`` (availability). This is the
  ``k_epist`` / ``k_avail`` split of whitepaper v2 §12.4.
- **Hedging.** The hedge timer is the observed p95 for (kind, budget) once
  enough samples exist (SPEC §11.3); until then a declared fallback is used
  and reported as such. When the elapsed time of the node and model running
  an attempt has been learned, the attempt is hedged once it runs past
  twice that time, if that comes sooner (``speed`` in ``hedge_timer``).
- **Verification before acceptance.** A result enters assembly only after its
  Ed25519 signature, attempt id and schema check pass (SPEC §10, §13). Layer-1
  commitments are not available and never simulated.
- **Cancellation semantics.** Replicas cancelled after acceptance are recorded
  as *slow*, never as *dishonest* (SPEC §11.4).
"""

from __future__ import annotations

import asyncio
import collections
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..events import EventBus
from ..node_roles import FALLBACK_ROLES, models_for_role, roles_for
from ..p2p.messages import verify_signed

MAX_RESULT_CHARS = 64_000
MIN_SAMPLES_FOR_P95 = 8
HEDGE_FACTOR = 2.0       # hedge an attempt running past 2× its learned time…
HEDGE_MARGIN_S = 1.0     # …plus a second of transport,
MIN_HEDGE_S = 2.0        # never sooner than this


class SpeedStats:
    """Observed generation speed per (node, model), shared across requests.

    On the heterogeneous network a node's largest model is not always the
    best choice: llama3.1:8b on the CPU of a 512 GB server needed more than
    60 s for one section and timed out (P3b.3'', 22 Oct 2026) while a
    3.8 B model on another node took 20–36 s. Speed is learned from accepted
    results (tokens / generation time); a timeout records an upper bound.
    """

    FAILURE_MEMORY_S = 300.0
    BUSY_BACKOFF_S = 15.0
    UNAVAILABLE_S = 60.0

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self._tps: dict[tuple[str, str], float] = {}
        self._elapsed: dict[tuple[str, str, str], float] = {}
        self._failed_at: dict[str, float] = {}
        self._busy_until: dict[str, float] = {}
        self._unavailable_until: dict[str, float] = {}

    def observe_elapsed(self, node_id: str, model: str, key: str, seconds: float) -> None:
        """Time from sending an attempt to its result, per (node, model, task
        kind and budget). Unlike tokens per second it includes how long the
        node really writes for this kind of task (a batch answer is 30 tokens
        of a 400-token budget)."""
        if seconds > 0:
            k = (node_id, model, key)
            old = self._elapsed.get(k)
            self._elapsed[k] = seconds if old is None else (
                (1 - self.alpha) * old + self.alpha * seconds)

    def observe_elapsed_floor(self, node_id: str, model: str, key: str,
                              seconds: float) -> None:
        """An attempt cancelled as slow after ``seconds``: it needs at least
        that long. Without this a node that never finishes is never learned
        (P3f.1, 22 Oct 2026: the old Mac's attempts were all cancelled, so
        every new one waited for the 30 s fallback)."""
        if seconds > 0:
            k = (node_id, model, key)
            self._elapsed[k] = max(self._elapsed.get(k, 0.0), seconds)

    def expected_elapsed(self, node_id: str, model: str, key: str) -> float | None:
        return self._elapsed.get((node_id, model, key))

    def record_failure(self, node_id: str) -> None:
        """A node that just failed (backend timeout, execution error, deadline)
        ranks below healthy ones for a few minutes (P3c.1, 22 Oct 2026: a node
        whose Ollama timed out after 31 s kept receiving tasks)."""
        self._failed_at[node_id] = time.monotonic()

    def record_success(self, node_id: str) -> None:
        self._failed_at.pop(node_id, None)
        self._busy_until.pop(node_id, None)
        self._unavailable_until.pop(node_id, None)

    def record_unavailable(self, node_id: str) -> None:
        """The worker answered that it has no inference backend (its Ollama
        is down). It cannot answer anything, so for a minute it is chosen
        only if no other worker is left (P3f.1, 22 Oct 2026: the old Mac
        failed this way five times in one batch, each time picked first as
        the "distinct machine")."""
        self._unavailable_until[node_id] = time.monotonic() + self.UNAVAILABLE_S

    def unavailable(self, node_id: str) -> bool:
        return self._unavailable_until.get(node_id, 0.0) > time.monotonic()

    def record_busy(self, node_id: str, seconds: float | None = None) -> None:
        """The worker is still busy with work it was given and gave up on:
        it refused a task as "at concurrency limit", or missed a deadline.
        P3e.1 (22 Oct 2026): after a 60 s deadline the old Mac refused five
        tries in a row, one per model family, across two requests."""
        self._busy_until[node_id] = time.monotonic() + (
            self.BUSY_BACKOFF_S if seconds is None else seconds)

    def busy(self, node_id: str) -> bool:
        return self._busy_until.get(node_id, 0.0) > time.monotonic()

    def recently_failed(self, node_id: str) -> bool:
        at = self._failed_at.get(node_id)
        return at is not None and time.monotonic() - at < self.FAILURE_MEMORY_S

    def observe(self, node_id: str, model: str, tokens: Any, gen_ms: Any) -> None:
        try:
            tokens, gen_ms = float(tokens), float(gen_ms)
        except (TypeError, ValueError):
            return
        if tokens <= 0 or gen_ms <= 0:
            return
        self._update((node_id, model), tokens / (gen_ms / 1000.0))

    def observe_timeout(self, node_id: str, model: str, max_tokens: int,
                        timeout_s: float) -> None:
        """It could not produce ``max_tokens`` in ``timeout_s``: at most that rate."""
        if timeout_s > 0 and max_tokens > 0:
            bound = max_tokens / timeout_s
            key = (node_id, model)
            self._tps[key] = min(self._tps.get(key, bound), bound)

    def _update(self, key: tuple[str, str], value: float) -> None:
        old = self._tps.get(key)
        self._tps[key] = value if old is None else (1 - self.alpha) * old + self.alpha * value

    def tokens_per_s(self, node_id: str, model: str) -> float | None:
        return self._tps.get((node_id, model))

    def estimate_s(self, node_id: str, model: str, max_tokens: int) -> float | None:
        tps = self.tokens_per_s(node_id, model)
        return None if not tps else max_tokens / tps


class RoleStats:
    """Observed per-role outcomes per node, in memory (3.5, D-018).

    A node's advertised role is a self-declared claim and is never trusted as
    proof. Placement learns from what actually happened: a node whose role
    attempt failed recently is deprioritised for that role for a while, but it
    is still chosen when no other role-capable worker is left. Nothing here is
    persisted or sent to peers.
    """

    FAILURE_MEMORY_S = 300.0

    def __init__(self) -> None:
        self._failed_at: dict[tuple[str, str], float] = {}
        self._ok: dict[tuple[str, str], int] = {}
        self._failed: dict[tuple[str, str], int] = {}

    def record_success(self, node_id: str, role: str) -> None:
        if not role:
            return
        key = (node_id, role)
        self._ok[key] = self._ok.get(key, 0) + 1
        self._failed_at.pop(key, None)

    def record_failure(self, node_id: str, role: str) -> None:
        if not role:
            return
        key = (node_id, role)
        self._failed[key] = self._failed.get(key, 0) + 1
        self._failed_at[key] = time.monotonic()

    def recently_failed(self, node_id: str, role: str) -> bool:
        at = self._failed_at.get((node_id, role))
        return at is not None and time.monotonic() - at < self.FAILURE_MEMORY_S

    def snapshot(self) -> list[dict[str, Any]]:
        """What this requester observed, for the request metadata."""
        now = time.monotonic()
        out = []
        for node_id, role in sorted(set(self._failed_at) | set(self._ok)):
            at = self._failed_at.get((node_id, role))
            out.append({"node": node_id[:12], "role": role,
                        "failed_ago_s": (round(max(0.0, now - at), 1)
                                         if at is not None else None),
                        "ok": self._ok.get((node_id, role), 0),
                        "failed": self._failed.get((node_id, role), 0)})
        return out


class LatencyStats:
    """Per (kind, budget-bucket) latency history for the p95 hedge timer."""

    def __init__(self, maxlen: int = 200):
        self._data: dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=maxlen))

    @staticmethod
    def key(kind: str, max_tokens: int) -> str:
        bucket = 128
        while bucket < max_tokens:
            bucket *= 2
        return f"{kind}:{bucket}"

    def add(self, key: str, seconds: float) -> None:
        self._data[key].append(float(seconds))

    def p95(self, key: str) -> float | None:
        values = sorted(self._data.get(key, ()))
        if len(values) < MIN_SAMPLES_FOR_P95:
            return None
        return values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))]

    def samples(self, key: str) -> int:
        return len(self._data.get(key, ()))


CANCEL_GRACE_S = 2.0   # seconds a worker keeps its slot after a timeout/cancel
CANCEL_BUSY_S = 8.0    # a slow attempt cancelled: other requests avoid the node


@dataclass
class Attempt:
    task_id: str
    number: int
    node_id: str
    family: str
    reason: str                       # initial | hedge | retry | tie_break
    attempt_id: str = ""              # wire attempt id (D-020 receipt hash)
    status: str = "dispatched"        # dispatched|accepted|extra|failed|cancelled_slow
    code: str = ""
    elapsed_ms: int | None = None
    tokens_out: int | None = None
    bytes_out: int = 0
    bytes_in: int = 0
    model: str = ""
    note: str = ""                    # e.g. the start of a rejected replica
    max_tokens: int = 0
    latency_key: str = ""
    started_at: float | None = None   # sent; reset when it leaves the slot queue
    hedged: bool = False              # already triggered a speed hedge
    # D-017: the destination class and the circle/member the receipt names.
    destination_class: str = ""
    circle_id: str = ""
    circle_name: str = ""
    member_name: str = ""
    passages: int = 0                 # document passages in this packet
    # D-018: the node role the task asked for, and whether the requester had
    # to fall back to a generic worker (large_model/reasoner only).
    role: str = ""
    role_fallback: bool = False
    # WP4b: an executor attempt (search/corpus), its public query and whether
    # the packet carries a corpus passage (egress kind PASSAGES).
    executor: str = ""
    query: str = ""
    carries_passages: bool = False
    # 3.5, WP3 / D-016: the transport hop of the send. ``direct`` is the
    # normal path; ``relayed`` names the circle relay that forwarded
    # ciphertext and saw metadata only.
    transport: str = "direct"
    relay_host: str = ""
    relay_port: int = 0

    def to_dict(self) -> dict[str, Any]:
        out = self._base()
        if self.note:
            out["note"] = self.note
        return out

    def _base(self) -> dict[str, Any]:
        return {"task": self.task_id, "attempt": self.number,
                "node": self.node_id[:12], "family": self.family,
                "model": self.model, "reason": self.reason,
                "status": self.status, "code": self.code,
                "elapsed_ms": self.elapsed_ms, "tokens_out": self.tokens_out,
                "bytes_out": self.bytes_out, "bytes_in": self.bytes_in,
                "destination_class": self.destination_class,
                "circle_id": self.circle_id, "circle_name": self.circle_name,
                "member_name": self.member_name, "passages": self.passages,
                "role": self.role,
                **({"role_fallback": True} if self.role_fallback else {}),
                **({"executor": self.executor} if self.executor else {}),
                **({"query": self.query} if self.query else {}),
                **({"carries_passages": True} if self.carries_passages else {}),
                "transport": self.transport,
                **({"relay": {"host": self.relay_host,
                              "port": self.relay_port,
                              "metadata_only": True,
                              "saw": ["who", "when", "bytes"],
                              "content": False}}
                   if self.transport == "relayed" and self.relay_host else {})}


@dataclass
class Replica:
    text: str
    node_id: str
    family: str
    model: str
    elapsed_ms: int
    telemetry: dict[str, Any] = field(default_factory=dict)
    # WP4b: provenance of executor material. The requester labels it from the
    # destination it actually sent to, never from the worker's own claim.
    sources: list[dict[str, Any]] = field(default_factory=list)
    executor: str = ""
    circle_id: str = ""
    circle_name: str = ""
    member_name: str = ""


class TaskFailed(RuntimeError):
    """A task could not produce a usable replica.

    ``reason`` is a small stable category the orchestrator can report per
    step (``role_unavailable``, ``no_worker``, ``deadline``,
    ``policy_refusal``, ``node_lost``, ``failed``); ``code`` is the last
    stable wire/policy code when there is one.
    """

    def __init__(self, message: str, *, code: str = "", reason: str = ""):
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.detail = message


def _failure_reason(codes: set[str]) -> str:
    """The honest category of a failed task, from the attempts' codes."""
    if codes & {"E_DEADLINE", "E_TIMEOUT"}:
        return "deadline"
    if codes & {"E_CIRCLE_REQUIRED", "E_EGRESS_DENIED", "E_POLICY",
                "E_TIER_VIOLATION"}:
        return "policy_refusal"
    if "E_ROLE_UNAVAILABLE" in codes:
        return "role_unavailable"
    if codes & {"E_TRANSPORT", "E_DISCONNECTED"}:
        return "node_lost"
    return "failed"


@dataclass
class StepState:
    """What happened to one step of a plan (partial results, D-019)."""

    status: str = "pending"        # pending|completed|failed|blocked
    reason: str = ""               # stable category, not user prose
    detail: str = ""               # short English detail for the record
    blocked_by: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status}
        if self.reason:
            out["reason"] = self.reason
        if self.detail:
            out["detail"] = self.detail
        if self.blocked_by:
            out["blocked_by"] = list(self.blocked_by)
        return out


@dataclass
class LevelsOutcome:
    """Results that survived, and the state of every step of the plan."""

    results: dict[str, Any] = field(default_factory=dict)
    states: dict[str, StepState] = field(default_factory=dict)

    def state(self, task_id: str) -> StepState:
        return self.states.setdefault(task_id, StepState())


class RunCancelled(RuntimeError):
    """The user stopped the request; this stays a stop, not a partial answer."""


class Scheduler:
    def __init__(self, nodes, bus: EventBus, request_id: str, *,
                 k_min: int, k_max: int, max_concurrency: int,
                 timeout_s: float, hedge_fallback_s: float,
                 latency: LatencyStats, kind: str = "generate",
                 min_params_b: float = 0.0, queue_retries: bool = True,
                 speed: SpeedStats | None = None,
                 passage_texts: list[str] | None = None,
                 role_stats: RoleStats | None = None,
                 credits: Any = None):
        self.nodes = nodes
        # Models below this size are not used (tags without a size always are).
        self.min_params_b = float(min_params_b)
        self.rejected = 0
        # False when the requester has its own model: a retry that would wait
        # behind busy workers fails fast instead, and the task runs locally
        # (P3b.3': queued retries waited 50 s and then timed out anyway).
        self.queue_retries = bool(queue_retries)
        self.speed = speed or SpeedStats()
        # D-018: per-role outcomes per node, shared across requests by the app.
        self.role_stats = role_stats or RoleStats()
        # D-020: the requester's credit service. A verified, accepted replica
        # from a circle member earns one signed receipt; nothing else does.
        self.credits = credits
        # D-017: the list recipe passes the texts it attached; each attempt
        # records how many of them its packet really carried.
        self.passage_texts = [str(text) for text in (passage_texts or []) if text]
        self._max_tokens = 0          # budget of the task being dispatched
        # After a timeout or a cancelled hedge the worker may still be
        # finishing (older workers ignore "cancel"): keep its slot for a
        # short grace period instead of sending it work it would refuse.
        self._busy_until: dict[str, float] = {}
        self.bus = bus
        self.request_id = request_id
        self.k_min = max(1, int(k_min))
        self.k_max = max(self.k_min, int(k_max))
        self.timeout_s = float(timeout_s)
        self.hedge_fallback_s = float(hedge_fallback_s)
        self.latency = latency
        self.kind = kind
        self._sem = asyncio.Semaphore(max(1, int(max_concurrency)))
        self._slots: dict[str, asyncio.Semaphore] = {}
        self.attempts: list[Attempt] = []
        self.hedges = 0
        # Models whose replica failed the quality check in this request: for
        # the request's other tasks they come after the rest (P3k.1: phi3.5
        # echoed items 7–12 and 19–24, and the tie-break went to phi3.5 again).
        self.rejected_models: set[str] = set()
        self.retries = 0
        self.timeouts = 0
        self.hedge_timer_source: set[str] = set()
        self._load: collections.Counter = collections.Counter()
        self._pair_load: collections.Counter = collections.Counter()  # (node, family)
        self._pair_used: collections.Counter = collections.Counter()  # spread over time

    # -- worker selection -------------------------------------------------------
    def _candidates(self, role: str = "", require_passages: bool = False
                    ) -> list[tuple[Any, str, str]]:
        """(peer, family, model): per worker and family, its largest eligible model.

        Capability (parameter count from the tag) decides *which* model of a
        family a node runs; models below ``min_params_b`` are skipped. If that
        filter would leave no candidate at all, every model is allowed again
        (a small swarm must still answer).

        With ``role`` (D-018) only workers that advertise it are candidates,
        and for a model-bearing role only the models named by that role.
        """
        from .capability import eligible, rank_params

        def collect(min_b: float) -> list[tuple[Any, str, str]]:
            out = []
            for peer in self.nodes.available_workers(self.kind):
                if require_passages and not self._passages_allowed(peer.node_id):
                    continue
                if role:
                    entries = [entry for entry in (peer.advertisement.get("roles") or [])
                               if isinstance(entry, dict) and entry.get("role") == role]
                    if not entries:
                        continue
                    role_models = set(models_for_role(peer.advertisement, role))
                else:
                    role_models = set()
                best: dict[str, str] = {}
                for model in (peer.advertisement.get("models") or [{"family": "unknown"}]):
                    family = str(model.get("family") or "unknown")
                    version = str(model.get("version") or "")
                    if version and role_models and version not in role_models:
                        continue
                    if version and not eligible(version, min_b):
                        continue
                    if family not in best or rank_params(version) > rank_params(best[family]):
                        best[family] = version
                out.extend((peer, family, version) for family, version in best.items())
            return out

        return collect(self.min_params_b) or collect(0.0)

    def _passages_allowed(self, node_id: str) -> bool:
        """Whether document passages may be forwarded to this worker.

        Corpus results from a role executor are the requester's passages for
        egress purposes: they may reach the local pool, or a circle peer whose
        per-circle ``circle_passages`` switch is on (own-devices uses its own
        switch). A Directory that cannot answer is treated as refusing.
        """
        fn = getattr(self.nodes, "passages_allowed", None)
        if not callable(fn):
            return True                # unit-test doubles without a policy
        try:
            return bool(fn(node_id))
        except Exception:
            return False

    def _capacity(self, peer) -> int:
        try:
            return max(1, int((peer.advertisement.get("policy") or {})
                              .get("max_concurrent") or 1))
        except (TypeError, ValueError):
            return 1

    def _select(self, used_pairs: set[tuple[str, str]], used_families: set[str],
                used_nodes: set[str], free_only: bool = False,
                max_tokens: int | None = None, role: str = "",
                require_passages: bool = False):
        """Best (peer, family, model). ``free_only``: only workers with a free
        slot — a hedge queued behind a busy worker adds load and saves no
        time (P3b.3, 22 Oct 2026: after the server left, hedges queued on the
        two remaining single-slot workers and every task missed its deadline)."""
        best = None
        best_key = None
        for peer, family, model in self._candidates(role, require_passages):
            if (peer.node_id, family) in used_pairs:
                continue
            busy = self.speed.busy(peer.node_id)
            if free_only and (busy or self._load[peer.node_id] >= self._capacity(peer)):
                continue
            from .capability import rank_params
            estimate = self.speed.estimate_s(
                peer.node_id, model, max_tokens if max_tokens is not None else self._max_tokens)
            expected = self.speed.expected_elapsed(
                peer.node_id, model, LatencyStats.key(self.kind, max_tokens
                                                      if max_tokens is not None
                                                      else self._max_tokens))
            too_slow = ((estimate is not None and estimate > 0.9 * self.timeout_s)
                        or (expected is not None and expected >= self.hedge_fallback_s))
            key = (self.speed.unavailable(peer.node_id),   # no backend: last resort
                   family in used_families,           # diversity first (MUST)
                   peer.node_id in used_nodes,         # then distinct machines
                   model in self.rejected_models,      # then not just rejected
                   self._load[peer.node_id] + peer.tasks_inflight
                   + (self._capacity(peer) if busy else 0),
                   too_slow,                           # then: can it finish in time?
                   self.speed.recently_failed(peer.node_id),   # and is it healthy?
                   # D-018: a role that failed here recently goes after the
                   # nodes this requester has not seen fail that role.
                   self.role_stats.recently_failed(peer.node_id, role) if role else False,
                   -rank_params(model),                # then the most capable model
                   self._pair_load[(peer.node_id, family)],
                   self._pair_used[(peer.node_id, family)],  # spread across models
                   peer.rtt_ms if peer.rtt_ms is not None else 1e9,
                   peer.node_id, family)
            if best_key is None or key < best_key:
                best, best_key = (peer, family, model), key
        return best

    # -- one task ---------------------------------------------------------------
    async def run_task(self, task_id: str, build: Callable[..., dict],
                       max_tokens: int,
                       validate: Callable[[str], bool] | None = None, *,
                       k_min: int | None = None, k_max: int | None = None,
                       exclude: set[tuple[str, str]] | None = None,
                       start_number: int = 0,
                       reason: str = "initial",
                       free_only: bool = False,
                       role: str = "", require_passages: bool = False
                       ) -> list[Replica]:
        """Dispatch replicas of one task; return ≥1 verified replica or raise.

        ``validate`` rejects a signed, well-formed replica whose content is
        unusable (e.g. a batch answered by echoing its items): the attempt is
        recorded as ``rejected`` (``E_QUALITY``) and another node is tried,
        within ``k_max``. If every replica is rejected, the rejected ones are
        returned rather than failing the request (the monitor shows it).
        """
        rejected: list[tuple[Replica, Attempt]] = []
        # D-018: only a worker that advertises the role may receive a role
        # task. If none does, large_model/reasoner may degrade to the best
        # generic worker (recorded); search/corpus cannot be substituted and
        # the task fails instead of pretending.
        requested_role = str(role or "")
        role_fallback = False
        effective_role = requested_role
        if requested_role:
            if requested_role not in ("large_model", "reasoner", "search", "corpus"):
                raise TaskFailed(
                    f"{task_id}: role {requested_role!r} unavailable: unknown role",
                    code="E_ROLE_UNAVAILABLE", reason="role_unavailable")
            if not self._candidates(requested_role, require_passages):
                if requested_role not in FALLBACK_ROLES:
                    raise TaskFailed(
                        f"{task_id}: role {requested_role!r} unavailable: no worker "
                        "advertises it", code="E_ROLE_UNAVAILABLE",
                        reason="role_unavailable")
                role_fallback = True
                effective_role = ""
        k_min = self.k_min if k_min is None else int(k_min)
        k_max = self.k_max if k_max is None else int(k_max)
        used_pairs: set[tuple[str, str]] = set(exclude or ())
        used_families: set[str] = {family for _, family in used_pairs}
        used_nodes: set[str] = {node for node, _ in used_pairs}
        accepted: list[Replica] = []
        inflight: dict[asyncio.Task, Attempt] = {}
        number = int(start_number)
        k_max += number            # attempt numbers continue an earlier round
        latency_key = LatencyStats.key(self.kind, max_tokens)
        self._max_tokens = int(max_tokens)

        def launch(reason: str, free_only: bool = False) -> bool:
            nonlocal number
            if number >= k_max:
                return False
            choice = self._select(used_pairs, used_families, used_nodes,
                                  free_only=free_only or reason == "hedge",
                                  max_tokens=max_tokens, role=effective_role,
                                  require_passages=require_passages)
            if choice is None:
                return False
            peer, family, model = choice
            used_pairs.add((peer.node_id, family))
            used_families.add(family)
            used_nodes.add(peer.node_id)
            multi = len(peer.advertisement.get("models") or []) > 1
            message = build(number, family if multi else None, model if multi else None)
            constraints = message.setdefault("constraints", {})
            if effective_role:
                # MINOR-safe packet extension (SPEC §3): older workers ignore
                # it; a worker that knows it refuses an unadvertised role.
                constraints["role"] = effective_role
                if effective_role == "reasoner":
                    # think travels only when the chosen worker advertised it;
                    # a model without the capability is announced without it
                    # (or not at all), so the role never widens a call.
                    entry = next((item for item in roles_for(
                        peer.advertisement, "reasoner")
                        if model is None or item.get("model") == model), None)
                    if entry is not None and entry.get("think") is True:
                        constraints["think"] = True
                    else:
                        constraints.pop("think", None)
            elif role_fallback:
                # The generic worker must not be sent a role it never claimed.
                constraints.pop("role", None)
                constraints.pop("think", None)
            if require_passages:
                # MINOR-safe: the peer send carries a corpus passage, so the
                # egress ledger records PASSAGES and the receipt says so.
                constraints["carries_passages"] = True
            packet_text = str(message)
            attempt = Attempt(task_id, number, peer.node_id, family, reason,
                              model=model,
                              bytes_out=len(packet_text),
                              max_tokens=int(max_tokens), latency_key=latency_key,
                              started_at=time.monotonic(),
                              passages=sum(1 for text in self.passage_texts
                                           if text in packet_text),
                              role=requested_role, role_fallback=role_fallback,
                              executor=(requested_role if requested_role in
                                        ("search", "corpus") else ""),
                              query=(str((message.get("task") or {}).get("instruction") or "")
                                     if requested_role == "search" else ""),
                              carries_passages=require_passages)
            if role_fallback:
                attempt.note = (f"role {requested_role} unavailable, ran on "
                                f"{peer.node_id[:12]} (generic worker)")
            number += 1
            self.attempts.append(attempt)
            self._load[peer.node_id] += 1
            self._pair_load[(peer.node_id, family)] += 1
            self._pair_used[(peer.node_id, family)] += 1
            task = asyncio.ensure_future(self._dispatch_one(peer.node_id, message,
                                                            attempt))
            inflight[task] = attempt
            self._event(attempt, "dispatched")
            return True

        for _ in range(k_min):
            if not launch(reason, free_only=free_only):
                break
        if not inflight:
            raise TaskFailed(f"{task_id}: no connected worker available",
                             code="E_NO_WORKER", reason="no_worker")

        while inflight and len(accepted) < k_min:
            hedge_after, source, late = self._hedge_after(list(inflight.values()),
                                                          latency_key)
            can_hedge = number < k_max
            if can_hedge:
                self.hedge_timer_source.add(source)
            done, _ = await asyncio.wait(
                set(inflight), timeout=hedge_after if can_hedge else None,
                return_when=asyncio.FIRST_COMPLETED)
            if not done:
                if late is not None:
                    late.hedged = True
                if launch("hedge"):
                    self.hedges += 1
                continue
            for finished in done:
                attempt = inflight.pop(finished)
                self._load[attempt.node_id] -= 1
                self._pair_load[(attempt.node_id, attempt.family)] -= 1
                replica = finished.result()
                if replica is not None and validate is not None:
                    try:
                        usable = bool(validate(replica.text))
                    except Exception:
                        usable = True
                    if not usable:
                        attempt.status, attempt.code = "rejected", "E_QUALITY"
                        self.rejected_models.add(attempt.model)
                        attempt.note = " ".join(replica.text.split())[:160]
                        explain = getattr(validate, "explain", None)
                        if explain is not None:
                            try:
                                attempt.note = f"[{explain(replica.text)}] {attempt.note}"[:240]
                            except Exception:
                                pass
                        self.rejected += 1
                        rejected.append((replica, attempt))
                        self._event(attempt, "rejected")
                        # A rejected replica says nothing about the workers'
                        # health, and the local model tends to fail the same
                        # way (P3e.1: two echoes, no free worker, no retry,
                        # the local rescue echoed too): this retry may queue.
                        if len(accepted) + len(inflight) < k_min and launch("retry"):
                            self.retries += 1
                        continue
                if replica is not None:
                    attempt.status = "accepted"
                    accepted.append(replica)
                    self.latency.add(latency_key, replica.elapsed_ms / 1000.0)
                    self._event(attempt, "accepted")
                    # Only now, after signature/schema verification and the
                    # quality check, does the requester accept the result and
                    # sign a credit receipt for a circle member (D-020).
                    if self.credits is not None:
                        try:
                            await self.credits.issue_for_attempt(attempt, replica)
                        except Exception:
                            pass
                else:
                    self._event(attempt, "failed")
                    if len(accepted) + len(inflight) < k_min and launch("retry", free_only=not self.queue_retries):
                        self.retries += 1

        for task, attempt in inflight.items():
            task.cancel()
            self._load[attempt.node_id] -= 1
            self._pair_load[(attempt.node_id, attempt.family)] -= 1
            attempt.status = "cancelled_slow"   # slow, not dishonest (SPEC §11.4)
            if attempt.role and not attempt.role_fallback:
                self.role_stats.record_failure(attempt.node_id, attempt.role)
            if attempt.started_at is not None:
                ran = time.monotonic() - attempt.started_at
                self.speed.observe_elapsed_floor(attempt.node_id, attempt.model,
                                                 attempt.latency_key, ran)
                if ran >= MIN_HEDGE_S:
                    # It may keep its slot while it stops (a slow CPU cannot
                    # stop mid prompt): P3f.1, refused 84 ms later.
                    self.speed.record_busy(attempt.node_id, CANCEL_BUSY_S)
            self._event(attempt, "cancelled_slow")
        if not accepted and rejected:
            # Degraded, but an answer: the attempts say so ("degraded").
            for replica, attempt in rejected:
                attempt.status = "degraded"
                replica.telemetry = dict(replica.telemetry or {}, degraded=True)
            return [replica for replica, _ in rejected]
        if not accepted:
            codes = {a.code for a in self.attempts
                     if a.task_id == task_id and a.code}
            joined = ", ".join(sorted(codes))
            raise TaskFailed(
                f"{task_id}: all {number} attempt(s) failed ({joined})",
                code=next(iter(codes), ""), reason=_failure_reason(codes))
        return accepted

    def _hedge_after(self, attempts: list[Attempt], latency_key: str):
        """Seconds to wait before hedging, its source, and the attempt it is for.

        The p95 for (kind, budget), or the fallback, is the ceiling. On a
        heterogeneous swarm one figure fits no node: a gemma2:2b answers a
        batch in 1–2 s and llama3.1:8b on a CPU in 6–12 s, so the fixed 30 s
        fallback let a stuck fast node hold a task for 30 s (P3d, 22 Oct 2026).
        With a learned elapsed time for an attempt's node and model, that
        attempt is hedged at ``HEDGE_FACTOR`` × that time; each attempt
        triggers at most one such hedge.
        """
        p95 = self.latency.p95(latency_key)
        base = p95 if p95 is not None else self.hedge_fallback_s
        source = "p95" if p95 is not None else "fallback"
        now = time.monotonic()
        best, late = None, None
        for attempt in attempts:
            if attempt.hedged or attempt.started_at is None:
                continue
            expected = self.speed.expected_elapsed(attempt.node_id, attempt.model,
                                                   latency_key)
            if expected is None:
                continue
            due = attempt.started_at + HEDGE_FACTOR * expected + HEDGE_MARGIN_S - now
            if best is None or due < best:
                best, late = due, attempt
        if best is not None and best < base:
            return max(MIN_HEDGE_S, best), "speed", late
        return base, source, None

    def _slot(self, node_id: str) -> asyncio.Semaphore:
        """Respect each worker's advertised capacity: queue here rather than
        send a task the worker would refuse as over its limit."""
        if node_id not in self._slots:
            peer = self.nodes.peers.get(node_id)
            try:
                cap = int(((peer.advertisement if peer else {}).get("policy") or {})
                          .get("max_concurrent") or 1)
            except (TypeError, ValueError):
                cap = 1
            self._slots[node_id] = asyncio.Semaphore(max(1, cap))
        return self._slots[node_id]

    def _record_transport(self, attempt: Attempt) -> None:
        try:
            hop = self.nodes.transport_hop(attempt.node_id)
        except Exception:
            hop = {"transport": "direct"}
        attempt.transport = str(hop.get("transport") or "direct")
        relay = hop.get("relay") or {}
        attempt.relay_host = str(relay.get("host") or "")
        try:
            attempt.relay_port = int(relay.get("port") or 0)
        except (TypeError, ValueError):
            attempt.relay_port = 0

    async def _dispatch_one(self, node_id: str, message: dict[str, Any],
                            attempt: Attempt) -> Replica | None:
        started = time.monotonic()
        attempt.attempt_id = str(message.get("attempt_id", "") or "")
        # D-020: offer one earned credit only to a worker this requester knows
        # is busy (it refused a task at its concurrency limit, or missed a
        # deadline); spending a receipt on an idle worker buys nothing.
        offer_credit = self.speed.busy(node_id)
        async with self._slot(node_id), self._sem:
            wait = self._busy_until.get(node_id, 0.0) - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            attempt.started_at = time.monotonic()
            try:
                destination = self.nodes.classify_peer(node_id)
            except Exception:
                destination = {}
            attempt.destination_class = str(destination.get("clase") or "")
            attempt.circle_id = str(destination.get("circle_id") or "")
            attempt.circle_name = str(destination.get("circle_name") or "")
            attempt.member_name = str(destination.get("member_name") or "")
            self._record_transport(attempt)
            try:
                if offer_credit:
                    result = await self.nodes.dispatch_async(
                        node_id, message, self.timeout_s, offer_credit=True)
                else:
                    result = await self.nodes.dispatch_async(node_id, message,
                                                             self.timeout_s)
                self._record_transport(attempt)
            except asyncio.CancelledError:
                self._busy_until[node_id] = time.monotonic() + CANCEL_GRACE_S
                raise
            except Exception as exc:
                self._record_transport(attempt)
                attempt.status = "failed"
                attempt.code = getattr(exc, "code", "") or "E_TRANSPORT"
                attempt.note = str(getattr(exc, "detail", "") or exc)[:160]
                if attempt.code in ("E_CIRCLE_REQUIRED", "E_EGRESS_DENIED"):
                    # D-017: the gate refused before the write; no bytes left.
                    attempt.bytes_out = 0
                    attempt.passages = 0
                if attempt.code in ("E_EXECUTION", "E_DEADLINE", "E_TRANSPORT"):
                    self.speed.record_failure(node_id)
                if "backend unavailable" in attempt.note.lower():
                    self.speed.record_unavailable(node_id)
                if attempt.code == "E_DEADLINE" or (
                        attempt.code == "E_POLICY" and "concurrency" in attempt.note):
                    self.speed.record_busy(node_id)
                if attempt.code == "E_DEADLINE":
                    self._busy_until[node_id] = time.monotonic() + CANCEL_GRACE_S
                    self.timeouts += 1
                    self.speed.observe_timeout(node_id, attempt.model,
                                               attempt.max_tokens or self._max_tokens,
                                               self.timeout_s)
                if attempt.role and not attempt.role_fallback:
                    self.role_stats.record_failure(node_id, attempt.role)
                attempt.elapsed_ms = int((time.monotonic() - started) * 1000)
                return None
        attempt.elapsed_ms = int((time.monotonic() - started) * 1000)
        attempt.bytes_in = len(str(result))
        problem = verify_result(node_id, message, result)
        if problem:
            attempt.status = "failed"
            attempt.code = problem
            if attempt.role and not attempt.role_fallback:
                self.role_stats.record_failure(node_id, attempt.role)
            return None
        profile = result.get("profile") or {}
        telemetry = result.get("telemetry") or {}
        attempt.tokens_out = telemetry.get("tokens_out")
        # A cold model load is not generation speed: P3k.1 (23 Oct 2026),
        # the first request after a restart took 25 s on two nodes and their
        # largest models were then ranked too slow and skipped.
        try:
            load_s = max(0.0, float(telemetry.get("load_ms") or 0) / 1000.0)
        except (TypeError, ValueError):
            load_s = 0.0
        gen_ms = telemetry.get("gen_ms")
        if isinstance(gen_ms, (int, float)) and load_s:
            gen_ms = max(1.0, gen_ms - load_s * 1000.0)
        self.speed.observe(node_id, str(profile.get("model_version") or attempt.model),
                           telemetry.get("tokens_out"), gen_ms)
        self.speed.record_success(node_id)
        if attempt.role and not attempt.role_fallback:
            self.role_stats.record_success(node_id, attempt.role)
        if attempt.latency_key and attempt.started_at is not None:
            self.speed.observe_elapsed(node_id, attempt.model, attempt.latency_key,
                                       max(0.1, time.monotonic() - attempt.started_at
                                           - load_s))
        attempt.model = str(profile.get("model_version") or attempt.model)
        family = str(profile.get("model_family") or attempt.family)
        sources = result.get("sources") if isinstance(result.get("sources"), list) else []
        return Replica(text=str(result["text"]), node_id=node_id, family=family,
                       model=attempt.model, elapsed_ms=attempt.elapsed_ms,
                       telemetry=telemetry, sources=sources[:8],
                       executor=str(result.get("executor") or ""),
                       circle_id=attempt.circle_id, circle_name=attempt.circle_name,
                       member_name=attempt.member_name)

    def _event(self, attempt: Attempt, status: str) -> None:
        self.bus.publish("swarm.attempt", request_id=self.request_id,
                         **attempt.to_dict(), event=status)


def verify_result(node_id: str, packet: dict[str, Any], result: dict[str, Any]) -> str:
    """Return an error code if the result must not enter assembly, else ''."""
    if result.get("type") != "result":
        return "E_SCHEMA"
    if result.get("attempt_id") != packet.get("attempt_id"):
        return "E_SCHEMA"
    if not verify_signed(node_id, result):
        return "E_VERIFY_FAILED"
    text = result.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_RESULT_CHARS:
        return "E_SCHEMA"
    sources = result.get("sources")
    if sources is not None:
        if not isinstance(sources, list) or len(sources) > 8:
            return "E_SCHEMA"
        for source in sources:
            if not isinstance(source, dict):
                return "E_SCHEMA"
            for key in ("title", "span", "cite", "url", "snippet", "text", "provider"):
                value = source.get(key)
                if value is not None and (not isinstance(value, str) or len(value) > 2000):
                    return "E_SCHEMA"
    return ""


async def run_levels(scheduler: Scheduler, order: list[str],
                     consumed_deps: dict[str, tuple[str, ...]],
                     run_one: Callable[[str], Awaitable[Any]], *,
                     outcome: LevelsOutcome | None = None,
                     deadline: float | None = None,
                     cancel: Any = None) -> LevelsOutcome:
    """Run tasks as soon as their consumed predecessors are done.

    A step that cannot be completed does not abort the whole plan (3.5,
    D-019): its state is recorded, every step that depends on it is marked
    ``blocked`` and never run, and independent steps continue. ``cancel``
    (the user's stop) still raises :class:`RunCancelled`; the caller turns
    that into a stop, never into a partial answer. ``deadline`` is a
    ``time.monotonic()`` backstop: steps still waiting or running then are
    marked failed with reason ``deadline``.
    """
    out = outcome if outcome is not None else LevelsOutcome()
    for task_id in order:
        out.state(task_id)
    remaining = list(order)
    running: dict[asyncio.Task, str] = {}

    def mark_missing(reason: str, detail: str, tasks: list[str]) -> None:
        for task_id in tasks:
            state = out.state(task_id)
            if state.status == "pending":
                state.status, state.reason, state.detail = "failed", reason, detail

    try:
        while remaining or running:
            if cancel is not None and cancel.is_set():
                raise RunCancelled()
            if deadline is not None and time.monotonic() >= deadline:
                mark_missing("deadline", "the run exceeded its global deadline",
                             list(remaining))
                remaining.clear()
                for task in list(running):
                    task.cancel()
                mark_missing("deadline", "the run exceeded its global deadline",
                             list(running.values()))
                running.clear()
                break
            # Dependencies that will never complete block their dependents;
            # a blocked step is named with the step that blocked it, not run.
            for task_id in list(remaining):
                deps = consumed_deps.get(task_id, ())
                blocked = [dep for dep in deps
                           if dep in out.states
                           and out.states[dep].status in ("failed", "blocked")]
                if blocked:
                    state = out.state(task_id)
                    state.status, state.reason = "blocked", "blocked"
                    state.blocked_by = tuple(blocked)
                    state.detail = ("depends on " + ", ".join(blocked))
                    remaining.remove(task_id)
            ready = [t for t in remaining
                     if all(d in out.results for d in consumed_deps.get(t, ()))]
            for task_id in ready:
                remaining.remove(task_id)
                running[asyncio.ensure_future(run_one(task_id))] = task_id
            if not running:
                if remaining:
                    # No runnable step and no dependency that could explain
                    # it: this plan cannot make progress.
                    mark_missing("blocked",
                                 "the plan has unsatisfiable dependencies",
                                 list(remaining))
                    remaining.clear()
                break
            timeout = None
            if cancel is not None or deadline is not None:
                timeout = 0.2
            done, _ = await asyncio.wait(set(running), timeout=timeout,
                                         return_when=asyncio.FIRST_COMPLETED)
            if not done:
                continue
            for finished in done:
                task_id = running.pop(finished)
                try:
                    value = finished.result()
                    if value is None:
                        # A step is completed only when something produced its
                        # output; a bare success with no result is a failure.
                        state = out.state(task_id)
                        state.status, state.reason = "failed", "failed"
                        state.detail = "the step produced no output"
                        continue
                    out.results[task_id] = value
                except asyncio.CancelledError:
                    out.state(task_id).status = "failed"
                    out.state(task_id).reason = "cancelled"
                except TaskFailed as exc:
                    state = out.state(task_id)
                    state.status, state.reason = "failed", (exc.reason or "failed")
                    state.detail = str(exc)[:240]
                except Exception as exc:  # a bug or a backend seam: one step, not all
                    state = out.state(task_id)
                    state.status, state.reason = "failed", "failed"
                    state.detail = str(exc)[:240]
                else:
                    out.state(task_id).status = "completed"
    finally:
        for task in running:
            task.cancel()
    return out
