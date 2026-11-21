"""WP4b: the search and corpus node-role executors (D-018).

The privacy rules matter more than the features: a search task carries only a
public query inside a trusted circle, a corpus task reads only the project the
owner shared with that circle, and the requester labels returned material with
the member and circle it actually sent to.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from swarmbly_app import egress
from swarmbly_app.chat import ActiveRequest
from swarmbly_app.engine.directory import Directory
from swarmbly_app.engine.orchestrator import Orchestrator
from swarmbly_app.engine.scheduler import (LatencyStats, Scheduler, TaskFailed)
from swarmbly_app.node_roles import (corpus_size_bucket, derive_roles,
                                     search_engines)
from swarmbly_app.p2p.messages import WIRE_VERSION, packet
from swarmbly_app.p2p.worker import E_ROLE_UNAVAILABLE
from swarmbly_app.state import AppState, _build_advertisement

from conftest import FakeBackend

_ports = itertools.count(20940)
CIRCLE_NAME = "Nodos"


def wait_for(predicate, timeout=10.0, step=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def make_node(tmp_path, name, *, worker=False, models=None, search=False,
              corpus=None, mode="circle", reply="a useful fragment answer",
              providers=("wikipedia",), port=None):
    state = AppState(str(tmp_path / name))
    models = list(models or ["fake-model:1b"])
    cfg = {
        "swarm": {"p2p_port": port or next(_ports), "p2p_host": "127.0.0.1",
                  "lan_enabled": False, "worker_enabled": worker,
                  "worker_models": models, "worker_max_concurrent": 2,
                  "timeout_ms": 8000, "hedge_fallback_ms": 3000},
        "circle": {"admission_mode": mode, "node_name": name},
        "privacy": {"tier": "GLOBAL"},
        "model": {"model_name": models[0]},
        "evidence": {"providers": list(providers), "searxng_url": ""},
        "node_roles": {"search": {"enabled": bool(search)}},
    }
    if corpus is not None:
        cfg["node_roles"]["corpus"] = dict(corpus)
    state.config.update(cfg)
    fake = FakeBackend(reply)
    state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    state.start_p2p()
    return state, fake


@pytest.fixture()
def nodes(tmp_path):
    created = []

    def factory(*args, **kw):
        state, fake = make_node(tmp_path, *args, **kw)
        created.append(state)
        return state, fake

    yield factory
    for state in created:
        state.stop()


def add_to_circle(owner, member, circle=None):
    if circle is None:
        circle = owner.circles.create_circle(CIRCLE_NAME)
    invite = owner.circles.invite(
        circle["circle_id"],
        endpoints=[f"127.0.0.1:{owner.nodes.listen_port}"])
    member.circles.accept_invitation(
        invite["code"], endpoints=[f"127.0.0.1:{member.nodes.listen_port}"])
    assert wait_for(lambda: any(
        r["node_id"] == member.identity.node_id
        for r in owner.circles.list_payload()["circles"][0]["pending_joins"]))
    owner.circles.approve(circle["circle_id"], member.identity.node_id)
    assert wait_for(lambda: member.identity.node_id in owner.nodes.peers
                    and owner.nodes.peers[member.identity.node_id].admitted)
    assert wait_for(lambda: owner.identity.node_id in member.nodes.peers
                    and member.nodes.peers[owner.identity.node_id].admitted)
    return circle


def role_packet(role, instruction, *, attempt="role:0", lang="en"):
    return packet(
        attempt_id=attempt,
        contract={"lang": lang},
        predecessors=[],
        task={"instruction": instruction, "kind": "generate",
              "expects": {"format": "prose", "max_tokens": 128}},
        deadline_ms=60000, lane="PUBLIC", tier="GLOBAL",
        constraints={"role": role})


def builder(role, instruction):
    def build(attempt, family=None, model=None):
        return role_packet(role, instruction, attempt=f"role:{attempt}")
    return build


def scheduler_for(owner, *, k_min=1, k_max=1):
    directory = Directory(owner.nodes, None, remote_allowed=True)
    return Scheduler(directory, SimpleNamespace(publish=lambda *a, **k: None),
                     "r", k_min=k_min, k_max=k_max, max_concurrency=2,
                     timeout_s=8, hedge_fallback_s=4, latency=LatencyStats(),
                     min_params_b=1.5, role_stats=owner.role_stats)


def wiki_fetch(calls, title="Mockingbird", snippet="A mockingbird is a bird."):
    def fetch(url, timeout, user_agent):
        calls.append(url)
        return {"query": {"search": [{"title": title, "snippet": snippet}]}}
    return fetch


# -- opt-in and advertisement --------------------------------------------------------

def test_executors_default_off(nodes):
    state, _ = nodes("default", worker=True, models=["llama3.1:8b"])
    roles = _build_advertisement(state)["roles"]
    assert not any(role["role"] in ("search", "corpus") for role in roles)
    assert state.worker.node_roles() == [
        {"role": "large_model", "model": "llama3.1:8b", "params_b": 8.0}]


def test_worker_off_means_no_executor_roles(nodes):
    state, _ = nodes("off", worker=False, search=True,
                     corpus={"project_id": "", "circle_ids": [],
                             "display_name": ""})
    assert _build_advertisement(state)["roles"] == []


def test_search_advertisement_lists_only_configured_engines(nodes):
    state, _ = nodes("search", worker=True, models=["qwen2.5:3b"], search=True)
    roles = _build_advertisement(state)["roles"]
    search = next(role for role in roles if role["role"] == "search")
    assert search["engines"] == ["wikipedia"]
    # A configured SearXNG URL is an engine this worker can really use.
    state.config.update({"evidence": {"providers": ["wikipedia", "web"],
                                      "searxng_url": "http://127.0.0.1:8088"}})
    state.on_config_changed()
    search = next(role for role in _build_advertisement(state)["roles"]
                  if role["role"] == "search")
    assert search["engines"] == ["wikipedia", "searxng"]
    # PubMed on, Wikipedia off: the role never lists an engine it cannot use.
    state.config.update({"evidence": {"providers": ["pubmed"], "searxng_url": ""}})
    search = next(role for role in _build_advertisement(state)["roles"]
                  if role["role"] == "search")
    assert search["engines"] == ["pubmed"]


def test_corpus_size_buckets_and_derivation():
    assert corpus_size_bucket(0) == "S"
    assert corpus_size_bucket(25) == "S"
    assert corpus_size_bucket(26) == "M"
    assert corpus_size_bucket(200) == "M"
    assert corpus_size_bucket(201) == "L"
    cfg = {"node_roles": {"search": {"enabled": True}},
           "evidence": {"providers": ["wikipedia"]}}
    roles = derive_roles(["qwen2.5:3b"], cfg,
                         corpus_share={"name": "Field notes", "size": "S"})
    assert {"role": "search", "engines": ["wikipedia"]} in roles
    assert {"role": "corpus", "name": "Field notes", "size": "S"} in roles
    assert search_engines({"evidence": {"providers": ["wikidata"]}}) == []


# -- public query --------------------------------------------------------------------

def test_private_terms_are_never_sent(app_state):
    assert app_state._public_query("Rincón Alto") == ""
    query = app_state._public_query("Busca la Parcela Norte sobre el mockingbird")
    assert "mockingbird" in query
    assert "Parcela" not in query and "Norte" not in query
    assert len(query) <= 160


def test_search_packet_carries_only_the_public_query():
    from swarmbly_app.engine.packets import PacketPlan, build_search_message
    from swarmbly_app.p2p.messages import new_session_id
    plan = PacketPlan(task_id="t0", wire_task_id="", level=0, index=0,
                      instruction="mockingbird", consumes=False, depends_on=(),
                      lane="PUBLIC", role="search")
    message = build_search_message(plan, new_session_id(), 0,
                                   deadline_ms=60000, tier="GLOBAL")
    assert message["contract"] == {}
    assert message["predecessors"] == []
    assert message["task"]["instruction"] == "mockingbird"
    assert "conversation" not in str(message).lower()


# -- worker search -------------------------------------------------------------------

def test_search_refuses_a_document_like_query(nodes):
    state, _ = nodes("doc", worker=True, models=["qwen2.5:3b"], search=True,
                     mode="own_devices")
    calls = []
    state.worker.search_fetch = wiki_fetch(calls)
    long_query = "word " * 40
    reply = asyncio.run(state.worker.handle(
        "peer", role_packet("search", long_query)))
    assert reply["type"] == "error" and reply["code"] == "E_POLICY"
    reply = asyncio.run(state.worker.handle(
        "peer", role_packet("search", "one line\nsecond line")))
    assert reply["type"] == "error" and reply["code"] == "E_POLICY"
    assert calls == [] and state.worker.ledger_events() == []


def test_search_requires_a_trusted_circle(nodes):
    state, _ = nodes("own", worker=True, models=["qwen2.5:3b"], search=True,
                     mode="own_devices")
    calls = []
    state.worker.search_fetch = wiki_fetch(calls)
    reply = asyncio.run(state.worker.handle(
        "peer", role_packet("search", "mockingbird")))
    assert reply["type"] == "error" and reply["code"] == E_ROLE_UNAVAILABLE
    assert calls == [] and state.worker.ledger_events() == []


def test_search_role_runs_in_a_circle_and_records_on_behalf(nodes):
    owner, _ = nodes("owner", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("worker", worker=True, models=["qwen2.5:3b"], search=True)
    circle = add_to_circle(owner, worker)
    assert wait_for(lambda: "search" in {
        entry["role"] for entry in owner.nodes.peers[
            worker.identity.node_id].advertisement.get("roles", [])})
    calls = []
    worker.worker.search_fetch = wiki_fetch(calls)
    scheduler = scheduler_for(owner)
    replicas = asyncio.run(scheduler.run_task(
        "t0", builder("search", "mockingbird"), 128, role="search"))
    assert replicas and "Mockingbird" in replicas[0].text
    assert replicas[0].sources[0]["kind"] == "search"
    attempt = scheduler.attempts[0]
    assert attempt.executor == "search" and attempt.query == "mockingbird"
    assert attempt.destination_class == egress.CIRCLE
    assert attempt.circle_name == CIRCLE_NAME
    events = worker.worker.ledger_events()
    on_behalf = [event for event in events if event.get("on_behalf")]
    assert on_behalf and on_behalf[0]["query"] == "mockingbird"
    assert on_behalf[0]["circle_name"] == CIRCLE_NAME
    assert on_behalf[0]["executor"] == "search"
    # The worker's own ledger names the real destination (the engine host),
    # not the requester: the requester is the on-behalf field.
    assert all("wikipedia.org" in event["destino"] for event in on_behalf
               if event.get("clase") != egress.LOCAL)
    assert on_behalf[0]["on_behalf"] == owner.identity.node_id[:12]
    assert calls and "wikipedia.org" in calls[0]

    # Requester receipt: public query text, circle, member and executor kind;
    # the engine cannot be verified by the requester and the receipt says so.
    request = ActiveRequest(request_id="r", conversation_id="c", message_id="m")
    request.ledger = egress.Ledger()
    meta: dict = {}
    owner.chat._attach_receipt(
        request, meta, "answer",
        {"n_tasks": 1, "attempts": [attempt.to_dict()]})
    entry = meta["receipt"]["envios"][0]
    assert entry["tipo"] == "entidad_publica"
    assert entry["valor"] == "mockingbird"
    assert entry["circle_name"] == CIRCLE_NAME
    assert entry["executor"] == "search"
    assert entry["on_behalf"] is True and entry["engine_unverified"] is True
    assert circle["circle_id"] == attempt.circle_id


def test_search_non_member_gets_role_unavailable(nodes):
    owner, _ = nodes("owner2", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("worker2", worker=True, models=["qwen2.5:3b"], search=True)
    stranger, _ = nodes("stranger", worker=False, models=["stranger:1b"])
    add_to_circle(owner, worker)
    assert wait_for(lambda: owner.identity.node_id in worker.nodes.peers)
    calls = []
    worker.worker.search_fetch = wiki_fetch(calls)
    reply = asyncio.run(worker.worker.handle(
        stranger.identity.node_id, role_packet("search", "mockingbird")))
    assert reply["type"] == "error" and reply["code"] == E_ROLE_UNAVAILABLE
    assert calls == [] and worker.worker.ledger_events() == []


def test_orchestrator_places_a_corpus_plan_task_with_honest_provenance(nodes, tmp_path):
    owner, _ = nodes("orch-owner2", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("orch-worker2", worker=True, models=["qwen2.5:3b"])
    project = _make_project(
        worker, tmp_path, "Orch shared",
        "# Field notes\n\nExtract key fact per item from the apples and bridges notes.\n")
    circle = add_to_circle(owner, worker)
    worker.config.update({"node_roles": {"corpus": {
        "project_id": project.id, "circle_ids": [circle["circle_id"]],
        "display_name": "Orch set"}}})
    worker.on_config_changed()
    assert wait_for(lambda: "corpus" in {
        entry["role"] for entry in owner.nodes.peers[
            worker.identity.node_id].advertisement.get("roles", [])})
    result = owner.get_orchestrator().run(
        TEST_PROMPT, mode="lan", task_roles={"t0": "corpus"})
    assert result["routed"] == "distributed", result
    attempt = next(a for a in result["metadata"]["attempts"]
                   if a.get("executor") == "corpus")
    assert attempt["role"] == "corpus"
    sources = [s for s in result["metadata"]["role_sources"]
               if s.get("executor") == "corpus"]
    assert sources and sources[0]["kind"] == "corpus"
    assert sources[0]["circle_name"] == CIRCLE_NAME
    assert sources[0]["member_name"] == "orch-worker2"
    assert str(project.path) not in str(sources)


TEST_PROMPT = (
    "Extract one key fact per item from the following list of five items: "
    "apples, bridges, comets, drums, electrons. List 5 bullet points, one per "
    "item, separately."
)


def test_orchestrator_places_a_search_plan_task_and_labels_its_sources(nodes):
    owner, _ = nodes("orch-owner", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("orch-worker", worker=True, models=["qwen2.5:3b"],
                      search=True)
    add_to_circle(owner, worker)
    assert wait_for(lambda: "search" in {
        entry["role"] for entry in owner.nodes.peers[
            worker.identity.node_id].advertisement.get("roles", [])})
    calls = []

    def fetch(url, timeout, user_agent):
        calls.append(url)
        return {"query": {"search": [{
            "title": "Extract key fact per item from",
            "snippet": "Extract key fact per item from a public page."}]}}
    worker.worker.search_fetch = fetch
    result = owner.get_orchestrator().run(
        TEST_PROMPT, mode="lan", task_roles={"t0": "search"})
    assert result["routed"] == "distributed", result
    attempts = result["metadata"]["attempts"]
    search_attempt = next(a for a in attempts if a.get("executor") == "search")
    assert search_attempt["role"] == "search"
    assert search_attempt["query"]
    assert "Rincón" not in search_attempt["query"]
    sources = result["metadata"]["role_sources"]
    assert sources and sources[0]["kind"] == "search"
    assert sources[0]["circle_name"] == CIRCLE_NAME
    assert sources[0]["member_name"] == "orch-worker"
    assert calls


# -- worker corpus -------------------------------------------------------------------

def _make_project(state, tmp_path, name, text, filename="notes.md"):
    project = state.projects.create(name, parent=tmp_path / f"{name}-projects")
    project.sources.mkdir(parents=True, exist_ok=True)
    (project.sources / filename).write_text(text, encoding="utf-8")
    return project


def test_corpus_reads_only_the_shared_project_and_cites_no_paths(nodes):
    state, _ = nodes("corpus-local", worker=True, models=["qwen2.5:3b"],
                     mode="own_devices")
    shared = _make_project(state, Path(state.dirs.root), "Shared",
                           "# Field notes\n\nEl piquero de patas azules es un ave marina.\n")
    other = _make_project(state, Path(state.dirs.root), "Other",
                          "# Other\n\nUn unicornio verde vive en la luna.\n")
    state.config.update({"node_roles": {"corpus": {
        "project_id": shared.id, "circle_ids": [], "display_name": "Field set"}}})
    reply = state.worker.execute_local(
        role_packet("corpus", "piquero de patas azules"),
        state.worker.shared_models(), 5)
    assert reply["type"] == "result", reply
    assert reply["executor"] == "corpus"
    assert reply["sources"]
    source = reply["sources"][0]
    assert "piquero" in source["text"].lower()
    assert "unicornio" not in reply["text"].lower()
    assert source["title"] == "notes" and source["span"].startswith("p")
    assert source["cite"].startswith("doc:")
    assert str(shared.path) not in reply["text"]
    assert str(other.path) not in reply["text"]
    assert "/" not in source["title"] and "/" not in source["span"]


def test_corpus_circle_not_shared_refused_without_retrieval(nodes):
    owner, _ = nodes("owner3", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("worker3", worker=True, models=["qwen2.5:3b"])
    project = _make_project(worker, Path(worker.dirs.root), "Shared",
                            "# Notes\n\nEl piquero es un ave.\n")
    circle = add_to_circle(owner, worker)
    worker.config.update({"node_roles": {"corpus": {
        "project_id": project.id, "circle_ids": ["another-circle"],
        "display_name": "Field set"}}})
    worker.on_config_changed()
    called = []
    worker.worker.lce.retrieve = lambda *a, **k: called.append(1) or []
    reply = asyncio.run(worker.worker.handle(
        owner.identity.node_id, role_packet("corpus", "piquero")))
    assert reply["type"] == "error" and reply["code"] == E_ROLE_UNAVAILABLE
    assert called == [] and worker.worker.ledger_events() == []


def test_corpus_not_shared_with_the_requesters_circle_is_refused(nodes):
    state, _ = nodes("corpus-unshared", worker=True, models=["qwen2.5:3b"])
    project = _make_project(state, Path(state.dirs.root), "Shared",
                            "# Notes\n\nEl piquero es un ave.\n")
    state.config.update({"node_roles": {"corpus": {
        "project_id": project.id, "circle_ids": ["circle-b"],
        "display_name": "Field set"}}})
    state.worker.circle_for = lambda node_id, allowed=None: (
        None if allowed is not None and "circle-a" not in allowed
        else {"circle_id": "circle-a", "circle_name": "Other circle"})
    called = []
    state.worker.lce.retrieve = lambda *a, **k: called.append(1) or []
    message = role_packet("corpus", "piquero")
    reply = state.worker._run_corpus(
        message, message["task"], attempt_id="x", requester="peer",
        local=False, started=time.monotonic(), queue_ms=0, serving_others=False)
    assert reply["type"] == "error" and reply["code"] == E_ROLE_UNAVAILABLE
    assert called == []


def test_corpus_role_runs_in_a_circle_with_neutral_provenance(nodes):
    owner, _ = nodes("owner4", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("worker4", worker=True, models=["qwen2.5:3b"])
    project = _make_project(worker, Path(worker.dirs.root), "Shared",
                            "# Field notes\n\nEl piquero de patas azules es un ave marina.\n")
    circle = add_to_circle(owner, worker)
    worker.config.update({"node_roles": {"corpus": {
        "project_id": project.id, "circle_ids": [circle["circle_id"]],
        "display_name": "Field set"}}})
    worker.on_config_changed()
    assert wait_for(lambda: "corpus" in {
        entry["role"] for entry in owner.nodes.peers[
            worker.identity.node_id].advertisement.get("roles", [])})
    scheduler = scheduler_for(owner)
    replicas = asyncio.run(scheduler.run_task(
        "t0", builder("corpus", "piquero de patas azules"), 128, role="corpus"))
    assert replicas and replicas[0].sources
    source = replicas[0].sources[0]
    assert source["title"] == "notes" and "/" not in source["title"]
    assert str(project.path) not in replicas[0].text
    events = worker.worker.ledger_events()
    sent = [event for event in events if event.get("executor") == "corpus"]
    assert sent and sent[0]["tipo"] == egress.PASSAGES
    assert sent[0]["circle_name"] == CIRCLE_NAME
    assert sent[0]["passages"] >= 1 and sent[0]["bytes"] > 0
    # The requester labels it with the member and circle it sent to.
    labelled = Orchestrator._role_sources({"t0": {"replica_meta": [{
        "node": worker.identity.node_id[:12], "executor": "corpus",
        "circle_id": circle["circle_id"], "circle_name": CIRCLE_NAME,
        "member_name": "worker4", "sources": replicas[0].sources}]}})
    assert labelled[0]["circle_name"] == CIRCLE_NAME
    assert labelled[0]["member_name"] == "worker4"
    assert labelled[0]["executor"] == "corpus"


def test_corpus_non_member_gets_role_unavailable(nodes):
    owner, _ = nodes("owner5", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("worker5", worker=True, models=["qwen2.5:3b"])
    stranger, _ = nodes("stranger5", worker=False, models=["stranger:1b"])
    project = _make_project(worker, Path(worker.dirs.root), "Shared",
                            "# Notes\n\nEl piquero es un ave.\n")
    circle = add_to_circle(owner, worker)
    worker.config.update({"node_roles": {"corpus": {
        "project_id": project.id, "circle_ids": [circle["circle_id"]],
        "display_name": "Field set"}}})
    worker.on_config_changed()
    called = []
    worker.worker.lce.retrieve = lambda *a, **k: called.append(1) or []
    reply = asyncio.run(worker.worker.handle(
        stranger.identity.node_id, role_packet("corpus", "piquero")))
    assert reply["type"] == "error" and reply["code"] == E_ROLE_UNAVAILABLE
    assert called == [] and worker.worker.ledger_events() == []


# -- passage forwarding gate ---------------------------------------------------------

def test_corpus_passages_are_not_forwarded_without_passage_permission(nodes):
    owner, _ = nodes("owner6", worker=False, models=["owner-model:1b"])
    worker, _ = nodes("worker6", worker=True, models=["qwen2.5:3b"])
    circle = add_to_circle(owner, worker)
    scheduler = scheduler_for(owner)
    packets = []

    def build(attempt, family=None, model=None):
        message = packet(
            attempt_id=f"p:{attempt}",
            contract={"lang": "en"}, predecessors=[],
            task={"instruction": "a normal fragment", "kind": "generate",
                  "expects": {"format": "prose", "max_tokens": 128}},
            deadline_ms=60000, lane="PUBLIC", tier="GLOBAL",
            constraints={})
        packets.append(message)
        return message
    with pytest.raises(TaskFailed):
        asyncio.run(scheduler.run_task("t0", build, 128, require_passages=True))
    assert owner.circles.set_circle_passages(circle["circle_id"], True)
    assert owner.circles.peer_passages_allowed(worker.identity.node_id)[0]
    replicas = asyncio.run(scheduler.run_task(
        "t0", build, 128, require_passages=True))
    assert replicas
    attempt = scheduler.attempts[-1]
    assert attempt.carries_passages is True
    assert attempt.to_dict()["carries_passages"] is True


# -- local pool ----------------------------------------------------------------------

def test_local_pool_runs_search_and_corpus(app_state, tmp_path):
    project = _make_project(app_state, tmp_path, "Local shared",
                            "# Notes\n\nEl piquero de patas azules es un ave marina.\n")
    app_state.config.update({
        "swarm": {"worker_enabled": False},
        "model": {"multi_model": True,
                  "local_models": ["qwen2.5:3b", "llama3.2:3b"]},
        "node_roles": {"search": {"enabled": True},
                       "corpus": {"project_id": project.id, "circle_ids": [],
                                  "display_name": "Local set"}},
        "evidence": {"providers": ["wikipedia"], "searxng_url": ""},
        "privacy": {"tier": "GLOBAL"},
    })
    app_state.start_p2p()
    calls = []
    app_state.worker.search_fetch = wiki_fetch(calls)
    pool = app_state._local_pool()
    assert pool is not None
    assert {role["role"] for role in pool.peer.advertisement["roles"]} >= {
        "search", "corpus"}
    scheduler = Scheduler(Directory(None, pool, remote_allowed=False),
                          SimpleNamespace(publish=lambda *a, **k: None), "r",
                          k_min=1, k_max=1, max_concurrency=2, timeout_s=8,
                          hedge_fallback_s=4, latency=LatencyStats(),
                          min_params_b=1.5)
    search = asyncio.run(scheduler.run_task(
        "s", builder("search", "mockingbird"), 128, role="search"))
    assert search and search[0].sources[0]["kind"] == "search"
    corpus = asyncio.run(scheduler.run_task(
        "c", builder("corpus", "piquero de patas azules"), 128, role="corpus"))
    assert corpus and corpus[0].sources[0]["kind"] == "corpus"
    assert "piquero" in corpus[0].text.lower()
    assert calls


# -- model-service passage rule ------------------------------------------------------

class _EgressModel:
    name = "fake"
    accepts_think = False

    def __init__(self):
        self.calls = 0

    def stream_chat(self, messages, *, model, max_tokens=1024, temperature=0.2,
                    **kw):
        from swarmbly_app.inference.base import GenerationResult
        self.calls += 1
        egress.check_call("https://third.example/v1", 8, "modelo",
                          kind=egress.PASSAGES)
        return GenerationResult(text="answer", model=model, completion_tokens=1)


def test_corpus_passages_need_the_requester_passage_permission_for_a_model_service(app_state):
    app_state.config.update({
        "privacy": {"third_party_models": ["third.example"],
                    "third_party_passages": False},
    })
    backend = _EgressModel()
    orchestrator = Orchestrator(app_state.nodes, app_state.bus, backend,
                                app_state.config.all, local_model="qwen2.5:3b")
    message = {"attempt_id": "x", "task": {"instruction": "use the passage"}}
    assert orchestrator._local_fallback("t0", message, 64, "test",
                                        passages=True) is None
    assert backend.calls == 1
    app_state.config.update({"privacy": {"third_party_passages": True}})
    replica = orchestrator._local_fallback("t0", message, 64, "test",
                                           passages=True)
    assert replica is not None and replica.text == "answer"
    assert backend.calls == 2


def test_circle_for_matches_the_shared_circle_among_several(nodes, monkeypatch):
    """A requester in two circles with this node reaches a corpus shared with
    the second one; only valid manifests listing both nodes count."""
    state, _ = nodes("corpus-two-circles", worker=True, models=["qwen2.5:3b"])
    manifests = [{"circle_id": "circle-a", "name": "Alpha"},
                 {"circle_id": "circle-b", "name": "Beta"}]
    monkeypatch.setattr(state.circles, "mode", lambda: "circle")
    monkeypatch.setattr(state.circles, "_local_candidates",
                        lambda node_id, now=None: list(manifests))
    assert state._circle_for("peer")["circle_id"] == "circle-a"
    assert state._circle_for("peer", ["circle-b"])["circle_id"] == "circle-b"
    assert state._circle_for("peer", ["circle-c"]) is None
    monkeypatch.setattr(state.circles, "_local_candidates",
                        lambda node_id, now=None: [])
    assert state._circle_for("peer") is None
