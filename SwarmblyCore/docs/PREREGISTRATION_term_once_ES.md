---
status: current
lang: es
---
# Prerregistración — `term_once` en el ensamblador

> **CERRADA 5 septiembre 2026.** Endpoint primario CUMPLIDO con el doble del
> margen: +8.61 contra el +13.40 exigido. La condición de refutación 2 SÍ se
> disparó (27/36 contra 29/36) y estaba mal especificada — cualquier método
> basado en borrar oraciones cuesta algo en `must_mention`. Las dos lecturas
> quedan registradas. Ver `docs/RESULTS_2026-09-05_term_once.md`.

**Escrita:** 5 de septiembre de 2026, después de `comp-oracle` y **antes** de que
`comp-dev-once` corra. Nada de lo que sigue puede cambiarse una vez que esa
corrida empiece.

## La afirmación

> Imponer `term_once` **mecánicamente en el ensamblado** — conservar la primera
> oración que lleva cada término-una-vez, borrar las demás — mueve la celda de
> composición declarada (ρ = 4.0, N = 3, k = 1) en **al menos 5 puntos**, desde
> el **+18.40** de la corrida dev con k=1 hasta **+13.40 o mejor**.

Juzgado sobre `mean_delta` de
`composition_criterion[composition@rho=4.0@N=3@k=1]`, split dev, contra la
corrida `comp-dev` del 4 de septiembre. **Dev contra dev.** Doce prompts está por
debajo de `MIN_CLUSTERS_FOR_A_VERDICT`, así que esto es una estimación puntual y
el tier no imprimirá veredicto; el intervalo no debe citarse como cota.

## Por qué 5 puntos, y de dónde sale el número

`comp-oracle` midió el mecanismo directamente, sobre este corpus, sobre este
split:

| brazo | `term_once` |
|---|---|
| monolítico | 13/24 |
| tubería enviada | 6/24 |
| oráculo, briefs redundantes | 6/24 |
| **oráculo, redundantes + dedup mecánico** | **14/24** |

Ocho restricciones ganadas de 24. Costó **dos** `must_mention` y **dos**
`words_per_paragraph`, ambas de oraciones borradas que llevaban algo más — y
`words_per_paragraph` lo impone el ensamblador y de todos modos queda excluida
del puntaje de titular.

Ocho ganadas, dos costadas, sobre un denominador de unas 60 comprobaciones
comparables por brazo. Cinco puntos es deliberadamente menos de lo que sugiere
esa aritmética, porque los fragmentos del oráculo no son los fragmentos de la
tubería enviada.

## Por qué debería ir mejor aquí que en el oráculo, y por qué eso es un riesgo

El oráculo aplicó el dedup a su **propio texto redundante**, que sacó 17/24 en el
bucket de `must_mention`, que también es `term_once`. La **tubería enviada saca
21/24 en el mismo bucket**, porque cada fragmento ve el prompt entero y varios
mencionan el término. El dedup no toca `must_mention` salvo a través de las
oraciones borradas, así que aplicado al brazo enviado debería conservar 21/24 *y*
ganar el `term_once`.

Ése es el razonamiento, y es exactamente la clase de razonamiento sobre la que
este proyecto ya se ha equivocado antes. Supone que los borrados se comportan
igual sobre fragmentos reales que sobre los del oráculo. Puede que no: el brazo
enviado escribe 8.9 párrafos donde el oráculo escribe 2, así que hay más
oraciones que borrar y más ocasiones de que un borrado se lleve consigo un
término exigido.

## Qué lo refutaría

Cualquiera de estas:

* `mean_delta` en **+18.40** o por encima — el cambio no compró nada;
* la tasa de `must_mention` igual o por debajo de la de la tubería enviada — los
  borrados cuestan más sobre fragmentos reales que sobre los del oráculo, y la
  interacción es el hallazgo;
* `term_once_sentences_removed` en **0 en todas partes** en `results.csv` — el
  paso no disparó y la comparación es nula, digan lo que digan los puntajes.

El control a N = 8 debe seguir fallando, como en todo tier de composición.

## Qué NO se afirma

* Nada sobre el split **final**. Ésta es una comparación dev contra dev y decide
  si el cambio vale una corrida final prerregistrada, no si funciona.
* Nada sobre los otros 19.2 puntos. `comp-oracle` puso el **1.4%** de la pérdida
  extremo a extremo al alcance de la asignación; el residuo es `must_mention`
  (−9 comprobaciones) y `no_repeated_ngram` (−7 comprobaciones) contra el
  monolítico, y este cambio no ataca ninguno de los dos.
* Nada sobre la **calidad**. Borrar una oración para satisfacer una regla de
  conteo acorta el texto y puede empeorarlo de formas que ninguna restricción de
  este corpus verifica. El puntaje es un conteo de restricciones satisfechas, y
  eso es todo lo que es.

## La bandera, y por qué está apagada por defecto

`--enforce-term-once` cambia la **respuesta entregada** de cada celda. Toda cifra
de composición publicada se produjo sin ella, así que un valor por defecto que
reclasificara el registro en silencio sería el defecto de instrucción obsoleta
con un radio de daño peor.

Es además una **bandera y no un brazo pareado**, a diferencia de `--editor` y
`--typed-carry`. Ésos existen como tuplas en `SweepConfig` porque las dos mitades
están pensadas para correr juntas contra una sola línea base. Ésta no puede: un
barrido que produjera las dos llevaría dos condiciones `fragmented` bajo una sola
etiqueta, que es el defecto de agregación que este proyecto ha corregido cuatro
veces (ρ sobre N, N sobre k, una tasa sin su denominador, `_full` sobre
`comparable`). Para comparar, hay que correr dos tiers.

La función que llama el ensamblador es
`swarmbly_v0.constraints.enforce_term_once` — el mismo objeto que midió
`comp-oracle`, aseverado por un test. Dos implementaciones de un mismo
comportamiento se desvían, y la desviación se le atribuye al brazo que la nota
segundo.

## La corrida

```bash
bash scripts/run_ollama.sh comp-dev-once     # ~1 h
```
