"""OpenAI-compatible backend (covers llama.cpp server, vLLM, OpenAI).

Uses /v1/chat/completions with ``stream: true`` (SSE). Requires no SDK: httpx
is enough.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

import httpx

from .base import BackendError, GenerationResult, Interrupted


class OpenAICompatBackend:
    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str = "",
                 timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as client:
                return client.get(f"{self.base_url}/models").status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.base_url}/models")
                resp.raise_for_status()
                return [m.get("id", "") for m in resp.json().get("data", [])]
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
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        started = time.monotonic()
        text_parts: list[str] = []
        prompt_tokens = completion_tokens = None
        finish_reason = "stop"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", f"{self.base_url}/chat/completions",
                                   json=payload, headers=headers) as resp:
                    if resp.status_code >= 400:
                        body = resp.read().decode("utf-8", "replace")[:400]
                        raise BackendError(f"HTTP {resp.status_code}: {body}")
                    for line in resp.iter_lines():
                        if interrupt and interrupt():
                            raise Interrupted("generation interrupted")
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        choice = (obj.get("choices") or [{}])[0]
                        delta = (choice.get("delta") or {}).get("content") or ""
                        if delta:
                            text_parts.append(delta)
                            if on_delta:
                                on_delta(delta)
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        usage = obj.get("usage")
                        if usage:
                            prompt_tokens = usage.get("prompt_tokens")
                            completion_tokens = usage.get("completion_tokens")
        except httpx.HTTPError as exc:
            raise BackendError(str(exc)) from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return GenerationResult(
            text="".join(text_parts), model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_ms=elapsed_ms, finish_reason=finish_reason,
            meta={"backend": self.name, "url": self.base_url})
