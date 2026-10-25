"""F1b — ¿La proyección en Γ encarece la redundancia ρ? (segunda mitad de H-C2)

Mide, con el PLANIFICADOR y el PACKER reales de Swarmbly (``swarmbly_ref``,
repositorio hermano), cuánto sube ρ cuando el contrato Γ lleva la proyección
de la LCE, sobre material extenso y real: el documento de procedimientos de
cada usuario del corpus del benchmark (30-50 oraciones), fragmentado con
P9 (L=10, F=2).

La proyección usada es la regla DETERMINISTA de la enmienda 3 (léxico =
términos "Prefiero el término X en lugar de Y" del documento de estilo;
registro = primera línea del mismo documento), la misma que lee las palabras
ancladas del usuario. La proyección con modelo ya está medida en la corrida
confirmatoria 2 (media 97 bytes); este script mide qué hace ESE tamaño al ρ.

QUÉ SE REPORTA (y qué no): con el protocolo actual (Γ replicado en cada
paquete), la proyección añade un +6–8 % de ρ (corrida guardada). La comparación con su
GANANCIA (la condición de muerte real de H-C2 en el whitepaper: «muere si
el aumento de ρ supera la ganancia») NO se hace aquí y queda pendiente; el
escenario por solicitud y el caché de Γ describen diseños no existentes y
su costo NO está medido. Δρ es estructural: ≈ tamaño de Γ / tamaño de cada
paquete, y no se diluye con documentos más largos.

La proyección usa el PROJECTOR real de la LCE sobre la wiki digerida de
cada usuario (qwen2.5:3b, anclaje por cita, reconciliación de tipos).

Salida: ``results/bench_rho/results.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
SWARM_REF = ROOT.parent / "Swarmbly-AI_Clean" / "swarmbly_ref"
sys.path.insert(0, str(ROOT.parent / "Swarmbly-AI_Clean"))

from swarmbly_ref import packer, planner, units  # noqa: E402
from lce_validation.bench_corpus_gen import USERS as CORPUS  # noqa: E402
from lce_validation.experiments import build_wiki  # noqa: E402
from swarmbly_lce.backends import OpenAICompatBackend  # noqa: E402
from swarmbly_lce.projection import Projector  # noqa: E402

OUT = ROOT / "results" / "bench_rho"
USERS_DIR = HERE / "fixtures" / "bench_users"


def deterministic_projection(style_text: str) -> dict[str, str]:
    """La regla de la enmienda 3 sobre las palabras del usuario."""
    lexicon = re.findall(r"Prefiero el término (.+?) en lugar de (.+?)[.\n]",
                         style_text)
    register = next((l for l in style_text.splitlines() if l.strip()), "")
    # tope realista: la proyección medida en la corrida confirmatoria 2 fue
    # de ~97 bytes en total; el registro se trunca para no inflar el costo
    return {
        "register": register[:60],
        "lexicon": [x[0].strip() for x in lexicon],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--L", type=int, default=10)
    ap.add_argument("--F", type=int, default=2)
    ap.add_argument("--swarmbly-ref",
                    default=os.environ.get("SWARMBLY_REF",
                                           str(ROOT.parent / "Swarmbly-AI_Clean")))
    ap.add_argument("--digest-model", default="qwen2.5:3b")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    args = ap.parse_args(argv)
    if str(ROOT.parent / "Swarmbly-AI_Clean") not in sys.path:
        sys.path.insert(0, args.swarmbly_ref)

    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"L": args.L, "F": args.F, "users": {}}

    digest_backend = OpenAICompatBackend(model=args.digest_model,
                                         base_url=args.url)
    import importlib
    # versión del planificador registrada
    import swarmbly_ref
    ref_ver = getattr(swarmbly_ref, "__version__", "sin __version__")
    report["planner_version"] = ref_ver
    report["planner_commit"] = subprocess.run(
        ["git", "-C", args.swarmbly_ref, "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True).stdout.strip()
    for uid in sorted(CORPUS):
        base = USERS_DIR / uid
        material = (base / "teach" / "procedures" / "procedimientos.md"
                    ).read_text(encoding="utf-8")
        wiki, _stats = build_wiki(base, base / "policy.json", digest_backend,
                                  anchor_mode="quote", reconcile_types=True,
                                  suffixes=frozenset({".md"}))
        claims = list(wiki.claims.values())
        proj_res = Projector().project(
            "resumir el procedimiento operativo del usuario", claims)
        proj = {"register": proj_res.projection.register,
                "lexicon": list(proj_res.projection.lexicon.values())
                or [k for k in proj_res.projection.lexicon]}
        sentences = units.split_sentences(material)
        n_sent = len(sentences)
        task = {
            "objective": f"Resumir el procedimiento operativo de {uid}",
            "format": "prose",
            "entities": {t: "" for t in
                         sorted(set(re.findall(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+", material)))[:6]},
            "global_constraints": ["preserve every numeric threshold"],
        }
        gamma_base = packer.build_gamma(task)
        gamma_proj = gamma_base + "\nPERSONAL (contract extension):\n" + \
            f"REGISTER: {proj['register']}\n" + \
            "LEXICON: " + "; ".join(proj["lexicon"])
        plan = planner.plan(material, list(task["entities"]), args.L, args.F,
                            unique_terms=[], cut_mode="weak")
        material_tokens = units.approx_tokens(material)
        packets_base, packets_proj = [], []
        for i, (a, b) in enumerate(plan["ranges"]):
            frag = " ".join(plan["sentences"][a:b])
            flank_lead = " ".join(plan["sentences"][max(0, a - args.F):a])
            flank_trail = " ".join(plan["sentences"][b:b + args.F])
            packets_base.append(packer.build_packet(
                task, gamma_base, frag, flank_lead, flank_trail, [],
                "Resume tu fragmento.", args.F))
            packets_proj.append(packer.build_packet(
                task, gamma_proj, frag, flank_lead, flank_trail, [],
                "Resume tu fragmento.", args.F))
        rho_base, tok_base = packer.rho_total(packets_base, material_tokens)
        rho_proj, tok_proj = packer.rho_total(packets_proj, material_tokens)
        d_rho = rho_proj - rho_base
        # escenario por-solicitud: la proyección entra UNA vez por material
        # (el ensamblador la inyecta en el encabezado de la solicitud, no en
        # cada paquete) — cota inferior del costo por solicitud
        d_tok_req = units.approx_tokens(gamma_proj) - units.approx_tokens(gamma_base)
        rho_req = round((tok_base + d_tok_req) / material_tokens, 3)
        d_tok = units.approx_tokens(gamma_proj) - units.approx_tokens(gamma_base)
        report["users"][uid] = {
            "sentences": n_sent, "fragments": len(plan["ranges"]),
            "material_tokens": material_tokens,
            "projection_tokens": d_tok,
            "mechanism_delta_rho_per_token": round(
                len(plan["ranges"]) / material_tokens, 5),
            "rho_base": rho_base, "rho_proj": rho_proj,
            "rho_proj_per_request": rho_req,
            "delta_rho": round(d_rho, 3),
            "delta_pct": round(100 * d_rho / rho_base, 2),
            "delta_pct_per_request": round(100 * (rho_req - rho_base) / rho_base, 2),
            "tokens_base": tok_base, "tokens_proj": tok_proj,
            "lexicon_terms": len(proj["lexicon"]),
        }
        print(f"  {uid}: ρ {rho_base} -> {rho_proj} "
              f"(+{100*d_rho/rho_base:.1f}%) | {n_sent} oraciones, "
              f"{len(plan['ranges'])} fragmentos, material {material_tokens} tok")

    deltas = [u["delta_pct"] for u in report["users"].values()]
    deltas_req = [u["delta_pct_per_request"] for u in report["users"].values()]
    med = sorted(deltas)[len(deltas) // 2]
    med_req = sorted(deltas_req)[len(deltas_req) // 2]
    worst = max(deltas)
    worst_req = max(deltas_req)
    lo_pct, hi_pct = min(deltas), max(deltas)
    rango = f"+{lo_pct:.1f} %" if lo_pct == hi_pct else f"+{lo_pct:.1f}–{hi_pct:.1f} %"
    verdict = (f"con el protocolo actual (Γ en cada paquete) la proyección "
               f"añade {rango} de ρ (mediana +{med:.0f} %); la comparación "
               f"con su ganancia (la condición de muerte real de H-C2) y el "
               f"costo del diseño por-solicitud o con caché quedan pendientes")
    report["summary"] = {
        "median_delta_pct": round(med, 2), "worst_delta_pct": round(worst, 2),
        "median_delta_pct_per_request": round(med_req, 2),
        "worst_delta_pct_per_request": round(worst_req, 2),
        "verdict_hc2_rho": verdict,
        "note": ("Delta-rho es estructural: ~ tamano de Gamma / tamano de "
                 "cada paquete; no se diluye con documentos mas largos. Los "
                 "escenarios por-solicitud y con cache describen disenos no "
                 "existentes y no estan medidos.")}
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    print(f"\n=== RESUMEN F1b ===")
    print(f"Δρ por paquete: mediano +{med:.1f}% | peor +{worst:.1f}%")
    print(f"Δρ por solicitud (Γ una vez): mediano +{med_req:.1f}% | peor +{worst_req:.1f}%")
    print(f"H-C2 (ρ): {verdict}")
    print(f"resultados: {OUT/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
