"""Ollama client wrapper for the Swarmbly reference implementation.

Zero-dependency HTTP client. Deterministic generation (temperature 0 + seed)
so that runs are reproducible, matching the whitepaper's measurement regime.
"""

import json
import urllib.request

BASE = "http://127.0.0.1:11434"


def _post(path, payload, timeout=900):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def generate(model, prompt, max_tokens=400, temperature=0.0, seed=0,
             num_ctx=4096, keep_alive="10m"):
    """Single non-streaming generation. Returns timing + counts + text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": num_ctx,
            "seed": seed,
        },
    }
    r = _post("/api/generate", payload)
    return {
        "text": r.get("response", ""),
        "eval_count": r.get("eval_count", 0),
        "prompt_eval_count": r.get("prompt_eval_count", 0),
        "total_duration_s": r.get("total_duration", 0) / 1e9,
        "load_duration_s": r.get("load_duration", 0) / 1e9,
    }


def embed(texts, model="nomic-embed-text"):
    """Embed a list of texts (batch endpoint). Returns list of vectors."""
    payload = {"model": model, "input": list(texts)}
    r = _post("/api/embed", payload, timeout=300)
    return r.get("embeddings", [])


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0
