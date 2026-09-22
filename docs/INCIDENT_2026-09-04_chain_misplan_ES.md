---
status: current
lang: es
---
# Incidente — todo prompt enumerado se planificó como una cadena de dependencias

**Encontrado:** 4 de septiembre de 2026, diagnosticando por qué un solo worker
fragmentado produjo una respuesta parseable para un ítem de cada seis mientras el
brazo monolítico produjo 150 de 150.
**Severidad:** dos resultados publicados retirados, uno parcialmente. El nivel
`v4` de 16 horas se retuvo correctamente bajo esta sospecha y debe seguir
retenido hasta una re-ejecución.
**Clase:** asimetría entre brazos en el **estímulo**. Todos los defectos previos
de este proyecto estaban en el instrumento. Este cambió lo que se les preguntó a
los modelos.

---

## Qué pasó

`swarmbly_v0/router.py:58` lista `\bthen\b` entre los `_SEQUENTIAL_CUES`. Todo
prompt en `prompts/ground_truth.json`, y todo prompt enumerado en
`free_form.json`, termina con una directiva de formato de salida que dice:

> Give one line per item. Begin the line with the item number in square brackets,
> exactly as given, **then** a single space, **then** the value. […] **Items are
> independent: the answer to one must not depend on the answer to any other, and
> you must not reconcile them against each other.**

Los dos `then` son tipografía. Están en la misma oración que la afirmación de que
los ítems son independientes. Un solo indicio supera la compuerta —
`_saturate(1, 1.5) = 0.487 ≥ 0.45` — así que **los 15 prompts de ground truth se
planificaron como cadenas de cuatro niveles de profundidad**.

La consecuencia no es sutil. Con ρ = 2.5, N = 4, **42 de 60 paquetes de fragmento
llevaban un bloque `[PREDECESSOR SUMMARIES]` que contenía las líneas de respuesta
de otro paquete** — `- t0: [01] 576` — situado directamente encima de un bloque
de tarea que dice *«Answer only the items listed here.»* El prompt monolítico no
llevaba ninguno.

Un worker al que se le muestran las respuestas de otro paquete las repite.
`task_item_scope` descarta correctamente esas repeticiones por estar fuera de
alcance, así que el ítem no queda ni respondido ni recuperable — que es
exactamente el 16 % que se ve con k = 1, y la razón por la que se recupera al
subir k: el consenso fusiona réplicas y solo algunas familias repiten.

El propio docstring de `carry_block` ya nombraba la consecuencia: *«the successor
restates them as its own, and an enumerated corpus reported 379 graded items
against a key holding 150.»* El mecanismo estaba documentado. El disparador no.

Un segundo defecto, independiente, lo volvió incondicional:
`swarmbly_v0/packing.py:196` colocaba el bloque de predecesor *opcional* sin
ninguna compuerta, mientras que la vía *obligatoria* (`carry_block`) está
condicionada a `consumes_predecessor` precisamente para impedir esto. Por encima
del piso de empaquetado siempre hay holgura, así que el bloque entraba de todos
modos — que es la razón por la que esto salió a la superficie en la primera
ejecución jamás realizada por encima del piso.

## Por qué no se detectó

La evaluación de descomponibilidad del router está publicada y no era incorrecta:
lee un vector de características sobre el prompt completo, y «then» es un indicio
secuencial real en prosa. El error fue usar el *prompt completo* — incluido el
bloque que describe el formato de salida — para decidir la **topología de
dependencias**. Una directiva de formato no es una afirmación sobre dependencias
de datos, y ningún test aseveraba eso.

## El arreglo

- `planner.ordering_text()` — la decisión de dependencia ahora lee el preámbulo y
  los ítems de un lote enumerado, nunca su bloque de formato de salida. `plan()`
  la usa. El vector de características del propio router queda intacto, así que
  su evaluación publicada no se ve afectada.
- `packing.answers_by_item_label()` — un paquete cuyo bloque de tarea nombra sus
  propios ítems como `[NN]` no recibe ningún resumen de predecesor como contexto
  *opcional*. Los fragmentos de prosa quedan intactos; las cadenas genuinas
  siguen recibiendo su carry obligatorio.

**Alcance del cambio**, medido en lugar de supuesto:

| corpus | prompts planificados como cadenas, antes → después |
|---|---|
| `ground_truth.json` | **15/15 → 0/15** |
| `free_form.json` (mitad enumerada) | **6/11 → 0/11** |
| `tables24.json` | 0/24 → 0/24 |
| `prompts.json` | 4/8 → 4/8 |
| `complex.json` | 5/20 → 5/20 — todo `chain_*` sigue siendo una cadena |

Cinco tests de regresión, cada uno verificado como fallido contra el código
previo al arreglo, con cada arreglo revertido de forma aislada y con ambos a la
vez.

## Qué queda retirado

**`RESULTS_V3C_GT_CORRECTED.md` — por completo, en ambas direcciones.** No solo
las comparaciones entre brazos. Con k > 1 cada réplica de una misma tarea recibe
el *mismo* paquete, así que un bloque de predecesor compartido les da algo sobre
lo cual converger: el acuerdo medio de 0.966 puede estar inflado por el defecto.
Si lo está, entonces «el predictor no tiene varianza, AUC 0.525, el mapa queda
retirado» se apoya en una varianza que fue suprimida artificialmente. **La
conclusión no es segura en ninguna de las dos direcciones**, incluida la
afirmación de mecanismo de la §2 sobre cinco familias que coinciden y se
equivocan el 29 % de las veces.

**`RESULTS_V3C_FF_COMPOSITION.md` — solo la §5.** Seis de los ocho prompts que
alimentan la calibración de acuerdo son los enumerados afectados. El AUC 0.602,
el lift 2.15, la p = 0.0026 y el intervalo agrupado quedan todos retirados. **Las
§1–4 se sostienen**: los tres prompts `comp_*` no coinciden con ningún indicio
secuencial ni antes ni después del arreglo, así que la brecha de restricciones de
14 a 21 puntos, el impuesto de coherencia que da cero sobre esos mismos textos, y
el mecanismo de duplicación-y-omisión no se ven afectados.

**No afectados:** `tables-final` y `tables-dev`. `tables24.json` planifica 0
cadenas antes y después, así que la celda declarada — +2.30 %, IC [−2.05 %,
+7.49 %], NOT MET — se sostiene.

## Qué cuesta esto y qué vale

Dos noches de cómputo, y el primer resultado no nulo en seis mediciones del mapa
de confianza. Ese era el resultado más tentador de la sesión y el que más valía la
pena poner en duda; esta es la razón.

En contra de eso: el hallazgo de composición sobrevive, y es el resultado mayor. Y
el defecto es el primero que este proyecto encuentra en el **estímulo** y no en el
instrumento — una categoría que nada en el harness estaba vigilando. Las
compuertas agregadas esta semana (`publishable`, la post-condición de `run_tier`,
la comprobación de k contra familias) vigilan todas la medición. Ninguna de ellas
podría haber visto esto.

**Qué lo habría detectado:** una aserción de que a los dos brazos se les despacha
la misma pregunta. Ahora hay una — `test_no_answer_sheet_fragment_is_handed_another_packets_answers`
— y es la propiedad, no la instancia.
