#!/usr/bin/env python3
"""Draw the charts and the animation of the Swarmbly AI README.

Same palette and style as SwarmblyCore/scripts/readme_figures.py and the LCE
figures, in a light and a dark variant (the README serves them with
<picture>). Every value comes from a published record, named next to it in
``DATA``; the coverage panel is a simulation of SwarmblyCore's coverage model
(analytic curve and Monte Carlo points). Requires matplotlib.

    python scripts/readme_figures.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"

THEMES = {
    "light": {"text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3de", "blue": "#2a78d6",
              "orange": "#eb6834", "gray": "#a3a29c", "red": "#e34948", "green": "#1f9d6b",
              "panel": "#f6f5f1", "edge": "#d6d4cc"},
    "dark": {"text": "#f0efec", "muted": "#c3c2b7", "grid": "#3a3a37", "blue": "#3987e5",
             "orange": "#d95926", "gray": "#77766f", "red": "#e66767", "green": "#38c58e",
             "panel": "#1b1c1a", "edge": "#3a3a37"},
}

#: Published values. Each tuple: (label, value, maximum), with its record.
DATA = {
    # SwarmblyApp/docs/CHANGELOG.md, rounds 10b, 11a and 12 (LAN, 4 nodes, 3 repetitions each)
    "evidence": [
        ("IUCN status of 8 species", [("without evidence", 2 / 3, 8), ("Wikipedia only", 11 / 3, 8),
                                       ("Wikidata + Wikipedia + PubMed", 8, 8)]),
        ("Year of 5 Galápagos events", [("without evidence", 1 / 3, 5), ("Wikidata + Wikipedia", 2, 5),
                                         ("+ event subject resolution", 5, 5)]),
        ("Year of 10 historical events", [("without evidence", 10, 10), ("with evidence", 10, 10)]),
    ],
    # SwarmblyApp/docs/CHANGELOG.md, P2e rounds 1, 9, 9c, 11b and 13c: 16 questions on one person's
    # documents, 44 key elements, mean of the repetitions. DEVELOPMENT set, not held out.
    "local": [
        ("no memory", 1 / 3), ("C1, keywords only\n(round 1)", 7.0), ("hybrid retrieval\n(round 9)", 92 / 3),
        ("+ public evidence,\n27B writer (9c)", 94 / 3), ("+ Wikidata\n(11b)", 36.5),
        ("+ headings, overlap,\nformats (13c)", 38.5),
    ],
}


def _style(ax, t, grid="x"):
    ax.set_facecolor("none")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(colors=t["muted"], length=0, labelsize=9)
    (ax.xaxis if grid == "x" else ax.yaxis).grid(True, color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def evidence(plt, t, path):
    groups = DATA["evidence"]
    heights = [len(g[1]) for g in groups]
    fig, axes = plt.subplots(len(groups), 1, figsize=(7.2, 0.42 * sum(heights) + 1.5),
                             gridspec_kw={"height_ratios": heights}, sharex=True)
    fig.patch.set_alpha(0)
    for ax, (title, bars) in zip(axes, groups):
        _style(ax, t)
        palette = [t["gray"], t["blue"], t["green"]] if len(bars) == 3 else [t["gray"], t["green"]]
        for i, (label, v, mx) in enumerate(bars):
            pct = 100 * v / mx
            ax.barh(i, pct, color=palette[i], height=0.66)
            ax.text(pct + 1.5, i, f"{pct:.0f} %", va="center", color=t["text"], fontsize=8.5)
        ax.set_yticks(range(len(bars)))
        ax.set_yticklabels([b[0] for b in bars], color=t["muted"], fontsize=8.5)
        ax.invert_yaxis()
        ax.set_title(title, color=t["text"], fontsize=9.5, fontweight="bold", loc="left", pad=4)
    axes[-1].set_xlim(0, 112)
    axes[-1].set_xticks([0, 25, 50, 75, 100])
    axes[-1].set_xticklabels(["0 %", "25 %", "50 %", "75 %", "100 %"])
    fig.suptitle("Public evidence on the LAN network: correct answers (mean of 3 runs)",
                 color=t["text"], fontsize=10, x=0.02, ha="left")
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def local(plt, t, path):
    rows = DATA["local"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    fig.patch.set_alpha(0)
    _style(ax, t, grid="y")
    xs = range(len(rows))
    vals = [v for _, v in rows]
    ax.plot(xs, vals, color=t["blue"], linewidth=2, marker="o", markersize=6, zorder=3)
    for x, v in zip(xs, vals):
        ax.text(x, v + 1.6, f"{v:.1f}", ha="center", color=t["text"], fontsize=8.5)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([n for n, _ in rows], fontsize=7.5, color=t["muted"])
    ax.set_xlim(-0.4, len(rows) - 0.6)
    ax.set_ylim(0, 48)
    ax.set_yticks([0, 11, 22, 33, 44])
    ax.axhline(44, color=t["grid"], linewidth=1, linestyle="--")
    ax.text(len(rows) - 1, 45, "44 key facts", ha="right", color=t["muted"], fontsize=7.5)
    ax.set_title("Answers about one person's own documents (development set, 16 questions)",
                 color=t["text"], fontsize=10, loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def coverage(plt, t, path):
    """SwarmblyCore's coverage model: replicas per unit ~ Poisson(c), each lost with
    probability p, so a unit stays uncovered with probability exp(-c(1-p)); the
    design rule is c >= ln(1/eps)/(1-p). Curves: analytic. Dots: Monte Carlo."""
    rng = random.Random(7)
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    fig.patch.set_alpha(0)
    _style(ax, t, grid="y")
    eps = 0.01
    for p, color in ((0.1, t["green"]), (0.3, t["blue"]), (0.5, t["orange"])):
        cs = [i / 10 for i in range(5, 101)]
        ax.plot(cs, [math.exp(-c * (1 - p)) for c in cs], color=color, linewidth=2,
                label=f"loss p = {p:.0%}")
        for c in range(1, 11):
            n, miss = 6000 * c, 0
            for _ in range(n):
                k = _poisson(rng, c)
                miss += all(rng.random() < p for _ in range(k))
            if miss:
                ax.plot(c, miss / n, "o", color=color, markersize=4, alpha=0.85)
        need = math.log(1 / eps) / (1 - p)
        ax.axvline(need, color=color, linewidth=0.8, linestyle=":")
        ax.text(need, 1.6e-4, f" c ≥ {need:.1f}", color=color, fontsize=7.5, ha="left")
    ax.axhline(eps, color=t["muted"], linewidth=0.8, linestyle="--")
    ax.text(0.6, eps * 0.62, "ε = 1 % uncovered", ha="left", color=t["muted"], fontsize=7.5)
    ax.set_yscale("log")
    ax.set_ylim(1e-4, 1)
    ax.set_xlim(0.5, 10)
    ax.set_xlabel("replicas per unit (c)", color=t["muted"], fontsize=8.5)
    ax.set_ylabel("fraction left uncovered", color=t["muted"], fontsize=8.5)
    leg = ax.legend(frameon=False, fontsize=8, loc="upper right")
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    ax.set_title("Simulation: how many replicas keep every unit covered (lines: model, dots: Monte Carlo)",
                 color=t["text"], fontsize=9.5, loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


def _poisson(rng, lam):
    l, k, prod = math.exp(-lam), 0, rng.random()
    while prod > l:
        k += 1
        prod *= rng.random()
    return k


def flow_svg(t, path):
    """Animated diagram (SMIL): a public batch is cut into fragments, sent once to
    nodes of different model families and assembled locally; the user's documents
    stay on the device."""
    W, H, cyc = 920, 320, 7
    nodes = [("llama", 660, 112), ("qwen", 760, 186), ("phi", 660, 260)]
    frag_colors = [t["blue"], t["green"], t["orange"]]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
             f'font-family="ui-sans-serif, -apple-system, Segoe UI, Helvetica, Arial, sans-serif">',
             f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="{t["panel"]}" stroke="{t["edge"]}"/>']

    def box(x, y, w, h, label, sub=""):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{t["panel"]}" stroke="{t["muted"]}" stroke-width="1.4"/>')
        parts.append(f'<text x="{x+w/2}" y="{y+h/2-(5 if sub else -5)}" text-anchor="middle" font-size="14" fill="{t["text"]}" font-weight="600">{label}</text>')
        if sub:
            parts.append(f'<text x="{x+w/2}" y="{y+h/2+14}" text-anchor="middle" font-size="11" fill="{t["muted"]}">{sub}</text>')

    def hexagon(cx, cy, r, color, label):
        pts = " ".join(f"{cx + r*math.cos(math.radians(60*i-30)):.1f},{cy + r*math.sin(math.radians(60*i-30)):.1f}" for i in range(6))
        parts.append(f'<polygon points="{pts}" fill="{t["panel"]}" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="11.5" fill="{t["text"]}">{label}</text>')

    parts.append(f'<text x="24" y="36" font-size="15" fill="{t["text"]}" font-weight="700">Fragment the problem, not the model</text>')
    parts.append(f'<text x="24" y="57" font-size="11.5" fill="{t["muted"]}">Each fragment crosses the network once; the answer is assembled on your computer, your documents never leave it.</text>')
    # your computer region
    parts.append(f'<rect x="16" y="76" width="404" height="230" rx="12" fill="none" stroke="{t["green"]}" stroke-width="1.4" stroke-dasharray="6 5"/>')
    parts.append(f'<text x="30" y="96" font-size="11" fill="{t["green"]}" font-weight="600">YOUR COMPUTER</text>')
    parts.append(f'<text x="896" y="96" text-anchor="end" font-size="11" fill="{t["blue"]}" font-weight="600">VOLUNTEER NODES</text>')
    # links (drawn first)
    parts.append(f'<path d="M152,140 L218,140" stroke="{t["muted"]}" stroke-width="1.6"/>')
    parts.append(f'<path d="M152,250 L186,250" stroke="{t["green"]}" stroke-width="1.6" stroke-dasharray="4 4" fill="none"/>')
    parts.append(f'<path d="M270,184 L270,222" stroke="{t["muted"]}" stroke-width="1.6"/>')
    outs, backs = [], []
    for name, x, y in nodes:
        outs.append(f"M318,140 C460,140 520,{y} {x-34},{y}")
        backs.append(f"M{x-34},{y} C540,{y} 470,252 382,252")
    for d in outs:
        parts.append(f'<path d="{d}" stroke="{t["grid"]}" stroke-width="1.4" fill="none"/>')
    for d in backs:
        parts.append(f'<path d="{d}" stroke="{t["grid"]}" stroke-width="1.4" stroke-dasharray="3 4" fill="none"/>')
    box(32, 110, 120, 60, "Request", "6 items")
    box(32, 220, 120, 60, "Documents", "stay local")
    hexagon(270, 140, 48, t["green"], "orchestrator")
    box(186, 222, 196, 62, "Assembly", "vote per item · sources")
    for name, x, y in nodes:
        hexagon(x, y, 34, t["blue"], name)
    # request dot
    parts.append(f'<circle r="6" fill="{t["text"]}"><animateMotion dur="{cyc}s" repeatCount="indefinite" '
                 f'keyPoints="0;1;1" keyTimes="0;0.12;1" calcMode="linear" path="M152,140 L218,140"/>'
                 f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.12;0.13;1" dur="{cyc}s" repeatCount="indefinite"/></circle>')
    for i, (name, x, y) in enumerate(nodes):
        c = frag_colors[i]
        parts.append(f'<rect x="-9" y="-6" width="18" height="12" rx="3" fill="{c}" opacity="0">'
                     f'<animateMotion dur="{cyc}s" repeatCount="indefinite" calcMode="linear" '
                     f'keyPoints="0;0;1;1" keyTimes="0;0.15;0.42;1" path="{outs[i]}"/>'
                     f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.15;0.42;0.43;1" dur="{cyc}s" repeatCount="indefinite"/></rect>')
        parts.append(f'<circle cx="{x}" cy="{y}" r="34" fill="none" stroke="{c}" stroke-width="2" opacity="0">'
                     f'<animate attributeName="opacity" values="0;0;0.8;0;0" keyTimes="0;0.42;0.5;0.58;1" dur="{cyc}s" repeatCount="indefinite"/>'
                     f'<animate attributeName="r" values="34;34;44;50;34" keyTimes="0;0.42;0.5;0.58;1" dur="{cyc}s" repeatCount="indefinite"/></circle>')
        parts.append(f'<circle r="6" fill="{c}" opacity="0"><animateMotion dur="{cyc}s" repeatCount="indefinite" calcMode="linear" '
                     f'keyPoints="0;0;1;1" keyTimes="0;0.58;0.8;1" path="{backs[i]}"/>'
                     f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;0.57;0.58;0.8;0.81;1" dur="{cyc}s" repeatCount="indefinite"/></circle>')
    parts.append(f'<rect x="186" y="222" width="196" height="62" rx="10" fill="{t["green"]}" opacity="0">'
                 f'<animate attributeName="opacity" values="0;0;0.25;0.25;0" keyTimes="0;0.82;0.86;0.97;1" dur="{cyc}s" repeatCount="indefinite"/></rect>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["svg.hashsalt"] = "swarmbly"
    plt.rcParams["font.family"] = "DejaVu Sans"
    OUT.mkdir(parents=True, exist_ok=True)
    for name, t in THEMES.items():
        evidence(plt, t, OUT / f"evidence_effect_{name}.svg")
        local(plt, t, OUT / f"local_answers_{name}.svg")
        coverage(plt, t, OUT / f"coverage_simulation_{name}.svg")
        flow_svg(t, OUT / f"flow_animated_{name}.svg")
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
