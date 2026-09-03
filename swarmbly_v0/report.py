"""Self-contained HTML report for a V0 sweep.

Renders the coherence-tax-vs-``rho`` curve plus the supporting tables from a
results CSV. The output is a single file with inline CSS and inline JS and no
CDN references, so it survives being emailed, committed, or opened offline.

Two charts, both built by the same helpers and both obeying the same rules:

1. the macro-level headline curve -- coherence tax against ``rho``;
2. the micro-level calibration -- judged acceptability rate against agreement
   score, binned.

Chart conventions applied here:

* one **single-series** line per chart; the per-``N``, per-category and per-``k``
  breakdowns are tables, not extra series
* categorical palette slot 1: ``#2a78d6`` (light) / ``#3987e5`` (dark)
* 2px stroke, 10px-diameter markers
* recessive grid: hairline, low-contrast, horizontal only
* direct labels on the series and on every point -- no legend
* **no dual axis**; a second instrument gets its own table column or its own
  chart, never a second y-scale
* a hover tooltip on every marker (inline SVG ``<title>``: no script, no CDN)
* a data-table view toggled from each chart, so every plotted number is
  readable as text
"""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Sequence

from .experiment import UNIT_CSV_NAME, PromptSpec, read_unit_rows, summarize

__all__ = ["render_report", "read_rows"]

_WIDTH = 840
_HEIGHT = 420
_MARGIN = {"left": 70, "right": 168, "top": 28, "bottom": 56}

_CSS = """
:root {
  --bg: #ffffff; --panel: #f7f8fa; --fg: #14181f; --muted: #5b6472;
  --grid: #e3e7ed; --axis: #aab2be; --series1: #2a78d6; --accent-soft: #eaf1fb;
  --warn-bg: #fff7e6; --warn-fg: #7a4f00; --warn-border: #e8c979;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #10141a; --panel: #171d26; --fg: #e8ecf2; --muted: #98a2b3;
    --grid: #242c38; --axis: #3a4453; --series1: #3987e5; --accent-soft: #17263a;
    --warn-bg: #2a2213; --warn-fg: #f0c66a; --warn-border: #5c4a1f;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 24px 72px; background: var(--bg); color: var(--fg);
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
main { max-width: 980px; margin: 0 auto; }
h1 { font-size: 26px; letter-spacing: -0.01em; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 40px 0 10px; letter-spacing: -0.005em; }
p.sub { color: var(--muted); margin: 0 0 24px; }
.warn {
  background: var(--warn-bg); color: var(--warn-fg); border: 1px solid var(--warn-border);
  border-radius: 10px; padding: 14px 16px; margin: 0 0 28px; font-size: 14px;
}
.warn strong { letter-spacing: 0.01em; }
.card { background: var(--panel); border-radius: 12px; padding: 20px 20px 12px; }
.kpis { display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 28px; }
.kpi {
  background: var(--panel); border-radius: 10px; padding: 12px 16px; min-width: 168px;
}
.kpi .label { color: var(--muted); font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.06em; }
.kpi .value { font-size: 22px; font-variant-numeric: tabular-nums; margin-top: 2px; }
.toggle { display: flex; gap: 6px; margin: 0 0 14px; }
.toggle button {
  font: inherit; font-size: 13px; padding: 6px 14px; border-radius: 999px;
  border: 1px solid var(--grid); background: transparent; color: var(--muted); cursor: pointer;
}
.toggle button[aria-pressed="true"] {
  background: var(--accent-soft); color: var(--series1); border-color: var(--series1);
}
table { border-collapse: collapse; width: 100%; font-size: 13.5px;
  font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--grid); }
th:first-child, td:first-child { text-align: left; }
thead th { color: var(--muted); font-weight: 600; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.05em; }
tbody tr:hover { background: var(--accent-soft); }
.scroll { max-height: 460px; overflow: auto; }
.hidden { display: none; }
.pass { color: var(--series1); font-weight: 600; }
.fail { color: #c2453c; font-weight: 600; }
@media (prefers-color-scheme: dark) { .fail { color: #f0776c; } }
footer { color: var(--muted); font-size: 12.5px; margin-top: 44px; }
code { background: var(--panel); padding: 1px 5px; border-radius: 4px; font-size: 13px; }
svg text { font: 12px ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, sans-serif; }
"""

_JS = """
(function () {
  // Each chart owns its own toggle group, keyed by data-group, so switching
  // one chart to its table view does not switch the others with it.
  document.querySelectorAll('.toggle').forEach(function (toggle) {
    var group = toggle.getAttribute('data-group');
    var buttons = toggle.querySelectorAll('button');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var target = btn.getAttribute('data-view');
        buttons.forEach(function (b) {
          b.setAttribute('aria-pressed', String(b.getAttribute('data-view') === target));
        });
        var selector = '[data-panel][data-group="' + group + '"]';
        document.querySelectorAll(selector).forEach(function (panel) {
          panel.classList.toggle('hidden', panel.getAttribute('data-panel') !== target);
        });
      });
    });
  });
})();
"""


def read_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read a results CSV back into a list of dicts with numbers parsed."""
    numeric_prefixes = ("rho_", "coherence_tax", "quality_tax", "err_", "n_")
    numeric_exact = {
        "router_score", "booook_like_score", "entity_grid", "judge_score",
        "redundancy_self", "redundancy_between", "mean_seam_similarity",
        "input_tokens", "output_tokens", "tau_sem", "seed",
        "k", "mean_agreement", "frac_high", "frac_medium", "frac_low",
    }
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, Any] = {}
            for key, value in raw.items():
                if value == "" or value is None:
                    row[key] = ""
                    continue
                if key in numeric_exact or key.startswith(numeric_prefixes):
                    try:
                        row[key] = float(value)
                        continue
                    except ValueError:
                        pass
                if value in ("True", "False"):
                    row[key] = value == "True"
                else:
                    row[key] = value
            rows.append(row)
    return rows


def _nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """Round-ish tick values spanning ``[low, high]``."""
    if high <= low:
        high = low + 1.0
    span = high - low
    raw = span / max(count - 1, 1)
    magnitude = 10 ** (len(str(int(abs(raw)))) - 1) if abs(raw) >= 1 else 1.0
    while magnitude > abs(raw) and magnitude > 1e-9:
        magnitude /= 10.0
    step = magnitude
    for candidate in (1, 2, 2.5, 5, 10):
        if magnitude * candidate >= raw:
            step = magnitude * candidate
            break
    start = step * (int(low / step) - (1 if low < 0 else 0))
    ticks: list[float] = []
    value = start
    while value <= high + step * 0.5 and len(ticks) < 12:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _single_series_chart(
    points: Sequence[tuple[float, float, str]],
    *,
    aria_label: str,
    x_axis_label: str,
    y_axis_label: str,
    series_label: str,
    series_sublabel: str = "",
    x_tick_format: str = "{:g}",
    y_tick_format: str = "{:g}%",
    point_format: str = "{:.1f}%",
    y_floor: float | None = None,
    y_ceiling: float | None = None,
    reference: tuple[float, str] | None = None,
    empty_message: str = "Nothing to plot.",
) -> str:
    """Inline SVG for one **single-series** line chart with markers.

    The single renderer behind every chart in this report, so the conventions
    (palette slot 1, 2px stroke, 10px markers, recessive horizontal grid, direct
    labelling instead of a legend, no dual axis, a ``<title>`` tooltip per
    marker) are stated once and cannot drift apart between charts.

    Args:
        points: ``(x, y, tooltip)`` in plotting order.
        aria_label: Accessible description of the whole chart.
        x_axis_label / y_axis_label: Axis captions.
        series_label / series_sublabel: The direct label at the series end.
        x_tick_format / y_tick_format / point_format: ``str.format`` templates.
        y_floor / y_ceiling: Values the y-range must include, if any.
        reference: ``(value, label)`` for a dashed reference rule -- a rule, not
            a second series.
        empty_message: Rendered when there is nothing to plot.
    """
    if not points:
        return f'<p class="sub">{html.escape(empty_message)}</p>'

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    x_lo, x_hi = min(xs), max(xs)
    if x_hi == x_lo:
        x_lo, x_hi = x_lo - 0.1, x_hi + 0.1
    candidates = list(ys)
    if y_floor is not None:
        candidates.append(y_floor)
    if y_ceiling is not None:
        candidates.append(y_ceiling)
    if reference is not None:
        candidates.append(reference[0])
    y_lo, y_hi = min(candidates), max(candidates)
    if y_hi == y_lo:
        y_hi = y_lo + 1.0
    pad = max((y_hi - y_lo) * 0.18, 1.0)
    y_lo -= pad * 0.35
    y_hi += pad

    plot_w = _WIDTH - _MARGIN["left"] - _MARGIN["right"]
    plot_h = _HEIGHT - _MARGIN["top"] - _MARGIN["bottom"]

    def sx(value: float) -> float:
        return _MARGIN["left"] + (value - x_lo) / (x_hi - x_lo) * plot_w

    def sy(value: float) -> float:
        return _MARGIN["top"] + plot_h - (value - y_lo) / (y_hi - y_lo) * plot_h

    parts: list[str] = [
        f'<svg viewBox="0 0 {_WIDTH} {_HEIGHT}" width="100%" height="{_HEIGHT}" '
        f'role="img" aria-label="{html.escape(aria_label)}">'
    ]

    # Recessive grid: horizontal hairlines only, plus a single axis rule.
    for tick in _nice_ticks(y_lo, y_hi):
        y = sy(tick)
        if not (_MARGIN["top"] - 1 <= y <= _MARGIN["top"] + plot_h + 1):
            continue
        parts.append(
            f'<line x1="{_MARGIN["left"]}" y1="{y:.1f}" x2="{_MARGIN["left"] + plot_w}" '
            f'y2="{y:.1f}" stroke="var(--grid)" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{_MARGIN["left"] - 12}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="var(--muted)">{y_tick_format.format(tick)}</text>'
        )

    parts.append(
        f'<line x1="{_MARGIN["left"]}" y1="{_MARGIN["top"] + plot_h}" '
        f'x2="{_MARGIN["left"] + plot_w}" y2="{_MARGIN["top"] + plot_h}" '
        f'stroke="var(--axis)" stroke-width="1" />'
    )

    if reference is not None:
        ref_value, ref_label = reference
        y_ref = sy(ref_value)
        parts.append(
            f'<line x1="{_MARGIN["left"]}" y1="{y_ref:.1f}" x2="{_MARGIN["left"] + plot_w}" '
            f'y2="{y_ref:.1f}" stroke="var(--axis)" stroke-width="1" stroke-dasharray="5 4" />'
        )
        parts.append(
            f'<text x="{_MARGIN["left"] + plot_w + 8}" y="{y_ref + 4:.1f}" '
            f'fill="var(--muted)">{html.escape(ref_label)}</text>'
        )

    for x_value in xs:
        parts.append(
            f'<text x="{sx(x_value):.1f}" y="{_MARGIN["top"] + plot_h + 24}" '
            f'text-anchor="middle" fill="var(--muted)">{x_tick_format.format(x_value)}</text>'
        )
    parts.append(
        f'<text x="{_MARGIN["left"] + plot_w / 2:.1f}" y="{_HEIGHT - 12}" '
        f'text-anchor="middle" fill="var(--muted)">{html.escape(x_axis_label)}</text>'
    )
    parts.append(
        f'<text transform="translate(18,{_MARGIN["top"] + plot_h / 2:.1f}) rotate(-90)" '
        f'text-anchor="middle" fill="var(--muted)">{html.escape(y_axis_label)}</text>'
    )

    path = " ".join(
        f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(zip(xs, ys))
    )
    parts.append(
        f'<path d="{path}" fill="none" stroke="var(--series1)" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round" />'
    )

    for x, y, tooltip in points:
        parts.append(
            f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="5" fill="var(--series1)" '
            f'stroke="var(--bg)" stroke-width="2">'
            f'<title>{html.escape(tooltip)}</title></circle>'
        )
        parts.append(
            f'<text x="{sx(x):.1f}" y="{sy(y) - 14:.1f}" text-anchor="middle" '
            f'fill="var(--fg)">{point_format.format(y)}</text>'
        )

    # Direct label instead of a legend.
    parts.append(
        f'<text x="{sx(xs[-1]) + 12:.1f}" y="{sy(ys[-1]) + 4:.1f}" fill="var(--series1)" '
        f'font-weight="600">{html.escape(series_label)}</text>'
    )
    if series_sublabel:
        parts.append(
            f'<text x="{sx(xs[-1]) + 12:.1f}" y="{sy(ys[-1]) + 20:.1f}" fill="var(--muted)">'
            f'{html.escape(series_sublabel)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _line_chart(curve: Sequence[dict[str, Any]]) -> str:
    """Macro level: single-series coherence tax (%) against ``rho``."""
    # A point can be None when every cell at that rho had a denominator too small
    # to make a ratio (see MIN_BASELINE). Plotting it as zero would draw
    # "no degradation"; it is simply not plotted, and the table below still
    # reports it as "-" so the gap is visible rather than invented.
    points = [
        (
            float(c["rho"]),
            float(c["coherence_tax_booook"]) * 100.0,
            f"rho {float(c['rho']):g} (achieved {float(c['rho_achieved_mean']):.2f}) — "
            f"tax {float(c['coherence_tax_booook']) * 100:.2f}% over {c['n_cells']} cells",
        )
        for c in curve
        if isinstance(c.get("coherence_tax_booook"), (int, float))
    ]
    return _single_series_chart(
        points,
        aria_label="Coherence tax versus contextual redundancy ratio rho",
        x_axis_label="contextual redundancy ratio rho (dispatched tokens per prompt token)",
        y_axis_label="coherence tax (% relative)",
        series_label="coherence tax",
        series_sublabel="BooookScore-like",
        y_floor=0.0,
        y_ceiling=5.0,
        reference=(5.0, "5% go/no-go"),
        empty_message="No fragmented cells to plot.",
    )


def _agreement_chart(calibration: dict[str, Any]) -> str:
    """Micro level: judged acceptability rate against consensus agreement score.

    The question the chart asks is whether the agreement score is worth
    routing on. A rising line means agreement carries information about
    quality; a flat line means the confidence map is decorative and the
    ``HIGH`` label is unearned. Empty bins are skipped rather than drawn at
    zero, because "no units landed here" is not "nothing here was acceptable".
    """
    bins = [b for b in calibration.get("bins", []) if b.get("n_units")]
    points = [
        (
            float(b["midpoint"]),
            float(b["acceptability_rate"]) * 100.0,
            f"agreement {float(b['low']):.1f}–{float(b['high']):.1f} — "
            f"{float(b['acceptability_rate']) * 100:.1f}% judged acceptable "
            f"of {b['n_units']} units",
        )
        for b in bins
        if b.get("acceptability_rate") is not None
    ]
    return _single_series_chart(
        points,
        aria_label="Judged acceptability rate versus consensus agreement score",
        x_axis_label="consensus agreement score (fraction of k replicas that agree)",
        y_axis_label="judged acceptable (% of units)",
        series_label="acceptability",
        series_sublabel="per agreement bin",
        x_tick_format="{:.1f}",
        y_floor=0.0,
        empty_message="No consensus units in this run — sweep with --k greater than 1.",
    )


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


def render_report(
    csv_path: str | Path,
    out_path: str | Path,
    metadata: dict[str, Any] | None = None,
    prompts: Sequence[PromptSpec] | None = None,
) -> Path:
    """Render ``csv_path`` into a self-contained HTML report at ``out_path``.

    The per-consensus-unit sidecar written next to the CSV
    (:data:`swarmbly_v0.experiment.UNIT_CSV_NAME`) is picked up automatically
    when present, which is what lets the micro-level chart render from nothing
    but a CSV path. Its absence is not an error -- a ``k = 1`` run has no
    consensus units and says so.
    """
    rows = read_rows(csv_path)
    units = read_unit_rows(Path(csv_path).with_name(UNIT_CSV_NAME))
    stats = summarize(rows, prompts, unit_records=units)
    curve = stats["curve"]
    calibration = stats["agreement_quality_correlation"]

    meta = dict(metadata or {})
    if not meta:
        sidecar = Path(csv_path).with_name("run_metadata.json")
        if sidecar.exists():
            meta = json.loads(sidecar.read_text(encoding="utf-8"))

    backend_name = str(meta.get("backend") or (rows[0].get("backend") if rows else "unknown"))
    is_mock = backend_name == "mock" or bool(meta.get("harness_validation_only"))

    best = stats["best_overall"] or {}
    best_cell = stats["best_category_cell"] or {}
    go = stats["go_no_go"]

    warn = ""
    if is_mock:
        warn = (
            '<div class="warn"><strong>HARNESS VALIDATION ONLY — NOT EVIDENCE ABOUT '
            'LANGUAGE MODELS.</strong><br>This run used <code>MockBackend</code>, a '
            'deterministic text generator that <em>injects</em> coherence failures with a '
            'probability that decreases as packets carry more context. It performs no '
            'inference. The curve below therefore demonstrates that the planner, the rho '
            'targeting, the seam detector, the entity grid and the error taxonomy all '
            'respond to the variable under study — and nothing more. The go/no-go criterion '
            'can only be adjudicated with a real backend.</div>'
        )
    if meta.get("embeddings_degraded"):
        warn += (
            '<div class="warn"><strong>EMBEDDINGS DEGRADED TO HASHING.</strong><br>'
            'The embedding route failed during this run and the harness fell back to '
            '<code>HashEmbedder</code>, a deterministic stand-in whose cosine values '
            'carry no semantics. Everything downstream of an embedding — the calibrated '
            '<code>tau_sem</code> reported below, seam detection, and the semantic-unit '
            'alignment behind the agreement score — is therefore <em>mechanically valid '
            'and semantically meaningless</em>. Re-run with a working embedding route '
            '(<code>--embedder api</code> against a server with an <code>/embeddings</code> '
            'route, or <code>--embedder st</code>) before quoting any number from this '
            'report.</div>'
        )
    excluded = int(stats.get("rows_excluded_below_floor") or 0)
    if excluded:
        # The same banner the console now prints, because this is the file that
        # gets shared and the console output is not. `rho_reachable` was written
        # to every row from the first run and read by nothing; a curve rendered
        # with rows silently missing is how that happened.
        warn += (
            f'<div class="warn"><strong>{excluded} ROW(S) DROPPED: CONTEXT BUDGET '
            'BELOW THE PACKING FLOOR.</strong><br>A cell measures a context budget '
            'only if the budget exceeds the prompt&rsquo;s own <em>packing floor</em> — '
            'what the micro-tasks and their contract headers cost before any context is '
            'added. Below it, <code>build_packet</code> falls back to '
            '<code>budget = max(mandatory_tokens, …)</code>, every packet collapses to '
            'its bare task, and two different &rho; labels produce byte-identical '
            'packets. Those rows are excluded from every figure on this page rather '
            'than annotated, because a note beside a number does not travel with the '
            'number. They are in <code>results.csv</code> with '
            '<code>rho_reachable=false</code>. If the curve below looks sparse, this is '
            'why — and if a &rho; row is missing entirely, that budget was never '
            'measured on this corpus.</div>'
        )

    curve_table = _table(
        ["rho (target)", "rho (achieved)", "coherence tax (BooookScore-like)",
         "coherence tax (entity grid)", "cells"],
        [
            [f"{c['rho']:g}", f"{c['rho_achieved_mean']:.2f}",
             _fmt_pct(c["coherence_tax_booook"]), _fmt_pct(c["coherence_tax_entity_grid"]),
             c["n_cells"]]
            for c in curve
        ],
    )

    agreement_table = _table(
        ["agreement bin", "units", "judged acceptable"],
        [
            [f"{float(b['low']):.1f} – {float(b['high']):.1f}", b["n_units"],
             _fmt_pct(b["acceptability_rate"])]
            for b in calibration.get("bins", [])
        ],
    ) or ""

    r_value = calibration.get("pearson_r")
    if not calibration.get("n_units"):
        agreement_caption = (
            "This run swept <code>k = 1</code> only, so no replicas were compared "
            "and there is nothing to calibrate."
        )
    elif r_value is None:
        agreement_caption = (
            f"{calibration['n_units']} units; the correlation is undefined because one "
            "of the two variables is constant."
        )
    else:
        agreement_caption = (
            f"Point-biserial r = <strong>{r_value:+.3f}</strong> over "
            f"{calibration['n_units']} units "
            f"(acceptance rate {_fmt_pct(calibration['acceptance_rate'])}). "
            "Agreement is not truth: models sharing training data share errors, so this "
            "correlation is the thing to measure, never to assume."
        )

    consensus_curve = stats.get("consensus_curve", [])
    consensus_html = ""
    if any(int(c["k"]) > 1 for c in consensus_curve):
        consensus_html = (
            "<h2>Consensus by replica count k</h2>"
            + _table(
                ["k", "families (mean)", "mean agreement", "HIGH", "MEDIUM", "LOW",
                 "low-confidence regions", "coherence tax", "cells"],
                [
                    [c["k"], f"{c['n_families_mean']:.1f}", f"{c['mean_agreement']:.3f}",
                     _fmt_pct(c["frac_high"]), _fmt_pct(c["frac_medium"]),
                     _fmt_pct(c["frac_low"]), c["n_low_conf_regions"],
                     _fmt_pct(c["coherence_tax_booook"]), c["n_cells"]]
                    for c in consensus_curve
                ],
            )
            + '<p class="sub">HIGH takes the medoid unjudged, MEDIUM and LOW are '
              'judge-selected, and LOW additionally marks a low-confidence region in the '
              'answer. The two alphas that separate them are provisional placeholders '
              'and must be calibrated exactly as tau_sem is.</p>'
        )

    kpis = [
        ("backend", backend_name),
        ("rho swept", ", ".join(f"{c['rho']:g}" for c in curve) or "-"),
        ("best rho", f"{best.get('rho', '-'):g}" if best else "-"),
        ("tax at best rho", _fmt_pct(best.get("coherence_tax_booook"))),
        ("tau_sem (calibrated)", f"{float(meta.get('tau_sem', 0)):.3f}" if meta.get("tau_sem")
         else "-"),
        ("fragmented cells", str(stats["n_fragmented_cells"])),
        ("k swept", ", ".join(f"{int(c['k'])}" for c in consensus_curve) or "-"),
        ("agreement vs quality r",
         f"{r_value:+.3f}" if isinstance(r_value, (int, float)) else "-"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(str(value))}</div></div>'
        for label, value in kpis
    )

    by_rho_n = _table(
        ["rho", "N", "coherence tax (BooookScore-like)"],
        [[f"{r['rho']:g}", r["n_tasks"], _fmt_pct(r["coherence_tax_booook"])]
         for r in stats["by_rho_n"]],
    )

    category_table = _table(
        ["category", "rho", "coherence tax", "clears 5%?"],
        [
            [c["category"], f"{c['rho']:g}", _fmt_pct(c["coherence_tax_booook"]),
             ("yes" if isinstance(c["coherence_tax_booook"], (int, float))
                        and c["coherence_tax_booook"] < 0.05 else "no")]
            for c in stats["category_curve"]
        ],
    )

    raw_headers = [k for k in (rows[0].keys() if rows else []) if k]
    raw_table = _table(
        raw_headers,
        [[row.get(h, "") for h in raw_headers] for row in rows],
    )

    verdict_class = "pass" if go["passed"] else "fail"
    verdict_text = (
        f"{'MET' if go['passed'] else 'NOT MET'} — {len(go['passing_cells'])} "
        f"(category, rho) cell(s) below 5% relative degradation"
    )

    router_html = ""
    if "router" in stats:
        r = stats["router"]
        router_html = (
            "<h2>Router (decomposability gate)</h2>"
            + _table(
                ["threshold", "accuracy", "precision", "recall", "false-positive rate",
                 "TP", "FP", "TN", "FN"],
                [[f"{r['threshold']:.2f}", f"{r['accuracy']:.2f}", f"{r['precision']:.2f}",
                  f"{r['recall']:.2f}", f"{r['false_positive_rate']:.2f}",
                  r["confusion"]["tp"], r["confusion"]["fp"], r["confusion"]["tn"],
                  r["confusion"]["fn"]]],
            )
            + '<p class="sub">The threshold is above 0.5 on purpose: a false-positive '
              'fragmentation degrades an answer the user receives, while a false negative '
              'only forgoes speedup.</p>'
        )

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Swarmbly AI — V0 coherence tax</title>
<style>{_CSS}</style>
</head>
<body>
<main>
  <h1>V0 — Coherence tax vs contextual redundancy</h1>
  <p class="sub">How much output quality is lost by fragmenting and reassembling,
     as a function of how much context travels with each fragment.
     Coherence tax = relative degradation against monolithic generation.</p>
  {warn}
  <div class="kpis">{kpi_html}</div>

  <h2>Headline curve — macro level</h2>
  <p class="sub">Macro assembly joins different sub-tasks of one task by
     overlap-and-splice. This is the curve <code>rho</code> controls.</p>
  <div class="toggle" data-group="tax">
    <button data-view="chart" aria-pressed="true">Chart</button>
    <button data-view="table" aria-pressed="false">Data</button>
  </div>
  <div class="card" data-panel="chart" data-group="tax">{_line_chart(curve)}</div>
  <div class="card hidden" data-panel="table" data-group="tax">{curve_table}</div>

  <h2>Agreement vs judged quality — micro level</h2>
  <p class="sub">Micro assembly resolves <code>k</code> complete replicas of the
     <em>same</em> micro-task, produced by different model families, by multiple
     alignment plus a per-unit agreement score. This chart asks the only
     question that makes the agreement score worth reporting: does it predict
     quality? {agreement_caption}</p>
  <div class="toggle" data-group="agreement">
    <button data-view="chart" aria-pressed="true">Chart</button>
    <button data-view="table" aria-pressed="false">Data</button>
  </div>
  <div class="card" data-panel="chart" data-group="agreement">{_agreement_chart(calibration)}</div>
  <div class="card hidden" data-panel="table" data-group="agreement">{agreement_table}</div>

  {consensus_html}

  <h2>Go / no-go criterion</h2>
  <p>There must exist a <code>rho</code> at which coherence degradation is under 5%
     relative to monolithic generation, in at least one task category.
     Verdict: <span class="{verdict_class}">{verdict_text}</span>.
     Best cell: <code>{html.escape(str(best_cell.get('category', '-')))}</code> at
     rho = {best_cell.get('rho', '-')} with a tax of
     {_fmt_pct(best_cell.get('coherence_tax_booook'))}.</p>

  <h2>Coherence tax by rho and N</h2>
  {by_rho_n}

  <h2>Coherence tax by category</h2>
  {category_table}

  {router_html}

  <h2>All rows</h2>
  <div class="scroll">{raw_table}</div>

  <footer>
    Generated by <code>swarmbly_v0.report</code> from
    <code>{html.escape(str(Path(csv_path).name))}</code>.
    Backend <code>{html.escape(backend_name)}</code>,
    embedder <code>{html.escape(str(meta.get('embedder', 'hash')))}</code>,
    seed <code>{html.escape(str(meta.get('seed', '0')))}</code>,
    tau_sem <code>{html.escape(str(meta.get('tau_sem', 'n/a')))}</code>
    (calibrated with an asymmetric F-beta, beta =
    <code>{html.escape(str(meta.get('beta', '0.5')))}</code>).
    Self-contained: no external requests.
  </footer>
</main>
<script>{_JS}</script>
</body>
</html>
"""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    return target
