"""Prueba A/A de reproducibilidad (preregistro R14 1.2–1.4; Enmienda 6 c).

AA1  generación determinista: repite el brazo A2 de R13 (temperatura 0, mismo
     contexto) y compara con las respuestas guardadas;
AA2  digestión determinista (v2, Enmienda 7): segunda corrida de la
     digestión nativa con semilla, comparada con las W_never de F-forget;
AA3  semilla: qwen2.5:3b escribe los 20 temas de C2 a T = 0.7 con las
     semillas 1000–1002, dos veces, por el endpoint compatible con OpenAI y
     por el nativo (``/api/generate``, ``options.seed``);
AA4  medida estocástica: homogeneidad entre semillas por tema en las dos
     repeticiones del endpoint compatible con OpenAI.

Correr DESPUÉS de ``bench_forget`` (AA2 usa sus wikis).

    python -m lce_validation.aa_test
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from swarmbly_lce.backends import PROMPT_MARKERS, OpenAICompatBackend  # noqa: E402
from swarmbly_lce.diversity import homogeneity  # noqa: E402
from lce_validation import run_r13 as R  # noqa: E402
from lce_validation.experiments import FIXTURES, _write  # noqa: E402
from lce_validation.provenance import check_digests, record  # noqa: E402

PREREG = ROOT / "docs" / "PREREGISTRATION_BENCH_R1X_ES.md"
OUT = ROOT / "results" / "aa_test"
R13 = ROOT / "results" / "bench_r13_confirm"
if not (R13 / "results.json").exists():
    R13 = ROOT / "results" / "bench_r13"
FORGET_CACHE = ROOT / "results" / "bench_forget" / "wikis_cache"
RESPONDERS = ["qwen2.5:3b", "llama3.2:3b", "gemma2:2b"]
WRITER, EMBED = "qwen2.5:3b", "nomic-embed-text"
SEEDS = [1000, 1001, 1002]


def _boot(x, B: int = 10_000, seed: int = 20261005):
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    m = [a[rng.integers(0, len(a), len(a))].mean() for _ in range(B)]
    return [round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)]


def aa1(url: str) -> dict[str, Any]:
    stored = json.loads((R13 / "results.json").read_text(encoding="utf-8"))
    old = {(c["user"], c["q"]["q"], c["responder"]): c for c in stored["cells"] if c["arm"] == "A2"}
    backends = {m: OpenAICompatBackend(model=m, base_url=url) for m in RESPONDERS}
    same, ok_old, ok_new, rows = [], [], [], []
    for uid in sorted(p.name for p in R.USERS_DIR.iterdir() if p.is_dir()):
        base = R.USERS_DIR / uid
        doc = "\n\n".join(p.read_text(encoding="utf-8") for p in sorted((base / "teach").rglob("*.md"))
                          if p.name != "borrada.md")
        from lce_validation.bench_forget import load_questions
        for q in load_questions(base):
            ctx = R.rag_context(doc, q["q"])
            for r in RESPONDERS:
                prev = old.get((uid, q["q"], r))
                if prev is None:
                    continue
                ans, _ = R._ask(backends[r], q, context=ctx)
                s = ans[:200] == prev["answer"][:200]
                same.append(s)
                ok_old.append(float(prev["ok"]))
                ok_new.append(float(R.score_answer(q, ans)))
                rows.append({"user": uid, "q": q["q"], "responder": r, "identical": s,
                             "old": prev["answer"][:200], "new": ans})
    rate = float(np.mean(same))
    dacc = float(np.mean(ok_new) - np.mean(ok_old))
    return {"n": len(same), "identical_rate": round(rate, 4), "accuracy_old": round(float(np.mean(ok_old)), 4),
            "accuracy_new": round(float(np.mean(ok_new)), 4), "accuracy_delta": round(dacc, 4),
            "passed": rate >= 0.99 and abs(dacc) <= 0.01, "rows": rows}


def aa2() -> dict[str, Any]:
    """AA2 v2 (Enmienda 7): digestión determinista corrida a corrida.

    Digiere las 15 (usuario, digestor) una SEGUNDA vez con el backend nativo
    con semilla derivada del prompt y compara los conjuntos de claims con las
    W_never de F-forget (primera corrida, mismo backend). Pasa si >= 14 de 15
    conjuntos coinciden."""
    from swarmbly_lce.backends import OllamaNativeBackend
    from lce_validation.bench_forget import _digest
    root = ROOT / "results" / "aa_test" / "second_digest"
    root.mkdir(parents=True, exist_ok=True)
    out, n_same = [], 0
    from lce_validation.fsnames import model_token, split_cache_name
    for f in sorted(FORGET_CACHE.glob("*__never.json")):
        uid, d = split_cache_name(f.name, "__never.json")
        base = FIXTURES / "bench_users" / uid
        backend = OllamaNativeBackend(model=d, base_url="http://localhost:11434")
        cache = root / f"{uid}__{model_token(d)}.json"
        try:
            _digest(base, backend, frozenset({"borrada.md"}), cache, resume=False)
        except Exception as exc:  # noqa: BLE001 - celda no disponible
            out.append({"user": uid, "digester": d, "available": False,
                        "error": str(exc)[:120]})
            continue
        a = {c["claim_id"] for c in json.loads(f.read_text(encoding="utf-8"))["claims"]}
        b = {c["claim_id"] for c in json.loads(cache.read_text(encoding="utf-8"))["claims"]}
        same = a == b
        n_same += same
        out.append({"user": uid, "digester": d, "available": True, "identical": same,
                    "jaccard": round(len(a & b) / len(a | b), 4) if a | b else 1.0,
                    "n_first": len(a), "n_second": len(b)})
    avail = [x for x in out if x["available"]]
    return {"wikis": len(avail), "identical": n_same,
            "mean_jaccard": round(float(np.mean([x["jaccard"] for x in avail])), 4) if avail else None,
            "passed": len(avail) == 15 and n_same >= 14, "rows": out}


def _prompt(topic: str) -> str:
    return (f"{PROMPT_MARKERS['write']}\nWrite two sentences about the topic. Follow the contract fields if present.\n"
            f"TOPIC: {topic}\n")


def _native(url: str, model: str, prompt: str, seed: int, temperature: float = 0.7) -> str:
    root = url.rstrip("/").removesuffix("/v1")
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": temperature, "seed": seed, "num_predict": 160}}).encode()
    req = urllib.request.Request(root + "/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["response"]


def aa3_aa4(url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    topics = json.loads((FIXTURES / "open_queries.json").read_text(encoding="utf-8"))["topics"]
    writer = OpenAICompatBackend(model=WRITER, base_url=url, embed_model=EMBED)
    texts: dict[str, dict[int, dict[tuple, str]]] = {"openai": {1: {}, 2: {}}, "native": {1: {}, 2: {}}}
    for rep in (1, 2):
        for t in topics:
            for s in SEEDS:
                texts["openai"][rep][(t, s)] = _write(writer, t, {}, 0.7, s)
                texts["native"][rep][(t, s)] = _native(url, WRITER, _prompt(t), s)
    aa3 = {}
    for ep in ("openai", "native"):
        same = [texts[ep][1][k] == texts[ep][2][k] for k in texts[ep][1]]
        aa3[ep] = {"n": len(same), "identical_rate": round(float(np.mean(same)), 4),
                   "seed_effective": float(np.mean(same)) >= 0.95}
    hom = {rep: [homogeneity(writer.embed([texts["openai"][rep][(t, s)] for s in SEEDS])) for t in topics]
           for rep in (1, 2)}
    diff = [a - b for a, b in zip(hom[1], hom[2])]
    aa4 = {"topics": len(topics), "homogeneity_rep1": round(float(np.mean(hom[1])), 4),
           "homogeneity_rep2": round(float(np.mean(hom[2])), 4),
           "mean_diff": round(float(np.mean(diff)), 4), "ci95": _boot(diff),
           "passed": abs(float(np.mean(diff))) <= 0.01}
    aa3["texts"] = {ep: {str(rep): {f"{t}|{s}": v for (t, s), v in d.items()} for rep, d in reps.items()}
                    for ep, reps in texts.items()}
    return aa3, aa4


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:11434/v1")
    args = ap.parse_args(argv)
    prov = record(PREREG, RESPONDERS, url=args.url, extra={"mode": "A/A (Enmienda 6c)"})
    problems = check_digests(prov, models=RESPONDERS)
    if problems:
        print("NEGADA (digests):", "; ".join(problems))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    print("AA1 (A2 de R13 repetido, T=0) ...", flush=True)
    r1 = aa1(args.url)
    print(f"  idénticas {r1['identical_rate']:.4f}; Δexactitud {r1['accuracy_delta']:+.4f}", flush=True)
    r2 = aa2()
    print(f"AA2 digestión: {r2['identical']}/{r2['wikis']} wikis idénticas", flush=True)
    print("AA3/AA4 (escrituras con semilla, dos repeticiones) ...", flush=True)
    r3, r4 = aa3_aa4(args.url)
    print(f"  semilla OpenAI {r3['openai']['identical_rate']:.3f}; nativa {r3['native']['identical_rate']:.3f}; "
          f"Δhomogeneidad {r4['mean_diff']:+.4f} {r4['ci95']}", flush=True)
    summary = {"AA1": {k: v for k, v in r1.items() if k != "rows"}, "AA2": {k: v for k, v in r2.items() if k != "rows"},
               "AA3": {k: v for k, v in r3.items() if k != "texts"}, "AA4": r4,
               "R14_rerun_criterion_closed": bool(r1["passed"] and r2["passed"] and r4["passed"])}
    report = {"kind": "A/A (Enmienda 6c)", "prereg": str(PREREG), "provenance": prov, "summary": summary,
              "aa1_rows": r1["rows"], "aa2_rows": r2["rows"], "aa3_texts": r3["texts"]}
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
