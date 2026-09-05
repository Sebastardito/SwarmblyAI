"""The composition oracle arm: does the allocation actually allocate?

`comp-final` put composition at +22.40 points against monolithic and published
it with a limit: each fragment wrote a complete answer, so the number measures
this implementation rather than fragmentation. The oracle arm removes the limit
by adding a third arm whose allocation is correct by construction.

An oracle that is wrong is worse than no oracle, because the whole point of the
arm is to be the thing the other two are measured against. These tests are about
the allocation and the arithmetic, which are the two places it can be wrong
without looking wrong.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "run_composition_oracle",
    Path(__file__).resolve().parent.parent / "scripts" / "run_composition_oracle.py")
oracle = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(oracle)


HARBOUR = [
    {"id": "paragraphs", "kind": "paragraph_count", "count": 2},
    {"id": "length", "kind": "words_per_paragraph", "min": 60, "max": 140},
    {"id": "mentions_tide", "kind": "must_mention", "term": "tide window"},
    {"id": "mentions_berth", "kind": "must_mention", "term": "berth"},
    {"id": "avoids", "kind": "must_not_mention", "term": "obviously"},
    {"id": "no_repeated_sentence", "kind": "no_repeated_sentence"},
    {"id": "no_repeated_phrase", "kind": "no_repeated_ngram", "size": 8},
    {"id": "tide_once", "kind": "term_once", "term": "tide window"},
]


# --------------------------------------------------------------------------
# The allocation
# --------------------------------------------------------------------------


def test_every_required_term_is_owned_by_exactly_one_fragment():
    """`must_mention` failed 9 -> 64 from N=3 to N=8 because nobody owned it."""
    briefs = oracle.allocate(HARBOUR, 2)
    owners = [term for brief in briefs for term in brief["must_mention"]]
    assert sorted(owners) == ["berth", "tide window"]
    assert len(owners) == len(set(owners)), "a term owned twice is not allocated"


def test_a_term_once_term_is_forbidden_to_every_non_owner():
    """This is the mechanism. `term_once` failed 34 times at N=3: two fragments
    each used the term, each of them correctly, and the text held it twice."""
    briefs = oracle.allocate(HARBOUR, 2)
    owner = [b for b in briefs if "tide window" in b["must_mention"]]
    others = [b for b in briefs if "tide window" not in b["must_mention"]]
    assert len(owner) == 1 and others
    for brief in others:
        assert "tide window" in brief["must_avoid"], (
            "a fragment that does not own a term_once term must be told not to "
            "write it, or 'exactly once' is not satisfiable locally")


def test_a_term_that_is_not_term_once_is_not_forbidden_to_the_others():
    """Repeating it is legal. Forbidding it would be the oracle inventing a
    constraint the prompt does not carry, and flattering itself with it."""
    briefs = oracle.allocate(HARBOUR, 2)
    for brief in briefs:
        assert "berth" not in brief["must_avoid"]


def test_a_prohibition_goes_to_every_fragment():
    briefs = oracle.allocate(HARBOUR, 2)
    for brief in briefs:
        assert "obviously" in brief["must_avoid"]


def test_the_repetition_constraints_reach_no_fragment_and_that_is_deliberate():
    """They are properties of a PAIR of fragments. A parallel worker cannot
    check a pair, and an oracle that pretended otherwise would be sequential --
    monolithic with extra steps, recovering the constraint by abolishing the
    thing under test."""
    briefs = oracle.allocate(HARBOUR, 2)
    for brief in briefs:
        assert set(brief) == {"must_mention", "must_avoid"}, (
            "a brief carries an allocation and nothing else; a repetition "
            "constraint smuggled in here would be unenforceable and would make "
            "the oracle look like it had been given a fair chance at it")
    terms = {t for b in briefs for t in b["must_mention"] + b["must_avoid"]}
    assert terms <= {"tide window", "berth", "obviously"}, (
        f"only the prompt's own terms may be allocated, found {terms}")


def test_allocation_is_a_function_of_the_prompt_and_not_of_a_seed():
    assert oracle.allocate(HARBOUR, 3) == oracle.allocate(HARBOUR, 3)


def test_more_fragments_than_terms_leaves_some_fragments_unowned():
    """Not an error: a paragraph with no required term still has to be written,
    and the alternative is duplicating a term to fill the slot."""
    briefs = oracle.allocate(HARBOUR, 5)
    assert len(briefs) == 5
    assert sum(len(b["must_mention"]) for b in briefs) == 2


# --------------------------------------------------------------------------
# The brief the fragment actually sees
# --------------------------------------------------------------------------


def test_a_fragment_is_told_it_is_writing_one_paragraph_of_several():
    """The stated limit of comp-final was 7.96 paragraphs against 2.0: each
    fragment wrote a complete answer. If the oracle's brief does not say
    otherwise, the oracle reproduces the defect it exists to control for."""
    brief = oracle.allocate(HARBOUR, 2)[0]
    text = oracle.oracle_prompt("Describe a harbour.", brief, position=0,
                                total=2, low=60, high=140)
    assert "paragraph 1 of 2" in text
    assert "nothing else" in text
    assert "60" in text and "140" in text


def test_the_brief_carries_the_terms_the_fragment_must_avoid():
    briefs = oracle.allocate(HARBOUR, 2)
    other = [b for b in briefs if "tide window" not in b["must_mention"]][0]
    text = oracle.oracle_prompt("Describe a harbour.", other, position=1,
                                total=2, low=60, high=140)
    assert "tide window" in text and "Do not use" in text


def test_the_topic_is_the_prompt_without_its_constraint_paragraph():
    """Handing a fragment the full constraint text tells it to write two
    paragraphs of its own -- the exact failure being controlled for."""
    full = ("Describe how a harbour reschedules cargo.\n\n"
            "Write exactly two paragraphs, separated by a blank line, each "
            "between 60 and 140 words. Mention all of these: tide window.")
    assert oracle.topic_of(full) == "Describe how a harbour reschedules cargo."
    assert "two paragraphs" not in oracle.topic_of(full)


# --------------------------------------------------------------------------
# The arithmetic, which is the part that can be wrong without looking wrong
# --------------------------------------------------------------------------


def test_the_two_halves_sum_to_the_end_to_end_loss():
    d = oracle._decompose(mono=0.90, oracle=0.80, real=0.60)
    assert d["end_to_end_loss"] == pytest.approx(0.30)
    assert (d["parallelism_cost_monolithic_to_oracle"]
            + d["allocation_cost_oracle_to_real"]) == pytest.approx(0.30)


def test_allocation_dominating_is_named_as_a_planner_fix():
    d = oracle._decompose(mono=0.90, oracle=0.88, real=0.60)
    assert "ALLOCATION dominates" in d["reading"]
    assert d["share_recoverable_by_allocation"] > 0.9


def test_parallelism_dominating_is_named_as_not_fragmentable():
    d = oracle._decompose(mono=0.90, oracle=0.62, real=0.60)
    assert "PARALLELISM dominates" in d["reading"]


def test_no_loss_is_refused_rather_than_attributed():
    """The first version compared `allocation > parallelism * 2` unguarded. On a
    rehearsal where the fragmented arm scored ABOVE monolithic it read
    "ALLOCATION dominates" from allocation 0.000 against parallelism -0.131,
    because 0 > -0.26. A sign test wearing a magnitude test's clothes."""
    d = oracle._decompose(mono=0.13, oracle=0.26, real=0.26)
    assert "NOTHING TO DECOMPOSE" in d["reading"]
    assert d["share_recoverable_by_allocation"] is None


def test_an_oracle_worse_than_the_planner_says_so_about_the_oracle():
    """If the shipped planner beats the oracle, the briefs are the suspect."""
    d = oracle._decompose(mono=0.90, oracle=0.50, real=0.60)
    assert "PARALLELISM accounts for MORE" in d["reading"]
    assert "oracle's" in d["reading"] or "briefs" in d["reading"]


def test_a_missing_arm_produces_no_decomposition():
    assert oracle._decompose(0.9, None, 0.6)["verdict"] is None


# --------------------------------------------------------------------------
# End to end, against the mock
# --------------------------------------------------------------------------


def test_the_three_arms_run_end_to_end_and_are_scored_by_one_scorer():
    """Rehearsal, and the rule from POSTMORTEM_2026-09-05: no tier is handed
    over until it has been run. The mock cannot satisfy a content constraint,
    so the numbers are meaningless -- what is under test is that all three arms
    produce a scored text through the same path."""
    from swarmbly_v0.backends import get_backend, get_embedder
    from swarmbly_v0.experiment import PromptSpec

    spec = PromptSpec(
        prompt_id="t1", category="composition", expected_decomposable=True,
        text=("Describe how a harbour reschedules cargo.\n\n"
              "Write exactly two paragraphs, separated by a blank line, each "
              "between 60 and 140 words. Mention all of these: tide window, berth."),
        constraints=HARBOUR, split="dev")

    result = oracle.run_instance(spec, get_backend("mock"), get_embedder("hash"),
                                 rho=4.0, n_tasks=3, tau_sem=0.6, arms=oracle.ARMS)
    assert "monolithic" in result and "oracle" in result
    assert "real" in result or "real-refused" in result
    for arm, report in result.items():
        assert report["constraint_score_comparable"] is not None, arm
        assert report["n_constraints"] == len(HARBOUR), (
            f"{arm} was scored against a different constraint list; the whole "
            f"decomposition rests on one scorer over one list")


def test_the_oracle_arm_reports_no_rho_rather_than_a_plausible_one():
    """It never goes through the packer. A rho here would be a number with no
    packet behind it, printed beside two that have one."""
    from swarmbly_v0.backends import get_backend, get_embedder
    from swarmbly_v0.experiment import PromptSpec

    spec = PromptSpec(prompt_id="t1", category="composition",
                      expected_decomposable=True,
                      text="Describe a harbour.\n\nWrite exactly two paragraphs.",
                      constraints=HARBOUR, split="dev")
    result = oracle.run_instance(spec, get_backend("mock"), get_embedder("hash"),
                                 rho=4.0, n_tasks=3, tau_sem=0.6, arms=("oracle",))
    assert result["oracle"]["rho_achieved"] is None


def test_the_declared_cell_is_the_one_comp_final_declared():
    """Decomposing a different cell and comparing it to the published +22.40 is
    the tables-final defect: two arms at different points on the axis with the
    largest effect, reported under one label."""
    assert oracle.DECLARED == {"rho": 4.0, "n_tasks": 3, "k": 1}


def test_the_runner_lives_outside_the_benchmark_package():
    """ADR-001 in the opposite direction. V7 may not import the harness's
    scorer, because it must be able to disagree with it. This script MUST use
    the harness's scorer, because it decomposes a number the harness produced --
    a reimplementation that drifted by one check would attribute the drift to
    the oracle. So it lives here, where the ban does not apply."""
    root = Path(__file__).resolve().parent.parent
    assert (root / "scripts" / "run_composition_oracle.py").exists()
    assert not (root / "benchmark_v7" / "run_composition_oracle.py").exists()
    source = (root / "scripts" / "run_composition_oracle.py").read_text(encoding="utf-8")
    assert "ADR-001" in source, "the reason must travel with the file"
