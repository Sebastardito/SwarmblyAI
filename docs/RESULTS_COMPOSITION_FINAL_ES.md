---
status: superseded
superseded_by: RESULTS_2026-09-05_final_dedup.md
reason: >
  Su +22.40 se midió antes de que se impusiera term_once en el ensamblador.
  Sobre la misma partición con la imposición activa la cifra es +7.64, y
  sobre un corpus que nadie había visto es -0.35.
lang: es
---
# El criterio de composición: NOT MET por 23.5 puntos, y el impuesto no pudo verlo

**Corrida:** `results/comp-final-20260904-123403`. `prompts/composition.json`,
partición `final` — 24 prompts, ρ = 4.0, N ∈ {3, 8}, k = 1, cinco familias de
modelo. 72 filas.

> **Procedencia.** `harness_validation_only: false`, `embeddings_degraded: false`,
> τ_sem 0.585 ajustada sobre la mitad dev, semilla 0,
> **`rows_excluded_below_floor: 0`**, ρ alcanzada 3.97–4.03 frente a 4.00,
> `rho_fidelity.within_tolerance: true`. Digest del corpus `e9e382b9…`, huella de
> código `e3d0a0dc…` — **el mismo código que ajustó τ**, comprobado por
> `assert_same_code_as_dev` antes de que arrancara la corrida.

Este es el primer resultado de este proyecto producido por el aparato completo:
una celda nombrada en un documento escrito antes de la corrida, un umbral fijado
en un valor que los datos piloto no cumplían, un control obligado a fallar, una
partición de corpus congelada, un piso de clusters y un veredicto sobre el límite
superior. Nada de lo que sigue se eligió después de ver datos.

---

## 1. El veredicto

> **La composición con ρ = 4.0, N = 3, k = 1 cuesta menos de 5 puntos de
> satisfacción de restricciones contra su línea base monolítica.**

| | |
|---|---|
| monolítico | **0.873** (8 de 24 en 1.000) |
| fragmentado N=3 | **0.649** |
| **diferencia pareada** | **+22.40 puntos** (mediana +22.50) |
| IC del 95 %, agrupado por prompt | **[+16.15; +28.51]** |
| n_prompts | **24** (piso 20) |
| **VEREDICTO** | **NOT MET — se pasa por 23.51 puntos en el límite superior** |

**El control falla como se le exigía.** N = 8 en la misma grilla: **+70.56
puntos**, IC [+64.58; +75.62]. El instrumento separa los brazos por un factor de
3.2, y un control que hubiera cumplido habría dejado ambos números sin valor.

**Diecinueve de 24 prompts perdieron terreno. Cinco no perdieron exactamente
nada. Ninguno ganó.** `n_at_or_below_zero` es 5 y cada uno de esos es exactamente
0.000 — así que sobre este corpus fragmentar una composición nunca la mejoró.

La mitad dev, corrida primero y sobre prompts distintos, situó la misma celda en
**+18.40 puntos** con un IC de [+9.79; +29.72]. La estimación final queda dentro
de ese intervalo. La mitad reservada no produjo ninguna sorpresa.

## 2. El hallazgo que importa más que el veredicto

Los mismos 24 textos, puntuados por el instrumento alrededor del cual se ha
construido este proyecto:

| | celda declarada (N=3) | control (N=8) |
|---|---|---|
| **impuesto de coherencia** | **+0.14 %** | +20.45 % |
| **puntuación de restricciones** | **+22.40 puntos** | +70.56 puntos |

**El impuesto de coherencia tipo BooookScore marca +0.14 % en la celda donde un
conteo mecánico de esas mismas cadenas de texto encuentra 22.4 puntos perdidos.**
Dieciséis de los 24 prompts marcan **exactamente +0.000**. Uno marca −0.448.

La sección 4 de `RESULTS_V3C_FF_COMPOSITION.md` dijo esto sobre tres prompts,
como descripción. Ahora es una medición preregistrada sobre 24, con un control, y
replica.

**Por qué el impuesto no puede verlo aquí.** Diecisiete de las 24 líneas base
monolíticas de BooookScore son exactamente **1.000**. Un impuesto definido como
*(monolítico − fragmentado) / monolítico* contra un denominador clavado en el
techo solo puede leer ≥ 0 y casi no tiene resolución. El corpus se construyó con
tres tiers de dificultad para darle a la **puntuación de restricciones** espacio
para moverse, y funcionó — esa línea base es 0.873, no 1.000. Nada se diseñó para
darle espacio a la **métrica de coherencia**, y se saturó de todos modos.

La línea de consola con la que hay que tener cuidado es la que marca `+10.29 %`.
Ese es el impuesto **agrupado sobre N = 3 y N = 8** — el brazo bajo prueba
promediado con el control que está obligado a fallar. Por brazo es +0.14 % y
+20.45 %, y la media de esos dos no pertenece a ninguno.

## 3. Qué se rompió realmente

Contado a partir del texto. Sin juez, sin ningún modelo en el veredicto.

| comprobación fallida | monolítico | N = 3 | N = 8 |
|---|---|---|---|
| `term_once` | 16 | **34** | 42 |
| `must_mention` | 4 | 9 | **64** |
| `no_repeated_ngram` | 1 | 1 | 1 |
| `no_repeated_sentence` | 0 | 1 | 1 |
| **fallos totales** | 21 | 47 | 110 |

Dos familias, y son opuestas:

* La **duplicación** domina con N = 3. `term_once` falla porque un término que
  debe aparecer una vez aparece una vez *por fragmento*.
* La **omisión** toma el control con N = 8. Los fallos de `must_mention` pasan de
  9 a 64: con ocho fragmentos escribiendo cada uno una rebanada, los términos
  requeridos dejan de quedar cubiertos del todo.

`repeated_sentences_cross_task` — dos trabajadores distintos escribiendo la misma
frase — es **0 en monolítico, 12 con N=3, 50 con N=8**. Esto **contradice** la
corrida de respuesta libre, que reportó 0 en todas partes y concluyó que la
duplicación era más fina que el nivel de frase. Sobre este corpus no lo es:
frases enteras están siendo escritas dos veces por trabajadores distintos. El
refinamiento anterior era cierto de aquel corpus, no de la composición de prosa
en general, y queda corregido aquí.

### El costo cae donde había algo que perder

| línea base monolítica | n | pérdida media |
|---|---|---|
| **1.000** | 8 | **+0.360** |
| 0.80 – 0.99 | 11 | +0.206 |
| **< 0.80** | 5 | **+0.045** |

Correlación entre línea base y pérdida: **r = +0.705**. Parte de eso es mecánico
— una línea base de 0.70 topa la pérdida en 0.70 — pero en 1.000 la pérdida media
es 0.360, ni cerca de su tope, así que el patrón no es un artefacto del techo.
Donde el brazo monolítico ya estaba fallando comprobaciones, fragmentar no costó
casi nada extra. Los cinco prompts que perdieron exactamente cero tienen todos
líneas base entre 0.700 y 0.833.

## 4. La decisión que achicó el resultado, y por qué fue correcta

`constraint_score_comparable` excluye `paragraph_count` y `words_per_paragraph`,
que el ensamblador satisface para un brazo y que el modelo debe ganarse solo en
el otro. Las puntuaciones crudas:

| brazo | cruda | comparable |
|---|---|---|
| monolítico | 0.898 | 0.873 |
| fragmentado N=3 | **0.514** | **0.649** |

Sobre la puntuación cruda la brecha es de **38.4 puntos**. Sobre la puntuación
comparable entre brazos es de **22.4**. Excluir las dos comprobaciones impuestas
por el ensamblador **recortó el efecto medido casi a la mitad, en la dirección
que favorece a la hipótesis bajo prueba** — y aun así falla por 23.5 puntos en el
límite superior.

Vale la pena decir esto con todas las letras porque todos los defectos de
instrumento que este proyecto encontró antes de agosto se inclinaban en la
dirección contraria.

## 5. El límite de este resultado, y es un límite real

**`mean_paragraphs`: monolítico 2.0, fragmentado N=3 = 7.96, N=8 = 14.13.**

Todos los prompts dicen *"Write exactly two paragraphs."* El brazo monolítico
escribe exactamente dos. El brazo fragmentado escribe **ocho**, y con N = 8
escribe **catorce**. Cada fragmento está produciendo una respuesta completa y de
largo entero en lugar de una rebanada de una, y el ensamblador las concatena.

Eso no es un detalle. Es la mayor parte del mecanismo detrás de los 22.4 puntos:
un término que debe aparecer una vez aparece tres veces **porque tres
trabajadores escribieron cada uno una composición entera**. Así que el enunciado
honesto de lo que se midió es más estrecho que "fragmentar prosa cuesta 22.4
puntos":

> **Esta implementación, fragmentando en tres una composición de dos párrafos con
> ρ = 4.0, pierde 22.4 puntos de satisfacción de restricciones contra su propia
> línea base monolítica.**

Es una medición de extremo a extremo del pipeline entregado, que es exactamente
lo que declaró el criterio. **No** es evidencia de que partir prosa sea
intrínsecamente caro, porque a los fragmentos no se les dio un alcance que
pudieran respetar.

**Lo que separa esas dos lecturas es un brazo oráculo, y la composición no tiene
uno.** `benchmark_v7` tiene uno para tareas de grafo de hechos y localizó una
falla en una sola lectura el día en que se construyó. Un brazo oráculo aquí — a
cada fragmento se le dice explícitamente qué párrafo, qué presupuesto de palabras
y qué términos requeridos son responsabilidad *suya* — diría si 22.4 puntos son
el costo de la división o el costo de un contrato que no divide las restricciones
de la tarea. Esa es la siguiente medición, y es barata.

Dos cosas que **no** están mal en esta corrida, comprobadas en lugar de
supuestas: ρ estuvo dentro de tolerancia en todas las celdas (3.97–4.03 frente a
4.00), y ninguna fila se descartó por debajo del piso de empaquetado.

## 6. Qué zanja esto

**Zanjado.** El criterio declarado se ha puesto a prueba y ha fallado, sobre un
corpus partido antes de la corrida, con un control que falló como se le exigía y
un intervalo que no se acerca a 11 puntos del umbral en su límite inferior. La
afirmación cuantitativa central del proyecto sobre la composición de prosa, tal
como la realiza esta implementación, queda refutada en lugar de sin sustento.

**Zanjado, y más grande.** El impuesto de coherencia no es un instrumento
utilizable para esta carga de trabajo. Marca +0.14 % donde un conteo mecánico
encuentra 22.4 puntos, sobre las mismas cadenas de texto, al nivel de
fragmentación que la arquitectura propone de verdad. Toda cifra que este proyecto
ha producido sobre composición —retirada o en pie— se midió con él.

**Abierto.** Si los 22.4 puntos son división o contrato. La §5 dice cómo
averiguarlo.

**Sin afectar.** El veredicto de `tables-final` sobre `table_summary` (+2.30 %,
IC [−2.05 %; +7.49 %], NOT MET) se sostiene; es un corpus distinto, una métrica
distinta y una celda distinta.
