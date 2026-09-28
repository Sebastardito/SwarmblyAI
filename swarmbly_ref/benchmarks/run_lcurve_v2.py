"""Curva-L sobre el corpus ADMITIDO `prompts/lcurve_v2.json` (T06/T08R).

Por cada documento dev y cada celda declarada (N, L):
  1. fragmenta las filas en N bloques de L filas (sin flancos: la pregunta es
     solvabilidad pura vs L),
  2. cada fragmento se REPORTA verbatim (extracción, un modelo por fragmento),
  3. el ensamblado (concatenación) se le da al brazo monolítico para que
     responda las preguntas globales,
  4. se califican las globales contra las claves.

La curva es calidad(global) vs L. El brazo monolítico directo (sin fragmentar)
ya está medido por run_admission.py: 61.1 % con llama3.2.

Sólo llama3.2:3b despejó el piso de admisión; se usa esa familia.

    python3 benchmarks/run_lcurve_v2.py --model llama3.2:3b
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
sys.path.insert(0, ROOT)

from swarmbly_ref import llm  # noqa: E402
from swarmbly_ref.benchmarks.run_admission import (build_prompt, check_answer,
                                                   parse_answers)  # noqa: E402


def _rows_of(doc):
    return [l for l in doc["material"].splitlines() if l.strip()]


def fragment_report(model, rows, n_ctx=4096):
    prompt = ("Report each row below VERBATIM, one line per row, preserving "
              "every number and name. Output nothing else.\n\n"
              + "\n".join(rows))
    out = llm.generate(model, prompt, max_tokens=900, num_ctx=n_ctx,
                       temperature=0.0)
    return out["text"]


def run_cell(model, doc, N, L, quiet=False):
    rows = _rows_of(doc)
    fragments = [rows[i:i + L] for i in range(0, min(len(rows), N * L), L)][:N]
    assembled = "\n".join(fragment_report(model, frag) for frag in fragments)
    prompt = build_prompt({**doc, "material": assembled})
    n_ctx = max(4096, min(32768, len(assembled.split()) * 2 + 1024))
    out = llm.generate(model, prompt, max_tokens=220, num_ctx=n_ctx)
    answers = parse_answers(out["text"])
    gh = gt = lh = lt = 0
    for q in doc["questions"]:
        ans = answers.get(q["id"], out["text"])
        ok = check_answer(q, ans)
        if q["kind"] == "global":
            gt += 1
            gh += ok
        else:
            lt += 1
            lh += ok
    rec = {"doc": doc["id"], "model": model, "N": N, "L": L,
           "n_rows": doc["n_rows"], "global_ok": gh, "global_n": gt,
           "local_ok": lh, "local_n": lt,
           "assembled_words": len(assembled.split()),
           "assembled": assembled[:4000]}
    if not quiet:
        print(f"  {doc['id']} N={N} L={L}: global {gh}/{gt}, local {lh}/{lt}",
              flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--out", default=os.path.join(ROOT, "data",
                                                  "lcurve_v2_runs.jsonl"))
    args = ap.parse_args()

    d = json.load(open(os.path.join(ROOT, "prompts", "lcurve_v2.json"),
                       encoding="utf-8"))
    dev_ids = d["_frozen"]["dev"]
    docs = [x for x in d["prompts"] if x["id"] in dev_ids]
    n_cells = sum(len(x["cells"]) for x in docs)
    print(f"dev: {len(docs)} docs, {n_cells} celdas, modelo {args.model}")

    recs = []
    path = args.out
    for doc in docs:
        for N, L in doc["cells"]:
            recs.append(run_cell(args.model, doc, N, L))
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(recs[-1], ensure_ascii=False) + "\n")

    # resumen por L
    by_L = {}
    for r in recs:
        by_L.setdefault(r["L"], {"ok": 0, "n": 0})
        by_L[r["L"]]["ok"] += r["global_ok"]
        by_L[r["L"]]["n"] += r["global_n"]
    print("\n=== curva-L (tasa global por L) ===")
    for L in sorted(by_L):
        b = by_L[L]
        print(f"  L={L:3d}: {b['ok']}/{b['n']} = {b['ok']/b['n']:.1%}")
    summary = {"model": args.model, "by_L": by_L, "cells": len(recs)}
    with open(os.path.join(ROOT, "data", "lcurve_v2_summary.json"),
              "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nregistros: {path}")


if __name__ == "__main__":
    main()
