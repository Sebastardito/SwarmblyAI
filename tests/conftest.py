"""Shared fixtures: isolated data dir, app state, fake backend."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_app.chat import ChatService  # noqa: E402
from swarmbly_app.db import Database  # noqa: E402
from swarmbly_app.events import EventBus  # noqa: E402
from swarmbly_app.inference.base import GenerationResult  # noqa: E402
from swarmbly_app.state import AppState  # noqa: E402


class FakeBackend:
    """Deterministic in-memory backend for chat/engine tests."""

    name = "fake"

    def __init__(self, reply: str = "Hello from the fake backend.",
                 delay: float = 0.0, fail: bool = False):
        self.reply = reply
        self.delay = delay
        self.fail = fail
        self.calls: list[dict] = []

    def available(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["fake-model:1b"]

    def stream_chat(self, messages, *, model, max_tokens=1024,
                    temperature=0.2, on_delta=None, interrupt=None,
                    system=None, **kw):
        self.calls.append({"messages": messages, "model": model})
        if self.delay:
            import time as _t
            _t.sleep(self.delay)
        if self.fail:
            from swarmbly_app.inference.base import BackendError
            raise BackendError("simulated backend failure")
        if interrupt and interrupt():
            from swarmbly_app.inference.base import Interrupted
            raise Interrupted("interrupted")
        if on_delta:
            for word in self.reply.split(" "):
                on_delta(word + " ")
        return GenerationResult(text=self.reply, model=model,
                                completion_tokens=len(self.reply.split()),
                                total_ms=12)


@pytest.fixture()
def app_state(tmp_path: Path) -> AppState:
    state = AppState(str(tmp_path / "data"))
    # Public evidence is on by default; tests stay off the network unless
    # they turn it on with fake providers.
    state.config.update({"evidence.enabled": False})
    yield state
    state.stop()


@pytest.fixture()
def fake_chat(app_state: AppState) -> tuple[ChatService, FakeBackend]:
    fake = FakeBackend()
    app_state.backends.resolve = lambda config=None: fake  # type: ignore[method-assign]
    return app_state.chat, fake
