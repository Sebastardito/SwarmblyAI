"""Backend registry: resolves app config to a working inference backend."""

from __future__ import annotations

from typing import Any

from .anthropic import DEFAULT_URL as ANTHROPIC_DEFAULT_URL, AnthropicBackend
from .base import StreamBackend
from .ollama import DEFAULT_URL, OllamaBackend
from .openai_compat import OpenAICompatBackend

KNOWN_BACKENDS = ("auto", "ollama", "openai_compat", "anthropic")


class IncompleteSettings(RuntimeError):
    """The configured backend needs a URL / model the user has not set."""


def endpoint(backend: StreamBackend | None) -> str:
    """The address a backend sends to ("" if unknown)."""
    return str(getattr(backend, "url", "") or getattr(backend, "base_url", "") or "")


class BackendRegistry:
    """Builds backends from config and remembers the last working choice."""

    def __init__(self):
        self._last_backend: StreamBackend | None = None

    def resolve(self, config: dict[str, Any]) -> StreamBackend:
        model_cfg = config.get("model", {})
        backend = model_cfg.get("backend", "auto")
        url = model_cfg.get("backend_url", "") or ""
        if backend not in KNOWN_BACKENDS:
            raise IncompleteSettings(
                f"Unknown model backend {backend!r}. Choose auto, ollama, "
                "openai_compat or anthropic in Settings -> Models.")

        if backend == "anthropic":
            from ..keystore import get_secret
            candidate = AnthropicBackend(
                url or ANTHROPIC_DEFAULT_URL,
                api_key=get_secret("model.api_key") or model_cfg.get("api_key", ""))
            if model_cfg.get("think") is not None:
                candidate.think = bool(model_cfg.get("think"))
            self._last_backend = candidate
            return candidate

        if backend == "openai_compat":
            if not url:
                raise IncompleteSettings("OpenAI-compatible backend needs a URL")
            from ..keystore import get_secret
            candidate: StreamBackend = OpenAICompatBackend(
                url, api_key=get_secret("model.api_key") or model_cfg.get("api_key", ""))
            self._last_backend = candidate
            return candidate

        if backend == "ollama" or backend == "auto":
            candidate = OllamaBackend(url or DEFAULT_URL)
            if model_cfg.get("think") is not None:
                candidate.think = bool(model_cfg.get("think"))
            if backend == "ollama" or candidate.available():
                self._last_backend = candidate
                return candidate
        raise IncompleteSettings(
            "No inference backend is reachable. Start Ollama, or configure an "
            "OpenAI-compatible URL or Anthropic in Settings → Models.")

    def build(self, kind: str, url: str, api_key: str = "", think: bool | None = None) -> StreamBackend:
        """A backend for a role that runs on its own server (3.3)."""
        if kind == "anthropic":
            candidate: StreamBackend = AnthropicBackend(url or ANTHROPIC_DEFAULT_URL,
                                                        api_key=api_key)
            candidate.think = bool(think)
            return candidate
        if kind == "openai_compat":
            if not url:
                raise IncompleteSettings("OpenAI-compatible backend needs a URL")
            return OpenAICompatBackend(url, api_key=api_key)
        if kind in ("ollama", "auto"):
            candidate = OllamaBackend(url or DEFAULT_URL)
            candidate.think = think
            return candidate
        raise IncompleteSettings(
            f"Unknown backend kind {kind!r}. Choose ollama, openai_compat or anthropic.")

    def last(self) -> StreamBackend | None:
        return self._last_backend
