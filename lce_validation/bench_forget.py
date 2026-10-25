"""F-forget — ¿olvidar una fuente borra lo que la wiki aprendió de ella?

Preregistrado en la Enmienda 6 (c) de ``PREREGISTRATION_BENCH_R1X``, ANTES de
correr. Para cada usuario y digestor se construyen tres wikis:

  W_full    digerida con TODAS las fuentes ``.md`` (incluida ``borrada.md``);
  W_forget  W_full tras ``Wiki.forget_source`` de esa fuente (SPEC 7.8.1);
  W_never   digerida en la misma corrida sin esa fuente.

Medidas estructurales (principales, sin respondedores): S1 manipulación,
S2 residuo, S3 daño colateral, S4 equivalencia con W_never (conjunto de
claims y contexto entregado a las 126 preguntas de R13), y el barrido que
olvida cada fuente de cada W_full. Medidas de conducta (secundarias):
abstención en las preguntas sobre la fuente borrada con las tres wikis,
mismo prompt, recuperación y rúbrica que R13.

    python -m lce_validation.bench_forget
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from swarmbly_lce.backends import OpenAICompatBackend  # noqa: E402
from swarmbly_lce.policy import LearningPolicy  # noqa: E402
from swarmbly_lce.wiki import Wiki  # noqa: E402
from lce_validation import run_r13 as R  # noqa: E402
from lce_validation.experiments import build_wiki  # noqa: E402
from lce_validation.provenance import check_digests, record  # noqa: E402

PREREG = ROOT / "docs" / "PREREGISTRATION_BENCH_R1X_ES.md"
OUT = ROOT / "results" / "bench_forget"
FORGET = "teach/knowledge/borrada.md"
MODELS = ["qwen2.5:3b", "llama3.2:3b", "gemma2:2b"]


def anchored_to(w: Wiki, src: str) -> set[str]:
    return {cid for cid, c in w.claims.items() if any(a.source == src for a in c.anchors)}


def _sig(c) -> tuple:
    return (c.text, c.type.value, c.maturity.value,
            tuple(sorted((a.source, a.start, a.end) for a in c.anchors)))


def forget_structural(w_full: Wiki, src: str) -> tuple[Wiki, dict[str, int]]:
    """Olvida ``src`` en una COPIA de ``w_full`` y mide residuo y daño colateral."""
    before = {cid: _sig(c) for cid, c in w_full.claims.items()}
    anch = anchored_to(w_full, src)
    w = copy.deepcopy(w_full)
    w.forget_source(src)
    collateral = [cid for cid, sig in before.items()
                  if cid not in anch and (cid not in w.claims or _sig(w.claims[cid]) != sig)]
    return w, {"anchored_before": len(anch),
               "residue": len(anchored_to(w, src)),
               "collateral": len(collateral),
               "kept_multi_anchored": len([c for c in anch if c in w.claims])}


def sources_of(w: Wiki) -> list[str]:
    return sorted({a.source for c in w.claims.values() for a in c.anchors})


def load_questions(base: Path) -> list[dict]:
    qs = []
    for fname in ("questions.json", "questions_v2.json", "questions_v3.json"):
        p = base / fname
        if p.exists():
            for q in json.loads(p.read_text(encoding="utf-8"))["questions"]:
                q = dict(q)
                q.setdefault("type", "simple")
                qs.append(q)
    return qs


def source_dates(base: Path) -> dict[str, int]:
    return {sp.relative_to(base).as_posix(): (R._source_date_ordinal(sp.read_text(encoding="utf-8")) or 0)
            for sp in sorted((base / "teach").rglob("*.md"))}


def _digest(base: Path, backend, exclude: frozenset[str], cache: Path, resume: bool) -> Wiki:
    policy = LearningPolicy.load(base / "policy.json")
    if resume and cache.exists():
        return Wiki.load(cache, policy)
    wiki, _ = build_wiki(base, base / "policy.json", backend, anchor_mode="quote",
                         reconcile_types=True, suffixes=frozenset({".md"}),
                         exclude_names=exclude)
    wiki.save(cache)
    return Wiki.load(cache, policy)   # misma ruta de carga para las tres wikis


def _boot(x: list[float], B: int = 10_000, seed: int = 20261005) -> list[float] | None:
    if not x:
        return None
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    m = [a[rng.integers(0, len(a), len(a))].mean() for _ in range(B)]
    return [round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--users", default=None)
    ap.add_argument("--resume", action="store_true", help="reusar wikis ya digeridas en ESTA prueba")
    args = ap.parse_args(argv)
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    prov = record(PREREG, models, url=args.url, extra={"mode": "exploratory (Enmienda 6c)"})
    problems = check_digests(prov, models=models)
    if problems:
        print("NEGADA (digests):", "; ".join(problems))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    cache_dir = OUT / "wikis_cache"
    cache_dir.mkdir(exist_ok=True)
    from swarmbly_lce.backends import OllamaNativeBackend
    # digestores nativos (deterministas, Enmienda 7); los respondedores usan
    # el mismo backend nativo para las preguntas de conducta
    backends = {m: OllamaNativeBackend(model=m, base_url=args.url.replace("/v1", ""))
                for m in models}
    users = sorted(p.name for p in R.USERS_DIR.iterdir()
                   if p.is_dir() and (p / FORGET).exists())
    if args.users:
        users = [u for u in users if u in {x.strip() for x in args.users.split(",")}]

    cells_struct, sweep, s4, behav = [], [], [], []
    for uid in users:
        base = R.USERS_DIR / uid
        qs = load_questions(base)
        dates = source_dates(base)
        deleted = [q for q in qs if q["type"] == "deleted"]
        for d in models:
            from lce_validation.fsnames import cache_file
            w_full = _digest(base, backends[d], frozenset(),
                             cache_file(cache_dir, uid, d, "__full.json"), args.resume)
            w_never = _digest(base, backends[d], frozenset({"borrada.md"}),
                              cache_file(cache_dir, uid, d, "__never.json"), args.resume)
            w_forget, st = forget_structural(w_full, FORGET)
            st.update({"user": uid, "digester": d, "refused": st["anchored_before"] == 0})
            cells_struct.append(st)
            for src in sources_of(w_full):
                _, sw = forget_structural(w_full, src)
                sweep.append({"user": uid, "digester": d, "source": src, **sw})
            ids_f, ids_n = set(w_forget.claims), set(w_never.claims)
            union = ids_f | ids_n
            same_ctx = [R.wiki_context(w_forget, q["q"], dates) == R.wiki_context(w_never, q["q"], dates)
                        for q in qs]
            s4.append({"user": uid, "digester": d, "claims_forget": len(ids_f), "claims_never": len(ids_n),
                       "jaccard": round(len(ids_f & ids_n) / len(union), 4) if union else 1.0,
                       "identical_claim_sets": ids_f == ids_n,
                       "context_identical_rate": round(float(np.mean(same_ctx)), 4)})
            print(f"  {uid}×{d}: borrada {st['anchored_before']} claims; residuo {st['residue']}; "
                  f"colateral {st['collateral']}; jaccard forget/never {s4[-1]['jaccard']}", flush=True)
            for q in deleted:
                ctxs = {"full": R.wiki_context(w_full, q["q"], dates),
                        "forget": R.wiki_context(w_forget, q["q"], dates),
                        "never": R.wiki_context(w_never, q["q"], dates)}
                for r in models:
                    for cond, ctx in ctxs.items():
                        ans, tok = R._ask(backends[r], q, context=ctx)
                        behav.append({"user": uid, "digester": d, "responder": r, "cond": cond,
                                      "q": q, "abstained": R.score_answer(q, ans), "answer": ans,
                                      "context": ctx, "tokens": tok})

    ok = [c for c in cells_struct if not c["refused"]]
    # Enmienda 6 (c): las celdas rechazadas por S1 no entran en la conducta
    refused = {(c["user"], c["digester"]) for c in cells_struct if c["refused"]}
    behav = [x for x in behav if (x["user"], x["digester"]) not in refused] + \
        [dict(x, refused=True) for x in behav if (x["user"], x["digester"]) in refused]
    behav_ok = [x for x in behav if not x.get("refused")]
    rates = {c: float(np.mean([b["abstained"] for b in behav_ok if b["cond"] == c])) for c in ("full", "forget", "never")}
    by_q: dict[tuple, dict[str, list[float]]] = {}
    for b in behav_ok:
        by_q.setdefault((b["user"], b["q"]["q"]), {}).setdefault(b["cond"], []).append(float(b["abstained"]))
    d_fn = [np.mean(v["forget"]) - np.mean(v["never"]) for v in by_q.values()]
    d_ff = [np.mean(v["forget"]) - np.mean(v["full"]) for v in by_q.values()]
    b1 = rates["never"] - rates["full"] >= 0.10
    structural_holds = bool(ok) and all(c["residue"] == 0 and c["collateral"] == 0 for c in ok) \
        and all(s["residue"] == 0 and s["collateral"] == 0 for s in sweep)
    summary = {
        "cells": len(cells_struct), "refused_cells": len(cells_struct) - len(ok),
        "S1_anchored_to_forgotten": [c["anchored_before"] for c in cells_struct],
        "S2_residue_total": sum(c["residue"] for c in ok),
        "S3_collateral_total": sum(c["collateral"] for c in ok),
        "sweep_forgets": len(sweep),
        "sweep_residue_total": sum(s["residue"] for s in sweep),
        "sweep_collateral_total": sum(s["collateral"] for s in sweep),
        "S4_identical_claim_sets": sum(x["identical_claim_sets"] for x in s4),
        "S4_mean_jaccard": round(float(np.mean([x["jaccard"] for x in s4])), 4),
        "S4_context_identical_rate": round(float(np.mean([x["context_identical_rate"] for x in s4])), 4),
        "abstention": {k: round(v, 3) for k, v in rates.items()},
        "forget_minus_never": round(float(np.mean(d_fn)), 3), "forget_minus_never_ci95": _boot(d_fn),
        "forget_minus_full": round(float(np.mean(d_ff)), 3), "forget_minus_full_ci95": _boot(d_ff),
        "B1_manipulation_ok": b1,
        "B2_behavioural_complete": (b1 and rates["forget"] > rates["full"]
                                     and abs(rates["forget"] - rates["never"]) <= 0.10),
        "verdict_structural": "se sostiene" if structural_holds else "falsificada",
        "n_deleted_questions": len(by_q),
    }
    report: dict[str, Any] = {"kind": "exploratory (Enmienda 6c)", "prereg": str(PREREG), "provenance": prov,
                              "models": models, "forgotten_source": FORGET, "structural": cells_struct,
                              "sweep": sweep, "equivalence": s4, "behaviour": behav, "summary": summary}
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n=== F-forget ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
