#!/usr/bin/env python3
"""Un documento, un modelo, el texto crudo. Para mirar antes de gastar otra corrida.

`lcurve-dev` del 22 de septiembre terminó con el brazo monolítico en 1 de 72
sobre preguntas globales, incluso con S = 10 -- una tabla de diez filas que cabe
entera en cualquier ventana. La calificación está sana: una respuesta perfecta
construida desde la clave saca 100 % en los 72 documentos, y hay un test que lo
comprueba. Así que o los modelos no saben hacer la tarea, o la hacen bien y
escriben la respuesta en un formato que el extractor rechaza.

Eso no se puede decidir desde los artefactos de aquella corrida porque no
guardó el texto. Ya lo guarda. Mientras tanto, esto lo mira con una llamada.

    python3 scripts/probe_lcurve.py                 # S = 10, el caso más fácil
    python3 scripts/probe_lcurve.py --n-rows 80
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_v0.backends import get_backend  # noqa: E402
from swarmbly_v0.grading import extract_items  # noqa: E402

CORPUS = Path(__file__).resolve().parent.parent / "prompts" / "lcurve.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-rows", type=int, default=10)
    parser.add_argument("--backend", default="openai")
    parser.add_argument("--index", type=int, default=0)
    arguments = parser.parse_args(argv)

    prompts = json.loads(CORPUS.read_text(encoding="utf-8"))["prompts"]
    candidates = [p for p in prompts
                  if p["n_rows"] == arguments.n_rows and p["split"] == "dev"]
    if not candidates:
        print(f"no hay documento dev con n_rows={arguments.n_rows}")
        return 1
    doc = candidates[arguments.index]

    print(f"=== {doc['id']}  ({doc['n_rows']} filas, {doc['prompt_tokens']} tokens)")
    print("\n=== INSTRUCCION DE FORMATO (cola del prompt) ===")
    print(doc["prompt"].rsplit("\n\n", 1)[-1])

    text = get_backend(arguments.backend).generate(
        doc["prompt"], max_tokens=400, temperature=0.0)

    print("\n=== TEXTO CRUDO DEL MODELO ===")
    print(text)

    extracted = dict(extract_items(text))
    print("\n=== LO QUE extract_items SACA ===")
    for item_id, value in sorted(extracted.items()):
        print(f"  [{item_id}] {value!r}")

    print("\n=== CONTRA LA CLAVE ===")
    print(f"{'id':>4} {'clase':>7} {'esperado':>12}   extraido")
    for qid, spec in sorted(doc["key"].items()):
        got = extracted.get(qid.zfill(2), "")
        mark = "ok " if got.strip().lower() == spec["expected"].strip().lower() else "NO "
        print(f"{mark}{qid:>2} {spec['kind']:>7} {spec['expected']:>12}   {got!r}")

    missing = [q for q in doc["key"] if q.zfill(2) not in extracted]
    if missing:
        print(f"\nIDs que el extractor NO encontró: {missing}")
        print("Si el modelo SI los contestó, el defecto es de formato y no de "
              "capacidad, y se arregla en el corpus o en el extractor -- no "
              "cambiando de modelos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
