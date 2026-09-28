"""Orquestador del arnés de validación de Swarmbly AI.

Dos baterías, un punto de entrada:

* **derivación** (T00–T12) — reproduce la aritmética de los documentos, prueba
  los predicados de rechazo y mide δ, la longitud y la interacción sobre los
  artefactos del repositorio.
* **empírica** (T0R–T10R, TRR, TR2, TLR) — juzga los modelos M1–M5 contra las
  341 corridas reales de `benchmark.jsonl`.

Uso:

    python3 run_all.py                 # sólo derivación  → REPORT.md
    python3 run_all.py --real          # sólo empírica    → REPORT_REAL.md
    python3 run_all.py --all           # las dos + REPORT_COMBINED.md
    python3 tests/t1_split_k.py        # un test suelto

Salida distinta de cero si alguna batería contiene un FAIL, para que el arnés
sirva en CI sin que nadie tenga que leer el resumen.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from swarmblyval import loaders, report
from swarmblyval.report import FAIL
from tests import t0_provenance, t1_split_k, t2_triage, t3_uniqueness, t4_delta
from tests import t5_rho_scaling, t6_corpus, t7_rd_surface, t8_l_curve
from tests import t9_criterion, t10_aligner, t11_length, t12_interaction

DERIVATION = [t0_provenance, t1_split_k, t2_triage, t3_uniqueness, t4_delta,
              t5_rho_scaling, t6_corpus, t7_rd_surface, t8_l_curve, t9_criterion,
              t10_aligner, t11_length, t12_interaction]


def _scope():
    try:
        repo = loaders.repo_root()
        return repo, (f"datos reales del repositorio ({repo}); los fixtures se "
                      f"reconcilian contra los artefactos antes de usarse")
    except loaders.DataRefusal:
        return None, ("sin repositorio: sólo reproducción aritmética sobre "
                      "fixtures. Exporta SWARMBLY_REPO para desbloquear T04/T06")


def run_derivation():
    return [t.run() for t in DERIVATION]


def _write(results, meta, md_name, json_name):
    md = os.path.join(ROOT, md_name)
    js = os.path.join(ROOT, json_name)
    report.write_report(results, meta, md, js)
    return md, js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true",
                    help="ejecuta sólo la batería empírica sobre benchmark.jsonl")
    ap.add_argument("--all", action="store_true",
                    help="ejecuta las dos baterías y escribe un reporte combinado")
    ap.add_argument("--data", default=None,
                    help="ruta a benchmark.jsonl (por defecto swarmbly_ref/data/)")
    ap.add_argument("--embed", action="store_true",
                    help="habilita el alineador semántico con embeddings (T10R)")
    args = ap.parse_args()

    do_deriv = args.all or not args.real
    do_real = args.all or args.real

    deriv, real = [], []
    written = []

    if do_deriv:
        deriv = run_derivation()
        print(report.render_console(deriv))
        repo, scope = _scope()
        written.append(_write(deriv, {
            "project": "Swarmbly AI",
            "source": "WHITEPAPER_V2 (+ EXT, VALIDATION_STRATEGY_V2, FUNDAMENTOS)",
            "scope": scope,
            "repo": repo or "no encontrado",
            "run_all": "python3 run_all.py",
        }, "REPORT.md", "results.json"))

    if do_real:
        import run_real
        real, data = run_real.run_suite(args.data, embed=args.embed)
        print(report.render_console(real))
        written.append(_write(real, {
            "project": "Swarmbly AI — datos reales",
            "source": f"{data} (Ollama local, 5 familias SLM)",
            "scope": "veredictos empíricos; ver notas de alcance por test",
            "run_all": "python3 run_all.py --real",
        }, "REPORT_REAL.md", "results_real.json"))

    if args.all:
        repo, scope = _scope()
        written.append(_write(deriv + real, {
            "project": "Swarmbly AI — arnés completo",
            "source": "documentos + benchmark.jsonl",
            "scope": ("derivación y empírica en un solo reporte; el veredicto "
                      "de cada test conserva su alcance original"),
            "repo": repo or "no encontrado",
            "run_all": "python3 run_all.py --all",
        }, "REPORT_COMBINED.md", "results_combined.json"))

    for md, js in written:
        print(f"\nReporte: {md}\nJSON:    {js}")

    failed = [r.id for r in deriv + real if r.verdict == FAIL]
    if failed:
        print(f"\nFAIL en: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
