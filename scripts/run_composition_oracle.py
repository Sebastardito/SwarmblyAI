#!/usr/bin/env python3
"""The composition oracle arm: what are the 22.4 points made of?

``comp-final`` measured composition at rho 4.0, N 3, k 1 as costing **+22.40
points** of constraint satisfaction against its monolithic baseline, CI
[+16.15, +28.51], NOT MET by 23.51 points on the upper bound. That result is
end-to-end, and it carries a stated limit which this script exists to remove:

    mean_paragraphs was 2.0 monolithic against 7.96 fragmented. Each fragment
    wrote a complete answer. So the 22.4 points measure THIS IMPLEMENTATION
    fragmenting prose, not the cost of fragmenting prose.

Five arms, one corpus, one mechanical scorer, no judge anywhere.

``monolithic``               one call, the whole prompt. The ceiling.
``oracle-exclusive``         each required term owned by exactly one fragment;
                             where it is also ``term_once`` the others are
                             forbidden it.
``oracle-redundant``         every fragment required to mention every term.
``oracle-redundant-dedup``   the redundant arm's TEXT, with ``term_once``
                             enforced mechanically at assembly.
``real``                     the shipped router, planner, packer, assembler.

WHY FIVE, AND NOT THE THREE THIS FILE STARTED WITH
--------------------------------------------------

The run of 5 September dispatched one oracle, under the exclusive policy, and
it scored BELOW the shipped pipeline: 0.571 against 0.649, with monolithic at
0.844. The guard refused to decompose -- correctly -- and named the oracle's
briefs as the thing to check. They were.

The whole collapse was in one bucket. Splitting ``must_mention`` by whether the
term is also ``term_once``:

    must_mention, term is ALSO term_once   mono 21/24   oracle 11/24   real 21/24
    must_mention, term is NOT term_once    mono 11/12   oracle  8/12   real  8/12

On the terms exclusivity does not touch, the oracle and the shipped pipeline are
IDENTICAL. On the terms it forbids to every non-owner, the oracle halves. The
exclusivity clause converts a term with N chances into a term with one, and a 3B
owner complies about half the time.

And it did buy what it was for -- ``term_once`` 9/24 against real's 6/24 -- for
three satisfied constraints against ten lost. A bad trade, and the reason the
policy is now a parameter with both halves measured rather than a rule.

THE TRADE, WHICH IS THE ACTUAL FINDING
--------------------------------------

A term that must APPEAR and must appear EXACTLY ONCE is a conjunction that
parallel workers cannot satisfy blind:

* redundancy makes it appear and guarantees it appears twice;
* exclusivity makes it appear once and often not at all.

Only a writer who can see the finished text satisfies both, and monolithic does
-- 21/24 on mention, 13/24 on once. No allocation over parallel fragments closes
that gap, because the information each worker is missing is the other worker's
output.

``oracle-redundant-dedup`` is the proposal that falls out of it, and it is an
ASSEMBLY change rather than a planning one. ``paragraph_count`` and
``words_per_paragraph`` are already satisfied mechanically by the assembler
rather than by asking a model nicely. ``term_once`` is the same shape of
constraint -- a property of the finished text, checkable by counting -- and only
history puts it on the generation side.

What the oracle deliberately does NOT fix
-----------------------------------------

The oracle is **parallel**. Fragments are dispatched independently and no
fragment sees another's text, because that is the architecture's actual claim --
a sequential oracle that showed fragment i the output of 1..i-1 would be
monolithic with extra steps, and would recover the repetition constraints by
abolishing the thing under test.

So `no_repeated_sentence` and `no_repeated_ngram` are the classes allocation
cannot reach, and whatever the oracle loses on them is the price of parallelism
itself. That is the residual this script exists to measure. It is reported as
its own column rather than folded into a mean.

ADR-001
-------

This lives in ``scripts/`` and not in ``benchmark_v7/`` for the reason the V7
runner does, and the reason is the opposite of the one for V7's scorer. V7 must
be able to DISAGREE with the harness, so it may not import the harness's
metrics. This script must decompose a number the harness produced, so it MUST
use the harness's scorer -- ``swarmbly_v0.constraints`` and
``ASSEMBLER_ENFORCED`` -- or it is decomposing a different number and the
arithmetic does not close. A reimplementation here that drifted by one check
would attribute the drift to the oracle.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_v0.backends import get_backend, get_embedder  # noqa: E402
from swarmbly_v0.constraints import grade_text  # noqa: E402
from swarmbly_v0.experiment import (ASSEMBLER_ENFORCED, PromptSpec,  # noqa: E402
                                    SweepConfig, _answer_budget,
                                    run_fragmented, run_monolithic)
from swarmbly_v0.planner import global_contract  # noqa: E402
from swarmbly_v0.textutil import split_sentences  # noqa: E402

ARMS = ("monolithic", "oracle-exclusive", "oracle-redundant",
        "oracle-redundant-dedup", "real")
"""Five arms, because the run of 5 September showed the ALLOCATION POLICY is
itself under test rather than a detail of the oracle.

``oracle-exclusive``        one owner per term, others forbidden it.
``oracle-redundant``        every fragment required to mention every term.
``oracle-redundant-dedup``  the same generation, with `term_once` enforced
                            mechanically at assembly instead of by asking.

The first two are the two halves of a trade nobody had measured: exclusivity
buys "exactly once" and loses "appears at all"; redundancy does the reverse.
The third is the proposal that falls out of the trade."""

ORACLE_ARMS = ("oracle-exclusive", "oracle-redundant", "oracle-redundant-dedup")

DECLARED = {"rho": 4.0, "n_tasks": 3, "k": 1}
"""The cell comp-final declared. The oracle decomposes THAT cell or nothing.

Running the oracle at a different rho or N and comparing it to the published
+22.40 would be the tables-final defect again: two arms at different points on
the axis with the largest effect, reported under one label."""


# --------------------------------------------------------------------------- #
# The allocation
# --------------------------------------------------------------------------- #

def allocate(constraints: Sequence[Mapping[str, Any]], n_fragments: int,
             policy: str = "exclusive") -> list[dict[str, Any]]:
    """Give each fragment its share of the global constraints, under a POLICY.

    The policy is the thing under test, and the run of 5 September is why it is
    a parameter rather than a rule. `exclusive` was the only policy then, and it
    scored BELOW the shipped pipeline: `must_mention` fell to 11/24 on the terms
    it makes exclusive, against 21/24 for both monolithic and real. Telling every
    non-owner "do not write this term" converts a term with N chances into a term
    with ONE, and a 3B owner complies about half the time.

    It bought what it was supposed to buy -- `term_once` 9/24 against real's 6/24
    -- and paid ten `must_mention` for three `term_once`. A bad trade, and not
    one to hardcode.

    ``exclusive``
        Every required term owned by exactly one fragment; where the term is
        also ``term_once`` the others are forbidden it. Maximises "exactly
        once", minimises the chance the term appears at all.

    ``redundant``
        Every fragment required to mention every required term. Maximises the
        chance the term appears, and guarantees ``term_once`` fails whenever
        more than one fragment complies -- which is what the shipped pipeline
        already does by accident, since every fragment sees the whole prompt.

    Neither satisfies both. That is the finding, not a defect in either: a term
    that must appear AND appear exactly once is a conjunction parallel workers
    cannot satisfy blind, and only a writer who can see the whole text --
    monolithic, at 21/24 and 13/24 -- satisfies both. The third arm,
    ``redundant`` generation plus a mechanical dedup at assembly, is the
    proposal that falls out of it.

    The rule, in either policy:

    * every ``must_mention`` term is **owned by exactly one** fragment, assigned
      round-robin over the sorted terms so the allocation is a function of the
      prompt and not of a random seed;
    * a term that is also ``term_once`` is **forbidden** to every fragment that
      does not own it, which makes "exactly once" satisfiable locally -- the
      owner writes it once and nobody else can write it at all;
    * a term that is not ``term_once`` is required of its owner and merely not
      required of the others, because repeating it is legal and forbidding it
      would be the oracle enforcing a constraint the prompt does not carry;
    * ``must_not_mention`` goes to **everyone**. A prohibition needs no
      coordination: it is satisfied locally or not at all.

    ``no_repeated_sentence`` and ``no_repeated_ngram`` are absent from every
    fragment's brief on purpose. Allocation cannot express them -- they are
    properties of a pair of fragments, and no parallel worker can check a pair.

    The mechanism this repairs is the one comp-final localised: ``term_once``
    failed 34 times at N=3 (two fragments each used the term) and
    ``must_mention`` failed 9 -> 64 from N=3 to N=8 (no fragment used it). Both
    are allocation, and both are gone by construction here.
    """
    once_terms = {str(c.get("term")) for c in constraints
                  if c.get("kind") == "term_once"}
    required = sorted({str(c.get("term")) for c in constraints
                       if c.get("kind") == "must_mention"})
    forbidden = sorted({str(c.get("term")) for c in constraints
                        if c.get("kind") == "must_not_mention"})

    if policy not in ("exclusive", "redundant"):
        raise ValueError(f"unknown allocation policy {policy!r}")

    briefs: list[dict[str, Any]] = [
        {"must_mention": [], "must_avoid": list(forbidden)}
        for _ in range(n_fragments)
    ]
    if policy == "redundant":
        for brief in briefs:
            brief["must_mention"] = list(required)
        return briefs

    for position, term in enumerate(required):
        owner = position % n_fragments
        briefs[owner]["must_mention"].append(term)
        if term in once_terms:
            for index, brief in enumerate(briefs):
                if index != owner:
                    brief["must_avoid"].append(term)
    return briefs


def deduplicate_term_once(text: str, constraints: Sequence[Mapping[str, Any]]
                          ) -> tuple[str, int]:
    """Keep the FIRST sentence carrying each ``term_once`` term, drop the rest.

    The architecture proposal this run produced, made testable rather than
    argued. ``paragraph_count`` and ``words_per_paragraph`` are already
    satisfied mechanically by the assembler rather than by asking a model
    nicely; ``term_once`` is the same shape of constraint -- a property of the
    finished text, checkable by counting -- and nothing but history puts it on
    the generation side.

    So: let every fragment mention every term (``redundant``, which scores 21/24
    on `must_mention` because the term gets N chances), then delete the
    duplicates at assembly.

    Deleting the whole SENTENCE rather than the term, because removing a noun
    phrase from a sentence leaves a sentence that no longer parses, and this is
    a mechanical step with no model in it. The cost is that a deleted sentence
    may carry another required term or a needed clause -- which is exactly why
    this is measured rather than assumed. ``sentences_removed`` travels with the
    score.
    """
    once_terms = [str(c.get("term")) for c in constraints
                  if c.get("kind") == "term_once"]
    if not once_terms:
        return text, 0

    removed = 0
    paragraphs_out: list[str] = []
    seen: set[str] = set()
    for paragraph in [p for p in text.split("\n\n") if p.strip()]:
        kept: list[str] = []
        for sentence in split_sentences(paragraph):
            if not sentence.strip():
                continue
            lowered = sentence.lower()
            present = [t for t in once_terms if t.lower() in lowered]
            # A sentence carrying two once-terms, one already seen and one not,
            # must not mark the second as seen on its way to being deleted --
            # that would consume the term's only surviving occurrence and turn a
            # duplicate into an omission. Decide first, record after.
            if any(term in seen for term in present):
                removed += 1
                continue
            seen.update(present)
            kept.append(sentence.strip())
        if kept:
            paragraphs_out.append(" ".join(kept))
    return "\n\n".join(paragraphs_out), removed


def _length_bounds(constraints: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    for constraint in constraints:
        if constraint.get("kind") == "words_per_paragraph":
            return int(constraint.get("min", 60)), int(constraint.get("max", 140))
    return 60, 140


def _paragraph_count(constraints: Sequence[Mapping[str, Any]], default: int) -> int:
    for constraint in constraints:
        if constraint.get("kind") == "paragraph_count":
            return int(constraint.get("count", default))
    return default


def oracle_prompt(topic: str, brief: Mapping[str, Any], *, position: int,
                  total: int, low: int, high: int) -> str:
    """One fragment's brief: its paragraph, its terms, and the others' terms.

    The fragment is told the total so it knows it is writing a part, and told
    which terms belong to other paragraphs so it does not reach for them. It is
    NOT told what the other fragments wrote, because they are running at the
    same time.
    """
    must = brief["must_mention"]
    avoid = brief["must_avoid"]
    lines = [
        topic,
        "",
        f"Write paragraph {position + 1} of {total}. Write that paragraph and "
        f"nothing else: no heading, no preamble, no summary of the whole, and "
        f"no restatement of the subject if this is not the first paragraph.",
        f"It must be between {low} and {high} words.",
    ]
    if must:
        lines.append("This paragraph must mention, in its own words: "
                     + ", ".join(f'"{term}"' for term in must) + ".")
    if avoid:
        lines.append("Do not use these anywhere in this paragraph -- they "
                     "belong to a different paragraph or are forbidden "
                     "outright: " + ", ".join(f'"{term}"' for term in avoid) + ".")
    return "\n".join(lines)


def topic_of(prompt_text: str) -> str:
    """The instruction without its constraint paragraph.

    A composition prompt is a subject sentence followed by the constraints as
    prose. Handing a fragment the full constraint paragraph would tell it to
    write two paragraphs of its own, which is the very failure the oracle is
    controlling for.
    """
    return prompt_text.split("\n\n", 1)[0].strip()


# --------------------------------------------------------------------------- #
# The arms
# --------------------------------------------------------------------------- #

def _score(text: str, constraints: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    report = grade_text(text, constraints)
    by_kind: dict[str, list[bool]] = defaultdict(list)
    for result in report.results:
        by_kind[result.kind].append(bool(result.satisfied))

    # `must_mention`, split by whether the term is ALSO `term_once`.
    #
    # This split is the diagnosis of 5 September and it is computed rather than
    # noted, because it was invisible in the mean: the exclusive oracle read
    # 19/36 on must_mention against real's 29/36, which looks like a worse
    # oracle. Split, it is 11/24 against 21/24 on the terms exclusivity touches
    # and 8/12 against 8/12 -- identical -- on the terms it does not. One bucket
    # carries the entire gap, and only one policy creates it.
    once_terms = {str(c.get("term")) for c in constraints
                  if c.get("kind") == "term_once"}
    failed_ids = {r.constraint_id for r in report.failed}
    buckets: dict[str, list[bool]] = defaultdict(list)
    for constraint in constraints:
        if constraint.get("kind") != "must_mention":
            continue
        name = ("must_mention_also_term_once" if str(constraint.get("term")) in once_terms
                else "must_mention_repetition_allowed")
        buckets[name].append(str(constraint.get("id")) not in failed_ids)

    return {
        "constraint_score": report.score,
        "constraint_score_comparable": report.score_excluding(ASSEMBLER_ENFORCED),
        "n_constraints": len(report.results),
        "n_paragraphs": report.n_paragraphs,
        "failed": [r.constraint_id for r in report.failed],
        "by_kind": {kind: {"satisfied": sum(v), "checked": len(v)}
                    for kind, v in sorted(by_kind.items())},
        "must_mention_split": {name: {"satisfied": sum(v), "checked": len(v)}
                               for name, v in sorted(buckets.items())},
    }


def run_oracle(spec: PromptSpec, backend: Any, *, n_tasks: int,
               policy: str = "exclusive",
               max_tokens: int = 420) -> tuple[str, list[str]]:
    """Dispatch one fragment per paragraph and splice them with blank lines."""
    constraints = list(spec.constraints or [])
    paragraphs = _paragraph_count(constraints, n_tasks)
    low, high = _length_bounds(constraints)
    briefs = allocate(constraints, paragraphs, policy=policy)
    topic = topic_of(spec.text)

    written: list[str] = []
    dispatched: list[str] = []
    for position, brief in enumerate(briefs):
        packet = oracle_prompt(topic, brief, position=position,
                               total=paragraphs, low=low, high=high)
        dispatched.append(packet)
        text = str(backend.generate(packet, max_tokens=max_tokens, seed=0))
        # One paragraph per fragment. A fragment that wrote several is folded
        # back into one rather than dropped: the oracle controls allocation, not
        # the model's compliance, and silently discarding output would flatter
        # it exactly where `real` is charged.
        written.append(" ".join(part.strip() for part in text.split("\n\n")
                                if part.strip()))
    return "\n\n".join(written), dispatched


def run_instance(spec: PromptSpec, backend: Any, embedder: Any, *,
                 rho: float, n_tasks: int, tau_sem: float,
                 arms: Sequence[str]) -> dict[str, dict[str, Any]]:
    constraints = list(spec.constraints or [])
    config = SweepConfig(rhos=(rho,), ns=(n_tasks,), ks=(1,), n_candidates=1,
                         seed=0, tau_sem=tau_sem)
    contract = global_contract(spec.text, backend,
                               target_length_tokens=_answer_budget(spec, 420))
    out: dict[str, dict[str, Any]] = {}
    baseline: dict[str, Any] | None = None

    if "monolithic" in arms or "real" in arms:
        baseline = run_monolithic(spec, backend, embedder, config,
                                  contract=contract)
        if "monolithic" in arms:
            out["monolithic"] = _score(str(baseline.get("_text", "")), constraints)

    # The two generation policies are dispatched once each; the dedup arm reuses
    # the redundant arm's TEXT rather than generating again, so the comparison
    # between them is the assembly step alone and not two samples of a model.
    redundant_text: str | None = None
    for arm, policy in (("oracle-exclusive", "exclusive"),
                        ("oracle-redundant", "redundant")):
        if arm not in arms and not (arm == "oracle-redundant"
                                    and "oracle-redundant-dedup" in arms):
            continue
        text, dispatched = run_oracle(spec, backend, n_tasks=n_tasks,
                                      policy=policy)
        if policy == "redundant":
            redundant_text = text
        if arm in arms:
            out[arm] = _score(text, constraints)
            out[arm]["n_fragments"] = len(dispatched)
            out[arm]["allocation_policy"] = policy
            # rho is undefined for these arms and must not be reported as though
            # it were: an oracle never goes through the packer, so there is no
            # packet whose size could be divided by anything.
            out[arm]["rho_achieved"] = None

    if "oracle-redundant-dedup" in arms and redundant_text is not None:
        deduped, removed = deduplicate_term_once(redundant_text, constraints)
        out["oracle-redundant-dedup"] = _score(deduped, constraints)
        out["oracle-redundant-dedup"]["allocation_policy"] = "redundant+dedup"
        out["oracle-redundant-dedup"]["sentences_removed"] = removed
        out["oracle-redundant-dedup"]["rho_achieved"] = None

    if "real" in arms:
        row = run_fragmented(spec, backend, embedder, config, rho_target=rho,
                             n_tasks=n_tasks, tau_sem=tau_sem, k=1,
                             contract=contract, baseline=baseline)
        refused = str(row.get("plan_refused", "")).strip().lower() in ("true", "1", "yes")
        name = "real-refused" if refused else "real"
        out[name] = _score(str(row.get("_text", "")), constraints)
        out[name]["rho_achieved"] = row.get("rho_achieved")
    return out


# --------------------------------------------------------------------------- #
# Reading it
# --------------------------------------------------------------------------- #

def summarise(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per arm, and per constraint kind, with the denominator beside every rate.

    No interval. Three arms over a dev split of twelve prompts is not a sample
    to resample, and `MIN_CLUSTERS_FOR_A_VERDICT` is 20 for reasons this project
    paid for. The point estimates decompose a verdict that already has its
    interval; they do not carry one of their own.
    """
    def _mean(values: Sequence[float]) -> float | None:
        clean = [v for v in values if isinstance(v, (int, float))]
        return round(sum(clean) / len(clean), 6) if clean else None

    arms = sorted({arm for row in rows for arm in row["arms"]})
    per_arm: dict[str, Any] = {}
    for arm in arms:
        scores = [row["arms"][arm]["constraint_score_comparable"]
                  for row in rows if arm in row["arms"]]
        full = [row["arms"][arm]["constraint_score"]
                for row in rows if arm in row["arms"]]
        paras = [row["arms"][arm]["n_paragraphs"]
                 for row in rows if arm in row["arms"]]
        per_arm[arm] = {
            "n_prompts": len([s for s in scores if s is not None]),
            "mean_constraint_score_comparable": _mean(scores),
            "mean_constraint_score": _mean(full),
            "mean_paragraphs": _mean(paras),
        }

    # The per-kind table is where the decomposition actually lives.
    by_kind: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"satisfied": 0, "checked": 0}))
    for row in rows:
        for arm, report in row["arms"].items():
            for kind, counts in report["by_kind"].items():
                by_kind[kind][arm]["satisfied"] += counts["satisfied"]
                by_kind[kind][arm]["checked"] += counts["checked"]

    split: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"satisfied": 0, "checked": 0}))
    for row in rows:
        for arm, report in row["arms"].items():
            for bucket, counts in report.get("must_mention_split", {}).items():
                split[bucket][arm]["satisfied"] += counts["satisfied"]
                split[bucket][arm]["checked"] += counts["checked"]

    kinds = {
        kind: {arm: {**counts,
                     "rate": (round(counts["satisfied"] / counts["checked"], 6)
                              if counts["checked"] else None)}
               for arm, counts in sorted(arms_counts.items())}
        for kind, arms_counts in sorted(by_kind.items())
    }

    def _of(arm: str) -> float | None:
        return (per_arm.get(arm) or {}).get("mean_constraint_score_comparable")

    mono, real = _of("monolithic"), _of("real")

    # Which oracle. There are three policies now, and picking the best one AFTER
    # seeing the scores is choosing a result -- the defect `falsifiable_go_no_go`
    # exists to stop. So every oracle gets its own decomposition, reported side
    # by side and named, and the headline `decomposition` stays on the policy
    # that was declared first: exclusive, the one the 5 September run used.
    per_policy = {arm: _decompose(mono, _of(arm), real)
                  for arm in ORACLE_ARMS if _of(arm) is not None}
    headline = (per_policy.get("oracle-exclusive")
                or (next(iter(per_policy.values())) if per_policy else
                    _decompose(mono, None, real)))

    return {
        "declared_cell": DECLARED,
        "by_arm": per_arm,
        "by_constraint_kind": kinds,
        "assembler_enforced_and_excluded": sorted(ASSEMBLER_ENFORCED),
        "decomposition": headline,
        "decomposition_by_policy": per_policy,
        "must_mention_split": {
            bucket: {arm: {**counts,
                           "rate": (round(counts["satisfied"] / counts["checked"], 6)
                                    if counts["checked"] else None)}
                     for arm, counts in sorted(arms_counts.items())}
            for bucket, arms_counts in sorted(split.items())
        },
        "must_mention_split_note": (
            "Read by_constraint_kind's must_mention beside term_once, and split "
            "must_mention by whether the term is ALSO term_once. On 5 September "
            "the exclusive oracle scored 11/24 on the terms it makes exclusive "
            "and 8/12 on the ones it does not -- identical to the shipped "
            "pipeline on the second bucket. The whole gap was the exclusivity "
            "clause, and a mean over both buckets hid it."
        ),
        "note": (
            "Scores are constraint_score_comparable: paragraph_count and "
            "words_per_paragraph are dropped because the assembler satisfies "
            "them mechanically in the fragmented arm and the model alone "
            "satisfies them in the monolithic one. by_constraint_kind reports "
            "every kind including those two, with its own denominator."
        ),
    }


def _decompose(mono: float | None, oracle: float | None,
               real: float | None) -> dict[str, Any]:
    """Split the end-to-end loss into the part allocation explains and the rest.

    ``allocation`` is oracle -> real: constraints a correct allocation would
    have satisfied and the shipped planner did not. A planner defect.

    ``parallelism`` is monolithic -> oracle: what a perfectly allocated set of
    fragments still loses by not being able to see each other. No allocation
    scheme recovers it.

    They sum to the end-to-end loss by construction, which is the point of
    scoring all three arms with one scorer.
    """
    if mono is None or oracle is None or real is None:
        return {"verdict": None,
                "note": "an arm is missing; no decomposition without all three"}
    total = mono - real
    parallelism = mono - oracle
    allocation = oracle - real

    # A share is only a share of something positive. The first version of this
    # function compared `allocation > parallelism * 2` unguarded, and on a
    # rehearsal where the fragmented arm scored ABOVE monolithic it read
    # "ALLOCATION dominates" from allocation 0.000 against parallelism -0.131 --
    # 0 > -0.26 is true. A sign test dressed as a magnitude test.
    if total <= 1e-9:
        return {
            "end_to_end_loss": round(total, 6),
            "parallelism_cost_monolithic_to_oracle": round(parallelism, 6),
            "allocation_cost_oracle_to_real": round(allocation, 6),
            "share_recoverable_by_allocation": None,
            "reading": ("NOTHING TO DECOMPOSE: the fragmented arm did not score "
                        "below monolithic on this run, so there is no loss to "
                        "attribute. Check the arms before reading anything else."),
        }

    # Either half can come out negative -- an arm scoring above the one it is
    # measured against -- and that is a fact about the run, not a share of the
    # loss. Say so rather than reporting a negative percentage.
    if parallelism < 0:
        reading = ("ALLOCATION accounts for MORE than the whole loss: the "
                   "oracle scored above monolithic, so correct allocation not "
                   "only recovers the loss but beats the unfragmented arm. "
                   "Check the oracle's briefs before believing it")
    elif allocation < 0:
        reading = ("PARALLELISM accounts for MORE than the whole loss: the "
                   "shipped planner scored above the oracle, so the oracle's "
                   "allocation is worse than what the planner does. Its briefs "
                   "are the thing to check, not the planner")
    elif allocation > parallelism * 2:
        reading = ("ALLOCATION dominates: most of the loss is fragments not "
                   "being told about each other, which is a planner defect "
                   "with a planner fix")
    elif parallelism > allocation * 2:
        reading = ("PARALLELISM dominates: even perfect allocation loses most "
                   "of it, so this workload is not fragmentable rather than "
                   "badly fragmented")
    else:
        reading = ("MIXED: neither half dominates, and a planner fix recovers "
                   f"at most {allocation:.3f} of {total:.3f}")
    return {
        "end_to_end_loss": round(total, 6),
        "parallelism_cost_monolithic_to_oracle": round(parallelism, 6),
        "allocation_cost_oracle_to_real": round(allocation, 6),
        "share_recoverable_by_allocation": round(allocation / total, 6),
        "reading": reading,
    }


def _load(path: Path, split: str | None) -> list[PromptSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload["prompts"] if isinstance(payload, dict) else payload
    specs = []
    for entry in entries:
        if split and entry.get("split") != split:
            continue
        specs.append(PromptSpec(
            prompt_id=entry["id"],
            category=entry.get("category", "composition"),
            expected_decomposable=bool(entry.get("expected_decomposable", True)),
            text=entry["prompt"],
            constraints=list(entry.get("constraints") or []) or None,
            split=entry.get("split"),
        ))
    return specs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prompts", default="prompts/composition.json")
    parser.add_argument("--split", default="dev", choices=("dev", "final", "all"))
    parser.add_argument("--rho", type=float, default=DECLARED["rho"])
    parser.add_argument("--n", type=int, default=DECLARED["n_tasks"])
    parser.add_argument("--tau-sem", type=float, default=0.6)
    parser.add_argument("--backend", default="openai-compat")
    parser.add_argument("--embedder", default="ollama")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--out", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    if (args.rho, args.n) != (DECLARED["rho"], DECLARED["n_tasks"]):
        print(f"NOTE: rho={args.rho} N={args.n} is NOT the declared cell "
              f"({DECLARED['rho']}, {DECLARED['n_tasks']}). This run decomposes "
              f"a different cell than comp-final's verdict, and the two numbers "
              f"may not be compared.", file=sys.stderr)

    specs = _load(Path(args.prompts), None if args.split == "all" else args.split)
    if args.limit:
        specs = specs[:args.limit]
    arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())

    backend = get_backend(args.backend)
    embedder = get_embedder(args.embedder)

    rows: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        print(f"[{index}/{len(specs)}] {spec.prompt_id}", flush=True)
        result = run_instance(spec, backend, embedder, rho=args.rho,
                              n_tasks=args.n, tau_sem=args.tau_sem, arms=arms)
        for arm, report in sorted(result.items()):
            print(f"      {arm:16} comparable="
                  f"{report['constraint_score_comparable']}"
                  f"  paragraphs={report['n_paragraphs']}"
                  f"  failed={report['failed']}", flush=True)
        rows.append({"prompt_id": spec.prompt_id, "split": spec.split,
                     "arms": result})

    summary = summarise(rows)
    print("\n" + "=" * 72)
    print("PER ARM (constraint_score_comparable)")
    for arm, stats in summary["by_arm"].items():
        print(f"  {arm:16} {stats['mean_constraint_score_comparable']}"
              f"   paragraphs {stats['mean_paragraphs']}"
              f"   n={stats['n_prompts']}")
    print("\nPER CONSTRAINT KIND (satisfied / checked)")
    for kind, per_arm in summary["by_constraint_kind"].items():
        cells = "  ".join(f"{arm}={c['satisfied']}/{c['checked']}"
                          for arm, c in per_arm.items())
        marker = "  [assembler-enforced]" if kind in ASSEMBLER_ENFORCED else ""
        print(f"  {kind:22} {cells}{marker}")
    print("\nMUST_MENTION, SPLIT BY WHETHER THE TERM IS ALSO term_once")
    for bucket, per_arm in summary["must_mention_split"].items():
        cells = "  ".join(f"{arm}={c['satisfied']}/{c['checked']}"
                          for arm, c in per_arm.items())
        print(f"  {bucket:34} {cells}")

    print("\nDECOMPOSITION, PER ALLOCATION POLICY")
    for arm, d in summary.get("decomposition_by_policy", {}).items():
        print(f"  {arm}")
        print(f"    parallelism (mono->oracle) {d.get('parallelism_cost_monolithic_to_oracle')}"
              f"   allocation (oracle->real) {d.get('allocation_cost_oracle_to_real')}")
        print(f"    {d.get('reading')}")

    decomposition = summary["decomposition"]
    print("\nDECOMPOSITION (headline: the policy declared first)")
    for key, value in decomposition.items():
        print(f"  {key:38} {value}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)

        # summary.json and results.csv under exactly those names, because
        # `run_tier` checks for both before it will call a tier completed. That
        # post-condition exists because a truncated command line once exited 0
        # having swept the wrong grid into the wrong directory, and a tier that
        # invented its own artefact names would opt out of the check.
        (out / "summary.json").write_text(
            json.dumps({"summary": summary, "rows": rows}, indent=2),
            encoding="utf-8")

        import csv as _csv
        fields = ["prompt_id", "split", "arm", "constraint_score",
                  "constraint_score_comparable", "n_constraints",
                  "n_paragraphs", "rho_achieved", "failed"]
        with (out / "results.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = _csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                for arm, report in sorted(row["arms"].items()):
                    writer.writerow({
                        "prompt_id": row["prompt_id"], "split": row["split"],
                        "arm": arm,
                        "constraint_score": report["constraint_score"],
                        "constraint_score_comparable":
                            report["constraint_score_comparable"],
                        "n_constraints": report["n_constraints"],
                        "n_paragraphs": report["n_paragraphs"],
                        "rho_achieved": report.get("rho_achieved"),
                        "failed": ";".join(report["failed"]),
                    })

        (out / "run_metadata.json").write_text(json.dumps({
            "tier": "comp-oracle",
            "backend": args.backend,
            "embedder": args.embedder,
            # The same stamp every other tier carries, and it must be true here
            # for the same reason: a rehearsal against the mock is harness
            # validation, and nothing in it is evidence about models.
            "harness_validation_only": args.backend == "mock",
            "embeddings_degraded": args.embedder == "hash",
            "declared_cell": DECLARED,
            "rho": args.rho, "n_tasks": args.n, "split": args.split,
            "corpus": str(args.prompts),
        }, indent=2), encoding="utf-8")

        print(f"\nwrote {out / 'summary.json'} and {out / 'results.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
