"""Small fakes shared by the tests: no model, no network, no real clock."""

from __future__ import annotations

import copy
import json
from typing import Any

from swarmbly_agent import Allow, Deny, NeedsApproval, Observation, ToolDescriptor

TOOLS = [
    ToolDescriptor(
        name="echo",
        description="Return the text it was given.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )
]


class FakeClock:
    """A clock that moves only when a test says so."""

    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class ScriptedGenerate:
    """Replay a fixed list of actions and record every call."""

    def __init__(
        self,
        actions: list[Any],
        clock: FakeClock | None = None,
        advance: float = 0.0,
    ) -> None:
        self.actions = list(actions)
        self.calls: list[tuple[list[dict[str, str]], list[ToolDescriptor]]] = []
        self.clock = clock
        self.advance = advance

    def __call__(self, messages, tools):
        self.calls.append((copy.deepcopy(messages), list(tools)))
        if self.clock is not None:
            self.clock.advance(self.advance)
        if not self.actions:
            raise AssertionError("generate called more times than the script allows")
        action = self.actions.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


class RecordingExecutor:
    """Record every request and token, and return a fixed observation."""

    def __init__(
        self,
        observation: Observation | None = None,
        clock: FakeClock | None = None,
        advance: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self.observation = observation
        self.requests = []
        self.tokens = []
        self.clock = clock
        self.advance = advance
        self.error = error

    def __call__(self, request, token):
        self.requests.append(request)
        self.tokens.append(token)
        if self.clock is not None:
            self.clock.advance(self.advance)
        if self.error is not None:
            raise self.error
        if self.observation is not None:
            return self.observation
        return Observation(
            tool=request.tool,
            ok=True,
            content=json.dumps(request.arguments, sort_keys=True),
            source="test",
        )


def allow(_request) -> Allow:
    return Allow()


def deny(reason: str):
    def policy(_request) -> Deny:
        return Deny(reason)

    return policy


def needs_approval(reason: str):
    def policy(_request) -> NeedsApproval:
        return NeedsApproval(reason)

    return policy
