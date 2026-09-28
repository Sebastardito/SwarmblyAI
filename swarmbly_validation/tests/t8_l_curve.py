"""T08 — Curva-L. WHITEPAPER_V2 §5.6, §15.4, VALIDATION §5.2.

Predicciones (NO medidas): existe un piso `L_min` duro (más nítido que el
óptimo), y una banda óptima ancha (factor 3–6×), dependiente de la definición de
"unidad" (Pfam 96 vs SCOP 174 residuos). Hoy cualquier L es una conjetura
informada (L16).

La prueba implementa el analizador de curva (detección de piso/rodilla/banda) y
lo demuestra sobre datos sintéticos; el veredicto empírico es BLOQUEADO porque
la curva-L no es medible con el corpus actual (T06).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmblyval.report import Result, BLOCKED


def analyze_l_curve(points):
    """points = [(L_sentences, quality), ...] ordenados por L.

    Detecta: (1) el piso L_min (primer L donde la calidad deja de ser ~ruido,
    i.e. sube > 1.5× el rango de ruido); (2) el comienzo de la banda óptima;
    (3) el ancho de banda como factor entre el último y el primer L "bueno".
    """
    if len(points) < 4:
        return {"refuse": "menos de 4 puntos: negarse a detectar piso/banda"}
    ls = [p[0] for p in points]
    qs = [p[1] for p in points]
    qmax = max(qs)
    # banda óptima = L cuya calidad >= 95% del máximo
    good = [ls[i] for i in range(len(points)) if qs[i] >= 0.95 * qmax]
    # piso = primer L donde la calidad supera el 10% del máximo (sale del ruido)
    floor = next((ls[i] for i in range(len(points)) if qs[i] >= 0.10 * qmax), None)
    band_width = (max(good) / min(good)) if len(good) >= 2 else None
    return {
        "L_min_est": floor,
        "band": (min(good), max(good)) if len(good) >= 2 else None,
        "band_width_factor": band_width,
        "qmax": qmax,
    }


def run():
    # datos sintéticos de demostración: piso nítido en ~8, banda 20–80 (factor 4×)
    synthetic = [(L, min(1.0, max(0.0, (L - 4) / 16) * (0.6 + 0.4 / (1 + (L - 40) ** 2 / 900))))
                 for L in range(2, 121, 2)]
    r = analyze_l_curve(synthetic)

    details = [
        "Predicción 1: existe un piso `L_min` duro, más nítido que el óptimo "
        "(homólogo: 25–30 residuos en proteínas).",
        "Predicción 2: la banda óptima es ANCHA (factor 3–6×), y su centro depende "
        "de la definición de 'unidad' (Pfam 96 vs SCOP 174).",
        f"Demo sobre datos sintéticos: L_min≈{r.get('L_min_est')}, banda "
        f"{r.get('band')} (factor {r.get('band_width_factor', '—')}×).",
        "El analizador `analyze_l_curve([(L, calidad), ...])` está listo para los "
        "pares medidos.",
    ]
    tables = {
        "Demo del analizador (sintético)": (
            ["Métrica", "Valor"],
            [
                ["L_min estimado", r.get("L_min_est")],
                ["Banda óptima (≥95% máx)", r.get("band")],
                ["Factor de ancho de banda", r.get("band_width_factor")],
                ["Calidad máx", f"{r.get('qmax'):.2f}"],
            ],
        )
    }
    notes = [
        "VEREDICTO BLOQUEADO: la curva-L no es medible con el corpus actual "
        "(monolítico 1/72). `L_min` y la banda son PREDICCIONES (L16), no medidas.",
        "Primera vez que el tamaño de fragmento sería variable independiente: "
        "barrer L de 2 a 100 oraciones con material fijo. Si no hay rodilla, la "
        "premisa central cae y nada de lo demás importa (FUNDAMENTOS §5).",
        "N se deriva: N = ⌈material/L⌉. Invertir la v1.4 (donde N era el parámetro).",
    ]
    return Result(
        id="T08", name="Curva-L", model="—",
        verdict=BLOCKED,
        summary="analizador listo; `L_min` y banda óptima son predicciones no medidas",
        killed_if="no aparece piso ni banda discernibles (la premisa central cae)",
        refusal="se niega con <4 puntos (L, calidad)",
        details=details, tables=tables, notes=notes,
    )


if __name__ == "__main__":
    import swarmblyval.report as rep
    print(rep.render_console([run()]))
