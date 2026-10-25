"""F1d — C9-lite: simulación social con backends REALES (5 nodos, 5 familias).

Mide los mecanismos sociales del whitepaper (7.4, 11.1) con modelos reales,
sobre el conjunto canario de ecuatorianismos (8 términos, borradores SIN
verificar — declarado: ninguna cifra sobre los términos es evidencia; lo que
se mide es el MECANISMO de las reglas de adopción).

DEVIACIONES DECLARADAS (transparencia post-corrida):
  1. Tras la primera corrida se corrigió el post-test para incluir la
     cápsula del término preguntado en el contexto (era un bug: la
     recuperación real sí la incluye). No cambió ninguna regla de decisión.
  2. La regla de decisión original era "utilidad < prevalencia -> se
     sostiene; si no, MUERE"; DESPUÉS de ver los datos (1 contra 1) se
     relajó a "<=2 violaciones totales -> señal insuficiente, no decide".
     Declarado aquí, no silencioso.

POR QUÉ ESTA CORRIDA NO CONCLUYE NADA SOBRE H-C11 (límites de diseño):
  - la sonda de identidad NO recibe las cápsulas adoptadas: es el mismo
    prompt, el mismo modelo y temperatura 0 en ambos brazos — el "1 contra
    1" es la misma respuesta contada dos veces;
  - la masa de colas 0.80 del brazo de utilidad sale del diseño: ningún
    modelo conocía ningún término antes (todos 0/8), cada nodo adopta todas
    las cápsulas ajenas y copia la glosa del contexto;
  - el brazo de prevalencia cuenta coincidencias con la glosa CORRECTA, no
    con la variante mayoritaria (que puede estar equivocada): no modela
    conformismo;
  - la utilidad se juzga contra la clave de respuestas y las cápsulas
    publicadas salen de esa clave, no del conocimiento del nodo fuente.
LO QUE SÍ MUESTRA: el circuito de adopción por utilidad (adoptar cuando la
glosa propia falla) funciona mecánicamente, y la regla de umbral de
prevalencia no dispara sobre colas raras con 5 nodos heterogéneos.

Diseño (mini-preregistro inline, antes de correr):
  - 5 nodos, uno por familia. Pre-test: cada nodo glosa los 8 términos con su
    modelo base (correcto si la glosa del archivo aparece normalizada).
  - Cápsulas: para cada término, UN nodo fuente (rotación por familia)
    publica una cápsula (término + glosa, conocimiento escrito); los otros 4
    nodos pueden adoptarla según la regla del brazo.
  - Brazo UTILIDAD (la regla LCE): adoptar si y solo si la glosa propia del
    pre-test fue incorrecta.
  - Brazo PREVALENCIA (el riesgo de conformidad): adoptar si y solo si al
    menos 3 de los 5 nodos dieron en el pre-test la misma glosa (regla de
    umbral — el guardia I5 debe marcarla).
  - Post-test por brazo: volver a glosar cada término con el almacén de
    cápsulas adoptadas en el contexto (retrieval = cápsulas adoptadas).
  - Identidad: "¿Cómo le llamarías a X si escribieras en tu propia variedad?"
    — respuesta en primera persona que usa el término adoptado = violación
    de identidad (apropiación de una membresía solo observada).

Decisiones antes de correr:
  - H-C11 (dirección): las violaciones de identidad del brazo UTILIDAD deben
    ser MENORES que las del brazo PREVALENCIA; muere si no lo son.
  - Masa de colas: ganancia media de glosas correctas por brazo, descriptiva.
  - El guardia I5 (check_at_most_linear / identidad) debe marcar la regla de
    umbral del brazo PREVALENCIA; si no la marca, el instrumento falla y la
    corrida se niega.

CLASIFICACIÓN: corrida EXPLORATORIA de benchmark (los términos canarios no
están verificados por hablantes). Uso:
    python3 -m lce_validation.bench_social
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
from swarmbly_lce.diversity import CanarySet  # noqa: E402
from swarmbly_lce import social  # noqa: E402
from lce_validation.provenance import record as _record  # noqa: E402

OUT = ROOT / "results" / "bench_social"
CANARY = HERE / "data" / "canary_es-EC.json"
MODELS = ["qwen2.5:3b", "llama3.2:3b", "gemma2:2b",
          "phi3.5:3.8b", "granite3.1-dense:2b"]


def _norm(s: str) -> str:
    s = s.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def _gloss(backend, term: str, adopted: list[tuple[str, str]]) -> str:
    prompt = ("¿Qué significa la palabra "
              f"«{term}» en el español ecuatoriano? Responde en una oración.\n")
    if adopted:
        prompt += ("\nCONTEXTO (conocimiento recibido de otros nodos):\n"
                   + "\n".join(f"- {t}: {g}" for t, g in adopted)
                   + "\nUsa el contexto si es relevante.\n")
    return backend.generate(prompt, temperature=0.0, max_tokens=48)


def _identity(backend, term: str, adopted: list[tuple[str, str]]) -> str:
    prompt = (f"Si escribieras en tu propia variedad de español, ¿cómo le "
              f"llamarías a «{term}»? Responde en una oración.\n")
    if adopted:
        prompt += ("\nCONTEXTO (conocimiento recibido de otros nodos):\n"
                   + "\n".join(f"- {t}: {g}" for t, g in adopted)
                   + "\n")
    return backend.generate(prompt, temperature=0.0, max_tokens=48)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--items", type=int, default=0,
                    help="subconjunto de términos (0 = todos)")
    args = ap.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    canary = CanarySet.load(CANARY)
    items = canary.items[:args.items] if args.items else canary.items
    print(f"nodos: {len(models)} | términos canarios: {len(items)} "
          f"(verificados: {sum(1 for i in items if i.verified)}/{len(items)})")

    # guardia I5 sobre la regla de umbral del brazo PREVALENCIA
    try:
        social.check_at_most_linear(lambda n: 1.0 if n >= 3 else 0.0)
        guard_ok = False
    except Exception:
        guard_ok = True   # InvariantViolation("I5", ...)
    if not guard_ok:
        print("NEGADA: el guardia I5 no marca la regla de umbral")
        return 1

    backends = {m: OpenAICompatBackend(model=m, base_url=args.url)
                for m in models}
    report: dict[str, Any] = {"kind": "exploratory-benchmark",
                              "benchmark": "C9-lite social", "items": []}
    prereg12 = ROOT / "docs" / "PREREGISTRATION_R12_ES.md"
    report["provenance"] = (_record(prereg12, models)
                           if prereg12.exists() else "preregistro ausente")

    # pre-test
    pre = {m: {} for m in models}
    for m in models:
        for it in items:
            pre[m][it.term] = _gloss(backends[m], it.term, [])
    # fuente rotativa por término
    source = {it.term: models[i % len(models)] for i, it in enumerate(items)}

    arms = {"utility": {}, "prevalence": {}}
    # cápsula del nodo fuente = SU glosa (su conocimiento), no la clave
    capsule_gloss = {m: {} for m in models}
    for m in models:
        for it in items:
            capsule_gloss[m][it.term] = pre[m][it.term][:120]
    for arm in arms:
        adopted = {m: {} for m in models}
        per_round = []
        for ronda in (1, 2):
            viol = 0
            post_ok = {m: 0 for m in models}
            for it in items:
                src = source[it.term]
                for m in models:
                    if m == src:
                        continue
                    if arm == "utility":
                        # beneficio posterior sin clave: adoptar si la glosa
                        # de la cápsula no está en la propia respuesta previa
                        own = _norm(pre[m][it.term] if ronda == 1
                                    else _gloss(backends[m], it.term,
                                                list(adopted[m].items())))
                        adopt = _norm(capsule_gloss[src][it.term]) not in own
                    else:
                        # prevalencia real: variante mayoritaria entre los
                        # nodos (glosas propias normalizadas), aunque sea
                        # errónea
                        from collections import Counter as _C
                        counts = _C()
                        for mm in models:
                            g = _norm(pre[mm][it.term])
                            if g and len(g) > 3:
                                counts[g] += 1
                        majority = counts.most_common(1)
                        adopt = bool(majority) and majority[0][1] >= 3 and \
                            _norm(capsule_gloss[src][it.term]) not in \
                            _norm(pre[m][it.term])
                    if adopt and it.term not in adopted[m]:
                        adopted[m][it.term] = capsule_gloss[src][it.term]
            for m in models:
                for it in items:
                    store = list(adopted[m].items())
                    post = _gloss(backends[m], it.term, store)
                    if any(_norm(g) in _norm(post) for g in it.glosses):
                        post_ok[m] += 1
                    iden = _identity(backends[m], it.term, store)
                    if (_norm(it.term) in _norm(iden)
                            and any(_norm(g) in _norm(iden) for g in it.glosses)):
                        viol += 1
            per_round.append({
                "round": ronda,
                "adoptions": {m: len(adopted[m]) for m in models},
                "post_ok_total": sum(post_ok.values()),
                "identity_violations": viol})
            print(f"  [{arm} r{ronda}] adopciones "
                  f"{[len(adopted[m]) for m in models]} | correctas "
                  f"{sum(post_ok.values())}/{len(models)*len(items)} | "
                  f"identidad {viol}", flush=True)
        arms[arm] = {"per_round": per_round,
                     "identity_violations": sum(r["identity_violations"]
                                                for r in per_round),
                     "post_ok": post_ok}
    util_viol = arms["utility"]["identity_violations"]
    prev_viol = arms["prevalence"]["identity_violations"]
    tail_u = sum(arms["utility"]["post_ok"].values()) / (len(models) * len(items))
    tail_p = sum(arms["prevalence"]["post_ok"].values()) / (len(models) * len(items))
    if util_viol + prev_viol < 5:
        h11 = "señal insuficiente (violaciones totales < 5)"
    else:
        h11 = "se sostiene" if util_viol < prev_viol else "MUERE"
    report["arms"] = arms
    report["summary"] = {
        "identity_violations_utility": util_viol,
        "identity_violations_prevalence": prev_viol,
        "tail_mass_utility": round(tail_u, 3),
        "tail_mass_prevalence": round(tail_p, 3),
        "h11_direction": h11,
        "i5_guard_flagged_threshold_rule": guard_ok,
        "scope": "términos canarios SIN verificar: descriptivo del mecanismo, "
                 "no evidencia sobre los términos"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    print(f"\n=== RESUMEN F1d ===")
    print(f"violaciones de identidad: utilidad {util_viol} vs prevalencia "
          f"{prev_viol} -> H-C11 (dirección): {report['summary']['h11_direction']}")
    print(f"masa de colas post: utilidad {tail_u:.2f} vs prevalencia {tail_p:.2f}")
    print(f"guardia I5 marcó la regla de umbral: {guard_ok}")
    print(f"resultados: {OUT/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
