"""App adapter for the ``swarmbly-agent`` runtime (D-007, D-011).

The runtime owns the loop, the step budget and the observation quoting; this
module supplies the four injected pieces and nothing else:

* ``generate`` calls the conversation's model through the existing backends.
  The backend itself checks the destination policy at the point where bytes
  leave; a third-party host is refused before the call when it is not in
  ``privacy.third_party_models``. The receipt records the model destination.
* ``execute_tool`` calls :meth:`~swarmbly_app.tools.broker.ToolBroker.invoke`
  with the one-time token that the approval endpoint issued. No other code
  path issues a token.
* ``policy`` applies D-011: a local MCP tool with a standing approval for its
  current contract runs (``Allow``); every other call needs the user's yes
  (``NeedsApproval``); a tool whose Settings approval is missing or stale is
  denied (``Deny``). Sandbox and author search always ask.
* Observations are built from the broker's result, so they carry the source
  and the SHA-256 of the full text. The runtime turns them into the quoted
  ``TOOL OUTPUT`` message; this module never writes system text.

``swarmbly-agent`` is an optional extra (``pip install 'swarmbly-app[agent]'``)
and is imported lazily. Without it the feature reports itself unavailable and
says how to install it; importing the app never needs the package.

Pending runs live in memory for the life of the app process. A page reload
shows the pending card again because it is stored in the assistant message's
``meta``; an app restart stops the run (there is no token or run on disk).
"""

from __future__ import annotations

import copy
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import egress
from .inference.registry import BackendRegistry, endpoint
from .tools import ToolBroker, ToolCall, ToolDenied, ToolSpec
from .tools.schema import sha256_canonical
from .tools.standing import StandingError, StandingStore

AGENT_EXTRA_HINT = (
    "the tools agent needs the optional swarmbly-agent package; install it "
    "with pip install 'swarmbly-app[agent]'")

AGENT_DEFAULTS = {"max_steps": 8, "max_tool_calls": 8,
                  "max_observation_chars": 4000}
AGENT_LIMITS = {"max_steps": (1, 8), "max_tool_calls": (1, 8),
                "max_observation_chars": (500, 8000)}
_MCP_ID_RE = re.compile(r"^mcp:([^/]+)/")


class AgentUnavailable(RuntimeError):
    """The optional runtime is not installed."""


class AgentConflict(ValueError):
    """A pending run is missing, stale or was already decided."""


def _runtime():
    """Import the optional package once; raise a plain-language error if absent."""
    try:
        import swarmbly_agent  # type: ignore[import-not-found]
    except Exception as exc:  # ImportError, but a broken install also counts
        raise AgentUnavailable(AGENT_EXTRA_HINT) from exc
    return swarmbly_agent


def agent_available() -> bool:
    try:
        _runtime()
    except AgentUnavailable:
        return False
    return True


def _clamp_budget(config: dict[str, Any]) -> dict[str, int]:
    raw = ((config or {}).get("tools") or {}).get("agent") or {}
    out: dict[str, int] = {}
    for key, default in AGENT_DEFAULTS.items():
        value = raw.get(key, default)
        low, high = AGENT_LIMITS[key]
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        out[key] = max(low, min(high, number))
    return out


def _server_of(spec: ToolSpec) -> str:
    match = _MCP_ID_RE.match(spec.id)
    if match:
        return match.group(1)
    return spec.provider


def _remote_host(backend: Any, model: str) -> str:
    """Where Ollama really runs a model ("" here or in the user's network)."""
    fn = getattr(backend, "remote_host", None)
    try:
        return str(fn(model) or "") if callable(fn) and model else ""
    except Exception:
        return egress.cloud_host_by_name(model)


def _destination(config: dict[str, Any], backend: Any, model: str) -> dict[str, str]:
    cls, host = egress.classify_url(endpoint(backend) or "http://127.0.0.1")
    remote = _remote_host(backend, model)
    if remote:
        # An Ollama cloud model: the bytes leave through the local Ollama, so
        # the policy applies to where the model actually runs.
        return {"clase": egress.THIRD_PARTY, "host": remote, "via": host}
    return {"clase": cls, "host": host}


def _model_error(host: str, lang: str) -> str:
    es = (lang or "").lower().startswith("es")
    return (
        f"El modelo configurado se ejecuta en {host}, un servicio externo que no has autorizado. "
        "No se envió nada. Autorízalo en Ajustes → Modelos o elige un modelo de esta computadora."
        if es else
        f"The configured model runs at {host}, a third-party service you have not authorised. "
        "Nothing was sent. Authorise it in Settings → Models, or choose a model on this computer.")


@dataclass
class AgentRun:
    """One conversation run and everything the receipt and UI need."""

    run_id: str
    request_id: str
    conversation_id: str
    message_id: str
    project_id: str
    task: str
    model: str
    budget: dict[str, int]
    runtime: Any = None
    state: Any = None
    ledger_events: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, str]] = field(default_factory=list)
    model_destination: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_model: dict[str, Any] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def status(self) -> str:
        return str(getattr(self.state, "status", "") or "")

    def pending_request(self):
        return getattr(self.state, "pending", None)


class AgentAdapter:
    """The App side of the runtime: model, broker, policy and approval state."""

    def __init__(self, broker: ToolBroker, config_getter: Callable[[], dict[str, Any]],
                 registry: BackendRegistry, *,
                 standing: StandingStore | None = None,
                 bus: Any = None):
        if not isinstance(broker, ToolBroker):
            raise TypeError("broker must be a ToolBroker")
        self.broker = broker
        self.config = config_getter
        self.registry = registry
        self.bus = bus
        self.standing = standing or StandingStore(
            broker.approvals.data_root,
            project_path=getattr(broker.approvals, "_project_path", None))
        self._runs: dict[str, AgentRun] = {}
        self._lock = threading.RLock()

    # -- availability and inventory -----------------------------------------
    def available(self) -> bool:
        return agent_available()

    def reason_unavailable(self) -> str:
        return "" if self.available() else AGENT_EXTRA_HINT

    def budget(self) -> dict[str, int]:
        return _clamp_budget(self.config())

    def tool_specs(self, project_id: str = "") -> list[ToolSpec]:
        specs = list(self.broker.specs().values())
        specs.sort(key=lambda spec: spec.id)
        return specs

    def tools_view(self, project_id: str = "") -> dict[str, Any]:
        """What the conversation may offer, and why the toggle is shown."""
        try:
            _runtime()
            available, reason = True, ""
        except AgentUnavailable as exc:
            available, reason = False, str(exc)
        tools = []
        mcp_approved = False
        for spec in self.tool_specs(project_id):
            approved = self.broker.approvals.is_approved(spec, project_id)
            if spec.provider in ("mcp_local", "mcp_remote") and approved:
                mcp_approved = True
            try:
                current_hash = spec.current_hash()
            except Exception:
                current_hash = ""
            can_stand = spec.provider == "mcp_local" and spec.destination == "local"
            tools.append({
                "id": spec.id,
                "provider": spec.provider,
                "local": spec.destination == "local",
                "remote": spec.destination != "local",
                "destination": spec.destination,
                "approved": approved,
                "standing": bool(can_stand and self.standing.is_standing(
                    spec.id, project_id, current_hash)),
                "can_stand": can_stand,
                "description": spec.description,
            })
        return {"available": available, "reason": reason,
                "project_id": project_id, "mcp_approved": mcp_approved,
                "tools": tools, "budget": self.budget()}

    def _descriptors(self, project_id: str) -> list[Any]:
        module = _runtime()
        return [
            module.ToolDescriptor(
                name=spec.id,
                description=spec.description,
                input_schema=copy.deepcopy(spec.input_schema),
            )
            for spec in self.tool_specs(project_id)
        ]

    def standing_records(self, project_id: str = "") -> list[dict[str, str]]:
        return self.standing.records(project_id)

    def grant_standing(self, spec_id: str, project_id: str = "") -> dict[str, str]:
        spec = self.broker.spec(spec_id)
        if spec is None:
            raise StandingError(f"unknown tool {spec_id!r}")
        if not self.broker.approvals.is_approved(spec, project_id):
            raise StandingError(
                f"tool {spec_id} is not approved in Settings; approve it there first")
        return self.standing.grant(spec, project_id)

    def revoke_standing(self, spec_id: str, project_id: str = "") -> bool:
        return self.standing.revoke(spec_id, project_id)

    # -- the three injected callables ---------------------------------------
    def policy(self, request: Any, project_id: str = "") -> Any:
        """D-011 in one decision: allow only a standing local MCP tool."""
        module = _runtime()
        spec = self.broker.spec(request.tool)
        if spec is None:
            return module.Deny(f"unknown tool: {request.tool}")
        try:
            approved = self.broker.approvals.is_approved(spec, project_id)
        except Exception as exc:
            return module.Deny(f"approval store error: {type(exc).__name__}: {exc}")
        if not approved:
            return module.Deny(
                f"tool {spec.id} is not approved in Settings for this project")
        try:
            current_hash = spec.current_hash()
        except Exception:
            current_hash = ""
        if spec.provider == "mcp_local" and spec.destination == "local" \
                and current_hash \
                and self.standing.is_standing(spec.id, project_id, current_hash):
            return module.Allow()
        if spec.provider in ("sandbox", "author"):
            return module.NeedsApproval(
                "the sandbox and author search always ask before running")
        if spec.provider == "mcp_remote":
            return module.NeedsApproval(
                "a remote MCP tool is a third party and always asks")
        return module.NeedsApproval("this tool needs your approval for this call")

    def _policy(self, run: AgentRun):
        return lambda request: self.policy(request, run.project_id)

    def _generate(self, run: AgentRun):
        def generate(messages: list[dict[str, str]], tools: list[Any]) -> Any:
            module = _runtime()
            cfg = self.config()
            backend = self.registry.resolve(cfg)
            model = run.model or ((backend.list_models() or [""])[0])
            if not model:
                raise RuntimeError("no model selected")
            destination = _destination(cfg, backend, model)
            run.model_destination = destination
            lang = str(cfg.get("language") or "en")
            if destination.get("clase") == egress.THIRD_PARTY:
                host = str(destination.get("host") or "")
                if not egress.policy().authorised(host):
                    raise RuntimeError(_model_error(host, lang))
            if run.state is not None and run.state.status == "stopped":
                raise RuntimeError("run stopped by user")
            model_cfg = cfg.get("model") or {}
            with egress.purpose(egress.QUESTION):
                result = backend.stream_chat(
                    [dict(message) for message in messages],
                    model=model,
                    max_tokens=int(model_cfg.get("max_tokens", 1024) or 1024),
                    temperature=float(model_cfg.get("temperature", 0.2) or 0.2),
                    interrupt=lambda: run.state is not None
                    and run.state.status == "stopped",
                )
            run.last_model = {
                "model": getattr(result, "model", model),
                "prompt_tokens": getattr(result, "prompt_tokens", None),
                "completion_tokens": getattr(result, "completion_tokens", None),
                "total_ms": getattr(result, "total_ms", None),
                "finish_reason": getattr(result, "finish_reason", ""),
            }
            return module.parse_json_action(getattr(result, "text", "") or "")
        return generate

    def _execute(self, run: AgentRun):
        def execute_tool(request: Any, token: str | None) -> Any:
            module = _runtime()
            spec = self.broker.spec(request.tool)
            if spec is None:
                return module.Observation(
                    tool=request.tool, ok=False,
                    content=f"denied: unknown tool {request.tool}",
                    source="policy")
            call = ToolCall(
                spec_id=request.tool,
                arguments=request.arguments,
                request_id=run.request_id,
                token=token,
                project_id=run.project_id,
                purpose=request.why,
            )
            try:
                prior = [step.observation.content
                         for step in getattr(run.state, "steps", []) or []
                         if step.observation is not None]
                if spec.provider == "mcp_remote" and prior:
                    # A tool result is data the model has seen. Mark it for the
                    # broker's shingle guard so a passage returned by a local
                    # tool cannot be forwarded to a remote one without
                    # privacy.third_party_passages.
                    from .tools import mcp as mcp_module
                    with mcp_module.passages(prior):
                        result = self.broker.invoke(call)
                else:
                    result = self.broker.invoke(call)
            except ToolDenied as exc:
                content = f"denied: {exc}"
                observation = module.Observation(
                    tool=request.tool, ok=False, content=content, source="policy")
                self._remember_approval(run, request, "denied", token)
                return observation
            except Exception as exc:
                content = f"tool error: {type(exc).__name__}: {exc}"
                observation = module.Observation(
                    tool=request.tool, ok=False, content=content, source="runtime")
                self._remember_approval(run, request, "denied", token)
                return observation
            self._remember_approval(run, request, "approved", token)
            return module.Observation(
                tool=request.tool,
                ok=bool(result.ok),
                content=str(result.content if result.ok else (result.error or result.content)),
                source=str(result.source or spec.destination),
                sha256=str(result.sha256 or ""),
                truncated=bool(result.truncated),
            )
        return execute_tool

    @staticmethod
    def _remember_approval(run: AgentRun, request: Any, decision: str,
                           token: str | None) -> None:
        run.approvals.append({
            "tool": request.tool,
            "args_sha256": sha256_canonical(request.arguments),
            "decision": decision,
            "by": "user" if token else "standing",
        })

    # -- running -------------------------------------------------------------
    def _instrument(self, run: AgentRun) -> Any:
        module = _runtime()
        budget = module.Budget(**run.budget)
        return module.AgentRuntime(
            generate=self._generate(run),
            execute_tool=self._execute(run),
            policy=self._policy(run),
            budget=budget,
        )

    def start(self, *, request_id: str, conversation_id: str, message_id: str,
              project_id: str, task: str, model: str = "") -> AgentRun:
        """Begin a run; returns at the final answer, a budget stop or a pause."""
        module = _runtime()
        run = AgentRun(
            run_id=f"agent-{message_id}",
            request_id=request_id,
            conversation_id=conversation_id,
            message_id=message_id,
            project_id=project_id,
            task=task,
            model=model or str((self.config().get("model") or {}).get("model_name") or ""),
            budget=self.budget(),
        )
        run.runtime = self._instrument(run)
        descriptors = self._descriptors(project_id)
        with run.lock:
            with egress.request_ledger(run.request_id) as ledger:
                run.state = run.runtime.run(task, descriptors)
            run.ledger_events.extend(ledger.events)
        with self._lock:
            self._runs[run.message_id] = run
        return run

    def resume(self, run: AgentRun, approved: bool,
               token: str | None = None) -> AgentRun:
        if run.state is None or run.state.status != "awaiting_approval":
            raise AgentConflict("this run is not waiting for an approval")
        with run.lock:
            with egress.request_ledger(run.request_id) as ledger:
                run.state = run.runtime.resume(run.state, approved=approved, token=token)
            run.ledger_events.extend(ledger.events)
        return run

    def approve(self, run: AgentRun, decision: str, *, remember: bool = False,
                args_sha256: str = "") -> AgentRun:
        """Decide the pending call: run, skip or stop.

        This is the only place a one-time token is issued. The token binds the
        tool, the exact arguments, the request id and an expiry; the broker
        consumes it once.
        """
        if run.state is None or run.state.status != "awaiting_approval":
            raise AgentConflict("this run is not waiting for an approval")
        request = run.state.pending
        if request is None:
            raise AgentConflict("the run has no pending tool request")
        card = self.pending_card(run)
        if args_sha256 and args_sha256 != card["args_sha256"]:
            raise AgentConflict(
                "the arguments changed since the card was shown; nothing ran")
        decision = {"approve": "run", "deny": "skip"}.get(decision, decision)
        if decision not in ("run", "skip", "stop"):
            raise AgentConflict(f"unknown decision {decision!r}")

        if decision == "stop":
            run.approvals.append({
                "tool": request.tool,
                "args_sha256": card["args_sha256"],
                "decision": "stopped",
                "by": "user",
            })
            run.state.status = "stopped"
            run.state.stop_reason = "stopped_by_user"
            run.state.pending = None
            run.state.pending_reason = None
            return run

        if decision == "skip":
            run.approvals.append({
                "tool": request.tool,
                "args_sha256": card["args_sha256"],
                "decision": "skipped",
                "by": "user",
            })
            return self.resume(run, approved=False)

        if remember and not card["can_remember"]:
            raise AgentConflict(
                "only a local MCP tool can be set to \"don't ask again in "
                "this project\"")
        call = ToolCall(
            spec_id=request.tool,
            arguments=request.arguments,
            request_id=run.request_id,
            project_id=run.project_id,
            purpose=request.why,
        )
        token = self.broker.issue_token(call)
        if remember:
            self.grant_standing(request.tool, run.project_id)
        return self.resume(run, approved=True, token=token)

    def stop_request(self, request_id: str) -> AgentRun | None:
        with self._lock:
            run = next((item for item in self._runs.values()
                        if item.request_id == request_id), None)
        if run is None:
            return None
        with run.lock:
            if run.state is not None and run.state.status == "awaiting_approval":
                request = run.state.pending
                if request is not None:
                    run.approvals.append({
                        "tool": request.tool,
                        "args_sha256": sha256_canonical(request.arguments),
                        "decision": "stopped",
                        "by": "user",
                    })
                run.state.status = "stopped"
                run.state.stop_reason = "stopped_by_user"
                run.state.pending = None
                run.state.pending_reason = None
            elif run.state is not None and run.state.status == "running":
                # The generate closure stops on the next interrupt check.
                run.state.status = "stopped"
                run.state.stop_reason = "stopped_by_user"
        return run

    # -- lookup and views ----------------------------------------------------
    def get(self, message_id: str) -> AgentRun | None:
        with self._lock:
            return self._runs.get(message_id)

    def forget(self, message_id: str) -> None:
        with self._lock:
            self._runs.pop(message_id, None)

    def summary(self, run: AgentRun) -> dict[str, Any]:
        state = run.state
        return {
            "steps": len(getattr(state, "steps", []) or []),
            "tool_calls": int(getattr(state, "tool_calls", 0) or 0),
            "approvals": [dict(item) for item in run.approvals],
            "stop_reason": str(getattr(state, "stop_reason", "") or ""),
            "status": str(getattr(state, "status", "") or ""),
            "budget": dict(run.budget),
        }

    def pending_card(self, run: AgentRun) -> dict[str, Any]:
        request = run.pending_request()
        if request is None:
            raise AgentConflict("the run has no pending tool request")
        spec = self.broker.spec(request.tool)
        if spec is None:
            raise AgentConflict(f"unknown pending tool {request.tool!r}")
        local = spec.destination == "local"
        host = "local" if local else egress.host_of(spec.destination)
        arguments = request.arguments
        try:
            pretty = json.dumps(arguments, ensure_ascii=False, indent=2,
                                sort_keys=True, default=str)
        except (TypeError, ValueError):
            pretty = repr(arguments)
        try:
            current_hash = spec.current_hash()
        except Exception:
            current_hash = ""
        return {
            "run_id": run.run_id,
            "message_id": run.message_id,
            "request_id": run.request_id,
            "tool": spec.id,
            "server": _server_of(spec),
            "provider": spec.provider,
            "local": local,
            "third_party": not local,
            "destination": spec.destination,
            "host": host,
            "arguments": arguments,
            "arguments_json": pretty,
            "args_sha256": sha256_canonical(arguments),
            "why": request.why,
            "reason": str(getattr(run.state, "pending_reason", "") or ""),
            "can_remember": spec.provider == "mcp_local" and local,
            "standing": bool(spec.provider == "mcp_local" and local
                             and current_hash
                             and self.standing.is_standing(
                                 spec.id, run.project_id, current_hash)),
        }

    def receipt(self, run: AgentRun, answer: str) -> dict[str, Any]:
        """The privacy receipt for this run, built from the accumulated ledger."""
        ledger = egress.Ledger(run.request_id, list(run.ledger_events))
        destination = run.model_destination or {"clase": egress.LOCAL, "host": ""}
        consent: dict[str, Any] = {
            "requerido": False, "otorgado": False, "alcance": "",
            "base": "no hubo consulta pública",
        }
        if destination.get("clase") == egress.THIRD_PARTY:
            consent["modelo_terceros"] = {
                "host": destination.get("host", ""), "autorizado": True,
                "pasajes": False,
            }
        receipt = egress.build_receipt(
            ledger, lane="público", route="local", answer=answer,
            consent=consent, model_destination=destination)
        receipt["agent"] = self.summary(run)
        return receipt
