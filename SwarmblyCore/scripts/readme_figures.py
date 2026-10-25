#!/usr/bin/env python3
"""Draw the README charts from the harness output and the committed records.

Every chart comes in a light and a dark variant with the same data; the README
serves them with <picture> according to the reader's theme. Figures produced
by the harness are read from ``swarmbly_validation/results_real.json`` (run
``python3 swarmbly_validation/run_real.py`` first); the L-curve extraction
fidelity comes from ``data/lcurve_v3_summary.json``. Two figures predate the
harness and are taken from the result documents that report them, named next
to each value in ``QUOTED`` below. Requires matplotlib (not a dependency of the
package).

    python3 swarmbly_validation/run_real.py
    python3 scripts/readme_figures.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"

#: Values not emitted by the harness, with the document that reports each.
QUOTED = {
    # docs/RESULTS_TABLES_FINAL_CORRECTED.md, section 1 (16 held-out prompts)
    "tables_final_n2": (2.30, -2.05, 7.49),
    "tables_final_n8": (16.23, 11.33, 20.28),
    # docs/RESULTS_V0_V3C.md and RESULTS_TABLES_FINAL_CORRECTED.md:
    # Mantel-Haenszel common odds ratios, agreement vs answer-key correctness
    "confidence_map_or": (3.47, 0.26, 1.24),
}

THEMES = {
    "light": {"text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3de", "blue": "#2a78d6",
              "orange": "#eb6834", "gray": "#a3a29c", "red": "#e34948"},
    "dark": {"text": "#f0efec", "muted": "#c3c2b7", "grid": "#3a3a37", "blue": "#3987e5",
             "orange": "#d95926", "gray": "#77766f", "red": "#e66767"},
}


def _signed(x: float, nd: int = 2) -> str:
    return f"{x:+.{nd}f}".replace("-", "−")


def _harness() -> dict:
    p = ROOT / "swarmbly_validation" / "results_real.json"
    if not p.exists():
        sys.exit("run `python3 swarmbly_validation/run_real.py` first")
    rows = json.loads(p.read_text(encoding="utf-8"))["results"]
    return {r["id"]: r for r in rows}


def _table(row: dict, title: str) -> tuple[list, list]:
    for name, (header, body) in row["tables"].items():
        if name.startswith(title):
            return header, body
    raise KeyError(title)


def _style(ax, t: dict, grid: str = "x") -> None:
    ax.set_facecolor("none")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(colors=t["muted"], length=0, labelsize=9)
    (ax.xaxis if grid == "x" else ax.yaxis).grid(True, color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def _new(plt, t: dict, w: float, h: float, grid: str = "x"):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_alpha(0)
    _style(ax, t, grid)
    return fig, ax


def _title(fig, t: dict, title: str, sub: str) -> None:
    fig.text(0.01, 0.97, title, ha="left", va="top", fontsize=11.5, weight="bold", color=t["text"])
    fig.text(0.01, 0.905, sub, ha="left", va="top", fontsize=8.8, color=t["muted"])


def fig_coherence_tax(plt, t: dict, H: dict):
    m = re.search(r"tax ([+-][\d.]+)% IC95 \[([+-][\d.]+), ([+-][\d.]+)\]", H["T09R"]["summary"])
    ref = tuple(float(x) for x in m.groups())
    rows = [("N = 2, k = 1 · held-out test", QUOTED["tables_final_n2"], t["blue"], "NOT MET"),
            ("N = 8, k = 1 · control, must fail", QUOTED["tables_final_n8"], t["gray"], "fails, as required"),
            ("5 families, matched output budget", ref, t["orange"], "REFUSED: length-confounded")]
    rows = list(reversed(rows))
    fig, ax = _new(plt, t, 7.2, 2.9)
    for i, (lab, (pt, lo, hi), col, verdict) in enumerate(rows):
        ax.plot([lo, hi], [i, i], color=col, linewidth=2.2, solid_capstyle="round")
        ax.plot(pt, i, "o", color=col, markersize=7)
        ax.text(hi + 0.6, i, f"{_signed(pt)} % [{_signed(lo)}, {_signed(hi)}] · {verdict}",
                va="center", fontsize=8.4, color=t["text"])
    ax.axvline(5, color=t["red"], linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(5.3, -0.62, "5 % threshold", color=t["red"], fontsize=8.4, va="center")
    ax.axvline(0, color=t["muted"], linewidth=0.8)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], color=t["text"])
    ax.set_xlim(-5, 58)
    ax.set_ylim(-0.85, len(rows) - 0.5)
    ax.set_xlabel("coherence tax (% quality lost vs. not fragmenting), 95 % CI", color=t["muted"], fontsize=9)
    _title(fig, t, "The abandonment criterion: not met, then not measurable",
           "Criterion registered before any data: the upper bound must fall below 5 % in some task category")
    fig.subplots_adjust(left=0.3, right=0.99, top=0.78, bottom=0.18)
    return fig


def fig_extraction(plt, t: dict, H: dict):
    header, body = _table(H["T08R4"], "Por tamaño")
    cols = {h: i for i, h in enumerate(header)}
    arms = [("monolítico", "model alone", t["gray"]),
            ("N=1 + código", "whole document extracted + code", t["orange"]),
            ("fragmentos + código", "fragments extracted + code", t["blue"])]
    import numpy as np
    fig, ax = _new(plt, t, 7.2, 3.1, grid="y")
    x = np.arange(len(body))
    w = 0.26
    for j, (key, lab, col) in enumerate(arms):
        vals = [float(r[cols[key]].rstrip("%")) for r in body]
        bars = ax.bar(x + (j - 1) * w, vals, width=w - 0.02, color=col, label=lab)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f} %", ha="center", fontsize=8.4, color=t["text"])
    ax.set_xticks(x, [f"{r[cols['filas']]} rows per document" for r in body], color=t["text"])
    ax.set_ylim(0, 118)
    ax.set_ylabel("questions answered correctly", color=t["muted"], fontsize=9)
    leg = ax.legend(frameon=False, fontsize=8.4, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.13))
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    m = re.search(r"partir ([+-][\d.]+) pts \[([+-][\d.]+), ([+-][\d.]+)\]", H["T08R4"]["summary"])
    _title(fig, t, "Extract with small models, aggregate with code",
           f"L curve v3 · llama3.2:3b · 8 documents · effect of splitting {_signed(float(m.group(1)), 1)} points "
           f"[{_signed(float(m.group(2)), 1)}, {_signed(float(m.group(3)), 1)}]")
    fig.subplots_adjust(left=0.1, right=0.99, top=0.74, bottom=0.12)
    return fig


def fig_fidelity(plt, t: dict, H: dict):
    s = json.loads((ROOT / "data" / "lcurve_v3_summary.json").read_text(encoding="utf-8"))
    header, body = _table(H["T08R4"], "Por tamaño")
    fi = header.index("fidelidad N=1")
    ok = sum(int(r[fi].split("/")[0]) for r in body)
    n = sum(int(r[fi].split("/")[1]) for r in body)
    rows = [("whole document (N = 1)", 100 * ok / n, t["orange"])]
    for L, v in sorted(s["by_L"].items(), key=lambda kv: int(kv[0])):
        rows.append((f"fragments of L = {L} rows", 100 * v["rows_ok"] / v["rows"], t["blue"]))
    rows = list(reversed(rows))
    fig, ax = _new(plt, t, 7.2, 2.8)
    for i, (lab, v, col) in enumerate(rows):
        ax.barh(i, v, height=0.55, color=col)
        ax.text(v + 1, i, f"{v:.1f} %", va="center", fontsize=8.8, color=t["text"])
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], color=t["text"])
    ax.set_xlim(0, 112)
    ax.set_xlabel("records extracted correctly (80- and 160-row documents)", color=t["muted"], fontsize=9)
    _title(fig, t, "A small node extracts reliably up to a size",
           f"{s['model']} · fragmenting keeps each task below the size where single-call extraction collapses")
    fig.subplots_adjust(left=0.27, right=0.98, top=0.78, bottom=0.18)
    return fig


def fig_node_class(plt, t: dict, H: dict):
    header, body = _table(H["T0RR"], "Impuesto por CLASE")
    rows = sorted(((r[0], float(r[2].rstrip("%")), r[5]) for r in body), key=lambda r: -r[1])
    fig, ax = _new(plt, t, 7.2, 2.8)
    for i, (lab, v, frac) in enumerate(rows):
        ax.barh(i, v, height=0.55, color=t["blue"])
        ax.text(v + 0.4, i, f"{_signed(v, 1)} %   ({frac} of cells expensive)", va="center", fontsize=8.6, color=t["text"])
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], color=t["text"])
    ax.set_xlim(0, 42)
    ax.set_xlabel("mean coherence tax over 16 table tasks (80 operational cells)", color=t["muted"], fontsize=9)
    auc = re.search(r"AUC LOO ([\d.]+)", H["T0RR"]["summary"]).group(1)
    _title(fig, t, "Node class separates; individual cells do not",
           f"Per-cell routability refuted (AUC {auc}); a per-class policy is what the data support")
    fig.subplots_adjust(left=0.24, right=0.98, top=0.78, bottom=0.18)
    return fig


def fig_confidence_map(plt, t: dict, H: dict):
    ors = QUOTED["confidence_map_or"]
    fig, ax = _new(plt, t, 7.2, 2.5)
    ax.set_xscale("log")
    labels = ["run 1", "run 2", "run 3"]
    for i, v in enumerate(reversed(ors)):
        ax.plot(v, i, "o", color=t["blue"], markersize=8)
        ax.text(v * 1.12, i, f"OR {v:.2f}", va="center", fontsize=9, color=t["text"])
    ax.axvline(1, color=t["muted"], linewidth=1)
    ax.text(1, 2.45, " no relationship", color=t["muted"], fontsize=8.4, va="bottom")
    ax.set_yticks(range(3), list(reversed(labels)), color=t["text"])
    ax.set_ylim(-0.5, 2.9)
    ax.set_xlim(0.15, 8)
    from matplotlib.ticker import NullFormatter, NullLocator
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks([0.25, 0.5, 1, 2, 4], ["0.25", "0.5", "1", "2", "4"])
    ax.set_xlabel("common odds ratio: replica agreement vs. answer-key correctness (log scale)",
                  color=t["muted"], fontsize=9)
    _title(fig, t, "Agreement between replicas does not predict quality",
           "Three runs land above, below and astride 1 · the confidence map was withdrawn, not demoted")
    fig.subplots_adjust(left=0.1, right=0.98, top=0.74, bottom=0.2)
    return fig


FIGURES = {"coherence_tax": fig_coherence_tax, "extraction_arms": fig_extraction,
           "extraction_fidelity": fig_fidelity, "tax_by_node_class": fig_node_class,
           "confidence_map": fig_confidence_map}


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"svg.fonttype": "none", "font.family": "sans-serif",
                         "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
                         "svg.hashsalt": "swarmbly"})
    H = _harness()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        for theme, t in THEMES.items():
            fig = fn(plt, t, H)
            fig.savefig(OUT / f"{name}_{theme}.svg", format="svg", metadata={"Date": None})
            plt.close(fig)
            print("wrote", OUT / f"{name}_{theme}.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
