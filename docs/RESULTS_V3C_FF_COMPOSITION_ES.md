---
status: partially_withdrawn
stands: Secciones 1 a 4
reason: >
  La sección 5 queda retirada. Su repeated_sentences_cross_task = 0 era cierto
  de ese corpus, no de la composición de prosa: sobre el corpus de composición
  marca 12 con N=3 y 50 con N=8.
lang: es
---
# La primera medición de composición — y el impuesto de coherencia no puede verla

> # ⚠ PARCIALMENTE RETIRADO — 4 de septiembre de 2026
>
> **Las secciones 1–4 se sostienen. La sección 5 queda retirada.** La división
> es exacta y vale la pena enunciarla con precisión.
>
> El `_SEQUENTIAL_CUES` del router coincide con `\bthen\b`, que aparece en la
> directiva de formato de salida de todo prompt *enumerado* («…**then** a single
> space, **then** the value»). Esos prompts se planificaron como cadenas y a sus
> fragmentos se les entregaron como contexto las líneas de respuesta de otros
> paquetes.
>
> | prompt | enumerado | planificado como cadena | afectado |
> |---|---|---|---|
> | `ff_overunder_L1/L2`, `ff_fieldname_L1/L2`, `ff_rulecheck_L1/L2` | sí | **sí** | **retirado** |
> | `comp_harbour`, `comp_archive`, `comp_relay` | no | no | **se sostiene** |
> | `grounded_manifest`, `grounded_backlog` | no | no | se sostiene |
>
> **Las §1–4 —el resultado de composición— no están afectadas.** Los tres prompts
> `comp_*` no coinciden con ninguna pista secuencial ni antes ni después de la
> corrección; nunca se planificaron como cadenas y sus fragmentos nunca
> recibieron un bloque predecesor. La brecha de restricciones de 14 a 21 puntos,
> el impuesto de coherencia leyendo cero sobre esos mismos textos, el mecanismo
> de duplicación y omisión, y la saturación de la línea base se sostienen
> exactamente como están escritos.
>
> **La §5 —el resultado de acuerdo— queda retirada.** Seis de los ocho prompts
> que aportan ítems de calibración son los enumerados afectados. Con k > 1 cada
> réplica de una tarea recibe el mismo paquete, así que un bloque predecesor
> compartido les da algo en qué converger, lo que plausiblemente *infla* el
> acuerdo. El AUC de 0.602, el lift de marcado de 2.15, p = 0.0026 y el intervalo
> agrupado descansan todos sobre eso. Solo `grounded_manifest` y
> `grounded_backlog` están limpios — dos clusters, demasiado pocos para volver a
> derivar nada de ellos.
>
> **El primer no nulo en seis mediciones no es, por tanto, un resultado todavía.**
> Era el desenlace del que más valía la pena sospechar, y esta es la razón. Hay
> que volver a ejecutar el tier después de la corrección antes de tratar nada de
> la §5 como evidencia.


**Ejecución:** `results/v3c-ff-20260903-224021`. `prompts/free_form.json`, 11
prompts —seis ítems de respuesta libre, tres composiciones de dos párrafos, dos
resúmenes anclados— con ρ = 2.5, N = 3, k ∈ {1, 3, 5}, cinco familias de modelo.
44 filas.

> **Procedencia.** `harness_validation_only: false`, `embeddings_degraded: false`,
> τ_sem 0.640 ajustada sobre 128 pares (F₀.₅ 0.933, P 0.964, R 0.828), semilla 0,
> `rows_excluded_below_floor: 0`, ρ alcanzada 2.49–2.51 frente a 2.50.
> `n_families_mean` 3.0 con k=3 y 5.0 con k=5.

**La composición de prosa es la carga de trabajo sobre la que esta arquitectura
se propone, y hasta esta ejecución nunca se había medido.** Ya se midió, y el
resultado no trata de que fragmentar salga caro. Trata del instrumento.

---

## 1. El hallazgo

Satisfacción mecánica de restricciones — contada desde el texto, sin juez, sin
modelo:

| brazo | puntuación de restricciones (comparable) |
|---|---|
| **monolítico** | **1.000** |
| fragmentado N=3, k=1 | 0.864 |
| fragmentado N=3, k=3 | 0.786 |
| fragmentado N=3, k=5 | 0.857 |

El brazo monolítico satisface **todas las restricciones comprobables en todas las
composiciones**. Fragmentar en tres cuesta **de 14 a 21 puntos**.

Ahora los mismos textos, sobre la métrica alrededor de la cual se ha construido
este proyecto:

| prompt de composición | impuesto de coherencia con k=1 | con k=3 | con k=5 |
|---|---|---|---|
| `comp_harbour` | +0.000 | +0.000 | +0.000 |
| `comp_archive` | +0.000 | +0.000 | +0.000 |
| `comp_relay` | +0.000 | +0.000 | +0.000 |

**Cero. En todas las composiciones, con todo k.**

El impuesto de coherencia tipo BooookScore —la cantidad contra la que está
escrito el criterio de continuar o abandonar, la cantidad que reportaron cuatro
documentos retirados— dice que fragmentar no cuesta *nada* exactamente sobre los
textos donde un conteo mecánico encuentra un fallo de 14 puntos.

## 2. Qué se rompió en realidad

Las restricciones que fallaron nombran el mecanismo:

| tipo | cuáles fallaron | qué significa |
|---|---|---|
| `term_once` | `retention_once`, `tide_once`, `battery_once` | un término requerido aparece **más de una vez** — dos trabajadores lo introdujeron cada uno |
| `no_repeated_ngram` | `no_repeated_phrase` | una frase queda duplicada a través del empalme |
| `must_mention` | `mentions_reading`, `mentions_heaviest` | algo requerido quedó **omitido** — ningún fragmento lo cubrió |
| `words_per_paragraph` | `length` | el texto ensamblado tiene el tamaño equivocado |
| `paragraph_count` | `paragraphs` | el empalme produjo el número equivocado de párrafos |

Dos familias de fallo, y son opuestas: **duplicación** (tres de las cinco
comprobaciones `*_once`) y **omisión** (`must_mention`). Ambas son precisamente
lo que debería producir el ensamblaje a partir de fragmentos independientes, y
ambas son invisibles para una puntuación de coherencia basada en transiciones —
porque cada pasaje duplicado es localmente fluido y una omisión no deja costura.

**Un refinamiento que vale la pena tener:** `repeated_sentences_cross_task` es
**0** en todas las condiciones. Ningún par de trabajadores escribió la misma
*oración*. La duplicación está en el nivel del término y de la frase. Las notas
de diseño del proyecto describen el fallo característico como «dos trabajadores
concluyen cada uno» — reformulación a nivel de oración. Con esta evidencia es
más fino que eso, lo que importa para cualquier cosa que intente detectarlo o
repararlo.

## 3. La corrección de neutralidad de brazo, y la dirección que nadie esperaba

Las puntuaciones cruda y comparable difieren marcadamente:

| brazo | cruda | comparable | brecha |
|---|---|---|---|
| fragmentado k=1 | 0.633 | 0.864 | **+23 puntos** |
| fragmentado k=3 | 0.711 | 0.786 | +7 |
| fragmentado k=5 | 0.756 | 0.857 | +10 |

La puntuación comparable, que excluye `paragraph_count` y
`words_per_paragraph`, es **más alta** — así que la puntuación cruda estaba
penalizando al brazo *fragmentado* en las comprobaciones que impone el
ensamblador.

Ese es el caso invertido que predijo el comentario de la propia corrección y que
esta ejecución confirma: cuando un prompt describe su estructura sin nombrar un
número de párrafos, `requested_paragraphs` devuelve `None`, `select_then_splice`
mete las piezas en un solo párrafo, y el brazo fragmentado falla
`paragraph_count` **por construcción**. En el corpus de tablas esas mismas dos
comprobaciones eran un *aprobado* garantizado para ese brazo. Mismo instrumento,
sesgo opuesto, decidido por la redacción del prompt — que es exactamente por lo
que no pueden figurar en ninguna cifra que cruce brazos.

Hay que leer la puntuación comparable. La cruda exagera aquí el costo hasta en 23
puntos y lo subestimó en otros lugares.

## 4. El impuesto de coherencia no tiene espacio para moverse en este corpus

**Diez de las once líneas base monolíticas puntúan exactamente 1.000**; la
undécima es 0.875. Un impuesto definido como *(monolítico − fragmentado) /
monolítico* contra una línea base clavada en el techo solo puede ser **≥ 0**. No
puede detectar una mejora, y casi no tiene resolución para detectar una
degradación pequeña.

El +2.74 % reportado con k=1 es, por tanto, una medición de un solo lado hecha
contra un denominador saturado. No está mal, pero no es el costo de fragmentar
en este corpus — la puntuación de restricciones sí lo es, y dice de 14 a 21
puntos.

Combinado con la §1: sobre la carga de trabajo para la que existe la
arquitectura, el impuesto de coherencia está a la vez **saturado** y **ciego a
los fallos que de hecho ocurren**. Ese es un hallazgo sobre el instrumento
principal del proyecto, y tiene más consecuencias que cualquier cifra que el
instrumento haya producido.

## 5. Acuerdo — el primer no nulo en seis mediciones, y sus límites exactos

| | v3c-gt (clave de respuestas) | **v3c-ff (respuesta libre)** |
|---|---|---|
| acuerdo medio | 0.966 | **0.932** |
| ítems fuera del bin superior | 8 de 183 | **18 de 158** |
| **AUC** | 0.525 | **0.602** |
| lift de marcado al 10 % | 1.12 | **2.15** |
| exactitud | 0.694 | 0.652 |

Marcar el 10 % de ítems con menor acuerdo atrapa errores a **2.15× la tasa
base**. En el corpus de clave de respuestas el mismo estadístico era 1.12.

**Para esto fue diseñado el mecanismo y es la primera vez que se le dan las
condiciones para funcionar.** El corpus de respuesta libre aporta respuestas que
pueden formularse de otro modo y seguir siendo correctas, así que las réplicas
*pueden* discrepar; el predictor tiene varianza, y con varianza lleva alguna
información. Es exactamente la dirección predicha a partir de los bins de
v3c-gt: el acuerdo es informativo donde no está clavado en 1.0.

**La medición declarada ya se hizo, sobre esta ejecución almacenada, antes de
generar nada nuevo.** Bootstrap agrupado por prompt, 10 000 remuestreos, y una
prueba de permutación que baraja las etiquetas de corrección *dentro* de cada
prompt:

| | |
|---|---|
| AUC, puntual | **0.602** |
| IC del 95 %, bootstrap agrupado por prompt | **[0.5014, 0.7243]** |
| prueba de permutación (etiquetas barajadas dentro del prompt) | **p = 0.0026** |
| prompts que aportan ítems | **8** |
| ítems | 158 (103 correctos, 55 incorrectos) |

**Las dos pruebas no dicen lo mismo, y la diferencia es el resultado.**

La prueba de permutación pregunta: *dentro de estos prompts, ¿ordena el acuerdo
los ítems mejor que el azar?* Responde con claridad — **p = 0.0026**. Aquí el
acuerdo no es inerte.

El bootstrap agrupado hace una pregunta más difícil: *¿sobreviviría esto a otro
sorteo de prompts?* Su límite inferior es **0.5014** — azar hasta el tercer
decimal. Excluye 0.5 por 0.0014, sobre **ocho clusters**, donde un cluster
bootstrap no es confiable en absoluto; veinte es el piso habitual.

**El enunciado honesto es por tanto estrecho y vale la pena enunciarlo con
precisión:** en este corpus, el acuerdo lleva información real sobre cuáles
ítems están mal. Si eso generaliza más allá de estos ocho prompts no está
establecido, y esta ejecución no puede establecerlo.

Tres límites más, enunciados ahora y no después de que alguien objete:

1. **90 de 248 ítems se excluyeron por tener una sola réplica** y 45 más por
   ininteligibles. Los 158 que sobreviven no son un subconjunto aleatorio.
2. Esta es la **sexta** medición de esta pregunta y la primera que no es nula.
   Eso merece más escepticismo, no menos — aunque esta ejecución se programó
   antes de que v3c-gt devolviera 0.525, así que no es un diseño elegido después
   de verlos.
3. El efecto está donde la teoría dijo que estaría, lo que tranquiliza y es
   también el aspecto que tiene un resultado espurio cuando coincide por
   casualidad con una creencia previa.

**Qué cambia esto.** El mapa de confianza se retiró sobre cinco nulos. Esto no lo
des-retira: la afirmación de que el acuerdo predice la corrección *en general*
sigue sin estar respaldada. Lo que ahora sí está respaldado, sobre ocho prompts,
es una versión **acotada** — **donde las respuestas pueden formularse de otro
modo, el acuerdo no es inerte.** Establecer si esa cota es real necesita más
prompts, no más réplicas: la cantidad limitante son los clusters, y pasar de 8 a
25 prompts de respuesta libre haría más que cualquier número de ítems
adicionales dentro de los que ya existen.

## 6. Qué zanja esta ejecución y qué abre

**Zanja:** fragmentar tiene un costo real y medible sobre la composición de prosa
— de 14 a 21 puntos de satisfacción de restricciones frente a un brazo
monolítico que puntúa perfecto — y el costo es duplicación y omisión, no
reformulación a nivel de oración.

**Abre, y este es el punto mayor:** el impuesto de coherencia no es un
instrumento usable para esta carga de trabajo. Está saturado contra una línea
base en el techo y reporta cero sobre textos con un fallo mecánico de 14 puntos.
Toda cifra que este proyecto ha producido, retirada o vigente, se midió con él.

La puntuación de restricciones es un mejor instrumento para composición y ya
existe. Lo que le falta es una celda preregistrada, un control y una división del
corpus — el aparato que `tables-final` sí tiene. Construir eso para composición
es ahora un uso más valioso de una noche que cualquier otra ejecución de
impuesto de coherencia.
