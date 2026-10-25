---
status: current
note: >
  The current composition verdict. comp-final-v2 reads -0.35 on a corpus
  nobody had seen.
lang: es
---
# Los dos veredictos finales — 5 de septiembre de 2026

Cuatro corridas: `comp-dev-once` (re-corrida), `comp-final-once`, `comp-dev-v2`,
`comp-final-v2`. Huella de código idéntica en las cuatro (`136fc431…`), corpus
verificados, control fallando en todas, cero filas excluidas.

**Los dos veredictos son NOT MET.** Y aun así este es, por un margen amplio, el
resultado más fuerte que ha producido el proyecto.

---

## 1. Los tres splits finales, lado a lado

Todos a ρ = 4.0, N = 3, k = 1, 24 clusters, mismo estimador, mismo criterio.

| corrida | monolítico | fragmentado | diferencia | IC 95 % | veredicto |
|---|---|---|---|---|---|
| `comp-final` (4 sep, **sin** dedup) | 0.873 | 0.649 | **+22.40** | [+16.15, +28.51] | NOT MET por 23.51 |
| `comp-final-once` (v1, **con** dedup) | 0.873 | 0.797 | **+7.64** | [+1.42, +13.61] | NOT MET por **8.61** |
| `comp-final-v2` (v2, **con** dedup) | 0.813 | 0.816 | **−0.35** | [−8.33, +7.64] | NOT MET por **2.64** |

En el mismo corpus v1, con el mismo split, con la única diferencia de imponer
`term_once` en el ensamblador: **+22.40 → +7.64**. Casi **quince puntos**
recuperados sobre el split final, y el fallo pasó de 23.51 puntos a 8.61.

En un corpus que nadie había visto: **−0.35 puntos**. El brazo fragmentado
puntuó *por encima* del monolítico. Falla el criterio por 2.64 puntos, y falla
**por el ancho del intervalo, no por el tamaño del efecto**.

---

## 2. La forma del resultado

| corrida | pierde | empata | **gana** |
|---|---|---|---|
| 4 sep, sin dedup | 19 | 5 | **0** |
| v1, con dedup | 13 | 5 | **6** |
| v2, con dedup | 8 | 6 | **10** |

En v2, fragmentar en tres **ganó en 10 de 24 prompts** y perdió en 8. Es un
volado. En la corrida del 4 de septiembre no ganó ni uno solo en veinticuatro.

---

## 3. El techo de la línea base: dónde vive el costo que queda

`baseline_at_ceiling` existe porque **donde el monolítico saca 1.000 la
diferencia pareada no puede ser negativa**. Separando los prompts por eso:

| corrida | en el techo | Δ ahí | fuera del techo | **Δ ahí** |
|---|---|---|---|---|
| 4 sep, sin dedup | 8 | +36.04 | 16 | +15.57 |
| v1, con dedup | 8 | +22.40 | 16 | **+0.26** |
| v2, con dedup | 4 | +14.17 | 20 | **−3.25** |

**En los prompts donde la diferencia es libre de moverse en las dos
direcciones, el costo con dedup es +0.26 en v1 y −3.25 en v2.** Cero, dos veces,
en dos corpus independientes.

Todo el costo medido que queda está concentrado en los prompts donde el
monolítico fue perfecto. Y ahí hay que ser honesto porque admite dos lecturas:

* **Es real:** fragmentar cuesta ~2 restricciones cuando el monolítico las
  satisface todas, y ~0 cuando el monolítico ya falla algunas. Fragmentar no
  alcanza la perfección pero sí iguala la imperfección.
* **Es censura:** si el efecto verdadero por prompt fuera ruido centrado en
  cero, en los prompts de techo sólo se observa la mitad desfavorable (el
  monolítico no puede ser superado), y la media de media-normal es positiva. Un
  Δ positivo ahí es **exactamente** lo que se vería bajo efecto nulo con
  censura.

Los datos no separan las dos con 24 clusters. Lo que sí se puede decir: **la
diferencia entre v1 (+7.64) y v2 (−0.35) se explica casi enteramente por cuántos
prompts están en el techo** — 8 de 24 contra 4 de 24. No hace falta invocar
"otro corpus, otro número".

---

## 4. Qué NO dice esto

**No es un pase.** El criterio declarado es la cota superior por debajo de 5
puntos, y es +7.64 en v2. Se falló, dos veces, sobre hipótesis prerregistradas.

**Los dos corpus no coinciden en magnitud.** +7.64 contra −0.35. Sus intervalos
se solapan en [+1.42, +7.64], así que son compatibles, pero **ninguno de los dos
debe citarse solo como "el" costo**. La replicación hizo su trabajo: detectó que
el número depende del corpus, y la tabla del techo dice por qué.

**No dice nada sobre calidad.** El dedup borra oraciones. `enforce_term_once`
quitó 55 oraciones en v1 y 75 en v2 a N=3. El puntaje cuenta restricciones
satisfechas; que el texto quede mejor o peor de leer no lo mide nada aquí.

**No dice nada sobre N = 8.** El control falló fuerte en las dos (+69.62 y
+49.79) — el instrumento separa los brazos, que es la comprobación que más
importa. Y el dedup casi no dispara ahí: **1 oración** en 24 celdas, contra 55 y
75 a N=3. A N=8 el problema es omisión, y no se puede deduplicar lo que nunca se
escribió.

**Sigue siendo con modelos de 3B, y sobre tareas que caben veinte veces en la
ventana del nodo más chico.** El límite de `REVISION_2026-09-05` no se movió.

---

## 5. Dos cosas menores que quedan resueltas

**La tubería es determinista.** La re-corrida de `comp-dev-once` a las 13:21 dio
números **idénticos** a la de las 12:05 — mismo τ (0.585), mismo +8.61, misma
tasa celda por celda. La pregunta que dejé abierta ("si las estimaciones salen
distintas, eso es varianza entre corridas") tiene respuesta: a semilla 0 no hay
varianza entre corridas. Lo que cambia entre corpus es el corpus.

**Los tiers de v2 replican los de v1.** `baseline_at_ceiling` 3 de 12 en los dos
devs, `mean_baseline` 0.842 contra 0.844. El generador nuevo produce dificultad
equivalente, que era la condición para que v2 sirviera de algo.

---

## 6. Dónde queda el proyecto

| resultado | estado |
|---|---|
| `term_once` en el ensamblador recupera ~15 puntos en el split final | **Medido, prerregistrado, replicado en dos corpus** |
| Fuera del techo de la línea base, el costo de fragmentar en 3 es cero | Medido dos veces, +0.26 y −3.25 |
| El criterio declarado (cota superior < 5) sigue sin cumplirse | NOT MET por 8.61 (v1) y 2.64 (v2) |
| El control a N=8 falla siempre | El instrumento separa los brazos |
| 98.6 % del costo *previo* era paralelismo, no el planner | `comp-oracle`, sin cambios |
| El acuerdo entre modelos no predice corrección | Cerrado, seis mediciones |
| ρ no es la palanca; N sí | Cerrado |

**Lo que ahora bloquea un pase es el ancho del intervalo, no el efecto.** Con 24
clusters y una desviación por prompt de este tamaño, la cota superior no baja de
5 puntos aunque la media sea cero. Para pasar hacen falta más clusters — un
corpus de 60 o 72 prompts — o una medida con menos varianza por prompt.

Eso es una decisión de diseño experimental, no un arreglo de la arquitectura, y
conviene decidirla con la cabeza fría: **subir el número de clusters hasta que un
efecto nulo pase el criterio es una forma de conseguir el resultado que uno
quiere.** Si se hace, se declara antes cuántos clusters y por qué, y el corpus
se genera antes de mirar nada.

## Lo pendiente que no cambió

Sigue sin probarse el caso para el que existe la arquitectura: **una tarea que no
quepa en un nodo**. El prompt más grande del proyecto mide 375 tokens contra una
ventana de 8192. Todo lo anterior mide cuánto cuesta partir algo que no hacía
falta partir — y ese costo ahora es aproximadamente cero, lo cual es una noticia
buena y sigue sin ser la pregunta.
