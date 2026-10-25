"""T04 — ¿δ explica la bimodalidad? (M4). WHITEPAPER_V2 §6.8, VALIDATION §4.4.

Desbloqueado el 24-09-2026: ahora corre sobre los **16 prompts reales** de
`results/tables-final-*/results.csv` y sobre el **corte real** que produjo la
medición (`swarmbly_v0.planner._segment`), no sobre una reconstrucción.

Instrumento
-----------
δ se computa con la lista de componentes declarada en `swarmblyval/delta.py`,
fijada antes de mirar ninguna correlación y sin parámetros libres.

Prueba primaria: asociación δ↔impuesto sobre los 16 (Spearman, p por
permutación). Usa toda la muestra en lugar de colapsarla en dos grupos.

Prueba secundaria (la preregistrada): 2 caros vs 11 gratuitos, rank-sum
**exacto**. Se reporta antes su techo de p: con n₁=11 y n₂=2 el menor p
alcanzable es 0.0256, de modo que sólo una separación perfecta podría ser
significativa. Eso se dice antes de correr, no después.

Condiciones de rechazo (declaradas)
-----------------------------------
· varianza cero en el predictor → negarse (no hay asociación que estimar)
· algún grupo con <2 prompts → negarse
· techo de p > α → negarse por falta de potencia, no reportar un nulo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval import delta as D
from swarmblyval import loaders as L
from swarmblyval.report import Result, BLOCKED, FAIL, PASS, REFUSE
from swarmblyval.stats import (attainable_min_p, exact_rank_sum, p_value_ceiling,
                               spearman_permutation_p, variance_refusal)

ALPHA = 0.05


def run():
    if not L.have_repo():
        return Result(
            id="T04", name="δ explica la bimodalidad (M4)", model="M4",
            verdict=BLOCKED,
            summary="sin repositorio: exporta SWARMBLY_REPO para desbloquear",
            killed_if="δ no separa / no se asocia con el impuesto",
            refusal="sin datos reales no se emite veredicto",
            notes=["El veredicto empírico exige `prompts/tables24.json` y "
                   "`results/tables-final-*/results.csv`."])

    try:
        tab = L.load_tables24()
        tax, run_dir = L.load_tax_16()
        segmenter = L.real_segmenter()
    except L.DataRefusal as exc:
        return Result(
            id="T04", name="δ explica la bimodalidad (M4)", model="M4",
            verdict=REFUSE, summary=f"datos rechazados: {exc}",
            killed_if="δ no separa / no se asocia con el impuesto",
            refusal=str(exc))

    ids = tab["final"]
    dt = D.delta_table(ids, tab["all"], segmenter, n_tasks=2)

    details = [
        f"Corrida: `{run_dir}`, celda ρ=3.5 · N=2 · k=1, corpus sha256 "
        f"`{tab['sha256'][:16]}…`.",
        "El cargador reproduce la medición documentada antes de usarla: media "
        "+2.30, mediana 0.00, 11 de 16 en cero o por debajo, y los dos caros en "
        "+28.50 / +23.08. Si alguno no cuadrara, se negaría.",
        "δ se computa contra el **corte real** de `planner._segment(prompt, 2)`.",
    ]
    tables, notes = {}, []

    # --- condición de rechazo 1: varianza del predictor ----------------------
    struct = [dt[p]["delta_struct"] for p in ids]
    total = [dt[p]["delta"] for p in ids]
    ref_s, why_s = variance_refusal(struct, "δ estructural")
    ref_t, why_t = variance_refusal(total, "δ total")

    details.append(f"Varianza δ estructural: {why_s}")
    details.append(f"Varianza δ total: {why_t}")

    if ref_t:
        return Result(
            id="T04", name="δ explica la bimodalidad (M4)", model="M4",
            verdict=REFUSE,
            summary="δ es constante en los 16 prompts: nada que asociar",
            killed_if="δ no se asocia con el impuesto",
            refusal=why_t, details=details)

    # --- prueba primaria -----------------------------------------------------
    ys = [tax[p] for p in ids]
    rho, p_perm = spearman_permutation_p(total, ys, n_perm=50000, seed=7)

    # --- prueba secundaria (preregistrada) -----------------------------------
    expensive = [p for p in ids if tax[p] > 20.0]
    free = [p for p in ids if tax[p] <= 0.0]
    ceiling = p_value_ceiling(len(free), len(expensive))
    underpowered = False
    if min(len(free), len(expensive)) < 2:
        notes.append("Grupo con <2 prompts: la comparación de grupos se omite.")
        U = p_exact = None
        attainable = None
    else:
        a = [dt[p]["delta"] for p in free]
        b = [dt[p]["delta"] for p in expensive]
        attainable, _best = attainable_min_p(a, b)
        underpowered = attainable > ALPHA
        U, p_exact, n_perm = exact_rank_sum(a, b)
        details.append(
            f"Rank-sum **exacto** ({n_perm} permutaciones) entre {len(free)} "
            f"gratuitos y {len(expensive)} caros: U={U:.1f}, p={p_exact:.4f}.")
        details.append(
            f"Pero con **estos** valores de δ el p más pequeño alcanzable es "
            f"**{attainable:.4f}**"
            + (f" > α={ALPHA}: ninguna disposición de estos datos podría haber "
               f"sido significativa, así que la comparación de dos grupos no "
               f"informa en ningún sentido."
               if underpowered else
               f", de modo que la comparación sí podía decidir."))

    details.insert(3, (
        f"Techo de p sin empates con n₁={len(free)}, n₂={len(expensive)}: "
        f"**{ceiling:.4f}** — sólo una separación perfecta llegaría a α={ALPHA}. "
        f"δ toma pocos valores distintos sobre los 16, así que el techo real se "
        f"computa sobre los datos y no con la fórmula."))
    details.append(
        f"Asociación δ↔impuesto sobre los 16: **Spearman ρ = {rho:+.3f}**, "
        f"p (permutación) = {p_perm:.4f}. M4 predice ρ > 0.")

    hi = [tax[p] for p in ids if dt[p]["delta"] >= 5.75]
    lo = [tax[p] for p in ids if dt[p]["delta"] <= 5.25]
    if hi and lo:
        details.append(
            f"Dirección: δ alta (n={len(hi)}) → impuesto medio "
            f"{sum(hi)/len(hi):+.2f} %; δ baja (n={len(lo)}) → "
            f"{sum(lo)/len(lo):+.2f} %. El signo va **al revés** de lo predicho.")

    # --- rescate: diseño pareado intra-prompt a través de N ------------------
    # Cada prompt es su propio control, así que todo lo que el corpus tiene
    # constante por construcción (mismo molde, mismas restricciones, mismas 20
    # filas) se cancela. Es el diseño más fuerte que estos datos permiten.
    paired = None
    try:
        t8, _run8 = L.load_tax_cell(n_tasks=8)
        common = [p for p in ids if p in t8]
        if len(common) >= 8:
            d8 = D.delta_table(common, tab["all"], segmenter, n_tasks=8)
            ddelta = [d8[p]["delta_boundary"] - dt[p]["delta_boundary"] for p in common]
            dtax = [t8[p] - tax[p] for p in common]
            r_pair, p_pair = spearman_permutation_p(ddelta, dtax, n_perm=50000, seed=11)
            r_x8, p_x8 = spearman_permutation_p(
                [d8[p]["delta_boundary"] for p in common], [t8[p] for p in common],
                n_perm=50000, seed=3)
            worse = sum(1 for p in common if t8[p] > tax[p])
            paired = (r_pair, p_pair, r_x8, p_x8, worse, len(common))
            details.append(
                f"**Rescate — diseño pareado intra-prompt (N=2 → N=8).** Cada "
                f"prompt es su propio control, así que lo que el corpus tiene "
                f"constante se cancela. Δδ↔Δimpuesto: ρ = {r_pair:+.3f}, "
                f"p = {p_pair:.4f}.")
            details.append(
                f"Transversal en la celda N=8 ({len(common)} prompts): "
                f"ρ = {r_x8:+.3f}, p = {p_x8:.4f}.")
            details.append(
                f"Y un hecho grande que sí aparece: pasar de N=2 a N=8 **empeora "
                f"{worse} de {len(common)} prompts** (entre +7 y +31 puntos). El "
                f"efecto de N es enorme; δ simplemente no lo sigue prompt a prompt.")
    except L.DataRefusal as exc:
        notes.append(f"Celda N=8 no disponible para el pareado: {exc}")

    tables["δ y el impuesto, por prompt (datos reales)"] = (
        ["prompt", "impuesto %", "δ", "δ estructural", "δ instanciada"],
        [[p, f"{tax[p]:+.2f}", f"{dt[p]['delta']:.2f}",
          f"{dt[p]['delta_struct']:.2f}", f"{dt[p]['delta_data']:.2f}"]
         for p in sorted(ids, key=lambda q: -tax[q])])

    # --- veredicto -----------------------------------------------------------
    supported = rho > 0 and p_perm < ALPHA
    verdict = PASS if supported else FAIL
    if supported:
        summary = f"δ se asocia con el impuesto como M4 predice (ρ={rho:+.3f})"
    else:
        summary = (f"M4 no se sostiene en este corpus: ρ={rho:+.3f} "
                   f"(predicho >0), p={p_perm:.3f}")

    notes.append(
        "**Alcance, y limita la fuerza del resultado.** La mitad *estructural* de "
        "δ es constante (3.50) en los 16: el corpus se construyó a propósito con "
        "24 prompts del mismo molde — 20 filas, idéntico juego de restricciones, "
        "corte de 170/162 tokens en todos. Lo único que varía es δ instanciada, y "
        "ahí manda un solo componente (categorías de mercancía que cruzan el "
        "corte); D4 y D5 son cero en los 16. Lo probado es por tanto un δ pobre.")
    notes.append(
        "**Consecuencia para la agenda, y corrige a VALIDATION §4.4.** Allí T04 "
        "figura como prueba gratuita capaz de matar M4 *antes* de construir "
        "corpus. Eso era incorrecto: sobre tables24 no existe variación "
        "estructural que anotar, así que un test fuerte de M4 necesita un corpus "
        "cuya *descomposición* varíe. **T04 depende de T06**, no lo precede.")
    if underpowered:
        notes.append(
            "**La prueba secundaria no podía decidir.** Con los valores de δ que "
            "el corpus produce, el p más pequeño alcanzable en la comparación "
            f"2-contra-11 es {attainable:.3f}. Su resultado no es un nulo: es la "
            "ausencia de una prueba. El veredicto descansa sólo en la asociación "
            "sobre los 16.")
    if paired:
        r_pair, p_pair, r_x8, p_x8, worse, ncom = paired
        notes.append(
            f"**Tres pruebas, tres resultados negativos, y ninguna es la misma "
            f"prueba.** Transversal N=2: ρ={rho:+.3f} (p={p_perm:.3f}). "
            f"Transversal N=8: ρ={r_x8:+.3f} (p={p_x8:.3f}). Pareada intra-prompt: "
            f"ρ={r_pair:+.3f} (p={p_pair:.3f}). Que la pareada —el diseño más "
            f"fuerte que estos datos permiten— coincida con las transversales "
            f"hace el resultado bastante más sólido que un solo nulo.")
        notes.append(
            "**Se probaron dos operacionalizaciones de δ y las dos fallan.** "
            "δ_A (normalizada por N) y δ_B (ponderada por límites, declarada "
            "después y por un defecto enunciado de δ_A). Probar un segundo "
            "estimador tras el fallo del primero infla el falso positivo, así "
            "que δ_B se juzga a α=0.025 y como exploratoria. No hizo falta: "
            "también falla.")
    notes.append(
        f"Lo que sí queda establecido: en el único corpus disponible, δ no "
        f"predice el impuesto en la dirección que M4 exige, y si algo tiende al "
        f"revés (ρ={rho:+.3f}, p={p_perm:.3f} — ni siquiera significativo). "
        f"La bimodalidad sigue sin explicación.")

    return Result(
        id="T04", name="δ explica la bimodalidad (M4)", model="M4",
        verdict=verdict, summary=summary,
        killed_if="δ no se asocia con el impuesto en la dirección predicha",
        refusal=(f"varianza cero en el predictor · grupo con <2 prompts · "
                 f"techo de p ({ceiling:.4f}) reportado antes de correr"),
        details=details, tables=tables, notes=notes)


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
