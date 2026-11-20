"""Anthropic's native Messages API: request shape, SSE, errors and egress.

The transport is mocked: no test here opens a network connection.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from swarmbly_app import egress, roles
from swarmbly_app.config import ConfigError, validate_changes
from swarmbly_app.inference import anthropic
from swarmbly_app.inference.anthropic import AnthropicBackend
from swarmbly_app.inference.base import BackendError, Interrupted
from swarmbly_app.inference.registry import BackendRegistry, IncompleteSettings
from swarmbly_app.models import ModelManager

HOST = "api.anthropic.com"
API = "https://api.anthropic.com"
KEY = "sk-ant-test"
MODEL = "claude-sonnet-4-5"


def sse(*events: dict) -> str:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


TEXT_STREAM = sse(
    {"type": "message_start",
     "message": {"id": "msg_1", "model": MODEL,
                 "usage": {"input_tokens": 17, "output_tokens": 1}}},
    {"type": "content_block_start", "index": 0,
     "content_block": {"type": "text", "text": ""}},
    {"type": "ping"},
    {"type": "content_block_delta", "index": 0,
     "delta": {"type": "thinking_delta", "thinking": "no debe salir"}},
    {"type": "content_block_delta", "index": 0,
     "delta": {"type": "text_delta", "text": "Hola "}},
    {"type": "content_block_delta", "index": 0,
     "delta": {"type": "text_delta", "text": "mundo."}},
    {"type": "content_block_delta", "index": 0,
     "delta": {"type": "signature_delta", "signature": "ignored"}},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
     "usage": {"output_tokens": 9}},
    {"type": "message_stop"},
)


class Capture:
    def __init__(self, *, status: int = 200, body: str = TEXT_STREAM,
                 models: dict | None = None):
        self.status = status
        self.body = body
        self.models = models
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/v1/messages"):
            if self.status != 200:
                return httpx.Response(self.status, json={
                    "type": "error", "error": {"type": "api_error", "message": "simulated"}})
            return httpx.Response(200, text=self.body,
                                  headers={"content-type": "text/event-stream"})
        if request.url.path.endswith("/v1/models"):
            if self.models is not None:
                return httpx.Response(200, json=self.models)
            after = request.url.params.get("after_id")
            if not after:
                return httpx.Response(200, json={
                    "data": [{"id": "claude-a"}], "has_more": True, "last_id": "claude-a"})
            return httpx.Response(200, json={
                "data": [{"id": "claude-b"}], "has_more": False, "last_id": "claude-b"})
        return httpx.Response(404, json={"error": {"type": "not_found_error",
                                                   "message": "no such path"}})


def mock_api(monkeypatch, handler) -> None:
    real = httpx.Client

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(anthropic.httpx, "Client", client)


@pytest.fixture()
def api(monkeypatch):
    cap = Capture()
    mock_api(monkeypatch, cap.handler)
    return cap


@pytest.fixture()
def policy(monkeypatch):
    cfg = {"privacy": {"third_party_models": [HOST], "third_party_passages": False}}
    monkeypatch.setattr(egress, "_config_getter", lambda: cfg)
    return cfg


def backend(**kw) -> AnthropicBackend:
    return AnthropicBackend(API, api_key=KEY, timeout=1.0, **kw)


def ask(b: AnthropicBackend, messages: list[dict[str, str]], **kw):
    with egress.purpose(egress.QUESTION):
        return b.stream_chat(messages, **kw)


# --- request shape -------------------------------------------------------------------

def test_request_shape_system_and_merged_roles(api, policy):
    deltas: list[str] = []
    result = ask(backend(), [
        {"role": "system", "content": "Eres útil."},
        {"role": "user", "content": "Uno"},
        {"role": "user", "content": "Dos"},
        {"role": "assistant", "content": "Vale"},
        {"role": "system", "content": "Sé breve."},
    ], model=MODEL, max_tokens=512, temperature=0.3, system="Piensa.",
        on_delta=deltas.append)

    request = api.requests[0]
    payload = json.loads(request.content)
    assert request.method == "POST" and request.url.path == "/v1/messages"
    assert request.headers["x-api-key"] == KEY
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert request.headers["content-type"].startswith("application/json")
    assert payload["model"] == MODEL
    assert payload["max_tokens"] == 512
    assert payload["stream"] is True and payload["temperature"] == 0.3
    assert payload["system"] == "Piensa.\n\nEres útil.\n\nSé breve."
    assert payload["messages"] == [
        {"role": "user", "content": "Uno\n\nDos"},
        {"role": "assistant", "content": "Vale"},
    ]
    assert "thinking" not in payload
    assert result.text == "Hola mundo." and deltas == ["Hola ", "mundo."]


def test_thinking_sends_a_budget_below_max_tokens_and_no_temperature(api, policy):
    body = sse(
        {"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "thinking", "thinking": ""}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "thinking_delta", "thinking": "razono"}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "signature_delta", "signature": "ignored"}},
        {"type": "content_block_start", "index": 1,
         "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1,
         "delta": {"type": "text_delta", "text": "Respuesta."}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
         "usage": {"output_tokens": 3}},
        {"type": "message_stop"},
    )
    api.body = body
    result = ask(backend(), [{"role": "user", "content": "Hola"}],
                 model=MODEL, max_tokens=2048, think=True)
    payload = json.loads(api.requests[0].content)
    assert payload["thinking"]["type"] == "enabled"
    assert 0 < payload["thinking"]["budget_tokens"] < payload["max_tokens"]
    assert "temperature" not in payload
    assert result.text == "Respuesta." and result.meta["thinking"] == "razono"


# --- streaming -----------------------------------------------------------------------

def test_streaming_text_stop_and_usage(api, policy):
    deltas: list[str] = []
    result = ask(backend(), [{"role": "user", "content": "Hola"}],
                 model=MODEL, max_tokens=100, on_delta=deltas.append)
    assert result.text == "Hola mundo."
    assert result.prompt_tokens == 17 and result.completion_tokens == 9
    assert result.finish_reason == "end_turn"
    assert result.meta["backend"] == "anthropic" and result.meta["url"] == API
    assert deltas == ["Hola ", "mundo."]


def test_interrupt_stops_after_the_first_delta(api, policy):
    seen: list[str] = []

    def on_delta(text: str) -> None:
        seen.append(text)

    with pytest.raises(Interrupted):
        ask(backend(), [{"role": "user", "content": "Hola"}], model=MODEL,
            on_delta=on_delta, interrupt=lambda: len(seen) >= 1)
    assert seen == ["Hola "]


# --- errors --------------------------------------------------------------------------

@pytest.mark.parametrize("status,error_type,message", [
    (401, "authentication_error", "authentication failed"),
    (403, "permission_error", "authentication failed"),
    (404, "not_found_error", "not found"),
    (429, "rate_limit_error", "rate limited"),
    (500, "api_error", "server error"),
    (529, "overloaded_error", "overloaded"),
])
def test_http_status_errors_are_backend_errors(api, policy, status, error_type, message):
    api.status = status
    api.body = json.dumps({"type": "error",
                           "error": {"type": error_type, "message": "simulated"}})
    with pytest.raises(BackendError, match=message):
        ask(backend(), [{"role": "user", "content": "Hola"}], model=MODEL)


def test_stream_error_event_is_a_backend_error(api, policy):
    api.body = sse({"type": "error",
                    "error": {"type": "overloaded_error", "message": "Overloaded"}})
    with pytest.raises(BackendError, match="overloaded"):
        ask(backend(), [{"role": "user", "content": "Hola"}], model=MODEL)


# --- models --------------------------------------------------------------------------

def test_list_models_follows_pagination(api, policy):
    names = backend().list_models()
    assert names == ["claude-a", "claude-b"]
    assert [r.url.params.get("after_id") for r in api.requests] == [None, "claude-a"]
    assert all(r.url.path == "/v1/models" for r in api.requests)


def test_available_is_a_cheap_request_without_content(api, policy):
    api.models = {"data": [{"id": MODEL}], "has_more": False}
    assert backend().available() is True
    request = api.requests[0]
    assert request.method == "GET" and request.url.path == "/v1/models"
    assert request.url.params.get("limit") == "1"


# --- egress --------------------------------------------------------------------------

def test_api_anthropic_com_is_classified_as_a_third_party():
    assert egress.classify_url(API) == (egress.THIRD_PARTY, HOST)


def test_nothing_is_sent_without_authorisation(api, policy):
    policy["privacy"]["third_party_models"] = []
    with egress.request_ledger("r-blocked") as ledger:
        with egress.purpose(egress.QUESTION):
            with pytest.raises(egress.EgressDenied):
                backend().stream_chat([{"role": "user", "content": "Hola"}], model=MODEL)
    assert api.requests == []
    blocked = [e for e in ledger.events if e.get("bloqueado")]
    assert blocked and blocked[-1]["destino"] == HOST
    receipt = egress.build_receipt(ledger, lane="local", route="local", answer="", consent={})
    assert receipt["envios"] == [] and receipt["bloqueados"]
    assert receipt["bloqueados"][0]["destino"] == HOST


def test_authorised_host_receives_the_question_and_the_ledger_records_it(api, policy):
    with egress.request_ledger("r-allowed") as ledger:
        with egress.purpose(egress.QUESTION):
            result = backend().stream_chat([{"role": "user", "content": "Hola"}], model=MODEL)
    assert result.text == "Hola mundo." and len(api.requests) == 1
    sent = [e for e in ledger.events if not e.get("bloqueado")]
    assert sent and sent[-1]["destino"] == HOST and sent[-1]["bytes"] > 0
    receipt = egress.build_receipt(ledger, lane="local", route="local", answer="ok", consent={})
    assert receipt["envios"][0]["destino"] == HOST


def test_passages_need_the_second_authorisation(api, policy):
    policy["privacy"]["third_party_passages"] = False
    with egress.request_ledger("r-passages") as ledger:
        with egress.purpose(egress.PASSAGES):
            with pytest.raises(egress.EgressDenied):
                backend().stream_chat([{"role": "user", "content": "texto del documento"}],
                                      model=MODEL)
    assert api.requests == []
    assert [e for e in ledger.events if e.get("bloqueado")]
    policy["privacy"]["third_party_passages"] = True
    with egress.purpose(egress.PASSAGES):
        result = backend().stream_chat([{"role": "user", "content": "texto del documento"}],
                                       model=MODEL)
    assert result.text == "Hola mundo." and len(api.requests) == 1


def test_list_models_also_obeys_the_policy(api, policy):
    policy["privacy"]["third_party_models"] = []
    with egress.request_ledger("r-list") as ledger:
        assert backend().list_models() == []
        assert backend().available() is False
    assert api.requests == []
    assert len([e for e in ledger.events if e.get("bloqueado")]) == 2


@pytest.mark.parametrize("role", ["writer", "verifier"])
def test_a_role_on_anthropic_needs_both_authorisations(policy, monkeypatch, role):
    monkeypatch.setattr(AnthropicBackend, "list_models", lambda self: [MODEL])
    cfg = {
        "model": {"backend": "ollama", "backend_url": "http://127.0.0.1:11434",
                  "model_name": "qwen2.5:7b"},
        "roles": {role: {"model": MODEL, "backend": "anthropic", "backend_url": API}},
        "privacy": policy["privacy"],
    }
    chat = object()
    choice = roles.choose(role, cfg, chat, "qwen2.5:7b", passages=True)
    assert not choice.own and "questions only" in choice.note
    policy["privacy"]["third_party_passages"] = True
    choice = roles.choose(role, cfg, chat, "qwen2.5:7b", passages=True)
    assert choice.own and choice.backend.name == "anthropic"
    assert choice.where == HOST


# --- config, registry and the worker -------------------------------------------------

def test_config_accepts_anthropic_and_defaults_its_address():
    flat = validate_changes({"model.backend": "anthropic",
                             "roles.writer.backend": "anthropic"})
    assert flat["model.backend"] == "anthropic"
    assert flat["model.backend_url"] == API
    assert flat["roles.writer.backend"] == "anthropic"
    with pytest.raises(ConfigError):
        validate_changes({"model.backend": "anthropic_sdk"})


def test_registry_resolves_and_builds_anthropic():
    registry = BackendRegistry()
    resolved = registry.resolve({"model": {"backend": "anthropic", "backend_url": "",
                                           "model_name": MODEL}})
    assert resolved.name == "anthropic" and resolved.base_url == API
    built = registry.build("anthropic", "", api_key="k", think=True)
    assert built.name == "anthropic" and built.api_key == "k" and built.think is True


@pytest.mark.parametrize("kind", ["bogus", "llama_cpp"])
def test_unknown_backend_kind_raises(kind):
    registry = BackendRegistry()
    with pytest.raises(IncompleteSettings, match="Unknown"):
        registry.resolve({"model": {"backend": kind, "backend_url": "http://127.0.0.1:1"}})
    with pytest.raises(IncompleteSettings, match="Unknown"):
        registry.build(kind, "http://127.0.0.1:1")


def test_model_detection_lists_anthropic_models(api, policy):
    api.models = {"data": [{"id": MODEL}, {"id": "claude-haiku-4-5"}], "has_more": False}
    info = ModelManager(timeout=0.2).probe_anthropic(API, api_key=KEY)
    assert info.name == "anthropic" and info.available is True
    assert [m.name for m in info.models] == [MODEL, "claude-haiku-4-5"]


def test_worker_never_serves_with_an_anthropic_conversation_model(app_state, fake_chat):
    from swarmbly_app.p2p.worker import WorkerService
    from tests.test_worker_policy import task_message

    app_state.config.update({"model": {"backend": "anthropic", "backend_url": "",
                                       "model_name": MODEL},
                             "swarm": {"worker_enabled": True},
                             "privacy": {"third_party_models": [HOST]}})
    # an empty address means the public API, never the local Ollama
    assert app_state.config.get("model.backend_url") == API
    assert egress.model_destination(app_state.config.all()) == {
        "clase": egress.THIRD_PARTY, "host": HOST}
    _, fake = fake_chat
    worker = WorkerService(app_state.config, app_state.db, app_state.bus,
                           app_state.identity_manager, app_state.lce, lambda: fake)
    worker_policy = worker.policy()
    assert worker_policy["third_party_backend"] is True
    assert worker_policy["enabled"] is False and worker_policy["kinds"] == []
    result = asyncio.run(worker.handle("peer", task_message()))
    assert result["code"] == "E_POLICY" and "third-party" in result["detail"]
    assert fake.calls == []
