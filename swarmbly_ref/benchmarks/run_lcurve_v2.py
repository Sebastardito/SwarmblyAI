"""Curva-L sobre el corpus ADMITIDO `prompts/lcurve_v2.json` — REDISEÑO v2.

Por qué v2: la v1 hacía que cada fragmento COPIARA sus filas verbatim; la
concatenación reconstruía el documento original, el modelo respondía sobre el
mismo texto que el monolítico, y las 48 celdas coincidieron una a una con el
monolítico (verificado: 48/48). Además L estaba confundido con el tamaño del
documento. v2 arregla ambas cosas:

  1. **Cada fragmento RESPONDE, no copia.** Recibe sus filas y debe contestar,
     por fila, el on_hand y el almacén, y calcular la SUMA de on_hand de su
     bloque (aritmética parcial). El ensamblador es código determinista:
     combina los valores extraídos y computa las respuestas globales.
     El brazo fragmentado hace trabajo distinto del monolítico (que lee todo
     y hace la aritmética él mismo).

  2. **L se compara sobre el MISMO documento.** Las celdas declaradas (N, L)
     con N·L = filas comparan L dentro de cada documento.

La curva resultante mide la fidelidad de extracción en función de L — el
mecanismo real que la v1 apuntaba y no podía medir.

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


def _rows_of(doc):
    return [l for l in doc["material"].splitlines() if l.strip()]


def _parse_row(line):
    """'R-012 | Harbour | seals | on_hand=941 | reorder_at=139' -> dict."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 2 or not parts[0].startswith("R-"):
        return None
    out = {"id": parts[0], "warehouse": parts[1]}
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = int(v.strip())
    return out


def fragment_answer(model, rows, n_ctx=4096):
    """El fragmento RESPONDE: por fila on_hand y almacén, y la suma parcial."""
    prompt = (
        "Read the rows below. Answer for EACH row its on_hand value and its "
        "warehouse, one per line, in the format 'R-001: 941 | Harbour'. "
        "Then answer the TOTAL sum of on_hand over all rows shown, in the "
        "format 'TOTAL: 2815'. Output nothing else.\n\n"
        + "\n".join(rows)
    )
    out = llm.generate(model, prompt, max_tokens=700, num_ctx=n_ctx,
                       temperature=0.0)
    return out["text"]


def parse_fragment(text, rows):
    """Devuelve (dict id->on_hand, dict id->warehouse, total_declarado|None)."""
    on_hand, warehouse, total = {}, {}, None
    truth = {}
    for line in rows:
        r = _parse_row(line)
        if r:
            truth[r["id"]] = r
    for line in text.splitlines():
        m = re.match(r"\s*R-(\d+)\s*[:=]\s*(\d+)\s*(?:\|\s*(.+?))?\s*$", line)
        if m:
            rid = f"R-{m.group(1)}"
            on_hand[rid] = int(m.group(2))
            if m.group(3):
                warehouse[rid] = m.group(3).strip()
        mt = re.match(r"\s*TOTAL\s*[:=]\s*(\d+)", line, re.I)
        if mt:
            total = int(mt.group(1))
    return on_hand, warehouse, total, truth


def answer_globals(doc, on_hand, warehouse):
    """Ensamblador determinista: combina y computa cada pregunta global."""
    g_ok = g_n = l_ok = l_n = 0
    missing = []
    for q in doc["questions"]:
        rows = q.get("rows", [])
        if q["kind"] == "local":
            l_n += 1
            val = warehouse.get(rows[0])
            l_ok += bool(val and re.sub(r"[^a-z0-9]", "", val.lower())
                         == re.sub(r"[^a-z0-9]", "", q["expected"].lower()))
            continue
        g_n += 1
        vals = [on_hand.get(r) for r in rows]
        if any(v is None for v in vals):
            missing.append((q["id"], [r for r, v in zip(rows, vals) if v is None]))
            continue   # pérdida de extracción: la global no es computable
        if q["form"] == "pair_diff":
            got = str(vals[0] - vals[1])
        elif q["form"] == "triple_sum":
            got = str(sum(vals))
        elif q["form"] == "pair_argmax":
            got = rows[0] if vals[0] >= vals[1] else rows[1]
        else:
            got = None
        ok = False
        if q.get("mode") == "numeric":
            ok = got is not None and abs(int(got) - int(q["expected"])) <= max(
                0, 0.02 * abs(int(q["expected"])))
        else:
            ok = got is not None and re.sub(r"[^a-z0-9]", "", got.lower()) == \
                re.sub(r"[^a-z0-9]", "", q["expected"].lower())
        g_ok += ok
    return g_ok, g_n, l_ok, l_n, missing


def run_cell(model, doc, N, L, quiet=False):
    rows = _rows_of(doc)
    fragments = [rows[i:i + L] for i in range(0, min(len(rows), N * L), L)][:N]
    on_hand, warehouse, totals = {}, {}, []
    for frag in fragments:
        text = fragment_answer(model, frag)
        oh, wh, tot, truth = parse_fragment(text, frag)
        on_hand.update(oh)
        warehouse.update(wh)
        totals.append((tot, sum(r["on_hand"] for r in truth.values())))
    g_ok, g_n, l_ok, l_n, missing = answer_globals(doc, on_hand, warehouse)
    rec = {
        "doc": doc["id"], "model": model, "N": N, "L": L,
        "n_rows": doc["n_rows"], "global_ok": g_ok, "global_n": g_n,
        "local_ok": l_ok, "local_n": l_n,
        "rows_extracted": len(on_hand),
        "rows_expected": sum(len(f) for f in fragments),
        "total_declared_correct": sum(1 for t, s in totals
                                      if t is not None and t == s),
        "total_declared_n": len(totals),
        "missing_global_rows": missing,
    }
    if not quiet:
        print(f"  {doc['id']} N={N} L={L}: global {g_ok}/{g_n}, "
              f"extraídas {len(on_hand)}/{sum(len(f) for f in fragments)} "
              f"filas, suma parcial correcta "
              f"{rec['total_declared_correct']}/{len(totals)}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--out", default=os.path.join(ROOT, "data",
                                                  "lcurve_v2_runs.jsonl"))
    ap.add_argument("--max-cells", type=int, default=0)
    args = ap.parse_args()

    d = json.load(open(os.path.join(ROOT, "prompts", "lcurve_v2.json"),
                       encoding="utf-8"))
    dev_ids = d["_frozen"]["dev"]
    docs = [x for x in d["prompts"] if x["id"] in dev_ids]
    n_cells = sum(len(x["cells"]) for x in docs)
    print(f"dev: {len(docs)} docs, {n_cells} celdas, modelo {args.model}")

    path = args.out
    open(path, "w", encoding="utf-8").close()   # campaña nueva: piso limpio
    recs = []
    done = 0
    for doc in docs:
        for N, L in doc["cells"]:
            if args.max_cells and done >= args.max_cells:
                break
            recs.append(run_cell(args.model, doc, N, L))
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(recs[-1], ensure_ascii=False) + "\n")
            done += 1
        if args.max_cells and done >= args.max_cells:
            break

    by_L = {}
    for r in recs:
        by_L.setdefault(r["L"], {"ok": 0, "n": 0})
        by_L[r["L"]]["ok"] += r["global_ok"]
        by_L[r["L"]]["n"] += r["global_n"]
    print("\n=== curva-L v2 (tasa global por L, ensamblador determinista) ===")
    for L in sorted(by_L):
        b = by_L[L]
        print(f"  L={L:3d}: {b['ok']}/{b['n']} = {b['ok']/b['n']:.1%}")
    summary = {"model": args.model, "by_L": by_L, "cells": len(recs),
               "mono_baseline_global_rate": 0.611}
    with open(os.path.join(ROOT, "data", "lcurve_v2_summary.json"),
              "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nregistros: {path}")


if __name__ == "__main__":
    main()
