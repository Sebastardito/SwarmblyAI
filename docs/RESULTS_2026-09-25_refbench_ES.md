---
status: current
lang: es
---

# Resultados — la campaña de referencia: 341 corridas sobre cinco familias

**25 de septiembre de 2026**

Este documento es el registro de la primera campaña que somete los cinco modelos
M1–M5 a medición sobre modelos reales. El análisis razonado está en §15.9 de
`WHITEPAPER_V2_ES.md`; aquí van el instrumento, la procedencia de los datos, la
tabla de veredictos y lo que cada uno permite y no permite afirmar.

## 1. Qué se corrió

| | |
|---|---|
| Implementación de referencia | `swarmbly_ref/` — router, planificador, empaquetado, triaje, ensamblado, calificación |
| Arnés de falsación | `swarmbly_validation/` — Python 3 stdlib, cero dependencias |
| Familias de nodo | `llama3.2:3b`, `qwen2.5:3b`, `gemma2:2b`, `phi3.5:3.8b`, `granite3.1-dense:2b` |
| Corpus de tareas | 22 tareas deterministas con claves verificables |
| Registro | `swarmbly_ref/data/benchmark.jsonl` — **341** corridas |
| Digest | sha256 `d94bb9cc7694d0f7…`, anclado en `T00` |

Reproducción completa:

```bash
python3 swarmbly_validation/run_all.py --all
```

El arnés devuelve código de salida distinto de cero si alguna prueba falla, y
**se niega** —en vez de emitir veredicto— cuando el dato no sostiene la
pregunta. El digest del corpus se comprueba antes de usarlo: si cambia, `T00`
falla y el resto no llega a correr.

## 2. Veredictos

| Prueba | Modelo | Veredicto | Cifra que decide |
|---|---|---|---|
| T0R | P2 | ✔ | router contra la verdad del corpus: **22/22** |
| T02R | M3 | ✔ | los **3** paquetes contaminados se rechazan; el incidente 42/60 no se reproduce |
| T03R | M2 | ✔ corregido | **6/35** exactamente una vez por obediencia del nodo; **35/35** tras imposición mecánica; **0** omisiones |
| T04R | M4 | ✘ | Spearman(δ, impuesto) = **−0.13** sobre **127** celdas intra-categoría |
| T05R | — | ✔ | contabilidad de paquete con **7.5 %** de error; ρ cae de **2.61** a **1.33** al pasar `L` de 10 a 40 |
| T06R | — | ✔ | calificador **21/21** sobre la respuesta perfecta; **100** de **105** monolíticos sobre el piso |
| T07R | M4 | ✘ | δ sube en **32/32** pares a ρ igual; el impuesto empeora sólo en **19/32** |
| T08R | — | ✘ | banda de `L`: factor **1.0** en `table_outturn`, **2.7** en `longform`; la banda ancha predicha no aparece |
| T09R | — | ◌ rehusado | **−18.32 %** IC 95 % [**−31.00**, **−6.95**] sobre **130** celdas, confundido con la longitud de salida |
| T10R | M1 | ▣ bloqueado | sin régimen no saturado en este corpus |
| T0RR | P2 | ✘ | AUC **0.38** con δ y reputación; **0.43** sin ninguno de los dos |
| T0RR2 | P2 | ✘ | AUC **0.47** con sondas de capacidad |
| T0LR | §5.7 | ✔ | `L*` varía por familia; ganancia media sobre `L` común: **+0.015** |

## 3. Lo que cada veredicto permite afirmar

**M4 — falsado.** T07R es la prueba que la estrategia declaró decisiva por
adelantado: el mismo prompt, el mismo `L`, dos cortes de distinta calidad. ρ
queda igual y sólo δ se mueve. La predicción es que el corte fuerte empeore la
distorsión en todos los pares; empeora en 19 de 32. T04R converge desde una
medición observacional independiente. δ se conserva como magnitud descriptiva
del plan y se retira como eje explicativo.

**M2 — sobrevive corregido.** Los nodos reales no obedecen `unique_here`: 6 de
35 términos aparecen exactamente una vez. Pero no hay ninguna omisión, y la
imposición mecánica del ensamblador lleva el resultado a 35/35. La asignación en
el plan elimina el modo de fallo irreparable; el reparable lo elimina el
ensamblador. «Cero por construcción» se retira como enunciado general.

**M3 — sobrevive.** El predicado mecánico rechaza los paquetes que llevan la
respuesta de otro paquete.

**M1 — sin instrumento.** El alineador con sustitución semántica está construido
y se verifica en banco (T10): distingue `noon~midday` de `noon~midnight`, que es
lo que el alineador por identidad no hace. El corpus real no produjo el régimen
de desacuerdo genuino que M1 necesita, así que el veredicto es *bloqueado* y no
*falsado*.

**El router por celda — refutado.** Ningún subconjunto de rasgos supera el azar.
Lo que separa es la clase de nodo:

| clase de nodo | n | impuesto medio | mediana | sd intra-clase | fracción cara |
|---|---|---|---|---|---|
| `granite3.1-dense:2b` | 16 | −41.9 % | −32.5 % | 44.1 | 19 % |
| `gemma2:2b` | 16 | −10.1 % | −9.4 % | 35.4 | 38 % |
| `qwen2.5:3b` | 16 | −7.8 % | −8.8 % | 47.4 | 38 % |
| `phi3.5:3.8b` | 16 | −0.4 % | −2.1 % | 22.9 | 38 % |
| `llama3.2:3b` | 16 | +7.6 % | +13.0 % | 31.3 | 56 % |

La distancia entre clases es grande y la varianza dentro de una clase es mayor.
Eso explica a la vez por qué la predicción por celda falla y por qué una
política por clase funciona: **−10.1 %** frente a **−10.5 %** fragmentando
siempre, sin necesitar la predicción que no existe.

## 4. Lo que no se puede afirmar, y por qué

El criterio de abandono **no se ha medido**. El brazo fragmentado recibió más
presupuesto de salida que el monolítico —cada fragmento heredaba el
`max_out_tokens` del prompt entero— y dentro de una misma tarea escribir más
puntúa más. El arnés rehúsa emitir veredicto sobre ese agregado.

La causa está localizada en el código y corregida. La corrida que resuelve el
asunto es una sola orden:

```bash
python3 swarmbly_ref/benchmarks/run_benchmark.py --matched
```

Los campos `output_words` y `length_ratio` son ahora campos de primera clase del
registro, de modo que el confundido sea visible en cualquier análisis futuro sin
tener que re-derivarlo del texto.

## 5. Documentos relacionados

- `WHITEPAPER_V2_ES.md` §15.9 — el análisis razonado y sus consecuencias de diseño.
- `PREREGISTRATION_2026-09-25_interaction_ES.md` y
  `RESULTS_2026-09-25_interaction_ES.md` — la hipótesis que se retiró durante
  esta campaña, y el preregistro que lo hizo posible.
- `VALIDATION_STRATEGY_V2_ES.md` §11 — qué le pasa a la agenda tras ejecutarla.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Compañero en inglés:
`RESULTS_2026-09-25_refbench_EN.md`.*
