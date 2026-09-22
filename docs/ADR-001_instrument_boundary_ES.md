---
status: current
lang: es
---
# ADR-001: El instrumento no debe importar aquello que mide

**Estado:** Aceptada
**Fecha:** 12 de agosto de 2026
**Alcance:** `swarmbly_v0/` (el harness) y `benchmark_v7/` (el benchmark)

## Contexto

Este proyecto mide si repartir un prompt entre varios modelos pequeños degrada
la respuesta. Su salida no es un sistema en ejecución — es un número, y ese
número se publica. Así que la falla que importa aquí no es una caída. Es una
cifra equivocada en una dirección que nadie revisó.

Eso ya ha ocurrido repetidas veces, y el patrón es lo bastante consistente como
para tratarse como una propiedad del diseño y no como una racha de mala suerte:

| | Qué salió mal | Cómo se encontró |
|---|---|---|
| Métrica de coherencia | No es neutral entre brazos: las entidades esperadas crecían con N, las omisiones se atribuían por turnos entre las cabezas de fragmento, las clases locales a la costura solo podían dispararse donde había costuras. El mismo texto puntuó 0.9375 en monolítico y 0.5000 en N=8. | Solo después de que cuatro documentos lo habían citado |
| Eje ρ | 13 de 96 celdas estaban por encima de su propio piso de empaquetado; las dos filas que anclaban el descenso publicado no tenían ninguna | Solo después de que la curva ya era el titular |
| Calificador de ítems | Un punto decimal leído como etiqueta de ítem; una respuesta correcta salió del denominador de exactitud y aterrizó en `items_echoed` | Revisión adversarial, 526 pruebas después |
| Regex de acarreo | El mismo defecto en el regex hermano, pero este *escribe* — un `[42]=5` fantasma entró en el paquete del sucesor | Verificando la corrección del calificador de ítems |
| Cuatro verificaciones de tokens | Un punto final de oración volvía invisible un token; `term_once`, `no_repeated_ngram`, `any_of`, `boolean`, todas afectadas | Generalizando una corrección |
| Filtro de alcance | Registros filtrados, totales del reporte no; ambos impresos lado a lado | Revisión adversarial |
| Asimetría del assembler | `paragraph_count` satisfecho por el formateador en un brazo y por el modelo en el otro | Revisión adversarial |
| Compuertas del runner | `\| tee … \|\| true` en cada nivel descartaba todo `PacketInvariantError` y reportaba como completa una corrida abortada | Auditoría del pipeline |

Dos cosas son comunes a todos ellos. Primero, **el defecto estaba en el
instrumento, nunca en el protocolo** — la arquitectura bajo prueba todavía no ha
sido contradicha por la evidencia; solo lo ha sido su medición. Segundo, **cada
defecto era unilateral en la dirección de la propia hipótesis del proyecto.** Esa
es la parte que no puede descartarse como ruido. Un error simétrico infla la
varianza; estos inflaron la respuesta que el proyecto quería.

La pregunta que este ADR zanja es dónde debe estar la frontera del instrumento,
ahora que `benchmark_v7/` se está construyendo y podría reutilizar la puntuación
del harness.

## Decisión

**`benchmark_v7/` no importa nada de `swarmbly_v0/`, y la prohibición se afirma
mediante una prueba que parsea el grafo de importaciones, y no por convención.**

En concreto:

1. `benchmark_v7.evaluate` no tiene dependencia de `swarmbly_v0.metrics`,
   `swarmbly_v0.grading`, ni `swarmbly_v0.constraints`. Tiene su propio parser,
   su propia tolerancia, su propio tipo de veredicto.
2. La *primera* prueba del benchmark es la invariante que se rompió en el
   harness — la misma respuesta puntúa igual sin importar cómo se cortó el
   prompt — afirmada antes de que el evaluador se use para nada.
3. El benchmark separa tres preguntas que la clave de respuestas plana del
   harness confundía: `correct` (si coincidió), `answerable` (si el paquete
   contenía todos los hechos que la afirmación requiere), y `owed_by` (qué
   paquete debió haber llevado un hecho faltante). "Incorrecto" e
   "irrespondible" tienen dueños distintos — el modelo y el packer — y se
   gastaron seis corridas en preguntas donde eran indistinguibles.

## Opciones consideradas

### Opción A — Reutilizar el puntuador del harness en el benchmark

| Dimensión | Evaluación |
|---|---|
| Complejidad | La más baja. Nada nuevo que escribir. |
| Comparabilidad | La más alta — las cifras del benchmark y del harness están en una sola escala |
| Modo de falla | **Un defecto en el puntuador los invalida a ambos a la vez** |
| Familiaridad del equipo | La más alta |

**A favor:** un solo puntuador, un solo conjunto de pruebas, cifras directamente
comparables entre V0–V6 y V7.

**En contra:** hace que las dos mediciones sean *dependientes*. El defecto de
neutralidad entre brazos se habría propagado en silencio hasta V7, y V7 habría
"confirmado" V0 — que es el peor desenlace posible, porque el acuerdo entre una
medición y su propio instrumento se lee como replicación.

### Opción B — Evaluador independiente, impuesto (elegida)

| Dimensión | Evaluación |
|---|---|
| Complejidad | Moderada. Un segundo parser y puntuador, ~200 líneas. |
| Comparabilidad | Reducida — las cifras de V7 no están en la escala de V0 |
| Modo de falla | Un defecto en un instrumento deja al otro en pie |
| Familiaridad del equipo | Menor; dos convenciones que sostener en la cabeza |

**A favor:** V7 puede *estar en desacuerdo* con el harness, y un desacuerdo es
informativo en lugar de un bug. La prueba de AST convierte la frontera en un
hecho sobre el código en lugar de una intención.

**En contra:** costo real. Dos parsers significan dos lugares donde puede vivir
un bug de parser, y el proyecto ya ha tenido cuatro bugs de parser. Mitigado
manteniendo el parser del benchmark deliberadamente más estricto y mucho más
pequeño — acepta solo ids de afirmación entre corchetes, donde el calificador
del harness tenía que tolerar lo que fuera que emitiera un modelo pequeño.

### Opción C — Puntuador compartido detrás de una prueba de contrato de neutralidad entre brazos

| Dimensión | Evaluación |
|---|---|
| Complejidad | Moderada |
| Comparabilidad | La más alta |
| Modo de falla | Solo se atrapan las fallas que la prueba de contrato anticipa |
| Familiaridad del equipo | Alta |

Esta es la opción que mejor se ve en el papel y que se rechaza por la evidencia.
Una prueba de contrato atrapa la clase de falla para la que fue escrita.
`test_instrument.py` ya tenía exactamente una prueba de neutralidad entre
brazos, para una sola métrica — atrapó su defecto y nunca se generalizó, y siete
defectos más de esa forma pasaron por el hueco. Un contrato vale lo que valga la
imaginación de quien lo escribió, y toda la historia de arriba es un registro de
esa imaginación quedándose corta.

## Análisis de la disyuntiva

La decisión cambia **comparabilidad por independencia**, y ese es el intercambio
correcto solo por aquello para lo que sirven las cifras de este proyecto. Si la
meta fuera seguir una métrica a lo largo del tiempo, un solo puntuador sería lo
correcto: un instrumento consistente le gana a uno exacto para detectar
tendencias. Pero la meta es una afirmación falsable con un umbral de abandono
pre-registrado, y ahí la pregunta es si la medición es *verdadera*, no si es
consistente con la del mes pasado.

La independencia compra una cosa específica: cuando V7 y el harness discrepan,
al menos uno de los dos está equivocado, y el proyecto se entera. Bajo la Opción
A no pueden discrepar.

El costo es honesto y no debe minimizarse. Las cifras de V7 no serán graficables
contra las de V0, y un lector va a querer ese gráfico. La respuesta es que las
cifras de V0 están retiradas de todos modos, así que hay menos continuidad que
preservar de lo que parece.

## Consecuencias

**Más fácil**

- Un defecto en un instrumento ya no invalida todos los resultados a la vez.
- Se le puede echar la culpa al packer. `answerable` y `owed_by` significan que
  una cifra mala puede atribuirse al planner, al packer o al modelo, en lugar de
  reportarse como "calidad perdida".
- El brazo oráculo se vuelve significativo: paquetes fragmentados con contexto
  perfecto separan *la tarea es demasiado difícil para un modelo 3B* de *el
  packer lo dejó en ayunas*.

**Más difícil**

- Dos parsers, dos tolerancias, dos convenciones. Todo cambio futuro de
  puntuación hay que considerarlo dos veces, y la tentación de unificarlos
  volverá.
- Narrativa entre versiones. Todo documento que compare V7 con corridas
  anteriores tiene que decir explícitamente que los instrumentos difieren.
- La prueba de AST es estructural y parece trivial. Necesita un comentario que
  explique por qué borrarla no es una limpieza.

**Por revisar**

- Si alguna vez se muestra que V7 y el harness coinciden a lo largo de una
  rejilla amplia sobre el mismo corpus, el caso para dos instrumentos se
  debilita y la Opción C se vuelve defendible. Ese acuerdo tiene que ser
  *medido*, no asumido.
- El corpus del benchmark es sintético — un grafo de hechos, no prosa. Eso acota
  lo que V7 puede concluir, y queda declarado en `benchmark_v7/__init__.py` en
  lugar de descubrirse después.

## Acciones

1. [x] `benchmark_v7.evaluate` escrito sin importaciones del harness
2. [x] Neutralidad entre brazos afirmada como la primera prueba del benchmark
3. [x] `correct` / `answerable` / `owed_by` separados en `ClaimVerdict`
4. [x] Prueba de AST que falla si `benchmark_v7/` alguna vez importa la
       puntuación del harness — `tests/test_benchmark_v7.py`, verificada contra
       una violación deliberada en lugar de darla por funcionando
5. [ ] Generación de instancias con una división dev/final congelada y
       `--verify`
6. [ ] `benchmark_v7/run.py`: Map y Chain primero, con el brazo oráculo incluido
       desde el inicio en lugar de añadirse una vez que un resultado se ve mal
