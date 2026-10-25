"""Benchmark CLI.

    python3 run_benchmark.py --pilot          # 1 tarea x 1 modelo, armas mono+frag
    python3 run_benchmark.py --full           # corpus completo x 5 modelos (largo)
    python3 run_benchmark.py --tasks table_outturn,fan_qa --models llama3.2:3b
    python3 run_benchmark.py --l-curve        # longform con L = 10/20/40/60
    python3 run_benchmark.py --fault          # incidente 42/60 con/sin compuerta
    python3 run_benchmark.py --kepist         # 3 familias sobre un fragmento (M1)
    python3 run_benchmark.py --router         # decisiones del router vs verdad
    python3 run_benchmark.py --matched        # re-corre frag con presupuesto
                                              # de salida igualado (resuelve T11)

Resume automático: los keys ya presentes en el JSONL no se re-ejecutan.
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)          # .../swarmbly_ref
ROOT = os.path.dirname(PKG)          # parent of the package
sys.path.insert(0, ROOT)

from swarmbly_ref import benchmark as bm  # noqa: E402
from swarmbly_ref.benchmarks import corpus  # noqa: E402

MODELS = ["llama3.2:3b", "qwen2.5:3b", "gemma2:2b", "phi3.5:3.8b",
          "granite3.1-dense:2b"]
GEN_TASKS = ["table_outturn", "table_bonded", "long_report",
             "constrained_composition", "extraction_grid", "longform"]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--models", default="")
    ap.add_argument("--l-curve", action="store_true")
    ap.add_argument("--fault", action="store_true")
    ap.add_argument("--kepist", action="store_true")
    ap.add_argument("--router", action="store_true")
    ap.add_argument("--strong-cut", action="store_true")
    ap.add_argument("--sc", action="store_true")
    ap.add_argument("--extend", action="store_true")
    ap.add_argument("--lcurve2", action="store_true")
    ap.add_argument("--pairs2", action="store_true")
    ap.add_argument("--lcurve3", action="store_true")
    ap.add_argument("--scale", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--probe2", action="store_true")
    ap.add_argument(
        "--match-output-tokens", action="store_true", dest="match_output",
        help=("reparte el presupuesto de salida del monolítico entre los "
              "fragmentos, en vez de dar el presupuesto completo a cada uno. "
              "Resuelve el confundido de longitud (T11): sin esto un plan de N "
              "fragmentos recibe N veces los tokens de salida del monolítico y "
              "el impuesto medido no es interpretable. Las celdas se registran "
              "con el sufijo `|matched`, así que conviven con las originales."))
    ap.add_argument("--matched", action="store_true",
                    help=("corrida de resolución: mono + frag con presupuesto "
                          "igualado sobre las tareas comparables. Implica "
                          "--match-output-tokens."))
    ap.add_argument("--data", default=os.path.join(PKG, "data"))
    args = ap.parse_args()
    if args.matched:
        args.match_output = True

    os.makedirs(args.data, exist_ok=True)
    path = os.path.join(args.data, "benchmark.jsonl")
    done = bm._load_keys(path)
    log(f"data: {path} ({len(done)} records ya registrados)")

    def skip(key):
        if key in done:
            log(f"  skip {key}")
            return True
        return False

    tasks = [t for t in args.tasks.split(",") if t] if args.tasks else None
    models = [m for m in args.models.split(",") if m] if args.models else None

    def run_task(task_id, model, fan=False):
        t = corpus.ALL_TASKS[task_id]
        k1 = f"{task_id}|mono|{model}"
        if not skip(k1):
            log(f"  mono {task_id} {model}")
            bm.run_monolithic(t, model, args.data)
        if fan:
            k2 = f"{task_id}|frag|{model}|fan"
            if not skip(k2):
                log(f"  fan  {task_id} {model}")
                bm.run_fan_qa(t, model, args.data)
        else:
            L, F = t.get("L_target", 8), t.get("F", 2)
            k2 = (f"{task_id}|frag|{model}|L{L}F{F}"
                  + ("|matched" if args.match_output else ""))
            if not skip(k2):
                log(f"  frag {task_id} {model} L={L}"
                    + ("  [presupuesto igualado]" if args.match_output else ""))
                bm.run_fragmented(t, model, args.data, L=L, F=F,
                                  match_output=args.match_output)

    if args.pilot:
        log("PILOT: table_outturn x llama3.2:3b")
        run_task("table_outturn", "llama3.2:3b")
        log("pilot terminado")
        return

    if args.matched:
        # Corrida de resolución del confundido de longitud (T11). Se re-corre
        # SÓLO el brazo fragmentado: el monolítico ya existe y su presupuesto
        # no cambia, así que la celda igualada se compara contra el mismo mono.
        pairs = sorted({(k.split("|")[0], k.split("|")[2], k)
                        for k in done
                        if "|frag|" in k
                        and "|matched" not in k and "|fan" not in k})
        log(f"MATCHED: {len(pairs)} celdas fragmentadas a re-correr con "
            f"presupuesto de salida igualado")
        for tid, model, _key in pairs:
            t = corpus.ALL_TASKS.get(tid)
            if t is None:
                log(f"  skip {tid}: no está en el corpus actual")
                continue
            if f"{tid}|mono|{model}" not in done:
                log(f"  skip {tid} {model}: sin monolítico contra el que comparar")
                continue
            cut = "strong" if "|strong" in _key else "weak"
            L, F = t.get("L_target", 8), t.get("F", 2)
            k = (f"{tid}|frag|{model}|L{L}F{F}"
                 + (f"|{cut}" if cut != "weak" else "") + "|matched")
            if not skip(k):
                log(f"  matched {tid} {model} L={L}"
                    + (" [strong]" if cut == "strong" else ""))
                bm.run_fragmented(t, model, args.data, L=L, F=F,
                                  cut_mode=cut, match_output=True)
        log("hecho (corrida igualada).")
        return

    if args.router:
        for tid in corpus.ALL_TASKS:
            r = bm.run_router_check(corpus.ALL_TASKS[tid])
            log(f"router {tid}: decide={r['decided']} truth={r['truth']} "
                f"correct={r['correct']} ({r['reason']})")

    selected = tasks or GEN_TASKS
    sel_models = models or MODELS
    if args.full and "fan_qa" not in selected:
        selected = selected + ["fan_qa"]

    for tid in selected:
        t = corpus.ALL_TASKS[tid]
        if tid == "fan_qa":
            for m in sel_models:
                run_task(tid, m, fan=True)
        elif tid in ("chain_refusal",):
            r = bm.run_router_check(t)
            log(f"router {tid}: decide={r['decided']} correct={r['correct']}")
            k = f"{tid}|mono|{sel_models[0]}"
            if not skip(k) and args.full:
                log(f"  mono (referencia) {tid} {sel_models[0]}")
                bm.run_monolithic(t, sel_models[0], args.data)
        else:
            for m in sel_models:
                run_task(tid, m)

    if args.full or args.l_curve:
        t = corpus.ALL_TASKS["longform"]
        for L in (10, 20, 40):
            for m in (models or ["llama3.2:3b", "phi3.5:3.8b", "gemma2:2b"]):
                k = f"longform|frag|{m}|L{L}F{t.get('F', 2)}"
                if not skip(k):
                    log(f"  L-curve L={L} {m}")
                    bm.run_fragmented(t, m, args.data, L=L)

    if args.strong_cut:
        # anti-P9 cuts: same L/F as the weak cut, maximised delta (M4, T07R)
        for tid in ("table_outturn", "table_bonded",
                    "portfolio_q1", "inventory_snapshot"):
            t = corpus.ALL_TASKS[tid]
            for m in (models or ["llama3.2:3b", "phi3.5:3.8b"]):
                L, F = t.get("L_target", 10), t.get("F", 2)
                k = f"{tid}|frag|{m}|L{L}F{F}|strong"
                if not skip(k):
                    log(f"  strong-cut {tid} {m}")
                    bm.run_fragmented(t, m, args.data, L=L, F=F, cut_mode="strong")

    if args.extend:
        # nuevas variantes de tabla: mono + frag (débil) para las 5 familias
        for tid in ("portfolio_q1", "inventory_snapshot"):
            for m in sel_models:
                run_task(tid, m)

    if args.scale:
        # escala de enrutabilidad: 8 tablas nuevas (mono + frag operativo)
        for tid in ("portfolio_q4", "portfolio_q5", "bond_municipal",
                    "bond_corporate", "inventory_tools",
                    "inventory_electrical", "fleet_metrics", "sales_regions"):
            for m in sel_models:
                run_task(tid, m)

    if args.pairs2:
        # (a) pares controlados delta: 4 tablas nuevas (mono+débil+fuerte, 5
        # familias) y cortes fuertes para las 4 tablas existentes (familias
        # restantes)
        new_tables = ["portfolio_q2", "portfolio_q3",
                      "inventory_machinery", "inventory_spares"]
        for tid in new_tables:
            for m in sel_models:
                run_task(tid, m)
        for tid in ("table_outturn", "table_bonded",
                    "portfolio_q1", "inventory_snapshot") + tuple(new_tables):
            t = corpus.ALL_TASKS[tid]
            for m in (models or ["qwen2.5:3b", "gemma2:2b", "granite3.1-dense:2b"]):
                L, F = t.get("L_target", 10), t.get("F", 2)
                k = f"{tid}|frag|{m}|L{L}F{F}|strong"
                if not skip(k):
                    log(f"  strong-cut {tid} {m}")
                    bm.run_fragmented(t, m, args.data, L=L, F=F, cut_mode="strong")

    if args.lcurve2:
        # más puntos de la curva-L en otras tareas
        for tid, Ls in (("table_outturn", (4, 6, 16)), ("long_report", (20,))):
            t = corpus.ALL_TASKS[tid]
            for L in Ls:
                for m in (models or ["llama3.2:3b", "phi3.5:3.8b"]):
                    k = f"{tid}|frag|{m}|L{L}F{t.get('F', 2)}"
                    if not skip(k):
                        log(f"  L-curve2 {tid} L={L} {m}")
                        bm.run_fragmented(t, m, args.data, L=L)

    if args.sc or (args.full and False):
        # baseline self-consistency (v0.3): k=5 muestras, medoid semántico
        for tid in ("table_outturn", "table_bonded",
                    "portfolio_q1", "inventory_snapshot"):
            for m in (models or ["llama3.2:3b", "phi3.5:3.8b"]):
                k = f"{tid}|selfcons|{m}|k5"
                if not skip(k):
                    log(f"  self-consistency {tid} {m}")
                    bm.run_selfconsistency(corpus.ALL_TASKS[tid], m, args.data,
                                           k=5, temperature=0.7)

    if args.probe:
        table_ids = [t for t in corpus.ALL_TASKS
                     if corpus.ALL_TASKS[t].get("kind") == "table_summary"]
        for tid in table_ids:
            for m in (models or MODELS):
                k = f"{tid}|probe|{m}"
                if not skip(k):
                    log(f"  probe {tid} {m}")
                    bm.run_probe(corpus.ALL_TASKS[tid], m, args.data)

    if args.lcurve3:
        # completar curvas-L por familia: longform L=10/20/40 para las 2
        # familias sin barrido, y table_outturn L=4/6/16 para las 3 restantes
        for m in (models or ["qwen2.5:3b", "granite3.1-dense:2b"]):
            for L in (10, 20, 40):
                k = f"longform|frag|{m}|L{L}F2"
                if not skip(k):
                    log(f"  L-curve3 longform L={L} {m}")
                    bm.run_fragmented(corpus.ALL_TASKS["longform"], m,
                                      args.data, L=L)
        for m in (models or ["llama3.2:3b", "phi3.5:3.8b", "qwen2.5:3b"]):
            for L in (4, 6, 16):
                k = f"table_outturn|frag|{m}|L{L}F2"
                if not skip(k):
                    log(f"  L-curve3 table L={L} {m}")
                    bm.run_fragmented(corpus.ALL_TASKS["table_outturn"], m,
                                      args.data, L=L)

    if args.probe2:
        for m in (models or MODELS):
            for kind in ("extract", "format"):
                k = f"probe2|{kind}|{m}"
                if not skip(k):
                    log(f"  probe2 {kind} {m}")
                    bm.run_probe2(m, kind, args.data)

    if args.full or args.fault:
        for m in (models or ["llama3.2:3b", "phi3.5:3.8b"]):
            k = f"table_outturn|fault|{m}|L4"
            if not skip(k):
                log(f"  fault-injection {m}")
                bm.run_fault_injection(corpus.ALL_TASKS["table_outturn"], m,
                                       args.data, L=4, corrupt=3)

    if args.full or args.kepist:
        k = "table_outturn|kepist|gemma2:2b+llama3.2:3b+phi3.5:3.8b|L8"
        if not skip(k):
            log("  kepist (3 familias, un fragmento)")
            bm.run_kepist(corpus.ALL_TASKS["table_outturn"],
                          "llama3.2:3b", "gemma2:2b", "phi3.5:3.8b",
                          args.data, L=8, fragment_index=0)

    log("hecho.")


if __name__ == "__main__":
    main()
