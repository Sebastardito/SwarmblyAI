---
status: current
lang: es
note: >
  Escrita antes de generar el corpus y antes de escribir el runner. La medición
  todavía no existe.
---
# Prerregistración — la curva de L

`docs/FUNDAMENTOS_2026-09-21_unidad_semantica.md` (privado) propuso rediseñar la
unidad semántica del protocolo por analogía con genómica: que existe un **tamaño
mínimo de fragmento** por debajo del cual un trozo deja de poder sostener una
respuesta, igual que una lectura demasiado corta deja de poder colocarse en un
genoma. La propuesta pedía fragmentos de unas 50 oraciones.

Esa propuesta no se puede implementar sin antes medir si la premisa es cierta en
esta arquitectura. Este documento define esa medición, y define qué resultado la
mata.

---

## 1. Lo que hoy no se puede separar

El harness no tiene una perilla de tamaño de fragmento. Tiene `n_tasks`, y
`_segment` reparte el material en exactamente `n_tasks` grupos de tokens
aproximadamente iguales. Con el prompt fijo, **L y N son la misma variable
escrita al revés**: L = S / N.

Toda corrida anterior movió N sobre un corpus de tamaño fijo. Por eso cada
conclusión sobre N en el registro de este proyecto es también una conclusión
sobre L, y ninguna de las dos es identificable por separado.

## 2. Cómo se separan

El corpus `longform` tiene un dial que los corpus anteriores no tenían: el
número de filas, `n_rows`. Con material de tamaño S y N fragmentos, L = S / N
en filas por fragmento. Eligiendo S = L · N se construye un factorial completo:

| | N = 2 | N = 4 | N = 8 |
|---|---|---|---|
| **L = 5** | S = 10 | S = 20 | S = 40 |
| **L = 10** | S = 20 | S = 40 | S = 80 |
| **L = 20** | S = 40 | S = 80 | S = 160 |
| **L = 40** | S = 80 | S = 160 | S = 320 |

Cada L aparece en tres valores de N y cada N en cuatro de L, así que el efecto
de L es identificable con N fijo.

La comparación más limpia del diseño está en las diagonales. **S = 40 se
fragmenta en L = 5 (N = 8), L = 10 (N = 4) y L = 20 (N = 2)**: el mismo
documento, las mismas preguntas, la misma clave, el mismo baseline monolítico,
y lo único que cambia es el tamaño del fragmento. Lo mismo ocurre en S = 20,
S = 80 y S = 160.

## 3. Lo que esta medición NO puede ver

Se declara antes de correr, no después de leer.

Una fila de inventario **ya es la unidad atómica** de este corpus. Agrupar 5 o
40 filas no cambia lo que un fragmento significa; cambia cuánto pesa. Por lo
tanto este experimento mide el **componente mecánico** de L —el coste de
cabecera por paquete, el coste de reintegrar más piezas— y **no puede ver** el
componente semántico que la propuesta genómica afirma.

Esto no lo invalida: lo acota. El componente mecánico es una **cota inferior**
del efecto total de L. Si ni siquiera el coste mecánico de fragmentar en trozos
pequeños se distingue de cero, entonces "el tamaño del fragmento importa" no
tiene apoyo alguno en esta arquitectura, y un corpus semántico —caro de
construir y de calificar— es la única esperanza que le queda a la premisa.
Si el coste mecánico es real, esta curva da su forma y su rodilla, que es el
número `L*` que el rediseño necesita.

## 4. La celda declarada

> **Enmienda, antes de correr nada.** La primera redacción de esta sección
> declaraba la celda en un solo tamaño: S = 80, L = 40 contra L = 10. Con 12
> documentos por tamaño y 8 en la mitad final, esa celda tiene **8 clusters**, y
> `MIN_CLUSTERS_FOR_A_VERDICT` es 20: el veredicto se habría rehusado en código
> después de gastar las corridas. Se corrige aquí, con el corpus todavía sin
> generar y sin un solo dato a la vista.

**El contraste de L dentro del mismo documento, agrupado sobre los tamaños que
admiten más de un L, sobre preguntas `global`.**

Cuatro tamaños ofrecen ese contraste: S = 20 (L = 10 contra 5), S = 40 (20
contra 5), S = 80 (40 contra 10) y S = 160 (40 contra 20). Ocho documentos
finales por tamaño dan **32 clusters**.

Predicción: el L grande puntúa más alto que el L chico del mismo documento.

- **Estimador:** diferencia pareada por documento en exactitud sobre ítems
  `global`, entre la fragmentación de L mayor y la de L menor del **mismo**
  documento. Mismo texto, mismas preguntas, misma clave, mismo baseline: lo
  único que cambia es el tamaño del fragmento.
- **Veredicto sobre la cota INFERIOR** de un bootstrap por clusters, donde el
  cluster es el documento. Es una afirmación de que existe un efecto, así que
  la cota que decide es la inferior.
- **Umbral:** `L_CURVE_THRESHOLD_POINTS = 0.05` en exactitud. Fijado antes de
  ver datos, en el mismo valor que usa el criterio de composición, por no
  inventar un umbral nuevo por conveniencia.
- **Mínimo de clusters:** 20, rehusado en código por debajo de eso.

**S = 80, L = 40 contra L = 10** se sigue reportando aparte, por ser el
contraste de mayor rango del diseño, pero con 8 clusters **no lleva veredicto**
y se imprime como descriptivo.

## 5. El control que tiene que fallar

**Las preguntas `local`.**

Una pregunta `local` pide el valor de una fila nombrada. La contesta el
fragmento que contiene esa fila, y la contesta igual de bien sea ese fragmento
de 5 filas o de 40. Si L mueve la exactitud `local`, lo que se está midiendo no
es el tamaño de la unidad semántica: es algo que se rompe en la tubería —el
segmentador, el enrutador, el ensamblador— y el experimento entero queda
inválido.

El control se declara con su propio umbral: si la exactitud `local` varía con L
en más de **0.05**, la corrida no se lee.

## 6. Condiciones de refutación

Evaluadas en código por `_invalidations()`, no en prosa después del hecho.

1. **Control fallado.** `local` varía con L por encima de 0.05 → corrida
   inválida, no se publica número alguno.
2. **Criterio NO CUMPLIDO.** La cota inferior de la celda declarada no supera
   0.05 → la predicción falla en su propia celda.
3. **El eje L está muerto.** Si en los tres valores de N el intervalo del efecto
   de L contiene el cero, entonces el tamaño de fragmento no mueve nada
   mecánicamente, y el rediseño genómico pierde su apoyo más barato. Esta es la
   condición que puede matar la premisa en una noche.
4. **Sin frontera.** Si todo S cabe bajo el presupuesto de nodo declarado, el
   brazo monolítico nunca falla y la comparación es de coste, no de
   factibilidad. Se registra junto al resultado, porque cambia cómo se lee.

5. **Piso del baseline.** `BASELINE_FLOOR = 0.20`. Si el brazo monolítico
   acierta menos de eso en preguntas `global`, ninguna cifra de la corrida
   habla sobre L: con los dos extremos en el piso, la diferencia pareada entre
   dos fragmentaciones es ruido alrededor de cero.

   > **Añadida el 22 de septiembre, DESPUÉS de la primera corrida.** Se dice
   > aquí porque añadir una condición de refutación después de ver datos es
   > exactamente la libertad que una prerregistración existe para quitar.
   >
   > `lcurve-dev` terminó sin disparar ninguna de las cuatro condiciones
   > anteriores y con el control marcando +0.000, que se lee como "nada se
   > rompió". El brazo monolítico había sacado **1 de 72** en preguntas
   > globales, incluso con S = 10 -- una tabla de diez filas que cabe entera en
   > cualquier ventana. El control marcaba cero porque los dos extremos estaban
   > en el piso. **Un control que pasa en el piso no es un control**, y ése fue
   > el defecto: cuatro condiciones y ninguna que preguntara si el instrumento
   > tiene rango dinámico.
   >
   > Esta condición no rescata aquella corrida ni cambia ningún veredicto -- no
   > hubo ninguno, la celda se rehusó por número de clusters. Rige desde la
   > siguiente.

## 7. Lo que se congela antes de correr

- El corpus y su digest SHA-256, con la clave dentro del digest.
- El split dev/final, y el gate `read_dev_run` que ya rehúsa un final sin dev.
- La huella de código, comparada por `assert_same_code_as_dev`.
- Este documento.
