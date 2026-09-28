---
status: current
lang: es
---

# Resultados de la confirmación — H-INT no sobrevive

**25 de septiembre de 2026 · ejecuta `PREREGISTRATION_2026-09-25_interaction_ES.md`**

Corpus: `swarmbly_ref/data/benchmark.jsonl`, sha256 `d94bb9cc7694d0f7…`,
verificado contra el preregistro antes de correr. 123 celdas comparables, 20
tareas, 5 modelos.

---

## 1. El resultado, sin rodeos

**H-INT está muerta, y murió por la razón exacta que el preregistro anticipó.**

| prueba | ρ | p | H-INT predice |
|---|---|---|---|
| **Primaria — fuerza LOO vs impuesto** | **−0.078** | 0.192 | ρ > 0 |
| Control de longitud (§4.2) | −0.370 | 0.009 | ρ > 0 |
| Control de techo (§4.3) | −0.075 | 0.211 | ρ > 0 |
| Ambos controles | −0.374 | 0.007 | ρ > 0 |

La prueba primaria no da nada, y donde da algo el signo es el contrario del
predicho. Por la condición de muerte de §6, **el hallazgo se retira**.

---

## 2. Por qué apareció: el estadístico se lo inventa solo

El preregistro (§3) advirtió que `impuesto = 1 − frag/mono` lleva `mono` en el
denominador y que correlacionarlo con el `mono` de la misma celda produce
asociación por construcción. La medición lo confirma de tres maneras:

| | ρ |
|---|---|
| Spearman(`mono` de **la misma celda**, impuesto) | **+0.675** |
| Spearman(**fuerza LOO independiente**, impuesto) | **−0.078** |
| **Simulación: `frag` y `mono` sorteados independientes** | **+0.684** |

La última fila es la prueba decisiva. Con datos donde **por construcción no
existe ninguna relación**, el estadístico devuelve +0.684 — prácticamente
idéntico al +0.675 observado. **La «interacción» la genera la fórmula, no los
datos.**

Y el barrido de umbral falla su condición de muerte declarada: el signo del
estrato fuerte cambia dentro del rango intercuartílico (−7.2 % con corte en
0.446; +8.3 % con corte en 0.673). No hay dos regímenes; hay un gradiente
fabricado por el denominador.

**La tabla estratificada no se publica.**

---

## 3. Cómo se produjo el error

El hallazgo se encontró **explorando** los datos, y se presentó como resuelto
antes de confirmarlo: en la revisión del 25 de septiembre se describió como «el
hallazgo que el contexto destrabó», se afirmó que resolvía una objeción abierta
y se dijo que cambiaba el enunciado del proyecto.

No lo hace. Es la **quinta aparición** del defecto recurrente de este proyecto
—*una comprobación que afirma más de lo que midió*— y apareció en el mismo
documento que reprochaba ese defecto en otras mediciones. Esa reincidencia es
informativa: el defecto no lo produce el descuido, lo produce la estructura del
análisis, y por eso la defensa tiene que ser estructural.

Lo que funcionó fue el preregistro: escribir el defecto sospechado y el diseño
que lo rompe **antes** de correr. Con el umbral elegido a ojo y el estadístico
acoplado, el análisis habría confirmado el error con números grandes y un
intervalo que excluía el cero.

---

## 4. Lo que sí sobrevive: el confundido de longitud

La misma sospecha se aplicó a la otra afirmación abierta —que el impuesto
agregado está confundido con la longitud de salida—. **Ésa sí aguanta las tres
pruebas.**

| | ρ | lectura |
|---|---|---|
| Spearman(razón de longitud, impuesto) | −0.575 | la observación original |
| Suelo del artefacto (impuesto permutado) | **+0.125** | lo que la forma del estadístico produce sola: pequeño y de signo contrario |
| **Spearman(razón, `frag − mono`)** — sin denominador | **+0.595** | misma magnitud, estadístico limpio |
| **Spearman(palabras_frag, score_frag) INTRA-tarea** | **mediana +0.683**, positivo en **16 de 18 tareas** | prueba directa |

La última fila es la que cierra el asunto: **dentro de una misma tarea, escribir
más puntúa más**, en 16 de 18 tareas. El brazo fragmentado escribe 1.39× más
(mediana), y eso basta para explicar buena parte de su ventaja.

Contraste que conviene tener a la vista: con el estadístico limpio, la longitud
da +0.595 y la fuerza del nodo da **+0.068**. Uno es un efecto; el otro es ruido.

---

## 5. Estado real de la evidencia, tras la confirmación

**No afectado** (y es la mayor parte):

- **T07R** — el experimento controlado de M4: ρ constante, los dos brazos
  fragmentados, δ variado por calidad de corte. La crítica de longitud nunca
  aplica aquí: los dos brazos escriben con el mismo presupuesto. δ sube en 32/32, el impuesto empeora en 19/32. **Sigue siendo la
  mejor prueba del conjunto y sigue siendo negativa para M4.**
- **T04R** — 127 celdas intra-categoría, ρ = −0.13. Converge con la medición
  independiente sobre `tables24` (ρ = −0.456).
- **T05R** ρ escalado, **T06R** instrumento del corpus, **T02R** triaje,
  **T0R** router contra la verdad, **T0LR** L por clase, **T10R** alineador.
- **T0RR** enrutabilidad: sigue en FAIL (AUC 0.38–0.47).

**Afectado:**

- **T09R** — el impuesto agregado está confundido con la longitud de salida. El
  −18.32 % no es interpretable tal cual, y **no hay ninguna interacción que lo
  rescate**: la que se propuso está retirada por este mismo documento.

---

## 6. Qué se puede afirmar hoy

> El instrumento funciona y está auto-verificado. M4 queda falsado en dos
> instrumentos independientes, con un experimento controlado a ρ constante. El
> router queda refutado a nivel de celda. La ley de escala de ρ se verifica
> contra datos reales. **La factibilidad no se puede afirmar todavía: la ventaja
> medida de fragmentar está confundida con el presupuesto de salida, y hasta
> igualarlo el criterio no se ha cumplido ni incumplido — no se ha medido.**

Es menos triunfal que «criterio cumplido, −18 %» y es lo que los datos
sostienen. También es publicable: un instrumento propio y verificado, dos
modelos falsados, un router refutado por celda y una ley de escala verificada
son un resultado, aunque ninguno de los cuatro sea el que se esperaba.

---

## 7. Lo que falta, y es barato

Una corrida con **presupuesto de salida igualado** entre brazos: el monolítico
recibe `max_tokens = T`, el fragmentado recibe `T` repartido entre sus
fragmentos. Con eso, el impuesto medido responde a la fragmentación y no a la
verbosidad.

El comando es `run_benchmark.py --matched`. Con el resume por key cuesta minutos
de cómputo, no horas.

---

## 8. Enmiendas al preregistro

Ninguna. El diseño se ejecutó como estaba escrito, incluida la condición de
muerte que lo mató.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Compañero en inglés:
`RESULTS_2026-09-25_interaction_EN.md`. Preregistro:
`PREREGISTRATION_2026-09-25_interaction_ES.md`.*
