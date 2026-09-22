---
status: partially_withdrawn
stands: las cifras de exactitud, acuerdo y restricciones
reason: >
  Todo impuesto de coherencia y toda afirmación de monotonía en N los produjo
  una métrica que no era neutral respecto del brazo y cuya penalización crecía
  con N por construcción.
lang: es
---
# V5 — potencia, el acarreo tipado, y dónde el mapa de confianza por fin tiene señal

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

> ## ⚠ También SUPERADO: el resultado del mapa de confianza de este documento
>
> El aviso de arriba exime a las cifras de acuerdo. **Esa exención ya no se
> sostiene**, y el título de este documento y la sección 3 son la razón por la
> que se enuncia aparte. El «primer resultado positivo que el mapa de confianza
> ha tenido jamás» era una razón de momios común de Mantel-Haenszel de 3.47 sobre
> afirmaciones agregadas. Dos ejecuciones posteriores sobre el estimador
> declarado devolvieron **0.26** y luego **1.24, IC [0.25, 3.75]** — por debajo
> de 1, y luego a horcajadas sobre 1 en la muestra más grande. Tres estimaciones
> que abarcan un orden de magnitud con signos inconsistentes no son una señal que
> necesite más datos; son ninguna señal, medida tres veces.
>
> El mapa de confianza queda por tanto **retirado** — no degradado, no a la
> espera de réplica — y fuera del banco de pruebas de V7. Léase la sección de
> acuerdo de este documento como la primera de tres mediciones que discrepan
> entre sí, y no se cite su razón de momios como un resultado. La afirmación de
> la sección 3 de que «retirar el mapa de confianza con la evidencia anterior
> habría sido un error» se deja en pie porque era una lectura justa en su
> momento; la conclusión que defiende, no. El cuerpo de abajo queda inalterado,
> porque un resultado retirado que ha sido borrado no se puede revisar.


**Ejecución:** `results/v4-20260824-214220`. Veinte prompts en tres formas de
tarea, cinco familias de modelo sobre Ollama, transporte `openai-sdk`, 0
reintentos de transporte, embeddings no degradados, τ_sem calibrada en 0.575.
ρ ∈ {2.0, 3.0}, N ∈ {2, 4, 6, 8}, k ∈ {1, 3}, brazos de editor y de acarreo
tipado, ambos emparejados. 320 celdas fragmentadas por N — cuatro veces el
conteo de V4.

Había tres preguntas abiertas. Una queda respondida y la respuesta es negativa,
otra es **inconcluyente porque el instrumento estaba mal**, y otra produjo el
mejor resultado que el mapa de confianza ha tenido jamás.

---

## 1. La pregunta del umbral queda respondida, y de forma menos amable de lo que V4 sugería

V4 dejó dos formas que parecían plausiblemente por debajo del umbral de 5 % de
degradación de coherencia. Cuadruplicar las observaciones debía zanjarlo, y lo
zanjó.

| celda | ρ | V4 (n=12) | V5 (n=64) | IC del 95 % | pasa |
|---|---|---|---|---|---|
| table_summary | 3.0 | +3.4 % | **+2.7 %** | [−0.7 %, +6.3 %] | no |
| table_summary | 2.0 | +3.1 % | +6.5 % | [+2.1 %, +10.9 %] | no |
| long_prose | 3.0 | +4.2 % | **+7.6 %** | [+4.9 %, +10.4 %] | no |
| long_prose | 2.0 | +6.0 % | +8.2 % | [+5.2 %, +11.4 %] | no |

El intervalo se redujo a la mitad, como se pretendía. Lo que reveló es que
**`long_prose` está con confianza *por encima* del umbral** — su límite inferior
ahora excluye el 5 % con ambos valores de ρ. El +5.1 % de V4 era una estimación
optimista de muestra pequeña, y más datos la movieron en la dirección
indeseada.

`table_summary` con ρ = 3.0 sigue siendo el único candidato: +2.7 %, intervalo
[−0.7 %, +6.3 %]. Con n = 64 el ancho restante es varianza real entre prompts y
no ruido de muestreo, así que más prompts del mismo tipo lo estrecharán despacio.
Esta es ya una pregunta sobre con cuánta firmeza hace falta hacer la afirmación,
no sobre si el experimento era suficientemente grande.

La curva misma replica limpiamente con cuatro veces el conteo de celdas:

| N | tokens/fragmento | impuesto (balanceado) | dependency_chain | long_prose | table_summary |
|---|---|---|---|---|---|
| 2 | 229 | +23.4 % | +57.7 % | +7.9 % | +4.6 % |
| 4 | 115 | +39.7 % | +74.6 % | +18.4 % | +26.0 % |
| 6 | 76 | +49.8 % | +85.7 % | +28.3 % | +35.5 % |
| 8 | 57 | +62.6 % | +97.3 % | +41.4 % | +49.0 % |

Monótona, `comparable_across_n: true`, 320 celdas por punto. El orden entre
formas de V4 se mantiene: a igual tamaño de fragmento, la cadena ordenada cuesta
un orden de magnitud más que la prosa o las tablas.

## 2. El acarreo tipado: la predicción falló, y el instrumento es la razón

La predicción era que acarrear cada valor etiquetado de forma literal elevaría
marcadamente la exactitud de cadena. Hizo lo contrario:

| | resumen plano | acarreo tipado | delta |
|---|---|---|---|
| dependency_chain | 0.303 | 0.255 | **−0.049** |
| table_summary | 0.617 | 0.618 | +0.001 |
| ρ alcanzada | 2.690 | 2.698 | +0.008 |

Que `table_summary` se mueva en +0.001 es el control comportándose
correctamente — no hay nada que tipar donde las respuestas no llevan etiquetas. ρ
subió en la pequeña cantidad predicha. Solo el efecto para el que existe el
mecanismo fue en la dirección equivocada.

**Antes de concluir que el mecanismo falla, hay que mirar qué estaba pidiendo el
corpus.** Exactitud por paso, agrupada sobre ambos brazos:

| paso | operación | exactitud |
|---|---|---|
| 1 | multiplicar | 67.4 % |
| 2 | **reducir en N por ciento** | **3.6 %** |
| 3 | dividir, redondear hacia abajo | 58.1 % |
| 4 | sumar | 51.5 % |
| 5 | **aumentar en N por ciento** | **0.0 %** |
| 6 | dividir, redondear hacia abajo | 4.0 % |
| 7 | restar | 7.4 % |
| 8 | multiplicar | 3.1 % |

Los dos pasos de porcentaje son los dos catastróficos. Dos de ocho pasos eran
**irresolubles para estos modelos sin importar lo que contuviera el paquete** —
y, sentados en las posiciones 2 y 5, envenenan todo lo que viene después, que es
la mayor parte de la cadena. Los pasos 6, 7 y 8 quedan por debajo del 8 % no
porque restar sea difícil, sino porque el paso 5 estaba mal para todos.

Un acarreo solo puede medirse por si un valor *acarreable* sobrevive a un límite
de paquete. Un paso que el modelo no podía computar ni teniendo el prompt entero
no dice nada sobre acarrear. **El −0.049 está medido a través de un instrumento
dominado por un fallo distinto, y no responde la pregunta.**

### Lo que la ejecución sí estableció sobre el acarreo

El eco es real y está cuantificado. De las respuestas incorrectas de la cadena,
un **13.4 % son exactamente el valor del predecesor repetido**, concentradas en
los pasos de porcentaje: 35.3 % en el paso 5, 18.9 % en el paso 2. Al recibir
`[04]=370` y que se le pida el paso 5, un modelo que no puede computar el
porcentaje devuelve 370.

Ese es un riesgo genuino que crea la forma tipada y que el resumen en prosa no
crea: presentar los valores como `[NN]=value` vuelve el eco el camino de menor
resistencia. Explica un tercio de los fallos del paso 5 — no la mayoría, pero lo
suficiente para que el próximo diseño del acarreo deba ser **selectivo**,
ofreciendo solo el valor que nombra el propio texto del sucesor, en vez de todo
lo que produjo el predecesor.

### El corpus está reconstruido, y ahora se imponen dos invariantes

Toda operación es una que la clase de 2–4B ejecuta de forma demostrable: sumar,
restar, multiplicar por un entero pequeño, dividir sin resto. El descuento se
ajusta un poco para que la división del paso 3 sea exacta en lugar de introducir
una regla de redondeo.

Dos propiedades las imponen ahora tests y no la esperanza. La cadena es
**estrictamente lineal** — una primera reconstrucción hizo por accidente que el
paso 3 consumiera el paso 1, cosa que el test atrapó. Y **no hay dos intermedios
que coincidan**: `chain_northwind` salió con 550 tanto en el paso 2 como en el
paso 5, lo que permitiría que un modelo que solo hace eco acertara por accidente
un paso posterior. Esa es exactamente la lectura que haría que un acarreo roto
pareciera uno que funciona.

## 3. Agregación: la primera señal de calibración que sobrevive a su propia guarda

Seis intentos de calibrar el mapa de confianza fracasaron porque el predictor se
saturaba — acuerdo entre 0.85 y 0.96 con casi ninguna dispersión. Separar las
unidades calificadas según si afirman algo que exige ver filas que el fragmento
puede no tener da, por primera vez, dos clases que difieren en **corrección**:

| clase de afirmación | n | exactitud | acuerdo medio | AUC |
|---|---|---|---|---|
| agregada | 800 | 57.1 % | 0.836 | **0.605** |
| local | 568 | 68.3 % | 0.699 | **0.660** |

Aquí importan tres cosas. La brecha de exactitud replica el hallazgo de V4 con
cinco veces la muestra. Las distribuciones de acuerdo difieren, así que el
predictor ya no está saturado. Y los AUC son **dentro de cada clase**, no
agrupados — de modo que no son el artefacto entre poblaciones que produjo un
titular equivocado tres veces en este proyecto.

0.605 y 0.660 son modestos. Son también los primeros números de este proyecto en
los que el acuerdo predice la corrección por encima del azar dentro de una
población homogénea. Retirar el mapa de confianza con la evidencia anterior
habría sido un error, y la razón por la que parecía retirable era que todavía no
se había medido nada sobre una población en la que la corrección variara.

## 4. El editor replica

| medida | V4 (144 pares) | V5 (320 pares) |
|---|---|---|
| tasa de aplicación | 52.1 % | 61.6 % |
| ganancia media de restricciones | +15.4 % | **+14.9 %** |
| delta de exactitud | 0.000 | **−0.003** |

El rechazo se mantiene con más del doble de muestra: el editor recupera alrededor
de un quince por ciento de las comprobaciones mecánicas y mueve la corrección por
ítem en nada. Tiene la respuesta ensamblada y el contrato y ningún acceso a la
fuente, así que puede reparar la forma y no puede reparar el hecho — y la
medición sigue diciéndolo.

## Lo que no es interpretable, y una cosa que no se pudo revisar en absoluto

El sidecar por ítem no registra qué brazo de acarreo produjo cada registro, así
que la exactitud por paso **no se pudo separar entre los brazos**. La tabla de
pasos de más arriba está agrupada, lo cual basta para mostrar que los pasos de
porcentaje están rotos para todos y no basta para decir cómo se comporta el
acarreo en cada profundidad. La columna queda añadida para la próxima ejecución;
este análisis sencillamente no se pudo hacer.

## Lo que sigue

1. **Volver a ejecutar la cadena sobre el corpus reconstruido.** La pregunta del
   acarreo está abierta, no respondida. No hace falta cambiar nada más para
   hacerla como corresponde.
2. **Hacer selectivo el acarreo.** Ofrecerle al sucesor el valor que nombra su
   propio texto, no todos los valores que produjo el predecesor. El eco explica
   un tercio de los fallos en el paso donde el modelo es más débil.
3. **`table_summary` con ρ = 3.0 es el único candidato vivo a umbral.** +2.7 %,
   intervalo [−0.7 %, +6.3 %], n = 64.
4. **Calibrar dentro de la clase de afirmación.** Es la única división hasta
   ahora en la que varían tanto el acuerdo como la corrección, que es lo que les
   faltaba a los seis intentos anteriores.
