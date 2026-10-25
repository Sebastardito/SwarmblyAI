"""R11 confirmatorio — el adaptador justo (H-C6, H-C10, I1, LC6), Enmienda 9.

Repara E6 y corre como la confirmatoria preregistrada en el sec. 3 del
preregistro, con las decisiones declaradas en la Enmienda 9:

  * Lote: ExampleBuilder SOLO sobre claims TRAINABLES (nunca hechos, I1) de
    la wiki canónica del usuario (digerida por qwen2.5:3b, el digestor
    validado de R13), para AMBAS familias base.
  * Sin colapso: 2 épocas (iters = 2 x ceil(n/2)), batch 2, lr 1e-4.
  * Tareas VALIDAS: lexico (parafrasis/eleccion/reescritura por preferencia
    del propio usuario), registro (reglas concretas del estilo) y
    procedimiento (umbrales del propio protocolo); >= 30 por usuario,
    con oro alcanzable (nunca una regla completa normalizada).
  * CUATRO brazos: base / recuperacion+Gamma (Gamma REAL, Projector sobre
    las claims recuperadas) / adaptador / adaptador+recuperacion+Gamma.
  * I1: hechos DEL USUARIO (10 factuales de su corpus), adaptador SIN
    recuperacion vs base, equivalencia +-0.10.
  * LC6: olvido por regeneracion — se olvida teach/style del usuario y se
    re-entrena sin esas claims; la adherencia a las tareas de estilo debe
    caer hacia el base.
  * H-C10: curva de 2 puntos (25 % y 100 % del presupuesto) sobre tareas de
    material consolidado (estilo), con y sin repaso.

    python3 -m lce_validation.bench_r11
"""

from __future__ import annotations

import argparse
import json
import math
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

import numpy as np  # noqa: E402

from swarmbly_lce.wiki import Wiki  # noqa: E402
from swarmbly_lce.policy import LearningPolicy  # noqa: E402
from swarmbly_lce.training import ExampleBuilder  # noqa: E402
from swarmbly_lce.backends import OpenAICompatBackend  # noqa: E402
from lce_validation import run_r13 as R  # noqa: E402
from lce_validation.provenance import record as _record  # noqa: E402

MLX_LORA = "/opt/homebrew/bin/mlx_lm.lora"
MLX_GEN = "/opt/homebrew/bin/mlx_lm.generate"
OUT = ROOT / "results" / "bench_r11_confirm"
BASE = {"qwen2.5:3b": "Qwen/Qwen2.5-3B-Instruct",
        "granite3.1-dense:2b": "ibm-granite/granite-3.1-2b-instruct"}
CANON = "qwen2.5:3b"

# tareas de registro con oro alcanzable (reglas concretas del estilo)
REGISTER = {
    "mara": [("¿Cómo escribes un umbral numérico en tus textos?",
              ["frecuencia del alelo menor"]),
             ("¿Cómo cierras tus correos?", ["agradecimiento"]),
             ("¿Con qué término te refieres a la división de prompts?",
              ["fragmentación semántica"]),
             ("¿Qué registro usas en tus textos?", ["técnico y conciso"])],
    "julian": [("¿Qué sección escribes siempre al final de un documento de diseño?",
                ["decisiones registradas", "descartada"]),
               ("¿En qué persona gramatical escribes tus documentos?",
                ["primera persona del plural"]),
               ("¿Qué término usas para un servicio pequeño e independiente?",
                ["servicio"])],
    "carmen": [("¿En qué orden presentas los elementos de las notas de tus informes?",
                ["causa", "efecto", "acción"]),
               ("¿Cómo escribes las cifras en tus informes?", ["materialidad"]),
               ("¿Qué término usas en lugar de reserva?", ["provisión"])],
}

# tareas de procedimiento (umbrales del propio protocolo; oro numérico exacto)
PROCEDURE = {
    "mara": [("¿Qué umbral QUAL mínimo exige tu protocolo?", ["40"]),
             ("¿Qué profundidad mínima por sitio exiges?", ["12"]),
             ("¿Con qué umbral de missingness retiras sitios?", ["0.08"]),
             ("¿Cuántas variantes mínimas conserva tu conjunto de trabajo?", ["5,000"]),
             ("¿En qué ventana podas por desequilibrio de ligamiento?", ["50"]),
             ("¿Bajo qué F_ST declaras muerta la hipótesis de aislamiento?", ["0.01"]),
             ("¿Qué retienes en el análisis de componentes principales?", ["10"]),
             ("¿Qué proporción de variantes privadas mostró Cerro de la Muerte?", ["3.1"]),
             ("¿Cuántas muestras de Cerro de la Muerte analizaste?", ["41"]),
             ("¿Qué frecuencia mínima del alelo menor exiges?", ["0.01"])],
    "julian": [("¿Qué cobertura mínima de pruebas exiges antes de un cambio?", ["85"]),
               ("¿Qué p95 de latencia exiges en la prueba de carga?", ["250"]),
               ("¿Con cuántos registros siembras la prueba de carga?", ["12,000"]),
               ("¿En qué incrementos mueves el tráfico en el despliegue azul-verde?", ["25", "50", "100"]),
               ("¿Cada cuánto se refresca la vista materializada?", ["15"]),
               ("¿Qué código tiene la variante huérfana?", ["CAT-102"]),
               ("¿Qué debes escribir antes de toda migración de esquema?", ["revierte"]),
               ("¿Sobre qué percentil defines tus alertas?", ["p95"]),
             ("¿Qué decidiste ante el exceso de cuota de almacenamiento?", ["cobrar"]),
             ("¿Cuál fue la causa raíz de tu último incidente mayor?", ["consulta sin límite"]),
             ("¿Cuánto duró tu último incidente mayor?", ["47"])],
    "carmen": [("¿Cuál es la materialidad vigente de tu informe trimestral?", ["6"]),
               ("¿Con qué confianza reportas el valor en riesgo?", ["99"]),
               ("¿Cuál es el límite de política del valor en riesgo?", ["2.2"]),
               ("¿En cuánto cierra la cartera el trimestre?", ["86.1"]),
               ("¿Qué porcentaje de la cartera está en euros?", ["19"]),
               ("¿Cuándo retiras el informe completo y lo regeneras?", ["1"]),
               ("¿Cuánto subió la provisión por deterioro entre trimestres?", ["1.1"]),
               ("¿Qué pasa cuando una variación supera la materialidad?", ["nota"]),
             ("¿Qué activó la subida de la provisión por deterioro?", ["1.6"]),
             ("¿Qué pasa si se supera el límite dos días seguidos?", ["directorio"]),
             ("¿Qué término prefieres en lugar de umbral de relevancia?", ["materialidad"])],
}


def _norm(s: str) -> str:
    s = s.lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n")]:
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def _env() -> dict:
    env = os.environ.copy()
    env["HF_HOME"] = str(ROOT / ".hf_cache")
    return env


def build_tasks(uid: str) -> tuple[list[dict], list[dict], list[dict]]:
    """(tareas conductuales >=30, tareas de estilo consolidado, factuales I1)"""
    style = (HERE / "fixtures" / "bench_users" / uid
             / "teach" / "style" / "estilo.md").read_text(encoding="utf-8")
    tasks: list[dict] = []
    for prefer, avoid in re.findall(r"Prefiero el término (.+?) en lugar de (.+?)[.\n]", style):
        tasks.append({"q": f"Corrige esta frase para que suene como yo: "
                           f"«el informe habla de la {avoid} del sistema»",
                      "gold": [prefer]})
        tasks.append({"q": f"¿Qué término elegirías frente a «{avoid}» en un texto tuyo?",
                      "gold": [prefer]})
        tasks.append({"q": f"Reescribe: «debemos revisar la {avoid} antes de publicar».",
                      "gold": [prefer]})
        tasks.append({"q": f"En una oración, ¿cómo nombras lo que otros llaman "
                           f"{avoid}?", "gold": [prefer]})
    for q, g in REGISTER[uid]:
        tasks.append({"q": q, "gold": g})
    for q, g in PROCEDURE[uid]:
        tasks.append({"q": q, "gold": g})
    style_tasks = tasks[:4 * 4 + 3]   # lexico + registro = material consolidado
    qs = json.loads((HERE / "fixtures" / "bench_users" / uid
                     / "questions.json").read_text(encoding="utf-8"))["questions"]
    factual = [{"q": f"Según tus notas: {q['q']}", "gold": q["gold"]}
               for q in qs if q.get("gold") and q.get("type", "simple") == "simple"
               and not q.get("abstain")][:10]
    return tasks, style_tasks, factual


def train(base_model: str, rows: list[dict], out_dir: Path, seed: int,
          budget_frac: float = 1.0) -> Path:
    data = out_dir / "data"
    data.mkdir(parents=True, exist_ok=True)
    n_valid = max(2, len(rows) // 5)
    (data / "train.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows[n_valid:])
        + "\n", encoding="utf-8")
    (data / "valid.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows[:n_valid])
        + "\n", encoding="utf-8")
    adapter = out_dir / "adapter"
    if adapter.exists() and any(adapter.glob("*.safetensors")):
        return adapter   # reanudación: el adaptador ya se entrenó
    iters = max(8, 2 * math.ceil(len(rows) / 2))   # 2 épocas: sin colapso
    iters = max(4, round(iters * budget_frac))
    cmd = [MLX_LORA, "--model", base_model, "--train", "--data", str(data),
           "--adapter-path", str(adapter), "--iters", str(iters),
           "--batch-size", "2", "--learning-rate", "1e-4", "--seed", str(seed)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=_env(),
                       timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return adapter


MLX_SERVER = "/opt/homebrew/bin/mlx_lm.server"
_SERVERS: dict[tuple, tuple] = {}
_PORT = 18080
_CUR: tuple | None = None


def _server(base_model: str, adapter: Path | None) -> tuple:
    """UN solo servidor activo a la vez: al arrancar uno nuevo se mata el
    anterior. El pool acumulaba procesos (2 por configuración, nunca
    cerrados) y saturaba la RAM hasta forzar el reinicio del equipo."""
    global _PORT, _CUR
    key = (base_model, str(adapter) if adapter else "")
    if key in _SERVERS:
        return _SERVERS[key]
    if _CUR is not None:
        _proc, _port, _oldkey = _CUR
        try:
            _proc.terminate()
            _proc.wait(timeout=30)
        except Exception:
            try:
                _proc.kill()
            except Exception:
                pass
        _SERVERS.pop(_oldkey, None)
    port = _PORT
    _PORT += 1
    cmd = [MLX_SERVER, "--model", base_model, "--port", str(port),
           "--temp", "0.0", "--max-tokens", "512"]
    if adapter:
        cmd += ["--adapter-path", str(adapter)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, env=_env())
    import urllib.request
    import time as _time
    for _ in range(240):     # hasta 4 min para cargar el modelo
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models",
                                        timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            _time.sleep(1.0)
    _SERVERS[key] = (proc, port)
    _CUR = (proc, port, key)
    return (proc, port)


def generate(prompt: str, adapter: Path | None, base_model: str,
             max_tokens: int = 60) -> str:
    # evaluación servida por un proceso MLX persistente: mismos pesos,
    # mismo prompt, temperatura 0 — solo cambia el mecanismo de servir
    # (la CLI recargaba el modelo por llamada y granite tardaba ~45 s).
    import urllib.request
    _proc, port = _server(base_model, adapter)
    body = json.dumps({"model": base_model, "prompt": prompt,
                       "temperature": 0.0, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions",
                                 data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode())
    return (data["choices"][0]["text"] or "").strip()


def _ok(golds: list[str], answer: str) -> bool:
    a = _norm(answer)
    return all(_norm(g) in a for g in golds)


def _ci(x: list[float]) -> tuple[float, float]:
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(20261005)
    m = [a[rng.integers(0, len(a), len(a))].mean() for _ in range(5000)]
    return round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)


def gamma_context(wiki: Wiki, q: str) -> tuple[str, str]:
    from swarmbly_lce.projection import Projector
    retr = wiki_context_simple(wiki, q)
    proj = Projector().project(q, list(wiki.claims.values()))
    return retr, proj.projection.as_text()


def wiki_context_simple(wiki: Wiki, q: str, budget: int = 200) -> str:
    from swarmbly_lce.retrieval import BM25Retriever
    hits = BM25Retriever().index(wiki.claims.values()).search(q, k=10)
    hits = R._latest_per_fact(hits, {})
    ctx = ""
    for h in hits:
        if len(ctx) + len(h.text) > budget:
            break
        ctx += h.text + "\n"
    return ctx


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="mara,julian,carmen")
    ap.add_argument("--families", default="qwen2.5:3b,granite3.1-dense:2b")
    ap.add_argument("--seeds", default="20261005,20261006")
    ap.add_argument("--skip-lc6", action="store_true")
    args = ap.parse_args(argv)
    users = [u.strip() for u in args.users.split(",")]
    fams = [f.strip() for f in args.families.split(",")]
    seeds = [int(s) for s in args.seeds.split(",")]
    OUT.mkdir(parents=True, exist_ok=True)

    prereg = ROOT / "docs" / "PREREGISTRATION_BENCH_R1X_ES.md"
    report: dict[str, Any] = {"cells": [], "trainings": [],
                              "provenance": (_record(prereg, fams)
                                             if prereg.exists() else "ausente")}
    for fam in fams:
        base_model = BASE[fam]
        for uid in users:
            tasks, style_tasks, factual = build_tasks(uid)
            from lce_validation.fsnames import cache_file
            wp = cache_file(ROOT / "results" / "bench_r13_confirm" / "wikis_cache", uid,
                            CANON, "_wiki.json")
            if not wp.exists():
                print(f"{uid}: falta la wiki canónica ({wp.name}), salto")
                continue
            wiki = Wiki.load(wp, LearningPolicy.load(
                HERE / "fixtures" / "bench_users" / uid / "policy.json"))
            rows = [{"messages": [{"role": "user", "content": e.prompt},
                                  {"role": "assistant", "content": e.response}],
                     "_cid": (e.claim_ids[0] if e.claim_ids else None)}
                    for e in ExampleBuilder(wiki).from_claims()
                    if e.kind != "preference_pair"]
            if len(rows) < 6:
                print(f"  {uid}×{fam}: lote insuficiente ({len(rows)}), salto")
                continue
            replay_rows = rows + rows[:4] + rows[:4]
            for replay in ("yes", "no"):
                batch = replay_rows if replay == "yes" else rows
                for seed in seeds:
                    for frac in (0.25, 1.0):
                        tag = f"{uid}__{fam}__s{seed}__r{replay}__b{frac}"
                        adir = OUT / tag
                        t0 = time.time()
                        try:
                            adapter = train(base_model, batch, adir, seed, frac)
                        except RuntimeError as e:
                            print(f"  {tag}: falló: {e}")
                            report["trainings"].append({"tag": tag, "ok": False})
                            continue
                        report["trainings"].append(
                            {"tag": tag, "ok": True, "batch": len(batch),
                             "seconds": round(time.time() - t0, 1)})
                        print(f"  {tag}: {len(batch)} pares, {time.time()-t0:.0f}s",
                              flush=True)
                        if frac != 1.0:      # la curva H-C10 solo en estilo
                            for t in style_tasks:
                                ans_b = generate(t["q"], None, base_model)
                                ans_a = generate(t["q"], adapter, base_model)
                                report["cells"].append({
                                    "tag": tag, "q": t["q"], "gold": t["gold"],
                                    "hc10": True, "style": True,
                                    "base_ok": _ok(t["gold"], ans_b),
                                    "adapter_ok": _ok(t["gold"], ans_a)})
                            continue
                        ctxs = {}
                        for t in tasks:
                            ctx, gamma = gamma_context(wiki, t["q"])
                            ctxs[t["q"]] = (ctx, gamma)
                        # brazo base + recuperación: servidor base (una carga)
                        for t in tasks:
                            ctx, gamma = ctxs[t["q"]]
                            ans_b = generate(t["q"], None, base_model)
                            ans_r = generate(t["q"] + "\nCONTEXTO:\n" + ctx
                                             + "\nΓ:\n" + gamma, None, base_model)
                            report["cells"].append({
                                "tag": tag, "q": t["q"], "gold": t["gold"],
                                "base_ok": _ok(t["gold"], ans_b),
                                "retrieval_ok": _ok(t["gold"], ans_r),
                                "adapter_ok": False, "adapter_retr_ok": False,
                                "base": ans_b[:120], "adapter": ""})
                        # brazos con adaptador: servidor del adaptador (una carga)
                        for t in tasks:
                            ctx, gamma = ctxs[t["q"]]
                            ans_a = generate(t["q"], adapter, base_model)
                            ans_ar = generate(t["q"] + "\nCONTEXTO:\n" + ctx
                                              + "\nΓ:\n" + gamma, adapter,
                                              base_model)
                            for c in report["cells"]:
                                if c["tag"] == tag and c["q"] == t["q"]:
                                    c["adapter_ok"] = _ok(t["gold"], ans_a)
                                    c["adapter_retr_ok"] = _ok(t["gold"], ans_ar)
                                    c["adapter"] = ans_a[:120]
                        for f in factual:     # I1: hechos DEL usuario
                            ans_b = generate(f["q"], None, base_model, 40)
                            ans_a = generate(f["q"], adapter, base_model, 40)
                            report["cells"].append({
                                "tag": tag, "q": f["q"], "gold": f["gold"],
                                "i1": True,
                                "base_ok": _ok(f["gold"], ans_b),
                                "adapter_ok": _ok(f["gold"], ans_a)})

    if not args.skip_lc6:
        # LC6: olvidar el estilo de mara y re-entrenar sin sus claims
        uid = "mara"
        from lce_validation.fsnames import cache_file
        wp = cache_file(ROOT / "results" / "bench_r13_confirm" / "wikis_cache", uid,
                        CANON, "_wiki.json")
        wiki = Wiki.load(wp, LearningPolicy.load(
            HERE / "fixtures" / "bench_users" / uid / "policy.json"))
        all_rows = [{"messages": [{"role": "user", "content": e.prompt},
                                  {"role": "assistant", "content": e.response}],
                     "_cid": (e.claim_ids[0] if e.claim_ids else None)}
                    for e in ExampleBuilder(wiki).from_claims()
                    if e.kind != "preference_pair"]
        style_ids = {c.claim_id for c in wiki.claims.values()
                     if c.type.name == "STYLE"}
        rows_kept = [r for r in all_rows if r.get("_cid") not in style_ids]
        for fam in fams:
            tag = f"lc6__{uid}__{fam}__s{seeds[0]}"
            adir = OUT / tag
            try:
                adapter = train(BASE[fam], rows_kept, adir, seeds[0], 1.0)
            except RuntimeError as e:
                print(f"  {tag}: falló: {e}")
                continue
            tasks, style_tasks, _ = build_tasks(uid)
            for t in style_tasks:
                ans_b = generate(t["q"], None, BASE[fam])
                ans_a = generate(t["q"], adapter, BASE[fam])
                report["cells"].append({
                    "tag": tag, "q": t["q"], "gold": t["gold"], "lc6": True,
                    "base_ok": _ok(t["gold"], ans_b),
                    "adapter_ok": _ok(t["gold"], ans_a)})

    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    print("\n=== RESUMEN R11 confirmatoria ===")
    cells = [c for c in report["cells"] if not c.get("i1") and not c.get("lc6")
             and not c.get("hc10")]
    by_tag: dict[str, list] = {}
    for c in cells:
        by_tag.setdefault(c["tag"], []).append(c)
    for tag, cs in sorted(by_tag.items()):
        n = len(cs)
        print(f"  {tag}: base {np.mean([c['base_ok'] for c in cs]):.2f} | "
              f"retr+Γ {np.mean([c['retrieval_ok'] for c in cs]):.2f} | "
              f"adapter {np.mean([c['adapter_ok'] for c in cs]):.2f} | "
              f"adapter+retr+Γ {np.mean([c['adapter_retr_ok'] for c in cs]):.2f} "
              f"(n={n})")
    i1 = [c for c in report["cells"] if c.get("i1")]
    if i1:
        d = np.mean([float(c["adapter_ok"]) for c in i1]) - np.mean(
            [float(c["base_ok"]) for c in i1])
        print(f"I1 (fuga de hechos del usuario): adaptador − base = {d:+.3f} "
              f"(equivalencia ±0.10)")
    print(f"\nresultados: {OUT/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
