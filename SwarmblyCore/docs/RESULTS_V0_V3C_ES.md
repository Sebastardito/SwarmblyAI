---
status: partially_withdrawn
stands: >
  lo que no se apoye en el eje rho ni en el impuesto de coherencia
reason: >
  La sección 1 no es una medición de rho -- toda celda quedó por debajo de su
  propio piso de empaquetado, así que dos etiquetas de rho produjeron paquetes
  idénticos byte a byte -- y el impuesto de coherencia vino de un instrumento
  que no era neutral respecto del brazo.
lang: es
---
# Primeras mediciones contra modelos reales — V0 y V3c

> # ⚠ SUPERADO — 12 de agosto de 2026
>
> **Nada en la sección 1 de este documento es una medición de ρ, y el impuesto
> de coherencia que reporta fue producido por un instrumento que no era neutral
> respecto del brazo. No cite ninguna cifra de aquí. Ambos defectos ya están
> corregidos en el harness; ninguno se puede reparar en los datos de esta
> corrida, porque los datos nunca se recogieron bajo las condiciones que la
> etiqueta del eje afirma.**
>
> **1. El eje ρ nunca se movió.** Una celda solo puede medir un presupuesto de
> contexto si ese presupuesto está por encima del *piso de empaquetado* del
> propio prompt — los tokens que cuestan las microtareas y sus encabezados de
> contrato antes de agregar contexto alguno. Por debajo del piso `build_packet`
> cae de vuelta a `budget = max(mandatory_tokens, …)`, todo paquete colapsa a su
> tarea pelada, y dos etiquetas distintas de ρ producen paquetes idénticos byte
> a byte. En este corpus los pisos honestos son:
>
> | | N = 2 | N = 4 | N = 8 |
> |---|---|---|---|
> | piso de empaquetado | 1.42 – 1.68 | 1.85 – 2.35 | 2.70 – 3.71 |
>
> El barrido de abajo corrió ρ ∈ {1.00, 1.25, 1.50, 2.00}. Celdas en su propio
> piso o por encima, sobre 8 prompts cada una:
>
> | ρ | N = 2 | N = 4 | N = 8 | fila |
> |---|---|---|---|---|
> | 1.00 | 0/8 | 0/8 | 0/8 | **0/24** |
> | 1.25 | 0/8 | 0/8 | 0/8 | **0/24** |
> | 1.50 | 2/8 | 0/8 | 0/8 | 2/24 |
> | 2.00 | 8/8 | 3/8 | 0/8 | 11/24 |
>
> **13 de 96 celdas — 13.5 % — estaban por encima del piso.** Las dos filas que
> anclan el descenso, ρ = 1.00 y ρ = 1.25, no contienen ninguna celda válida:
> 48 celdas, cero mediciones de ρ. La evidencia estuvo en la tabla publicada
> todo el tiempo y se leyó como ruido — *"ρ alcanzado 1.17"* contra un objetivo
> de 1.00 es un sobrepaso del 17 %, que es lo que hace un paquete cuando no
> cabe dentro de su presupuesto.
>
> Así que "el impuesto de coherencia cae monótonamente en ρ" reformula un hecho
> distinto: los paquetes que no llevan más que su tarea puntúan peor que los
> paquetes que llevan algo de contexto. Eso es cierto, y no es la hipótesis.
> `rho_reachable` se escribió en cada fila desde el comienzo; hasta el 12 de
> agosto de 2026 exactamente una función del análisis lo leía, y esa caía de
> vuelta a las filas inalcanzables cuando no existía ninguna porción alcanzable.
>
> **2. La métrica de coherencia no era neutral respecto del brazo.** El conjunto
> de entidades esperadas crecía con N, las omisiones se atribuían por turnos
> entre las cabezas de fragmento, y las clases de error locales a la costura
> solo podían dispararse donde había costuras — así que el mismo texto de
> dieciséis oraciones puntuó **0.9375 como monolítico y 0.5000 con N = 8**, un
> impuesto aparente de **+46.7 % sobre un texto que nunca cambió**. Toda cifra
> de impuesto de abajo carga con una porción desconocida de eso.
>
> **Qué lo reemplaza.** Una afirmación causal, una celda nombrada, un control
> que puede fallar, y un corpus partido de modo que ningún umbral se ajuste
> sobre los datos que juzga. El resultado está en
> [`RESULTS_TABLES_FINAL_CORRECTED.md`](RESULTS_TABLES_FINAL_CORRECTED.md):
> `table_summary` con ρ = 3.5, N = 2, k = 1 — **+2.30 %, IC del 95 % [−2.05 %,
> +7.49 %], 16 prompts reservados, criterio NO CUMPLIDO** por 2.49 puntos en la
> cota superior, con el control en N = 8 comportándose como se requiere
> (+16.23 %, IC [+11.33 %, +20.28 %], sin solapamiento con el brazo bajo
> prueba).
>
> La distribución es el hallazgo por el que el criterio no pregunta: **el prompt
> mediano pierde exactamente 0.00 % y 11 de 16 prompts quedan en cero o por
> debajo.** Dos prompts explican el 140 % de la media, y quitarlos deja −1.06 %
> sobre los otros catorce. Eso no supera la barra — dice que la barra preguntaba
> por un promedio que no describe casi nada del corpus.
>
> Una versión anterior de esta nota citaba la corrida del 27 de agosto (+3.26 %,
> IC [−0.02 %, +6.93 %]). Esa corrida usó el mismo instrumento defectuoso del
> que trata este aviso, y sus cifras quedan superadas por la recorrida del 3 de
> septiembre de arriba.
>
> **Qué sobrevive de este documento.** La sección 2 (V3c, acuerdo frente a
> calidad juzgada) no depende de ρ ni de la métrica de coherencia, y su hallazgo
> — ninguna relación entre el acuerdo entre réplicas y la calidad juzgada — se
> ha reproducido y fortalecido desde entonces. El mapa de confianza está muerto
> por su propia evidencia, y esa conclusión se sostiene.

**Corridas:** `results/v0-20260814-140941/` y `results/v3c-20260814-140941/` ·
**Backend:** Ollama local, tres familias (`llama3.2:3b`, `qwen2.5:3b`,
`gemma2:2b`), embeddings `nomic-embed-text` · **Corpus:** el smoke set de 8
prompts, una semilla, temperatura 0

> **Procedencia, revisada antes de leer nada de lo de abajo.** `harness_validation_only:
> false` y `embeddings_degraded: false` en ambas corridas — modelos reales,
> embeddings reales, no el mock. `transport_retries: 0` — ninguna conexión se
> cayó y se reintentó, así que nada de aquí es un resultado parcial cosido.
> τ_sem = 0.51, calibrado sobre **72 pares etiquetados** (F₀·₅ = 0.988,
> precisión 1.00, recall 0.944).
>
> **Reproducibilidad.** Estas corridas reproducen un par anterior, celda por
> celda, con la misma semilla. El pipeline es determinista a temperatura 0, que
> es lo que vuelve significativo —y no esperable— un desacuerdo entre dos
> corridas.
>
> **Escala.** Ocho prompts, una semilla, modelos de 2–3B. Una señal sobre la
> cual actuar, no un benchmark para publicar como titular.

---

## 1. V0 — el impuesto de coherencia cae monótonamente en ρ

> **RETIRADO.** Vea el aviso al inicio de este documento. Las filas ρ = 1.00 y
> ρ = 1.25 de abajo no contienen ninguna celda que estuviera por encima de su
> piso de empaquetado, así que el descenso que anclan no es una función de ρ. La
> métrica que produjo los porcentajes tampoco era neutral respecto del brazo. La
> tabla se conserva, inalterada, porque un resultado retirado que ha sido
> borrado no se puede revisar.

Impuesto tipo BooookScore contra el baseline monolítico, *k* = 1, 21 celdas
válidas por ρ:

| ρ (objetivo) | ρ (alcanzado) | Impuesto de coherencia | Diferencia absoluta | Celdas |
|---|---|---|---|---|
| 1.00 | 1.17 | **+24.1 %** | +0.1235 | 21 |
| 1.25 | 1.27 | **+20.4 %** | +0.0761 | 21 |
| 1.50 | 1.53 | **+16.1 %** | +0.0678 | 21 |
| 2.00 | 2.08 | **+13.7 %** | +0.0517 | 21 |

Tanto la razón como la diferencia absoluta sin denominador decrecen con ρ. Esto
es lo que predice la hipótesis H1: más contexto compartido por fragmento, menos
calidad perdida en el reensamblaje. Es la primera evidencia de que el
presupuesto de contexto es la variable que el diseño dice que es.

### El criterio de go/no-go se cumple

Seis de 28 celdas categoría × ρ caen por debajo del umbral de 5 % fijado antes
de que existiera dato alguno:

| Categoría | ρ | Impuesto |
|---|---|---|
| creative_writing | 2.00 | **−9.0 %** |
| synthetic_data | 1.50 | **−6.2 %** |
| synthetic_data | 1.25 | **−5.1 %** |
| synthetic_data | 2.00 | **−0.3 %** |
| synthetic_data | 1.00 | **+1.3 %** |
| code_shared_state | 1.50 | **+3.2 %** |

Negativo significa que la fragmentación *mejoró* la respuesta en ese
instrumento. `synthetic_data` supera el umbral en todo ρ probado. El criterio se
escribió como "al menos una categoría de tarea" porque nadie esperaba que
pasaran todas — y no pasan.

### Dos fallas de medición, reportadas porque acotan la tabla de arriba

**La grilla de entidades es inutilizable en este corpus.** Su baseline
monolítico va de 0.000 a 0.114 en los ocho prompts, mediana 0.024 — todas por
debajo del piso de 0.15 en el que una razón deja de ser un estadístico. Las
**96 de 96** celdas quedan excluidas y el harness reporta el impuesto relativo
de grilla de entidades como *no medido* y no como cero. Una versión anterior de
esta corrida, antes de que se revisara el denominador, reportó cifras tan
extremas como **−180 %**.

**Un prompt rompió su baseline.** `rag_summarization_filings` produjo una
respuesta monolítica de una oración y seis tokens — una falla de generación, no
un resultado de coherencia. Su baseline de BooookScore es 0.000 y sus 12 celdas
quedan excluidas. Esto hay que investigarlo antes de la siguiente corrida: un
prompt que no puede producir un baseline no puede aportar un impuesto.

## 2. V3c — el acuerdo no predice la calidad aquí

> **El hallazgo se sostiene; el veredicto de abajo ha sido superado.** La
> medición de esta sección no depende de ρ ni de la métrica de coherencia, y su
> dirección se ha mantenido. Lo que cambió es su fuerza. Donde esta sección
> concluye *"no sustentado, no refutado"* — una lectura justa contra un juez que
> aceptaba el 93.3 % de todo — el experimento contra ground truth al que remite
> se ha corrido desde entonces tres veces, devolviendo razones de momios comunes
> de Mantel-Haenszel de **3.47, 0.26 y 1.24**, la última con un IC de [0.25,
> 3.75]. Por encima, por debajo y a horcajadas de 1 sobre la misma pregunta no
> es una señal débil a la espera de un mejor instrumento; es ninguna señal,
> medida tres veces. **El mapa de confianza queda por tanto retirado, no
> degradado**, y sale del benchmark V7. Lea "no sustentado, no refutado" abajo
> como el veredicto de agosto de 2026, superado por su propio seguimiento. Las
> cifras están inalteradas.

Barriendo *k* ∈ {1, 3, 5} con ρ = 1.5, una réplica por familia:

| *k* | Impuesto de coherencia | Acuerdo medio | HIGH | LOW |
|---|---|---|---|---|
| 1 | +13.2 % | — | — | — |
| 3 | **+30.8 %** | 0.577 | 29.1 % | 42.3 % |
| 5 | **+33.3 %** | 0.728 | 58.3 % | 28.7 % |

El consenso cuesta aproximadamente **17 a 20 puntos de calidad** respecto de
*k* = 1. Lo que compra se suponía que era el mapa de confianza:

> **r de Pearson = −0.030 sobre 597 unidades semánticas.**

Los bins son planos y no monótonos, y el acuerdo no los ordena: el bin con
mayor puntaje es 0.6–0.8, el bin de *menor* acuerdo es el segundo, y el bin
donde los modelos más coincidieron puntúa por debajo de ambos.

| Acuerdo | Unidades | Juzgadas aceptables |
|---|---|---|
| 0.0 – 0.2 | 40 | 97.5 % |
| 0.2 – 0.4 | 91 | 91.2 % |
| 0.4 – 0.6 | 80 | 91.3 % |
| 0.6 – 0.8 | 122 | 99.2 % |
| 0.8 – 1.0 | 264 | 91.3 % |

La sección 11.4 del whitepaper se comprometió de antemano: *"una correlación
plana o negativa invalidaría el mapa de confianza como señal de fiabilidad, y
ese desenlace debe ser publicable."* Está publicado.

### La corrida no es el experimento que el whitepaper especifica

**El juez aceptó el 93.3 % de las unidades.** Con tan poca varianza en la
variable dependiente no puede aparecer una correlación aunque la señal
subyacente sea real. Esta medición por tanto **no puede distinguir**:

1. que el acuerdo entre familias de modelos independientes no predice la
   corrección; o
2. que un juez de la misma clase no discrimina la calidad con finura suficiente
   para detectarlo.

La sección 11.4 especifica V3c contra **conjuntos de datos con ground truth**.
Esta corrida usó el juez — el instrumento más débil del que el whitepaper ya
advierte. **El enunciado honesto es que el mapa de confianza no está sustentado,
no que esté refutado.**

Eso no rescata la afirmación. Una propiedad no sustentada no se puede publicitar
como la más valiosa de la arquitectura, y ya no lo es: la sección 1.3 se
reescribió, la sección 8.4b lleva el resultado medido, E16 ahora se declara
explícitamente como un mecanismo sin beneficio de fiabilidad afirmado, y L13
registra todo el asunto como una limitación.

## 3. Qué cambió en el paper

| Cambio | Dónde |
|---|---|
| Resultados reportados completos, incluido el desfavorable | nueva sección 11.3 |
| El resumen enuncia ambos desenlaces | Resumen |
| El mapa de confianza degradado de "propiedad más valiosa" a "mecanismo, beneficio no medido" | Sección 1.3, punto 2 |
| La correlación medida y su debilidad enunciadas en el mecanismo | Sección 8.4b, punto 2 |
| E16 declarado como un mecanismo sin afirmación de fiabilidad | Sección 13 |
| **L13** — el mapa de confianza no tiene valor demostrado | Sección 12 |
| **L14** — la grilla de entidades no funciona sobre respuestas cortas | Sección 12 |
| La tabla de métricas gana una columna *medido* | Sección 11.5 |
| Conclusión revisada: primera medición adentro, una contribución debilitada | Sección 14 |

## 4. Qué correr enseguida, en orden de prioridad

1. **V3c contra ground truth.** El único experimento que zanjaría si el mapa de
   confianza vale su costo de 17–20 puntos. Todo lo demás sobre E16 es
   especulación hasta que esto exista.
2. **Arreglar `rag_summarization_filings`.** Un prompt que rinde un baseline de
   seis tokens es un bug del corpus o de la generación, no un hallazgo.
3. **Reemplazar o reparar el segundo instrumento de coherencia.** Un solo proxy
   mecánico funcionando es evidencia más delgada de la que este diseño merece.
4. **Salidas más largas, más prompts, más semillas.** Ocho prompts y una semilla
   acotan cuánto puede significar cualquiera de los puntos anteriores.

## 5. Reproducir

```bash
./scripts/run_ollama.sh v0     # results/v0-<stamp>/
./scripts/run_ollama.sh v3c    # results/v3c-<stamp>/
```

Las corridas desde el commit `846aeea` en adelante registran el denominador
junto a cada razón, excluyen y cuentan las celdas inestables, toman el titular
de *k* = 1, reportan un punto no medido como ausente y no como cero, y
sobreviven a una conexión caída.
