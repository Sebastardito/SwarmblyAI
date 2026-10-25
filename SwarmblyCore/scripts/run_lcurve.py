#!/usr/bin/env python3
"""La curva de L: el tamaño de fragmento como variable independiente.

Ver `docs/PREREGISTRATION_L_curve.md`, escrita antes que este archivo, y
`scripts/make_lcurve.py`, que construye el corpus que hace identificable el eje.

Qué se compara
--------------

El mismo documento, fragmentado a dos o tres valores de L. Mismo texto, mismas
preguntas, misma clave calculada, mismo baseline monolítico. Lo único que
cambia es cuántas filas lleva cada fragmento. Esa es la comparación pareada de
la celda declarada, y es la razón por la que este corpus existe.

Lo que puede invalidar la corrida, evaluado en código
-----------------------------------------------------

Las preguntas `local` son el control. Una fila nombrada la contesta el fragmento
que la contiene, sea ese fragmento de 5 filas o de 40. Si L mueve la exactitud
`local`, lo medido no es el tamaño de la unidad semántica sino algo roto en la
tubería, y no se publica ninguna cifra.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_feasibility import _Recorder, grade  # noqa: E402
from swarmbly_v0.experiment import (MIN_CLUSTERS_FOR_A_VERDICT,  # noqa: E402
                                    PromptSpec, SweepConfig, _answer_budget,
                                    run_fragmented, run_monolithic)
from swarmbly_v0.planner import global_contract  # noqa: E402
from swarmbly_v0.stats import cluster_bootstrap  # noqa: E402

L_CURVE_THRESHOLD_POINTS = 0.05
"""El umbral de la celda declarada, en puntos de exactitud.

El mismo valor que usa el criterio de composición. Se reutiliza a propósito: un
umbral nuevo elegido para este experimento sería un grado de libertad más, y el
único momento honesto de fijarlo ya pasó."""

CONTROL_TOLERANCE = 0.05
"""Cuánto puede moverse la exactitud `local` con L antes de invalidar la corrida."""

BASELINE_FLOOR = 0.20
"""Exactitud mínima del brazo monolítico en `global` para que la corrida hable.

AÑADIDA DESPUÉS DE LA PRIMERA CORRIDA, y eso se dice aquí y no se esconde.

`lcurve-dev` del 22 de septiembre salió sin disparar ninguna condición de
invalidación y con el control marcando +0.000, que se lee como "nada se rompió".
No era eso. El brazo monolítico sacó 1 de 72 en preguntas globales -- incluso
con S = 10, una tabla de diez filas que cabe entera en cualquier ventana. Con
los dos extremos en el piso, la diferencia pareada entre dos fragmentaciones es
ruido alrededor de cero, y el control marca +0.000 PRECISAMENTE porque no hay
nada que mover.

Un control que pasa en el piso no es un control. Ése fue el defecto de la
prerregistración: cuatro condiciones de refutación y ninguna que preguntara si
el instrumento tiene rango dinámico.

Esta condición no rescata aquella corrida ni cambia ningún veredicto -- no hubo
ninguno, la celda se rehusó por clusters. Rige desde la siguiente."""


# --------------------------------------------------------------------------- #
# Una celda

def run_cell(doc: Mapping[str, Any], backend: Any, embedder: Any, *,
             n_tasks: int, rho: float, tau_sem: float) -> dict[str, Any]:
    """El brazo fragmentado con N FIJO.

    `run_feasibility.run_swarmbly` sube N hasta que los paquetes caben en el
    presupuesto, que es lo correcto cuando la pregunta es si el protocolo
    respeta W. Aquí la pregunta es otra y N es la variable, así que no se sube:
    si los paquetes no caben, eso se registra y se lee al final, porque
    "fragmentos grandes no caben en un nodo" sería un hallazgo sobre L, no un
    accidente que corregir en silencio.
    """
    spec = PromptSpec(prompt_id=doc["id"], category="lcurve",
                      expected_decomposable=True, text=doc["prompt"],
                      constraints=None, split=doc.get("split"))
    recorder = _Recorder(backend)
    contract = global_contract(spec.text, recorder,
                               target_length_tokens=_answer_budget(spec, 384))
    row = run_fragmented(spec, recorder, embedder,
                         SweepConfig(rhos=(rho,), ns=(n_tasks,), ks=(1,),
                                     n_candidates=1, seed=0, tau_sem=tau_sem),
                         rho_target=rho, n_tasks=n_tasks, tau_sem=tau_sem, k=1,
                         contract=contract)
    return {"n_tasks": n_tasks,
            "peak_node_context": recorder.peak_context,
            "total_context": recorder.total_context,
            "rho_achieved": row.get("rho_achieved"),
            "text": str(row.get("_text", ""))}


def run_document(doc: Mapping[str, Any], backend: Any, embedder: Any, *,
                 rho: float, tau_sem: float, budget: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spec = PromptSpec(prompt_id=doc["id"], category="lcurve",
                      expected_decomposable=True, text=doc["prompt"],
                      constraints=None, split=doc.get("split"))
    recorder = _Recorder(backend)
    contract = global_contract(spec.text, recorder,
                               target_length_tokens=_answer_budget(spec, 384))
    base = run_monolithic(spec, recorder, embedder,
                          SweepConfig(rhos=(rho,), ns=(2,), ks=(1,),
                                      n_candidates=1, seed=0, tau_sem=tau_sem),
                          contract=contract)
    rows.append({"prompt_id": doc["id"], "n_rows": doc["n_rows"], "split": doc["split"],
                 "arm": "monolithic", "n_tasks": 1, "L": doc["n_rows"],
                 "peak_node_context": recorder.peak_context,
                 "over_budget": recorder.peak_context > budget,
                 "text": str(base.get("_text", ""))[:2000],
                 **grade(str(base.get("_text", "")), doc["key"])})
    for n_tasks, rows_per_fragment in doc["cells"]:
        cell = run_cell(doc, backend, embedder, n_tasks=n_tasks, rho=rho,
                        tau_sem=tau_sem)
        rows.append({"prompt_id": doc["id"], "n_rows": doc["n_rows"],
                     "split": doc["split"], "arm": "fragmented",
                     "n_tasks": n_tasks, "L": rows_per_fragment,
                     "peak_node_context": cell["peak_node_context"],
                     "over_budget": cell["peak_node_context"] > budget,
                     "rho_achieved": cell["rho_achieved"],
                     "text": cell["text"][:2000],
                     **grade(cell["text"], doc["key"])})
    return rows


# --------------------------------------------------------------------------- #
# Lectura

def _accuracy(row: Mapping[str, Any], kind: str) -> float | None:
    """La proporción acertada de las preguntas de ``kind`` en una corrida.

    `grade` devuelve {"correct": n, "asked": m} y no una proporción, a
    propósito: un documento sin preguntas de esa clase tiene que poder decir
    "no aplica" en vez de 0.0, que es una nota y no un vacío.
    """
    entry = (row.get("by_kind") or {}).get(kind)
    if not entry or not entry.get("asked"):
        return None
    return entry["correct"] / entry["asked"]


def paired_contrast(rows: Sequence[Mapping[str, Any]], kind: str
                    ) -> list[dict[str, Any]]:
    """Por documento: el L mayor menos el L menor, sobre preguntas de ``kind``.

    Sólo entran los documentos que se corrieron a más de un L. Un documento con
    un solo L no aporta un contraste; incluirlo con diferencia cero diluiría el
    efecto hacia cero sin que ningún dato lo diga.
    """
    by_document: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["arm"] == "fragmented":
            by_document[row["prompt_id"]].append(row)
    out: list[dict[str, Any]] = []
    for prompt_id, group in by_document.items():
        if len(group) < 2:
            continue
        low = min(group, key=lambda r: r["L"])
        high = max(group, key=lambda r: r["L"])
        a, b = _accuracy(high, kind), _accuracy(low, kind)
        if a is None or b is None:
            continue
        out.append({"prompt_id": prompt_id, "n_rows": high["n_rows"],
                    "L_high": high["L"], "L_low": low["L"], "difference": a - b})
    return out


def _mean(records: Sequence[Mapping[str, Any]]) -> float | None:
    values = [r["difference"] for r in records]
    return sum(values) / len(values) if values else None


def verdict(contrast: Sequence[Mapping[str, Any]], seed: int = 0) -> dict[str, Any]:
    clusters = len({r["prompt_id"] for r in contrast})
    if clusters < MIN_CLUSTERS_FOR_A_VERDICT:
        return {"refused": True, "n_clusters": clusters,
                "why": (f"{clusters} clusters, y el piso son "
                        f"{MIN_CLUSTERS_FOR_A_VERDICT}.")}
    interval = cluster_bootstrap(contrast, _mean, cluster_key="prompt_id", seed=seed)
    # `cluster_bootstrap` devuelve el intervalo como `ci95`, no como `lower` y
    # `upper`. Leerlo con .get("lower") daba None en silencio, y None nunca
    # supera un umbral: la celda habría dicho NO CUMPLIDO sobre cualquier dato,
    # incluido un efecto real. Lo encontró tests/test_lcurve.py antes de gastar
    # una sola llamada a un modelo.
    low, high = interval.get("ci95", (None, None))
    return {"refused": False, "n_clusters": clusters,
            "mean": _mean(contrast), "lower": low, "upper": high,
            "draws_unusable": interval.get("draws_unusable"),
            # Afirmación de que existe un efecto: decide la cota INFERIOR.
            "met": low is not None and low > L_CURVE_THRESHOLD_POINTS}


def by_cell(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    table: dict[str, Any] = {}
    grouped: dict[tuple[int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["arm"] == "fragmented":
            grouped[(row["n_tasks"], row["L"])].append(row)
    for (n_tasks, size), group in sorted(grouped.items()):
        for kind in ("global", "local"):
            values = [v for v in (_accuracy(r, kind) for r in group) if v is not None]
            table[f"N={n_tasks},L={size},{kind}"] = (
                sum(values) / len(values) if values else None)
    return table


def _invalidations(rows: Sequence[Mapping[str, Any]],
                   control: Sequence[Mapping[str, Any]],
                   budget: int) -> list[str]:
    """Las condiciones de la prerregistración, evaluadas aquí y no en prosa."""
    found: list[str] = []

    drift = _mean(control)
    if drift is not None and abs(drift) > CONTROL_TOLERANCE:
        found.append(
            f"CONTROL FALLADO: la exactitud `local` se mueve {drift:+.3f} con L, "
            f"por encima de {CONTROL_TOLERANCE}. Una pregunta local la contesta "
            "el fragmento que contiene su fila, sea grande o chico; si L la "
            "mueve, lo roto está en la tubería y ninguna cifra de esta corrida "
            "se puede leer.")

    sizes = {r["n_rows"] for r in rows}
    over = {r["n_rows"] for r in rows if r["arm"] == "monolithic" and r["over_budget"]}
    if not over:
        found.append(
            f"SIN FRONTERA: ningún tamaño excede W = {budget} en el brazo "
            "monolítico, así que la comparación es de coste y no de "
            "factibilidad. No invalida nada, pero cambia cómo se lee.")
    elif over == sizes:
        found.append(
            f"TODO POR ENCIMA DE W: los {len(sizes)} tamaños exceden el "
            "presupuesto monolítico, así que no hay un extremo barato con el "
            "que contrastar.")

    baseline = [r for r in rows if r["arm"] == "monolithic"]
    correct = sum((r.get("by_kind", {}).get("global") or {}).get("correct", 0)
                  for r in baseline)
    asked = sum((r.get("by_kind", {}).get("global") or {}).get("asked", 0)
                for r in baseline)
    if asked and correct / asked < BASELINE_FLOOR:
        found.append(
            f"PISO DEL BASELINE: el brazo monolítico acierta {correct}/{asked} "
            f"= {correct / asked:.3f} en preguntas globales, por debajo de "
            f"{BASELINE_FLOOR}. Con el baseline en el piso, la diferencia entre "
            "dos fragmentaciones del mismo documento es ruido alrededor de cero "
            "y el control `local` marca +0.000 porque no hay nada que mover. "
            "NINGUNA cifra de esta corrida habla sobre L.")

    refused = [r for r in rows if r.get("plan_refused")]
    if refused:
        found.append(f"PLANES REHUSADOS: {len(refused)} corridas.")
    return found


def summarise(rows: Sequence[Mapping[str, Any]], budget: int) -> dict[str, Any]:
    global_contrast = paired_contrast(rows, "global")
    local_contrast = paired_contrast(rows, "local")
    out: dict[str, Any] = {
        "n_rows_observed": len(rows),
        "cells": by_cell(rows),
        "declared_cell": verdict(global_contrast),
        "control_local": {"mean": _mean(local_contrast),
                          "tolerance": CONTROL_TOLERANCE,
                          "n_clusters": len({r["prompt_id"] for r in local_contrast})},
        "threshold_points": L_CURVE_THRESHOLD_POINTS,
        "descriptive_S80": [r for r in global_contrast if r["n_rows"] == 80],
    }
    out["invalidations"] = _invalidations(rows, local_contrast, budget)
    return out


# --------------------------------------------------------------------------- #

def _load(path: Path, split: str | None) -> tuple[list[dict], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    prompts = payload["prompts"]
    if split:
        prompts = [p for p in prompts if p.get("split") == split]
    return prompts, str(payload.get("_frozen", ""))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path,
                        default=Path(__file__).resolve().parent.parent
                        / "prompts" / "lcurve.json")
    parser.add_argument("--split", choices=("dev", "final"), default="dev")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rho", type=float, default=4.0)
    parser.add_argument("--tau-sem", type=float, default=0.585)
    parser.add_argument("--budget", type=int, default=2048)
    parser.add_argument("--limit", type=int, default=0,
                        help="Sólo los primeros N documentos. Para el ensayo.")
    parser.add_argument("--backend", default="mock")
    parser.add_argument("--embedder", default="hash")
    arguments = parser.parse_args(argv)

    from swarmbly_v0.backends import get_backend, get_embedder  # noqa: E402

    prompts, frozen = _load(arguments.prompts, arguments.split)
    if arguments.limit:
        prompts = prompts[: arguments.limit]
    backend = get_backend(arguments.backend)
    embedder = get_embedder(arguments.embedder)

    rows: list[dict[str, Any]] = []
    for index, doc in enumerate(prompts, 1):
        print(f"[{index}/{len(prompts)}] {doc['id']}  "
              f"S={doc['n_rows']}  celdas={doc['cells']}", flush=True)
        rows.extend(run_document(doc, backend, embedder, rho=arguments.rho,
                                 tau_sem=arguments.tau_sem,
                                 budget=arguments.budget))

    summary = summarise(rows, arguments.budget)
    summary["corpus_digest"] = frozen
    summary["split"] = arguments.split
    arguments.out.mkdir(parents=True, exist_ok=True)
    (arguments.out / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (arguments.out / "rows.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    # `run_tier` exige results.csv como post-condición: un tramo que sale 0 sin
    # dejarlo se marca FAILED, porque la causa habitual de eso es una línea de
    # comando truncada que corrió menos de lo que dice. Es la comprobación
    # funcionando, no un formalismo, así que la fila se emite de verdad.
    fields = ["prompt_id", "split", "n_rows", "arm", "n_tasks", "L",
              "peak_node_context", "over_budget", "rho_achieved",
              "global_correct", "global_asked", "local_correct", "local_asked"]
    with (arguments.out / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            by_kind = row.get("by_kind") or {}
            flat = dict(row)
            for kind in ("global", "local"):
                entry = by_kind.get(kind) or {}
                flat[f"{kind}_correct"] = entry.get("correct", "")
                flat[f"{kind}_asked"] = entry.get("asked", "")
            writer.writerow(flat)

    print(f"\nescrito {arguments.out / 'summary.json'} y "
          f"{arguments.out / 'results.csv'}")
    print("\n" + "=" * 68)
    cell = summary["declared_cell"]
    if cell["refused"]:
        print(f"CELDA DECLARADA: REHUSADA -- {cell['why']}")
    else:
        print(f"CELDA DECLARADA  media {cell['mean']:+.3f}  "
              f"IC 95 % [{cell['lower']:+.3f}, {cell['upper']:+.3f}]  "
              f"n={cell['n_clusters']}")
        print(f"  {'CUMPLIDO' if cell['met'] else 'NO CUMPLIDO'} contra "
              f"{L_CURVE_THRESHOLD_POINTS} sobre la cota inferior")
    control = summary["control_local"]
    if control["mean"] is not None:
        print(f"CONTROL `local`: {control['mean']:+.3f} "
              f"(tolerancia {control['tolerance']})")
    for note in summary["invalidations"]:
        print(f"\n!! {note}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
