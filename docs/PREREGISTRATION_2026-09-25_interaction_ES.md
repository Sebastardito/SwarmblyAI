---
status: current
lang: es
---

# Preregistro — la interacción entre fuerza del nodo y el impuesto de fragmentación

**25 de septiembre de 2026 · escrito ANTES de correr el análisis**

Se publica junto con `RESULTS_2026-09-25_interaction_ES.md`, que reporta que la
hipótesis **no sobrevivió**. El preregistro se publica igualmente, y sobre todo
por eso: es el documento que impidió confirmar un hallazgo falso.

Este documento fija la hipótesis, las pruebas, las condiciones de rechazo y las
condiciones de muerte **antes** de tocar los datos con este diseño. Existe
porque el hallazgo que motiva el análisis se encontró mirando los datos, y un
hallazgo encontrado así no se confirma con los mismos grados de libertad con que
se encontró.

Datos: `swarmbly_ref/data/benchmark.jsonl`, 341 corridas, sha256
`d94bb9cc7694d0f7…`, congelado antes de escribir esto.

---

## 1. De dónde viene la hipótesis (declaración de origen)

> **Nota posterior, añadida al publicar.** Ese agregado quedó después **rehusado**: está confundido con el presupuesto de salida y no se ha medido. El análisis de abajo nunca dependió de que fuera correcto —parte de que mezcla celdas de signo opuesto— pero conviene que el lector no se lleve la cifra suelta.

Al revisar `REPORT_REAL.md` se observó que el impuesto agregado (−18.32 %) mezcla
celdas de signo opuesto, y que en la tabla mono/frag/SC los modelos con baseline
monolítico bajo ganaban mucho al fragmentar mientras los de baseline alto
perdían. Un análisis exploratorio con un umbral elegido a ojo (`mono < 0.5`) dio
−73 % y +15 % en los dos estratos.

**Ese análisis es exploratorio y no cuenta como confirmación.** Su umbral se
eligió después de ver los datos y su estadístico tiene un defecto que la
sección 3 describe. Lo que sigue es el diseño que sí cuenta.

---

## 2. Hipótesis

> **H-INT.** El impuesto de fragmentación depende de la fuerza del nodo: cuanto
> mejor resuelve un nodo la tarea sin fragmentar, más le cuesta fragmentar.
> Equivalentemente, la fragmentación rescata nodos débiles y daña nodos fuertes.

Predicción direccional: **asociación positiva** entre la fuerza del nodo y el
impuesto, donde `impuesto = (mono − frag)/mono · 100` (positivo = fragmentar es
peor).

---

## 3. El defecto que obliga a cambiar el estadístico

`impuesto = 1 − frag/mono` lleva `mono` en el denominador. Si se correlaciona el
impuesto con `mono` **de la misma celda**, la asociación aparece en parte por
construcción: el ruido de medición de `mono` entra dos veces y con signos que se
refuerzan. Una celda con `mono` bajo por azar produce impuesto muy negativo sin
que nada real haya ocurrido.

Es exactamente el tipo de comprobación que afirma más de lo que midió, así que
el diseño la evita:

> **La fuerza del nodo se estima con *leave-one-out*: el score monolítico medio
> de ese modelo sobre TODAS LAS DEMÁS tareas.** Predictor y resultado provienen
> entonces de datos disjuntos, y la coincidencia matemática desaparece.

Es la misma precaución que `T0RR` ya aplicaba a la reputación («sin fuga de la
tarea retenida»).

---

## 4. Pruebas

### 4.1 Primaria — H-INT con predictor LOO

Para cada celda `(tarea, modelo)` con celda monolítica y fragmentada
comparables:

- `LOO_strength(model, task)` = media de los scores monolíticos de ese modelo en
  todas las tareas **distintas** de ésta.
- `tax(task, model)` = `(mono − frag)/mono · 100` en esa tarea.

**Estadístico:** Spearman entre `LOO_strength` y `tax`, con p por permutación
(50 000, semilla 11) **agrupada por tarea** para no tratar celdas de la misma
tarea como independientes.

**H-INT se sostiene si** ρ > 0 con p < 0.05.

### 4.2 Control de longitud

La misma prueba restringida a celdas donde **el texto fragmentado NO es más
largo que el monolítico** (`razón ≤ 1.0`). Si la asociación se sostiene ahí, no
es verbosidad.

### 4.3 Control de techo

La misma prueba excluyendo celdas con `mono ≥ 0.90`. Un nodo con score casi
máximo sólo puede perder, así que parte de la asociación podría ser falta de
margen y no un efecto real.

### 4.4 Secundaria — tabla estratificada

Descriptiva, no confirmatoria. El umbral se fija **mecánicamente** como la
**mediana de los scores monolíticos del corpus**, calculada antes de mirar el
resultado, no elegido. Se acompaña de un **barrido del umbral** sobre todo el
rango intercuartílico para mostrar que el resultado no depende del punto de
corte.

---

## 5. Condiciones de rechazo (el análisis se niega, no adivina)

1. **< 20 grupos (tareas)** en cualquier prueba → negarse (`MIN_CLUSTERS`).
2. **< 8 celdas** en el estrato de longitud controlada → negarse en esa prueba y
   decirlo, en lugar de reportar un nulo sin potencia.
3. **Varianza cero** en `LOO_strength` → negarse.
4. **p mínimo alcanzable > 0.05** con los valores observados → negarse por falta
   de potencia.
5. Si el corpus no reproduce su sha256 → detener todo.

## 6. Condiciones de muerte

**H-INT muere si** ocurre cualquiera de estas:

- ρ ≤ 0 en la prueba primaria, o p ≥ 0.05.
- La asociación **desaparece bajo control de longitud** (§4.2): entonces lo
  medido era verbosidad y el hallazgo se retira.
- La asociación **desaparece al excluir el techo** (§4.3): entonces era falta de
  margen y no un efecto de la fragmentación.
- El barrido de umbral (§4.4) muestra que el signo del estrato cambia dentro del
  rango intercuartílico: entonces no hay dos regímenes, hay un gradiente sin
  punto de corte útil, y la tabla estratificada no debe publicarse.

## 7. Qué NO decide este análisis

- **No re-prueba el criterio de abandono.** El criterio exige 60–72 prompts de
  una sola categoría; esto son celdas de varias categorías. Lo que hace es
  mostrar que el agregado no es interpretable, no sustituirlo.
- **No establece causalidad sobre el mecanismo.** Que fragmentar rescate nodos
  débiles no dice *por qué*.
- **No amplía la muestra.** El estrato débil con longitud controlada seguirá
  siendo pequeño; ampliarlo exige correr más celdas y eso queda fuera de este
  análisis.

## 8. Enmiendas

Cualquier cambio a este documento posterior a la primera corrida se anota aquí
con fecha y razón. Una enmienda declarada vale; una silenciosa no.

*(sin enmiendas al momento de la primera corrida)*

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Compañero en inglés:
`PREREGISTRATION_2026-09-25_interaction_EN.md`. Resultados:
`RESULTS_2026-09-25_interaction_ES.md`.*
