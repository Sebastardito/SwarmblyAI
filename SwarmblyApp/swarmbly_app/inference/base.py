"""Common types for inference backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Protocol

DeltaHandler = Callable[[str], None]


@dataclass
class GenerationResult:
    text: str
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_ms: int | None = None
    finish_reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_ms": self.total_ms,
            "finish_reason": self.finish_reason,
            "meta": self.meta,
        }


class GenerationError(RuntimeError):
    pass


class Interrupted(GenerationError):
    """The user (or a timeout) stopped generation."""


class BackendError(GenerationError):
    """The backend refused or failed; the request may be retried."""


class StreamBackend(Protocol):
    """Minimal streaming backend protocol used across the app."""

    name: str

    def stream_chat(self, messages: list[dict[str, str]], *,
                    model: str, max_tokens: int, temperature: float,
                    on_delta: DeltaHandler | None = None,
                    interrupt: Callable[[], bool] | None = None,
                    ) -> GenerationResult:
        """Generate one chat completion, emitting deltas as they arrive.

        ``interrupt()`` returning True aborts generation and raises
        :class:`Interrupted`.
        """
        ...

    def available(self) -> bool:
        ...

    def list_models(self) -> list[str]:
        ...
