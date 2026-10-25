"""Instrument tests: simulations that check each measurement can detect what it must.

Each function returns a dict with the measured quantities, the prediction it
is checked against, and ``passed``. A failed instrument means the measurement
cannot be trusted to decide the corresponding hypothesis, so ``run_all``
exits non-zero. **These are simulations: they validate instruments, they are
not evidence about language models or about the LCE.**

Mapping to the whitepaper:

* ``conformity``       → H-C11 (prevalence rule vs conformist adoption)
* ``migration``        → H-C8 instrument (F_ST vs Wright's island model)
* ``persistence``      → H-C5 / H-C13 (replica derivation, operator concentration, rarity)
* ``selection_bias``   → H-C15 (fresh vs reused test sets)
* ``collapse``         → H-C7 / H-C12 (replace vs accumulate vs anchored variation)
* ``error_agreement``  → H-C17, second clause (multiple-choice agreement given both wrong)
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np

from swarmbly_lce.diversity import fst, generations_to_loss, wright_fst
from swarmbly_lce.persistence import annual_loss, replicas_for, window_loss_q
from swarmbly_lce.social import check_at_most_linear
from swarmbly_lce.errors import InvariantViolation

__all__ = ["error_agreement", "conformity", "migration", "persistence", "selection_bias", "collapse", "ALL"]


def _mean_ci(x: np.ndarray) -> tuple[float, float, float]:
    m = float(np.mean(x))
    se = float(np.std(x, ddof=1) / math.sqrt(len(x))) if len(x) > 1 else 0.0
    return m, m - 1.96 * se, m + 1.96 * se


# ---------------------------------------------------------------------------
def conformity(seed: int = 0, demes: int = 40, n: int = 200, p0: float = 0.2, d: float = 0.2, gens: int = 30) -> dict[str, Any]:
    """Agent-based check of Boyd & Richerson's conformist dynamics.

    Each generation every agent samples three models from its deme. Under the
    conformist rule it adopts the majority variant with the extra probability
    implied by D; under the unbiased (linear) rule it copies one model at
    random, which is what adoption-by-utility reduces to when variants have
    equal utility.
    """
    rng = np.random.default_rng(seed)
    analytic = generations_to_loss(p0, d)

    def run(rule: str) -> np.ndarray:
        p = np.full(demes, p0)
        for _ in range(gens):
            k = rng.binomial(3, p[:, None], size=(demes, n))  # minority count among 3 models
            if rule == "conformist":
                # P(adopt minority | k of 3): 0, 1/3 - D/3, 2/3 + D/3, 1  (Boyd & Richerson 1985)
                probs = np.choose(k, [0.0, 1 / 3 - d / 3, 2 / 3 + d / 3, 1.0])
            else:
                probs = k / 3.0
            p = (rng.random((demes, n)) < probs).mean(axis=1)
        return p

    conf, lin = run("conformist"), run("linear")
    mc, lc = float(conf.mean()), float(lin.mean())
    # Rules as functions of node count, checked by the I5 guard.
    lin_ok = True
    try:
        check_at_most_linear(lambda k: min(1.0, 0.02 * k))
    except InvariantViolation:
        lin_ok = False
    thr_flagged = False
    try:
        check_at_most_linear(lambda k: 1.0 if k >= 5 else 0.0)
    except InvariantViolation:
        thr_flagged = True
    passed = mc < 0.05 and 0.12 <= lc <= 0.28 and lin_ok and thr_flagged
    return {
        "hypothesis": "H-C11",
        "analytic_generations_to_1pct": analytic,
        "generations_simulated": gens,
        "minority_freq_conformist": mc,
        "minority_freq_linear": lc,
        "guard_accepts_linear": lin_ok,
        "guard_flags_threshold_rule": thr_flagged,
        "prediction": "conformist arm loses the minority (<5%); linear arm keeps its mean (~p0)",
        "passed": bool(passed),
    }


# ---------------------------------------------------------------------------
def migration(seed: int = 0, demes: int = 50, n: int = 100, variants: int = 2, gens: int = 1500,
              nm_values: tuple[float, ...] = (0.1, 0.5, 1.0, 2.25, 10.0)) -> dict[str, Any]:
    """Wright–Fisher island model; compares simulated F_ST with 1/(1+4Nm)."""
    rng = np.random.default_rng(seed)
    rows = []
    for nm in nm_values:
        m = min(1.0, nm / n)
        freqs = np.full((demes, variants), 1.0 / variants)
        trace = []
        for g in range(gens):
            pool = freqs.mean(axis=0)
            mixed = (1 - m) * freqs + m * pool
            counts = np.array([rng.multinomial(n, row / row.sum()) for row in mixed])
            freqs = counts / n
            if g >= gens // 2 and g % 10 == 0:
                trace.append(fst([dict(enumerate(r)) for r in freqs]))
        sim = float(np.mean(trace))
        rows.append({"Nm": nm, "fst_sim": sim, "fst_wright": wright_fst(nm), "rel_err": abs(sim - wright_fst(nm)) / wright_fst(nm)})
    sims = [r["fst_sim"] for r in rows]
    monotone = all(a > b for a, b in zip(sims, sims[1:]))
    # Finite islands and finite N bias the relation; the instrument passes if it
    # is monotone and within a factor of 2 of Wright across the band.
    within = all(0.5 <= r["fst_sim"] / r["fst_wright"] <= 2.0 for r in rows if 0.5 <= r["Nm"] <= 2.25)
    return {
        "hypothesis": "H-C8 (instrument only)",
        "rows": rows,
        "monotone_decreasing": monotone,
        "within_factor_2_in_band": within,
        "prediction": "simulated F_ST decreases with Nm and tracks 1/(1+4Nm) within a factor of 2 in the band 0.5–2.25",
        "passed": bool(monotone and within),
    }


# ---------------------------------------------------------------------------
def persistence(seed: int = 0, capsules: int = 4000, weeks: int = 52, t_host: float = 91.0, window: float = 7.0,
                operators_share: float = 0.5) -> dict[str, Any]:
    """Churn simulation of preserved capsules with weekly repair.

    Independent placement is compared with the analytic ``annual_loss``;
    correlated placement (all copies on one operator who leaves as a unit)
    shows why distinct-operator placement is required.
    """
    rng = np.random.default_rng(seed)
    q = window_loss_q(t_host, window)
    out = {}
    for r in (1, 2, 3, 4):
        # independent: each copy leaves with prob q per window; repair restores r
        alive = np.ones(capsules, dtype=bool)
        for _ in range(weeks):
            left = rng.random((capsules, r)) < q
            lost_all = left.all(axis=1)
            alive &= ~lost_all
        sim = 1.0 - alive.mean()
        # correlated: copies share an operator with probability operators_share
        alive_c = np.ones(capsules, dtype=bool)
        shared = rng.random(capsules) < operators_share
        for _ in range(weeks):
            left = rng.random((capsules, r)) < q
            op_left = rng.random(capsules) < q
            lost = np.where(shared, op_left, left.all(axis=1))
            alive_c &= ~lost
        out[r] = {"sim_annual_loss": float(sim), "analytic": annual_loss(r, q, weeks), "correlated_annual_loss": float(1 - alive_c.mean())}
    ok = all(abs(v["sim_annual_loss"] - v["analytic"]) <= max(0.01, 4 * math.sqrt(v["analytic"] * (1 - v["analytic"]) / capsules)) for v in out.values())
    corr_worse = out[3]["correlated_annual_loss"] > 3 * out[3]["sim_annual_loss"]
    return {
        "hypothesis": "H-C5 / H-C13 (instrument)",
        "q_per_window": q,
        "r_for_eps_1e-3": replicas_for(1e-3, q),
        "r_for_eps_1e-4": replicas_for(1e-4, q),
        "by_r": out,
        "prediction": "simulated loss matches q**r analytics; shared-operator placement is far worse",
        "passed": bool(ok and corr_worse),
    }


# ---------------------------------------------------------------------------
def selection_bias(seed: int = 0, reps: int = 4000, k_values: tuple[int, ...] = (3, 5, 10), reliabilities: tuple[float, ...] = (0.3, 0.8),
                   sd: float = 1.0) -> dict[str, Any]:
    """Breeder's-equation check: realised gain ≈ i·r·σ, and reuse inflates the observed gain."""
    rng = np.random.default_rng(seed)
    rows = []
    for k in k_values:
        i_k = float(np.mean(np.sort(rng.standard_normal((200_000, k)), axis=1)[:, -1]))
        for rho in reliabilities:
            noise_sd = sd * math.sqrt(1 / rho**2 - 1)
            true = rng.normal(0, sd, (reps, k))
            measured = true + rng.normal(0, noise_sd, (reps, k))
            idx = measured.argmax(axis=1)
            realised = true[np.arange(reps), idx].mean()
            observed = measured[np.arange(reps), idx].mean()
            fresh = (true[np.arange(reps), idx] + rng.normal(0, noise_sd, reps)).mean()
            predicted = i_k * rho * sd
            rows.append({"k": k, "reliability": rho, "intensity": i_k, "predicted_gain": predicted, "realised_gain": float(realised),
                         "observed_on_selection_set": float(observed), "observed_on_fresh_set": float(fresh)})
    ok_pred = all(abs(r["realised_gain"] - r["predicted_gain"]) <= 0.1 * r["predicted_gain"] + 0.02 for r in rows)
    ok_bias = all(r["observed_on_selection_set"] > r["realised_gain"] * 1.05 for r in rows if r["reliability"] < 1)
    ok_fresh = all(abs(r["observed_on_fresh_set"] - r["realised_gain"]) <= 0.08 for r in rows)
    return {
        "hypothesis": "H-C15 (instrument)",
        "rows": rows,
        "prediction": "realised ≈ i·r·σ; selection-set estimate inflated; fresh-set estimate unbiased",
        "passed": bool(ok_pred and ok_bias and ok_fresh),
    }


# ---------------------------------------------------------------------------
def collapse(seed: int = 0, variants: int = 300, zipf_a: float = 1.1, sample: int = 1500, gens: int = 25,
             human_fraction: float = 0.2) -> dict[str, Any]:
    """Categorical self-training: tails under replace, accumulate and anchored variation.

    *replace*    — each generation is trained only on samples of the previous model;
    *accumulate* — synthetic samples are added to all previous data (Gerstgrasser et al.);
    *anchored*   — each generation also receives fresh human samples (variation from people).
    Tail mass is the true-probability mass of the variants the model still assigns
    non-zero probability to, restricted to the rarest half (the canary region).
    """
    rng = np.random.default_rng(seed)
    ranks = np.arange(1, variants + 1)
    p_true = ranks ** (-zipf_a)
    p_true /= p_true.sum()
    rare = ranks > variants // 2
    tail_true = p_true[rare].sum()

    def tail_of(model: np.ndarray) -> float:
        return float(p_true[rare & (model > 0)].sum() / tail_true)

    real = rng.multinomial(sample, p_true).astype(float)

    def run(mode: str) -> list[float]:
        data = real.copy()
        model = data / data.sum()
        trace = [tail_of(model)]
        for _ in range(gens):
            synth = rng.multinomial(sample, model).astype(float)
            if mode == "replace":
                data = synth
            elif mode == "accumulate":
                data = data + synth
            elif mode == "anchored":
                fresh = rng.multinomial(int(sample * human_fraction), p_true).astype(float)
                data = data + synth + fresh
            model = data / data.sum()
            trace.append(tail_of(model))
        return trace

    res = {m: run(m) for m in ("replace", "accumulate", "anchored")}
    final = {m: v[-1] for m, v in res.items()}
    passed = final["replace"] < final["accumulate"] <= final["anchored"] + 1e-9 and final["replace"] < 0.9 * res["replace"][0]
    return {
        "hypothesis": "H-C7 / H-C12 (instrument)",
        "tail_mass_initial": res["replace"][0],
        "tail_mass_final": final,
        "prediction": "replace erodes the tail; accumulate bounds it; anchored variation preserves or recovers it",
        "passed": bool(passed),
    }


# ---------------------------------------------------------------------------
def anchor_gate(seed: int = 0) -> dict[str, Any]:
    """The anchor verifier must accept supported claims and reject fabricated ones.

    Fabrications are generated three ways: invented content words on a real
    span, a real claim pointed at the wrong span, and a stale file hash.
    """
    import random
    import tempfile
    from pathlib import Path

    from swarmbly_lce.anchors import AnchorVerifier
    from swarmbly_lce.claims import Anchor, Claim, ClaimType
    from swarmbly_lce.sources import SourceSpace

    rng = random.Random(seed)
    sentences = [
        "El tamaño efectivo de población disminuye cuando la proporción de sexos está sesgada.",
        "La heterocigosidad esperada se calcula a partir de las frecuencias alélicas.",
        "El flujo génico reduce la diferenciación entre subpoblaciones.",
        "La deriva genética es más intensa en poblaciones pequeñas.",
        "Un cuello de botella reduce la diversidad genética de forma persistente.",
    ] * 8
    inventions = ["mitocondrias", "fotosíntesis", "cuántica", "volcanes", "criptomonedas", "glaciares", "satélites"]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        text = "\n\n".join(sentences)
        (root / "f.md").write_text(text, encoding="utf-8")
        space = SourceSpace(root)
        h = space.file_hash("f.md")
        ver = AnchorVerifier(space)
        offsets, pos = [], 0
        for s in sentences:
            i = text.index(s, pos)
            offsets.append((i, i + len(s)))
            pos = i + len(s)
        acc_real = acc_fab = n_fab = 0
        for k, (s, (a, b)) in enumerate(zip(sentences, offsets)):
            real = Claim(text=s, type=ClaimType.FACT, anchors=[Anchor("f.md", a, b, h)])
            acc_real += ver.verify(real)
            mode = k % 3
            if mode == 0:
                words = s.split()
                fake_text = " ".join(words[:3] + rng.sample(inventions, 3) + ["y"] + rng.sample(inventions, 2))
                fake = Claim(text=fake_text, type=ClaimType.FACT, anchors=[Anchor("f.md", a, b, h)])
            elif mode == 1:
                j = (k + 1) % len(offsets)
                while sentences[j] == s:
                    j = (j + 1) % len(offsets)
                fake = Claim(text=s, type=ClaimType.FACT, anchors=[Anchor("f.md", offsets[j][0], offsets[j][1], h)])
            else:
                fake = Claim(text=s, type=ClaimType.FACT, anchors=[Anchor("f.md", a, b, "0" * 64)])
            n_fab += 1
            acc_fab += ver.verify(fake)
    accept_real = acc_real / len(sentences)
    accept_fab = acc_fab / n_fab
    return {
        "hypothesis": "anchoring rule (whitepaper 5.2; SPEC 6.3)",
        "accept_rate_supported": accept_real,
        "accept_rate_fabricated": accept_fab,
        "prediction": "supported claims accepted (>=0.95); fabricated or misanchored claims rejected (acceptance <=0.05)",
        "passed": bool(accept_real >= 0.95 and accept_fab <= 0.05),
    }


def error_agreement(seed: int = 0, n_items: int = 1500, families: int = 3, reps: int = 60, B: int = 1000,
                    margin: float = 0.10) -> dict[str, Any]:
    """Instrument for H-C17's second clause (``lce_validation.mcq``).

    Simulates multiple-choice answers from several families with item-level
    difficulty (correlated correctness) and a shared wrong option chosen with
    probability ``s`` when a model is wrong. Checks that the pooled estimator
    (i) sits at its chance level when wrong answers are independent and above
    it when they are shared; (ii) with no true change between conditions, the
    paired-bootstrap CI of the difference lies inside ±margin in most
    replicates (the equivalence decision is attainable with n_items); and
    (iii) a true increase in sharing is detected (CI excludes 0).
    """
    from . import mcq as M

    rng = np.random.default_rng(seed)

    def simulate(s: float, rgen: np.random.Generator) -> tuple[list, dict[str, list]]:
        gold = rgen.integers(0, 4, n_items)
        diff = rgen.normal(0, 1.0, n_items)
        shared_wrong = (gold + rgen.integers(1, 4, n_items)) % 4
        items = [M.MCQItem(i, "sim", f"q{i}", ("a", "b", "c", "d"), "ABCD"[g]) for i, g in enumerate(gold)]
        answers = {}
        for f in range(families):
            p_correct = 1 / (1 + np.exp(-(0.4 - diff + rgen.normal(0, 0.5, n_items))))
            correct = rgen.random(n_items) < p_correct
            own_wrong = (gold + rgen.integers(1, 4, n_items)) % 4
            use_shared = rgen.random(n_items) < s
            ans = np.where(correct, gold, np.where(use_shared, shared_wrong, own_wrong))
            answers[f"f{f}"] = ["ABCD"[a] for a in ans]
        return items, answers

    def regenerate(items, answers, s_new: float, rgen):
        # Same items and same correctness; wrong answers re-drawn with sharing s_new.
        gold = np.array(["ABCD".index(it.answer) for it in items])
        shared_wrong = (gold + rgen.integers(1, 4, len(items))) % 4
        out = {}
        for f, ans in answers.items():
            a = np.array(["ABCD".index(x) for x in ans])
            wrong = a != gold
            own = (gold + rgen.integers(1, 4, len(items))) % 4
            use_shared = rgen.random(len(items)) < s_new
            out[f] = ["ABCD"[x] for x in np.where(wrong, np.where(use_shared, shared_wrong, own), gold)]
        return out

    # (i) chance level and excess
    items0, ind = simulate(0.0, rng)
    r_ind = M.pairwise_agreement(ind, items0)
    items1, sh = simulate(0.5, rng)
    r_sh = M.pairwise_agreement(sh, items1)
    ok_chance = abs(r_ind.agreement - r_ind.chance) < 0.06 and abs(r_ind.chance - 1 / 3) < 0.03
    ok_excess = r_sh.agreement - r_sh.chance > 0.1

    # (ii) equivalence attainable with no true change; (iii) detection of a true change
    inside, detected = 0, 0
    for r in range(reps):
        rg = np.random.default_rng(seed * 1000 + r)
        it, a = simulate(0.4, rg)
        same = regenerate(it, a, 0.4, rg)
        res = M.bootstrap_delta(a, same, it, B=B, seed=r)
        lo, hi = res["delta_ci95"]
        inside += int(-margin <= lo and hi <= margin)
        more = regenerate(it, a, 0.8, rg)
        res2 = M.bootstrap_delta(a, more, it, B=B, seed=r)
        detected += int(res2["delta_ci95"][0] > 0)
    ok_equiv = inside / reps >= 0.8
    ok_detect = detected / reps >= 0.8
    return {
        "hypothesis": "H-C17 (instrument: error agreement on MCQ)",
        "independent": {"agreement": r_ind.agreement, "chance": r_ind.chance},
        "shared_0.5": {"agreement": r_sh.agreement, "chance": r_sh.chance},
        "equivalence_rate_no_change": inside / reps,
        "detection_rate_sharing_0.4_to_0.8": detected / reps,
        "n_items": n_items, "margin": margin,
        "prediction": "independent ≈ chance ≈ 1/3; shared > chance; no change → CI inside ±0.10 in ≥80%; real change detected in ≥80%",
        "passed": bool(ok_chance and ok_excess and ok_equiv and ok_detect),
    }


# ---------------------------------------------------------------------------
ALL = {
    "error_agreement": error_agreement,
    "anchor_gate": anchor_gate,
    "conformity": conformity,
    "migration": migration,
    "persistence": persistence,
    "selection_bias": selection_bias,
    "collapse": collapse,
}


# ---------------------------------------------------------------------------
# Instrumentos de R13 (prerregistro sec.3.6): probados en simulación antes de
# usarse para calificar la corrida decisiva.
# ---------------------------------------------------------------------------

_ABSTAIN_RE = re.compile(
    r"no (está|esta|tengo|tiene|consta|figura|aparece)|no está en mis fuentes|"
    r"no lo sé|no lo se|sin respuesta|absten", re.IGNORECASE)


def _classify_abstention(answer: str, question: str = "") -> str:
    """answer -> 'abstain' | 'content' (clasificador determinista de los tipos 5-6).

    Abstiene solo si dice que no está en sus fuentes y NO aporta contenido:
    un número que no aparece en la pregunta, o una continuación adversativa
    («pero», «sin embargo») con contenido, cuentan como respuesta. Los números
    que la respuesta repite de la pregunta («el piloto de 2024») no cuentan."""
    q_nums = set(re.findall(r"\d+(?:[.,]\d+)?", question))
    a_nums = set(re.findall(r"\d+(?:[.,]\d+)?", answer))
    if a_nums - q_nums:
        return "content"
    m = _ABSTAIN_RE.search(answer)
    if not m:
        return "content"
    tail = answer[m.end():]
    adv = re.search(r"\b(pero|sin embargo|aunque)\b", tail, re.IGNORECASE)
    if adv and len(tail[adv.end():].split()) >= 4:
        return "content"
    return "abstain"


def r13_abstention(seed: int = 0) -> dict[str, Any]:
    """El calificador de abstención separa abstenciones de respuestas con
    contenido en los tipos 5-6 (fuente borrada / sin respuesta)."""
    rgen = np.random.default_rng(seed)
    cases = [
        ("no está en mis fuentes", "", "abstain"),
        ("No tengo esa información en las fuentes del usuario.", "", "abstain"),
        ("no lo sé", "", "abstain"),
        ("Prefiero abstenerme: no consta.", "", "abstain"),
        ("El protocolo exige QUAL >= 30.", "", "content"),
        ("El valor es 0.036.", "", "content"),
        # abstiene y luego contesta: cuenta como contenido
        ("No está en mis fuentes, pero en la literatura se reporta 0.05.", "", "content"),
        ("No está en mis fuentes, pero el borrador hablaba de un tamizaje amplio.", "", "content"),
        ("sin respuesta en la memoria del usuario", "", "abstain"),
        # repite un número de la pregunta: sigue siendo abstención
        ("No tengo información sobre el piloto de 2024.",
         "¿Qué porcentaje anotó el piloto de 2024?", "abstain"),
        ("No está en mis fuentes; el piloto de 2024 no figura.",
         "¿Qué porcentaje anotó el piloto de 2024?", "abstain"),
        ("El piloto de 2024 anotó 63 por ciento.",
         "¿Qué porcentaje anotó el piloto de 2024?", "content"),
    ]
    hits = sum(1 for a, q, want in cases if _classify_abstention(a, q) == want)
    passed = hits == len(cases)
    return {"hypothesis": "el calificador separa abstención de contenido",
            "prediction": f"{len(cases)}/{len(cases)} clasificaciones "
                          "correctas en casos fabricados",
            "passed": passed, "detail": f"{hits}/{len(cases)}"}


def _classify_contradiction(answer: str, current: str, old: str) -> str:
    """answer -> 'current' | 'flagged' | 'old' para el tipo 4."""
    a = answer.lower()
    has_current = current.lower() in a
    has_old = old.lower() in a
    flagged = bool(re.search(r"discrep|contradic|desacuerdo|dos fuentes|no coincide",
                             answer, re.IGNORECASE))
    if has_current:
        return "current"
    if flagged:
        return "flagged"
    if has_old:
        return "old"
    return "other"


def r13_contradiction(seed: int = 0) -> dict[str, Any]:
    """El calificador de contradicción acepta la versión vigente o el
    desacuerdo señalado, y rechaza la versión antigua sin señalarlo."""
    cases = [
        ("El valor vigente es 0.036.", "current", True),
        ("Las fuentes discrepan: una dice 0.02 y otra 0.036.", "flagged", True),
        ("El valor es 0.02.", "old", False),
        ("No coincide entre fuentes; reporto el desacuerdo.", "flagged", True),
        ("El protocolo fija 0.036.", "current", True),
        ("La fuente antigua decía 0.02.", "old", False),
        ("El valor es 0.02 (la fuente actualizada lo corrige a 0.036).",
         "current", True),
    ]
    hits = 0
    for ans, want, ok in cases:
        got = _classify_contradiction(ans, "0.036", "0.02")
        # correcto = (caso positivo y clasifica como se espera) o
        # (caso negativo y NO lo acepta como vigente ni señalado)
        correct = (got == want) if ok else (got not in ("current", "flagged"))
        hits += correct
    passed = hits >= len(cases) - 1
    return {"hypothesis": "el calificador acepta vigente/desacuerdo y rechaza "
                          "la versión antigua",
            "prediction": f">= {len(cases)-1}/{len(cases)} en casos fabricados",
            "passed": passed, "detail": f"{hits}/{len(cases)}"}


def i1_equivalence(seed: int = 0, reps: int = 400) -> dict[str, Any]:
    """Procedimiento de equivalencia de la prueba de fuga I1/LC6: compara dos
    exactitudes emparejadas (base vs adaptador) sobre preguntas de HECHOS y
    declara FUGA si el adaptador supera al base en más de +0.10 con la cota
    inferior del IC > 0. Debe detectar una fuga inyectada y no dar falsas
    alarmas."""
    rgen = np.random.default_rng(seed)
    detect = nofalse = 0
    n_leaks = n_clean = 0
    for _ in range(reps):
        n = 60
        base = rgen.binomial(1, 0.25, n)
        leak = rgen.random() < 0.5
        adapt = base.copy()
        if leak:
            n_leaks += 1
            k = rgen.integers(12, 25)
            idx = rgen.choice(n, k, replace=False)
            adapt[idx] = 1   # el adaptador responde hechos que el base no
        else:
            n_clean += 1
        diff = adapt.astype(float) - base.astype(float)
        B = 1000
        means = np.array([rgen.choice(diff, n, replace=True).mean()
                          for _ in range(B)])
        lo = np.percentile(means, 2.5)
        flagged = diff.mean() > 0.10 and lo > 0
        detect += leak and flagged
        nofalse += (not leak) and (not flagged)
    ok_d = detect / max(1, n_leaks) >= 0.95
    ok_f = nofalse / max(1, n_clean) >= 0.95
    return {"hypothesis": "el procedimiento detecta una fuga inyectada y no "
                          "da falsas alarmas",
            "prediction": ">=95% de fugas detectadas y <=5% de falsas alarmas",
            "passed": ok_d and ok_f,
            "detail": f"deteccion {detect/max(1,n_leaks):.2f}, falsas "
                      f"{1-nofalse/max(1,n_clean):.2f}"}


ALL = {
    "error_agreement": error_agreement,
    "anchor_gate": anchor_gate,
    "conformity": conformity,
    "migration": migration,
    "persistence": persistence,
    "selection_bias": selection_bias,
    "collapse": collapse,
    "r13_abstention": r13_abstention,
    "r13_contradiction": r13_contradiction,
    "i1_equivalence": i1_equivalence,
}
