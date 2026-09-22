---
status: current
lang: es
---
# v0, v3c-ff, v3c-gt — 4–5 de septiembre de 2026

Tres niveles, unas once horas, todos completados. La procedencia está limpia en
los tres: `harness_validation_only: false`, `embeddings_degraded: false`, huella
de código `81e0215b…` en cada uno de ellos, y **cero filas excluidas por motivo
alguno** — ninguna celda por debajo del piso, por encima del techo, forzada por
encima del objetivo, ni rechazada. El trabajo de rejilla del 4 de septiembre se
sostiene.

Léase en el orden que prescribe el runbook; el orden es la razón por la que se
retiraron cuatro documentos.

| corrida | directorio |
|---|---|
| v0 | `results/v0-20260904-231812/{N2,N4,N8}` |
| v3c-ff | `results/v3c-ff-20260904-233926` |
| v3c-gt | `results/v3c-gt-20260904-234814` |

---

## 1. v0 no produjo veredicto, y nunca pudo haberlo producido

Las **cuarenta** entradas de `falsifiable_go_no_go` volvieron con `passed: null`,
`n_observations: 1`. La celda declarada es (categoría, ρ, N, k); el corpus de v0
contiene exactamente **un prompt por categoría**; el criterio necesita dos
clusters para formar un intervalo. Así que sobre este corpus el criterio no puede
dispararse — ni para esta rejilla, ni para ninguna rejilla, ni en una
re-ejecución.

Mientras tanto, el nivel imprimió, tres veces:

```
[superseded] maximum-statistic criterion: passes (20 passing cells) -- not a verdict.
             ... Read falsifiable_go_no_go in summary.json instead
```

Enviaba al lector a un bloque estructuralmente vacío mientras un estadístico que
*pasa con datos aleatorios* permanecía en pantalla diciendo "passes". Las dos
mitades son honestas por separado y el par es engañoso.

**Corregido:** `summarize` ahora emite `falsifiable_go_no_go_census`
(`cells` / `with_a_verdict` / `refused` / `max_observations_in_any_cell`) y la
CLI imprime, inmediatamente debajo de la línea superseded:

```
             AND IT IS EMPTY: 0 of 40 declared cells returned a verdict.
             This corpus holds ONE prompt per category ... THIS TIER PRODUCES
             CURVES, NOT A VERDICT
```

**v0 es un nivel de curvas.** Nada en él es un resultado declarado, y este
documento lo cita solo como descripción.

---

## 2. El hallazgo: el impuesto es función de N, no de ρ

Es la primera vez que los tres brazos corren sobre rejillas que están enteramente
dentro de sus ventanas de empaquetado, así que es la primera vez que las curvas
significan algo.

| brazo | ρ barrida | impuesto en cada ρ | rango | media |
|---|---|---|---|---|
| N=2 | 2.0 → 4.8 | +10.5 %, +7.3 %, −10.3 %, −4.3 %, −1.5 % | 0.208 | **+0.4 %** |
| N=4 | 3.0 → 6.6 | +2.0 %, +5.1 %, +3.8 %, −0.6 %, +0.4 % | 0.057 | **+2.2 %** |
| N=8 | 4.5 → 6.5 | +21.4 %, +25.3 %, +22.9 %, +16.2 %, +18.8 % | 0.091 | **+20.9 %** |

Barrer ρ a lo largo de **toda la ventana utilizable** de un brazo mueve el
impuesto en 0.06–0.21 y lo hace de forma no monótona — la firma del ruido, no de
una curva. Cambiar N lo mueve en **20.5 puntos**.

ρ no es la palanca. Esa es la respuesta a H1, y es una respuesta negativa para la
forma en que SPEC 11.5 plantea la pregunta.

Dos cosas la afinan:

* **El costo no es lineal en N.** N=2 → N=4 es +1.8 puntos; N=4 → N=8 es
  **+18.7**. En ρ = 4.8, el único punto de rejilla que dos brazos comparten, N=2
  marca −1.5 % y N=4 marca +3.8 % — una brecha de 5.3 puntos, cómodamente dentro
  de la dispersión propia de cada brazo. N=2 y N=4 no son distinguibles aquí.
  N=8 es distinto en especie.
* **El objetivo de SPEC 11.5 es inalcanzable, no meramente incumplido.** Pide
  ρ < 2.0. El brazo N=8 no puede empaquetarse por debajo de 4.45 sobre este
  corpus. Ningún barrido lo alcanza.

### Un defecto que esta corrida expuso, ya corregido

Los tres brazos **no compartían ningún punto de ρ**. N=8 barrió 5.0 donde N=2 y
N=4 barrieron 4.8, mientras el propio texto del nivel decía "comparar N a ρ fija
es honesto solo en 4.5 y 4.8" — 4.5 no estaba en ningún otro brazo y 4.8 no
estaba en N=8. La única comparación que el nivel le indicó al operador que
hiciera no podía hacerse con los datos.

Peor: una prueba afirmaba la frase **literalmente**, de modo que la afirmación
falsa quedó fijada en su lugar por la suite. Una cadena no es un hecho sobre la
rejilla.

N=8 ahora barre `4.5, 4.8, 5.5, 6.0, 6.5` — `check_grid` empaqueta 4.8 con
−0.5 % en el peor caso sobre los ocho prompts — y la prueba ahora intersecta las
tres rejillas en lugar de coincidir con una frase.

---

## 3. El acuerdo no predice la corrección. Dos corpus, una respuesta.

La pregunta que especifica la sección 11.4, formulada dos veces la misma noche,
con el veredicto proveniente de una clave de respuestas en lugar de un juez de
clase par.

| | v3c-gt | v3c-ff |
|---|---|---|
| ítems calificados | 465 de 526 vistos | 160 |
| exactitud | **0.695** | 0.688 |
| acuerdo medio | 0.978 | 0.935 |
| **AUC** | **0.532** | **0.547** |
| r de Pearson | 0.179 | 0.129 |

0.5 no es señal. Marcar los ítems de menor acuerdo a una tasa de marcado del
10 % atrapa 8 de 79 errores — **lift 1.009**, indistinguible de marcar al azar.
La tasa del 20 % marca 1.70 y la del 30 % marca 1.22, no monótonas sobre
26/52/78 ítems marcados, que es lo que parece el ruido.

Dentro de cada categoría, donde agrupar no puede fabricar una señal mezclando
ítems fáciles que a la vez concuerdan más y aciertan más a menudo:

| categoría | exactitud | acuerdo medio | AUC |
|---|---|---|---|
| arithmetic | 0.409 | 0.941 | 0.596 |
| date_arithmetic | 0.358 | 0.985 | 0.515 |
| field_extraction | 1.000 | 0.987 | — (sin varianza) |
| threshold_decision | 0.814 | 0.982 | 0.570 |
| unit_conversion | 0.857 | 0.990 | 0.479 |

La exactitud va de 0.36 a 1.00 mientras el acuerdo se mantiene en 0.94–0.99 en
todo el rango. El predictor es plano a lo largo de una variación de cuatro veces
en aquello que se supone que predice.

**Esto retira el mapa de confianza.** Es la quinta y la sexta medición, y las dos
primeras en que el instrumento era capaz de mostrar una señal de haberla habido
— el resultado del 14 de agosto era ininterpretable porque el juez aceptaba el
93.3 % de todo. Nótese que el *juez* lo volvió a hacer aquí: aceptación del
100.0 % sobre 340 unidades en v3c-gt y 367 en v3c-ff. La clave de respuestas es
la única razón por la que estas corridas dicen algo.

Salvedades que acompañan a la cifra: 112 de 643 unidades no llevaban etiqueta,
61 ítems eran ininteligibles y 27 repetían el prompt. Los denominadores son
sólidos; el cumplimiento de formato de los modelos no lo es.

---

## 4. k arregla la explosión de párrafos — y solo eso

El veredicto de +22.4 puntos de `comp-final` traía un límite declarado: el brazo
fragmentado escribió 7.96 párrafos contra los 2.0 del monolítico, de modo que
cada fragmento escribía una respuesta completa y el resultado medía la
implementación, no la fragmentación.

v3c-ff, con N=3 sobre la misma carga de composición, muestra lo que k le hace a
eso:

| condición | párrafos | puntuación de restricción (cruda) | puntuación de restricción (**comparable**) |
|---|---|---|---|
| monolítico | 2.00 | 1.000 | 1.000 |
| fragmentado k=1 | **7.40** | 0.633 | 0.864 |
| fragmentado k=3 | **2.00** | 0.711 | 0.786 |
| fragmentado k=5 | **2.00** | 0.756 | 0.857 |

El consenso **elimina por completo** la inflación de párrafos — 7.40 →
exactamente 2.00, igualando al monolítico. La puntuación cruda sube con k en
consecuencia (0.633 → 0.756).

Y la puntuación comparable, que excluye `paragraph_count` y
`words_per_paragraph` precisamente porque el ensamblador los impone, **no se
mueve**: 0.864, 0.786, 0.857 sobre cinco composiciones es plana.

Así que k repara las restricciones que impone el ensamblador y no hace nada por
el resto. Lo cual predice que **el titular de `comp-final` no mejoraría con
k=3**, dado que la parte que k arregla es la parte que
`constraint_score_comparable` ya excluye. Eso es barato de probar — `comp-dev`
con k=3 — y vale la pena probarlo antes de que alguien proponga el consenso como
respuesta a los 22.4 puntos.

v3c-gt apunta en la misma dirección desde el otro lado: el impuesto comparable
**sube** con k, +21.2 % → +37.4 % → +44.6 %. Más réplicas, peor compuesto.

`repeated_sentences_cross_task` fue **0 en todas las condiciones**. El fallo de
ensamblaje característico — dos trabajadores escribiendo la misma frase,
invisible para una puntuación de coherencia basada en transiciones porque cada
copia se lee bien — no ocurrió sobre este corpus. Un negativo limpio sobre
aquello que el nivel fue construido para detectar.

---

## 5. Un par de números mal etiquetados, en todos los niveles, durante dos semanas

Todos los niveles imprimían:

```
rho=2.5  BooookScore-like  +21.15%
         absolute difference  BooookScore-like  +0.4335   (denominator-free)
```

En v3c-gt **toda línea base monolítica era exactamente 1.000** — el caso en que
una diferencia relativa y una absoluta son aritméticamente el mismo número.
Diferían en 0.22.

La brecha no era el denominador. El titular relativo se computa sobre
`booook_comparable`; el absoluto se computaba sobre `booook_like_score`. Son
puntuaciones distintas, y el resumen las llamaba "la versión sin denominador de
la misma comparación".

La diferencia entre ambas son las clases ancladas a costuras e impuestas por el
ensamblador que `booook_comparable` existe para eliminar, porque un texto
monolítico no tiene costuras y no puede incurrir en ellas, y hay N−1 costuras —
así que incluirlas le cobra al brazo fragmentado **más cuanto más fragmentado
está**: 5.7 puntos con N=2 y 10.1 con N=8 en la corrida de tablas del 26 de
agosto.

La cifra absoluta reintroducía por lo tanto, bajo una etiqueta que prometía
neutralidad, exactamente el sesgo que la puntuación comparable se creó para
retirar.

**Corregido.** `abs_delta_booook` es ahora la puntuación comparable sin
denominador; `abs_delta_booook_full` conserva la cifra vieja bajo su propio
nombre e imprime solo donde discrepa, etiquetada como *no comparable entre
brazos*. Tres pruebas lo fijan, incluido el caso de línea base de 1.0 donde
ambas deben coincidir.

---

## Qué cambia esto

* **H1 queda respondida, en negativo.** ρ no es la palanca; N sí lo es, y el
  costo aparece entre N=4 y N=8. La arquitectura no puede mantener N y ρ
  independientes — las ventanas utilizables tienen 0.45 de ancho en su
  intersección.
* **El mapa de confianza queda retirado.** El acuerdo no predice la corrección,
  sobre dos corpus, con un veredicto mecánico.
* **El consenso no es la respuesta al costo de composición.** Arregla la parte
  que el titular ya excluye.
* **v0 es un nivel de curvas y ahora lo dice.**

## Qué sigue abierto — y qué se construyó para ello

Los dos seguimientos que este documento pedía fueron construidos, corridos y
escritos en **`docs/RESULTS_2026-09-05_oracle_and_k3.md`**. En resumen:
`comp-dev-k3` confirmó su predicción (+19.38 contra los +18.40 de k=1 — el
consenso no es una palanca), y `comp-oracle` se negó a descomponer porque su
política de asignación era la equivocada, lo que produjo un hallazgo más agudo
del que habría producido la descomposición. El oráculo tiene ahora cinco brazos
y vale la pena volver a correrlo.

```bash
bash scripts/run_ollama.sh comp-oracle    # ~1-2 h
bash scripts/run_ollama.sh comp-dev-k3    # ~1 h
```

**`comp-oracle`** es el brazo que puede cambiar la lectura de los 22.4 puntos.
Tres brazos sobre un mismo calificador mecánico: el monolítico, un oráculo cuya
asignación de restricciones es correcta por construcción, y el pipeline que se
entrega. Cada término requerido pertenece a exactamente un fragmento, y donde el
término es además `term_once` a los demás se les indica evitarlo — de modo que
los dos mecanismos que `comp-final` localizó (duplicación con N=3, omisión con
N=8) desaparecen por construcción.

Su `decomposition.reading` da una de dos respuestas opuestas, y ambas vale la
pena tenerlas: **ALLOCATION dominates** convierte los 22.4 puntos en un defecto
del planificador con un arreglo de planificador; **PARALLELISM dominates**
convierte esta carga en no fragmentable en lugar de mal fragmentada.

El oráculo es deliberadamente **paralelo** — ningún fragmento ve el texto de otro
— porque un oráculo secuencial recuperaría las restricciones de repetición
aboliendo aquello que está bajo prueba. `no_repeated_ngram` y
`no_repeated_sentence` son por lo tanto las clases que la asignación no puede
alcanzar, y lo que el oráculo pierde en ellas es el precio del paralelismo mismo.

La única comprobación que puede invalidar la corrida entera:
`by_arm.mean_paragraphs`. Si el oráculo sigue escribiendo siete párrafos, su
encargo no se está obedeciendo y nada por debajo de eso significa algo.

**`comp-dev-k3`** prueba directamente la predicción de §4, contra la estimación
dev de k=1 de +18.40, dev contra dev.

**La duplicación frente a ρ** no ha cambiado y sigue siendo una decisión de
arquitectura, no una corrida: la partición del oráculo es un recubrimiento, no
una partición, y ρ cobra por cada token duplicado.
