"""Curva-L v3 sobre el corpus ADMITIDO `prompts/lcurve_v2.json`.

La v2 midió algo real y se leyó mal tres veces. Esta versión corrige lo que la
revisión del 29-09-2026 encontró en los datos, no en el razonamiento:

1. **Ensamblador completo.** La v2 computaba 3 de las 6 formas de pregunta
   global; `pair_sum`, `triple_argmax` y `pair_warehouse` (32 de 72 globales en
   dev) se calificaban como fallo por construcción, y el techo del brazo
   fragmentado era la cobertura del ensamblador. Aquí se computan las seis, y
   cada pregunta registra si fue computable.

2. **L sobre el MISMO documento.** La v2 corría las celdas declaradas, y cada L
   caía sobre su propia banda de tamaños (L=5 sobre 10–40 filas, L=40 sobre
   80–320). Aquí cada documento de los tamaños elegidos se corre con TODOS los
   L que lo parten en al menos dos fragmentos, así que la pendiente en L se
   mide dentro de documento.

3. **Fidelidad de valor, no cobertura.** Se guarda, por fila, el valor que
   devolvió el fragmento y el verdadero. `rows_correct` es exactitud;
   `rows_answered` es la cobertura que la v2 llamaba «extracción».

4. **Respuestas crudas.** Se guarda el texto de cada fragmento, así que las
   sumas parciales —y cualquier otra afirmación sobre lo que el nodo hizo— se
   pueden auditar. La suma parcial se lee con el último entero de su línea
   (acepta «9: 941+139=1080»).

El monolítico se toma de `data/admission.json` (misma familia, mismos
documentos, generación determinista). `--rerun-mono` lo vuelve a correr bajo
las mismas condiciones y lo guarda junto a cada celda, para descartar que un
cambio de versión del servidor explique la diferencia.

    python3 swarmbly_ref/benchmarks/run_lcurve_v3.py --model llama3.2:3b
    python3 swarmbly_ref/benchmarks/run_lcurve_v3.py --mock-error 0.1   # sin Ollama

`--mock-error p` sustituye el modelo por un simulador determinista que lee las
filas del prompt y se equivoca con probabilidad p por valor. Sirve para
verificar la tubería sin Ollama; escribe en `data/lcurve_v3_mock.jsonl` y
nunca en el archivo de la campaña.
"""

import argparse
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
sys.path.insert(0, ROOT)

L_GRID = (5, 10, 20, 40)
#: 80 y 160 filas admiten los cuatro L con N ≥ 2, así que TODOS los documentos
#: se corren con TODOS los L: el diseño queda balanceado y la pendiente en L
#: se lee sin que el tamaño del documento se mezcle.
DEFAULT_SIZES = (80, 160)

#: Las seis formas del corpus. Si aparece una forma nueva, la pregunta se
#: registra como NO computable en vez de calificarse como fallo en silencio.
FORMS = frozenset({"pair_sum", "pair_diff", "triple_sum", "pair_argmax",
                   "triple_argmax", "pair_warehouse"})


# ------------------------------------------------------------------ filas ---

def rows_of(doc):
    return [l for l in doc["material"].splitlines() if l.strip()]


def parse_row(line):
    """'R-012 | Harbour | seals | on_hand=941 | reorder_at=139' -> dict."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 2 or not parts[0].startswith("R-"):
        return None
    out = {"id": parts[0], "warehouse": parts[1]}
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            try:
                out[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return out


# -------------------------------------------------------------- fragmento ---

def fragment_prompt(rows):
    """Preguntas numeradas: 1..n on_hand, n+1..2n almacén, 2n+1 suma parcial.
    Sin ejemplos numéricos: la v2 mostró que el modelo copia el ejemplo."""
    ids = [r.split(" | ")[0] for r in rows]
    n = len(ids)
    qs = [f"{i + 1}) What is the on_hand of {rid}?" for i, rid in enumerate(ids)]
    qs += [f"{n + i + 1}) Which warehouse holds {rid}?" for i, rid in enumerate(ids)]
    qs.append(f"{2 * n + 1}) What is the SUM of the on_hand values of the "
              f"{n} rows listed above?")
    return ("Read the rows below. Then answer each question on its own line, "
            "in the format 'N: answer'. Output nothing else.\n\n"
            + "\n".join(rows) + "\n\n" + "\n".join(qs))


def parse_fragment(text, rows):
    """Devuelve (on_hand, warehouse, suma) predichos. Lectura tolerante: para
    las preguntas numéricas vale el ÚLTIMO entero de la línea."""
    ids = [r.split(" | ")[0] for r in rows]
    n = len(ids)
    ans = {}
    for line in str(text or "").splitlines():
        m = re.match(r"\s*(\d{1,3})\s*[:.)\-]\s*(.+?)\s*$", line)
        if m:
            ans.setdefault(int(m.group(1)), m.group(2))
    on_hand, wh = {}, {}
    for i, rid in enumerate(ids, start=1):
        a = ans.get(i)
        if a is not None:
            nums = re.findall(r"-?\d+", a.replace(",", ""))
            if nums:
                on_hand[rid] = int(nums[-1])
        b = ans.get(n + i)
        if b is not None:
            wh[rid] = b.strip().strip(".").split("|")[-1].strip()
    total = None
    s = ans.get(2 * n + 1)
    if s is not None:
        nums = re.findall(r"-?\d+", s.replace(",", ""))
        if nums:
            total = int(nums[-1])
    return on_hand, wh, total


# ------------------------------------------------------------- ensamblador --

def _norm(x):
    return re.sub(r"[^a-z0-9]", "", str(x or "").lower())


def assemble(doc, on_hand, wh):
    """Computa cada pregunta global con código. Devuelve {id: registro}."""
    out = {}
    for q in doc["questions"]:
        if q["kind"] != "global":
            continue
        rows, form = q.get("rows", []), q.get("form")
        rec = {"form": form, "expected": q["expected"], "computable": form in FORMS,
               "got": None, "ok": False, "missing_rows": []}
        if not rec["computable"]:
            out[q["id"]] = rec
            continue
        vals = [on_hand.get(r) for r in rows]
        rec["missing_rows"] = [r for r, v in zip(rows, vals) if v is None]
        if rec["missing_rows"]:
            out[q["id"]] = rec          # pérdida de extracción, no de ensamblador
            continue
        if form in ("pair_sum", "triple_sum"):
            got = str(sum(vals))
        elif form == "pair_diff":
            got = str(abs(vals[0] - vals[1]))
        elif form in ("pair_argmax", "triple_argmax"):
            got = rows[max(range(len(rows)), key=lambda i: vals[i])]
        elif form == "pair_warehouse":
            top = rows[max(range(len(rows)), key=lambda i: vals[i])]
            got = wh.get(top)
        else:                           # inalcanzable: FORMS lo filtra
            got = None
        rec["got"] = got
        if got is None:
            rec["missing_rows"] = rec["missing_rows"] or ["<warehouse>"]
        elif q.get("mode") == "numeric":
            exp = int(q["expected"])
            rec["ok"] = abs(int(got) - exp) <= max(0, 0.02 * abs(exp))
        else:
            rec["ok"] = _norm(got) == _norm(q["expected"])
        out[q["id"]] = rec
    return out


# --------------------------------------------------------------- modelos ----

def make_generate(model, mock_error=None, seed=0):
    """Devuelve generate(prompt, max_tokens, num_ctx) -> texto."""
    if mock_error is None:
        from swarmbly_ref import llm

        def gen(prompt, max_tokens, num_ctx):
            return llm.generate(model, prompt, max_tokens=max_tokens,
                                num_ctx=num_ctx, temperature=0.0)["text"]
        return gen

    rng = random.Random(seed)

    def gen(prompt, max_tokens, num_ctx):
        rows = [parse_row(l) for l in prompt.splitlines()]
        rows = [r for r in rows if r]
        n = len(rows)
        lines = []
        for i, r in enumerate(rows, start=1):
            v = r["on_hand"]
            lines.append(f"{i}: {v + rng.choice([-7, 3, 11]) if rng.random() < mock_error else v}")
        for i, r in enumerate(rows, start=1):
            w = "Nowhere" if rng.random() < mock_error else r["warehouse"]
            lines.append(f"{n + i}: {w}")
        tot = sum(r["on_hand"] for r in rows)
        lines.append(f"{2 * n + 1}: {tot + (5 if rng.random() < 0.5 else 0)}")
        return "\n".join(lines)
    return gen


def mono_answer(gen, doc):
    from swarmbly_ref.benchmarks.run_admission import build_prompt
    prompt = build_prompt(doc)
    n_ctx = max(4096, min(32768, len(prompt.split()) * 2 + 1024))
    return gen(prompt, 220, n_ctx)


# ----------------------------------------------------------------- celda ----

def run_cell(gen, doc, L, model, mono=None):
    rows = rows_of(doc)
    frags = [rows[i:i + L] for i in range(0, len(rows), L)]
    truth = {r["id"]: r for r in (parse_row(x) for x in rows) if r}
    on_hand, wh, frag_log = {}, {}, []
    for frag in frags:
        prompt = fragment_prompt(frag)
        max_t = 40 + 14 * len(frag)
        n_ctx = max(4096, min(32768, len(prompt.split()) * 3 + max_t + 512))
        text = gen(prompt, max_t, n_ctx)
        oh, w, tot = parse_fragment(text, frag)
        on_hand.update(oh)
        wh.update(w)
        ids = [x.split(" | ")[0] for x in frag]
        true_sum = sum(truth[i]["on_hand"] for i in ids)
        frag_log.append({
            "rows": ids, "raw": text,
            "on_hand": {i: oh.get(i) for i in ids},
            "warehouse": {i: w.get(i) for i in ids},
            "partial_sum": tot, "partial_sum_true": true_sum,
            "partial_sum_ok": tot == true_sum,
        })
    pq = assemble(doc, on_hand, wh)
    g_ok = sum(1 for v in pq.values() if v["ok"])
    rec = {
        "version": "v3", "doc": doc["id"], "model": model, "N": len(frags),
        "L": L, "n_rows": doc["n_rows"],
        "global_ok": g_ok, "global_n": len(pq),
        "global_computable": sum(1 for v in pq.values() if v["computable"]),
        "per_question": pq,
        "rows_expected": len(truth),
        "rows_answered": sum(1 for i in truth if i in on_hand),
        "rows_correct": sum(1 for i in truth if on_hand.get(i) == truth[i]["on_hand"]),
        "wh_correct": sum(1 for i in truth
                          if _norm(wh.get(i)) == _norm(truth[i]["warehouse"])),
        "partial_sums_ok": sum(f["partial_sum_ok"] for f in frag_log),
        "partial_sums_n": len(frag_log),
        "fragments": frag_log,
    }
    if mono is not None:
        rec["mono_rerun"] = mono
    return rec


def cells_for(doc, sizes):
    if doc["n_rows"] not in sizes:
        return []
    return [L for L in L_GRID if doc["n_rows"] % L == 0 and doc["n_rows"] // L >= 2]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--sizes", default=",".join(map(str, DEFAULT_SIZES)),
                    help="tamaños de documento (filas) a correr con todos los L")
    ap.add_argument("--rerun-mono", action="store_true")
    ap.add_argument("--mock-error", type=float, default=None)
    ap.add_argument("--full-control", action="store_true",
                    help=("control N=1: el MISMO procedimiento de extracción "
                          "sobre el documento entero, con el mismo ensamblador. "
                          "Separa el efecto de partir del efecto de agregar con "
                          "código. Escribe en data/lcurve_v3_full.jsonl"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    sizes = {int(x) for x in args.sizes.split(",") if x}
    base = "lcurve_v3_full" if args.full_control else "lcurve_v3_runs"
    out = args.out or os.path.join(
        ROOT, "data", (base + "_mock" if args.mock_error is not None
                       else base) + ".jsonl")
    d = json.load(open(os.path.join(ROOT, "prompts", "lcurve_v2.json"),
                       encoding="utf-8"))
    dev = set(d["_frozen"]["dev"])
    docs = [x for x in d["prompts"] if x["id"] in dev and cells_for(x, sizes)]
    if args.full_control:
        # un solo «fragmento» del tamaño del documento: extracción monolítica
        plan = [(doc, doc["n_rows"]) for doc in docs]
    else:
        plan = [(doc, L) for doc in docs for L in cells_for(doc, sizes)]
    calls = sum(doc["n_rows"] // L for doc, L in plan)
    print(f"v3: {len(docs)} documentos, {len(plan)} celdas, {calls} llamadas "
          f"de fragmento, modelo {args.model}"
          + (f" [SIMULADO, error {args.mock_error}]" if args.mock_error is not None else ""))

    gen = make_generate(args.model, args.mock_error)
    open(out, "w", encoding="utf-8").close()
    mono_cache = {}
    by_L = {}
    for doc, L in plan:
        mono = None
        if args.rerun_mono:
            if doc["id"] not in mono_cache:
                mono_cache[doc["id"]] = mono_answer(gen, doc)
            mono = mono_cache[doc["id"]]
        rec = run_cell(gen, doc, L, args.model, mono)
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        b = by_L.setdefault(L, {"ok": 0, "n": 0, "rows_ok": 0, "rows": 0})
        b["ok"] += rec["global_ok"]; b["n"] += rec["global_n"]
        b["rows_ok"] += rec["rows_correct"]; b["rows"] += rec["rows_expected"]
        print(f"  {doc['id']} L={L:>2} N={rec['N']:>2}: global "
              f"{rec['global_ok']}/{rec['global_n']}, filas exactas "
              f"{rec['rows_correct']}/{rec['rows_expected']}, sumas parciales "
              f"{rec['partial_sums_ok']}/{rec['partial_sums_n']}", flush=True)

    print("\n=== por L (mismos documentos en todos los L) ===")
    for L in sorted(by_L):
        b = by_L[L]
        print(f"  L={L:>2}: global {b['ok']}/{b['n']} = {b['ok'] / b['n']:.1%}; "
              f"fidelidad {b['rows_ok']}/{b['rows']} = {b['rows_ok'] / b['rows']:.1%}")
    if args.mock_error is None and not args.full_control:
        with open(os.path.join(ROOT, "data", "lcurve_v3_summary.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"model": args.model, "sizes": sorted(sizes),
                       "by_L": by_L, "cells": len(plan)}, f, indent=2)
    print(f"\nregistros: {out}")
    print("siguiente: python3 swarmbly_validation/run_all.py --real  (T08R3)")


if __name__ == "__main__":
    main()
