---
status: partially_withdrawn
stands: Secciones 5 y 6
reason: >
  Las secciones 1 a 4 y 7 descansan en una métrica de coherencia que no era
  neutral entre brazos: una misma respuesta idéntica puntúa 0.9375 por la
  convención de un brazo y 0.5000 por la del otro.
lang: es
---
# tables-dev — la hipótesis quedó refutada, y se encontró otra cosa

> ## ⚠ RETIRADO, 27 de agosto de 2026 — §1 a §4 y §7 no se sostienen
>
> **La métrica de coherencia no era neutral entre brazos.** Puntuar una misma
> respuesta idéntica de 16 oraciones a través de las convenciones de llamada de
> los dos brazos devuelve **0.9375 y 0.5000** — un impuesto aparente de **+46.7 %
> sobre un texto que nunca cambió**. Esa demostración no necesita ningún dato de
> esta corrida y no está en duda.
>
> **El tamaño del efecto sobre esta corrida no está establecido, y un borrador
> anterior de este aviso afirmó que sí lo estaba.** Citaba +17.2 % con N=2 y
> +14.6 % con N=8, a partir de una repuntuación de las propias respuestas de la
> corrida. Esas cifras salían de reconstruir los offsets de oración del
> ensamblador como una partición uniforme, y los offsets no están espaciados de
> manera uniforme — los fragmentos producen distinta cantidad de oraciones.
> `scripts/rescore.py` ahora contrasta esa reconstrucción con `results.csv` y
> **la rechaza**, por hasta 0.15. Las trazas de esta corrida no guardan los
> offsets, así que no se puede repuntuar de forma exacta. **La cifra corregida
> para esta corrida solo puede salir de volver a correrla.**
>
> Lo que sí está establecido: el sesgo existe, infla el brazo fragmentado y
> crece con N por construcción.
>
> Tres mecanismos, todos funciones de la partición y no de la respuesta: el
> conjunto esperado del detector de omisiones creció con N (0 para un baseline
> que pasa `plan=None`, 6 con N=2, **17 con N=8**); las mismas omisiones se
> atribuyeron round-robin entre N cabezas de fragmento, así que las omisiones de
> un documento ensuciaban una oración en el monolítico y hasta N en N tareas; y
> `missing_transition` y el `dangling_reference` anclado a costura solo pueden
> dispararse en las costuras, de las cuales una respuesta monolítica no tiene
> ninguna. Ver `swarmbly_v0/metrics.py` y el invariante que ahora se afirma en
> `tests/test_instrument.py`.
>
> **Lo que esto significa para §1:** la refutación de la hipótesis del impuesto
> de coherencia **queda retirada**. `table_summary` con ρ=3.5, N=2 vuelve a estar
> sin decidir, no refutada. Un cuarto mecanismo — `register_tense_shift`, una
> penalización de homogeneidad que se disparó en 0.00 de las oraciones del
> baseline y en 0.44 de las del brazo fragmentado — lo llevaría a +4.3 %, pero
> ese **no** se trató como un bug: en su lugar se agregó la directiva de tiempo
> verbal al corpus, así que la pregunta queda resuelta por medición y no por
> argumento.
>
> **Lo que sí se sostiene:** §5 (el juez aceptando 100 %), §6 (el mapa de
> confianza funcionando solo para afirmaciones agregadas) y §8 (la hipótesis
> sucesora). Ninguno de ellos descansa en la métrica de coherencia — descansan en
> la fidelidad numérica y en el acuerdo.
>
> **El corpus también cambió**, así que `tables24.json` pasa del digest
> `47ceb5f0…` al `0c5cb7e2…` y τ_sem = 0.805 ya no se aplica a nada.
>
> Hay que volver a correr `tables-dev` antes de citar cualquiera de §1–§4.
> Aproximadamente una hora.


**Corrida:** `results/tables-dev-20260826-115300`. Ocho prompts de tabla, la
mitad dev de `prompts/tables24.json` (sha256 `47ceb5f0…1ecaea`, verificado antes
de la corrida). ρ = 3.5, N ∈ {2, 8}, k ∈ {1, 3}. Sin editor, sin carry tipado.
Cinco familias de modelos sobre Ollama, transporte `openai-sdk`, **0
reintentos**, embeddings sin degradar, `harness_validation_only: false`. τ_sem
ajustado aquí en **0.805** y congelado para la mitad final. 40 filas.

Esta es la primera corrida del proyecto con una hipótesis declarada, una celda
nombrada y un control elegido de antemano para fallar. Todas las cifras de abajo
salen de `scripts/reanalyse.py`, que las recalcula desde los propios CSV de la
corrida a través de las funciones de la librería — se encontraron seis defectos
en el análisis después de terminada la corrida, y ninguno de ellos obligó a
regenerar nada.

---

## 1. La hipótesis declarada falla, y no por poco

**Declarado antes de la corrida:** `table_summary` con ρ=3.5, N=2 cuesta menos de
5 %, con el *límite superior* del intervalo por debajo de 0.05.

| celda | punto | IC 95 % (sobre prompts) | veredicto |
|---|---|---|---|
| **N=2, k=1** | **+20.6 %** | [+10.6 %, +29.7 %] | falla |
| **N=2, k=3** | **+16.0 %** | [+2.2 %, +27.6 %] | falla |
| N=8, k=1 *(control)* | +25.3 % | [+19.1 %, +31.2 %] | falla |
| N=8, k=3 *(control)* | +63.7 % | [+56.5 %, +72.3 %] | falla |

n = 8 prompts en cada celda. El intervalo en N=2, k=1 supera el 5 % por más de
cinco puntos en su límite *inferior*. Esto es una refutación, no un resultado sin
decidir.

`table_summary` con el fragmento más ancho era la única celda que este proyecto
había producido que se acercara al umbral. No sobrevive a su propio corpus.

**El control se comporta.** N=8 es peor que N=2 en ambos k, y con k=3 los
intervalos no se acercan a tocarse. El instrumento discrimina, así que la falla
en N=2 es una medición y no un instrumento que falla con todo.

## 2. Contra el +5.8 % de V6, y por qué dieciséis prompts más son la respuesta

V6 ubicaba esta misma celda — `table_summary`, ρ=3.5, N=2, k=1 — en **+5.8 %** con
un intervalo de [−2.2 %, +14.5 %]. Esta corrida la ubica en **+20.6 %**, [+10.6 %,
+29.7 %].

Los dos intervalos se solapan solo en [+10.6 %, +14.5 %]. No son formalmente
incompatibles, pero están forzados, y la razón se ve en ambos: cada uno descansa
en **ocho prompts**. Dos muestras de ocho, de dos extracciones distintas del mismo
generador, difieren en catorce puntos. Ese es el tamaño honesto de la
incertidumbre, y ninguna cantidad de cuidado en el análisis sustituye a los
dieciséis prompts de la mitad final.

Lo que esto *no* autoriza es elegir el más amable de los dos. La mitad dev es
donde se fijan los umbrales y las elecciones; la estimación pertenece a la mitad
final, corrida una sola vez.

## 3. El consenso y la fragmentación interactúan, y con fuerza

| | k=1 | k=3 | diferencia |
|---|---|---|---|
| N=2 | +20.6 % | **+16.0 %** | el consenso **ayuda** por 4.6 |
| N=8 | +25.3 % | **+63.7 %** | el consenso **perjudica** por 38.4 |

Con una partición gruesa tres réplicas mejoran el texto ensamblado. Con una fina
lo arruinan. Un fragmento de 56 tokens les da a tres modelos demasiado poco sobre
lo cual converger; el medoide elige una lectura, y ocho elecciones así
ensambladas en secuencia producen algo mucho peor que una sola generación de los
mismos fragmentos.

Este es el segundo mecanismo que muestra la misma dependencia de N. El carry
tipado de V6 dio +7.6 y +8.3 con N=2 y 4, y luego −14.6 y −3.4 con N=6 y 8. Dos
reparaciones independientes que ayudan en particiones gruesas y perjudican en las
finas es un patrón que merece un nombre y una prueba propia.

También es la razón por la que el criterio ahora nombra k. Filtrado solo por
categoría, ρ y N, la celda declarada daba **+18.3 %** — el punto medio de +20.6 %
y +16.0 %, un número que no describe a ninguno de los dos brazos. Con N=8 la misma
omisión habría promediado +25.3 % con +63.7 %.

## 4. El impuesto no está siguiendo la exactitud factual

Con k=1, a lo largo de las mismas celdas donde el impuesto de coherencia sube de
+20.6 % a +25.3 %:

| N | tokens/fragmento | impuesto de coherencia | fidelidad numérica | n calificados |
|---|---|---|---|---|
| 2 | 222 | +20.6 % | **80.0 %** | 65 |
| 8 | 56 | +25.3 % | **81.0 %** | 189 |

La exactitud no se mueve. Con k=3 cae modestamente — de 85.3 % a 78.0 % —
mientras el impuesto sube 48 puntos en el mismo intervalo.

**La fragmentación está costando coherencia, no corrección.** Las cifras que
enuncia un fragmento siguen siendo fieles a la tabla que alcanza a ver; lo que se
degrada es la forma de la respuesta ensamblada — la estructura de párrafos, las
restricciones de mencionar una sola vez, la repetición a través de las costuras.
Esa es una afirmación más estrecha y más útil que "la fragmentación degrada la
calidad", y le apunta al editor exactamente a la cosa que sí puede reparar.

## 5. El juez está muerto en este corpus

```
agreement vs judged quality: r = undefined over 723 units (acceptance rate 100.0%)
```

El juez de clase par aceptó **todo**. Esta es la falla que volvió ininterpretable
la corrida del 14 de agosto con 93.3 %; con 100 % la correlación no puede existir,
exista o no la señal. Todo número basado en el juez sobre prosa fundamentada debe
tratarse como ausente, no como nulo. La calificación contra ground truth no está
afectada y es lo que de todos modos especifica la Sección 11.4.

## 6. El mapa de confianza funciona — para una clase de afirmación

Este es el hallazgo, y los dos estadísticos de resumen que yo habría citado lo
ocultaban.

El acuerdo es `consistent / k`, así que con k=3 toma **cuatro valores**. La
exactitud en cada uno:

| acuerdo | afirmaciones agregadas | afirmaciones locales | agrupado |
|---|---|---|---|
| 0.00 | **0.000** (n=2) | 0.833 (n=6) | 0.625 |
| 0.33 | **0.250** (n=8) | 0.946 (n=74) | 0.878 |
| 0.67 | **0.625** (n=40) | 0.936 (n=47) | 0.793 |
| 1.00 | **0.750** (n=44) | 0.845 (n=97) | 0.816 |
| | **monótona, rango 0.75** | no monótona, rango 0.11 | no monótona |

Para las **afirmaciones agregadas** — enunciados que exigen ver filas que un
fragmento puede no tener — el acuerdo separa lo correcto de lo incorrecto a lo
largo de setenta y cinco puntos de exactitud, de forma monótona y sin
excepciones. Para las **afirmaciones locales** no separa nada: el rango es de once
puntos y el bin más alto es *peor* que los dos de abajo.

Agrupadas, las dos producen una curva que no es ninguna de las dos, y el AUC
agrupado da **0.481** — en el azar — mientras que el AUC agregado da **0.656**.

El marcado cuenta la misma historia:

| tasa de marcado | lift agrupado | agregadas | locales |
|---|---|---|---|
| 10 % | **0.52** | **2.21** | 1.62 |
| 20 % | 0.96 | **2.21** | 0.61 |
| 30 % | 0.76 | **2.21** | 0.61 |

Revisar las afirmaciones agregadas de menor acuerdo detecta errores a **2.2× la
tasa base**. La cifra agrupada dice que el mapa de confianza es peor que el azar.

**Por qué agrupar lo invierte.** Las dos clases se ubican en esquinas opuestas:
las afirmaciones agregadas llevan acuerdo *alto* (0.78) y exactitud *baja* (0.64);
las locales llevan acuerdo *bajo* (0.68) y exactitud *alta* (0.90). Agrupados, los
ítems de alto acuerdo son desproporcionadamente los equivocados. Las réplicas
coinciden con facilidad en un total o en un promedio porque son formulaicos de
redactar, no porque la aritmética esté bien.

Este es el sexto artefacto de agrupamiento en este proyecto y el primero que
corrió en la dirección contraria. Los cinco anteriores hacían que un nulo
pareciera un resultado; este hizo que un resultado pareciera un nulo.

**El lift es 2.21 en las tres tasas porque el predictor admite un solo corte.**
Los grupos de empate ahora se toman enteros — marcar el 20 % de un predictor de
cuatro valores pedía 64 ítems de un grupo de 82 que el predictor no puede
distinguir, y dos implementaciones correctas diferían en 0.6 de lift solo por el
orden de los empates. Lo que el mapa ofrece aquí en realidad es una sola decisión:
revisar las afirmaciones agregadas en las que coincidieron menos de dos de tres
réplicas. Eso es 10 de 94 ítems, y 8 de esos 10 están mal.

## 7. Una celda que no corrió con el presupuesto que nombra su etiqueta

| ρ objetivo | N | ρ alcanzado | desviación |
|---|---|---|---|
| 3.5 | 2 | 3.481 | −0.5 % |
| 3.5 | 8 | **3.907** | **+11.6 %** |

`rho_floor` con N=8 es 1.13, así que el piso no estaba forzando esto — el
empacador se pasó. El control N=8 recibió entonces *más* contexto que N=2 y aun
así le fue mucho peor, lo cual es conservador para la conclusión que se saca de
él. La dirección fue suerte, no diseño. Nada había verificado esto nunca;
`rho_fidelity` ahora sí lo hace, y una corrida con `within_tolerance: false`
debería nombrar la celda que deriva en vez de promediarla adentro.

## 8. La hipótesis sucesora, declarada antes de correr la mitad final

Registrada aquí el **26 de agosto de 2026**, después de la mitad dev y antes de
que se generara ninguno de los dieciséis prompts finales. Implementada como
`swarmbly_v0.experiment.flag_effect`; se corre con `bash scripts/run_ollama.sh
tables-final`.

> Entre las **afirmaciones agregadas**, marcar aquellas en las que coincidieron
> menos de dos de tres réplicas identifica errores por encima del azar, **dentro
> de un prompt**.

| | |
|---|---|
| **Estimador** | odds ratio común de Mantel-Haenszel, **prompt como estrato** |
| **Intervalo** | cluster bootstrap sobre prompts |
| **Pasa si** | el **límite inferior** del intervalo de 95 % supera **2.0** |
| **Corte** | `agreement < 2/3`, congelado como `FLAG_CUT` |
| **Grilla** | ρ=3.5, N=2, k=3 — una celda |
| **Control que debe fallar** | el mismo marcado sobre afirmaciones **locales** no debe pasar |

**Por qué un odds ratio y no el lift.** El lift no estratificado de dev da 2.21, y
no es confiable. Tres de ocho prompts no tenían ningún ítem marcado, y los tres
con más marcas eran los tres con más errores:

| prompt | marcados, equivocados | sin marcar, equivocados |
|---|---|---|
| drayage | 4 / 4 | 4 / 7 |
| consolidation | 2 / 3 | 7 / 11 |
| groupage | 1 / 1 | 4 / 13 |
| intake | 0 / 1 | 3 / 7 |
| recall | 1 / 1 | 2 / 10 |
| manifest, reconciliation, staging | 0 / 0 | 6 / 36 |

Un lift calculado a través de los prompts no puede separar *esta afirmación está
mal* de *este prompt es difícil* — y solo lo primero vale algo, porque lo segundo
ya se obtiene de la tasa de error. Estratificado, el efecto sobrevive:

| clase | OR | IC 95 % | estratos que contribuyen | marcados |
|---|---|---|---|---|
| **agregadas** | **3.47** | **[0.80, 11.19]** | 5 / 8 | 10 / 94 |
| locales *(control)* | 0.56 | [0.14, 1.09] | 8 / 8 | 80 / 224 |

Dos cosas para leer aquí. El intervalo de las agregadas **no excluye 1.0**, así
que dev no establece el efecto — lo dimensiona. Y el control hace más que fallar:
con OR 0.56 el mismo marcado es *peor que inútil* sobre las afirmaciones locales.
Las dos clases son opuestas en signo, no meramente distintas en grado, que es lo
que predice un mecanismo específico de la afirmación y lo que un artefacto de
dificultad del prompt no predice.

**Por qué la vara está en 2.0.** Un odds ratio de 2 es más o menos donde marcar
duplica la tasa de aciertos de un revisor, que es el efecto más chico que paga al
revisor. No es una vara construida para ser superada: el propio límite inferior de
dev es **0.80**.

**Por qué solo N=2 y k=3.** La hipótesis es sobre afirmaciones, no sobre el tamaño
del fragmento; k=1 no tiene acuerdo que medir; y N=8 corrió con ρ 3.91 contra un
objetivo de 3.5, así que esa celda no midió lo que dice su etiqueta.

**El riesgo de hacer esto, dicho sin rodeos.** Reemplazar una hipótesis refutada
por otra descubierta en los mismos datos es la manera en que un proyecto se
convence a sí mismo de salir de un resultado negativo. Tres cosas son portantes
contra eso, y si alguna de ellas cede la sucesora no vale nada: la refutación del
impuesto de coherencia **se sostiene** y no está retirada; esta declaración queda
registrada antes de que exista la mitad final; y la mitad final se gasta una sola
vez, en esto, con el estimador, el corte, el umbral y el control todos fijados
arriba.

## Lo que sigue

1. **No correr todavía la mitad final.** La hipótesis declarada está refutada en
   dev, y correr dieciséis prompts más para refutarla otra vez gasta dos horas en
   una pregunta ya respondida. La mitad final vale la pena gastarla en una
   hipótesis que haya sobrevivido a dev. Esta no lo hizo.
2. **El mapa de confianza de afirmaciones agregadas es esa hipótesis**, declarada
   en §8 arriba con su estimador, corte, umbral y control fijados. Es el primer
   resultado de calibración positivo del proyecto que es monótono, tiene un
   mecanismo y enuncia una decisión sobre la cual un usuario podría actuar.
3. **Corregir la deriva de ρ en N=8** antes de que alguna corrida use N=8 como
   punto de comparación.
4. **La interacción consenso × N necesita su propia prueba.** +16 % con N=2 contra
   +64 % con N=8 es la interacción más grande de cualquier corrida hasta ahora, y
   el carry tipado mostró la misma forma.
5. **Retirar el juez sobre prosa fundamentada.** 100 % de aceptación no es una
   medición.
6. **`table_summary` con N=2 ya no es un candidato vivo.** Era el último. Ninguna
   celda de este proyecto tiene hoy un camino creíble al umbral de 5 %, y eso
   debería decirse sin rodeos en vez de dejarlo para que el próximo corpus lo
   redescubra.
