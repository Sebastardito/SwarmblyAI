"""Análisis derivado de R13 (sin modelos): las cifras que citan los documentos.

Todo sale de ``results/bench_r13/results.json`` con la misma semilla y el
mismo bootstrap agrupado por pregunta; ``doc_figures`` y la prueba de anclaje
exigen que cada cifra citada en los documentos coincida con lo que esto
calcula. La cobertura de la respuesta en el contexto necesita las wikis en
caché (no versionadas) y se guarda aparte, marcada como tal.

    python -m lce_validation.r13_analysis
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

R13 = ROOT / "results" / "bench_r13_confirm"
if not (R13 / "results.json").exists():
    R13 = ROOT / "results" / "bench_r13"
DIGESTERS = ["qwen2.5:3b", "llama3.2:3b", "gemma2:2b"]
TYPES = ["simple", "cross", "updated", "contradiction", "deleted", "unanswerable"]
ANSWERABLE = ("simple", "cross", "updated", "contradiction")
# N1 (Enmienda 6 b): claves «simples» de la v1 que actualizacion.md declara superadas.
STALE = {
    ("andres", "¿Cuál fue la razón de riesgos de tu resultado principal y su intervalo de confianza?"),
    ("carmen", "¿Qué fondo superó el umbral de materialidad este trimestre y cuál fue su variación?"),
    ("mara", "Según tu criterio de abandono, ¿bajo qué valor de F_ST declararías muerta la "
             "hipótesis de aislamiento y cuál fue el valor medido entre Barú y Fábrega?"),
}


def _boot(x, B: int = 10_000, seed: int = 20261005) -> list[float]:
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    m = [a[rng.integers(0, len(a), len(a))].mean() for _ in range(B)]
    return [round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)]


def _per_question(cells, exclude=frozenset()):
    pq: dict = defaultdict(lambda: defaultdict(list))
    typ = {}
    for c in cells:
        k = (c["user"], c["q"]["q"])
        if k in exclude:
            continue
        typ[k] = c["q"].get("type", "simple")
        tag = c["arm"] if c["arm"] != "A3" else "A3"
        pq[k][tag].append(float(c["ok"]))
        if c["arm"] == "A3":
            pq[k]["A3|" + c["digester"]].append(float(c["ok"]))
    return pq, typ


def _diff(pq, typ, a, b, types=None):
    ks = [k for k in pq if a in pq[k] and b in pq[k] and (types is None or typ[k] in types)]
    x = [np.mean(pq[k][a]) - np.mean(pq[k][b]) for k in ks]
    return {"mean": round(float(np.mean(x)), 3), "ci95": _boot(x), "n_questions": len(ks)}


def analyse(d: dict, base: Path | None = None) -> dict:
    cells = d["cells"]
    pq, typ = _per_question(cells)
    out: dict = {"source_sha_note": f"derivado de results/{(base or R13).name}/results.json"}
    out["a3_minus_a2"] = _diff(pq, typ, "A3", "A2")
    out["a3_minus_a2_by_digester"] = {g: _diff(pq, typ, "A3|" + g, "A2") for g in DIGESTERS}
    out["a3_minus_a2_by_type"] = {t: _diff(pq, typ, "A3", "A2", (t,)) for t in TYPES}
    out["a3_minus_a0_answerable"] = _diff(pq, typ, "A3", "A0", ANSWERABLE)
    out["a2_minus_a0_answerable"] = _diff(pq, typ, "A2", "A0", ANSWERABLE)
    # E5: A4 contra la diagonal de A3 del mismo digestor
    a3d, a4 = {}, {}
    for c in cells:
        k = (c["user"], c["q"]["q"], c["responder"])
        if c["arm"] == "A3" and c["digester"] == c["responder"]:
            a3d[k] = float(c["ok"])
        if c["arm"] == "A4":
            a4[k] = float(c["ok"])
    out["a4_minus_a3_diagonal"] = {g: round(float(np.mean([a4[k] - a3d[k] for k in a4 if k[2] == g])), 3)
                                   for g in DIGESTERS}
    # N2: abstención junto con la exactitud en preguntas con respuesta, por brazo/digestor
    joint = {}
    for tag in ["A0", "A1", "A2", "A3|qwen2.5:3b", "A3|llama3.2:3b", "A3|gemma2:2b"]:
        def rate(types):
            v = [np.mean(pq[k][tag]) for k in pq if typ[k] in types and tag in pq[k]]
            return round(float(np.mean(v)), 3)
        joint[tag] = {"answerable_accuracy": rate(ANSWERABLE),
                      "abstention_deleted": rate(("deleted",)),
                      "abstention_unanswerable": rate(("unanswerable",))}
    out["abstention_with_accuracy"] = joint
    # N1: sensibilidad sin las tres claves superadas
    pq2, typ2 = _per_question(cells, STALE)
    out["n1_a3_minus_a2_without_stale"] = _diff(pq2, typ2, "A3", "A2")
    out["n1_stale_questions"] = len(STALE)
    out["f1a_n1"] = f1a_sensitivity()
    out["decision_rules"] = decision_rules(out, cells)
    acp = (base or R13) / "anchored_counts.json"
    if acp.exists():
        out["decision_rules"]["r13_h3"] = h3_from_counts(
            out["decision_rules"]["r13_h3"], json.loads(acp.read_text(encoding="utf-8")))
    return out


def decision_rules(out: dict, cells: list) -> dict:
    """Reglas de decisión del preregistro 2.7 sobre las celdas de la corrida."""
    total = out["a3_minus_a2"]
    upd = out["a3_minus_a2_by_type"].get("updated")
    dele = out["a3_minus_a2_by_type"].get("deleted")
    def _h(name, d):
        if d is None:
            return {"hypothesis": name, "verdict": "no computable"}
        mean, lo = d["mean"], d["ci95"][0]
        if lo > 0:
            v = "se sostiene"
        elif mean <= 0:
            v = "muere"
        else:
            v = "no concluyente"
        return {"hypothesis": name, "mean": mean, "ci95": d["ci95"],
                "verdict": v}
    r1 = _h("R13-H1: la wiki supera al RAG crudo", total)
    r2_hold = (upd and dele and upd["ci95"][0] > 0 and dele["ci95"][0] > 0)
    r2_die = (upd and dele and upd["mean"] <= 0 and dele["mean"] <= 0)
    r2 = {"hypothesis": "R13-H2: la wiki gana en actualización y olvido",
          "updated": upd, "deleted": dele,
          "verdict": "se sostiene" if r2_hold else
                     ("muere" if r2_die else "no concluyente")}
    # R13-H3: compuerta del digestor — utilidad por (usuario, digestor)
    # frente al piso de claims ancladas (>= 5)
    from collections import defaultdict
    by_cell: dict = defaultdict(list)
    for c in cells:
        if c["arm"] == "A3":
            by_cell[(c["user"], c["digester"])].append(float(c["ok"]))
    a2 = {(c["user"], c["q"]["q"], c["responder"]): float(c["ok"])
          for c in cells if c["arm"] == "A2"}
    rows = []
    for (uid, dg), oks in sorted(by_cell.items()):
        base = [float(c["ok"]) for c in cells if c["arm"] == "A2" and c["user"] == uid]
        rows.append({"user": uid, "digester": dg,
                     "mean_ok": round(float(np.mean(oks)), 3),
                     "vs_a2": round(float(np.mean(oks)) - float(np.mean(base)), 3)})
    r3 = {"hypothesis": "R13-H3: un piso de claims ancladas explica la utilidad",
          "rows": rows,
          "verdict": "pendiente de los conteos anclados por celda (wikis_cache)"}
    # Condición de muerte global (prereg 2.7): «RAG ≥ wiki en el total Y la wiki
    # no gana en 3 y 5». La redacción admite dos lecturas; se reportan las dos.
    # Además (Enmienda 6 b, N2): el tipo 5 no mide olvido (ningún brazo vio la
    # fuente borrada) y su abstención premia al brazo que recupera menos.
    win3 = bool(upd and upd["ci95"][0] > 0)
    win5 = bool(dele and dele["ci95"][0] > 0)
    rag_ge = total["mean"] <= 0
    return {"r13_h1": r1, "r13_h2": r2, "r13_h3": r3,
            "hc1_death_global": {
                "reading_wins_neither": "dispara" if (rag_ge and not win3 and not win5) else "no dispara",
                "reading_not_both": "dispara" if (rag_ge and not (win3 and win5)) else "no dispara",
                "a0_abstention_deleted": out.get("abstention_with_accuracy", {}).get("A0", {}).get("abstention_deleted"),
                "note": "con la lectura literal más estricta no dispara solo por el tipo 5, que la Enmienda 6 (b) declara inválido como medida de olvido"}}


def _avg_ranks(v: list) -> np.ndarray:
    """Rangos con empates promediados (Spearman estándar). argsort(argsort())
    rompe los empates según el algoritmo de ordenación de numpy, y el
    resultado cambiaba entre versiones y plataformas."""
    a = np.asarray(v, dtype=float)
    order = np.argsort(a, kind="stable")
    ranks = np.empty(len(a))
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[order[j + 1]] == a[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks


def h3_from_counts(r3: dict, ac: dict) -> dict:
    """R13-H3 (prereg 2.7): ¿el piso de 5 claims ancladas explica la utilidad?
    Se sostiene si la utilidad cae bajo el piso; muere si no hay relación
    monótona; si el piso nunca se alcanza, la compuerta se retira como regla."""
    n = {(r["user"], r["digester"]): r["anchored"] for r in ac["rows"]}
    pts = [(n[(r["user"], r["digester"])], r["mean_ok"]) for r in r3["rows"]
           if (r["user"], r["digester"]) in n and r["user"] != "lme"]
    below = [p for p in pts if p[0] < 5]
    x = _avg_ranks([p[0] for p in pts]); y = _avg_ranks([p[1] for p in pts])
    rho = float(np.corrcoef(x, y)[0, 1]) if len(pts) > 2 else None
    r3 = dict(r3)
    r3.update({"min_anchored": min(p[0] for p in pts), "max_anchored": max(p[0] for p in pts),
               "cells_below_floor": len(below),
               "spearman_anchored_vs_accuracy_own_users": round(rho, 3) if rho is not None else None,
               "verdict": "la compuerta se retira como regla (el piso de 5 nunca se alcanza)"
               if not below else r3.get("verdict")})
    return r3


def f1a_sensitivity() -> dict:
    """F1a con y sin las tres claves superadas (N1), bootstrap por pregunta."""
    h = json.loads((ROOT / "results" / "bench_hc1_scale" / "results.json").read_text(encoding="utf-8"))
    res = {}
    for name, excl in (("all", frozenset()), ("without_stale", STALE)):
        by: dict = defaultdict(list)
        for c in h["cells"]:
            if (c["user"], c["q"]) not in excl:
                by[(c["user"], c["q"])].append(c["with"] - c["without"])
        g = [float(np.mean(v)) for v in by.values()]
        res[name] = {"mean": round(float(np.mean(g)), 3), "ci95": _boot(g), "n_questions": len(g)}
    return res


def coverage(d: dict) -> dict | None:
    """Fracción de preguntas CON RESPUESTA de la corrida cuya clave está en el
    contexto que recibe cada brazo (requiere las wikis de la corrida)."""
    cache = R13 / "wikis_cache"
    if not cache.exists():
        return None
    from swarmbly_lce.policy import LearningPolicy
    from swarmbly_lce.wiki import Wiki
    from lce_validation import run_r13 as R
    from lce_validation.bench_forget import source_dates
    asked: dict = {}
    for c in d["cells"]:
        q = c["q"]
        if q.get("type", "simple") in ANSWERABLE:
            asked[(c["user"], q["q"])] = q
    res: dict = defaultdict(list)
    for uid in sorted({u for u, _ in asked}):
        base = R.USERS_DIR / uid
        doc = "\n\n".join(p.read_text(encoding="utf-8") for p in sorted((base / "teach").rglob("*.md"))
                           if p.name != "borrada.md")
        dates = source_dates(base)
        pol = base / "policy.json"
        from lce_validation.fsnames import cache_file
        wikis = {g: Wiki.load(cache_file(cache, uid, g, "_wiki.json"), LearningPolicy.load(pol))
                 for g in DIGESTERS if cache_file(cache, uid, g, "_wiki.json").exists()}
        for (u, _), q in asked.items():
            if u != uid:
                continue
            gold = [R._norm(x) for x in q["gold"]]
            has = lambda ctx: all(g in R._norm(ctx) for g in gold)  # noqa: E731
            res["A2"].append(has(R.rag_context(doc, q["q"])))
            for g, w in wikis.items():
                res["A3|" + g].append(has(R.wiki_context(w, q["q"], dates)))
    return {k: round(float(np.mean(v)), 3) for k, v in res.items()} | {"n_questions": len(res["A2"])}


def anchored_counts() -> dict | None:
    """Claims ancladas por (usuario, digestor) en las wikis de la corrida."""
    cache = R13 / "wikis_cache"
    if not cache.exists():
        return None
    rows = []
    for f in sorted(cache.glob("*_wiki.json")):
        from lce_validation.fsnames import split_cache_name
        uid, dg = split_cache_name(f.name, "_wiki.json")
        claims = json.loads(f.read_text(encoding="utf-8"))["claims"]
        anch = sum(1 for c in claims if c.get("anchors"))
        rows.append({"user": uid, "digester": dg, "anchored": anch, "claims": len(claims)})
    return {"rows": rows}


def main(argv: list[str] | None = None) -> int:
    global R13
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None, help="bench_r13 (piloto) o bench_r13_confirm")
    args = ap.parse_args(argv)
    if args.dir:
        R13 = ROOT / "results" / args.dir
    d = json.loads((R13 / "results.json").read_text(encoding="utf-8"))
    ac = anchored_counts()
    if ac is not None:
        (R13 / "anchored_counts.json").write_text(json.dumps(ac, ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8")
    a = analyse(d, base=R13)
    cov = coverage(d)
    if cov is not None:
        a["gold_in_context_answerable"] = cov
        a["gold_in_context_note"] = f"preguntas con respuesta de la corrida; requiere {R13.name}/wikis_cache"
    else:
        prev = R13 / "analysis.json"
        if prev.exists():
            old = json.loads(prev.read_text(encoding="utf-8"))
            for k in ("gold_in_context_answerable", "gold_in_context_note"):
                if k in old:
                    a[k] = old[k]
    (R13 / "analysis.json").write_text(json.dumps(a, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: a[k] for k in ("a3_minus_a2", "decision_rules")}, ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
