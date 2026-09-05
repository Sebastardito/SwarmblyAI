# Prerregistración — `comp-final-once`

**Escrita el 5 de septiembre de 2026, después de `comp-dev-once` y ANTES de que
`comp-final-once` corra.** Nada de lo que sigue puede cambiar una vez iniciada
la corrida.

## La hipótesis

> Con `term_once` impuesto **mecánicamente en el ensamblador**, la composición a
> ρ = 4.0, N = 3, k = 1 cuesta **menos de 5 puntos** de satisfacción de
> restricciones contra su línea base monolítica — juzgado sobre la **cota
> superior** de un bootstrap agrupado por prompt, con **N = 8 como control que
> debe fallar**.

* **Estimador:** diferencia pareada media, monolítico menos fragmentado, sobre
  `constraint_score_comparable`.
* **Intervalo:** bootstrap por clusters sobre prompts, 24 clusters.
* **Pasa si:** la cota superior del IC 95 % queda por debajo de 0.05.
* **Split:** final, 24 prompts, heredando τ_sem de
  `comp-dev-once-20260905-120541`.

Es una **hipótesis distinta sobre un sistema distinto**. `comp-final` del 4 de
septiembre juzgó la tubería *sin* esta imposición y respondió NOT MET por 23.51
puntos. Esa respuesta sigue en pie y no se revisa aquí.

## El costo, dicho antes

**Éste es el SEGUNDO uso del split final.**

El valor de un split final viene de evaluarse una sola vez. Usarlo dos veces lo
debilita, aunque la hipótesis y el sistema sean distintos: cada uso es otra
oportunidad de que un resultado favorable aparezca por azar. Queda escrito aquí
y lo imprime el propio tier, porque un costo que no se nombra antes se convierte
en una nota al pie después.

**Un tercer uso exige corpus nuevo.** El generador v2 se construye en paralelo
justamente para eso.

## Qué esperar, dicho antes y no después

En dev la estimación puntual se movió de **+18.40 a +8.61**, pero la cota
superior se quedó en **+22.08**. Un intercambio de +12 / −2 en una sola clase de
restricción no tiene por qué bastar para bajar una cota superior por debajo de 5
puntos.

**NOT MET sigue siendo el resultado más probable.** Y seguiría siendo el mejor
número que este proyecto ha producido: `term_once` pasó de 6/24 a 18/24, por
encima del techo monolítico de 13/24, sobre fragmentos reales.

## Qué invalidaría la corrida (no "refutaría": la haría ilegible)

| # | condición | consecuencia |
|---|---|---|
| 1 | `term_once_sentences_removed` = 0 en todas las celdas | El paso no disparó. La comparación es **nula**, cualquiera que sea el puntaje. El tier lo imprime en letras. |
| 2 | El control a N=8 **pasa** | El instrumento no separa los brazos y **ninguno** de los dos números es evidencia. Peor noticia que un fallo de la celda declarada. |
| 3 | `n_prompts` < 20 | No hay veredicto, sea cual sea la estimación puntual. |
| 4 | Cualquier fila excluida por piso, techo o plan rechazado | Las curvas se leen sin ellas; si son muchas, la celda no se midió. |

## Qué NO se afirma

* **Nada sobre calidad.** Borrar una oración para satisfacer una regla de conteo
  acorta el texto y puede empeorarlo de formas que ninguna restricción de este
  corpus verifica. El puntaje cuenta restricciones satisfechas, y eso es todo lo
  que es.
* **Nada sobre los otros ~19 puntos.** `comp-oracle` puso el **1.4 %** de la
  pérdida al alcance de la asignación. El residuo es `no_repeated_ngram` (−7 de
  12, irreducible para trabajadores paralelos) y `must_mention` (−5 de 36,
  efecto de tamaño de fragmento). Este cambio no toca ninguno de los dos.
* **Nada sobre N = 8.** El control existe para fallar, y en dev el dedup casi no
  disparó ahí — 8 eliminaciones contra 30 a N=3 — porque a N=8 el problema es
  omisión y no se puede deduplicar lo que nunca se escribió.
* **Nada fuera de modelos de 3B.** Un modelo que siguiera "menciona este
  término" de forma confiable movería `must_mention` y dejaría
  `no_repeated_ngram` donde está.

## La compuerta que se añadió para esta corrida

`read_dev_run` ahora exige que **el pipeline de ensamblado coincida**: un
`-final` con `--enforce-term-once` sólo acepta un `-dev` que también lo tuviera,
y viceversa. Antes se verificaban cuatro cosas — umbral, corpus, split, código —
y esta es la quinta.

Sin ella, un umbral ajustado por una tubería que impone `term_once`
mecánicamente podría emparejarse en silencio con otra que se lo pide al modelo, y
el emparejamiento es todo el valor de tener un split. Probada en las dos
direcciones.

## La corrida — y por qué dev se corre otra vez primero

**`comp-dev-once-20260905-120541` ya no sirve como dev para esta final**, y las
dos compuertas lo dicen por separado:

* `code_sha256` se movió — `feff3e83…` en esa corrida contra `136fc431…` hoy.
  Añadir `enforce_term_once` a la metadata **es** un cambio de código. Un umbral
  ajustado antes de un cambio de código es un umbral llevado a través de un
  cambio de código, que es la misma fuga que llevarlo a través de un cambio de
  corpus.
* Esa corrida es anterior al campo `enforce_term_once`, así que no dice con qué
  tubería se ajustó su umbral. La compuerta la rechaza **por esa razón propia**,
  no confundiéndola con un desajuste — leer "ausente" como "false" mandaría al
  operador a arreglar lo que no está roto.

No hay override, y el remedio es el que la compuerta ha dicho siempre: volver a
correr dev.

Los números de dev citados arriba (+8.61, cota superior +22.08, `term_once`
6/24 → 18/24) siguen siendo la evidencia que motiva esta hipótesis. Lo que la
re-corrida produce es un umbral y una huella válidos para juzgar el split final;
si sus estimaciones puntuales salen muy distintas de las del 12:05, **eso es
información sobre la varianza entre corridas** y hay que decirlo antes de mirar
la final.

```bash
bash scripts/run_ollama.sh comp-dev-once                                  # ~1 h
bash scripts/run_ollama.sh comp-final-once results/comp-dev-once-<stamp>  # ~2 h
```
