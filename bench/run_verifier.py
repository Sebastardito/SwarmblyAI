#!/usr/bin/env python3
"""Measure the claim verifier (3.3, recipe 3) on the open set of claims.

``bench/dev/verificador.json`` holds sentences with the paragraphs they cite
and a gold label: "si" when the cited paragraphs (with the title of their
document) say everything the sentence states, "no" when they do not, say
only a part, or say something else. Part of the sentences are real answers of
a 7B model in the open battery, read by hand; the rest were written by hand
over the same fictitious corpus.

For each model the script reports, as a verifier:

- the code alone (figures that are not in the cited paragraphs, a cited
  paragraph that shares no word with the sentence);
- the model alone, one short job per sentence (SÍ / PARTE / NO);
- both, the code first: what the app does.

A sentence is flagged when the verdict is not SÍ. Two numbers matter: how
many of the unsupported sentences are flagged, and how many supported ones
are flagged by mistake.

    python3 bench/run_verifier.py --model qwen2.5:7b
    python3 bench/run_verifier.py --model qwen2.5:7b,qwen2.5:14b --repeat 2 --label v1

Needs Ollama running with the models. Standard library only; the verifier is
read from the SwarmblyApp folder next to ``bench`` (or the installed package).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEV = HERE / "dev"
VERSION = "0.1.0"
WORDS = {"yes": "SÍ", "partly": "PARTE", "no": "NO"}
if (HERE.parent / "SwarmblyApp" / "swarmbly_app" / "verify.py").exists():
    sys.path.insert(0, str(HERE.parent / "SwarmblyApp"))


def load(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["afirmaciones"]
    for it in items:
        assert it["oro"] in ("si", "no"), it["id"]
        assert it["afirmacion"] and it["pasajes"], it["id"]
    return items


def sources(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"label": p["etiqueta"], "doc_title": p.get("titulo", ""), "rel": p.get("documento", ""),
             "text": p["texto"]} for p in item["pasajes"]]


class Ollama:
    def __init__(self, url: str, model: str, timeout: float = 120.0):
        self.url, self.model, self.timeout = url.rstrip("/"), model, timeout
        self.think: bool | None = False      # reasoning models answer in one word only without thinking

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def generate(self, prompt: str, max_tokens: int) -> str:
        body: dict[str, Any] = {"model": self.model, "stream": False,
                                "messages": [{"role": "user", "content": prompt}],
                                "options": {"temperature": 0, "num_predict": max_tokens}}
        if self.think is not None:
            body["think"] = self.think
        try:
            out = self._post(body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if self.think is not None and "think" in detail.lower():
                self.think = None            # a model without reasoning: ask again without the field
                return self.generate(prompt, max_tokens)
            raise RuntimeError(f"Ollama {exc.code}: {detail[:200]}") from exc
        return str((out.get("message") or {}).get("content") or "")


def measure(items: list[dict[str, Any]], generate: Any, verify: Any) -> list[dict[str, Any]]:
    """Each claim checked by the code, by the model, and by both."""
    rows = []
    for it in items:
        src = sources(it)
        split = verify.split(it["afirmacion"])
        labels = split[0]["labels"] if split else [p["etiqueta"] for p in it["pasajes"]]
        code = verify.check(it["afirmacion"], labels, src)
        t0 = time.monotonic()
        raw = generate(verify.prompt(it["afirmacion"], labels, src, "es"), 6)
        seconds = time.monotonic() - t0
        verdict = verify.parse(raw)
        by_code = code["ok"] is False
        by_model = verdict is not None and verdict != verify.YES
        rows.append({"id": it["id"], "oro": it["oro"], "tipo": it.get("tipo", ""),
                     "codigo": code.get("why", "") if by_code else "", "modelo": verdict or "",
                     "respuesta": raw.strip()[:40], "segundos": round(seconds, 2),
                     "marcada_codigo": by_code, "marcada_modelo": by_model,
                     "marcada": by_code or by_model, "sin_veredicto": verdict is None})
    return rows


def tally(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    no = [r for r in rows if r["oro"] == "no"]
    si = [r for r in rows if r["oro"] == "si"]
    caught = sum(1 for r in no if r[key])
    false = sum(1 for r in si if r[key])
    return {"no": len(no), "detectadas": caught, "si": len(si), "falsas": false,
            "aciertos": caught + len(si) - false, "total": len(rows)}


def summarise(model: str, runs: list[list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [r for run in runs for r in run]
    kinds: dict[str, list[int]] = {}
    for r in rows:
        if r["oro"] == "no":
            k = kinds.setdefault(r["tipo"] or "otro", [0, 0])
            k[0] += 1
            k[1] += r["marcada"]
    return {"modelo": model, "repeticiones": len(runs),
            "codigo": tally(rows, "marcada_codigo"), "solo_modelo": tally(rows, "marcada_modelo"),
            "ambos": tally(rows, "marcada"), "por_tipo": kinds,
            "sin_veredicto": sum(r["sin_veredicto"] for r in rows),
            "segundos_por_frase": round(sum(r["segundos"] for r in rows) / max(1, len(rows)), 2)}


def line(name: str, t: dict[str, Any]) -> str:
    def pct(a: int, b: int) -> str:
        return f"{a}/{b} ({round(100 * a / b)} %)" if b else "—"
    return (f"| {name} | {pct(t['detectadas'], t['no'])} | {pct(t['falsas'], t['si'])} | "
            f"{pct(t['aciertos'], t['total'])} |")


def report(stamp: str, n_items: int, summaries: list[dict[str, Any]], runs: dict[str, list[list[dict[str, Any]]]],
           items: list[dict[str, Any]]) -> str:
    out = [f"# Verificador de afirmaciones · {stamp}", "",
           f"Conjunto abierto `bench/dev/verificador.json`: {n_items} frases "
           f"({sum(1 for i in items if i['oro'] == 'no')} sin respaldo, "
           f"{sum(1 for i in items if i['oro'] == 'si')} respaldadas). Una frase queda marcada cuando el "
           "veredicto no es SÍ.", ""]
    for s in summaries:
        out += [f"## {s['modelo']}", "",
                f"Repeticiones: {s['repeticiones']} · segundos por frase: {s['segundos_por_frase']} · "
                f"respuestas sin veredicto: {s['sin_veredicto']}", "",
                "| Quién comprueba | Sin respaldo detectadas | Respaldadas marcadas por error | Aciertos |",
                "|---|---|---|---|",
                line("Solo el código", s["codigo"]), line("Solo el modelo", s["solo_modelo"]),
                line("Código y modelo", s["ambos"]), "",
                "Sin respaldo detectadas (código y modelo), por tipo: "
                + "; ".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(s["por_tipo"].items())) + ".", ""]
        wrong = [r for r in runs[s["modelo"]][0] if (r["oro"] == "no") != r["marcada"]]
        if wrong:
            by_id = {i["id"]: i for i in items}
            out += ["Fallos de la primera repetición:", ""]
            out += [f"- `{r['id']}` (oro: {r['oro']}, {r['tipo'] or '—'}; modelo: {WORDS.get(r['modelo'], 'sin veredicto')}): "
                    f"{by_id[r['id']]['afirmacion'][:140]}" for r in wrong]
            out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True, help="one model or several, comma-separated")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--label", default="")
    ap.add_argument("--set", dest="path", default=str(DEV / "verificador.json"), help="the set of claims")
    ap.add_argument("--out", default=str(DEV / "ejecuciones"))
    args = ap.parse_args(argv)
    venv = HERE.parent / ".venv" / "bin" / "python"
    if sys.version_info < (3, 10) and venv.exists() and not os.environ.get("SWARMBLY_VERIFIER_REEXEC"):
        os.environ["SWARMBLY_VERIFIER_REEXEC"] = "1"     # the app needs Python 3.10 or later
        os.execv(str(venv), [str(venv), str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:])])
    try:
        from swarmbly_app import verify
    except ImportError as exc:
        print(f"No encuentro swarmbly_app.verify ({exc}). Ejecuta el script desde el repositorio de Swarmbly AI "
              "o con el Python que tiene Swarmbly instalado.", file=sys.stderr)
        return 2
    items = load(Path(args.path))
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_verificador" + (f"_{args.label}" if args.label else "")
    runs: dict[str, list[list[dict[str, Any]]]] = {}
    summaries = []
    for model in [m.strip() for m in args.model.split(",") if m.strip()]:
        backend = Ollama(args.ollama, model)
        try:
            backend.generate("Responde solo: SÍ", 4)      # loads the model, outside the timing
        except Exception as exc:
            print(f"{model}: no responde ({exc})", file=sys.stderr)
            continue
        runs[model] = []
        for n in range(max(1, args.repeat)):
            print(f"{model} · repetición {n + 1} · {len(items)} frases…", flush=True)
            runs[model].append(measure(items, backend.generate, verify))
        summaries.append(summarise(model, runs[model]))
    if not summaries:
        return 1
    folder = Path(args.out) / stamp
    folder.mkdir(parents=True, exist_ok=True)
    text = report(stamp, len(items), summaries, runs, items)
    (folder / "resumen.md").write_text(text, encoding="utf-8")
    (folder / "resumen.json").write_text(json.dumps(
        {"version": VERSION, "conjunto": len(items), "resumen": summaries, "corridas": runs},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + text)
    print(f"Guardado en {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
