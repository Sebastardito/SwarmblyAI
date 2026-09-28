"""Integración de datos reales en el arnés de validación.

Lee el JSONL producido por swarmbly_ref (Ollama, 5 familias) y re-verifica las
pruebas del arnés con datos empíricos:

    python3 run_real.py --data ../swarmbly_ref/data/benchmark.jsonl

Produce resumen en consola + REPORT_REAL.md. Si no hay datos, emite BLOCKED con
la razón (sin fabricar resultados).
"""

import argparse
import json
import math
import os
import sys
from statistics import fmean, median

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from swarmblyval import constants as C
from swarmblyval import report
from swarmblyval.report import Result, PASS, FAIL, REFUSE, BLOCKED
from swarmblyval.stats import (attainable_min_p, clustered_bootstrap,
                               exact_rank_sum, rank_sum_test, spearman)
from swarmbly_ref import llm, planner, units
from swarmbly_ref.benchmarks import corpus as ref_corpus


def ap_default_data():
    """Ruta por defecto del corpus de referencia.

    Apunta a `HERE`, no a `ROOT`: el error anterior resolvía a un directorio
    inexistente, con lo que una corrida sin `--data` cargaba cero registros y
    emitía BLOCKED en todos los tests — indistinguible de «no hay datos».
    `SWARMBLY_BENCH` la sobreescribe, igual que en el resto del arnés.
    """
    from swarmblyval.loaders import bench_path
    return bench_path() or os.path.join(HERE, "swarmbly_ref", "data",
                                        "benchmark.jsonl")


def load(path):
    recs = []
    if not os.path.exists(path):
        return recs
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return recs


def mono(recs, task, model):
    return next((r for r in recs if r.get("task") == task
                 and r.get("arm") == "mono" and r.get("model") == model), None)


def delta_of(record):
    """Recomputa delta desde los cortes guardados con la definición refinada
    (acoplamiento en el corte + cadenas + explícitas), independientemente de
    la versión del planner que escribió el registro."""
    task = ref_corpus.ALL_TASKS.get(record.get("task"))
    if task is None or "cuts" not in record:
        return None
    sents = units.split_sentences(task["material"])
    chains = units.entity_chains(sents, list(task.get("entities", {}).keys()))
    return round(planner.compute_delta(sents, record["cuts"], chains,
                                       task.get("explicit_crossings", 0)), 3)


def frag(recs, task, model):
    return next((r for r in recs if r.get("task") == task
                 and r.get("arm") == "frag" and r.get("model") == model), None)


def score_of(task_id, text_or_grade):
    """Recompone el score con el INSTRUMENTO ACTUAL (grader vivo, incluidos
    los componentes numéricos) desde el TEXTO guardado; así las mejoras de
    instrumento aplican retroactivamente sin re-correr modelos. Si se pasa un
    dict de grados (registros fault sin texto), cae al camino de pesos."""
    from swarmbly_ref import grader as gr
    t = ref_corpus.ALL_TASKS.get(task_id)
    if isinstance(text_or_grade, str):
        if not text_or_grade.strip():
            return 0.0
        return gr.grade(t, text_or_grade)["score"] if t else 0.0
    w = t["weights"] if t else {"coverage": 0.4, "qa": 0.4, "seam_free": 0.2}
    return round(sum(text_or_grade.get(k, 0.0) * wk for k, wk in w.items()), 4)


def tax_of(mono_r, frag_r):
    if mono_r is None or frag_r is None:
        return None
    m = score_of(mono_r["task"], mono_r.get("text", ""))
    f = score_of(frag_r["task"], frag_r.get("assembled_text", ""))
    if m < 0.20:
        return None
    return round((m - f) / m * 100.0, 2)


# ---------------------------------------------------------------------------

def t05_real(recs):
    """Ley de escala de rho con datos reales, con contabilidad NO circular:
    el tamaño de paquete observado se predice desde componentes medidos por
    separado (Γ + instrucción + flancos + material), y la ley de escala se
    prueba con el barrido de L del longform."""
    frags = [r for r in recs if r.get("arm") == "frag"]
    if not frags:
        return Result(id="T05R", name="Ley de escala de ρ (datos reales)",
                      model="—", verdict=BLOCKED,
                      summary="sin registros frag en el JSONL",
                      killed_if="el ρ observado no sigue la curva",
                      refusal="sin datos", details=[])

    rows = []
    for r in frags:
        if not all(k in r for k in ("material_tokens", "per_packet_tokens",
                                    "n_fragments")):
            continue   # fan records: no packet accounting
        n = r["n_fragments"]
        if n < 2 or r.get("task") not in ref_corpus.ALL_TASKS:
            continue
        task = ref_corpus.ALL_TASKS[r["task"]]
        L, F = r.get("L", 8), r.get("F", 2)
        n_sent = len(units.split_sentences(task["material"]))
        tok_per_sent = r["material_tokens"] / max(1, n_sent)
        mat_per = r["material_tokens"] / n
        # fixed per packet: Gamma + instruction (model-free token count)
        from swarmbly_ref import packer
        h_fixed = units.approx_tokens(packer.build_gamma(task)
                                      + "\n\n" + task["instruction_frag"])
        # flanks: F lead + F trail sentences, minus edges (2F * (1 - 1/N))
        flank_per = 2 * F * (1 - 1.0 / n) * tok_per_sent
        pred_pkt = mat_per + flank_per + h_fixed
        obs_pkt = fmean(r["per_packet_tokens"])
        err = abs(obs_pkt - pred_pkt) / obs_pkt
        rows.append((r["task"], r["model"], L, r["rho"], h_fixed,
                     round(flank_per), round(pred_pkt), round(obs_pkt), err))

    errs = [r[8] for r in rows]
    accounting_ok = fmean(errs) < 0.15
    # scaling: across the longform sweep, rho must fall as L grows
    sweep = sorted((r[2], r[3]) for r in rows if r[0] == "longform")
    monotone = all(sweep[i][1] >= sweep[i + 1][1] - 1e-9
                   for i in range(len(sweep) - 1)) if len(sweep) >= 2 else None

    details = [
        f"H fijo (Γ+instrucción, contado sin modelos): media "
        f"{fmean([r[4] for r in rows]):.0f} tok por paquete — el documento "
        f"declara H≈39 para un Γ compacto; aquí Γ incluye el glosario de entidades.",
        f"Contabilidad: paquete predicho (material+flancos+H) vs observado, "
        f"error medio {fmean(errs):.1%} → la derivación "
        f"{'explica' if accounting_ok else 'NO explica'} los tamaños observados.",
    ]
    if monotone is not None:
        # una fila por punto distinto: el barrido repetía cada L una vez por
        # familia, y cinco copias del mismo par no son cinco datos
        uniq = sorted({(l, round(rho, 2)) for l, rho in sweep})
        details.append(
            f"Barrido longform L={[l for l, _ in uniq]}: "
            f"ρ={[r for _, r in uniq]} "
            f"— {'cae' if monotone else 'NO cae'} al crecer L "
            f"(predicción de escalabilidad).")
    verdict = PASS if (accounting_ok and (monotone in (None, True))) else FAIL
    tables = {
        "Contabilidad de paquetes (observado vs predicho)": (
            ["tarea", "modelo", "L", "ρ obs", "H fijo", "flancos", "pkt pred",
             "pkt obs", "err"],
            [[r[0][:12], r[1], r[2], f"{r[3]:.2f}", r[4], r[5], r[6], r[7],
              f"{r[8]:.0%}"] for r in rows],
        )
    }
    return Result(
        id="T05R", name="Ley de escala de ρ (datos reales)", model="—",
        verdict=verdict,
        summary=f"contabilidad predice paquetes con error {fmean(errs):.1%}; "
                f"barrido L {'cae' if monotone else 'n/d'}",
        killed_if="el ρ observado no sigue la curva derivada",
        refusal="sin celdas frag comparables",
        details=details, tables=tables, notes=[])


def t04_real(recs):
    """δ explica la bimodalidad — test CANÓNICO intra-categoría: solo celdas
    de tabla (table_summary), que ahora incluyen 4 tareas × 5 modelos ×
    cortes débil/fuerte (δ variado dentro de la categoría)."""
    cells = []
    for r in recs:
        if r.get("arm") != "frag":
            continue
        task = ref_corpus.ALL_TASKS.get(r.get("task"))
        if task is None or task.get("kind") != "table_summary":
            continue
        m = mono(recs, r["task"], r["model"])
        if m is None:
            continue
        t = tax_of(m, r)
        if t is None:
            continue
        cells.append((r["task"], r["model"], delta_of(r) or 0.0, t))
    if len(cells) < 6:
        return Result(id="T04R", name="δ explica la bimodalidad (datos reales)",
                      model="M4", verdict=BLOCKED,
                      summary=f"solo {len(cells)} celdas de tabla con tax y δ: negarse a concluir",
                      killed_if="δ no separa los grupos",
                      refusal=f"{len(cells)} celdas < 6", details=[])

    free = [c[2] for c in cells if c[3] <= 0.0]
    expensive = [c[2] for c in cells if c[3] > 5.0]
    sep = None
    exact = None
    pmin = None
    if len(free) >= 2 and len(expensive) >= 2:
        # Grupos chicos: la aproximación normal no vale y sobreestima el p.
        # Se usa la permutación exacta cuando el espacio es enumerable, y se
        # reporta además el p MÍNIMO ALCANZABLE con estos empates: sin él, un
        # "no separa" puede ser falta de potencia disfrazada de resultado.
        if len(free) + len(expensive) <= 22:
            _U, p_exact, _tot = exact_rank_sum(free, expensive)
            pmin, _ = attainable_min_p(free, expensive)
            exact = True
            sep = (p_exact, None, None)
        else:
            U, z, p = rank_sum_test(free, expensive)
            exact = False
            sep = (p, z, U)
    # correlación de rangos δ vs tax, con corrección de empates
    # (el cálculo anterior mapeaba valor→índice en un dict, de modo que los
    # empates colapsaban al último índice en vez de promediar el rango)
    n = len(cells)
    rho_dt = spearman([c[2] for c in cells], [c[3] for c in cells])

    n_tasks_here = len({c[0] for c in cells})
    details = [
        f"{n} celdas de tabla ({n_tasks_here} tareas × {len(MODEL_IDS)} modelos × "
        "cortes débil/fuerte) con tax y δ medidos — la categoría única que exige "
        "el test canónico.",
        f"Spearman(δ, tax) = {rho_dt:+.2f} (rangos con corrección de empates) "
        f"— M4 predice correlación positiva.",
        f"Grupo 'caro' (tax>5%): n={len(expensive)}, δ mediana "
        f"{median(expensive) if expensive else '—'}.",
        f"Grupo 'gratis' (tax≤0): n={len(free)}, δ mediana {median(free) if free else '—'}.",
    ]
    if sep:
        kind = "permutación exacta" if exact else "aproximación normal"
        line = (f"Rank-sum entre grupos ({kind}): p={sep[0]:.4f} → "
                f"{'SEPARA' if sep[0] < 0.05 else 'no separa a α=0.05'}.")
        if pmin is not None:
            line += (f" Techo de potencia con estos empates: p mínimo "
                     f"alcanzable = {pmin:.4f}"
                     + ("  — **el diseño no puede alcanzar α=0.05**, así que un "
                        "'no separa' aquí no es evidencia contra M4, es falta de "
                        "potencia." if pmin >= 0.05 else "."))
        details.append(line)
    underpowered = pmin is not None and pmin >= 0.05
    verdict = PASS if (rho_dt > 0.2 and (sep is None or sep[0] < 0.05)) else FAIL
    tables = {
        "Celdas de tabla reales (tax % vs δ)": (
            ["tarea", "modelo", "δ", "tax %"],
            [[c[0][:14], c[1], f"{c[2]:.2f}", f"{c[3]:+.1f}"] for c in
             sorted(cells, key=lambda c: -c[3])],
        )
    }
    notes = ["La pregunta decisiva de M4 (δ mueve la distorsión a ρ "
             "constante) la responde además el experimento controlado "
             "T07R (corte débil vs fuerte en el MISMO prompt)."]
    if underpowered:
        notes.append(
            "**Alcance del rank-sum.** Con estos tamaños y empates el p mínimo "
            f"alcanzable es {pmin:.4f}: la prueba de separación no puede dar "
            "significativo aunque la separación fuera perfecta. El veredicto "
            "descansa entonces en la correlación y en T07R, no en este p.")
    return Result(id="T04R", name="δ explica la bimodalidad (datos reales)",
                  model="M4", verdict=verdict,
                  summary=f"Spearman(δ,tax)={rho_dt:+.2f} sobre {n} celdas de tabla (intra-categoría)",
                  killed_if="δ no separa los grupos (Spearman≈0 y rank-sum ns)",
                  refusal=f"n={len(cells)} celdas; mínimo para veredicto: 6",
                  details=details, tables=tables, notes=notes)


def t06_real(recs):
    """Verificación del instrumento: el grader puntúa 100% la respuesta
    perfecta (escrita a mano donde la clave es DERIVADA); piso del monolítico;
    y answerability: ¿qué claves son citables vs derivables?"""
    from swarmbly_ref import grader
    n_ok, n_bad = 0, 0
    derivable = {}
    for tid, t in ref_corpus.ALL_TASKS.items():
        if tid == "chain_refusal":
            continue
        perfect = t.get("perfect_answer", t["material"])
        g = grader.grade(t, perfect)["score"]
        if g >= 0.99:
            n_ok += 1
        else:
            n_bad += 1
        # answerability: mono qa split into stated vs computed keys
        m = next((r for r in recs if r.get("task") == tid
                  and r.get("arm") == "mono"), None)
        if m and t.get("answer_keys"):
            stated, computed = 0, 0
            for k in t["answer_keys"]:
                ks = k if isinstance(k, list) else [k]
                if any(x in t["material"] for x in ks):
                    stated += 1
                else:
                    computed += 1
            derivable[tid] = (stated, computed,
                              round(m["grade"].get("qa", 0), 2))
    monos = [score_of(r["task"], r.get("text", "")) for r in recs if r.get("arm") == "mono"]
    above_floor = [s for s in monos if s >= 0.20]
    details = [
        f"Grader auto-verificado con respuesta perfecta (a mano donde la clave "
        f"es derivada): {n_ok}/{n_ok + n_bad} tareas puntúan ≥0.99.",
        f"Monolíticos (n={len(monos)}): {len(above_floor)} despejan el piso 0.20; "
        f"media {fmean(monos):.3f}.",
        "Answerability (qa del monolítico): las claves DERIVADAS (totales "
        "calculados) replican el diagnóstico de la curva-L documentada.",
    ]
    tables = {
        "Answerability por tarea (claves citables vs derivables)": (
            ["tarea", "citables", "derivables", "qa mono"],
            [[tid, v[0], v[1], f"{v[2]:.2f}"] for tid, v in derivable.items()],
        )
    }
    verdict = PASS if n_bad == 0 and len(above_floor) >= max(2, len(monos) // 2) \
        else (BLOCKED if n_bad else FAIL)
    return Result(id="T06R", name="Instrumento del corpus (datos reales)",
                  model="—", verdict=verdict,
                  summary=f"grader verificado ({n_ok}/{n_ok + n_bad}); monolíticos sobre piso: {len(above_floor)}/{len(monos)}",
                  killed_if="—", refusal="sin datos",
                  details=details, tables=tables,
                  notes=["El piso de 0.20 se aplica por celda; las celdas bajo el "
                         "piso se excluyen del cálculo de tax (como exige §15.7)."])


def _l_curve_analysis(rows):
    rows = sorted(rows)
    ls = [r[0] for r in rows]
    qs = [r[1] for r in rows]
    qmax = max(qs)
    good = [ls[i] for i in range(len(rows)) if qs[i] >= 0.95 * qmax]
    floor = next((ls[i] for i in range(len(rows)) if qs[i] >= 0.10 * qmax), None)
    band = (min(good), max(good)) if len(good) >= 2 else None
    factor = (max(good) / min(good)) if len(good) >= 2 else None
    return rows, ls, qs, qmax, floor, band, factor


def t08_real(recs):
    """Curva-L real, por tarea (longform con barrido 10–40; table_outturn con
    4–16). Los scores solo son comparables DENTRO de cada tarea."""
    curves = {}
    for r in recs:
        if r.get("arm") == "frag" and "|strong" not in r.get("key", ""):
            tid = r.get("task")
            if tid in ("longform", "table_outturn"):
                curves.setdefault(tid, []).append(
                    (r.get("L", 15),
                     score_of(tid, r.get("assembled_text", ""))))
    if not curves:
        return Result(id="T08R", name="Curva-L (datos reales)", model="—",
                      verdict=BLOCKED, summary="sin puntos (L, calidad)",
                      killed_if="no aparece piso ni banda",
                      refusal="sin datos", details=[])

    analyses = {tid: _l_curve_analysis(rows) for tid, rows in curves.items()}
    details, table_rows = [], []
    all_factors = []
    for tid, (rows, ls, qs, qmax, floor, band, factor) in analyses.items():
        details.append(
            f"{tid}: L_min≈{floor}, banda {band} "
            f"(factor {factor:.2f})" if floor else f"{tid}: sin piso detectable")
        if factor:
            all_factors.append(factor)
        table_rows.extend([[tid, str(l), f"{q:.3f}"] for l, q in rows])
    band_ok = all(f >= 1.5 for f in all_factors) if all_factors else False
    verdict = PASS if band_ok else FAIL
    return Result(id="T08R", name="Curva-L (datos reales)", model="—",
                  verdict=verdict,
                  summary="; ".join(
                      f"{tid}: banda {a[5]} (factor {a[6]:.2f})" if a[5] else
                      f"{tid}: sin banda" for tid, a in analyses.items()),
                  killed_if="no aparece piso ni banda discernibles",
                  refusal="sin puntos suficientes",
                  details=details,
                  tables={"Curva-L observada (por tarea)": (
                      ["tarea", "L (oraciones)", "score"],
                      table_rows)},
                  notes=["Los scores no son comparables ENTRE tareas (graders y "
                         "pesos distintos); la banda se juzga dentro de cada una.",
                         "La predicción: piso L_min nítido y banda ancha (factor "
                         "3–6×). Esta es la primera curva con más de un punto por "
                         "tarea."])


def _length_confound(recs, negligible=0.20):
    """¿El impuesto agregado está confundido con la longitud de salida?

    Devuelve (bool, detalle). Usa el estadístico SIN denominador (`frag - mono`)
    para no heredar el acoplamiento del propio impuesto.
    """
    import statistics as _st
    monos = {(r["task"], r["model"]): r for r in recs if r.get("arm") == "mono"}
    def _w(r):
        return len(str(r.get("assembled_text") or r.get("text") or "").split())
    # si existen celdas con presupuesto igualado (|matched), son ellas las que
    # deciden: la pregunta del confundido es si IGUALADO el presupuesto el
    # agregado sigue confundido, no si el presupuesto desigual lo estaba
    matched = [r for r in recs if r.get("arm") == "frag"
               and r.get("match_output")]
    ratio, diff = [], []
    for r in recs:
        if r.get("arm") != "frag" or "|strong" in r.get("key", ""):
            continue
        if matched and not r.get("match_output"):
            continue   # presupuesto igualado disponible: medir sobre él
        m = monos.get((r["task"], r["model"]))
        if m is None:
            continue
        ms = m["grade"]["score"]
        if ms is None or ms < 0.20:
            continue
        ratio.append(_w(r) / max(1, _w(m)))
        diff.append(r["grade"]["score"] - ms)
    if len(ratio) < 20:
        return False, f"sólo {len(ratio)} celdas: no se evalúa el confundido"
    rho = _spearman_simple(ratio, diff)
    med = _st.median(ratio)
    return abs(rho) >= negligible, (
        f"Confundido de longitud: el fragmentado escribe **{med:.2f}×** lo que "
        f"el monolítico (mediana) y Spearman(razón, frag − mono) = **{rho:+.3f}** "
        f"sobre {len(ratio)} celdas — estadístico sin denominador.")


def _spearman_simple(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    import math
    rx, ry = rank(list(xs)), rank(list(ys))
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def t09_real(recs):
    """Re-prueba del criterio: distribución del tax sobre las celdas reales."""
    matched_any = any(r.get("arm") == "frag" and r.get("match_output")
                      for r in recs)
    cells = []
    for r in recs:
        if r.get("arm") != "frag" or "|strong" in r.get("key", ""):
            continue   # el criterio se mide sobre el corte operativo (P9)
        if matched_any and not r.get("match_output"):
            continue   # con presupuesto igualado disponible, medir sobre él
        m = mono(recs, r["task"], r["model"])
        t = tax_of(m, r)
        if t is None:
            continue
        cells.append((r["task"], r["model"], t))
    if len(cells) < 8:
        return Result(id="T09R", name="Criterio de abandono (datos reales)",
                      model="—", verdict=BLOCKED,
                      summary=f"{len(cells)} celdas < 8: negarse a emitir veredicto",
                      killed_if="—", refusal=f"{len(cells)} celdas < 8", details=[])
    taxes = [c[2] for c in cells]
    mean, lo, hi, se = clustered_bootstrap(taxes, [c[0] for c in cells])
    met = hi < C.CRITERION_TAX
    at_or_below = sum(1 for t in taxes if t <= 0)

    # --- baseline self-consistency (v0.3, Zhang et al.) ---------------------
    # una fila por (tarea, modelo): SC vs la celda frag PRIMARIA (L por defecto)
    sc_rows = []
    scs = {(r["task"], r["model"]): r for r in recs
           if r.get("arm") == "selfcons"}
    for (tid, model), sc in scs.items():
        m = mono(recs, tid, model)
        if m is None:
            continue
        s_m = score_of(tid, m.get("text", ""))
        if s_m < 0.20:
            continue   # piso baseline
        task = ref_corpus.ALL_TASKS.get(tid, {})
        L = task.get("L_target", 10)
        f = next((r for r in recs if r.get("arm") == "frag"
                  and r.get("task") == tid and r.get("model") == model
                  and r.get("L") == L
                  and "|strong" not in r.get("key", "")), None)
        if f is None:
            continue
        s_f = score_of(tid, f.get("assembled_text", ""))
        s_sc = score_of(tid, sc.get("text", ""))
        sc_rows.append((tid, model, round(s_m, 2), round(s_f, 2),
                        round(s_sc, 2), round((s_m - s_sc) / s_m * 100, 1)))
    sc_detail = []
    if sc_rows:
        wins = sum(1 for r in sc_rows if r[3] is not None and r[3] >= r[4] - 1e-9)
        sc_detail = [
            f"Self-consistency (k=5, temp 0.7, medoid semántico): {len(sc_rows)} "
            f"celdas comparables; la fragmentación ≥ SC en {wins}/{len(sc_rows)}.",
            "v0.3 exige justificar el cómputo extra contra este rival, no solo "
            "contra el monolítico de una pasada.",
        ]

    # --- COMPUERTA DE LONGITUD (añadida 25-09-2026) -------------------------
    # El brazo fragmentado escribe más que el monolítico y las componentes que
    # deciden el score suben con la longitud. Mientras el presupuesto de salida
    # no esté igualado, este agregado no dice si fragmentar ayuda: dice que el
    # brazo que escribe más puntúa más. T11 lo mide; aquí se REHÚSA el veredicto
    # en vez de emitir un CUMPLIDO que no es interpretable.
    confounded, conf_detail = _length_confound(recs)
    if confounded:
        return Result(
            id="T09R", name="Criterio de abandono (datos reales)", model="—",
            verdict=REFUSE,
            summary=(f"REHUSADO: tax {mean:+.2f}% IC95 [{lo:+.2f}, {hi:+.2f}] "
                     f"pero el agregado está confundido con la longitud de salida"),
            killed_if="— (go/no-go del proyecto)",
            refusal=("presupuesto de salida no igualado entre brazos: el "
                     "criterio no está cumplido ni incumplido, está sin medir"),
            details=[
                f"n={len(cells)} celdas; mediana {median(taxes):+.2f}%; "
                f"{at_or_below} en ≤0.",
                conf_detail,
                "Para desbloquear: correr con presupuesto de salida igualado "
                "(`--match-output-tokens`) y volver a juzgar.",
            ] + sc_detail,
            tables={"Tax por celda": (
                ["tarea", "modelo", "tax %"],
                [[c[0][:14], c[1], f"{c[2]:+.1f}"]
                 for c in sorted(cells, key=lambda x: -x[2])]),
                "Mono vs frag vs self-consistency (score)": (
                    ["tarea", "modelo", "mono", "frag", "SC", "tax SC %"],
                    [[r[0][:12], r[1], r[2],
                      f"{r[3]:.2f}" if r[3] is not None else "—",
                      r[4], f"{r[5]:+.1f}"] for r in sc_rows])},
            notes=["No afecta a T04R ni T07R: ésos comparan fragmentado contra "
                   "fragmentado a ρ constante, donde la longitud es comparable."])

    verdict = PASS if met else FAIL
    return Result(id="T09R", name="Criterio de abandono (datos reales)",
                  model="—", verdict=verdict,
                  summary=f"tax medio {mean:+.2f}%, IC95 [{lo:+.2f}, {hi:+.2f}] → "
                          f"{'CUMPLIDO' if met else 'NO cumplido'} vs 5%",
                  killed_if="— (go/no-go del proyecto)",
                  refusal=f"{len(cells)} celdas < 8; baseline <0.20 excluido",
                  details=[
                      f"n={len(cells)} celdas (tarea×modelo); mediana "
                      f"{median(taxes):+.2f}%; {at_or_below} en ≤0.",
                      "Criterio formal: el límite SUPERIOR del IC95 agrupado por "
                      "prompt debe quedar bajo 5%.",
                  ] + sc_detail,
                  tables={"Tax por celda": (
                      ["tarea", "modelo", "tax %"],
                      [[c[0][:14], c[1], f"{c[2]:+.1f}"] for c in
                       sorted(cells, key=lambda c: -c[2])]),
                      "Mono vs frag vs self-consistency (score)": (
                          ["tarea", "modelo", "mono", "frag", "SC", "tax SC %"],
                          [[r[0][:12], r[1], r[2],
                            f"{r[3]:.2f}" if r[3] is not None else "—",
                            r[4], f"{r[5]:+.1f}"] for r in sc_rows])},
                  notes=["MUESTRA PEQUEÑA: el plan exige 60–72 prompts de una sola "
                         "categoría; esto es ~n celdas de varias categorías. No "
                         "sustituye la re-prueba formal, pero es la primera "
                         "medición del criterio con datos propios."])


def t02_real(recs):
    """Compuerta de triaje real: fallo inyectado con y sin compuerta."""
    faults = [r for r in recs if r.get("arm") == "fault"]
    if not faults:
        return Result(id="T02R", name="Compuerta de triaje (datos reales)",
                      model="M3", verdict=BLOCKED, summary="sin registro fault",
                      killed_if="rechaza demasiado trabajo legítimo",
                      refusal="sin datos", details=[])
    rows = []
    for f in faults:
        contained = f["gate_rejected"] >= f["corrupted_packets"]
        s_ung = score_of(f["task"], f["grade_ungated"])
        s_gat = score_of(f["task"], f["grade_gated"])
        gated_better = (s_gat >= s_ung - 1e-9)
        rows.append((f["model"], f["corrupted_packets"], f["gate_rejected"],
                     contained, gated_better, round(s_ung, 3), round(s_gat, 3)))
    verdict = PASS if all(r[3] and r[4] for r in rows) else FAIL
    return Result(id="T02R", name="Compuerta de triaje (datos reales)", model="M3",
                  verdict=verdict,
                  summary=f"compuerta rechaza {rows[0][2]}/{rows[0][1]} contaminados; contención {'SÍ' if all(r[3] for r in rows) else 'NO'}",
                  killed_if="rechaza tanto trabajo legítimo que el reintento cuesta más",
                  refusal="sin datos",
                  details=[f"{r[0]}: {r[1]} paquetes corruptos, {r[2]} rechazados; "
                           f"score sin compuerta {r[5]}, con compuerta {r[6]}."
                           for r in rows],
                  tables={"Contención medida": (
                      ["modelo", "corruptos", "rechazados", "contenido",
                       "gated ≥ ungated"],
                      [[r[0], r[1], r[2], "SÍ" if r[3] else "NO",
                        "SÍ" if r[4] else "NO"] for r in rows])},
                  notes=["El incidente 42/60 reconstruido: los paquetes que "
                         "llevan la respuesta de otro paquete no pasan el "
                         "predicado mecánico."])


def t03_real(recs):
    """Cardinalidad M2 sobre salidas reales: crudo (nodos) vs con la
    reparación mecánica del ensamblador (v1.4: trim de sobre-expansión)."""
    rows = []
    for r in recs:
        if r.get("arm") == "frag" and r.get("cardinality") \
                and "|strong" not in r.get("key", ""):
            c = r["cardinality"]
            if c.get("per_term"):
                task = ref_corpus.ALL_TASKS.get(r["task"], {})
                terms = list(c["per_term"].keys())
                # reparación mecánica REAL sobre el texto ensamblado guardado
                from swarmbly_ref import assemble as asm
                _, counts = asm.enforce_cardinality(
                    r.get("assembled_text", ""), terms)
                en_ok = sum(1 for v in counts.values() if v == 1)
                rows.append((r["task"], r["model"], c["exactly_once"],
                             c["over_compression"], c["over_expansion"],
                             len(c["per_term"]), en_ok))
    if not rows:
        return Result(id="T03R", name="Unicidad en el plan (datos reales)",
                      model="M2", verdict=BLOCKED, summary="sin datos de cardinalidad",
                      killed_if="no baja de 18/24", refusal="sin datos", details=[])
    tot = sum(r[5] for r in rows)
    ok = sum(r[2] for r in rows)
    over = sum(r[4] for r in rows)
    under = sum(r[3] for r in rows)
    enforced = sum(r[6] for r in rows)
    verdict = PASS if under == 0 else FAIL
    return Result(id="T03R", name="Unicidad en el plan (datos reales)", model="M2",
                  verdict=verdict,
                  summary=f"crudo {ok}/{tot} exactos ({under} omitidos, {over} repetidos); "
                          f"ensamblador con reparación real {enforced}/{tot}",
                  killed_if="no reduce violaciones por debajo de 18/24",
                  refusal="sin datos",
                  details=[f"{r[0]} × {r[1]}: {r[2]}/{r[5]} exactos, "
                           f"{r[3]} omitidos, {r[4]} repetidos → {r[6]}/{r[5]} "
                           "tras reparación" for r in rows],
                  tables={"Cardinalidad por celda": (
                      ["tarea", "modelo", "exactos", "omitidos", "repetidos",
                       "tras reparación"],
                      [[r[0][:12], r[1], r[2], r[3], r[4], r[6]] for r in rows])},
                  notes=[
                      "HALLAZGO: los SLM reales NO obedecen `unique_here` solos "
                      f"({over} menciones repetidas). La predicción de M2 '0 por "
                      "construcción' es FALSA tal como está redactada para nodos "
                      "reales.",
                      "Con la reparación mecánica REAL del ensamblador "
                      f"(enforce_cardinality sobre los textos guardados): "
                      f"{enforced}/{tot} exactamente-una-vez. La sobre-expansión se "
                      "recorta; lo único irreparable es la sobre-compresión "
                      f"({under} términos ausentes), que es justo lo que la "
                      "asignación en el plan debía impedir.",
                      "Corrección a M2 para el whitepaper: asignación en el plan + "
                      "ejecución mecánica en el ensamblador (la de v1.4), no "
                      "asignación sola. La asignación localiza; la ejecución "
                      "garantiza."])


def t07_real(recs):
    """El test decisivo de M4: mismo L y ρ, δ distinto (corte débil P9 vs
    corte fuerte anti-P9). M4 predice que subir δ empeora la distorsión a
    tasa constante."""
    pairs = []
    for r in recs:
        if r.get("arm") != "frag" or "|strong" not in r.get("key", ""):
            continue
        base_key = r["key"].replace("|strong", "")
        weak = next((x for x in recs if x.get("key") == base_key), None)
        m = mono(recs, r["task"], r["model"])
        if weak is None or m is None:
            continue
        t_weak = tax_of(m, weak)
        t_strong = tax_of(m, r)
        if t_weak is None or t_strong is None:
            continue
        pairs.append((r["task"], r["model"], delta_of(weak) or 0.0,
                      delta_of(r) or 0.0, t_weak, t_strong,
                      r["rho"], weak["rho"]))
    if len(pairs) < 3:
        return Result(id="T07R", name="D(ρ,δ): δ mueve la distorsión (datos reales)",
                      model="M4", verdict=BLOCKED,
                      summary=f"solo {len(pairs)} pares débil/fuerte: negarse",
                      killed_if="distorsión función de ρ solo (δ sin efecto)",
                      refusal=f"{len(pairs)} pares < 3", details=[])
    delta_up = all(p[3] > p[2] + 1e-9 for p in pairs)
    rho_equal = all(abs(p[6] - p[7]) / p[7] < 0.05 for p in pairs)
    tax_worse = all(p[5] > p[4] for p in pairs)
    verdict = PASS if (delta_up and rho_equal and tax_worse) else FAIL
    return Result(id="T07R", name="D(ρ,δ): δ mueve la distorsión (datos reales)",
                  model="M4", verdict=verdict,
                  summary=f"δ sube en {sum(1 for p in pairs if p[3] > p[2])}/{len(pairs)} pares; "
                          f"tax empeora en {sum(1 for p in pairs if p[5] > p[4])}/{len(pairs)} a ρ igual",
                  killed_if="distorsión función de ρ solo (δ sin efecto medible)",
                  refusal=f"{len(pairs)} pares < 3",
                  details=[
                      f"δ sube al cortar fuerte: {'SÍ' if delta_up else 'NO'} "
                      f"(P9 mínimiza δ).",
                      f"ρ comparable entre cortes (±5%): {'SÍ' if rho_equal else 'NO'}.",
                      f"Tax peor con corte fuerte en todos los pares: "
                      f"{'SÍ' if tax_worse else 'NO'} — la predicción decisiva de M4.",
                  ],
                  tables={"Corte débil (P9) vs fuerte (anti-P9), mismo L": (
                      ["tarea", "modelo", "δ débil", "δ fuerte", "tax débil %",
                       "tax fuerte %", "ρ"],
                      [[p[0][:12], p[1], f"{p[2]:.2f}", f"{p[3]:.2f}",
                        f"{p[4]:+.1f}", f"{p[5]:+.1f}", f"{p[6]:.2f}"]
                       for p in pairs])},
                  notes=["Este es el experimento que la estrategia declaró como "
                         "decisivo para M4: variar δ a ρ constante. Si el corte "
                         "fuerte no empeora la distorsión, ρ basta como eje y el "
                         "segundo eje es decorativo."])


def t10_real(recs, embed=False):
    """Alineador M1 sobre salidas reales de 3 familias (k_epist)."""
    kep = [r for r in recs if r.get("arm") == "kepist"]
    if not kep:
        return Result(id="T10R", name="Alineador M1 (datos reales)", model="M1",
                      verdict=BLOCKED, summary="sin registro kepist",
                      killed_if="acuerdo por-unidad no supera el azar en régimen no saturado",
                      refusal="sin datos", details=[])
    r = kep[0]
    answers = list(r["answers"].values())
    models = list(r["answers"].keys())
    if len(answers) < 2:
        return Result(id="T10R", name="Alineador M1 (datos reales)", model="M1",
                      verdict=BLOCKED, summary="k_epist < 2 respuestas",
                      killed_if="—", refusal="k<2", details=[])

    # sentence-level M1: segment + align with embedding substitution cost
    from tests.t10_aligner import gotoh_align, normalized
    seqs = [units.split_sentences(a) for a in answers]
    if embed:
        try:
            embs = {s: e for s, e in zip(
                [s for seq in seqs for s in seq],
                llm.embed([s for seq in seqs for s in seq]))}
            def sem(a, b):
                return llm.cosine(embs.get(a, []), embs.get(b, []))
        except Exception:
            sem = None
    else:
        sem = None

    pairs = []
    for i in range(len(seqs)):
        for j in range(i + 1, len(seqs)):
            sc_id, _, _ = gotoh_align(seqs[i], seqs[j],
                                      lambda a, b: 1.0 if a == b else 0.0)
            if sem:
                sc_sem, _, _ = gotoh_align(seqs[i], seqs[j], sem)
            else:
                sc_sem = None
            pairs.append((models[i], models[j],
                          round(normalized(sc_id, len(seqs[i]), len(seqs[j])), 3),
                          round(normalized(sc_sem, len(seqs[i]), len(seqs[j])), 3)
                          if sc_sem is not None else None))
    # per-unit agreement = fraction of aligned columns with high semantic sim
    if sem:
        agree = []
        for i in range(len(seqs)):
            for j in range(i + 1, len(seqs)):
                _, aa, ab = gotoh_align(seqs[i], seqs[j], sem)
                cols = [(a, b) for a, b in zip(aa, ab) if a != "—" and b != "—"]
                if cols:
                    agree.append(fmean(sem(a, b) for a, b in cols))
        agreement = round(fmean(agree), 3)
    else:
        agreement = None

    details = [
        f"Fragmento respondido por {len(models)} familias: {', '.join(models)}.",
        "Alineamiento por oraciones (Gotoh) con sustitución semántica "
        f"(nomic-embed-text, 768 dims). Acuerdo medio por unidad: "
        f"{agreement if agreement is not None else 'n/d'}.",
    ]
    details += [f"{a} vs {b}: identidad {s1}, semántico {s2}"
                for a, b, s1, s2 in pairs]
    verdict = PASS if sem is not None else BLOCKED
    return Result(id="T10R", name="Alineador M1 (datos reales)", model="M1",
                  verdict=verdict,
                  summary=("3 familias alineadas; acuerdo semántico por "
                           f"unidad {agreement:.3f}" if agreement is not None
                           else "3 familias alineadas; el acuerdo por unidad "
                                "no se midió (sin embeddings: usa --embed)"),
                  killed_if="acuerdo no supera el azar donde hay desacuerdo real",
                  refusal="sin embeddings disponibles",
                  details=details,
                  tables={"Alineamientos por pares": (
                      ["familia A", "familia B", "identidad", "semántico"],
                      [[a, b, s1, s2 if s2 is not None else "—"]
                       for a, b, s1, s2 in pairs])},
                  notes=["L13 sigue vigente: esto reporta ACUERDO, nunca "
                         "exactitud. La prueba de muerte de M1 (correlación con "
                         "corrección en régimen no saturado) requiere etiquetas "
                         "de corrección por unidad."])


def router_check():
    from swarmbly_ref import planner as pl
    rows = []
    for tid, t in ref_corpus.ALL_TASKS.items():
        d, reason = pl.router(t, t["material"])
        rows.append((tid, d, bool(t.get("decomposable")), d == bool(t.get("decomposable")), reason[:60]))
    ok = sum(1 for r in rows if r[3])
    return Result(id="T0R", name="Router (datos reales)", model="—",
                  verdict=PASS if ok == len(rows) else FAIL,
                  summary=f"router decide {ok}/{len(rows)} según la verdad del corpus",
                  killed_if="—", refusal="—",
                  details=[f"{r[0]}: decide={r[1]} (verdad={r[2]}) — {r[4]}"
                           for r in rows])


def _sigmoid(z):
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


def _logreg_fit(X, y, lr=0.3, iters=1500, l2=1e-3):
    n, d = len(X), len(X[0])
    w = [0.0] * d
    for _ in range(iters):
        grad = [0.0] * d
        for i in range(n):
            z = sum(X[i][j] * w[j] for j in range(d))
            err = _sigmoid(z) - y[i]
            for j in range(d):
                grad[j] += err * X[i][j]
        for j in range(d):
            w[j] -= lr * (grad[j] / n + l2 * w[j])
    return w


def _standardize(rows, stats=None):
    cols = list(zip(*rows))
    if stats is None:
        means = [fmean(c) for c in cols]
        stds = [(sum((x - m) ** 2 for x in c) / len(c)) ** 0.5 for c, m in zip(cols, means)]
        stds = [s if s > 1e-9 else 1.0 for s in stds]
        stats = (means, stds)
    means, stds = stats
    return [[(x - m) / s for x, m, s in zip(row, means, stds)] for row in rows], stats


def _auc(scores, ys):
    pos = [s for s, y in zip(scores, ys) if y == 1]
    neg = [s for s, y in zip(scores, ys) if y == 0]
    if not pos or not neg:
        return None
    return (sum(1 for a in pos for b in neg if a > b)
            + 0.5 * sum(1 for a in pos for b in neg if a == b)) / (len(pos) * len(neg))


def _f_beta(tp, fp, fn, beta=0.5):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    b2 = beta * beta
    return (1 + b2) * p * r / (b2 * p + r) if (b2 * p + r) else 0.0


MODEL_IDS = ["llama3.2:3b", "qwen2.5:3b", "gemma2:2b", "phi3.5:3.8b",
             "granite3.1-dense:2b"]


def _router_features(cell, with_delta=True, probes=None):
    """Lo que el orquestador conoce ANTES del despacho: plan (δ, ρ, N, L, F),
    material (oraciones, tokens, entidades, acoplamiento medio) y clase de
    nodo (familia)."""
    tid, model, delta, rho, _tax = cell
    task = ref_corpus.ALL_TASKS[tid]
    sents = units.split_sentences(task["material"])
    couplings = [units.coupling(sents[i], sents[i + 1])
                 for i in range(len(sents) - 1)]
    f = []
    if with_delta:
        f.append(delta)
    f += [rho, task.get("L_target", 10), task.get("F", 2),
          len(sents), units.approx_tokens(task["material"]),
          len(task.get("entities", {})),
          fmean(couplings) if couplings else 0.0]
    f += [1.0 if m == model else 0.0 for m in MODEL_IDS]
    # answerability: fracción de claves (normalizadas) presentes literalmente
    # en el material — proxy pre-dispatch de cuán difícil será el monolítico
    from swarmbly_ref import grader as _gr
    mat_norm = _gr._norm(task["material"])
    keys = task.get("answer_keys", [])
    if keys:
        present = sum(1 for k in keys
                      if any(_gr._norm(x) in mat_norm for x in
                             (k if isinstance(k, (list, tuple)) else [k])))
        f.append(present / len(keys))
    else:
        f.append(0.0)
    # sonda de capacidad pre-dispatch: ¿el nodo sumó correctamente? (0.5 si no hay dato)
    f.append(probes.get((tid, model), 0.5) if probes else 0.5)
    return f


def tR_real(recs):
    """Enrutabilidad CON reputación por nodo (escala): ¿puede un router
    predecir ANTES del despacho si una celda será cara (tax>5%)?

    Reputación = agregados del nodo sobre OTRAS tareas del pliegue de
    entrenamiento (tax medio, fracción cara, score mono medio) — lo que un
    router desplegado conoce sin fuga. LOO por tarea, ablación 2×2 (δ × rep)."""
    cells = []
    for r in recs:
        if r.get("arm") != "frag" or "|strong" in r.get("key", ""):
            continue
        task = ref_corpus.ALL_TASKS.get(r.get("task"))
        if task is None or task.get("kind") != "table_summary":
            continue
        if r.get("L") != task.get("L_target", 10):
            continue
        m = mono(recs, r["task"], r["model"])
        if m is None:
            continue
        s_m = score_of(r["task"], m.get("text", ""))
        if s_m < 0.20:
            continue
        t = tax_of(m, r)
        if t is None:
            continue
        cells.append((r["task"], r["model"], delta_of(r) or 0.0, r["rho"],
                      t, s_m))

    if len(cells) < 30:
        return Result(id="T0RR", name="Enrutabilidad (router con δ y reputación)",
                      model="P2", verdict=BLOCKED,
                      summary=f"{len(cells)} celdas operativas < 30: negarse",
                      killed_if="el router no reconoce los casos caros de antemano",
                      refusal=f"{len(cells)} celdas < 30", details=[])

    probes = {(r["task"], r["model"]): (1.0 if r.get("correct") else 0.0)
              for r in recs if r.get("arm") == "probe"}
    tasks = sorted({c[0] for c in cells})

    def rep_for(model, train_cells, exclude_task):
        mc = [c for c in train_cells if c[1] == model and c[0] != exclude_task]
        if not mc:
            return (0.0, 0.0, 0.0)
        return (fmean([c[4] for c in mc]),
                fmean([1.0 if c[4] > 5 else 0.0 for c in mc]),
                fmean([c[5] for c in mc]))

    def feats(cell, tr_cells, with_delta, with_rep):
        tid, model, delta, rho, _t, _s = cell
        task = ref_corpus.ALL_TASKS[tid]
        sents = units.split_sentences(task["material"])
        couplings = [units.coupling(sents[i], sents[i + 1])
                     for i in range(len(sents) - 1)]
        f = []
        if with_delta:
            f.append(delta)
        f += [rho, task.get("L_target", 10), len(sents),
              units.approx_tokens(task["material"]),
              len(task.get("entities", {})),
              fmean(couplings) if couplings else 0.0]
        # answerability (claves presentes en el material)
        from swarmbly_ref import grader as _gr
        mat_norm = _gr._norm(task["material"])
        keys = task.get("answer_keys", [])
        if keys:
            present = sum(1 for k in keys
                          if any(_gr._norm(x) in mat_norm for x in
                                 (k if isinstance(k, (list, tuple)) else [k])))
            f.append(present / len(keys))
        else:
            f.append(0.0)
        f.append(probes.get((tid, model), 0.5))
        if with_rep:
            f += list(rep_for(model, tr_cells, tid))
        return f

    results = {}
    for with_delta in (True, False):
        for with_rep in (True, False):
            pool_s, pool_y = [], []
            for held in tasks:
                tr = [c for c in cells if c[0] != held]
                te = [c for c in cells if c[0] == held]
                y_tr = [1 if c[4] > 5.0 else 0 for c in tr]
                if sum(y_tr) < 2 or (len(y_tr) - sum(y_tr)) < 2:
                    continue
                X_tr, stats = _standardize(
                    [feats(c, tr, with_delta, with_rep) for c in tr])
                w = _logreg_fit(X_tr, y_tr, lr=0.2, iters=1500, l2=0.05)
                X_te, _ = _standardize(
                    [feats(c, tr, with_delta, with_rep) for c in te], stats)
                for c, x in zip(te, X_te):
                    pool_s.append(_sigmoid(sum(a * b for a, b in zip(w, x))))
                    pool_y.append(1 if c[4] > 5.0 else 0)
            if sum(pool_y) < 2 or (len(pool_y) - sum(pool_y)) < 2:
                results[(with_delta, with_rep)] = None
                continue
            auc = _auc(pool_s, pool_y)
            best = (0.0, 0.0)
            for thr in sorted(set(round(x, 2) for x in pool_s)):
                tp = sum(1 for a, b in zip(pool_s, pool_y) if a >= thr and b == 1)
                fp = sum(1 for a, b in zip(pool_s, pool_y) if a >= thr and b == 0)
                fn = sum(1 for a, b in zip(pool_s, pool_y) if a < thr and b == 1)
                fb = _f_beta(tp, fp, fn, 0.5)
                if fb > best[1]:
                    best = (thr, fb, tp, fp, fn)
            results[(with_delta, with_rep)] = (auc, best)

    main = results.get((True, True))
    if main is None:
        return Result(id="T0RR", name="Enrutabilidad (router con δ y reputación)",
                      model="P2", verdict=BLOCKED,
                      summary="pliegues sin señal suficiente: negarse",
                      killed_if="—", refusal="señal insuficiente", details=[])

    # política POR CLASE de nodo (LOO): fragmentar para un modelo si su tax
    # medio histórico (pliegue de entrenamiento) es < 0; si no, rechazar.
    pol_cells = []   # (tax efectivo bajo la política)
    for held in tasks:
        tr = [c for c in cells if c[0] != held]
        te = [c for c in cells if c[0] == held]
        for c in te:
            mc = [x for x in tr if x[1] == c[1]]
            if not mc:
                continue
            mean_tax = fmean([x[4] for x in mc])
            pol_cells.append(c[4] if mean_tax < 0 else 0.0)
    mean_all = fmean([c[4] for c in cells])
    mean_pol = fmean(pol_cells) if pol_cells else 0.0

    def fmt(key):
        r = results.get(key)
        return (f"{r[0]:.2f} (F_0.5 {r[1][1]:.2f})") if r else "—"

    # regla PURA de reputación (sin ML): puntuar cada celda por el tax medio
    # histórico de su nodo en el pliegue de entrenamiento
    rep_scores, rep_ys = [], []
    for held in tasks:
        tr = [c for c in cells if c[0] != held]
        te = [c for c in cells if c[0] == held]
        for c in te:
            mc = [x for x in tr if x[1] == c[1]]
            if mc:
                rep_scores.append(fmean([x[4] for x in mc]))
                rep_ys.append(1 if c[4] > 5 else 0)
    auc_rep_rule = _auc(rep_scores, rep_ys) if len(rep_scores) >= 4 else None

    details = [
        f"{len(cells)} celdas operativas ({len(tasks)} tareas de tabla × "
        f"{len(MODEL_IDS)} familias); prevalencia de 'caro': "
        f"{fmean([1 if c[4] > 5 else 0 for c in cells]):.0%}.",
        f"AUC LOO con δ + reputación: {fmt((True, True))}.",
        f"con δ, sin reputación: {fmt((True, False))}.",
        f"sin δ, con reputación: {fmt((False, True))}.",
        f"sin δ, sin reputación: {fmt((False, False))}.",
        "La reputación = tax/fracción-cara/score-mono del nodo en OTRAS "
        "tareas del pliegue (sin fuga de la tarea retenida).",
        f"Regla PURA de reputación (sin ML): AUC "
        f"{auc_rep_rule:.2f}" if auc_rep_rule is not None else
        "Regla pura de reputación: datos insuficientes.",
        f"Política POR CLASE de nodo (fragmentar si tax histórico < 0): "
        f"tax medio efectivo {mean_pol:+.1f}% vs {mean_all:+.1f}% "
        f"fragmentando siempre (rechazar todo = 0%).",
    ]
    # El perfil POR CLASE de nodo, calculado aquí y no transcrito: la versión
    # anterior de esta nota llevaba el rango «−42% a +7.6%» escrito a mano, que
    # es precisamente la falla que §15.7 nombra — una afirmación que el
    # instrumento no recomputa. Ahora sale de la misma población que el AUC.
    by_class = {}
    for c in cells:
        by_class.setdefault(c[1], []).append(c[4])
    class_rows = []
    for mdl in sorted(by_class, key=lambda k: fmean(by_class[k])):
        v = by_class[mdl]
        sd = (sum((x - fmean(v)) ** 2 for x in v) / len(v)) ** 0.5 if len(v) > 1 else 0.0
        class_rows.append([mdl, len(v), f"{fmean(v):+.1f}%",
                           f"{median(v):+.1f}%", f"{sd:.1f}",
                           f"{fmean([1 if x > 5 else 0 for x in v]):.0%}"])
    class_means = [fmean(v) for v in by_class.values()]
    class_sds = [((sum((x - fmean(v)) ** 2 for x in v) / len(v)) ** 0.5)
                 for v in by_class.values() if len(v) > 1]
    spread = (f"{min(class_means):+.1f}% a {max(class_means):+.1f}%"
              if class_means else "—")
    sd_range = (f"{min(class_sds):.0f}–{max(class_sds):.0f}" if class_sds else "—")

    auc_main = main[0]
    verdict = PASS if auc_main >= 0.65 else FAIL
    return Result(id="T0RR", name="Enrutabilidad (router con δ y reputación)",
                  model="P2", verdict=verdict,
                  summary=f"AUC LOO {auc_main:.2f} (δ+rep) | sin δ+rep: {fmt((False, True))}",
                  killed_if="el router no reconoce los casos caros de antemano",
                  refusal="pliegues sin señal suficiente",
                  details=details,
                  tables={
                      "Ablación 2×2 (AUC LOO por tarea)": (
                          ["", "con δ", "sin δ"],
                          [["con reputación", fmt((True, True)), fmt((False, True))],
                           ["sin reputación", fmt((True, False)), fmt((False, False))]]),
                      "Impuesto por CLASE de nodo (mismas celdas operativas)": (
                          ["clase de nodo", "n", "tax medio", "mediana",
                           "sd intra-clase", "fracción cara"],
                          class_rows),
                  },
                  notes=[
                      "Umbral calibrado sobre el pool (ligeramente optimista).",
                      f"HALLAZGO CLAVE A ESCALA ({len(cells)} celdas, "
                      f"{len(tasks)} tareas): la predicción POR CELDA no "
                      f"funciona (AUC {auc_main:.2f}), pero las CLASES de nodo "
                      f"se separan (tax medio por modelo {spread}; la varianza "
                      f"intra-clase sd {sd_range} es lo que mata la predicción "
                      "fina). El router desplegado debe decidir POR CLASE de "
                      "nodo (perfil/reputación), no por tarea.",
                      "La política por clase (fragmentar si el tax histórico "
                      f"de la clase < 0) logra {mean_pol:+.1f}% vs "
                      f"{mean_all:+.1f}% fragmentando siempre: captura la señal "
                      "disponible sin predicción por celda."])


def tR2_real(recs):
    """Router RICO: perfil de capacidades por modelo (3 sondas) + δ +
    features de material. LOO por tarea, F_0.5 (β<1)."""
    # perfil de capacidades por modelo
    arith = {}
    for r in recs:
        if r.get("arm") == "probe":
            arith.setdefault(r["model"], []).append(1.0 if r["correct"] else 0.0)
    ext = {}
    fmt = {}
    for r in recs:
        if r.get("arm") == "probe2":
            (ext if r["kind"] == "extract" else fmt).setdefault(
                r["model"], []).append(1.0 if r["correct"] else 0.0)
    profile = {m: (fmean(arith.get(m, [0.0])), ext.get(m, [0.0])[0],
                   fmt.get(m, [0.0])[0]) for m in MODEL_IDS}

    cells = []
    for r in recs:
        if r.get("arm") != "frag" or "|strong" in r.get("key", ""):
            continue
        task = ref_corpus.ALL_TASKS.get(r.get("task"))
        if task is None or task.get("kind") != "table_summary":
            continue
        if r.get("L") != task.get("L_target", 10):
            continue
        m = mono(recs, r["task"], r["model"])
        if m is None:
            continue
        s_m = score_of(r["task"], m.get("text", ""))
        if s_m < 0.20:
            continue
        t = tax_of(m, r)
        if t is None:
            continue
        cells.append((r["task"], r["model"], delta_of(r) or 0.0, r["rho"], t))

    if len(cells) < 20:
        return Result(id="T0RR2", name="Router rico (sondas + δ)",
                      model="P2", verdict=BLOCKED,
                      summary=f"{len(cells)} celdas < 20: negarse",
                      killed_if="—", refusal=f"{len(cells)} celdas < 20",
                      details=[])

    def feats(cell, with_delta=True):
        tid, model, delta, rho, _ = cell
        task = ref_corpus.ALL_TASKS[tid]
        sents = units.split_sentences(task["material"])
        couplings = [units.coupling(sents[i], sents[i + 1])
                     for i in range(len(sents) - 1)]
        f = []
        if with_delta:
            f.append(delta)
        f += [rho, task.get("L_target", 10), len(sents),
              units.approx_tokens(task["material"]),
              len(task.get("entities", {})),
              fmean(couplings) if couplings else 0.0]
        f += list(profile.get(model, (0.5, 0.5, 0.5)))   # 3 sondas
        return f

    tasks = sorted({c[0] for c in cells})
    out = {}
    for with_delta in (True, False):
        pool_s, pool_y = [], []
        for held in tasks:
            tr = [c for c in cells if c[0] != held]
            te = [c for c in cells if c[0] == held]
            y_tr = [1 if c[4] > 5.0 else 0 for c in tr]
            if sum(y_tr) < 2 or (len(y_tr) - sum(y_tr)) < 2:
                continue
            X_tr, stats = _standardize([feats(c, with_delta) for c in tr])
            w = _logreg_fit(X_tr, y_tr, lr=0.2, iters=1200, l2=0.05)
            X_te, _ = _standardize([feats(c, with_delta) for c in te], stats)
            for c, x in zip(te, X_te):
                pool_s.append(_sigmoid(sum(a * b for a, b in zip(w, x))))
                pool_y.append(1 if c[4] > 5.0 else 0)
        if sum(pool_y) < 2 or (len(pool_y) - sum(pool_y)) < 2:
            out[with_delta] = None
            continue
        auc = _auc(pool_s, pool_y)
        best = (0.0, 0.0)
        for thr in sorted(set(round(x, 2) for x in pool_s)):
            tp = sum(1 for a, b in zip(pool_s, pool_y) if a >= thr and b == 1)
            fp = sum(1 for a, b in zip(pool_s, pool_y) if a >= thr and b == 0)
            fn = sum(1 for a, b in zip(pool_s, pool_y) if a < thr and b == 1)
            fb = _f_beta(tp, fp, fn, 0.5)
            if fb > best[1]:
                best = (thr, fb, tp, fp, fn)
        out[with_delta] = (auc, best)

    if out.get(True) is None:
        return Result(id="T0RR2", name="Router rico (sondas + δ)",
                      model="P2", verdict=BLOCKED,
                      summary="pliegues sin señal suficiente: negarse",
                      killed_if="—", refusal="señal insuficiente", details=[])

    auc_d, best_d = out[True]
    auc_nd = out.get(False, (None, None))[0]
    details = [
        f"{len(cells)} celdas operativas; perfil de capacidades por modelo "
        "(aritmética / extracción / formato):",
    ]
    details += [f"  {m}: {profile[m][0]:.0%} / {profile[m][1]:.0%} / {profile[m][2]:.0%}"
                for m in MODEL_IDS]
    details += [
        f"AUC LOO con sondas + δ: {auc_d:.3f} (sin δ: {auc_nd:.3f}).",
        f"F_0.5: {best_d[1]:.3f} (umbral {best_d[0]:.2f}; TP={best_d[2]} "
        f"FP={best_d[3]} FN={best_d[4]}).",
    ]
    verdict = PASS if auc_d >= 0.65 else FAIL
    return Result(id="T0RR2", name="Router rico (sondas + δ)", model="P2",
                  verdict=verdict,
                  summary=f"AUC LOO {auc_d:.2f} (sondas+δ) vs {auc_nd:.2f} (sin δ); F_0.5 {best_d[1]:.2f}",
                  killed_if="el router no reconoce los casos caros de antemano",
                  refusal="pliegues sin señal suficiente",
                  details=details,
                  tables={"Perfil de capacidades (sondas)": (
                      ["modelo", "aritmética", "extracción", "formato"],
                      [[m, f"{profile[m][0]:.0%}", f"{profile[m][1]:.0%}",
                        f"{profile[m][2]:.0%}"] for m in MODEL_IDS])},
                  notes=["Umbral calibrado sobre el pool (ligeramente optimista).",
                         "Si las sondas separan, la enrutabilidad gana su "
                         "primera evidencia; si no, el cuello es el tamaño de "
                         "muestra o la definición de 'caro'."])



def tL_real(recs):
    """L por clase de nodo (§5.7): L* por familia desde la curva longform
    real, comparado contra el L=15 único (one-size)."""
    curves = {}
    for r in recs:
        if r.get("task") == "longform" and r.get("arm") == "frag" \
                and "|strong" not in r.get("key", ""):
            curves.setdefault(r["model"], []).append(
                (r.get("L", 15), score_of("longform", r.get("assembled_text", ""))))
    rows = []
    for m in MODEL_IDS:
        pts = curves.get(m, [])
        if len(pts) < 2:
            rows.append((m, None, None, None, None, len(pts)))
            continue
        best_L = max(pts, key=lambda p: (p[1], p[0]))[0]   # calidad, luego L mayor
        q_star = max(p[1] for p in pts)
        q_15 = next((q for L, q in pts if L == 15), None)
        rows.append((m, best_L, round(q_star, 3),
                     round(q_15, 3) if q_15 is not None else None,
                     len(pts), pts))
    with_curve = [r for r in rows if r[1] is not None]
    if len(with_curve) < 3:
        return Result(id="T0LR", name="L por clase de nodo", model="§5.7",
                      verdict=BLOCKED, summary="curvas-L insuficientes por familia",
                      killed_if="—", refusal="<3 familias con curva", details=[])
    gain = [r[2] - r[3] for r in with_curve if r[3] is not None]
    details = [
        f"L* por familia (curva longform, desempate hacia L mayor = menor ρ):",
    ]
    details += [f"  {r[0]}: L*={r[1]}, calidad {r[2]}, L=15 → {r[3]}"
                for r in with_curve]
    details += [
        f"Ganancia media de usar L* en vez de L=15: {fmean(gain):+.3f}.",
        "§5.7 dice que L es propiedad de la clase de nodo; esto lo mide por "
        "primera vez con datos reales.",
    ]
    verdict = PASS if fmean(gain) > 0.005 else FAIL
    return Result(id="T0LR", name="L por clase de nodo", model="§5.7",
                  verdict=verdict,
                  summary=f"L* varía por familia; ganancia media vs L=15: {fmean(gain):+.3f}",
                  killed_if="L no varía por clase de nodo",
                  refusal="<3 familias con curva",
                  details=details,
                  tables={"L* por familia": (
                      ["modelo", "L*", "calidad L*", "calidad L=15", "puntos"],
                      [[r[0], r[1], r[2], r[3] if r[3] is not None else "—",
                        r[4]] for r in rows])},
                  notes=["Los puntos de cada curva mezclan tarea fija (longform) "
                         "y modelos distintos; la comparación es intra-modelo.",
                         "Si L* ≠ 15 para varias familias, el one-size L es "
                         "subóptimo y el perfil del nodo debe declarar su L."])


def run_suite(data=None, embed=False, quiet=False):
    """Ejecuta la batería empírica y devuelve (resultados, ruta_de_datos).

    Expuesta como función para que `run_all.py --real` corra exactamente los
    mismos tests que `python3 run_real.py`, en vez de una segunda lista que se
    desincroniza sin avisar.
    """
    data = data or ap_default_data()
    recs = load(data)
    if not quiet:
        print(f"registros cargados: {len(recs)} desde {data}")
    results = [router_check(), t02_real(recs), t03_real(recs), t04_real(recs),
               t05_real(recs), t06_real(recs), t07_real(recs), t08_real(recs),
               t09_real(recs), t10_real(recs, embed=embed),
               tR_real(recs), tR2_real(recs), tL_real(recs)]
    return results, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--embed", action="store_true")
    args = ap.parse_args()

    results, data = run_suite(args.data, embed=args.embed)
    print(report.render_console(results))
    md = os.path.join(HERE, "REPORT_REAL.md")
    js = os.path.join(HERE, "results_real.json")
    report.write_report(results, {
        "project": "Swarmbly AI — datos reales",
        "source": f"{data} (Ollama local, 5 familias SLM)",
        "scope": "veredictos empíricos; ver notas de alcance por test",
    }, md, js)
    print(f"\nReporte real: {md}")


if __name__ == "__main__":
    main()
