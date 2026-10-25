"""Seam detection and select-then-splice behaviour on a broken assembly."""

from __future__ import annotations

import pytest

from swarmbly_v0 import HashEmbedder, MockBackend, select_then_splice
from swarmbly_v0.assembler import boundary_windows
from swarmbly_v0.schema import Contract, Fragment, Plan, Task

# Two fragments about the same thing, and one about something completely
# unrelated. A working seam detector must rank the junctions accordingly.
LEDGER_A = (
    "The Aurora Registry stores every ledger entry it receives. "
    "The Aurora Registry validates each ledger entry before writing it to disk. "
    "The Aurora Registry then emits a signed receipt for the ledger entry."
)
LEDGER_B = (
    "Each signed receipt from the ledger is retained for seven years. "
    "The receipt records the ledger entry identifier and the validation outcome. "
    "Auditors reconcile the receipt against the ledger entry it describes."
)
UNRELATED = (
    "Coastal fog forms when warm marine air passes over a cold upwelling current. "
    "Lighthouse keepers historically logged fog density every four hours. "
    "The foghorn was sounded whenever visibility dropped below one nautical mile."
)

CONTRACT = Contract(
    objective="Describe the ledger receipt lifecycle.",
    audience="an auditor",
    register="formal",
    output_format="report",
    target_length_tokens=200,
    forbidden_terms=("obviously",),
    canonical_entities=("Aurora Registry", "ledger entry"),
    session_id="test0001",
    prompt_tokens=60,
)


def _plan(task_ids: list[str]) -> Plan:
    return Plan(
        prompt="test",
        tasks=[Task(task_id=tid, instruction=f"part {tid}") for tid in task_ids],
    )


@pytest.fixture()
def backend() -> MockBackend:
    return MockBackend(seed=7)


@pytest.fixture()
def embedder() -> HashEmbedder:
    return HashEmbedder()


def test_broken_seam_scores_lower_than_a_coherent_one(embedder: HashEmbedder) -> None:
    """A topic break must be measurably less similar than a genuine continuation."""
    good_left, good_right = boundary_windows(LEDGER_A, LEDGER_B)
    bad_left, bad_right = boundary_windows(LEDGER_A, UNRELATED)

    vectors = embedder.embed([good_left, good_right, bad_left, bad_right])
    good_sim = float(vectors[0] @ vectors[1])
    bad_sim = float(vectors[2] @ vectors[3])

    assert bad_sim < good_sim, f"broken seam {bad_sim:.3f} should score below {good_sim:.3f}"


def test_synthesis_fires_only_on_the_broken_seam(
    backend: MockBackend, embedder: HashEmbedder
) -> None:
    """With tau between the two similarities, exactly one bridge is generated."""
    fragments = [
        Fragment(task_id="t0", candidates=[LEDGER_A], order=0),
        Fragment(task_id="t1", candidates=[LEDGER_B], order=1),
        Fragment(task_id="t2", candidates=[UNRELATED], order=2),
    ]
    plan = _plan(["t0", "t1", "t2"])

    probe = select_then_splice(fragments, CONTRACT, backend, 0.0, plan, embedder)
    sims = {(s.left_task, s.right_task): s.similarity for s in probe.seams}
    good = sims[("t0", "t1")]
    bad = sims[("t1", "t2")]
    assert bad < good
    tau = (good + bad) / 2

    assembly = select_then_splice(fragments, CONTRACT, backend, tau, plan, embedder)

    assert len(assembly.seams) == 2
    bridged = {(s.left_task, s.right_task): s.bridged for s in assembly.seams}
    assert bridged[("t1", "t2")] is True, "the broken seam must be bridged"
    assert bridged[("t0", "t1")] is False, "the coherent seam must be spliced, not rewritten"
    assert assembly.n_bridges == 1


def test_tau_zero_never_bridges_and_tau_one_always_does(
    backend: MockBackend, embedder: HashEmbedder
) -> None:
    """Synthesis is the exception; the threshold is what makes it so."""
    fragments = [
        Fragment(task_id="t0", candidates=[LEDGER_A], order=0),
        Fragment(task_id="t1", candidates=[UNRELATED], order=1),
    ]
    plan = _plan(["t0", "t1"])

    assert select_then_splice(fragments, CONTRACT, backend, 0.0, plan, embedder).n_bridges == 0
    assert select_then_splice(fragments, CONTRACT, backend, 0.99, plan, embedder).n_bridges == 1


def test_assembly_preserves_every_fragment(
    backend: MockBackend, embedder: HashEmbedder
) -> None:
    """Losing a fragment would corrupt the experiment silently."""
    fragments = [
        Fragment(task_id="t0", candidates=[LEDGER_A], order=0),
        Fragment(task_id="t1", candidates=[LEDGER_B], order=1),
        Fragment(task_id="t2", candidates=[UNRELATED], order=2),
    ]
    assembly = select_then_splice(
        fragments, CONTRACT, backend, 0.9, _plan(["t0", "t1", "t2"]), embedder
    )
    for text in (LEDGER_A, LEDGER_B, UNRELATED):
        assert text.split(".")[0] in assembly.text


def test_fragments_are_ordered_by_the_plan(
    backend: MockBackend, embedder: HashEmbedder
) -> None:
    """Assembly order comes from the DAG, not from the input list order."""
    fragments = [
        Fragment(task_id="t2", candidates=[UNRELATED], order=2),
        Fragment(task_id="t0", candidates=[LEDGER_A], order=0),
        Fragment(task_id="t1", candidates=[LEDGER_B], order=1),
    ]
    plan = Plan(
        prompt="test",
        tasks=[
            Task(task_id="t0", instruction="a"),
            Task(task_id="t1", instruction="b", depends_on=("t0",)),
            Task(task_id="t2", instruction="c", depends_on=("t1",)),
        ],
    )
    assembly = select_then_splice(fragments, CONTRACT, backend, 0.0, plan, embedder)

    assert assembly.order == ["t0", "t1", "t2"]
    assert assembly.text.index(LEDGER_A[:30]) < assembly.text.index(UNRELATED[:30])


def test_judge_selects_the_contract_compliant_candidate(
    backend: MockBackend, embedder: HashEmbedder
) -> None:
    """Selection is the cheap, lossless half of select-then-splice."""
    compliant = LEDGER_A
    non_compliant = (
        "Yeah so obviously the whole thing was kind of a mess and we didn't bother. "
        "You'll probably just want to skip it honestly!"
    )
    fragments = [Fragment(task_id="t0", candidates=[non_compliant, compliant], order=0)]

    assembly = select_then_splice(fragments, CONTRACT, backend, 0.5, _plan(["t0"]), embedder)

    assert assembly.selected["t0"] == compliant
    assert assembly.judge_scores["t0"] > 0.0


def test_sentence_offsets_point_at_fragment_starts(
    backend: MockBackend, embedder: HashEmbedder
) -> None:
    """Offsets are what let the taxonomy attribute seam-local errors exactly."""
    fragments = [
        Fragment(task_id="t0", candidates=[LEDGER_A], order=0),
        Fragment(task_id="t1", candidates=[LEDGER_B], order=1),
    ]
    assembly = select_then_splice(
        fragments, CONTRACT, backend, 0.0, _plan(["t0", "t1"]), embedder
    )

    from swarmbly_v0.textutil import split_sentences

    sentences = split_sentences(assembly.text)
    assert assembly.fragment_sentence_offsets[0] == 0
    assert assembly.fragment_sentence_offsets[1] == 3
    assert sentences[3].startswith("Each signed receipt")
