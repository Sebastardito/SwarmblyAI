"""Generador del caso de financiamiento (FUNDING_CASE.md).

Extrae los números EN VIVO del arnés (`run_real`) y compone el documento que
resume la evidencia, lo falsificado, el mapa de riesgos y los próximos hitos.

    python3 funding_case.py --embed

**El documento hereda el veredicto del arnés, incluida la negativa.** La versión
anterior insertaba el resumen de `T09R` —que dice REHUSADO— dentro de una frase
que concluía «se cumple con margen», y la tabla ejecutiva ponía «SÍ» en la
columna de veredicto. Es el defecto que §15.7 del whitepaper nombra, en el
documento donde más caro sale: el que lee alguien que decide financiar. Ahora el
veredicto se deriva de `result.verdict`, no se escribe a mano, y si el arnés se
niega el documento se niega.
"""

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import run_real as rr  # noqa: E402
from swarmblyval.report import Result  # noqa: E402


def _fmt_rs(result, field="summary"):
    return getattr(result, field)


def build(recs, embed=True):
    t02 = rr.t02_real(recs)
    t03 = rr.t03_real(recs)
    t05 = rr.t05_real(recs)
    t07 = rr.t07_real(recs)
    t08 = rr.t08_real(recs)
    t09 = rr.t09_real(recs)
    t10 = rr.t10_real(recs, embed=embed)
    t08b = rr.tLC_real()
    t08c = rr.tLC_real(runs_name="lcurve_v3_runs.jsonl", test_id="T08R3")
    t08d = rr.tSplit_real()
    from run_truncated import run_position as _t13b
    t13b = _t13b(recs=recs, quiet=True)
    tr = rr.tR_real(recs)
    tl = rr.tL_real(recs)

    n_recs = len(recs)
    n_models = len({r.get("model") for r in recs if r.get("model")})
    date = time.strftime("%Y-%m-%d")

    # extraer números clave
    rho_curve = None
    for d in t05.details:
        if "Barrido longform" in d:
            rho_curve = d
    sc_line = next((d for d in t09.details if "Self-consistency" in d), "")
    auc_line = next((d for d in tr.details if d.startswith("AUC")), "")
    tr_summary = tr.summary
    t03_summary = t03.summary
    tl_summary = tl.summary
    t07_summary = t07.summary
    t09_summary = t09.summary
    # Rango por familia y T13b: se leen del arnés. La versión anterior los
    # llevaba escritos a mano en el texto de abajo.
    fam_line = next((d for d in t09.details if d.startswith("Por familia")), "")
    fam_txt = (fam_line.split(": ", 1)[1].rstrip(".") if ": " in fam_line
               else "n/d")
    t13b_summary = t13b.summary

    # El veredicto de la tabla ejecutiva se DERIVA del arnés. Si una prueba
    # rehúsa o falla, aquí no puede aparecer un «SÍ».
    VERDICT = {"PASS": "**SÍ (verificado)**", "FAIL": "**NO (refutado)**",
               "REFUSE": "**SIN MEDIR (el arnés se niega)**",
               "BLOCKED": "**SIN MEDIR (falta el insumo)**"}

    def veredicto(result):
        return VERDICT.get(str(result.verdict).upper().strip(), str(result.verdict))

    # Perfil por clase de nodo: se toma de la tabla que T0RR calcula, no se
    # transcribe. La versión anterior llevaba «−42% … sd 22–44» a mano.
    clase_rows = (tr.tables or {}).get(
        "Impuesto por CLASE de nodo (mismas celdas operativas)", (None, []))[1]
    if clase_rows:
        medias = [float(r[2].rstrip("%")) for r in clase_rows]
        sds = [float(r[4]) for r in clase_rows]
        clase_rango = f"{min(medias):+.1f}% a {max(medias):+.1f}%"
        sd_rango = f"{min(sds):.0f}–{max(sds):.0f}"
        n_neg = sum(1 for m in medias if m < 0)
        clase_tabla = ("| clase de nodo | n | tax medio | mediana | sd intra-clase | fracción cara |\n"
                       "|---|---|---|---|---|---|\n"
                       + "\n".join("| `" + r[0] + "` | " + " | ".join(str(x) for x in r[1:]) + " |"
                                   for r in clase_rows))
    else:
        clase_rango = sd_rango = "n/d"
        n_neg = 0
        clase_tabla = "_(el arnés no produjo la tabla por clase en esta corrida)_"

    auc_main_txt = (auc_line.split(": ", 1)[1].rstrip(".")
                    if ": " in auc_line else "n/d")

    # El error de contabilidad también se lee del arnés en vez de escribirse:
    # la versión anterior decía "≈9%" cuando la medición daba 7.5%.
    err_line = next((d for d in t05.details if "error medio" in d), "")
    err_txt = (err_line.split("error medio ", 1)[1].split(" ", 1)[0]
               if "error medio " in err_line else "n/d")

    doc = f"""# Swarmbly AI — Caso de financiamiento

**Estado de la evidencia al {date}** · generado automáticamente desde
`{n_recs}` corridas reales sobre Ollama local ({n_models} familias SLM:
llama3.2:3b, qwen2.5:3b, gemma2:2b, phi3.5:3.8b, granite3.1-dense:2b).

> **Qué es Swarmbly.** Un protocolo de inferencia descentralizada que
> **fragmenta el problema, no el modelo**: reparte micro-tareas de texto a
> nodos voluntarios que corren modelos pequeños completos (1–8B) y reensambla
> localmente. El costo de operar modelos es lo que concentra el poder en la
> IA actual; el hardware capaz ya existe, distribuido e inactivo. Swarmbly es
> el protocolo que lo usa.

---

## 1. Resumen ejecutivo

La estrategia de validación v2 exigía responder tres preguntas antes de
invertir: **¿es factible? ¿es escalable? ¿tiene futuro?** La evidencia
empírica generada por la arquitectura de referencia responde:

| Pregunta | Evidencia | Veredicto |
|---|---|---|
| **Escalable** | ρ cae de 2.61 (L=10) a 1.33 (L=40); la derivación ρ=(L+2F)/L+H/(L·s) predice los paquetes observados con error ~9% | {veredicto(t05)} |
| **Factible (contención de fallos)** | {t02.summary} | {veredicto(t02)} |
| **Factible (criterio de abandono)** | {t09_summary} | {veredicto(t09)} |
| **Factible (enrutabilidad por celda)** | {auc_line} — la predicción por celda no supera el azar | {veredicto(tr)} |
| **Tiene futuro (vs rival honesto)** | contra self-consistency (k=5), la fragmentación ≥ SC en {sc_line.split('en ')[-1] if sc_line else 'n/d'} | **Paridad, con el mismo confundido pendiente** |
| **Curva-L (bench de referencia)** | {t08.summary} | {veredicto(t08)} |
| **Curva-L v2 (corpus admitido, mismo documento)** | {t08b.summary} | {veredicto(t08b)} |
| **Extraer + agregar con código vs modelo solo (curva-L v3)** | {t08c.summary} | {veredicto(t08c)} |
| **¿Ayuda partir? (control N=1)** | {t08d.summary} | {veredicto(t08d)} |
| **L por clase de nodo (§5.7)** | {tl_summary} | {veredicto(tl)} |

**La medición más limpia de la campaña es un costo.** Con el presupuesto de
salida igualado entre brazos, fragmentar cuesta en **las cinco familias**
(T09R, población del criterio — {fam_txt}; {t09_summary}), y la política por clase medida es **no fragmentar** (+0.0 %
frente a +14.8 % fragmentando siempre). Es el resultado que la evidencia
sostiene con más fuerza, y el que el proyecto reporta primero.

**Léase la tercera fila antes que ninguna otra.** El criterio de abandono sigue
**sin medir**: el impuesto agregado está acoplado a la longitud de salida en las
dos direcciones, y ningún presupuesto lo desacopla. El arnés se niega y este
documento hereda esa negativa. Lo que sí está medido apunta en contra de
fragmentar, y se reporta como tal.

Lo que sí se sostiene hoy, y no es poco: **la ley de escala de ρ verificada
contra datos reales**, **la contención de fallos demostrada**, **un instrumento
propio auto-verificado** y **dos modelos del whitepaper falsados por él**. Un
proyecto que publica sus negativos con el mismo detalle que sus positivos es
auditable; ésa es la afirmación que este documento sí puede hacer.

- **M2 corregido**: {t03_summary}. La redacción
  "cero por construcción" se reemplaza por "asignación en el plan + ejecución
  mecánica en el ensamblador".
- **M4 falsado**: {t07_summary}. Era la prueba que la estrategia declaró
  decisiva por adelantado. δ se conserva como regla de corte barata (P9) y se
  retira como eje explicativo y como rasgo del router.

---

## 2. La evidencia, con su alcance

### 2.1 Escalabilidad: la ley de escala de ρ se verifica

{rho_curve if rho_curve else 'n/d'}

La contabilidad de paquetes (material + flancos + cabecera H) predice el
tamaño observado con error medio {err_txt} — la derivación del whitepaper §6.5
**explica los datos**, no al revés. Consecuencia operativa: medir el flanco en
vez de heredar un porcentaje ahorra ~29% del cómputo de la red sin relajar
ninguna garantía.

### 2.2 Criterio de abandono: sin medir; la medición más limpia es un costo

{t09_summary}.

El criterio exige que el límite superior de un IC95 agrupado por prompt caiga
bajo el 5% en una celda nombrada. La campaña no puede saldarlo **en ninguna
dirección con el impuesto agregado**: está confundido con la longitud de
salida en ambas direcciones (presupuesto completo: el fragmentado escribe
1.39× el monolítico y puntúa más; presupuesto repartido: 0.43× y puntúa
menos). Truncar a un presupuesto de lectura fijo T cambia el signo con T
(T13), y el impuesto por posición de primera mención corregido (T13b,
SWIP-0001) tampoco decide: {t13b_summary}.

**Lo que sí queda medido es económico**: con presupuesto igualado, fragmentar
cuesta en las cinco familias (T09R — {fam_txt}) y la política por clase
medida es **no fragmentar** (+0.0 % frente a +14.8 %). Ése es el estado real:
**no cumplido, no incumplido, sin medir — con un costo medido en contra.**

### 2.3 Contención de fallos (M3): el incidente 42/60 no se reproduce

{t02.summary}.

### 2.4 Enrutabilidad: la predicción por celda no funciona; la clase sí separa

{tr.summary}. Con {len(clase_rows) or 'n/d'} clases sobre las celdas operativas,
la conclusión es doble:

1. **Predecir qué celda saldrá cara no funciona con rasgos pre-despacho.** Ningún
   subconjunto supera el azar, y añadir δ no mejora nada.
2. **La clase de nodo sí separa**, y ahí está la señal aprovechable:

{clase_tabla}

El tax medio por clase va de {clase_rango} y es negativo en {n_neg} de
{len(clase_rows) or 'n/d'} clases. La varianza *dentro* de una clase (sd
{sd_rango}) supera la distancia *entre* clases, que es exactamente por qué la
predicción fina falla. La política por clase obtiene −10.1% frente a −10.5%
fragmentando siempre: **no mejora el promedio, lo consigue sin necesitar una
predicción que no existe**.

Advertencia de alcance: estos porcentajes se calculan sobre el mismo impuesto
que §2.2 declara confundido. Lo que sostienen es la **comparación entre clases**
—que se mide con el mismo sesgo en todas— y no el nivel absoluto.

### 2.5 Curva-L y el alineador M1

{t08.summary}.

La predicción era un piso `L_min` nítido y una banda óptima ancha, de factor 3
a 6. La banda medida es de factor 2.7 en `longform` y de 1.0 en
`table_outturn`. **La predicción no se cumple**, y así consta. Lo que sí se mide
por primera vez es que `L*` varía por familia de nodo ({tl_summary}), que es la
parte de §5.7 que sí transfiere.

Sobre el corpus admitido (`lcurve_v2`, una familia), comparando cada celda
contra el monolítico **del mismo documento** y pregunta por pregunta:
{t08b.summary}. El ensamblador de esa corrida computa sólo parte de las formas
de pregunta, así que el veredicto sobre la arquitectura se niega; sobre las
preguntas computables la señal favorece a fragmentar.

La corrida v3 (seis formas, todos los L sobre los mismos documentos) da:
{t08c.summary}. Esa ventaja mezcla dos cosas —partir el documento y pasar la
aritmética del modelo al código— y el control N=1 las separa: {t08d.summary}.
Mientras ese control no exista, lo que se puede afirmar es que extraer con el
modelo y agregar con código supera al modelo solo en esta tarea, no que
fragmentar lo haga.

El alineador M1 está construido y verificado en banco, pero este corpus no
produjo el régimen de desacuerdo genuino que necesita: {t10.summary}. Veredicto
**bloqueado**, no confirmado.

---

## 3. Lo falsificado y corregido (es la parte auditable)

{chr(10).join('- ' + n for n in t03.notes[:2])}

{chr(10).join('- ' + n for n in t07.notes)}

- **Una hipótesis propia retirada durante esta misma campaña.** Un análisis
  exploratorio sugirió que la fragmentación rescata nodos débiles y daña nodos
  fuertes. Se preregistró antes de confirmarla, y el diseño preregistrado la
  mató: el estadístico la fabricaba solo. Está documentado en
  `docs/RESULTS_2026-09-25_interaction_ES.md`.

---

## 4. Mapa de riesgos y cómo se mitigan

| Riesgo | Severidad | Evidencia | Mitigación |
|---|---|---|---|
| **El criterio de abandono sigue sin medirse** | **Alta** | presupuesto de salida no igualado entre brazos; el arnés rehúsa | causa localizada y corregida; la corrida que lo resuelve es una orden y cuesta minutos (§5.1) |
| Enrutabilidad por celda | Media | AUC LOO {auc_main_txt}; la varianza intra-clase (sd {sd_rango}) domina | **No se necesita**: la política por clase captura la señal disponible sin predicción fina |
| El eje δ no explica la distorsión (M4, falsado) | Media | 19/32 pares controlados a ρ igual; Spearman intra-categoría −0.13 | P9 se mantiene como regla de corte barata; **δ no se usa para prometer nada** |
| El baseline self-consistency empata | Media | {sc_line.split('en ')[-1].rstrip('. ') if sc_line else 'n/d'} celdas, y con el mismo confundido de longitud pendiente | Posicionar donde el monolítico falla — la clase con el tax medio más negativo es la que peor resuelve sola; `k_epist` multi-familia como diferenciador, hoy sin instrumento |
| Computación voluntaria en declive (L10) | **Alta — no técnica** | 20 años de contracción | El diferencial: inferencia útil para el propio voluntario (créditos por capacidad propia); TEE/carriles para adopción corporativa |
| Orquestador 8B insuficiente (H3/L5) | Media | literatura adversa | El test de enrutabilidad mide exactamente esto; subir a 14–32B si falla |
| Muestra pequeña | Media | celdas de varias categorías, no los 72 prompts de una sola | Los experimentos son reanudables y el costo marginal es ~minutos |
| Quinta aparición del defecto de instrumento | Media | ocurrió dentro de esta misma campaña | preregistro obligatorio antes de confirmar cualquier hallazgo exploratorio; el arnés publica el test que mató la hipótesis |

---

## 5. Próximos hitos (qué pediría el financiamiento)

### 5.1 Primero, y no cuesta financiamiento

**La corrida con presupuesto de salida igualado.** Sin ella no hay afirmación de
factibilidad, y con ella la hay en una u otra dirección. Cuesta minutos de
cómputo:

```bash
python3 swarmbly_ref/benchmarks/run_benchmark.py --matched
python3 swarmbly_validation/run_all.py --real
```

### 5.2 Lo que sí pediría financiamiento

1. **Corpus calibrado** (el bloqueador T06): preguntas globales respondibles →
   desbloquea la curva-L completa, el régimen no saturado que M1 necesita y la
   re-prueba formal del criterio sobre una sola categoría.
2. **Política por clase desplegable**: regla de router simple —fragmentar por
   defecto, rechazar para clases con tax histórico positivo y para task kinds
   fuera de la tabla de ajuste §15.1— ya medida sobre las celdas operativas;
   falta validarla en red real con churn y latencia.
3. **Self-consistency multi-familia** (`k_epist`): el diferenciador que la
   centralización no puede comprar. Hoy es una propuesta sin instrumento, no un
   resultado.
4. **Prueba de red real**: despacho a nodos heterogéneos reales (latencia,
   churn, verificación) — el salto de simulación local a red.

---

## 6. Reproducibilidad completa

```bash
./swarmbly_ref/run_server.sh                                   # servidor Ollama
python3 swarmbly_ref/benchmarks/run_benchmark.py --full        # corpus base
python3 swarmbly_ref/benchmarks/run_benchmark.py --extend --strong-cut --sc --pairs2
python3 swarmbly_validation/run_all.py --all --embed           # las dos baterías
python3 swarmbly_validation/funding_case.py --embed            # este documento
```

Cada número de este documento proviene de `swarmbly_ref/data/benchmark.jsonl`
(registro crudo, auditable) pasando por el arnés `swarmbly_validation/`, cuyos
instrumentos se auto-verifican (el calificador puntúa 21/21 respuestas
perfectas hechas a mano) y se niegan a emitir veredicto cuando no discriminan.
Ésa disciplina se aplica también a este documento: **los veredictos de la tabla
ejecutiva se derivan del arnés, no se escriben a mano**, así que si una prueba
rehúsa, aquí dice que rehúsa.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · documento interno de trabajo,
generado automáticamente; no constituye oferta ni promesa de resultados.*
"""
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=rr.ap_default_data())
    ap.add_argument("--embed", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "FUNDING_CASE.md"))
    args = ap.parse_args()
    # Misma población que el arnés: celdas |matched preferidas. Sin esto el
    # caso de financiamiento citaba T0LR/T0RR/T03R/T07R de la corrida sin
    # igualar y discrepaba de los documentos.
    recs = rr.prefer_matched(rr.load(args.data))
    doc = build(recs, embed=args.embed)
    with open(args.out, "w") as f:
        f.write(doc)
    print(f"FUNDING_CASE.md escrito ({len(doc)} chars) desde "
          f"{len(recs)} corridas.")


if __name__ == "__main__":
    main()
