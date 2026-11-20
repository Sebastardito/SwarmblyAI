"""3.4 (carried over from 3.3): the ``embeddings`` role.

Retrieval over the user's sources embeds passages, so the role follows the
same destinations policy as a model: a third party only with the host
authorised **and** ``privacy.third_party_passages``.  A refusal happens before
a byte, then the app's own Ollama embedder is used when it is local, else C1
keeps the keyword search.  Anthropic has no embeddings endpoint.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

from swarmbly_app import egress, roles
from swarmbly_app.config import ConfigError, validate_changes
from swarmbly_app.inference import embeddings

MARKER = "ZETA-EMBED-MARKER-7731"
DOC = ("# Nota de campo\n\n"
       "El proyecto Zeta coordina el monitoreo de la costa norte. "
       f"{MARKER}.\n\n"
       "Los sensores registran la temperatura del agua cada hora.")
QUESTION = "¿Qué dice mi nota sobre el proyecto Zeta y el monitoreo de la costa?"


class FakeEmbeddingServer:
    """A local HTTP server that answers Ollama and OpenAI embedding routes."""

    def __init__(self):
        self.model = "nomic-embed-text"
        self.dim = 4
        self.requests: list[dict] = []
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):        # keep the test output quiet
                return

            def _send(self, code: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):                    # model lists, if ever asked
                if self.path.endswith("/api/tags"):
                    self._send(200, {"models": [{"name": outer.model}]})
                elif self.path.endswith("/v1/models"):
                    self._send(200, {"data": [{"id": outer.model}]})
                else:
                    self._send(404, {})

            def do_POST(self):
                size = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(size)
                data = json.loads(raw.decode("utf-8"))
                with outer._lock:
                    outer.requests.append(
                        {"path": self.path, "json": data, "bytes": len(raw)})
                inputs = data.get("input") or []
                if isinstance(inputs, str):
                    inputs = [inputs]
                vectors = [outer.vector(text) for text in inputs]
                if self.path.endswith("/api/embed"):
                    self._send(200, {"embeddings": vectors})
                elif self.path.endswith("/v1/embeddings"):
                    self._send(200, {"data": [{"embedding": vec, "index": i}
                                              for i, vec in enumerate(vectors)]})
                else:
                    self._send(404, {})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def vector(self, text: str) -> list[float]:
        """Deterministic, word-sensitive vector of ``self.dim`` dimensions."""
        out = [0.0] * self.dim
        for word in str(text).lower().split():
            out[sum(map(ord, word)) % self.dim] += 1.0
        if not any(out):
            out[0] = 1.0
        return out

    def posts(self, suffix: str = "") -> list[dict]:
        with self._lock:
            return [r for r in self.requests if r["path"].endswith(suffix)]

    def inputs(self, suffix: str = "") -> list[str]:
        return [text for post in self.posts(suffix)
                for text in post["json"].get("input") or []]

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


@pytest.fixture()
def servers(monkeypatch):
    """One local server and one that egress classifies as a third party."""
    local, remote = FakeEmbeddingServer(), FakeEmbeddingServer()
    real_classify = egress.classify_url

    def classify(url: str):
        try:
            if urlsplit(url).port == remote.port:
                return egress.THIRD_PARTY, "api.simulada.invalid"
        except ValueError:
            pass
        return real_classify(url)

    monkeypatch.setattr(egress, "classify_url", classify)
    embeddings.reset_dimensions()
    try:
        yield local, remote
    finally:
        local.close()
        remote.close()
        embeddings.reset_dimensions()


def _setup(state, local, **role):
    state.dirs.sources.mkdir(parents=True, exist_ok=True)
    (state.dirs.sources / "notas.md").write_text(DOC, encoding="utf-8")
    state.config.update({
        "model": {"backend": "ollama", "backend_url": local.url,
                  "model_name": "fake-model:1b",
                  "embed_model": "nomic-embed-text"},
        "lce": {"enabled": True, "level": "C1", "dense_retrieval": True,
                "query_expansion": False, "retrieval_k": 4},
        "roles": {"embeddings": {"model": "", "backend": "",
                                 "backend_url": "", "api_key": ""}},
    })
    if role:
        state.config.update({"roles": {"embeddings": role}})


def _ask(state, text: str = QUESTION) -> dict:
    conv = state.chat.create_conversation(mode="local")
    state.chat.send(conv["id"], text, mode="local", run_async=False)
    return state.chat.get_messages(conv["id"])[-1]


def _embedding_meta(message: dict) -> dict:
    return message["meta"]["lce"]["embeddings"]


# -- default and the chosen server --------------------------------------------------

def test_default_keeps_the_same_ollama_embedder(app_state, fake_chat, servers):
    local, _remote = servers
    _setup(app_state, local)
    message = _ask(app_state)

    paths = [post["path"] for post in local.requests]
    assert "/api/embed" in paths and "/v1/embeddings" not in paths
    documents = [p for p in local.posts("/api/embed")
                 if any(MARKER in text for text in p["json"]["input"])]
    assert documents
    assert all(text.startswith("search_document: ")
               for text in documents[0]["json"]["input"])
    assert any(text.startswith("search_query: ")
               for text in local.inputs("/api/embed"))
    meta = _embedding_meta(message)
    assert meta["model"] == "nomic-embed-text" and meta["backend"] == "ollama"
    assert meta["dimension"] == 4 and not meta.get("rebuilt")
    assert not meta.get("fallback") and not meta.get("note")
    assert message["meta"]["receipt"]["envios"] == []


def test_openai_compatible_local_server_is_used_when_chosen(app_state, fake_chat, servers):
    local, _remote = servers
    _setup(app_state, local, model="embed-local", backend="openai_compat",
           backend_url=local.url + "/v1")
    message = _ask(app_state)

    posts = local.posts("/v1/embeddings")
    assert posts and posts[0]["json"]["model"] == "embed-local"
    assert any(MARKER in text for text in local.inputs("/v1/embeddings"))
    assert not local.posts("/api/embed")
    meta = _embedding_meta(message)
    assert meta["model"] == "embed-local" and meta["backend"] == "openai_compat"
    assert meta["own"] is True and meta["dimension"] == 4


# -- the third-party policy ----------------------------------------------------------

def test_third_party_without_authorisation_is_refused_before_any_byte(
        app_state, fake_chat, servers):
    local, remote = servers
    _setup(app_state, local, model="embed-remote", backend="openai_compat",
           backend_url=remote.url + "/v1")
    message = _ask(app_state)

    assert remote.requests == []                         # not a single byte
    assert local.posts("/api/embed")                     # local fallback did the job
    meta = _embedding_meta(message)
    assert meta["fallback"] == "local" and meta["blocked"] == "api.simulada.invalid"
    assert "not authorised" in meta["note"]
    receipt = message["meta"]["receipt"]
    assert receipt["envios"] == []
    blocked = [entry for entry in receipt["bloqueados"]
               if entry["destino"] == "api.simulada.invalid"]
    assert blocked and blocked[0]["tipo"] == "pasaje"
    assert blocked[0]["bytes"] == 0


def test_authorised_host_without_passage_permission_is_refused(
        app_state, fake_chat, servers):
    local, remote = servers
    _setup(app_state, local, model="embed-remote", backend="openai_compat",
           backend_url=remote.url + "/v1")
    app_state.config.update({"privacy": {
        "third_party_models": ["api.simulada.invalid"],
        "third_party_passages": False}})
    message = _ask(app_state)

    assert remote.requests == []
    assert local.posts("/api/embed")
    meta = _embedding_meta(message)
    assert meta["fallback"] == "local"
    assert "authorised for questions only" in meta["note"]
    receipt = message["meta"]["receipt"]
    assert receipt["envios"] == [] and receipt["pasajes_enviados"] == 0
    assert any(entry["destino"] == "api.simulada.invalid"
               for entry in receipt["bloqueados"])


def test_both_authorisations_send_the_passages_and_appear_in_the_receipt(
        app_state, fake_chat, servers):
    local, remote = servers
    _setup(app_state, local, model="embed-remote", backend="openai_compat",
           backend_url=remote.url + "/v1")
    app_state.config.update({"privacy": {
        "third_party_models": ["api.simulada.invalid"],
        "third_party_passages": True}})
    message = _ask(app_state)

    posts = remote.posts("/v1/embeddings")
    assert posts and any(MARKER in text for post in posts
                         for text in post["json"]["input"])
    assert not local.posts("/api/embed")
    meta = _embedding_meta(message)
    assert not meta.get("fallback") and meta["where"] == "api.simulada.invalid"
    receipt = message["meta"]["receipt"]
    sent = [entry for entry in receipt["envios"]
            if entry["destino"] == "api.simulada.invalid"]
    assert sent and any(entry["tipo"] == "pasaje" and entry["bytes"] > 0
                        for entry in sent)
    assert receipt["pasajes_enviados"] >= 1


# -- Anthropic ----------------------------------------------------------------------

def test_anthropic_is_refused_with_a_clear_message(app_state, fake_chat, servers):
    local, remote = servers
    with pytest.raises(ConfigError, match="no embeddings endpoint"):
        validate_changes({"roles.embeddings.backend": "anthropic"})

    _setup(app_state, local, model="text-embedding-x", backend="anthropic")
    message = _ask(app_state)
    assert remote.requests == []
    assert local.posts("/api/embed")                     # local fallback
    meta = _embedding_meta(message)
    assert "Anthropic has no embeddings endpoint" in meta["note"]
    assert meta["fallback"] == "local"

    choice = roles.choose("embeddings", app_state.config.all(), None, "")
    assert choice.note.startswith("blocked:") and "Anthropic" in choice.note
    with pytest.raises(egress.EgressDenied, match="no embeddings endpoint"):
        app_state._embed([MARKER], "document")

    # No embeddings role chosen, but the conversation itself uses Anthropic:
    # its address still has no embeddings route, so nothing is sent.
    cfg = {"model": {"backend": "anthropic",
                     "backend_url": "https://api.anthropic.com",
                     "embed_model": "nomic-embed-text"},
           "roles": {"embeddings": {"model": "", "backend": ""}},
           "privacy": {"third_party_models": ["api.anthropic.com"],
                       "third_party_passages": True}}
    implicit = roles.choose("embeddings", cfg, None, "")
    assert implicit.backend is None and "Anthropic" in implicit.note


# -- model and dimension changes -----------------------------------------------------

def _document_posts(server: FakeEmbeddingServer) -> int:
    return len([post for post in server.posts("/v1/embeddings")
                if any(MARKER in text for text in post["json"]["input"])])


def test_changing_the_embeddings_model_rebuilds_the_index(app_state, fake_chat, servers):
    local, _remote = servers
    local.model, local.dim = "embed-a", 3
    _setup(app_state, local, model="embed-a", backend="openai_compat",
           backend_url=local.url + "/v1")
    first = _ask(app_state)
    assert _embedding_meta(first)["rebuilt"] is False
    assert _embedding_meta(first)["dimension"] == 3
    before = _document_posts(local)

    local.model, local.dim = "embed-b", 4
    app_state.config.update({"roles.embeddings.model": "embed-b"})
    second = _ask(app_state)
    meta = _embedding_meta(second)
    assert meta["rebuilt"] is True and "model" in meta["reason"]
    assert meta["model"] == "embed-b" and meta["dimension"] == 4
    assert _document_posts(local) > before               # old vectors were discarded


def test_a_dimension_change_never_mixes_vectors_then_rebuilds(
        app_state, fake_chat, servers):
    local, _remote = servers
    local.model, local.dim = "embed-a", 4
    _setup(app_state, local, model="embed-a", backend="openai_compat",
           backend_url=local.url + "/v1")
    first = _ask(app_state)
    assert _embedding_meta(first)["dimension"] == 4
    before = _document_posts(local)

    local.dim = 5                       # same model id, different vector size
    transition = _ask(app_state)
    meta = _embedding_meta(transition)
    assert meta["fallback"] == "lexical"
    assert "dimension changed from 4 to 5" in meta["error"]
    assert _document_posts(local) == before              # no mixed vectors were cached

    rebuilt = _ask(app_state)
    meta = _embedding_meta(rebuilt)
    assert meta["rebuilt"] is True and meta["reason"] == "dimension changed"
    assert meta["dimension"] == 5
    assert _document_posts(local) > before                # the index was rebuilt


# -- settings -----------------------------------------------------------------------

def test_role_settings_and_the_secret_key_are_registered():
    from swarmbly_app.config import DEFAULTS
    from swarmbly_app.keystore import SECRET_KEYS

    assert "embeddings" in DEFAULTS["roles"]
    assert "roles.embeddings.api_key" in SECRET_KEYS
    cfg = {"model": {"embed_model": "legacy-embed", "backend_url": "http://127.0.0.1:11434"},
           "roles": {"embeddings": {"model": "", "backend": ""}}}
    assert roles.embeddings_configured(cfg) is False
    choice = roles.choose("embeddings", cfg, None, "")
    assert choice.backend.model == "legacy-embed" and not choice.note
    cfg["roles"]["embeddings"] = {"model": "bge-m3", "backend": "ollama"}
    assert roles.embeddings_configured(cfg) is True


def test_the_orchestrator_seam_embedder_uses_the_role():
    from swarmbly_app.engine.orchestrator import Orchestrator
    from swarmbly_app.inference.embeddings import DocumentEmbedder

    cfg = {"model": {"embedder": "hash"},
           "roles": {"embeddings": {"model": "embed-seam",
                                    "backend": "openai_compat",
                                    "backend_url": "http://127.0.0.1:9/v1"}}}

    class Stub:
        def config(self):
            return cfg

    embedder, name = Orchestrator._embedder(Stub())
    assert isinstance(embedder, DocumentEmbedder)
    assert name == "server:embed-seam"


def test_the_orchestrator_seam_embedder_falls_back_when_the_role_is_blocked(
        servers):
    from swarmbly_app.engine.orchestrator import Orchestrator
    from swarmbly_app.inference.embeddings import DocumentEmbedder
    from swarmbly_v0 import HashEmbedder

    _local, remote = servers
    cfg = {"model": {"embedder": "hash"},
           "roles": {"embeddings": {"model": "embed-remote",
                                    "backend": "openai_compat",
                                    "backend_url": remote.url + "/v1"}},
           "privacy": {"third_party_models": [], "third_party_passages": False}}

    class Stub:
        def config(self):
            return cfg

    # A local legacy embedder is configured: it takes over.
    embedder, name = Orchestrator._embedder(Stub())
    assert isinstance(embedder, DocumentEmbedder)
    assert "fallback: local" in name and remote.requests == []

    # No local legacy embedder (the old switch points at the third party too):
    # the seam similarity stays lexical.
    cfg["model"]["backend_url"] = remote.url
    embedder, name = Orchestrator._embedder(Stub())
    assert isinstance(embedder, HashEmbedder)
    assert "no local embedder" in name and remote.requests == []
