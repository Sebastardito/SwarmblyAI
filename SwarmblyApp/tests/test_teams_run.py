"""Teams end to end and honest partial results (3.5, D-019).

A team is the same plan on one node (the local pool) or on several (real
loopback workers in a shared circle). A step that cannot finish leaves a
partial answer naming it and blocking only its dependents; when nothing
completes the run is failed, and a user stop is still a stop.
"""

from __future__ import annotations

import itertools
import threading
import time

import pytest

from swarmbly_app import egress
from swarmbly_app.state import AppState
from swarmbly_app.teams import normalise_team

from conftest import FakeBackend
from test_node_executors import add_to_circle, make_node

_ports = itertools.count(21940)


def wait_for(predicate, timeout=10.0, step=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


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


def team(steps, name="Team"):
    return normalise_team({"name": name, "steps": steps})


def _send(state, text, team_obj, mode="lan"):
    conv = state.chat.create_conversation(mode=mode)
    state.chat.send(conv["id"], text, mode=mode, run_async=False,
                    team=team_obj)
    return state.chat.get_messages(conv["id"])[-1]


# -- the same team on the local pool -------------------------------------------------

def test_a_team_runs_entirely_on_the_local_pool(app_state, tmp_path):
    app_state.config.update({
        "swarm": {"worker_enabled": True, "query_retries": False},
        "model": {"multi_model": True,
                  "local_models": ["llama3.1:8b", "qwen2.5:7b"],
                  "local_parallel": 2},
        "node_roles": {"large_model_min_b": 7,
                       "reasoner_models": ["qwen2.5:7b"]},
        "privacy": {"tier": "GLOBAL"},
    })
    app_state.start_p2p()
    fake = FakeBackend("a local team answer")
    app_state.backends.resolve = lambda cfg=None: fake  # type: ignore[method-assign]
    pool = app_state._local_pool()
    assert pool is not None
    assert {role["role"] for role in pool.peer.advertisement["roles"]} >= {
        "large_model", "reasoner"}
    template = team([
        {"id": "s1", "name": "Write", "role": "large_model",
         "instruction": "Write about {request}"},
        {"id": "s2", "name": "Check", "role": "reasoner",
         "depends_on": ["s1"], "instruction": "Check the draft."},
    ])
    outcome = app_state.get_orchestrator().run(
        "un tema neutral", mode="local", team=template)
    assert outcome["routed"] == "distributed", outcome
    assert outcome["status"] == "complete", outcome["metadata"]
    assert outcome["metadata"]["team"]["name"] == "Team"
    assert [s["name"] for s in outcome["metadata"]["steps"]] == ["Write", "Check"]
    assert all(s["status"] == "completed" for s in outcome["metadata"]["steps"])
    assert outcome["metadata"]["routing"]["remote_allowed"] is False
    # Nothing left the computer: the local pool is this device's own models.
    assert outcome["metadata"]["attempts"]
    assert all(a["destination_class"] == egress.LOCAL
               for a in outcome["metadata"]["attempts"])


# -- the same team across two circle members -----------------------------------------

def test_the_same_team_places_each_step_by_role_in_a_circle(nodes):
    owner, _ = nodes("team-owner", worker=False, models=["owner:1b"])
    searcher, _ = nodes("team-search", worker=True, models=["qwen2.5:3b"],
                        search=True)
    writer, _ = nodes("team-writer", worker=True, models=["llama3.1:8b"])
    circle = owner.circles.create_circle("Equipo neutral")
    add_to_circle(owner, searcher, circle)
    add_to_circle(owner, writer, circle)
    calls = []

    def fetch(url, timeout, user_agent):
        calls.append(url)
        return {"query": {"search": [{
            "title": "Neutral note", "snippet": "A neutral public fact."}]}}
    searcher.worker.search_fetch = fetch
    template = team([
        {"id": "s1", "name": "Public search", "role": "search",
         "instruction": "Find public sources about {request}"},
        {"id": "s2", "name": "Write", "role": "large_model",
         "depends_on": ["s1"],
         "instruction": "Write the answer from the sources above: {request}"},
    ])
    outcome = owner.get_orchestrator().run(
        "a neutral public question", mode="lan", team=template)
    assert outcome["routed"] == "distributed", outcome
    assert outcome["status"] == "complete", outcome["metadata"]
    attempts = outcome["metadata"]["attempts"]
    by_task = {}
    for attempt in attempts:
        by_task.setdefault(attempt["task"], []).append(attempt)
    search_attempt = by_task["t0"][0]
    write_attempt = by_task["t1"][0]
    assert search_attempt["role"] == "search"
    assert search_attempt["node"] == searcher.identity.node_id[:12]
    assert write_attempt["role"] == "large_model"
    assert write_attempt["node"] == writer.identity.node_id[:12]
    assert search_attempt["destination_class"] == egress.CIRCLE
    assert search_attempt["circle_name"] == "Equipo neutral"
    assert calls


# -- partial results ------------------------------------------------------------------

def test_a_lost_worker_gives_a_partial_answer_with_blocked_dependents(nodes):
    owner, _ = nodes("loss-owner", worker=False, models=["owner:1b"])
    lost, _ = nodes("loss-search", worker=True, models=["qwen2.5:3b"],
                    search=True)
    writer, _ = nodes("loss-writer", worker=True, models=["llama3.1:8b"])
    circle = owner.circles.create_circle("Lost node team")
    add_to_circle(owner, lost, circle)
    add_to_circle(owner, writer, circle)
    stopped = []

    def slow_fetch(url, timeout, user_agent):
        time.sleep(1.2)             # the request is in flight when it dies
        return {"query": {"search": []}}
    lost.worker.search_fetch = slow_fetch

    def on_event(event):
        payload = event.get("payload") or {}
        if (event.get("type") == "swarm.attempt"
                and payload.get("event") == "dispatched"
                and payload.get("executor") == "search" and not stopped):
            stopped.append(True)
            threading.Timer(0.15, lost.stop).start()
    owner.bus.subscribe(on_event)
    template = team([
        {"id": "s1", "name": "Draft", "role": "large_model",
         "instruction": "Write about {request}"},
        {"id": "s2", "name": "Public search", "role": "search",
         "instruction": "Find public sources about {request}"},
        {"id": "s3", "name": "Review", "role": "reasoner",
         "depends_on": ["s2"], "instruction": "Review the search material."},
    ])
    outcome = owner.get_orchestrator().run(
        "a neutral public question", mode="lan", team=template)
    assert outcome["routed"] == "distributed", outcome
    assert outcome["status"] == "partial", outcome["metadata"]
    steps = {step["name"]: step for step in outcome["metadata"]["steps"]}
    assert steps["Draft"]["status"] == "completed"
    assert steps["Public search"]["status"] == "failed"
    assert steps["Public search"]["reason"] in ("node_lost", "deadline")
    assert steps["Review"]["status"] == "blocked"
    assert steps["Review"]["blocked_by"] == ["t1"]
    # The completed step is in the answer; the missing one is named with why.
    assert "a local answer" in outcome["text"] or outcome["text"].strip()
    assert "Public search" in outcome["text"]
    assert "blocked by" in outcome["text"]


def test_nothing_completed_is_failed_not_partial(nodes):
    owner, _ = nodes("failed-owner", worker=False, models=["owner:1b"])
    writer, _ = nodes("failed-writer", worker=True, models=["llama3.1:8b"])
    add_to_circle(owner, writer)
    template = team([
        {"id": "s1", "name": "Search", "role": "search",
         "instruction": "Find public sources about {request}"},
    ])
    outcome = owner.get_orchestrator().run(
        "a neutral public question", mode="lan", team=template)
    assert outcome["routed"] == "distributed", outcome
    assert outcome["status"] == "failed", outcome["metadata"]
    assert outcome["metadata"]["status"] == "failed"
    assert outcome["metadata"]["steps"][0]["reason"] == "role_unavailable"
    assert not any(step["status"] == "completed"
                   for step in outcome["metadata"]["steps"])


def test_a_team_that_carries_no_permission_stays_local(nodes):
    owner, _ = nodes("private-owner", worker=False, models=["owner:1b"])
    searcher, _ = nodes("private-search", worker=True, models=["qwen2.5:3b"],
                        search=True)
    add_to_circle(owner, searcher)
    owner.config.update({"privacy": {"tier": "LOCAL"}})
    owner.on_config_changed()
    calls = []
    searcher.worker.search_fetch = lambda *a, **k: calls.append(1) or {"query": {}}
    template = team([
        {"id": "s1", "name": "Search", "role": "search",
         "instruction": "Find public sources about {request}"},
    ])
    outcome = owner.get_orchestrator().run(
        "my private plan", mode="lan", team=template)
    # No local pool: the team cannot run, and the gate says why.
    assert outcome["routed"] == "local", outcome
    assert "LOCAL" in outcome["reason"]
    assert calls == []


# -- user stop ------------------------------------------------------------------------

def test_a_user_stop_remains_a_stop(nodes):
    owner, _ = nodes("stop-owner", worker=False, models=["owner:1b"])
    worker, fake = nodes("stop-worker", worker=True, models=["llama3.1:8b"])
    fake.delay = 2.0
    add_to_circle(owner, worker)
    stop = threading.Event()
    threading.Timer(0.25, stop.set).start()
    template = team([
        {"id": "s1", "name": "Slow", "role": "large_model",
         "instruction": "Write about {request}"},
    ])
    outcome = owner.get_orchestrator().run(
        "a neutral request", mode="lan", team=template, cancel=stop)
    assert outcome["routed"] == "error", outcome
    assert outcome.get("status") == "stopped"
    assert "interrupted" in outcome["reason"]


# -- chat integration -----------------------------------------------------------------

def test_chat_marks_a_partial_answer_and_stores_the_steps(nodes):
    owner, _ = nodes("chat-owner", worker=False, models=["owner:1b"])
    writer, _ = nodes("chat-writer", worker=True, models=["llama3.1:8b"])
    add_to_circle(owner, writer)
    template = team([
        {"id": "s1", "name": "Write", "role": "large_model",
         "instruction": "Write about {request}"},
        {"id": "s2", "name": "Missing search", "role": "search",
         "instruction": "Find public sources about {request}"},
    ])
    message = _send(owner, "a neutral request", template)
    assert message["meta"]["status"] == "done", message["meta"]
    assert message["meta"]["answer_status"] == "partial"
    swarm = message["meta"]["swarm"]
    assert swarm["status"] == "partial"
    assert {s["name"] for s in swarm["missing_steps"]} == {"Missing search"}
    assert "Missing search" in message["content"]


# -- recipe 4 keeps the waves that worked ---------------------------------------------

class _FlakyWaves:
    """A swarm that fails its second list wave and answers the others."""

    def __init__(self):
        self.prompts = []
        self.calls = 0

    def run(self, prompt, *, mode="lan", request_id=None, cancel=None,
            history=None, passage_texts=None, passage_peer_ids=None, **kw):
        import re
        self.calls += 1
        self.prompts.append(str(prompt))
        if self.calls == 2:
            return {"routed": "error", "status": "failed",
                    "reason": "all 1 attempt(s) failed (E_DEADLINE)",
                    "metadata": {"n_tasks": 1, "attempts": [],
                                 "status": "failed",
                                 "steps": [{"step": "t0", "status": "failed",
                                            "reason": "deadline",
                                            "detail": "the deadline expired"}]},
                    "stages": []}
        items = re.findall(r"^\s*(\d+)\.\s+(.+)$", prompt, re.M)
        text = "\n".join(f"{n}. answer {n}" for n, _ in items)
        return {"routed": "distributed", "text": text,
                "metadata": {"n_tasks": 1, "status": "complete",
                             "attempts": [{"node": "W1", "task": "t0",
                                           "bytes_out": len(prompt)}]},
                "status": "complete", "stages": []}


def test_one_failed_list_wave_keeps_the_others(app_state, monkeypatch):
    from swarmbly_app import recipes
    app_state.chat.orchestrator = lambda: _FlakyWaves()  # type: ignore[assignment]
    app_state.circles.mode = lambda: "own_devices"  # type: ignore[method-assign]
    app_state.circles.own_devices_passages = lambda: False  # type: ignore[method-assign]
    items = [f"item {n}" for n in range(1, 27)]   # 12 + 12 + 2
    job = recipes.normalise_list_job(
        {"items": items, "operation": "Give the status of this item",
         "where": "swarm", "source": {"kind": "pasted"}}, max_items=200)
    conv = app_state.chat.create_conversation(mode="lan")
    app_state.chat.send(conv["id"], job.operation, recipe="list",
                        list_job=job.to_dict(), run_async=False)
    message = app_state.chat.get_messages(conv["id"])[-1]
    meta = message["meta"]
    assert meta["status"] == "done", meta
    assert meta["list"]["answered"] == 14           # waves 1 and 3
    assert meta["list"]["failed"] == 12             # wave 2, item by item
    assert meta["list"]["waves"] == 3
    rows = meta["table"]["rows_data"]
    assert rows[0]["status"] == "answered"
    assert rows[12]["status"] == "failed"
    assert "deadline" in rows[12]["reason"].lower()
    assert rows[-1]["status"] == "answered"         # a later wave still ran
    assert "Wave 2" in message["content"]


# -- regression: a plan without a team still runs and reports complete ---------------

def test_a_request_without_a_team_is_complete_as_before(nodes):
    owner, _ = nodes("plain-owner", worker=False, models=["owner:1b"])
    worker, _ = nodes("plain-worker", worker=True, models=["llama3.1:8b"])
    add_to_circle(owner, worker)
    outcome = owner.get_orchestrator().run(
        "Extract one key fact per item from this list: apples, bridges, comets, "
        "drums, electrons. List 5 bullet points, one per item.", mode="lan")
    assert outcome["routed"] == "distributed", outcome
    assert outcome["status"] == "complete", outcome["metadata"]
    assert outcome["metadata"]["team"] is None
    assert all(step["status"] == "completed"
               for step in outcome["metadata"]["steps"])


# -- T11.1: a failed role step is either recorded as a fallback or failed ----

from test_node_roles import make_node as make_role_node  # noqa: E402


class _AlwaysFailingBackend(FakeBackend):
    """The reviewer's model fails every call: nothing ran that step."""

    name = "fake"

    def stream_chat(self, messages, *, model, **kw):
        from swarmbly_app.inference.base import BackendError
        self.calls.append({"messages": messages, "model": model})
        raise BackendError("Ollama HTTP 400: simulated execution failure")


def _write_review_team():
    return team([
        {"id": "s1", "name": "Write", "role": "large_model",
         "instruction": "Write about {request}"},
        {"id": "s2", "name": "Review", "role": "reasoner",
         "depends_on": ["s1"], "instruction": "Review the draft."},
    ])


def _circle(owner, *members):
    circle = owner.circles.create_circle("T11 neutral circle")
    for member in members:
        add_to_circle(owner, member, circle)
    return circle


def test_a_role_fallback_is_recorded_in_steps_meta_and_receipt(nodes, tmp_path):
    owner, _ = nodes("fallback-owner", worker=False, models=["owner:1b"],
                     reply="a local review from this device")
    writer, _ = nodes("fallback-writer", worker=True, models=["llama3.1:8b"])
    reviewer, _ = make_role_node(
        tmp_path, "fallback-reviewer", worker=True, models=["llama3.1:8b"],
        roles_cfg={"large_model_min_b": 99.0,
                   "reasoner_models": ["llama3.1:8b"]}, mode="circle")
    reviewer.backends.resolve = lambda cfg=None: _AlwaysFailingBackend()
    _circle(owner, writer, reviewer)
    message = _send(owner, "a neutral request", _write_review_team())
    meta = message["meta"]
    steps = {step["name"]: step for step in meta["swarm"]["steps"]}
    assert steps["Write"]["status"] == "completed"
    assert steps["Review"]["status"] == "completed"
    assert steps["Review"]["role_fallback"] is True
    assert steps["Review"]["ran_on"] == "owner:1b"
    assert meta["swarm"]["step_fallbacks"][0]["task"] == "t1"
    assert meta["swarm"]["status"] == "complete"
    assert any(item.get("task") == "t1" and item.get("kind") == "local"
               for item in meta["swarm"]["role_fallbacks"])
    assert any(item.get("task") == "t1" for item in meta["receipt"]["role_fallbacks"])
    assert "a local review from this device" in message["content"]


def test_without_a_fallback_the_step_fails_and_the_note_is_localised(nodes, tmp_path):
    owner, _ = nodes("nofallback-owner", worker=False, models=["owner:1b"])
    owner.backends.resolve = lambda cfg=None: (_ for _ in ()).throw(
        RuntimeError("no local model"))
    owner.orchestrator = None
    writer, _ = nodes("nofallback-writer", worker=True, models=["llama3.1:8b"])
    reviewer, _ = make_role_node(
        tmp_path, "nofallback-reviewer", worker=True,
        models=["llama3.1:8b"],
        roles_cfg={"large_model_min_b": 99.0,
                   "reasoner_models": ["llama3.1:8b"]}, mode="circle")
    reviewer.backends.resolve = lambda cfg=None: _AlwaysFailingBackend()
    _circle(owner, writer, reviewer)
    message = _send(owner, "a neutral request", _write_review_team())
    meta = message["meta"]
    steps = {step["name"]: step for step in meta["swarm"]["steps"]}
    assert steps["Write"]["status"] == "completed"
    assert steps["Review"]["status"] == "failed"
    assert meta["answer_status"] == "partial"
    assert meta["partial"] is True
    assert [step["name"] for step in meta["swarm"]["missing_steps"]] == ["Review"]
    assert "Review" in message["content"]
    assert "could not be completed" in message["content"]
    assert "Ollama HTTP" not in message["content"]
    assert "execution failed" not in message["content"]


def test_a_team_with_nothing_completed_fails_with_the_localised_note(nodes, tmp_path):
    owner, _ = nodes("allfail-owner", worker=False, models=["owner:1b"])
    owner.backends.resolve = lambda cfg=None: (_ for _ in ()).throw(
        RuntimeError("no local model"))
    owner.orchestrator = None
    reviewer, _ = make_role_node(
        tmp_path, "allfail-reviewer", worker=True,
        models=["llama3.1:8b"],
        roles_cfg={"large_model_min_b": 99.0,
                   "reasoner_models": ["llama3.1:8b"]}, mode="circle")
    reviewer.backends.resolve = lambda cfg=None: _AlwaysFailingBackend()
    _circle(owner, reviewer)
    template = team([
        {"id": "s1", "name": "Review", "role": "reasoner",
         "instruction": "Review {request}"},
    ])
    message = _send(owner, "a neutral request", template)
    meta = message["meta"]
    assert meta["status"] == "failed"
    assert meta["swarm"]["status"] == "failed"
    assert "Review" in meta["error"]
    assert "could not be completed" in meta["error"]
    assert "Ollama HTTP" not in meta["error"]


def test_a_generic_worker_that_runs_a_reasoner_step_is_recorded(nodes):
    owner, _ = nodes("generic-owner", worker=False, models=["owner:1b"])
    writer, _ = nodes("generic-writer", worker=True, models=["llama3.1:8b"],
                      reply="a generic review answer")
    _circle(owner, writer)
    template = team([
        {"id": "s1", "name": "Review", "role": "reasoner",
         "instruction": "Review {request}"},
    ])
    outcome = owner.get_orchestrator().run(
        "a neutral request", mode="lan", team=template)
    assert outcome["status"] == "complete", outcome["metadata"]
    step = outcome["metadata"]["steps"][0]
    assert step["status"] == "completed"
    assert step["role_fallback"] is True
    assert step["fallback"]["kind"] == "generic"
    assert step["ran_on"] == writer.identity.node_id[:12]
    assert outcome["metadata"]["role_fallbacks"][0]["kind"] == "generic"
