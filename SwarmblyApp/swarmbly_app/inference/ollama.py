"""Ollama backend (native streaming /api/chat)."""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

from .base import BackendError, GenerationResult, Interrupted

DEFAULT_URL = "http://127.0.0.1:11434"


def _stream_lines(response: httpx.Response):
    """Ollama returns one JSON object per line."""
    for line in response.iter_lines():
        if line:
            yield line


COLD_LOAD_READ_S = 90.0   # first chunk after a cold model load


class OllamaBackend:
    name = "ollama"

    def __init__(self, url: str = DEFAULT_URL, timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as client:
                return client.get(f"{self.url}/api/tags").status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.url}/api/tags")
                resp.raise_for_status()
                return [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception:
            return []

    def stream_chat(self, messages: list[dict[str, str]], *,
                    model: str, max_tokens: int = 1024,
                    temperature: float = 0.2,
                    on_delta: Callable[[str], None] | None = None,
                    interrupt: Callable[[], bool] | None = None,
                    system: str | None = None,
                    ) -> GenerationResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": ([{"role": "system", "content": system}] if system else [])
                        + list(messages),
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        started = time.monotonic()
        text_parts: list[str] = []
        prompt_tokens = completion_tokens = load_ns = None
        finish_reason = "stop"
        try:
            # The first chunk only arrives once the model is in memory: a cold
            # load took more than 30 s on a Windows node and every such task
            # failed as "timed out" (P3k.1, 23 Oct 2026). Connecting still
            # fails fast; callers stop long generations with ``interrupt``.
            timeout = httpx.Timeout(self.timeout, read=max(self.timeout, COLD_LOAD_READ_S))
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", f"{self.url}/api/chat", json=payload) as resp:
                    if resp.status_code >= 400:
                        body = resp.read().decode("utf-8", "replace")[:400]
                        raise BackendError(f"Ollama HTTP {resp.status_code}: {body}")
                    for line in resp.iter_lines():
                        if interrupt and interrupt():
                            raise Interrupted("generation interrupted")
                        if not line:
                            continue
                        try:
                            obj = __import__("json").loads(line)
                        except ValueError:
                            continue
                        delta = (obj.get("message") or {}).get("content") or ""
                        if delta:
                            text_parts.append(delta)
                            if on_delta:
                                on_delta(delta)
                        if obj.get("done"):
                            prompt_tokens = obj.get("prompt_eval_count")
                            completion_tokens = obj.get("eval_count")
                            finish_reason = obj.get("done_reason") or "stop"
                            load_ns = obj.get("load_duration")
                            break
        except httpx.HTTPError as exc:
            raise BackendError(str(exc)) from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return GenerationResult(
            text="".join(text_parts), model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_ms=elapsed_ms, finish_reason=finish_reason,
            meta={"backend": self.name, "url": self.url,
                  # time Ollama spent loading the model into memory: a cold
                  # load is not generation speed (P3k, 23 Oct 2026)
                  "load_ms": (int(load_ns / 1e6) if isinstance(load_ns, (int, float))
                              else None)})


# Backwards-friendly helper mirroring the OpenAI-style call shape.
def ollama_chat(url: str, model: str, messages: list[dict[str, str]], **kw: Any) -> GenerationResult:
    return OllamaBackend(url=url).stream_chat(messages, model=model, **kw)
