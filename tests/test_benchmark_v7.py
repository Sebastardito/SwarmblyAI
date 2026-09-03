"""V7's own instrument check, before V7 measures anything.

The harness earned this file the hard way: nine defects found by adversarial
review in one sitting, a coherence metric that was not arm-neutral, a packing
floor that disagreed with its own definition. Every one of them was found *after*
a run had been analysed and a figure quoted.

So the benchmark's evaluator is tested against the same class of fault before it
is used, and the first test is the invariant that broke in the harness.
"""

from __future__ import annotations

import pytest

from benchmark_v7.evaluate import evaluate, parse_claims
from benchmark_v7.graph import build_instance, instance_digest


# --------------------------------------------------------------------------- #
# the invariant that broke in the harness
# --------------------------------------------------------------------------- #

def test_the_same_answer_scores_the_same_however_the_prompt_was_cut() -> None:
    """Arm neutrality, asserted before the evaluator is ever used.

    In the harness the monolithic baseline entered the scorer by one path and
    the fragmented arm by another, and one identical sixteen-sentence answer
    came back 0.9375 and 0.5000 -- an apparent tax of +46.7 % on text that never
    changed. The arm label reaches this evaluator too; it must not touch the
    verdict.
    """
    instance = build_instance("map", seed=1)
    answer = "\n".join(f"[{c.claim_id}] {c.answer:g}" for c in instance.claims)

    reports = [evaluate(instance, answer, arm=arm)
               for arm in ("monolithic", "oracle", "real", "real+carry")]
    accuracies = {r.accuracy for r in reports}
    coverages = {r.coverage for r in reports}

    assert accuracies == {1.0}, f"the arm label moved the verdict: {accuracies}"
    assert coverages == {1.0}
    assert all(r.unanswerable_rate == 0.0 for r in reports)


def test_wrong_and_unanswerable_are_different_verdicts() -> None:
    """The distinction the flat answer key could never make.

    A claim the packet could not have produced is a packing failure; a claim the
    packet had everything for and still got wrong is a model failure. Six runs
    were spent on questions where these were indistinguishable, and in at least
    three cases the answer turned out to be the second.
    """
    instance = build_instance("reduce", seed=7)
    grand = next(c for c in instance.claims if c.claim_id == "c_grand")

    # Same wrong answer, twice. Once from a packet that held everything, once
    # from a packet that held only the first section.
    answer = f"[c_grand] {grand.answer + 500:g}"
    first_section = [s.section_id for s in instance.sections][:1]
    partial = {"p0": sorted(instance.facts_in_sections(first_section))}
    owner = {c.claim_id: "p0" for c in instance.claims}

    fed = evaluate(instance, answer, arm="oracle")
    starved = evaluate(instance, answer, arm="real",
                       facts_available=partial, claim_owner=owner)

    fed_verdict = next(v for v in fed.verdicts if v.claim_id == "c_grand")
    starved_verdict = next(v for v in starved.verdicts if v.claim_id == "c_grand")

    assert fed_verdict.failure == "wrong"
    assert starved_verdict.failure == "unanswerable"
    assert starved_verdict.missing_facts, "the missing facts must be named"
    assert starved_verdict.owed_by, "and the section that owed them"
    assert starved.unanswerable_rate > 0


def test_an_unstated_claim_is_neither_right_nor_wrong() -> None:
    """Folding it into either verdict moves accuracy toward whichever was
    chosen. It is counted, and excluded."""
    instance = build_instance("map", seed=3)
    stated = instance.claims[0]
    report = evaluate(instance, f"[{stated.claim_id}] {stated.answer:g}", arm="real")

    assert report.accuracy == 1.0, "the one stated claim was right"
    assert report.coverage == pytest.approx(1 / len(instance.claims))
    assert report.as_dict()["failures"]["not_stated"] == len(instance.claims) - 1


# --------------------------------------------------------------------------- #
# the parser, which is where the harness's grader was wrong for six runs
# --------------------------------------------------------------------------- #

def test_a_prose_reference_to_a_step_is_not_an_answer_to_it() -> None:
    """The harness's ``_TASK_ITEM_RE`` accepted an unbracketed number, so a step
    ending "...from step 3." claimed item 03 as well as its own 04."""
    parsed = parse_claims(
        "[c_1] 480\n"
        "Add the value from step 1 to get the running total.\n"
        "[c_2] 908")
    assert parsed == {"c_1": 480.0, "c_2": 908.0}


def test_the_parser_accepts_the_shapes_a_model_actually_emits() -> None:
    parsed = parse_claims("(c_grand): 1,430.5\n[c_max]=945\n [c_mean] 357.6")
    assert parsed["c_grand"] == pytest.approx(1430.5)
    assert parsed["c_max"] == pytest.approx(945)
    assert parsed["c_mean"] == pytest.approx(357.6)


# --------------------------------------------------------------------------- #
# the instances themselves
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("task_class", ["map", "reduce", "chain", "compose"])
def test_every_answer_is_computed_from_the_material_it_describes(task_class) -> None:
    """A key that is asserted rather than computed drifts from its prompt. That
    is what made the V5 corpus rebuild necessary."""
    instance = build_instance(task_class, seed=11)
    facts = instance.facts

    assert instance.claims, f"{task_class} produced no claims"
    for claim in instance.claims:
        assert claim.requires, f"{claim.claim_id} requires nothing"
        for fact_id in claim.requires:
            assert fact_id in facts, f"{claim.claim_id} needs a fact that is absent"

    # Spot-check the arithmetic against the source rather than trusting it.
    if task_class in ("map", "compose"):
        for claim in instance.claims:
            if claim.kind == "local":
                assert claim.answer == pytest.approx(
                    sum(facts[f].value for f in claim.requires))


def test_reduce_claims_genuinely_span_sections_and_map_claims_do_not() -> None:
    """Otherwise the two classes measure the same thing and the contrast that
    has held across every run -- aggregate claims wrong 36 % against 8 % for
    local ones -- has nothing to rest on."""
    mapped = build_instance("map", seed=5)
    reduced = build_instance("reduce", seed=5)

    assert all(c.sections_needed == 1 for c in mapped.claims)
    assert all(c.sections_needed > 1 for c in reduced.claims)


def test_a_chain_step_depends_on_the_step_before_it() -> None:
    chain = build_instance("chain", seed=9)
    steps = list(chain.claims)
    assert len(steps) >= 3
    assert steps[0].requires_claims == ()
    for earlier, later in zip(steps, steps[1:]):
        assert later.requires_claims == (earlier.claim_id,)
    # Each step adds one value: the arithmetic the models solve monolithically,
    # so the control separates state transport from arithmetic ability.
    facts = chain.facts
    for earlier, later in zip(steps, steps[1:]):
        added = sum(facts[f].value for f in later.requires)
        assert later.answer == pytest.approx(earlier.answer + added)


def test_instances_are_a_pure_function_of_their_seed() -> None:
    assert (build_instance("reduce", seed=42).prompt()
            == build_instance("reduce", seed=42).prompt())
    assert (build_instance("reduce", seed=42).prompt()
            != build_instance("reduce", seed=43).prompt())


def test_the_digest_moves_when_a_split_or_an_answer_moves() -> None:
    """Frozen the way tables24.json is: a threshold is only valid for the corpus
    it was fitted on, and a bare filename cannot carry that."""
    import dataclasses

    base = [build_instance("map", seed=s, split="dev") for s in (1, 2, 3)]
    assert instance_digest(base) == instance_digest(list(base))

    moved_split = list(base)
    moved_split[0] = dataclasses.replace(moved_split[0], split="final")
    assert instance_digest(moved_split) != instance_digest(base)


# --------------------------------------------------------------------------- #
# the boundary itself (ADR-001)
# --------------------------------------------------------------------------- #

def test_the_benchmark_does_not_import_the_harness_it_is_checking() -> None:
    """ADR-001, asserted against the import graph rather than trusted.

    The benchmark exists to be able to DISAGREE with the harness. If it scored
    through `swarmbly_v0.metrics`, the arm-neutrality defect that cost this
    project four documents would have propagated into V7 silently, and V7 would
    have "confirmed" V0 -- the worst available outcome, because agreement
    between a measurement and its own instrument reads as replication.

    This test looks trivial and is load-bearing. Deleting it is not a cleanup:
    the previous version of this boundary was a docstring, and every defect in
    the list at the top of ADR-001 got through a boundary that was a docstring.
    """
    import ast
    from pathlib import Path

    banned = {"metrics", "grading", "constraints", "experiment", "packing",
              "planner", "assembler", "consensus", "editor", "report"}
    package = Path(__file__).resolve().parent.parent / "benchmark_v7"
    offences: list[str] = []

    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if not name.startswith("swarmbly_v0"):
                    continue
                tail = name.split(".")[1] if "." in name else ""
                if tail in banned or tail == "":
                    offences.append(f"{path.name}:{node.lineno} imports {name}")

    assert not offences, (
        "benchmark_v7 must not import the harness's scoring:\n  "
        + "\n  ".join(offences)
        + "\nSee docs/ADR-001_instrument_boundary.md.")
