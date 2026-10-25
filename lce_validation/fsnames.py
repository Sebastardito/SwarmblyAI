"""Portable file names for per-model caches.

Ollama model tags contain ``:`` (``gemma2:2b``), which Windows forbids in
file names. A cache named ``mara__gemma2:2b_wiki.json`` made the repository
impossible to check out on Windows (``git clone`` → "invalid path"), and so
impossible to install with ``pip`` there (SwarmblyApp, 17 October 2026).

Model tags are encoded reversibly with percent-encoding (``gemma2%3A2b``).
Readers fall back to the legacy name, so caches written before the change
still load on macOS and Linux.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote, unquote

SAFE = "._-"


def model_token(model: str) -> str:
    """``gemma2:2b`` → ``gemma2%3A2b`` (valid on every file system, reversible)."""
    return quote(model, safe=SAFE)


def token_model(token: str) -> str:
    return unquote(token)


def cache_file(cache: Path, uid: str, model: str, suffix: str) -> Path:
    """Path of ``{uid}__{model}{suffix}`` to read: the portable name, or the
    legacy one when only that exists (never on Windows)."""
    portable = cache / f"{uid}__{model_token(model)}{suffix}"
    if portable.exists() or os.name == "nt":
        return portable
    legacy = cache / f"{uid}__{model}{suffix}"
    return legacy if legacy.exists() else portable


def split_cache_name(name: str, suffix: str) -> tuple[str, str]:
    """``mara__gemma2%3A2b_wiki.json`` → ``("mara", "gemma2:2b")``."""
    uid, token = name[: -len(suffix)].split("__", 1)
    return uid, token_model(token)
