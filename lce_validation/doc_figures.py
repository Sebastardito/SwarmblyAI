"""Anclaje de las cifras citadas en los documentos (preregistro R14 1.3.2).

Cada entrada dice: «este documento debe contener esta cifra, y la cifra se
calcula aquí desde los JSON guardados». Si alguien edita una cifra a mano, o
si una re-corrida cambia los datos sin actualizar el texto, la prueba
``tests/test_doc_figures.py`` falla. Cubre las cifras vigentes de F1a y R13
en los documentos de resultados (pilotos y confirmatorias de R13, F-forget,
A/A, R11, C2-bis y cierre de H-C2), la SWIP, STATUS, README y el whitepaper v0.2.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _s(x: float, sign: bool = True) -> str:
    return (f"{x:+.3f}" if sign else f"{x:.3f}").replace("-", "−")


def _pair(d: dict, plus: bool = True) -> str:
    """'−0.256 [−0.317, −0.194]', '+0.156 [−0.067, +0.378]': siempre con signo."""
    lo, hi = d["ci95"]
    return f"{_s(d['mean'])} [{_s(lo)}, {_s(hi)}]"


def expected() -> list[tuple[str, str]]:
    an = json.loads((ROOT / "results" / "bench_r13" / "analysis.json").read_text(encoding="utf-8"))
    r13 = json.loads((ROOT / "results" / "bench_r13" / "results.json").read_text(encoding="utf-8"))["summary"]
    total = _pair(an["a3_minus_a2"])
    out: list[tuple[str, str]] = []
    for doc in ("docs/RESULTS_2026-10-09_R13_pilot_ES.md", "docs/RESULTS_2026-10-09_R13_pilot_EN.md"):
        out.append((doc, total))
        for g in ("gemma2:2b", "qwen2.5:3b", "llama3.2:3b"):
            out.append((doc, _pair(an["a3_minus_a2_by_digester"][g])))
            out.append((doc, f"{r13['a3_by_digester'][g]:.3f}"))
        for t in ("simple", "cross", "updated", "contradiction"):
            out.append((doc, _pair(an["a3_minus_a2_by_type"][t], plus=False)))
        for t in ("deleted", "unanswerable"):
            out.append((doc, _pair(an["a3_minus_a2_by_type"][t], plus=True)))
        out.append((doc, _pair(an["n1_a3_minus_a2_without_stale"])))
        out.append((doc, _pair(an["a3_minus_a0_answerable"], plus=True)))
        out.append((doc, _pair(an["a2_minus_a0_answerable"], plus=True)))
        for g, v in an["a4_minus_a3_diagonal"].items():
            out.append((doc, _s(v)))
        for k, v in an["gold_in_context_answerable"].items():
            if k != "n_questions":
                out.append((doc, f"{100 * v:.1f} %"))
        out.append((doc, f"{r13['mean_by_arm']['A3']:.3f}"))
        out.append((doc, f"{r13['mean_by_arm']['A4']:.3f}"))
    out += _r13_confirm()
    f1 = an["f1a_n1"]
    f1s = f"+{f1['all']['mean']:.3f} [{f1['all']['ci95'][0]:.3f}, {f1['all']['ci95'][1]:.3f}]"
    swip = "swips/SWIP-XXXX-local-cognitive-extension.md"
    out.append((swip, f"+{f1['all']['mean']:.3f} by question, 95 % CI [{f1['all']['ci95'][0]:.3f}, {f1['all']['ci95'][1]:.3f}]"))
    out.append((swip, f"+{f1['without_stale']['mean']:.3f} [{f1['without_stale']['ci95'][0]:.3f}, {f1['without_stale']['ci95'][1]:.3f}]"))
    ctotal = _confirm_total()
    for doc in ("README.md", "docs/STATUS.md", "publication/SWIP_ISSUE_Swarmbly-AI.md", swip,
                "docs/WHITEPAPER_LCE_v0.2_ES.md", "docs/WHITEPAPER_LCE_v0.2_EN.md"):
        if ctotal:
            out.append((doc, ctotal))
    out += [("README.md", f1s), ("docs/WHITEPAPER_LCE_v0.2_ES.md", f1s), ("docs/WHITEPAPER_LCE_v0.2_EN.md", f1s),
            ("publication/SWIP_ISSUE_Swarmbly-AI.md",
             f"+{f1['all']['mean']:.3f} (question-clustered 95 % CI [{f1['all']['ci95'][0]:.3f}, {f1['all']['ci95'][1]:.3f}]")]
    out += _forget_aa()
    out += _r11_c2bis_hc2()
    out += _readme_figures()
    return out


def _readme_figures() -> list[tuple[str, str]]:
    """Las figuras del README (docs/figures/*.svg, texto plano) deben llevar las
    cifras vigentes; si los datos cambian, regenerarlas con
    ``python -m lce_validation.readme_figures``."""
    out: list[tuple[str, str]] = []
    an = _load("results/bench_r13_confirm/analysis.json")
    res = _load("results/bench_r13_confirm/results.json")
    f1 = _load("results/bench_hc1_scale/results.json")
    fa = _load("results/bench_forget/analysis.json")
    for theme in ("light", "dark"):
        d = f"docs/figures/{{}}_{theme}.svg"
        if f1:
            for v in f1["summary"]["by_model"].values():
                out.append((d.format("f1a_memory_gain"), _s(v["mean_gain"])))
        if an and res:
            out.append((d.format("r13_arms"), _pair(an["a3_minus_a2"])))
            for v in res["summary"]["mean_by_arm"].values():
                out.append((d.format("r13_arms"), f"{v:.3f}"))
            for v in an["a3_minus_a2_by_type"].values():
                out.append((d.format("r13_types"), f"{_s(v['mean'])} n={v['n_questions']}"))
            for k, v in an["gold_in_context_answerable"].items():
                if k != "n_questions":
                    out.append((d.format("r13_coverage"), f"{100 * v:.1f} %"))
        if fa:
            bp = fa["behaviour_prereg"]
            ff = f"{_s(bp['forget_minus_full'])} [{_s(bp['forget_minus_full_ci95'][0])}, {_s(bp['forget_minus_full_ci95'][1])}]"
            out.append((d.format("forget_abstention"), ff))
            for v in bp["abstention"].values():
                out.append((d.format("forget_abstention"), f"{v:.3f}"))
    return out


def _load(rel: str) -> dict | None:
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _confirm_total() -> str | None:
    an = _load("results/bench_r13_confirm/analysis.json")
    return _pair(an["a3_minus_a2"]) if an else None


def _r13_confirm() -> list[tuple[str, str]]:
    """Cifras de la confirmatoria de R13 en sus dos documentos."""
    an = _load("results/bench_r13_confirm/analysis.json")
    res = _load("results/bench_r13_confirm/results.json")
    if not (an and res):
        return []
    cs = res["summary"]
    out: list[tuple[str, str]] = []
    for doc in ("docs/RESULTS_2026-10-11_R13_confirm_ES.md", "docs/RESULTS_2026-10-11_R13_confirm_EN.md"):
        out.append((doc, _pair(an["a3_minus_a2"])))
        out.append((doc, f"{cs['questions']}"))
        for g in ("gemma2:2b", "qwen2.5:3b", "llama3.2:3b"):
            out.append((doc, _pair(an["a3_minus_a2_by_digester"][g])))
            out.append((doc, f"{cs['a3_by_digester'][g]:.3f}"))
        for t, d in an["a3_minus_a2_by_type"].items():
            out.append((doc, _pair(d)))
        out.append((doc, _pair(an["a3_minus_a0_answerable"])))
        out.append((doc, _pair(an["a2_minus_a0_answerable"])))
        for v in an["a4_minus_a3_diagonal"].values():
            out.append((doc, _s(v)))
        for k, v in an["gold_in_context_answerable"].items():
            if k != "n_questions":
                out.append((doc, f"{100 * v:.1f} %"))
        for v in cs["mean_by_arm"].values():
            out.append((doc, f"{v:.3f}"))
        for row in an["abstention_with_accuracy"].values():
            for v in row.values():
                out.append((doc, f"{v:.3f}"))
        h3 = an["decision_rules"]["r13_h3"]
        out.append((doc, f"{h3['spearman_anchored_vs_accuracy_own_users']:.3f}"))
        out.append((doc, f"{h3['min_anchored']}"))
    return out


def _r11_c2bis_hc2() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    r11 = _load("results/bench_r11_confirm/results.json")
    if r11:
        main = [c for c in r11["cells"] if "adapter_retr_ok" in c]
        same = sum(c["adapter"] == c["base"] for c in main)
        ok_same = sum(c["base_ok"] == c["adapter_ok"] for c in r11["cells"])
        for doc in ("docs/RESULTS_2026-10-11_R11_confirm_ES.md", "docs/RESULTS_2026-10-11_R11_confirm_EN.md"):
            out += [(doc, f"{same}"), (doc, f"{ok_same}"), (doc, f"{len(r11['trainings'])}")]
            for u in ("mara", "julian", "carmen"):
                cu = [c for c in main if c["tag"].split("__")[0] == u]
                for k in ("base_ok", "retrieval_ok"):
                    out.append((doc, f"{sum(c[k] for c in cu) / len(cu):.3f}"))
    c2 = _load("results/bench_c2bis/results.json")
    s4 = lambda x: f"{x:+.4f}".replace("-", "−")  # noqa: E731
    if c2:
        cs = c2["summary"]
        pair = f"{s4(cs['mean_reduction'])} [{s4(cs['ci95'][0])}, {s4(cs['ci95'][1])}]"
        for doc in ("docs/RESULTS_2026-10-11_C2bis_ES.md", "docs/RESULTS_2026-10-11_C2bis_EN.md",
                    "swips/SWIP-XXXX-local-cognitive-extension.md"):
            out.append((doc, pair))
    hc = _load("results/bench_hc2_closure/results.json")
    if hc:
        hs = hc["summary"]
        for doc in ("docs/RESULTS_2026-10-11_HC2_closure_ES.md", "docs/RESULTS_2026-10-11_HC2_closure_EN.md"):
            out += [(doc, s4(hs["mean_gain"])), (doc, f"{hs['frac_gain_positive']:.4f}"),
                    (doc, f"{hs['median_delta_rho_pct']:.2f} %"), (doc, f"{hs['n_tasks']}")]
    return out


def _forget_aa() -> list[tuple[str, str]]:
    fp = ROOT / "results" / "bench_forget" / "analysis.json"
    ap = ROOT / "results" / "aa_test" / "results.json"
    rp = ROOT / "results" / "bench_forget" / "results.json"
    if not (fp.exists() and ap.exists() and rp.exists()):
        return []
    fa = json.loads(fp.read_text(encoding="utf-8"))
    fs = json.loads(rp.read_text(encoding="utf-8"))["summary"]
    bp = fa["behaviour_prereg"]
    s = json.loads(ap.read_text(encoding="utf-8"))["summary"]
    s4 = lambda x: f"{x:+.4f}".replace("-", "−")  # noqa: E731
    ff = f"{_s(bp['forget_minus_full'])} [{_s(bp['forget_minus_full_ci95'][0])}, {_s(bp['forget_minus_full_ci95'][1])}]"
    fn = f"{_s(bp['forget_minus_never'])} [{_s(bp['forget_minus_never_ci95'][0])}, {_s(bp['forget_minus_never_ci95'][1])}]"
    aa4 = f"{s4(s['AA4']['mean_diff'])} [{s4(s['AA4']['ci95'][0])}, {s4(s['AA4']['ci95'][1])}]"
    aa1 = f"{100 * s['AA1']['identical_rate']:.1f} %"
    out = []
    for doc, of in (("docs/RESULTS_2026-10-10_Fforget_AA_ES.md", "de"), ("docs/RESULTS_2026-10-10_Fforget_AA_EN.md", "of")):
        out += [(doc, ff), (doc, fn), (doc, aa4), (doc, aa1),
                (doc, f"{bp['abstention']['full']:.3f}"), (doc, f"{bp['abstention']['forget']:.3f}"),
                (doc, f"{bp['abstention']['never']:.3f}"),
                (doc, f"{s['AA2']['identical']} {of} {s['AA2']['wikis']}"),
                (doc, f"{s['AA2']['mean_jaccard']:.3f}"),
                (doc, f"{fs['S4_identical_claim_sets']} {of} {fs['cells']}"),
                (doc, f"{fs['S4_mean_jaccard']:.3f}"),
                (doc, f"{100 * fs['S4_context_identical_rate']:.1f} %"),
                (doc, f"{fs['sweep_forgets']} "),
                (doc, f"{s['AA1']['n']}"), (doc, f"{100 * bp['identical_answers_forget_never']:.1f} %")]
        eq = fa.get("independent_equivalence")
        if eq:
            out.append((doc, f"{eq['forget_eq_r13']} {of} {eq['wikis']}"))
    swip = "swips/SWIP-XXXX-local-cognitive-extension.md"
    out += [(swip, ff), (swip, f"{aa1} identical"),
            (swip, f"{s['AA2']['identical']}/{s['AA2']['wikis']} wikis identical")]
    for doc in ("docs/WHITEPAPER_LCE_v0.2_ES.md", "docs/WHITEPAPER_LCE_v0.2_EN.md"):
        out.append((doc, ff))
    return out


def missing() -> list[tuple[str, str]]:
    bad = []
    for doc, needle in expected():
        path = ROOT / doc
        if not path.exists():
            bad.append((doc, "(no existe el documento)"))
            continue
        text = " ".join(path.read_text(encoding="utf-8").split())
        if needle not in text:
            bad.append((doc, needle))
    return bad


if __name__ == "__main__":
    m = missing()
    for d, n in m:
        print(f"FALTA en {d}: {n}")
    raise SystemExit(1 if m else 0)
