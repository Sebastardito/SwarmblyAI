"""Rules for a node with the LCE installed acting as a worker (SPEC 9, I2).

``WorkerGuard`` wraps task execution for other clients. It enforces that the
backend serving the task is the base model declared in the node profile with
no personal adapter loaded, and that nothing from the task reaches any LCE
store. Its ``execute`` returns the result and keeps only aggregate
operational counters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .errors import InvariantViolation

__all__ = ["ServingBackend", "WorkerGuard"]


class ServingBackend(Protocol):
    model: str
    adapter: str | None

    def generate(self, prompt: str, **kw: Any) -> str:  # pragma: no cover - protocol
        ...


@dataclass
class WorkerGuard:
    declared_model: str
    counters: dict[str, int] = field(default_factory=lambda: {"tasks": 0, "bytes_in": 0, "bytes_out": 0})
    _sinks: list[Callable[[str], None]] = field(default_factory=list)

    def forbid_sink(self, sink: Callable[[str], None]) -> None:
        """Register an LCE store writer that must never receive task content."""
        self._sinks.append(sink)

    def check(self, backend: Any) -> None:
        model = getattr(backend, "model", None) or getattr(backend, "name", None)
        adapter = getattr(backend, "adapter", None)
        if adapter:
            raise InvariantViolation("I2", f"worker must serve the base model without a personal adapter (loaded: {adapter!r})")
        if model != self.declared_model:
            raise InvariantViolation("I2", f"serving model {model!r} differs from the declared base model {self.declared_model!r}")

    def execute(self, backend: Any, packet_prompt: str, **kw: Any) -> str:
        self.check(backend)
        out = backend.generate(packet_prompt, **kw)
        self.counters["tasks"] += 1
        self.counters["bytes_in"] += len(packet_prompt.encode("utf-8"))
        self.counters["bytes_out"] += len(out.encode("utf-8"))
        # Content is not retained anywhere: no sink is called, by construction.
        return out
