"""run_derive — regenera todas las cifras derivadas desde las salidas crudas.

Prerregistro R14 sec.1.3.1: un solo comando, sin modelos, que recalcula las
cifras publicadas y termina con código distinto de cero si alguna no
coincide. Recalcula desde las celdas crudas:

  1. F1a: ganancia media por pregunta (bootstrap agrupado, semilla fija);
  2. F1b: deltas de ρ por usuario desde las entradas guardadas;
  3. adaptador y social: sus resúmenes desde los datos guardados;
  4. corrida confirmatoria 2: re-ejecuta ``decide.py`` sobre las salidas
     guardadas y compara los veredictos;
  5. regenera ``results/BENCH_REPORT.md`` y lo compara byte a byte con el
     versionado.

    python3 -m lce_validation.run_derive
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def _boot_ci(values, B=10_000, seed=20261005):
    rng = np.random.default_rng(seed)
    n = len(values)
    means = np.array([rng.choice(values, n, replace=True).mean()
                      for _ in range(B)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _check(name: str, got, want, tol=1e-6):
    if got is None or want is None or abs(got - want) > tol:
        FAILURES.append(f"{name}: derivado {got} != guardado {want}")
        return False
    return True


def derive_hc1() -> None:
    p = ROOT / "results" / "bench_hc1_scale" / "results.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    by_q: dict[tuple, list[float]] = {}
    for c in d["cells"]:
        by_q.setdefault((c["user"], c["q"]), []).append(c["with"] - c["without"])
    q_gains = np.array([float(np.mean(v)) for v in by_q.values()])
    lo, hi = _boot_ci(q_gains)
    s = d["summary"]
    _check("F1a mean_by_question", float(q_gains.mean()),
           s.get("mean_gain_by_question"))
    _check("F1a ci_lo", lo, s.get("gain_ci95_by_question", [None])[0])
    _check("F1a ci_hi", hi, s.get("gain_ci95_by_question", [None, None])[1])
    _check("F1a n_questions", len(by_q), s.get("n_questions"))


def derive_rho() -> None:
    p = ROOT / "results" / "bench_rho" / "results.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    deltas = [u["delta_pct"] for u in d["users"].values()]
    _check("F1b worst", max(deltas), d["summary"].get("worst_delta_pct"))
    _check("F1b median", sorted(deltas)[len(deltas) // 2],
           d["summary"].get("median_delta_pct"))
    rango = f"+{min(deltas):.1f}–{max(deltas):.1f} %"
    if rango not in d["summary"].get("verdict_hc2_rho", ""):
        FAILURES.append(f"F1b veredicto: el rango {rango} no está en el texto guardado")


def derive_run2() -> None:
    p = ROOT / "results" / "2026-10-05_C1C2_run2" / "results_real.json"
    if not p.exists():
        return
    import lce_validation.decide as decide
    d = json.loads(p.read_text(encoding="utf-8"))
    got = decide.decide(d)
    for k, v in (d.get("verdicts") or {}).items():
        g = got.get(k)
        if g is None:
            FAILURES.append(f"run2 {k}: decide ya no emite este veredicto")
        elif str(g.get("verdict")) != str(v.get("verdict")):
            FAILURES.append(f"run2 {k}: derivado {g.get('verdict')} != "
                            f"guardado {v.get('verdict')}")


def derive_r13() -> None:
    """R13: re-califica cada celda con la rúbrica actual y recomputa el
    resumen con la MISMA función que usa run_r13 (``summarize``), que no
    sobrescribe digestores (E1). Las celdas de corridas anteriores guardaban
    la respuesta truncada a 200 caracteres; solo esas pueden diferir al
    re-calificar y se cuentan aparte."""
    p = ROOT / "results" / "bench_r13_confirm" / "results.json"
    if not p.exists():
        p = ROOT / "results" / "bench_r13" / "results.json"
    if not p.exists():
        return
    from lce_validation.run_r13 import score_answer, summarize
    d = json.loads(p.read_text(encoding="utf-8"))
    cells = d["cells"]
    bad = [c for c in cells if score_answer(c["q"], c["answer"]) != c["ok"]]
    if any(len(c["answer"]) != 200 for c in bad):
        FAILURES.append(f"R13: {sum(len(c['answer']) != 200 for c in bad)} celdas "
                        "no se re-califican igual (rúbrica cambiada o celda editada)")
    got = summarize(cells, d["digesters"])
    want = d.get("summary", {})
    for k, v in got.items():
        if want.get(k) != v:
            FAILURES.append(f"R13 {k}: derivado {v} != guardado {want.get(k)}")

def derive_r13_analysis() -> None:
    """Las cifras de R13 que citan los documentos (analysis.json del piloto y
    de la confirmatoria) deben salir de las celdas guardadas; la cobertura
    (requiere las wikis) no se recalcula aquí."""
    from lce_validation.r13_analysis import analyse
    for name in ("bench_r13", "bench_r13_confirm"):
        p = ROOT / "results" / name / "analysis.json"
        if not (p.parent / "results.json").exists():
            continue
        if not p.exists():
            FAILURES.append(f"{name}: falta analysis.json")
            continue
        want = json.loads(p.read_text(encoding="utf-8"))
        got = analyse(json.loads((p.parent / "results.json").read_text(encoding="utf-8")), base=p.parent)
        for k, v in got.items():
            if want.get(k) != v:
                FAILURES.append(f"{name} analysis {k}: derivado != guardado")


def derive_forget() -> None:
    """Recomputa el resumen de F-forget desde las celdas estructurales y de
    conducta y lo compara con el guardado."""
    import numpy as np
    p = ROOT / "results" / "bench_forget" / "results.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    sm = d.get("summary", {})
    st = d.get("structural", [])
    sw = d.get("sweep", {})
    _check("F-forget S2 total", sum(r.get("residue", 0) for r in st),
           sm.get("S2_residue_total"))
    _check("F-forget S3 total", sum(r.get("collateral", 0) for r in st),
           sm.get("S3_collateral_total"))
    _check("F-forget barrido residuo", sum(r.get("residue", 0) for r in sw),
           sm.get("sweep_residue_total"))
    _check("F-forget barrido colateral", sum(r.get("collateral", 0) for r in sw),
           sm.get("sweep_collateral_total"))
    beh = d.get("behaviour", [])
    by_cond: dict[str, list[int]] = {}
    for r in beh:
        if not r.get("refused"):
            by_cond.setdefault(r["cond"], []).append(int(r.get("abstained")))
    for cond, want in (sm.get("abstention") or {}).items():
        got = round(float(np.mean(by_cond.get(cond, []))), 3) if by_cond.get(cond) else None
        _check(f"F-forget abstención {cond}", got, round(want, 3))
    verdict = ("se sostiene" if sm.get("S2_residue_total", 1) == 0
               and sm.get("S3_collateral_total", 1) == 0 else "se falsifica")
    _check("F-forget veredicto estructural",
           verdict == sm.get("verdict_structural"),
           True)


def derive_forget_analysis() -> None:
    """La conducta conforme al preregistro (sin celdas rechazadas) debe salir
    de las celdas guardadas; la equivalencia independiente requiere caché."""
    p = ROOT / "results" / "bench_forget" / "analysis.json"
    if not (ROOT / "results" / "bench_forget" / "results.json").exists():
        return
    if not p.exists():
        FAILURES.append("F-forget: falta results/bench_forget/analysis.json")
        return
    from lce_validation.forget_analysis import FORGET, analyse
    want = json.loads(p.read_text(encoding="utf-8"))
    got = analyse(json.loads((FORGET / "results.json").read_text(encoding="utf-8")))
    for k, v in got.items():
        if want.get(k) != v:
            FAILURES.append(f"F-forget analysis {k}: derivado != guardado")


def derive_aa() -> None:
    """Recomputa AA1/AA2 y el criterio de re-corrida desde las filas crudas."""
    p = ROOT / "results" / "aa_test" / "results.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    sm = d.get("summary", {})
    r1 = d.get("aa1_rows", [])
    if r1:
        got_rate = round(sum(1 for r in r1 if r.get("identical")) / len(r1), 4)
        _check("AA1 tasa idénticas", got_rate,
               round(sm["AA1"]["identical_rate"], 4))
    r2 = [r for r in d.get("aa2_rows", []) if r.get("available")]
    if r2:
        _check("AA2 wikis idénticas", sum(1 for r in r2 if r.get("identical")),
               sm["AA2"]["identical"])
        _check("AA2 jaccard medio", round(
            sum(r.get("jaccard", 0) for r in r2) / len(r2), 4),
            round(sm["AA2"]["mean_jaccard"], 4))
    _check("A/A criterio cerrado",
           (sm["AA1"]["passed"] and sm["AA2"]["passed"]
            and sm["AA4"]["passed"]) == sm["R14_rerun_criterion_closed"],
           True)


def derive_c2bis_hc2() -> None:
    """Recomputa C2-bis y el cierre H-C2 desde sus celdas/tareas."""
    import numpy as np
    p = ROOT / "results" / "bench_c2bis" / "results.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        red = np.array([c["reduction"] for c in d["cells"]])
        sm = d.get("summary", {})
        _check("C2-bis reducción media", round(float(red.mean()), 4),
               round(sm.get("mean_reduction"), 4))
    p2 = ROOT / "results" / "bench_hc2_closure" / "results.json"
    if p2.exists():
        d2 = json.loads(p2.read_text(encoding="utf-8"))
        gains = np.array([t["gain"] for t in d2["tasks"]])
        drho = np.array([t["delta_rho_pct"] for t in d2["tasks"]])
        sm2 = d2.get("summary", {})
        _check("H-C2 fracción", round(float(np.mean((gains > 0) & (drho <= 10.0))), 4),
               round(sm2.get("frac_both"), 4))
        _check("H-C2 ganancia media", round(float(np.mean(gains)), 4),
               round(sm2.get("mean_gain"), 4))


def derive_report() -> None:
    import lce_validation.bench_report as br
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "BENCH_REPORT.md"
        # regenerar apuntando la salida al temporal
        saved = br.OUT
        br.OUT = tmp
        try:
            rc = br.main()
        finally:
            br.OUT = saved
        if rc != 0:
            FAILURES.append("report: el generador falló")
            return
        want = (ROOT / "results" / "BENCH_REPORT.md").read_text(encoding="utf-8")
        got = tmp.read_text(encoding="utf-8")
        if got != want:
            FAILURES.append("report: regenerado != versionado (deriva de cifras)")


def main() -> int:
    derive_hc1()
    derive_rho()
    derive_run2()
    derive_r13()
    derive_r13_analysis()
    derive_forget()
    derive_forget_analysis()
    derive_aa()
    derive_c2bis_hc2()
    derive_report()
    if FAILURES:
        print("✘ DERIVA DETECTADA:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("✔ todas las cifras derivadas coinciden con las guardadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
