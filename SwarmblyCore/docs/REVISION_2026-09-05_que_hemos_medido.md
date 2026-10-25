---
status: current
lang: es
---
# ¿Vamos en círculos? — revisión del planteamiento

**5 de septiembre de 2026.** Una revisión del planteamiento que responde dos
preguntas, sin defenderse: si hay algo mal en cómo están planteadas las pruebas,
y si hay un sesgo hacia evidenciar debilidades en vez de ver la fortaleza del
fundamento.

Las dos respuestas son **sí, en parte** — y la segunda apunta a un defecto de
encuadre que es más grande que cualquiera de los errores de ejecución.

---

## 1. El hecho que reencuadra todo

El prompt más grande de **todo** el proyecto mide **375 tokens**.

| corpus | n | mediana | máximo |
|---|---|---|---|
| `complex.json` | 20 | 332 | **375** |
| `ground_truth.json` | 15 | 243 | 373 |
| `tables24.json` | 24 | 332 | 332 |
| `free_form.json` | 11 | 179 | 296 |
| `prompts.json` | 8 | 145 | 160 |
| `composition.json` | 36 | 106 | 119 |

El modelo más pequeño del pool (`gemma2:2b`) tiene una ventana de **8192
tokens**. El prompt más grande usa el **4.6 %** de la memoria del nodo más chico.

**Ninguna tarea, en ningún corpus, en ninguna corrida, ha necesitado
fragmentarse.** El brazo monolítico siempre funcionó porque siempre cupo.

Entonces lo que hemos medido durante tres semanas es: *cuánto cuesta partir una
tarea que no hacía falta partir*. Y la respuesta correcta a esa pregunta —
medida con rigor, seis veces, con instrumentos que fuimos corrigiendo — es
**cuesta**. No podía ser otra cosa. No hay ganancia posible que medir, porque
nunca hubo nada infactible.

Eso no invalida ninguna medición. Las invalida como **evaluación de la
arquitectura**.

---

## 2. Sobre el sesgo: dónde sí lo hay y dónde no

### Donde el instrumento SÍ favoreció a la arquitectura

* `constraint_score_comparable` se creó para **quitar** un sesgo en contra del
  brazo fragmentado: las clases ancladas a costuras cobraban más mientras más
  fragmentado estuviera (5.7 puntos a N=2, 10.1 a N=8).
* `packing_ceiling`, `predict_rho` y `check_grid` existen para eliminar
  **falsos fallos** — celdas que abortaban por la grilla, no por la arquitectura.
* El brazo oráculo se construyó para darle a la arquitectura su **mejor caso**, y
  cuando la primera política resultó injustamente dura con la propia arquitectura
se corrigió y se midieron las dos mitades.

### Donde el planteamiento SÍ está inclinado

1. **Todas las compuertas son de una sola dirección.** Ninguna ha abortado jamás
   una corrida por ser *demasiado favorable*. Detienen falsos positivos y no
   falsos negativos.
2. **Todo veredicto se juzga sobre la cota SUPERIOR** del intervalo. Para una
   medida de *costo* eso significa tomar siempre la estimación más pesimista. Es
   la elección correcta para una afirmación del tipo "cuesta menos de 5 puntos",
   pero significa que un resultado marginalmente bueno se lee como fracaso.
3. **Se reemplazó un instrumento favorable por uno desfavorable.** El impuesto de
coherencia leía +0.14 %; se argumentó que estaba saturado y ciego a duplicación
y omisión — lo cual es cierto y demostrable — y se sustituyó por un conteo que
   lee 22 puntos. La justificación es sólida; **la dirección del cambio merece
   quedar escrita**.
4. **El corpus de composición está construido con la conjunción más difícil
   posible para trabajadores paralelos**: `must_mention` + `term_once` sobre el
   mismo término. Se construyó así para que la línea base no se saturara. El efecto lateral es que
se seleccionaron justo las restricciones sensibles a
   coordinación.
5. **Modelos de 3B confunden capacidad con arquitectura.** Buena parte de la
   pérdida en `must_mention` es que el modelo no sigue la instrucción, no que la
   arquitectura pierda información. No existe ningún brazo que separe las dos.
6. **Nunca se ha medido ningún eje donde fragmentar debería ganar.** Ni costo por
   nodo, ni memoria pico, ni factibilidad. Toda medición es calidad contra
   monolítico, que es el único eje donde partir sólo puede perder.

El punto 6 y el hecho de los 375 tokens son el mismo problema visto dos veces.

---

## 3. Y aun así: no hemos ido en círculos

Siete cosas quedaron establecidas, y ninguna se ha tenido que retirar:

| # | resultado | estado |
|---|---|---|
| 1 | El acuerdo entre modelos **no** predice corrección. AUC 0.532 y 0.547, seis mediciones, contra clave de respuestas. | Cerrado. Retira el mapa de confianza. |
| 2 | ρ no es la palanca; **N** sí. Dentro de un brazo, barrer toda la ventana mueve 0.06–0.21; cambiar N mueve 20.5 puntos. | Cerrado. |
| 3 | ρ < 2.0 con N=8 es **inalcanzable** en este corpus, no sólo incumplido. | Cerrado. |
| 4 | El impuesto de coherencia es el instrumento equivocado para prosa. | Cerrado, tres confirmaciones. |
| 5 | El consenso (k) **no** recupera el costo de composición: +19.38 contra +18.40. | Cerrado, predicho de antemano. |
| 6 | Con asignación perfecta, **98.6 %** del costo de composición sigue ahí. No es un defecto del planner. | Cerrado a nivel dev. |
| 7 | `term_once` pertenece al **ensamblador**: 14/24 contra 6/24, por encima del monolítico. | Prometedor, en prueba ahora. |

Siete conclusiones en tres semanas no es ir en círculos. La sensación viene de
que **los errores son ruidosos y las conclusiones son calladas**, y de que seis
de las siete son negativas. Un resultado negativo sigue siendo un resultado: el
punto 1 mata una funcionalidad completa del diseño, y el punto 2 redirige todo el
esfuerzo de optimización que se hubiera gastado en ρ.

---

## 4. Lo que debe cambiar

### a. Probar el caso para el que la arquitectura existe

Un corpus donde el brazo monolítico **no pueda correr**: material que exceda la
ventana del nodo. Ahí la pregunta deja de ser "¿cuánto cuesta partir?" y pasa a
ser "¿es esto factible de alguna otra forma?". Si la respuesta es que no, el
costo de calidad es el precio de existir, no una pérdida.

Es también la única forma de que ρ signifique algo: hoy ρ = 4 dice que pagamos
cuatro veces los tokens por un resultado peor. Con material que no cabe, ρ es la
razón por la que el resultado existe.

### b. Medir los ejes donde fragmentar debería ganar

Tokens por nodo, memoria pico por nodo, y **factibilidad**: ¿corrió o no corrió?
Ninguno está instrumentado hoy.

### c. Separar capacidad del modelo de arquitectura

Un brazo con un modelo grande. Si `must_mention` sube y `no_repeated_ngram` se
queda donde está, la parte atribuible a la arquitectura es más chica de lo que
hemos venido reportando — y la parte irreducible es más grande.

### d. Correr la mejor configuración conocida, junta

Nunca se ha hecho: **N=2**, `term_once` en el ensamblador, sin asignación
exclusiva, con el brief de un párrafo por fragmento. Cada pieza se midió por
separado y ninguna corrida las tiene todas.

### e. Una compuerta simétrica

Algo que marque un resultado sospechosamente **favorable** con la misma dureza
con que hoy se marca uno inválido.

---

## 5. La respuesta corta a la pregunta

**No hay sesgo en los instrumentos** — varios corrigen en favor de la
arquitectura y están documentados.

**Sí hay un sesgo en el encuadre**, y es este: durante tres semanas evaluamos
Swarmbly únicamente en el eje donde fragmentar sólo puede perder, sobre tareas
que nunca necesitaron fragmentarse. Eso no fue una decisión que alguien tomara;
fue una que nadie tomó, y tenía que haberse visto antes.

El fundamento no ha sido refutado. **Ha sido no probado.**
