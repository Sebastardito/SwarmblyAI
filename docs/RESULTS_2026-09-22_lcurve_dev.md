---
status: current
lang: es
note: >
  La corrida no habla sobre L. Se publica porque el defecto que encontró es de
  método y no de resultado.
---
# lcurve-dev — el instrumento no tiene rango, y el control no lo dijo

**Corrida:** `results/lcurve-dev-20260922-080202`. Corpus `prompts/lcurve.json`,
digest `a21100e2…` verificado antes de arrancar. 24 documentos dev, seis
tamaños, 12 celdas de la rejilla L × N. Cinco familias de modelos sobre Ollama.

**La corrida terminó limpia y no dice nada sobre L.** Esa segunda mitad tardó
en verse, y cómo tardó es el resultado.

---

## 1. Lo que imprimió

```
CELDA DECLARADA: REHUSADA -- 16 clusters, y el piso son 20.
CONTROL `local`: +0.000 (tolerancia 0.05)
```

Ninguna condición de invalidación se disparó. El rechazo de la celda era lo
esperado: la mitad dev tiene 16 documentos con contraste de L y el piso son 20,
así que dev nunca iba a dar veredicto — para eso está la mitad final.

Leído así, el informe dice: *la tubería corrió, el control pasó, seguí al
final.* Y eso habría sido falso.

## 2. Lo que había debajo

Exactitud del brazo monolítico, que es el techo de cualquier lectura:

| | `global` | `local` |
|---|---|---|
| monolítico, todos los tamaños | **1 / 72** | 14 / 48 |
| fragmentado, todos los tamaños | 3 / 144 | 10 / 96 |

Y por tamaño, el monolítico en `global`: **0.08 con S = 10**, cero en todos los
demás. S = 10 es una tabla de **diez filas** que cabe entera en la ventana de
cualquier modelo del pool.

Las doce celdas de la rejilla leen entre 0.000 y 0.083 en `global`. No hay
curva. No hay nada que medir.

## 3. Por qué el control marcó cero

El control declarado eran las preguntas `local`: si el tamaño del fragmento
mueve la exactitud sobre una fila nombrada, lo roto está en la tubería. Marcó
**+0.000**.

Marcó cero porque **los dos extremos estaban en el piso**. Una diferencia
pareada entre dos fragmentaciones que aciertan cero y cero es cero, y es cero
tanto si la tubería está sana como si está rota.

**Un control que pasa en el piso no es un control.**

Ése es el defecto, y es de la prerregistración, no de la corrida: cuatro
condiciones de refutación escritas antes de mirar datos, y ninguna que
preguntara si el instrumento tiene rango dinámico. La corrida hizo exactamente
lo que se le pidió y lo informó exactamente como se le pidió.

## 4. Qué se descartó, y con qué

**La calificación está sana.** Una respuesta perfecta construida desde la clave
de cada documento saca **100 % en los 72 documentos** del corpus. No es una
opinión: es un test, y queda en la suite. El defecto que mató dos corridas de
feasibility —el corpus escribiendo `[Q1]` donde el calificador esperaba `01`—
no está aquí.

**Queda abierto** si los modelos producen valores correctos en un formato que
el extractor rechaza. Entre las respuestas incorrectas aparecen formas como
`dado='[03] 215'` para una pregunta que no era la 03, que huele a desalineación
de etiquetas. No se puede decidir desde los artefactos de esta corrida **porque
no guardó el texto del modelo**, y ése es un segundo defecto: una corrida que no
se puede depurar desde su propia salida obliga a repetirla para mirarla.

Ambas cosas están arregladas: el runner ya persiste el texto, y
`scripts/probe_lcurve.py` mira un documento con una sola llamada.

## 5. La condición que faltaba

`BASELINE_FLOOR = 0.20`. Si el brazo monolítico acierta menos de eso en
`global`, ninguna cifra de la corrida habla sobre L.

Evaluada sobre esta misma corrida, dispara:

> PISO DEL BASELINE: el brazo monolítico acierta 1/72 = 0.014 en preguntas
> globales, por debajo de 0.2.

Se añadió **después** de ver los datos, y eso queda escrito en la
prerregistración con su fecha y su razón. No rescata esta corrida ni cambia
ningún veredicto —no hubo ninguno— y rige desde la siguiente.

## 6. Lo que sigue

En orden, y el primero es barato:

1. `python3 scripts/probe_lcurve.py` con el pool real. Una llamada. Decide si
   el piso es de capacidad o de formato, que son dos arreglos distintos.
2. Si es de formato: arreglarlo en el corpus o en el extractor, y volver a
   correr dev. No cambiar de modelos por un defecto de parsing.
3. Si es de capacidad: las preguntas `global` de este corpus —sumas y conteos
   sobre decenas de filas— están fuera del alcance de un pool de 2–3.8 B. La
   pregunta tiene que cambiar, no el protocolo: un máximo, un conteo bajo
   umbral, una fila que domina. El eje bajo prueba sigue siendo L; lo que se
   ajusta es la dificultad por fila, que el generador ya trata como un dial
   separado del tamaño.

Lo que **no** sigue es `lcurve-final`. El split sigue sin usar, y ése es el
único activo de esta corrida que conviene conservar intacto.
