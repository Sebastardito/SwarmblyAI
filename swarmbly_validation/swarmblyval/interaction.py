"""H-INT: la fuerza del nodo predice el impuesto de fragmentación.

Implementa el diseño de `PREREGISTRATION_2026-09-25_interaction_ES.md`, escrito antes
de correr esto. Dos cosas lo separan del análisis exploratorio que lo motivó:

1. **El predictor es leave-one-out.** `impuesto = 1 − frag/mono` lleva `mono` en
   el denominador, así que correlacionarlo con el `mono` de la MISMA celda
   produce asociación por construcción. La fuerza del nodo se estima aquí con
   los scores monolíticos de ese modelo en las demás tareas, de modo que
   predictor y resultado vienen de datos disjuntos.

2. **No hay umbral libre.** La prueba primaria es continua. La tabla
   estratificada es descriptiva, su punto de corte es la mediana del corpus
   (mecánica, no elegida) y se acompaña de un barrido.
"""

import json
import statistics as st

from .stats import clustered_bootstrap, spearman, variance_refusal

__all__ = ["load_cells", "loo_strength", "h_int", "stratified", "threshold_sweep"]

#: Piso de baseline del proyecto: por debajo no hay nada que comparar (§15.7).
BASELINE_FLOOR = 0.20
#: Celdas por encima de esto se consideran en techo (control §4.3).
CEILING = 0.90


def _words(rec):
    return len(str(rec.get("assembled_text") or rec.get("text") or "").split())


def load_cells(path, exclude_strong=True):
    """Celdas comparables (tarea, modelo) con su impuesto y su razón de longitud.

    ``exclude_strong`` descarta los cortes anti-P9, como hace T09R: el criterio
    se mide sobre el corte operativo, no sobre uno diseñado para ser malo.
    """
    recs = [json.loads(line) for line in open(path, encoding="utf-8")]
    mono = {(r["task"], r["model"]): r for r in recs if r.get("arm") == "mono"}
    cells = []
    for r in recs:
        if r.get("arm") != "frag":
            continue
        if exclude_strong and "|strong" in r.get("key", ""):
            continue
        m = mono.get((r["task"], r["model"]))
        if m is None:
            continue
        ms = m["grade"]["score"]
        if ms is None or ms < BASELINE_FLOOR:
            continue
        fs = r["grade"]["score"]
        cells.append({
            "task": r["task"], "model": r["model"],
            "mono": ms, "frag": fs,
            "tax": (ms - fs) / ms * 100.0,
            "words_mono": _words(m), "words_frag": _words(r),
            "ratio": _words(r) / max(1, _words(m)),
            "L": r.get("L"),
        })
    # fuerza del modelo en cada tarea, para el LOO
    by_model_task = {}
    for (task, model), m in mono.items():
        s = m["grade"]["score"]
        if s is not None and s >= BASELINE_FLOOR:
            by_model_task.setdefault(model, {})[task] = s
    return cells, by_model_task


def loo_strength(model, task, by_model_task):
    """Score monolítico medio del modelo en TODAS LAS DEMÁS tareas.

    Devuelve None si el modelo no tiene otra tarea: sin datos disjuntos no hay
    predictor válido y la celda se descarta en lugar de rellenarse.
    """
    scores = by_model_task.get(model, {})
    others = [s for t, s in scores.items() if t != task]
    if not others:
        return None
    return st.fmean(others)


def _perm_p_clustered(xs, ys, groups, n_perm=50000, seed=11):
    """p por permutación de Spearman, permutando DENTRO de la estructura de grupo.

    Las celdas de una misma tarea no son independientes, así que la hipótesis
    nula se construye permutando las etiquetas de grupo completas en vez de las
    observaciones sueltas.
    """
    import random
    rho = spearman(xs, ys)
    rng = random.Random(seed)
    idx_by_group = {}
    for i, g in enumerate(groups):
        idx_by_group.setdefault(g, []).append(i)
    keys = list(idx_by_group)
    hits = 0
    for _ in range(n_perm):
        shuffled = keys[:]
        rng.shuffle(shuffled)
        permuted = list(ys)
        for src, dst in zip(keys, shuffled):
            a, b = idx_by_group[src], idx_by_group[dst]
            n = min(len(a), len(b))
            for i in range(n):
                permuted[a[i]] = ys[b[i]]
        if abs(spearman(xs, permuted)) >= abs(rho) - 1e-12:
            hits += 1
    return rho, (hits + 1) / (n_perm + 1)


def h_int(cells, by_model_task, length_control=None, exclude_ceiling=False,
          n_perm=50000, seed=11):
    """Prueba primaria: fuerza LOO del nodo vs impuesto.

    ``length_control``: si es un número, se queda con celdas de ``ratio`` menor
    o igual. ``exclude_ceiling``: descarta celdas con mono >= CEILING.
    Devuelve un dict con el resultado o con la razón de rechazo.
    """
    sel = []
    for c in cells:
        if length_control is not None and c["ratio"] > length_control:
            continue
        if exclude_ceiling and c["mono"] >= CEILING:
            continue
        s = loo_strength(c["model"], c["task"], by_model_task)
        if s is None:
            continue
        sel.append((s, c["tax"], c["task"], c))

    n_groups = len({t for _s, _t, t, _c in sel})
    if len(sel) < 8:
        return {"refused": True, "why": f"{len(sel)} celdas < 8: sin potencia",
                "n": len(sel)}
    ref, why = variance_refusal([s for s, _t, _g, _c in sel], "fuerza LOO")
    if ref:
        return {"refused": True, "why": why, "n": len(sel)}

    xs = [s for s, _t, _g, _c in sel]
    ys = [t for _s, t, _g, _c in sel]
    gs = [g for _s, _t, g, _c in sel]
    rho, p = _perm_p_clustered(xs, ys, gs, n_perm=n_perm, seed=seed)
    return {"refused": False, "rho": rho, "p": p, "n": len(sel),
            "n_groups": n_groups, "cells": [c for _s, _t, _g, c in sel]}


def stratified(cells, threshold=None):
    """Tabla descriptiva. El umbral por defecto es la MEDIANA de los monolíticos."""
    monos = sorted({(c["task"], c["model"]): c["mono"] for c in cells}.values())
    if threshold is None:
        threshold = st.median(monos)
    out = {"threshold": threshold, "rows": []}
    for label, sel in (
        ("débil · toda longitud", [c for c in cells if c["mono"] < threshold]),
        ("débil · frag no más largo",
         [c for c in cells if c["mono"] < threshold and c["ratio"] <= 1.0]),
        ("fuerte · toda longitud", [c for c in cells if c["mono"] >= threshold]),
        ("fuerte · frag no más largo",
         [c for c in cells if c["mono"] >= threshold and c["ratio"] <= 1.0]),
    ):
        if len(sel) < 8:
            out["rows"].append((label, len(sel), None, None, None, None))
            continue
        mean, lo, hi, _se = clustered_bootstrap([c["tax"] for c in sel],
                                                [c["task"] for c in sel])
        out["rows"].append((label, len(sel), mean, lo, hi,
                            st.median([c["ratio"] for c in sel])))
    return out


def threshold_sweep(cells, lo_q=0.25, hi_q=0.75, steps=11):
    """Barrido del punto de corte sobre el rango intercuartílico (§4.4).

    Si el signo de un estrato cambia dentro del rango, no hay dos regímenes y la
    tabla estratificada no debe publicarse — es una condición de muerte
    declarada en el preregistro.
    """
    monos = sorted(c["mono"] for c in cells)
    qs = st.quantiles(monos, n=4)
    lo, hi = qs[0], qs[2]
    out = []
    for i in range(steps):
        thr = lo + (hi - lo) * i / (steps - 1)
        weak = [c["tax"] for c in cells if c["mono"] < thr]
        strong = [c["tax"] for c in cells if c["mono"] >= thr]
        out.append((round(thr, 3), len(weak), len(strong),
                    st.fmean(weak) if len(weak) >= 5 else None,
                    st.fmean(strong) if len(strong) >= 5 else None))
    return out
