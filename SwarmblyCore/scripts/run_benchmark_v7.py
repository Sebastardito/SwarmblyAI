#!/usr/bin/env python3
"""V7's runner. Deliberately OUTSIDE ``benchmark_v7/``, and that is the design.

``benchmark_v7/__init__`` says router, packing, assembler and consensus are
"reused, not rewritten", and
``test_the_benchmark_does_not_import_the_harness_it_is_checking`` bans
``swarmbly_v0.planner``, ``packing``, ``assembler``, ``consensus``, ``editor``,
``metrics``, ``grading``, ``experiment`` and bare ``swarmbly_v0`` from every
file in the package. Read together those look like a contradiction, and the
first person to hit the test will be tempted to relax it. They should not.

The two statements are about different things, and the split is the whole point
of ADR-001:

* **The benchmark** -- instances and scoring -- must be able to DISAGREE with
  the harness. If it scored through ``swarmbly_v0.metrics`` then the
  arm-neutrality defect that cost this project four documents would have
  propagated into V7 in silence, and V7 would have "confirmed" V0. Agreement
  between a measurement and its own instrument reads as replication, which is
  the worst available outcome.
* **The runner** is glue. It must drive the SHIPPED protocol and nothing else,
  because a runner that reimplemented planning or packing would measure a
  protocol that is not the one in the repository -- a confound worth more than
  every defect V7 exists to find.

So the runner imports both, and it lives here, where the ban does not apply and
cannot be silently widened. Deleting this docstring re-opens the trap.

What this measures
------------------

Three arms per instance, scored by ``benchmark_v7.evaluate`` in every case:

``monolithic``  the model's ceiling. Every fact available, one prompt.
``oracle``      fragmented, and every packet handed EXACTLY the facts its own
                claims require -- built here, without the router or the packer.
                Answers "is this partition viable in principle?"
``real``        fragmented through the shipped router, planner, packer and
                assembler.

**The oracle arm is the point, and it is the reading order.** Every packaging
failure this project spent weeks on -- a contract that never reached a fragment,
a phantom carry line, 42 of 60 packets holding another packet's answers -- would
have read as *oracle fine, real broken*, which localises the fault to planning,
packing or assembly in one look. Without it, ``real`` at 40 % accuracy is
indistinguishable from a 3B model that cannot add.

``unanswerable_rate`` separates the two further, and it is the packer's number
rather than the model's: a claim whose packet did not hold the facts it requires
could not have been produced correctly by any model. A run where that is high
has a packing problem wearing a capability problem's clothes.

What it cannot establish
------------------------

A fact-graph corpus is synthetic and its answers are canonical by construction.
V7 can establish **the protocol does not lose information it was given**. It
cannot establish **the protocol works on your documents**. Stated here, before
the first result, so it is a property of the design and not a caveat added under
pressure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_v7.evaluate import InstanceReport, evaluate  # noqa: E402
from benchmark_v7.graph import Instance, build_instance, instance_digest  # noqa: E402
from swarmbly_v0.backends import get_backend, get_embedder  # noqa: E402
from swarmbly_v0.experiment import (PromptSpec, SweepConfig, run_fragmented,  # noqa: E402
                                    run_monolithic, _answer_budget)
from swarmbly_v0.planner import global_contract  # noqa: E402

TASK_CLASSES = ("map", "reduce", "chain", "compose")
ARMS = ("monolithic", "oracle", "real")

REFUSED_ARM = "real-refused"
"""What the real arm is called when the planner declined to fragment.

A separate name rather than a flag on the same name, because a mean over
"real" that silently mixed fragmented and unfragmented cells is the shape of
every pooling defect this project has corrected: rho pooled over N, N pooled
over k, a rate reported without its denominator. Two different things measured
under one label is the defect, not the reporting of it."""

_TASK_MARKER = re.compile(r"\[TASK (t\d+)\]")
_CLAIM_IN_TEXT = re.compile(r"[\[(]\s*(c[_\w]+)\s*[\])]")


@dataclass
class _Recorder:
    """A backend that records every prompt it is asked to generate from.

    The packets are the evidence. ``facts_available`` and ``claim_owner`` have to
    describe what was ACTUALLY dispatched, not what the planner intended -- the
    defect of 4 September was precisely a gap between those two, and a runner
    that reconstructed the packets from the plan would have reproduced the gap
    instead of measuring it.

    Detection is by substring on the fact's own source line, which is how the
    fact appears in the material. Mechanical, and it cannot drift from the
    generator: ``Fact.as_line`` is the single definition of that string.
    """

    inner: Any

    def __post_init__(self) -> None:
        self.prompts: list[str] = []
        self.name = getattr(self.inner, "name", "recorded")
        self.family = getattr(self.inner, "family", "")
        self.model = getattr(self.inner, "model", "")

    def for_replica(self, family: str, model: str = "") -> "_Recorder":
        inner = (self.inner.for_replica(family, model)
                 if hasattr(self.inner, "for_replica") else self.inner)
        clone = _Recorder(inner)
        clone.prompts = self.prompts
        clone.family, clone.model = family, model
        return clone

    def generate(self, prompt: str, **kwargs: Any) -> str:
        self.prompts.append(prompt)
        return self.inner.generate(prompt, **kwargs)

    def embed(self, texts: Sequence[str]) -> Any:
        return self.inner.embed(texts)


def _spec_for(instance: Instance) -> PromptSpec:
    """The instance as the harness's own prompt type.

    No key and no numeric facts: V7 grades through ``benchmark_v7.evaluate`` and
    must not hand the harness's grader anything to score, or the boundary ADR-001
    describes stops being a boundary. ``constraints`` travels because the compose
    class needs it and the harness's assembler reads it.
    """
    return PromptSpec(
        prompt_id=instance.instance_id,
        category=f"v7_{instance.task_class}",
        expected_decomposable=instance.task_class != "chain",
        text=instance.prompt(),
        constraints=list(instance.constraints) or None,
        split=instance.split,
    )


def _facts_held(instance: Instance, packet: str) -> set[str]:
    """Which of the instance's facts this packet's text actually contains."""
    return {fact_id for fact_id, fact in instance.facts.items()
            if fact.as_line() in packet}


def _packet_view(instance: Instance, prompts: Sequence[str]) -> tuple[
        dict[str, set[str]], dict[str, str]]:
    """``facts_available`` and ``claim_owner``, read off the dispatched packets.

    A packet owns a claim when its task block names that claim's id. A claim no
    packet named is attributed to no packet, and ``evaluate`` then judges it
    against every fact -- which is the right default: the failure is that nobody
    was asked for it, and calling that "unanswerable" would blame the packer for
    an omission made by the planner.
    """
    facts_available: dict[str, set[str]] = {}
    claim_owner: dict[str, str] = {}
    claims = {c.claim_id for c in instance.claims}

    for packet in dict.fromkeys(prompts):
        marker = _TASK_MARKER.search(packet)
        if marker is None:
            continue
        task_id = marker.group(1)
        facts_available[task_id] = _facts_held(instance, packet)
        for named in _CLAIM_IN_TEXT.findall(packet[marker.start():]):
            if named in claims:
                claim_owner.setdefault(named, task_id)
    return facts_available, claim_owner


def _oracle_partition(instance: Instance) -> tuple[dict[str, set[str]],
                                                   dict[str, str]]:
    """One packet per claim, holding exactly the facts that claim requires.

    Built here rather than by the packer, because the question is whether the
    PARTITION is viable at all -- if the oracle arm cannot answer a claim, no
    packing strategy can, and the task class itself is the problem. On ``reduce``
    that is the expected reading: every claim requires every fact, so a packet
    per claim holds the whole material and the arm collapses to monolithic. That
    is not a bug in the arm, it is the measurement -- a reduce is not
    partitionable, and the oracle says so before any model is asked.
    """
    facts_available = {f"oracle_{c.claim_id}": set(c.requires)
                       for c in instance.claims}
    claim_owner = {c.claim_id: f"oracle_{c.claim_id}" for c in instance.claims}
    return facts_available, claim_owner


def _oracle_prompt(instance: Instance, claim_ids: Sequence[str]) -> str:
    """The packet an oracle worker sees: its claims, and only its facts."""
    wanted = {c.claim_id: c for c in instance.claims}
    needed: set[str] = set()
    for claim_id in claim_ids:
        needed |= set(wanted[claim_id].requires)
    lines = [f"  {fact.as_line()}" for fact_id, fact in instance.facts.items()
             if fact_id in needed]
    asked = "\n".join(
        f"  [{cid}] {wanted[cid].prose}" for cid in claim_ids)
    return (f"{instance.instruction}\n\n"
            f"Answer only the items listed here:\n{asked}\n\n"
            f"Material:\n" + "\n".join(lines) + "\n\n"
            f"Give one line per item as [item id] followed by the value alone.")


def run_instance(instance: Instance, backend: Any, embedder: Any, *,
                 rho: float, n_tasks: int, tau_sem: float,
                 arms: Sequence[str]) -> dict[str, InstanceReport]:
    """One instance through each requested arm. Same evaluator for all of them."""
    reports: dict[str, InstanceReport] = {}
    spec = _spec_for(instance)
    config = SweepConfig(rhos=(rho,), ns=(n_tasks,), ks=(1,), n_candidates=1,
                         seed=0, tau_sem=tau_sem)
    contract = global_contract(spec.text, backend,
                               target_length_tokens=_answer_budget(spec, 420))
    baseline: dict[str, Any] | None = None

    if "monolithic" in arms or "real" in arms:
        recorder = _Recorder(backend)
        baseline = run_monolithic(spec, recorder, embedder, config,
                                  contract=contract)
        if "monolithic" in arms:
            reports["monolithic"] = evaluate(
                instance, str(baseline.get("_text", "")), "monolithic")

    if "oracle" in arms:
        facts_available, claim_owner = _oracle_partition(instance)
        answers: list[str] = []
        for claim in instance.claims:
            answers.append(backend.generate(
                _oracle_prompt(instance, [claim.claim_id]), max_tokens=256,
                seed=0))
        reports["oracle"] = evaluate(
            instance, "\n".join(answers), "oracle",
            facts_available={k: sorted(v) for k, v in facts_available.items()},
            claim_owner=claim_owner)

    if "real" in arms:
        recorder = _Recorder(backend)
        row = run_fragmented(spec, recorder, embedder, config, rho_target=rho,
                             n_tasks=n_tasks, tau_sem=tau_sem, k=1,
                             contract=contract, baseline=baseline)
        facts_available, claim_owner = _packet_view(instance, recorder.prompts)
        # A REFUSED plan is not a fragmented measurement, and this is the
        # direction that matters. When `planner.references_are_recoverable` says
        # no, `plan` returns a single task holding the whole prompt, so the
        # "real" arm scores whatever the monolithic arm scores -- 1.000 with a
        # compliant worker. Reported as an accuracy that would read as *the
        # implementation is fine*, on a prompt that was never fragmented.
        #
        # The harness drops such a row at `is_reachable`; this arm records it
        # under its own name instead of scoring it. Three of V7's four task
        # classes come back refused, and a summary that hid that behind 1.000
        # would be the most flattering wrong number in the project.
        arm = "real-refused" if _refused(row) else "real"
        reports[arm] = evaluate(
            instance, str(row.get("_text", "")), arm,
            facts_available={k: sorted(v) for k, v in facts_available.items()},
            claim_owner=claim_owner)

    return reports


def _refused(row: Mapping[str, Any]) -> bool:
    """Did the planner decline to fragment this prompt?

    Read from the row rather than recomputed, so the runner cannot disagree with
    the harness about what happened -- the same reason ``facts_available`` is
    read off the dispatched packets.
    """
    value = row.get("plan_refused", False)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def summarise(reports: Sequence[InstanceReport]) -> dict[str, Any]:
    """Per arm and per task class, with the denominators beside every rate.

    No interval. A mean over four task classes is not a sample of anything, and
    this project has published one bootstrap on eight clusters already. When V7
    has enough instances per class to resample, the interval goes in then and is
    clustered by instance.
    """
    def _mean(values: Sequence[float]) -> float | None:
        usable = [v for v in values if v is not None]
        return round(sum(usable) / len(usable), 6) if usable else None

    out: dict[str, Any] = {"by_arm": {}, "by_arm_and_class": {}}
    arms = sorted({r.arm for r in reports})
    classes = sorted({r.task_class for r in reports})

    for arm in arms:
        group = [r for r in reports if r.arm == arm]
        out["by_arm"][arm] = {
            "n_instances": len(group),
            "n_claims": sum(r.n_claims for r in group),
            "accuracy": _mean([r.accuracy for r in group]),
            "coverage": _mean([r.coverage for r in group]),
            "unanswerable_rate": _mean([r.unanswerable_rate for r in group]),
        }
        for task_class in classes:
            cell = [r for r in group if r.task_class == task_class]
            if not cell:
                continue
            out["by_arm_and_class"][f"{arm}@{task_class}"] = {
                "n_instances": len(cell),
                "accuracy": _mean([r.accuracy for r in cell]),
                "coverage": _mean([r.coverage for r in cell]),
                "unanswerable_rate": _mean([r.unanswerable_rate for r in cell]),
            }

    oracle = out["by_arm"].get("oracle", {}).get("accuracy")
    real = out["by_arm"].get("real", {}).get("accuracy")
    mono = out["by_arm"].get("monolithic", {}).get("accuracy")
    refused = out["by_arm"].get(REFUSED_ARM, {}).get("n_instances", 0)
    fragmented = out["by_arm"].get("real", {}).get("n_instances", 0)
    out["n_refused"] = refused
    out["reading"] = _reading(mono, oracle, real, refused, fragmented)
    out["note"] = (
        "Read oracle before real. oracle high and real low localises the fault "
        "to planning, packing or assembly; both low means the partition itself "
        "is not viable for that task class; monolithic low means the model "
        "cannot do the task and neither fragmented number is interpretable. "
        "unanswerable_rate is the packer's figure, not the model's: a claim "
        "whose packet did not hold the facts it requires could not have been "
        "answered correctly by any model. No interval: a mean over four task "
        "classes is not a sample."
    )
    return out


def _reading(mono: float | None, oracle: float | None,
             real: float | None, refused: int = 0,
             fragmented: int = 0) -> str:
    """The one-line diagnosis, stated by the runner rather than left to a reader.

    tables-dev computed its declared cell and printed everything except it. A
    figure a reader has to assemble from three numbers in a JSON file is a figure
    that gets quoted wrong.
    """
    # The refusal comes FIRST, before any comparison. A run where the planner
    # declined to fragment most of the corpus has not measured fragmentation,
    # and saying "the implementation is not losing more than noise" about it
    # would be true and useless -- there was no implementation in the loop.
    if refused and not fragmented:
        return (f"{refused} instance(s) refused and none fragmented: the planner "
                f"declined every prompt, so this run measures nothing about "
                f"fragmentation")
    if mono is None or oracle is None or real is None:
        if refused:
            return (f"{refused} instance(s) refused; the remaining arms did not "
                    f"all run, so no localisation is available")
        return "not all three arms ran; no localisation available"
    if mono < 0.5:
        return (f"monolithic {mono:.3f}: the model cannot do this task, so "
                f"neither fragmented figure is interpretable")
    if oracle < 0.5:
        return (f"oracle {oracle:.3f} with monolithic {mono:.3f}: the PARTITION "
                f"is not viable -- no packing strategy recovers this")
    if real < oracle - 0.05:
        return (f"oracle {oracle:.3f} against real {real:.3f}: the partition is "
                f"viable and the implementation loses "
                f"{(oracle - real) * 100:.1f} points -- planning, packing or "
                f"assembly")
    tail = (f"oracle {oracle:.3f} against real {real:.3f}: the implementation "
            f"is not losing more than noise against its own oracle")
    if refused:
        tail += (f" -- on the {fragmented} instance(s) it agreed to fragment. "
                 f"{refused} were refused and are not in that comparison.")
    return tail


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=4,
                        help="instances per task class (default: 4)")
    parser.add_argument("--classes", default=",".join(TASK_CLASSES),
                        help=f"comma-separated task classes ({', '.join(TASK_CLASSES)})")
    parser.add_argument("--arms", default=",".join(ARMS),
                        help=f"comma-separated arms ({', '.join(ARMS)})")
    parser.add_argument("--rho", type=float, default=3.0)
    parser.add_argument("--n", type=int, default=4, dest="n_tasks")
    parser.add_argument("--tau", type=float, default=0.6)
    parser.add_argument("--backend", default="mock",
                        help="mock | openai. mock validates the wiring and "
                             "measures nothing about models.")
    parser.add_argument("--embedder", default="hash")
    parser.add_argument("--split", default="dev", choices=("dev", "final"),
                        help="stamped onto the instances and into the digest")
    parser.add_argument("--out", default=None,
                        help="directory for reports.json and summary.json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = set(classes) - set(TASK_CLASSES) or set(arms) - set(ARMS)
    if unknown:
        parser.error(f"unknown task class or arm: {sorted(unknown)}")

    backend = get_backend(args.backend, seed=0)
    # `api` reads its route off the generation backend; `hash` and `st` take no
    # backend at all and raise on the keyword. Matches how cli.py constructs it.
    embedder = (get_embedder(args.embedder, backend=backend)
                if args.embedder in {"api", "server", "ollama", "openai"}
                else get_embedder(args.embedder))
    instances = [build_instance(task_class, seed, split=args.split)
                 for task_class in classes
                 for seed in range(args.seeds)]

    print(f"V7 benchmark: {len(instances)} instances "
          f"({len(classes)} classes x {args.seeds} seeds), arms {arms}")
    print(f"  digest {instance_digest(instances)}")
    print(f"  rho {args.rho}  N {args.n_tasks}  backend {backend.name}")
    if getattr(backend, "name", "") == "mock":
        print("  *** MockBackend: this validates the wiring. It is NOT evidence "
              "about models. ***")

    reports: list[InstanceReport] = []
    for instance in instances:
        produced = run_instance(instance, backend, embedder, rho=args.rho,
                                n_tasks=args.n_tasks, tau_sem=args.tau,
                                arms=arms)
        reports.extend(produced.values())
        line = "  ".join(
            f"{arm}={'--' if r.accuracy is None else format(r.accuracy, '.3f')}"
            for arm, r in produced.items())
        print(f"  {instance.instance_id:<24} {line}")

    summary = summarise(reports)
    print("\n" + "=" * 72)
    for arm, block in summary["by_arm"].items():
        print(f"  {arm:<12} accuracy={block['accuracy']}  "
              f"coverage={block['coverage']}  "
              f"unanswerable={block['unanswerable_rate']}  "
              f"(n={block['n_instances']}, claims={block['n_claims']})")
    print(f"\n  READING: {summary['reading']}")
    print("=" * 72)

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "reports.json").write_text(
            json.dumps([r.as_dict() for r in reports], indent=2) + "\n")
        (out / "summary.json").write_text(
            json.dumps({**summary,
                        "instance_digest": instance_digest(instances),
                        "backend": backend.name,
                        "harness_validation_only":
                            getattr(backend, "name", "") == "mock",
                        "rho": args.rho, "n_tasks": args.n_tasks,
                        "split": args.split}, indent=2) + "\n")
        print(f"  -> {out}/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
