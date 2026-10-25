"""T01 — Separar `k` en tres propósitos (M5). WHITEPAPER_V2 §12.4, §15.6.

No mide nada: es una separación conceptual de un parámetro que ya existe. La
prueba valida que (a) los tres propósitos son realmente distintos, (b) cada uno
tiene un mecanismo correcto distinto, y (c) un único `k` paga por los tres al
precio del más caro. La condición de muerte es que estén tan acoplados que
separarlos no ahorre nada.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval import report
from swarmblyval.report import Result, CONCEPTUAL


PURPOSES = [
    # (nombre, qué compra, mecanismo correcto, costo relativo típico)
    ("k_avail  (disponibilidad)", "el task completa aunque caiga un nodo", "threshold over-dispatch", 2.0),
    ("k_verif  (verificación)", "un nodo deshonesto no impone un falso resultado", "spot-checking basado en credibilidad", 1.01),
    ("k_epist  (redundancia epistémica)", "el mapa de divergencia tiene algo que alinear", "réplicas de familias distintas", 3.0),
]


def run():
    # (a) propósitos distintos -> mecanismos distintos
    mechanisms = {p[2] for p in PURPOSES}
    distinct = len(mechanisms) == len(PURPOSES)

    # (b) costo de un único k = precio del más caro
    unified_cost = max(p[3] for p in PURPOSES)          # k=3 en todo lo crítico
    separated_cost = sum(p[3] for p in PURPOSES) / len(PURPOSES)  # media (cada rol lo suyo)
    saving = (unified_cost - separated_cost) / unified_cost

    details = [
        f"{len(PURPOSES)} propósitos, {len(mechanisms)} mecanismos distintos: "
        f"separación {'coherente' if distinct else 'NO coherente'}.",
        f"Costo de un único `k` (precio del más caro): {unified_cost:.2f}×.",
        f"Costo medio separado (cada rol su mínimo): {separated_cost:.2f}× — "
        f"ahorro ilustrativo {saving:.1%}.",
        "`k_verif` no escala con réplicas: Sarmenta/BOINC muestran que el "
        "spot-checking reduce el error linealmente a una fracción del costo.",
        "`k_epist` no es sustituible por ninguno de los otros dos: su producto "
        "es señal (divergencia), no tolerancia a fallos.",
    ]
    tables = {
        "Tres propósitos, tres mecanismos": (
            ["Parámetro", "Compra", "Mecanismo correcto", "Costo rel. típico"],
            [[p[0], p[1], p[2], f"{p[3]:.2f}×"] for p in PURPOSES],
        )
    }
    notes = [
        "Veredicto CONCEPTUAL: no hay medición nueva que correr. La prueba real "
        "es de implementación (observar si el costo total baja al separarlos).",
        "El caso particular del trusted swarm (whitelist elimina k_verif pero no "
        "k_epist) ya está en v1.4; aquí se generaliza a tres propósitos.",
    ]
    return Result(
        id="T01", name="Separar k en tres (M5)", model="M5",
        verdict=CONCEPTUAL,
        summary=f"separación coherente: un único k paga max (ilustrativo {saving:.1%} de ahorro)",
        killed_if="los tres están tan acoplados que separarlos no ahorra nada",
        refusal="— (no se emite veredicto de medición; es un chequeo de razonamiento)",
        details=details, tables=tables, notes=notes,
    )


if __name__ == "__main__":
    print(report.render_console([run()]))
