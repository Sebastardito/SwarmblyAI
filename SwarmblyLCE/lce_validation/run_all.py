"""Run every instrument test and the mock experiments; write results.json and REPORT.md.

    python -m lce_validation.run_all            # writes into results/harness/
    python -m lce_validation.run_all --out DIR

The default output lies outside the directories that ``run_real`` requires to be
clean (``swarmbly_lce/``, ``lce_validation/``, ``docs/``), so running the harness
before a confirmatory run never turns that run exploratory.

Exit status is 1 if any instrument fails: a failed instrument cannot decide
its hypothesis, and the whitepaper's experiments must not be run on it.

THE OUTPUT OF THIS SCRIPT IS NOT EVIDENCE. Instruments are simulations and
experiments use MockBackend; both exist to show that the measurements respond
to what they measure. See run_real.py for runs against real models.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from swarmbly_lce.backends import MockBackend
from swarmbly_lce.report import run_header

from . import experiments as E
from . import instruments as I

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "results" / "harness"

BANNER = ("> **SIMULATION AND MOCK RUN — NOT EVIDENCE.** Instruments are simulations; experiments use `MockBackend`, "
          "which answers by rules and injects the effects being measured. These numbers show that each measurement "
          "responds to what it measures. No figure here may be cited as a result about language models or about the LCE.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    instruments = {name: fn(seed=args.seed) for name, fn in I.ALL.items()}
    mb = MockBackend(seed=args.seed)
    wiki, wstats = E.build_wiki(E.FIXTURES / "corpus", E.FIXTURES / "policy.json", mb)
    families = [MockBackend(family=f, seed=args.seed) for f in ("fam-a", "fam-b", "fam-c")]
    experiments = {
        "build_wiki": wstats,
        "C1": E.c1_memory(mb, wiki),
        "C2": E.c2_projection(families, mb),
        "C10_sim": {k: v for k, v in E.c10_selection(seed=args.seed).items() if k != "history"},
        "canary": E.canary_check(mb, wiki),
    }
    results = {"header": run_header("simulation", "MockBackend + numpy simulations", seed=args.seed),
               "instruments": instruments, "experiments_mock": experiments}
    # Salida determinista y versionable: sin tiempos de reloj (los tiempos
    # pertenecen a las corridas reales) y flotantes redondeados a 9
    # decimales (estabilidad entre versiones de numpy; R14 fija el entorno).
    def _stable(o):
        if isinstance(o, dict):
            return {k: _stable(v) for k, v in o.items()
                    if not (isinstance(k, str) and k.endswith("_ms"))}
        if isinstance(o, list):
            return [_stable(v) for v in o]
        if isinstance(o, float):
            return round(o, 9)
        return o
    (out / "results.json").write_text(json.dumps(_stable(results), indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    lines = ["# lce_validation — instrument and mock report", "", BANNER, "",
             f"Version {results['header']['lce_version']} · seed {args.seed}", "",
             "## Instruments", "", "| instrument | hypothesis | prediction | passed |", "|---|---|---|---|"]
    for name, r in instruments.items():
        lines.append(f"| `{name}` | {r['hypothesis']} | {r['prediction']} | {'yes' if r['passed'] else '**NO**'} |")
    c2 = experiments["C2"]
    lines += ["", "## Mock experiments (plumbing only)", "",
              f"- Wiki on the fixture corpus: {wstats['claims']} claims, {wstats['trainable']} trainable, "
              f"anchor rejection rate {wstats['anchor_verification']['rejection_rate']:.2f}.",
              f"- C1: accuracy with memory {experiments['C1']['acc_with_memory']:.2f} vs without {experiments['C1']['acc_without_memory']:.2f} (mock answers from context by rule).",
              *E.format_c2(c2),
              f"- C10 (simulated trainer): {experiments['C10_sim']['accepted']} accepted adapters over "
              f"{experiments['C10_sim']['generations']} generations, {experiments['C10_sim']['distinct_test_sets']} distinct test sets.",
              f"- Canary: {experiments['canary']['items']} items, {experiments['canary']['verified_items']} verified; training guard {experiments['canary']['training_guard']}.",
              ""]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    failed = [n for n, r in instruments.items() if not r["passed"]]
    print("\n".join(lines))
    if failed:
        print(f"\nINSTRUMENT FAILURE: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
