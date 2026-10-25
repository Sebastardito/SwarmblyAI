---
status: withdrawn
reason: >
  Todas las cifras se produjeron bajo una asimetría entre brazos en el
  ESTÍMULO y no en la métrica: una sola pista secuencial en la instrucción
  compartida planificó los 15 prompts como cadenas de cuatro niveles.
lang: es
---
# V3c contra ground truth — el mapa de confianza falla, y esta corrida dice por qué

> # ⚠ RETIRADO — 4 de septiembre de 2026
>
> **Todas las cifras de este documento se produjeron bajo una asimetría entre
> brazos en el ESTÍMULO, no en la métrica. No se cite ningún número de él, en
> ninguna dirección.**
>
> Los 15 prompts de `ground_truth.json` terminan con: *"Begin the line with the
> item number in square brackets, exactly as given, **then** a single space,
> **then** the value."* El `_SEQUENTIAL_CUES` del router coincide con `\bthen\b`.
> Una sola pista franquea la puerta, así que **todos los prompts se planificaron
> como cadenas de cuatro niveles** — sobre un corpus en el que cada prompt dice,
> en esa misma frase, *"Items are independent: the answer to one must not depend
> on the answer to any other."*
>
> La consecuencia: **42 de 60 paquetes de fragmento llevaban las LÍNEAS DE
> RESPUESTA de otro paquete** — `- t0: [01] 576` — justo encima de un bloque de
> tarea que decía *"Answer only the items listed here."* El prompt monolítico no
> llevaba ninguna.
>
> **Qué invalida esto, y es más que las comparaciones entre brazos.**
>
> - Todas las cifras de fragmentado frente a monolítico de aquí. A los dos brazos
>   se les despacharon preguntas distintas.
> - **También la calibración, y en una dirección que va en contra de la propia
>   conclusión de este documento.** Con k > 1 cada réplica de una tarea recibe el
>   *mismo* paquete, así que un bloque predecesor compartido les da algo en qué
>   converger. El acuerdo medio de 0.966 puede estar inflado por el defecto. Si lo
>   está, el veredicto "el predictor no tiene varianza, AUC 0.525, el mapa queda
>   retirado" descansa sobre una varianza que fue suprimida artificialmente — así
>   que **el hallazgo central de este documento no es seguro en ninguna de las dos
>   direcciones.**
> - La afirmación de mecanismo de la §2 — cinco familias que coinciden casi
>   siempre, y que se equivocan el 29 % de las veces donde coinciden — es la parte
>   más expuesta a esto, porque es una afirmación *sobre la distribución del
>   acuerdo*.
>
> **Qué sobrevive.** Nada sobre el acuerdo. La aritmética de atrición de ítems de
> la §4 queda explicada por este defecto en lugar de invalidada por él: los ítems
> "faltantes" eran reformulaciones del bloque predecesor, descartadas
> correctamente por `task_item_scope`, que es la razón por la que se recuperaban
> con k.
>
> Corregido en `planner.ordering_text()` y `packing.answers_by_item_label()`;
> después de la corrección 0 de 15 prompts se planifican como cadenas y los
> prompts `chain_*` genuinos de `complex.json` siguen haciéndolo. **Este tier
> debe volver a ejecutarse antes de usar cualquier cifra suya.** Véase
> `docs/INCIDENT_2026-09-04_chain_misplan.md`.


**Corrida:** `results/v3c-gt-20260903-201624`. 15 prompts × 150 ítems,
`prompts/ground_truth.json`, ρ = 2.5, N = 4, k ∈ {1, 3, 5}, cinco familias de
modelo distintas. Calificados mecánicamente contra una clave de respuestas por
`swarmbly_v0.grading` — **ningún modelo en el veredicto**. 60 filas.

> **Procedencia.** `harness_validation_only: false`, `embeddings_degraded: false`,
> τ_sem 0.765 ajustada sobre 180 pares, semilla 0, huella de código `4abed34a…`.
> **`rows_excluded_below_floor: 0`** y ρ alcanzada 2.49–2.51 frente a un objetivo
> de 2.50. `n_families_mean` 3.0 con k=3 y 5.0 con k=5 — el brazo k=5 realmente
> ejecutó cinco linajes distintos, cosa que la corrida contaminada del 24 de
> agosto no hizo.

**Es la primera vez que este experimento se ejecuta por encima de su propio piso
de empaquetado.** Todos los tiers v3c anteriores barrieron ρ = 1.5 contra pisos
de 1.51–2.37, así que toda celda fragmentada colapsaba a una tarea desnuda: esas
corridas midieron el acuerdo entre réplicas que respondían microtareas *sin
contexto*. Sus razones de momios de 3.47, 0.26 y 1.24 describen una configuración
que nadie eligió.

---

## 1. El veredicto

| estadístico | valor | lectura |
|---|---|---|
| **AUC, agrupado** | **0.525** | 0.500 es azar. Era 0.507 antes de la corrección de `returns_input_value` del 4 de septiembre; véase §4. |
| **Lift de marcado** con tasa de marcado del 10 / 20 / 30 % | **1.12 / 1.21 / 0.99** | 1.0 es aleatorio |
| *r* de Pearson | +0.117 | véase §3 — descansa sobre tres ítems |
| ítems en la calibración | 183 (127 correctos, 56 incorrectos) | |

Las instrucciones del propio tier, escritas antes de la corrida: *"un lift
cercano a 1.0 significa que la marca no es mejor que el azar, y ese resultado
retira el mapa de confianza."*

Marcar el 30 % de ítems con menor acuerdo detecta el 29.6 % de los errores. Eso
es lo que hace marcar el 30 % de los ítems al azar.

**Por categoría, los AUC se dispersan a ambos lados del azar y se cancelan:**

| categoría | n | exactitud | AUC |
|---|---|---|---|
| unit_conversion | 51 | 0.941 | 0.812 |
| arithmetic | 22 | 0.455 | 0.583 |
| date_arithmetic | 51 | 0.353 | 0.530 |
| **threshold_decision** | 40 | 0.850 | **0.382** |
| field_extraction | 17 | 1.000 | — (sin errores) |

`threshold_decision` está **por debajo** del azar: ahí, un acuerdo más alto
predice una respuesta *equivocada*. Que las categorías caigan a ambos lados de
0.5 y se agrupen en el azar es la firma de que no hay señal, no de que la señal
sea débil. (Esta tabla se computa antes de la corrección de calificación de la
§4, que lleva la exactitud de `arithmetic` a 0.478 y el AUC agrupado a 0.525; el
patrón no cambia.)

**Y añadir familias no ayuda.** k=3 da un AUC de 0.483, k=5 da 0.527. Dos linajes
independientes más no compraron nada.

## 2. Por qué — y esta es la parte a la que las corridas anteriores no podían llegar

El veredicto anterior era "el acuerdo no predice la corrección". Esta corrida
muestra el mecanismo, y es peor que una relación débil.

**El acuerdo medio es 0.966. Ciento setenta y tres de 183 ítems se sitúan en el
tramo superior, y la corrección de calificación de la §4 deja ese tramo intacto.**

| tramo de acuerdo | ítems | exactitud |
|---|---|---|
| 0.0 – 0.2 | 0 | — |
| 0.2 – 0.4 | 2 | 0.000 |
| 0.4 – 0.6 | 1 | 0.000 |
| 0.6 – 0.8 | 5 | 0.800 |
| **0.8 – 1.0** | **173** | **0.711** |

Cinco familias de modelo — cinco organizaciones, cinco linajes de
preentrenamiento, elegidas por su diversidad precisamente para que pudieran
discrepar — **coinciden entre sí casi siempre. Y donde coinciden casi a la
perfección, se equivocan el 29 % de las veces.**

El mapa de confianza no falla porque la correlación sea débil. Falla porque **el
predictor casi no tiene varianza que ofrecer**, y la varianza que tiene no sigue
al error. No se puede extraer una señal de una constante.

Este es el modo de fallo que las propias notas de diseño del proyecto nombraron y
después dieron por descartado: *los modelos que comparten datos de entrenamiento
comparten errores, así que coinciden con confianza en el mismo error*. Ahora se
ha medido directamente. Las familias independientes no son estimadores
independientes en esta carga de trabajo.

**Eso es un hallazgo sobre la ecología de los modelos, no sobre Swarmbly**, y es
la mitad más útil de esta corrida. Acota cualquier arquitectura —no solo esta—
que proponga derivar fiabilidad del acuerdo entre modelos a esta escala.

## 3. Por qué la *r* de Pearson no es evidencia

`pearson_r = +0.117` es positiva y apunta en la dirección "correcta". No debería
citarse. Descansa sobre el rango de 0.2 a 0.6, que contiene **tres ítems** en
total, todos ellos equivocados. Quítense esos tres y el predictor es una
constante.

Léase el AUC antes que la *r* — que es lo que dicen las instrucciones del tier, y
por qué lo dicen. Un AUC de 0.525 es el resumen honesto.

## 4. Corrección — y el hallazgo de cumplimiento que le sobrevive

> **La primera versión de esta sección, publicada el 3 de septiembre, era
> errónea.** Leía `units_with_no_label: 323 of 719` como una tasa de atrición del
> 45 % y concluía que "tres cuartas partes del trabajo despachado no llegan a la
> calibración". Eso es una lectura equivocada del estadístico, y es exactamente
> la clase de error que este proyecto no deja de corregir: un conteo leído como
> si midiera algo que no mide.

Una **unidad es una línea**, no una oportunidad de respuesta.
`units_with_no_label` cuenta toda línea que no es una respuesta — un preámbulo,
una despedida, una línea en blanco. No descarta nada. Corriendo el pipeline real
sobre el corpus real con un modelo que responde **todos los ítems, en el formato
pedido, correctamente**:

| brazo | unidades | sin etiqueta | ítems vistos | correctos |
|---|---|---|---|---|
| monolítico | 180 | 30 (16.7 %) | 150 | 150 |
| fragmentado N=2 | 210 | 60 (28.6 %) | 150 | 150 |
| **fragmentado N=4** | 270 | **120 (44.4 %)** | 150 | 150 |
| fragmentado N=8 | 390 | 240 (61.5 %) | 150 | 150 |

44.4 % con N = 4 frente al 45 % de la corrida, con **cero ítems perdidos y una
exactitud de 1.000**. La razón es una función pura de N — un sobrecoste fijo por
respuesta pagado N veces contra listas de respuestas N veces más pequeñas — así
que no es una tasa de error y nunca debe compararse entre brazos.

### La atrición real, que es menor y más interesante

`items_seen` es 387 contra un techo de 600 (150 ítems de la clave × 4
condiciones). Desglosada, no es una pérdida uniforme del 35 % — es casi por
completo un solo brazo con k bajo, y *mejora* a medida que se añaden réplicas:

| condición | ítems vistos / 150 |
|---|---|
| monolítico | **150 (100 %)** |
| fragmentado, k = 1 | **24 (16 %)** |
| fragmentado, k = 3 | 82 (55 %) |
| fragmentado, k = 5 | 131 (87 %) |

El brazo monolítico cumple a la perfección. Un solo trabajador fragmentado
produce una respuesta parseable para **un ítem de cada seis**. Añadir réplicas
recupera la mayor parte, porque un ítem cuenta como visto si *alguna* réplica lo
etiquetó.

Esta es una asimetría grande entre brazos en un denominador, que es la forma de
defecto por la que este proyecto ha retirado resultados dos veces. **Se enuncia
aquí y no se interpreta.** Hay dos lecturas vivas y esta corrida no puede
separarlas: o bien los trabajadores fragmentados genuinamente no logran emitir el
formato, o bien `task_item_scope` está eliminando ítems dentro de alcance que
debería conservar. Necesita su propio diagnóstico antes de que se cite ninguna
cifra que compare brazos sobre este corpus.

### El defecto de calificación que encontró esta investigación

`returns_input_value` reducía una respuesta a `_as_number` — el **último** número
— y la declaraba una reformulación siempre que ese número aparecía en la línea de
origen del ítem. `21 - 80`, contra una fuente que decía *"21 crates, 16 units per
crate, 80 removed"* y una clave de 256, quedó archivada como reformulación. Es un
intento: enuncia dos números y un operador omitido. Una reformulación devuelve un
valor y se detiene, así que la guarda ahora exige que la respuesta enuncie
exactamente un número.

Recomputada a partir de las respuestas guardadas de esta corrida, la corrección
devuelve **12 ítems** al denominador, todos en `arithmetic`, todos equivocados
por construcción:

| | antes | después |
|---|---|---|
| ítems calificados | 308 | 320 |
| exactitud agrupada | 0.7175 | **0.6906** |
| exactitud de `arithmetic` | 0.647 | **0.478** |
| ítems de calibración | 181 | 183 |
| exactitud de la calibración | 0.7017 | 0.6940 |
| **AUC agrupado** | 0.5073 | **0.5249** |

La dirección es la que importa: **la exactitud reportada era demasiado alta.** El
tramo de acuerdo superior no cambia, con 173 ítems y una exactitud de 0.711, así
que la §2 se sostiene exactamente como está escrita.

## 5. Qué zanja esto

El mapa de confianza se ha medido ya **cinco veces**: una contra un juez saturado
(r = −0.030, ininterpretable), tres contra una clave de respuestas sobre corridas
por debajo del piso (razones de momios comunes de 3.47, 0.26 y 1.24 — por encima,
por debajo y a caballo del 1), y una aquí, por encima del piso, con cinco
familias genuinas y un veredicto mecánico.

**AUC 0.525. Lift de marcado 1.0. Queda retirado.**

El mecanismo sigue en el protocolo: las réplicas se siguen despachando, el
acuerdo se sigue computando y reportando, y una región de acuerdo bajo sigue
siendo un lugar donde un lector podría mirar. Lo que se retira es la *afirmación*
— que la puntuación de acuerdo lleva información sobre si la respuesta es
correcta. No la lleva, y ahora hay una explicación en lugar de solamente un nulo.

**Lo que no debe decirse:** que este es un resultado débil o preliminar. Es la
corrida más limpia que ha tenido esta pregunta, y es inequívoca. El costo honesto
del mecanismo de consenso debería enunciarse junto a ella: k = 5 cuesta una parte
grande de la calidad de salida contra una señal que no existe.
