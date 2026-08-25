"""Command line interface for the V0 coherence-tax experiment.

::

    python -m swarmbly_v0 run --rho 1.0,1.25,1.5,2.0 --n 2,4,8 --k 1,3 --backend mock --out results/
    python -m swarmbly_v0 report results/results.csv --out results/report.html
    python -m swarmbly_v0 route --prompts prompts/prompts.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .backends import get_backend, get_embedder
from .experiment import (
    DEFAULT_PROMPTS_PATH,
    SweepConfig,
    load_prompts,
    run_sweep,
    summarize,
    write_csv,
)
from .report import render_report
from .router import DEFAULT_THRESHOLD, evaluate_router, is_decomposable

__all__ = ["main", "build_parser"]


def _floats(text: str) -> tuple[float, ...]:
    return tuple(float(part) for part in text.split(",") if part.strip())


def _ints(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split(",") if part.strip())


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for ``python -m swarmbly_v0``."""
    parser = argparse.ArgumentParser(
        prog="swarmbly_v0",
        description="Swarmbly AI V0: measure the coherence tax of fragmented inference.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the rho x N sweep and write results.csv")
    run.add_argument("--rho", type=_floats, default=(1.0, 1.25, 1.5, 2.0),
                     help="comma-separated rho targets (default: 1.0,1.25,1.5,2.0)")
    run.add_argument("--n", type=_ints, default=(2, 4, 8),
                     help="comma-separated micro-task counts (default: 2,4,8)")
    run.add_argument("--k", type=_ints, default=(1,),
                     help="comma-separated replica counts for micro-level consensus; "
                          "k>1 dispatches k complete replicas of each micro-task to "
                          "different model families (default: 1)")
    run.add_argument("--typed-carry", action="store_true",
                     help="also run the typed-carry arm, paired with each prose-summary "
                          "cell: a predecessor's labelled values travel verbatim instead "
                          "of as a rationed prose summary")
    run.add_argument("--editor", action="store_true",
                     help="also run the post-processing editor arm, paired with each "
                          "unedited cell (adds one condition, not one flag)")
    run.add_argument("--backend", default="mock",
                     help="mock | openai (any OpenAI-compatible endpoint)")
    run.add_argument("--embedder", default="hash",
                     help="hash | st | api (api = the generation server's own /embeddings "
                          "route, e.g. Ollama nomic-embed-text; recommended for real runs)")
    run.add_argument("--prompts", default=str(DEFAULT_PROMPTS_PATH),
                     help="path to the labelled prompt corpus")
    run.add_argument("--out", default="results/", help="output directory")
    run.add_argument("--seed", type=int, default=0, help="global seed (default: 0)")
    run.add_argument("--candidates", type=int, default=2,
                     help="candidate generations per micro-task (default: 2)")
    run.add_argument("--beta", type=float, default=0.5,
                     help="F-beta weight for tau calibration; must be < 1 (default: 0.5)")
    run.add_argument("--tau", type=float, default=None,
                     help="fix tau_sem instead of calibrating it (discouraged)")
    run.add_argument("--max-prompts", type=int, default=None,
                     help="use only the first K prompts (for smoke runs)")
    run.add_argument("--router-threshold", type=float, default=DEFAULT_THRESHOLD,
                     help=f"router decision threshold (default: {DEFAULT_THRESHOLD})")
    run.add_argument("--quiet", action="store_true", help="suppress per-cell progress lines")
    run.add_argument("--no-report", action="store_true",
                     help="do not render report.html after the sweep")

    report = sub.add_parser("report", help="render an HTML report from a results CSV")
    report.add_argument("csv", help="path to results.csv")
    report.add_argument("--out", default=None,
                        help="output HTML path (default: <csv dir>/report.html)")
    report.add_argument("--prompts", default=str(DEFAULT_PROMPTS_PATH),
                        help="prompt corpus, used for the router table")

    route = sub.add_parser("route", help="evaluate the decomposability router on the corpus")
    route.add_argument("--prompts", default=str(DEFAULT_PROMPTS_PATH))
    route.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts = load_prompts(args.prompts)
    config = SweepConfig(
        rhos=tuple(args.rho),
        ns=tuple(args.n),
        ks=tuple(args.k),
        editors=(False, True) if args.editor else (False,),
        carries=(False, True) if args.typed_carry else (False,),
        seed=args.seed,
        backend_name=args.backend,
        embedder_name=args.embedder,
        n_candidates=args.candidates,
        beta=args.beta,
        tau_sem=args.tau,
        router_threshold=args.router_threshold,
        max_prompts=args.max_prompts,
    )
    backend = get_backend(args.backend, seed=args.seed)
    embedder = get_embedder(args.embedder)

    def progress(message: str) -> None:
        if not args.quiet:
            print(message, flush=True)

    rows, metadata = run_sweep(prompts, config, backend, embedder, progress=progress)
    csv_path = write_csv(rows, out_dir / "results.csv")

    used = prompts[: args.max_prompts] if args.max_prompts else prompts
    stats = summarize(rows, used, args.router_threshold)
    (out_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    (out_dir / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\nwrote {csv_path} ({len(rows)} rows)")
    print(f"wrote {out_dir / 'summary.json'}")
    if stats.get("headline_restricted_to_k"):
        print(f"\nheadline taken from k={stats['headline_k']} "
              f"(run spans k={stats['ks_present']}); k is a separate axis and "
              "averaging it into the tax would report a number belonging to neither.")
    print("\ncoherence tax (relative degradation vs monolithic), mean over prompts and N:")
    def _pct(value: float | None) -> str:
        return f"{value * 100:+7.2f}%" if isinstance(value, (int, float)) else "    n/a "
    for point in stats["curve"]:
        print(
            f"  rho={point['rho']:<5g} (achieved {point['rho_achieved_mean']:.2f})  "
            f"BooookScore-like {_pct(point['coherence_tax_booook'])}   "
            f"entity-grid {_pct(point['coherence_tax_entity_grid'])}"
        )
        print(
            f"           absolute difference   "
            f"BooookScore-like {point['abs_delta_booook']:+7.4f}    "
            f"entity-grid {point['abs_delta_entity_grid']:+7.4f}   "
            f"(denominator-free)"
        )
    unstable = stats.get("unstable_cells", {})
    dropped = unstable.get("excluded_booook", 0) + unstable.get("excluded_entity_grid", 0)
    if dropped:
        print(
            f"  NOTE: {unstable['excluded_booook']} BooookScore and "
            f"{unstable['excluded_entity_grid']} entity-grid cells were excluded from the "
            f"relative means because their monolithic baseline fell below "
            f"{unstable['min_baseline']}. A ratio over a near-zero denominator is not a "
            f"measurement; the absolute differences above include every cell."
        )
    consensus_curve = [c for c in stats.get("consensus_curve", []) if int(c["k"]) > 1]
    if consensus_curve:
        print("\nmicro-level consensus (k complete replicas per micro-task):")
        for point in consensus_curve:
            print(
                f"  k={point['k']:<3g} families={point['n_families_mean']:.1f}  "
                f"mean agreement {point['mean_agreement']:.3f}   "
                f"HIGH {point['frac_high'] * 100:5.1f}%  "
                f"MEDIUM {point['frac_medium'] * 100:5.1f}%  "
                f"LOW {point['frac_low'] * 100:5.1f}%  "
                f"({point['n_low_conf_regions']} low-confidence regions)"
            )
        calibration = stats["agreement_quality_correlation"]
        r_value = calibration.get("pearson_r")
        r_text = f"{r_value:+.3f}" if isinstance(r_value, (int, float)) else "undefined"
        print(f"  agreement vs judged quality: r = {r_text} "
              f"over {calibration['n_units']} units "
              f"(acceptance rate {calibration['acceptance_rate'] * 100:.1f}%)")
        print("  agreement is not truth: models sharing training data share errors, so "
              "this correlation must be measured, not assumed.")

    go = stats["go_no_go"]
    print(f"\ngo/no-go (<5% in at least one category): "
          f"{'MET' if go['passed'] else 'NOT MET'} "
          f"({len(go['passing_cells'])} passing cells)")
    if metadata.get("harness_validation_only"):
        print("\n*** MockBackend: these numbers validate the harness. They are NOT "
              "evidence about real models. ***")

    if not args.no_report:
        html_path = render_report(csv_path, out_dir / "report.html", metadata, used)
        print(f"wrote {html_path}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"error: {csv_path} does not exist", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else csv_path.parent / "report.html"
    try:
        prompts = load_prompts(args.prompts)
    except (OSError, KeyError, ValueError):
        prompts = None
    path = render_report(csv_path, out, None, prompts)
    print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


def _cmd_route(args: argparse.Namespace) -> int:
    prompts = load_prompts(args.prompts)
    print(f"{'prompt':<32} {'category':<20} {'exp':<5} {'pred':<5} {'score':<7} ok")
    for spec in prompts:
        decision = is_decomposable(spec.text, args.threshold)
        ok = "yes" if decision.decomposable == spec.expected_decomposable else "NO"
        print(f"{spec.prompt_id:<32} {spec.category:<20} "
              f"{str(spec.expected_decomposable):<5} {str(decision.decomposable):<5} "
              f"{decision.score:<7.3f} {ok}")
    evaluation = evaluate_router(
        [(p.text, p.expected_decomposable) for p in prompts], args.threshold
    )
    print(f"\nthreshold={evaluation.threshold:.2f}  accuracy={evaluation.accuracy:.2f}  "
          f"precision={evaluation.precision:.2f}  recall={evaluation.recall:.2f}  "
          f"FPR={evaluation.false_positive_rate:.2f}  "
          f"(TP={evaluation.true_positive} FP={evaluation.false_positive} "
          f"TN={evaluation.true_negative} FN={evaluation.false_negative})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "route":
        return _cmd_route(args)
    parser.error(f"unknown command {args.command!r}")
    return 2
