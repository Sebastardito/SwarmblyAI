"""3.3: models by role. A role names a model, its thinking setting and,
optionally, a server of its own; it never widens what may leave the computer."""

from __future__ import annotations

import json

import httpx
import pytest

from swarmbly_app import egress, roles
from swarmbly_app.inference import ollama, openai_compat
from swarmbly_app.keystore import redact

MARKER = "ZETA-MARCADOR-9042"
API = "https://api.simulada.invalid/v1"
COMPOSITION = "Escribe un párrafo de 60 a 80 palabras sobre mi trabajo en el proyecto Zeta."
QUESTION = "¿Desde cuándo coordino el monitoreo del proyecto Zeta?"


class Capture:
    """A local Ollama and a simulated OpenAI-compatible API, both mocked."""

    def __init__(self):
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/chat/completions"):
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"Texto de la API [D1 p1]."}}]}'
                                            '\n\ndata: [DONE]\n\n')
        if path.endswith("/api/chat"):
            return httpx.Response(200, text=json.dumps(
                {"message": {"content": "Respuesta local [D1 p1]."}, "done": True}) + "\n")
        if path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "modelo-api"}]})
        if path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}, {"name": "grande:27b"}]})
        return httpx.Response(404)

    def sent(self, suffix: str) -> list[dict]:
        return [json.loads(r.content.decode("utf-8")) for r in self.requests if r.url.path.endswith(suffix)]


@pytest.fixture()
def capture(monkeypatch):
    cap = Capture()
    real = httpx.Client

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(cap.handler)
        return real(*args, **kwargs)
    monkeypatch.setattr(openai_compat.httpx, "Client", client)
    monkeypatch.setattr(ollama.httpx, "Client", client)
    ollama._REMOTE.clear()
    return cap


def _setup(state, **extra):
    state.dirs.sources.mkdir(parents=True, exist_ok=True)
    (state.dirs.sources / "cv.md").write_text(
        f"# Mi currículum\n\nCoordino el monitoreo del proyecto Zeta desde 2024. {MARKER}.", encoding="utf-8")
    state.config.update({"model": {"backend": "ollama", "backend_url": "http://127.0.0.1:11434",
                                   "model_name": "qwen2.5:7b"},
                         "lce": {"enabled": True, "level": "C1", "dense_retrieval": False,
                                 "query_expansion": False}, **extra})


def _ask(state, text):
    conv = state.chat.create_conversation(mode="local")
    state.chat.send(conv["id"], text, mode="local", run_async=False)
    return state.chat.get_messages(conv["id"])[-1]


def test_older_settings_are_the_roles_fallback():
    cfg = {"compose": {"model": "a:27b"}, "lce": {"expansion_model": "b:3b"},
           "evidence": {"fusion_model": "c:14b"}, "roles": {"writer": {"model": "", "think": False}}}
    assert roles.settings(cfg, "writer") == {"model": "a:27b", "think": False}
    assert roles.settings(cfg, "search_terms")["model"] == "b:3b"
    assert roles.settings(cfg, "fusion")["model"] == "c:14b"
    assert roles.settings({"roles": {"writer": {"model": "x"}}, "compose": {"model": "a"}}, "writer")["model"] == "x"


def test_settings_nest_all_the_way_and_keys_stay_out(app_state):
    app_state.config.update({"roles.writer.model": "grande:27b", "roles.writer.think": False})
    cfg = app_state.config.all()
    assert cfg["roles"]["writer"]["model"] == "grande:27b" and cfg["roles"]["writer"]["think"] is False
    assert cfg["roles"]["fusion"]["model"] == "" and "writer.model" not in cfg["roles"]
    shown = redact({**cfg, "roles": {**cfg["roles"], "writer": {**cfg["roles"]["writer"], "api_key": "sk-x"}}})
    assert shown["roles"]["writer"]["api_key"] == "" and "roles.writer.api_key" in shown["_secrets"]


def test_a_local_writer_writes_compositions_only_with_its_own_thinking(app_state, capture):
    _setup(app_state, roles={"writer": {"model": "grande:27b", "think": False}})
    msg = _ask(app_state, COMPOSITION)
    calls = capture.sent("/api/chat")
    assert calls[-1]["model"] == "grande:27b" and calls[-1]["think"] is False
    assert msg["meta"]["roles"]["writer"] == {"model": "grande:27b", "own": True, "think": False}
    assert msg["meta"]["receipt"]["envios"] == []                       # still on this computer
    _ask(app_state, QUESTION)
    last = capture.sent("/api/chat")[-1]
    assert last["model"] == "qwen2.5:7b" and "think" not in last        # a question: the chat's model


def test_a_writer_on_another_server_needs_both_authorisations(app_state, capture):
    writer = {"model": "modelo-api", "backend": "openai_compat", "backend_url": API}
    _setup(app_state, roles={"writer": writer})
    msg = _ask(app_state, COMPOSITION)                                   # not authorised
    assert msg["meta"]["status"] == "done" and not capture.sent("/chat/completions")
    assert "not authorised" in msg["meta"]["roles"]["writer"]["note"]
    assert "api.simulada.invalid" in msg["meta"]["composer_blocked"]
    app_state.config.update({"privacy": {"third_party_models": ["api.simulada.invalid"]}})
    msg = _ask(app_state, COMPOSITION)                                   # questions only
    assert not capture.sent("/chat/completions")
    assert "questions only" in msg["meta"]["roles"]["writer"]["note"]
    assert not any(MARKER in r.content.decode("utf-8") for r in capture.requests
                   if "simulada" in str(r.url))
    app_state.config.update({"privacy": {"third_party_passages": True}})
    msg = _ask(app_state, COMPOSITION)                                   # both: the API writes
    sent = capture.sent("/chat/completions")
    assert sent and sent[-1]["model"] == "modelo-api" and MARKER in json.dumps(sent[-1], ensure_ascii=False)
    assert msg["meta"]["roles"]["writer"]["where"] == "api.simulada.invalid"
    assert msg["content"].startswith("Texto de la API")
    receipt = msg["meta"]["receipt"]
    assert {s["destino"] for s in receipt["envios"]} == {"api.simulada.invalid"} and receipt["pasajes_enviados"] >= 1
    before = len(capture.sent("/chat/completions"))
    _ask(app_state, QUESTION)                                            # a question never goes there
    assert len(capture.sent("/chat/completions")) == before


def test_a_missing_role_model_falls_back_and_says_so(app_state, capture):
    _setup(app_state, roles={"writer": {"model": "no-instalado:70b"}})
    msg = _ask(app_state, COMPOSITION)
    assert capture.sent("/api/chat")[-1]["model"] == "qwen2.5:7b"
    assert msg["meta"]["roles"]["writer"]["note"] == "missing" and msg["meta"]["composer_missing"] == "no-instalado:70b"


def test_search_terms_role_and_the_writer_as_its_default(app_state, capture):
    _setup(app_state, roles={"search_terms": {"model": "grande:27b"}})
    app_state.config.update({"lce": {"query_expansion": True}})
    msg = _ask(app_state, QUESTION)
    models = [c["model"] for c in capture.sent("/api/chat")]
    assert models[0] == "grande:27b" and models[-1] == "qwen2.5:7b"
    assert msg["meta"]["roles"]["search_terms"]["model"] == "grande:27b"
    choice = roles.choose("search_terms", {"roles": {}}, object(), "chat:7b")
    assert choice.model == "chat:7b" and not choice.own
