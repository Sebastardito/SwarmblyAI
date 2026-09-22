---
status: current
lang: es
---
# Preregistro — el costo de la fragmentación sobre la composición de prosa

**Escrito:** 4 de septiembre de 2026, **antes** de correr el corpus contra
cualquier modelo real. Nada de lo que sigue puede cambiarse una vez ejecutado
`comp-final`; una cifra que se mueve después de ver la mitad final no es
estimación de nada.

**Estado:** declarado, todavía no ejecutado. `comp-dev` ajusta τ_sem y comprueba
que el corpus se comporta; `comp-final` produce el veredicto, una sola vez.

---

## 1. Por qué existe esto

La corrida del 3 de septiembre produjo la medición más fuerte que tiene este
proyecto. Sobre tres composiciones de dos párrafos, calificadas contando hechos
sobre la cadena de texto y sin ningún modelo en el veredicto:

| brazo | puntuación de restricciones (comparable entre brazos) |
|---|---|
| **monolítico** | **1.000** |
| fragmentado N=3, k=1 | 0.864 |
| fragmentado N=3, k=3 | 0.786 |
| fragmentado N=3, k=5 | 0.857 |

De catorce a veintiún puntos. Y sobre los *mismos textos*, el impuesto de
coherencia tipo BooookScore —la magnitud contra la que está escrito el criterio
de continuidad o abandono de este proyecto, la magnitud que reportaron cuatro
documentos retirados— marcó **+0.000** con todo k.

Ese hallazgo descansaba sobre **tres prompts**, sin celda preregistrada, sin
control y sin partición del corpus. `tables24.json` se construyó para darle al
impuesto de coherencia exactamente ese aparato. **El instrumento más fuerte tenía
detrás el método más débil**, y una descripción de tres prompts no es evidencia
sobre una carga de trabajo. Este documento es el aparato que faltaba, y
construirlo vale más que cualquier corrida adicional del impuesto.

## 2. La hipótesis declarada

> **La composición de prosa con ρ = 4.0, N = 3, k = 1 cuesta menos de 5 puntos
> de satisfacción de restricciones contra su línea base monolítica.**

| | |
|---|---|
| **Corpus** | `prompts/composition.json`, partición `final` — 24 prompts, digest `e9e382b9…` |
| **Métrica** | `constraint_score_comparable` — la proporción de comprobaciones satisfechas, excluyendo `paragraph_count` y `words_per_paragraph` |
| **Estimador** | diferencia media **pareada**, monolítico − fragmentado, un par por prompt |
| **Intervalo** | cluster bootstrap sobre los prompts, 10 000 muestras, semilla 0 |
| **Se cumple si** | el límite **superior** del intervalo del 95 % queda por debajo de 0.05 |
| **Control** | la misma celda con **N = 8**, obligada a **fallar** |
| **Se rehúsa si** | aportan menos de 20 prompts (`MIN_CLUSTERS_FOR_A_VERDICT`) |

Implementado en `experiment.composition_criterion`; el umbral es
`experiment.COMPOSITION_THRESHOLD_POINTS`; la celda se nombra en la línea de
comandos con `--declare-composition`, así que la declaración es un hecho sobre la
invocación y es recuperable desde `run.log`.

## 3. Cada decisión de arriba, y qué la forzó

### Puntos, no por ciento

Diez de las once líneas base monolíticas del 3 de septiembre puntuaron
exactamente **1.000**. Un impuesto relativo `(baseline − fragmented) / baseline`
contra un denominador clavado en el techo es máximamente sensible justo donde la
línea base es mejor: una sola comprobación perdida es el numerador entero.
Además no puede leer por debajo de cero, así que nunca puede mostrar que la
fragmentación no cuesta nada. La diferencia pareada en puntos no tiene
denominador al que ser sensible.

Esto es un cambio de estimador, y cambiar un estimador después de que devuelve
una respuesta incómoda es la manera en que un proyecto se habla a sí mismo para
salir de un resultado — así que vale la pena ser preciso sobre qué se cambia y
qué no. El **criterio del impuesto de coherencia queda intacto**: `tables-final`
sigue declarando una degradación relativa por debajo del 5 %, y su veredicto del
4 de septiembre (+2.30 %, IC [−2.05 %; +7.49 %], NOT MET por 2.49 puntos) se
sostiene. Lo nuevo es un *segundo* criterio, sobre una métrica *distinta*, para
un corpus *distinto*. El impuesto nunca fue un buen instrumento para la prosa, y
la §4 de `RESULTS_V3C_FF_COMPOSITION.md` es la medición que lo dice.

### Pareado dentro del prompt

Ambos brazos responden el mismo prompt, así que la dificultad del prompt se
cancela. Hasta que `constraint_score_comparable` pasó a ser una columna por fila
el 4 de septiembre, la puntuación vivía solo dentro de `_trace` y solo podía
reportarse como una **media sobre una condición** — dos medias no pareadas, con
la dificultad del prompt dentro de la estimación. Así es como el impuesto de
coherencia pasó cuatro corridas siendo sensible a qué prompts cayeron en qué
celda.

### El límite superior

Un criterio que se salva con la estimación puntual es el que este proyecto ya
retiró. La documentación de `falsifiable_go_no_go` lleva la aritmética: "existe
una (categoría, ρ) con degradación < 5 %" tiene P(cumplir) = **100 %** bajo su
propio nulo. El límite es lo que hace que cumplir signifique algo.

### Un control obligado a fallar

N = 8 en la misma grilla. Si la fragmentación en ocho también cuesta menos de 5
puntos, el instrumento no está separando los brazos y **ninguno de los dos
números es evidencia**. Un control que cumple es peor noticia que una celda
declarada que falla, y la CLI lo imprime con esas palabras.

### El umbral se declaró contra datos que no lo cumplen

`COMPOSITION_THRESHOLD_POINTS = 0.05` es el go/no-go del 5 % existente traducido
a una métrica que se cuenta en lugar de juzgarse. El piloto situó la brecha entre
14 y 21 puntos — **de tres a cuatro veces el techo**. El umbral se escribe en el
valor que implica el criterio viejo, sabiendo eso, precisamente para que nadie
pueda decir después que se fijó donde cayó la respuesta. Un umbral elegido
después de ver 14 puntos habría sido 0.25.

### Un piso de clusters, en el código y no en una advertencia

Esa misma corrida del 3 de septiembre reportó un AUC de 0.602 con un intervalo
del 95 % agrupado de [0.5014; 0.7243] — que excluye el azar por 0.0014, sobre
**ocho clusters**. La advertencia estaba en la prosa; el número es lo que un
lector recuerda. Por debajo de 20 prompts, `composition_criterion` devuelve
`passed: None` y enuncia ambos conteos. `comp-dev` tiene 12 prompts y por lo
tanto no imprimirá **veredicto alguno**, por diseño.

### ρ = 4.0, muy por encima de lo que pide SPEC

El piso de empaquetado de este corpus con N = 8 va de **3.324 a 3.843**. No hay
ninguna ρ más baja a la que el brazo de control exista: por debajo del piso todo
paquete colapsa a su tarea desnuda, y `publishable()` descarta esas filas de toda
cifra. Tres tiers v3c se corrieron con ρ = 1.5 contra pisos de 1.51 a 2.37 y
produjeron 0 de 15, 0 de 11 y 0 de 8 celdas alcanzables.

Dos consecuencias, ambas enunciadas y no suavizadas:

1. **Esto es en sí mismo un hallazgo.** El piso sube con N — 2.13 con N = 3, 3.84
   con N = 8 — así que fragmentar más fuerte *obliga* a más contexto. Eso es lo
   contrario de lo que promete la arquitectura, y es el mismo muro que el
   objetivo de ρ < 2.0 de la SPEC §11.5, inalcanzable sobre todo corpus medido
   hasta ahora.
2. **Es conservador para este criterio.** Más contexto solo puede ayudar al brazo
   fragmentado, así que un **FALLO con ρ = 4.0 es fuerte** y un **CUMPLIMIENTO es
   débil**. Dado que los doce defectos de instrumento encontrados en este
   proyecto se inclinaron todos hacia su propia hipótesis, ser conservador en
   esta dirección es justamente el punto.

## 4. El corpus, y las dos formas de romper en silencio una partición congelada

`scripts/make_composition.py`, semilla 20260904, 36 prompts, **12 dev / 24
final**, digest sobre id, partición, tier y texto del prompt.

Tres tiers de dificultad, doce prompts cada uno, porque una línea base saturada
es un problema incluso para una diferencia pareada: nunca puede mostrar que la
fragmentación no cuesta nada y no puede comprobarse que sea neutral entre brazos.
Las perillas son las comprobaciones que el piloto mostró que de verdad aprietan —
tres de sus cinco fallos fueron `*_once`:

| tier | términos requeridos | de los cuales exactamente una vez | ventana de frase repetida |
|---|---|---|---|
| easy | 2 | 1 | 8 |
| mid | 3 | 2 | 7 |
| hard | 4 | 3 | 5 |

`term_once` es difícil también para el brazo **monolítico**: quien escribe
cubriendo un término a lo largo de dos párrafos lo nombra dos veces sin darse
cuenta. Eso es deliberado.

**Dos modos de fallo que un digest no detecta**, ambos aseverados en su lugar:

* **Una partición desbalanceada.** Asignar todos los prompts hard a dev deja el
  digest intacto y las dos mitades incomparables. El generador se niega a
  escribir, y `test_the_split_is_balanced_across_difficulty_tiers` comprueba el
  archivo que se entregó: dev es 4/4/4, final es 8/8/8.
* **Una mitad final demasiado pequeña para responder.** 24 contra un piso de 20,
  aseverado por `test_the_composition_corpus_can_support_a_verdict`, para que el
  tier no pueda quemar una noche y devolver `passed: None`.

Los temas son deliberadamente aburridos y libres de conocimiento — cómo maneja
una panadería una entrega tardía de harina. Un corpus que necesitara datos
confundiría "el modelo no sabe esto" con "el ensamblaje a partir de fragmentos
rompió esto", que es el confusor que los corpus de clave de respuestas existen
para evitar.

**Comprobado contra el defecto del 4 de septiembre:** 0 de 36 prompts coinciden
con una pista secuencial, y 0 de 36 se planifican como cadena de dependencias. Un
corpus nuevo es exactamente donde vuelve esa clase de error, y sobre un prompt de
composición una cadena mal planificada sería *silenciosa* en lugar de visible en
la calificación — `test_no_composition_prompt_is_planned_as_a_dependency_chain`
está ahí por esa razón.

## 5. Lo que está deliberadamente ausente

Una ρ, una k, dos N. Sin editor, sin acarreo tipado, sin juez, sin calibración de
acuerdo declarada.

Cada una de esas cosas es una afirmación causal aparte, y un corpus barrido sobre
muchas celdas responde la pregunta del **estadístico máximo** — ¿hay *alguna*
celda que supere el umbral? — que se cumple sobre datos aleatorios. La maquinaria
de acuerdo sigue corriendo y se sigue reportando, porque el dato sale gratis una
vez que ocurre la corrida, pero **nada depende de ella**: el mapa de confianza se
ha medido seis veces, cinco nulas y la sexta retirada el 4 de septiembre, y aquí
no se vuelve a declarar.

## 6. Cómo ejecutarlo

```bash
bash scripts/run_ollama.sh comp-dev            # ~1 h, 12 prompts, NO verdict
bash scripts/run_ollama.sh comp-final <dir>    # ~2 h, 24 prompts, once
```

`comp-final` toma el **directorio** de la corrida dev, no un valor de τ: un
número pelado no puede llevar consigo sobre qué corpus se ajustó, y el tier
comprueba el umbral, el digest congelado y la partición antes de arrancar.

**Antes de pasar de dev a final, léase `baseline_at_ceiling`.** Si es 12 de 12 el
corpus se saturó como el anterior, y los tiers necesitan reconstruirse *antes* de
tocar la mitad final. Esa es la única decisión que `comp-dev` existe para
sostener, y es el último punto en el que puede cambiarse algo.

## 7. Qué establecería y qué no un resultado aquí

**Establecería:** una cota sobre lo que cuesta fragmentar en tres una composición
de prosa, sobre 24 prompts, con un presupuesto de contexto lo bastante generoso
como para que el brazo fragmentado no quede desabastecido — medido mecánicamente,
con un control que tenía que fallar y un umbral fijado de antemano.

**No establecería:** nada sobre el impuesto de coherencia, que marca +0.000 sobre
estos textos y se mide sobre una magnitud distinta; nada sobre el acuerdo ni
sobre el mapa de confianza; nada a una ρ a la que la arquitectura querría correr
de verdad, dado que con N = 8 no se puede bajar de 3.85 sobre este corpus en
absoluto.
