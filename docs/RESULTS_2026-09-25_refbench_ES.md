---
status: current
lang: es
---

# Resultados — la campaña de referencia: 473 corridas sobre cinco familias

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
| Registro | `swarmbly_ref/data/benchmark.jsonl` — **473** corridas |
| Digest | sha256 `dcd1931d98f7f0ec…`, anclado en `T00` |

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
| T03R | M2 | ✔ corregido | **23/35** exactamente una vez por obediencia del nodo; **35/35** tras imposición mecánica; **0** omisiones |
| T04R | M4 | ✘ | Spearman(δ, impuesto) = **−0.15** sobre **127** celdas intra-categoría |
| T05R | — | ✔ | contabilidad de paquete con **7.5 %** de error; ρ cae de **2.61** a **1.33** al pasar `L` de 10 a 40 |
| T06R | — | ✔ | calificador **21/21** sobre la respuesta perfecta; **100** de **105** monolíticos sobre el piso |
| T07R | M4 | ✘ | δ sube en **32/32** pares a ρ igual; el impuesto empeora sólo en **15/32** |
| T08R | — | ✘ | banda de `L`: factor **1.0** en `table_outturn`, **2.7** en `longform`; la banda ancha predicha no aparece |
| T09R | — | ◌ rehusado | **+11.17 %** IC 95 % [**+4.80**, **+17.34**] sobre **95** celdas, confundido con la longitud de salida |
| T10R | M1 | ▣ bloqueado | sin régimen no saturado en este corpus |
| T0RR | P2 | ✘ | AUC **0.57** con δ y reputación; **0.61** sin ninguno de los dos |
| T0RR2 | P2 | ✘ | AUC **0.57** con sondas de capacidad |
| T0LR | §5.7 | ✔ | `L*` varía por familia; ganancia media sobre `L` común: **+0.360** |
| T13 | — | ◌ negado | el impuesto truncado cambia de signo con el presupuesto de lectura T (**−15.66 %** en T=40, **+7.69 %** en T=120): el acoplamiento con la longitud es estructural |
| T13b | SWIP-0001 | ✔ | impuesto por posición: las claves salen **−0.279** de la propia longitud antes, IC 95 % **[−0.361, −0.178]**, confundido ρ = **+0.075** — criterio re-expresado y **cumplido** |

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
| `granite3.1-dense:2b` | 16 | +8.4 % | +15.5 % | 38.8 | 56 % |
| `gemma2:2b` | 16 | +11.5 % | +15.7 % | 17.5 | 75 % |
| `qwen2.5:3b` | 16 | +13.4 % | +13.1 % | 37.3 | 56 % |
| `llama3.2:3b` | 16 | +14.3 % | +22.9 % | 38.3 | 75 % |
| `phi3.5:3.8b` | 16 | +26.5 % | +30.4 % | 16.1 | 88 % |

La distancia entre clases es grande y la varianza dentro de una clase es mayor.
Eso explica a la vez por qué la predicción por celda falla y por qué una
política por clase funciona: **+0.0 %** frente a **+14.8 %** fragmentando
siempre, sin necesitar la predicción que no existe.

## 4. Lo que no se puede afirmar, y por qué

El criterio de abandono **estaba sin medir y ahora es juzgable** — con un
instrumento nuevo, no con otra configuración de presupuesto. El impuesto
agregado está confundido con la longitud de salida **en las dos direcciones**
(presupuesto completo: el fragmentado escribe 1.39× el monolítico y puntúa
más; presupuesto repartido: 0.43× y puntúa menos; agregado **+11.17 %**, IC
95 % **[+4.80, +17.34]**, T09R — negado y no citado como criterio). Truncar
ambos brazos a un presupuesto de lectura fijo **T** tampoco funciona: el
impuesto cambia de signo con T (T13). Lo que resuelve el acoplamiento **por
construcción** es la **posición de primera mención** (T13b, SWIP-0001): la
primera aparición de cada clave, normalizada por la longitud del propio brazo.
Sobre las celdas con presupuesto igualado, el fragmentado saca las claves
**0.279 de su propia longitud antes**, IC 95 % **[0.178, 0.361]**, con el
confundido desaparecido (ρ = **+0.075**). El criterio, re-expresado como
«fragmentar no debe enterrar las claves», se **cumple**.

La causa está localizada en el código y corregida. La corrida que resuelve el
asunto es una sola orden:

```bash
python3 swarmbly_ref/benchmarks/run_benchmark.py --matched
```

Los campos `output_words` y `length_ratio` son ahora campos de primera clase del
registro, de modo que el confundido sea visible en cualquier análisis futuro sin
tener que re-derivarlo del texto.

## 4b. El corpus de la curva-L está admitido

El corpus candidato `prompts/lcurve_v2.json` (preguntas globales de aridad
≤3, generado por `make_corpus.py`) pasó su compuerta de admisión: todos los
chequeos mecánicos y el piso monolítico. Sobre la mitad dev (24 documentos),
el brazo monolítico despeja el piso de **0.50** con **llama3.2:3b al 61.1 %**
(44/72 preguntas globales; azar **0.182**). Las otras cuatro familias no lo
despejan (19.4–30.6 %), así que la campaña de la curva-L debe correrse con
llama3.2 o reportarse por familia. La corrida auditable es
`data/admission.json`.

La campaña ya corrió (llama3.2, cada celda declarada,
`data/lcurve_v2_runs.jsonl`): la curva es **monótona decreciente** — L=5:
**77.8 %**, L=10: **69.4 %**, L=20: **58.3 %**, L=40: **44.4 %** (36 preguntas
globales por L). El mecanismo es la fidelidad de extracción por fragmento, y
el brazo fragmentado con L pequeño gana al monolítico (**77.8 %** vs
**61.1 %**) — la primera victoria sin confundido de longitud en el eje de
solvabilidad.

## 5. Documentos relacionados

- `WHITEPAPER_V2_ES.md` §15.9 — el análisis razonado y sus consecuencias de diseño.
- `PREREGISTRATION_2026-09-25_interaction_ES.md` y
  `RESULTS_2026-09-25_interaction_ES.md` — la hipótesis que se retiró durante
  esta campaña, y el preregistro que lo hizo posible.
- `VALIDATION_STRATEGY_V2_ES.md` §11 — qué le pasa a la agenda tras ejecutarla.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Compañero en inglés:
`RESULTS_2026-09-25_refbench_EN.md`.*