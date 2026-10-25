---
status: current
lang: es
---
# El segmentador separa una pregunta de los datos que la responden

**Encontrado:** 4 de septiembre de 2026, en la primera instancia a la que se
apuntó el brazo oracle de V7.
**Clase:** una limitación arquitectónica, no un bug. Nada se comporta mal
respecto de su propio docstring. Lo que está mal es una afirmación construida
encima.
**Estado:** **reparado**, por decisión del autor, como una fusión de dos de las
tres opciones de §6 — enseñarle al segmentador la dependencia donde es
recuperable, y negarse a fragmentar donde no lo es. §9 registra qué cubre la
reparación, qué rechaza y la única tensión que no puede resolver.

---

## 1. Qué se midió

La clase `map` de `benchmark_v7` es la tarea más trivialmente particionable
disponible: cuatro totales independientes por sección, sin dependencia entre
secciones en ningún lado. Una instancia, ρ = 3.0, N = 4, contra un piso de
empaquetado de **1.62** — o sea muy por encima del piso, y *no* la condición
degenerada por debajo del piso que invalidó tres niveles de v3c.

El trabajador es un **trabajador cumplidor**: responde las afirmaciones que su
paquete nombra, correctamente, en el formato pedido, y no responde nada cuyos
hechos no le fueron dados. Eso elimina por construcción "el modelo no puede
hacer la tarea".

| brazo | exactitud | cobertura | sin respuesta posible |
|---|---|---|---|
| monolítico | **1.000** | 1.000 | 0.000 |
| oracle | **1.000** | 1.000 | 0.000 |
| **real** | — | **0.000** | **1.000** |

La tarea está bien. La partición está bien. **Ninguna afirmación del brazo real
se podía responder**, y aquí está el porqué — los cuatro paquetes efectivamente
despachados:

```
t0   all four QUESTIONS, and none of the data
       [c_s1] the total for Depot group 1  ... [c_s4] the total for Depot group 4
t1   the output-format directive, and section 1's rows
t2   sections 2 and 3's rows, and no question
t3   the tail of section 3, section 4's rows, and no question
```

`t0` es dueño de todas las afirmaciones y no contiene ningún hecho. A los tres
paquetes que tenían todos los datos no se les preguntó nada. Y `s3` queda
partido entre `t2` y `t3`, así que ni siquiera un paquete al que *sí* se le
hubiera pedido `c_s3` habría podido responderla.

## 2. El mecanismo, exactamente

`planner._segment` dice qué hace, y lo hace:

> Los prompts enumerados se parten por sus propios bullets; si no, las oraciones
> se empacan en `n_tasks` grupos de tokens aproximadamente iguales.

Dos pasos, ambos verificados:

1. `split_enumerated` devuelve `None` sobre este prompt. La lista de ítems está
   indentada bajo un preámbulo y no se reconoce como un lote enumerado.
2. El fallback es una partición **contigua y balanceada en tokens** sobre las
   oraciones.

Así que la descomposición la deciden **la posición y el conteo de tokens**. El
segmentador **no tiene representación alguna de la dependencia entre una
pregunta y el material que la responde**. Un corte contiguo a través de un
prompt que enuncia primero sus preguntas y después su material necesariamente
los separa.

## 3. Por qué seis versiones no lo vieron

Por el formato del corpus, no por el código.

Todo corpus que este proyecto ha corrido pone una pregunta y sus datos **en el
mismo ítem**:

```
[01] 21 crates, 16 units per crate, 80 removed
```

Una partición contigua los mantiene juntos — por accidente del formato. El
corpus `tables24` hace lo mismo, una fila por línea. `free_form` hace lo mismo.
La forma de grafo de hechos es el primer corpus donde las preguntas se enuncian
aparte del material, y es el primero que corta entre ellos.

**Ese accidente está haciendo trabajo estructural.** La arquitectura afirma que
fragmenta un problema; lo que la implementación puede fragmentar es un prompt
cuyas preguntas y datos están colocados juntos, ítem por ítem. Esa es una clase
mucho más estrecha, y excluye algunas de las formas reales más ordinarias: un
informe más un anexo, un conjunto de preguntas más un documento, una petición
más un adjunto.

## 4. Por qué el brazo oracle es la razón de que esto se encontrara en una sola mirada

Sin él, `real` en cobertura cero es indistinguible de otras cuatro cosas: un
modelo que no sabe sumar, un calificador que no sabe parsear, un corpus cuya
clave está mal, una violación del piso de empaquetado. Cada una le ha costado
días a este proyecto.

Con él, la lectura es una línea, y el runner la imprime:

> oracle 1.000 contra real 0.000: la partición es viable y la implementación
> pierde 100.0 puntos — planificación, empaquetado o ensamblaje

`unanswerable_rate` luego lo localiza más, y es **un número del empaquetador, no
del modelo**: una afirmación cuyo paquete no contenía los hechos que requiere no
podría haber sido respondida correctamente por ningún modelo. La distinción es
para lo que existe `Claim.requires`, y es lo que una clave de respuestas plana
nunca puede expresar.

`benchmark_v7/__init__` predijo esto, antes de que el brazo existiera:

> **El brazo oracle es el punto.** Todo fallo de empaquetado en el que este
> proyecto gastó semanas se habría leído como *oracle bien, real roto*, lo que
> localiza la falla en planificación, empaquetado o ensamblaje en una sola
> lectura.

Se leyó exactamente así, en la primera instancia.

## 5. Dos defectos menores encontrados en el camino, ambos corregidos

**`run_fragmented` no guardaba su propia salida.** `run_monolithic` siempre ha
llevado `_text`; el brazo fragmentado no. En un corpus de composición `_trace`
llevaba el texto, lo que ocultaba el hueco — y `_trace` existe solo cuando el
prompt tiene restricciones, así que en todo corpus de clave de respuestas y de
grafo de hechos **la salida del brazo fragmentado era irrecuperable a partir de
una fila completada**. Un calificador independiente habría visto un brazo y no
el otro, y habría calificado al brazo fragmentado como si no hubiera producido
nada. Esa es la forma de asimetría por la que este proyecto ha retirado
resultados dos veces, en un lugar donde nadie estaba mirando: no en la métrica,
en lo que la fila guarda. Corregido; `_text` se queda fuera de `CSV_COLUMNS`.

**Las instrucciones de V7 pedían ids que su propio evaluador no podía parsear.**
Las instrucciones decían *"Dé una línea por grupo como **[id de grupo]**
seguido del valor solo"*. Los ids de grupo en el material son `s1`, `s2` — los
escribe `Section.as_text`. Los ids de afirmación son `c_s1`, `c_s2`. Así que una
respuesta **perfectamente cumplidora** era `[s1] 440`, y `parse_claims` acepta
ids con prefijo `c_` y dígitos sueltos: `s1` no es ninguno de los dos. Todos los
brazos habrían obtenido cobertura cero por una razón que no tiene nada que ver
con la fragmentación.

Era invisible porque el test del parser le daba ids con prefijo `c_` a mano en
vez de la forma que el corpus pide. La reparación es `graph._asked`, que nombra
los ids en la instrucción, más un **round-trip sobre el corpus real** — la misma
reparación, por la misma razón, que
`test_every_answer_in_the_corpus_round_trips_through_every_label_style` en la
suite del propio harness. El espacio de nombres de las afirmaciones se mantiene
distinto del de las secciones, así que hacer eco de `[s1] Depot group 1` desde
el material sigue sin parsear como nada, y hay un test de control que lo dice.

Esa corrección tiene un segundo efecto que vale nombrar: como ahora los paquetes
llevan los ids de afirmación, un runner puede atribuir una afirmación al paquete
al que **se le pidió**. Sin eso, la localización de arriba no tiene a qué
atribuir.

## 6. Qué no se está afirmando aquí

- **No** que el planner esté roto. Hace lo que documenta.
- **No** una cifra sobre ningún modelo. Todo número de arriba viene de un
  trabajador cumplidor; el punto de ese trabajador es que no tiene ninguna
  capacidad que medir.
- **No** un resultado sobre prompts reales. El corpus de grafo de hechos es
  sintético, y `benchmark_v7/__init__` enuncia el límite antes del primer
  resultado: V7 puede establecer *que el protocolo no pierde información que se
  le dio*; no puede establecer *que el protocolo funciona sobre tus documentos*.
- **No** corregido *al momento en que esto se escribió*. Tres reparaciones eran
  visibles desde aquí y no son equivalentes — enseñarle al segmentador que una
  pregunta necesita su material; exigir que todo paquete lleve las preguntas y
  particionar solo los datos; o restringir el router a prompts cuyas preguntas y
  datos están colocados juntos y decirlo. Elegir entre ellas era una decisión de
  arquitectura y le correspondía al autor. **Desde entonces se tomó — una fusión
  de la primera y la tercera — y §9 registra qué se construyó.** Este párrafo
  queda como fue escrito para que la decisión se lea como una decisión y no como
  algo que la medición implicaba.

## 7. Dónde queda fijado

`tests/test_benchmark_v7_runner.py`:

- `test_the_segmenter_splits_the_questions_away_from_their_data` — el
  comportamiento, sobre la forma que lo produce. **Fija** en vez de aprobar; si
  empieza a fallar porque el segmentador aprendió sobre la dependencia, bórralo.
- `test_the_real_arm_is_starved_and_the_oracle_arm_is_not` — la localización,
  con una aserción de que ρ está por encima del piso para que el resultado no
  pueda reexplicarse como la condición por debajo del piso.
- `test_the_assembled_text_is_recoverable_from_a_fragmented_row`
- `test_a_fact_graph_prompt_names_every_claim_it_asks_for`, y
  `test_a_section_header_is_not_read_as_an_answer` como su control.
- `test_the_runner_is_outside_the_package_and_stays_there` — la frontera de
  ADR-001. El runner maneja el protocolo publicado y califica a través del
  evaluador independiente; vive en `scripts/` porque un runner dentro de
  `benchmark_v7/` no puede hacer lo primero sin romper lo segundo, y la
  reparación tentadora — ampliar la prohibición de imports — borraría el ADR.

## 8. Cómo reproducirlo

```bash
python scripts/run_benchmark_v7.py --seeds 4 --backend mock     # wiring only
python -m pytest tests/test_benchmark_v7_runner.py -q           # the finding
```

El backend mock no emite respuestas parseables por diseño, así que la corrida de
cableado reporta cobertura cero en todos los brazos y no mide nada. El
trabajador cumplidor vive en el archivo de test, donde corresponde que esté un
sustituto del comportamiento de un modelo.

---

## 9. La reparación, y exactamente qué no cubre

Decidida por el autor el 4 de septiembre: una **fusión de las opciones 1 y 3**,
de modo que el alcance se estreche solo donde la dependencia es genuinamente
irrecuperable y no en todos lados.

### La regla

`planner.reference_map` enlaza cada **pedido** con el **material** que nombra.

* Una línea etiquetada es un *pedido* cuando lleva a lo sumo
  `MAX_VALUES_IN_AN_ASK` valores numéricos, y *material* en caso contrario. Una
  unidad es una línea etiquetada más las líneas sin etiqueta debajo de ella, así
  que un encabezado de sección se cuenta junto con sus filas — que es lo que
  permite distinguir uno del otro: un encabezado solo lleva un valor, un
  encabezado con cuatro filas lleva cinco.
* Un pedido **refiere** a una unidad de material cuando comparte un token que
  aparece en **exactamente una** unidad de material. Unicidad, no longitud.

La primera formulación exigía dos palabras de contenido compartidas
consecutivas, con el razonamiento de que una sola palabra compartida es ruido.
Era el eje equivocado, y medirlo lo dijo dos veces: `depot group` coincidía con
las cuatro secciones, lo que volvía idénticos todos los conjuntos de referentes
y la partición inconstruible; y no coincidía nada en absoluto en la clase
`chain`, cuyas preguntas nombran un único nombre propio (*"el total acumulado
después de agregar Mombasa"*). Un token que está en exactamente una unidad es el
nombre de esa unidad, sea `mombasa` o `4`. Un mecanismo, sin umbrales que
ajustar.

### Qué cubre

| clase | antes | después |
|---|---|---|
| `map` | 4 preguntas en un paquete, los datos en los otros tres; **1.000 sin respuesta posible** | una pregunta por paquete con exactamente la sección que nombra; **0.000 sin respuesta posible, exactitud = oracle** |
| `reduce` | el mismo defecto | **rechazado** — toda afirmación necesita todos los hechos |
| `chain` | el mismo defecto | **rechazado** — varios pasos necesitan la misma sección |
| `compose` | el mismo defecto | **rechazado** — una afirmación es un agregado |

### Qué rechaza, y por qué rechazar es la respuesta

`plan` devuelve una **única tarea** cuando la forma está presente y el enlace no
es recuperable. Dos casos:

1. **Ningún pedido nombra nada.** Una pregunta agregada — *"el total sobre todos
   los grupos"* — necesita todo el material y no nombra nada de él.
2. **Dos pedidos nombran el mismo material.** No pueden contenerlo ambos sin que
   ese material se emita dos veces, y duplicar una unidad infla
   `sum(|task_i|)` por encima de `|P|` y sube el piso de ρ alcanzable.
   `_segment` siempre se ha negado a duplicar, por esa razón.

No se usa un mapa *parcial*. Una partición que mantuviera tres preguntas con sus
datos y dejara varada a la cuarta produciría una cifra con una afirmación
silenciosamente sin respuesta posible adentro, lo que es peor que ninguna cifra.

### La tensión que no puede resolver, dicha sin rodeos

**La partición oracle duplica.** `_oracle_partition` le entrega a cada
afirmación exactamente los hechos que requiere, y esos conjuntos se solapan
libremente. Así que la partición que es viable *en principio* es un
**recubrimiento**, no una partición — y ρ, definido como `sum(|K_i|)/|P|`, cobra
por cada token duplicado.

El argumento de ρ baja de la arquitectura y su propio oracle quedan entonces en
tensión directa, y ningún segmentador puede resolverla. Permitir la duplicación
compra las clases `chain`, `reduce` y `compose` al costo de un piso de ρ que
sube con el solapamiento; prohibirla significa que esas clases no son
fragmentables. Esa es la misma decisión de arquitectura, un nivel más abajo, y
ahora es el ítem abierto en `STATE_2026-09-04.md` §7 y no en este.

### Una fila rechazada no es una medición fragmentada

Esta es la mitad que con más probabilidad se entienda mal, y es la dirección que
importa. Un plan rechazado tiene el prompt entero en un solo paquete, así que la
fila etiquetada `fragmented` obtiene lo que sea que obtenga el brazo monolítico
— 1.000 con un trabajador cumplidor. Dejada en una cifra entre brazos se lee
como *fragmentar sale barato*, sobre un prompt que nunca se fragmentó. Esa es la
dirección equivocada, y es la dirección hacia la que se inclinaban los doce
defectos de instrumento de `REVISION_2026-08-12.md`.

Tres guardas, deliberadamente en tres niveles distintos:

* `row["plan_refused"]`, descartada por **`is_reachable`** — el mismo cuello de
  botella que una fila por debajo del piso, extendido en vez de duplicado,
  porque `rho_reachable` alguna vez se escribió en cada fila y lo leía una
  función de ocho.
* el invariante de deriva de ρ se **omite** en una fila rechazada. Un solo
  paquete tiene ρ cerca de 1 diga lo que diga el objetivo, así que el chequeo
  convertiría un rechazo deliberado en un crash y un operador leería el
  traceback como una falla del harness.
* el runner de V7 la archiva bajo **`real-refused`**, un nombre de brazo aparte.
  Un promedio sobre una etiqueta que mezcla celdas fragmentadas y no
  fragmentadas es la forma de todo defecto de agregación que este proyecto ha
  corregido — ρ agregado sobre N, N agregado sobre k, una tasa sin su
  denominador.

### La medición que dice que la reparación es segura

**456 particiones, seis corpus, N ∈ {2, 3, 4, 8}: cero se movieron.** Cero
planes existentes colapsaron, y el camino pregunta/material se dispara en **0 de
150** prompts existentes — que es también la respuesta a por qué seis versiones
nunca vieron el defecto.

Esa es la propiedad que importa más que la reparación misma. Toda cifra
publicada en este proyecto se midió sobre una partición; un cambio del
segmentador que reparticionara un prompt existente habría cambiado
silenciosamente de qué eran esas cifras, y una compuerta que rechazara uno
habría vaciado una celda que antes estaba llena. Ninguna de las dos aparece como
un error.

`test_no_existing_corpus_partition_moves` compara los seis corpus prompt por
prompt y N por N, afirma que todo prompt sigue siendo recuperable, y afirma el
conteo de segmentos — así que encoger silenciosamente la comparación no es la
manera fácil de hacerlo pasar.
`test_the_reference_path_fires_on_no_existing_corpus_prompt` falla en el momento
en que llega un corpus nuevo con esta forma, que es cuando el operador necesita
saberlo: antes de que se gaste una noche en ello.

Ambas mitades de la reparación se verificaron fallando contra el código
revertido — quitar el camino de referencia rompe los tests de `map`, quitar la
compuerta rompe los tests de rechazo.
