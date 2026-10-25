"""In-process event bus.

Events are the only mechanism the UI and the monitor consume: no polling.
Names follow ``domain.action`` (e.g. ``chat.delta``, ``request.stage``,
``node.discovered``). Payloads are JSON-serializable dicts.

Publishers may run on any thread (the chat engine and the P2P loop are
separate threads). Async subscribers (the WebSocket bridge) are therefore
dispatched onto a captured event loop with ``run_coroutine_threadsafe`` when
the publishing thread has no running loop of its own.
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable

Handler = Callable[[dict[str, Any]], None]
AsyncHandler = Callable[[dict[str, Any]], Any]


class EventBus:
    def __init__(self, history: int = 500):
        self._subscribers: list[Handler] = []
        self._async_subscribers: list[AsyncHandler] = []
        self._lock = threading.Lock()
        self._history: deque[dict[str, Any]] = deque(maxlen=history)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the main asyncio loop (uvicorn) for cross-thread dispatch."""
        with self._lock:
            self._loop = loop

    def subscribe(self, handler: Handler) -> None:
        with self._lock:
            self._subscribers.append(handler)

    def unsubscribe(self, handler: Handler) -> None:
        with self._lock:
            if handler in self._subscribers:
                self._subscribers.remove(handler)

    def subscribe_async(self, coro_handler: AsyncHandler) -> None:
        with self._lock:
            self._async_subscribers.append(coro_handler)

    def unsubscribe_async(self, coro_handler: AsyncHandler) -> None:
        with self._lock:
            if coro_handler in self._async_subscribers:
                self._async_subscribers.remove(coro_handler)

    def publish(self, event_type: str, **payload: Any) -> dict[str, Any]:
        event = {
            "id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "type": event_type,
            "payload": payload,
        }
        self._history.append(event)
        with self._lock:
            subs = list(self._subscribers)
            async_subs = list(self._async_subscribers)
            loop = self._loop
        for handler in subs:
            try:
                handler(event)
            except Exception:  # a subscriber must never break the publisher
                pass
        for coro_handler in async_subs:
            try:
                coro = coro_handler(event)
            except Exception:
                continue
            self._dispatch_async(coro, loop)
        return event

    def _dispatch_async(self, coro: Any, loop: asyncio.AbstractEventLoop | None) -> None:
        """Run the coroutine on the captured (UI) loop, whatever thread we are on.

        Publishers on *another* running loop (the P2P loop) must not schedule
        the WebSocket coroutine on their own loop: it would never reach the UI.
        """
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        try:
            if loop is not None and not loop.is_closed():
                if current is loop:
                    asyncio.ensure_future(coro)
                else:
                    asyncio.run_coroutine_threadsafe(coro, loop)
            elif current is not None:
                asyncio.ensure_future(coro)
            else:
                coro.close()  # no loop to deliver to (headless, no UI yet)
        except Exception:
            try:
                coro.close()
            except Exception:
                pass

    def recent(self, n: int = 100) -> list[dict[str, Any]]:
        return list(self._history)[-n:]
