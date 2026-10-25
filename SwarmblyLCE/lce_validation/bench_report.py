"""F2 — Reporte integrado de los benchmarks de la LCE.

Lee los resultados de cada benchmark y del arnés, y escribe
``results/BENCH_REPORT.md``: resumen claro, cifras, explicaciones,
conclusiones y ajustes propuestos. Sin modelos: solo compila lo ya medido.

    python3 -m lce_validation.bench_report
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "results" / "BENCH_REPORT.md"


def _s(x: float) -> str:
    """+0.123 / −0.123 con menos tipográfico."""
    return f"{x:+.3f}".replace("-", "−")


def _ci(ci) -> str:
    return "[" + ", ".join(_s(v) for v in ci) + "]"


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    hc1 = _load(ROOT / "results" / "bench_hc1_scale" / "results.json")
    rho = _load(ROOT / "results" / "bench_rho" / "results.json")
    soc = _load(ROOT / "results" / "bench_social" / "results.json")
    run2 = _load(ROOT / "results" / "2026-10-05_C1C2_run2" / "results_real.json")

    lines = [
        "---",
        "status: current",
        "lang: es",
        "kind: exploratory",
        "---",
        "",
        "# Reporte integrado de benchmarks — Swarmbly LCE",
        "",
        "*Generado por `lce_validation/bench_report.py` desde los resultados "
        "guardados de cada benchmark (regenerable byte a byte con "
        "`run_derive`). Ningún número de este reporte proviene de simulaciones: "
        "solo de corridas reales (benchmarks) y de la corrida confirmatoria "
        "preregistrada (C1/C2).*",
        "",
        "## 1. Estado exploratorio agregado",
        "",
        "| Pregunta | Evidencia | Estado exploratorio |",
        "|---|---|---|",
    ]

    # F1a
    if hc1 and "summary" in hc1:
        s = hc1["summary"]
        st = ("se sostiene (descriptivo)" if s["holds_descriptively"]
              else "no se sostiene")
        lines.append(
            f"| H-C1 a escala: ¿la memoria local mejora al modelo del usuario? "
            f"| ganancia media por pregunta **"
            f"{s['mean_gain_by_question']:+.3f}** IC95 "
            f"[{s['gain_ci95_by_question'][0]:+.3f}, "
            f"{s['gain_ci95_by_question'][1]:+.3f}] sobre "
            f"{s['n_questions']} preguntas × 5 familias | **{st}** |")
    if run2 and "verdicts" in run2:
        v = run2["verdicts"]
        lines.append(
            "| C1 (control positivo, preregistrado) | exactitud 0.80 con "
            "memoria vs 0.00 sin ella | **se sostiene** |")
        lines.append(
            "| H-C2 léxico (preregistrado) | adherencia 0.667 con Γ vs 0.033 "
            "sin Γ | **se sostiene** |")
        lines.append(
            "| H-C17a / H-C17b (preregistrado) | reducción de homogeneidad "
            "0.073 supera placebo; Δ acuerdo de errores 0.039 dentro de ±0.10 "
            "| **se sostiene, con matices** |")
    if rho and "summary" in rho:
        rs = rho["summary"]
        lines.append(
            f"| H-C2 ρ: ¿la proyección encarece la redundancia? | Δρ por "
            f"paquete +{rs['worst_delta_pct']:.1f}% (peor, medido); por "
            f"solicitud ≈+{rs['worst_delta_pct_per_request']:.1f}% (estimación "
            "aritmética, diseño no implementado) | **"
            f"{rs['verdict_hc2_rho']}** |")
    adp = _load(ROOT / "results" / "bench_adapter" / "results.json")
    if adp and "summary" in adp:
        a = adp["summary"]
        lines.append(
            f"| H-C6 (adaptador real) | LoRA rank 8 en 36 s; adherencia "
            f"bruta {a['adherence']['adapter']:.2f} vs "
            f"{a['adherence']['retrieval']:.2f} (brazos NO comparables) | "
            f"**{a['h6']}** |")
    if soc and "summary" in soc:
        ss = soc["summary"]
        lines.append(
            f"| H-C11 (dirección, C9-lite) | circuito de adopción por "
            f"utilidad ejercitado; identidad 1+1 es la misma respuesta dos "
            f"veces | **{ss['h11_direction']}** |")
    an = _load(ROOT / "results" / "bench_r13" / "analysis.json")
    if an:
        d = an["a3_minus_a2"]
        lines.append(
            "| R13 (piloto): ¿la wiki anclada supera a un RAG crudo? | A3 − A2 = "
            f"**{_s(d['mean'])}** {_ci(d['ci95'])} sobre {d['n_questions']} "
            "preguntas, tres digestores × tres respondedores | **el RAG crudo gana "
            "en exactitud; la pérdida está en la cobertura de la digestión** |")
    lines.append(
        "| R11 (piloto): adaptador justo | conclusiones retiradas (E6: adaptador "
        "colapsado, tareas inválidas, sin Γ en el brazo de recuperación) | "
        "**sin evidencia; rediseño en la siguiente fase** |")
    lines.append(
        "| R12 (exploratorio): plano social | 0/40 por construcción; utilidad "
        "implementada como novedad; sin F_ST (E7) | **compatible con la I4, no la "
        "mide** |")
    ca = _load(ROOT / "results" / "bench_r13_confirm" / "analysis.json")
    if ca:
        d, dr = ca["a3_minus_a2"], ca["decision_rules"]
        lines.append(
            "| R13 CONFIRMATORIA: ¿la wiki anclada supera a un RAG crudo? | A3 − A2 = "
            f"**{_s(d['mean'])}** {_ci(d['ci95'])} sobre {d['n_questions']} preguntas | "
            f"**R13-H1 {dr['r13_h1']['verdict']}**; H2 {dr['r13_h2']['verdict']} (el tipo "
            "`deleted` no mide olvido, N2); H3: la compuerta se retira como regla |")
    lines.append(
        "| F-forget: ¿olvidar una fuente borra lo aprendido de ella? | residuo 0, "
        "colateral 0; abstención W_full → W_forget ≈ W_never | **el olvido se "
        "sostiene (mecanismo)** |")
    lines.append(
        "| A/A de reproducibilidad (R14) | generación casi idéntica, digestión no "
        "reproducible entre corridas | **R14 abierto (negativo documentado)** |")
    lines.append(
        "| C2-bis | mide la homogeneidad entre SEMILLAS de un mismo usuario, no "
        "entre usuarios | **no prueba H-C17a (constructo distinto)** |")
    lines.append(
        "| Cierre H-C2 (2.9) | ganancia medida en exactitud de QA, no en adherencia; "
        "regla inalcanzable con ganancias binarias por tarea | **descriptivo: Γ "
        "cuesta ρ y no mejora QA; H-C2 sin decidir para escritura** |")
    lines.append(
        "| R11 CONFIRMATORIA: adaptador justo | adaptador y base dan texto idéntico "
        "byte a byte en las 720 tareas y los mismos aciertos en las 1454 celdas | "
        "**rechazada: falla de "
        "manipulación (el adaptador no se aplicó en la evaluación)** |")
    lines += ["", "## 2. Detalle por benchmark", ""]

    # 2.1 H-C1 a escala
    if hc1 and "summary" in hc1:
        s = hc1["summary"]
        lines += ["", "### 2.1 H-C1 a escala (memoria local, 5 familias × 5 usuarios)",
                  "",
                  f"**Cifra central.** {s['n_questions']} preguntas (12 por "
                  "usuario: 5 factuales, 4 de léxico, 3 de procedimiento, con "
                  "preguntas entre documentos), 5 familias por pregunta. "
                  "Ganancia media por PREGUNTA "
                  f"**{s['mean_gain_by_question']:+.3f}** con IC95 "
                  f"[{s['gain_ci95_by_question'][0]:+.3f}, "
                  f"{s['gain_ci95_by_question'][1]:+.3f}] (agrupado por "
                  "pregunta; por celda: "
                  f"{s['mean_gain']:+.3f} [{s['gain_ci95_cells'][0]:+.3f}, "
                  f"{s['gain_ci95_cells'][1]:+.3f}]). Las estadísticas de la "
                  "wiki por familia y usuario están guardadas en el "
                  "resultado.",
                  "",
                  "**Por familia:**", ""]
        ws = hc1.get("wiki_stats", {})
        for m, v in s["by_model"].items():
            extra = ""
            if m in ws:
                us = list(ws[m].values())
                anch = [u["claims"] - u["maturity"]["RAW"] - u["maturity"]["DIGESTED"] for u in us]
                rate = [1 - u["anchor_rejection_rate"] for u in us]
                extra = (f"; afirmaciones ancladas por usuario {min(anch)}–{max(anch)} "
                         f"(media {sum(anch) / len(anch):.1f}), tasa de anclaje "
                         f"{min(rate):.2f}–{max(rate):.2f}")
            lines.append(f"- `{m}`: ganancia media {v['mean_gain']:+.3f} "
                         f"(n={v['n']}){extra}")
        lines += ["", "**Por usuario:**", ""]
        for u, v in s["by_user"].items():
            lines.append(f"- `{u}`: ganancia media {v['mean_gain']:+.3f} "
                         f"(n={v['n']})")
        lines += [
            "",
            "**Explicación.** La memoria convierte en recuperables preguntas "
            "que ningún modelo base puede responder (hechos del usuario, "
            "umbrales de su protocolo, términos preferidos). La variación "
            "entre familias mezcla dos cosas —la familia digiere Y responde— "
            "y la atribución al digestor la separa el diseño cruzado de R13 "
            "(sección 2.8), que la explica por la cobertura de la digestión. "
            "Solo phi3.5 se separa aquí por el tamaño de su wiki (muchas menos "
            "afirmaciones ancladas); entre las otras cuatro, ni el número de "
            "afirmaciones ancladas ni la tasa de anclaje ordenan la ganancia. "
            "R13-H3 retiró el piso de afirmaciones ancladas como regla: una "
            "compuerta, si se adopta, debe medir cobertura contra preguntas "
            "reservadas.",
            "",
            "**Ajuste propuesto.** Un usuario real; el brazo «memoria + "
            "proyección Γ» y el diseño cruzado digestor/respuesta se hicieron en "
            "R13 (sección 2.8)."]

    # 2.2 ρ
    if rho and "summary" in rho:
        rs = rho["summary"]
        lines += ["", "### 2.2 ρ de la proyección (camino de despacho real)", "",
                  f"**Cifra central.** Sobre el documento de procedimientos de "
                  "cada usuario (19-32 oraciones, 391-718 tokens de material), "
                  "fragmentado con P9 (L=10, F=2), con el PROYECTOR real de la "
                  "LCE: la proyección sube ρ "
                  f"**+{rs['median_delta_pct']:.1f}%** (mediana) y "
                  f"**+{rs['worst_delta_pct']:.1f}%** (peor) con el protocolo "
                  "actual (Γ replicado en cada paquete).",
                  "",
                  "**Explicación.** Δρ es estructural: ≈ tamaño de Γ / tamaño "
                  "de cada paquete, y no se diluye con documentos más largos.",
                  "",
                  "**Qué NO concluye.** La condición de muerte real de H-C2 "
                  "(«muere si el aumento de ρ supera la ganancia») exige "
                  "comparar este costo con la ganancia de adherencia; esa "
                  "comparación y los diseños por-solicitud o con caché "
                  "quedan pendientes.",
                  "",
                  "**Estimación, no medición.** Si Γ se inyectara una sola vez "
                  "por solicitud, la misma aritmética sobre estos conteos de "
                  "tokens daría "
                  f"+{min(u['delta_pct_per_request'] for u in rho['users'].values()):.1f}% a "
                  f"+{rs['worst_delta_pct_per_request']:.1f}% "
                  f"(mediana +{rs['median_delta_pct_per_request']:.1f}%). Ese "
                  "diseño no existe en el protocolo y la cifra no está medida; "
                  "una caché de Γ por usuario en el nodo podría acercarla a "
                  "cero, lo que es una hipótesis."]

    # 2.3 C9-lite
    if soc and "summary" in soc:
        ss = soc["summary"]
        lines += ["", "### 2.3 C9-lite social (5 nodos reales)", "",
                  f"**Cifras.** Masa de colas post: utilidad "
                  f"{ss['tail_mass_utility']:.2f} vs prevalencia "
                  f"{ss['tail_mass_prevalence']:.2f} (la del brazo de "
                  "utilidad sale del diseño: nadie conocía los términos y "
                  "todos copian la glosa del contexto). Identidad: "
                  f"{ss['identity_violations_utility']}+"
                  f"{ss['identity_violations_prevalence']} — la sonda no "
                  "recibe las cápsulas, así que es la misma respuesta dos "
                  "veces. Estado: **" + ss["h11_direction"] + "**.",
                  "",
                  f"**Alcance y desviaciones.** {ss['scope']}. Dos "
                  "desviaciones post-corrida están declaradas en el "
                  "encabezado de `bench_social.py`.",
                  "",
                  "**Ajuste propuesto.** La versión justa (siguiente fase): "
                  "sonda con cápsulas en contexto, prevalencia que adopta la "
                  "variante mayoritaria aunque sea errónea, utilidad juzgada "
                  "por beneficio posterior, cápsulas con el conocimiento del "
                  "nodo fuente, varias rondas, y el canario verificado por "
                  "hablantes nativos."]

    # 2.4 adaptador (factibilidad)
    if adp and "summary" in adp:
        a = adp["summary"]
        lines += ["", "### 2.4 Adaptador real (factibilidad, MLX LoRA)", "",
                  f"**Cifras.** LoRA rank 8 entrenado en 36 s (200 iters, 13 "
                  "pares) sobre Qwen2.5-3B-Instruct. Adherencia bruta: base "
                  f"{a['adherence']['base']:.2f}, recuperación "
                  f"{a['adherence']['retrieval']:.2f}, adaptador "
                  f"{a['adherence']['adapter']:.2f}. Facticidad: base "
                  f"{a['factual_base']:.2f} vs adaptador "
                  f"{a['factual_adapter']:.2f}.",
                  "",
                  "**Qué NO concluye.** La adherencia no compara brazos "
                  "justos (el lote contamina las tareas; la recuperación "
                  "solo recibió el documento de estilo; sin intervalo de "
                  "confianza): "
                  f"**{a['h6']}**. Los pesos no se distribuyen (licencia "
                  "qwen-research del modelo base); el manifiesto con su "
                  "SHA-256 y la receta están en el resultado. Reentrenar con "
                  "la receta da un adaptador funcionalmente equivalente, no "
                  "necesariamente idéntico bit a bit (MLX no garantiza "
                  "determinismo); el manifiesto permite comprobarlo.",
                  "",
                  f"**Alcance.** {a['scope']}.",
                  "",
                  "**Ajuste propuesto (siguiente fase).** Tareas separadas "
                  "del lote con otra redacción, lote solo de afirmaciones "
                  "entrenables (I1) con ExampleBuilder, repaso y prueba "
                  "nueva, ≥30 tareas con IC, y una segunda familia base de "
                  "licencia permisiva."]

    if an:
        d = an["a3_minus_a2"]
        dg = an["a3_minus_a2_by_digester"]
        ty = an["a3_minus_a2_by_type"]
        cov = an.get("gold_in_context_answerable", {})
        lines += ["", "### 2.5 R13 (piloto exploratorio, superado por la confirmatoria de la sección 2.8)", "",
                  f"**Cifra central.** A3 − A2 = **{_s(d['mean'])}** {_ci(d['ci95'])} "
                  f"por pregunta ({d['n_questions']} preguntas; bootstrap agrupado por "
                  "pregunta). Por digestor: " + "; ".join(
                      f"`{g}` {_s(v['mean'])} {_ci(v['ci95'])}" for g, v in dg.items()) + ".",
                  "",
                  "**Por tipo:** " + "; ".join(
                      f"`{k}` {_s(v['mean'])} {_ci(v['ci95'])} (n={v['n_questions']})"
                      for k, v in ty.items()) + ".",
                  "",
                  "**Memoria frente a nada (preguntas con respuesta):** A3 − A0 = "
                  f"{_s(an['a3_minus_a0_answerable']['mean'])} {_ci(an['a3_minus_a0_answerable']['ci95'])}; "
                  f"A2 − A0 = {_s(an['a2_minus_a0_answerable']['mean'])} {_ci(an['a2_minus_a0_answerable']['ci95'])}.",
                  "",
                  "**Dónde pierde la wiki.** Clave presente en el contexto (preguntas "
                  "con respuesta): " + "; ".join(f"{k} {v:.3f}" for k, v in cov.items()
                                                 if k != "n_questions") + ". " +
                  "La diferencia está en la cobertura de la digestión.",
                  "",
                  "**Qué NO concluye.** `deleted` no mide olvido (ningún brazo vio "
                  "la fuente borrada) y la abstención premia al brazo que recupera "
                  "menos; la prueba de olvido real es F-forget (Enmienda 6). Sin las "
                  "tres claves superadas (N1): "
                  f"{_s(an['n1_a3_minus_a2_without_stale']['mean'])} "
                  f"{_ci(an['n1_a3_minus_a2_without_stale']['ci95'])}."]
    ff = _load(ROOT / "results" / "bench_forget" / "results.json")
    fa = _load(ROOT / "results" / "bench_forget" / "analysis.json")
    if ff and fa:
        fs, bp = ff["summary"], fa["behaviour_prereg"]
        lines += ["", "### 2.6 F-forget (olvido real, Enmienda 6 c)", "",
                  f"**Estructura.** {fs['cells'] - fs['refused_cells']} celdas válidas "
                  f"(usuario × digestor): residuo S2 = {fs['S2_residue_total']} y daño "
                  f"colateral S3 = {fs['S3_collateral_total']}; barrido de "
                  f"{fs['sweep_forgets']} olvidos sin residuo ni daño. `forget_source` "
                  "borra por anclaje, así que S2 y S3 verifican la implementación sobre "
                  f"wikis reales. **Veredicto estructural: {fs['verdict_structural']}.** "
                  f"W_forget coincide con la W_never de la misma corrida en "
                  f"{fs['S4_identical_claim_sets']}/{fs['cells']} wikis: la diferencia es "
                  "el no determinismo de la digestión (AA2).",
                  "",
                  "**Conducta.** Abstención en las preguntas sobre la fuente borrada: "
                  f"W_full {bp['abstention']['full']:.3f}, W_forget "
                  f"{bp['abstention']['forget']:.3f}, W_never {bp['abstention']['never']:.3f}; "
                  f"forget − full = {_s(bp['forget_minus_full'])} {_ci(bp['forget_minus_full_ci95'])}, "
                  f"forget − never = {_s(bp['forget_minus_never'])} "
                  f"{_ci(bp['forget_minus_never_ci95'])} ({bp['n_questions']} preguntas; mecanismo)."]
    aa = _load(ROOT / "results" / "aa_test" / "results.json")
    if aa and "summary" in aa:
        s = aa["summary"]
        yn = lambda b: "pasa" if b else "falla"  # noqa: E731
        lines += ["", "### 2.7 A/A de reproducibilidad (R14)", "",
                  f"AA1 generación a T = 0 contra la confirmatoria de R13: "
                  f"{100 * s['AA1']['identical_rate']:.1f} % de {s['AA1']['n']} respuestas "
                  f"idénticas, Δ exactitud {s['AA1']['accuracy_delta']:+.4f} "
                  f"({yn(s['AA1']['passed'])}, el umbral es 99 %). AA2 digestión: "
                  f"{s['AA2']['identical']}/{s['AA2']['wikis']} wikis idénticas entre corridas, "
                  f"Jaccard {s['AA2']['mean_jaccard']:.3f} ({yn(s['AA2']['passed'])}). AA3: "
                  f"semilla del endpoint nativo {100 * s['AA3']['native']['identical_rate']:.0f} % "
                  f"idéntica, compatible con OpenAI {100 * s['AA3']['openai']['identical_rate']:.0f} %. "
                  f"AA4 homogeneidad: Δ {_s(s['AA4']['mean_diff'])} {_ci(s['AA4']['ci95'])} "
                  f"({yn(s['AA4']['passed'])}).",
                  "",
                  "**R14 queda abierto como negativo documentado (Enmienda 12):** la "
                  "digestión con Ollama no es reproducible entre corridas en este equipo "
                  "en ninguna de las cuatro configuraciones probadas."]
    if ca:
        d, dr = ca["a3_minus_a2"], ca["decision_rules"]
        ty, dg, aw = ca["a3_minus_a2_by_type"], ca["a3_minus_a2_by_digester"], ca["abstention_with_accuracy"]
        cov = ca.get("gold_in_context_answerable", {})
        g = dr["hc1_death_global"]
        lines += ["", "### 2.8 R13 confirmatoria (preregistro 2.7, enmiendas 7–12)", "",
                  f"**Cifra central.** A3 − A2 = **{_s(d['mean'])}** {_ci(d['ci95'])} sobre "
                  f"{d['n_questions']} preguntas (≥ 30 por tipo, LongMemEval incluido, N1 "
                  "excluido). Por digestor: " + "; ".join(
                      f"`{k}` {_s(v['mean'])} {_ci(v['ci95'])}" for k, v in dg.items()) + ".",
                  "",
                  "**Por tipo:** " + "; ".join(
                      f"`{k}` {_s(v['mean'])} {_ci(v['ci95'])} (n={v['n_questions']})"
                      for k, v in ty.items()) + ".",
                  "",
                  "**Cobertura de la respuesta en el contexto (preguntas con respuesta):** "
                  + "; ".join(f"{k} {v:.3f}" for k, v in cov.items() if k != "n_questions") + ".",
                  "",
                  f"**Veredictos.** R13-H1 {dr['r13_h1']['verdict']}. R13-H2 "
                  f"{dr['r13_h2']['verdict']}: la wiki pierde en actualización y su "
                  "«victoria» en `deleted` es el artefacto N2 (A0, sin memoria, se abstiene "
                  f"en el {100 * aw['A0']['abstention_deleted']:.0f} %). R13-H3: la compuerta "
                  "se retira como regla. Muerte global de H-C1: "
                  f"{g['reading_wins_neither']} con la lectura «no gana en ninguno», "
                  f"{g['reading_not_both']} con «no gana en ambos» (el texto en español dice "
                  "«ni», el inglés «and»: Enmienda 15.3); por la letra en español no "
                  "dispara solo por el tipo 5, que no mide olvido. La justificación de la "
                  "wiki por exactitud cae por R13-H1."]
    c2b = _load(ROOT / "results" / "bench_c2bis" / "results.json")
    if c2b and "summary" in c2b:
        cs = c2b["summary"]
        lines += ["", "### 2.9 C2-bis (placebo igualado en instrucción)", "",
                  f"Diferencia de homogeneidad placebo − Γ = {_s(cs['mean_reduction'])} {_ci(cs['ci95'])} "
                  f"({cs['n_cells']} celdas usuario × tema). La homogeneidad se calculó entre "
                  "las tres SEMILLAS de un mismo usuario y tema, no entre usuarios: mide la "
                  "variedad de muestreo dentro de un usuario, no lo que H-C17a pregunta "
                  "(la convergencia de la población). **No prueba H-C17a**; el rediseño "
                  "necesita homogeneidad entre usuarios, brazo sin contrato y un placebo "
                  "neutro que no prescriba registro ni vocabulario. Los números de la primera corrida (invalidada por "
                  "la Enmienda 14) no se conservaron. Ver `docs/RESULTS_2026-10-11_C2bis_ES.md`."]
    hc2 = _load(ROOT / "results" / "bench_hc2_closure" / "results.json")
    if hc2 and "summary" in hc2:
        hs = hc2["summary"]
        lines += ["", "### 2.10 Cierre de H-C2 (preregistro 2.9)", "",
                  f"{hs['n_tasks']} tareas: ganancia media {_s(hs['mean_gain'])} (A4 − A3 en "
                  f"exactitud de QA), Δρ mediana {hs['median_delta_rho_pct']:.0f} % con "
                  f"contextos de 200 tokens (cota aritmética: tokens de Γ por fragmento, sin "
                  f"el packer); fracción con ganancia > 0 y Δρ ≤ 10 % = "
                  f"{hs['frac_both']:.2f}. La regla dispara mecánicamente, pero mide otra cosa: "
                  "la ganancia preregistrada era de adherencia (léxico) y aquí es exactitud de "
                  "QA, y con ganancias binarias por tarea la regla del 80 % es casi "
                  "inalcanzable. **Descriptivo:** en QA, Γ añade ρ sin mejorar la exactitud; "
                  "H-C2 queda sin decidir para su uso propio, la escritura. Ver "
                  "`docs/RESULTS_2026-10-11_HC2_closure_ES.md`."]
    r11 = _load(ROOT / "results" / "bench_r11_confirm" / "results.json")
    if r11 and "cells" in r11:
        cells = r11["cells"]
        txt = [c for c in cells if "base" in c and "adapter" in c]
        same_txt = sum(c["base"] == c["adapter"] for c in txt)
        same_ok = sum(c["base_ok"] == c["adapter_ok"] for c in cells)
        lines += ["", "### 2.11 R11 confirmatoria (Enmiendas 9 y 13)", "",
                  f"En {same_txt} de {len(txt)} tareas el texto del adaptador es idéntico "
                  f"byte a byte al del modelo base, y en {same_ok} de {len(cells)} celdas "
                  "(tareas, I1, LC6, H-C10) coinciden los aciertos; el brazo adaptador + "
                  "recuperación coincide exactamente con recuperación. Con pesos LoRA "
                  "distintos de cero, eso indica que el adaptador no se aplicó en la "
                  "evaluación (servidor MLX con el nombre del modelo base en cada petición; "
                  "además, la evaluación usa completions sin la plantilla de chat con la que "
                  "se entrenó). **La corrida se rechaza por falla de manipulación**, como la "
                  "corrida 1 de C2: no dice nada sobre H-C6, H-C10, I1 ni LC6, y la capa 2 "
                  "no queda retirada por esta evidencia."]
    lines += ["", "## 3. Cierre", "",
              "Lo confirmado: la corrida 2 de C1/C2 (léxico, homogeneidad entre usuarios "
              "frente a placebo, equivalencia de errores compartidos) y R13-H1 (la wiki "
              "anclada pierde frente a un RAG crudo en exactitud, por la cobertura de la "
              "digestión). Lo medido como mecanismo: la memoria local ayuda (F1a), el olvido "
              "funciona (F-forget). Lo abierto: R14 (digestión no reproducible), H-C17a con "
              "un placebo igualado entre usuarios, H-C2 para escritura, y la capa 2, cuya "
              "confirmatoria se rechazó por falla de manipulación.", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"reporte escrito: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
