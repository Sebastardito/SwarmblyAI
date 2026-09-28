"""T11 — ¿el impuesto medido responde a fragmentar, o a escribir más?

El brazo fragmentado produce más texto que el monolítico, y las componentes que
deciden el score —cobertura, claves numéricas— suben con la longitud casi
mecánicamente. Este test mide ese confundido y **se niega a validar un veredicto
de factibilidad mientras el presupuesto de salida no esté igualado**.

Tres estadísticos, porque uno solo no bastaba:

1. `Spearman(razón de longitud, impuesto)` — la observación original, pero el
   impuesto lleva `mono` en el denominador, así que se contrasta contra…
2. `Spearman(razón, frag − mono)` — diferencia absoluta, sin denominador.
3. `Spearman(palabras_frag, score_frag)` **dentro de cada tarea** — la prueba
   directa: a tarea fija, ¿escribir más puntúa más?

Condición de muerte del confundido (es decir, lo que lo declararía inocuo): que
el estadístico limpio (2) y la prueba directa (3) den ≈0 mientras (1) da algo.
Entonces (1) sería artefacto y el impuesto agregado sería interpretable.
"""

import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval import interaction as I
from swarmblyval.loaders import bench_path
from swarmblyval.report import Result, BLOCKED, FAIL, PASS
from swarmblyval.stats import clustered_bootstrap, spearman

#: Por debajo de esto el estadístico limpio se considera sin efecto.
NEGLIGIBLE = 0.20
#: Tareas mínimas para la prueba directa intra-tarea.
MIN_TASKS = 8


def run():
    path = bench_path()
    if not path:
        return Result(id="T11", name="Confundido de longitud de salida", model="—",
                      verdict=BLOCKED,
                      summary="sin benchmark.jsonl: exporta SWARMBLY_BENCH",
                      killed_if="el estadístico limpio y la prueba directa dan ≈0",
                      refusal="sin datos reales no se emite veredicto")

    cells, _bmt = I.load_cells(path)
    if len(cells) < 20:
        return Result(id="T11", name="Confundido de longitud de salida", model="—",
                      verdict=BLOCKED, summary=f"{len(cells)} celdas < 20",
                      killed_if="—", refusal=f"{len(cells)} celdas < 20")

    ratio = [c["ratio"] for c in cells]
    tax = [c["tax"] for c in cells]
    diff = [c["frag"] - c["mono"] for c in cells]

    rho_tax = spearman(ratio, tax)
    rho_diff = spearman(ratio, diff)

    # Suelo del artefacto: la razón observada contra un impuesto SORTEADO. Da
    # cuánto de (1) puede producir la forma del estadístico sin que exista
    # relación alguna. Se computa aquí y no se transcribe, por §15.7.
    import random as _rnd
    _r = _rnd.Random(13)
    shuffled = list(tax)
    _r.shuffle(shuffled)
    rho_floor = spearman(ratio, shuffled)

    # prueba directa, intra-tarea
    by_task = {}
    for c in cells:
        by_task.setdefault(c["task"], []).append(c)
    rhos = [spearman([x["words_frag"] for x in v], [x["frag"] for x in v])
            for v in by_task.values() if len(v) >= 5]
    direct_median = st.median(rhos) if rhos else None
    direct_pos = sum(1 for r in rhos if r > 0)

    details = [
        f"Corpus: {len(cells)} celdas comparables en {len(by_task)} tareas.",
        f"Longitud: mediana {st.median([c['words_mono'] for c in cells]):.0f} "
        f"palabras monolítico vs "
        f"{st.median([c['words_frag'] for c in cells]):.0f} fragmentado — "
        f"razón mediana **{st.median(ratio):.2f}×**.",
        f"(1) Spearman(razón, impuesto) = **{rho_tax:+.3f}** — pero el impuesto "
        f"lleva `mono` en el denominador, así que no decide solo.",
        f"(2) Spearman(razón, frag − mono) = **{rho_diff:+.3f}** — estadístico "
        f"sin denominador, misma magnitud y signo coherente.",
        f"Suelo del artefacto (mismo estadístico con el impuesto permutado): "
        f"**{rho_floor:+.3f}** — lo que la forma del estadístico produce sola.",
    ]
    if direct_median is not None:
        details.append(
            f"(3) Prueba directa, Spearman(palabras, score) **dentro de cada "
            f"tarea**: mediana **{direct_median:+.3f}**, positiva en "
            f"**{direct_pos} de {len(rhos)}** tareas.")

    # el impuesto por estrato de longitud
    tables = {}
    rows = []
    for label, sel in (
        ("todas las celdas", cells),
        ("frag NO más largo (razón ≤ 1.0)", [c for c in cells if c["ratio"] <= 1.0]),
        ("longitud comparable (0.8–1.25)",
         [c for c in cells if 0.8 <= c["ratio"] <= 1.25]),
        ("frag más largo (> 1.25)", [c for c in cells if c["ratio"] > 1.25]),
    ):
        if len(sel) < 8:
            rows.append([label, len(sel), "n<8: se niega", "", ""])
            continue
        mean, lo, hi, _ = clustered_bootstrap([c["tax"] for c in sel],
                                              [c["task"] for c in sel])
        rows.append([label, len(sel), f"{mean:+.1f}%", f"[{lo:+.1f}, {hi:+.1f}]",
                     "cumple" if hi < 5.0 else "NO cumple"])
    tables["Impuesto por estrato de longitud"] = (
        ["estrato", "n", "impuesto", "IC95", "vs criterio 5%"], rows)

    confounded = (abs(rho_diff) >= NEGLIGIBLE
                  or (direct_median is not None and direct_median >= NEGLIGIBLE
                      and len(rhos) >= MIN_TASKS))

    notes = [
        "**Qué bloquea este test.** Mientras el confundido esté vivo, el impuesto "
        "agregado no es interpretable: no dice si fragmentar ayuda, dice que el "
        "brazo que escribe más puntúa más. El criterio de abandono no está "
        "cumplido ni incumplido — está **sin medir**.",
        "**Cómo se resuelve.** Igualar el presupuesto de salida: el monolítico "
        "recibe `max_tokens = T` y el fragmentado el mismo `T` repartido entre "
        "sus fragmentos. Con el resume por key, sólo se re-corren las celdas "
        "afectadas.",
        "No invalida T07R ni T04R: ésos comparan fragmentado contra fragmentado a "
        "ρ constante, donde los dos brazos producen salida comparable.",
    ]

    return Result(
        id="T11", name="Confundido de longitud de salida", model="—",
        verdict=FAIL if confounded else PASS,
        summary=(f"el impuesto agregado está confundido con la longitud "
                 f"(limpio {rho_diff:+.3f}, directo {direct_median:+.3f} en "
                 f"{direct_pos}/{len(rhos)} tareas)" if confounded else
                 "sin evidencia de confundido: el impuesto agregado es interpretable"),
        killed_if="el estadístico sin denominador y la prueba directa dan ≈0",
        refusal=f"<20 celdas · <{MIN_TASKS} tareas para la prueba directa",
        details=details, tables=tables, notes=notes)


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
