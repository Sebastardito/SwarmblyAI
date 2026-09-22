#!/usr/bin/env python3
"""Separa la varianza ENTRE prompts del ruido de medición, y dimensiona el corpus.

Por qué existe
--------------

El resultado de composición en `comp-final-v2` fue una diferencia pareada de
**-0.35 puntos** con intervalo [-8.49, +7.80] sobre 24 clusters: falla el
criterio por el ANCHO del intervalo, no por el tamaño del efecto. La reacción
obvia es construir un corpus más grande, y la aritmética dice que harían falta
unos 60 clusters para que la cota superior caiga bajo los 5 puntos del umbral.

Esa aritmética da por hecho algo que nadie midió. La desviación entre clusters
es de **20.36 puntos** contra un umbral de 5, y esa cifra suma dos cosas
distintas:

* **σ_entre** -- que los prompts de verdad difieran en cuánto cuesta
  fragmentarlos. Sólo se combate con más prompts.
* **σ_ruido** -- que la misma medición sobre el mismo prompt salga distinta.
  Sólo se combate con más repeticiones del mismo prompt.

Si domina la segunda, un corpus de 72 prompts gasta cómputo en el eje
equivocado. Correr el mismo split dos veces con semillas distintas las separa,
y cuesta una fracción de lo que cuesta construir el corpus a ciegas.

    python3 scripts/variance_decomposition.py CORRIDA_A CORRIDA_B
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

THRESHOLD_POINTS = 5.0
"""El umbral del criterio de composición, en puntos. Vive en la
prerregistración; se repite aquí sólo para dimensionar."""


def deltas(run: Path, n_tasks: str = "3", rho: str = "4.0") -> dict[str, float]:
    """La diferencia pareada por prompt en la celda declarada, en puntos."""
    out: dict[str, list[float]] = {}
    with (run / "results.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("n_tasks") != n_tasks or row.get("rho_target") != rho:
                continue
            try:
                base = float(row["baseline_constraint_score_comparable"])
                frag = float(row["constraint_score_comparable"])
            except (KeyError, ValueError):
                continue
            out.setdefault(row["prompt_id"], []).append((base - frag) * 100)
    return {k: statistics.fmean(v) for k, v in out.items()}


def decompose(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    """σ_entre y σ_ruido a partir de dos medidas del mismo prompt.

    Con dos observaciones por prompt, la varianza de su diferencia es dos veces
    la del ruido, y la varianza de su media es σ²_entre + σ²_ruido/2. Dos
    ecuaciones, dos incógnitas, sin modelo que ajustar.
    """
    shared = sorted(set(a) & set(b))
    if len(shared) < 8:
        raise SystemExit(f"sólo {len(shared)} prompts en común; hacen falta 8+")
    pairs = [(a[k], b[k]) for k in shared]
    diff = [x - y for x, y in pairs]
    mean = [(x + y) / 2 for x, y in pairs]
    noise_var = statistics.pvariance(diff) / 2
    mean_var = statistics.variance(mean)
    between_var = max(0.0, mean_var - noise_var / 2)
    return {
        "n_prompts": len(shared),
        "sigma_noise": math.sqrt(noise_var),
        "sigma_between": math.sqrt(between_var),
        "total_sd_one_run": math.sqrt(between_var + noise_var),
        "mean_a": statistics.fmean(a[k] for k in shared),
        "mean_b": statistics.fmean(b[k] for k in shared),
    }


def plan(sigma_between: float, sigma_noise: float, effect: float) -> list[tuple]:
    """Coste de alcanzar el umbral, por combinación de prompts y repeticiones.

    SE² = σ²_entre / P + σ²_ruido / (P·R). Más prompts baja los dos términos;
    más repeticiones baja sólo el segundo. Por eso, cuando σ_ruido es chico,
    repetir no compra nada y la única salida son prompts.
    """
    rows = []
    for prompts in (24, 36, 48, 60, 72, 96):
        for repeats in (1, 2, 3):
            se = math.sqrt(sigma_between**2 / prompts
                           + sigma_noise**2 / (prompts * repeats))
            rows.append((prompts, repeats, prompts * repeats, se,
                         effect + 1.96 * se))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    parser.add_argument("--effect", type=float, default=None,
                        help="Efecto verdadero supuesto, en puntos. Por "
                             "defecto la media observada de las dos corridas.")
    arguments = parser.parse_args(argv)

    a, b = deltas(arguments.run_a), deltas(arguments.run_b)
    result = decompose(a, b)
    effect = (arguments.effect if arguments.effect is not None
              else (result["mean_a"] + result["mean_b"]) / 2)

    print(f"prompts en común: {result['n_prompts']}")
    print(f"media corrida A: {result['mean_a']:+.2f}   "
          f"corrida B: {result['mean_b']:+.2f}")
    print()
    print(f"  sigma ENTRE prompts : {result['sigma_between']:6.2f} puntos"
          "   (sólo baja con más prompts)")
    print(f"  sigma RUIDO         : {result['sigma_noise']:6.2f} puntos"
          "   (sólo baja con más repeticiones)")
    print(f"  sd de una corrida   : {result['total_sd_one_run']:6.2f} puntos")

    share = result["sigma_noise"] ** 2 / max(
        1e-9, result["sigma_noise"] ** 2 + result["sigma_between"] ** 2)
    print(f"\n  el ruido explica el {share:.0%} de la varianza observada")
    if share < 0.25:
        print("  -> repetir el mismo prompt no compra casi nada. Hacen falta "
              "PROMPTS.")
    elif share > 0.6:
        print("  -> la mayor parte de la dispersión es ruido de medición. "
              "Repetir es más barato que ampliar el corpus.")
    else:
        print("  -> las dos vías compran algo; la tabla de abajo dice cuál "
              "cuesta menos.")

    print(f"\nefecto supuesto {effect:+.2f} puntos, umbral {THRESHOLD_POINTS}")
    print(f"\n{'prompts':>8} {'repet':>6} {'corridas':>9} {'SE':>7} "
          f"{'cota sup':>9}")
    for prompts, repeats, cost, se, upper in plan(
            result["sigma_between"], result["sigma_noise"], effect):
        mark = "  CUMPLE" if upper < THRESHOLD_POINTS else ""
        print(f"{prompts:>8} {repeats:>6} {cost:>9} {se:>7.2f} "
              f"{upper:>+9.2f}{mark}")

    print("\nLa fila más barata que CUMPLE es el tamaño del corpus v3. Nada se "
          "construye antes de mirarla.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
