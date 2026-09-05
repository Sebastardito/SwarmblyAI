#!/usr/bin/env python3
"""The composition oracle arm: what are the 22.4 points made of?

``comp-final`` measured composition at rho 4.0, N 3, k 1 as costing **+22.40
points** of constraint satisfaction against its monolithic baseline, CI
[+16.15, +28.51], NOT MET by 23.51 points on the upper bound. That result is
end-to-end, and it carries a stated limit which this script exists to remove:

    mean_paragraphs was 2.0 monolithic against 7.96 fragmented. Each fragment
    wrote a complete answer. So the 22.4 points measure THIS IMPLEMENTATION
    fragmenting prose, not the cost of fragmenting prose.

Three arms, the same corpus, the same mechanical scorer, no judge anywhere.

``monolithic``  one call, the whole prompt. The ceiling.
``oracle``      fragmented, and every global constraint ALLOCATED across the
                fragments by construction: each required term is owned by
                exactly one fragment, and where the term is also `term_once`
                the others are told to avoid it. No router, no planner, no
                packer. Answers "how much of the loss is a coordination
                failure the planner could in principle fix?"
``real``        the shipped router, planner, packer and assembler.

**The reading is the gap structure, not any single number.**

* ``oracle`` near ``monolithic`` and ``real`` far below both -> the loss is
  allocation. Workers are not told about each other, and that is a planner
  defect with a planner fix.
* ``oracle`` and ``real`` both far below ``monolithic`` -> the loss is
  parallel prose. No allocation scheme recovers it, because the fragments
  cannot see each other's text at all, and the answer is that this workload is
  not fragmentable rather than that this implementation is bad at it.

Both readings are useful and they are opposite. Without this arm the +22.40 is
compatible with either, which is why it was published with a limit attached.

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

ARMS = ("monolithic", "oracle", "real")

DECLARED = {"rho": 4.0, "n_tasks": 3, "k": 1}
"""The cell comp-final declared. The oracle decomposes THAT cell or nothing.

Running the oracle at a different rho or N and comparing it to the published
+22.40 would be the tables-final defect again: two arms at different points on
the axis with the largest effect, reported under one label."""


# --------------------------------------------------------------------------- #
# The allocation
# --------------------------------------------------------------------------- #

def allocate(constraints: Sequence[Mapping[str, Any]], n_fragments: int
             ) -> list[dict[str, Any]]:
    """Give each fragment its own share of the global constraints.

    The rule, and it is the whole oracle:

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

    briefs: list[dict[str, Any]] = [
        {"must_mention": [], "must_avoid": list(forbidden)}
        for _ in range(n_fragments)
    ]
    for position, term in enumerate(required):
        owner = position % n_fragments
        briefs[owner]["must_mention"].append(term)
        if term in once_terms:
            for index, brief in enumerate(briefs):
                if index != owner:
                    brief["must_avoid"].append(term)
    return briefs


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
    return {
        "constraint_score": report.score,
        "constraint_score_comparable": report.score_excluding(ASSEMBLER_ENFORCED),
        "n_constraints": len(report.results),
        "n_paragraphs": report.n_paragraphs,
        "failed": [r.constraint_id for r in report.failed],
        "by_kind": {kind: {"satisfied": sum(v), "checked": len(v)}
                    for kind, v in sorted(by_kind.items())},
    }


def run_oracle(spec: PromptSpec, backend: Any, *, n_tasks: int,
               max_tokens: int = 420) -> tuple[str, list[str]]:
    """Dispatch one fragment per paragraph and splice them with blank lines."""
    constraints = list(spec.constraints or [])
    paragraphs = _paragraph_count(constraints, n_tasks)
    low, high = _length_bounds(constraints)
    briefs = allocate(constraints, paragraphs)
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

    if "oracle" in arms:
        text, dispatched = run_oracle(spec, backend, n_tasks=n_tasks)
        out["oracle"] = _score(text, constraints)
        out["oracle"]["n_fragments"] = len(dispatched)
        # rho is undefined for this arm and must not be reported as though it
        # were: the oracle never goes through the packer, so there is no packet
        # whose size could be divided by anything.
        out["oracle"]["rho_achieved"] = None

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

    kinds = {
        kind: {arm: {**counts,
                     "rate": (round(counts["satisfied"] / counts["checked"], 6)
                              if counts["checked"] else None)}
               for arm, counts in sorted(arms_counts.items())}
        for kind, arms_counts in sorted(by_kind.items())
    }

    mono = (per_arm.get("monolithic") or {}).get("mean_constraint_score_comparable")
    oracle = (per_arm.get("oracle") or {}).get("mean_constraint_score_comparable")
    real = (per_arm.get("real") or {}).get("mean_constraint_score_comparable")

    return {
        "declared_cell": DECLARED,
        "by_arm": per_arm,
        "by_constraint_kind": kinds,
        "assembler_enforced_and_excluded": sorted(ASSEMBLER_ENFORCED),
        "decomposition": _decompose(mono, oracle, real),
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
    decomposition = summary["decomposition"]
    print("\nDECOMPOSITION")
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
