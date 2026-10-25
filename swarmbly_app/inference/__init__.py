"""Inference backends with progressive (streaming) output.

Two adapters share one minimal protocol (the same spirit as Swarmbly's
``Backend.generate(prompt, **kw)``): streaming deltas, completion callbacks,
interruption and usage metadata. The local chat uses these directly; the
distributed engine (Phase 2) wraps them into SPEC wire packets.
"""

from __future__ import annotations

from .ollama import OllamaBackend, ollama_chat
from .openai_compat import OpenAICompatBackend
from .registry import BackendRegistry, IncompleteSettings

__all__ = [
    "OllamaBackend",
    "OpenAICompatBackend",
    "BackendRegistry",
    "IncompleteSettings",
    "ollama_chat",
]
