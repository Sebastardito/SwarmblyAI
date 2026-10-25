---
status: current
lang: es
---
# comp-oracle, cinco brazos — 5 de septiembre de 2026

`results/comp-oracle-20260905-112603`, digest del corpus `e9e382b9…`, doce
prompts de dev.

**La primera comprobación pasó:** los tres oráculos escribieron **2.00
párrafos**, contra los 2.00 del monolítico y los **8.92** del pipeline
desplegado. Los briefs se obedecieron, así que la ejecución es legible.

---

## La respuesta: paralelismo, por un factor de setenta

| brazo | puntuación de restricción (comparable) | párrafos |
|---|---|---|
| monolítico | **0.844** | 2.00 |
| oracle-exclusive | 0.571 | 2.00 |
| oracle-redundant | 0.586 | 2.00 |
| **oracle-redundant-dedup** | **0.652** | 2.00 |
| real (desplegado) | 0.649 | 8.92 |

Solo `oracle-redundant-dedup` es una **cota superior** de lo que puede lograr la
asignación — los otros dos puntúan por debajo del pipeline desplegado, así que
midieron sus propios briefs y no la asignación. Su descomposición:

| | |
|---|---|
| pérdida de extremo a extremo | **0.194** |
| paralelismo (monolítico → oráculo) | **0.192** |
| asignación (oráculo → real) | **0.003** |
| **porción recuperable por asignación** | **1.4 %** |

**El 98.6 % del costo de composición no es alcanzable por ningún cambio de
planificación.** Un asignador perfecto, más la imposición mecánica de la única
clase de restricción que puede mecanizarse, llega a 0.652 contra el 0.844 del
monolítico — todavía 19.2 puntos por debajo, y a la par del pipeline desplegado
sobre el que debía mejorar.

Esta es la respuesta sin la cual se publicó `comp-final`, y es la poco
halagadora. Los 22.4 puntos **no** son un defecto del planificador.

### Una regla que cambié después de ver los datos, y la auditoría de ese cambio

El titular solía estar anclado a la política **declarada primero** — exclusive —,
que en esta ejecución produjo «revisen los briefs del oráculo» mientras una
descomposición limpia estaba dos líneas más abajo.

La regla ahora se enuncia sobre el **instrumento**: un oráculo es una cota
superior, así que uno que puntúe por debajo del pipeline desplegado no ha medido
la asignación. El titular es la política declarada primero **entre las que pasan**
esa comprobación. Elegir entre instrumentos válidos por orden de declaración no
es elegir un resultado; elegir entre todos ellos por puntuación sí lo sería.

Una regla revisada después de ver los datos tiene que auditarse por la dirección
en la que mueve las cosas. Esta movió el titular de *«el oráculo está roto»* a
*«PARALLELISM dominates — esta carga de trabajo no es fragmentable»* — **en
dirección contraria** a la propia hipótesis del proyecto, no hacia ella.

---

## Dónde vive el residuo

El monolítico menos el oráculo del titular, en comprobaciones en lugar de puntos:

| clase | monolítico | oráculo dedup | perdidas |
|---|---|---|---|
| `must_mention` | 32/36 | 23/36 | **−9** |
| `no_repeated_ngram` | 11/12 | 4/12 | **−7** |
| `no_repeated_sentence` | 12/12 | 10/12 | −2 |
| `words_per_paragraph` | 12/12 | 10/12 | −2 *(impuesta por el ensamblador)* |
| `must_not_mention` | 12/12 | 12/12 | 0 |
| `paragraph_count` | 12/12 | 12/12 | 0 *(impuesta por el ensamblador)* |
| **`term_once`** | 13/24 | **14/24** | **+1** |

Dos clases lo cargan.

**`no_repeated_ngram`, −7 de 12.** Irreducible. Un 8-grama repetido es una
propiedad de un *par* de fragmentos; ningún worker paralelo puede revisar un par;
todo brazo que no ve el texto del otro aterriza en 4–5 de 12 mientras el
monolítico se queda en 11. Este es el precio del paralelismo, con nombre y
apellido.

**`must_mention`, −9 de 36.** Esta *no* es cuestión de asignación, y esa es la
sorpresa. Decirle a **cada** fragmento que mencione **cada** término llega igual
a solo 25/36 (23 después de las eliminaciones del dedup) contra el 32/36 del
monolítico. Un fragmento que escribe 60–140 palabras sobre lo que da un párrafo
de un tema tiene menos espacio para encajar tres o cuatro términos requeridos que
un escritor con las 120–280 palabras completas. Es un efecto de **tamaño de
fragmento**.

Lo cual aterriza exactamente donde aterrizó `v0` desde un instrumento
completamente distinto: el impuesto es una función de N, N=2 y N=4 no son
distinguibles, y N=8 es distinto en especie. Menos fragmentos, más grandes. Dos
instrumentos, una conclusión.

---

## Lo único que funcionó, y funcionó mejor que el techo

| brazo | `term_once` |
|---|---|
| monolítico | 13/24 |
| pipeline desplegado | 6/24 |
| oráculo, briefs redundantes | 6/24 |
| **oráculo, redundante + dedup mecánico** | **14/24** |

Mover «exactamente una vez» del lado de la generación al ensamblador lo llevó de
6/24 a 14/24 — **por encima del brazo sin fragmentar**. Costó dos `must_mention`
y dos `words_per_paragraph`, ambas por oraciones eliminadas que cargaban algo
más. Ocho ganadas, cuatro perdidas, dos de esas cuatro excluidas del titular de
todos modos.

Es la misma forma de restricción que `paragraph_count` y `words_per_paragraph`,
que el ensamblador siempre ha impuesto de esta manera: una propiedad del texto
terminado, verificable contando. Solo la historia la puso del lado de la
generación.

**Esto es una recomendación de despliegue**, y ahora existe como tal:
`--enforce-term-once`, por defecto **apagado**, con `swarmbly_v0.constraints.
enforce_term_once` como la única implementación que llaman tanto el oráculo como
el ensamblador — asegurada por un test, porque dos implementaciones de un mismo
comportamiento derivan y la deriva se le atribuye al brazo que la nota segundo.

La predicción está prerregistrada en `docs/PREREGISTRATION_term_once.md` y el
nivel es `comp-dev-once`.

---

## Dos cosas que vale la pena conservar y que no son el titular

**La redundancia del pipeline desplegado es estructural, y les gana a los dos
oráculos en `must_mention`.** 21/24 en el bucket de also-once, contra el 17/24
del oráculo redundante y el 11/24 del oráculo exclusivo. Cada fragmento ve el
prompt completo, así que varios mencionan el término. Cualquiera que «arreglara»
el planificador para asignar los términos correctamente habría empeorado las
cosas — ahora hay un número para eso, en ambas direcciones.

**La mitad del límite declarado de `comp-final` queda eliminada.** Los 7.96
párrafos son un **defecto de brief**: decirle a un fragmento «escribe el párrafo
1 de 2 y nada más» produce exactamente 2.00, en los tres brazos oracle, sobre los
doce prompts. Eso es corregible en el planificador desplegado y vale la pena
hacerlo al margen del resto — aunque nótese que vale *menos puntos de los que
parece*, ya que `paragraph_count` y `words_per_paragraph` están excluidas de la
puntuación comparable precisamente porque el ensamblador ya se ocupa de ellas.

---

## Qué cambia esto

* **El costo de composición es un hecho sobre la prosa paralela, no sobre este
  planificador.** El 98.6 % sobrevive a una asignación perfecta. Dejen de
  buscarlo en el planificador.
* **`term_once` le pertenece al ensamblador.** Medido en 14/24 contra 6/24, por
  encima del techo sin fragmentar, y ahora prerregistrado.
* **La palanca, si hay alguna, es el tamaño de fragmento.** Las dos clases que
  sobreviven empeoran a medida que los fragmentos se achican, y `v0` dice lo
  mismo desde el otro extremo. N=2 y N=4 no son distinguibles; N=8 es donde
  aparece el costo.
* **El planificador debería conservar su redundancia accidental.**

## Límites honestos

Doce prompts de dev, sin intervalo, sin veredicto — esto descompone un número que
tiene su propio intervalo, no carga uno. El brazo dedup en 0.652 contra el 0.649
de real es una diferencia de 0.3 puntos sobre doce prompts y no significa nada
por sí sola; lo que sí significa algo es la tabla **por clase** que está debajo,
donde los mecanismos tienen denominadores.

Y todo esto está medido con modelos 3B. Un modelo más grande que siguiera
«menciona este término» de manera confiable movería `must_mention` y dejaría
`no_repeated_ngram` exactamente donde está — lo que haría la porción del
paralelismo *mayor*, no menor.

## Siguiente

```bash
bash scripts/run_ollama.sh comp-dev-once     # ~1 h, preregistered
```
