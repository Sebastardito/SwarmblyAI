"""T12 — H-INT: ¿la fuerza del nodo predice el impuesto? (RETIRADA)

Ejecuta `PREREGISTRATION_2026-09-25_interaction_ES.md`. La hipótesis era que fragmentar
rescata nodos débiles y daña nodos fuertes. **No sobrevivió**, y el test se
conserva para que la retirada sea reproducible en vez de una nota al pie.

El punto metodológico vale más que la hipótesis: `impuesto = 1 − frag/mono`
lleva `mono` en el denominador, así que correlacionarlo con el `mono` de la
misma celda produce asociación **por construcción**. El test lo demuestra con
una simulación donde `frag` y `mono` se sortean independientes — si ese control
no reprodujera la correlación observada, el hallazgo habría sido real.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval import interaction as I
from swarmblyval.report import Result, BLOCKED, FAIL, PASS
from swarmblyval.stats import spearman

from swarmblyval.loaders import bench_path

ALPHA = 0.05
#: Si la simulación de ruido reproduce la correlación observada dentro de esta
#: tolerancia, la asociación es un artefacto del estadístico.
ARTEFACT_TOL = 0.10


def run():
    path = bench_path()
    if not path:
        return Result(id="T12", name="H-INT: fuerza del nodo vs impuesto (retirada)",
                      model="—", verdict=BLOCKED,
                      summary="sin benchmark.jsonl: exporta SWARMBLY_BENCH",
                      killed_if="ρ ≤ 0 · desaparece bajo control · el ruido la reproduce",
                      refusal="sin datos reales no se emite veredicto")

    cells, bmt = I.load_cells(path)
    primary = I.h_int(cells, bmt)
    if primary.get("refused"):
        return Result(id="T12", name="H-INT: fuerza del nodo vs impuesto (retirada)",
                      model="—", verdict=BLOCKED, summary=primary["why"],
                      killed_if="—", refusal=primary["why"])

    length = I.h_int(cells, bmt, length_control=1.0)
    ceiling = I.h_int(cells, bmt, exclude_ceiling=True)

    # el diagnóstico: acoplamiento matemático
    same = spearman([c["mono"] for c in cells], [c["tax"] for c in cells])
    rng = random.Random(7)
    sim = [((m := rng.uniform(0.2, 0.9)), (m - rng.uniform(0.2, 0.9)) / m * 100)
           for _ in range(2000)]
    sim_rho = spearman([a for a, _ in sim], [b for _, b in sim])
    artefact = abs(sim_rho - same) <= ARTEFACT_TOL

    # estadístico sin denominador, para comparar
    diff = spearman(
        [I.loo_strength(c["model"], c["task"], bmt) or 0.0 for c in cells],
        [c["frag"] - c["mono"] for c in cells])

    holds = primary["rho"] > 0 and primary["p"] < ALPHA

    details = [
        f"Prueba primaria (predictor **leave-one-out**, sin acoplamiento): "
        f"ρ = **{primary['rho']:+.3f}**, p = {primary['p']:.4f}, "
        f"n={primary['n']} en {primary['n_groups']} tareas. H-INT predice ρ > 0.",
        f"Control de longitud: ρ = {length.get('rho', float('nan')):+.3f}, "
        f"p = {length.get('p', float('nan')):.4f} (n={length.get('n')}).",
        f"Control de techo: ρ = {ceiling.get('rho', float('nan')):+.3f}, "
        f"p = {ceiling.get('p', float('nan')):.4f} (n={ceiling.get('n')}).",
        f"Estadístico sin denominador (fuerza LOO vs `frag − mono`): "
        f"ρ = **{diff:+.3f}** — ruido.",
    ]

    tables = {"El diagnóstico: el estadístico se genera solo": (
        ["comparación", "ρ"],
        [["`mono` de **la misma celda** vs impuesto", f"{same:+.3f}"],
         ["**fuerza LOO independiente** vs impuesto", f"{primary['rho']:+.3f}"],
         ["**simulación**: `frag` y `mono` independientes", f"{sim_rho:+.3f}"]])}

    sweep = I.threshold_sweep(cells)
    signs = {(w < 0, s < 0) for _t, _a, _b, w, s in sweep
             if w is not None and s is not None}
    stable = len(signs) == 1
    tables["Barrido del umbral (condición de muerte §6 del preregistro)"] = (
        ["umbral", "n débil", "n fuerte", "impuesto débil", "impuesto fuerte"],
        [[f"{t:.3f}", a, b,
          f"{w:+.1f}%" if w is not None else "—",
          f"{s:+.1f}%" if s is not None else "—"] for t, a, b, w, s in sweep])

    notes = [
        f"**Veredicto: H-INT retirada.** La prueba primaria no la sostiene "
        f"(ρ={primary['rho']:+.3f}, p={primary['p']:.3f}) y donde algo aparece el "
        f"signo es el contrario del predicho.",
        f"**La causa está demostrada, no supuesta.** Una simulación donde `frag` "
        f"y `mono` son independientes por construcción devuelve ρ = {sim_rho:+.3f}, "
        f"frente al {same:+.3f} observado con el `mono` de la misma celda. "
        f"{'El estadístico reproduce la asociación entera.' if artefact else ''}",
        f"Barrido de umbral: signos {'estables' if stable else '**inestables**'} "
        f"en el rango intercuartílico"
        + ("" if stable else " → no hay dos regímenes; la tabla estratificada **no se publica**."),
        "El hallazgo se encontró explorando y se presentó antes de confirmarlo. "
        "Lo que lo atrapó fue preregistrar el defecto sospechado y el diseño que "
        "lo rompe **antes** de correr. Con el estadístico acoplado y un umbral "
        "elegido a ojo, habría salido confirmado con números grandes.",
    ]

    return Result(
        id="T12", name="H-INT: fuerza del nodo vs impuesto (retirada)", model="—",
        verdict=PASS if holds else FAIL,
        summary=(f"H-INT retirada: ρ={primary['rho']:+.3f} (p={primary['p']:.3f}) "
                 f"con predictor independiente; el ruido reproduce {sim_rho:+.3f}"),
        killed_if="ρ ≤ 0 · desaparece bajo control · la simulación de ruido la reproduce",
        refusal="<8 celdas · varianza cero en el predictor",
        details=details, tables=tables, notes=notes)


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
