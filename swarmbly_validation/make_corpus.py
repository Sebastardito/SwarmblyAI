"""Genera el corpus candidato de la curva-L con preguntas globales respondibles.

    python3 make_corpus.py --out prompts/lcurve_v2.json

Conserva el material, los ids, la división dev/final y las celdas del corpus
existente, y **sólo cambia las preguntas**: de agregados n-arios sobre todas las
filas a preguntas de aridad ≤3 sobre filas verificadas en fragmentos distintos
para cada celda declarada (véase `swarmblyval/corpus.py`).

Mantener el material fijo es deliberado: si cambiaran a la vez el material y las
preguntas, una diferencia de resultado no podría atribuirse a ninguna de las dos.

El corpus que sale de aquí **no está admitido**. Falta la única comprobación que
decide, y necesita una corrida:

    1. correr el brazo monolítico sobre la mitad `dev`
    2. pasar la tasa global a `corpus.preflight(docs, monolithic_global_rate=…)`
    3. si no despeja 0.50, el corpus se rechaza y no se toca la mitad `final`
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swarmblyval import corpus as CO
from swarmblyval import loaders as L


def parse_material(material):
    rows = []
    for line in material.split("\n"):
        if not line.strip():
            continue
        parts = [x.strip() for x in line.split("|")]
        if len(parts) < 5:
            continue
        rows.append({"id": parts[0], "warehouse": parts[1], "goods": parts[2],
                     "on_hand": int(parts[3].split("=")[1]),
                     "reorder_at": int(parts[4].split("=")[1])})
    return rows


def admit(corpus_path, run_dir):
    """Cierra la compuerta: lee una corrida y decide si el corpus se admite."""
    payload = json.load(open(corpus_path, encoding="utf-8"))
    docs = payload["prompts"]
    rows = json.load(open(os.path.join(run_dir, "rows.json"), encoding="utf-8"))
    mono = [r for r in rows if r["arm"] == "monolithic"]
    if not mono:
        print(f"{run_dir}: no hay filas del brazo monolítico. No se admite.")
        return 1
    ok = sum(r["by_kind"]["global"]["correct"] for r in mono)
    n = sum(r["by_kind"]["global"]["asked"] for r in mono)
    l_ok = sum(r["by_kind"]["local"]["correct"] for r in mono)
    l_n = sum(r["by_kind"]["local"]["asked"] for r in mono)
    rate = ok / n if n else 0.0

    print(f"Corrida: {run_dir}")
    print(f"  monolítico · globales {ok}/{n} = {rate:.3f}")
    print(f"  monolítico · locales  {l_ok}/{l_n} = {l_ok/l_n:.3f}"
          if l_n else "  monolítico · locales: sin datos")
    print()
    rep = CO.preflight(docs, monolithic_global_rate=rate)
    print("Compuerta de admisión:")
    print(rep)
    print()
    if rep.admitted:
        print(f"ADMITIDO. El corpus discrimina: el monolítico despeja "
              f"{CO.MONOLITHIC_FLOOR:.2f}.")
        print("Siguiente: T07/T08/T09 dejan de estar bloqueados, y T04 se puede "
              "rehacer sobre un corpus con variación de descomposición.")
        return 0
    print("NO ADMITIDO.")
    if rate < CO.MONOLITHIC_FLOOR:
        print(f"  El monolítico se queda en {rate:.3f}, bajo el piso de "
              f"{CO.MONOLITHIC_FLOOR:.2f}.")
        print("  La mitad `final` NO se toca. Opciones, en orden de coste:")
        print("    1. bajar la aridad: --n-global 3 con sólo pair_sum/pair_diff")
        print("    2. material más pequeño (S=10) para aislar si el problema es la longitud")
        print("    3. si las LOCALES también están bajas, el problema no son las "
              "preguntas sino el formato de respuesta o el backend")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="lcurve_v2.json")
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--n-global", type=int, default=3)
    ap.add_argument("--n-local", type=int, default=2)
    ap.add_argument("--admit", metavar="RUNDIR",
                    help="no genera: lee una corrida y cierra la compuerta")
    ap.add_argument("--corpus", default=None,
                    help="ruta del corpus a admitir (por defecto --out)")
    args = ap.parse_args()

    if args.admit:
        return admit(args.corpus or args.out, args.admit)

    prompts, meta = L.load_lcurve_prompts()
    docs, refused = [], []
    for i, p in enumerate(prompts):
        try:
            d = CO.build_document(p["id"], parse_material(p["material"]),
                                  [tuple(c) for c in p["cells"]],
                                  seed=args.seed + i,
                                  n_local=args.n_local, n_global=args.n_global)
        except ValueError as exc:
            refused.append((p["id"], str(exc)))
            continue
        d["split"] = p.get("split")
        d["material_tokens"] = p.get("material_tokens")
        docs.append(d)

    rep = CO.preflight(docs)
    print("Compuerta de admisión (mecánica):")
    print(rep)
    if refused:
        print(f"\nEl generador se negó en {len(refused)} documentos:")
        for pid, why in refused[:5]:
            print(f"  {pid}: {why}")
    if rep.failures:
        print("\nHay fallos mecánicos: no se escribe el corpus.")
        return 1

    payload = {
        "_seed": args.seed,
        "_derives_from": "prompts/lcurve.json (material idéntico, preguntas nuevas)",
        "_l_values": meta.get("_l_values"),
        "_n_values": meta.get("_n_values"),
        "_about": (
            "Preguntas globales de aridad <=3 sobre filas verificadas en "
            "fragmentos distintos para cada celda declarada. Son globales por "
            "construccion -- ningun fragmento las contesta solo -- mientras la "
            "aritmetica baja de 'suma veinte numeros' a 'suma dos'. El corpus "
            "anterior fallaba porque sus tres globales eran agregados n-arios: "
            "el monolitico daba 0/24, 0/24 y 1/24."),
        "_admission": {
            "mechanical": [[n, ok, d] for n, ok, d in rep.checks],
            "pending": [[n, d] for n, d in rep.pending],
            "monolithic_floor": CO.MONOLITHIC_FLOOR,
            "status": "NOT ADMITTED: falta la corrida del brazo monolitico",
        },
        "_frozen": {
            "dev": [d["id"] for d in docs if d.get("split") == "dev"],
            "final": [d["id"] for d in docs if d.get("split") == "final"],
            "rule": ("Umbrales y cualquier eleccion se fijan sobre dev. La mitad "
                     "final se evalua una vez, despues, sin nada que elegir."),
        },
        "prompts": docs,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    payload["_frozen"]["sha256"] = hashlib.sha256(blob).hexdigest()

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    n_g = sum(1 for d in docs for q in d["questions"] if q["kind"] == "global")
    print(f"\nEscrito: {args.out}")
    print(f"  {len(docs)} documentos · {n_g} preguntas globales · "
          f"dev {len(payload['_frozen']['dev'])} / final {len(payload['_frozen']['final'])}")
    print(f"  sha256 {payload['_frozen']['sha256'][:16]}…")
    print("\nEstado: NO ADMITIDO hasta que el brazo monolítico despeje "
          f"{CO.MONOLITHIC_FLOOR:.2f} sobre las globales de la mitad dev.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
