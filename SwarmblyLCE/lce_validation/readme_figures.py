"""Figuras del README, derivadas de los resultados guardados.

Cada figura se dibuja en dos variantes (clara y oscura) con los mismos datos;
el README las sirve con <picture> según el tema del lector. Ninguna cifra se
escribe a mano: todas salen de los JSON de results/. Requiere matplotlib
(opcional; no es dependencia del paquete).

    python -m lce_validation.readme_figures
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "figures"

THEMES = {
    "light": {"text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3de", "blue": "#2a78d6",
              "orange": "#eb6834", "gray": "#a3a29c", "zero": "#52514e"},
    "dark": {"text": "#f0efec", "muted": "#c3c2b7", "grid": "#3a3a37", "blue": "#3987e5",
             "orange": "#d95926", "gray": "#77766f", "zero": "#c3c2b7"},
}


def _load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _signed(x: float) -> str:
    return f"{x:+.3f}".replace("-", "−")


def _setup(plt, t: dict, w: float, h: float):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_alpha(0)
    _style(ax, t)
    return fig, ax


def _style(ax, t: dict) -> None:
    ax.set_facecolor("none")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(colors=t["muted"], length=0, labelsize=9)
    ax.xaxis.grid(True, color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def _title(fig, t: dict, title: str, sub: str) -> None:
    fig.text(0.01, 0.97, title, ha="left", va="top", fontsize=11.5, weight="bold", color=t["text"])
    fig.text(0.01, 0.905, sub, ha="left", va="top", fontsize=8.8, color=t["muted"])


def fig_f1a(plt, t: dict):
    s = _load("results/bench_hc1_scale/results.json")["summary"]
    refused = {m for m, _, _ in s["refusals"]}
    rows = sorted(s["by_model"].items(), key=lambda kv: kv[1]["mean_gain"])
    fig, ax = _setup(plt, t, 7.2, 3.1)
    for i, (m, v) in enumerate(rows):
        col = t["gray"] if m in refused else t["blue"]
        ax.barh(i, v["mean_gain"], height=0.55, color=col)
        note = "  (3 of 5 users refused: < 5 anchored claims)" if m in refused else ""
        ax.text(v["mean_gain"] + 0.01, i, f"{_signed(v['mean_gain'])}{note}", va="center",
                fontsize=8.8, color=t["text"])
    ax.axvline(s["mean_gain_by_question"], color=t["muted"], linestyle=(0, (3, 3)), linewidth=1)
    lo, hi = s["gain_ci95_by_question"]
    ax.text(s["mean_gain_by_question"], len(rows) - 0.35,
            f" mean {_signed(s['mean_gain_by_question'])} [{lo:.3f}, {hi:.3f}]",
            fontsize=8.5, color=t["muted"], va="bottom")
    ax.set_yticks(range(len(rows)), [m for m, _ in rows], color=t["text"])
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("accuracy gain with local memory (with − without)", color=t["muted"], fontsize=9)
    _title(fig, t, "Local memory helps all five model families",
           "F1a, exploratory · 5 synthetic users × 12 questions · question-clustered 95 % CI")
    fig.subplots_adjust(left=0.2, right=0.98, top=0.8, bottom=0.17)
    return fig


ARM_LABELS = [("A0", "A0 · no memory"), ("A1", "A1 · first 200 words"), ("A2", "A2 · raw RAG"),
              ("A3", "A3 · LCE wiki"), ("A4", "A4 · wiki + Γ")]


def fig_r13_arms(plt, t: dict):
    s = _load("results/bench_r13_confirm/results.json")["summary"]
    fig, ax = _setup(plt, t, 7.2, 3.0)
    rows = list(reversed(ARM_LABELS))
    for i, (k, lab) in enumerate(rows):
        col = t["orange"] if k == "A2" else (t["blue"] if k in ("A3", "A4") else t["gray"])
        v = s["mean_by_arm"][k]
        ax.barh(i, v, height=0.55, color=col)
        ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=9, color=t["text"])
    ax.set_yticks(range(len(rows)), [lab for _, lab in rows], color=t["text"])
    ax.set_xlim(0, 0.75)
    ax.set_xlabel("accuracy (251 questions, 3 responders; A3 = 3 digesters × 3 responders)",
                  color=t["muted"], fontsize=9)
    an = _load("results/bench_r13_confirm/analysis.json")["a3_minus_a2"]
    lo, hi = an["ci95"]
    _title(fig, t, "Raw retrieval beats the digested wiki",
           f"R13 confirmatory · same 200-token budget · A3 − A2 = {_signed(an['mean'])} "
           f"[{_signed(lo)}, {_signed(hi)}]")
    fig.subplots_adjust(left=0.24, right=0.98, top=0.8, bottom=0.17)
    return fig


TYPE_LABELS = {"simple": "simple", "cross": "cross-document", "updated": "updated",
               "contradiction": "contradiction", "deleted": "deleted (N2 artefact)",
               "unanswerable": "unanswerable"}


def fig_r13_types(plt, t: dict):
    an = _load("results/bench_r13_confirm/analysis.json")
    rows = [("overall", an["a3_minus_a2"])] + [(TYPE_LABELS[k], v) for k, v in an["a3_minus_a2_by_type"].items()]
    rows = list(reversed(rows))
    fig, ax = _setup(plt, t, 7.2, 3.4)
    for i, (lab, d) in enumerate(rows):
        col = t["gray"] if lab.startswith("deleted") else t["blue"]
        lo, hi = d["ci95"]
        ax.plot([lo, hi], [i, i], color=col, linewidth=2, solid_capstyle="round")
        ax.plot(d["mean"], i, "o", color=col, markersize=7 if lab == "overall" else 6)
        ax.text(0.40, i, f"{_signed(d['mean'])}  n={d['n_questions']}", va="center", fontsize=8.6,
                color=t["text"], ha="right")
    ax.axvline(0, color=t["zero"], linewidth=1)
    ax.set_yticks(range(len(rows)), [lab for lab, _ in rows], color=t["text"])
    for lbl in ax.get_yticklabels():
        if lbl.get_text() == "overall":
            lbl.set_fontweight("bold")
    ax.set_xlim(-0.45, 0.42)
    ax.set_xlabel("A3 − A2 (wiki − raw RAG), 95 % CI · left of 0: RAG better", color=t["muted"], fontsize=9)
    _title(fig, t, "No answerable question type favours the wiki",
           "R13 confirmatory · `deleted` never showed the source to any arm: it does not measure forgetting")
    fig.subplots_adjust(left=0.24, right=0.98, top=0.82, bottom=0.15)
    return fig


def fig_coverage(plt, t: dict):
    an = _load("results/bench_r13_confirm/analysis.json")
    cov = an["gold_in_context_answerable"]
    acc = an["abstention_with_accuracy"]
    rows = [("raw RAG", cov["A2"], acc["A2"]["answerable_accuracy"], t["orange"])]
    for g, lab in (("gemma2:2b", "wiki · gemma2"), ("qwen2.5:3b", "wiki · qwen2.5"), ("llama3.2:3b", "wiki · llama3.2")):
        rows.append((lab, cov["A3|" + g], acc["A3|" + g]["answerable_accuracy"], t["blue"]))
    rows = list(reversed(rows))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
    fig.patch.set_alpha(0)
    for ax, idx, xl, fmt in ((a1, 1, "answer key reaches the context", "{:.1%}"),
                              (a2, 2, "accuracy on answerable questions", "{:.3f}")):
        _style(ax, t)
        for i, r in enumerate(rows):
            ax.barh(i, r[idx], height=0.55, color=r[3])
            ax.text(r[idx] + 0.015, i, fmt.format(r[idx]).replace("%", " %"), va="center", fontsize=8.8,
                    color=t["text"])
        ax.set_xlim(0, 1.15)
        ax.set_xlabel(xl, color=t["muted"], fontsize=9)
    a1.set_yticks(range(len(rows)), [r[0] for r in rows], color=t["text"])
    _title(fig, t, "Where the wiki loses: digestion drops the answer",
           f"R13 confirmatory · {cov['n_questions']} answerable questions · same order in both panels")
    fig.subplots_adjust(left=0.17, right=0.98, top=0.78, bottom=0.18, wspace=0.08)
    return fig


def fig_forget(plt, t: dict):
    bp = _load("results/bench_forget/analysis.json")["behaviour_prereg"]
    ab = bp["abstention"]
    rows = [("W_full · digested with the source", ab["full"], t["gray"]),
            ("W_forget · after forget_source", ab["forget"], t["blue"]),
            ("W_never · never saw the source", ab["never"], t["blue"])]
    rows = list(reversed(rows))
    fig, ax = _setup(plt, t, 7.2, 2.6)
    for i, (lab, v, col) in enumerate(rows):
        hatch = "////" if lab.startswith("W_never") else None
        ax.barh(i, v, height=0.55, color="none" if hatch else col, edgecolor=col, hatch=hatch, linewidth=1.5)
        ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=9, color=t["text"])
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], color=t["text"])
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("abstention on questions about the forgotten source", color=t["muted"], fontsize=9)
    lo, hi = bp["forget_minus_full_ci95"]
    _title(fig, t, "Forgetting a source returns behaviour to the never-seen level",
           f"F-forget · forget − full = {_signed(bp['forget_minus_full'])} [{_signed(lo)}, {_signed(hi)}] · "
           f"5 questions, mechanism only")
    fig.subplots_adjust(left=0.36, right=0.98, top=0.76, bottom=0.2)
    return fig


FIGURES = {"f1a_memory_gain": fig_f1a, "r13_arms": fig_r13_arms, "r13_types": fig_r13_types,
           "r13_coverage": fig_coverage, "forget_abstention": fig_forget}


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"svg.fonttype": "none", "font.family": "sans-serif",
                         "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
                         "svg.hashsalt": "swarmbly-lce", "hatch.linewidth": 1.0})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        for theme, t in THEMES.items():
            fig = fn(plt, t)
            fig.savefig(OUT / f"{name}_{theme}.svg", format="svg", metadata={"Date": None})
            plt.close(fig)
            print("escrita", OUT / f"{name}_{theme}.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
