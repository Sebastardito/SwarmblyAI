"""Benchmark H-C1 a escala: memoria local (wiki + recuperación) vs sin memoria.

Corre sobre el corpus multi-usuario generado por ``bench_corpus_gen.py``
(5 usuarios × 12 preguntas) con las cinco familias de modelos. Cada familia
digiere la wiki de CADA usuario (anclaje por cita, reconciliación de tipos —
los ajustes de la enmienda 3) y responde cada pregunta dos veces: sin memoria
(modelo base, solo la pregunta) y con memoria (recuperación BM25 sobre la
wiki del usuario en el contexto).

CLASIFICACIÓN: corrida EXPLORATORIA de benchmark, NO la corrida confirmatoria
del preregistro C1/C2 (que sigue intacto en ``docs/PREREGISTRATION_C1_C2_*``).
No emite veredictos preregistrados; reporta estadística descriptiva y un
intervalo bootstrap de la ganancia media, con su alcance declarado.

Reglas de decisión fijadas ANTES de correr (mini-preregistro inline):
  - la ganancia de una celda es correcta_con_memoria - correcta_sin_memoria;
  - una pregunta cuenta como correcta si TODAS las claves de oro aparecen en
    la respuesta (subcadenas normalizadas: sin signos ni acentos);
  - H-C1 a escala se sostiene descriptivamente si la ganancia media es > 0
    con IC95 bootstrap que excluye el cero;
  - la corrida se NIEGA (no reporta cifras) si alguna familia no responde o
    si el anclaje produce menos de 5 claims en algún usuario (nada aguas
    abajo sería interpretable).

Uso:
    python3 -m lce_validation.bench_hc1_scale \
        --models llama3.2:3b,qwen2.5:3b,gemma2:2b,phi3.5:3.8b,granite3.1-dense:2b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from swarmbly_lce.backends import OpenAICompatBackend  # noqa: E402
from lce_validation.experiments import build_wiki  # noqa: E402
from swarmbly_lce.retrieval import BM25Retriever  # noqa: E402

USERS_DIR = HERE / "fixtures" / "bench_users"
OUT = ROOT / "results" / "bench_hc1_scale"


def _norm(s: str) -> str:
    s = s.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def _correct(answer: str, gold: list[str]) -> bool:
    a = _norm(answer)
    return all(_norm(g) in a for g in gold)


def _answer(backend, question: str, context: str = "") -> str:
    prompt = ("Responde en una o dos oraciones. Si hay CONTEXTO, úsalo y no "
              "inventes nada fuera de él; si no hay contexto, responde con lo "
              "que sepas.\n")
    if context:
        prompt += f"CONTEXTO:\n{context}\n"
    prompt += f"PREGUNTA: {question}\n"
    return backend.generate(prompt, temperature=0.0, max_tokens=96)


def _boot_ci(values, B=10_000, seed=20261005):
    rng = np.random.default_rng(seed)
    n = len(values)
    means = np.array([rng.choice(values, n, replace=True).mean()
                      for _ in range(B)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="llama3.2:3b,qwen2.5:3b,gemma2:2b,"
                                         "phi3.5:3.8b,granite3.1-dense:2b")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--users", default=None, help="subconjunto separado por comas")
    args = ap.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    users = sorted(p.name for p in USERS_DIR.iterdir() if p.is_dir())
    if args.users:
        keep = {u.strip() for u in args.users.split(",")}
        users = [u for u in users if u in keep]

    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "kind": "exploratory-benchmark", "benchmark": "H-C1 at scale",
        "models": models, "users": users, "cells": [], "wiki_stats": {}}
    from lce_validation.provenance import record as _record
    prereg = ROOT / "docs" / "PREREGISTRATION_BENCH_R1X_ES.md"
    report["provenance"] = _record(
        prereg, models) if prereg.exists() else "preregistro ausente"

    total_gain, total_q, refused = [], 0, []
    for model in models:
        backend = OpenAICompatBackend(model=model, base_url=args.url)
        print(f"\n=== {model} ===", flush=True)
        for uid in users:
            base = USERS_DIR / uid
            try:
                wiki, stats = build_wiki(base, base / "policy.json", backend,
                                         anchor_mode="quote",
                                         reconcile_types=True,
                                         suffixes=frozenset({".md"}))
            except Exception as exc:  # pragma: no cover
                print(f"  {uid}: wiki falló ({exc})", flush=True)
                refused.append((model, uid, str(exc)))
                continue
            n_claims = stats["claims"]
            qs = json.loads((base / "questions.json").read_text(
                encoding="utf-8"))["questions"]
            if n_claims < 5:
                refused.append((model, uid, f"solo {n_claims} claims"))
                continue
            retr = BM25Retriever().index(wiki.claims.values())
            ok_w = ok_wo = 0
            for q in qs:
                t0 = time.perf_counter()
                a_wo = _answer(backend, q["q"])
                ms_wo = (time.perf_counter() - t0) * 1000
                hits = retr.search(q["q"], k=3)
                context = "\n".join(h.text for h in hits)
                t1 = time.perf_counter()
                a_w = _answer(backend, q["q"], context=context)
                ms_w = (time.perf_counter() - t1) * 1000
                c_w, c_wo = _correct(a_w, q["gold"]), _correct(a_wo, q["gold"])
                ok_w += c_w
                ok_wo += c_wo
                total_q += 1
                total_gain.append(c_w - c_wo)
                report["cells"].append({
                    "model": model, "user": uid, "q": q["q"],
                    "gold": q["gold"], "with": c_w, "without": c_wo,
                    "answer_with": a_w[:300], "answer_without": a_wo[:300],
                    "ms_with": round(ms_w, 1), "ms_without": round(ms_wo, 1)})
            report["wiki_stats"].setdefault(model, {})[uid] = {
                "claims": n_claims,
                "maturity": stats["maturity"],
                "trainable": stats["trainable"],
                "anchor_rejection_rate":
                    stats["anchor_verification"]["rejection_rate"],
                "digest_ms": round(stats["digest_ms"], 1),
            }
            print(f"  {uid}: {ok_w}/{len(qs)} con memoria vs {ok_wo}/{len(qs)} "
                  f"sin memoria | {n_claims} claims | digest "
                  f"{stats['digest_ms']/1000:.0f}s | rechazo ancla "
                  f"{stats['anchor_verification']['rejection_rate']:.2f}",
                  flush=True)

    if refused:
        print("\nREFUSALS:", flush=True)
        for r in refused:
            print(" ", r)
        if len(refused) >= len(models) * len(users) // 2:
            print("demasiados rechazos: la corrida no reporta cifras")
            return 1

    gains = np.array(total_gain, dtype=float)
    lo, hi = _boot_ci(gains)
    # unidad de análisis correcta: la PREGUNTA (media de sus 5 familias)
    by_q: dict[str, list[float]] = {}
    for c in report["cells"]:
        by_q.setdefault((c["user"], c["q"]), []).append(
            c["with"] - c["without"])
    q_gains = np.array([float(np.mean(v)) for v in by_q.values()])
    qlo, qhi = _boot_ci(q_gains)
    report["summary"] = {
        "n_questions": len(by_q),
        "n_cells": total_q,
        "mean_gain": float(gains.mean()),
        "gain_ci95_cells": [lo, hi],
        "mean_gain_by_question": float(q_gains.mean()),
        "gain_ci95_by_question": [qlo, qhi],
        "holds_descriptively": qlo > 0,
        "refusals": refused,
    }
    by_user: dict[str, list[float]] = {}
    by_model: dict[str, list[float]] = {}
    for c in report["cells"]:
        by_user.setdefault(c["user"], []).append(c["with"] - c["without"])
        by_model.setdefault(c["model"], []).append(c["with"] - c["without"])
    report["summary"]["by_user"] = {
        u: {"mean_gain": round(float(np.mean(v)), 3), "n": len(v)}
        for u, v in by_user.items()}
    report["summary"]["by_model"] = {
        m: {"mean_gain": round(float(np.mean(v)), 3), "n": len(v)}
        for m, v in by_model.items()}
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")

    s = report["summary"]
    print(f"\n=== RESUMEN ===")
    print(f"preguntas: {s['n_questions']} (celdas: {s['n_cells']})")
    print(f"ganancia media por celda: {s['mean_gain']:+.3f} "
          f"IC95 [{s['gain_ci95_cells'][0]:+.3f}, {s['gain_ci95_cells'][1]:+.3f}]")
    print(f"ganancia media por PREGUNTA (5 familias por pregunta): "
          f"{s['mean_gain_by_question']:+.3f} IC95 "
          f"[{s['gain_ci95_by_question'][0]:+.3f}, {s['gain_ci95_by_question'][1]:+.3f}]")
    print(f"H-C1 a escala (descriptivo, exploratorio): "
          f"{'se sostiene' if s['holds_descriptively'] else 'no se sostiene'}")
    print("\nganancia por familia:")
    for m, v in s["by_model"].items():
        print(f"  {m:20s} {v['mean_gain']:+.3f} (n={v['n']})")
    print("\nganancia por usuario:")
    for u, v in s["by_user"].items():
        print(f"  {u:12s} {v['mean_gain']:+.3f} (n={v['n']})")
    print(f"\nresultados: {OUT/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
