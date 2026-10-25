#!/usr/bin/env python3
"""Verify a sweep grid against a corpus BEFORE spending hours on it.

Three tiers died on 4 September 2026, each for a different reason, and each cost
hours because the only way to find out was to run it:

* ``v0`` asked rho 5.5 at N=2 where the packing CEILING is 4.90. Five hours in,
  it undershot by 6.5 % and the drift invariant aborted the tier. One
  unreachable cell of 144 took 143 measured ones with it.
* ``v0`` again, after I moved the grid, asked 3.95 at N=8 on a chain prompt and
  overshot by 5.6 %. Five more hours.
* Looking for the cause found that ``tables-dev``/``tables-final`` had been
  running their DECLARED cell above the ceiling all along, undershooting by a
  systematic 3.4 % that passed the fidelity check because it was inside
  tolerance.

I patched the grid twice from a hypothesis about the cause and was wrong both
times. This script does not need a hypothesis. It packs every cell of a grid and
reports the achieved rho, in seconds.

**It is a bound, not a sample.** A mock sweep gives false confidence: the drift
scales with how verbose the predecessor summaries are, and a mock's are short --
the cell that aborted the second tier read +3.9 % under a mock and +5.6 %
against real models. ``summarize_fragment`` truncates every summary to
``WORST_CASE_SUMMARY_TOKENS``, so packing at that cap is the worst any run can
do. On the cell that failed, this predicts +8.7 % where the real run gave
+5.6 %: conservative, in the safe direction.

Usage::

    python scripts/check_grid.py --rho 1.8,2.55,3.1 --n 2,4,8
    python scripts/check_grid.py --prompts prompts/composition.json \\
        --rho 4.0 --n 3,8 --split final
    python scripts/check_grid.py --suggest --n 2,4,8      # propose a grid

Exit code 1 if any cell would drift outside tolerance, so a runner can gate on
it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_v0.backends import MockBackend  # noqa: E402
from swarmbly_v0.experiment import (DEFAULT_PROMPTS_PATH, RHO_TOLERANCE,  # noqa: E402
                                    load_prompts, predict_rho, _answer_budget)
from swarmbly_v0.packing import packing_ceiling, packing_floor  # noqa: E402
from swarmbly_v0.planner import global_contract, plan as build_plan  # noqa: E402


def _cells(corpus: str, split: str | None, rhos, ns):
    backend = MockBackend()
    for spec in load_prompts(corpus, split=split):
        contract = global_contract(spec.text, backend,
                                   target_length_tokens=_answer_budget(spec, 420))
        for n_tasks in ns:
            plan = build_plan(spec.text, backend, n_tasks=n_tasks,
                              contract=contract,
                              answer_sheet=spec.has_ground_truth)
            floor = packing_floor(contract, plan)
            ceiling = packing_ceiling(contract, plan)
            for rho in rhos:
                yield (spec.prompt_id, rho, n_tasks, floor, ceiling,
                       predict_rho(spec, contract, plan, rho))


def _verdict(rho: float, floor: float, ceiling: float, achieved: float) -> str:
    if rho < floor:
        return "BELOW FLOOR"
    if rho > ceiling:
        return "ABOVE CEILING"
    if abs(achieved - rho) / rho > RHO_TOLERANCE:
        return "DRIFT"
    return "ok"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompts", default=str(DEFAULT_PROMPTS_PATH))
    parser.add_argument("--split", default=None, choices=("dev", "final"))
    parser.add_argument("--rho", default="1.8,2.55,3.1,3.95,4.3,4.6")
    parser.add_argument("--n", default="2,4,8")
    parser.add_argument("--suggest", action="store_true",
                        help="scan a fine grid and print the rho values that "
                             "hold for every prompt at each N")
    parser.add_argument("--quiet", action="store_true",
                        help="print only the cells that fail")
    args = parser.parse_args(argv)

    ns = [int(v) for v in args.n.split(",") if v.strip()]

    if args.suggest:
        candidates = [round(1.0 + 0.05 * i, 2) for i in range(120)]
        holds: dict[int, list[float]] = {n: [] for n in ns}
        for n_tasks in ns:
            for rho in candidates:
                bad = any(_verdict(r, f, c, a) != "ok"
                          for _, r, n, f, c, a in _cells(args.prompts, args.split,
                                                         [rho], [n_tasks]))
                if not bad:
                    holds[n_tasks].append(rho)
        print(f"corpus {args.prompts}"
              + (f" split={args.split}" if args.split else ""))
        for n_tasks in ns:
            values = holds[n_tasks]
            span = f"{values[0]} .. {values[-1]}" if values else "NONE"
            print(f"  N={n_tasks}: {len(values):>3} usable rho values   {span}")
        every = sorted(set.intersection(*(set(v) for v in holds.values()))) if all(
            holds.values()) else []
        print(f"  usable at EVERY N: {every[:12]}{' ...' if len(every) > 12 else ''}")
        if not every:
            print("  no rho holds at every N -- the grid must be uneven across N")
        return 0

    rhos = [float(v) for v in args.rho.split(",") if v.strip()]
    failures = 0
    dropped = 0
    checked = 0
    print(f"{'prompt':30} {'rho':>5} {'N':>2} {'floor':>6} {'ceil':>7} "
          f"{'predicted':>9} {'drift':>7}  verdict")
    for prompt_id, rho, n_tasks, floor, ceiling, achieved in _cells(
            args.prompts, args.split, rhos, ns):
        checked += 1
        verdict = _verdict(rho, floor, ceiling, achieved)
        # Only DRIFT is a failure. Below floor and above ceiling are DROPPED by
        # `publishable` -- expected, and the grid is uneven across N on purpose,
        # so counting them as failures would condemn every honest grid. Drift is
        # the one that aborts the tier, and the one that quietly mislabels a
        # published cell when it stays inside tolerance.
        if verdict == "DRIFT":
            failures += 1
        elif verdict != "ok":
            dropped += 1
        if verdict != "ok" or not args.quiet:
            drift = (achieved - rho) / rho * 100
            print(f"{prompt_id:30} {rho:>5} {n_tasks:>2} {floor:>6.2f} "
                  f"{ceiling:>7.2f} {achieved:>9.3f} {drift:>+6.1f}%  {verdict}")

    print(f"\n{checked} cells checked.")
    print(f"  {dropped:>3} will be DROPPED (below floor or above ceiling). Expected: the")
    print( "      grid is uneven across N on purpose and publishable() removes them.")
    print(f"  {failures:>3} would DRIFT outside tolerance. Each one aborts the tier, or")
    print( "      -- worse -- stays inside tolerance and mislabels a published cell.")
    if failures:
        print("\nFix the grid before running. `--suggest` prints the rho values that hold.")
    for n_tasks in ns:
        usable = sum(1 for _, r, n, f, c, a in _cells(args.prompts, args.split, rhos, [n_tasks])
                     if _verdict(r, f, c, a) == "ok")
        per_prompt = usable / max(len(load_prompts(args.prompts, split=args.split)), 1)
        print(f"  N={n_tasks}: {per_prompt:.1f} usable rho points per prompt"
              + ("   <-- fewer than 3, not a curve" if per_prompt < 3 else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
