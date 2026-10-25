"""T00 — Procedencia de los datos y autocomprobación del instrumento.

Tres trabajos, y los tres son precondición de todo lo demás.

1. **Reconciliar** cada fixture dorado contra el artefacto real del repositorio.
   Un arnés que valida documentos contra sí mismos no valida nada; si la cifra
   transcrita y la medición no cuadran, hay que verlo aquí y no tres tests más
   abajo.

2. **Autocomprobar los predicados de rechazo.** Son el mecanismo que separa a
   este proyecto de un manifiesto, así que se prueban como cualquier otra cosa:
   con casos cuyo resultado correcto se conoce de antemano. Dos de ellos
   fallaban silenciosamente y las regresiones quedan fijadas abajo.

3. **Fijar el corpus de referencia.** `benchmark.jsonl` es la base de todos los
   veredictos empíricos, así que su digest queda anclado y su estructura
   comprobada: sin keys duplicadas, sin celdas fragmentadas huérfanas, sin
   scores fuera de rango. Si el corpus cambia, esto lo dice antes de que un
   número cambie en silencio en un documento.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval import constants as C
from swarmblyval import derivation as DV
from swarmblyval import fixtures as F
from swarmblyval import loaders as L
from swarmblyval.report import Result, FAIL, PASS, REFUSE
from swarmblyval.stats import (attainable_min_p, bimodality_summary,
                               exact_rank_sum, p_value_ceiling,
                               variance_refusal, withdraw_if_largest_cell_undoes)

#: Digest del corpus de referencia con el que se escribieron los documentos.
#: Anclarlo convierte «los números cambiaron» en un fallo visible en vez de una
#: discrepancia que alguien nota meses después.
BENCH_SHA256 = "dcd1931d98f7f0ec4d6c6dbf5d4ce6251680cc1bc133841a395be279e02c6285"
BENCH_RECORDS = 473


def _reconcile_bench(path):
    """Comprobaciones estructurales del corpus. Devuelve (filas, fallos)."""
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    recs, malformed = [], 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1

    keys = [r.get("key") for r in recs if r.get("key")]
    dupes = len(keys) - len(set(keys))
    arms = {}
    for r in recs:
        arms[r.get("arm", "—")] = arms.get(r.get("arm", "—"), 0) + 1
    monos = {(r["task"], r["model"]) for r in recs if r.get("arm") == "mono"}
    orphans = sum(1 for r in recs if r.get("arm") == "frag"
                  and (r.get("task"), r.get("model")) not in monos)
    scores = [r["grade"]["score"] for r in recs
              if isinstance(r.get("grade"), dict)
              and r["grade"].get("score") is not None]
    out_of_range = sum(1 for s in scores if not 0.0 <= s <= 1.0)

    rows = [
        ["digest sha256", BENCH_SHA256[:16] + "…", digest[:16] + "…",
         digest == BENCH_SHA256],
        ["registros", BENCH_RECORDS, len(recs), len(recs) == BENCH_RECORDS],
        ["líneas malformadas", 0, malformed, malformed == 0],
        ["keys duplicadas", 0, dupes, dupes == 0],
        ["celdas frag sin monolítico", 0, orphans, orphans == 0],
        ["scores fuera de [0,1]", 0, out_of_range, out_of_range == 0],
    ]
    fails = [r[0] for r in rows if not r[3]]
    return rows, fails, arms, len(scores)


def _selftest():
    """Casos con respuesta conocida para los predicados de rechazo."""
    out = []

    # Regresión 1: la guardia de conclusión agrupada exigía además
    # abs(rest) < abs(total), de modo que callaba justo cuando la inversión era
    # grande. Debe retirar.
    w, _ = withdraw_if_largest_cell_undoes([1.0, 101.0, -101.0])
    out.append(("guardia retira una inversión grande (total +1 → resto −100)", w))

    # Regresión 2: sólo quitaba un contribuyente, así que no veía el caso
    # documentado, donde la media la fabrican DOS prompts juntos.
    cells = [28.50, 23.08] + [-14.78 / 14] * 14
    w1, _ = withdraw_if_largest_cell_undoes(cells, top=1)
    w2, _ = withdraw_if_largest_cell_undoes(cells, top=2)
    out.append(("quitar 1 no invierte el signo (correcto)", not w1))
    out.append(("quitar 2 sí lo invierte: el caso documentado se detecta", w2))

    # Regresión 3: bimodality_summary mezclaba lista y dict; reventaba con ambas.
    try:
        s = bimodality_summary({"a": 1.0, "b": -2.0, "c": 3.0}, ("c",))
        ok = s["n"] == 3 and s["at_or_below_zero"] == 1 and s["expensive"] == {"c": 3.0}
    except Exception:
        ok = False
    out.append(("bimodality_summary acepta {id: valor}", ok))

    # Varianza cero debe rechazar.
    ref, _ = variance_refusal([3.5] * 16, "δ")
    out.append(("varianza cero del predictor se rechaza", ref))

    # El techo de p es el que dice la teoría para 11 vs 2.
    out.append(("techo de p (11 vs 2) = 0.0256", abs(p_value_ceiling(11, 2) - 2 / 78) < 1e-12))

    # El rank-sum exacto alcanza ese techo con separación perfecta y SIN empates.
    # (Con los once valores empatados el mínimo alcanzable es otro: los empates
    # colapsan la distribución de permutación. Ese matiz costó una falla de esta
    # misma autocomprobación y por eso existe `attainable_min_p`.)
    _, p, _ = exact_rank_sum([0.1 + i / 1000 for i in range(11)], [0.9, 0.95])
    out.append(("rank-sum exacto alcanza el techo sin empates",
                abs(p - 2 / 78) < 1e-9))

    # Con empates el techo real es peor que la fórmula sin empates.
    pmin_tied, _ = attainable_min_p([5.5] * 11, [5.5, 4.5])
    out.append(("con empates, el p mínimo alcanzable empeora respecto de 0.0256",
                pmin_tied > 2 / 78))
    return out


def run():
    details, tables, notes = [], {}, []
    failures = []

    # --- 1. autocomprobación -------------------------------------------------
    checks = _selftest()
    bad = [n for n, ok in checks if not ok]
    failures += bad
    tables["Autocomprobación de los predicados de rechazo"] = (
        ["comprobación", "resultado"],
        [[n, "PASS" if ok else "FAIL"] for n, ok in checks])
    details.append(
        f"Autocomprobación del instrumento: {len(checks) - len(bad)}/{len(checks)} "
        f"predicados se comportan como se declara.")

    # --- 2. discrepancia H ---------------------------------------------------
    implied = [DV.header_implied_H(p_tokens, n, floor)
               for _name, p_tokens, n, floor, _h in F.HEADER_FLOOR]
    mean_implied = sum(implied) / len(implied)
    rho_doc = DV.rho_from(C.L_REF, C.F_MEASURED, H=C.H_TOKENS)
    rho_imp = DV.rho_from(C.L_REF, C.F_MEASURED, H=mean_implied)
    tables["H declarada frente a H despejada de los pisos"] = (
        ["prompt", "|P|", "N", "piso ρ", "H despejada"],
        [[n, p, k, f, f"{h:.1f}"]
         for (n, p, k, f, _), h in zip(F.HEADER_FLOOR, implied)])
    details.append(
        f"`H` declarada en el whitepaper: **{C.H_TOKENS:.0f}** tokens. Despejada "
        f"de los cuatro pisos de empaquetado: {', '.join(f'{h:.1f}' for h in implied)} "
        f"→ media **{mean_implied:.2f}**.")
    details.append(
        f"Impacto en ρ (L={C.L_REF}, F={C.F_MEASURED}): {rho_doc:.4f} con H=39 "
        f"frente a {rho_imp:.4f} con H={mean_implied:.2f} — una diferencia de "
        f"{abs(rho_imp - rho_doc):.4f}, que no mueve ninguna conclusión pero "
        f"conviene unificar en los documentos.")

    # --- 3. el corpus de referencia (no depende del repo) --------------------
    bench = L.bench_path()
    if bench is None:
        notes.append("Sin `benchmark.jsonl`: el corpus de referencia no se "
                     "reconcilia. Exporta `SWARMBLY_BENCH` para activarlo.")
    else:
        rows, bfails, arms, n_scored = _reconcile_bench(bench)
        failures += bfails
        tables["Corpus de referencia (`benchmark.jsonl`)"] = (
            ["comprobación", "esperado", "observado", "coincide"],
            [[n, e, o, "sí" if ok else "NO"] for n, e, o, ok in rows])
        details.append(
            f"Corpus de referencia anclado: {', '.join(f'{k}={v}' for k, v in sorted(arms.items()))} "
            f"— {n_scored} registros con score.")

    # --- 4. reconciliación con los artefactos reales -------------------------
    if not L.have_repo():
        notes.append("Sin repositorio: la reconciliación con datos reales se omite. "
                     "Exporta `SWARMBLY_REPO` para activarla.")
        verdict = FAIL if failures else PASS
        return Result(id="T00", name="Procedencia y autocomprobación", model="—",
                      verdict=verdict,
                      summary=(f"{len(failures)} discrepancias: {failures[:3]}"
                               if failures else
                               "predicados verificados y corpus anclado; sin "
                               "repo no hay reconciliación de fixtures"),
                      killed_if="— (precondición, no modelo)",
                      refusal="sin artefactos reales no se reconcilia",
                      details=details, tables=tables, notes=notes)

    # Ausente y discrepante no son lo mismo, y el arnés no debe confundirlos.
    # Los directorios de corrida viven fuera del control de versiones (política
    # de `results/` del repositorio), así que quien clone no los tiene: eso es
    # una RECONCILIACIÓN NO DISPONIBLE, no una cifra que no cuadra. Un artefacto
    # presente que no reproduce su cifra sí es un fallo, y sigue siéndolo.
    rec, unavailable = [], []
    try:
        tax, run_dir = L.load_tax_16()
        xs = sorted(tax.values())
        mean = sum(xs) / len(xs)
        med = (xs[len(xs) // 2] if len(xs) % 2
               else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2)
        rec.append(("media del impuesto (16 prompts)", F.TAX_16["mean"], f"{mean:.4f}",
                    abs(mean - F.TAX_16["mean"]) <= 0.02))
        rec.append(("mediana", F.TAX_16["median"], f"{med:.4f}",
                    abs(med - F.TAX_16["median"]) <= 0.02))
        rec.append(("prompts en cero o por debajo", F.TAX_16["n_at_or_below_zero"],
                    sum(1 for x in xs if x <= 0),
                    sum(1 for x in xs if x <= 0) == F.TAX_16["n_at_or_below_zero"]))
        for pid, val in F.TAX_16["expensive"].items():
            rec.append((f"{pid}", val, f"{tax[pid]:.2f}", abs(tax[pid] - val) <= 0.02))
        details.append(f"Impuesto reconciliado contra `{run_dir}`.")
    except L.DataRefusal as exc:
        unavailable.append(f"impuesto: {exc}")

    try:
        rows_json, lrun = L.load_lcurve_rows()
        g_ok = sum(r["by_kind"]["global"]["correct"]
                   for r in rows_json if r["arm"] == "monolithic")
        g_n = sum(r["by_kind"]["global"]["asked"]
                  for r in rows_json if r["arm"] == "monolithic")
        rec.append(("globales del monolítico (curva-L)",
                    f"{F.LCURVE['monolithic_global_ok']}/{F.LCURVE['n_documents']}",
                    f"{g_ok}/{g_n}",
                    g_ok == F.LCURVE["monolithic_global_ok"] and
                    g_n == F.LCURVE["n_documents"]))
        details.append(f"Curva-L reconciliada contra `{lrun}`.")
    except L.DataRefusal as exc:
        unavailable.append(f"curva-L: {exc}")

    if rec:
        tables["Fixture documentado frente a artefacto real"] = (
            ["cifra", "documentos", "artefacto", "coincide"],
            [[n, d, a, "sí" if ok else "NO"] for n, d, a, ok in rec])
        failures += [n for n, _d, _a, ok in rec if not ok]

    # --- hallazgo medido sobre la calificación -------------------------------
    notes.append(
        "Discrepancia `H` = 39 (whitepaper) frente a 41.25 (media despejada). "
        "Real y menor: mueve ρ de 1.4520 a 1.4550. Unificar, no recalcular nada.")
    notes.append(
        "Ambigüedad señalada en los documentos entre «25 % del fragmento» y "
        "«F = 25 oraciones»: con L=50 las dos lecturas coinciden numéricamente "
        "(25 oraciones = 50 % del núcleo, 2F/L = 1.0), lo que explica que no se "
        "detectara. Conviene fijar **F en oraciones** y borrar la forma "
        "porcentual, que es la que reintroduce el error que §6.5 corrige.")

    if unavailable:
        notes.append(
            "**Reconciliación parcial.** No están en el árbol los artefactos de "
            "corrida que cita el whitepaper v1.4 (" + "; ".join(unavailable) +
            "). El repositorio no versiona `results/`, así que un clon no los "
            "tiene: la comprobación **se declara no disponible** en vez de "
            "pasar o fallar. Para activarla, apunta `SWARMBLY_REPO` a un "
            "checkout que conserve sus directorios de corrida.")

    if failures:
        verdict = FAIL
        summary = f"{len(failures)} discrepancias: {failures[:3]}"
    elif unavailable:
        verdict = REFUSE
        summary = ("predicados verificados y corpus anclado; la reconciliación "
                   f"con {len(unavailable)} artefactos de corrida no está "
                   "disponible en un clon")
    else:
        verdict = PASS
        summary = ("fixtures reconciliados con los artefactos reales; "
                   "predicados verificados")
    return Result(
        id="T00", name="Procedencia y autocomprobación", model="—",
        verdict=verdict, summary=summary,
        killed_if="— (precondición, no modelo)",
        refusal="cualquier fixture que no reproduzca su artefacto detiene el arnés",
        details=details, tables=tables, notes=notes)


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
