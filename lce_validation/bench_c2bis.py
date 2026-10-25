"""C2-bis — placebo igualado en CANTIDAD de instrucción (R13 preregistro 2.8).

H-C17a: la reducción de homogeneidad por la proyección Γ supera a la de un
placebo de igual longitud con CI95 > 0. Cinco usuarios (los del corpus, que
difieren en >= 2 rasgos de estilo cada uno: registro + lexico propio), 20
temas abiertos, 3 semillas por celda, escritura por el endpoint NATIVO con
semilla (determinista, AA3). La Γ sale del Projector real sobre la wiki del
usuario; el placebo repite la estructura de la Γ (REGISTER + LEXICON) con
contenido neutro y la MISMA cantidad de tokens (pareada por celda).

Se corre DESPUÉS de la confirmatoria de R13 (usa sus wikis).

    python3 -m lce_validation.bench_c2bis
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from swarmbly_lce.backends import PROMPT_MARKERS, OpenAICompatBackend, OllamaNativeBackend  # noqa: E402
from swarmbly_lce.diversity import homogeneity  # noqa: E402
from swarmbly_lce.policy import LearningPolicy  # noqa: E402
from swarmbly_lce.projection import Projector  # noqa: E402
from swarmbly_lce.wiki import Wiki  # noqa: E402
from lce_validation.experiments import FIXTURES  # noqa: E402
from lce_validation.provenance import record as _record  # noqa: E402

OUT = ROOT / "results" / "bench_c2bis"
WRITER, EMBED = "qwen2.5:3b", "nomic-embed-text"
SEEDS = [1000, 1001, 1002]
USERS = ["mara", "julian", "carmen", "andres", "luisa"]


def _tokens(s: str) -> int:
    return len(s.split())


def _placebo(gamma: str) -> str:
    """Placebo con la MISMA cantidad de tokens que la Γ, contenido neutro."""
    n = _tokens(gamma)
    base = ("REGISTER: un registro claro y neutral, con oraciones completas y "
            "sin tecnicismos propios de ninguna persona. LEXICON: usar un "
            "vocabulario general y comun, sin preferencias lexicas particulares, "
            "con terminos corrientes para las ideas habituales de cada tema.")
    words = base.split()
    if len(words) < n:
        pad = " y palabras corrientes" * ((n - len(words)) // 3 + 1)
        words += pad.split()
    return " ".join(words[:n])


def _write_native(model: str, url: str, prompt: str, seed: int) -> str:
    import urllib.request
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.7, "seed": seed,
                                   "num_predict": 160}}).encode()
    req = urllib.request.Request(url.rstrip("/").removesuffix("/v1")
                                 + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode()).get("response", "")


def _boot(x, B: int = 10_000, seed: int = 20261005):
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    m = [a[rng.integers(0, len(a), len(a))].mean() for _ in range(B)]
    return [round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--topics", type=int, default=20)
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)

    topics = json.loads((FIXTURES / "open_queries.json")
                        .read_text(encoding="utf-8"))["topics"][:args.topics]
    writer = OpenAICompatBackend(model=WRITER, base_url=args.url,
                                 embed_model=EMBED)
    report: dict[str, Any] = {"users": USERS, "topics": len(topics),
                              "seeds": SEEDS,
                              "provenance": _record(
                                  ROOT / "docs" / "PREREGISTRATION_BENCH_R1X_ES.md",
                                  [WRITER])}
    cells = []
    for uid in USERS:
        from lce_validation.fsnames import cache_file
        wp = cache_file(ROOT / "results" / "bench_r13_confirm" / "wikis_cache", uid,
                        "qwen2.5:3b", "_wiki.json")
        if not wp.exists():
            print(f"{uid}: falta la wiki de la confirmatoria, salto")
            continue
        wiki = Wiki.load(wp, LearningPolicy.load(
            FIXTURES / "bench_users" / uid / "policy.json"))
        gamma = Projector().project(
            "", list(wiki.claims.values())
        ).projection.as_text()   # petición vacía: rasgos amplios (fallback)
        placebo = _placebo(gamma)
        for t in topics:
            g_texts, p_texts = [], []
            for s in SEEDS:
                prompt_g = (f"{PROMPT_MARKERS['write']}\nWrite two sentences about "
                            f"the topic. Follow the contract fields if present.\n"
                            f"CONTRACT:\n{gamma}\nTOPIC: {t}\n")
                prompt_p = (f"{PROMPT_MARKERS['write']}\nWrite two sentences about "
                            f"the topic. Follow the contract fields if present.\n"
                            f"CONTRACT:\n{placebo}\nTOPIC: {t}\n")
                g_texts.append(_write_native(WRITER, args.url, prompt_g, s))
                p_texts.append(_write_native(WRITER, args.url, prompt_p, s))
            hom_g = homogeneity(writer.embed(g_texts))
            hom_p = homogeneity(writer.embed(p_texts))
            cells.append({"user": uid, "topic": t, "hom_gamma": round(hom_g, 4),
                          "hom_placebo": round(hom_p, 4),
                          "reduction": round(hom_p - hom_g, 4),
                          "gamma_tokens": _tokens(gamma),
                          "placebo_tokens": _tokens(placebo)})
        print(f"  {uid}: Γ {_tokens(gamma)} tokens, placebo {_tokens(placebo)}",
              flush=True)

    red = np.array([c["reduction"] for c in cells])
    mean, (lo, hi) = float(red.mean()), _boot(red)
    report["cells"] = cells
    report["summary"] = {
        "n_cells": len(cells),
        "mean_reduction": round(mean, 4),
        "ci95": [lo, hi],
        # Enmienda 15.5: la homogeneidad se calcula entre las semillas de un
        # mismo usuario, no entre usuarios; no decide H-C17a.
        "h17a": "sin veredicto (mide homogeneidad entre semillas; Enmienda 15.5)",
    }
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    print(f"=== C2-bis: reducción de homogeneidad Γ vs placebo = {mean:+.4f} "
          f"[{lo:+.4f}, {hi:+.4f}] -> H-C17a {report['summary']['h17a']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
