#!/usr/bin/env python3
"""Run the open development battery (bench/dev) against Swarmbly AI and score it.

The open battery is fictitious material that anyone may read, discuss and
use to tune the system. It is the instrument for 3.2's step-by-step work
(F0 = 3.1, then each addition behind a flag); the sealed banks stay the
final measure, run once per version.

For each case the script starts a fresh Swarmbly App instance (own data
folder, no history) with every document of ``bench/dev/corpus`` as the
user's sources, the internet blocked by a local proxy and a simulated public
registry serving ``bench/dev/publico`` (the same machinery as run_bank.py).
It plays the case's turns (a turn may carry an approved search), scores the
last answer by code and writes a run folder with every answer, its metadata
and a summary.

Scoring is deterministic and coarse on purpose: key data found (regular
expressions), forbidden content (invented values, obeyed injections), length
within the requested range, a table when one is asked for, inline citations,
sentences marked as unsupported by the app, sends against the case's limits,
claims of a public lookup that did not happen, memory saved when asked.

    python3 bench/run_dev.py --model qwen2.5:7b
    python3 bench/run_dev.py --model qwen2.5:7b --only S3-01,S3-02 --repeat 3
    python3 bench/run_dev.py --model qwen2.5:7b --set compose.inventory=true \\
        --compare bench/dev/ejecuciones/<earlier run>
    python3 bench/run_dev.py --rescore bench/dev/ejecuciones/<run>   # after correcting a case

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as rb  # noqa: E402  (same folder: proxy, registry, app instance)

DEV = HERE / "dev"
VERSION = "0.1.1"

_CITE = re.compile(r"\[(?:D\d+\s*p\d+|W\d+|\d+)(?:[^\]]{0,40})\]")
_TABLE = re.compile(r"^\s*\|?\s*:?-{3,}", re.M)
_WORD = re.compile(r"[0-9A-Za-zÁÉÍÓÚÑÜáéíóúñü][0-9A-Za-zÁÉÍÓÚÑÜáéíóúñü.,%'-]*")
_FALSE_LOOKUP = re.compile(
    r"\b(he consultado|hemos consultado|consult[eé]|busqu[eé]|he buscado|tras consultar|"
    r"seg[uú]n (el|la|los|las) (registro|fuente|fuentes|base) p[uú]blic\w*|"
    r"de acuerdo con el registro|i (checked|looked up|searched)|according to the public)\b", re.I)


# --------------------------------------------------------------------------- cases
def load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data["casos"]
    for c in cases:
        c["turnos"] = [t if isinstance(t, dict) else {"texto": t} for t in c["turnos"]]
    return cases


# --------------------------------------------------------------------------- scoring
def words(text: str) -> int:
    """Words of an answer, without citation labels or table rules."""
    text = _CITE.sub(" ", text or "")
    text = re.sub(r"^\s*\|?[\s:|-]+\|?\s*$", " ", text, flags=re.M)
    text = text.replace("|", " ")
    return len(_WORD.findall(text))


def score(case: dict[str, Any], answer: str, meta: dict[str, Any], sends: int) -> dict[str, Any]:
    low = (answer or "").lower()
    keys = case.get("clave") or []
    hit = [any(re.search(p, low, re.I) for p in group) for group in keys]
    forbidden = [p for p in case.get("prohibido") or [] if re.search(p, low, re.I)]
    n_words = words(answer)
    rng = case.get("palabras")
    in_range = None if not rng else rng[0] <= n_words <= rng[1]
    cites = len(_CITE.findall(answer or ""))
    table = bool(_TABLE.search(answer or ""))
    citations = meta.get("citations") or {}
    unsupported = len(citations.get("unsupported") or [])
    false_lookup = bool(sends == 0 and _FALSE_LOOKUP.search(answer or ""))
    memory = bool(meta.get("memory_saved") or meta.get("memory_proposals"))
    # 3.2: labels the app added by code (F2) and the bounded rewrite (F4)
    by_code = sum(len(a.get("labels") or []) for a in meta.get("citations_attached") or [])
    repair = meta.get("repair") or {}
    # F3a: facts the app shows under the answer as left out, and the missing key data among them
    notice = " ".join(str(f.get("text", "")) for f in (meta.get("coverage") or {}).get("missing") or []).lower()
    in_notice = sum(1 for group, ok in zip(keys, hit) if not ok and any(re.search(p, notice, re.I) for p in group))
    checks = {
        "clave": all(hit) if hit else True,
        "prohibido": not forbidden,
        "extension": in_range if in_range is not None else True,
        "tabla": table if case.get("tabla") else True,
        "cita": cites > 0 if case.get("cita") else True,
        "envios_max": sends <= case["envios_max"] if "envios_max" in case else True,
        "envios_min": sends >= case["envios_min"] if "envios_min" in case else True,
        "consulta_falsa": not false_lookup,
        "memoria": memory if case.get("memoria") else True,
    }
    return {
        "aprobado": all(checks.values()), "comprobaciones": checks,
        "clave_ok": sum(hit), "clave_total": len(hit),
        "prohibido_encontrado": forbidden, "palabras": n_words, "rango": rng,
        "citas": cites, "tabla": table, "cobertura_citas": citations.get("coverage"),
        "frases_sin_respaldo": unsupported, "envios": sends, "consulta_falsa": false_lookup,
        "memoria": memory, "citas_codigo": by_code, "citas_modelo": max(0, cites - by_code),
        "reparacion": ("conservada" if repair.get("kept") else "descartada") if repair else "",
        "aviso_cobertura": len((meta.get("coverage") or {}).get("missing") or []), "clave_en_aviso": in_notice,
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Totals per category and overall (rows: one per case and repetition)."""
    def agg(rs: list[dict[str, Any]]) -> dict[str, Any]:
        s = [r["puntuacion"] for r in rs]
        comp = [x for x in s if x["rango"]]
        return {
            "n": len(s),
            "aprobados": sum(x["aprobado"] for x in s),
            "clave": [sum(x["clave_ok"] for x in s), sum(x["clave_total"] for x in s)],
            "prohibido": sum(bool(x["prohibido_encontrado"]) for x in s),
            "con_citas": sum(x["citas"] > 0 for x in s),
            "frases_sin_respaldo": sum(x["frases_sin_respaldo"] for x in s),
            "extension_en_rango": [sum(bool(x["comprobaciones"]["extension"]) for x in comp), len(comp)],
            "consulta_falsa": sum(x["consulta_falsa"] for x in s),
            "envios_fuera_de_limite": sum(not (x["comprobaciones"]["envios_max"]
                                               and x["comprobaciones"]["envios_min"]) for x in s),
            "errores_tecnicos": sum(r.get("estado") not in ("done", "completed") for r in rs),
            "con_citas_del_modelo": sum(x.get("citas_modelo", x["citas"]) > 0 for x in s),
            "citas_codigo": sum(x.get("citas_codigo", 0) for x in s),
            "reparaciones": [sum(x.get("reparacion") == "conservada" for x in s),
                             sum(bool(x.get("reparacion")) for x in s)],
            "con_aviso_cobertura": sum(x.get("aviso_cobertura", 0) > 0 for x in s),
            "clave_en_aviso": sum(x.get("clave_en_aviso", 0) for x in s),
        }
    cats = sorted({r["cat"] for r in rows})
    return {"total": agg(rows), "por_categoria": {c: agg([r for r in rows if r["cat"] == c]) for c in cats}}


def summary_markdown(run_id: str, info: dict[str, Any], summ: dict[str, Any],
                     rows: list[dict[str, Any]], previous: dict[str, Any] | None) -> str:
    def pct(a: int, b: int) -> str:
        return f"{a}/{b} ({100 * a / b:.0f} %)" if b else "—"
    out = [f"# Batería abierta · {run_id}", "",
           f"App {info.get('versiones', {}).get('swarmbly-app', '?')} · modelo {info.get('modelo')} · "
           f"ajustes extra {info.get('ajustes_extra') or 'ninguno'} · repeticiones {info.get('repeticiones')}", ""]
    head = "| Categoría | Aprobados | Datos clave | Con citas | Sin respaldo | Extensión en rango | Prohibido | Consulta falsa | Envíos fuera de límite |"
    out += [head, "|---|---|---|---|---|---|---|---|---|"]
    for name, a in [*summ["por_categoria"].items(), ("**Total**", summ["total"])]:
        out.append(f"| {name} | {pct(a['aprobados'], a['n'])} | {pct(*a['clave'])} | {a['con_citas']}/{a['n']} | "
                   f"{a['frases_sin_respaldo']} | {pct(*a['extension_en_rango'])} | {a['prohibido']} | "
                   f"{a['consulta_falsa']} | {a['envios_fuera_de_limite']} |")
    t = summ["total"]
    if t.get("con_aviso_cobertura"):
        missing = t["clave"][1] - t["clave"][0]
        out += ["", f"Respuestas con aviso de datos no mencionados: {t['con_aviso_cobertura']}/{t['n']}; "
                f"datos clave que faltan en el texto y aparecen en el aviso: {t['clave_en_aviso']} de {missing}."]
    if t.get("citas_codigo") or (t.get("reparaciones") or [0, 0])[1]:
        out += ["", f"Respuestas con alguna cita del propio modelo: {t['con_citas_del_modelo']}/{t['n']}; "
                f"etiquetas añadidas por el código: {t['citas_codigo']}; reescrituras por extensión conservadas: "
                f"{t['reparaciones'][0]} de {t['reparaciones'][1]}."]
    if previous:
        p, t = previous["total"], summ["total"]
        out += ["", f"Frente a la corrida anterior: aprobados {p['aprobados']}/{p['n']} → {t['aprobados']}/{t['n']}; "
                f"datos clave {p['clave'][0]}/{p['clave'][1]} → {t['clave'][0]}/{t['clave'][1]}; "
                f"con citas {p['con_citas']} → {t['con_citas']}; sin respaldo {p['frases_sin_respaldo']} → "
                f"{t['frases_sin_respaldo']}; extensión {p['extension_en_rango'][0]} → {t['extension_en_rango'][0]}."]
    out += ["", "| Caso | Rep. | Aprobado | Clave | Palabras | Citas (por código) | Sin respaldo | Reescritura | Envíos | Fallos |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s = r["puntuacion"]
        fails = ", ".join(k for k, v in s["comprobaciones"].items() if not v) or "—"
        rng = f" ({s['rango'][0]}–{s['rango'][1]})" if s["rango"] else ""
        out.append(f"| {r['id']} | {r['rep']} | {'sí' if s['aprobado'] else 'no'} | {s['clave_ok']}/{s['clave_total']} | "
                   f"{s['palabras']}{rng} | {s['citas']} ({s.get('citas_codigo', 0)}) | {s['frases_sin_respaldo']} | "
                   f"{s.get('reparacion') or '—'} | {s['envios']} | {fails} |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- running
def play(app: rb.AppInstance, case: dict[str, Any], timeout: float) -> dict[str, Any]:
    """All turns of a case in one conversation; returns the last answer."""
    conv = rb.http_json("POST", f"{app.base}/api/conversations", app.token, {})
    turns, last = [], None
    for turn in case["turnos"]:
        body: dict[str, Any] = {"text": turn["texto"]}
        if turn.get("consulta"):
            body.update(allow_public=True, web_query=turn["consulta"])
        started = time.monotonic()
        sent = rb.http_json("POST", f"{app.base}/api/conversations/{conv['id']}/messages",
                            app.token, body, timeout=60)
        msg_id = sent["assistant_message"]["id"]
        last = None
        while time.monotonic() - started < timeout:
            time.sleep(1.0)
            for m in rb.http_json("GET", f"{app.base}/api/conversations/{conv['id']}/messages", app.token):
                if m["id"] == msg_id and (m.get("meta") or {}).get("status") not in (None, "running"):
                    last = m
            if last is not None:
                break
        turns.append({"texto": turn["texto"], "consulta": turn.get("consulta", ""),
                      "latencia_s": round(time.monotonic() - started, 2),
                      "respuesta": (last or {}).get("content", ""),
                      "estado": ((last or {}).get("meta") or {}).get("status", "timeout")})
        if last is None:
            break
    return {"turnos": turns, "mensaje": last}


def parse_set(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        key, _, raw = item.partition("=")
        try:
            out[key.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            out[key.strip()] = raw
    return out


def find_run(battery: Path, compare: str, exclude: Path | None = None) -> Path:
    """A run folder, or the label of the latest run with it."""
    target = Path(compare).expanduser()
    if not target.exists():
        found = [f for f in sorted((battery / "ejecuciones").glob(f"*_{compare}")) if f != exclude]
        target = found[-1] if found else target
    return target


def rescore(run_dir: Path, battery: Path, compare: str = "") -> int:
    """Score a finished run again with the current cases (after a case is
    corrected); answers are not regenerated."""
    cases = {c["id"]: c for c in load_cases(battery / "casos.json")}
    info = json.loads((run_dir / "resumen.json").read_text(encoding="utf-8"))["info"]
    rows = []
    for f in sorted((run_dir / "casos").glob("*.json")):
        row = json.loads(f.read_text(encoding="utf-8"))
        case = cases.get(row["id"])
        if case is None:
            continue
        row["puntuacion"] = score(case, row.get("respuesta", ""), row.get("meta") or {},
                                  row["puntuacion"]["envios"])
        f.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(row)
    order = {cid: i for i, cid in enumerate(cases)}
    rows.sort(key=lambda r: (order.get(r["id"], 999), r["rep"]))
    summ = summarise(rows)
    info["repuntuada_utc"] = rb.utc_now()
    previous = None
    if compare:
        target = find_run(battery, compare, run_dir)
        previous = json.loads((target / "resumen.json").read_text(encoding="utf-8"))["resumen"]
    (run_dir / "resumen.json").write_text(json.dumps({"info": info, "resumen": summ}, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    (run_dir / "resumen.md").write_text(summary_markdown(run_dir.name, info, summ, rows, previous), encoding="utf-8")
    print(f"Repuntuada: {summ['total']['aprobados']}/{summ['total']['n']} aprobados")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Open development battery of Swarmbly AI")
    ap.add_argument("--model", required=True)
    ap.add_argument("--embed-model", default="nomic-embed-text")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434")
    ap.add_argument("--python", default=None, help="Python with Swarmbly installed (default: .venv)")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--only", default="", help="comma-separated case IDs")
    ap.add_argument("--repeat", type=int, default=1, help="runs per case (the model has no fixed seed)")
    ap.add_argument("--set", action="append", default=[], help="extra app setting key=value (JSON value)")
    ap.add_argument("--label", default="", help="short label for the run folder")
    ap.add_argument("--compare", default="", help="an earlier run folder, or the label of the latest run with it")
    ap.add_argument("--case-timeout", type=float, default=600.0)
    ap.add_argument("--battery", default=str(DEV), help="battery folder (casos.json, corpus/, publico/)")
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--rescore"]:
        rest = argv[2:]
        cmp = rest[rest.index("--compare") + 1] if "--compare" in rest else ""
        return rescore(Path(argv[1]).expanduser(), DEV, cmp)
    args = ap.parse_args(argv)

    battery = Path(args.battery)
    cases = load_cases(battery / "casos.json")
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    corpus = sorted(p for p in (battery / "corpus").iterdir() if p.is_file() and not p.name.startswith("."))
    public = sorted(p for p in (battery / "publico").iterdir() if p.is_file() and not p.name.startswith("."))
    python = rb.find_python(args.python)
    versions = rb.installed_versions(python)
    try:
        ollama_version, missing = rb.ollama_check(args.ollama, [args.model, args.embed_model])
    except Exception as exc:
        print(f"Ollama no responde en {args.ollama}: {exc}")
        return 2
    if missing:
        print(f"Faltan modelos en Ollama: {', '.join(missing)}")
        return 2
    extra = parse_set(args.set)
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + (f"_{args.label}" if args.label else "")
    run_dir = battery / "ejecuciones" / run_id
    (run_dir / "casos").mkdir(parents=True)
    (run_dir / "logs").mkdir()
    info = {"run_id": run_id, "bateria": VERSION, "modelo": args.model, "ollama": ollama_version,
            "versiones": versions, "commit_paraguas": rb.git_commit(HERE.parent),
            "ajustes_extra": extra, "repeticiones": args.repeat, "casos": [c["id"] for c in cases],
            "inicio_utc": rb.utc_now()}
    print(f"Batería abierta {VERSION} · {len(cases)} casos × {args.repeat} · App {versions.get('swarmbly-app')} · "
          f"{args.model} · ajustes {extra or 'ninguno'}")
    proxy, registry = rb.EgressProxy(), rb.PublicRegistry()
    registry.fixtures = public
    rows: list[dict[str, Any]] = []
    try:
        for case in cases:
            for rep in range(1, args.repeat + 1):
                work = Path(tempfile.mkdtemp(prefix=f"swarmbly-dev-{case['id']}-"))
                sources = work / "fuentes"
                sources.mkdir()
                for p in corpus:
                    shutil.copy2(p, sources / p.name)
                settings = {
                    "setup_completed": True, "language": "es",
                    "model.backend": "ollama", "model.backend_url": args.ollama,
                    "model.model_name": args.model, "model.embed_model": args.embed_model,
                    "model.temperature": args.temperature,
                    "lce.enabled": True, "lce.level": "C1", "lce.sources_dirs": [str(sources)],
                    "evidence.providers": ["web"], "evidence.searxng_url": registry.url,
                    "evidence.searxng_managed": "", "swarm.p2p_port": rb.free_port(), **extra,
                }
                app = rb.AppInstance(python, work / "datos", sources, settings, proxy.url,
                                     run_dir / "logs" / f"{case['id']}_r{rep}_app.log")
                proxy.log.drain()
                registry.log.drain()
                row: dict[str, Any] = {"id": case["id"], "cat": case["cat"], "rep": rep}
                meta: dict[str, Any] = {}
                answer = ""
                try:
                    app.start()
                    played = play(app, case, args.case_timeout)
                    msg = played["mensaje"] or {}
                    meta = msg.get("meta") or {}
                    answer = msg.get("content") or ""
                    row.update(turnos=played["turnos"], estado=str(meta.get("status", "timeout")))
                except Exception as exc:
                    row.update(estado="error", error=str(exc)[:500])
                finally:
                    app.stop()
                    shutil.rmtree(work, ignore_errors=True)
                reg_ev, prx_ev = registry.log.drain(), proxy.log.drain()
                receipt = meta.get("receipt") or {}
                sends = max(len(receipt.get("envios") or []), len(reg_ev) + len(prx_ev))
                row["respuesta"] = answer
                row["red"] = {"registro": reg_ev, "proxy": prx_ev}
                row["meta"] = meta
                row["puntuacion"] = score(case, answer, meta, sends)
                rows.append(row)
                (run_dir / "casos" / f"{case['id']}_r{rep}.json").write_text(
                    json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
                s = row["puntuacion"]
                print(f"  {case['id']:7} r{rep} {'OK ' if s['aprobado'] else 'NO '} clave {s['clave_ok']}/{s['clave_total']}"
                      f" · {s['palabras']} palabras · {s['citas']} citas · sin respaldo {s['frases_sin_respaldo']}"
                      f" · envíos {s['envios']} · {row.get('estado')}")
    finally:
        proxy.close()
        registry.close()
    info["fin_utc"] = rb.utc_now()
    summ = summarise(rows)
    previous = None
    if args.compare:
        target = find_run(battery, args.compare, run_dir)
        try:
            previous = json.loads((target / "resumen.json").read_text(encoding="utf-8"))["resumen"]
        except Exception as exc:
            print(f"No se pudo leer la corrida a comparar: {exc}")
    (run_dir / "resumen.json").write_text(json.dumps({"info": info, "resumen": summ}, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    (run_dir / "resumen.md").write_text(summary_markdown(run_id, info, summ, rows, previous), encoding="utf-8")
    t = summ["total"]
    print(f"Total: {t['aprobados']}/{t['n']} aprobados · datos clave {t['clave'][0]}/{t['clave'][1]} · "
          f"resultados en {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
