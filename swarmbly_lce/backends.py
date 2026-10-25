"""Generation and embedding backends.

``Backend`` is the same minimal protocol used by Swarmbly's ``swarmbly_v0``
(``generate(prompt, **kw) -> str`` and ``embed(texts) -> ndarray``), so the
two code bases can share backends without importing each other.

.. warning::
   **MockBackend is a HARNESS-VALIDATION tool, NOT evidence about real
   models.** It does not do inference. It answers the LCE's structured
   prompts with deterministic rules and *deliberately injects* the effects
   the harness must be able to detect: wrong answers that are shared across
   "families" with a configurable probability (the correlated-error effect
   of Kim et al., 2025) and style that follows the projected Γ fields. Any
   curve produced with it exists by construction. **No number produced with
   MockBackend may be cited as a result about language models.**
"""

from __future__ import annotations

import hashlib
import json
import zlib
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from random import Random
from typing import Any, Protocol, Sequence, runtime_checkable

import numpy as np

__all__ = [
    "Backend",
    "BackendUnavailable",
    "HashEmbedder",
    "MockBackend",
    "OpenAICompatBackend",
    "get_backend",
    "PROMPT_MARKERS",
]

PROMPT_MARKERS = {
    "extract": "TASK: EXTRACT_CLAIMS",
    "answer": "TASK: ANSWER",
    "write": "TASK: WRITE",
    "support": "Answer only YES or NO",
    "mcq": "TASK: MCQ",
}


class BackendUnavailable(RuntimeError):
    """A remote backend cannot be reached or is misconfigured."""


@runtime_checkable
class Backend(Protocol):
    name: str
    family: str

    def generate(self, prompt: str, **kw: Any) -> str:  # pragma: no cover - protocol
        ...

    def embed(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover - protocol
        ...


_TOKEN = re.compile(r"[\wáéíóúñü]+", re.IGNORECASE)


def _stable(text: str) -> int:
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


@dataclass
class HashEmbedder:
    """Feature-hashing embedder over word unigrams and bigrams. Offline, deterministic."""

    dim: int = 512

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float64)
        for i, t in enumerate(texts):
            toks = [w.lower() for w in _TOKEN.findall(t)]
            feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
            for f in feats:
                h = _stable(f)
                out[i, h % self.dim] += 1.0 if (h >> 32) & 1 else -1.0
            n = np.linalg.norm(out[i])
            if n > 0:
                out[i] /= n
        return out


def _sentences(text: str) -> list[tuple[int, int, str]]:
    out = []
    for m in re.finditer(r"[^.!?\n]+[.!?]?", text):
        s = m.group(0)
        stripped = s.strip()
        if len(stripped) >= 12:
            lead = len(s) - len(s.lstrip())
            out.append((m.start() + lead, m.start() + lead + len(stripped), stripped))
    return out


_TYPE_RULES = [
    ("preference", re.compile(r"\b(prefiero|prefer|i like|me gusta|always use|uso siempre)\b", re.I)),
    ("style", re.compile(r"\b(escribo|i write|my style|mi estilo|suelo decir|i usually say|registro)\b", re.I)),
    ("procedure", re.compile(r"\b(primero|first,|then|luego|steps?|pasos?|procedimiento|procedure)\b", re.I)),
    ("belief", re.compile(r"\b(creo que|i believe|i think|pienso que)\b", re.I)),
    ("opinion", re.compile(r"\b(en mi opini[oó]n|in my opinion)\b", re.I)),
    ("hypothesis", re.compile(r"\b(hip[oó]tesis|hypothesis|quiz[aá]s|perhaps|might)\b", re.I)),
    ("experience", re.compile(r"\b(ayer|yesterday|last week|la semana pasada|hoy|today)\b", re.I)),
]


def _guess_type(sentence: str) -> str:
    for t, rx in _TYPE_RULES:
        if rx.search(sentence):
            return t
    return "fact"


@dataclass
class MockBackend:
    """Deterministic rule-based stand-in for an SLM. See the module warning."""

    family: str = "mock-a"
    seed: int = 0
    shared_error_rate: float = 0.6
    base_accuracy: float = 0.55
    name: str = "mock"
    embedder: HashEmbedder = field(default_factory=HashEmbedder)
    calls: int = 0

    def for_family(self, family: str) -> "MockBackend":
        return MockBackend(family=family, seed=self.seed, shared_error_rate=self.shared_error_rate,
                           base_accuracy=self.base_accuracy, embedder=self.embedder)

    # -- protocol ---------------------------------------------------------------
    def generate(self, prompt: str, **kw: Any) -> str:
        self.calls += 1
        if PROMPT_MARKERS["support"] in prompt:
            return self._support(prompt)
        if PROMPT_MARKERS["extract"] in prompt:
            return self._extract(prompt)
        if PROMPT_MARKERS["answer"] in prompt:
            return self._answer(prompt)
        if PROMPT_MARKERS["write"] in prompt:
            return self._write(prompt, float(kw.get("temperature", 0.0)), int(kw.get("seed", 0)))
        if PROMPT_MARKERS["mcq"] in prompt:
            return self._mcq(prompt)
        return "OK"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return self.embedder.embed(texts)

    # -- behaviours -------------------------------------------------------------
    @staticmethod
    def _field(prompt: str, name: str) -> str:
        m = re.search(rf"^{name}:\s*(.*?)(?=^\w[\w ]*:|\Z)", prompt, re.S | re.M)
        return m.group(1).strip() if m else ""

    def _support(self, prompt: str) -> str:
        span = self._field(prompt, "SOURCE PASSAGE")
        claim = self._field(prompt, "CLAIM")
        cw = {w.lower() for w in _TOKEN.findall(claim) if len(w) > 3}
        sw = {w.lower() for w in _TOKEN.findall(span)}
        return "YES" if cw and len(cw & sw) / len(cw) >= 0.6 else "NO"

    def _extract(self, prompt: str) -> str:
        passage = self._field(prompt, "PASSAGE")
        items = [{"text": s, "type": _guess_type(s), "start": a, "end": b, "quote": s} for a, b, s in _sentences(passage)]
        return json.dumps({"claims": items}, ensure_ascii=False)

    def _answer(self, prompt: str) -> str:
        question = self._field(prompt, "QUESTION")
        context = self._field(prompt, "CONTEXT")
        qw = {w.lower() for w in _TOKEN.findall(question) if len(w) > 3}
        if context:
            best, score = "", 0.0
            for _, _, s in _sentences(context):
                sw = {w.lower() for w in _TOKEN.findall(s)}
                sc = len(qw & sw) / max(1, len(qw))
                if sc > score:
                    best, score = s, sc
            if score >= 0.5:
                return best
        # No usable context: answer "from parametric memory". Correctness and the
        # identity of the wrong answer are deterministic functions of the question,
        # with a shared wrong answer across families (correlated errors).
        rng = Random(_stable(f"{self.seed}|{question}|{self.family}"))
        shared = Random(_stable(f"{self.seed}|{question}|shared"))
        if shared.random() < self.base_accuracy:
            return f"CORRECT::{_stable(question) % 997}"
        if rng.random() < self.shared_error_rate:
            return f"WRONG::shared::{_stable(question) % 991}"
        return f"WRONG::{self.family}::{_stable(question + self.family) % 983}"

    def _mcq(self, prompt: str) -> str:
        # Synthetic arithmetic items only ("What is a + b?"). The STYLE line is
        # ignored, so projection cannot change errors here: by construction.
        q = self._field(prompt, "QUESTION").splitlines()[0]
        m = re.search(r"(-?\d+)\s*\+\s*(-?\d+)", q)
        opts = dict(re.findall(r"^([ABCD])\. (.*)$", prompt, re.M))
        if not m or len(opts) != 4:
            return "A"
        gold = next((L for L, v in opts.items() if v.strip() == str(int(m.group(1)) + int(m.group(2)))), "A")
        wrong = [L for L in "ABCD" if L != gold]
        shared = Random(_stable(f"{self.seed}|{q}|shared"))
        if shared.random() < self.base_accuracy:
            return gold
        if Random(_stable(f"{self.seed}|{q}|{self.family}")).random() < self.shared_error_rate:
            return wrong[_stable(q) % 3]
        return wrong[_stable(q + self.family) % 3]

    def _write(self, prompt: str, temperature: float = 0.0, seed: int = 0) -> str:
        topic = self._field(prompt, "TOPIC") or "the topic"
        register = self._field(prompt, "REGISTER")
        lexicon = [w.strip() for w in self._field(prompt, "LEXICON").split(",") if w.strip()]
        style = self._field(prompt, "STYLE_SEED")
        # Shared "hivemind" core shared by every family, then per-user variation
        # carried only by the projected Γ fields.
        core = f"A clear overview of {topic}, covering its definition, main uses and limits."
        parts = [core]
        if register:
            parts.append(f"Written in a {register} register.")
        if lexicon:
            parts.append("Key terms: " + ", ".join(lexicon) + ".")
        if style:
            parts.append(style.rstrip(".") + ".")
        if temperature > 0:
            # Emulates decoding variation between samples (seeded), so that a
            # baseline without Γ is not identical by construction.
            fillers = ["It is an active field.", "Its limits are debated.", "It has practical uses.",
                       "Several approaches exist.", "It keeps evolving."]
            parts.append(fillers[Random(_stable(f"{topic}|{seed}")).randrange(len(fillers))])
        return " ".join(parts)


@dataclass
class OpenAICompatBackend:
    """Client for any OpenAI-compatible endpoint (Ollama, llama.cpp, vLLM, LM Studio).

    Stdlib only. ``base_url`` defaults to Ollama's ``http://localhost:11434/v1``.
    """

    model: str
    base_url: str = "http://localhost:11434/v1"
    family: str = ""
    api_key: str = ""
    timeout: float = 120.0
    retries: int = 2
    name: str = "openai-compat"
    embed_model: str = ""
    _fallback: HashEmbedder = field(default_factory=HashEmbedder)

    def __post_init__(self) -> None:
        if not self.family:
            self.family = self.model.split(":")[0].split("/")[-1]
        self.api_key = self.api_key or os.environ.get("LCE_API_KEY", "")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + path
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last = exc
                time.sleep(min(2.0 * (attempt + 1), 6.0))
        raise BackendUnavailable(f"{url}: {last}")

    def generate(self, prompt: str, **kw: Any) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(kw.get("temperature", 0.0)),
            "max_tokens": int(kw.get("max_tokens", 512)),
        }
        if "seed" in kw:
            payload["seed"] = int(kw["seed"])
        data = self._post("/chat/completions", payload)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendUnavailable(f"malformed response: {str(data)[:200]}") from exc

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not self.embed_model:
            return self._fallback.embed(texts)
        data = self._post("/embeddings", {"model": self.embed_model, "input": list(texts)})
        arr = np.array([d["embedding"] for d in data["data"]], dtype=np.float64)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms


@dataclass
class OllamaNativeBackend:
    """Client for Ollama's NATIVE /api/generate with a deterministic seed.

    The seed is derived from the prompt text (stable across runs and call
    order): the same prompt always gets the same seed, so digestion is
    reproducible run to run. AA3 (Enmienda 6) showed the native endpoint's
    seed is effective (100 % identical writes at T = 0.7) while the
    OpenAI-compatible endpoint's is not; the re-run criterion of R14 adopts
    this backend for digestion (Enmienda 7).
    """

    model: str
    base_url: str = "http://localhost:11434"
    family: str = ""
    timeout: float = 300.0
    retries: int = 2
    name: str = "ollama-native"
    embed_model: str = ""
    _fallback: HashEmbedder = field(default_factory=HashEmbedder)

    def __post_init__(self) -> None:
        if not self.family:
            self.family = self.model.split(":")[0].split("/")[-1]

    @staticmethod
    def _seed_for(prompt: str) -> int:
        return zlib.crc32(prompt.encode("utf-8")) & 0x7FFFFFFF

    def generate(self, prompt: str, **kw: Any) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(kw.get("temperature", 0.0)),
                "seed": int(kw.get("seed", self._seed_for(prompt))),
                "num_predict": int(kw.get("max_tokens", 512)),
            },
        }
        url = self.base_url.rstrip("/") + "/api/generate"
        body = json.dumps(payload).encode("utf-8")
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, data=body,
                                             headers={"Content-Type": "application/json"},
                                             method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8")).get("response", "")
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last = exc
                time.sleep(min(2.0 * (attempt + 1), 6.0))
        raise BackendUnavailable(f"{url}: {last}")

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not self.embed_model:
            return self._fallback.embed(texts)
        data = self._post_embed(texts)
        arr = np.array([d["embedding"] for d in data["embeddings"]], dtype=np.float64)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def _post_embed(self, texts: Sequence[str]) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + "/api/embed"
        body = json.dumps({"model": self.embed_model, "input": list(texts)}).encode("utf-8")
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def get_backend(name: str = "mock", **kw: Any) -> Backend:
    if name == "mock":
        return MockBackend(**kw)
    if name in {"ollama", "openai", "openai-compat"}:
        return OpenAICompatBackend(**kw)
    if name == "ollama-native":
        return OllamaNativeBackend(**kw)
    raise ValueError(f"unknown backend {name!r}")
