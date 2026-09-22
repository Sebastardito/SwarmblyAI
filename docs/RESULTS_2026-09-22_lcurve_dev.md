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

## 4. No es el formato, y no es el corpus

El sondeo sobre `lc_010_00` —diez filas, la tarea más fácil del diseño— cierra
las dos hipótesis alternativas de una sola vez.

**El modelo obedece la instrucción de formato al pie de la letra:**

```
[01] seals
[02] Eastdock
[03] 3053
[04] 3
[05] 4
```

**`extract_items` saca los cinco ids con sus cinco valores, sin perder ninguno.**
No hay desalineación de etiquetas. La forma `dado='[03] 215'` que vi en los
artefactos era un artefacto de truncado a 80 caracteres, no un defecto de
parsing — y decirlo así corrige lo que escribí antes de mirar.

**La clave es correcta.** Verificada a mano contra el material: `R-002` tiene
`on_hand=570`; la suma de las diez filas es 5889; el mayor `on_hand` es 979 en
`R-007`; ninguna fila tiene `on_hand` por debajo de su `reorder_at`, y por eso
la cuenta es 0. Los cinco valores de la clave son los correctos.

**La calificación está sana.** Una respuesta perfecta construida desde la clave
saca 100 % en los 72 documentos. Es un test, no una opinión, y queda en la
suite.

Así que es capacidad. Pero la forma del fallo importa más que la etiqueta:

| pregunta | pide | contestó |
|---|---|---|
| `[01]` local | `on_hand` de `R-002` → 570 | `seals` |
| `[03]` global | la suma de diez números → 5889 | 3053 |
| `[04]` global | el id de fila con mayor `on_hand` → `R-007` | `3` |
| `[05]` global | cuántas filas cumplen un umbral → 0 | 4 |

`[01]` y `[04]` no son errores de aritmética. En `[01]` el modelo devolvió la
**categoría** en vez del `on_hand`; en `[04]` devolvió un número desnudo donde
se pedía un id de fila. Sobre una fila como
`R-002 | Northgate | seals | on_hand=570 | reorder_at=175`, el modelo no está
localizando el campo que se le nombra.

Eso apunta a la **dificultad por fila**, no a la dificultad de la pregunta. El
generador ya trata las dos como diales separados —ésa era la intención
declarada: *más filas es más material sin cambiar la dificultad por fila*— pero
nadie calibró el segundo antes de construir la rejilla sobre el primero.

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

**La comprobación que la prerregistración debió pedir antes de construir la
rejilla:** un diseño que varía X tiene que mostrar primero que el instrumento
responde. No estaba, y es la lección de método de esta corrida.

```bash
python3 scripts/probe_lcurve.py --calibrate
```

Monolítico, S = 10, las cinco familias del pool, sobre los cuatro documentos
dev de ese tamaño. Veinte llamadas. Responde una sola pregunta: **¿alguna
familia despega del piso de 0.20 en el caso más fácil del diseño?**

- **Si alguna despega:** el piso no es del pool entero y el corpus sirve. El
  arreglo está en qué modelos se usan, y la rejilla se puede volver a correr
  tal cual.
- **Si ninguna despega:** este corpus no puede medir L con este pool, y no se
  arregla con más corridas. Hay que bajar la dificultad **por fila** —un
  formato de material que no exija localizar un campo entre cinco— y
  **calibrar de nuevo antes** de construir otra rejilla. El eje bajo prueba
  sigue siendo L; lo que se ajusta es lo que rodea a L.

Lo que **no** sigue es `lcurve-final`. El split sigue sin usar, y ése es el
único activo de esta corrida que conviene conservar intacto.
