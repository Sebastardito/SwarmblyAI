"""Model manager: detect inference backends and their installed models.

Supported backends (spec §3.3): Ollama, OpenAI-compatible servers (covers
llama.cpp server and vLLM), and local llama.cpp detection. Never downloads
anything: recommendation only, downloads require explicit user action outside
the app (decision Q4).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import httpx

OLLAMA_DEFAULT_URL = "http://127.0.0.1:11434"


EMBEDDING_HINTS = ("embed", "bert", "minilm", "bge", "e5-", "gte-")


@dataclass
class DetectedModel:
    name: str
    family: str = ""
    size_bytes: int | None = None
    quantization: str = ""
    backend: str = "ollama"
    source: str = "backend"
    parameter_size: str = ""        # as reported, e.g. "3.2B"
    kind: str = "chat"              # chat | embedding

    @property
    def params_b(self) -> float | None:
        """Parameter count in billions, when the backend reports it."""
        text = (self.parameter_size or "").strip().upper()
        try:
            if text.endswith("B"):
                return float(text[:-1])
            if text.endswith("M"):
                return float(text[:-1]) / 1000.0
        except ValueError:
            return None
        return None


def classify_kind(name: str, family: str = "") -> str:
    label = f"{name} {family}".lower()
    return "embedding" if any(h in label for h in EMBEDDING_HINTS) else "chat"


@dataclass
class BackendInfo:
    name: str                       # ollama | openai_compat | llama_cpp
    url: str
    available: bool
    error: str = ""
    models: list[DetectedModel] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "available": self.available,
            "error": self.error,
            "models": [dict(m.__dict__, params_b=m.params_b) for m in (self.models or [])],
        }


class ModelManager:
    def __init__(self, timeout: float = 3.0):
        self._timeout = timeout
        self._lock = threading.Lock()
        self._cache: dict[str, BackendInfo] = {}
        self._cache_ts: float = 0.0

    def probe_ollama(self, url: str = OLLAMA_DEFAULT_URL) -> BackendInfo:
        info = BackendInfo(name="ollama", url=url, available=False)
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{url.rstrip('/')}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                info.available = True
                models = []
                for item in data.get("models", []):
                    name = item.get("name", "")
                    detail = item.get("details", {}) or {}
                    family = detail.get("family", "")
                    quant = detail.get("quantization_level", "")
                    models.append(DetectedModel(
                        name=name, family=family,
                        size_bytes=item.get("size") or None,
                        quantization=quant, backend="ollama",
                        source="ollama /api/tags",
                        parameter_size=str(detail.get("parameter_size") or ""),
                        kind=classify_kind(name, family)))
                info.models = models
        except httpx.HTTPError as exc:
            info.error = str(exc)
        except Exception as exc:  # pragma: no cover - defensive
            info.error = str(exc)
        return info

    def probe_openai_compat(self, url: str) -> BackendInfo:
        """An OpenAI-compatible /v1/models endpoint (llama.cpp server, vLLM…)."""
        base = url.rstrip("/")
        info = BackendInfo(name="openai_compat", url=base, available=False)
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{base}/models")
                resp.raise_for_status()
                data = resp.json()
                info.available = True
                models = []
                for item in data.get("data", []):
                    name = item.get("id", "")
                    models.append(DetectedModel(
                        name=name, backend="openai_compat",
                        source="openai-compatible /models",
                        kind=classify_kind(name)))
                info.models = models
        except httpx.HTTPError as exc:
            info.error = str(exc)
        except Exception as exc:  # pragma: no cover - defensive
            info.error = str(exc)
        return info

    def detect(self, configured_backend: str = "auto",
               configured_url: str = "") -> list[BackendInfo]:
        """Probe the configured backend; ``auto`` tries Ollama first."""
        infos: list[BackendInfo] = []
        if configured_backend == "openai_compat" and configured_url:
            infos.append(self.probe_openai_compat(configured_url))
            return infos
        ollama_url = configured_url or OLLAMA_DEFAULT_URL
        if configured_backend in ("auto", "ollama"):
            infos.append(self.probe_ollama(ollama_url))
        if configured_backend == "auto" and configured_url:
            infos.append(self.probe_openai_compat(configured_url))
        return infos

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()

    def detect_cached(self, configured_backend: str = "auto",
                      configured_url: str = "", ttl: float = 15.0) -> list[BackendInfo]:
        with self._lock:
            now = __import__("time").time()
            key = (configured_backend, configured_url)
            if key in self._cache and now - self._cache_ts < ttl:
                return self._cache[key]
            infos = self.detect(configured_backend, configured_url)
            self._cache[key] = infos
            self._cache_ts = now
            return infos

    def first_available_model(self, infos: list[BackendInfo],
                              preferred: str = "") -> tuple[str | None, BackendInfo | None]:
        """Pick a model: preferred name if present, else the first detected."""
        for info in infos:
            if not info.available or not info.models:
                continue
            if preferred:
                for model in info.models:
                    if model.name == preferred:
                        return model.name, info
            if info.models:
                return info.models[0].name, info
        return None, None

    def recommend(self, hardware: dict[str, Any]) -> list[dict[str, Any]]:
        """Size-class recommendations by RAM (never downloaded automatically)."""
        mem = (hardware.get("memory", {}).get("value", {}) or {}).get("total_bytes")
        gb = (mem / (1024 ** 3)) if mem else None
        if gb is None:
            size_class = "unknown"
        elif gb < 8:
            size_class = "<=2B"
        elif gb < 16:
            size_class = "3B"
        else:
            size_class = "7-8B"
        table = {
            "<=2B": [{"model": "gemma2:2b", "size_gb": 1.6, "why": "smallest RAM footprint"},
                     {"model": "qwen2.5:1.5b", "size_gb": 1.0, "why": "minimal footprint"}],
            "3B": [{"model": "llama3.2:3b", "size_gb": 2.0, "why": "standard Swarmbly SLM (benchmarked)"},
                   {"model": "qwen2.5:3b", "size_gb": 1.9, "why": "benchmarked in Swarmbly runs"}],
            "7-8B": [{"model": "llama3.1:8b", "size_gb": 4.9, "why": "orchestrator-class local model"},
                     {"model": "qwen2.5:7b", "size_gb": 4.7, "why": "strong generalist SLM"}],
            "unknown": [{"model": "llama3.2:3b", "size_gb": 2.0, "why": "safe default when RAM is unknown"}],
        }
        return [dict(item, install="ollama pull " + item["model"],
                     requires_authorization=True, source="ollama.com/library")
                for item in table[size_class]]
