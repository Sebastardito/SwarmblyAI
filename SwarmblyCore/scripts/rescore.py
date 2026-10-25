#!/usr/bin/env python3
"""Re-score a finished run's assembled answers with the CURRENT metric.

Why this is a tool and not a one-off
------------------------------------

``results.csv`` stores the coherence score as it was computed at run time. When
the metric itself is corrected, every figure in that file is stale, and
``scripts/reanalyse.py`` -- which recomputes statistics *from* the CSV -- will
faithfully reproduce the old, wrong number. That is a trap: the corrected code is
installed, the tool runs clean, and the headline has not moved.

This reads the assembled answers back out of ``composition_traces.md`` and scores
them again through the current metric. It is the only way to apply a metric
correction to a run without spending the GPU again.

What the correction was
-----------------------

The two arms entered ``seam_error_taxonomy`` by different paths: the monolithic
baseline passed ``plan=None``, the fragmented arm passed the plan. Three
consequences, all functions of the partition rather than of the answer:

1. the omission detector's expected set was the union of
   ``plan.tasks[].expected_entities`` -- 0 for a baseline that passes no plan, 6
   at N=2, 17 at N=8 on the table corpus;
2. the identical set of missing entities was attributed round-robin across N
   fragment heads, and the score is ``clean / n_sentences``, so one document's
   omissions dirtied one sentence at monolithic and up to N at N tasks;
3. ``missing_transition`` and a seam-anchored ``dangling_reference`` can only
   fire where fragments meet, and a monolithic answer has no seams.

Scored through both conventions, one identical 16-sentence answer came back
0.9375 and 0.5000 -- an apparent coherence tax of +46.7 % on text that never
changed.

Two things it refuses to guess
------------------------------

**The offsets.** Seam-local errors fire at the sentence indices the assembler
chose, and those are not evenly spaced -- fragments produce different numbers of
sentences. Traces written from 27 August store them; earlier ones do not, and for
those this script **refuses** rather than reconstructing them. That refusal is
not hypothetical: reconstructing them as an even split on the run of 26 August
moved the recomputed score by up to 0.15, and an earlier draft of that run's
correction notice published figures derived exactly that way.

**The join.** Traces and ``results.csv`` are written in the same sweep order, so
zipping them is sound -- and verified rather than assumed. The script recomputes
each answer's score under the *old* convention and checks it against
``booook_like_score``. If the pairing were wrong those numbers would not line up.

Usage::

    python3 scripts/rescore.py results/tables-dev-20260826-115300
    python3 scripts/rescore.py results/<run> --csv corrected.csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarmbly_v0.backends import MockBackend  # noqa: E402
from swarmbly_v0.metrics import seam_error_taxonomy  # noqa: E402
from swarmbly_v0.planner import global_contract, plan as build_plan  # noqa: E402
from swarmbly_v0.report import read_rows  # noqa: E402
from swarmbly_v0.stats import cluster_bootstrap  # noqa: E402
from swarmbly_v0.textutil import split_sentences  # noqa: E402

MIN_BASELINE = 0.15
"""A ratio over a near-zero denominator is not a measurement."""

JOIN_TOLERANCE = 0.02
"""How far a recomputed old-convention score may sit from the CSV's before the
join is treated as unsound. Not zero: the trace stores the text, and a stored
text re-split into sentences can differ by one boundary from the live object."""


def parse_traces(path: Path) -> list[dict[str, Any]]:
    """``{prompt_id, label, text, offsets}`` in file order.

    ``offsets`` is empty for traces written before 27 August, and that is the
    condition this script refuses on: the seam-local classes fire at the
    sentences the assembler's offsets name, those offsets are not evenly spaced,
    and reconstructing them as an even split reproduces neither the seam
    positions nor the score.
    """
    raw = path.read_text(encoding="utf-8")
    out: list[dict[str, Any]] = []
    header: tuple[str, str] | None = None
    offsets: list[int] = []
    for block in raw.split("<details><summary>Generated text</summary>"):
        found, seen_offsets = None, []
        for line in block.splitlines():
            match = re.match(r"^## ([\w.\-]+) — (.+)$", line)
            if match:
                found, seen_offsets = match, []
            off = re.match(r"^`offsets: \[([\d,\s]*)\]`$", line.strip())
            if off:
                seen_offsets = [int(x) for x in off.group(1).split(",") if x.strip()]
        fence = re.search(r"```\n(.*?)\n```", block, re.S)
        if header and fence:
            out.append({"prompt_id": header[0], "label": header[1],
                        "text": fence.group(1), "offsets": offsets})
        header = (found.group(1), found.group(2).strip()) if found else None
        offsets = seen_offsets
    return out


def _score(text: str, contract: Any, prompt: str, backend: Any,
           n_tasks: int | None, expected: list[str] | None,
           offsets: list[int] | None = None) -> dict[str, float]:
    """Score one answer. ``expected=None`` reproduces the OLD convention.

    ``offsets`` are the assembler's, read back from the trace. They are not
    reconstructed: an even split does not reproduce them, because fragments
    produce different numbers of sentences.
    """
    if n_tasks is None:
        report = seam_error_taxonomy(text, None, None, contract,
                                     expected_entities=expected)
    else:
        built = build_plan(prompt, backend, n_tasks=n_tasks, contract=contract)
        report = seam_error_taxonomy(text, built, offsets, contract,
                                     expected_entities=expected)
    return {"full": report.booook_like_score,
            "comparable": report.comparable_score,
            "seam_rate": report.seam_error_rate}


def analyse(run_dir: Path, corpus_path: Path) -> dict[str, Any]:
    from swarmbly_v0.experiment import PromptSpec, prompt_expected_entities

    rows = read_rows(run_dir / "results.csv")
    corpus = {p["id"]: p for p in json.loads(corpus_path.read_text())["prompts"]}
    backend = MockBackend()
    traces = parse_traces(run_dir / "composition_traces.md")

    # Traces and results.csv are written in the same sweep order, so zipping the
    # fragmented sections against the fragmented rows is sound -- and verified
    # below rather than assumed.
    frag_rows = [r for r in rows if str(r.get("condition", "")).startswith("fragmented")]
    frag_traces = [t for t in traces if not t["label"].startswith("monolithic")]
    mono_text = {t["prompt_id"]: t["text"] for t in traces
                 if t["label"].startswith("monolithic")}

    missing_offsets = [t for t in frag_traces if not t["offsets"]]
    if missing_offsets:
        raise SystemExit(
            f"{len(missing_offsets)} of {len(frag_traces)} fragmented traces carry no "
            f"`offsets:` line, so this run CANNOT be re-scored exactly.\n\n"
            f"The seam-local error classes fire at the sentence indices the assembler "
            f"chose, those indices are not evenly spaced, and reconstructing them as an "
            f"even split reproduces neither the seam positions nor the score. Traces "
            f"written before 27 August do not store them.\n\n"
            f"The corrected figure for this run can only come from running it again:\n"
            f"    bash scripts/run_ollama.sh tables-dev\n\n"
            f"Refusing to print a number that would look like a measurement and would "
            f"not be one.")

    if len(frag_rows) != len(frag_traces):
        raise SystemExit(
            f"cannot join: {len(frag_rows)} fragmented rows against "
            f"{len(frag_traces)} fragmented traces. The trace file and the CSV "
            f"do not describe the same run.")

    results: list[dict[str, Any]] = []
    drift: list[float] = []
    for row, trace in zip(frag_rows, frag_traces):
        pid = str(row["prompt_id"])
        trace_pid, label, text = trace["prompt_id"], trace["label"], trace["text"]
        if trace_pid != pid:
            raise SystemExit(
                f"cannot join: results.csv row {pid} against trace {trace_pid}. "
                f"Order differs; refusing to report a corrected figure.")
        spec_data = corpus[pid]
        contract = global_contract(spec_data["prompt"], backend)
        spec = PromptSpec(prompt_id=pid, category=spec_data["category"],
                          expected_decomposable=True, text=spec_data["prompt"])
        expected = prompt_expected_entities(spec, contract, backend)
        n_tasks = int(float(row["n_tasks"]))

        old = _score(text, contract, spec_data["prompt"], backend, n_tasks, None,
                     trace["offsets"])
        new = _score(text, contract, spec_data["prompt"], backend, n_tasks, expected,
                     trace["offsets"])
        base_old = _score(mono_text[pid], contract, spec_data["prompt"], backend,
                          None, None)
        base_new = _score(mono_text[pid], contract, spec_data["prompt"], backend,
                          None, expected)

        drift.append(abs(old["full"] - float(row["booook_like_score"])))
        results.append({
            "prompt_id": pid, "n_tasks": n_tasks, "k": int(float(row["k"])),
            "label": label,
            "tax_as_reported": float(row["coherence_tax_booook"]),
            "tax_recomputed_old": ((base_old["full"] - old["full"]) / base_old["full"]
                                   if base_old["full"] >= MIN_BASELINE else None),
            "tax_corrected": ((base_new["comparable"] - new["comparable"])
                              / base_new["comparable"]
                              if base_new["comparable"] >= MIN_BASELINE else None),
            "seam_rate": new["seam_rate"],
            "baseline_comparable": base_new["comparable"],
        })

    worst = max(drift) if drift else 0.0
    if worst > JOIN_TOLERANCE:
        raise SystemExit(
            f"JOIN CHECK FAILED. Recomputing the old-convention score from the "
            f"traces differs from results.csv by up to {worst:.4f} (tolerance "
            f"{JOIN_TOLERANCE}). The trace sections are probably paired with the "
            f"wrong rows. Refusing to report a corrected figure.")

    return {"run": str(run_dir), "join_max_drift": round(worst, 6),
            "rows": results}


def report(result: dict[str, Any]) -> None:
    print(f"\n=== {result['run']} — re-scored with the current metric ===")
    print(f"join verified: old-convention scores match results.csv to "
          f"{result['join_max_drift']:.4f}\n")

    cells: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in result["rows"]:
        cells.setdefault((row["n_tasks"], row["k"]), []).append(row)

    print(f"{'cell':<12} {'as reported':>12} {'corrected':>11} {'moved':>8} "
          f"{'seam/sent':>10}   95% CI of the corrected tax")
    print("-" * 88)
    for (n_tasks, k), group in sorted(cells.items()):
        reported = [r["tax_as_reported"] for r in group]
        corrected = [r for r in group if r["tax_corrected"] is not None]
        if not corrected:
            print(f"N={n_tasks} k={k}      no cell above the baseline floor")
            continue
        mean_reported = sum(reported) / len(reported)
        mean_corrected = sum(r["tax_corrected"] for r in corrected) / len(corrected)
        seam = sum(r["seam_rate"] for r in group) / len(group)
        interval = cluster_bootstrap(
            [{"prompt_id": r["prompt_id"], "v": r["tax_corrected"]} for r in corrected],
            lambda rs: sum(x["v"] for x in rs) / len(rs) if rs else None)
        span = (f"[{interval['ci95'][0]:+.1%}, {interval['ci95'][1]:+.1%}]"
                if interval.get("ci95") else "not estimable")
        print(f"N={n_tasks} k={k}      {mean_reported:>+12.1%} {mean_corrected:>+11.1%} "
              f"{mean_reported - mean_corrected:>+8.1%} {seam:>10.3f}   {span}")

    print("\n  'moved' is how much of the reported figure was the instrument "
          "rather than the answer.")
    print("  'seam/sent' is the cost specific to assembly, which the baseline "
          "cannot incur at all")
    print("  and which therefore belongs beside the tax rather than inside it.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--prompts", default=None,
                        help="corpus file; defaults to the one in run_metadata.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    for needed in ("results.csv", "composition_traces.md"):
        if not (run_dir / needed).exists():
            print(f"{run_dir / needed} does not exist", file=sys.stderr)
            return 1

    corpus = args.prompts
    if corpus is None:
        meta = run_dir / "run_metadata.json"
        corpus = json.loads(meta.read_text()).get("corpus") if meta.exists() else None
    if not corpus or not Path(corpus).exists():
        print("pass --prompts: the corpus this run used could not be located",
              file=sys.stderr)
        return 1

    result = analyse(run_dir, Path(corpus))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
