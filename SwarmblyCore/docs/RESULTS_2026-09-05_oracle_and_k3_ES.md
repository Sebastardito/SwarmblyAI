---
status: current
lang: es
---
# comp-oracle y comp-dev-k3 — 5 de septiembre de 2026

Dos corridas, ambas cortas, ambas probando algo nombrado antes de que empezara.
Una confirmó su predicción. La otra se negó a responder la pregunta para la que
fue construida, porque el instrumento estaba equivocado — y la forma en que
estaba equivocado resultó ser el resultado más interesante.

| corrida | directorio |
|---|---|
| comp-oracle | `results/comp-oracle-20260905-103954` |
| comp-dev-k3 | `results/comp-dev-k3-20260905-104132` |

Huella del corpus verificada en ambas: `e9e382b9…`.

---

## 1. comp-dev-k3 — la predicción se sostiene

> **Declarado antes de la corrida:** el titular de `comp-final` **no** mejora
> con k=3.

| | diferencia pareada | IC 95% | n |
|---|---|---|---|
| k=1 dev (4 sept) | **+18.40 puntos** | [+9.79, +29.72] | 12 |
| **k=3 dev (5 sept)** | **+19.38 puntos** | [+11.18, +27.36] | 12 |

Mediana +18.33. El control en N=8 lee +44.65 y falla como se requiere. Ninguna
imprime un veredicto — 12 prompts contra un piso de 20, por diseño.

**El consenso no es la respuesta al costo de composición.** k=3 deja el titular
donde lo dejó k=1, y si acaso un punto peor. El razonamiento que lo predijo se
sostiene: k repara `paragraph_count` y `words_per_paragraph`, y
`constraint_score_comparable` está definido excluyendo exactamente esos.

Dos cosas que vale la pena registrar de la misma corrida:

* **El impuesto de coherencia leyó +4.07%** en textos donde el conteo mecánico
  encuentra 19.4 puntos perdidos. Tercera confirmación independiente de que el
  impuesto es el instrumento equivocado para la prosa.
* **La división `_full`/`comparable` se imprimió correctamente en el campo.** La
  línea nueva leyó `on the FULL score +0.1304 (seams and assembler-enforced classes included — not comparable across arms)` junto a `+0.0407`. Antes de la
  corrección de ayer esos dos habrían aparecido como "relativo" y "absoluto" de
  la misma cosa, separados por un factor de tres.
* La concordancia media cayó a **0.735** en composiciones contra 0.978 en
  respuestas de ground-truth — las réplicas en prosa difieren genuinamente, así
  que el problema de saturación es una propiedad de las respuestas fácticas
  cortas, y no de la maquinaria de concordancia. El juez aún aceptó el
  **100.0%** de 720 unidades.

---

## 2. comp-oracle — el oráculo puntuó por debajo de aquello que medía

| brazo | puntaje de restricción (comparable) | párrafos |
|---|---|---|
| monolítico | **0.844** | 2.00 |
| oráculo (asignación exclusiva) | **0.571** | 2.00 |
| real (pipeline desplegado) | **0.649** | 8.92 |

El guardia de descomposición se negó a atribuir la pérdida y nombró los briefs
del oráculo como aquello que había que revisar. Tenía razón, y ese guardia se
escribió el día anterior precisamente para esta forma de resultado.

**La primera verificación pasó, y importa:** el oráculo escribió **2.00
párrafos** contra los 2.00 de monolítico. El brief fue obedecido. Así que la
mitad del límite declarado de `comp-final` queda ahora respondida — decirle a un
fragmento "escribe el párrafo 1 de 2 y nada más" funciona, y los 7.96 párrafos
que produce el pipeline desplegado son un defecto de brief, no un hecho sobre la
fragmentación. El brazo real sigue escribiendo **8.92**.

### Todo el colapso está en un solo bucket

Dividiendo `must_mention` según si el término está **también** sujeto a
`term_once`:

| bucket | monolítico | oráculo | real |
|---|---|---|---|
| el término es **también** `term_once` | 21/24 (0.875) | **11/24 (0.458)** | 21/24 (0.875) |
| el término **no** es `term_once` | 11/12 (0.917) | 8/12 (0.667) | 8/12 (0.667) |

En los términos que la exclusividad no toca, **el oráculo y el pipeline
desplegado son idénticos.** En los términos que prohíbe a todo no-dueño, el
oráculo cae a la mitad.

Agrupado, esto se lee como `must_mention` 19/36 del oráculo contra 29/36 del
real, lo que parece un oráculo peor. Dividido, es un diagnóstico: la cláusula de
exclusividad convierte un término con N oportunidades en un término con
**una**, y un dueño 3B cumple cerca de la mitad de las veces.

Y sí compró aquello para lo que existía — `term_once` **9/24** contra **6/24**
del real. Tres restricciones satisfechas, por diez perdidas. Un mal intercambio,
cableado como regla.

---

## 3. El hallazgo que produjo en su lugar

**Un término que debe APARECER y debe aparecer EXACTAMENTE UNA VEZ es una
conjunción que los trabajadores paralelos no pueden satisfacer a ciegas.**

| estrategia | `must_mention` | `term_once` |
|---|---|---|
| redundancia (lo que el pipeline desplegado hace por accidente) | 21/24 | 6/24 |
| exclusividad (lo que el oráculo hizo a propósito) | 11/24 | 9/24 |
| **un solo escritor que puede ver el texto entero** | **21/24** | **13/24** |

La redundancia hace que el término aparezca y garantiza que aparezca dos veces.
La exclusividad hace que aparezca una vez y a menudo que no aparezca en
absoluto. Monolítico satisface ambas, porque la información que le falta a cada
trabajador paralelo es *la salida del otro trabajador* — y ningún esquema de
asignación sobre fragmentos paralelos puede suministrarla.

Esta es una afirmación más fuerte y más específica que "la fragmentación cuesta
22 puntos". Nombra una clase de restricción — global, exactamente-una-vez — y
dice por qué la fragmentación paralela no puede satisfacerla, de un modo que es
independiente de la calidad de esta implementación.

Nótese que el pipeline desplegado cae del lado de la redundancia **por
accidente**: cada fragmento ve el prompt entero, así que varios mencionan el
término. Ese accidente es estructural. Cualquiera que "arreglara" el planner
para asignar los términos correctamente habría empeorado las cosas, y ahora hay
una medición que lo dice.

### Y el costo del paralelismo, medido limpiamente

`no_repeated_ngram`: monolítico **11/12**, oráculo **5/12**, real **4/12**.

Este es el único número de la corrida que significa exactamente lo que fue
diseñado para significar. La asignación nunca iba a ayudar — una frase repetida
es una propiedad de un *par* de fragmentos y ningún trabajador paralelo puede
revisar un par — y no ayudó. Seis de doce perdidos solo por el paralelismo, con
una asignación perfecta.

---

## 4. Lo que se construyó en respuesta

La política de asignación es ahora un **parámetro con ambas mitades medidas**, y
no una regla. Cinco brazos:

| brazo | qué hace |
|---|---|
| `monolithic` | el techo |
| `oracle-exclusive` | un dueño por término, prohibido a los demás |
| `oracle-redundant` | cada fragmento obligado a mencionar cada término |
| `oracle-redundant-dedup` | el **texto** del brazo redundante, con `term_once` impuesto mecánicamente en el ensamblaje |
| `real` | el pipeline desplegado |

`oracle-redundant-dedup` es la propuesta que produjo el intercambio, y es un
cambio de **ensamblaje** más que de planificación. `paragraph_count` y
`words_per_paragraph` ya los satisface mecánicamente el assembler en lugar de
pedírselo amablemente a un modelo; `term_once` es la misma forma de restricción
— una propiedad del texto terminado, verificable contando — y solo la historia
la pone del lado de la generación.

El dedup conserva la primera oración que lleva cada término-una-vez y descarta
el resto. Oraciones enteras, porque quitar un sintagma nominal deja una oración
que ya no parsea y este paso no tiene ningún modelo dentro. El costo es que una
oración borrada puede llevar otro término requerido, y por eso
`sentences_removed` viaja junto al puntaje en lugar de darse por supuesto.

El brazo dedup reutiliza el **texto** del brazo redundante en lugar de generar
otra vez, así que la comparación entre ambos es el paso de ensamblaje solo y no
dos muestras de un modelo.

**Tres oráculos significan tres oportunidades de elegir un ganador después de
los hechos.** Así que cada uno recibe su propia descomposición, reportada lado a
lado y nombrada, y el titular se queda en la política declarada primero — la
exclusiva, la que usó esta corrida. Elegir la política de mejor puntaje después
de ver los puntajes es el defecto que `falsifiable_go_no_go` existe para
prevenir.

La división de `must_mention` ahora se **calcula**, no se anota. Era invisible
en la media, y una media que oculta su propio diagnóstico es justo lo que este
proyecto corrige una y otra vez.

---

## Lo que esto cambia

* **El consenso no es una palanca sobre la composición.** Medido, predicho de
  antemano, confirmado.
* **El límite declarado de `comp-final` queda removido a la mitad.** La
  inflación de párrafos es un defecto de brief y el oráculo no la reproduce. La
  mitad restante — cuánto de los 22.4 puntos sobrevive a una asignación
  correcta — sigue abierta, porque la primera asignación que se probó fue la
  equivocada.
* **El planner no debe ser "arreglado" para asignar los términos de forma
  exclusiva.** Costaría más de lo que compra, y ahora hay un número para ello.
* **Las restricciones globales de exactamente-una-vez le pertenecen al
  assembler**, junto a las dos que ya viven ahí. `oracle-redundant-dedup` lo
  prueba en cerca de una hora.

## Siguiente

```bash
bash scripts/run_ollama.sh comp-oracle    # ~2-3 h, five arms now
```

Léase en este orden: `by_arm.mean_paragraphs` (la corrida es nula si los
oráculos no están en 2.0), luego `must_mention_split`, luego
`by_constraint_kind`, luego `decomposition_by_policy`.

El resultado que más importaría: **`oracle-redundant-dedup` igual o por encima
de monolítico en `term_once` manteniendo 21/24 en `must_mention`.** Eso
convertiría la clase exactamente-una-vez en un problema del assembler con una
respuesta resuelta, y le quitaría un mordisco real a los 22.4 puntos.
