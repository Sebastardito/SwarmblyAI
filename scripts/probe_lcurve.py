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
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_v0.backends import get_backend  # noqa: E402
from swarmbly_v0.grading import extract_items  # noqa: E402

CORPUS = Path(__file__).resolve().parent.parent / "prompts" / "lcurve.json"


RUNNER = Path(__file__).resolve().parent / "run_ollama.sh"


def family_pool() -> list[tuple[str, str]]:
    """El pool de familias, del entorno o del runner, nunca inventado.

    `SWARMBLY_REPLICA_MODELS` lo exporta `run_ollama.sh`, así que un tramo
    siempre lo tiene. Esta sonda se corre a mano y no lo tiene, y la primera
    versión resolvía eso degradando en silencio a una sola familia -- y luego
    imprimía una conclusión sobre "el pool entero" con una familia medida.
    Ése es el mismo defecto que esta sesión lleva corrigiendo en otros sitios:
    una comprobación que afirma más de lo que midió.

    Así que la lista se saca del runner, que es donde vive, en vez de copiarse
    aquí donde se quedaría obsoleta.
    """
    raw = os.environ.get("SWARMBLY_REPLICA_MODELS", "").strip()
    if not raw and RUNNER.exists():
        for line in RUNNER.read_text(encoding="utf-8").splitlines():
            if line.startswith("MODELS_DEFAULT="):
                raw = line.split("=", 1)[1].strip().strip('"')
                break
    pairs: list[tuple[str, str]] = []
    for entry in raw.split(","):
        family, _, model = entry.strip().partition(":")
        if family and model:
            pairs.append((family, model))
    return pairs


def wrapped(doc: dict) -> str:
    """El prompt tal como el harness lo despacha, con su contrato global."""
    from swarmbly_v0.experiment import PromptSpec, _answer_budget  # noqa: E402
    from swarmbly_v0.packing import build_monolithic_prompt  # noqa: E402
    from swarmbly_v0.planner import global_contract  # noqa: E402

    spec = PromptSpec(prompt_id=doc["id"], category="lcurve",
                      expected_decomposable=True, text=doc["prompt"],
                      constraints=None, split=doc.get("split"))
    contract = global_contract(spec.text, get_backend("mock"),
                               target_length_tokens=_answer_budget(spec, 384))
    return build_monolithic_prompt(contract, doc["prompt"])


def _score(replica, docs: list[dict], use_contract: bool) -> dict[str, list[int]]:
    got = {"global": [0, 0], "local": [0, 0]}
    for doc in docs:
        text = replica.generate(wrapped(doc) if use_contract else doc["prompt"],
                                max_tokens=400, temperature=0.0)
        extracted = dict(extract_items(text))
        for qid, spec in doc["key"].items():
            kind = spec["kind"]
            got[kind][1] += 1
            if (extracted.get(qid.zfill(2), "").strip().lower()
                    == spec["expected"].strip().lower()):
                got[kind][0] += 1
    return got


def calibrate(prompts: list[dict], backend_name: str, n_rows: int) -> int:
    """¿Alguna familia del pool despega del piso en el caso más fácil?

    El eje bajo prueba es L. Si el baseline no puede hacer la tarea en el punto
    más fácil del diseño, ningún contraste entre fragmentaciones es legible, y
    eso no se arregla con más corridas. Ésta es la comprobación que la
    prerregistración debió pedir ANTES de construir la rejilla: un diseño que
    varía X tiene que mostrar primero que el instrumento responde.
    """
    docs = [p for p in prompts if p["n_rows"] == n_rows and p["split"] == "dev"]
    pool = family_pool()
    if len(pool) < 2:
        print("REHUSADA: se necesitan al menos dos familias para decir algo "
              f"sobre el pool, y hay {len(pool)}.\n")
        print("  export SWARMBLY_REPLICA_MODELS="
              "\"llama:llama3.2:3b,qwen:qwen2.5:3b,...\"")
        print("\n  o correr esta sonda con el entorno del runner ya puesto.")
        return 1

    print(f"calibración: monolítico, S = {n_rows}, {len(docs)} documentos, "
          f"{len(pool)} familias\n")
    print("Dos envíos por familia: el prompt CRUDO, y el mismo prompt envuelto")
    print("en el contrato global que el harness antepone. Mismos documentos,")
    print("mismos modelos, misma clave: lo único que cambia es el envoltorio.\n")
    header = (f"{'familia':>24} {'global crudo':>13} {'global contrato':>16}"
              f" {'local crudo':>12} {'local contrato':>15}")
    print(header)
    print("-" * len(header))
    cleared: list[str] = []
    totals = {"raw": [0, 0], "contract": [0, 0]}
    for family, model in pool:
        os.environ["SWARMBLY_MODEL"] = model
        replica = get_backend(backend_name)
        raw, con = _score(replica, docs, False), _score(replica, docs, True)
        if raw["global"][0] / max(1, raw["global"][1]) >= 0.20:
            cleared.append(model)
        totals["raw"][0] += raw["local"][0]; totals["raw"][1] += raw["local"][1]
        totals["contract"][0] += con["local"][0]
        totals["contract"][1] += con["local"][1]
        cell = lambda d, k: f"{d[k][0]}/{d[k][1]}"
        print(f"{model:>24} {cell(raw,'global'):>13} {cell(con,'global'):>16}"
              f" {cell(raw,'local'):>12} {cell(con,'local'):>15}")

    print()
    a = totals["raw"][0] / max(1, totals["raw"][1])
    b = totals["contract"][0] / max(1, totals["contract"][1])
    print(f"LOOKUP (`local`), pool entero:  crudo {a:.3f}   contrato {b:.3f}"
          f"   diferencia {b - a:+.3f}")
    if a - b >= 0.15:
        print("\nEl contrato global le está costando al baseline en una tarea")
        print("que sabe hacer. El contrato pide `output_format: report` y 384")
        print("tokens; el corpus pide una línea por pregunta con el valor solo.")
        print("Se contradicen, y el contrato va primero.")
    print()
    if cleared:
        print(f"Despegan del piso: {', '.join(cleared)}.")
        print("El piso NO es del pool entero. El corpus sirve y el arreglo "
              "está en qué modelos se usan.")
    else:
        print(f"Ninguna de las {len(pool)} familias despega del piso de 0.20 "
              "en el caso más fácil del diseño.")
        print("Este corpus no puede medir L con este pool. Hay que bajar la "
              "dificultad POR FILA -- que el generador ya trata como un dial "
              "separado del tamaño -- y calibrar de nuevo ANTES de construir "
              "otra rejilla.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-rows", type=int, default=10)
    parser.add_argument("--backend", default="openai")
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--contract", action="store_true",
                        help="Enviar el prompt envuelto en el contrato global, "
                             "como lo hace el harness, en vez del prompt crudo. "
                             "Con --calibrate mide las dos y las compara.")
    parser.add_argument("--calibrate", action="store_true",
                        help="Monolítico en TODAS las familias del pool, sobre "
                             "el tamaño más fácil. Decide si el piso es del "
                             "pool entero o de un modelo.")
    arguments = parser.parse_args(argv)

    prompts = json.loads(CORPUS.read_text(encoding="utf-8"))["prompts"]
    if arguments.calibrate:
        return calibrate(prompts, arguments.backend, arguments.n_rows)
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
