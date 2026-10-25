"""Backend registry: resolves app config to a working inference backend."""

from __future__ import annotations

from typing import Any

from .base import StreamBackend
from .ollama import DEFAULT_URL, OllamaBackend
from .openai_compat import OpenAICompatBackend


class IncompleteSettings(RuntimeError):
    """The configured backend needs a URL / model the user has not set."""


class BackendRegistry:
    """Builds backends from config and remembers the last working choice."""

    def __init__(self):
        self._last_backend: StreamBackend | None = None

    def resolve(self, config: dict[str, Any]) -> StreamBackend:
        model_cfg = config.get("model", {})
        backend = model_cfg.get("backend", "auto")
        url = model_cfg.get("backend_url", "") or ""

        if backend == "openai_compat":
            if not url:
                raise IncompleteSettings("OpenAI-compatible backend needs a URL")
            candidate: StreamBackend = OpenAICompatBackend(
                url, api_key=model_cfg.get("api_key", ""))
            self._last_backend = candidate
            return candidate

        if backend == "ollama" or backend == "auto":
            candidate = OllamaBackend(url or DEFAULT_URL)
            if backend == "ollama" or candidate.available():
                self._last_backend = candidate
                return candidate
        raise IncompleteSettings(
            "No inference backend is reachable. Start Ollama or configure an "
            "OpenAI-compatible URL in Settings → Models.")

    def last(self) -> StreamBackend | None:
        return self._last_backend
