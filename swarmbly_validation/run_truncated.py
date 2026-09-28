"""T13 — Grader normalizado por longitud (truncado a T fijo). OFFLINE.

El confundido de T09R es estructural: los componentes del grader suben con la
longitud de salida (T11). Este análisis elimina el acoplamiento POR
CONSTRUCCIÓN: califica sólo los primeros ``T`` tokens (palabras) de CADA brazo,
con el mismo T para monolítico y fragmentado. Lo que queda es la densidad de
información al frente del texto, no cuánto se escribió.

Cero corridas nuevas: los textos ya están en benchmark.jsonl (473 registros).
Si el impuesto es estable a través de T y el confundido desaparece, el criterio
se vuelve juzgable con este instrumento y se reporta su veredicto.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from swarmblyval import report
from swarmblyval.report import Result, PASS, FAIL, REFUSE
from swarmblyval.stats import clustered_bootstrap, spearman
from swarmbly_ref import grader as gr
from swarmbly_ref.benchmarks import corpus as ref_corpus

import run_real as rr

T_SWEEP = (40, 60, 80, 120)
NEGLIGIBLE = 0.20   # mismo umbral que T11: |rho| por debajo = confundido resuelto


def _words(text):
    return len(str(text or "").split())


def _truncate(text, T):
    return " ".join(str(text or "").split()[:T])


def cells_operative(recs):
    """Celdas operativas con preferencia |matched, como T09R."""
    best = {}
    for r in recs:
        if r.get("arm") != "frag":
            continue
        base = r.get("key", "").replace("|matched", "")
        cur = best.get(base)
        if cur is None or r.get("key", "").endswith("|matched"):
            best[base] = r
    keep = {id(r) for r in best.values()}
    keep |= {id(r) for r in recs if r.get("arm") != "frag"}
    recs = [r for r in recs if id(r) in keep]
    mono = {(r["task"], r["model"]): r for r in recs if r.get("arm") == "mono"}
    out = []
    for r in recs:
        if r.get("arm") != "frag" or "|strong" in r.get("key", ""):
            continue
        task = ref_corpus.ALL_TASKS.get(r.get("task"))
        if task is not None and r.get("L") != task.get("L_target", 10):
            continue
        m = mono.get((r["task"], r["model"]))
        if m is None:
            continue
        out.append((r, m))
    return out


def sweep(recs):
    rows = []
    pairs = cells_operative(recs)
    for T in T_SWEEP:
        taxes, ratios, diffs, clusters = [], [], [], []
        for r, m in pairs:
            task = ref_corpus.ALL_TASKS.get(r["task"])
            if task is None:
                continue
            mt = _truncate(m.get("text"), T)
            ft = _truncate(r.get("assembled_text"), T)
            ms = gr.grade(task, mt)["score"]
            fs = gr.grade(task, ft)["score"]
            if ms < 0.20:
                continue   # piso baseline: nada que comparar
            taxes.append((ms - fs) / ms * 100.0)
            wm, wf = _words(mt), _words(ft)
            ratios.append(wf / max(1, wm))
            diffs.append(fs - ms)
            clusters.append(r["task"])
        mean, lo, hi, _se = clustered_bootstrap(taxes, clusters)
        rho = spearman(ratios, diffs) if len(ratios) >= 8 else None
        met = hi < 5.0
        rows.append({
            "T": T, "n": len(taxes), "mean": round(mean, 2),
            "lo": round(lo, 2), "hi": round(hi, 2),
            "rho_confound": round(rho, 3) if rho is not None else None,
            "met": met,
        })
    return rows, pairs


def run(data=None, recs=None, quiet=False):
    if recs is None:
        data = data or rr.ap_default_data()
        recs = rr.prefer_matched(rr.load(data))
    rows, pairs = sweep(recs)
    if not rows:
        return Result(id="T13", name="Grader truncado (normalizado por longitud)",
                      model="—", verdict=REFUSE,
                      summary="sin celdas operativas: negarse",
                      killed_if="—", refusal="sin datos", details=[])

    # confundido resuelto si |rho| < 0.20 en TODOS los T
    rhos = [r["rho_confound"] for r in rows if r["rho_confound"] is not None]
    confound_gone = all(abs(x) < NEGLIGIBLE for x in rhos) if rhos else False
    # estabilidad del impuesto entre T
    means = [r["mean"] for r in rows]
    spread = max(means) - min(means)
    stable = spread <= 8.0
    # veredicto del criterio: mismo signo en todos los T
    met_any = any(r["met"] for r in rows)
    met_all = all(r["met"] for r in rows)

    details = [
        f"{len(pairs)} celdas operativas (presupuesto igualado); calificación "
        f"sobre los primeros T tokens de cada brazo.",
        f"Confundido tras truncar: ρ ∈ "
        f"[{min(rhos):+.3f}, {max(rhos):+.3f}] por T — "
        f"{'RESUELTO por construcción' if confound_gone else 'PERSISTE'} "
        f"(umbral {NEGLIGIBLE}).",
        f"Impuesto agregado entre T={T_SWEEP[0]} y T={T_SWEEP[-1]}: "
        f"{min(means):+.2f}% a {max(means):+.2f}% — "
        f"{'estable' if stable else 'INESTABLE'} (amplitud {spread:.1f} pts).",
        f"Criterio (límite superior < 5%): "
        f"{'CUMPLIDO en todos los T' if met_all else ('CUMPLIDO en algún T' if met_any else 'NO cumplido en ningún T')}.",
    ]
    verdict = PASS if (confound_gone and stable and met_all) else \
        (FAIL if (confound_gone and stable and not met_any) else REFUSE)
    return Result(
        id="T13", name="Grader truncado (normalizado por longitud)", model="—",
        verdict=verdict,
        summary=f"impuesto truncado {min(means):+.2f}% a {max(means):+.2f}%; "
                f"confundido {'resuelto' if confound_gone else 'persistente'}; "
                f"criterio {'CUMPLIDO' if met_all else ('no cumplido' if not met_any else 'depende de T')}",
        killed_if="el impuesto cambia de signo según T (el instrumento no decide)",
        refusal="confundido persistente o impuesto inestable entre T",
        details=details,
        tables={"Impuesto por T (grader truncado)": (
            ["T (tokens)", "n", "tax medio %", "IC95 bajo", "IC95 alto",
             "ρ confundido", "criterio"],
            [[r["T"], r["n"], f"{r['mean']:+.2f}", f"{r['lo']:+.2f}",
              f"{r['hi']:+.2f}",
              f"{r['rho_confound']:+.3f}" if r["rho_confound"] is not None else "—",
              "CUMPLIDO" if r["met"] else "no"] for r in rows])},
        notes=[
            "El truncado elimina la ventaja de longitud POR CONSTRUCCIÓN: ambos "
            "brazos se califican sobre el mismo número de tokens. Lo que queda "
            "es la densidad de información al frente del texto.",
            "Si el impuesto es estable entre T y el confundido desaparece, éste "
            "es el instrumento para la re-prueba formal del criterio: una "
            "campaña con max_out=T fijo para ambos brazos.",
            "Análisis offline sobre los textos guardados: 0 corridas nuevas."])


if __name__ == "__main__":
    print(report.render_console([run()]))


# --- T13b: impuesto por POSICIÓN de primera mención (invariante a longitud) --

def _first_mention_frac(text, item):
    """Posición (fracción de palabras) de la primera mención de `item`, o None."""
    import re as _re
    words = str(text or "").split()
    if not words:
        return None
    joined = " ".join(words)
    m = _re.search(_re.escape(item), joined, _re.IGNORECASE)
    if m is None:
        return None
    before = len(joined[:m.start()].split())
    return before / len(words)


def run_position(data=None, recs=None, quiet=False):
    """Impuesto por posición: ¿el fragmentado menciona las claves ANTES o
    DESPUÉS que el monolítico, en fracción de su propia longitud?

    Invariante a la longitud POR CONSTRUCCIÓN: la posición se normaliza por el
    largo de cada brazo. Sin parámetro libre T."""
    if recs is None:
        data = data or rr.ap_default_data()
        recs = rr.prefer_matched(rr.load(data))
    pairs = cells_operative(recs)
    deltas, ratios, clusters = [], [], []
    n_items = 0
    for r, m in pairs:
        task = ref_corpus.ALL_TASKS.get(r["task"])
        if task is None:
            continue
        items = list(task.get("required_items", [])) + [
            k[0] for k in task.get("answer_keys", []) if k]
        if not items:
            continue
        mt, ft = m.get("text"), r.get("assembled_text")
        d = []
        for it in items:
            pm = _first_mention_frac(mt, it)
            pf = _first_mention_frac(ft, it)
            if pm is None or pf is None:
                continue
            d.append(pf - pm)   # positivo = fragmentado lo menciona más tarde
        if not d:
            continue
        deltas.append(sum(d) / len(d))
        n_items += len(d)
        ratios.append(_words(ft) / max(1, _words(mt)))
        clusters.append(r["task"])
    if len(deltas) < 20:
        return Result(id="T13b", name="Impuesto por posición de primera mención",
                      model="—", verdict=REFUSE,
                      summary=f"{len(deltas)} celdas < 20: negarse",
                      killed_if="—", refusal=f"{len(deltas)} celdas < 20",
                      details=[])
    mean, lo, hi, _se = clustered_bootstrap(deltas, clusters)
    rho = spearman(ratios, deltas)
    confound_gone = abs(rho) < NEGLIGIBLE
    worse = mean > 0.02   # umbral declarado: +2% de longitud desplazada = peor
    details = [
        f"{len(deltas)} celdas, {n_items} claves con primera mención medible.",
        f"Desplazamiento medio de primera mención (fragmentado − monolítico): "
        f"**{mean:+.4f}** de la longitud, IC95 [{lo:+.4f}, {hi:+.4f}].",
        f"Confundido de longitud: ρ(posición, razón de longitud) = {rho:+.3f} "
        f"— {'resuelto por construcción' if confound_gone else 'persiste'}.",
        f"Veredicto del criterio restablecido (desplazar las claves > +2% de "
        f"longitud = fragmentar perjudica): "
        f"{'PERJUDICA' if worse else 'NO perjudica'}.",
    ]
    verdict = PASS if (confound_gone and not worse) else \
        (FAIL if (confound_gone and worse) else REFUSE)
    return Result(
        id="T13b", name="Impuesto por posición de primera mención", model="—",
        verdict=verdict,
        summary=f"desplazamiento de claves {mean:+.3f} [ {lo:+.3f}, {hi:+.3f} ]; "
                f"confundido {'resuelto' if confound_gone else 'persistente'}; "
                f"fragmentar {'PERJUDICA' if worse else 'no perjudica'}",
        killed_if="el fragmentado entierra las claves (desplazamiento > +2%)",
        refusal="confundido persistente",
        details=details,
        notes=[
            "La posición se mide en fracción de la longitud del propio brazo: "
            "escribir más no ayuda ni perjudica por construcción.",
            "Esto mide DÓNDE pone el texto las claves, no cuánto escribió — el "
            "reemplazo natural del impuesto agregado para el criterio."])


if __name__ == "__main__":
    print(report.render_console([run(), run_position()]))
