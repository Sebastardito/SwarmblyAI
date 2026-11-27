"""Worker role (product spec §7.4): voluntarily serve micro-tasks.

Every gate is enforced in code, not in the UI: worker disabled → refuse;
LAN/internet scopes; lane/tier; task kind and token budget; concurrency
limit; idle-only mode; deadline. Execution is wrapped in LCE ``WorkerGuard``
(invariant I2: serve the base model, never a personal adapter, never retain
task content).

``deadline_ms`` is read as a **duration** from receipt (as in the SPEC §8
example), so nodes with unsynchronised clocks interoperate; generation is cut
when it expires. ``constraints.model_family`` (Swarmbly App extension, ignored
by implementations that do not know it, SPEC §3) lets an orchestrator ask a
multi-model worker for a specific family; the result's ``profile`` always
reports the model actually used (SPEC §10).
"""

from __future__ import annotations

import asyncio
import collections
import functools
import threading
import time
from typing import Any, Callable

from ..config import Config
from ..db import Database
from ..events import EventBus
from ..identity import IdentityManager
from ..inference.base import Interrupted, StreamBackend
from ..lce_adapter import LCEAdapter
from ..models import family_for
from ..node_roles import (derive_roles, models_for_role, search_engines,
                         search_enabled)
from .messages import canonical_bytes, error, result

ALLOWED_KINDS = ("extract", "classify", "generate", "summarize",
                 "transform", "judge")
MAX_DEADLINE_MS = 10 * 60 * 1000
E_ROLE_UNAVAILABLE = "E_ROLE_UNAVAILABLE"
# WP4b bounds: a public query, never a document; bounded results and passages.
MAX_SEARCH_QUERY_CHARS = 200
MAX_SEARCH_QUERY_WORDS = 32
MAX_SEARCH_RESULTS = 5
MAX_CORPUS_QUERY_CHARS = 2000
MAX_CORPUS_PASSAGES = 5
MAX_CORPUS_TEXT_CHARS = 1000


def _refused_thinking(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return "does not support thinking" in text or "thinking is not supported" in text


class PromptBackend:
    """Adapts a StreamBackend to the ServingBackend protocol used by the LCE
    WorkerGuard: exposes ``model`` and ``generate(prompt, **kw)``."""

    def __init__(self, stream: StreamBackend, model: str,
                 interrupt: Callable[[], bool] | None = None):
        self._stream = stream
        self.model = model
        self.adapter = None  # invariant I2: no personal adapter on workers
        self._interrupt = interrupt
        self.last = None
        self.applied_think: bool | None = None

    def generate(self, prompt: str, **kw: Any) -> str:
        call: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kw.get("max_tokens", 800),
            "temperature": kw.get("temperature", 0.2),
            "interrupt": self._interrupt,
        }
        # 3.5, D-018: a reasoner packet carries think: true. Only a backend
        # that accepts the parameter receives it; the others keep today's
        # behaviour (the prompt is unchanged and nothing is faked).
        think = kw.get("think")
        if isinstance(think, bool) and getattr(self._stream, "accepts_think", False):
            call["think"] = think
            self.applied_think = think
        try:
            out = self._stream.stream_chat(
                [{"role": "user", "content": prompt}], **call)
        except Exception as exc:
            # A model that does not support thinking refuses the flag with
            # HTTP 400.  Retry once without it and record that think was not
            # used; the task still runs, and the profile says so.
            if "think" not in call or not _refused_thinking(exc):
                raise
            call.pop("think", None)
            self.applied_think = False
            out = self._stream.stream_chat(
                [{"role": "user", "content": prompt}], **call)
        self.last = out
        return out.text


def model_family(name: str) -> str:
    """Family of an Ollama-style tag: ``llama3.2:3b`` → ``llama3.2``."""
    return (name or "").split(":")[0].split("/")[-1] or "unknown"


class WorkerService:
    def __init__(self, config: Config, db: Database, bus: EventBus,
                 identity: IdentityManager, lce: LCEAdapter,
                 backend_factory, model_info: Callable[[str], dict] | None = None,
                 circle_guard: Callable[[str], tuple[bool, str, str]] | None = None,
                 role_provider: Callable[..., list[dict[str, Any]]] | None = None,
                 circle_for: Callable[..., dict[str, Any] | None] | None = None,
                 project_provider: Callable[[str], Any] | None = None,
                 credits: Any = None):
        self.config = config
        self.db = db
        self.bus = bus
        self.identity = identity
        self.lce = lce
        self.backend_factory = backend_factory  # () -> StreamBackend
        self.model_info = model_info or (lambda name: {})
        # D-015: the worker gate asks the circle service again, so revocation
        # takes effect even on an already-open session.
        self.circle_guard = circle_guard or (lambda node_id: (True, "", ""))
        # WP4b: executors need the app's resolved roles, circles and projects;
        # the defaults keep a headless/test worker usable without AppState.
        self.role_provider = role_provider
        self.circle_for = circle_for or (lambda node_id, allowed=None: None)
        self.project_provider = project_provider or (lambda project_id: None)
        # D-020: a validated credit_spend marker for one exact attempt. It
        # can only change queue order while this worker is busy.
        self.credits = credits
        # A test seam for the public engines: no real network in unit tests.
        self.search_fetch: Callable[..., Any] | None = None
        self._tasks_now = 0
        self._priority_waiters = 0
        self._lock = threading.Lock()
        self._ledger_lock = threading.Lock()
        # What this node did on behalf of peers (public search, shared corpus),
        # bounded like the worker counters; never model/task content.
        self._worker_ledger: collections.deque = collections.deque(maxlen=200)
        # (requesting node, attempt_id) -> cancel flag checked between tokens
        self._cancels: dict[tuple[str, str], threading.Event] = {}

    # -- node roles (3.5, D-018) --------------------------------------------------
    def node_roles(self, models: list[str] | None = None, *,
                   remote: bool = True) -> list[dict[str, Any]]:
        """Roles this worker can run for ``models`` (default: what it shares)."""
        offered = self.shared_models() if models is None else list(models)
        if self.role_provider is not None:
            return self.role_provider(offered, announce=True, remote=remote)
        return derive_roles(offered, self.config.all(), announce=True)

    def role_names(self, models: list[str] | None = None, *,
                   remote: bool = True) -> set[str]:
        return {str(role.get("role")) for role in self.node_roles(
            models, remote=remote) if isinstance(role, dict)}

    def _role_models(self, role: str, models: list[str]) -> list[str]:
        advertisement = {
            "models": [{"version": name} for name in models],
            "roles": self.node_roles(models),
        }
        return models_for_role(advertisement, role)

    def ledger_events(self) -> list[dict[str, Any]]:
        """The executor ledger this node kept (public searches, corpus sends)."""
        with self._ledger_lock:
            return [dict(event) for event in self._worker_ledger]

    def _remember_ledger(self, events: list[dict[str, Any]]) -> None:
        with self._ledger_lock:
            for event in events:
                self._worker_ledger.append(dict(event))
        if events:
            self.bus.publish("worker.egress", events=[dict(e) for e in events])

    # -- policy -----------------------------------------------------------------
    def shared_models(self) -> list[str]:
        """Models this node offers to third parties (never a personal adapter)."""
        cfg = self.config.all()
        from .. import egress
        shared = [m for m in (cfg["swarm"].get("worker_models") or []) if m]
        if not shared and cfg["model"].get("model_name"):
            shared = [cfg["model"]["model_name"]]
        # an Ollama cloud model would send other nodes' fragments to ollama.com
        return [m for m in shared if not egress.cloud_host_by_name(m)]

    def policy(self) -> dict[str, Any]:
        from .. import egress
        full = self.config.all()
        cfg = full["swarm"]
        # 3.0.1: a node whose model is a third-party service never serves the
        # swarm: other nodes' fragments would go to an organisation they never
        # chose, and the key's owner would pay for them.
        third_party = egress.model_destination(full)["clase"] == egress.THIRD_PARTY
        enabled = bool(cfg.get("worker_enabled")) and bool(self.shared_models()) \
            and not third_party
        return {
            "enabled": enabled,
            "allow_lan": bool(cfg.get("worker_allow_lan", True)),
            "allow_internet": bool(cfg.get("worker_allow_internet", False)),
            "max_concurrent": max(1, int(cfg.get("worker_max_concurrent", 1))),
            "max_tokens_per_task": int(cfg.get("worker_max_tokens_per_task", 800)),
            "max_task_seconds": int(cfg.get("worker_max_task_seconds", 120)),
            # Advertised kinds are empty while the worker role is off, so
            # peers never offer us a task we would refuse.
            "kinds": list(ALLOWED_KINDS) if enabled else [],
            "idle_only": bool(cfg.get("worker_only_idle", False)),
            "only_plugged": bool(cfg.get("worker_only_plugged", False)),
            "paused": bool(cfg.get("worker_paused", False)),
            "third_party_backend": third_party,
        }

    # -- handler -------------------------------------------------------------------
    async def handle(self, node_id: str, message: dict[str, Any]) -> dict[str, Any]:
        """Process one SPEC §8 packet. Runs on the P2P event loop."""
        received = time.monotonic()
        policy = self.policy()
        attempt_id = message.get("attempt_id")
        requested_role = str((message.get("constraints") or {}).get("role") or "")
        if policy["third_party_backend"]:
            return error("E_POLICY", "this node's model is a third-party service; it never "
                         "serves the swarm", attempt_id)
        allowed, code, detail = self.circle_guard(node_id)
        if not allowed:
            # WP4b: a non-member asking for an executor role gets the same
            # honest role refusal as a member of an unshared circle, with
            # nothing searched or retrieved.
            if requested_role in ("search", "corpus"):
                return error(E_ROLE_UNAVAILABLE,
                             detail or "sender is not in a shared trusted circle",
                             attempt_id)
            return error(code or "E_CIRCLE_REQUIRED",
                         detail or "sender is not in a shared trusted circle",
                         attempt_id)
        if not policy["enabled"]:
            return error("E_POLICY", "worker role disabled", attempt_id)
        if policy["paused"]:
            return error("E_POLICY", "worker paused by its owner", attempt_id)
        if not policy["allow_lan"]:  # v0.1 peers are LAN peers by construction
            return error("E_POLICY", "LAN requests not accepted", attempt_id)
        # 3.5, D-018: a role task is only accepted when this node advertises
        # the role. Refused before any model is loaded, slot taken or byte
        # generated, so a false claim executes nothing.
        if requested_role and requested_role not in self.role_names():
            return error(E_ROLE_UNAVAILABLE,
                         f"role {requested_role!r} is not advertised by this node",
                         attempt_id)
        lane = str(message.get("lane", "PUBLIC"))
        if lane == "SENSITIVE":
            return error("E_LANE_VIOLATION",
                         "sensitive packet offered to an open node", attempt_id)
        tier = str(message.get("tier", "GLOBAL"))
        if tier == "TRUSTED":
            return error("E_MTLS_REQUIRED",
                         "trusted-swarm links require mutual TLS (not yet supported)",
                         attempt_id)
        if tier == "LOCAL":
            return error("E_TIER_VIOLATION", "LOCAL requests are never serialized",
                         attempt_id)
        task = message.get("task") or {}
        kind = str(task.get("kind", "generate"))
        if kind not in policy["kinds"]:
            return error("E_KIND_UNSUPPORTED", f"kind {kind!r} not served",
                         attempt_id)
        expects = task.get("expects") or {}
        try:
            max_tokens = int(expects.get("max_tokens", 0) or 0)
            deadline_ms = int(message.get("deadline_ms", 60000) or 60000)
        except (TypeError, ValueError):
            return error("E_SCHEMA", "max_tokens/deadline_ms must be integers",
                         attempt_id)
        if max_tokens > policy["max_tokens_per_task"]:
            return error("E_BUDGET_EXCEEDED",
                         f"max_tokens {max_tokens} above node policy "
                         f"{policy['max_tokens_per_task']}", attempt_id)
        if deadline_ms <= 0 or deadline_ms > MAX_DEADLINE_MS:
            return error("E_SCHEMA", "deadline_ms must be a duration in "
                         f"(0, {MAX_DEADLINE_MS}]", attempt_id)
        budget_s = min(deadline_ms / 1000.0, float(policy["max_task_seconds"]))
        if policy["only_plugged"] and self._on_battery():
            return error("E_POLICY", "worker serves only on AC power", attempt_id)
        if policy["idle_only"]:
            idle = await asyncio.get_running_loop().run_in_executor(
                None, self._machine_idle)
            if not idle:
                return error("E_POLICY", "worker participates only when idle",
                             attempt_id)
        # D-020: a credit is a queue courtesy, never an admission or a policy
        # exception. Every gate above has already run; a requester without a
        # credit is still served whenever a slot is free. Only while busy does
        # a credited task wait for a slot instead of being refused, and an
        # uncredited task yields to a credited one that is already waiting.
        credited = False
        if self.credits is not None:
            try:
                credited = bool(self.credits.take_priority(
                    node_id, str(attempt_id or "")))
            except Exception:
                credited = False
        if not await self._acquire_slot(int(policy["max_concurrent"]),
                                        credited=credited,
                                        budget_s=budget_s):
            return error("E_POLICY", "worker at concurrency limit", attempt_id)
        cancel_event = threading.Event()
        key = (node_id, str(attempt_id or ""))
        self._cancels[key] = cancel_event
        try:
            hard_deadline = received + budget_s
            return await asyncio.get_running_loop().run_in_executor(
                None, functools.partial(
                    self._execute, message, hard_deadline,
                    int((time.monotonic() - received) * 1000),
                    requester=node_id, cancel_event=cancel_event))
        finally:
            self._cancels.pop(key, None)
            with self._lock:
                self._tasks_now -= 1

    async def _acquire_slot(self, limit: int, *, credited: bool,
                            budget_s: float) -> bool:
        """Take a concurrency slot; a credited task may wait while busy."""
        deadline = time.monotonic() + max(0.0, float(budget_s))
        if credited:
            with self._lock:
                self._priority_waiters += 1
        try:
            while True:
                with self._lock:
                    if self._tasks_now < limit and (
                            credited or self._priority_waiters == 0):
                        self._tasks_now += 1
                        return True
                if not credited or time.monotonic() >= deadline:
                    return False
                await asyncio.sleep(0.02)
        finally:
            if credited:
                with self._lock:
                    self._priority_waiters = max(0, self._priority_waiters - 1)

    @staticmethod
    def _machine_idle() -> bool:
        """CPU-based heuristic (blocking 0.5 s, run in an executor)."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.5) < 50.0
        except Exception:
            return True

    @staticmethod
    def _on_battery() -> bool:
        try:
            import psutil
            battery = psutil.sensors_battery()
        except Exception:
            return False
        return battery is not None and not battery.power_plugged

    def _pick_model(self, message: dict[str, Any],
                    models: list[str] | None = None) -> str:
        """The exact model asked for (``constraints.model``) when shared; else
        the *largest* shared model of the wanted family (the first one listed
        was taken before, so a node offering llama3.2:1b and llama3.1:8b ran
        the 1B model); else the first shared model."""
        from ..engine.capability import rank_params
        shared = models if models is not None else self.shared_models()
        constraints = message.get("constraints") or {}
        exact = str(constraints.get("model") or "")
        if exact and exact in shared:
            return exact
        wanted = str(constraints.get("model_family") or "")
        if wanted:
            matches = []
            for name in shared:
                fam = family_for(name, (self.model_info(name) or {}).get("family", ""))
                base = model_family(name)
                if wanted in (fam, base, name) or base.startswith(wanted) \
                        or str(fam).startswith(wanted):
                    matches.append(name)
            if matches:
                return max(matches, key=rank_params)
        return shared[0] if shared else "base"

    # -- execution (blocking; runs in an executor thread) -----------------------------
    def _execute(self, message: dict[str, Any], hard_deadline: float,
                 queue_ms: int, models: list[str] | None = None,
                 serving_others: bool = True,
                 requester: str = "", local: bool = False,
                 cancel_event: threading.Event | None = None) -> dict[str, Any]:
        """Execute one packet. ``models`` overrides the shared set (local pool);
        contribution counters only count work served to *other* nodes."""
        started = time.monotonic()
        attempt_id = str(message.get("attempt_id", ""))
        prompt = render_packet_prompt(message)
        offered = self.shared_models() if models is None else list(models)
        task = message.get("task") or {}
        constraints = message.get("constraints") or {}
        role = str(constraints.get("role") or "")
        if role and role not in self.role_names(offered, remote=not local):
            # Defence in depth: the packet may arrive through execute_local
            # (or a future path) without passing handle().
            return error(E_ROLE_UNAVAILABLE,
                         f"role {role!r} is not advertised by this node",
                         attempt_id)
        if role in ("search", "corpus"):
            # WP4b: executors, not model generation. They enforce their own
            # circle check, bounds and egress before returning a signed result.
            return self._execute_role(
                message, role, hard_deadline=hard_deadline, queue_ms=queue_ms,
                requester=requester, local=local, serving_others=serving_others)
        model_name = self._pick_model(message, models)
        if role:
            role_models = self._role_models(role, offered)
            if role_models:
                exact = str(constraints.get("model") or "")
                from ..engine.capability import rank_params
                model_name = exact if exact in role_models else max(
                    role_models, key=rank_params)
        max_tokens = int((task.get("expects") or {}).get("max_tokens") or 400)
        temperature = float(constraints.get("temperature", 0.2) or 0.2)
        # 3.5, D-018: think travels only where a backend accepts it (below).
        think = constraints.get("think")
        if not isinstance(think, bool):
            # The requester decides from the advertisement.  A reasoner whose
            # model was not proven to support thinking is run without it; the
            # role alone never adds a parameter.
            think = None
        try:
            stream = self.backend_factory()
        except Exception as exc:
            return error("E_EXECUTION", f"backend unavailable: {exc}", attempt_id)
        backend = PromptBackend(
            stream, model_name,
            interrupt=lambda: (time.monotonic() > hard_deadline
                               or (cancel_event is not None and cancel_event.is_set())))
        from .. import egress
        try:
            # what this call carries, for the destinations policy (3.0.1)
            purpose = egress.purpose(egress.FOREIGN if serving_others else egress.FRAGMENT)
            purpose.__enter__()
            guard = self.lce.worker_guard(model_name)
            if guard is not None:
                guard.forbid_sink(self._forbidden_sink)
                text = guard.execute(backend, prompt, max_tokens=max_tokens,
                                     temperature=temperature, think=think)
            else:
                text = backend.generate(prompt, max_tokens=max_tokens,
                                        temperature=temperature, think=think)
        except Interrupted:
            return error("E_DEADLINE", "deadline reached during generation",
                         attempt_id)
        except Exception as exc:
            return error("E_EXECUTION", f"execution failed: {str(exc)[:160]}",
                         attempt_id)
        finally:
            purpose.__exit__(None, None, None)
        gen_ms = int((time.monotonic() - started) * 1000)
        info = self.model_info(model_name) or {}
        tokens_out = (backend.last.completion_tokens
                      if backend.last is not None else None)
        profile = {
            "model_family": family_for(model_name, info.get("family", "")),
            "model_version": model_name,
            "quantization": info.get("quantization", ""),
            "prompt_template_id": "swarmbly-app/packet-v1",
            "sampling_params": {"temperature": temperature,
                                "max_tokens": max_tokens},
            "seed": None,
            # app extension (D-018): what the backend really received; absent
            # when it does not accept think, so nothing is simulated.
            **({"think": backend.applied_think}
               if isinstance(backend.applied_think, bool) else {}),
        }
        finish_reason = (getattr(backend.last, "finish_reason", "") or ""
                         if backend.last is not None else "")
        load_ms = ((backend.last.meta or {}).get("load_ms")
                   if backend.last is not None else None)
        telemetry = {"gen_ms": gen_ms, "queue_ms": queue_ms,
                     "tokens_out": tokens_out, "energy_j": None,
                     # model load time inside gen_ms (app extension; Ollama)
                     "load_ms": load_ms,
                     # "length" = the generation hit max_tokens (truncated).
                     "finish_reason": finish_reason}
        reply = result(attempt_id, text, profile, telemetry, b"", commitment=None)
        reply["sig"] = _b64(self.identity.sign(
            canonical_bytes({k: v for k, v in reply.items() if k != "sig"})))
        if serving_others:
            self._record_stats(gen_ms, tokens_out or 0,
                               len(canonical_bytes(message)), len(canonical_bytes(reply)))
            # Only operational aggregates leave this method (I2 / LCE §9.6).
            self.bus.publish("worker.task_served", model=model_name, gen_ms=gen_ms,
                             tokens_out=tokens_out)
        return reply

    # -- WP4b executors -----------------------------------------------------------
    @staticmethod
    def _executor_profile(role: str) -> dict[str, Any]:
        return {"model_family": role, "model_version": role, "quantization": "",
                "prompt_template_id": f"swarmbly-app/{role}-v1",
                "sampling_params": {}, "seed": None, "executor": role}

    def _role_reply(self, attempt_id: str, role: str, text: str,
                    telemetry: dict[str, Any], sources: list[dict[str, Any]],
                    message: dict[str, Any], serving_others: bool) -> dict[str, Any]:
        profile = self._executor_profile(role)
        reply = result(attempt_id, text, profile, telemetry, b"", commitment=None)
        # App extension (MINOR-safe): the requester uses it to label the
        # material, never as proof of where it came from.
        reply["executor"] = role
        reply["sources"] = sources[:8]
        reply["sig"] = _b64(self.identity.sign(
            canonical_bytes({k: v for k, v in reply.items() if k != "sig"})))
        if serving_others:
            self._record_stats(int(telemetry.get("gen_ms") or 0), 0,
                               len(canonical_bytes(message)), len(canonical_bytes(reply)))
            self.bus.publish("worker.executor_served", executor=role,
                             gen_ms=int(telemetry.get("gen_ms") or 0),
                             sources=len(sources))
        return reply

    def _execute_role(self, message: dict[str, Any], role: str, *, hard_deadline: float,
                      queue_ms: int, requester: str, local: bool,
                      serving_others: bool) -> dict[str, Any]:
        started = time.monotonic()
        attempt_id = str(message.get("attempt_id", ""))
        task = message.get("task") or {}
        contract = message.get("contract") or {}
        try:
            if role == "search":
                return self._run_search(
                    message, task, contract, attempt_id=attempt_id,
                    requester=requester, local=local, started=started,
                    queue_ms=queue_ms, serving_others=serving_others)
            return self._run_corpus(
                message, task, attempt_id=attempt_id, requester=requester,
                local=local, started=started, queue_ms=queue_ms,
                serving_others=serving_others)
        except Exception as exc:
            return error("E_EXECUTION", f"executor failed: {str(exc)[:160]}",
                         attempt_id)

    def _run_search(self, message: dict[str, Any], task: dict[str, Any],
                    contract: dict[str, Any], *, attempt_id: str, requester: str,
                    local: bool, started: float, queue_ms: int,
                    serving_others: bool) -> dict[str, Any]:
        raw = str(task.get("instruction") or "")
        words = raw.split()
        lines = [line for line in raw.splitlines() if line.strip()]
        if not raw.strip() or len(raw.strip()) > MAX_SEARCH_QUERY_CHARS \
                or len(words) > MAX_SEARCH_QUERY_WORDS or len(lines) > 1:
            # A document or a pasted fragment is not a public search query.
            return error("E_POLICY",
                         "search query refused: needs one line of at most "
                         f"{MAX_SEARCH_QUERY_CHARS} characters and "
                         f"{MAX_SEARCH_QUERY_WORDS} words", attempt_id)
        query = " ".join(words)
        circle = None if local else self.circle_for(requester)
        if not local and not circle:
            # Deliberately stricter than the 3.4 LAN rule: a public search on
            # another person's behalf needs a trusted circle, not own devices.
            return error(E_ROLE_UNAVAILABLE,
                         "public search is shared only inside a trusted circle",
                         attempt_id)
        cfg = self.config.all()
        engines = search_engines(cfg)
        if not search_enabled(cfg) or not engines:
            return error(E_ROLE_UNAVAILABLE,
                         "this node does not advertise the search role", attempt_id)
        lang = str(contract.get("lang") or cfg.get("language") or "es")
        ev_cfg = dict(cfg.get("evidence") or {})
        providers: list[str] = []
        if "pubmed" in engines:
            providers.append("pubmed")
        if "wikipedia" in engines:
            providers.append("wikipedia")
        if "searxng" in engines:
            providers.append("web")
        ev_cfg["providers"] = providers
        from .. import egress
        from .. import web_search
        # The worker's own policy decides each host before a search runs. The
        # public-query kind allows public sources; a local SearXNG is local.
        for url in self._search_urls(engines, lang, ev_cfg):
            cls, host = egress.classify_url(url)
            ok, why = egress.policy().allows(cls, host, egress.PUBLIC_QUERY)
            if not ok:
                return error("E_EGRESS_DENIED", why[:200], attempt_id)
        short = (requester or "local pool")[:12]
        circle_id = str((circle or {}).get("circle_id") or "")
        circle_name = str((circle or {}).get("circle_name") or "")

        def fetch(url: str, timeout_s: float, user_agent: str) -> Any:
            cls, host = egress.classify_url(url)
            extra = {"on_behalf": short, "query": query, "executor": "search",
                     "circle_id": circle_id, "circle_name": circle_name,
                     "member_name": short}
            if cls == egress.LOCAL:
                egress.record(destino=host, clase=cls, tipo=egress.PUBLIC_QUERY,
                              bytes=len(query.encode("utf-8")),
                              motivo=f"consulta pública para nodo {short}", **extra)
            else:
                egress.check_call(
                    url, len(query.encode("utf-8")),
                    f"consulta pública para nodo {short} en círculo "
                    f"{circle_name or 'local'}", kind=egress.PUBLIC_QUERY,
                    **extra)
            if self.search_fetch is not None:
                return self.search_fetch(url, timeout_s, user_agent)
            from ..engine.providers import _get
            return _get(url, timeout_s, user_agent)

        with egress.request_ledger(attempt_id) as ledger:
            found = web_search.search(query, ev_cfg, lang=lang, recent=False,
                                      limit=MAX_SEARCH_RESULTS, fetch=fetch)
            events = [dict(event) for event in ledger.events]
        self._remember_ledger(events)
        results: list[dict[str, Any]] = []
        for hit in (found.get("results") or [])[:MAX_SEARCH_RESULTS]:
            if not isinstance(hit, dict):
                continue
            title = str(hit.get("title") or "")[:300]
            url = str(hit.get("url") or "")[:500]
            if url and not url.lower().startswith(("http://", "https://")):
                url = ""
            snippet = str(hit.get("snippet") or "")[:300]
            if not title and not url:
                continue
            results.append({"kind": "search", "title": title, "url": url,
                            "snippet": snippet,
                            "provider": str(hit.get("provider") or "")[:40],
                            "label": f"S{len(results) + 1}"})
        lines = [f"Public search on behalf of nodo {short} in circle "
                 f"{circle_name or 'local'} (query: «{query}»)."]
        for item in results:
            line = f"[{item['label']}] {item['title']} <{item['url']}>"
            if item["snippet"]:
                line += f": {item['snippet']}"
            lines.append(line)
        if not results:
            lines.append("(no results)")
        gen_ms = int((time.monotonic() - started) * 1000)
        telemetry = {"gen_ms": gen_ms, "queue_ms": queue_ms, "tokens_out": 0,
                     "energy_j": None, "load_ms": None, "finish_reason": "stop",
                     "executor": "search", "results": len(results)}
        return self._role_reply(attempt_id, "search", "\n".join(lines),
                                telemetry, results, message, serving_others)

    @staticmethod
    def _search_urls(engines: list[str], lang: str,
                     ev_cfg: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        if "pubmed" in engines:
            urls.append("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi")
        if "wikipedia" in engines:
            for code in dict.fromkeys([lang, "en"]):
                urls.append(f"https://{code}.wikipedia.org/w/api.php")
        if "searxng" in engines and str(ev_cfg.get("searxng_url") or "").strip():
            urls.append(str(ev_cfg["searxng_url"]))
        return urls

    def _run_corpus(self, message: dict[str, Any], task: dict[str, Any], *,
                    attempt_id: str, requester: str, local: bool, started: float,
                    queue_ms: int, serving_others: bool) -> dict[str, Any]:
        from .. import egress
        from ..node_roles import configured_corpus_share
        cfg = self.config.all()
        share = configured_corpus_share(cfg)
        if share is None:
            return error(E_ROLE_UNAVAILABLE,
                         "this node shares no corpus", attempt_id)
        circle = None
        if not local:
            if not self.circle_for(requester):
                return error(E_ROLE_UNAVAILABLE,
                             "the corpus is shared only inside a trusted circle",
                             attempt_id)
            # The requester may share several circles with this node: match
            # the one(s) the corpus is shared with, never just the first.
            circle = self.circle_for(requester, list(share["circle_ids"]))
            if not circle or str(circle.get("circle_id") or "") \
                    not in share["circle_ids"]:
                return error(E_ROLE_UNAVAILABLE,
                             "this corpus is not shared with the requester's circle",
                             attempt_id)
        project = self.project_provider(share["project_id"])
        if project is None:
            return error(E_ROLE_UNAVAILABLE, "the shared corpus is not available",
                         attempt_id)
        raw = str(task.get("instruction") or "").strip()
        if not raw or len(raw) > MAX_CORPUS_QUERY_CHARS:
            return error("E_POLICY", "corpus question is empty or too long", attempt_id)
        short = (requester or "local pool")[:12]
        circle_id = str((circle or {}).get("circle_id") or "")
        circle_name = str((circle or {}).get("circle_name") or "")
        with egress.request_ledger(attempt_id) as ledger:
            try:
                hits = self.lce.retrieve(raw, k=MAX_CORPUS_PASSAGES,
                                         roots=project.roots())
            except Exception as exc:
                return error("E_EXECUTION", f"corpus retrieval failed: {str(exc)[:160]}",
                             attempt_id)
            sources = [self._corpus_source(hit) for hit in hits[:MAX_CORPUS_PASSAGES]]
            sources = [source for source in sources if source["text"]]
            if sources and not local:
                payload = sum(len(source["text"].encode("utf-8")) for source in sources)
                egress.record(
                    destino=f"nodo {short}", clase=egress.CIRCLE,
                    tipo=egress.PASSAGES, bytes=payload,
                    motivo=f"pasajes del corpus compartido en nombre de nodo {short}",
                    circle_id=circle_id, circle_name=circle_name,
                    member_name=short, on_behalf=short,
                    passages=len(sources), executor="corpus")
            events = [dict(event) for event in ledger.events]
        self._remember_ledger(events)
        lines = [f"Shared corpus «{share['display_name'] or project.name}» "
                 f"(circle {circle_name or 'local'}): {len(sources)} passage(s) "
                 f"on behalf of nodo {short}."]
        for index, source in enumerate(sources, 1):
            lines.append(f"[C{index}] {source['title']} (span {source['span']}): "
                         f"{source['text']}")
        if not sources:
            lines.append("(no passage matched the question)")
        gen_ms = int((time.monotonic() - started) * 1000)
        telemetry = {"gen_ms": gen_ms, "queue_ms": queue_ms, "tokens_out": 0,
                     "energy_j": None, "load_ms": None, "finish_reason": "stop",
                     "executor": "corpus", "passages": len(sources)}
        return self._role_reply(attempt_id, "corpus", "\n".join(lines),
                                telemetry, sources, message, serving_others)

    @staticmethod
    def _corpus_source(hit: dict[str, Any]) -> dict[str, Any]:
        """Neutral citation: document title and span id, never a path."""
        from pathlib import Path as _Path
        title = _Path(str(hit.get("source") or "document")).name
        title = title.rsplit(".", 1)[0] if "." in title else title
        cite = str(hit.get("cite") or "")
        if not cite.startswith("doc:"):
            cite = ""
        span = str(hit.get("anchor") or "")
        if not span and "#" in cite:
            span = cite.split("#", 1)[1]
        text = str(hit.get("text") or "")[:MAX_CORPUS_TEXT_CHARS]
        return {"kind": "corpus", "title": title[:200] or "document",
                "span": span[:16] or "p1", "cite": cite[:80],
                "text": text, "score": hit.get("score")}

    def cancel(self, node_id: str, attempt_id: str) -> bool:
        """Stop a task the requesting node no longer waits for (it timed out,
        or another replica won). Only the node that sent the task can cancel
        it. Without this, a worker kept generating after the requester gave
        up, and refused the requester's next task as "at concurrency limit"
        (P3b.3, 22 Oct 2026)."""
        event = self._cancels.get((node_id, str(attempt_id or "")))
        if event is None:
            return False
        event.set()
        return True

    def execute_local(self, message: dict[str, Any], models: list[str],
                      timeout_s: float) -> dict[str, Any]:
        """Run a packet on this device's own models (local multi-model pool).
        Same packet, rendering, guard and signature as for a remote worker;
        nothing leaves the device and nothing counts as served to others."""
        return self._execute(message, time.monotonic() + timeout_s, 0,
                             models=models, serving_others=False, local=True)

    def _forbidden_sink(self, text: str) -> None:
        raise RuntimeError("task content must never reach LCE stores (I2)")

    def _record_stats(self, gen_ms: int, tokens_out: int, bytes_in: int,
                      bytes_out: int) -> None:
        import datetime
        self.db.add_stats(datetime.date.today().isoformat(),
                          tasks_served=1, served_ms=gen_ms,
                          served_tokens=tokens_out,
                          bytes_in=bytes_in, bytes_out=bytes_out)

    def status(self) -> dict[str, Any]:
        with self._lock:
            busy = self._tasks_now
        import datetime
        today = datetime.date.today().isoformat()
        stats = self.db.get_stats(days=1)
        served = sum(s.get("tasks_served", 0) for s in stats if s["day"] >= today)
        return {"policy": self.policy(), "busy_now": busy,
                "shared_models": self.shared_models(),
                "tasks_served_today": served}


def render_packet_prompt(message: dict[str, Any]) -> str:
    """Render a SPEC §8 packet into the worker's model prompt.

    The contract header is mandatory content (§9.1); predecessor summaries
    and the task block follow. Fragments are data, never instructions: the
    worker's prompt only ever contains what the packet carries. No
    ``session_id`` ever appears here (the wire packet has none).
    """
    from ..lang import strings, value

    parts: list[str] = []
    contract = message.get("contract") or {}
    # Γ extension ``lang``: scaffolding in the request's language (English
    # when absent, byte-identical to v0.2.0).
    lang = contract.get("lang") if isinstance(contract.get("lang"), str) else None
    s = strings(lang)
    if contract:
        lines = [s["contract"]]
        for key in ("objective", "audience", "register", "format", "target_len"):
            if contract.get(key) not in (None, "", 0):
                lines.append(f"{s[key]}: {value(lang, contract[key])}")
        lexicon = contract.get("lexicon") or {}
        if lexicon.get("prefer"):
            lines.append(f"{s['prefer']}: " + ", ".join(map(str, lexicon["prefer"])))
        if lexicon.get("forbid"):
            lines.append(f"{s['avoid']}: " + ", ".join(map(str, lexicon["forbid"])))
        if contract.get("entities"):
            lines.append(f"{s['entities']}: " + ", ".join(
                str(e.get("canonical") or e.get("name")) for e in contract["entities"]
                if isinstance(e, dict)))
        if contract.get("style_seed"):
            lines.append(f"{s['style']}: {contract['style_seed']}")
        parts.append("\n".join(lines))
    for pred in message.get("predecessors") or []:
        if isinstance(pred, dict) and pred.get("summary"):
            parts.append(f"[{s['context']} {str(pred.get('task_id', ''))[:8]}] "
                         f"{pred['summary']}")
    task = message.get("task") or {}
    instruction = str(task.get("instruction") or "")
    expects = task.get("expects") or {}
    if expects.get("format"):
        instruction += "\n" + s["respond_format"].format(fmt=value(lang, expects["format"]))
    parts.append(f"{s['task']}\n{instruction}")
    return "\n\n".join(parts)


def _b64(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
