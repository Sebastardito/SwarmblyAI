"""Model capability from its tag, for routing on a heterogeneous swarm.

On the first heterogeneous network (21 October 2026: a 512 GB server
offering qwen2.5:7b and llama3.1:8b next to 8 GB laptops with 0.5–1.5 B
models) the scheduler chose a *family* per node and the worker took the
first model of that family it listed — llama3.2:1b instead of llama3.1:8b,
qwen2.5:1.5b answering by echoing its input. Capability was never
considered.

The only capability signal every node already advertises is the model tag,
which for Ollama carries the parameter count (``qwen2.5:7b``,
``phi3.5:3.8b``). It is a coarse proxy — size is not quality — but it is
honest, local and needs no benchmark.
"""

from __future__ import annotations

import re

_SIZE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z])")
UNKNOWN_PARAMS_B = 3.0     # a tag without a size ranks as a mid-size model


def model_params_b(tag: str) -> float | None:
    """Billions of parameters stated in a model tag, or ``None``."""
    tag = tag or ""
    for part in (tag.split(":", 1)[1] if ":" in tag else "", tag):
        match = _SIZE.search(part)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def rank_params(tag: str) -> float:
    size = model_params_b(tag)
    return UNKNOWN_PARAMS_B if size is None else size


def eligible(tag: str, min_params_b: float) -> bool:
    """Below ``min_params_b`` a model is not used for generation; tags without
    a size are always eligible (the owner chose to share them)."""
    size = model_params_b(tag)
    return size is None or size >= min_params_b
