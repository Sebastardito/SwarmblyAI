"""T09 — Re-prueba del criterio de abandono. WHITEPAPER_V2 §15.2, §15.5.

El criterio: debe existir un ρ con degradación < 5% vs generación monolítica, en
≥1 categoría, juzgado contra el límite SUPERIOR del IC 95% agrupado por prompt.
Resultado documentado: +2.30%, IC [−2.05, +7.49%] → NO cumplido por 2.49 puntos.

La aritmética de muestra ya fue verificada por el propio proyecto: con SD
between-prompt 20.36 y SE medido 4.16 (n≈24), para que el límite superior quede
bajo 5% se necesitan 60 prompts mínimo / 72 con margen. Esta prueba reproduce
esa aritmética y define el protocolo + rechazos. La re-prueba en sí es BLOQUEADA
(requiere corpus + 72 prompts).
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval import fixtures as F
from swarmblyval import derivation as D
from swarmblyval import stats
from swarmblyval.report import Result, BLOCKED, PASS


def run():
    c = F.COMPOSITION
    tax = F.TAX_16

    # (1) reproducir n implicito desde SE medido
    n_implied = (c["sd_between"] / c["se"]) ** 2
    # (2) tamaño de muestra requerido: rango honesto de supuestos
    z = 1.96
    n_mean_obs = (z * c["sd_between"] / (c["threshold"] - c["mean"])) ** 2
    n_mean_zero = (z * c["sd_between"] / c["threshold"]) ** 2
    n_with_margin = (z * c["sd_between"] / (c["threshold"] - c["mean"] - 0.5)) ** 2
    # (3) reproducción de la bimodalidad
    b = D.tax_distribution_stats()

    details = [
        f"n implícito en la celda declarada: ({c['sd_between']}/{c['se']})² = "
        f"{n_implied:.0f} prompts — reproduce la celda de ~24.",
        f"n para límite superior < 5%: {n_mean_obs:.0f} (media observada −0.35) a "
        f"{n_mean_zero:.0f} (media 0, conservador) → el '60 mínimo' cae en ese rango.",
        f"n con margen (½ punto bajo el umbral): {n_with_margin:.0f} → '72 con margen' "
        f"{'consistente' if abs(n_with_margin - c['sample_margin']) <= 8 else 'revisar'}.",
        "Repeats no compran nada: el pipeline es determinista a temperatura 0; "
        "repetir el mismo prompt no reduce la varianza between-prompt, que es la que domina.",
        f"Bimodalidad reproducida: media {b['total_points']:.1f} pts, los 2 caros "
        f"suman {b['expensive_sum']:.1f} = {b['expensive_share_of_mean']:.1%} de la media, "
        f"resto ({b['n_rest']}) media {b['rest_mean']:.2f}%.",
        f"Criterio documentado: IC [{tax['ci_low']}, {tax['ci_high']}] → "
        f"{tax['ci_high'] - 5.0:.2f} pts por encima del umbral → NO cumplido.",
    ]
    tables = {
        "Aritmética del tamaño de muestra (SD=20.36, umbral 5.0)": (
            ["Cantidad", "Valor", "Documentado"],
            [
                ["n implícito (SE 4.16)", f"{n_implied:.0f}", "~24"],
                ["n (media −0.35)", f"{n_mean_obs:.0f}", "—"],
                ["n (media 0, conservador)", f"{n_mean_zero:.0f}", "60"],
                ["n con margen ½ pt", f"{n_with_margin:.0f}", "72"],
            ],
        )
    }
    notes = [
        "La aritmética de muestra se valida (PASS parcial); la re-prueba del "
        "criterio es BLOQUEADA: necesita corpus calibrado + 72 prompts y el "
        "baseline de self-consistency (Zhang et al.), no sólo el monolítico.",
        "Segundo baseline obligatorio (v0.3): justificar el cómputo extra contra "
        "un agente único con self-consistency, no contra el monolítico ingenuo.",
        "Condiciones de rechazo: <20 clusters → negarse; piso baseline <0.20 → "
        "nada que comparar; SE planeado vs medido difieren >25% → negarse.",
    ]
    return Result(
        id="T09", name="Re-prueba del criterio de abandono", model="—",
        verdict=BLOCKED,
        summary=f"aritmética de muestra validada (60/72); re-prueba pendiente de corpus + 72 prompts",
        killed_if="— (no es un modelo; es el go/no-go del proyecto)",
        refusal="<20 clusters · baseline <0.20 · SE planeado/medido >25%",
        details=details, tables=tables, notes=notes,
    )


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
