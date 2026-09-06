#!/usr/bin/env python3
"""El corpus de material largo: tareas que NO caben en un nodo.

Por qué existe
--------------

`docs/REVISION_2026-09-05_que_hemos_medido.md` estableció el hecho que reencuadra
todo lo medido antes: el prompt más grande del proyecto mide **375 tokens** y el
modelo más chico del pool tiene una ventana de **8.192**. Ninguna tarea, en
ningún corpus, en ninguna corrida, había necesitado fragmentarse — el brazo
monolítico siempre funcionó porque siempre cupo.

Este corpus produce material que **no cabe en un presupuesto de nodo declarado**,
que es la única situación en la que la pregunta deja de ser "¿cuánto cuesta
partir?" y pasa a ser "¿existe la respuesta?".

Ver `docs/PREREGISTRATION_feasibility.md`, escrita antes que este archivo.

La forma
--------

Cada documento es un registro de inventario: filas ``R-nnn`` con un almacén, una
categoría y dos números. Se elige así por tres razones y ninguna es estética:

* **La clave se calcula, no se escribe.** Cada respuesta sale de las filas
  generadas, así que no hay juez y no hay modelo en el veredicto.
* **Las filas son independientes.** Un troceado que respete los límites de fila
  no rompe ningún dato, lo que le da al baseline obvio su mejor versión. Un
  corpus donde trocear parta un registro por la mitad estaría amañado a favor
  del protocolo.
* **El tamaño es un dial.** Más filas es más material sin cambiar la dificultad
  por fila, que es exactamente el eje bajo prueba.

Dos clases de pregunta, y la distinción es el diseño entero
-----------------------------------------------------------

``local``
    El valor de una fila nombrada. **Un solo trozo la contesta.** Es el control:
    si el brazo de troceado falla aquí, el troceado está roto y nada por debajo
    se puede leer.

``global``
    Un total, un máximo, un conteo bajo umbral. **Ningún trozo la contesta
    solo** — hay que combinar. Aquí es donde un protocolo puede añadir algo
    sobre concatenar, y por eso la hipótesis de utilidad se juzga sólo sobre
    estas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_v0.textutil import count_tokens  # noqa: E402

SEED = 20260905
OUT = Path(__file__).resolve().parent.parent / "prompts" / "longform.json"

NODE_BUDGET_TOKENS = 2048
"""El presupuesto por nodo, declarado en la prerregistración y no ajustable.

Vive aquí porque el generador tiene que saberlo para elegir los tamaños, pero
la autoridad es `docs/PREREGISTRATION_feasibility.md`. Si esto y el documento
discrepan, el documento gana y el corpus se regenera."""

SIZES = (24, 60, 150, 380, 900)
"""Filas por documento. Los tamaños cruzan el presupuesto a propósito.

A ~13 tokens por fila más la instrucción, 24 filas caben cómodos en 2048 y 900
no caben ni de lejos. Dos tamaños por debajo del presupuesto, uno cerca y dos
por encima: la frontera se mide, no se supone, y `--report` imprime dónde cae
para cada tamaño antes de que nadie corra nada."""

WAREHOUSES = ("Northgate", "Eastdock", "Southfield", "Westhill", "Midvale",
              "Harbour", "Riverside", "Fell End")
CATEGORIES = ("fasteners", "seals", "bearings", "filters", "couplings",
              "gaskets", "bushings", "spacers")


def _rows(count: int, rng: random.Random) -> list[dict]:
    return [
        {
            "id": f"R-{index + 1:03d}",
            "warehouse": rng.choice(WAREHOUSES),
            "category": rng.choice(CATEGORIES),
            "on_hand": rng.randrange(5, 995),
            "reorder_at": rng.randrange(10, 200),
        }
        for index in range(count)
    ]


def _table(rows: list[dict]) -> str:
    return "\n".join(
        f"{r['id']} | {r['warehouse']} | {r['category']} | "
        f"on_hand={r['on_hand']} | reorder_at={r['reorder_at']}"
        for r in rows)


def _questions(rows: list[dict], rng: random.Random) -> list[dict]:
    """Dos locales y tres globales por documento, con la clave calculada.

    Las globales están elegidas para que ningún trozo pueda contestarlas y para
    que combinarlas requiera algo distinto en cada caso: una suma es asociativa
    y un máximo también, pero **cuál** registro tiene el máximo no lo es en el
    sentido que importa aquí — un trozo que devuelve su máximo local obliga a
    quien combina a comparar valores, no a concatenar texto. El conteo bajo
    umbral es el caso donde concatenar da la respuesta equivocada de la forma
    más silenciosa: dos trozos que dicen "3" y "4" no dicen "7" a menos que
    alguien sume.
    """
    picked = rng.sample(rows, 2)
    total = sum(r["on_hand"] for r in rows)
    largest = max(rows, key=lambda r: (r["on_hand"], r["id"]))
    threshold = 500
    below = sum(1 for r in rows if r["on_hand"] < r["reorder_at"])

    return [
        {"id": "Q1", "kind": "local",
         "text": f"What is on_hand for {picked[0]['id']}?",
         "expected": str(picked[0]["on_hand"]), "mode": "numeric"},
        {"id": "Q2", "kind": "local",
         "text": f"Which warehouse holds {picked[1]['id']}?",
         "expected": picked[1]["warehouse"], "mode": "exact_norm"},
        {"id": "Q3", "kind": "global",
         "text": "What is the total on_hand across every row?",
         "expected": str(total), "mode": "numeric"},
        {"id": "Q4", "kind": "global",
         "text": "Which row id has the largest on_hand?",
         "expected": largest["id"], "mode": "exact_norm"},
        {"id": "Q5", "kind": "global",
         "text": ("How many rows have on_hand strictly below their own "
                  "reorder_at?"),
         "expected": str(below), "mode": "numeric"},
    ]


def document(index: int, n_rows: int, rng: random.Random) -> dict:
    rows = _rows(n_rows, rng)
    questions = _questions(rows, rng)
    material = _table(rows)
    asked = "\n".join(f"[{q['id']}] {q['text']}" for q in questions)
    prompt = (
        "Answer the questions from the inventory below.\n\n"
        f"Questions:\n{asked}\n\n"
        f"Inventory:\n{material}\n\n"
        "Give one line per question. Begin the line with the question id in "
        "square brackets, exactly as given, then a single space, then the "
        "value alone: no working, no restatement, no commentary."
    )
    return {
        "id": f"lf_{n_rows:03d}_{index:02d}",
        "category": "longform",
        "n_rows": n_rows,
        "expected_decomposable": True,
        "prompt": prompt,
        "material": material,
        "material_tokens": count_tokens(material),
        "prompt_tokens": count_tokens(prompt),
        "questions": questions,
        "key": {q["id"]: {"expected": q["expected"], "mode": q["mode"],
                          "kind": q["kind"]} for q in questions},
        "notes": (
            "Calificado contra una clave calculada en la generacion: sin juez y "
            "sin modelo en el veredicto. Las preguntas `local` son el control de "
            "que el troceado funciona; la hipotesis de utilidad se juzga solo "
            "sobre las `global`, que ningun trozo puede contestar por separado."
        ),
    }


def build(seed: int = SEED) -> list[dict]:
    """Seis documentos por tamaño: dos a dev, cuatro a final.

    El split se asigna por posición dentro de cada tamaño, no globalmente, para
    que **las dos mitades tengan la misma distribución de tamaños**. Un split
    donde dev quedara con los documentos cortos y final con los largos no es un
    split: es dos experimentos distintos con una etiqueta.
    """
    rng = random.Random(seed)
    prompts: list[dict] = []
    for n_rows in SIZES:
        for index in range(6):
            doc = document(index, n_rows, rng)
            doc["split"] = "dev" if index < 2 else "final"
            prompts.append(doc)
    return prompts


def digest(prompts: list[dict]) -> str:
    """SHA-256 sobre id, split, tamaño, prompt y clave, en orden.

    La clave entra en el digest y en el de composición no entraba, porque aquí
    la clave ES el veredicto: una clave que cambiara en silencio movería cada
    resultado sin mover el prompt.
    """
    payload = "\n".join(
        f"{p['id']}\t{p['split']}\t{p['n_rows']}\t{p['prompt']}\t"
        + json.dumps(p["key"], sort_keys=True)
        for p in prompts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _report(prompts: list[dict]) -> None:
    print(f"\npresupuesto por nodo declarado: W = {NODE_BUDGET_TOKENS} tokens\n")
    print(f"{'filas':>6} {'docs':>5} {'material':>10} {'prompt':>8}  "
          f"{'cabe en W?':>11}  {'nodos minimos':>14}")
    for n_rows in SIZES:
        group = [p for p in prompts if p["n_rows"] == n_rows]
        material = sum(p["material_tokens"] for p in group) // len(group)
        total = sum(p["prompt_tokens"] for p in group) // len(group)
        fits = total <= NODE_BUDGET_TOKENS
        # Techo, y con la instruccion repetida en cada nodo: el material se
        # reparte pero la pregunta no, que es de donde sale rho > 1.
        overhead = total - material
        per_node = max(1, NODE_BUDGET_TOKENS - overhead)
        nodes = max(1, -(-material // per_node))
        print(f"{n_rows:>6} {len(group):>5} {material:>10} {total:>8}  "
              f"{'SI' if fits else 'NO':>11}  {nodes:>14}")
    print("\n  La frontera se MIDE aqui, no se supone. Un tamano que cae del "
          "lado equivocado\n  de W invalida el diseno antes de gastar una hora, "
          "no despues.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--verify", action="store_true",
                        help="Reconstruir y comparar contra el digest en --out. "
                             "Sale 1 si no coincide.")
    parser.add_argument("--report", action="store_true",
                        help="Imprimir donde cae la frontera del presupuesto y salir.")
    args = parser.parse_args()

    prompts = build(args.seed)
    path = Path(args.out)
    current = digest(prompts)

    if args.report:
        _report(prompts)
        return 0

    if args.verify:
        if not path.exists():
            print(f"{path} no existe; nada que verificar", file=sys.stderr)
            return 1
        stored = json.loads(path.read_text()).get("_frozen", {}).get("sha256")
        if stored != current:
            print(f"DIGEST MISMATCH\n  guardado {stored}\n  reconstruido {current}\n"
                  f"El corpus en disco no es el que construye este script. "
                  f"Cualquier umbral congelado contra el guardado ya no aplica.",
                  file=sys.stderr)
            return 1
        print(f"verified {path}: {current}")
        return 0

    ids = [p["id"] for p in prompts]
    assert len(set(ids)) == len(ids), "id duplicado"
    for p in prompts:
        qids = [q["id"] for q in p["questions"]]
        assert len(set(qids)) == len(qids), f"{p['id']}: dos preguntas comparten id"
        assert len(p["key"]) == len(p["questions"])

    # El split debe tener la misma distribucion de tamanos en las dos mitades.
    for n_rows in SIZES:
        group = [p for p in prompts if p["n_rows"] == n_rows]
        assert sum(1 for p in group if p["split"] == "dev") == 2, (
            f"tamano {n_rows}: el split no esta balanceado; dev y final tienen "
            f"distribuciones de tamano distintas y eso no es un split")

    dev = [p for p in prompts if p["split"] == "dev"]
    final = [p for p in prompts if p["split"] == "final"]
    payload = {
        "_seed": args.seed,
        "_node_budget_tokens": NODE_BUDGET_TOKENS,
        "_frozen": {
            "sha256": current,
            "dev": sorted(p["id"] for p in dev),
            "final": sorted(p["id"] for p in final),
            "rule": (
                "El presupuesto por nodo, la clase de pregunta bajo la que se "
                "juzga la utilidad y el tamano declarado se fijan en dev. El "
                "split final se evalua una vez, despues, sin nada que elegir."
            ),
        },
        "_about": (
            "Material que NO cabe en un presupuesto de nodo declarado. Primera "
            "medicion del proyecto en la que la pregunta es si la respuesta "
            "existe, y no cuanta calidad se pierde. Ver "
            "docs/PREREGISTRATION_feasibility.md."
        ),
        "prompts": prompts,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {path}: {len(prompts)} documentos "
          f"({len(dev)} dev / {len(final)} final)")
    print(f"  sha256 {current}")
    _report(prompts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
