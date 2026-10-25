"""R13 — la pregunta decisiva de H-C1: ¿la wiki anclada supera a una memoria simple?

Corre los cinco brazos del prerregistro consolidado (A0 sin memoria, A1
documento completo, A2 RAG crudo, A3 wiki LCE, A4 wiki + Γ) sobre las
preguntas v1+v2 del corpus de usuarios, con el diseño cruzado 3×3 en los
brazos de wiki, la rúbrica por tipo de pregunta (simple/cross/updated/
contradiction/deleted/unanswerable) y la contabilidad de tokens enviados
por brazo.

MODOS:
  --confirm  corrida CONFIRMATORIA: exige preregistro confirmado, árbol
             limpio, digests verificados y ≥3 respondedores (R14 sec.1.1);
  (por defecto) PILOTO EXPLORATORIO: corre igual, reporta todo, y declara
  que no emite veredictos preregistrados (Enmienda 1).

Uso:
  python3 -m lce_validation.run_r13 --digesters qwen2.5:3b,llama3.2:3b,gemma2:2b \
      --responders qwen2.5:3b,llama3.2:3b,gemma2:2b
"""

from __future__ import annotations

import argparse
import os
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from swarmbly_lce.backends import OpenAICompatBackend  # noqa: E402
from swarmbly_lce.retrieval import BM25Retriever  # noqa: E402
from lce_validation.experiments import build_wiki  # noqa: E402
from lce_validation.provenance import record as _record  # noqa: E402
from lce_validation import instruments as I  # noqa: E402

PREREG = ROOT / "docs" / "PREREGISTRATION_BENCH_R1X_ES.md"
USERS_DIR = HERE / "fixtures" / "bench_users"

# N1 (Enmienda 6 b): claves «simples» de la v1 que actualizacion.md declara
# superadas — se excluyen de todas las corridas.
STALE = {
    ("andres", "¿Cuál fue la razón de riesgos de tu resultado principal y su intervalo de confianza?"),
    ("carmen", "¿Qué fondo superó el umbral de materialidad este trimestre y cuál fue su variación?"),
    ("mara", "Según tu criterio de abandono, ¿bajo qué valor de F_ST declararías muerta la "
             "hipótesis de aislamiento y cuál fue el valor medido entre Barú y Fábrega?"),
}
OUT = (HERE / ".." / "results" / os.environ.get("R13_OUT_DIR", "bench_r13")).resolve()

ABSTAIN_RE = I._ABSTAIN_RE


def _norm(s: str) -> str:
    s = s.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def _tokens(text: str) -> int:
    return len(text.split())


class _Shim:
    """Objeto compatible con el índice BM25 (sentencias crudas o claims
    cacheadas)."""
    from swarmbly_lce.claims import Status as _S
    status = _S.ACTIVE
    _n = 0

    def __init__(self, t: str):
        self.text = t
        _Shim._n += 1
        self.claim_id = f"shim-{_Shim._n}"

    def render_for_retrieval(self) -> str:
        return self.text


_STOP = set("el la los las un una de del en y o a con por para que se su sus al lo es son fue han como entre sobre más este esta estos estas".split())


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-záéíóúñ0-9]+", text.lower())
            if len(w) > 3 and w not in _STOP}


def _latest_per_fact(ranked: list, dates: dict) -> list:
    """Del ranking (fecha, madurez, score), conserva por HECHO solo la claim
    más reciente: si una claim fechada comparte >=2 palabras de contenido con
    una claim ya conservada, la anterior se descarta (la actualización
    sustituye a la antigua)."""
    kept: list = []
    kept_words: list[set] = []
    for h in ranked:
        src = h.claim.anchors[0].source if getattr(h.claim, "anchors", None) else ""
        dated = dates.get(src, 0) > 0
        words = _content_words(h.text)
        shadowed = False
        for kw in kept_words:
            if len(words & kw) >= 2 and dated:
                shadowed = True
                break
        if shadowed:
            continue
        kept.append(h)
        kept_words.append(words)
    return kept


def wiki_context(wiki, question: str, src_dates: dict, budget: int = 200) -> str:
    """Contexto de los brazos de wiki (A3/A4), una sola implementación.

    Top-10 BM25 sobre las claims; orden por vigencia DESCENDENTE (fecha de la
    fuente, luego madurez, luego score: Enmienda 2, corregida en E2); una
    claim por hecho (``_latest_per_fact``, Enmienda 3); hasta ``budget``
    tokens (palabras)."""
    hits = BM25Retriever().index(wiki.claims.values()).search(question, k=10)
    ranked = sorted(
        hits,
        key=lambda h: (
            src_dates.get(h.claim.anchors[0].source
                          if getattr(h.claim, "anchors", None) else "", 0),
            h.claim.maturity.rank,
            h.score),
        reverse=True)
    ranked = _latest_per_fact(ranked, src_dates)
    ctx = ""
    for h in ranked:
        if _tokens(ctx + h.text) > budget:
            break
        ctx += h.text + "\n"
    return ctx


def rag_context(doc: str, question: str, budget: int = 200) -> str:
    """Contexto del brazo A2: BM25 sobre las oraciones crudas del usuario."""
    sents = re.split(r"(?<=[.!?])\s+", doc)
    ctx = ""
    for h in BM25Retriever().index([_Shim(s) for s in sents]).search(question, k=12):
        if _tokens(ctx + h.text) > budget:
            break
        ctx += h.text + "\n"
    return ctx


def summarize(cells: list[dict], digesters: list[str], B: int = 10_000,
              seed: int = 20261005) -> dict:
    """Resumen de R13 (E1): A3 por digestor, sin sobrescribir celdas, y
    A3 − A2 emparejado por (pregunta, respondedor), promediado por pregunta y
    con bootstrap agrupado por pregunta. Lo usan run_r13 y run_derive."""
    arms = ["A0", "A1", "A2", "A3", "A4"]
    present = [a for a in arms if any(c["arm"] == a for c in cells)]
    means = {a: float(np.mean([c["ok"] for c in cells if c["arm"] == a]))
             for a in present}
    by_dig = {d: float(np.mean([c["ok"] for c in cells if c["arm"] == "A3"
                                and c.get("digester") == d]))
              for d in digesters
              if any(c["arm"] == "A3" and c.get("digester") == d for c in cells)}
    diag = [c for c in cells if c["arm"] == "A3"
            and c.get("digester") == c["responder"]]
    a3_all = [c for c in cells if c["arm"] == "A3"]
    a2 = {(c["user"], c["q"]["q"], c["responder"]): float(c["ok"])
          for c in cells if c["arm"] == "A2"}
    qd: dict[tuple, list[float]] = {}
    for c in a3_all:
        k = (c["user"], c["q"]["q"], c["responder"])
        if k in a2:
            qd.setdefault(k[:2], []).append(float(c["ok"]) - a2[k])
    out = {
        "questions": len(qd),
        "mean_by_arm": {a: round(means[a], 3) for a in present},
        "a3_by_digester": {d: round(v, 3) for d, v in by_dig.items()},
        "a3_diagonal_mean": round(float(np.mean([c["ok"] for c in diag])), 3) if diag else None,
        "a3_crossed_mean": round(float(np.mean([c["ok"] for c in a3_all])), 3) if a3_all else None,
        "tokens_by_arm": {a: round(float(np.mean(
            [c["tokens"] for c in cells if c["arm"] == a])), 1) for a in present},
    }
    if qd:
        q_gains = np.array([float(np.mean(v)) for v in qd.values()])
        rng = np.random.default_rng(seed)
        q_means = np.array([rng.choice(q_gains, len(q_gains), replace=True).mean()
                            for _ in range(B)])
        out["a3_minus_a2_by_question"] = round(float(q_gains.mean()), 3)
        out["a3_minus_a2_ci95"] = [round(float(np.percentile(q_means, 2.5)), 3),
                                   round(float(np.percentile(q_means, 97.5)), 3)]
    return out


_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
          "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
          "octubre": 10, "noviembre": 11, "diciembre": 12}


def _source_date_ordinal(text: str):
    """Fecha explícita más tardía de una fuente (None si no tiene)."""
    best = None
    for m in re.finditer(r"(\d{1,2}) de ([a-záéíóúñ]+) de (\d{4})", text,
                         re.IGNORECASE):
        mes = _MESES.get(m.group(2).lower())
        if mes:
            best = max(best or 0, int(m.group(3)) * 100 + mes)
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", text):
        best = max(best or 0, int(m.group(1)) * 100 + int(m.group(2)))
    return best


def score_answer(q: dict, answer: str) -> bool:
    """Rúbrica de R13 sec.2.3 por tipo."""
    t = q.get("type", "simple")
    if t in ("deleted", "unanswerable"):
        return I._classify_abstention(answer, q.get("q", "")) == "abstain"
    a = _norm(answer)
    if t == "updated":
        return all(_norm(g) in a for g in q["gold"])
    if t == "contradiction":
        has_gold = all(_norm(g) in a for g in q["gold"])
        flagged = bool(re.search(r"discrep|contradic|desacuerdo|no coincide", a))
        return has_gold or (q.get("allow_flag", False) and flagged)
    return all(_norm(g) in a for g in q["gold"])


def _ask(backend, q: dict, context: str = "", gamma: str = "") -> tuple[str, int]:
    prompt = ("Responde en una o dos oraciones SOLO si el contexto contiene "
              "la respuesta exacta a la pregunta. Si el contexto solo tiene "
              "información relacionada pero no la respuesta, di «no está en "
              "mis fuentes» y nada más.\n")
    if gamma:
        prompt += f"ESTILO DEL USUARIO: {gamma}\n"
    if context:
        prompt += f"FUENTES:\n{context}\n"
    prompt += f"PREGUNTA: {q['q']}\n"
    ans = backend.generate(prompt, temperature=0.0, max_tokens=96)
    return ans, _tokens(prompt + ans)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--digesters", default="qwen2.5:3b,llama3.2:3b,gemma2:2b")
    ap.add_argument("--responders", default="qwen2.5:3b,llama3.2:3b,gemma2:2b")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--users", default=None)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--arms", default="A0,A1,A2,A3,A4",
                    help="subconjunto de brazos a correr (el resto se hereda)")
    ap.add_argument("--base-json", default=None,
                    help="results.json previo del que heredar celdas")
    args = ap.parse_args(argv)

    digesters = [m.strip() for m in args.digesters.split(",") if m.strip()]
    responders = [m.strip() for m in args.responders.split(",") if m.strip()]
    users = sorted(p.name for p in USERS_DIR.iterdir() if p.is_dir())
    if args.users:
        keep = {u.strip() for u in args.users.split(",")}
        users = [u for u in users if u in keep]

    prov = _record(PREREG, sorted(set(digesters + responders)),
                   url=args.url, extra={"mode": "confirmatory" if args.confirm
                                        else "exploratory-pilot"})
    if args.confirm:
        problems = []
        if prov["git_dirty"]:
            problems.append("árbol sucio")
        if len(responders) < 3:
            problems.append("menos de 3 respondedores")
        from lce_validation.provenance import check_digests
        problems += check_digests(prov)
        if problems:
            print("NEGADA (confirmatoria):", "; ".join(problems))
            return 1

    arms_run = {a.strip() for a in args.arms.split(",") if a.strip()}
    OUT.mkdir(parents=True, exist_ok=True)
    cache_dir = OUT / "wikis_cache"
    cache_dir.mkdir(exist_ok=True)
    from swarmbly_lce.backends import OllamaNativeBackend
    backends = {m: (OllamaNativeBackend(model=m, base_url=args.url.replace("/v1", ""))
                    if m in digesters
                    else OpenAICompatBackend(model=m, base_url=args.url))
                for m in set(digesters + responders)}

    # wikis por (usuario, digestor) + RAG y documento completo
    # (las wikis se cachean en disco: un fallo no pierde las digestiones)
    wikis: dict[tuple, Any] = {}
    docs: dict[str, str] = {}
    stats: dict[str, Any] = {}
    for uid in users:
        base = USERS_DIR / uid
        srcs = []
        for p in sorted((base / "teach").rglob("*.md")):
            if p.name == "borrada.md":
                continue   # la fuente borrada se olvida antes de preguntar
            srcs.append(p.read_text(encoding="utf-8"))
        docs[uid] = "\n\n".join(srcs)
        from swarmbly_lce.wiki import Wiki as _Wiki
        from swarmbly_lce.policy import LearningPolicy as _LP
        for d in digesters:
            from lce_validation.fsnames import cache_file as _cache_file
            cache_file = _cache_file(cache_dir, uid, d, "_wiki.json")
            if cache_file.exists() and not getattr(args, "no_cache", False):
                wiki = _Wiki.load(cache_file,
                                  _LP.load(base / "policy.json"))
                wikis[(uid, d)] = wiki
                stats[f"{uid}|{d}"] = {"claims": len(wiki.claims),
                                       "cached": True}
                print(f"  wiki {uid}×{d}: {len(wiki.claims)} claims (caché)",
                      flush=True)
                continue
            wiki, st = build_wiki(base, base / "policy.json", backends[d],
                                  anchor_mode="quote", reconcile_types=True,
                                  suffixes=frozenset({".md"}),
                                  exclude_names=frozenset({"borrada.md"}))
            wiki.save(cache_file)
            wikis[(uid, d)] = wiki
            stats[f"{uid}|{d}"] = {"claims": st["claims"],
                                   "anchored": st["claims"],
                                   "rejection": st["anchor_verification"]
                                   ["rejection_rate"]}
            print(f"  wiki {uid}×{d}: {st['claims']} claims", flush=True)

    cells = []
    if args.base_json:
        prev = json.loads(Path(args.base_json).read_text(encoding="utf-8"))
        inherited = [c for c in prev["cells"] if c["arm"] not in arms_run]
        cells.extend(inherited)
        print(f"heredadas {len(inherited)} celdas de brazos no re-corridos")
    for uid in users:
        base = USERS_DIR / uid
        qs = []
        for fname in ("questions.json", "questions_v2.json",
                      "questions_v3.json", "questions_v4.json",
                      "questions_lme.json"):
            p = base / fname
            if p.exists():
                for q in json.loads(p.read_text(encoding="utf-8"))["questions"]:
                    q = dict(q)
                    q.setdefault("type", "simple")
                    qs.append(q)
        src_dates = {}
        for sp in sorted((base / "teach").rglob("*.md")):
            src_dates[sp.relative_to(base).as_posix()] = (
                _source_date_ordinal(sp.read_text(encoding="utf-8")) or 0)
        for q in qs:
            if (uid, q["q"]) in STALE:
                continue   # N1 (Enmienda 6 b): clave superada, no se pregunta
            # A0: sin memoria, cada respondedor
            if "A0" not in arms_run:
                continue_arm = True
            else:
                continue_arm = False
            for r in ([] if continue_arm else responders):
                ans, tok = _ask(backends[r], q)
                cells.append({"user": uid, "arm": "A0", "responder": r,
                              "q": q, "ok": score_answer(q, ans),
                              "tokens": tok, "answer": ans})
            # A1: documento completo, truncado al presupuesto común (200)
            if "A1" in arms_run:
                doc = " ".join(docs[uid].split()[:200])
                for r in responders:
                    ans, tok = _ask(backends[r], q, context=doc)
                    cells.append({"user": uid, "arm": "A1", "responder": r,
                                  "q": q, "ok": score_answer(q, ans),
                                  "tokens": tok, "answer": ans})
            # A2: RAG crudo (BM25 sobre oraciones), hasta 200 tokens
            if "A2" in arms_run:
                ctx2 = rag_context(docs[uid], q["q"])
                for r in responders:
                    ans, tok = _ask(backends[r], q, context=ctx2)
                    cells.append({"user": uid, "arm": "A2", "responder": r,
                                  "q": q, "ok": score_answer(q, ans),
                                  "tokens": tok, "answer": ans})
            # A3: wiki (cruzado digestor × respondedor), hasta 200 tokens,
            # con recuperación por vigencia: fecha de la fuente (más reciente
            # primero), luego madurez, luego score BM25
            if "A3" in arms_run:
                for d in digesters:
                    wiki = wikis[(uid, d)]
                    ctx3 = wiki_context(wiki, q["q"], src_dates)
                    for r in responders:
                        ans, tok = _ask(backends[r], q, context=ctx3)
                        cells.append({"user": uid, "arm": "A3", "digester": d,
                                      "responder": r, "q": q,
                                      "ok": score_answer(q, ans),
                                      "tokens": tok, "answer": ans})
            # A4: wiki + Gamma (proyección real; diagonal digester=responder),
            # misma recuperación por vigencia y presupuesto que A3
            if "A4" in arms_run:
                from swarmbly_lce.projection import Projector
                for d in digesters:
                    if d not in responders:
                        continue
                    wiki = wikis[(uid, d)]
                    ctx4 = wiki_context(wiki, q["q"], src_dates)
                    proj = Projector().project(q["q"], list(wiki.claims.values()))
                    gamma = proj.projection.as_text()
                    ans, tok = _ask(backends[d], q, context=ctx4, gamma=gamma)
                    cells.append({"user": uid, "arm": "A4", "digester": d,
                                  "responder": d, "q": q,
                                  "ok": score_answer(q, ans),
                                  "tokens": tok, "answer": ans})
        print(f"  {uid}: {len(qs)} preguntas respondidas por {len(responders)} "
              f"respondedores", flush=True)

    report = {
        "kind": "exploratory-pilot" if not args.confirm else "confirmatory",
        "prereg": str(PREREG), "provenance": prov,
        "digesters": digesters, "responders": responders,
        "wiki_stats": stats, "cells": cells,
    }
    arms = ["A0", "A1", "A2", "A3", "A4"]
    report["summary"] = {**summarize(cells, digesters), "mode": report["kind"]}
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    s = report["summary"]
    print("\n=== RESUMEN R13 (piloto exploratorio) ===")
    for a in arms:
        print(f"  {a}: exactitud {s['mean_by_arm'][a]:.3f} "
              f"(tokens medios {s['tokens_by_arm'][a]:.0f})")
    print("  A3 por digestor: " + ", ".join(
        f"{d} {v:.3f}" for d, v in s["a3_by_digester"].items()))
    print(f"  A3−A2 por pregunta: {s['a3_minus_a2_by_question']:+.3f} "
          f"[{s['a3_minus_a2_ci95'][0]:+.3f}, {s['a3_minus_a2_ci95'][1]:+.3f}]")
    print(f"resultados: {OUT/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
