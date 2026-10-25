"""rho targeting accuracy -- the independent variable must actually be controlled."""

from __future__ import annotations

import pytest

from swarmbly_v0 import MockBackend, build_packet, build_packets, global_contract, plan
from swarmbly_v0.packing import build_monolithic_prompt, measure_rho, packing_floor
from swarmbly_v0.textutil import count_tokens

PROMPT = (
    "Write a technical report of about 1800 words for a policy audience on the "
    "grid-integration cost of distributed solar generation. Organise the report into 6 "
    "sections: current deployment levels by region, interconnection queue dynamics, "
    "distribution-network upgrade costs and who bears them, tariff design responses, "
    "storage complementarity and its effect on peak coincidence, and the open questions "
    "that the evidence base cannot yet settle. Each section should stand on its own with "
    "its own evidence, and the sections may be drafted separately by different authors. "
    "Use a formal register throughout and keep terminology consistent across sections."
)


@pytest.fixture()
def backend() -> MockBackend:
    return MockBackend(seed=0)


@pytest.mark.parametrize("n_tasks", [2, 4, 8])
@pytest.mark.parametrize("rho_target", [1.25, 1.5, 2.0, 3.0])
def test_rho_targeting_is_accurate_above_the_floor(
    backend: MockBackend, n_tasks: int, rho_target: float
) -> None:
    """Achieved rho lands within 5% of the target whenever the target is reachable."""
    contract = global_contract(PROMPT, backend)
    p = plan(PROMPT, backend, n_tasks=n_tasks, contract=contract)
    floor = packing_floor(contract, p)
    if rho_target < floor:
        pytest.skip(f"rho={rho_target} is below the reachable floor {floor:.2f}")

    result = build_packets(contract, p, rho_target)

    assert result.reachable is True
    assert result.rho_achieved == pytest.approx(rho_target, rel=0.05), (
        f"target {rho_target}, achieved {result.rho_achieved:.3f}"
    )
    assert measure_rho(result.packets, PROMPT) == pytest.approx(result.rho_achieved)


@pytest.mark.parametrize("n_tasks", [2, 4, 8])
def test_below_floor_targets_collapse_to_the_floor_and_are_flagged(
    backend: MockBackend, n_tasks: int
) -> None:
    """An unreachable target must be reported, never silently mislabelled."""
    contract = global_contract(PROMPT, backend)
    p = plan(PROMPT, backend, n_tasks=n_tasks, contract=contract)
    floor = packing_floor(contract, p)

    result = build_packets(contract, p, 0.5)

    assert result.reachable is False
    assert result.rho_achieved == pytest.approx(floor, rel=0.02)
    assert floor >= 1.0  # dispatching N packets can never cost less than the prompt


def test_rho_is_monotone_in_the_target(backend: MockBackend) -> None:
    """More budget must buy more context, never less."""
    contract = global_contract(PROMPT, backend)
    p = plan(PROMPT, backend, n_tasks=4, contract=contract)
    achieved = [build_packets(contract, p, t).rho_achieved for t in (1.25, 1.5, 2.0, 2.5)]
    assert achieved == sorted(achieved)


def test_every_packet_always_contains_its_own_task(backend: MockBackend) -> None:
    """The task block is mandatory and must survive any budget, however small."""
    contract = global_contract(PROMPT, backend)
    p = plan(PROMPT, backend, n_tasks=4, contract=contract)

    result = build_packets(contract, p, 0.1)
    for packet, task in zip(result.packets, p.tasks):
        assert f"[TASK {task.task_id}]" in packet.text
        assert task.instruction.strip()[:40] in packet.text
        assert packet.task_tokens > 0


def test_context_grows_with_the_budget(backend: MockBackend) -> None:
    """Context tokens -- not task tokens -- are what the budget actually buys."""
    contract = global_contract(PROMPT, backend)
    p = plan(PROMPT, backend, n_tasks=4, contract=contract)
    task = p.tasks[0]

    small = build_packet(contract, task, {}, 0.05)
    large = build_packet(contract, task, {}, 0.6)

    # The contract header is mandatory, not rationed context, so the smallest
    # packet still carries it. This assertion used to read `== 0`, which encoded
    # the assumption that a packet could be squeezed below its own contract --
    # and a fragment scored against a contract it never received measures the
    # contract's absence rather than the cost of fragmenting. What the budget
    # buys is everything *above* the header.
    assert small.blocks_included == ("contract_header",)
    assert large.context_tokens > small.context_tokens
    assert large.task_tokens == small.task_tokens


def test_predecessor_summaries_only_reach_actual_dependents(backend: MockBackend) -> None:
    """The DAG is what decides who pays for whose summary.

    Also pins down the trade-off the sweep exists to expose: predecessor
    context is not free, so there is a rho below which it simply does not fit
    in the packet, and above which it does.
    """
    contract = global_contract(PROMPT, backend)
    p = plan(PROMPT, backend, n_tasks=4, contract=contract)
    summaries = {"t0": "SENTINEL summary of the first part.",
                 "t1": "second part summary.", "t2": "third part summary."}

    independent = [t for t in p.tasks if not t.depends_on]
    dependent = [t for t in p.tasks if t.depends_on]
    assert independent and dependent

    carries: list[float] = []
    for rho in (1.25, 1.5, 2.0, 2.5, 3.0, 4.0):
        result = build_packets(contract, p, rho, summaries)
        by_id = {packet.task_id: packet for packet in result.packets}
        # A summary must never reach a task that does not depend on it.
        for task in independent:
            assert "SENTINEL" not in by_id[task.task_id].text
        if any("SENTINEL" in by_id[t.task_id].text for t in dependent):
            carries.append(rho)

    assert carries, "predecessor summaries must fit at some rho in the swept range"
    # Once affordable, more budget never takes the summary away again.
    assert carries == [rho for rho in (1.25, 1.5, 2.0, 2.5, 3.0, 4.0) if rho >= carries[0]]


def test_monolithic_prompt_has_no_task_marker(backend: MockBackend) -> None:
    """The baseline must be distinguishable from a packet."""
    contract = global_contract(PROMPT, backend)
    mono = build_monolithic_prompt(contract, PROMPT)

    assert "[TASK" not in mono
    assert PROMPT in mono
    assert count_tokens(mono) > count_tokens(PROMPT)
