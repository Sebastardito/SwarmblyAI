#!/usr/bin/env python3
"""Recompute a finished run's headline statistics from its CSVs.

Why this exists
---------------

Every defect found in this project so far has been in the *analysis*, not in the
generation: a grader that inverted a baseline, a sentinel that entered a
calibration, five separate pooling artefacts. Each was found after a run that
cost hours, and each time the choice was to re-run or to hand-compute. Neither is
right: re-running spends GPU on a question the existing generations already
answer, and hand-computing means the corrected number comes from a throwaway
script rather than from the code the next run will use.

So this reads ``results.csv`` and ``ground_truth_items.csv`` back and calls the
library functions on them. The numbers it prints come from the same code path a
fresh run would take, which is the only way a correction can be trusted to apply
to the next run as well as to this one.

What it recomputes, and why each was wrong at least once:

* ``falsifiable_go_no_go`` **per (category, rho, N, k)**. The declared cell did
  not name k until 26 August, so the table run reported +18.3 % -- the midpoint
  of +20.6 % at k=1 and +16.0 % at k=3.
* ``rho_fidelity``. Nothing checked whether a cell ran at the budget its label
  names. That run's N=8 arm sat at 3.91 against a target of 3.5.
* the agreement calibration **stratified by claim class**. Pooled, that run's
  flagging lift read 1.05 / 0.70 / 0.88 -- at or below random. Inside the
  aggregate class it reads 2.15 / 1.75 / 1.48.

Usage::

    python3 scripts/reanalyse.py results/tables-dev-20260826-115300
    python3 scripts/reanalyse.py results/<run> --json > corrected.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarmbly_v0.experiment import (  # noqa: E402
    agreement_truth_calibration,
    discrete_calibration,
    falsifiable_go_no_go,
    flag_effect,
    rho_fidelity,
    stratified_auc,
    stratified_flagging,
)
from swarmbly_v0.report import read_rows  # noqa: E402

_TRUE = {"true", "1", "yes"}


def _truth_records(path: Path) -> list[dict[str, Any]]:
    """Read ground_truth_items.csv with the three fields that decide a verdict.

    ``correct`` is tri-state on purpose: an empty cell means the unit was not
    gradable, which is neither right nor wrong, and coercing it to False would
    move every accuracy figure toward the answer that flatters fragmentation
    least. ``agreement`` is likewise ``None`` when absent rather than 0.0 -- the
    sentinel that produced the V6 "agreement collapse".
    """
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            record: dict[str, Any] = dict(raw)
            value = str(raw.get("correct", "")).strip().lower()
            record["correct"] = (value in _TRUE) if value in _TRUE | {"false", "0", "no"} else None
            agreement = str(raw.get("agreement", "")).strip()
            record["agreement"] = float(agreement) if agreement else None
            for field in ("k", "n_tasks"):
                text = str(raw.get(field, "")).strip()
                record[field] = int(float(text)) if text else None
            record["graded"] = str(raw.get("graded", "")).strip().lower() in _TRUE
            out.append(record)
    return out


def analyse(run_dir: Path) -> dict[str, Any]:
    rows = read_rows(run_dir / "results.csv")
    fragmented = [r for r in rows if str(r.get("condition", "")) == "fragmented"]
    truth = _truth_records(run_dir / "ground_truth_items.csv")
    graded = [r for r in truth
              if r["graded"] and r["correct"] is not None
              and str(r.get("condition", "")).startswith("fragmented")]

    cells = {
        f"{cat}@rho={rho}@N={n}@k={k}": falsifiable_go_no_go(
            fragmented, category=cat, rho=rho, n_tasks=n, k=k)
        for cat in sorted({str(r.get("category", "")) for r in fragmented})
        for rho in sorted({float(r["rho_target"]) for r in fragmented
                           if isinstance(r.get("rho_target"), (int, float))})
        for n in sorted({int(r["n_tasks"]) for r in fragmented
                         if str(r.get("n_tasks", "")).strip().replace(".0", "").isdigit()})
        for k in sorted({int(r["k"]) for r in fragmented
                         if str(r.get("k", "")).strip().replace(".0", "").isdigit()})
    }
    cells = {name: cell for name, cell in cells.items() if cell["n_observations"]}

    by_claim = {
        claim: agreement_truth_calibration(
            [r for r in graded if str(r.get("claim", "")) == claim])
        for claim in ("aggregate", "local")
        if any(str(r.get("claim", "")) == claim for r in graded)
    }

    return {
        "run": str(run_dir),
        # A CSV written before the metric correction has no comparable column, and
        # every coherence tax in it was computed by the arm-dependent metric. The
        # tool must say so rather than faithfully reproducing a wrong number.
        "metric_is_stale": not any("booook_comparable" in r for r in rows),
        "rho_fidelity": rho_fidelity(fragmented),
        "go_no_go": cells,
        "calibration": {
            "pooled": agreement_truth_calibration(graded),
            "by_claim": by_claim,
            "stratified_by_claim_auc": stratified_auc(graded, key="claim"),
            "flagging_pooled": agreement_truth_calibration(graded).get("flagging"),
            "flagging_by_claim": stratified_flagging(graded, key="claim"),
            "discrete_by_claim": discrete_calibration(graded, key="claim"),
            "discrete_pooled": discrete_calibration(graded),
            "flag_effect_by_claim": {
                claim: flag_effect([r for r in graded
                                    if str(r.get("claim", "")) == claim])
                for claim in ("aggregate", "local")
            },
        },
    }


def _pct(value: Any) -> str:
    return f"{value * 100:+7.2f}%" if isinstance(value, (int, float)) else "     n/a"


def report(result: dict[str, Any]) -> None:
    print(f"\n=== {result['run']} ===\n")

    if result.get("metric_is_stale"):
        print("*" * 78)
        print("WARNING: this results.csv predates the coherence-metric correction of")
        print("27 August. It has no `booook_comparable` column, so every coherence")
        print("tax below is the figure computed at run time by a metric that was not")
        print("arm-neutral: the baseline was held to a smaller expected-entity set,")
        print("its omissions dirtied one sentence where the fragmented arm's dirtied")
        print("N, and it could not incur a seam error at all. On the table run that")
        print("accounted for 5.7 points at N=2 and 10.1 at N=8.")
        print("")
        print("The calibration figures below are unaffected -- they rest on numeric")
        print("fidelity and agreement, not on this metric.")
        print("")
        print("To correct the tax without re-running the models:")
        print(f"    python3 scripts/rescore.py {result['run']}")
        print("*" * 78)
        print("")

    fidelity = result["rho_fidelity"]
    print("rho fidelity -- did each cell run at the budget its label names?")
    for cell in fidelity["cells"]:
        mark = "ok " if cell["within_tolerance"] else "OUT"
        print(f"  {mark}  rho_target={cell['rho_target']:<5g} N={cell['n_tasks']:<3} "
              f"achieved={cell['rho_achieved_mean']:<6.3f} "
              f"deviation={cell['relative_deviation']:+.1%}  n={cell['n_rows']}")
    if not fidelity["within_tolerance"]:
        print("  ^ a cell outside tolerance did not measure what its axis label says.")

    print("\ngo/no-go, one cell per (category, rho, N, k) -- k is part of the cell:")
    for name, cell in sorted(result["go_no_go"].items()):
        interval = cell.get("ci95")
        span = (f"[{interval[0] * 100:+6.2f}%, {interval[1] * 100:+6.2f}%]"
                if interval else "        no interval")
        verdict = {True: "PASS", False: "fail", None: "  --"}[cell.get("passed")]
        print(f"  {name:<42} {_pct(cell.get('point_estimate'))}  {span}  "
              f"prompts={cell.get('n_prompts')}  {verdict}")

    calibration = result["calibration"]
    pooled = calibration["pooled"]
    print(f"\ncalibration, pooled: n={pooled['n_items']} "
          f"acc={pooled['accuracy']} agreement={pooled['mean_agreement']} "
          f"AUC={pooled['auc']}")
    print(f"  excluded: single-replica {pooled['excluded_single_replica']}, "
          f"ungradable {pooled['excluded_unintelligible']}")
    for claim, entry in calibration["by_claim"].items():
        print(f"  {claim:<10} n={entry['n_items']:<5} acc={entry['accuracy']} "
              f"agreement={entry['mean_agreement']} AUC={entry['auc']}")

    print("\nflagging lift -- pooled against inside each claim class:")
    pooled_flags = {row["flag_rate"]: row for row in (pooled.get("flagging") or [])}
    for row in calibration["flagging_by_claim"]:
        rate = row["flag_rate"]
        pooled_lift = pooled_flags.get(rate, {}).get("lift")
        strata = "  ".join(f"{name}={s['lift']:.2f}"
                           for name, s in sorted(row["by_stratum"].items()))
        print(f"  rate={rate:<5} pooled={pooled_lift if pooled_lift is not None else 'n/a':<8} "
              f"stratified={row['lift']}   {strata}")
    discrete = calibration["discrete_by_claim"]
    if discrete["discrete"]:
        print(f"\naccuracy at each distinct agreement value "
              f"({discrete['n_distinct_values']} values -- agreement is consistent/k):")
        for name, entry in sorted(discrete["by_stratum"].items()):
            shape = "monotone" if entry["monotone"] else "NOT monotone"
            cells = "  ".join(f"{p['agreement']:.2f}:{p['accuracy']:.3f}(n={p['n']})"
                              for p in entry["points"])
            print(f"  {name:<10} {cells}")
            print(f"  {'':<10} {shape}, accuracy span {entry['span']:.3f}, n={entry['n']}")
        pooled_table = calibration["discrete_pooled"]["by_stratum"].get("all")
        if pooled_table:
            cells = "  ".join(f"{p['agreement']:.2f}:{p['accuracy']:.3f}"
                              for p in pooled_table["points"])
            shape = "monotone" if pooled_table["monotone"] else "NOT monotone"
            print(f"  {'pooled':<10} {cells}")
            print(f"  {'':<10} {shape} -- a mixture of the two above, and neither")

    print("\nthe declared test -- MH odds ratio, prompt as stratum, cut at agreement < 2/3:")
    for claim, entry in calibration["flag_effect_by_claim"].items():
        role = "(under test)" if claim == "aggregate" else "(control, must fail)"
        interval = entry.get("ci95")
        verdict = "PASS" if interval and interval[0] > 2.0 else "fail"
        print(f"  {claim:<10} {role:<22} OR={entry['odds_ratio']}  CI95={interval}")
        print(f"  {'':<10} strata contributing={entry['n_strata_contributing']}/"
              f"{entry['n_clusters']}  flagged={entry['n_flagged']}/{entry['n_items']}  "
              f"lift_unstratified={entry['lift_unstratified']}  -> {verdict}")
        if entry.get("unestimable_reason"):
            print(f"  {'':<10} {entry['unestimable_reason']}")

    print("\n  A pooled lift below 1.0 beside stratified lifts above it means the")
    print("  pooling is measuring the difference between the classes, not between")
    print("  right and wrong answers.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="a results/<run> directory")
    parser.add_argument("--json", action="store_true",
                        help="emit the full result as JSON instead of a table")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not (run_dir / "results.csv").exists():
        print(f"{run_dir}/results.csv does not exist", file=sys.stderr)
        return 1

    result = analyse(run_dir)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
