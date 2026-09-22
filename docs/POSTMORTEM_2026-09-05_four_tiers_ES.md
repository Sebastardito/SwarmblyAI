---
status: current
lang: es
---
# Post-mortem — cuatro tramos fallaron seguidos, y el patrón es mío

**Escrito:** 5 de septiembre de 2026, después de que Seb hiciera la pregunta
correcta: *¿qué pasó con el proceso de revisión, y por qué de golpe hay tantos
errores?*

**Costo:** unas quince horas de su cómputo, repartidas en cuatro corridas
abortadas, ninguna de las cuales produjo una cifra usable.

Esto no es una disculpa. Es un diagnóstico, porque la respuesta resultó ser
específica y comprobable en vez de «fui descuidado».

---

## 1. Las cuatro fallas

| # | tramo | qué pasó | clase |
|---|---|---|---|
| 1 | `v0` | ρ 5.5 pedido en N=2, **techo** de empaquetado 4.90. Quedó corto, la invariante abortó a la quinta hora. | la grilla se topa con el corpus |
| 2 | `v0` | se movió la grilla; ρ 3.95 en N=8 sobre una **cadena**, cuyos acarreos obligatorios fuerzan un exceso en la banda por encima de su piso. +5.6 %, abortada a la quinta hora. | la grilla se topa con el corpus |
| 3 | *(encontrada mientras se diagnosticaba #1)* | `tables-dev`/`tables-final` venían corriendo su celda **declarada** por encima del techo desde siempre, quedándose cortas un −3.4 % sistemático que pasaba el chequeo de fidelidad. | la grilla se topa con el corpus |
| 4 | `v0` | el barrido **se completó** — `results.csv`, `summary.json`, `report.html` todos escritos — y `run_tier` lo marcó FAILED porque yo no había creado el subdirectorio por N al que le hace tee de `run.log`. | shell |

## 2. Qué cubrió realmente el proceso de revisión, y qué no

La revisión `/engineering:*` y `/data:*` de fines de agosto fue real y funcionó:
encontró doce defectos del instrumento, todos unilaterales hacia la hipótesis
del propio proyecto, y produjo `REVISION_2026-08-12.md`, ADR-001 y la mayoría de
las compuertas que hoy están en el harness.

**Revisó código que ya existía.** En las veinticuatro horas previas a este
post-mortem escribí nueve commits y unas dos mil líneas nuevas — un criterio de
composición, un generador de corpus, un runner de benchmark, una reparación del
segmentador, un techo de ρ, un predictor de ρ, un chequeador de grilla — y no le
apliqué a nada de eso nada parecido a esa profundidad de revisión.

Eso por sí solo sería una respuesta ordinaria («revisar también el código
nuevo»). No es la respuesta real, porque **una revisión de código no habría
atrapado ninguna de las cuatro.** Las fallas 1–3 son sobre cómo una grilla se
topa con un corpus, cosa que ninguna lectura del código revela; la falla 4 es
shell, que la suite de Python no puede ejecutar.

## 3. El hueco real, y es una sola línea

**Verifiqué todo menos lo que estaba entregando.**

Para cada una de las cuatro corrí: la suite unitaria (648 pruebas, todas
pasando), y para las fallas de grilla `check_grid.py`, que empaqueta las celdas
correctamente y no dice nada del resto del pipeline. **Ni una sola vez corrí
`bash scripts/run_ollama.sh v0`.**

La evidencia es limpia, y es la razón por la que existe este post-mortem en vez
de una resolución general de tener más cuidado:

| tramo | ¿lo corrí de punta a punta antes de entregarlo? | resultado |
|---|---|---|
| `comp-dev` | **sí** | funcionó a la primera |
| `comp-final` | **sí** | funcionó a la primera, produjo el veredicto |
| `v0` | no | falló tres veces |
| `smoke` | no | se entregó con guía desactualizada y sin wrapper |

Dos ensayados, dos no. Dos funcionaron, dos no. Eso no es una coincidencia y no
es cuestión de esfuerzo — nada corre el tramo salvo correr el tramo.

## 4. Qué se construyó en respuesta

**Modo ensayo.** `SWARMBLY_REHEARSE=1 bash scripts/run_ollama.sh <tier>` corre el
tramo de punta a punta contra el backend mock, sin Ollama y sin modelos, en
segundos. Las mismas funciones, las mismas invocaciones, el mismo wrapper
`run_tier`, las mismas post-condiciones — solo el backend y el preflight quedan
stubbeados, y el cambio ocurre **dentro de `run_tier`**, así que un tramo no
puede ensayarse con un comando distinto del que se entrega. Toda corrida queda
sellada con `harness_validation_only: true`.

**Ahora es una prueba.** `test_every_tier_rehearses_clean` corre los siete
tramos por el runner real como parte de la suite. Es lenta para los estándares
de ese archivo — 84 segundos contra 25 — y ese es el intercambio correcto contra
cinco horas.

**Y de inmediato encontró dos más**, antes de que ninguna llegara a Seb:

* `v3c` habría abortado en ρ 2.5, N=4 sobre la misma cadena, +8.6 %. Movido a
  3.0, que `check_grid` dice que está dentro del rango usable. **Son tres horas
  que no costó.**
* `smoke` era el único tramo que despachaba `python3 -m swarmbly_v0`
  directamente en vez de pasar por `run_tier`, así que el tramo que un operador
  corre *primero* — para averiguar si algo anda mal — era el único sin marcador
  FAILED y sin post-condición. Un aborto ahí habría impreso un traceback y
  después «Done».

**`run_tier` ahora crea su propio directorio de salida**, así que ningún
llamador puede repetir la falla 4.

### Y después el ensayo produjo un defecto propio

Los primeros siete ensayos escribieron dentro de `results/` bajo los nombres
reales de los tramos. Uno de ellos fue `results/comp-dev-20260905-045427` — más
nuevo que `results/comp-dev-20260904-122727`, que es la corrida contra la que se
calibró el veredicto de composición declarado. Todo lector en este proyecto
selecciona una corrida por glob y toma la última, incluido el fragmento del
runbook que escribí yo mismo. **Una corrida mock se había vuelto el `comp-dev`
más nuevo en disco.**

`harness_validation_only: true` estaba en sus metadatos y lo habría atrapado si
alguien leyera los metadatos primero. Esa es precisamente la suposición sobre la
que este proyecto se equivocó cuatro veces. El sello es una etiqueta; la guarda
tiene que ser un hecho. Los ensayos ahora escriben en `results/rehearsal/`, que
`results/<tier>-*` no captura, y `test_every_tier_rehearses_clean` verifica
después de cada tramo que no apareció ningún directorio `results/<tier>-*`
nuevo.

Que el arreglo de un hueco de verificación abriera de inmediato un agujero de
procedencia vale decirlo sin rodeos: **la maquinaria de seguridad nueva es
código nuevo, y el código nuevo no queda exento de las compuertas.** Los siete
directorios sueltos fueron sacados de `results/` en la copia de trabajo.

## 5. Lo que hice mal dos veces, aparte del proceso

En las fallas 1 y 2 parcheé la grilla de ρ **a partir de una hipótesis sobre la
causa**, la entregué, y me equivoqué las dos veces. Después probé tres
explicaciones más para la falla 2 — cuantización, contabilidad de separadores,
un piso realizado por tokens obligatorios — y medí cada una como falsa.

El arreglo que funcionó fue dejar de hipotetizar: `predict_rho` empaqueta una
celda exactamente como lo hace el barrido y devuelve el ρ alcanzado en
milisegundos, como un límite superior y no como una muestra. Debí haberlo
escrito después de la primera falla, no de la tercera. Una guarda que había
construido sobre la hipótesis del piso realizado fue revertida antes de
entregarla, porque no pude demostrar que se disparara — esa parte, al menos, fue
el instinto correcto aplicado demasiado tarde.

## 6. Qué dice esto del proyecto, que es la parte que vale la pena conservar

Cada una de estas fue atrapada por una compuerta. Las fallas 1, 2 y 4 abortaron
en vez de producir un número plausible; la falla 3 se encontró mientras se
diagnosticaba la falla 1 y venía etiquetando mal, en silencio, una celda
**publicada** durante dos días.

Eso es el harness funcionando como fue diseñado, y vale decirlo sin rodeos
frente a la frustración: **la alternativa a quince horas desperdiciadas eran
quince horas que producían una cifra en la que nadie podía confiar.** Este
proyecto ya retiró cuatro documentos, y cada uno se retiró porque un número
llegó a una tabla que nunca debió haberse calculado.

Lo que cambió hoy es que las compuertas ahora se disparan en **segundos** en vez
de horas.

## 7. La regla

> Ningún tramo se entrega hasta que haya sido ensayado de punta a punta.

Cuesta segundos. Las cuatro fallas de arriba costaron quince horas, y a cada una
la habría atrapado.
