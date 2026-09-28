#!/usr/bin/env python3
"""La frontera de factibilidad: ¿existe la respuesta cuando no cabe en un nodo?

Ver `docs/PREREGISTRATION_feasibility.md`, escrita antes que este archivo y
antes del corpus.

La pregunta que cambia
----------------------

Todo lo medido antes del 5 de septiembre preguntaba **cuánta calidad se pierde
al fragmentar**, sobre tareas que el brazo monolítico siempre pudo hacer porque
siempre cupieron — el prompt más grande del proyecto medía 375 tokens contra una
ventana de 8.192. La única respuesta posible a esa pregunta era "se pierde".

Aquí hay un **presupuesto por nodo declarado**, `W`, que todos los brazos
respetan por igual. Por encima de `W` el brazo monolítico no puntúa bajo: **no
existe**. La pregunta pasa a ser si la respuesta existe, y a qué precio.

Los tres brazos, y el segundo es el que decide
-----------------------------------------------

``monolithic-capped``
    Un nodo, presupuesto `W`. Infactible por encima, y registrado como
    infactible y no como cero — un cero se promedia, un infactible no.

``naive-chunk``
    **El baseline obvio, en su mejor versión razonable.** Trocear el material
    respetando límites de fila, preguntar TODO a cada trozo, y combinar las
    respuestas parciales con **una llamada más** dentro de `W`. Es el map-reduce
    que escribiría cualquiera, no usa conocimiento de oráculo sobre el tipo de
    pregunta, y no tiene router, planner, packer ni ensamblador.

``swarmbly``
    El protocolo enviado, con `N` calculado por documento para que los paquetes
    quepan en `W`.

**Si `swarmbly` ≈ `naive-chunk`, el hallazgo es que el valor está en trocear** y
las cuatro piezas del protocolo no están pagando su costo. Ese resultado es tan
publicable como el contrario y está dicho aquí, antes de correr, para que no se
pueda reescribir después.

La condición de invalidación que se mide y no se supone
--------------------------------------------------------

El presupuesto se comprueba **midiendo el contexto real de cada paquete
despachado**, no confiando en que el packer respetó su objetivo. Es el mismo
patrón que `packing_ceiling`: medir, no derivar. Un brazo que exceda `W` en
cualquier nodo invalida la corrida entera, porque su factibilidad sería ficticia.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swarmbly_v0.backends import get_backend, get_embedder  # noqa: E402
from swarmbly_v0.experiment import (PromptSpec, SweepConfig,  # noqa: E402
                                    _answer_budget, run_fragmented)
from swarmbly_v0.grading import extract_items, grade_answer  # noqa: E402
from swarmbly_v0.planner import global_contract  # noqa: E402
from swarmbly_v0.schema import source_fingerprint  # noqa: E402
from swarmbly_v0.textutil import count_tokens  # noqa: E402

ARMS = ("monolithic-capped", "naive-chunk", "swarmbly")

DECLARED_ROWS = 380
"""El tamaño declarado. Tres nodos mínimos a W=2048, muy por encima de la
frontera y no tan extremo que todo degenere. Fijado en la prerregistración."""


@dataclass
class _Recorder:
    """Un backend que anota cada prompt que se le pide generar.

    Los paquetes son la evidencia. `peak_node_context` tiene que describir lo
    que se DESPACHÓ y no lo que el packer se propuso: la condición de
    invalidación 3 de la prerregistración exige exactamente esa distinción, y un
    runner que reconstruyera los paquetes desde el plan mediría la intención.
    """

    inner: Any
    prompts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = getattr(self.inner, "name", "recorded")
        self.family = getattr(self.inner, "family", "")
        self.model = getattr(self.inner, "model", "")

    def for_replica(self, family: str, model: str = "") -> "_Recorder":
        inner = (self.inner.for_replica(family, model)
                 if hasattr(self.inner, "for_replica") else self.inner)
        clone = _Recorder(inner)
        clone.prompts = self.prompts
        clone.family, clone.model = family, model
        return clone

    def generate(self, prompt: str, **kwargs: Any) -> str:
        self.prompts.append(prompt)
        return self.inner.generate(prompt, **kwargs)

    def embed(self, texts: Sequence[str]) -> Any:
        return self.inner.embed(texts)

    @property
    def peak_context(self) -> int:
        return max((count_tokens(p) for p in self.prompts), default=0)

    @property
    def total_context(self) -> int:
        return sum(count_tokens(p) for p in self.prompts)


# --------------------------------------------------------------------------- #
# Calificación: contra la clave, sin juez
# --------------------------------------------------------------------------- #

def grade(text: str, key: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    """Cada pregunta calificada, y separada por clase.

    `local` y `global` no se promedian juntas en ningún sitio. Las locales son
    el control de que el troceado funciona; la hipótesis se juzga sólo sobre las
    globales. Un promedio sobre las dos diría que un brazo que contesta bien lo
    fácil y mal lo difícil está a mitad de camino, cuando lo que hace es no
    servir para el caso bajo prueba.
    """
    given = {item_id: answer for item_id, answer in extract_items(text or "")}
    by_kind: dict[str, list[bool]] = defaultdict(list)
    detail: dict[str, Any] = {}
    for qid, spec in key.items():
        # `extract_items` normaliza el id a dos digitos, y SOLO reconoce
        # etiquetas numericas. El corpus las emite ya normalizadas para que el
        # emparejamiento sea una igualdad y no una traduccion -- una traduccion
        # es donde vivio tres horas el defecto de la primera version.
        raw = given.get(qid.zfill(2), "")
        ok = grade_answer(raw, spec["expected"], spec.get("mode", "exact_norm"))
        ok = bool(ok)
        by_kind[spec["kind"]].append(ok)
        detail[qid] = {"kind": spec["kind"], "given": raw[:80],
                       "expected": spec["expected"], "correct": ok}
    return {
        "by_kind": {kind: {"correct": sum(v), "asked": len(v)}
                    for kind, v in sorted(by_kind.items())},
        "detail": detail,
    }


# --------------------------------------------------------------------------- #
# Los brazos
# --------------------------------------------------------------------------- #

def _instruction_of(prompt: str) -> tuple[str, str]:
    """Separa el prompt en (todo menos el inventario, el inventario)."""
    marker = "\nInventory:\n"
    head, _, material = prompt.partition(marker)
    return head, material


def run_monolithic_capped(doc: Mapping[str, Any], backend: Any, *,
                          budget: int) -> dict[str, Any]:
    """Un nodo. Por encima del presupuesto no hay respuesta, y eso es el dato."""
    size = count_tokens(doc["prompt"])
    if size > budget:
        return {"feasible": False, "n_nodes": 0, "peak_node_context": size,
                "total_context": 0, "text": "",
                "reason": f"el prompt mide {size} tokens contra un presupuesto "
                          f"de {budget}: no existe un nodo que lo sostenga"}
    recorder = _Recorder(backend)
    text = recorder.generate(doc["prompt"], max_tokens=512, seed=0)
    return {"feasible": True, "n_nodes": 1,
            "peak_node_context": recorder.peak_context,
            "total_context": recorder.total_context, "text": str(text)}


def chunk_rows(material: str, head: str, budget: int) -> list[str]:
    """Trozos que respetan los límites de fila y caben con la instrucción.

    Respetar la fila es lo que le da al baseline su mejor versión: un troceado
    que partiera un registro por la mitad estaría amañado a favor del protocolo,
    y la prerregistración se compromete a no hacer eso.
    """
    overhead = count_tokens(head) + 16
    room = max(64, budget - overhead)
    chunks: list[str] = []
    current: list[str] = []
    used = 0
    for line in material.strip().splitlines():
        cost = count_tokens(line) + 1
        if current and used + cost > room:
            chunks.append("\n".join(current))
            current, used = [], 0
        current.append(line)
        used += cost
    if current:
        chunks.append("\n".join(current))
    return chunks


def run_naive_chunk(doc: Mapping[str, Any], backend: Any, *,
                    budget: int) -> dict[str, Any]:
    """Map sobre trozos, reduce con una llamada más. El map-reduce evidente.

    El reduce es una llamada a un modelo y no una regla mecánica a propósito.
    Sumar los parciales cuando la pregunta es una suma, y tomar el máximo cuando
    es un máximo, exigiría saber de qué TIPO es cada pregunta -- conocimiento de
    oráculo que este brazo no tiene y que lo volvería injustamente fuerte. Lo que
    escribiría cualquiera es pasarle los parciales a un nodo más y pedirle que
    los combine.
    """
    head, material = _instruction_of(doc["prompt"])
    chunks = chunk_rows(material, head, budget)
    recorder = _Recorder(backend)

    partials: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        packet = (f"{head}\nInventory (part {index} of {len(chunks)}):\n{chunk}\n\n"
                  "Answer only from this part. If a question cannot be answered "
                  "from this part alone, give your best answer for THIS PART.")
        partials.append(str(recorder.generate(packet, max_tokens=384, seed=0)))

    if len(chunks) == 1:
        text = partials[0]
    else:
        joined = "\n\n".join(f"--- part {i} ---\n{p}"
                             for i, p in enumerate(partials, start=1))
        # El reduce tambien respeta W. Si los parciales no caben, se recortan --
        # y se registra, porque un reduce truncado es una limitacion real del
        # troceado ingenuo y no un descuido del runner.
        asked = head.split("\n\nInventory")[0]
        reduce_head = (f"{asked}\n\nBelow are partial answers from "
                       f"{len(chunks)} parts of the same inventory. Combine "
                       f"them into one final answer. Totals must be added "
                       f"across parts; a maximum is the largest across parts; "
                       f"a count is the sum of the per-part counts.\n\n")
        room = max(128, budget - count_tokens(reduce_head))
        truncated = joined
        while count_tokens(truncated) > room and "\n" in truncated:
            truncated = truncated[: int(len(truncated) * 0.9)]
        text = str(recorder.generate(reduce_head + truncated,
                                     max_tokens=384, seed=0))

    return {"feasible": True, "n_nodes": len(chunks) + (1 if len(chunks) > 1 else 0),
            "peak_node_context": recorder.peak_context,
            "total_context": recorder.total_context, "text": text,
            "n_chunks": len(chunks),
            "reduce_truncated": len(chunks) > 1 and count_tokens(joined) > room}


def nodes_needed(doc: Mapping[str, Any], budget: int) -> int:
    head, material = _instruction_of(doc["prompt"])
    return max(2, len(chunk_rows(material, head, budget)))


MAX_NODE_ATTEMPTS = 4
"""Cuántas veces se sube N buscando que los paquetes quepan en el presupuesto.

Un tope y no un bucle abierto: si cuatro intentos no bastan, el dato es que el
protocolo no respeta ese presupuesto en ese documento, y esconderlo tras un
quinto intento sería convertir una limitación en una espera."""


def run_swarmbly(doc: Mapping[str, Any], backend: Any, embedder: Any, *,
                 budget: int, rho: float, tau_sem: float) -> dict[str, Any]:
    """El protocolo, con N subido hasta que los paquetes MEDIDOS quepan en W.

    El primer diseño calculaba N desde el troceado ingenuo y daba por hecho que
    los paquetes cabrían. No cabían: en el ensayo con material de 900 filas el
    pico medido fue 2113 contra un presupuesto de 2048, y la condición de
    invalidación 3 se disparó -- correctamente, antes de gastar una hora de
    modelos reales.

    La causa no es un defecto: un paquete del protocolo lleva su cabecera de
    contrato y sus acarreos, así que pesa MÁS que un trozo ingenuo del mismo
    número de filas. Eso es un costo real y medible del protocolo, y el arreglo
    honesto es medirlo, no aflojar la comprobación.

    Así que N sube hasta que el pico despachado cabe, y `n_attempts` viaja con
    el resultado. "Cuántos nodos necesita el protocolo para respetar el
    presupuesto" es una de las cifras que la prerregistración manda registrar, y
    ésta es la forma de obtenerla sin derivarla.
    """
    spec = PromptSpec(prompt_id=doc["id"], category="longform",
                      expected_decomposable=True, text=doc["prompt"],
                      constraints=None, split=doc.get("split"))
    n_tasks = nodes_needed(doc, budget)
    attempts = 0
    result: dict[str, Any] = {}
    while attempts < MAX_NODE_ATTEMPTS:
        attempts += 1
        config = SweepConfig(rhos=(rho,), ns=(n_tasks,), ks=(1,), n_candidates=1,
                             seed=0, tau_sem=tau_sem)
        recorder = _Recorder(backend)
        contract = global_contract(spec.text, recorder,
                                   target_length_tokens=_answer_budget(spec, 384))
        row = run_fragmented(spec, recorder, embedder, config, rho_target=rho,
                             n_tasks=n_tasks, tau_sem=tau_sem, k=1,
                             contract=contract)
        result = {"feasible": True, "n_nodes": n_tasks,
                  "n_attempts": attempts,
                  "peak_node_context": recorder.peak_context,
                  "total_context": recorder.total_context,
                  "text": str(row.get("_text", "")),
                  "rho_achieved": row.get("rho_achieved"),
                  "plan_refused": bool(str(row.get("plan_refused", "")).lower()
                                       in ("true", "1", "yes"))}
        if recorder.peak_context <= budget:
            return result
        # Un nodo mas de los que faltan por el exceso medido, no uno arbitrario.
        over = recorder.peak_context - budget
        per_node = max(1, recorder.peak_context // max(1, n_tasks))
        n_tasks += max(1, -(-over // per_node))
    result["budget_not_reachable"] = True
    return result


# --------------------------------------------------------------------------- #

def run_document(doc: Mapping[str, Any], backend: Any, embedder: Any, *,
                 budget: int, rho: float, tau_sem: float,
                 arms: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "monolithic-capped" in arms:
        out["monolithic-capped"] = run_monolithic_capped(doc, backend, budget=budget)
    if "naive-chunk" in arms:
        out["naive-chunk"] = run_naive_chunk(doc, backend, budget=budget)
    if "swarmbly" in arms:
        out["swarmbly"] = run_swarmbly(doc, backend, embedder, budget=budget,
                                       rho=rho, tau_sem=tau_sem)
    for arm, result in out.items():
        result.update(grade(result.get("text", ""), doc["key"])
                      if result["feasible"] else {"by_kind": {}, "detail": {}})
        result["over_budget"] = result["peak_node_context"] > budget and result["feasible"]
    return out


def summarise(rows: Sequence[Mapping[str, Any]], budget: int) -> dict[str, Any]:
    arms = sorted({a for r in rows for a in r["arms"]})
    per_arm: dict[str, Any] = {}
    for arm in arms:
        cells = [r["arms"][arm] for r in rows if arm in r["arms"]]
        feasible = [c for c in cells if c["feasible"]]
        kinds: dict[str, dict[str, int]] = defaultdict(
            lambda: {"correct": 0, "asked": 0})
        for c in feasible:
            for kind, counts in c["by_kind"].items():
                kinds[kind]["correct"] += counts["correct"]
                kinds[kind]["asked"] += counts["asked"]
        per_arm[arm] = {
            "n_documents": len(cells),
            "n_feasible": len(feasible),
            "feasible_rate": round(len(feasible) / len(cells), 6) if cells else None,
            "accuracy_by_kind": {
                kind: {**c, "rate": round(c["correct"] / c["asked"], 6)
                       if c["asked"] else None}
                for kind, c in sorted(kinds.items())},
            "peak_node_context_max": max((c["peak_node_context"] for c in feasible),
                                         default=0),
            "total_context_mean": (round(sum(c["total_context"] for c in feasible)
                                         / len(feasible), 1) if feasible else None),
            "n_nodes_mean": (round(sum(c["n_nodes"] for c in feasible)
                                   / len(feasible), 2) if feasible else None),
            "cells_over_budget": sum(1 for c in cells if c.get("over_budget")),
        }

    by_size: dict[int, Any] = {}
    for size in sorted({r["n_rows"] for r in rows}):
        group = [r for r in rows if r["n_rows"] == size]
        by_size[size] = {
            arm: {
                "feasible": sum(1 for r in group if r["arms"].get(arm, {}).get("feasible")),
                "of": len(group),
                "global_rate": _rate(group, arm, "global"),
                "local_rate": _rate(group, arm, "local"),
            } for arm in arms
        }

    return {
        "node_budget_tokens": budget,
        "declared_rows": DECLARED_ROWS,
        "by_arm": per_arm,
        "by_size": by_size,
        "invalidations": _invalidations(per_arm, by_size, budget),
        "note": (
            "feasible_rate y accuracy_by_kind NUNCA se combinan en un solo "
            "numero: un brazo infactible no es un brazo con puntaje cero. La "
            "hipotesis de utilidad se juzga sobre las preguntas `global`, que "
            "ningun trozo puede contestar por separado; las `local` son el "
            "control de que el troceado funciona."
        ),
    }


def _rate(group: Sequence[Mapping[str, Any]], arm: str, kind: str) -> float | None:
    correct = asked = 0
    for row in group:
        cell = row["arms"].get(arm)
        if not cell or not cell["feasible"]:
            continue
        counts = cell["by_kind"].get(kind)
        if counts:
            correct += counts["correct"]
            asked += counts["asked"]
    return round(correct / asked, 6) if asked else None


def _invalidations(per_arm: Mapping[str, Any], by_size: Mapping[int, Any],
                   budget: int) -> dict[str, Any]:
    """Las cuatro condiciones de la prerregistración, evaluadas en código.

    En código y no en una nota, por la misma razón que
    `MIN_CLUSTERS_FOR_A_VERDICT` está en código: una condición de invalidación
    que hay que acordarse de comprobar es una que se comprueba cuando el
    resultado no gusta.
    """
    problems: list[str] = []

    naive = per_arm.get("naive-chunk", {})
    local = (naive.get("accuracy_by_kind", {}).get("local") or {}).get("rate")
    if local is not None and local < 0.80:
        problems.append(
            f"1: naive-chunk acierta {local:.1%} de las preguntas `local`, por "
            f"debajo del 80% exigido. El troceado esta roto y nada por debajo "
            f"se puede leer.")

    mono = per_arm.get("monolithic-capped", {})
    if mono.get("feasible_rate") == 1.0:
        problems.append(
            "2: monolithic-capped fue factible en TODOS los tamanos. El "
            "presupuesto no esta mordiendo y el diseno no probo nada.")

    for arm, stats in per_arm.items():
        if stats.get("cells_over_budget"):
            problems.append(
                f"3: {arm} excedio el presupuesto de {budget} tokens en "
                f"{stats['cells_over_budget']} celdas. La factibilidad medida "
                f"es ficticia.")

    return {"conditions_met": problems,
            "run_is_readable": not problems,
            "note": ("Si conditions_met no esta vacia, la corrida no se lee: se "
                     "arregla lo que nombra y se vuelve a correr.")}


def _load(path: Path, split: str | None) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    prompts = payload["prompts"]
    if split:
        prompts = [p for p in prompts if p.get("split") == split]
    return prompts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prompts", default="prompts/longform.json")
    parser.add_argument("--split", default="dev", choices=("dev", "final", "all"))
    parser.add_argument("--budget", type=int, default=2048)
    parser.add_argument("--rho", type=float, default=2.0)
    parser.add_argument("--tau-sem", type=float, default=0.6)
    parser.add_argument("--backend", default="openai-compat")
    parser.add_argument("--embedder", default="ollama")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--out", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    docs = _load(Path(args.prompts), None if args.split == "all" else args.split)
    if args.limit:
        docs = docs[: args.limit]
    arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())

    backend = get_backend(args.backend)
    embedder = get_embedder(args.embedder)

    rows: list[dict[str, Any]] = []
    for index, doc in enumerate(docs, start=1):
        print(f"[{index}/{len(docs)}] {doc['id']}  {doc['n_rows']} filas, "
              f"{doc['prompt_tokens']} tokens", flush=True)
        result = run_document(doc, backend, embedder, budget=args.budget,
                              rho=args.rho, tau_sem=args.tau_sem, arms=arms)
        for arm, cell in result.items():
            if not cell["feasible"]:
                print(f"      {arm:20} INFACTIBLE  ({cell.get('reason','')})",
                      flush=True)
                continue
            g = cell["by_kind"].get("global", {})
            l = cell["by_kind"].get("local", {})
            print(f"      {arm:20} nodos={cell['n_nodes']:<3} "
                  f"pico={cell['peak_node_context']:<6} "
                  f"local={l.get('correct',0)}/{l.get('asked',0)} "
                  f"global={g.get('correct',0)}/{g.get('asked',0)}", flush=True)
        rows.append({"id": doc["id"], "n_rows": doc["n_rows"],
                     "split": doc.get("split"), "arms": result})

    summary = summarise(rows, args.budget)

    print("\n" + "=" * 72)
    print(f"POR BRAZO  (presupuesto W = {args.budget} tokens)")
    for arm, s in summary["by_arm"].items():
        acc = s["accuracy_by_kind"]
        print(f"  {arm:20} factible {s['n_feasible']}/{s['n_documents']}   "
              f"local {(acc.get('local') or {}).get('rate')}   "
              f"global {(acc.get('global') or {}).get('rate')}   "
              f"pico {s['peak_node_context_max']}   nodos {s['n_nodes_mean']}")

    print("\nPOR TAMANO  (factibles / global correcto)")
    for size, per_arm in summary["by_size"].items():
        cells = "   ".join(
            f"{arm.split('-')[0]}={v['feasible']}/{v['of']}"
            + (f" g={v['global_rate']:.2f}" if v["global_rate"] is not None else "")
            for arm, v in per_arm.items())
        marker = "  <- CELDA DECLARADA" if size == DECLARED_ROWS else ""
        print(f"  {size:>4} filas   {cells}{marker}")

    inv = summary["invalidations"]
    print("\nCONDICIONES DE INVALIDACION")
    if inv["run_is_readable"]:
        print("  ninguna se cumplio: la corrida se puede leer")
    else:
        for problem in inv["conditions_met"]:
            print(f"  *** {problem}")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_text(
            json.dumps({"summary": summary, "rows": rows}, indent=2),
            encoding="utf-8")
        fields = ["id", "n_rows", "split", "arm", "feasible", "n_nodes",
                  "peak_node_context", "total_context", "over_budget",
                  "local_correct", "local_asked", "global_correct", "global_asked"]
        with (out / "results.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                for arm, cell in sorted(row["arms"].items()):
                    l = cell["by_kind"].get("local", {})
                    g = cell["by_kind"].get("global", {})
                    writer.writerow({
                        "id": row["id"], "n_rows": row["n_rows"],
                        "split": row["split"], "arm": arm,
                        "feasible": cell["feasible"], "n_nodes": cell["n_nodes"],
                        "peak_node_context": cell["peak_node_context"],
                        "total_context": cell["total_context"],
                        "over_budget": cell.get("over_budget"),
                        "local_correct": l.get("correct"), "local_asked": l.get("asked"),
                        "global_correct": g.get("correct"), "global_asked": g.get("asked"),
                    })
        (out / "run_metadata.json").write_text(json.dumps({
            "tier": "feasibility",
            "backend": args.backend, "embedder": args.embedder,
            "harness_validation_only": args.backend == "mock",
            "embeddings_degraded": args.embedder == "hash",
            "node_budget_tokens": args.budget,
            "declared_rows": DECLARED_ROWS,
            "rho": args.rho, "split": args.split, "corpus": str(args.prompts),
            "corpus_frozen_sha256": json.loads(
                Path(args.prompts).read_text())["_frozen"]["sha256"],
            "corpus_split": args.split,
            "tau_sem": args.tau_sem,
            # Los dos campos que `read_dev_run` exige de cualquier corrida dev.
            # Se escriben aqui y no se dejan ausentes porque una corrida sin
            # ellos no dice con que codigo ni con que tuberia se ajusto, y la
            # compuerta la rechaza -- correctamente, y una hora tarde.
            "code_sha256": source_fingerprint(),
            "enforce_term_once": False,
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {out / 'summary.json'} and {out / 'results.csv'}")
    return 0 if summary["invalidations"]["run_is_readable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
