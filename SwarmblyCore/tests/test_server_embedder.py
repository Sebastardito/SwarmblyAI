"""The server-backed embedder, and its refusal to degrade silently.

A tau_sem calibrated on hashed embeddings is not a threshold, it is a number.
The one thing these tests protect is that a run cannot *report* server
embeddings while actually having used the hash fallback.
"""

from __future__ import annotations

import numpy as np
import pytest

from swarmbly_v0.backends import (
    HashEmbedder,
    OpenAICompatBackend,
    ServerEmbedder,
    get_embedder,
)


class _HttpOnly(OpenAICompatBackend):
    """Forces the HTTP transport so a stub on `_post_once` is actually reached.

    Without this the fake is bypassed on any machine with the openai package
    installed, and the test silently measures the SDK talking to localhost.
    """

    def __init__(self, **kw):
        super().__init__(prefer_sdk=False, **kw)


class _Unreachable(_HttpOnly):
    """A backend whose /embeddings route always fails.

    Stubs `_post_once`, the transport, rather than `_post`, the retry policy
    wrapped around it. Stubbing the policy layer silently disabled the bounded
    retry for anything these fakes drove, which is how the SDK path came to have
    no retry at all without a single test noticing.
    """

    def _post_once(self, path, payload):  # type: ignore[override]
        raise OSError("connection refused")


class _Working(_HttpOnly):
    """A backend whose /embeddings route returns two fixed vectors."""

    def _post_once(self, path, payload):  # type: ignore[override]
        assert path == "/embeddings"
        n = len(payload["input"])
        return {"data": [{"embedding": [float(i + 1), 0.0, 0.0]} for i in range(n)]}


def test_factory_accepts_the_api_aliases():
    for alias in ("api", "server", "ollama", "openai"):
        assert isinstance(get_embedder(alias), ServerEmbedder)
    assert isinstance(get_embedder("hash"), HashEmbedder)
    with pytest.raises(ValueError, match="unknown embedder"):
        get_embedder("word2vec")


def test_server_route_is_used_and_rows_are_unit_norm():
    e = ServerEmbedder(backend=_Working())
    v = e.embed(["a", "b"])
    assert v.shape == (2, 3)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0)
    assert e.available
    assert e.name == "server-embeddings"


def test_empty_input_does_not_touch_the_network():
    e = ServerEmbedder(backend=_Unreachable())
    assert e.embed([]).shape[0] == 0
    assert e.available, "an empty call must not be recorded as a degradation"


def test_degradation_is_recorded_on_the_backend_and_in_the_name():
    b = _Unreachable()
    e = ServerEmbedder(backend=b)
    assert e.available
    v = e.embed(["a", "b"])
    assert v.shape[0] == 2, "the sweep still gets vectors"
    assert not e.available
    assert b.embed_degraded.startswith("OSError")
    assert "degraded->hash" in e.name, "run metadata must see the degradation"


def test_the_degradation_reason_is_recorded_once_not_overwritten():
    b = _Unreachable()
    e = ServerEmbedder(backend=b)
    e.embed(["a"])
    first = b.embed_degraded
    e.embed(["b"])
    assert b.embed_degraded == first
    assert e.name.count("degraded->hash") == 1


def test_run_metadata_reports_the_degradation(monkeypatch):
    """A sweep must not report server embeddings it did not actually get."""
    from swarmbly_v0.experiment import SweepConfig, load_prompts, run_sweep

    class _NoEmbed(_Working):
        def _post_once(self, path, payload):  # type: ignore[override]
            if path == "/embeddings":
                raise OSError("404 no embeddings route")
            return {"choices": [{"message": {"content": "Alpha beta. Gamma delta epsilon."}}]}

    prompts = load_prompts()[:2]
    backend = _NoEmbed()
    rows, meta = run_sweep(
        prompts,
        SweepConfig(rhos=(1.0,), ns=(2,), ks=(1,), backend_name="openai"),
        backend,
        ServerEmbedder(backend=_NoEmbed()),
    )
    assert meta["embeddings_degraded"] is True
    assert "degraded->hash" in meta["embedder"]
    assert "MUST NOT be" in meta["tau_sem_warning"]


def test_run_metadata_is_clean_when_embeddings_work():
    from swarmbly_v0.experiment import SweepConfig, load_prompts, run_sweep

    class _Both(_Working):
        def _post_once(self, path, payload):  # type: ignore[override]
            if path == "/embeddings":
                return super()._post_once(path, payload)
            return {"choices": [{"message": {"content": "Alpha beta. Gamma delta epsilon."}}]}

    prompts = load_prompts()[:2]
    rows, meta = run_sweep(
        prompts,
        SweepConfig(rhos=(1.0,), ns=(2,), ks=(1,), backend_name="openai"),
        _Both(),
        ServerEmbedder(backend=_Both()),
    )
    assert meta["embeddings_degraded"] is False
    assert "tau_sem_warning" not in meta
    assert meta["embedder"] == "server-embeddings"
