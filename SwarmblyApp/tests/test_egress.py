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
        if request.url.path.endswith("/api/tags"):
            # an Ollama cloud model is listed with the host it is forwarded to
            return httpx.Response(200, json={"models": [
                {"name": "qwen2.5:7b"},
                {"name": "grande-pro:cloud", "remote_host": "https://ollama.com"},
                {"name": "sin-sufijo:latest", "remote_host": "https://ollama.com"}]})
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


def test_circle_and_unclassified_peer_policy():
    policy = egress.Policy()
    assert policy.allows(egress.CIRCLE, "peer-node", egress.FRAGMENT)[0]
    # D-017: a peer outside every circle is refused, never labelled third party.
    assert not policy.allows("", "peer-node", egress.FRAGMENT)[0]
    with egress.request_ledger("circle-check"):
        egress.check_call("peer://node-1", 10, "fragmento t0", kind=egress.FRAGMENT,
                          destination_class=egress.CIRCLE,
                          destination_label="nodo node-1",
                          circle_id="c1", circle_name="Familia",
                          member_name="Ana")
    with egress.request_ledger("circle-block") as ledger:
        with pytest.raises(egress.EgressDenied):
            egress.check_call("peer://node-2", 10, "fragmento t0",
                              kind=egress.FRAGMENT, destination_class="",
                              destination_label="nodo node-2")
    assert ledger.events[-1]["bloqueado"] is True
    assert ledger.events[-1]["clase"] == ""


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


# -- the receipt sees what leaves from worker threads (3.0.1 fix) -------------

class _QueryingProvider:
    """Looks things up from a worker thread, as the real providers do."""
    names = ["web"]
    lang = "es"

    def _send(self, term: str) -> None:
        egress.record_public_query("http://127.0.0.1:8888/search?q=" + term.replace(" ", "+"),
                                   provider="searxng")

    def lookup(self, text, profile=None):
        self._send(text)
        return None

    def passages(self, name, focus=None):
        self._send(name)
        return []


def test_carry_keeps_the_ledger_in_pool_threads():
    from concurrent.futures import ThreadPoolExecutor
    with egress.request_ledger("r1") as ledger, egress.purpose(egress.QUESTION):
        def one(i):
            egress.record(tipo=egress.current_purpose(), valor=str(i))
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(one, range(3)))                 # plain: lost
            assert ledger.events == []
            list(pool.map(egress.carry(one), range(3)))   # carried: recorded
    assert sorted(e["valor"] for e in ledger.events) == ["0", "1", "2"]
    assert {e["tipo"] for e in ledger.events} == {egress.QUESTION}


def test_carry_reaches_run_in_executor():
    async def main():
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, egress.carry(lambda: egress.record(valor="x")))
    with egress.request_ledger("r2") as ledger:
        asyncio.run(main())
    assert [e["valor"] for e in ledger.events] == ["x"]


def test_public_lookups_from_worker_threads_reach_the_receipt():
    from swarmbly_app import local_context
    from swarmbly_app.engine import evidence
    provider = _QueryingProvider()
    with egress.request_ledger("r3") as ledger:
        evidence.gather({1: "Orestias ficticia", 2: "Lontra ficticia"}, provider)
        local_context.public_evidence(
            [{"name": "Puma ficticio", "from": "pregunta"}],
            local_context.parse_expansion(""), provider)
    sent = sorted(e["valor"] for e in ledger.events if e["tipo"] == egress.PUBLIC_QUERY)
    assert "Puma ficticio" in sent
    receipt = egress.build_receipt(ledger, lane="local", route="local+consulta_publica",
                                   answer="", consent={}, passages=[])
    assert len(receipt["envios"]) == len(ledger.events) >= 1


# --- Ollama cloud models (3.2) -------------------------------------------------------
#
# Ollama runs on this computer and forwards its cloud models to ollama.com: the
# address the app connects to (127.0.0.1) is not where the text goes. Found on
# 15 November 2026 while adding a composer model by role: a cloud model chosen
# as the chat's model or the composer would have taken the user's documents
# off the computer with an empty receipt.

def _cloud_setup(state, model="grande-pro:cloud", **privacy):
    from swarmbly_app.inference import ollama as oll
    oll._REMOTE.clear()
    _personal_setup(state, **privacy)
    state.config.update({"model": {"backend": "ollama", "backend_url": "http://127.0.0.1:11434",
                                   "model_name": model}})


@pytest.mark.parametrize("name,host", [("deepseek-v4-pro:cloud", "ollama.com"), ("gpt-oss:120b-cloud", "ollama.com"),
                                       ("qwen2.5:7b", ""), ("cloud-model:7b", ""), ("cloudy", "")])
def test_cloud_models_by_name(name, host):
    assert egress.cloud_host_by_name(name) == host


def test_cloud_model_counts_as_a_third_party_destination():
    dest = egress.model_destination({"model": {"backend_url": "http://127.0.0.1:11434",
                                               "model_name": "grande-pro:cloud"}})
    assert dest == {"clase": egress.THIRD_PARTY, "host": "ollama.com", "via": "127.0.0.1"}


@pytest.mark.parametrize("model", ["grande-pro:cloud", "sin-sufijo:latest"])
def test_unauthorised_ollama_cloud_model_receives_nothing(app_state, capture, model):
    _cloud_setup(app_state, model=model)
    msg = _ask(app_state, "¿Desde cuándo coordino el monitoreo del proyecto Zeta?")
    assert msg["meta"]["status"] == "failed" and "not authorised" in msg["meta"]["error"]
    assert not [r for r in capture.requests if r.url.path.endswith("/api/chat")]
    assert not any(MARKER in b for b in capture.bodies())
    receipt = msg["meta"]["receipt"]
    assert receipt["bloqueados"] and receipt["destino_modelo"]["host"] == "ollama.com"


def test_ollama_cloud_model_authorised_for_questions_keeps_documents_out(app_state, capture):
    _cloud_setup(app_state, third_party_models=["ollama.com"])
    msg = _ask(app_state, "¿Desde cuándo coordino el monitoreo del proyecto Zeta?")
    assert msg["meta"]["status"] == "done" and "passages_withheld" in msg["meta"]
    sent = [b for r, b in zip(capture.requests, capture.bodies()) if r.url.path.endswith("/api/chat")]
    assert sent and not any(MARKER in b for b in sent)
    receipt = msg["meta"]["receipt"]
    assert [s["destino"] for s in receipt["envios"]] == ["ollama.com"] and receipt["pasajes_enviados"] == 0


def test_a_cloud_model_set_by_hand_is_stopped_where_the_bytes_leave(capture):
    from swarmbly_app.inference import ollama as oll
    oll._REMOTE.clear()
    backend = oll.OllamaBackend("http://127.0.0.1:11434")
    with egress.request_ledger("t") as ledger, egress.purpose(egress.PASSAGES):
        with pytest.raises(egress.EgressDenied):
            backend.stream_chat([{"role": "user", "content": MARKER}], model="grande-pro:cloud", max_tokens=5)
    assert not [r for r in capture.requests if r.url.path.endswith("/api/chat")]
    assert any(e.get("bloqueado") and e.get("destino") == "ollama.com" for e in ledger.events)


def test_cloud_composer_is_not_used_without_both_authorisations(app_state, capture):
    _cloud_setup(app_state, model="qwen2.5:7b")
    app_state.config.update({"compose": {"model": "grande-pro:cloud"}})
    conv = app_state.chat.create_conversation(mode="local")
    app_state.chat.send(conv["id"], "Escribe un párrafo de 60 a 80 palabras sobre mi trabajo en el proyecto Zeta.",
                        mode="local", run_async=False)
    msg = app_state.chat.get_messages(conv["id"])[-1]
    assert msg["meta"]["status"] == "done" and "ollama.com" in msg["meta"]["composer_blocked"]
    models = [json.loads(b).get("model") for r, b in zip(capture.requests, capture.bodies())
              if r.url.path.endswith("/api/chat")]
    assert models and "grande-pro:cloud" not in models


def test_worker_never_shares_a_cloud_model(app_state, fake_chat):
    from swarmbly_app.p2p.worker import WorkerService
    app_state.config.update({"model": {"model_name": "grande-pro:cloud"},
                             "swarm": {"worker_enabled": True, "worker_models": ["qwen2.5:7b", "x:120b-cloud"]}})
    _, fake = fake_chat
    worker = WorkerService(app_state.config, app_state.db, app_state.bus,
                           app_state.identity_manager, app_state.lce, lambda: fake)
    assert worker.shared_models() == ["qwen2.5:7b"]
    assert worker.policy()["third_party_backend"] is True and worker.policy()["enabled"] is False
