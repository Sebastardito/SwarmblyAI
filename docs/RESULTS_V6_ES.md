---
status: partially_withdrawn
stands: las cifras de exactitud, acuerdo y restricciones
reason: >
  Todo impuesto de coherencia y toda afirmación de monotonía en N los produjo
  una métrica que no era neutral respecto del brazo y cuya penalización crecía
  con N por construcción.
lang: es
---
# V6 — la primera ejecución cuyo instrumento se revisó antes de correrla

> ## ⚠ Las cifras de impuesto de coherencia de este documento están SUPERADAS (27 de agosto de 2026)
>
> La métrica que las produjo no era neutral respecto del brazo. A la línea base
> monolítica se la sujetaba a un conjunto de entidades esperadas más pequeño que
> al brazo fragmentado, sus omisiones ensuciaban una oración donde las del brazo
> fragmentado ensuciaban N, y no podía incurrir en ningún error de costura — así
> que la penalización crecía con N por construcción. Puntuar una misma respuesta
> idéntica por ambas convenciones da 0.9375 frente a 0.5000. Todo impuesto de
> coherencia y toda afirmación de «monótono en N» de más abajo están afectados;
> las cifras de exactitud, acuerdo y restricciones no.
>
> `scripts/rescore.py <run>` recalcula el impuesto de una ejecución terminada con
> la métrica corregida a partir de las respuestas ensambladas de la propia
> ejecución — pero solo para ejecuciones cuyas trazas guardan los offsets de
> oración del ensamblador, cosa que no hace ninguna escrita antes del 27 de
> agosto. Para esas, la cifra corregida solo puede salir de volver a ejecutarlas.


**Ejecución:** `results/v4-20260825-184625`. Veinte prompts en tres formas de
tarea, cinco familias de modelo sobre Ollama, transporte `openai-sdk`, **0
reintentos de transporte**, embeddings no degradados, τ_sem calibrada en 0.580 a
partir de 240 pares etiquetados. ρ ∈ {3.5, 4.5}, N ∈ {2, 4, 6, 8}, k ∈ {1, 3},
brazos de editor y de acarreo tipado, ambos emparejados. 1 280 filas
fragmentadas, ~16 horas.

Esta es la primera ejecución precedida por una revisión adversarial del harness.
Se encontraron y corrigieron de antemano nueve defectos, cinco de los cuales
habrían dejado los números sin significado. Dos consecuencias dominan todo lo
que sigue.

---

## 1. Arreglar el instrumento redujo aproximadamente a la mitad el costo medido

Los fragmentos de `long_prose` venían recibiendo una directiva de hoja de
respuestas en lugar de su propio bloque de formato, así que el contrato de ocho
párrafos, de 70 a 130 palabras y de mención única llegaba a **ningún fragmento**
mientras que la línea base monolítica lo conservaba entero. Con eso corregido:

| N | tokens/fragmento | dependency_chain | long_prose | table_summary |
|---|---|---|---|---|
| 2 | 228 | +21.2 % | **+9.7 %** | **+5.8 %** |
| 4 | 114 | +55.1 % | +12.6 % | +11.8 % |
| 6 | 76 | +77.0 % | +15.4 % | +10.8 % |
| 8 | 57 | +100.0 % | **+20.0 %** | **+12.1 %** |

Monótono, `comparable_across_n: true`, una celda limpia por punto (ρ=3.5, k=1,
sin editor, sin acarreo).

Frente a las cifras de V5 con N=8 — `long_prose` +41.4 %, `table_summary`
+49.0 % — ambas se reducen aproximadamente a la mitad. **V4 y V5 estaban midiendo
un contrato ausente, no un costo de fragmentación.** El orden entre formas
sobrevive: a igual tamaño de fragmento, la cadena ordenada sigue costando varias
veces lo que cuestan la prosa o las tablas.

## 2. La corrección del corpus de cadenas funcionó, y el compuesto de ε se ve por primera vez

Reemplazar los dos pasos de porcentaje — que la clase de 2–4B fallaba al 3.6 % y
al 0.0 % sin importar el contexto — llevó la exactitud de cadena de **0.303 a
0.719**. El instrumento ya discrimina, y lo que muestra es la forma que predice
el argumento de dependencia:

| paso | exactitud | n |
|---|---|---|
| 1 | 100.0 % | 84 |
| 2 | 94.4 % | 71 |
| 3 | 80.4 % | 46 |
| 4 | 81.8 % | 33 |
| 6 | 16.0 % | 25 |
| 7 | 8.3 % | 24 |
| 8 | 0.0 % | 22 |

Eso es 1 − (1 − ε)^D vuelto visible: casi perfecto en profundidad 1, decayendo
por el medio, colapsado para la profundidad 6. Todo intento anterior de ver esto
quedó bloqueado por un paso que los modelos no podían computar en absoluto.

Dos cosas de la tabla son hallazgos en sí mismas. Los denominadores **caen con la
profundidad** — de 84 a 22 — así que una cadena no solo responde mal los pasos
posteriores, sino que cada vez más deja de producir una respuesta parseable. Y el
paso 5 está ausente porque quedó por debajo del umbral de reporte, que es el
mismo fenómeno.

## 3. El acarreo tipado: sigue sin ser resoluble, y ahora honestamente

| N | plano | tipado | delta |
|---|---|---|---|
| 2 | 78.9 % (45/57) | 86.5 % (45/52) | **+7.6** |
| 4 | 50.0 % (7/14) | 58.3 % (7/12) | **+8.3** |
| 6 | 79.1 % (34/43) | 64.5 % (40/62) | **−14.6** |
| 8 | 59.4 % (19/32) | 56.0 % (28/50) | −3.4 |

Agrupado: −0.037. Pero la cifra agrupada es una **mezcla de signos opuestos**, no
un efecto: el acarreo ayuda en particiones gruesas y perjudica en las finas,
sobre 12 a 62 registros por celda. Aquí nada es resoluble con este tamaño de
muestra, y reportar −0.037 como «el acarreo no funciona» sería leer ruido.

Los controles se comportan. `table_summary` se mueve en −0.003 — no hay nada que
tipar donde las respuestas no llevan etiquetas. ρ se mueve en −0.002, así que el
mecanismo ni compra ni gasta contexto.

Una observación que vale la pena llevar adelante: el brazo tipado produce **más**
registros calificados con N=6 y N=8 (62 frente a 43, 50 frente a 32). El filtro
de alcance añadido antes de esta ejecución impide que a un fragmento se le
acredite un ítem fuera de su paquete, así que son respuestas dentro de alcance —
el acarreo hace que los sucesores *respondan más*, y en particiones finas esas
respuestas adicionales son desproporcionadamente incorrectas.

**El brazo de cadena necesita su propia ejecución.** Cuatro prompts son muy pocos
para un diseño de ocho pasos × cuatro N, y es la parte del corpus más barata de
ejecutar por separado.

## 4. Un defecto en el criterio de continuar o abandonar, obra mía

El criterio filtraba por categoría y por ρ pero **no por N** — y N es el eje con
mucho el mayor efecto. Agrupado sobre N, `table_summary` con ρ=3.5 marca +20.9 %
y falla con holgura. Restringido a N=2, el tamaño de fragmento sobre el que en
realidad versa la pregunta del umbral:

| celda | puntual | IC del 95 % | pasa |
|---|---|---|---|
| table_summary @ ρ3.5, N=2 | **+5.8 %** | [−2.2 %, +14.5 %] | no |
| long_prose @ ρ3.5, N=2 | +9.7 % | [+3.8 %, +16.2 %] | no |
| dependency_chain @ ρ3.5, N=2 | +21.2 % | [+15.6 %, +25.0 %] | no |

Un criterio escrito para impedir que un estadístico máximo pasara por ruido
estaba él mismo **escondiendo al único candidato vivo dentro de una media**.
`n_tasks` ya forma parte de la celda declarada y un test codifica el caso.

`table_summary` con el fragmento más ancho sigue siendo el único candidato que
alguna vez se ha acercado, y sigue sin decidirse — ahora sobre n = 8, porque
rebanar correctamente cuesta muestra. Ese es el estado honesto: ni un pase ni una
refutación, y la pregunta más estrecha que le queda al proyecto.

## 5. El editor replica y se fortalece

| medida | V5 (320 pares) | V6 (640 pares) |
|---|---|---|
| tasa de aplicación | 61.6 % | 67.7 % |
| ganancia media de restricciones | +14.9 % | **+21.0 %** |
| delta de exactitud | −0.003 | **+0.0006** |

El rechazo se mantiene con el doble de muestra y la ganancia es mayor ahora que
los fragmentos reciben las restricciones contra las que el editor repara.
Recupera una quinta parte de las comprobaciones mecánicas y mueve la corrección
por ítem en nada, que es exactamente lo que debería hacer un mecanismo que tiene
la respuesta y el contrato pero no la fuente.

## 6. El «colapso del acuerdo» era mi aritmética — y lo que estaba tapando

*Escrito a posteriori, a partir de los artefactos de la propia ejecución. Las
cifras publicadas primero en esta sección fueron:*

| clase de afirmación | n | exactitud | acuerdo medio | AUC |
|---|---|---|---|---|
| agregada | 2 359 | 57.0 % | 0.392 | 0.583 |
| local | 6 041 | 93.9 % | 0.391 | **0.477** |

**Ambas cifras de acuerdo eran constantes, no mediciones.** Dos poblaciones cuya
exactitud difiere en 37 puntos no pueden coincidir hasta el tercer decimal; eso
es un valor por defecto anunciándose, y yo lo publiqué como un fenómeno.

La causa es una corrección que hice antes de esta ejecución. Con k=1 no se habían
producido registros calificables en absoluto, así que el brazo fragmentado se
calificaba solo con k=3 mientras que la línea base es una sola generación —
fragmentación y consenso eran inseparables. Calificar k=1 era lo correcto. Lo que
vino con ello fue un `agreement` de una sola réplica de **0.0**, bajo un
comentario que afirmaba que eso lo «mantiene fuera de toda calibración por
construcción». Nada lo mantuvo fuera. 0.0 es una puntuación de acuerdo legal, así
que **8 984 filas — el 45 % de la masa calificada — entraron en la calibración
como sus ítems menos confiables.**

Restringido a k = 3, donde el acuerdo está definido:

| clase de afirmación | n | prompts | exactitud | acuerdo medio | AUC | IC del 95 % (por prompt) |
|---|---|---|---|---|---|---|
| agregada | 1 137 | 8 | 65.5 % | **0.813** | 0.481 | [0.414, 0.541] |
| local | 3 210 | 8 | 92.2 % | **0.736** | 0.616 | [0.508, 0.712] |

El 0.836 y el 0.699 de V5 — **replicados**. No hubo colapso.

El AUC por debajo del azar tiene el mismo origen y vale la pena enunciarlo
aparte, porque es otra vez el artefacto de agrupar, por quinta vez. El bloque
empatado en cero era **correcto en un 95.8 %** frente al 92.2 % de las filas con
k=3. Una masa de ítems *correctos* clavados al fondo de la escala de acuerdo
arrastra el estadístico por debajo de 0.5. El instrumento no estaba mal
calibrado; se le estaba preguntando por una variable que no existía para la mitad
de sus entradas.

**Lo que sobrevive a la corrección es más pequeño que lo que afirmaba cualquiera
de las dos versiones.** Con los intervalos remuestreados sobre prompts en lugar
de sobre oraciones — 8 prompts, no 8 400 oraciones:

* **las afirmaciones locales replican, débilmente.** AUC 0.616 [0.508, 0.712]
  frente al 0.660 [0.540, 0.771] de V5. La curva es monótona (72.7 % → 88.9 % →
  92.5 % → 94.7 %), pero todo el rango son 22 puntos y el 48 % de la masa está en
  el bin superior. Restricción de rango, exactamente como en V3c.
* **las afirmaciones agregadas no.** AUC 0.481 [0.414, 0.541] — **en el azar**,
  frente al 0.605 [0.537, 0.654] de V5. La curva ya no es monótona: 16.7 % →
  58.2 % → 78.8 % → **62.2 %**, y la caída está en el bin superior, que contiene
  el 59 % de los ítems. El acuerdo alto dejó de predecir la corrección para las
  afirmaciones que más importan.

Esa no replicación es un resultado real y es el que hay que llevar adelante.
Descansa sobre ocho prompts, y por eso la §*Lo que sigue* empieza ahora por el
corpus.

**Corregido.** `agreement` es `None` donde no está definido;
`agreement_truth_calibration` excluye los registros de una sola réplica por `k` y
no por el valor — un centinela de 0.5 habría pasado un filtro por valor — y
reporta `excluded_single_replica` junto a los demás denominadores.
`tests/test_instrument.py` inyecta el fallo con tres centinelas distintos y falla
si alguno llega al estadístico.

## Lo que sigue

1. **Veinticuatro prompts de tablas, divididos antes de ajustar nada.**
   `prompts/tables24.json`, construido por `scripts/make_tables.py`: 8 de dev /
   16 finales, intercalados, con un SHA-256 en el archivo y `--verify` para
   comprobarlo. Los umbrales, los bordes de los bins, las tasas de marcado y
   τ_sem se ajustan sobre dev; el final se evalúa una sola vez. Todo intervalo de
   más arriba descansa sobre 8 prompts, y también lo hace el único candidato vivo
   a umbral.
2. **`table_summary` con ρ=3.5, N=2** es ese candidato: +5.8 %, intervalo
   [−2.2 %, +14.5 %]. Dieciséis prompts más lo reducen aproximadamente a la
   mitad.
3. **Ejecutar la cadena sola.** Cuatro prompts y ocho pasos no pueden responder
   la pregunta del acarreo; las cadenas son además la rebanada más barata de
   ejecutar, unas dos horas.
4. **El AUC agregado no replicó.** 0.605 → 0.481, en el azar, con una curva no
   monótona. Esa es ahora la pregunta de calibración, y reemplazó a la que yo
   creía tener.
5. **Las cifras de prosa y de tablas de V4 y V5 quedan superadas**, no refinadas.
   Midieron fragmentos que nunca recibieron su contrato. Las cifras de acuerdo de
   V5, en cambio, se sostienen — las equivocadas eran las de V6.
