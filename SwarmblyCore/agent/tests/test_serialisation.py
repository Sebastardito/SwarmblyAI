"""A run must survive a JSON round-trip and resume from the record alone."""

from __future__ import annotations

import json

import pytest

from helpers import (
    TOOLS,
    FakeClock,
    RecordingExecutor,
    ScriptedGenerate,
    allow,
    needs_approval,
)
from swarmbly_agent import (
    AgentRuntime,
    Budget,
    Final,
    Observation,
    RunState,
    Step,
    ToolDescriptor,
    ToolRequest,
    action_from_dict,
    action_to_dict,
)


def test_tool_descriptor_round_trip() -> None:
    tool = TOOLS[0]
    assert ToolDescriptor.from_dict(tool.to_dict()) == tool


@pytest.mark.parametrize(
    "action",
    [
        Final("answer"),
        Final("answer", parse_note="why"),
        ToolRequest("echo", {"text": "hi"}, "because"),
    ],
)
def test_action_round_trip(action) -> None:
    assert action_from_dict(json.loads(json.dumps(action_to_dict(action)))) == action


def test_observation_round_trip() -> None:
    observation = Observation(
        tool="echo",
        ok=False,
        content="denied",
        source="policy",
        sha256="0" * 64,
        truncated=True,
    )
    assert Observation.from_dict(observation.to_dict()) == observation


def test_budget_round_trip() -> None:
    budget = Budget(
        max_steps=3,
        max_tool_calls=2,
        max_seconds=1.5,
        max_observation_chars=10,
    )
    assert Budget.from_dict(budget.to_dict()) == budget


def test_a_done_run_round_trips_through_json() -> None:
    generate = ScriptedGenerate([ToolRequest("echo", {"text": "hi"}), Final("done")])
    executor = RecordingExecutor(Observation(tool="echo", ok=True, content="hi"))
    runtime = AgentRuntime(generate, executor, allow)
    finished = runtime.run("a task", TOOLS)

    encoded = json.dumps(finished.to_dict(), sort_keys=True)
    restored = RunState.from_dict(json.loads(encoded))

    assert restored.to_dict() == finished.to_dict()
    assert restored.status == "done"
    assert restored.steps[0].action == ToolRequest("echo", {"text": "hi"})
    assert restored.steps[0].observation is not None
    assert restored.steps[1].action == Final("done")


def test_an_awaiting_run_round_trips_and_resumes() -> None:
    request = ToolRequest("echo", {"text": "hi"}, "needs a yes")
    generate = ScriptedGenerate([request])
    executor = RecordingExecutor(Observation(tool="echo", ok=True, content="hi"))
    runtime = AgentRuntime(generate, executor, needs_approval("remote"))

    paused = runtime.run("a task", TOOLS)
    restored = RunState.from_dict(json.loads(json.dumps(paused.to_dict())))

    assert restored.to_dict() == paused.to_dict()
    assert restored.status == "awaiting_approval"
    assert restored.pending == request
    assert restored.pending_reason == "remote"
    assert restored.steps[0].observation is None

    generate.actions.append(Final("done"))
    finished = runtime.resume(restored, approved=True, token="tok")

    assert finished.status == "done"
    assert executor.tokens == ["tok"]
    # Rebuilt from the record: system, user, assistant request, tool result.
    assert [message["role"] for message in generate.calls[1][0]] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]


def test_step_round_trip() -> None:
    step = Step(
        index=0,
        action=ToolRequest("echo", {"x": 1}),
        observation=Observation(tool="echo", ok=True, content="1"),
        started=1.0,
        ended=2.0,
    )
    assert Step.from_dict(step.to_dict()) == step


def test_from_dict_rejects_an_unknown_status() -> None:
    data = RunState(status="done").to_dict()
    data["status"] = "paused"
    with pytest.raises(ValueError, match="unknown status"):
        RunState.from_dict(data)


def test_from_dict_rejects_a_final_answer_as_pending() -> None:
    data = RunState(status="awaiting_approval").to_dict()
    data["pending"] = {"type": "final", "text": "not a request", "parse_note": None}
    with pytest.raises(ValueError, match="pending"):
        RunState.from_dict(data)


def test_from_dict_rejects_a_corrupt_step() -> None:
    state = RunState(status="done", steps=[Step(index=0, action=Final("x"))])
    data = state.to_dict()
    data["steps"][0]["index"] = "zero"
    with pytest.raises(ValueError, match="index"):
        RunState.from_dict(data)


def test_state_has_no_hidden_runtime_reference() -> None:
    state = RunState(status="done", task="task", tools=list(TOOLS))
    payload = json.dumps(state.to_dict())
    assert "AgentRuntime" not in payload
    assert "generate" not in payload
    assert "policy" not in payload


def test_elapsed_seconds_round_trip() -> None:
    clock = FakeClock()
    generate = ScriptedGenerate([Final("done")], clock=clock, advance=0.4)
    runtime = AgentRuntime(generate, RecordingExecutor(), allow, clock=clock)
    state = runtime.run("task", TOOLS)
    restored = RunState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.elapsed_seconds == pytest.approx(0.4)
