"""Análisis derivado de F-forget (sin modelos), conforme a la Enmienda 6 (c).

1. Conducta SIN las celdas rechazadas por S1 (la wiki completa no tenía
   claims de la fuente borrada): así lo pide el preregistro; el resumen que
   escribió ``bench_forget`` las incluía. Bootstrap agrupado por pregunta.
2. Equivalencia con una digestión independiente (S4 bis, posterior a los
   datos y declarada como tal): W_forget se compara también con la wiki
   de R13 digerida horas antes sin la fuente. Requiere las wikis en caché
   (no versionadas); si no están, se conserva el valor guardado.

    python -m lce_validation.forget_analysis
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

FORGET = ROOT / "results" / "bench_forget"
R13_CACHE = ROOT / "results" / "bench_r13" / "wikis_cache"
SRC = "teach/knowledge/borrada.md"


def _boot(x, B: int = 10_000, seed: int = 20261005) -> list[float]:
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    m = [a[rng.integers(0, len(a), len(a))].mean() for _ in range(B)]
    return [round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)]


def behaviour(d: dict) -> dict:
    refused = {(c["user"], c["digester"]) for c in d["structural"] if c["refused"]}
    rows = [b for b in d["behaviour"] if (b["user"], b["digester"]) not in refused]
    rate = {c: round(float(np.mean([b["abstained"] for b in rows if b["cond"] == c])), 3)
            for c in ("full", "forget", "never")}
    by_q: dict = defaultdict(lambda: defaultdict(list))
    for b in rows:
        by_q[(b["user"], b["q"]["q"])][b["cond"]].append(float(b["abstained"]))
    ff = [np.mean(v["forget"]) - np.mean(v["full"]) for v in by_q.values()]
    fn = [np.mean(v["forget"]) - np.mean(v["never"]) for v in by_q.values()]
    key = lambda b: (b["user"], b["digester"], b["responder"], b["q"]["q"])  # noqa: E731
    fa = {key(b): b["answer"] for b in rows if b["cond"] == "forget"}
    na = {key(b): b["answer"] for b in rows if b["cond"] == "never"}
    return {"refused_cells": sorted("|".join(r) for r in refused), "cells_used": len({(b["user"], b["digester"]) for b in rows}),
            "abstention": rate,
            "forget_minus_full": round(float(np.mean(ff)), 3), "forget_minus_full_ci95": _boot(ff),
            "forget_minus_never": round(float(np.mean(fn)), 3), "forget_minus_never_ci95": _boot(fn),
            "n_questions": len(by_q),
            "identical_answers_forget_never": round(float(np.mean([fa[k] == na[k] for k in fa])), 3)}


def independent_equivalence() -> dict | None:
    cache = FORGET / "wikis_cache"
    if not (cache.exists() and R13_CACHE.exists()):
        return None
    from swarmbly_lce.policy import LearningPolicy
    from swarmbly_lce.wiki import Wiki
    ids = lambda p: {c["claim_id"] for c in json.loads(p.read_text(encoding="utf-8"))["claims"]}  # noqa: E731
    out = {"forget_eq_r13": 0, "never_eq_r13": 0, "forget_eq_never": 0, "wikis": 0}
    from lce_validation.fsnames import cache_file, split_cache_name
    for f in sorted(cache.glob("*__full.json")):
        uid, dg = split_cache_name(f.name, "__full.json")
        r13 = cache_file(R13_CACHE, uid, dg, "_wiki.json")
        if not r13.exists():
            continue
        w = Wiki.load(f, LearningPolicy())
        w.forget_source(SRC)
        fg, nv, rr = set(w.claims), ids(cache_file(cache, uid, dg, "__never.json")), ids(r13)
        out["wikis"] += 1
        out["forget_eq_r13"] += fg == rr
        out["never_eq_r13"] += nv == rr
        out["forget_eq_never"] += fg == nv
    return out


def analyse(d: dict) -> dict:
    return {"behaviour_prereg": behaviour(d)}


def main() -> int:
    d = json.loads((FORGET / "results.json").read_text(encoding="utf-8"))
    a = analyse(d)
    eq = independent_equivalence()
    prev = FORGET / "analysis.json"
    if eq is not None:
        a["independent_equivalence"] = eq
        a["independent_equivalence_note"] = ("posterior a los datos; requiere las wikis en caché "
                                             "(no versionadas): W_forget frente a la wiki de R13 "
                                             "digerida sin la fuente en otra corrida")
    elif prev.exists():
        old = json.loads(prev.read_text(encoding="utf-8"))
        for k in ("independent_equivalence", "independent_equivalence_note"):
            if k in old:
                a[k] = old[k]
    prev.write_text(json.dumps(a, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(a, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
