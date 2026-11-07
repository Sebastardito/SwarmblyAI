"""3.0.1: destinations, outbound policy, ledger and privacy receipt.

The synthetic leak test: a source with a marker, a third-party model
reached through a mocked HTTP transport. Nothing leaves without the user's
authorisation, passages need a second one, a node never serves the swarm
through a third party, and the receipt says what actually left.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from swarmbly_app import egress
from swarmbly_app.inference import openai_compat, ollama

MARKER = "ZETA-MARCADOR-7731"
PROVIDER = "https://provider.invalid/v1"


class Capture:
    def __init__(self):
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/chat/completions"):
            body = ('data: {"choices":[{"delta":{"content":"Respuesta de prueba."}}]}\n\n'
                    'data: [DONE]\n\n')
            return httpx.Response(200, text=body)
        if request.url.path.endswith("/api/chat"):
            return httpx.Response(200, text=json.dumps(
                {"message": {"content": "Respuesta local."}, "done": True}) + "\n")
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "remote-model"}]})
        return httpx.Response(404)

    def bodies(self) -> list[str]:
        return [r.content.decode("utf-8", "replace") for r in self.requests]


@pytest.fixture()
def capture(monkeypatch):
    cap = Capture()
    real = httpx.Client

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(cap.handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(openai_compat.httpx, "Client", client)
    monkeypatch.setattr(ollama.httpx, "Client", client)
    return cap


def _personal_setup(state, **privacy):
    state.dirs.sources.mkdir(parents=True, exist_ok=True)
    (state.dirs.sources / "cv.md").write_text(
        f"# Mi currículum\n\nCoordino el monitoreo del proyecto Zeta desde 2024. {MARKER}.",
        encoding="utf-8")
    state.config.update({"model": {"backend": "openai_compat", "backend_url": PROVIDER,
                                   "model_name": "remote-model"},
                         "lce": {"enabled": True, "level": "C1", "dense_retrieval": False,
                                 "query_expansion": False},
                         "privacy": privacy})


def _ask(state, text):
    conv = state.chat.create_conversation(mode="local")
    state.chat.send(conv["id"], text, mode="local", run_async=False)
    return state.chat.get_messages(conv["id"])[-1]


# --- destinations and policy ---------------------------------------------------------

@pytest.mark.parametrize("url,cls", [
    ("http://127.0.0.1:11434", egress.LOCAL), ("http://localhost:8080", egress.LOCAL),
    ("http://[::1]:11434", egress.LOCAL), ("http://192.168.1.20:11434", egress.OWN_NETWORK),
    ("http://10.0.0.5", egress.OWN_NETWORK), ("http://ollama:11434", egress.OWN_NETWORK),
    ("http://nas.local:11434", egress.OWN_NETWORK), ("http://100.101.1.2", egress.OWN_NETWORK),
    ("https://api.openai.com/v1", egress.THIRD_PARTY), ("https://8.8.8.8", egress.THIRD_PARTY),
])
def test_destination_classes(url, cls):
    assert egress.classify_url(url)[0] == cls


def test_local_names_from_environment(monkeypatch):
    monkeypatch.setenv("SWARMBLY_LOCAL_HOSTS", "ollama,searxng")
    assert egress.classify_url("http://ollama:11434")[0] == egress.LOCAL


def test_policy_rules():
    strict = egress.Policy()
    assert not strict.allows(egress.THIRD_PARTY, "api.x.com", egress.QUESTION)[0]
    assert strict.allows(egress.OWN_NETWORK, "nas.local", egress.PASSAGES)[0]
    authorised = egress.Policy(("api.x.com",), third_party_passages=False)
    assert authorised.allows(egress.THIRD_PARTY, "api.x.com", egress.QUESTION)[0]
    assert not authorised.allows(egress.THIRD_PARTY, "api.x.com", egress.PASSAGES)[0]
    assert not authorised.allows(egress.THIRD_PARTY, "api.x.com", egress.UNKNOWN)[0]
    full = egress.Policy(("api.x.com",), third_party_passages=True)
    assert full.allows(egress.THIRD_PARTY, "api.x.com", egress.PASSAGES)[0]
    assert not full.allows(egress.THIRD_PARTY, "api.x.com", egress.FOREIGN)[0]


# --- the synthetic leak test -----------------------------------------------------------

def test_unauthorised_third_party_receives_nothing(app_state, capture):
    _personal_setup(app_state)
    msg = _ask(app_state, "¿Desde cuándo coordino el monitoreo del proyecto Zeta?")
    assert msg["meta"]["status"] == "failed"
    assert "not authorised" in msg["meta"]["error"]
    assert not [r for r in capture.requests if r.url.path.endswith("/chat/completions")]
    assert not any(MARKER in b for b in capture.bodies())
    receipt = msg["meta"]["receipt"]
    assert receipt["envios"] == [] and receipt["bloqueados"]
    assert receipt["destino_modelo"]["clase"] == egress.THIRD_PARTY


def test_authorised_for_questions_keeps_documents_out(app_state, capture):
    _personal_setup(app_state, third_party_models=["provider.invalid"])
    msg = _ask(app_state, "¿Desde cuándo coordino el monitoreo del proyecto Zeta?")
    assert msg["meta"]["status"] == "done"
    sent = [b for r, b in zip(capture.requests, capture.bodies()) if r.url.path.endswith("/chat/completions")]
    assert sent and not any(MARKER in b for b in sent)
    assert "passages_withheld" in msg["meta"]
    receipt = msg["meta"]["receipt"]
    assert receipt["pasajes_enviados"] == 0
    assert [s["tipo"] for s in receipt["envios"]] == [egress.QUESTION]
    assert receipt["envios"][0]["destino"] == "provider.invalid"
    assert receipt["consentimiento"]["modelo_terceros"]["pasajes"] is False
    assert msg["meta"]["computed_at"] == "provider.invalid"


def test_passages_go_only_with_the_second_authorisation(app_state, capture):
    _personal_setup(app_state, third_party_models=["provider.invalid"], third_party_passages=True)
    msg = _ask(app_state, "¿Desde cuándo coordino el monitoreo del proyecto Zeta?")
    sent = [b for r, b in zip(capture.requests, capture.bodies()) if r.url.path.endswith("/chat/completions")]
    assert any(MARKER in b for b in sent)
    receipt = msg["meta"]["receipt"]
    assert receipt["pasajes_enviados"] == 1 and receipt["carril"] == "personal"


def test_local_model_leaves_an_empty_receipt(app_state, capture):
    _personal_setup(app_state)
    app_state.config.update({"model": {"backend": "ollama", "backend_url": "http://127.0.0.1:11434"}})
    msg = _ask(app_state, "¿Desde cuándo coordino el monitoreo del proyecto Zeta?")
    assert msg["meta"]["status"] == "done"
    receipt = msg["meta"]["receipt"]
    assert receipt["envios"] == [] and receipt["bytes_salientes"] == 0
    assert receipt["ruta"] == "local" and receipt["fragmentos_creados"] == 0
    assert receipt["hash_respuesta_sha256"]


def test_embeddings_never_reach_an_unauthorised_third_party(app_state):
    app_state.config.update({"model": {"backend_url": PROVIDER}})
    with pytest.raises(egress.EgressDenied):
        app_state._embed(["texto del documento"], "document")


def test_worker_never_serves_through_a_third_party(app_state, fake_chat):
    from swarmbly_app.p2p.worker import WorkerService
    from tests.test_worker_policy import task_message
    app_state.config.update({"model": {"model_name": "fake-model:1b", "backend": "openai_compat",
                                       "backend_url": PROVIDER},
                             "swarm": {"worker_enabled": True},
                             "privacy": {"third_party_models": ["provider.invalid"],
                                         "third_party_passages": True}})
    _, fake = fake_chat
    worker = WorkerService(app_state.config, app_state.db, app_state.bus,
                           app_state.identity_manager, app_state.lce, lambda: fake)
    assert worker.policy()["enabled"] is False and worker.policy()["kinds"] == []
    result = asyncio.run(worker.handle("peer", task_message()))
    assert result["code"] == "E_POLICY" and "third-party" in result["detail"]
    assert fake.calls == []


# --- ledger and receipt ----------------------------------------------------------------

def test_public_query_records_what_was_actually_sent():
    with egress.request_ledger("r1") as ledger:
        egress.record_public_query(
            "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Lontra+felina+status",
            provider="wikidata")
        egress.record_public_query("http://127.0.0.1:8888/search?q=Lontra+felina&format=json",
                                   provider="searxng")
    values = [e["valor"] for e in ledger.events]
    assert values == ["Lontra felina status", "Lontra felina"]
    assert ledger.events[1]["clase"] == egress.THIRD_PARTY
    assert "reenvía" in ledger.events[1]["destino"]


def test_receipt_flags_a_passage_or_a_personal_name():
    ledger = egress.Ledger("r2")
    passage = "Coordino el monitoreo del proyecto Zeta desde marzo de 2024 en la costa norte"
    ledger.add(destino="www.wikidata.org", clase=egress.THIRD_PARTY, tipo=egress.PUBLIC_QUERY,
               valor=passage, bytes=len(passage))
    ledger.add(destino="www.wikidata.org", clase=egress.THIRD_PARTY, tipo=egress.PUBLIC_QUERY,
               valor="Vera Cárdenas Moll", bytes=18)
    ledger.add(destino="www.wikidata.org", clase=egress.THIRD_PARTY, tipo=egress.PUBLIC_QUERY,
               valor="Lontra felina", bytes=13)
    r = egress.build_receipt(ledger, lane="personal", route="local+consulta_publica",
                             answer="ok", consent={}, passages=[passage],
                             personal_names=["Vera Cárdenas Moll"])
    assert [s["tipo"] for s in r["envios"]] == ["pasaje", "nombre_personal", "entidad_publica"]
    assert r["pasajes_enviados"] == 1 and r["nombres_personales_enviados"] == 1
    assert r["bytes_salientes"] == len(passage) + 18 + 13


# --- secrets -------------------------------------------------------------------------

def test_api_key_never_leaves_through_the_api(app_state):
    from fastapi.testclient import TestClient
    from swarmbly_app.api import create_app
    from swarmbly_app.keystore import get_secret
    app = create_app(app_state)
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    c.headers["X-Swarmbly-Token"] = app.state.guard.token
    r = c.put("/api/config", json={"model": {"api_key": "sk-test-123"},
                                   "privacy": {"third_party_models": ["https://API.Example.com/v1"]}})
    assert r.status_code == 200
    assert "sk-test-123" not in r.text
    assert get_secret("model.api_key") == "sk-test-123"
    assert app_state.config.get("model.api_key") == ""
    got = c.get("/api/config").json()
    assert got["model"]["api_key"] == "" and got["_secrets"]["model.api_key"] == "file"
    assert got["privacy"]["third_party_models"] == ["api.example.com"]
    assert "sk-test-123" not in (app_state.dirs.root / "config.json").read_text(encoding="utf-8")


def test_old_keys_in_config_are_migrated(tmp_path):
    from swarmbly_app.config import Config
    from swarmbly_app.keystore import configure, get_secret, migrate
    from swarmbly_app.paths import DataDirs
    dirs = DataDirs(tmp_path / "d")
    dirs.ensure()
    cfg = Config(dirs)
    cfg.update({"model": {"api_key": "sk-old"}})
    configure(dirs.root)
    assert migrate(cfg) == ["model.api_key"]
    assert cfg.get("model.api_key") == "" and get_secret("model.api_key") == "sk-old"


def test_list_models_sends_the_key(capture):
    backend = openai_compat.OpenAICompatBackend(PROVIDER, api_key="sk-x")
    assert backend.list_models() == ["remote-model"]
    assert capture.requests[-1].headers.get("authorization") == "Bearer sk-x"
