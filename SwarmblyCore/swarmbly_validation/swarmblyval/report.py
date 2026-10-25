"""Test-result schema and rendering (console summary + Markdown report)."""

from dataclasses import dataclass, field, asdict
import json
from typing import Any


# Verdict vocabulary
PASS = "PASS"
FAIL = "FAIL"
REFUSE = "REFUSE"
BLOCKED = "BLOCKED"
CONCEPTUAL = "CONCEPTUAL"   # a reasoning check with no new measurement to run


@dataclass
class Result:
    id: str
    name: str
    model: str                     # e.g. "M5", "M4", "—"
    verdict: str
    summary: str                   # one line, the headline
    killed_if: str                 # the model's death condition
    refusal: str = ""              # refusal condition actually applied
    details: list = field(default_factory=list)     # bullet strings
    tables: dict = field(default_factory=dict)      # {title: (headers, rows)}
    notes: list = field(default_factory=list)       # caveats / adjustments

    def to_dict(self):
        return asdict(self)


_VERDICT_GLYPH = {
    PASS: "✔ PASS",
    FAIL: "✘ FAIL",
    REFUSE: "◌ REFUSE",
    BLOCKED: "▣ BLOCKED",
    CONCEPTUAL: "· CONCEPTUAL",
}


def render_console(results):
    lines = []
    width = 74
    lines.append("=" * width)
    lines.append("SWARMBLY AI — VALIDATION HARNESS".center(width))
    lines.append("reproducción aritmética + pruebas de falsación M1–M5".center(width))
    lines.append("=" * width)
    lines.append("")
    for r in results:
        lines.append(f"[{r.id}] {_VERDICT_GLYPH.get(r.verdict, r.verdict):14s} {r.name}")
        lines.append(f"          modelo {r.model:4s} · {r.summary}")
        if r.details:
            for d in r.details[:4]:
                lines.append(f"            - {d}")
            if len(r.details) > 4:
                lines.append(f"            … (+{len(r.details) - 4} más en el reporte)")
        lines.append("")
    # tally
    from collections import Counter
    tally = Counter(r.verdict for r in results)
    lines.append("-" * width)
    lines.append("Recuento: " + "  ".join(
        f"{_VERDICT_GLYPH.get(k, k)} = {v}" for k, v in tally.items()))
    lines.append("=" * width)
    return "\n".join(lines)


def _md_table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def render_markdown(results, meta=None):
    lines = []
    lines.append("# Swarmbly AI — Reporte de validación")
    lines.append("")
    lines.append("> Generado automáticamente por `run_all.py`. Los valores citados "
                 "provienen de `WHITEPAPER_V2_EN.md` y documentos acompañantes; no "
                 "son mediciones nuevas salvo donde se indica.")
    lines.append("")
    if meta:
        for k, v in meta.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")

    lines.append("## Resumen de veredictos")
    lines.append("")
    lines.append(_md_table(
        ["#", "Test", "Modelo", "Veredicto", "Titular"],
        [[r.id, r.name, r.model, r.verdict, r.summary] for r in results]))
    lines.append("")

    for r in results:
        lines.append(f"## {r.id} — {r.name}")
        lines.append("")
        lines.append(f"- **Modelo:** {r.model}")
        lines.append(f"- **Veredicto:** `{r.verdict}`")
        lines.append(f"- **Titular:** {r.summary}")
        lines.append(f"- **Condición de muerte:** {r.killed_if}")
        if r.refusal:
            lines.append(f"- **Condición de rechazo aplicada:** {r.refusal}")
        lines.append("")
        if r.details:
            lines.append("### Detalle")
            lines.append("")
            for d in r.details:
                lines.append(f"- {d}")
            lines.append("")
        if r.tables:
            for title, (headers, rows) in r.tables.items():
                lines.append(f"### {title}")
                lines.append("")
                lines.append(_md_table(headers, rows))
                lines.append("")
        if r.notes:
            lines.append("### Ajustes y observaciones")
            lines.append("")
            for n in r.notes:
                lines.append(f"- {n}")
            lines.append("")
    return "\n".join(lines)


def write_report(results, meta, md_path, json_path):
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(results, meta))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": [r.to_dict() for r in results]},
                  f, ensure_ascii=False, indent=2)
