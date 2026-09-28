"""T07 — Superficie D(ρ, δ) (M4). WHITEPAPER_V2 §6.7–6.8, §15.6.

Tres predicciones falsables sobre un corpus calibrado por dificultad:
  1. δ fijo, ρ varía (mismo corte, distinto flanco) → curva monótona decreciente.
  2. ρ fijo, δ varía (mismo presupuesto, cortes de distinto acoplamiento) →
     variación en distorsión a tasa constante (esto mata "ρ basta como eje").
  3. Región inalcanzable → un piso de distorsión que ningún ρ mejora.

Esta prueba implementa el arnés de análisis sobre triples medidos (ρ, δ, D) y
declara BLOQUEADO el veredicto empírico: depende del corpus (T06).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval.report import Result, BLOCKED


def analyze_surface(points):
    """points = [(rho, delta, distortion), ...].

    Devuelve un dict con las tres pruebas de M4 sobre los datos medidos.
    """
    out = {}
    # 1. monotonicidad en rho a delta (casi) fijo
    fixed_delta = sorted([p for p in points if abs(p[1] - points[0][1]) < 1e-6],
                         key=lambda p: p[0])
    if len(fixed_delta) >= 3:
        diffs = [fixed_delta[i + 1][2] - fixed_delta[i][2]
                 for i in range(len(fixed_delta) - 1)]
        out["monotone_in_rho"] = all(d <= 1e-9 for d in diffs), diffs
    # 2. variacion en delta a rho (casi) fijo
    fixed_rho = sorted([p for p in points if abs(p[0] - points[0][0]) < 1e-6],
                       key=lambda p: p[1])
    if len(fixed_rho) >= 2:
        spread = max(p[2] for p in fixed_rho) - min(p[2] for p in fixed_rho)
        out["delta_effect_at_const_rho"] = spread, fixed_rho
    # 3. piso de distorsion (region inalcanzable)
    if points:
        out["min_distortion"] = min(p[2] for p in points)
    return out


def run():
    details = [
        "Depende del corpus calibrado (T06). Sin él, el veredicto empírico es BLOQUEADO.",
        "Predicción 1: a δ fijo, distorsión monótona decreciente en ρ.",
        "Predicción 2 (la decisiva): a ρ fijo, variación de distorsión al variar δ "
        "→ si no hay variación, ρ basta como eje y el marco nuevo no añade nada.",
        "Predicción 3: un piso de distorsión que ningún ρ mejora (región inalcanzable, "
        "condición de información de Bresler).",
        "El arnés `analyze_surface([(rho, delta, D), ...])` está listo para los triples medidos.",
    ]
    notes = [
        "L19: del marco rate-distortion se hereda la EXISTENCIA de un piso y la "
        "monotonicidad cualitativa, NO un número computable. No reclamar un ρ* calculable.",
        "Condición de rechazo: si no hay ≥3 puntos a δ fijo o ≥2 a ρ fijo, negarse "
        "a emitir veredicto de forma de curva.",
    ]
    return Result(
        id="T07", name="Superficie D(ρ, δ) (M4)", model="M4",
        verdict=BLOCKED,
        summary="arnés listo; requiere el corpus calibrado (T06) para los triples (ρ, δ, D)",
        killed_if="la distorsión resulta función de ρ solo (δ sin efecto medible)",
        refusal="se niega sin ≥3 puntos a δ fijo o ≥2 a ρ fijo",
        details=details, notes=notes,
    )


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
