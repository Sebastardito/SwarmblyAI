#!/usr/bin/env python3
"""A deterministic, local Ollama stand-in for the CI batteries.

The real App talks to Ollama through ``/api/tags``, ``/api/chat`` (streaming
NDJSON) and ``/api/embed``.  This server answers all three with fixed values so
the team and node-loss batteries can run without a model, without a GPU and
without network access.

It is not a model: the answer is a short deterministic text derived from the
prompt, and embeddings are a deterministic hash vector.  Only tests and open
batteries use it; the maintainer's real-model run uses Ollama.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable


def _vector(text: str, dim: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [round((digest[i] / 255.0) * 2 - 1, 6) for i in range(dim)]


def default_answer(prompt: str, model: str) -> str:
    """A stable answer that is different for different prompts."""
    line = " ".join(str(prompt or "").split())[:220]
    return f"[{model}] {line}" if line else f"[{model}] listo"


class FakeOllama:
    """Serve the three Ollama routes on loopback.

    ``delay_s`` slows every generation; ``delay_prompt`` may return a bigger
    delay for one prompt (used to kill a node while it is generating).
    ``answer`` overrides :func:`default_answer`.
    """

    def __init__(self, *, models: tuple[str, ...] = ("fake:7b",),
                 delay_s: float = 0.0,
                 answer: Callable[[str, str], str] | None = None,
                 delay_prompt: Callable[[str, str], float] | None = None) -> None:
        self.models = list(models)
        self.delay_s = max(0.0, float(delay_s))
        self.answer = answer or default_answer
        self.delay_prompt = delay_prompt
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                return

            def _json(self, data: Any, status: int = 200) -> None:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0].rstrip("/")
                if path == "/api/tags":
                    self._json({"models": [{"name": name, "model": name}
                                           for name in server.models]})
                elif path == "/api/version":
                    self._json({"version": "fake-1.0"})
                else:
                    self._json({"error": "not found"}, 404)

            def do_POST(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0].rstrip("/")
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    body = {}
                model = str(body.get("model") or "")
                if path == "/api/chat":
                    messages = body.get("messages") or []
                    prompt = "\n".join(str(m.get("content") or "") for m in messages
                                       if isinstance(m, dict))
                    with server._lock:
                        server.requests.append({"route": "chat", "model": model,
                                                "prompt": prompt, "t": time.time()})
                    delay = server.delay_s
                    if server.delay_prompt is not None:
                        delay = max(delay, float(server.delay_prompt(prompt, model)))
                    if delay:
                        time.sleep(delay)
                    text = server.answer(prompt, model)
                    lines = [
                        {"model": model, "created_at": "", "done": False,
                         "message": {"role": "assistant", "content": text}},
                        {"model": model, "created_at": "", "done": True,
                         "done_reason": "stop", "prompt_eval_count": 8,
                         "eval_count": max(1, len(text.split()))},
                    ]
                    raw = ("\n".join(json.dumps(line) for line in lines) + "\n").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                elif path == "/api/embed":
                    texts = body.get("input") or []
                    if isinstance(texts, str):
                        texts = [texts]
                    with server._lock:
                        server.requests.append({"route": "embed", "model": model,
                                                "texts": list(texts), "t": time.time()})
                    self._json({"embeddings": [_vector(str(t)) for t in texts]})
                else:
                    self._json({"error": "not found"}, 404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def prompts(self) -> list[str]:
        with self._lock:
            return [item["prompt"] for item in self.requests if item["route"] == "chat"]

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self) -> "FakeOllama":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
