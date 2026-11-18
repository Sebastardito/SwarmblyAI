"""Value types for the local agent runtime.

Everything in this module is a plain dataclass with a ``to_dict``/``from_dict``
pair, so a run can be written to disk and resumed without the runtime object.
The only imports are from the standard library.

The runtime keeps no state outside :class:`RunState`: after every step the
state describes exactly what happened, what is pending, and why the loop
stopped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

STATUSES = ("running", "awaiting_approval", "done", "stopped")


# --------------------------------------------------------------------------- #
# what the application offers
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ToolDescriptor:
    """A tool the model may ask for.

    The description and schema are data supplied by the application. They are
    shown to the model but cannot change the runtime's rules.
    """

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolDescriptor":
        return cls(
            name=_str(data.get("name"), "ToolDescriptor.name"),
            description=_str(data.get("description"), "ToolDescriptor.description"),
            input_schema=_dict(data.get("input_schema"), "ToolDescriptor.input_schema"),
        )


# --------------------------------------------------------------------------- #
# what the model decides
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Final:
    """The model's answer. ``parse_note`` explains a rejected JSON action."""

    text: str
    parse_note: str | None = None

    @property
    def note(self) -> str | None:
        """Alias for readers that call the parse note simply ``note``."""
        return self.parse_note

    def to_dict(self) -> dict[str, Any]:
        return {"type": "final", "text": self.text, "parse_note": self.parse_note}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Final":
        note = data.get("parse_note")
        if note is not None and not isinstance(note, str):
            raise ValueError("Final.parse_note must be a string or null")
        return cls(text=_str(data.get("text"), "Final.text"), parse_note=note)


@dataclass(frozen=True)
class ToolRequest:
    """A request for one tool call. Arguments are passed through unchanged."""

    tool: str
    arguments: dict[str, Any]
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": "tool", "tool": self.tool, "arguments": self.arguments, "why": self.why}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolRequest":
        why = data.get("why", "")
        if not isinstance(why, str):
            raise ValueError("ToolRequest.why must be a string")
        return cls(
            tool=_str(data.get("tool"), "ToolRequest.tool"),
            arguments=_dict(data.get("arguments"), "ToolRequest.arguments"),
            why=why,
        )


Action = Union[Final, ToolRequest]


def action_to_dict(action: Action) -> dict[str, Any]:
    if isinstance(action, (Final, ToolRequest)):
        return action.to_dict()
    raise TypeError(f"not an Action: {type(action).__name__}")


def action_from_dict(data: dict[str, Any]) -> Action:
    kind = data.get("type")
    if kind == "final":
        return Final.from_dict(data)
    if kind == "tool":
        return ToolRequest.from_dict(data)
    raise ValueError(f"unknown action type: {kind!r}")


# --------------------------------------------------------------------------- #
# what the tool returned
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Observation:
    """One tool result, already sized and labelled by the executor.

    ``sha256`` is the digest of the content *before* truncation, so the receipt
    still identifies the whole result. An empty digest is filled in by the
    runtime, which also applies ``Budget.max_observation_chars``.
    """

    tool: str
    ok: bool
    content: str
    source: str = "local"
    sha256: str = ""
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "content": self.content,
            "source": self.source,
            "sha256": self.sha256,
            "truncated": self.truncated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Observation":
        ok = data.get("ok")
        truncated = data.get("truncated", False)
        if not isinstance(ok, bool):
            raise ValueError("Observation.ok must be a boolean")
        if not isinstance(truncated, bool):
            raise ValueError("Observation.truncated must be a boolean")
        return cls(
            tool=_str(data.get("tool"), "Observation.tool"),
            ok=ok,
            content=_str(data.get("content"), "Observation.content"),
            source=_str(data.get("source", "local"), "Observation.source"),
            sha256=_str(data.get("sha256", ""), "Observation.sha256"),
            truncated=truncated,
        )


# --------------------------------------------------------------------------- #
# the policy's decision
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Allow:
    """The tool may run now."""


@dataclass(frozen=True)
class Deny:
    """The tool may not run. The reason is shown to the model as data."""

    reason: str


@dataclass(frozen=True)
class NeedsApproval:
    """The tool may run only after the user says yes."""

    reason: str


Decision = Union[Allow, Deny, NeedsApproval]


# --------------------------------------------------------------------------- #
# budget and record
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Budget:
    """Hard limits for one run.

    ``max_seconds`` is active execution time: time spent paused for approval is
    not counted. ``max_observation_chars`` truncates tool output, never the
    digest.
    """

    max_steps: int = 8
    max_tool_calls: int = 8
    max_seconds: float | None = None
    max_observation_chars: int | None = 4000

    def __post_init__(self) -> None:
        for name in ("max_steps", "max_tool_calls"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"Budget.{name} must be a non-negative integer")
        if self.max_seconds is not None:
            if isinstance(self.max_seconds, bool) or self.max_seconds < 0:
                raise ValueError("Budget.max_seconds must be non-negative or null")
        if self.max_observation_chars is not None:
            value = self.max_observation_chars
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(
                    "Budget.max_observation_chars must be a non-negative integer or null"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_steps": self.max_steps,
            "max_tool_calls": self.max_tool_calls,
            "max_seconds": self.max_seconds,
            "max_observation_chars": self.max_observation_chars,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Budget":
        return cls(
            max_steps=data.get("max_steps", 8),
            max_tool_calls=data.get("max_tool_calls", 8),
            max_seconds=data.get("max_seconds"),
            max_observation_chars=data.get("max_observation_chars", 4000),
        )


@dataclass
class Step:
    """One decision, its observation, and when it ran.

    A step without an observation is either a final answer or a tool request
    that was not executed (paused for approval, or stopped by a budget).
    """

    index: int
    action: Action
    observation: Observation | None = None
    started: float = 0.0
    ended: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "action": action_to_dict(self.action),
            "observation": None if self.observation is None else self.observation.to_dict(),
            "started": self.started,
            "ended": self.ended,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Step":
        index = data.get("index")
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError("Step.index must be an integer")
        started = data.get("started", 0.0)
        ended = data.get("ended")
        if not isinstance(started, (int, float)) or isinstance(started, bool):
            raise ValueError("Step.started must be a number")
        if ended is not None and (
            not isinstance(ended, (int, float)) or isinstance(ended, bool)
        ):
            raise ValueError("Step.ended must be a number or null")
        raw = data.get("observation")
        return cls(
            index=index,
            action=action_from_dict(_dict(data.get("action"), "Step.action")),
            observation=None if raw is None else Observation.from_dict(_dict(raw, "Step.observation")),
            started=float(started),
            ended=None if ended is None else float(ended),
        )


@dataclass
class RunState:
    """The whole record of a run: no hidden state lives in the runtime."""

    status: str
    steps: list[Step] = field(default_factory=list)
    pending: ToolRequest | None = None
    stop_reason: str | None = None
    task: str = ""
    tools: list[ToolDescriptor] = field(default_factory=list)
    tool_calls: int = 0
    elapsed_seconds: float = 0.0
    pending_reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown status: {self.status!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "steps": [step.to_dict() for step in self.steps],
            "pending": None if self.pending is None else self.pending.to_dict(),
            "stop_reason": self.stop_reason,
            "task": self.task,
            "tools": [tool.to_dict() for tool in self.tools],
            "tool_calls": self.tool_calls,
            "elapsed_seconds": self.elapsed_seconds,
            "pending_reason": self.pending_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        status = _str(data.get("status"), "RunState.status")
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status!r}")
        raw_pending = data.get("pending")
        pending: ToolRequest | None = None
        if raw_pending is not None:
            action = action_from_dict(_dict(raw_pending, "RunState.pending"))
            if not isinstance(action, ToolRequest):
                raise ValueError("RunState.pending must be a tool request")
            pending = action
        stop_reason = data.get("stop_reason")
        if stop_reason is not None and not isinstance(stop_reason, str):
            raise ValueError("RunState.stop_reason must be a string or null")
        pending_reason = data.get("pending_reason")
        if pending_reason is not None and not isinstance(pending_reason, str):
            raise ValueError("RunState.pending_reason must be a string or null")
        tool_calls = data.get("tool_calls", 0)
        if not isinstance(tool_calls, int) or isinstance(tool_calls, bool):
            raise ValueError("RunState.tool_calls must be an integer")
        elapsed = data.get("elapsed_seconds", 0.0)
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool):
            raise ValueError("RunState.elapsed_seconds must be a number")
        return cls(
            status=status,
            steps=[Step.from_dict(_dict(raw, "RunState.steps[]")) for raw in data.get("steps", [])],
            pending=pending,
            stop_reason=stop_reason,
            task=_str(data.get("task", ""), "RunState.task"),
            tools=[ToolDescriptor.from_dict(_dict(raw, "RunState.tools[]")) for raw in data.get("tools", [])],
            tool_calls=tool_calls,
            elapsed_seconds=float(elapsed),
            pending_reason=pending_reason,
        )


# --------------------------------------------------------------------------- #
# small validators, so a corrupt state fails here rather than mid-loop
# --------------------------------------------------------------------------- #

def _str(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{where} must be a string")
    return value


def _dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value
