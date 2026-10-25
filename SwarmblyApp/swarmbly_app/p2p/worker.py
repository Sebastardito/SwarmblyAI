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
from .messages import canonical_bytes, error, result

ALLOWED_KINDS = ("extract", "classify", "generate", "summarize",
                 "transform", "judge")
MAX_DEADLINE_MS = 10 * 60 * 1000


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

    def generate(self, prompt: str, **kw: Any) -> str:
        out = self._stream.stream_chat(
            [{"role": "user", "content": prompt}], model=self.model,
            max_tokens=kw.get("max_tokens", 800),
            temperature=kw.get("temperature", 0.2),
            interrupt=self._interrupt)
        self.last = out
        return out.text


def model_family(name: str) -> str:
    """Family of an Ollama-style tag: ``llama3.2:3b`` → ``llama3.2``."""
    return (name or "").split(":")[0].split("/")[-1] or "unknown"


class WorkerService:
    def __init__(self, config: Config, db: Database, bus: EventBus,
                 identity: IdentityManager, lce: LCEAdapter,
                 backend_factory, model_info: Callable[[str], dict] | None = None):
        self.config = config
        self.db = db
        self.bus = bus
        self.identity = identity
        self.lce = lce
        self.backend_factory = backend_factory  # () -> StreamBackend
        self.model_info = model_info or (lambda name: {})
        self._tasks_now = 0
        self._lock = threading.Lock()
        # (requesting node, attempt_id) -> cancel flag checked between tokens
        self._cancels: dict[tuple[str, str], threading.Event] = {}

    # -- policy -----------------------------------------------------------------
    def shared_models(self) -> list[str]:
        """Models this node offers to third parties (never a personal adapter)."""
        cfg = self.config.all()
        shared = [m for m in (cfg["swarm"].get("worker_models") or []) if m]
        if not shared and cfg["model"].get("model_name"):
            shared = [cfg["model"]["model_name"]]
        return shared

    def policy(self) -> dict[str, Any]:
        cfg = self.config.all()["swarm"]
        enabled = bool(cfg.get("worker_enabled")) and bool(self.shared_models())
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
        }

    # -- handler -------------------------------------------------------------------
    async def handle(self, node_id: str, message: dict[str, Any]) -> dict[str, Any]:
        """Process one SPEC §8 packet. Runs on the P2P event loop."""
        received = time.monotonic()
        policy = self.policy()
        attempt_id = message.get("attempt_id")
        if not policy["enabled"]:
            return error("E_POLICY", "worker role disabled", attempt_id)
        if policy["paused"]:
            return error("E_POLICY", "worker paused by its owner", attempt_id)
        if not policy["allow_lan"]:  # v0.1 peers are LAN peers by construction
            return error("E_POLICY", "LAN requests not accepted", attempt_id)
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
        with self._lock:
            if self._tasks_now >= int(policy["max_concurrent"]):
                return error("E_POLICY", "worker at concurrency limit", attempt_id)
            self._tasks_now += 1
        cancel_event = threading.Event()
        key = (node_id, str(attempt_id or ""))
        self._cancels[key] = cancel_event
        try:
            hard_deadline = received + budget_s
            return await asyncio.get_running_loop().run_in_executor(
                None, functools.partial(
                    self._execute, message, hard_deadline,
                    int((time.monotonic() - received) * 1000),
                    cancel_event=cancel_event))
        finally:
            self._cancels.pop(key, None)
            with self._lock:
                self._tasks_now -= 1

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
                fam = (self.model_info(name) or {}).get("family") or model_family(name)
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
                 cancel_event: threading.Event | None = None) -> dict[str, Any]:
        """Execute one packet. ``models`` overrides the shared set (local pool);
        contribution counters only count work served to *other* nodes."""
        started = time.monotonic()
        attempt_id = str(message.get("attempt_id", ""))
        prompt = render_packet_prompt(message)
        model_name = self._pick_model(message, models)
        task = message.get("task") or {}
        constraints = message.get("constraints") or {}
        max_tokens = int((task.get("expects") or {}).get("max_tokens") or 400)
        temperature = float(constraints.get("temperature", 0.2) or 0.2)
        try:
            stream = self.backend_factory()
        except Exception as exc:
            return error("E_EXECUTION", f"backend unavailable: {exc}", attempt_id)
        backend = PromptBackend(
            stream, model_name,
            interrupt=lambda: (time.monotonic() > hard_deadline
                               or (cancel_event is not None and cancel_event.is_set())))
        try:
            guard = self.lce.worker_guard(model_name)
            if guard is not None:
                guard.forbid_sink(self._forbidden_sink)
                text = guard.execute(backend, prompt, max_tokens=max_tokens,
                                     temperature=temperature)
            else:
                text = backend.generate(prompt, max_tokens=max_tokens,
                                        temperature=temperature)
        except Interrupted:
            return error("E_DEADLINE", "deadline reached during generation",
                         attempt_id)
        except Exception as exc:
            return error("E_EXECUTION", f"execution failed: {str(exc)[:160]}",
                         attempt_id)
        gen_ms = int((time.monotonic() - started) * 1000)
        info = self.model_info(model_name) or {}
        tokens_out = (backend.last.completion_tokens
                      if backend.last is not None else None)
        profile = {
            "model_family": info.get("family") or model_family(model_name),
            "model_version": model_name,
            "quantization": info.get("quantization", ""),
            "prompt_template_id": "swarmbly-app/packet-v1",
            "sampling_params": {"temperature": temperature,
                                "max_tokens": max_tokens},
            "seed": None,
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
                             models=models, serving_others=False)

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
