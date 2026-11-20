"""Anthropic backend (native Messages API).

Uses ``POST /v1/messages`` with ``stream: true`` (SSE) and
``GET /v1/models`` for the model list. No SDK: httpx is enough.

Anthropic carries the system prompt in a top-level ``system`` field and only
accepts ``user``/``assistant`` turns in ``messages``; consecutive turns of the
same role are merged here. Thinking is off unless the caller or the configured
backend asks for it. When it is on, the request sends
``thinking: {type: "enabled", budget_tokens: N}`` (N below ``max_tokens``) and
omits ``temperature``, which the API does not accept together with thinking;
thinking text is kept in ``meta["thinking"]`` and never added to the answer.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

import httpx

from .. import egress, test_hosts
from .base import BackendError, GenerationResult, Interrupted

DEFAULT_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


def _error(status: int, error_type: str, message: str) -> BackendError:
    """Anthropic's errors on the app's single retryable backend error."""
    detail = f"{error_type}: {message}" if error_type and message else (message or error_type)
    if status in (401, 403) or error_type == "authentication_error":
        label = "authentication failed"
    elif status == 404 or error_type == "not_found_error":
        label = "model or endpoint not found"
    elif status == 429 or error_type == "rate_limit_error":
        label = "rate limited"
    elif status == 529 or error_type == "overloaded_error":
        label = "service overloaded"
    elif status >= 500 or error_type in ("api_error", "server_error"):
        label = "server error"
    else:
        label = "request rejected"
    where = f" (HTTP {status})" if status else ""
    return BackendError(f"Anthropic {label}{where}: {detail}".rstrip(": "))


def _http_error(status: int, body: str) -> BackendError:
    error_type, message = "", body[:400]
    try:
        data = json.loads(body)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            error_type = str(err.get("type") or "")
            message = str(err.get("message") or "")
    except ValueError:
        pass
    return _error(status, error_type, message)


def _sse_error(event: dict[str, Any]) -> BackendError:
    err = event.get("error") if isinstance(event.get("error"), dict) else event
    return _error(0, str(err.get("type") or ""), str(err.get("message") or ""))


def _content_text(content: Any) -> str:
    """Message content as text (Anthropic also allows a list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(b.get("text", "")) for b in content
                       if isinstance(b, dict) and b.get("type") == "text")
    return "" if content is None else str(content)


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, url: str = DEFAULT_URL, api_key: str = "",
                 timeout: float = 60.0):
        self.base_url = (url or DEFAULT_URL).rstrip("/")
        self.url = self.base_url
        self.api_key = api_key
        self.timeout = timeout
        self.think = False
        self.accepts_think = True

    # -- requests -----------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def _models_url(self) -> str:
        return f"{self.base_url}/v1/models"

    def _messages_url(self) -> str:
        return f"{self.base_url}/v1/messages"

    def _check(self, url: str, nbytes: int, reason: str) -> None:
        # Every request passes the destinations policy first, even a model list.
        egress.check_call(url, nbytes, reason=reason, kind=egress.QUESTION)

    def available(self) -> bool:
        """A cheap check that sends no user content: one model, one page."""
        url = self._models_url()
        try:
            self._check(url, 0, "comprobación de disponibilidad (Anthropic)")
            with test_hosts.httpx_client(timeout=2.0) as client:
                return client.get(url, params={"limit": 1},
                                  headers=self._headers()).status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """The account's models, following Anthropic's ``has_more``/``last_id``."""
        names: list[str] = []
        after_id = ""
        try:
            with test_hosts.httpx_client(timeout=3.0) as client:
                for _ in range(50):
                    params: dict[str, Any] = {"limit": 100}
                    if after_id:
                        params["after_id"] = after_id
                    url = self._models_url()
                    self._check(url, 0, "listado de modelos (Anthropic)")
                    resp = client.get(url, params=params, headers=self._headers())
                    resp.raise_for_status()
                    data = resp.json()
                    for item in data.get("data") or []:
                        name = str(item.get("id") or "")
                        if name:
                            names.append(name)
                    if not data.get("has_more"):
                        break
                    last_id = str(data.get("last_id") or "")
                    if not last_id or last_id == after_id:
                        break
                    after_id = last_id
        except Exception:
            return []
        return names

    # -- generation ---------------------------------------------------------------
    def _payload(self, messages: list[dict[str, str]], *, model: str,
                 max_tokens: int, temperature: float, system: str | None,
                 think: bool | None) -> dict[str, Any]:
        if think is None:
            think = self.think
        system_parts: list[str] = []
        if system:
            system_parts.append(str(system))
        turns: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role") or "").lower()
            content = _content_text(message.get("content"))
            if role == "system":
                system_parts.append(content)
            elif role in ("user", "assistant"):
                if turns and turns[-1]["role"] == role:
                    turns[-1]["content"] += "\n\n" + content
                else:
                    turns.append({"role": role, "content": content})
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens),
            "messages": turns,
            "stream": True,
        }
        if system_parts:
            payload["system"] = "\n\n".join(p for p in system_parts if p)
        budget = min(1024, int(max_tokens) - 1) if think else 0
        if budget >= 1:
            # N must stay below max_tokens; 1024 is Anthropic's usual budget.
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
        else:
            payload["temperature"] = temperature
        return payload

    def stream_chat(self, messages: list[dict[str, str]], *,
                    model: str, max_tokens: int = 1024,
                    temperature: float = 0.2,
                    on_delta: Callable[[str], None] | None = None,
                    interrupt: Callable[[], bool] | None = None,
                    system: str | None = None,
                    think: bool | None = None,
                    ) -> GenerationResult:
        if interrupt and interrupt():
            raise Interrupted("generation interrupted")
        thinking_enabled = self.think if think is None else bool(think)
        payload = self._payload(messages, model=model, max_tokens=max_tokens,
                                temperature=temperature, system=system,
                                think=thinking_enabled)
        url = self._messages_url()
        egress.check_call(url, len(json.dumps(payload).encode("utf-8")),
                          reason=f"modelo {model}")
        started = time.monotonic()
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        prompt_tokens = completion_tokens = None
        finish_reason = "stop"
        try:
            with test_hosts.httpx_client(timeout=self.timeout) as client:
                with client.stream("POST", url, json=payload,
                                   headers=self._headers()) as resp:
                    if resp.status_code >= 400:
                        body = resp.read().decode("utf-8", "replace")
                        raise _http_error(resp.status_code, body)
                    for line in resp.iter_lines():
                        if interrupt and interrupt():
                            raise Interrupted("generation interrupted")
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            event = json.loads(data)
                        except ValueError:
                            continue
                        kind = str(event.get("type") or "")
                        if kind == "message_start":
                            usage = ((event.get("message") or {}).get("usage") or {})
                            prompt_tokens = usage.get("input_tokens", prompt_tokens)
                        elif kind == "content_block_start":
                            block = event.get("content_block") or {}
                            if block.get("type") == "text" and block.get("text"):
                                text_parts.append(str(block["text"]))
                                if on_delta:
                                    on_delta(str(block["text"]))
                        elif kind == "content_block_delta":
                            delta = event.get("delta") or {}
                            delta_type = str(delta.get("type") or "")
                            if delta_type == "text_delta":
                                text = str(delta.get("text") or "")
                                if text:
                                    text_parts.append(text)
                                    if on_delta:
                                        on_delta(text)
                            elif delta_type == "thinking_delta" and thinking_enabled:
                                thinking_parts.append(str(delta.get("thinking") or ""))
                            # signature_delta and unknown deltas are ignored
                        elif kind == "message_delta":
                            delta = event.get("delta") or {}
                            if delta.get("stop_reason"):
                                finish_reason = str(delta["stop_reason"])
                            usage = event.get("usage") or {}
                            if usage.get("output_tokens") is not None:
                                completion_tokens = usage["output_tokens"]
                            if usage.get("input_tokens") is not None:
                                prompt_tokens = usage["input_tokens"]
                        elif kind == "message_stop":
                            break
                        elif kind == "error":
                            raise _sse_error(event)
                        # ping and unknown events are ignored
        except httpx.HTTPError as exc:
            raise BackendError(str(exc)) from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        meta: dict[str, Any] = {"backend": self.name, "url": self.base_url}
        if thinking_parts:
            meta["thinking"] = "".join(thinking_parts)
        return GenerationResult(
            text="".join(text_parts), model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_ms=elapsed_ms, finish_reason=finish_reason, meta=meta)
