#!/usr/bin/env python3
"""El corpus de la curva de L: tamaños elegidos para que L y N se separen.

Por qué existe
--------------

El harness no tiene perilla de tamaño de fragmento. Tiene `n_tasks`, y con el
material fijo **L y N son la misma variable escrita al revés**: L = S / N. Toda
corrida anterior de este proyecto movió N sobre un corpus de tamaño fijo, así
que cada conclusión sobre N es también una conclusión sobre L y ninguna de las
dos es identificable por separado.

Este corpus rompe el confundido eligiendo S = L · N. Cada L aparece en varios N
y cada N en varios L, y sobre todo **el mismo documento se fragmenta a dos o
tres valores de L distintos**, que es la comparación pareada que decide.

Ver `docs/PREREGISTRATION_L_curve.md`, escrita antes que este archivo.

Lo que este corpus NO puede ver, declarado aquí y no después: una fila de
inventario ya es la unidad atómica, así que agrupar 5 o 40 filas cambia cuánto
pesa un fragmento, no lo que significa. Esto mide el componente MECÁNICO de L.
Es una cota inferior del efecto total, y si ni siquiera ella se distingue de
cero, la premisa del tamaño mínimo de unidad semántica se queda sin su apoyo
más barato.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from make_longform import NODE_BUDGET_TOKENS, document  # noqa: E402
from swarmbly_v0.textutil import count_tokens  # noqa: E402

SEED = 20260922
OUT = Path(__file__).resolve().parent.parent / "prompts" / "lcurve.json"

L_VALUES = (5, 10, 20, 40)
"""Filas por fragmento. El eje bajo prueba."""

N_VALUES = (2, 4, 8)
"""Fragmentos. El eje con el que L estuvo confundido hasta ahora."""

SIZES = tuple(sorted({size * count for size in L_VALUES for count in N_VALUES}))
"""Los tamaños de documento que hacen falta para cruzar L con N.

Se derivan del producto, no se eligen a mano: escribir la lista a mano sería
otra oportunidad de que el corpus y la rejilla dejen de coincidir en silencio."""

DOCUMENTS_PER_SIZE = 12
"""Cuatro a dev, ocho a final.

Ocho por tamaño, por los cuatro tamaños que admiten más de un L, dan los 32
clusters que la celda declarada necesita para no ser rehusada por el piso de
`MIN_CLUSTERS_FOR_A_VERDICT`. El número sale de esa cuenta, no de la comodidad."""


def cells(n_rows: int) -> list[tuple[int, int]]:
    """Los pares (N, L) que este tamaño admite, como (n_tasks, filas_por_trozo).

    Un tamaño sólo entra en una celda si la división es exacta y el L resultante
    está en la rejilla. S = 160 con N = 2 daría L = 80, que no está declarado, y
    queda fuera: ampliar la rejilla después de ver los datos es exactamente la
    libertad que una prerregistración existe para quitar.
    """
    return [(count, n_rows // count) for count in N_VALUES
            if n_rows % count == 0 and n_rows // count in L_VALUES]


def build(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    prompts: list[dict] = []
    for n_rows in SIZES:
        for index in range(DOCUMENTS_PER_SIZE):
            doc = document(index, n_rows, rng)
            doc["id"] = f"lc_{n_rows:03d}_{index:02d}"
            doc["category"] = "lcurve"
            doc["split"] = "dev" if index < 4 else "final"
            doc["cells"] = cells(n_rows)
            prompts.append(doc)
    return prompts


def digest(prompts: list[dict]) -> str:
    """SHA-256 sobre id, split, tamaño, rejilla, prompt y clave.

    Las celdas entran en el digest. Si alguien cambiara la rejilla sin cambiar
    el texto, el gate del tramo final tiene que rehusarse: la rejilla ES parte
    de lo que se congeló.
    """
    payload = "\n".join(
        f"{p['id']}\t{p['split']}\t{p['n_rows']}\t{p['cells']}\t{p['prompt']}\t"
        + json.dumps(p["key"], sort_keys=True)
        for p in prompts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _report(prompts: list[dict]) -> None:
    print(f"\nrejilla L x N, S = L * N.  W declarado = {NODE_BUDGET_TOKENS}\n")
    header = f"{'filas':>6} {'docs':>5} {'prompt tok':>11}  celdas (N->L)"
    print(header)
    print("-" * len(header))
    runs = 0
    for n_rows in SIZES:
        group = [p for p in prompts if p["n_rows"] == n_rows]
        tokens = sum(p["prompt_tokens"] for p in group) // len(group)
        grid = "  ".join(f"N={c}->L={size}" for c, size in cells(n_rows))
        print(f"{n_rows:>6} {len(group):>5} {tokens:>11}  {grid}")
        runs += len(group) * len(cells(n_rows))
    calls = sum(len([p for p in prompts if p["n_rows"] == s]) * sum(c for c, _ in cells(s))
                for s in SIZES)
    print(f"\ncorridas fragmentadas: {runs}   ·   monolíticas: {len(prompts)}")
    print(f"llamadas al modelo: ~{calls + len(prompts)}")
    for split in ("dev", "final"):
        half = [p for p in prompts if p["split"] == split]
        contrast = sum(1 for p in half if len(cells(p["n_rows"])) > 1)
        print(f"  {split:>5}: {len(half):>3} documentos, "
              f"{contrast:>3} con contraste de L (clusters de la celda declarada)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="Reconstruir y comparar contra el digest en --out. "
                             "No escribe nada.")
    arguments = parser.parse_args(argv)

    prompts = build()
    current = digest(prompts)

    if arguments.check:
        if not arguments.out.exists():
            print(f"{arguments.out} no existe.")
            return 1
        stored = json.loads(arguments.out.read_text(encoding="utf-8"))
        if stored.get("_frozen") != current:
            print(f"digest distinto.\n  en disco: {stored.get('_frozen')}\n"
                  f"  generado: {current}")
            return 1
        print(f"digest coincide: {current}")
        return 0

    payload = {
        "_seed": SEED,
        "_node_budget_tokens": NODE_BUDGET_TOKENS,
        "_l_values": list(L_VALUES),
        "_n_values": list(N_VALUES),
        "_frozen": current,
        "_about": ("Corpus de la curva de L. S = L * N, para que el tamano de "
                   "fragmento se pueda mover con N fijo. Ver "
                   "docs/PREREGISTRATION_L_curve.md."),
        "prompts": prompts,
    }
    arguments.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"escrito {arguments.out}  ({len(prompts)} documentos)")
    print(f"digest: {current}")
    if arguments.report:
        _report(prompts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
