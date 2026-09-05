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

from swarmbly_v0.constraints import enforce_term_once

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
    briefs = oracle.allocate(HARBOUR, 2, policy="exclusive")
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
    assert "monolithic" in result
    for arm in oracle.ORACLE_ARMS:
        assert arm in result, f"{arm} was requested and did not run"
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
                                 rho=4.0, n_tasks=3, tau_sem=0.6,
                                 arms=oracle.ORACLE_ARMS)
    for arm in oracle.ORACLE_ARMS:
        assert result[arm]["rho_achieved"] is None, arm


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


# --------------------------------------------------------------------------
# The allocation POLICY, which the 5 September run showed is the thing under
# test rather than a detail
#
# The exclusive oracle scored 0.571 against the shipped pipeline's 0.649, with
# monolithic at 0.844 -- below the arm it was built to be an upper bound for.
# Split by whether the term is also `term_once`:
#
#     also term_once   mono 21/24   oracle 11/24   real 21/24
#     not term_once    mono 11/12   oracle  8/12   real  8/12
#
# On the terms exclusivity does not touch, oracle and real are IDENTICAL. The
# exclusivity clause converts a term with N chances into a term with one, and
# it bought three satisfied `term_once` for ten lost `must_mention`.
# --------------------------------------------------------------------------


def test_the_redundant_policy_requires_every_term_of_every_fragment():
    briefs = oracle.allocate(HARBOUR, 2, policy="redundant")
    for brief in briefs:
        assert sorted(brief["must_mention"]) == ["berth", "tide window"], (
            "redundancy is the policy that gives a term N chances instead of 1")


def test_the_redundant_policy_forbids_nothing_but_the_prohibition():
    """Its whole point is that no fragment is told to withhold a term."""
    briefs = oracle.allocate(HARBOUR, 2, policy="redundant")
    for brief in briefs:
        assert brief["must_avoid"] == ["obviously"]


def test_an_unknown_policy_is_refused_rather_than_defaulted():
    with pytest.raises(ValueError):
        oracle.allocate(HARBOUR, 2, policy="whatever")


def test_the_two_policies_actually_differ():
    assert (oracle.allocate(HARBOUR, 2, policy="exclusive")
            != oracle.allocate(HARBOUR, 2, policy="redundant"))


# --------------------------------------------------------------------------
# The dedup, which is the proposal the trade produced
#
# It lives in `swarmbly_v0.constraints` rather than in this script, because the
# shipped assembler now calls it behind a flag and the oracle arm measures it.
# Two implementations of one behaviour would drift, and the drift would be
# attributed to whichever arm noticed second.
# --------------------------------------------------------------------------


def test_dedup_keeps_the_first_sentence_carrying_a_term_and_drops_the_rest():
    text = ("The tide window closes at noon. Berths are reassigned.\n\n"
            "The tide window matters again here. Cargo waits.")
    out, removed = enforce_term_once(text, HARBOUR)
    assert removed == 1
    assert out.lower().count("tide window") == 1
    assert "Berths are reassigned." in out and "Cargo waits." in out


def test_dedup_leaves_a_text_that_already_complies_untouched():
    text = "The tide window closes at noon.\n\nBerths are reassigned."
    out, removed = enforce_term_once(text, HARBOUR)
    assert removed == 0
    assert out == text


def test_dedup_does_not_consume_a_terms_only_occurrence():
    """A sentence carrying two once-terms, one already seen and one not, must
    not mark the second as seen on its way to being deleted -- that turns a
    duplicate into an omission, which is the failure the whole arm is about."""
    constraints = [
        {"id": "a_once", "kind": "term_once", "term": "alpha"},
        {"id": "b_once", "kind": "term_once", "term": "beta"},
    ]
    text = ("Alpha is introduced here.\n\n"
            "Alpha and beta appear together.\n\n"
            "Beta stands alone at the end.")
    out, removed = enforce_term_once(text, constraints)
    assert removed == 1
    assert out.lower().count("alpha") == 1
    assert out.lower().count("beta") == 1, (
        "beta's only surviving sentence must not have been marked seen while "
        "the sentence that carried it was being deleted")


def test_dedup_is_a_no_op_when_the_prompt_has_no_term_once():
    text = "One sentence. Another sentence."
    assert enforce_term_once(text, [
        {"id": "m", "kind": "must_mention", "term": "x"}]) == (text, 0)


# --------------------------------------------------------------------------
# The reporting: a split that a mean hides, and a policy chosen in advance
# --------------------------------------------------------------------------


def test_must_mention_is_split_by_whether_the_term_is_also_term_once():
    """19/36 against 29/36 looks like a worse oracle. 11/24 against 21/24 on
    one bucket and 8/12 against 8/12 on the other is a diagnosis."""
    text = "The berth is ready.\n\nNothing else is said."
    report = oracle._score(text, HARBOUR)
    split = report["must_mention_split"]
    assert split["must_mention_also_term_once"]["checked"] == 1   # tide window
    assert split["must_mention_repetition_allowed"]["checked"] == 1  # berth
    assert split["must_mention_repetition_allowed"]["satisfied"] == 1
    assert split["must_mention_also_term_once"]["satisfied"] == 0


def test_the_headline_is_the_declared_first_oracle_THAT_PASSES_VALIDITY():
    """Three oracles is three chances to pick a winner after the fact.

    The first rule pinned the headline to the policy declared first, full stop.
    On 5 September that produced a headline reading "check the oracle's briefs"
    while a different policy, in the same run, had produced a clean
    decomposition two lines below it.

    So the rule is stated on the INSTRUMENT: an oracle is an upper bound on what
    allocation can achieve, so one scoring below the shipped pipeline has not
    measured allocation, it has measured its own briefs. Among the oracles that
    ARE upper bounds, declaration order decides. Choosing among valid
    instruments by declaration order is not choosing a result; choosing among
    all of them by score would be.
    """
    rows = [{"prompt_id": "p1", "split": "dev", "arms": {
        "monolithic": _fake(0.90), "real": _fake(0.60),
        "oracle-exclusive": _fake(0.50),    # below real: not an upper bound
        "oracle-redundant": _fake(0.88),    # valid
        "oracle-redundant-dedup": _fake(0.75),  # valid, declared later
    }}]
    summary = oracle.summarise(rows)
    assert summary["decomposition_valid_oracles"] == [
        "oracle-redundant", "oracle-redundant-dedup"]
    assert summary["decomposition_headline_arm"] == "oracle-redundant", (
        "among valid oracles, the one declared first")
    assert (summary["decomposition"]
            == summary["decomposition_by_policy"]["oracle-redundant"])


def test_the_declared_first_oracle_still_wins_when_it_is_valid():
    """The validity check must not become a way of preferring a better score."""
    rows = [{"prompt_id": "p1", "split": "dev", "arms": {
        "monolithic": _fake(0.90), "real": _fake(0.60),
        "oracle-exclusive": _fake(0.70),        # valid, and WORSE than
        "oracle-redundant": _fake(0.85),        # this one, which is also valid
    }}]
    summary = oracle.summarise(rows)
    assert summary["decomposition_headline_arm"] == "oracle-exclusive"


def test_when_no_oracle_is_an_upper_bound_the_summary_says_so():
    rows = [{"prompt_id": "p1", "split": "dev", "arms": {
        "monolithic": _fake(0.90), "real": _fake(0.60),
        "oracle-exclusive": _fake(0.50), "oracle-redundant": _fake(0.55),
    }}]
    summary = oracle.summarise(rows)
    assert summary["decomposition_headline_arm"] is None
    assert summary["decomposition_valid_oracles"] == []
    assert "NO ORACLE PASSED" in summary["decomposition"]["headline_note"]


def test_the_residual_names_the_classes_the_oracle_could_not_reach():
    """A residual of 0.19 is a number to quote. `no_repeated_ngram` at 4/12
    against 11/12 is a mechanism with a name, and only one of those is
    actionable."""
    rows = [{"prompt_id": "p1", "split": "dev", "arms": {
        "monolithic": _fake(0.90, by_kind={
            "must_mention": {"satisfied": 3, "checked": 3},
            "no_repeated_ngram": {"satisfied": 1, "checked": 1}}),
        "real": _fake(0.60),
        "oracle-redundant": _fake(0.85, by_kind={
            "must_mention": {"satisfied": 2, "checked": 3},
            "no_repeated_ngram": {"satisfied": 0, "checked": 1}}),
    }}]
    residual = oracle.summarise(rows)["residual_by_kind"]
    assert residual["against"] == "oracle-redundant"
    kinds = list(residual["by_kind"])
    assert kinds[0] == "must_mention", "worst class first, in checks not points"
    assert residual["by_kind"]["must_mention"]["constraints_lost"] == 1
    assert residual["by_kind"]["no_repeated_ngram"]["constraints_lost"] == 1


def test_the_residual_is_refused_when_no_oracle_is_valid():
    rows = [{"prompt_id": "p1", "split": "dev", "arms": {
        "monolithic": _fake(0.90), "real": _fake(0.60),
        "oracle-exclusive": _fake(0.50)}}]
    assert "by_kind" not in oracle.summarise(rows)["residual_by_kind"]


def _fake(score: float, by_kind: dict | None = None) -> dict:
    return {"constraint_score": score, "constraint_score_comparable": score,
            "n_constraints": 8, "n_paragraphs": 2, "failed": [],
            "by_kind": by_kind or {}, "must_mention_split": {}}


# --------------------------------------------------------------------------
# term_once at the assembler: the shipped path, behind a flag
# --------------------------------------------------------------------------


def test_the_shipped_pipeline_can_enforce_term_once_and_records_that_it_did():
    """Off by default, because every published composition figure was produced
    without it and a default that changes the delivered answer would silently
    reclassify the record."""
    from swarmbly_v0.backends import get_backend, get_embedder
    from swarmbly_v0.experiment import (PromptSpec, SweepConfig, run_fragmented,
                                        global_contract)

    spec = PromptSpec(prompt_id="t1", category="composition",
                      expected_decomposable=True,
                      text=("Describe a harbour.\n\nWrite exactly two paragraphs, "
                            "each between 60 and 140 words."),
                      constraints=HARBOUR, split="dev")
    backend, embedder = get_backend("mock"), get_embedder("hash")
    config = SweepConfig(rhos=(4.0,), ns=(2,), ks=(1,), n_candidates=1, seed=0)
    contract = global_contract(spec.text, backend)

    off = run_fragmented(spec, backend, embedder, config, rho_target=4.0,
                         n_tasks=2, tau_sem=0.6, contract=contract)
    on = run_fragmented(spec, backend, embedder, config, rho_target=4.0,
                        n_tasks=2, tau_sem=0.6, contract=contract,
                        enforce_term_once_mechanically=True)

    assert off["term_once_enforced"] is False
    assert on["term_once_enforced"] is True
    assert off["term_once_sentences_removed"] == "", (
        "blank, not 0: 'ran and removed nothing' and 'did not run' are "
        "different facts, and this file has confused them twice")
    assert isinstance(on["term_once_sentences_removed"], int)


def test_the_oracle_and_the_assembler_call_the_same_function():
    """Two implementations of one behaviour drift, and the drift is attributed
    to whichever arm notices second. comp-oracle measured 14/24; the shipped
    path must be measuring the same thing."""
    import swarmbly_v0.experiment as experiment
    from swarmbly_v0.constraints import enforce_term_once as canonical

    assert experiment.enforce_term_once is canonical
    source = (Path(__file__).resolve().parent.parent
              / "scripts" / "run_composition_oracle.py").read_text(encoding="utf-8")
    assert "from swarmbly_v0.constraints import" in source
    assert "enforce_term_once" in source
    assert "def enforce_term_once" not in source, (
        "the script must import it, not own a second copy")


# --------------------------------------------------------------------------
# The fifth thing a -final tier inherits from its -dev run
#
# Threshold, corpus, split and code were already checked. The assembly PIPELINE
# was not, and `--enforce-term-once` changes the delivered answer for every
# cell -- so a threshold fitted by one pipeline could have been paired silently
# with the other, and the pairing is the entire value of having a split.
# --------------------------------------------------------------------------


RUNNER = Path(__file__).resolve().parent.parent / "scripts" / "run_ollama.sh"


def test_the_sweep_records_which_assembly_pipeline_produced_it():
    from swarmbly_v0.backends import get_backend, get_embedder
    from swarmbly_v0.experiment import SweepConfig, load_prompts, run_sweep

    prompts = load_prompts("prompts/composition.json")[:1]
    for flag in (False, True):
        cfg = SweepConfig(rhos=(4.0,), ns=(3,), ks=(1,), n_candidates=1,
                          seed=0, enforce_term_once=flag)
        _, metadata = run_sweep(prompts, cfg, get_backend("mock"),
                                get_embedder("hash"))
        assert metadata["enforce_term_once"] is flag, (
            "a -final tier reads this to refuse a dev run from the other "
            "pipeline; if it is absent the check silently passes")


def test_the_final_tiers_check_the_pipeline_matches_their_dev_run():
    script = RUNNER.read_text(encoding="utf-8")
    assert "read_dev_run" in script, "the shared gate must exist"
    body = script[script.index("read_dev_run() {"):]
    body = body[:body.index("\n}\n")]
    assert "PIPELINE MISMATCH" in body
    assert "enforce_term_once" in body
    # Ausente no es falso. El campo llego el 5 de septiembre; una corrida
    # anterior no dice nada sobre su tuberia en vez de decir que no, y leerla
    # como "no" mandaria al operador a arreglar lo que no esta roto.
    assert "'absent'" in body and 'dev_once" = "absent"' in body, (
        "una corrida sin el campo debe refutarse por su propia razon, no "
        "confundirse con un desajuste")

    # And both callers must pass what they expect rather than defaulting.
    for tier, expected in (("run_comp_final()", '"false"'),
                           ("run_comp_final_once()", '"true"')):
        start = script.index(tier)
        chunk = script[start:start + 4000]
        assert f'read_dev_run "$dev" {expected}' in chunk, (
            f"{tier} must state the pipeline it expects; a default would let "
            f"the two halves of the split be paired across pipelines")


def test_comp_final_once_passes_the_flag_it_gates_on():
    """A tier that checked for the flag and then did not pass it would refuse
    the right dev runs and then measure the wrong pipeline."""
    script = RUNNER.read_text(encoding="utf-8")
    start = script.index("run_comp_final_once()")
    body = script[start:script.index("\n}\n", start)]
    assert "--enforce-term-once" in body
    assert "--split final" in body
    assert "comp-final-once" in body


# --------------------------------------------------------------------------
# Corpus v2: el reemplazo, porque el split final de v1 se usa dos veces
# --------------------------------------------------------------------------


def _generator():
    import importlib.util
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "make_composition", root / "scripts" / "make_composition.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v1_digest_is_unchanged_by_the_v2_work():
    """El umbral de comp-final esta congelado contra e9e382b9... Un solo
    caracter movido en v1 lo invalida, y anadir v2 al mismo generador es
    exactamente el cambio que podria moverlo sin que nadie lo note."""
    g = _generator()
    assert g.digest(g.build(corpus="v1")).startswith("e9e382b92b1af6e3")


def test_v2_shares_no_prompt_id_and_no_required_term_with_v1():
    g = _generator()
    v1, v2 = g.build(corpus="v1"), g.build(corpus="v2")
    assert not ({p["id"] for p in v1} & {p["id"] for p in v2})

    def terms(prompts):
        return {c["term"] for p in prompts for c in p["constraints"]
                if c["kind"] in ("must_mention", "term_once")}
    shared = terms(v1) & terms(v2)
    assert not shared, (
        f"un termino compartido hace que las dos mediciones no sean "
        f"independientes: {sorted(shared)}")


def test_both_corpora_are_built_by_the_same_function():
    """Un segundo generador que construyera los prompts a su manera haria que
    las dos mediciones no fueran comparables, y la diferencia se atribuiria al
    corpus en vez de a la tuberia."""
    g = _generator()
    v1, v2 = g.build(corpus="v1")[0], g.build(corpus="v2")[0]
    assert [c["kind"] for c in v1["constraints"]] == [c["kind"] for c in v2["constraints"]]
    assert v1["tier"] == v2["tier"]
    # y el mismo texto de plantilla, salvo el sujeto y los terminos
    for marker in ("Write exactly two paragraphs", "must appear exactly once",
                   "Do not repeat any sentence"):
        assert marker in v1["prompt"] and marker in v2["prompt"]


def test_v2_splits_are_balanced_across_tiers():
    g = _generator()
    prompts = g.build(corpus="v2")
    for split, expected in (("dev", 4), ("final", 8)):
        counts = {t: sum(1 for p in prompts if p["split"] == split and p["tier"] == t)
                  for t in g.TIER_ORDER}
        assert set(counts.values()) == {expected}, (
            f"un split cuyas mitades difieren en dificultad no es un split: {counts}")


def test_the_v2_tiers_read_the_v2_corpus_and_nothing_else():
    script = RUNNER.read_text(encoding="utf-8")
    for tier in ("run_comp_dev_v2()", "run_comp_final_v2()"):
        start = script.index(tier)
        body = script[start:script.index("\n}\n", start)]
        assert "composition_v2.json" in body
        assert "prompts/composition.json" not in body, (
            f"{tier} nombra el corpus v1; el digest coincidiria con el corpus "
            f"equivocado y la compuerta pasaria por la razon opuesta")
