"""Embedding clients for the ``embeddings`` role (3.4, carried over from 3.3).

Two servers can compute embeddings:

* ``ollama`` — the native ``POST /api/embed`` route already used by the app's
  retrieval (``nomic-embed-text`` and similar); ``nomic`` models keep their
  ``search_query:`` / ``search_document:`` task prefixes.
* ``openai_compat`` — ``POST /v1/embeddings`` (llama.cpp server, vLLM, Ollama's
  OpenAI shim, any compatible service).

Every request passes :func:`swarmbly_app.egress.check_call` **before** a byte
is written, with ``PASSAGES`` for document text and ``QUESTION`` for a query,
so a third-party destination receives passages only when the host is
authorised and ``privacy.third_party_passages`` is on. A refusal raises
:class:`EgressDenied` before the HTTP client is opened.

The cache in SwarmblyLCE keys vectors by text only; mixing vectors from two
models (or two dimensions) would silently truncate them in ``zip``. The
module keeps the observed dimension per ``(backend, model, endpoint)``
identity and raises :class:`EmbeddingDimensionError` when a server changes it,
so the caller can discard the old index and start again.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

import httpx

from .. import egress, test_hosts

ANTHROPIC_NO_EMBEDDINGS = (
    "Anthropic has no embeddings endpoint; choose Ollama or an "
    "OpenAI-compatible server for the embeddings role.")

DEFAULT_TIMEOUT_S = 120.0

# identity -> dimension observed from that server for that model.
_DIMS: dict[str, int] = {}


class EmbeddingError(RuntimeError):
    """The embedding server answered with something unusable."""


class EmbeddingDimensionError(EmbeddingError):
    """The same model answered with a different vector size."""


def reset_dimensions() -> None:
    """Forget the dimensions seen so far (tests, or a server reset)."""
    _DIMS.clear()


def _prefix(model: str, kind: str) -> str:
    """nomic-embed-text expects task prefixes; other models do not."""
    if "nomic" in (model or "").lower():
        return "search_query: " if kind == "query" else "search_document: "
    return ""


def _vectors_from_rows(rows: Iterable[Any], expected: int, model: str) -> list[list[float]]:
    """Validate an OpenAI/Ollama response and return plain float vectors."""
    rows = list(rows)
    if len(rows) != expected:
        raise EmbeddingError(
            f"embeddings {model}: asked for {expected} vectors, got {len(rows)}")
    out: list[list[float]] = []
    for row in rows:
        vec = row.get("embedding") if isinstance(row, dict) else row
        if not isinstance(vec, (list, tuple)) or not vec:
            raise EmbeddingError(f"embeddings {model}: a vector is empty or not a list")
        try:
            out.append([float(x) for x in vec])
        except (TypeError, ValueError) as exc:
            raise EmbeddingError(f"embeddings {model}: a vector is not numeric") from exc
    dimensions = {len(v) for v in out}
    if len(dimensions) != 1:
        raise EmbeddingError(
            f"embeddings {model}: one response mixed dimensions {sorted(dimensions)}")
    return out


class EmbeddingClient:
    """One server and model for the embeddings role."""

    def __init__(self, backend: str, model: str, url: str,
                 api_key: str = "", timeout: float = DEFAULT_TIMEOUT_S):
        self.backend = backend
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        base = (url or "").strip().rstrip("/")
        if backend == "openai_compat":
            if not base:
                raise EmbeddingError(
                    "an OpenAI-compatible embeddings server needs a URL")
            if not base.endswith("/v1"):
                base += "/v1"
            self.url = base
            self.endpoint = base + "/embeddings"
        elif backend == "ollama":
            if not base:
                raise EmbeddingError("an Ollama embeddings server needs a URL")
            if base.endswith("/v1"):
                base = base[:-3].rstrip("/")
            self.url = base
            self.endpoint = base + "/api/embed"
        else:
            raise EmbeddingError(f"unknown embeddings backend {backend!r}")

    # -- identity ---------------------------------------------------------------
    @property
    def identity(self) -> str:
        """Stable across calls for one model on one server."""
        return f"{self.backend}|{self.model}|{self.url}"

    @property
    def dim(self) -> int:
        """The dimension last seen for this identity (0 before the first call)."""
        return _DIMS.get(self.identity, 0)

    @property
    def where(self) -> str:
        """Host this client talks to ("" is not assumed; use egress)."""
        return egress.classify_url(self.endpoint)[1]

    # -- call -------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]:
        """Vectors for ``texts`` (``kind`` is ``document`` or ``query``).

        ``egress.check_call`` runs before the request: a third party that may
        not receive these passages raises :class:`EgressDenied` and no socket
        is opened.
        """
        texts = [str(t) for t in texts]
        if not texts:
            return []
        payload = {"model": self.model,
                   "input": [_prefix(self.model, kind) + t for t in texts]}
        body = json.dumps(payload).encode("utf-8")
        egress.check_call(self.endpoint, len(body),
                          reason=f"embeddings {self.model}",
                          kind=egress.QUESTION if kind == "query" else egress.PASSAGES)
        try:
            with test_hosts.httpx_client(timeout=self.timeout) as client:
                resp = client.post(self.endpoint, content=body, headers=self._headers())
                if resp.status_code >= 400:
                    detail = resp.text[:400]
                    raise EmbeddingError(
                        f"embeddings {self.model}: HTTP {resp.status_code}: {detail}")
                data = resp.json()
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"embeddings {self.model}: {exc}") from exc
        except ValueError as exc:
            raise EmbeddingError(
                f"embeddings {self.model}: the server did not answer with JSON") from exc
        rows = data.get("embeddings") if self.backend == "ollama" else data.get("data")
        vectors = _vectors_from_rows(rows or [], len(texts), self.model)
        self._check_dimension(vectors)
        return vectors

    def _check_dimension(self, vectors: list[list[float]]) -> None:
        if not vectors:
            return
        dim = len(vectors[0])
        known = _DIMS.get(self.identity)
        if known is not None and known != dim:
            # Record the new size so the next call can rebuild the index, but
            # never hand these vectors to a cache that still holds ``known``.
            _DIMS[self.identity] = dim
            raise EmbeddingDimensionError(
                f"embeddings {self.model}: dimension changed from {known} to "
                f"{dim}; rebuilding the index")
        _DIMS[self.identity] = dim


def openai_embedder(model: str, base_url: str, api_key: str = "",
                    timeout: float = DEFAULT_TIMEOUT_S) -> EmbeddingClient:
    """An OpenAI-compatible client (``/v1/embeddings``)."""
    return EmbeddingClient("openai_compat", model, base_url, api_key, timeout)


def ollama_embedder(model: str, base_url: str, api_key: str = "",
                    timeout: float = DEFAULT_TIMEOUT_S) -> EmbeddingClient:
    """A native Ollama client (``/api/embed``)."""
    return EmbeddingClient("ollama", model, base_url, api_key, timeout)


class DocumentEmbedder:
    """Adapter for callers that expect ``embed(texts)`` (the orchestrator).

    Seam/agreement similarity works on generated fragments, which may quote
    the user's sources: every call still goes through the embedding client
    and its egress check.  A failure (a local server that is down, or a
    destination the policy refuses) degrades to the caller's lexical
    embedder, as the previous server embedder did.
    """

    def __init__(self, client: EmbeddingClient, fallback: Any = None):
        self.client = client
        self.fallback = fallback
        self.name = f"server:{client.model}"
        self.degraded = ""

    def embed(self, texts: Iterable[str]) -> Any:
        try:
            return self.client.embed(list(texts), "document")
        except Exception as exc:
            self.degraded = f"{type(exc).__name__}: {exc}"
            if self.fallback is None:
                raise
            return self.fallback.embed(list(texts))
