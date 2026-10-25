"""Plan DAG construction, topological ordering and cycle rejection."""

from __future__ import annotations

import pytest

from swarmbly_v0 import MockBackend, global_contract, plan
from swarmbly_v0.schema import Plan, Task

PARALLEL_PROMPT = (
    "Extract structured fields from each of the 40 invoice records in the export. "
    "For each record, extract the customer name, the invoice total, and the payment status. "
    "Return one bullet per record. The records are mutually independent and may be "
    "processed separately, so do not reconcile totals across records."
)

SEQUENTIAL_PROMPT = (
    "Solve the problem step by step. First compute the weekly demand from the series. "
    "Then use that result to derive the reorder point given a three week lead time. "
    "Then substitute the reorder point into the safety-stock equation and calculate the "
    "holding cost. Each step depends on the numeric output of the previous step."
)


@pytest.fixture()
def backend() -> MockBackend:
    return MockBackend(seed=0)


def test_topological_levels_respect_dependencies(backend: MockBackend) -> None:
    """Every task appears strictly after all of its dependencies."""
    p = plan(PARALLEL_PROMPT, backend, n_tasks=5)
    levels = p.topological_levels()
    level_of = {tid: i for i, level in enumerate(levels) for tid in level}

    assert set(level_of) == set(p.task_ids)
    for task in p.tasks:
        for dep in task.depends_on:
            assert level_of[dep] < level_of[task.task_id], (
                f"{task.task_id} must come after its dependency {dep}"
            )


def test_topological_order_is_a_flat_valid_order(backend: MockBackend) -> None:
    """The flat order is a genuine topological sort with no repeats or drops."""
    p = plan(PARALLEL_PROMPT, backend, n_tasks=6)
    order = p.topological_order()

    assert sorted(order) == sorted(p.task_ids)
    assert len(order) == len(set(order))
    position = {tid: i for i, tid in enumerate(order)}
    for task in p.tasks:
        for dep in task.depends_on:
            assert position[dep] < position[task.task_id]


def test_parallel_prompt_yields_fan_in_topology(backend: MockBackend) -> None:
    """Independent work sits on one level; only the integration node waits."""
    p = plan(PARALLEL_PROMPT, backend, n_tasks=4, force_sequential=False)
    levels = p.topological_levels()

    assert len(levels) == 2
    assert len(levels[0]) == 3
    assert levels[1] == ["t3"]
    assert p.by_id("t3").kind == "integration"


def test_sequential_prompt_yields_a_chain(backend: MockBackend) -> None:
    """A prompt whose step i needs step i-1 must not be given parallel levels."""
    p = plan(SEQUENTIAL_PROMPT, backend, n_tasks=4)

    assert p.sequential is True
    levels = p.topological_levels()
    assert len(levels) == 4
    assert all(len(level) == 1 for level in levels)


def test_requested_n_tasks_is_honoured_exactly(backend: MockBackend) -> None:
    """N is the sweep's independent variable, so it must be exact."""
    for n in (2, 3, 4, 8, 16):
        assert len(plan(PARALLEL_PROMPT, backend, n_tasks=n).tasks) == n


def test_segments_do_not_duplicate_prompt_material(backend: MockBackend) -> None:
    """Task texts partition the prompt; duplication would inflate the rho floor."""
    from swarmbly_v0.textutil import count_tokens

    prompt_tokens = count_tokens(PARALLEL_PROMPT)
    for n in (2, 4, 8):
        p = plan(PARALLEL_PROMPT, backend, n_tasks=n)
        task_tokens = sum(count_tokens(t.instruction) for t in p.tasks)
        # Only the integration node adds a short fixed directive.
        assert task_tokens <= prompt_tokens + 15 * n


def test_cycles_are_rejected() -> None:
    """A cyclic DAG is a bug, not a plan."""
    with pytest.raises(ValueError, match="cycle"):
        Plan(
            prompt="x",
            tasks=[
                Task(task_id="t0", instruction="a", depends_on=("t1",)),
                Task(task_id="t1", instruction="b", depends_on=("t0",)),
            ],
        )


def test_unknown_dependency_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        Plan(prompt="x", tasks=[Task(task_id="t0", instruction="a", depends_on=("t9",))])


def test_global_contract_is_deterministic(backend: MockBackend) -> None:
    first = global_contract(PARALLEL_PROMPT, backend)
    second = global_contract(PARALLEL_PROMPT, backend)
    assert first == second
    assert first.session_id
    assert first.prompt_tokens > 0
