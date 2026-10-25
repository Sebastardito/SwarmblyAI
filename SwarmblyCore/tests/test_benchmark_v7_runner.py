"""The V7 runner: the arms, the localisation, and the boundary it sits outside.

``tests/test_benchmark_v7.py`` covers the instances and the evaluator. This file
covers the glue, and the reason it is a separate file is the reason the runner is
a separate file: ``benchmark_v7/`` may not import the harness's planner, packer,
assembler or scorer, and the runner must drive all of them. Putting the runner
inside the package would make
``test_the_benchmark_does_not_import_the_harness_it_is_checking`` fail, and the
tempting repair is to widen the ban. That repair would delete ADR-001.

Every test here uses a **compliant worker** -- one that answers the claims it was
asked for, correctly, in the asked format. That removes "the model cannot do the
task" by construction, which is exactly what the oracle arm exists to do at a
larger scale: whatever is lost after that is lost by the harness.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from benchmark_v7.graph import build_instance

ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = ROOT / "scripts" / "run_benchmark_v7.py"


def _runner():
    """Import the runner from ``scripts/``, which is not an importable package.

    Registered in ``sys.modules`` before execution: ``@dataclass`` resolves its
    own module to look up ``KW_ONLY``, and an unregistered module makes that
    lookup return ``None``.
    """
    import sys

    spec = importlib.util.spec_from_file_location("run_benchmark_v7", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _runner()


class _CompliantWorker:
    """Answers the claims named in its packet, correctly, in the asked format.

    A stand-in for a worker that does its job, not a claim about any model. It
    answers a claim only when the packet NAMES it and the packet holds every
    fact that claim requires -- so a packet starved of a fact produces no answer
    rather than a guess, which is the behaviour that lets ``unanswerable_rate``
    mean what it says.
    """

    name = "compliant"
    family = ""
    model = ""

    def __init__(self, instance, *, answer_unasked: bool = False):
        from swarmbly_v0.backends import HashEmbedder

        self.instance = instance
        self.answer_unasked = answer_unasked
        self._embedder = HashEmbedder()
        self.prompts: list[str] = []

    def for_replica(self, family: str, model: str = "") -> "_CompliantWorker":
        clone = _CompliantWorker(self.instance, answer_unasked=self.answer_unasked)
        clone.prompts = self.prompts
        clone.family, clone.model = family, model
        return clone

    def generate(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        claims = {c.claim_id: c for c in self.instance.claims}
        named = [c for c in re.findall(r"[\[(]\s*(c[_\w]+)\s*[\])]", prompt)
                 if c in claims]
        if not named and self.answer_unasked:
            named = list(claims)
        held = {fact_id for fact_id, fact in self.instance.facts.items()
                if fact.as_line() in prompt}
        lines = [f"[{cid}] {claims[cid].answer:g}"
                 for cid in dict.fromkeys(named)
                 if set(claims[cid].requires).issubset(held)]
        return "\n".join(lines)

    def embed(self, texts):
        return self._embedder.embed(texts)


def _run(instance, arms, *, answer_unasked: bool = True, rho: float = 3.0,
         n_tasks: int = 4):
    worker = _CompliantWorker(instance, answer_unasked=answer_unasked)
    return runner.run_instance(instance, worker, worker, rho=rho,
                               n_tasks=n_tasks, tau_sem=0.5, arms=arms)


# --------------------------------------------------------------------------- #
# the arms
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("task_class", ["map", "reduce", "chain", "compose"])
def test_a_compliant_worker_scores_perfectly_in_the_monolithic_arm(task_class) -> None:
    """The ceiling arm must be reachable, or nothing below it is interpretable.

    The monolithic packet holds every fact, so a worker that answers what it is
    asked, correctly, must score 1.000 with full coverage and nothing
    unanswerable. If this ever fails the fault is in the runner or the
    evaluator, not in an arm comparison -- and every arm comparison downstream
    of it is void.
    """
    instance = build_instance(task_class, seed=3)
    report = _run(instance, ["monolithic"])["monolithic"]
    assert report.accuracy == 1.0, [v.failure for v in report.verdicts]
    assert report.coverage == 1.0
    assert report.unanswerable_rate == 0.0


@pytest.mark.parametrize("task_class", ["map", "reduce", "chain", "compose"])
def test_the_oracle_arm_answers_everything_it_was_given_the_facts_for(task_class) -> None:
    """The oracle is the upper bound on any partition, so it must not lose a claim.

    By construction every oracle packet holds exactly the facts its claim
    requires, so a compliant worker answers all of them. An oracle arm below
    1.000 here means the partition itself is impossible for that task class, and
    that has to be a fact about the class rather than an artefact of the runner.
    """
    instance = build_instance(task_class, seed=5)
    report = _run(instance, ["oracle"])["oracle"]
    assert report.accuracy == 1.0, [v.failure for v in report.verdicts]
    assert report.unanswerable_rate == 0.0, (
        "an oracle packet is defined as holding what its claim requires; a "
        "non-zero rate here is a bug in _oracle_partition")


def test_a_reduce_oracle_packet_holds_the_whole_material_and_that_is_the_finding() -> None:
    """A reduce is not partitionable, and the oracle says so before any model runs.

    Every ``reduce`` claim requires every fact, so the packet that could answer
    it is the whole document: the oracle arm collapses onto monolithic. That is
    not a defect in the arm -- it is the cheapest possible measurement of a task
    class this architecture cannot fragment, available without dispatching
    anything.
    """
    instance = build_instance("reduce", seed=7)
    facts_available, claim_owner = runner._oracle_partition(instance)
    everything = set(instance.facts)
    assert len(facts_available) == len(instance.claims)
    for packet in facts_available.values():
        assert packet == everything, (
            "a reduce claim needs every fact; if an oracle packet holds fewer "
            "then Claim.requires is understating what the claim needs")
    assert set(claim_owner) == {c.claim_id for c in instance.claims}


def test_a_map_oracle_packet_holds_only_its_own_section() -> None:
    """CONTROL for the test above: the oracle must actually partition when it can.

    If ``map`` also handed every packet the whole document, the oracle arm would
    be monolithic under another name for every class and could never localise
    anything. This is the test that says the collapse on ``reduce`` is a property
    of the task and not of the runner.
    """
    instance = build_instance("map", seed=7)
    facts_available, _ = runner._oracle_partition(instance)
    everything = set(instance.facts)
    sizes = {len(v) for v in facts_available.values()}
    assert all(v < everything for v in facts_available.values()), (
        "a map claim needs one section; an oracle packet holding everything "
        "makes the oracle arm indistinguishable from monolithic")
    assert sizes and max(sizes) <= len(everything) // 2


# --------------------------------------------------------------------------- #
# the packet view: what was DISPATCHED, not what was planned
# --------------------------------------------------------------------------- #


def test_the_packet_view_reads_the_facts_a_packet_actually_contains() -> None:
    """``facts_available`` must describe the dispatched text.

    The defect of 4 September was a gap between what the planner intended and
    what the packets carried -- 42 of 60 held another packet's answer lines. A
    runner that reconstructed ``facts_available`` from the plan would have
    reproduced that gap instead of measuring it, and V7 would have agreed with
    the harness about a protocol neither of them was running.
    """
    instance = build_instance("map", seed=11)
    first = next(iter(instance.sections))
    other = instance.sections[1]
    packet = (f"[TASK t0]\nAnswer only the items listed here:\n"
              f"  [c_{first.section_id}] the total\n\nMaterial:\n"
              + "\n".join(f"  {f.as_line()}" for f in first.facts))

    facts_available, claim_owner = runner._packet_view(instance, [packet])
    assert facts_available["t0"] == {f.fact_id for f in first.facts}
    assert not (facts_available["t0"] & {f.fact_id for f in other.facts})
    assert claim_owner[f"c_{first.section_id}"] == "t0"


def test_a_claim_no_packet_was_asked_for_is_not_blamed_on_the_packer() -> None:
    """Nobody asked is a planner failure, and it must not read as a packing one.

    ``evaluate`` falls back to every fact for a claim with no owner, so the
    verdict comes out ``not_stated`` rather than ``unanswerable``. The two are
    different repairs -- one changes the plan, the other changes the packer --
    and conflating them is how a project spends a week in the wrong module.
    """
    from benchmark_v7.evaluate import evaluate

    instance = build_instance("map", seed=11)
    first = instance.sections[0]
    packet = (f"[TASK t0]\n  [c_{first.section_id}] the total\n\n"
              + "\n".join(f"  {f.as_line()}" for f in first.facts))
    facts_available, claim_owner = runner._packet_view(instance, [packet])

    report = evaluate(instance, "", "real",
                      facts_available={k: sorted(v) for k, v in facts_available.items()},
                      claim_owner=claim_owner)
    orphans = [v for v in report.verdicts if v.claim_id not in claim_owner]
    assert orphans, "this instance must have claims no packet was asked for"
    assert all(v.failure == "not_stated" for v in orphans), (
        [(v.claim_id, v.failure) for v in orphans])


def test_a_starved_packet_reports_unanswerable_and_not_wrong() -> None:
    """The packer's failure mode, named as the packer's.

    A packet asked for a claim whose facts it was not given cannot produce that
    claim, and calling the result "wrong" charges the model for the harness's
    omission. This is the distinction the flat answer key could never make, and
    it is why ``Claim.requires`` exists.
    """
    from benchmark_v7.evaluate import evaluate

    instance = build_instance("reduce", seed=13)
    one_section = instance.sections[0]
    packet = ("[TASK t0]\n  [c_grand] the total across every group\n\n"
              + "\n".join(f"  {f.as_line()}" for f in one_section.facts))
    facts_available, claim_owner = runner._packet_view(instance, [packet])

    report = evaluate(instance, "[c_grand] 1", "real",
                      facts_available={k: sorted(v) for k, v in facts_available.items()},
                      claim_owner=claim_owner)
    grand = next(v for v in report.verdicts if v.claim_id == "c_grand")
    assert grand.answerable is False and grand.failure == "unanswerable"
    assert grand.missing_facts, "the missing facts must be named, not just counted"
    assert grand.owed_by, "and attributed to the sections that owed them"


# --------------------------------------------------------------------------- #
# the reading: the runner states the diagnosis rather than leaving it to a reader
# --------------------------------------------------------------------------- #


def test_the_reading_blames_the_model_before_it_blames_the_harness() -> None:
    """A low monolithic arm makes both fragmented figures uninterpretable.

    Precedence matters and it must be this way round. On 24 August the corpus
    produced one correct answer in sixty-four on two-step arithmetic, and
    "fragmenting destroyed the task" was indistinguishable from "a 3B model
    cannot do it". Any reading that reaches for the harness while the ceiling is
    on the floor is reading noise.
    """
    assert "cannot do this task" in runner._reading(0.2, 0.9, 0.9)
    assert "PARTITION is not viable" in runner._reading(0.95, 0.3, 0.3)
    assert "planning, packing or assembly" in runner._reading(0.95, 0.90, 0.40)
    assert "not losing more than noise" in runner._reading(0.95, 0.90, 0.89)
    assert "no localisation" in runner._reading(None, 0.9, 0.9)


def test_the_summary_reports_a_denominator_beside_every_rate() -> None:
    """A rate without its denominator is the shape of the 45 % attrition error.

    ``units_with_no_label: 323/719`` was read as an attrition rate and published
    as "three quarters of the dispatched work does not reach the calibration".
    It was a count of LINES. Every rate in this summary carries the count it was
    computed over, in the same object.
    """
    reports = []
    for task_class in ("map", "reduce"):
        instance = build_instance(task_class, seed=2)
        reports.extend(_run(instance, ["monolithic", "oracle"]).values())

    summary = runner.summarise(reports)
    for arm, block in summary["by_arm"].items():
        assert block["n_instances"] > 0 and block["n_claims"] > 0, arm
        assert set(block) >= {"accuracy", "coverage", "unanswerable_rate",
                              "n_instances", "n_claims"}
    assert "ci95" not in json_keys(summary), (
        "no interval until there are enough instances per class to resample; "
        "this project has published one bootstrap on eight clusters already")


def json_keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        out |= set(obj)
        for value in obj.values():
            json_keys(value, out)
    elif isinstance(obj, list):
        for value in obj:
            json_keys(value, out)
    return out


# --------------------------------------------------------------------------- #
# the boundary, and the defect of 4 September checked on this corpus too
# --------------------------------------------------------------------------- #


def test_the_runner_is_outside_the_package_and_stays_there() -> None:
    """The package must hold no runner, because a runner cannot obey the ban.

    ``benchmark_v7/`` may not import the harness's planner, packer, assembler or
    scorer; a runner must drive all of them. So the runner lives in ``scripts/``.
    If someone moves it in, the import test fails and the tempting repair is to
    widen the ban -- which deletes ADR-001. This test makes the intended shape
    explicit so the repair is obviously wrong.
    """
    package = ROOT / "benchmark_v7"
    assert RUNNER_PATH.exists(), "the runner must exist somewhere"
    assert not (package / "run.py").exists(), (
        "a runner inside benchmark_v7 cannot import the protocol it is meant to "
        "drive without breaking the ADR-001 boundary; it belongs in scripts/")
    text = RUNNER_PATH.read_text(encoding="utf-8")
    assert "swarmbly_v0.experiment" in text, (
        "the runner must drive the SHIPPED protocol -- a runner that "
        "reimplemented planning or packing would measure a protocol that is not "
        "the one in this repository")
    assert "benchmark_v7.evaluate" in text, (
        "and it must score through the independent evaluator, or the boundary "
        "buys nothing")


@pytest.mark.parametrize("task_class", ["map", "reduce", "compose"])
def test_no_parallel_v7_class_is_planned_as_a_dependency_chain(task_class) -> None:
    """The defect of 4 September, checked on V7's own instructions.

    A ``then`` in an output-format directive planned all fifteen ground-truth
    prompts as four-deep chains. V7's instructions were written before that was
    known and happen not to use the word -- happen to, which is not a property.
    ``map``, ``reduce`` and ``compose`` are bags of independent work and must
    plan as such.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend = MockBackend()
    for seed in range(4):
        instance = build_instance(task_class, seed=seed)
        text = instance.prompt()
        contract = global_contract(text, backend)
        assert build_plan(text, backend, n_tasks=4, contract=contract
                          ).sequential is False, (
            f"{instance.instance_id} is parallel work and was planned as a chain")


def test_the_v7_chain_class_is_still_planned_as_a_chain() -> None:
    """CONTROL: the fix must not have flattened the one class that IS sequential.

    ``chain`` states its dependency in the WORK -- each step adds a value to the
    running total from the step before it -- not in a format directive. If this
    ever passes vacuously, V7 has lost the only arm that measures state
    transport.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.planner import global_contract, plan as build_plan

    backend = MockBackend()
    sequential = 0
    for seed in range(4):
        text = build_instance("chain", seed=seed).prompt()
        contract = global_contract(text, backend)
        sequential += int(build_plan(text, backend, n_tasks=4,
                                     contract=contract).sequential)
    assert sequential >= 1, (
        "no chain instance plans as a chain; the class that exists to measure "
        "state transport is not exercising it")


# --------------------------------------------------------------------------- #
# what the oracle arm found on the first instance it was pointed at
#
# `map` is the most trivially partitionable task class there is: four
# independent per-section totals, no cross-section dependency anywhere. At
# rho 3.0, N=4 -- well above the packing floor of 1.62 -- the shipped planner
# dispatched:
#
#   t0  all four QUESTIONS and none of the data
#   t1  the format directive and section 1's rows
#   t2  sections 2 and 3's rows, and no question
#   t3  the tail of section 3, section 4's rows, and no question
#
# oracle scored 1.000 on the same instances with the same worker. The reading
# `oracle fine, real broken` is the one the arm was built to produce, and it
# arrived immediately.
#
# These tests PIN the behaviour rather than assert it is correct. Nothing here
# is misbehaving relative to its own docstring: `_segment` says "sentences are
# packed into n_tasks roughly equal-token groups" and that is exactly what
# happened. What is wrong is the claim the architecture makes on top of it, and
# a test cannot fix that. See docs/FINDING_2026-09-04_segmenter_splits_question_from_data.md.
# --------------------------------------------------------------------------- #


def test_the_segmenter_keeps_a_question_with_the_data_that_answers_it() -> None:
    """The repair, on the shape that produced the defect.

    BEFORE (4 September, pinned here as the record): ``_segment`` partitioned
    the prompt by position and token count, and on a ``map`` instance produced
    ``t0`` holding all four questions and no data, ``t1`` the format directive
    and section 1, ``t2`` sections 2 and 3 with no question, ``t3`` the tail of
    section 3 and section 4 with no question. Every claim was owned by a packet
    holding zero facts, and ``s3`` was split across two packets so even a packet
    that HAD been asked for ``c_s3`` could not have answered it.

    AFTER: one question per segment with exactly the section it names. The link
    is a token that appears in exactly ONE material unit -- here the numeral in
    "Depot group 1" -- so it is mechanical, needs no model, and cannot drift.
    """
    import re as _re
    from swarmbly_v0.planner import _segment, split_enumerated

    instance = build_instance("map", seed=0)
    text = instance.prompt()
    assert split_enumerated(text) is None, (
        "the enumerated path would split on the item list; this test is about "
        "the reference path that replaced the token-balanced fallback")

    segments = _segment(text, 4)
    claims = [_re.findall(r"\[(c_\w+)\]", s) for s in segments]
    sections = [_re.findall(r"\[(s\d+)\]", s) for s in segments]
    assert all(len(c) == 1 for c in claims), (
        f"every segment must carry exactly one question: {claims}")
    assert all(len(s) == 1 for s in sections), (
        f"and exactly the one section it names: {sections}")
    for asked, held in zip(claims, sections):
        assert asked[0] == f"c_{held[0]}", (
            f"{asked[0]} was packed with {held[0]}; the question and its data "
            f"are in the same packet but they are not the same item")


def test_the_real_arm_now_answers_what_the_oracle_arm_can() -> None:
    """The localisation, closed, with the model removed by construction.

    BEFORE: monolithic 1.000, oracle 1.000, real **0.000 coverage and 1.000
    unanswerable** -- the reading the oracle arm exists to produce, arriving on
    the first instance it was pointed at.

    AFTER: all three at 1.000 on this class, and the assertion is that ``real``
    reaches ``oracle``, not that it reaches any particular number. ``rho`` 3.0
    at N=4 against a floor of 1.62, asserted below, so the result cannot be
    re-explained as the below-floor condition that invalidated three v3c tiers.
    """
    from swarmbly_v0.experiment import _answer_budget
    from swarmbly_v0.packing import packing_floor
    from swarmbly_v0.planner import global_contract, plan as build_plan

    instance = build_instance("map", seed=0)
    spec = runner._spec_for(instance)
    worker = _CompliantWorker(instance)
    contract = global_contract(spec.text, worker,
                               target_length_tokens=_answer_budget(spec, 420))
    floor = packing_floor(contract, build_plan(spec.text, worker, n_tasks=4,
                                               contract=contract))
    assert floor < 3.0, (
        f"floor {floor:.3f} at N=4 is above the rho this test runs at; the "
        f"packets would collapse to bare tasks and the result would be about "
        f"the floor, not about the packer")

    produced = _run(instance, ["monolithic", "oracle", "real"],
                    answer_unasked=False)
    assert "real" in produced, (
        "the planner refused a map instance; map is the class the repair is "
        "for, so a refusal here means the reference link stopped being found")
    assert produced["monolithic"].accuracy == 1.0
    assert produced["oracle"].accuracy == 1.0
    assert produced["real"].unanswerable_rate == 0.0, (
        f"unanswerable {produced['real'].unanswerable_rate}: a packet was asked "
        f"for a claim whose facts it did not hold")
    assert produced["real"].accuracy == produced["oracle"].accuracy, (
        f"real {produced['real'].accuracy} against oracle "
        f"{produced['oracle'].accuracy}: the partition is viable and the "
        f"implementation is losing against it")


def test_a_refused_plan_is_reported_under_its_own_name_and_never_as_success() -> None:
    """Three of V7's four classes are refused, and that must not read as 1.000.

    A refused plan returns a single task holding the whole prompt, so the
    "fragmented" arm scores whatever the monolithic arm scores -- 1.000 with a
    compliant worker. Reported as ``real`` it would be the most flattering wrong
    number in the project: *the implementation is fine*, on prompts that were
    never fragmented.

    Two guards, and both are needed. The harness drops such a row at
    ``is_reachable``, beside a below-floor row. The runner files it under
    ``real-refused``, because a mean over one label that mixed fragmented and
    unfragmented cells is the shape of every pooling defect this project has
    corrected -- rho pooled over N, N pooled over k, a rate without its
    denominator.
    """
    for task_class in ("reduce", "chain", "compose"):
        instance = build_instance(task_class, seed=0)
        produced = _run(instance, ["real"], answer_unasked=False)
        assert runner.REFUSED_ARM in produced, (
            f"{task_class} is refused by the planner but the runner filed it "
            f"as a fragmented measurement")
        assert "real" not in produced

    reading = runner._reading(1.0, 1.0, 1.0, refused=3, fragmented=0)
    assert "measures nothing about fragmentation" in reading, reading
    partial = runner._reading(1.0, 1.0, 1.0, refused=3, fragmented=1)
    assert "3 were refused" in partial and "not in that comparison" in partial


def test_a_refused_row_is_dropped_from_every_figure() -> None:
    """The chokepoint, extended rather than duplicated.

    ``is_reachable`` already decided whether a row is a measurement of rho.
    A refused plan is the second reason a row is not a measurement, and it goes
    through the same function so that a statistic added later cannot miss it --
    which is exactly what happened to ``rho_reachable``, written to every row
    and read by one function out of eight.

    Fails OPEN on a missing column, like ``rho_reachable``: a CSV written before
    the column existed must not be silently emptied.
    """
    from swarmbly_v0.experiment import CSV_COLUMNS, is_reachable, publishable

    assert "plan_refused" in CSV_COLUMNS, (
        "a refusal that is not written cannot be re-analysed from a stored run")
    assert is_reachable({}) is True
    assert is_reachable({"plan_refused": ""}) is True
    assert is_reachable({"plan_refused": True}) is False
    assert is_reachable({"plan_refused": "true"}) is False
    rows = [{"prompt_id": "a"}, {"prompt_id": "b", "plan_refused": True},
            {"prompt_id": "c", "rho_reachable": False}]
    assert [r["prompt_id"] for r in publishable(rows)] == ["a"]


def test_a_refused_plan_does_not_raise_on_the_rho_invariant() -> None:
    """A deliberate refusal must not surface as a crash.

    One packet holding the whole prompt has rho near 1 whatever the target
    says, so the drift invariant would fire on every refused cell and an
    operator would read the traceback as a harness fault rather than as the
    planner declining a prompt it cannot partition. The row is marked and
    dropped instead: not a measurement, not an error.
    """
    from swarmbly_v0.experiment import (SweepConfig, run_fragmented,
                                        run_monolithic, _answer_budget)
    from swarmbly_v0.planner import global_contract

    instance = build_instance("chain", seed=0)
    spec = runner._spec_for(instance)
    worker = _CompliantWorker(instance, answer_unasked=True)
    config = SweepConfig(rhos=(3.0,), ns=(4,), ks=(1,), n_candidates=1, seed=0,
                         tau_sem=0.5)
    contract = global_contract(spec.text, worker,
                               target_length_tokens=_answer_budget(spec, 420))
    mono = run_monolithic(spec, worker, worker, config, contract=contract)
    row = run_fragmented(spec, worker, worker, config, rho_target=3.0,
                         n_tasks=4, tau_sem=0.5, k=1, contract=contract,
                         baseline=mono)
    assert row["plan_refused"] is True
    assert row["n_tasks"] == 1, (
        "a refused plan is a single task; if this is 4 the refusal did not "
        "happen and this test is passing for the wrong reason")


def test_the_assembled_text_is_recoverable_from_a_fragmented_row() -> None:
    """Both arms must be readable from a completed row, or no scorer can compare them.

    ``run_monolithic`` has always kept ``_text``; ``run_fragmented`` did not.
    On a composition corpus ``_trace`` carried the text, which hid the gap --
    and ``_trace`` exists only when the prompt has constraints, so on every
    answer-key and fact-graph corpus the fragmented output was unrecoverable.

    An INDEPENDENT scorer would therefore have seen one arm and not the other,
    and would have scored the fragmented arm as having produced nothing at all.
    That is the shape of asymmetry this project has withdrawn results for
    twice, in a place nobody was looking: not in the metric, in what the row
    keeps.
    """
    from swarmbly_v0.experiment import (CSV_COLUMNS, SweepConfig, run_fragmented,
                                        run_monolithic, _answer_budget)
    from swarmbly_v0.planner import global_contract

    instance = build_instance("map", seed=1)
    spec = runner._spec_for(instance)
    worker = _CompliantWorker(instance, answer_unasked=True)
    config = SweepConfig(rhos=(3.0,), ns=(4,), ks=(1,), n_candidates=1, seed=0,
                         tau_sem=0.5)
    contract = global_contract(spec.text, worker,
                               target_length_tokens=_answer_budget(spec, 420))
    mono = run_monolithic(spec, worker, worker, config, contract=contract)
    frag = run_fragmented(spec, worker, worker, config, rho_target=3.0,
                          n_tasks=4, tau_sem=0.5, k=1, contract=contract,
                          baseline=mono)

    assert mono.get("_text"), "the baseline has always carried its own text"
    assert frag.get("_text"), (
        "the fragmented row carries no assembled text, so an independent "
        "scorer cannot see what this arm produced")
    assert "_text" not in CSV_COLUMNS, (
        "it must stay out of the CSV: it is the full generated text, not a "
        "column, and write_csv drops it by omission")


def test_a_fact_graph_prompt_names_every_claim_it_asks_for() -> None:
    """Round-trip over the real corpus, which is what the hand-written test lacked.

    The instructions read "Give one line per group as [group id] followed by the
    value alone", the group ids in the material are ``s1``, ``s2``, and the claim
    ids are ``c_s1``, ``c_s2``. So a perfectly compliant answer was ``[s1] 440``,
    which ``parse_claims`` cannot read -- its pattern accepts ``c_``-prefixed
    ids and bare digits, and ``s1`` is neither. The benchmark's evaluator could
    not parse the answer the benchmark's own instruction asked for.

    It was invisible because the parser test fed it ``c_``-prefixed ids by hand.
    The property is the round trip: every claim id must appear in the prompt, and
    an ideal answer must parse back to every claim, for every class and seed.
    """
    from benchmark_v7.evaluate import parse_claims

    for task_class in ("map", "reduce", "chain", "compose"):
        for seed in range(4):
            instance = build_instance(task_class, seed=seed)
            prompt = instance.prompt()
            for claim in instance.claims:
                assert f"[{claim.claim_id}]" in prompt, (
                    f"{instance.instance_id} asks for {claim.claim_id} without "
                    f"naming it; a compliant model cannot emit an id it was "
                    f"never given")
            ideal = "\n".join(f"[{c.claim_id}] {c.answer:g}"
                              for c in instance.claims)
            parsed = parse_claims(ideal)
            assert set(parsed) == {c.claim_id for c in instance.claims}, (
                f"{instance.instance_id}: an ideal answer in the asked format "
                f"parses to {sorted(parsed)}")


def test_a_section_header_is_not_read_as_an_answer() -> None:
    """CONTROL for the test above: naming the ids must not widen the parser.

    The claim namespace stays distinct from the section namespace on purpose. A
    model that echoes ``[s1] Depot group 1`` from the material must not have
    that read as an answer to anything -- which is the strictness
    ``parse_claims`` exists for, and the repair for the id mismatch had to
    preserve it rather than relax the pattern.
    """
    from benchmark_v7.evaluate import parse_claims

    instance = build_instance("map", seed=0)
    echoed = instance.source_text()
    parsed = parse_claims(echoed)
    assert not any(key.startswith("c_") for key in parsed), (
        f"reproducing the material parsed as answers: {sorted(parsed)}")
