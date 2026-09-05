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
from .schema import _source_files, source_fingerprint
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
    run.add_argument("--split", choices=("dev", "final"), default=None,
                     help="run only one half of a corpus that declares a split. "
                          "dev is where thresholds, bin edges and tau_sem are "
                          "fitted; final is evaluated once, afterwards, with "
                          "nothing left to choose. Omit for a corpus with no "
                          "split.")
    run.add_argument("--out", default="results/", help="output directory")
    run.add_argument("--seed", type=int, default=0, help="global seed (default: 0)")
    run.add_argument("--candidates", type=int, default=2,
                     help="candidate generations per micro-task (default: 2)")
    run.add_argument("--beta", type=float, default=0.5,
                     help="F-beta weight for tau calibration; must be < 1 (default: 0.5)")
    run.add_argument("--tau", type=float, default=None,
                     help="fix tau_sem instead of calibrating it (discouraged)")
    run.add_argument("--declare", action="append", default=None,
                     metavar="CATEGORY@rho=R@N=n@k=K",
                     help="name the cell this run is testing, BEFORE it runs. The "
                          "verdict for that one cell -- point estimate, bootstrap "
                          "interval clustered by prompt, and pass/fail on the UPPER "
                          "bound -- is then printed as the run's headline. May be "
                          "given twice: the second cell is treated as the control "
                          "and is expected to FAIL. Without this the console prints "
                          "curves and no verdict, and the verdict has to be dug out "
                          "of summary.json.")
    run.add_argument("--declare-composition", action="append", default=None,
                     metavar="CATEGORY@rho=R@N=n@k=K",
                     help="the same declaration, judged on the CONSTRAINT SCORE "
                          "instead of the coherence tax: a paired difference in "
                          "points, clustered by prompt, verdict on the upper "
                          "bound against experiment.COMPOSITION_THRESHOLD_POINTS. "
                          "Use this on a composition corpus. The tax reads +0.000 "
                          "on texts where the constraint score finds a 14-point "
                          "failure, so on prose the tax is the wrong instrument "
                          "and this is the criterion. May be given twice: the "
                          "second cell is the control and is expected to FAIL. No "
                          "verdict is printed below "
                          "experiment.MIN_CLUSTERS_FOR_A_VERDICT prompts.")
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

    prompts = load_prompts(args.prompts, split=args.split)
    if args.split:
        print(f"corpus split: {args.split} ({len(prompts)} prompts)")
    # The split is worth nothing if the final half re-fits the thresholds it is
    # supposed to be evaluated under. tau_sem is the one that moves: it is
    # calibrated inside the run, from that run's own baselines, so a final run
    # left to calibrate itself has learned its threshold from the data it is
    # about to judge -- the leakage the split exists to close, arriving through
    # the split. It must be passed in, from the dev run's run_metadata.json.
    if args.split == "final" and args.tau is None:
        raise SystemExit(
            "refusing to run --split final without --tau.\n"
            "  tau_sem is fitted inside the run unless it is given, so a final "
            "run without it calibrates its threshold on the data it then "
            "evaluates.\n"
            "  Take the value from the dev run: "
            "python -c \"import json;print(json.load("
            "open('results/<dev-run>/run_metadata.json'))['tau_sem'])\"\n"
            "  then pass it as --tau <value>.")
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
    # Which half of the corpus produced these rows, recorded next to them. A
    # split that lives only in the command line cannot be checked afterwards,
    # and "we calibrated on dev" is exactly the kind of claim that needs to
    # survive being asked about six weeks later.
    metadata["corpus"] = str(args.prompts)
    metadata["corpus_split"] = args.split or "(whole corpus)"
    metadata["prompt_ids"] = [s.prompt_id for s in used]
    # The corpus's own digest, so a threshold fitted here can be checked against
    # the corpus it is later applied to. A tau_sem carried from a dev run to a
    # final run is only valid if the prompts did not change in between -- and on
    # 27 August they did, when a tense directive was added to the contract. A
    # bare number passed on the command line cannot carry that fact; this can.
    #
    # TWO digests, deliberately named apart, because they are not the same number
    # and confusing them is its own trap:
    #
    #   corpus_file_sha256   -- the raw bytes. Changes when a comment changes.
    #   corpus_frozen_sha256 -- the corpus's own `_frozen.sha256`, over id, split
    #                           and prompt text only. This is the one
    #                           `make_tables.py --verify` prints, and the one a
    #                           frozen threshold is pinned to.
    #
    # An earlier draft recorded only the file digest and the runbook told the
    # reader to compare it against what --verify prints. They can never match.
    try:
        import hashlib
        raw = Path(args.prompts).read_bytes()
        metadata["corpus_file_sha256"] = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        metadata["corpus_frozen_sha256"] = str(
            (payload.get("_frozen") or {}).get("sha256", "")
            if isinstance(payload, dict) else "")
    except (OSError, ValueError):
        metadata["corpus_file_sha256"] = ""
        metadata["corpus_frozen_sha256"] = ""

    # WHICH CODE produced this run. Corpus digests said what was measured;
    # nothing said what did the measuring, and on 27 August that gap cost real
    # confusion: three tables-* runs sat side by side, two of them scored by an
    # arm-neutral metric and one by the defective one, and the only way to tell
    # them apart was the directory timestamp against a memory of when the fix
    # landed. A results directory has to be self-describing.
    metadata["code_sha256"] = source_fingerprint()
    metadata["code_files"] = len(_source_files())
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
    # The below-floor exclusion, printed FIRST and unconditionally.
    #
    # `publishable()` drops rows whose rho_target sat below their own packing
    # floor, and until this block existed it did so silently: the field went into
    # summary.json and nothing put it on screen. An operator watching a tier
    # finish saw a curve with rows missing and no reason given -- which is how
    # V0's below-floor grid became a published headline in the first place. A
    # gate the operator cannot see is a gate that gets argued with later.
    excluded = int(stats.get("rows_excluded_below_floor") or 0)
    if excluded:
        by_reason = stats.get("rows_excluded_by_reason") or {}
        below = int(by_reason.get("below_packing_floor") or 0)
        above = int(by_reason.get("above_packing_ceiling") or 0)
        refused = int(by_reason.get("plan_refused") or 0)
        print(f"\n*** {excluded} row(s) DROPPED and they are not one problem. ***")
        if below:
            print(f"    {below} BELOW the packing floor. Every packet collapses to its bare")
            print("      task, so the rho axis does not move and two rho labels give")
            print("      byte-identical cells. Raise the grid.")
        if above:
            print(f"    {above} ABOVE the packing ceiling. The expansion block list is FINITE,")
            print("      so a packet cannot spend that budget and the cell undershoots its")
            print("      own label. Lower the grid. This used to ABORT the whole tier: on")
            print("      4 September one unreachable cell of 144 destroyed 143 measured")
            print("      ones after five hours.")
        forced = int(by_reason.get("forced_above_target_by_carry") or 0)
        if forced:
            print(f"    {forced} FORCED above the target by mandatory carries. On a chain the")
            print("      predecessor value a task consumes is not optional, so the packet")
            print("      pays for it whatever the budget says. rho was never the independent")
            print("      variable in those cells. This used to ABORT the tier as a drift")
            print("      violation, on the one configuration the packer documents as")
            print("      overshooting BY DESIGN.")
        if refused:
            print(f"    {refused} the planner REFUSED to fragment. No rho would have helped;")
            print("      the prompt states its questions apart from its material and the")
            print("      link is not recoverable.")
        print("    All of them are in results.csv. None appears in any figure.")

    print("\ncoherence tax (relative degradation vs monolithic), mean over prompts and N:")
    def _pct(value: float | None) -> str:
        return f"{value * 100:+7.2f}%" if isinstance(value, (int, float)) else "    n/a "
    for point in stats["curve"]:
        # `n_cells` was computed from the start and never printed, so a mean over
        # ONE surviving cell read exactly like a mean over forty. On the smoke
        # tier that is the difference between "-16.67 %" and "-16.67 %, n=1".
        n_cells = point.get("n_cells")
        n_text = f"  [n={n_cells}]" if n_cells is not None else ""
        thin = isinstance(n_cells, int) and 0 < n_cells < 3
        print(
            f"  rho={point['rho']:<5g} (achieved {point['rho_achieved_mean']:.2f})  "
            f"BooookScore-like {_pct(point['coherence_tax_booook'])}   "
            f"entity-grid {_pct(point['coherence_tax_entity_grid'])}{n_text}"
            + ("   <- too few cells to read as a mean" if thin else "")
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
        n_units = calibration.get("n_units") or 0
        rate = calibration.get("acceptance_rate")
        # A correlation is unreadable when the judge has almost no variance to
        # correlate against, and "almost" starts well below SATURATION_LIMIT. On
        # the smoke tier the judge accepted 89.4 % -- six tenths of a point under
        # the flag -- and r = +0.224 over 47 units printed as though it meant
        # something. It is exactly the shape of the figure this project already
        # withdrew once. So the number is withheld, not annotated: a caveat
        # beside a printed r does not travel with the r.
        # Two different reasons to withhold, and they must not share a sentence.
        # A judge at 89 % acceptance has almost no variance to correlate against;
        # a judge at 50 % has the most variance available and simply has not been
        # asked enough questions. Saying "that little variance" about the second
        # is wrong, and a wrong explanation invites the reader to dismiss it.
        saturated = bool(calibration.get("saturated")) or (
            isinstance(rate, (int, float)) and (rate >= 0.85 or rate <= 0.15))
        underpowered = n_units < 100
        rate_text = (f", acceptance {rate * 100:.1f}%"
                     if isinstance(rate, (int, float)) else "")
        if saturated or underpowered:
            print(f"  agreement vs judged quality: NOT MEASURED here "
                  f"({n_units} units{rate_text})")
            if saturated:
                print("  The judge has almost no variance to correlate against, so a "
                      "correlation cannot")
                print("  appear whether or not the signal is there. This is the "
                      "instrument that made")
                print("  the 14 August result uninterpretable.")
            if underpowered:
                print("  Too few units for a correlation to mean anything, whatever "
                      "the judge does.")
            print("  Grade against an answer key (the v3c-gt tier), not a peer-class "
                  "judge.")
        else:
            r_text = f"{r_value:+.3f}" if isinstance(r_value, (int, float)) else "undefined"
            print(f"  agreement vs judged quality: r = {r_text} "
                  f"over {n_units} units "
                  f"(acceptance rate {rate * 100:.1f}%)")
        print("  agreement is not truth: models sharing training data share errors, so "
              "this correlation must be measured, not assumed. Four measurements to "
              "date say there is nothing to find -- see docs/REVISION_2026-08-12.md.")

    # The declared cell, printed as the headline it is.
    #
    # tables-dev exists to test ONE named cell and it printed everything except
    # that cell. The console led with "+8.95%", a mean pooling N=2 and N=8 --
    # the arm under test averaged with the control that is required to fail --
    # while the actual verdict (+4.24 %, CI [-4.09 %, +10.59 %], NOT MET) and the
    # control's (+13.67 %, CI [+7.15 %, +19.30 %]) appeared nowhere on screen and
    # had to be dug out of summary.json.
    #
    # The cell is named on the command line rather than inferred, so that the
    # declaration is a fact about the invocation -- recoverable from run.log and
    # from the shell history -- and not a paragraph the tier prints about itself.
    for position, key in enumerate(getattr(args, "declare", None) or []):
        cell = stats.get("falsifiable_go_no_go", {}).get(key)
        role = "DECLARED CELL" if position == 0 else "CONTROL (must fail)"
        print(f"\n{'=' * 72}\n{role}: {key}")
        if cell is None:
            available = sorted(stats.get("falsifiable_go_no_go", {}))
            print("  NOT PRESENT in this run. The declared cell was not measured, so")
            print("  this run has no verdict. Check the spelling against the grid:")
            for name in available[:6]:
                print(f"    {name}")
            if len(available) > 6:
                print(f"    ... and {len(available) - 6} more")
            continue
        lo, hi = cell["ci95"]
        passed = bool(cell["passed"])
        print(f"  point estimate      {cell['point_estimate'] * 100:+.2f}%")
        print(f"  95% CI (by prompt)  [{lo * 100:+.2f}%, {hi * 100:+.2f}%]")
        print(f"  criterion           upper bound below {cell['threshold'] * 100:.0f}%")
        print(f"  n_prompts           {cell['n_prompts']}   "
              f"(the sample size that matters; rows from one prompt share its difficulty)")
        print(f"  VERDICT             {'MET' if passed else 'NOT MET'}"
              + ("" if passed else
                 f"  -- short by {(hi - cell['threshold']) * 100:.2f} points on the upper bound"))
        if position > 0:
            # A control that passes is worse news than a declared cell that fails.
            print("  control reading     "
                  + ("*** THE CONTROL PASSED. The instrument is not discriminating "
                     "between N=2 and N=8, so NEITHER number is evidence. ***"
                     if passed else
                     "fails as required -- the instrument separates the arms."))
    if getattr(args, "declare", None):
        print("=" * 72)

    # The same headline on the constraint score, for a composition corpus.
    #
    # Kept separate from `--declare` rather than folded into it, because the two
    # criteria are not the same claim and must not be printed as though they
    # were: the tax is a relative degradation in coherence against a saturated
    # judge, and this is an absolute difference in checks a text either satisfies
    # or does not. On the free-form run of 3 September the tax read +0.000 on the
    # three compositions while this one found 14 to 21 points. A run that printed
    # a single "verdict" pooling those would be reporting the mean of a
    # measurement and a blind spot.
    for position, key in enumerate(getattr(args, "declare_composition", None) or []):
        cell = stats.get("composition_criterion", {}).get(key)
        role = ("DECLARED CELL, constraint score"
                if position == 0 else "CONTROL, constraint score (must fail)")
        print(f"\n{'=' * 72}\n{role}: {key}")
        if cell is None:
            available = sorted(stats.get("composition_criterion", {}))
            print("  NOT PRESENT in this run. The declared cell was not measured, so")
            print("  this run has no verdict. Check the spelling against the grid:")
            for name in available[:6]:
                print(f"    {name}")
            if len(available) > 6:
                print(f"    ... and {len(available) - 6} more")
            if not available:
                print("    (none -- no fragmented row in this run carried a "
                      "constraint score, so the corpus has no compositions)")
            continue
        threshold = float(cell["declared_cell"]["threshold_points"])
        print(f"  monolithic          {cell['mean_baseline']:.3f}"
              f"   (of which {cell['baseline_at_ceiling']} of "
              f"{cell['n_observations']} at 1.000)")
        print(f"  fragmented          {cell['mean_fragmented']:.3f}")
        print(f"  paired difference   {cell['mean_delta'] * 100:+.2f} points"
              f"   median {cell['median_delta'] * 100:+.2f}")
        interval = cell.get("mean_ci95")
        if interval:
            print(f"  95% CI (by prompt)  [{interval[0] * 100:+.2f}, "
                  f"{interval[1] * 100:+.2f}] points")
        print(f"  criterion           upper bound below "
              f"{threshold * 100:.0f} points")
        print(f"  n_prompts           {cell['n_prompts']}   "
              f"(floor {cell['declared_cell']['min_clusters']}; "
              f"rows from one prompt share its difficulty)")
        if cell.get("passed") is None:
            # No verdict is a result, and it must not read like a near miss.
            print("  VERDICT             NONE -- this run cannot answer the question")
            print(f"  reason              {cell.get('note', '')}")
            continue
        passed = bool(cell["passed"])
        print(f"  VERDICT             {'MET' if passed else 'NOT MET'}"
              + ("" if passed else
                 f"  -- over by {cell['short_by_points'] * 100:.2f} points on "
                 f"the upper bound"))
        if position > 0:
            print("  control reading     "
                  + ("*** THE CONTROL PASSED. The instrument is not separating "
                     "the arms, so NEITHER number is evidence. ***"
                     if passed else
                     "fails as required -- the instrument separates the arms."))
    if getattr(args, "declare_composition", None):
        print("=" * 72)

    # The old criterion, printed as what it is.
    #
    # "exists (category, rho) with relative degradation < 5 %" is a maximum
    # statistic over many noisy cells with no multiple-comparison control.
    # Simulating its own null -- no cell genuinely different, observations
    # shuffled between the 32 cells of n=3 -- gives P(some cell under 5 %) = 100 %.
    # It would have passed on random data, and its passing was never evidence.
    #
    # It stays in summary.json so old runs remain comparable, and it is printed
    # because deleting it would make an old run's history unreadable. But it is
    # NOT printed as a verdict any more: a line reading "go/no-go: MET" is quoted
    # from a terminal within the day, and this one said MET on a two-prompt smoke
    # run that measures nothing. `falsifiable_go_no_go` is the criterion --
    # cell named in advance, judged on the upper bound of a clustered bootstrap,
    # with a control required to fail.
    go = stats["go_no_go"]
    print(f"\n[superseded] maximum-statistic criterion (<5% in SOME category): "
          f"{'passes' if go['passed'] else 'does not pass'} "
          f"({len(go['passing_cells'])} passing cells) -- not a verdict.")
    print("             This statistic passes on random data. Read "
          "falsifiable_go_no_go in")
    print("             summary.json instead: one cell, named before the run, "
          "judged on the")
    print("             upper bound of a bootstrap clustered by prompt, with a "
          "control that must fail.")
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


if __name__ == "__main__":  # pragma: no cover - process entry
    # `python -m swarmbly_v0.cli run ...` used to import this module, define
    # `main`, and exit 0 without running anything -- no output, no directory, no
    # error. The supported spelling is `python -m swarmbly_v0`, which
    # `__main__.py` dispatches, but a plausible near-miss that exits 0 having
    # done nothing is the same failure shape as the comment inside a line
    # continuation that silently truncated a six-hour run on 3 September. Both
    # spellings now work.
    raise SystemExit(main())
