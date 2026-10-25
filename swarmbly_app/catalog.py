"""Model catalog for recommendations and consented downloads.

Download sizes are the Ollama library sizes of the default tag; licences are
the model-card metadata of the publisher's Hugging Face page. Both were
checked on 2026-10-12 and can change: the download dialog links to the model
page, and after a download the app shows the licence Ollama itself reports
(``/api/show``). Nothing here is downloaded automatically.
"""

from __future__ import annotations

from typing import Any

CHECKED_ON = "2026-10-12"

CATALOG: list[dict[str, Any]] = [
    # name, family, params (B), download GB (Ollama default tag), licence, role
    {"name": "qwen2.5:0.5b", "family": "qwen2", "params_b": 0.5, "download_gb": 0.398,
     "license": "Apache-2.0", "page": "https://ollama.com/library/qwen2.5",
     "roles": ["worker"], "note": "tiny; only for very constrained machines"},
    {"name": "qwen2.5:1.5b", "family": "qwen2", "params_b": 1.5, "download_gb": 0.986,
     "license": "Apache-2.0", "page": "https://ollama.com/library/qwen2.5",
     "roles": ["worker", "chat"], "note": "small, permissive licence"},
    {"name": "llama3.2:1b", "family": "llama", "params_b": 1.0, "download_gb": 1.3,
     "license": "Llama 3.2 Community License", "page": "https://ollama.com/library/llama3.2",
     "roles": ["worker"], "note": "small Llama for low-memory workers"},
    {"name": "gemma2:2b", "family": "gemma2", "params_b": 2.6, "download_gb": 1.6,
     "license": "Gemma Terms of Use", "page": "https://ollama.com/library/gemma2",
     "roles": ["worker", "chat"], "note": "used as orchestrator in Swarmbly demos"},
    {"name": "qwen2.5:3b", "family": "qwen2", "params_b": 3.1, "download_gb": 1.9,
     "license": "Qwen Research License (non-commercial)",
     "page": "https://ollama.com/library/qwen2.5",
     "roles": ["worker", "chat"], "note": "benchmarked in Swarmbly runs; licence "
                                          "restricts commercial use"},
    {"name": "llama3.2:3b", "family": "llama", "params_b": 3.2, "download_gb": 2.0,
     "license": "Llama 3.2 Community License", "page": "https://ollama.com/library/llama3.2",
     "roles": ["worker", "chat"], "note": "standard Swarmbly SLM (benchmarked)"},
    {"name": "phi3.5:3.8b", "family": "phi3", "params_b": 3.8, "download_gb": 2.2,
     "license": "MIT", "page": "https://ollama.com/library/phi3.5",
     "roles": ["worker", "chat"], "note": "permissive licence, distinct family"},
    {"name": "qwen2.5:7b", "family": "qwen2", "params_b": 7.6, "download_gb": 4.7,
     "license": "Apache-2.0", "page": "https://ollama.com/library/qwen2.5",
     "roles": ["chat", "orchestrator", "worker"], "note": "strong generalist"},
    {"name": "llama3.1:8b", "family": "llama", "params_b": 8.0, "download_gb": 4.9,
     "license": "Llama 3.1 Community License", "page": "https://ollama.com/library/llama3.1",
     "roles": ["chat", "orchestrator", "worker"],
     "note": "8B-class orchestrator (whitepaper v2 H3 is unresolved)"},
    {"name": "nomic-embed-text", "family": "nomic-bert", "params_b": 0.137,
     "download_gb": 0.274, "license": "Apache-2.0",
     "page": "https://ollama.com/library/nomic-embed-text",
     "roles": ["embedding"], "note": "semantic seam similarity instead of lexical"},
]


def by_name(name: str) -> dict[str, Any] | None:
    for entry in CATALOG:
        if entry["name"] == name:
            return dict(entry, checked_on=CHECKED_ON)
    return None


def estimated_memory_gb(download_gb: float | None, params_b: float | None) -> float | None:
    """Rough resident memory of a 4-bit model with an 8k context.

    Weights ≈ download size; plus ~20 % runtime overhead and ~0.5 GB of KV
    cache / buffers. An *estimate* (marked as such everywhere); measure on
    the device before treating it as a requirement.
    """
    if download_gb is None and params_b is not None:
        download_gb = params_b * 0.6  # ≈ 4.8 bits/parameter incl. embeddings
    if download_gb is None:
        return None
    return round(download_gb * 1.2 + 0.5, 1)
