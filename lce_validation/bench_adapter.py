"""F1c — C8/C10 real: LoRA de estilo vs recuperación (H-C6).

Ciclo completo con mlx-lm (instalado por el usuario):
  1. construye el lote de entrenamiento del usuario `mara` desde sus
     documentos de COMPORTAMIENTO (estilo + procedimientos): pares
     instrucción-respuesta derivados de sus reglas (términos preferidos,
     registro, convenciones, umbrales de protocolo);
  2. entrena un LoRA (rank 8, 200 iteraciones) sobre Qwen2.5-3B-Instruct
     con ``mlx_lm.lora`` (Homebrew);
  3. evalúa CUATRO brazos sobre las tareas de adherencia: base, base +
     recuperación (reglas en contexto), adaptador, adaptador + recuperación;
  4. control de facticidad fuera de la wiki: las 10 preguntas factuales del
     fixture respondidas por base vs adaptador (la alucinación no debe subir).

LÍMITES DECLARADOS DE ESTA CORRIDA (qué NO prueba):
  - el lote de entrenamiento y las tareas de adherencia comparten
    redacciones (contaminación: el adaptador memoriza su lote, no
    generaliza);
  - el brazo de recuperación recibe solo el documento de estilo, sin los
    procedimientos, y no puede acertar tareas de protocolo: los brazos no
    son comparables;
  - el lote incluye HECHOS de protocolo (QUAL, DP, método de Weir), lo que
    viola la invariante I1 (solo comportamiento en los pesos);
  - la diferencia bruta es de 2 aciertos sobre 8, sin intervalo de
    confianza, con ~36 pasadas por par (sobreajuste esperado).
LO QUE SÍ PRUEBA: factibilidad — un LoRA de rango 8 se entrena en ~36 s en
hardware de consumo y memoriza su lote. La comparación justa
(generalización vs recuperación) queda para la siguiente fase (diseño
confirmado en commit antes de correr).

CLASIFICACIÓN: corrida EXPLORATORIA de factibilidad (lote sintético de un
usuario, 200 iteraciones, un solo modelo base). Uso:
    python3 -m lce_validation.bench_adapter --train --base-model Qwen/Qwen2.5-3B-Instruct
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

MLX_LORA = "/opt/homebrew/bin/mlx_lm.lora"
MLX_GEN = "/opt/homebrew/bin/mlx_lm.generate"
OUT = ROOT / "results" / "bench_adapter"
STYLE = (HERE / "fixtures" / "bench_users" / "mara" / "teach" / "style"
         / "estilo.md").read_text(encoding="utf-8")
PROC = (HERE / "fixtures" / "bench_users" / "mara" / "teach" / "procedures"
        / "procedimientos.md").read_text(encoding="utf-8")


def _norm(s: str) -> str:
    s = s.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def build_batch() -> list[dict]:
    """Pares instrucción-respuesta de los documentos de comportamiento."""
    rows: list[dict] = []
    prefs = re.findall(r"Prefiero el término (.+?) en lugar de (.+?)[.\n]", STYLE)
    for prefer, avoid in prefs:
        rows.append({"messages": [
            {"role": "user", "content": f"Reescribe usando la terminología "
             f"preferida de mara: «la {avoid} del modelo»"},
            {"role": "assistant", "content": f"la {prefer} del modelo"}]})
        rows.append({"messages": [
            {"role": "user", "content": f"¿Qué término prefieres en lugar "
             f"de {avoid}?"},
            {"role": "assistant", "content": f"Prefiero el término "
             f"{prefer} en lugar de {avoid}."}]})
    rows.append({"messages": [
        {"role": "user", "content": "¿Cómo escribes tus textos?"},
        {"role": "assistant", "content": "Escribo en un registro técnico y "
         "conciso, con oraciones cortas y sin adjetivos de relleno."}]})
    rows.append({"messages": [
        {"role": "user", "content": "¿Cómo cierras tus correos?"},
        {"role": "assistant", "content": "Cierro siempre con un "
         "agradecimiento y mi nombre, y nunca escribo el cuerpo en más de "
         "tres párrafos."}]})
    rows.append({"messages": [
        {"role": "user", "content": "¿Qué haces si el conjunto final de "
         "variantes baja de 5,000?"},
        {"role": "assistant", "content": "Detengo el análisis y reviso el "
         "paso 2.2 del protocolo antes de continuar."}]})
    rows.append({"messages": [
        {"role": "user", "content": "¿Qué exige tu filtrado duro de "
         "variantes?"},
        {"role": "assistant", "content": "Calidad de variante QUAL mayor o "
         "igual a 30 y profundidad DP mayor o igual a 8 en al menos el 80 "
         "por ciento de las muestras."}]})
    rows.append({"messages": [
        {"role": "user", "content": "¿Cómo estimas el F_ST por pares?"},
        {"role": "assistant", "content": "Con el método de Weir y Cockerham, "
         "reportando la matriz completa y el valor medio ponderado."}]})
    return rows


ADHERENCE_TASKS = [
    {"q": "Reescribe en tu propio estilo: «la división de prompts del sistema»",
     "gold": ["fragmentación semántica"]},
    {"q": "¿Qué término prefieres en lugar de diversidad génica?",
     "gold": ["heterocigosidad esperada"]},
    {"q": "¿Qué término prefieres en lugar de historia poblacional?",
     "gold": ["demografía"]},
    {"q": "¿Qué término prefieres en lugar de mutación rara?",
     "gold": ["variante rara"]},
    {"q": "Escribe el cierre de un correo a un colega.",
     "gold": ["agradecimiento"]},
    {"q": "¿Cómo escribes tus textos?",
     "gold": ["técnico", "conciso"]},
    {"q": "¿Qué haces si el conjunto final baja de 5,000 variantes?",
     "gold": ["detengo", "reviso"]},
    {"q": "¿Con qué método estimas el F_ST por pares?",
     "gold": ["weir"]},
]

FACTUAL = json.loads((HERE / "fixtures" / "factual.json").read_text(
    encoding="utf-8"))["questions"]


def _env() -> dict:
    env = os.environ.copy()
    # el caché de HuggingFace vive dentro del workspace (el sandbox bloquea
    # ~/.cache) y está excluido del repositorio por .gitignore
    env["HF_HOME"] = str(ROOT / ".hf_cache")
    return env


def _generate(prompt: str, adapter: Path | None, max_tokens: int = 60) -> str:
    cmd = [MLX_GEN, "--model", "Qwen/Qwen2.5-3B-Instruct",
           "--prompt", prompt, "--max-tokens", str(max_tokens),
           "--temp", "0.0"]
    if adapter:
        cmd += ["--adapter-path", str(adapter)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                       env=_env())
    return r.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-3B-Instruct")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    adapter = OUT / "adapter_mara"

    if args.train or (not args.skip_train and not adapter.exists()):
        rows = build_batch()
        data = OUT / "data"
        data.mkdir(parents=True, exist_ok=True)
        n_valid = max(2, len(rows) // 5)   # mlx-lm exige >= batch_size en valid
        (data / "train.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows[n_valid:])
            + "\n", encoding="utf-8")
        (data / "valid.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows[:n_valid])
            + "\n", encoding="utf-8")
        print(f"lote de entrenamiento: {len(rows)} pares "
              f"({len(rows)-n_valid} train / {n_valid} valid)")
        cmd = [MLX_LORA, "--model", args.base_model, "--train",
               "--data", str(data), "--adapter-path", str(adapter),
               "--iters", "200", "--batch-size", "2",
               "--learning-rate", "1e-4", "--seed", "20261005"]
        print("entrenando LoRA (descarga del modelo la primera vez)...",
              flush=True)
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, env=_env())
        print(r.stdout[-600:], r.stderr[-400:])
        if r.returncode != 0:
            print("entrenamiento falló")
            return 1
        print(f"entrenamiento: {time.time()-t0:.0f}s")

    if not adapter.exists():
        print(f"adaptador ausente: {adapter}")
        return 1

    # evaluación de los cuatro brazos
    context = "\n".join(l for l in STYLE.splitlines() if l.strip())[:800]
    arms = {"base": (None, ""), "retrieval": (None, context),
            "adapter": (adapter, ""), "adapter+retrieval": (adapter, context)}
    results: dict[str, Any] = {"adherence": {}, "factual": {}}
    for name, (adp, ctx) in arms.items():
        ok = 0
        per = []
        for t in ADHERENCE_TASKS:
            prompt = t["q"] + "\n"
            if ctx:
                prompt += f"CONTEXTO (reglas de estilo de mara):\n{ctx}\n"
            ans = _generate(prompt, adp)
            c = all(_norm(g) in _norm(ans) for g in t["gold"])
            ok += c
            per.append({"q": t["q"], "ok": c, "answer": ans[:160]})
        results["adherence"][name] = {
            "score": ok / len(ADHERENCE_TASKS), "per": per}
        print(f"  adherencia [{name}]: {ok}/{len(ADHERENCE_TASKS)}", flush=True)
    # control de facticidad (fuera de la wiki): base vs adaptador
    counts: dict[str, int] = {}
    for name, adp in [("base", None), ("adapter", adapter)]:
        ok = 0
        for q in FACTUAL:
            ans = _generate(q["q"], adp, max_tokens=40)
            ok += all(_norm(g) in _norm(ans) for g in q["gold"])
        results["factual"][name] = ok / len(FACTUAL)
        counts[name] = ok
        print(f"  facticidad [{name}]: {ok}/{len(FACTUAL)}", flush=True)

    adh_a = results["adherence"]["adapter"]["score"]
    adh_r = results["adherence"]["retrieval"]["score"]
    diff = adh_a - adh_r
    # R5: sin veredicto de H-C6 — los brazos no son comparables y el lote
    # contamina las tareas. Solo factibilidad.
    h6 = "no concluyente (lote contaminado, brazos no comparables); " \
         "factibilidad demostrada"
    # conteos enteros: sin la frontera de punto flotante 0.8-0.7 > 0.1
    fact_drop = (counts["base"] - counts["adapter"]) / len(FACTUAL) * 100
    fact_ok = fact_drop <= 10
    summary = {
        "adherence": {k: v["score"] for k, v in results["adherence"].items()},
        "adapter_minus_retrieval": round(diff, 3),
        "h6": h6,
        "factual_base": results["factual"]["base"],
        "factual_adapter": results["factual"]["adapter"],
        "factual_drop_pts": round(fact_drop, 1),
        "factual_control": "ok" if fact_ok else "falla",
        "scope": "exploratorio: lote sintético de un usuario, 200 iters, "
                 "Qwen2.5-3B-Instruct"}
    results["summary"] = summary
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    print(f"\n=== RESUMEN F1c ===")
    print(f"adherencia: base {results['adherence']['base']['score']:.2f} | "
          f"retrieval {adh_r:.2f} | adapter {adh_a:.2f} | "
          f"adapter+retrieval "
          f"{results['adherence']['adapter+retrieval']['score']:.2f}")
    print(f"adaptador − recuperación: {diff:+.3f} -> H-C6: {h6}")
    print(f"facticidad: base {results['factual']['base']:.2f} vs adaptador "
          f"{results['factual']['adapter']:.2f} "
          f"(caída {fact_drop:.1f} pts) -> control: {summary['factual_control']}")
    print(f"resultados: {OUT/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
