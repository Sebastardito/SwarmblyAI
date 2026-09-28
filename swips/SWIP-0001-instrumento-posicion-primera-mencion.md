---
swip: 0001
title: Instrumento del criterio — impuesto por posición de primera mención
author: Sebastián A. Espinoza-Ulloa <sebas_saeu@hotmail.com>
status: Draft            # Draft | Accepted | Rejected | Withdrawn | Deferred | Final
created: 2026-09-28
requires: []             # SWIPs this depends on
supersedes: []           # SWIPs this replaces
spec-version: 0.2        # spec version this targets
---

## Abstract

El impuesto de coherencia agregado — `tax = 1 − frag/mono` sobre el score del
grader — queda **deprecado como instrumento del criterio de abandono** y se
reemplaza por el **impuesto por posición de primera mención**: para cada clave
del task, la posición (en fracción de la longitud del propio brazo) de su
primera mención. La métrica es invariante a la longitud de salida **por
construcción** y no tiene parámetro libre.

## Motivation

Tres mediciones sobre 473 corridas reales establecen que el instrumento actual
no discrimina:

1. **El acoplamiento con la longitud es bidireccional** (T11, T09R). Con el
   presupuesto completo el brazo fragmentado escribe 1.39× el monolítico y
   puntúa más; con el presupuesto repartido escribe 0.43× y puntúa menos.
   Spearman(razón de longitud, frag − mono) = +0.571 — el score sube con lo
   escrito, en ambas direcciones.
2. **El impuesto truncado depende del presupuesto de lectura T** (T13). Al
   calificar sólo los primeros T tokens de cada brazo, el impuesto agregado
   cambia de signo: −15.66 % (T=40) a +7.69 % (T=120). No existe un T que
   haga el instrumento decidir: la respuesta depende de cuánto texto se deja
   escribir.
3. **El instrumento por posición resuelve ambas cosas** (T13b). El
   desplazamiento medio de primera mención es **−0.279** de la longitud,
   IC95 **[−0.361, −0.178]**: el fragmentado saca las claves ~28 % antes.
   El confundido desaparece: ρ(posición, razón de longitud) = +0.075.

Sin este cambio, el criterio de abandono queda permanentemente «sin medir» y
ninguna afirmación de factibilidad es citable — el estado actual documentado
en WHITEPAPER_V2 §15.9 y RESULTS_2026-09-25_refbench.

## Specification

### Métrica

Para una celda (task, familia) con brazo monolítico `M` y brazo fragmentado
ensamblado `F`:

- **Claves del task** (`K`): la unión de `required_items` y los valores
  esperados de `answer_keys`. Las claves duplicadas cuentan una vez.
- **Posición de primera mención** `pos(x, A)`: el número de palabras que
  preceden a la primera ocurrencia (case-insensitive, por regex exacto) de la
  clave `x` en el texto del brazo `A`, dividido por el número total de
  palabras de `A`. Si `x` no aparece, la clave **no entra** en el promedio
  (se cuenta aparte como ausencia).
- **Desplazamiento por clave**: `d(x) = pos(x, F) − pos(x, M)`.
  Positivo = el fragmentado menciona la clave más tarde, en fracción de su
  propia longitud.
- **Impuesto por posición de la celda**: la media de `d(x)` sobre las claves
  con posición medible en ambos brazos.
- **Impuesto agregado**: media sobre celdas operativas (corte P9, presupuesto
  igualado `|matched` cuando existe), con IC 95 % por bootstrap agrupado por
  task y las condiciones de rechazo de §15.7 (piso baseline 0.20, mínimo 20
  celdas, mínimo 50 claves medibles).

### Criterio restablecido

El criterio de abandono se re-expresa así: **fragmentar no debe desplazar las
claves hacia atrás en más de +2 % de la longitud** (juzgado contra el límite
SUPERIOR del IC95). Un desplazamiento negativo —claves antes— es un beneficio
y se reporta como tal.

### Ausencias

Una clave presente en un brazo y ausente en el otro se registra en un contador
`missing_frag` / `missing_mono` por celda y se reporta junto al impuesto, pero
no entra en el promedio: la métrica mide *dónde*, no *si*.

### Condiciones de rechazo

- Menos de 20 celdas operativas → el instrumento **se niega**.
- Menos de 50 claves medibles en total → el instrumento **se niega**.
- `|ρ(posición, razón de longitud)| ≥ 0.20` → el instrumento **se niega**
  (el confundido que lo motivó no puede reaparecer silenciosamente).
- El impuesto cambia de signo entre mitades del corpus (split por tarea
  par/impar) → el instrumento **se niega**.

## Rationale

Alternativas consideradas y rechazadas:

- **Igualar el presupuesto de salida (`--match-output-tokens`)**: no basta.
  Con presupuesto repartido el confundido persiste invertido (0.43×, ρ=+0.343)
  porque el score sigue subiendo con lo escrito; además castiga al brazo
  fragmentado que necesita más tokens para cubrir sus filas.
- **Truncar ambos brazos a T fijo**: el impuesto depende de T (signo cambia
  entre T=40 y T=120) — el resultado diría más del presupuesto elegido que de
  la fragmentación.
- **Densidad (items / palabras)**: sensible a palabras de relleno y a la
  granularidad del tokenizador; no separa «mencionar antes» de «mencionar
  muchas veces».
- **Presencia por ítem sin posición**: es el componente que causó el
  confundido original (escribir más menciona más).

La posición normalizada por la longitud del propio brazo no premia escribir
más ni castiga escribir menos: dos brazos que ponen la misma clave a la mitad
de su texto empatan aunque uno tenga el doble de palabras.

## Backwards compatibility

No cambia el wire format, los esquemas de mensaje ni las obligaciones de
nodo. Los artefactos guardados (`benchmark.jsonl`) conservan su validez: el
instrumento se computa sobre los textos ya registrados, sin re-correr nada.
El impuesto agregado anterior se conserva como registro histórico y se marca
`deprecated` en el arnés (T09R lo seguirá reportando con la negativa, para
que nadie lo cite como vigente).

## Security and privacy implications

Ninguna identificada. La métrica se computa **en el cliente** sobre el texto
monolítico y el texto ensamblado — ambos ya en poder del cliente. Ningún nodo
observa nada nuevo, y la posición de primera mención no revela más estructura
del problema que el texto del que se extrae.
