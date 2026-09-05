# comp-dev-once — la predicción se cumplió, y con el doble del margen

`results/comp-dev-once-20260905-120541`. Digest del corpus `e9e382b9…`,
`harness_validation_only: false`, `embeddings_degraded: false`, **cero filas
excluidas** por ningún motivo.

**Prerregistrado:** al menos 5 puntos de mejora sobre el +18.40 del dev k=1, es
decir **+13.40 o mejor**.

**Resultado: +8.61 puntos.** Casi el doble del margen predicho.

---

## 1. El mecanismo, contado en restricciones

La comparación limpia no es contra el dev del 4 de septiembre, cuyo brazo
monolítico fue una muestra distinta. Es contra el brazo `real` de `comp-oracle`:
**misma celda** (ρ 4.0, N 3, k 1), **mismo valor monolítico** (0.844), mismo
corpus, mismo día.

| clase | total | monolítico | real, sin dedup | **real + DEDUP** |
|---|---|---|---|---|
| `must_mention` | 36 | 32 | 29 | **27** |
| `must_not_mention` | 12 | 12 | 12 | 12 |
| `no_repeated_ngram` | 12 | 11 | 4 | 4 |
| `no_repeated_sentence` | 12 | 12 | 11 | 11 |
| **`term_once`** | 24 | **13** | **6** | **18** |
| `paragraph_count` | 12 | 12 | 0 | 0 *(excluida)* |
| `words_per_paragraph` | 12 | 12 | 0 | 0 *(excluida)* |

**`term_once`: 6 → 18 de 24.** Doce restricciones ganadas, y **muy por encima
del brazo monolítico**, que sólo alcanza 13. Costó **dos** `must_mention`.

Neto sobre las 96 comprobaciones comparables: **62 → 72**. Que es exactamente el
0.649 → 0.758 de los promedios por prompt.

El oráculo había predicho +8 / −2. Sobre los fragmentos reales dio **+12 / −2**,
porque el brazo real ya partía de 21/24 en `must_mention` — su redundancia
accidental — mientras el oráculo redundante partía de 17/24. La razón por la que
debía funcionar mejor aquí que en el oráculo se cumplió, y por el motivo
declarado.

---

## 2. Cambió la forma del resultado, no sólo la media

| | comp-final (24 prompts, sin dedup) | **comp-dev-once (12 prompts, con dedup)** |
|---|---|---|
| prompts donde fragmentar perdió | 19 de 24 | **5 de 12** |
| empatados | 0 | **4** |
| prompts donde fragmentar **ganó** | 0 | **3** |
| mediana | — | **+0.00** |

Tres prompts donde el brazo fragmentado **superó** al monolítico
(`granary_dry` −0.167, `harbour_storm` −0.167, `relay_winter` −0.100). En
`comp-final` no hubo ni uno solo en veinticuatro.

La mediana es cero: en al menos la mitad de los prompts, fragmentar ya no cuesta
nada medible en este instrumento.

---

## 3. Lo que este resultado NO es

**No es un veredicto.** Doce clusters contra un piso de veinte. El tier imprimió
`VERDICT NONE` y tiene razón.

**El intervalo no baja del umbral.** [−2.78, **+22.08**]. El criterio declarado
exige que la cota superior quede por debajo de 5 puntos. La estimación puntual
se movió mucho; **la cota superior no**. Con 24 clusters el intervalo se
estrecharía, pero nada garantiza que baje de 5.

**El control sigue fallando, y fuerte:** N=8 en +63.40, IC [+56.11, +71.18]. El
instrumento sigue separando los brazos, que es la comprobación que más importa —
si el control también se hubiera derrumbado, el dedup estaría maquillando todo.

**El dedup casi no dispara a N=8:** 8 oraciones eliminadas en doce prompts,
contra 30 a N=3. A N=8 el problema no es duplicación sino **omisión** — casi
todos los `mentions_*` fallan — y no se puede deduplicar lo que nunca se
escribió.

---

## 4. Una de mis tres condiciones de refutación se disparó

Las escribí antes de la corrida. Éstas son:

| # | condición | ¿se disparó? |
|---|---|---|
| 1 | `mean_delta` ≥ +18.40 | **No.** +8.61 |
| 2 | tasa de `must_mention` igual o por debajo de la tubería enviada | **SÍ.** 27/36 contra 29/36 |
| 3 | `term_once_sentences_removed` = 0 en todas partes | **No.** 30 eliminaciones a N=3 |

**La condición 2 se disparó**, y hay que decirlo antes que cualquier otra cosa.

Ahora bien, el mecanismo que esa condición fue escrita para detectar **no
ocurrió**. La escribí así: *"las eliminaciones cuestan más en fragmentos reales
que en los del oráculo, y la interacción es el hallazgo"*. Medido: sobre el
texto del oráculo el dedup costó **−2** `must_mention`; sobre el texto real costó
**−2**. Idéntico.

Así que **la condición estaba mal especificada**: cualquier método basado en
borrar oraciones tiene que costar *algo* en `must_mention`. Una condición que se
dispara siempre que el método hace cualquier cosa no es una condición de
refutación, es una tautología. Debió decir *"pierde más en `must_mention` de lo
que gana en `term_once`"*, o *"pierde más que las 2 que perdió el oráculo"*.

**Señalar esto después de ver los datos es exactamente la maniobra que hay que
mirar con lupa**, así que el registro se queda con las dos lecturas: el endpoint
primario se cumplió con el doble del margen, y una condición secundaria se
disparó por estar mal escrita. La corrección para el futuro es nombrar el
**intercambio**, no la dirección.

---

## 5. Dónde queda el residuo

Contra monolítico, en comprobaciones:

| clase | perdidas | ¿alcanzable? |
|---|---|---|
| `no_repeated_ngram` | **−7** de 12 | **No.** Es propiedad de un *par* de fragmentos; ningún trabajador paralelo puede verificar un par |
| `must_mention` | **−5** de 36 | Parcialmente. Es efecto de **tamaño de fragmento**: menos espacio para acomodar los términos |
| `no_repeated_sentence` | −1 de 12 | Igual que la primera |
| **`term_once`** | **+5** de 24 | Ya resuelto — y por encima del techo |

Después de este cambio, **`no_repeated_ngram` es la mitad del residuo**. Y es la
clase irreducible. Lo que queda por ganar está en `must_mention`, y `v0` ya dijo
por dónde: fragmentos más grandes, N más chico.

---

## 6. Qué sigue, y su costo

La única forma de convertir esto en una afirmación es **24 clusters**, o sea
`comp-final` con el flag.

Eso tiene un costo que hay que nombrar: **sería el segundo uso del split final.**
Su valor viene de evaluarse una sola vez. Usarlo dos veces lo debilita, aunque la
hipótesis sea distinta y el sistema también.

Tres opciones, y la decisión es tuya:

| opción | qué cuesta | qué gana |
|---|---|---|
| **a.** `comp-final --enforce-term-once` contra este dev | segundo uso del split final, registrado como tal | un veredicto real, en ~2 h |
| **b.** Corpus nuevo de 36 prompts, dev+final frescos | revalidar los tiers de dificultad; medio día | el split final vuelve a valer una vez |
| **c.** No correrlo todavía | nada | el resultado se queda como descripción dev |

Mi recomendación es **(a), declarado como segundo uso, con prerregistración
escrita antes**, y dejando dicho que un tercer uso exige corpus nuevo. La razón:
la estimación puntual se movió 10 puntos, pero la cota superior sigue en +22, y
el único dato que decide si eso es señal o ruido de doce clusters es correrlo con
veinticuatro.

Y una advertencia sobre qué esperar: **es perfectamente posible que el veredicto
siga siendo NOT MET.** Un intercambio de +12 / −2 en una clase no tiene por qué
bastar para bajar la cota superior de un intervalo por debajo de 5 puntos. Eso
seguiría siendo el mejor resultado que este proyecto ha producido, y conviene
decirlo antes de la corrida y no después.
