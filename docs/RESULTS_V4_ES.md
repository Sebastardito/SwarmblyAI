---
status: partially_withdrawn
stands: las cifras de exactitud, acuerdo y restricciones
reason: >
  Todo impuesto de coherencia y toda afirmación de monotonía en N los produjo
  una métrica que no era neutral entre brazos y cuya penalización crecía con N
  por construcción.
lang: es
---
# V4 — el tamaño efectivo de un fragmento semántico

> ## ⚠ Las cifras de impuesto de coherencia de este documento están SUPERADAS (27 de agosto de 2026)
>
> La métrica que las produjo no era neutral entre brazos. La línea base
> monolítica se medía contra un conjunto de entidades esperadas más pequeño que
> el del brazo fragmentado, sus omisiones ensuciaban una frase donde las del
> brazo fragmentado ensuciaban N, y no podía incurrir en un error de costura en
> absoluto — así que la penalización crecía con N por construcción. Puntuar una
> misma respuesta idéntica bajo ambas convenciones da 0.9375 contra 0.5000. Todo
> impuesto de coherencia y toda afirmación de "monótono en N" más abajo están
> afectados; las cifras de exactitud, acuerdo y restricciones no lo están.
>
> `scripts/rescore.py <run>` recalcula el impuesto de una corrida terminada con
> la métrica corregida a partir de las propias respuestas ensambladas de la
> corrida — pero solo para corridas cuyas trazas guardan los desplazamientos de
> frase del ensamblador, cosa que ninguna escrita antes del 27 de agosto hace.
> Para esas, la cifra corregida solo puede venir de volver a correrlas.


**Corrida:** `results/v4-20260824-175122`. Cinco familias de modelos sobre
Ollama, transporte `openai-sdk`, 0 reintentos de transporte, embeddings no
degradados, `tau_sem` calibrado a 0.575 a partir de 108 pares etiquetados.
ρ ∈ {2.0, 3.0}, N ∈ {2, 4, 6, 8}, k ∈ {1, 3}, nueve prompts sobre tres formas de
tarea, 72 celdas fragmentadas por N.

Tres predicciones se escribieron en `scripts/run_ollama.sh` antes de la corrida.
Dos quedan confirmadas, una queda confirmada incluyendo su rechazo, y un eje de
la medición no es interpretable y se reporta como tal.

---

## 1. El costo cae con el tamaño del fragmento, de forma monótona

Reexaminar la corrida V0 del 14 de agosto encuentra en ella un resultado
durable: el impuesto de coherencia sube a medida que los fragmentos se hacen más
pequeños. Nunca se había probado por encima de 133 tokens canónicos por
fragmento, porque ningún corpus era lo bastante largo para producir uno más
ancho, y toda corrida posterior fijó N y barrió `k` en su lugar.

| N | tokens por fragmento | impuesto de coherencia | celdas |
|---|---|---|---|
| 2 | 224 | **+18.5 %** | 72 |
| 4 | 112 | +41.3 % | 72 |
| 6 | 75 | +47.1 % | 72 |
| 8 | 56 | +59.0 % | 72 |

Monótono, `comparable_across_n: true` — las tres formas de tarea contribuyen a
cada punto, así que ninguna parte de la tendencia es un cambio en aquello de lo
que el punto está hecho. Esta es la primera medición del efecto sobre un corpus
construido para expresarlo.

**Consecuencia inmediata para el planificador.** `suggest_n_tasks` fija en el
código una microtarea por cada **60 tokens canónicos**, una constante que nunca
se ha validado contra nada. Sobre este corpus, 60 tokens por fragmento quedan
entre las filas N=6 y N=8 — un impuesto de coherencia de alrededor de **+50 %**.
La curva medida dice que los fragmentos deberían ser unas cuatro veces más
grandes.

## 2. S\* no es un número — es una propiedad de la forma de la tarea

Esta era la afirmación más aguda, y es la que la corrida responde con mayor
claridad. Léase el fragmento más ancho, donde las tres formas tienen el mayor
contexto que llegarán a tener en este barrido:

| N | tokens/fragmento | dependency_chain | long_prose | table_summary |
|---|---|---|---|---|
| 2 | 224 | **+47.2 %** | **+5.1 %** | **+3.3 %** |
| 4 | 112 | +76.2 % | +19.4 % | +28.3 % |
| 6 | 75 | +74.2 % | +28.7 % | +38.2 % |
| 8 | 56 | +76.2 % | +48.8 % | +51.9 % |

Con 224 tokens por fragmento, la prosa y el resumen de tablas son **casi gratis
de fragmentar** — 5.1 % y 3.3 %, en el umbral que el proyecto persigue desde
agosto o por debajo de él. Con el mismo tamaño de fragmento, la cadena de
dependencias ya cuesta 47.2 %: de diez a catorce veces más, sobre fragmentos de
tamaño idéntico.

Un solo conteo de tokens no puede describir a las dos. El fragmento efectivo es
la **unidad semántica** — un tema, un grupo de filas, un paso — y las unidades
de la cadena están ordenadas, así que una frontera de paquete no divide
meramente el trabajo: corta un valor que el paso siguiente necesita.

La exactitud de la cadena dice lo mismo en el otro eje, y es la única serie de
exactitud monótona y limpia de la corrida: **0.259 → 0.219 → 0.143 → 0.091** a
medida que los fragmentos se encogen. Su impuesto se satura luego cerca de
+76 % desde N=4 en adelante, que es lo que parece una cadena rota: una vez que
el valor acarreado se pierde, perderlo otra vez no cuesta nada más.

**No existe S\* para la cadena de dependencias en el rango probado** — y la
razón resultó no ser en absoluto el tamaño del fragmento.

Rastrear después un paquete de cadena a través del empaquetador mostró que con
ρ = 2.0, el valor que usó esta corrida, **ningún paquete llevaba un bloque de
predecesor**. El bloque era contexto opcional, tercero en prioridad detrás del
encabezado del contrato y de la nota de longitud, financiado con la holgura que
quedara después del texto de la tarea — y la holgura se acabó primero. A cada
sucesor se le entregó "divide el valor neto del paso 2" sin nada sobre lo que el
paso 2 produjo. El paquete era imposible de responder por construcción.

Así que las cifras de arriba son reales pero se leyeron mal cuando se escribieron
por primera vez. No son el precio de fragmentar una tarea ordenada; son el precio
de fragmentarla *soltando el acarreo*. La saturación cerca de +76 % desde N=4 en
adelante es la firma: una vez que el valor acarreado desaparece, perderlo otra
vez no cuesta nada más.

De ahí siguen dos cambios, y son separables. El acarreo es ahora **obligatorio**
para una tarea cuyo texto consume un valor previo — en pie de igualdad con el
texto de la tarea, en lugar de competir con el glosario por la holgura. Y es
**tipado**: todo valor etiquetado que el fragmento produjo, donde
`summarize_fragment` conservaba la frase inicial y descartaba el resto en
silencio, de modo que un fragmento que cubría los pasos 3 a 5 le entregaba a su
sucesor el paso 3 y una lista de entidades.

La completitud se compra, no se encuentra: 10 tokens contra 4 en un fragmento
escueto. Un primer borrador del mecanismo predijo que ρ *caería*, con el
razonamiento de que un número es más barato que la prosa. La medición dijo otra
cosa — el resumen en prosa es barato precisamente porque es incompleto — y se
corrigió la predicción, no la medición.

La re-ejecución con ambos cambios es lo que resuelve si una cadena ordenada es
cara siquiera.

## 3. El editor repara la forma y no toca el hecho — exactamente como se predijo

144 celdas emparejadas, cada celda editada con una gemela sin editar en el mismo
prompt, N y k.

| medida | valor |
|---|---|
| tasa de aplicación | 52.1 % (75 de 144) |
| ganancia media de restricción | **+15.4 %** de las comprobaciones mecánicas recuperadas |
| delta medio del impuesto de coherencia | **−2.6 %** |
| exactitud por ítem, sin editar | 0.3804 |
| exactitud por ítem, editada | **0.3804** |
| **delta de exactitud** | **0.000** |
| tokens por edición | 671 |

La predicción era que las puntuaciones de restricción subirían y la exactitud por
ítem **no**, porque el editor tiene la respuesta ensamblada y el contrato y no
tiene acceso al material fuente. La exactitud se movió exactamente cero a lo
largo de 144 pares. De haber subido, el brazo habría quedado contaminado — el
editor respondiendo desde su propio conocimiento en lugar de editar — y la
ganancia de restricción no habría valido nada.

Ambos rechazos se dispararon con datos reales: **19 revisiones rechazadas por
puntuar peor** y **1 rechazada por introducir una cifra sin respaldo**. El
primero es la compuerta que el puente nunca tuvo; sin ella el editor habría
cambiado dimensiones no medidas por dimensiones medidas, que es precisamente
como la síntesis de puente rompió una restricción de `paragraph_count` el 25 de
agosto.

ρ no cambia por construcción — el editor nunca ve el prompt del problema — así
que los 671 tokens se reportan como su propia línea de presupuesto en lugar de
plegarse dentro de él.

## 4. La agregación es una clase de fallo distinta

Las respuestas equivocadas en el resumen de tablas no son artefactos de la
calificación. Son invenciones:

> "El envío más pesado es el que viene de Mombasa, con un peso de 935 kg, y el
> peso total de todos los envíos es de 1650 kg."

Un total de 1650 kg sobre veinte filas una de las cuales pesa 935 kg no es una
mala lectura, es una fabricación. Otras son peores — "un contenedor de 500
toneladas, mientras que el artículo más liviano es un paquete de 10 toneladas" —
en unidades que la tabla no usa.

Separando las afirmaciones según si aseveran un agregado (un total, un promedio,
el más pesado o el más liviano — cualquier cosa que requiera ver filas que el
fragmento no tiene):

| tipo de afirmación | erradas | tasa |
|---|---|---|
| asevera un agregado | 74 / 155 | **47.7 %** |
| no asevera nada agregado | 32 / 101 | 31.7 % |

Fisher exacto **p = 0.014**. Un trabajador al que se le pide el total mientras
tiene un tercio de la tabla no se abstiene; inventa. Este es un fallo que la
arquitectura predice y que el mapa de confianza debería poder atrapar, y es un
mejor objetivo para el próximo intento de calibración que cualquier cosa probada
hasta ahora — la predicción está disponible, es mecánica, y las dos clases
difieren.

## 5. El go/no-go ahora falla, que es de lo que se trata

El criterio de éxito se ha reformulado. La forma anterior -- "existe una celda
(categoría, ρ) por debajo del 5 %" -- es un estadístico máximo sobre muchas
celdas ruidosas sin control de comparaciones múltiples, y barajar observaciones
entre celdas bajo la hipótesis nula de que ninguna difiere lo satisface
esencialmente siempre. Un criterio que se cumple con casi certeza por
construcción no reporta nada sobre el mundo.

El reemplazo nombra su celda **por adelantado** y exige que la **cota superior**
de un intervalo bootstrap supere el umbral.

Con el fragmento más ancho, N=2:

| celda | ρ | estimación puntual | IC del 95 % | pasa |
|---|---|---|---|---|
| table_summary | 2.0 | +3.1 % | [−3.5 %, +10.3 %] | **no** |
| table_summary | 3.0 | +3.4 % | [−3.1 %, +10.6 %] | **no** |
| long_prose | 3.0 | +4.2 % | [+0.6 %, +7.8 %] | **no** |
| long_prose | 2.0 | +6.0 % | [+1.1 %, +12.2 %] | no |
| dependency_chain | 2.0 | +62.5 % | [+43.8 %, +81.3 %] | no |

`table_summary` tiene una estimación puntual **por debajo del 5 %** en ambos
valores de ρ. Un criterio que leyera solo estimaciones puntuales declararía un
pase con eso — y esta es exactamente la situación que la reformulación existe
para atrapar, porque con n = 12 el intervalo va de −3.5 % a +10.3 % y no
resuelve nada.

La afirmación honesta es: **dos de las tres formas de tarea están plausiblemente
por debajo del umbral con 224 tokens por fragmento, y la corrida no tiene la
potencia para establecerlo.** Más observaciones en esas dos celdas lo
resolverían; nada más necesita cambiar.

## Qué *no* es interpretable en esta corrida

**La exactitud frente al tamaño del fragmento, agrupada.** La serie balanceada es
0.480, 0.484, 0.249, 0.388 — no monótona. Los denominadores detrás de ella
oscilan de 38 a 90 ítems calificados sobre 336 a 466 unidades, porque cuántas
frases contienen una cifra varía con el tamaño del fragmento. Una razón cuyo
denominador se mueve por motivos ajenos a la hipótesis no es una medición de la
hipótesis. La exactitud por forma para `dependency_chain` es monótona y se
reporta arriba; la serie agrupada no lo es, y no se usa.

**El desglose por N de la tasa de fabricación.** La brecha entre afirmaciones
agregadas y no agregadas es sólida sobre la corrida entera (p = 0.014). Separada
por N descansa sobre tan solo 6 afirmaciones agregadas en una celda, y no se
reporta.

## Qué cambia esto

1. **La constante de 60 tokens del planificador está equivocada por
   aproximadamente 4×** con esta evidencia, y debería reemplazarse por un valor
   medido — por forma de tarea, no globalmente.
2. **Las cargas de prosa y de tablas pueden estar ya por debajo del umbral** con
   fragmentos grandes. Esa celda merece las observaciones necesarias para
   resolverla.
3. **La cadena de dependencias necesita un mecanismo, no un parámetro.** Ningún
   tamaño de fragmento en el rango probado la hace asequible.
4. **El editor se gana su lugar**: 15 % de las comprobaciones mecánicas
   recuperadas, una pequeña reducción del impuesto de coherencia, efecto cero
   sobre la corrección, por 671 tokens fuera del presupuesto de ρ.
5. **La agregación es el próximo objetivo de calibración**, y a diferencia de
   los seis intentos saturados que la precedieron, las dos clases que separa sí
   difieren.
