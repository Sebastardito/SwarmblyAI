#!/usr/bin/env python3
"""Run an open development battery against Swarmbly AI and score it.

The open battery is fictitious material that anyone may read, discuss and
use to tune the system. It is the instrument for 3.2's step-by-step work
(F0 = 3.1, then each addition behind a flag); the sealed banks stay the
final measure, run once per version.

A battery whose cases carry ``expected_items`` is a recipe 4 (list) battery:
the case is driven through ``/api/recipes/list/preview`` and then a local
``recipe: "list"`` message, and scored on the table it returns (order, stable
ids, duplicates, status column, per-cell regex, preview privacy and zero
sends).  ``bench/dev_list`` is the open battery for that recipe.

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
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_bank as rb  # noqa: E402  (same folder: proxy, registry, app instance)

DEV = HERE / "dev"
VERSION = "0.5.0"
LIST_VERSION = "0.1.0"
CODE_VERSION = "0.1.0"

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
        c["turnos"] = [t if isinstance(t, dict) else {"texto": t}
                       for t in c.get("turnos", [])]
    return cases


def corpus_files(battery: Path, case: dict[str, Any]) -> list[Path]:
    """The source files this case sees.

    Without a ``corpus`` field the whole ``corpus/`` folder is copied, which
    keeps every existing case unchanged.  A case may instead list paths
    relative to the battery (``"corpus": ["documentos/ficha.md"]``), so a
    document that only one case needs cannot leak into the others.
    """
    rels = case.get("corpus")
    if rels is None:
        return sorted(p for p in (battery / "corpus").iterdir()
                      if p.is_file() and not p.name.startswith("."))
    files: list[Path] = []
    for rel in rels:
        path = (battery / str(rel)).resolve()
        if not path.is_file():
            raise SystemExit(f"corpus file not found for {case['id']}: {rel}")
        files.append(path)
    return files


def is_list_case(case: dict[str, Any]) -> bool:
    """A recipe 4 case: the expected per-item cells are fixed in the file."""
    return "expected_items" in case


# --------------------------------------------------------------------------- scoring
def words(text: str) -> int:
    """Words of an answer, without citation labels or table rules."""
    text = _CITE.sub(" ", text or "")
    text = re.sub(r"^\s*\|?[\s:|-]+\|?\s*$", " ", text, flags=re.M)
    text = text.replace("|", " ")
    return len(_WORD.findall(text))


def score(case: dict[str, Any], answer: str, meta: dict[str, Any], sends: int,
          red: dict[str, Any] | None = None) -> dict[str, Any]:
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
    notice = " ".join([str(f.get("text", "")) for f in (meta.get("coverage") or {}).get("missing") or []]
                      + [str(c[k].get("text", "")) for c in meta.get("conflicts") or [] for k in ("a", "b")]).lower()
    in_notice = sum(1 for group, ok in zip(keys, hit) if not ok and any(re.search(p, notice, re.I) for p in group))
    # what left this computer (registry queries and refused outbound requests)
    sent_text = " ".join(str(e.get("q", "")) + " " + json.dumps(e, ensure_ascii=False)
                         for e in (red or {}).get("registro", []) + (red or {}).get("proxy", [])).lower()
    leaked = [p for p in case.get("envio_prohibido") or [] if re.search(r"\b" + p + r"\b", sent_text, re.I)]
    receipt = meta.get("receipt") or {}
    blocked = bool(receipt.get("bloqueados")) and meta.get("status") == "failed"
    # 0.5.0: what the app proposes under "Buscar en línea" (not sent until approved)
    offer = " ".join([str((meta.get("web_offer") or {}).get("query") or ""),
                      *[str(e) for e in (meta.get("public_offer") or {}).get("entities") or []]]).strip()
    offered = [p for p in case.get("oferta_prohibida") or [] if re.search(p, offer, re.I)]
    table_meta = meta.get("table") or {}
    checks = {
        "clave": all(hit) if hit else True,
        "envio_prohibido": not leaked,
        "bloqueo": blocked if case.get("espera_bloqueo") else True,
        "prohibido": not forbidden,
        "extension": in_range if in_range is not None else True,
        "tabla": table if case.get("tabla") else True,
        "cita": cites > 0 if case.get("cita") else True,
        "envios_max": sends <= case["envios_max"] if "envios_max" in case else True,
        "envios_min": sends >= case["envios_min"] if "envios_min" in case else True,
        "consulta_falsa": not false_lookup,
        "memoria": memory if case.get("memoria") else True,
        "oferta_prohibida": not offered,
    }
    # 0.2.1: the requested length is a notice, not a fail (a paragraph with every
    # figure the sources give is not wrong for being short); both are kept
    return {
        "aprobado": all(v for k, v in checks.items() if k != "extension"),
        "aprobado_con_extension": all(checks.values()), "comprobaciones": checks,
        "clave_ok": sum(hit), "clave_total": len(hit),
        "prohibido_encontrado": forbidden, "palabras": n_words, "rango": rng,
        "citas": cites, "tabla": table, "cobertura_citas": citations.get("coverage"),
        "frases_sin_respaldo": unsupported, "envios": sends, "consulta_falsa": false_lookup,
        "memoria": memory, "citas_codigo": by_code, "citas_modelo": max(0, cites - by_code),
        "reparacion": ("conservada" if repair.get("kept") else "descartada") if repair else "",
        "aviso_cobertura": len((meta.get("coverage") or {}).get("missing") or []), "clave_en_aviso": in_notice,
        "envio_prohibido_encontrado": leaked, "bloqueo_esperado": bool(case.get("espera_bloqueo")),
        # 3.3: a table built by code, and numeric cells that are in no passage
        "tabla_por_codigo": bool(table_meta.get("by_code", bool(table_meta))) if table_meta else False,
        "tabla_sin_codigo_motivo": "" if table_meta.get("by_code", True) else str(table_meta.get("reason", "")),
        "tabla_correcciones": len(table_meta.get("corrections") or []),
        "oferta": offer, "oferta_prohibida_encontrada": offered,
        "celdas_sin_respaldo": len((meta.get("table_audit") or {}).get("unsupported") or []),
        "celdas": int((meta.get("table_audit") or {}).get("cells") or 0),
        # 3.3: labelled sentences checked against what they cite
        "verificadas": int((meta.get("verification") or {}).get("claims") or 0),
        "sin_respaldo_de_su_cita": len((meta.get("verification") or {}).get("flagged") or []),
        "citas_completadas": len((meta.get("verification") or {}).get("completed") or []),
        "verificacion_s": float((meta.get("verification") or {}).get("seconds") or 0),
    }


# --------------------------------------------------------------------------- list scoring
def list_preview_payload(case: dict[str, Any]) -> dict[str, Any]:
    """The body of ``POST /api/recipes/list/preview`` for one case.

    A pasted case sends its raw text (blank lines included); a CSV case sends
    only the file and column, so the App itself resolves and reads the file.
    """
    source = case.get("source") or {"kind": "pasted"}
    return {
        "items": "" if source.get("kind") == "csv" else case.get("items", ""),
        "operation": case.get("operation", ""),
        "where": case.get("preview_where", "local"),
        "source": source,
    }


def _expected_duplicates(case: dict[str, Any]) -> dict[int, int]:
    return {int(d["n"]): int(d["of"]) for d in case.get("expected_duplicates") or []}


def score_list(case: dict[str, Any], preview: dict[str, Any], meta: dict[str, Any],
               sends: int, red: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score one recipe 4 answer against the cells fixed in the case file.

    A wrong row, a reordered table, an invented value where the case expects
    ``missing`` and a non-zero send each fail a named check; the cell count is
    reported apart so a partially correct table is visible.
    """
    preview = preview or {}
    meta = meta or {}
    table = meta.get("table") or {}
    list_meta = meta.get("list") or {}
    receipt = meta.get("receipt") or {}
    rows = table.get("rows_data") or []
    expected_items = [str(x) for x in case.get("expected_items") or []]
    expected = list(case.get("expected") or [])
    expected_dups = _expected_duplicates(case)
    total = len(expected)
    by_n = {r.get("n"): r for r in rows
            if isinstance(r, dict) and isinstance(r.get("n"), int)}
    got_dups = {n: d.get("duplicate_of") for n, d in by_n.items()
                if d.get("duplicate_of")}
    ids = [r.get("n") for r in rows if isinstance(r, dict)]
    got_items = [str(r.get("item") or "") for r in rows if isinstance(r, dict)]

    def duplicate_marked(n: int, of: int) -> bool:
        row = by_n.get(n) or {}
        cell = str(row.get("item_cell") or "").lower()
        return row.get("duplicate_of") == of and f"#{of}" in cell and (
            "duplicad" in cell or "duplicate" in cell)

    header = table.get("header") or []
    cells = table.get("cells") or []
    column_ok = (
        len(header) == 4
        and str(header[-1]).strip().lower() in ("estado", "status")
        and len(cells) == total
        and all(isinstance(c, list) and len(c) == 4 for c in cells)
        and all(str(c[3]) in ("answered", "missing", "disagreement") for c in cells)
        and all(str(c[0]) == str(i) and str(c[1]) == str((by_n.get(i) or {}).get("item_cell"))
                for i, c in enumerate(cells, 1))
    )

    cell_ok, failures = 0, []
    for n, (row, wanted) in enumerate(zip(rows, expected), 1):
        value = str((row or {}).get("answer") or "").strip()
        status = str((row or {}).get("status") or "")
        if wanted is None:
            ok = status == "missing" and value == "—"
        else:
            ok = (status == "answered" and value not in ("", "—")
                  and bool(re.search(str(wanted), value, re.I)))
        cell_ok += int(ok)
        if not ok:
            failures.append({"n": n, "esperado": wanted if wanted is not None else "missing",
                             "valor": value or "", "estado": status})

    missing_expected = sum(1 for x in expected if x is None)
    answered_expected = total - missing_expected
    waves = int(case.get("expected_waves") or 1)
    meta_ok = (
        list_meta.get("count") == total
        and list_meta.get("answered") == answered_expected
        and list_meta.get("missing") == missing_expected
        and list_meta.get("disagreement") == 0
        and list_meta.get("where") == "local"
        and list_meta.get("executed") == "local"
        and list_meta.get("waves") == waves
        and list_meta.get("duplicates") == len(expected_dups)
        and table.get("rows") == total
        and table.get("empty") == missing_expected
        and table.get("duplicates") == len(expected_dups)
    )

    preview_items = [str(x) for x in preview.get("items") or []]
    leaves = preview.get("what_leaves") or {}
    preview_ok = (
        preview_items == expected_items
        and preview.get("count") == total
        and preview.get("duplicates") == len(expected_dups)
        and leaves.get("count") == total
        and [str(x) for x in leaves.get("items") or []] == expected_items
    )
    if case.get("preview_local_only"):
        privacy = preview.get("privacy") or {}
        preview_ok = preview_ok and (
            preview.get("default_where") == "local"
            and bool(str(preview.get("local_only_reason") or "").strip())
            and privacy.get("sensitive") is True
            and bool(privacy.get("items_flagged"))
        )

    observed = len((red or {}).get("registro") or []) + len((red or {}).get("proxy") or [])
    checks = {
        "tabla_por_codigo": table.get("by_code") is True,
        "filas": len(rows) == total and ids == list(range(1, total + 1))
                 and got_items == expected_items,
        "duplicados": got_dups == expected_dups
                      and all(duplicate_marked(n, of) for n, of in expected_dups.items())
                      and table.get("duplicates") == len(expected_dups),
        "columnas": column_ok,
        "celdas": cell_ok == total and total > 0,
        "metadatos": meta_ok,
        "vista_previa": preview_ok,
        "recibo": receipt.get("recipe") == "list" and receipt.get("recipe_where") == "local",
        "envios": sends == 0 and observed == 0 and not (receipt.get("envios") or []),
    }
    return {
        "aprobado": all(checks.values()), "comprobaciones": checks,
        "celdas_ok": cell_ok, "celdas_total": total, "celdas_fallidas": failures,
        "faltantes": missing_expected, "filas": len(rows),
        "duplicados": len(expected_dups), "envios": sends,
        "vista_previa_default": preview.get("default_where"),
    }


def _list_agg(rs: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["puntuacion"] for r in rs]
    names = sorted({k for s in scores for k in (s.get("comprobaciones") or {})})
    return {
        "n": len(scores),
        "aprobados": sum(bool(s.get("aprobado")) for s in scores),
        "celdas": [sum(int(s.get("celdas_ok") or 0) for s in scores),
                   sum(int(s.get("celdas_total") or 0) for s in scores)],
        "por_comprobacion": {
            name: [sum(bool((s.get("comprobaciones") or {}).get(name)) for s in scores), len(scores)]
            for name in names
        },
        "faltantes": sum(int(s.get("faltantes") or 0) for s in scores),
        "envios": sum(int(s.get("envios") or 0) for s in scores),
        "latencia_media_s": round(
            sum(float((r.get("turnos") or [{}])[-1].get("latencia_s") or 0) for r in rs)
            / max(1, len(rs)), 1),
    }


def summarise_list(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Totals overall, per category, per check and per case (rows = reps)."""
    categories = sorted({r["cat"] for r in rows})
    cases = sorted({r["id"] for r in rows})
    return {
        "total": _list_agg(rows),
        "por_categoria": {c: _list_agg([r for r in rows if r["cat"] == c]) for c in categories},
        "por_caso": {
            cid: {
                "n": len([r for r in rows if r["id"] == cid]),
                "aprobados": sum(bool(r["puntuacion"].get("aprobado"))
                                 for r in rows if r["id"] == cid),
                "celdas": [
                    sum(int(r["puntuacion"].get("celdas_ok") or 0)
                        for r in rows if r["id"] == cid),
                    sum(int(r["puntuacion"].get("celdas_total") or 0)
                        for r in rows if r["id"] == cid),
                ],
            }
            for cid in cases
        },
    }


def list_summary_markdown(run_id: str, info: dict[str, Any], summ: dict[str, Any],
                          rows: list[dict[str, Any]],
                          previous: dict[str, Any] | None) -> str:
    def pct(a: int, b: int) -> str:
        return f"{a}/{b} ({100 * a / b:.0f} %)" if b else "—"
    t = summ["total"]
    out = [
        f"# Batería abierta de listas · {run_id}", "",
        f"App {info.get('versiones', {}).get('swarmbly-app', '?')} · modelo {info.get('modelo')} · "
        f"n={info.get('repeticiones')} por caso · batería abierta, no una medición sellada.", "",
        "## Total", "",
        f"- Casos aprobados: {pct(t['aprobados'], t['n'])}",
        f"- Celdas correctas: {pct(*t['celdas'])}",
        f"- Valores faltantes esperados encontrados: {t['faltantes']}",
        f"- Envíos observados: {t['envios']}",
        f"- Latencia media por caso: {t['latencia_media_s']} s", "",
        "## Comprobaciones", "", "| Comprobación | Aprobadas |", "|---|---|",
    ]
    for name, (ok, n) in sorted(t["por_comprobacion"].items()):
        out.append(f"| {name} | {pct(ok, n)} |")
    out += ["", "## Por caso", "", "| Caso | Reps | Aprobados | Celdas |", "|---|---|---|---|"]
    for cid, data in summ["por_caso"].items():
        out.append(f"| {cid} | {data['n']} | {data['aprobados']}/{data['n']} | "
                   f"{pct(*data['celdas'])} |")
    out += ["", "## Fallos", "", "| Caso | Rep. | Comprobaciones | Celdas fallidas |",
            "|---|---|---|---|"]
    any_failure = False
    for r in rows:
        s = r["puntuacion"]
        failed = [k for k, v in s["comprobaciones"].items() if not v]
        cells = "; ".join(
            f"#{f['n']} esperado {f['esperado']} valor {f['valor'] or '—'} ({f['estado']})"
            for f in s.get("celdas_fallidas") or [])
        if failed or cells:
            any_failure = True
            out.append(f"| {r['id']} | {r['rep']} | {', '.join(failed) or '—'} | {cells or '—'} |")
    if not any_failure:
        out.append("| — | — | — | — |")
    if previous:
        p = previous["total"]
        out += ["", f"Frente a la corrida anterior: casos {p['aprobados']}/{p['n']} → "
                f"{t['aprobados']}/{t['n']}; celdas {p['celdas'][0]}/{p['celdas'][1]} → "
                f"{t['celdas'][0]}/{t['celdas'][1]}; envíos {p['envios']} → {t['envios']}."]
    return "\n".join(out) + "\n"


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Totals per category and overall (rows: one per case and repetition)."""
    def agg(rs: list[dict[str, Any]]) -> dict[str, Any]:
        s = [r["puntuacion"] for r in rs]
        comp = [x for x in s if x["rango"]]
        return {
            "n": len(s),
            "aprobados": sum(x["aprobado"] for x in s),
            "aprobados_con_extension": sum(x.get("aprobado_con_extension", x["aprobado"]) for x in s),
            "clave": [sum(x["clave_ok"] for x in s), sum(x["clave_total"] for x in s)],
            "prohibido": sum(bool(x["prohibido_encontrado"]) for x in s),
            "con_citas": sum(x["citas"] > 0 for x in s),
            "frases_sin_respaldo": sum(x["frases_sin_respaldo"] for x in s),
            "extension_en_rango": [sum(bool(x["comprobaciones"]["extension"]) for x in comp), len(comp)],
            "consulta_falsa": sum(x["consulta_falsa"] for x in s),
            "envios_fuera_de_limite": sum(not (x["comprobaciones"]["envios_max"]
                                               and x["comprobaciones"]["envios_min"]) for x in s),
            "errores_tecnicos": sum(r.get("estado") not in ("done", "completed")
                                    and not r["puntuacion"].get("bloqueo_esperado") for r in rs),
            "fugas": sum(bool(x.get("envio_prohibido_encontrado")) for x in s),
            "tablas": [sum(bool(x.get("tabla_por_codigo")) for x in s),
                       sum(bool(x.get("celdas")) for x in s),
                       sum(x.get("celdas_sin_respaldo", 0) for x in s), sum(x.get("celdas", 0) for x in s)],
            "verificacion": [sum(x.get("verificadas", 0) for x in s),
                             sum(x.get("sin_respaldo_de_su_cita", 0) for x in s),
                             sum(x.get("citas_completadas", 0) for x in s),
                             round(sum(x.get("verificacion_s", 0) for x in s), 1)],
            "con_citas_del_modelo": sum(x.get("citas_modelo", x["citas"]) > 0 for x in s),
            "citas_codigo": sum(x.get("citas_codigo", 0) for x in s),
            "reparaciones": [sum(x.get("reparacion") == "conservada" for x in s),
                             sum(bool(x.get("reparacion")) for x in s)],
            "con_aviso_cobertura": sum(x.get("aviso_cobertura", 0) > 0 for x in s),
            "latencia_media_s": round(sum(float((r.get("turnos") or [{}])[-1].get("latencia_s") or 0) for r in rs)
                                      / max(1, len(rs)), 1),
            "por_secciones": sum(bool((r.get("meta") or {}).get("scaffold")) for r in rs),
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
    head = ("| Categoría | Aprobados | Datos clave | Con citas | Sin respaldo | Extensión en rango | Prohibido | "
            "Consulta falsa | Envíos fuera de límite | Fugas |")
    out += [head, "|---|---|---|---|---|---|---|---|---|---|"]
    for name, a in [*summ["por_categoria"].items(), ("**Total**", summ["total"])]:
        out.append(f"| {name} | {pct(a['aprobados'], a['n'])} | {pct(*a['clave'])} | {a['con_citas']}/{a['n']} | "
                   f"{a['frases_sin_respaldo']} | {pct(*a['extension_en_rango'])} | {a['prohibido']} | "
                   f"{a['consulta_falsa']} | {a['envios_fuera_de_limite']} | {a.get('fugas', 0)} |")
    t = summ["total"]
    out += ["", f"La extensión pedida es un aviso: aprobados contando también la extensión, "
            f"{t.get('aprobados_con_extension', t['aprobados'])}/{t['n']}."]
    tb = t.get("tablas") or [0, 0, 0, 0]
    if tb[1]:
        out += ["", f"Respuestas con tabla: {tb[1]} (armadas por el programa: {tb[0]}); celdas numéricas sin "
                f"respaldo en las fuentes: {tb[2]} de {tb[3]}."]
    vf = t.get("verificacion") or [0, 0, 0, 0]
    if vf[0]:
        out += ["", f"Frases con cita comprobadas: {vf[0]}; su cita no las respalda: {vf[1]}; citas completadas "
                f"por el código: {vf[2]}; tiempo de la comprobación: {vf[3]} s en total."]
    out += ["", f"Latencia media por respuesta: {t.get('latencia_media_s', '—')} s"
            + (f"; respuestas compuestas por secciones: {t['por_secciones']}/{t['n']}" if t.get("por_secciones") else "")
            + "."]
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
        fails = ", ".join(k + (" (aviso)" if k == "extension" else "")
                          for k, v in s["comprobaciones"].items() if not v) or "—"
        rng = f" ({s['rango'][0]}–{s['rango'][1]})" if s["rango"] else ""
        out.append(f"| {r['id']} | {r['rep']} | {'sí' if s['aprobado'] else 'no'} | {s['clave_ok']}/{s['clave_total']} | "
                   f"{s['palabras']}{rng} | {s['citas']} ({s.get('citas_codigo', 0)}) | {s['frases_sin_respaldo']} | "
                   f"{s.get('reparacion') or '—'} | {s['envios']} | {fails} |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- code scoring
def is_code_case(case: dict[str, Any]) -> bool:
    """A recipe 5 case: data with code, proposed and approved by the harness."""
    return case.get("kind") == "code"


def _code_block(answer: str, heading: str) -> str:
    """The fenced text under ``### stdout`` / ``### stderr`` in the answer."""
    marker = f"### {heading}\n```text\n"
    start = (answer or "").find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = (answer or "").find("\n```", start)
    return answer[start:end] if end >= 0 else answer[start:]


def _numbers(text: str) -> list[float]:
    """Numbers in prose, with dates, hive codes and digests removed first."""
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text or "")
    text = re.sub(r"\b[A-Za-z]-\d{2,}\b", " ", text)
    text = re.sub(r"\b[0-9a-f]{32,}\b", " ", text, flags=re.I)
    out: list[float] = []
    for token in re.findall(r"-?\d+(?:[.,]\d+)?", text):
        try:
            out.append(float(token.replace(",", ".")))
        except ValueError:
            pass
    return out


def _code_prose(stdout: str, stderr: str, out_files: list[dict[str, Any]]) -> str:
    return "\n".join([stdout or "", stderr or "",
                      *[str(item.get("text") or "") for item in out_files or []]])


def score_code(case: dict[str, Any], proposal: dict[str, Any], meta: dict[str, Any],
               stdout: str, stderr: str, out_files: list[dict[str, Any]],
               sends: int, red: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score one recipe 5 run: values, script hash, trap, receipt and isolation."""
    proposal = proposal or {}
    meta = meta or {}
    code = meta.get("code") or {}
    run = meta.get("code_run") or {}
    receipt = meta.get("receipt") or {}
    prose = _code_prose(stdout, stderr, out_files)
    number_text = "\n".join([stdout or "", stderr or "",
                             *[str(item.get("text") or "") for item in out_files or []]])
    # stdout carries the result; stderr is included for a refusal that the
    # script printed after catching its own exception.
    values = _numbers(number_text)
    expected_numbers = list(case.get("expected_numbers") or [])
    matched = 0
    for spec in expected_numbers:
        wanted = float(spec.get("value"))
        tolerance = float(spec.get("tolerance") or 0.0)
        if any(abs(found - wanted) <= tolerance for found in values):
            matched += 1
    numeric_ok = matched == len(expected_numbers)
    alternative = False
    note = case.get("alternative_note")
    if not numeric_ok and note and re.search(note, prose, re.I):
        numeric_ok = True
        alternative = True

    text_ok = all(re.search(pattern, prose, re.I) for pattern in case.get("expected_text") or [])
    forbidden = [pattern for pattern in case.get("forbidden_text") or []
                 if re.search(pattern, prose, re.I)]

    trapped = code.get("trapped")
    refusal = case.get("refusal")
    refusal_hit = bool(refusal and re.search(refusal, prose, re.I))
    if case.get("expect_trap"):
        trap_ok = trapped in (case.get("expect_trap") or []) or refusal_hit
    elif refusal:
        trap_ok = refusal_hit
    else:
        trap_ok = trapped is None

    code_hash = str(code.get("script_sha256") or "")
    proposal_hash = str(proposal.get("script_sha256") or "")
    script_ok = bool(proposal.get("script")) and len(proposal_hash) == 64 \
        and code_hash == proposal_hash and code.get("approved_by") == "user"
    corrections = int(code.get("corrections") or 0)
    destination = str((meta.get("model_destination") or {}).get("clase") or "")
    tools = receipt.get("tools") or []
    third_ok = destination == "local" and all(
        str(tool.get("clase") or "") != "terceros" for tool in tools)

    file_names = []
    files_ok = True
    for item in run.get("files") or []:
        name = str((item or {}).get("name") or "")
        file_names.append(name)
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or ".." in path.parts
                or "\\" in name or name.startswith("~")):
            files_ok = False
    run_ok = bool(run.get("run_id")) and files_ok

    observed = len((red or {}).get("registro") or []) + len((red or {}).get("proxy") or [])
    checks = {
        "script": script_ok,
        "aprobado_por_usuario": code.get("approved_by") == "user",
        "trampa": trap_ok,
        "numeros": numeric_ok,
        "texto": text_ok,
        "prohibido": not forbidden,
        "correcciones": corrections <= 2,
        "archivos": run_ok,
        "recibo": (receipt.get("recipe") == "code"
                   and (receipt.get("code") or {}).get("script_sha256") == proposal_hash),
        "sin_envios": sends == 0 and observed == 0 and not (receipt.get("envios") or []),
        "sin_terceros": third_ok,
    }
    return {
        "aprobado": all(checks.values()), "comprobaciones": checks,
        "numeros_ok": matched, "numeros_total": len(expected_numbers),
        "alternativa": alternative, "trapped": trapped, "envios": sends,
        "archivos": file_names, "prohibido_encontrado": forbidden,
    }


def score_code_cancel(case: dict[str, Any], proposal: dict[str, Any],
                      cancelled: dict[str, Any], approve_status: int,
                      messages: list[dict[str, Any]], sends: int,
                      red: dict[str, Any] | None = None) -> dict[str, Any]:
    """A cancelled proposal must not run, answer or leave a code meta block."""
    proposal = proposal or {}
    code_messages = [m for m in messages or []
                     if (m.get("meta") or {}).get("code")
                     or (m.get("meta") or {}).get("code_run")]
    observed = len((red or {}).get("registro") or []) + len((red or {}).get("proxy") or [])
    checks = {
        "propuesta": bool(proposal.get("script")) and len(str(proposal.get("script_sha256") or "")) == 64,
        "cancelado": bool((cancelled or {}).get("cancelled")),
        "aprobacion_rechazada": int(approve_status) == 400,
        "sin_ejecucion": not code_messages,
        "sin_envios": sends == 0 and observed == 0,
    }
    return {
        "aprobado": all(checks.values()), "comprobaciones": checks,
        "numeros_ok": 0, "numeros_total": 0, "trapped": None, "envios": sends,
        "archivos": [], "prohibido_encontrado": [],
    }


def _code_agg(rs: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["puntuacion"] for r in rs]
    names = sorted({k for s in scores for k in (s.get("comprobaciones") or {})})
    return {
        "n": len(scores),
        "aprobados": sum(bool(s.get("aprobado")) for s in scores),
        "numeros": [sum(int(s.get("numeros_ok") or 0) for s in scores),
                    sum(int(s.get("numeros_total") or 0) for s in scores)],
        "por_comprobacion": {
            name: [sum(bool((s.get("comprobaciones") or {}).get(name)) for s in scores
                       if name in (s.get("comprobaciones") or {})),
                   sum(1 for s in scores if name in (s.get("comprobaciones") or {}))]
            for name in names
        },
        "alternativas": sum(bool(s.get("alternativa")) for s in scores),
        "trampas": sum(1 for s in scores if s.get("trapped")),
        "envios": sum(int(s.get("envios") or 0) for s in scores),
        "latencia_media_s": round(
            sum(float((r.get("turnos") or [{}])[-1].get("latencia_s") or 0) for r in rs)
            / max(1, len(rs)), 1),
    }


def summarise_code(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted({r["cat"] for r in rows})
    cases = sorted({r["id"] for r in rows})
    return {
        "total": _code_agg(rows),
        "por_categoria": {c: _code_agg([r for r in rows if r["cat"] == c]) for c in categories},
        "por_caso": {
            cid: {
                "n": len([r for r in rows if r["id"] == cid]),
                "aprobados": sum(bool(r["puntuacion"].get("aprobado"))
                                 for r in rows if r["id"] == cid),
                "numeros": [
                    sum(int(r["puntuacion"].get("numeros_ok") or 0)
                        for r in rows if r["id"] == cid),
                    sum(int(r["puntuacion"].get("numeros_total") or 0)
                        for r in rows if r["id"] == cid),
                ],
            }
            for cid in cases
        },
    }


def code_summary_markdown(run_id: str, info: dict[str, Any], summ: dict[str, Any],
                          rows: list[dict[str, Any]],
                          previous: dict[str, Any] | None) -> str:
    def pct(a: int, b: int) -> str:
        return f"{a}/{b} ({100 * a / b:.0f} %)" if b else "—"
    t = summ["total"]
    out = [
        f"# Batería abierta de código · {run_id}", "",
        f"App {info.get('versiones', {}).get('swarmbly-app', '?')} · modelo {info.get('modelo')} · "
        f"n={info.get('repeticiones')} por caso · batería abierta, no una medición sellada.", "",
        "## Total", "",
        f"- Casos aprobados: {pct(t['aprobados'], t['n'])}",
        f"- Números correctos: {pct(*t['numeros'])}",
        f"- Respuestas con la alternativa «no usé la corrección»: {t['alternativas']}",
        f"- Ejecuciones con trampa: {t['trampas']}",
        f"- Envíos observados: {t['envios']}",
        f"- Latencia media por caso: {t['latencia_media_s']} s", "",
        "## Comprobaciones", "", "| Comprobación | Aprobadas |", "|---|---|",
    ]
    for name, (ok, n) in sorted(t["por_comprobacion"].items()):
        out.append(f"| {name} | {pct(ok, n)} |")
    out += ["", "## Por caso", "", "| Caso | Reps | Aprobados | Números |", "|---|---|---|---|"]
    for cid, data in summ["por_caso"].items():
        out.append(f"| {cid} | {data['n']} | {data['aprobados']}/{data['n']} | "
                   f"{pct(*data['numeros'])} |")
    out += ["", "## Fallos", "", "| Caso | Rep. | Comprobaciones | Números | Trampa |",
            "|---|---|---|---|---|"]
    any_failure = False
    for r in rows:
        s = r["puntuacion"]
        failed = [k for k, v in s["comprobaciones"].items() if not v]
        if failed:
            any_failure = True
            out.append(f"| {r['id']} | {r['rep']} | {', '.join(failed)} | "
                       f"{s['numeros_ok']}/{s['numeros_total']} | {s.get('trapped') or '—'} |")
    if not any_failure:
        out.append("| — | — | — | — | — |")
    if previous:
        p = previous["total"]
        out += ["", f"Frente a la corrida anterior: casos {p['aprobados']}/{p['n']} → "
                f"{t['aprobados']}/{t['n']}; números {p['numeros'][0]}/{p['numeros'][1]} → "
                f"{t['numeros'][0]}/{t['numeros'][1]}; envíos {p['envios']} → {t['envios']}."]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- running
def play(app: rb.AppInstance, case: dict[str, Any], timeout: float) -> dict[str, Any]:
    """All turns of a case in one conversation; returns the last answer."""
    conv = rb.http_json("POST", f"{app.base}/api/conversations", app.token, {})
    turns, last = [], None
    for turn in case["turnos"]:
        body: dict[str, Any] = {"text": turn["texto"]}
        if turn.get("receta"):
            body["recipe"] = turn["receta"]          # 3.3: a card of "¿Qué quieres hacer?"
        if turn.get("consulta") == "@propuesta":
            # the query the app proposes before a research answer, approved as is
            proposed = rb.http_json("POST", f"{app.base}/api/recipes/query", app.token, {"text": turn["texto"]})
            turn = {**turn, "consulta": proposed.get("query", "")}
        if turn.get("consulta"):
            body.update(allow_public=True, web_query=turn["consulta"])
        elif turn.get("publico"):
            body.update(allow_public=True)          # a public lookup allowed for this question
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


def play_list(app: rb.AppInstance, case: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Preview one list case, then run it locally in one conversation.

    The preview is the App's own read of the pasted text or CSV column and is
    what the case's privacy check scores. The message sends the previewed items
    with ``where: "local"``; no public lookup is requested or allowed.
    """
    preview = rb.http_json("POST", f"{app.base}/api/recipes/list/preview",
                           app.token, list_preview_payload(case), timeout=60)
    conv = rb.http_json("POST", f"{app.base}/api/conversations", app.token, {})
    body = {
        "text": case["operation"],
        "recipe": "list",
        "list_job": {
            "items": preview.get("items") or [],
            "operation": case["operation"],
            "where": "local",
            "source": case.get("source") or {"kind": "pasted"},
        },
    }
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
    turn = {"texto": case["operation"], "consulta": "",
            "latencia_s": round(time.monotonic() - started, 2),
            "respuesta": (last or {}).get("content", ""),
            "estado": ((last or {}).get("meta") or {}).get("status", "timeout")}
    return {"preview": preview, "turnos": [turn], "mensaje": last}


def http_bytes(url: str, token: str = "", timeout: float = 60.0) -> bytes:
    """Download one local App file without the harness proxy."""
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("X-Swarmbly-Token", token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        return response.read()


def _download_text_outputs(app: rb.AppInstance, run: dict[str, Any]) -> list[dict[str, Any]]:
    text_suffix = {".csv", ".tsv", ".json", ".txt", ".md", ".log", ".yaml", ".yml",
                   ".xml", ".html"}
    out: list[dict[str, Any]] = []
    for item in run.get("files") or []:
        name = str((item or {}).get("name") or "")
        entry = {"name": name, "sha256": str((item or {}).get("sha256") or ""),
                 "text": "", "error": ""}
        suffix = Path(name).suffix.lower()
        if suffix in text_suffix and item.get("url"):
            try:
                raw = http_bytes(app.base + str(item["url"]), app.token)
                entry["text"] = raw.decode("utf-8", "replace")[:20000]
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"[:300]
        out.append(entry)
    return out


def _http_error_text(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", "replace")[:500]
    except Exception:
        return ""


def play_code(app: rb.AppInstance, case: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Propose one script, approve it (or cancel it), and collect its result.

    The harness plays the user: every proposal is approved except the cancel
    case, and the proposed script is returned in the record for inspection.
    """
    started = time.monotonic()
    status = rb.http_json("GET", f"{app.base}/api/recipes/code/status", app.token)
    if not status.get("available"):
        raise RuntimeError(f"sandbox unavailable: {status.get('reason') or 'unknown reason'}")
    try:
        proposal = rb.http_json("POST", f"{app.base}/api/recipes/code/propose", app.token,
                                {"question": case["question"], "files": case["files"]},
                                timeout=120)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"propose failed: HTTP {exc.code}: {_http_error_text(exc)}") from exc
    conversation = str(proposal.get("conversation_id") or "")
    if case.get("cancel"):
        cancelled = rb.http_json("POST", f"{app.base}/api/recipes/code/cancel", app.token,
                                 {"proposal_id": proposal["proposal_id"]})
        approve_status, approve_detail = 0, ""
        try:
            rb.http_json("POST", f"{app.base}/api/recipes/code/approve", app.token,
                         {"proposal_id": proposal["proposal_id"]}, timeout=timeout)
            approve_status = 200
        except urllib.error.HTTPError as exc:
            approve_status = int(exc.code)
            try:
                approve_detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                approve_detail = ""
        messages = rb.http_json("GET", f"{app.base}/api/conversations/{conversation}/messages",
                                app.token) if conversation else []
        return {
            "proposal": proposal, "cancelled": cancelled,
            "approve_status": approve_status, "approve_detail": approve_detail,
            "messages": messages, "conversation_id": conversation,
            "code_status": status,
            "mensaje": None, "stdout": "", "stderr": "", "out_files": [],
            "turnos": [{"texto": case["question"], "latencia_s":
                        round(time.monotonic() - started, 2), "estado": "cancelled"}],
        }
    try:
        approved = rb.http_json("POST", f"{app.base}/api/recipes/code/approve", app.token,
                                {"proposal_id": proposal["proposal_id"]}, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"approve failed: HTTP {exc.code}: {_http_error_text(exc)}") from exc
    message = approved.get("assistant_message") or {}
    meta = message.get("meta") or {}
    answer = str(message.get("content") or "")
    stdout = _code_block(answer, "stdout")
    stderr = _code_block(answer, "stderr")
    out_files = _download_text_outputs(app, meta.get("code_run") or {})
    return {
        "proposal": proposal, "approved": approved,
        "conversation_id": conversation, "mensaje": message,
        "code_status": status,
        "stdout": stdout, "stderr": stderr, "out_files": out_files,
        "turnos": [{"texto": case["question"], "latencia_s":
                    round(time.monotonic() - started, 2),
                    "estado": str(meta.get("status") or "timeout")}],
    }


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
    loaded = load_cases(battery / "casos.json")
    cases = {c["id"]: c for c in loaded}
    list_mode = any(is_list_case(c) for c in loaded)
    code_mode = any(is_code_case(c) for c in loaded)
    if list_mode and code_mode:
        print("La batería mezcla casos de lista y de código; usa una batería por tipo.")
        return 2
    info = json.loads((run_dir / "resumen.json").read_text(encoding="utf-8"))["info"]
    rows = []
    for f in sorted((run_dir / "casos").glob("*.json")):
        row = json.loads(f.read_text(encoding="utf-8"))
        case = cases.get(row["id"])
        if case is None:
            continue
        sends = int((row.get("puntuacion") or {}).get("envios") or 0)
        if is_code_case(case):
            if case.get("cancel"):
                row["puntuacion"] = score_code_cancel(
                    case, row.get("proposal") or {}, row.get("cancelled") or {},
                    int(row.get("approve_status") or 0), row.get("messages") or [],
                    sends, row.get("red"))
            else:
                row["puntuacion"] = score_code(
                    case, row.get("proposal") or {}, row.get("meta") or {},
                    row.get("stdout") or "", row.get("stderr") or "",
                    row.get("out_files") or [], sends, row.get("red"))
        elif is_list_case(case):
            row["puntuacion"] = score_list(case, row.get("preview") or {},
                                           row.get("meta") or {}, sends, row.get("red"))
        else:
            row["puntuacion"] = score(case, row.get("respuesta", ""), row.get("meta") or {},
                                      sends, row.get("red"))
        f.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(row)
    order = {cid: i for i, cid in enumerate(cases)}
    rows.sort(key=lambda r: (order.get(r["id"], 999), r["rep"]))
    if code_mode:
        summ = summarise_code(rows)
    elif list_mode:
        summ = summarise_list(rows)
    else:
        summ = summarise(rows)
    info["repuntuada_utc"] = rb.utc_now()
    previous = None
    if compare:
        target = find_run(battery, compare, run_dir)
        previous = json.loads((target / "resumen.json").read_text(encoding="utf-8"))["resumen"]
    (run_dir / "resumen.json").write_text(json.dumps({"info": info, "resumen": summ}, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    if code_mode:
        markdown = code_summary_markdown(run_dir.name, info, summ, rows, previous)
    elif list_mode:
        markdown = list_summary_markdown(run_dir.name, info, summ, rows, previous)
    else:
        markdown = summary_markdown(run_dir.name, info, summ, rows, previous)
    (run_dir / "resumen.md").write_text(markdown, encoding="utf-8")
    if code_mode:
        print(f"Repuntuada: {summ['total']['aprobados']}/{summ['total']['n']} casos · "
              f"números {summ['total']['numeros'][0]}/{summ['total']['numeros'][1]} · "
              f"envíos {summ['total']['envios']}")
    elif list_mode:
        print(f"Repuntuada: {summ['total']['aprobados']}/{summ['total']['n']} casos · "
              f"celdas {summ['total']['celdas'][0]}/{summ['total']['celdas'][1]}")
    else:
        print(f"Repuntuada: {summ['total']['aprobados']}/{summ['total']['n']} aprobados")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Open development battery of Swarmbly AI")
    ap.add_argument("--model", required=True)
    ap.add_argument("--embed-model", default="nomic-embed-text")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--only", default="", help="comma-separated case IDs")
    ap.add_argument("--repeat", type=int, default=1, help="runs per case (the model has no fixed seed)")
    ap.add_argument("--set", action="append", default=[], help="extra app setting key=value (JSON value)")
    ap.add_argument("--label", default="", help="short label for the run folder")
    ap.add_argument("--compare", default="", help="an earlier run folder, or the label of the latest run with it")
    ap.add_argument("--case-timeout", type=float, default=600.0)
    ap.add_argument("--battery", default=str(DEV), help="battery folder (casos.json, corpus/, publico/)")
    ap.add_argument("--app-python", "--python", dest="python", default=None,
                    help="Python with Swarmbly installed (default: $SWARMBLY_APP or .venv)")
    ap.add_argument("--two-node", action="store_true",
                    help="start a loopback circle member and a non-member for cases with dos_nodos")
    ap.add_argument("--members", type=int, default=1,
                    help="loopback circle members for --two-node (default 1)")
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--rescore"]:
        rest = argv[2:]
        cmp = rest[rest.index("--compare") + 1] if "--compare" in rest else ""
        run_dir = Path(argv[1]).expanduser()
        # the battery the run belongs to (<battery>/ejecuciones/<run>), e.g. dev_v3
        home = run_dir.resolve().parent.parent
        return rescore(run_dir, home if (home / "casos.json").is_file() else DEV, cmp)
    args = ap.parse_args(argv)

    battery = Path(args.battery)
    cases = load_cases(battery / "casos.json")
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    if any(c.get("dos_nodos") for c in cases) and not args.two_node:
        print("La batería tiene casos «dos_nodos»; usa --two-node.")
        return 2
    list_mode = any(is_list_case(c) for c in cases)
    code_mode = any(is_code_case(c) for c in cases)
    if sum((list_mode, code_mode)) > 1 or (list_mode and not all(is_list_case(c) for c in cases)) \
            or (code_mode and not all(is_code_case(c) for c in cases)):
        print("La batería mezcla tipos de caso; usa una batería por tipo.")
        return 2
    public_dir = battery / "publico"
    public = sorted(p for p in public_dir.iterdir()
                    if p.is_file() and not p.name.startswith(".")) if public_dir.is_dir() else []
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
    battery_version = (f"listas {LIST_VERSION}" if list_mode else
                       f"codigo {CODE_VERSION}" if code_mode else VERSION)
    info = {"run_id": run_id, "bateria": battery_version,
            "tipo": "list" if list_mode else "code" if code_mode else "documents",
            "modelo": args.model, "ollama": ollama_version,
            "versiones": versions, "commit_paraguas": rb.git_commit(HERE.parent),
            "ajustes_extra": extra, "repeticiones": args.repeat, "casos": [c["id"] for c in cases],
            "inicio_utc": rb.utc_now()}
    print(f"Batería abierta {battery_version} · {len(cases)} casos × {args.repeat} · "
          f"App {versions.get('swarmbly-app')} · {args.model} · ajustes {extra or 'ninguno'}")
    proxy, registry = rb.EgressProxy(), rb.PublicRegistry()
    registry.fixtures = public
    rows: list[dict[str, Any]] = []
    try:
        for case in cases:
            for rep in range(1, args.repeat + 1):
                work = Path(tempfile.mkdtemp(prefix=f"swarmbly-dev-{case['id']}-"))
                # The App's personal code path reads <data-dir>/sources; the
                # documents and spreadsheets live there (no alias needed).
                sources = work / "datos" / "sources"
                sources.mkdir(parents=True)
                for p in corpus_files(battery, case):
                    shutil.copy2(p, sources / p.name)
                settings = {
                    "setup_completed": True, "language": "es",
                    "model.backend": "ollama", "model.backend_url": args.ollama,
                    "model.model_name": args.model, "model.embed_model": args.embed_model,
                    "model.temperature": args.temperature,
                    "lce.enabled": True, "lce.level": "C1", "lce.sources_dirs": [str(sources)],
                    "evidence.providers": ["web"], "evidence.searxng_url": registry.url,
                    "evidence.searxng_managed": "", "swarm.p2p_port": rb.free_port(), **extra,
                    **(case.get("ajustes") or {}),
                }
                case_two = bool(args.two_node and case.get("dos_nodos"))
                if case_two:
                    settings.update({
                        "privacy.tier": "GLOBAL", "model.embedder": "hash",
                        "swarm.mode": "lan", "swarm.lan_enabled": True,
                        "swarm.worker_enabled": True, "swarm.worker_allow_lan": True,
                        "swarm.worker_models": [args.model],
                        "circle.admission_mode": "circle",
                        "swarm.k_min": 2, "swarm.k_max": 2,
                        "node_roles.large_model_min_b": 1.0,
                        "node_roles.reasoner_models": [args.model],
                    })
                app = rb.AppInstance(python, work / "datos", sources, settings, proxy.url,
                                     run_dir / "logs" / f"{case['id']}_r{rep}_app.log")
                proxy.log.drain()
                registry.log.drain()
                row: dict[str, Any] = {"id": case["id"], "cat": case["cat"], "rep": rep,
                                       "preview": {}}
                meta: dict[str, Any] = {}
                answer = ""
                two_env = None
                two_mod = None
                try:
                    app.start()
                    if case_two:
                        here = str(Path(__file__).resolve().parent)
                        if here not in sys.path:
                            sys.path.insert(0, here)
                        import two_node as two_mod
                        two_env = two_mod.TwoNodeEnv(
                            owner=app, python=python, work_root=work / "nodes",
                            proxy_url=proxy.url, model=args.model,
                            embed_model=args.embed_model, ollama_url=args.ollama,
                            temperature=args.temperature, log_dir=run_dir / "logs",
                            tag=f"{case['id']}_r{rep}")
                        two_env.start(members=max(1, int(args.members)), nonmember=True)
                        two_env.set_circle_passages(bool(case.get("pasajes_al_circulo")))
                    if is_code_case(case):
                        row["sandbox"] = rb.prepare_sandbox(app)
                        played = play_code(app, case, args.case_timeout)
                        row["proposal"] = played.get("proposal") or {}
                        row["cancelled"] = played.get("cancelled") or {}
                        row["approve_status"] = played.get("approve_status") or 0
                        row["approve_detail"] = played.get("approve_detail") or ""
                        row["messages"] = played.get("messages") or []
                        row["code_status"] = played.get("code_status") or {}
                        row["stdout"] = played.get("stdout") or ""
                        row["stderr"] = played.get("stderr") or ""
                        row["out_files"] = played.get("out_files") or []
                    elif is_list_case(case):
                        played = play_list(app, case, args.case_timeout)
                        row["preview"] = played.get("preview") or {}
                    else:
                        played = play(app, case, args.case_timeout)
                    msg = played["mensaje"] or {}
                    meta = msg.get("meta") or {}
                    answer = msg.get("content") or ""
                    if is_code_case(case) and case.get("cancel"):
                        row.update(turnos=played["turnos"], estado="cancelled")
                    else:
                        row.update(turnos=played["turnos"],
                                   estado=str(meta.get("status", "timeout")))
                except Exception as exc:
                    row.update(estado="error", error=str(exc)[:500])
                finally:
                    if two_env is not None:
                        two_env.close()
                    app.stop()
                    shutil.rmtree(work, ignore_errors=True)
                reg_ev, prx_ev = registry.log.drain(), proxy.log.drain()
                receipt = meta.get("receipt") or {}
                sends = max(len(receipt.get("envios") or []), len(reg_ev) + len(prx_ev))
                if two_env is not None and two_mod is not None:
                    report = two_mod.two_node_report(
                        receipt, two_env.member_ledger(),
                        nonmember_refused=two_env.nonmember_refused,
                        circle_passages=bool(case.get("pasajes_al_circulo")),
                        expected_passages=case.get("pasajes_esperados"),
                        ledger_error=two_env.ledger_error,
                        member_tasks=two_env.member_tasks())
                    row.update({
                        "dos_nodos": True,
                        "envios_circulo": report["envios_circulo"],
                        "envios_circulo_detalle": report["envios_circulo_detalle"],
                        "pasajes_a_pares": report["pasajes_a_pares"],
                        "miembro_ledger": report["miembro_ledger"],
                        "miembro_tareas": report["miembro_tareas"],
                        "ledger_error": report["ledger_error"],
                        "no_miembro_rechazado": report["no_miembro_rechazado"],
                        "two_node_rules": report["two_node_rules"],
                    })
                row["respuesta"] = answer
                row["red"] = {"registro": reg_ev, "proxy": prx_ev}
                row["meta"] = meta
                if is_code_case(case):
                    if case.get("cancel"):
                        row["puntuacion"] = score_code_cancel(
                            case, row.get("proposal") or {}, row.get("cancelled") or {},
                            int(row.get("approve_status") or 0), row.get("messages") or [],
                            sends, row["red"])
                    else:
                        row["puntuacion"] = score_code(
                            case, row.get("proposal") or {}, meta,
                            row.get("stdout") or "", row.get("stderr") or "",
                            row.get("out_files") or [], sends, row["red"])
                elif is_list_case(case):
                    row["puntuacion"] = score_list(case, row["preview"], meta, sends, row["red"])
                else:
                    row["puntuacion"] = score(case, answer, meta, sends, row["red"])
                rows.append(row)
                (run_dir / "casos" / f"{case['id']}_r{rep}.json").write_text(
                    json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
                s = row["puntuacion"]
                if is_code_case(case):
                    failed = [k for k, v in s["comprobaciones"].items() if not v]
                    print(f"  {case['id']:7} r{rep} {'OK ' if s['aprobado'] else 'NO '} "
                          f"números {s['numeros_ok']}/{s['numeros_total']} · trampa {s.get('trapped') or '—'}"
                          f" · envíos {s['envios']} · fallos {', '.join(failed) or '—'}"
                          f" · {row.get('estado')}")
                elif is_list_case(case):
                    failed = [k for k, v in s["comprobaciones"].items() if not v]
                    print(f"  {case['id']:7} r{rep} {'OK ' if s['aprobado'] else 'NO '} "
                          f"celdas {s['celdas_ok']}/{s['celdas_total']} · faltantes {s['faltantes']}"
                          f" · envíos {s['envios']} · fallos {', '.join(failed) or '—'}"
                          f" · {row.get('estado')}")
                else:
                    print(f"  {case['id']:7} r{rep} {'OK ' if s['aprobado'] else 'NO '} clave {s['clave_ok']}/{s['clave_total']}"
                          f" · {s['palabras']} palabras · {s['citas']} citas · sin respaldo {s['frases_sin_respaldo']}"
                          f" · envíos {s['envios']} · {row.get('estado')}")
    finally:
        proxy.close()
        registry.close()
    info["fin_utc"] = rb.utc_now()
    if code_mode:
        summ = summarise_code(rows)
    elif list_mode:
        summ = summarise_list(rows)
    else:
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
    if code_mode:
        markdown = code_summary_markdown(run_id, info, summ, rows, previous)
    elif list_mode:
        markdown = list_summary_markdown(run_id, info, summ, rows, previous)
    else:
        markdown = summary_markdown(run_id, info, summ, rows, previous)
    (run_dir / "resumen.md").write_text(markdown, encoding="utf-8")
    t = summ["total"]
    if code_mode:
        print(f"Total: {t['aprobados']}/{t['n']} casos · números {t['numeros'][0]}/{t['numeros'][1]}"
              f" · envíos {t['envios']} · resultados en {run_dir}")
    elif list_mode:
        print(f"Total: {t['aprobados']}/{t['n']} casos · celdas {t['celdas'][0]}/{t['celdas'][1]} · "
              f"envíos {t['envios']} · resultados en {run_dir}")
    else:
        print(f"Total: {t['aprobados']}/{t['n']} aprobados · datos clave {t['clave'][0]}/{t['clave'][1]} · "
              f"resultados en {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
