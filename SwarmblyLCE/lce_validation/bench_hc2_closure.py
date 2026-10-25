"""Cierre de H-C2: ρ frente a su ganancia (R13 preregistro 2.9).

Con las celdas de la CONFIRMATORIA de R13 y el camino de despacho de
Swarmbly que pide la sección 2.9, se mide por tarea el par (ganancia con
Γ, Δρ). Enmienda 15.6: esta implementación mide la ganancia en exactitud de
QA (no adherencia) y Δρ por aritmética de palabras (no con el packer), así
que su salida es descriptiva:

  * ganancia = A4 − A3 por tarea (diagonal digestor = respondedor), con la
    rúbrica de R13 — el A4 añade Γ sobre la misma recuperación que A3;
  * Δρ por tarea = tokens de Γ añadidos a cada fragmento del contexto
    recuperado (hasta 4 fragmentos de 400 caracteres) sobre los tokens de
    ese contexto; es una cota aritmética, no una medida con el packer.

Regla de compensación preregistrada: **la proyección sobrevive si la
fracción de tareas con ganancia > 0 Y Δρ ≤ 10 % es ≥ 0.8**; se reporta el
diagrama completo por tarea.

    python3 -m lce_validation.bench_hc2_closure
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from swarmbly_lce.projection import Projector  # noqa: E402
from swarmbly_lce.wiki import Wiki  # noqa: E402
from swarmbly_lce.policy import LearningPolicy  # noqa: E402
from lce_validation import run_r13 as R  # noqa: E402
from lce_validation.experiments import FIXTURES  # noqa: E402
from lce_validation.provenance import record as _record  # noqa: E402

OUT = ROOT / "results" / "bench_hc2_closure"
R13 = ROOT / "results" / "bench_r13_confirm"


def _norm(s: str) -> str:
    import re
    s = s.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--swarmbly-ref",
                    default=os.environ.get("SWARMBLY_REF",
                                           str(ROOT.parent / "Swarmbly-AI_Clean")))
    args = ap.parse_args(argv)
    if str(ROOT.parent / "Swarmbly-AI_Clean") not in sys.path:
        sys.path.insert(0, args.swarmbly_ref)
    import swarmbly_ref
    from swarmbly_ref import packer

    OUT.mkdir(parents=True, exist_ok=True)
    d = json.loads((R13 / "results.json").read_text(encoding="utf-8"))
    cells = d["cells"]
    digesters = d.get("digesters") or sorted({c["digester"] for c in cells
                                              if c["arm"] == "A4"})
    report: dict[str, Any] = {
        "planner_version": getattr(swarmbly_ref, "__version__", "sin __version__"),
        "planner_commit": subprocess.run(
            ["git", "-C", args.swarmbly_ref, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "provenance": _record(ROOT / "docs" / "PREREGISTRATION_BENCH_R1X_ES.md",
                              digesters),
        "tasks": []}
    a3 = {}
    a4 = {}
    for c in cells:
        if c["arm"] == "A3" and c["digester"] == c["responder"]:
            a3[(c["user"], c["q"]["q"])] = float(c["ok"])
        elif c["arm"] == "A4":
            a4[(c["user"], c["q"]["q"])] = float(c["ok"])
    for uid in sorted({k[0] for k in a3}):
        from lce_validation.fsnames import cache_file
        wp = cache_file(R13 / "wikis_cache", uid, "qwen2.5:3b", "_wiki.json")
        if not wp.exists():
            continue
        wiki = Wiki.load(wp, LearningPolicy.load(
            FIXTURES / "bench_users" / uid / "policy.json"))
        proj = Projector().project("resumir el material del usuario",
                                   list(wiki.claims.values()))
        gamma = proj.projection.as_text()
        gamma_tok = len(gamma.split())
        for (u, q), ok3 in a3.items():
            if u != uid or (u, q) not in a4:
                continue
            # ρ por tarea: paquetes del contexto crudo vs con Γ (packer real)
            ctx = R.wiki_context(wiki, q, {})
            material_tokens = max(1, len(ctx.split()))
            task = {"objective": q, "format": "prose", "entities": {},
                    "global_constraints": []}
            frags = [ctx[i:i + 400] for i in range(0, len(ctx), 400)][:4]
            rho_base = 0.0
            rho_proj = 0.0
            for f in frags:
                rho_base += len(f.split()) / material_tokens
                rho_proj += (len(f.split()) + gamma_tok) / material_tokens
            d_rho_pct = 100.0 * (rho_proj - rho_base) / max(rho_base, 1e-9)
            gain = a4[(u, q)] - ok3
            report["tasks"].append({
                "user": u, "q": q, "a3_ok": ok3, "a4_ok": a4[(u, q)],
                "gain": gain, "delta_rho_pct": round(d_rho_pct, 2)})
    if report["tasks"]:
        gains = np.array([t["gain"] for t in report["tasks"]])
        drho = np.array([t["delta_rho_pct"] for t in report["tasks"]])
        frac = float(np.mean((gains > 0) & (drho <= 10.0)))
        report["summary"] = {
            "n_tasks": len(report["tasks"]),
            "frac_gain_positive": round(float(np.mean(gains > 0)), 4),
            "frac_drho_le_10": round(float(np.mean(drho <= 10.0)), 4),
            "frac_both": round(frac, 4),
            # Sin veredicto (Enmienda 15.6): la ganancia es exactitud de QA y
            # no adherencia, y Δρ es una cota aritmética, no la del packer.
            "verdict": "descriptivo, sin veredicto (Enmienda 15.6)",
            "rule_fraction_ge_0_8": frac >= 0.8,
            "mean_gain": round(float(np.mean(gains)), 4),
            "median_delta_rho_pct": round(float(np.median(drho)), 2),
        }
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    s = report.get("summary", {})
    print(f"=== Cierre H-C2: {s.get('n_tasks')} tareas, ganancia media "
          f"{s.get('mean_gain'):+.3f}, Δρ mediana {s.get('median_delta_rho_pct')}%, "
          f"fracción (ganancia>0 y Δρ<=10%): {s.get('frac_both')} -> "
          f"{s.get('verdict')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
