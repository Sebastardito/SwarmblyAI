"""Test 0: does the instrument detect the faults it exists to detect?

Why this file is the first thing that runs
------------------------------------------

Nine defects were found in the harness by adversarial review on 26 August, five
of which would have made an eight-hour run meaningless. Not one was caught by the
485 tests then in the suite, because every one of those tests asked *does the code
do what it says*. None asked *would this measurement notice if the mechanism it
measures were removed*.

That is a different question and it is the one that matters. A packing defect
that silently drops the predecessor block reads, downstream, as "an ordered task
is expensive to fragment" -- a finding, stated in the right units, with the right
sign, and wrong. The only defence is to break the mechanism on purpose and check
that the metric screams.

So each test below injects one known fault and asserts two things:

* the metric that owns that fault **moves**, in the right direction; and
* on the clean input the same metric is **quiet**, because a detector that fires
  on everything detects nothing.

Everything here runs against deterministic scripted backends. No LLM, no network,
seconds not hours. That is deliberate: an instrument check that is expensive to
run is an instrument check that gets skipped.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from swarmbly_v0.constraints import check_numeric_fidelity, grade_text
from swarmbly_v0.experiment import PromptSpec, SweepConfig, run_fragmented, task_item_scope
from swarmbly_v0.planner import global_contract, plan as build_plan


# --------------------------------------------------------------------------- #
# fault 1: strip the contract from a fragment
# --------------------------------------------------------------------------- #

CONSTRAINTS = [
    {"id": "paragraphs", "kind": "paragraph_count", "count": 2},
    {"id": "length", "kind": "words_per_paragraph", "min": 8, "max": 60},
    {"id": "mentions_tide", "kind": "must_mention", "term": "tide window"},
    {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
]

COMPLIANT = (
    "The tide window governs when a vessel may enter and it is published each "
    "morning by the harbourmaster for the whole shift.\n\n"
    "Berths are then allocated against that window in the order the shipper "
    "filed, which keeps the crane crews from idling between lifts.")


def test_a_fragment_that_lost_its_contract_scores_lower() -> None:
    """The V6 defect, as a detector test.

    long_prose fragments were handed an answer-sheet directive instead of their
    own format block, so the paragraph, length and mention constraints reached no
    fragment while the baseline kept all of them. The constraint score is the
    metric that owns this, and it must fall when the contract is gone.
    """
    without_contract = "tide window closes early"  # what a stripped fragment returns

    clean = grade_text(COMPLIANT, CONSTRAINTS)
    stripped = grade_text(without_contract, CONSTRAINTS)

    assert clean.score == 1.0, "the detector must be quiet on a compliant answer"
    assert stripped.score is not None and stripped.score <= 0.5
    assert {"paragraphs", "length"} <= {r.constraint_id for r in stripped.failed}


# --------------------------------------------------------------------------- #
# fault 2: remove the carry from a chain
# --------------------------------------------------------------------------- #

CHAIN_KEY = {
    "01": {"expected": "480", "mode": "numeric", "level": 1},
    "02": {"expected": "428", "mode": "numeric", "level": 2},
    "03": {"expected": "107", "mode": "numeric", "level": 3},
    "04": {"expected": "257", "mode": "numeric", "level": 4},
}

CHAIN_TEXT = (
    "Work through the costing chain below, one step at a time.\n\n"
    "  [01] Multiply 60 units by the unit price of 8 to get the gross value.\n"
    "  [02] Subtract the fixed rebate of 52 from the gross value in step 1 to get the net value.\n"
    "  [03] Divide the net value from step 2 by 4 weeks to get the weekly figure.\n"
    "  [04] Add the fixed handling fee of 150 to the weekly figure from step 3.\n\n"
    "Each step uses the numeric result of the step before it. Give one line per "
    "item, as [NN] followed by the value alone.")


class _StatefulWorker:
    """A worker that can only answer a step whose input it was actually given.

    This is the crux of the whole dependency argument made executable: a node
    that is told the predecessor's value computes correctly, and a node that is
    not cannot, so it guesses. If the carry is working, the second packet answers
    correctly; if the carry has been removed, it does not. A metric that fails to
    separate those two worlds cannot measure state transport at all.
    """

    name = "stateful"
    ANSWERS = {"01": "480", "02": "428", "03": "107", "04": "257"}

    def __init__(self, blind: bool = False) -> None:
        self.blind = blind
        self.packets: list[str] = []

    def generate(self, prompt: str, **kw: object) -> str:
        self.packets.append(prompt)
        # A task item reads "[03] Divide the net value..."; a carried value reads
        # "[02]=428". Telling them apart matters: looking only for "[02]" finds
        # the carry and makes a blinded worker behave like a fed one, which would
        # make this whole test pass vacuously.
        wanted = [item for item in ("01", "02", "03", "04")
                  if re.search(rf"\[{item}\]\s+[A-Za-z]", prompt)]
        carried = bool(re.search(r"\[\d{2}\]=", prompt)) and not self.blind
        held = set(wanted)
        lines, spoiled = [], set()
        for item in wanted:
            predecessor = f"{int(item) - 1:02d}"
            # Answerable when the step consumes nothing, when its input is in the
            # same packet, or when the carry brought the input in. A dependency
            # that does not cross a packet boundary needs no carry -- modelling it
            # otherwise would make the test demand a mechanism where none is due.
            answerable = item == "01" or predecessor in held or carried
            # And an error propagates: a step fed a wrong input produces a wrong
            # output even though its own arithmetic is sound. That is the
            # epsilon-compounding the chain corpus exists to exhibit, and a
            # worker that quietly recovered from a bad input would make a broken
            # chain look repairable.
            if not answerable or predecessor in spoiled:
                spoiled.add(item)
                lines.append(f"[{item}] 9999")
            else:
                lines.append(f"[{item}] {self.ANSWERS[item]}")
        return "\n".join(lines)

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _chain_spec() -> PromptSpec:
    return PromptSpec(prompt_id="chain", category="dependency_chain",
                      expected_decomposable=True, text=CHAIN_TEXT, key=CHAIN_KEY)


def _chain_accuracy(blind: bool) -> tuple[float, list[dict]]:
    backend = _StatefulWorker(blind=blind)
    row = run_fragmented(_chain_spec(), backend, backend,
                         SweepConfig(rhos=(3.0,), ns=(2,), ks=(1,)),
                         rho_target=3.0, n_tasks=2, tau_sem=0.5, typed_carry=True)
    records = [r for r in (row.get("_truth_records") or []) if r["correct"] is not None]
    correct = sum(1 for r in records if r["correct"])
    return (correct / len(records) if records else 0.0), records


def test_removing_the_carry_drops_accuracy_from_the_next_step_onward() -> None:
    """Fault injection on the mechanism V4 lost without noticing.

    With the carry, every step is answerable. Without it, step 1 still is -- it
    consumes nothing -- and everything after it is not. If accuracy does not
    separate those two runs, the harness cannot see state transport, and any
    number it reports about the chain is about something else.
    """
    with_carry, records_with = _chain_accuracy(blind=False)
    without_carry, records_without = _chain_accuracy(blind=True)

    assert with_carry == 1.0, f"a fed chain must be fully answerable, got {with_carry}"
    assert without_carry < with_carry, "the detector did not notice a missing carry"

    # And it must localise. At N=2 the packet boundary falls between items 02 and
    # 03, so steps 1 and 2 -- whose dependency is intra-packet -- must survive,
    # and the loss must begin exactly at the first step whose input had to cross.
    by_step = {r["item_id"]: r["correct"] for r in records_without}
    assert by_step.get("01") is True and by_step.get("02") is True, (
        "a dependency inside one packet needs no carry and must be unaffected")
    assert by_step.get("03") is False, (
        "the loss must begin at the first step whose input crossed the boundary")
    assert by_step.get("04") is False, (
        "and it must propagate: a step fed a wrong input is wrong too")


def test_the_carry_actually_reaches_the_packet_and_the_check_can_see_it() -> None:
    """A detector for the defect itself, not only for its consequence.

    V4's packets carried no predecessor block at all and nothing in the output
    said so; the absence was inferred months later by tracing a packet by hand.
    """
    backend = _StatefulWorker()
    run_fragmented(_chain_spec(), backend, backend,
                   SweepConfig(rhos=(3.0,), ns=(2,), ks=(1,)),
                   rho_target=3.0, n_tasks=2, tau_sem=0.5, typed_carry=True)
    successors = [p for p in backend.packets if "PREDECESSOR" in p]
    assert successors, "no packet carried a predecessor block"
    assert any("[01]=480" in p for p in successors)


# --------------------------------------------------------------------------- #
# fault 3: insert a repeated sentence
# --------------------------------------------------------------------------- #

def test_a_repeated_sentence_is_detected_and_a_clean_one_is_not() -> None:
    """The signature failure of assembly: two workers each writing the same
    sentence, each locally fluent, invisible to a transition-based score."""
    duplicated = (
        "The tide window governs when a vessel may enter and it is published each "
        "morning by the harbourmaster for the whole shift.\n\n"
        "The tide window governs when a vessel may enter and it is published each "
        "morning by the harbourmaster for the whole shift.")

    assert grade_text(COMPLIANT, CONSTRAINTS).score == 1.0
    failed = {r.constraint_id for r in grade_text(duplicated, CONSTRAINTS).failed}
    assert "no_repeated_sentence" in failed


# --------------------------------------------------------------------------- #
# fault 4: corrupt a fact in the source material
# --------------------------------------------------------------------------- #

def test_an_altered_figure_fails_the_factual_check_and_a_faithful_one_passes() -> None:
    """Both directions matter. A fidelity check that only ever says False is not
    a check -- and this project has twice shipped one that graded correct
    citations as fabrications."""
    allowed = [845.0, 210.0, 370.0, 1425.0]

    assert check_numeric_fidelity("The heaviest consignment is 845 kg.", allowed) is True
    assert check_numeric_fidelity("The three total 1425 kg.", allowed) is True
    assert check_numeric_fidelity("The heaviest consignment is 999 kg.", allowed) is False
    # A sentence with no figure is neither right nor wrong on this measure.
    assert check_numeric_fidelity("Cargo is held until the tide turns.", allowed) is None


# --------------------------------------------------------------------------- #
# fault 5: deliver the carry to the wrong fragment
# --------------------------------------------------------------------------- #

class _OutOfScopeWorker(_StatefulWorker):
    """A worker that answers items it was never asked for.

    Exactly what the typed carry invites: handed ``[01]=480 [02]=428`` formatted
    like answer lines, a successor restates them as its own. Before the scope
    filter those restatements were graded and scored -- 8 records and 8 correct
    where the packet's key held 4 -- which inflated the carry arm's own headline.
    """

    def generate(self, prompt: str, **kw: object) -> str:
        self.packets.append(prompt)
        return "\n".join(f"[{item}] {value}" for item, value in self.ANSWERS.items())


def test_answers_outside_a_packets_scope_are_not_credited_to_it() -> None:
    backend = _OutOfScopeWorker()
    row = run_fragmented(_chain_spec(), backend, backend,
                         SweepConfig(rhos=(3.0,), ns=(2,), ks=(1,)),
                         rho_target=3.0, n_tasks=2, tau_sem=0.5, typed_carry=True)
    records = row.get("_truth_records") or []

    # Four items exist. Each must be credited exactly once, to the packet that
    # owned it -- not once per packet that happened to name it.
    per_task: dict[str, set[str]] = {}
    for record in records:
        per_task.setdefault(str(record["task_id"]), set()).add(str(record["item_id"]))
    assert len(records) == 4, (
        f"every packet answered all four items; {len(records)} records means the "
        "scope filter is not confining the grader")
    for task_id, items in per_task.items():
        assert items, task_id
    assert set().union(*per_task.values()) == {"01", "02", "03", "04"}


def test_the_scope_is_recoverable_from_the_task_text_at_every_partition() -> None:
    """The filter depends on the scope being derivable. If a partition ever
    stopped naming its items, the filter would silently pass everything."""
    from swarmbly_v0.backends import MockBackend

    backend = MockBackend()
    contract = global_contract(CHAIN_TEXT, backend)
    for n_tasks in (2, 4):
        plan = build_plan(CHAIN_TEXT, backend, n_tasks=n_tasks, contract=contract,
                          answer_sheet=True)
        scope = task_item_scope(plan)
        assert scope, f"no scope recovered at N={n_tasks}"
        covered: set[str] = set()
        for items in scope.values():
            assert not (covered & items), "an item appears in two packets"
            covered |= items
        assert covered == {"01", "02", "03", "04"}, covered


# --------------------------------------------------------------------------- #
# fault 6: a sentinel that is a legal value in the measurement's own range
# --------------------------------------------------------------------------- #

def test_single_replica_records_cannot_enter_the_agreement_calibration() -> None:
    """The defect that produced the V6 "agreement collapse".

    A single generation has no agreement -- there is no second reply for it to
    agree with -- and the code wrote 0.0 there with a comment asserting that
    this "keeps it out of every calibration by construction". Nothing kept it
    out. 0.0 is a legal agreement score, so 8 984 single-replica rows, 45 % of
    the graded mass of the run of 26 August, entered the calibration pinned to
    the bottom of the confidence scale.

    Two published numbers came from that and both were artefacts: mean agreement
    of 0.392 and 0.391 for two claim classes 37 accuracy points apart, and a
    local AUC of 0.477, below chance. The below-chance figure is the tell -- the
    tied-at-zero block was 95.8 % correct against 92.2 % for the real k=3 rows,
    so a mass of *correct* items nailed to the lowest agreement value pushed the
    statistic under 0.5.

    The test injects the shape of that fault rather than the literal 0.0, so a
    future sentinel of 0.5 or -1.0 fails it too.
    """
    from swarmbly_v0.experiment import agreement_truth_calibration

    honest = [{"k": 3, "agreement": a, "correct": c} for a, c in
              [(0.9, True)] * 30 + [(0.8, True)] * 20 +
              [(0.3, False)] * 25 + [(0.2, False)] * 25]
    clean = agreement_truth_calibration(honest)
    assert clean["n_items"] == 100
    assert clean["auc"] is not None and clean["auc"] > 0.95

    for sentinel in (0.0, 0.5, -1.0):
        # Single-replica rows: mostly correct, all pinned to one value. This is
        # the real mixture -- k=1 accuracy was *higher* than k=3 accuracy.
        polluted = honest + [{"k": 1, "agreement": sentinel, "correct": True}] * 190 \
                          + [{"k": 1, "agreement": sentinel, "correct": False}] * 10
        out = agreement_truth_calibration(polluted)
        assert out["excluded_single_replica"] == 200, sentinel
        assert out["n_items"] == 100, (
            f"single-replica rows reached the calibration with sentinel {sentinel}")
        assert out["auc"] == clean["auc"], (
            f"sentinel {sentinel} moved the AUC from {clean['auc']} to {out['auc']}")
        assert out["mean_agreement"] == clean["mean_agreement"]


def test_a_unit_with_no_agreement_reports_none_rather_than_zero() -> None:
    """The upstream half: the sentinel must not be written in the first place.

    ``getattr(unit, "agreement", 0.0)`` manufactured a measurement out of a
    missing one. An absent score is ``None``, which every consumer already
    excludes and counts.
    """
    from swarmbly_v0.experiment import _MonolithicUnit
    from swarmbly_v0.grading import grade_units

    unit = _MonolithicUnit(index=0, text="[01] 480")
    assert unit.agreement is None, "the sentinel is back in the dataclass"

    records, _ = grade_units([unit], {"01": {"answer": "480", "mode": "numeric"}})
    assert records, "the unit produced no record"
    assert all(r["agreement"] is None for r in records)
    assert all(r["judge_score"] is None for r in records)


# --------------------------------------------------------------------------- #
# the statistical unit
# --------------------------------------------------------------------------- #

def test_the_cluster_bootstrap_widens_an_interval_that_ignored_clustering() -> None:
    """The correction Seb identified, as a detector.

    Twenty prompts, twenty sentences each: 400 records but only 20 independent
    draws. Treating the sentences as independent produces an interval too narrow
    by roughly the square root of the cluster size, and every by_claim figure
    this project has reported was computed that way.
    """
    import numpy as np
    from swarmbly_v0.stats import cluster_bootstrap, effective_sample_size

    rng = np.random.default_rng(11)
    records = []
    for prompt in range(20):
        # A per-prompt offset: sentences of one answer succeed or fail together.
        level = rng.normal(0.5, 0.30)
        for _ in range(20):
            records.append({"prompt_id": f"p{prompt}",
                            "value": float(level + rng.normal(0, 0.02))})

    def _mean(rows):
        values = [r["value"] for r in rows]
        return sum(values) / len(values) if values else None

    clustered = cluster_bootstrap(records, _mean, cluster_key="prompt_id", draws=800)
    naive = cluster_bootstrap(records, _mean, cluster_key="value", draws=800)

    clustered_width = clustered["ci95"][1] - clustered["ci95"][0]
    naive_width = naive["ci95"][1] - naive["ci95"][0]
    assert clustered_width > naive_width * 3, (clustered_width, naive_width)
    assert clustered["n_clusters"] == 20 and clustered["n_records"] == 400

    ess = effective_sample_size(records, "value", cluster_key="prompt_id")
    assert ess["n_effective"] < 40, (
        f"400 sentences from 20 prompts are worth about 20 observations, "
        f"not {ess['n_effective']}")


def test_the_effective_sample_never_exceeds_the_record_count() -> None:
    """A negative ICC estimate must clamp, not inflate."""
    from swarmbly_v0.stats import effective_sample_size

    records = [{"prompt_id": f"p{i % 4}", "value": float(i % 2)} for i in range(40)]
    ess = effective_sample_size(records, "value", cluster_key="prompt_id")
    assert ess["n_effective"] <= ess["n_records"]


# --------------------------------------------------------------------------- #
# the corpus split: a threshold fitted on its own evaluation data
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def tables24() -> dict:
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "prompts" / "tables24.json"
    if not path.exists():
        pytest.skip("prompts/tables24.json not generated")
    return json.loads(path.read_text())


def test_the_table_corpus_declares_a_split_and_the_split_is_honoured(tables24) -> None:
    """Eight dev, sixteen final, every prompt on exactly one side.

    The split is the control against fitting a threshold on the data it then
    evaluates -- tau_sem, the go/no-go threshold, the agreement bin edges and the
    flagging rate have all been chosen that way so far.
    """
    prompts = tables24["prompts"]
    dev = [p for p in prompts if p["split"] == "dev"]
    final = [p for p in prompts if p["split"] == "final"]
    assert len(prompts) == 24
    assert len(dev) == 8 and len(final) == 16
    assert {p["id"] for p in dev}.isdisjoint({p["id"] for p in final})
    assert len({p["id"] for p in prompts}) == 24, "a duplicated id joins two prompts"

    frozen = tables24["_frozen"]
    assert sorted(p["id"] for p in dev) == frozen["dev"]
    assert sorted(p["id"] for p in final) == frozen["final"]

    # Interleaved, not "the first eight". Sequential assignment would put the two
    # halves in different regions of the generator's stream.
    order = [p["split"] for p in prompts]
    assert order[:8] != ["dev"] * 8, "the split is sequential, not interleaved"


def test_the_frozen_digest_detects_a_corpus_that_has_moved(tables24) -> None:
    """A freeze is a claim about *when* something was decided, so it needs a
    mechanism. Editing one prompt must change the digest."""
    import copy
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from make_tables import build, digest

    rebuilt = build()
    assert digest(rebuilt) == tables24["_frozen"]["sha256"], (
        "the corpus on disk is not what make_tables.py builds")

    moved = copy.deepcopy(rebuilt)
    moved[0]["prompt"] += " One more sentence."
    assert digest(moved) != tables24["_frozen"]["sha256"]

    reassigned = copy.deepcopy(rebuilt)
    reassigned[1]["split"] = "dev"
    assert digest(reassigned) != tables24["_frozen"]["sha256"], (
        "moving a prompt across the split must change the digest")


def test_loading_one_half_returns_only_that_half_and_never_silently_nothing() -> None:
    """The refusal matters more than the filter.

    An empty result would let a calibration run on nothing and report its
    thresholds as though they had been fitted -- the failure the split exists to
    prevent, arriving through the mechanism meant to prevent it.
    """
    from swarmbly_v0.experiment import load_prompts

    path = Path(__file__).resolve().parents[1] / "prompts" / "tables24.json"
    if not path.exists():
        pytest.skip("prompts/tables24.json not generated")

    assert len(load_prompts(path)) == 24
    assert len(load_prompts(path, split="dev")) == 8
    assert len(load_prompts(path, split="final")) == 16
    assert all(s.split == "dev" for s in load_prompts(path, split="dev"))

    with pytest.raises(ValueError, match="Refusing to run a calibration"):
        load_prompts(path, split="holdout")

    # A corpus with no split is unaffected: no split declared, no filter applied.
    shared = Path(__file__).resolve().parents[1] / "prompts" / "complex.json"
    if shared.exists():
        specs = load_prompts(shared)
        assert specs and all(s.split == "" for s in specs)


def test_the_final_half_cannot_be_run_with_a_self_fitted_threshold() -> None:
    """The split's only real control.

    tau_sem is calibrated *inside* the run, from that run's own baselines. A
    final run left to calibrate itself has fitted its threshold on the data it
    is about to judge -- which is precisely the leakage the split exists to
    close, arriving through the split. So the runner refuses, and says where to
    get the value.
    """
    from swarmbly_v0.cli import main

    path = Path(__file__).resolve().parents[1] / "prompts" / "tables24.json"
    if not path.exists():
        pytest.skip("prompts/tables24.json not generated")
    base = ["run", "--prompts", str(path), "--rho", "3.5", "--n", "2",
            "--k", "1", "--backend", "mock", "--embedder", "hash",
            "--max-prompts", "1", "--no-report", "--quiet"]

    with pytest.raises(SystemExit) as caught:
        main(base + ["--split", "final", "--out", "/tmp/_swarmbly_refuse"])
    assert "refusing to run --split final without --tau" in str(caught.value)

    # dev is free to fit its own: that is what dev is for.
    assert main(base + ["--split", "dev", "--out", "/tmp/_swarmbly_dev"]) == 0


def test_every_table_prompt_carries_a_gradable_numeric_key(tables24) -> None:
    """A prompt whose figures cannot be checked contributes a denominator and no
    verdict. Twenty-four of those would widen the interval, not narrow it."""
    from swarmbly_v0.constraints import check_numeric_fidelity

    for prompt in tables24["prompts"]:
        allowed = prompt["numeric_facts"]["allowed"]
        assert len(allowed) > 20, prompt["id"]
        total = prompt["numeric_facts"]["total"]
        assert total in allowed, f"{prompt['id']}: the total is not a legal figure"
        # A correct sentence passes and an invented figure fails, on this key.
        assert check_numeric_fidelity(
            f"The total weight is {total:.0f} kg.", allowed) is True
        assert check_numeric_fidelity(
            f"The total weight is {total + 7:.0f} kg.", allowed) is False


# --------------------------------------------------------------------------- #
# fault 7: a stratification that inverts the answer
# --------------------------------------------------------------------------- #

def test_pooling_two_claim_classes_can_invert_the_flagging_verdict() -> None:
    """The sixth pooling artefact, and the first that ran the other way.

    The previous five made a null look like a result. This one made a result
    look like a null: on the table run of 26 August the pooled flagging lift
    read 1.05, 0.70 and 0.88 -- at or below random -- while inside the aggregate
    class it read 2.15, 1.75 and 1.48.

    The mixture that does it: aggregate claims carry HIGH agreement and LOW
    accuracy, local claims the reverse. Pooled, the high-agreement items are
    disproportionately the wrong ones and the ranking inverts. Reproduced here
    with the same shape.
    """
    from swarmbly_v0.experiment import stratified_flagging

    records = []
    # aggregate: HIGH agreement (0.70-0.90), 36 % wrong, and inside the class
    # the wrong ones sit at the bottom of its range -- a real signal.
    for i in range(100):
        records.append({"claim": "aggregate", "k": 3, "correct": i >= 36,
                        "agreement": 0.70 + 0.002 * i})
    # local: LOW agreement (0.30-0.70), 10 % wrong, spread evenly across its
    # range -- almost no signal, which is what the real local class looks like.
    for i in range(200):
        records.append({"claim": "local", "k": 3, "correct": i % 10 != 0,
                        "agreement": 0.30 + 0.002 * i})

    def pooled_lift(rows, rate):
        usable = [(float(r["agreement"]), bool(r["correct"])) for r in rows]
        cut = int(round(rate * len(usable)))
        flagged = sorted(usable)[:cut]
        n_wrong = sum(1 for _, ok in usable if not ok)
        caught = sum(1 for _, ok in flagged if not ok)
        return (caught / cut) / (n_wrong / len(usable))

    # Pooled, the flag lands entirely in the LOW-agreement class, which is the
    # class that is mostly right. It underperforms random.
    assert pooled_lift(records, 0.20) < 1.0

    stratified = stratified_flagging(records, key="claim")
    row = next(r for r in stratified if r["flag_rate"] == 0.20)
    assert row["lift"] > 1.5, row
    assert row["by_stratum"]["aggregate"]["lift"] > 1.5, row["by_stratum"]
    # And the point of by_stratum: local carries none of it. A confidence map
    # that works for one claim class is a narrower claim than the pooled figure
    # -- in either direction -- makes it look.
    assert row["by_stratum"]["local"]["lift"] < 1.2, row["by_stratum"]


def test_the_declared_cell_must_name_k_as_well_as_n() -> None:
    """One axis on from the N defect, and the same defect.

    The table run of 26 August declared table_summary at rho 3.5, N=2 and the
    criterion returned +18.3% -- the midpoint of +20.6% at k=1 and +16.0% at
    k=3. The rest of the summary already refuses to average k, on the stated
    grounds that such a mean "belongs to neither"; the criterion was the one
    place still doing it.
    """
    from swarmbly_v0.experiment import falsifiable_go_no_go

    rows = [{"condition": "fragmented", "category": "t", "rho_target": 3.5,
             "n_tasks": 2, "k": 1, "prompt_id": f"p{i}", "coherence_tax_booook": v}
            for i, v in enumerate((0.20, 0.21, 0.20, 0.21))]
    rows += [{"condition": "fragmented", "category": "t", "rho_target": 3.5,
              "n_tasks": 2, "k": 3, "prompt_id": f"p{i}", "coherence_tax_booook": v}
             for i, v in enumerate((0.01, 0.02, 0.01, 0.02))]

    pooled = falsifiable_go_no_go(rows, category="t", rho=3.5, n_tasks=2)
    assert pooled["declared_cell"]["k"] is None
    assert 0.10 < pooled["point_estimate"] < 0.12, "not the midpoint of the two arms"

    at_one = falsifiable_go_no_go(rows, category="t", rho=3.5, n_tasks=2, k=1)
    at_three = falsifiable_go_no_go(rows, category="t", rho=3.5, n_tasks=2, k=3)
    assert at_one["n_observations"] == 4 and at_three["n_observations"] == 4
    assert at_one["passed"] is False, "k=1 costs 20% and must fail"
    assert at_three["passed"] is True, "k=3 costs 1.5% and must pass"
    assert at_one["declared_cell"]["k"] == 1


# --------------------------------------------------------------------------- #
# fault 8: a cell that did not run at the budget its label names
# --------------------------------------------------------------------------- #

def test_a_cell_that_overshot_its_context_budget_is_flagged() -> None:
    """rho is the independent variable, so drift makes the label a lie.

    Nothing checked this until the table run of 26 August, where N=8 sat at 3.91
    against a target of 3.5 -- 11.6% over, with rho_floor at 1.13, so the floor
    was not forcing it. The N=8 arm received MORE context than N=2 and still did
    far worse. That direction happens to be conservative for the conclusion
    drawn from it; the direction was luck, not design.
    """
    from swarmbly_v0.experiment import rho_fidelity

    rows = [{"rho_target": 3.5, "n_tasks": 2, "rho_achieved": v}
            for v in (3.48, 3.44, 3.50, 3.47)]
    rows += [{"rho_target": 3.5, "n_tasks": 8, "rho_achieved": v}
             for v in (3.85, 3.98, 3.81, 3.96)]

    out = rho_fidelity(rows)
    assert out["within_tolerance"] is False
    assert out["n_cells_out_of_tolerance"] == 1
    assert out["worst"]["n_tasks"] == 8
    assert out["worst"]["relative_deviation"] > 0.10

    by_n = {c["n_tasks"]: c for c in out["cells"]}
    assert by_n[2]["within_tolerance"] is True, "N=2 is inside a percent and must pass"
    assert by_n[8]["within_tolerance"] is False

    # The clean control: a run that hit its target reports no drift at all.
    clean = rho_fidelity([{"rho_target": 3.5, "n_tasks": n, "rho_achieved": 3.49}
                          for n in (2, 8) for _ in range(4)])
    assert clean["within_tolerance"] is True
    assert clean["n_cells_out_of_tolerance"] == 0


# --------------------------------------------------------------------------- #
# fault 9: a percentile flag on a predictor with four values
# --------------------------------------------------------------------------- #

def test_a_flag_never_splits_a_tie_group_it_cannot_distinguish() -> None:
    """Agreement is consistent/k, so k=3 gives exactly four values.

    On the table run of 26 August those four held 8, 82, 87 and 141 items.
    "Flag the lowest 20 %" asks for 64 items out of a group of 82 that the
    predictor cannot tell apart, so which 64 depends on the sort's tie order --
    and two correct implementations disagreed by 0.6 in lift because of it.

    A flag that cannot be acted on is not a measurement, so a tie group is taken
    whole or not at all and `achieved_rate` says what that came to.
    """
    from swarmbly_v0.experiment import stratified_flagging

    # 100 items on four values, with a 40-item tie group straddling the 20 % cut.
    records = ([{"claim": "a", "k": 3, "agreement": 0.0, "correct": False}] * 5
               + [{"claim": "a", "k": 3, "agreement": 1 / 3, "correct": i >= 15}
                  for i in range(40)]
               + [{"claim": "a", "k": 3, "agreement": 2 / 3, "correct": True}] * 30
               + [{"claim": "a", "k": 3, "agreement": 1.0, "correct": True}] * 25)

    row = next(r for r in stratified_flagging(records, key="claim")
               if r["flag_rate"] == 0.20)
    stratum = row["by_stratum"]["a"]
    # 5 alone undershoots by 15; 5+40 overshoots by 25. It must stop at 5, not
    # slice the tie group.
    assert stratum["n_flagged"] == 5, stratum
    assert stratum["achieved_rate"] == 0.05
    assert stratum["errors_caught"] == 5

    # Shuffling within the tie group cannot change the answer any more.
    import random
    shuffled = list(records)
    random.Random(7).shuffle(shuffled)
    again = next(r for r in stratified_flagging(shuffled, key="claim")
                 if r["flag_rate"] == 0.20)
    assert again["by_stratum"]["a"] == stratum


def test_the_discrete_calibration_table_separates_what_the_auc_merged() -> None:
    """The statistic a four-valued predictor can actually support.

    Reproduces the run of 26 August: aggregate claims monotone across 75
    accuracy points, local claims flat and inverted at the top, and the pooled
    table neither.
    """
    from swarmbly_v0.experiment import discrete_calibration

    def block(claim, value, n, accuracy):
        return [{"claim": claim, "k": 3, "agreement": value,
                 "correct": i < round(n * accuracy)} for i in range(n)]

    records = (block("aggregate", 0.0, 2, 0.0) + block("aggregate", 1 / 3, 8, 0.25)
               + block("aggregate", 2 / 3, 40, 0.625) + block("aggregate", 1.0, 44, 0.75)
               + block("local", 0.0, 6, 0.833) + block("local", 1 / 3, 74, 0.946)
               + block("local", 2 / 3, 47, 0.936) + block("local", 1.0, 97, 0.845))

    out = discrete_calibration(records, key="claim")
    assert out["discrete"] is True and out["n_distinct_values"] == 4

    aggregate = out["by_stratum"]["aggregate"]
    assert aggregate["monotone"] is True
    assert aggregate["span"] > 0.70, "the working half of the confidence map"

    local = out["by_stratum"]["local"]
    assert local["monotone"] is False
    assert local["span"] < 0.20, "flat: nothing to separate"

    # Pooled, the shape of neither survives.
    assert discrete_calibration(records)["by_stratum"]["all"]["monotone"] is False


def test_a_cell_filter_matches_numbers_not_their_string_forms() -> None:
    """Rows read back from results.csv carry floats.

    ``str(2.0) != str(2)``, so the old string comparison made every cell filter
    match nothing -- and a criterion re-run over a finished run's own artefacts
    reported no cells rather than an error. Found by scripts/reanalyse.py on its
    first use.
    """
    from swarmbly_v0.experiment import falsifiable_go_no_go

    as_read = [{"condition": "fragmented", "category": "t", "rho_target": 3.5,
                "n_tasks": 2.0, "k": 1.0, "prompt_id": f"p{i}",
                "coherence_tax_booook": v}
               for i, v in enumerate((0.20, 0.21, 0.20, 0.21))]
    out = falsifiable_go_no_go(as_read, category="t", rho=3.5, n_tasks=2, k=1)
    assert out["n_observations"] == 4, "float 2.0 did not match int 2"
    assert out["passed"] is False


# --------------------------------------------------------------------------- #
# fault 10: a per-claim signal that is really a per-prompt one
# --------------------------------------------------------------------------- #

def test_a_flag_that_only_finds_hard_prompts_does_not_survive_stratification() -> None:
    """The threat to the successor hypothesis, injected.

    A confidence map is worth something if it says *this claim* is wrong. It is
    worth nothing if it only says *this prompt* is hard -- that is already
    available from the error rate. An unstratified lift cannot tell the two
    apart, and on the dev half three of eight prompts held no flagged item at
    all while the three with the most flags were the three with the most errors.

    Here the fault is injected pure: agreement is a perfect proxy for which
    prompt an item came from and carries no information *inside* any prompt. The
    lift must look impressive and the odds ratio must be 1.
    """
    from swarmbly_v0.experiment import flag_effect

    records = []
    # Four hard prompts: 60 % wrong, and every item low-agreement.
    for prompt in range(4):
        for i in range(20):
            records.append({"prompt_id": f"hard{prompt}", "k": 3,
                            "agreement": 1 / 3, "correct": i >= 12})
    # Four easy prompts: 10 % wrong, every item high-agreement.
    for prompt in range(4):
        for i in range(20):
            records.append({"prompt_id": f"easy{prompt}", "k": 3,
                            "agreement": 1.0, "correct": i >= 2})

    out = flag_effect(records)
    assert out["lift_unstratified"] > 1.6, out["lift_unstratified"]
    assert out["n_strata_contributing"] == 0, (
        "no prompt has both flagged and unflagged items, so nothing is estimable")
    assert out["odds_ratio"] is None
    assert "nothing is estimable" in out["unestimable_reason"]

    # The clean control: the same marginal error rates, but the flag now ranks
    # *inside* each prompt. Imperfect, as real data is -- two thirds of the
    # errors carry the low value and a tenth of the correct answers do too.
    within = []
    for prompt in range(8):
        wrong = 10 if prompt < 4 else 5
        for i in range(20):
            is_wrong = i < wrong
            # Two thirds of the errors carry the low value, and so does a fifth
            # of the correct answers -- every stratum has all four cells filled.
            low = (i % 3 != 2) if is_wrong else (i % 5 == 0)
            within.append({"prompt_id": f"p{prompt}", "k": 3,
                           "agreement": 1 / 3 if low else 1.0,
                           "correct": not is_wrong})
    clean = flag_effect(within)
    assert clean["n_strata_contributing"] == 8
    assert clean["odds_ratio"] is not None and clean["odds_ratio"] > 4, clean["odds_ratio"]
    assert clean["ci95"] and clean["ci95"][0] > 1.0, clean["ci95"]


def test_the_flag_cut_is_a_fraction_of_k_not_a_percentile() -> None:
    """Frozen before the final half, and expressible on the predictor.

    A percentile cut on a k+1-valued predictor lands inside a tie group; a
    fraction of k always lands between two of them.
    """
    from swarmbly_v0.experiment import FLAG_CUT, flag_effect

    assert abs(FLAG_CUT - 2 / 3) < 1e-9, "the frozen cut moved"

    # Each prompt sees all four agreement values, so every stratum informs.
    records = [{"prompt_id": f"p{i // 4}", "k": 3, "agreement": a, "correct": ok}
               for i, (a, ok) in enumerate(
                   [(0.0, False), (1 / 3, False), (2 / 3, True), (1.0, True)] * 8)]
    out = flag_effect(records)
    # Exactly the two values below 2/3 are flagged: half the items, no ties split.
    assert out["n_flagged"] == len(records) // 2
    assert out["precision_flagged"] == 1.0
    # Perfect separation is reported as such, not as "not estimable".
    assert out["odds_ratio"] is None
    assert "perfect separation" in out["unestimable_reason"]


# --------------------------------------------------------------------------- #
# fault 11: the metric is not arm-neutral
# --------------------------------------------------------------------------- #

_ANSWER = """The manifest lists twenty consignments bound for depots on three continents.
The heaviest consignment is reference H8215, carrying 945 kg of drive belts to Busan.
Total weight across all twenty rows comes to 9,420 kg.
Volumes are spread unevenly, with four depots taking more than 700 kg each.

Cable reels account for the largest share by count, appearing on five separate rows.
The lightest movement is 130 kg of gasket sets to Nantes.
Average consignment weight is 471 kg, which is close to the median.
No single destination dominates the schedule.

Pump seals and filter packs travel in comparable quantities.
Two depots appear twice in the schedule, which suggests a split delivery.
The spread between lightest and heaviest is 815 kg.
Planning should treat the four heaviest rows as the constraint.

Overall the manifest is balanced against the available dock capacity.
Scheduling risk sits with the Busan movement, given its weight.
The remaining nineteen rows fall inside routine handling limits.
A duty manager should confirm pilotage for the heaviest row only."""


def test_identical_text_scores_identically_however_it_was_partitioned() -> None:
    """The defect that inflated every coherence tax this project has reported.

    The two arms enter ``seam_error_taxonomy`` by different paths: monolithic
    passes ``plan=None``, fragmented passes the plan. Two consequences, neither
    of them a property of the answer, and both growing with N:

      * the omission detector took its expected set from the union of
        ``plan.tasks[].expected_entities`` -- 0 for a baseline that passes no
        plan, 6 at N=2, 17 at N=8 -- and then attributed the SAME missing
        entities round-robin across N fragment heads, so one document's
        omissions dirtied one sentence at monolithic and up to N at N tasks;
      * ``missing_transition`` and a seam-anchored ``dangling_reference`` fire
        only at seams, and a monolithic answer has none.

    Scored through both conventions, one identical 16-sentence answer came back
    0.9375 and 0.5000 -- an apparent tax of **+46.7 % on text that never
    changed**. Against the run of 26 August, where the reported figures were
    +22.9 % at N=2 and +63.8 % at N=8, that is most of the result.

    This test is the cheapest one in the file and would have caught it before any
    of six runs. It asserts the invariant directly: the comparable score is a
    property of the text.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import PromptSpec, prompt_expected_entities
    from swarmbly_v0.metrics import seam_error_taxonomy
    from swarmbly_v0.textutil import split_sentences

    backend = MockBackend()
    prompt = ("Summarise the manifest table below for a duty manager. "
              "Write exactly four paragraphs, each between 70 and 130 words. "
              "Name the heaviest consignment and give the total weight.")
    contract = global_contract(prompt, backend)
    spec = PromptSpec(prompt_id="m", category="table_summary",
                      expected_decomposable=True, text=prompt)
    expected = prompt_expected_entities(spec, contract, backend)
    n_sentences = len(split_sentences(_ANSWER))

    scores, seam_rates = {}, {}
    for n_tasks in (None, 2, 4, 8):
        if n_tasks is None:
            report = seam_error_taxonomy(_ANSWER, None, None, contract,
                                         expected_entities=expected)
        else:
            built = build_plan(prompt, backend, n_tasks=n_tasks, contract=contract)
            offsets = [round(i * n_sentences / n_tasks) for i in range(n_tasks)]
            report = seam_error_taxonomy(_ANSWER, built, offsets, contract,
                                         expected_entities=expected)
        scores[n_tasks] = report.comparable_score
        seam_rates[n_tasks] = report.seam_error_rate

    assert len(set(round(v, 9) for v in scores.values())) == 1, (
        f"the comparable score depends on the partition: {scores}")

    # The seam cost is real and is reported -- in its own column, where a reader
    # can see that it is the assembly's and not the answer's.
    assert seam_rates[None] == 0.0, "a monolithic answer has no seams"
    assert seam_rates[8] > seam_rates[2] > 0.0, seam_rates


def test_an_omission_dirties_the_same_sentences_at_every_partition() -> None:
    """The attribution must not change the score.

    ``anchor = offsets[i % len(offsets)]`` spread the identical set of missing
    entities across N fragment heads, and the score is clean/n_sentences.
    """
    from swarmbly_v0.metrics import seam_error_taxonomy

    text = ("The cache holds receipts. It expires them hourly. "
            "Nothing else is stored. The audit trail is separate.")
    absent = ["Vesper", "Tarrow", "Kelbrook", "Anwyl", "Sedge", "Marrin"]

    counts, scores = {}, {}
    for n_tasks in (1, 2, 4, 8):
        offsets = [round(i * 4 / n_tasks) for i in range(n_tasks)]
        report = seam_error_taxonomy(text, None, offsets, None,
                                    expected_entities=absent)
        counts[n_tasks] = report.counts["entity_omission"]
        scores[n_tasks] = report.comparable_score

    assert len(set(counts.values())) == 1 == len(set(scores.values())), (
        f"the partition moved the omission score: counts={counts} scores={scores}")
    assert counts[1] == len(absent), "every absent entity must still be counted"


# --------------------------------------------------------------------------- #
# the meta-test: a silent instrument must fail this file
# --------------------------------------------------------------------------- #

def test_every_injected_fault_has_a_detector_that_is_quiet_when_clean() -> None:
    """A detector that fires on everything detects nothing.

    Each fault above pairs an injection with a clean control. This asserts the
    pairing exists rather than trusting that it was remembered: the clean case of
    each metric must pass.
    """
    assert grade_text(COMPLIANT, CONSTRAINTS).score == 1.0
    assert check_numeric_fidelity("The heaviest is 845 kg.", [845.0]) is True
    fed, _ = _chain_accuracy(blind=False)
    assert fed == 1.0


# --------------------------------------------------------------------------- #
# fault 12: a result that cannot say what produced it
# --------------------------------------------------------------------------- #

def test_the_source_fingerprint_moves_when_the_measuring_code_moves() -> None:
    """A results directory has to be self-describing.

    On 27 August three ``tables-*`` runs sat side by side -- two scored by an
    arm-neutral coherence metric, one by the defective predecessor -- and
    nothing in any of them said which. The directory timestamp against a memory
    of when the fix landed was the only evidence, and that is not evidence.
    """
    import hashlib
    from swarmbly_v0.schema import _source_files, source_fingerprint

    files = _source_files()
    assert len(files) > 10, "the package should have more source files than this"
    assert all(p.suffix == ".py" for p in files)
    assert source_fingerprint() == source_fingerprint(), "not deterministic"

    # Changing any byte of any source file must move it, comments included: a
    # digest that only moved on "important" edits would need someone to decide
    # what counts as important, which is the judgement this removes.
    baseline = hashlib.sha256()
    for path in files:
        baseline.update(path.name.encode("utf-8"))
        baseline.update(path.read_bytes())
    assert source_fingerprint() == baseline.hexdigest()

    moved = hashlib.sha256()
    for i, path in enumerate(files):
        moved.update(path.name.encode("utf-8"))
        moved.update(path.read_bytes() + (b"# " if i == 0 else b""))
    assert moved.hexdigest() != baseline.hexdigest()


def test_a_run_records_the_code_and_the_corpus_that_produced_it() -> None:
    """Both halves, in the metadata, on every run."""
    import json
    from swarmbly_v0.cli import main
    from swarmbly_v0.schema import source_fingerprint

    path = Path(__file__).resolve().parents[1] / "prompts" / "tables24.json"
    if not path.exists():
        pytest.skip("prompts/tables24.json not generated")
    out = Path("/tmp/_swarmbly_provenance")
    assert main(["run", "--prompts", str(path), "--split", "dev",
                 "--rho", "3.5", "--n", "2", "--k", "1",
                 "--backend", "mock", "--embedder", "hash",
                 "--max-prompts", "1", "--no-report", "--quiet",
                 "--out", str(out)]) == 0

    meta = json.loads((out / "run_metadata.json").read_text())
    assert meta["code_sha256"] == source_fingerprint()
    assert meta["corpus_frozen_sha256"]
    assert meta["corpus_split"] == "dev"


# --------------------------------------------------------------------------- #
# fault 13: a packet that cannot answer its own question
# --------------------------------------------------------------------------- #

def test_the_run_refuses_before_dispatch_when_a_packet_lost_its_contract() -> None:
    """Blocking, not advisory, and BEFORE tokens are spent.

    ``rho_fidelity`` reported the same N=8 drift in four consecutive runs and
    every one of them completed, was analysed, and had a figure quoted from it.
    A check that has to be read is a check that gets skipped.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.packing import (PacketInvariantError, assert_packet_invariants,
                                     build_packets)
    from swarmbly_v0.schema import Packet

    backend = MockBackend()
    prompt = ("Summarise the manifest table for a duty manager in four "
              "paragraphs, naming the heaviest consignment and the total weight.")
    contract = global_contract(prompt, backend)
    built = build_plan(prompt, backend, n_tasks=2, contract=contract)
    packing = build_packets(contract, built, 3.5)

    # Clean: passes, quietly.
    assert_packet_invariants(packing.packets, built, contract,
                             rho_target=0.0, prompt=prompt)

    # Injected: one packet stripped of its contract header.
    stripped = list(packing.packets)
    victim = stripped[0]
    stripped[0] = Packet(task_id=victim.task_id,
                         text=victim.text.replace("[GLOBAL CONTRACT]", "[NOTES]"),
                         token_count=victim.token_count,
                         context_tokens=victim.context_tokens,
                         task_tokens=victim.task_tokens,
                         blocks_included=victim.blocks_included,
                         truncated=victim.truncated)
    with pytest.raises(PacketInvariantError, match="no \\[GLOBAL CONTRACT\\]"):
        assert_packet_invariants(stripped, built, contract,
                                 rho_target=0.0, prompt=prompt)


def test_rho_hits_its_target_at_every_partition() -> None:
    """The defect that survived four runs, as an invariant.

    build_packets was called once per topological level with the FULL budget
    each time, while only that level's packets were dispatched -- so a plan of
    sections plus an integration node budgeted the integration node twice, and
    the second time its `desired` had grown. Achieved rho came out at 3.90
    against a target of 3.5.
    """
    import json
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.experiment import RHO_TOLERANCE, SweepConfig, run_fragmented
    from swarmbly_v0.packing import packing_floor

    path = Path(__file__).resolve().parents[1] / "prompts" / "tables24.json"
    if not path.exists():
        pytest.skip("prompts/tables24.json not generated")
    data = json.loads(path.read_text())["prompts"][0]
    spec = PromptSpec(prompt_id=data["id"], category=data["category"],
                      expected_decomposable=True, text=data["prompt"],
                      numeric_facts=data.get("numeric_facts"))
    backend = MockBackend()

    for n_tasks in (2, 4, 6, 8):
        row = run_fragmented(spec, backend, backend,
                             SweepConfig(rhos=(3.5,), ns=(n_tasks,), ks=(1,)),
                             rho_target=3.5, n_tasks=n_tasks, tau_sem=0.5)
        if not row["rho_reachable"]:
            continue
        deviation = (row["rho_achieved"] - 3.5) / 3.5
        assert abs(deviation) <= RHO_TOLERANCE, (
            f"N={n_tasks}: achieved {row['rho_achieved']:.3f} against 3.5 "
            f"({deviation:+.1%})")


def test_the_floor_counts_the_header_it_has_always_claimed_to_count() -> None:
    """The module has always defined the floor as tasks plus one header each.

    The implementation summed only the task blocks, so the floor was
    under-reported by one header per packet and cells announced
    rho_reachable=true for targets they could not hit. On prompts.json -- V0's
    corpus -- the honest floor is 1.85 to 2.35 at N=4, and V0 swept rho from
    1.0 to 2.0.
    """
    from swarmbly_v0.backends import MockBackend
    from swarmbly_v0.packing import build_packet, packing_floor
    from swarmbly_v0.textutil import count_tokens

    backend = MockBackend()
    prompt = ("Write a technical note on harbour scheduling covering the tide "
              "window, berth allocation, the manifest and pilotage.")
    contract = global_contract(prompt, backend)

    for n_tasks in (2, 4, 8):
        built = build_plan(prompt, backend, n_tasks=n_tasks, contract=contract)
        floor = packing_floor(contract, built)
        # A packet squeezed to nothing still carries task block and header, so
        # the sum of the smallest possible packets IS the floor.
        smallest = sum(count_tokens(build_packet(contract, t, {}, 0.0).text)
                       for t in built.tasks)
        assert smallest / count_tokens(prompt) == pytest.approx(floor, rel=0.02)
        assert all("[GLOBAL CONTRACT]" in build_packet(contract, t, {}, 0.0).text
                   for t in built.tasks)


# --------------------------------------------------------------------------- #
# fault 14: a saturated judge, and a ratio with no room in its denominator
# --------------------------------------------------------------------------- #

def test_a_saturated_judge_is_reported_as_absent_not_as_a_null() -> None:
    """Four consecutive runs at 100 % acceptance, reported as a correlation.

    A verdict that does not vary cannot produce a correlation whether or not the
    signal exists. Reporting `pearson_r: None` alone lets a reader take an
    absent measurement for a measured null.
    """
    from swarmbly_v0.experiment import agreement_quality_correlation

    saturated = agreement_quality_correlation(
        [{"agreement": 0.3 + i * 0.01, "accepted": True} for i in range(50)])
    assert saturated["saturated"] is True
    assert saturated["pearson_r"] is None
    assert "saturated" in saturated["note"]

    working = agreement_quality_correlation(
        [{"agreement": 0.3 + i * 0.01, "accepted": i % 2 == 0} for i in range(50)])
    assert working["saturated"] is False
    assert working["pearson_r"] is not None


def test_the_paired_estimator_is_insensitive_to_a_baseline_at_the_ceiling() -> None:
    """Why the ratio missed by 1.9 points and what a companion estimator shows.

    A relative degradation divides by the baseline, so a baseline of 1.000 makes
    one lost sentence the whole numerator. On the final run `bonded` -- baseline
    1.000 -- contributed 1.3 of the 3.3 points.
    """
    from swarmbly_v0.experiment import falsifiable_go_no_go, paired_absolute_effect

    # Fifteen ordinary prompts losing 0.02 of score, and one at the ceiling
    # losing the same 0.02. The absolute loss is identical everywhere.
    rows = [{"condition": "fragmented", "category": "t", "rho_target": 3.5,
             "n_tasks": 2, "k": 1, "prompt_id": f"p{i}",
             "booook_comparable": 0.78, "baseline_booook_comparable": 0.80,
             "coherence_tax_booook": 0.02 / 0.80}
            for i in range(15)]
    rows.append({"condition": "fragmented", "category": "t", "rho_target": 3.5,
                 "n_tasks": 2, "k": 1, "prompt_id": "ceiling",
                 "booook_comparable": 0.98, "baseline_booook_comparable": 1.00,
                 "coherence_tax_booook": 0.02 / 1.00})

    paired = paired_absolute_effect(rows, category="t", rho=3.5, n_tasks=2, k=1)
    assert paired["n_observations"] == 16
    assert paired["baseline_at_ceiling"] == 1
    # Every prompt lost exactly 0.02, so the paired difference sees no outlier.
    assert paired["mean_delta"] == pytest.approx(0.02, abs=1e-6)
    assert paired["median_delta"] == pytest.approx(0.02, abs=1e-6)
    assert max(p["delta"] for p in paired["pairs"]) == pytest.approx(0.02, abs=1e-6)

    # The declared relative criterion still runs and is still the declared one.
    declared = falsifiable_go_no_go(rows, category="t", rho=3.5, n_tasks=2, k=1)
    assert declared["n_observations"] == 16
    assert declared["passed"] is not None
