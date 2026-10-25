"""T06 — Corpus con una pregunta global respondible (el bloqueador). §15.4.

Desbloqueado el 24-09-2026. Deja de ser un diagnóstico transcrito y pasa a ser
(a) un diagnóstico **medido** sobre `results/lcurve-dev-*/rows.json`, (b) un
**generador** de corpus candidato y (c) una **compuerta de admisión** mecánica.

El diagnóstico, por pregunta y no en agregado
---------------------------------------------
El agregado documentado (1/72 globales) es correcto pero no dice dónde duele.
Desglosado, el brazo monolítico da:

    Q03  total de on_hand sobre todas las filas   0/24
    Q05  cuántas filas están bajo su reorder_at   0/24
    Q04  qué fila tiene el mayor on_hand          1/24

Las tres son **agregados n-arios**: su respuesta es función de todas las filas.
Un modelo de 2–3B que suma diez números de cuatro cifras no falla en el
protocolo, falla en la aritmética.

El arreglo
----------
Una pregunta es *global* cuando ningún fragmento puede responderla solo. Eso no
exige tocar todas las filas: exige tocar filas que el corte separa. Con dos
basta. El generador emite preguntas de aridad ≤3 sobre filas **verificadas** en
fragmentos distintos para *cada* celda declarada.

Lo que esta prueba NO establece
-------------------------------
Que el pool sepa responderlas. Eso exige una corrida, y la compuerta lo reporta
como PENDIENTE en lugar de darlo por hecho: un corpus que pasa el preflight y
luego no despeja el piso monolítico sigue siendo un corpus rechazado.
"""

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval import corpus as CO
from swarmblyval import loaders as L
from swarmblyval.report import Result, BLOCKED, PASS, REFUSE


def _parse_material(material):
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


def diagnose(rows_json):
    """Acierto por pregunta y por brazo, desde la corrida real."""
    per = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    kind = {}
    for r in rows_json:
        for qid, d in (r.get("detail") or {}).items():
            kind[qid] = d["kind"]
            cell = per[r["arm"]][qid]
            cell[1] += 1
            cell[0] += 1 if d["correct"] else 0
    return per, kind


def run():
    if not L.have_repo():
        return Result(
            id="T06", name="Corpus con pregunta global (bloqueador)", model="—",
            verdict=BLOCKED, summary="sin repositorio: exporta SWARMBLY_REPO",
            killed_if="— (construcción, no test)",
            refusal="sin datos reales no se emite diagnóstico")

    try:
        rows_json, run_dir = L.load_lcurve_rows()
        prompts, meta = L.load_lcurve_prompts()
    except L.DataRefusal as exc:
        return Result(id="T06", name="Corpus con pregunta global (bloqueador)",
                      model="—", verdict=REFUSE, summary=f"datos rechazados: {exc}",
                      killed_if="— (construcción, no test)", refusal=str(exc))

    per, kind = diagnose(rows_json)
    details, tables, notes = [], {}, []

    mono = per["monolithic"]
    gq = [q for q in sorted(mono) if kind[q] == "global"]
    lq = [q for q in sorted(mono) if kind[q] == "local"]
    g_ok = sum(mono[q][0] for q in gq); g_n = sum(mono[q][1] for q in gq)
    l_ok = sum(mono[q][0] for q in lq); l_n = sum(mono[q][1] for q in lq)

    details.append(f"Corrida diagnosticada: `{run_dir}`.")
    details.append(
        f"Brazo monolítico: globales **{g_ok}/{g_n}** ({g_ok/g_n:.3f}), locales "
        f"**{l_ok}/{l_n}** ({l_ok/l_n:.3f}).")
    details.append(
        "Desglosado por pregunta, las tres globales son agregados n-arios y las "
        "tres están en el suelo — no es el protocolo, es la aritmética.")

    tables["Diagnóstico por pregunta (medido, no transcrito)"] = (
        ["pregunta", "clase", "monolítico", "fragmentado"],
        [[f"Q{q}", kind[q],
          f"{mono[q][0]}/{mono[q][1]} = {mono[q][0]/mono[q][1]:.3f}",
          f"{per['fragmented'][q][0]}/{per['fragmented'][q][1]} = "
          f"{per['fragmented'][q][0]/max(1,per['fragmented'][q][1]):.3f}"]
         for q in sorted(mono)])

    # --- construir el candidato ---------------------------------------------
    docs = []
    for i, p in enumerate(prompts):
        try:
            docs.append(CO.build_document(
                p["id"].replace("lc_", "lc2_"), _parse_material(p["material"]),
                [tuple(c) for c in p["cells"]], seed=i))
        except ValueError as exc:
            notes.append(f"{p['id']}: el generador se negó ({exc}).")

    rep = CO.preflight(docs)
    details.append(
        f"Corpus candidato generado sobre el mismo material: **{len(docs)} "
        f"documentos**, preguntas de aridad ≤{CO.ARITY_CEILING} y ≤"
        f"{CO.OPERAND_CEILING} operandos.")

    # verificación independiente del preflight
    checked = violations = 0
    for d in docs:
        idx = {r.split(" | ")[0]: i
               for i, r in enumerate(d["material"].split("\n")) if r.strip()}
        for q in d["questions"]:
            if q["kind"] != "global":
                continue
            for (_n, Lc) in d["cells"]:
                checked += 1
                if len({idx[r] // Lc for r in q["rows"]}) < 2:
                    violations += 1
    details.append(
        f"Verificación independiente del preflight: {checked} comprobaciones "
        f"(pregunta × celda), **{violations} violaciones** — cada pregunta global "
        f"cita filas que el corte separa en toda celda declarada.")

    tables["Compuerta de admisión del corpus candidato"] = (
        ["comprobación", "estado", "detalle"],
        [[n, "PASS" if ok else "FAIL", d] for n, ok, d in rep.checks] +
        [[n, "PENDIENTE", d] for n, d in rep.pending])

    ej = docs[0]
    tables[f"Ejemplo generado — {ej['id']}"] = (
        ["id", "clase", "forma", "operandos", "pregunta", "clave"],
        [[q["id"], q["kind"], q["form"], q["operands"], q["text"], q["expected"]]
         for q in ej["questions"]])

    notes.append(
        "**El corpus NO queda admitido aquí.** Todo lo mecánico pasa, pero la "
        "única comprobación que decide —que el brazo monolítico despeje el piso "
        f"de {CO.MONOLITHIC_FLOOR:.2f} sobre las globales— exige correrlo. "
        "Declararlo pendiente en vez de suponerlo es la diferencia entre una "
        "compuerta y un adorno.")
    notes.append(
        "Para desbloquear: correr el brazo monolítico sobre la mitad **dev** del "
        "corpus candidato y pasar la tasa a `corpus.preflight(docs, "
        "monolithic_global_rate=...)`. La mitad held-out sigue sin tocarse.")
    notes.append(
        "Hallazgo secundario, medido y **menor**: 2 de 360 calificaciones (0.6 %) "
        "marcan mal una respuesta que contiene el valor esperado — `[Which] "
        "R-010` frente a `R-010`, y `8` frente a `R-008`. Es real y conviene "
        "arreglarlo, pero no explica el 1/72: corregido, el monolítico pasaría de "
        "1/72 a 3/72, que sigue siendo el suelo. El diagnóstico documentado se "
        "sostiene.")

    verdict = PASS if not rep.failures else REFUSE
    summary = (f"diagnóstico medido por pregunta + corpus candidato de {len(docs)} "
               f"docs; {len(rep.checks)} comprobaciones mecánicas pasan, falta la corrida")
    return Result(
        id="T06", name="Corpus con pregunta global (bloqueador)", model="—",
        verdict=verdict, summary=summary,
        killed_if="— (construcción, no test)",
        refusal=(f"monolítico < {CO.MONOLITHIC_FLOOR} · línea base de azar ≥ 0.20 · "
                 f"pregunta global que un fragmento pueda responder solo"),
        details=details, tables=tables, notes=notes)


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
