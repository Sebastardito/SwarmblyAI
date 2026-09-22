---
status: current
note: >
  The preregistration stands. Its measurement does not exist yet: the
  feas-dev and feas-final runs of 5 September were invalidated by the corpus
  item ids, and the corrected corpus (digest 8f6c3565) has not been run.
lang: es
---
# Prerregistración — la frontera de factibilidad

> **CORRIDA 1 INVÁLIDA (5 sep, 23:47 y 23:52).** La condición 1 se cumplió en
> las dos mitades: `naive-chunk` 0 % en `local`. El diagnóstico no fue el
> troceado sino **el calificador**: el corpus salió con ids `[Q1]`..`[Q5]` y
> `grading.extract_items` sólo reconoce etiquetas numéricas, así que devolvía
> lista vacía y **toda** respuesta de **todo** brazo se calificó mal.
> `monolithic-capped` sacó 0/2 en documentos de 24 filas que tenía enteros en un
> solo nodo — imposible como fallo de capacidad.
>
> Corregido a ids numéricos; corpus regenerado (digest `8f6c3565…`, el anterior
> nunca se usó válidamente). Nada de la hipótesis, del presupuesto ni de los
> brazos cambia. **La condición de invalidación hizo su trabajo: tres horas
> perdidas y cero números publicados.**

**Escrita el 5 de septiembre de 2026, ANTES de construir el corpus y antes de
correr nada.** Es la primera medición del proyecto que puede salir a favor de la
arquitectura, y por eso el diseño se fija primero.

---

## Por qué existe

`REVISION_2026-09-05_que_hemos_medido.md` estableció el hecho que reencuadra
todo lo anterior: **el prompt más grande del proyecto mide 375 tokens y el modelo
más chico tiene una ventana de 8192.** Ninguna tarea, en ningún corpus, ha
necesitado fragmentarse. Tres semanas midiendo cuánto cuesta partir algo que no
hacía falta partir, y la única respuesta posible a esa pregunta era "cuesta".

Esta prueba cambia la pregunta de **"¿cuánta calidad se pierde?"** a **"¿existe
la respuesta?"**.

## Cómo se hace que una tarea no quepa

**No** eligiendo documentos que excedan la ventana de un modelo concreto — eso
depende de cuál modelo, y `llama3.2:3b` tiene 128k mientras `gemma2:2b` tiene 8k.
Una medición que dependa de esa lotería no mide la arquitectura.

**Sí** declarando un **presupuesto por nodo `W`**: un tope de contexto de entrada
que **todos los brazos respetan por igual, incluido el monolítico**. Eso es lo
que es realmente una red P2P de dispositivos pequeños y heterogéneos, y es la
afirmación de la arquitectura enunciada como una restricción medible.

`W = 2048` tokens de entrada (prompt + material + cabecera de contrato).
Declarado aquí y no ajustable después.

El brazo monolítico **falla por construcción** cuando `|P| > W`. Eso no es una
puntuación baja: es **infactible**, y se registra como tal.

## Los tres brazos, y el tercero es el que importa

| brazo | qué hace |
|---|---|
| `monolithic-capped` | un nodo, presupuesto `W`. Infactible por encima de `W`. |
| **`naive-chunk`** | **el baseline obvio**: partir el material en trozos de `W`, preguntar a cada uno, concatenar. Sin router, sin planner, sin packer, sin ensamblador. |
| `swarmbly` | el protocolo enviado. |

**`naive-chunk` es la única comparación que importa.** Sin él, el resultado sería
"fragmentar le gana a no-fragmentar en tareas que no caben", lo cual es
trivialmente cierto y no vale nada. La pregunta real es si **el protocolo le gana
a lo obvio**.

Si `swarmbly` ≈ `naive-chunk`, el hallazgo es que el valor está en trocear, y el
router, el planner, el packer y el ensamblador no están pagando su costo. Ese
resultado es tan publicable como el contrario, y hay que decirlo ahora.

## La hipótesis

> Existe un tamaño de material `S*` por encima del cual `monolithic-capped` es
> infactible y `swarmbly` sigue respondiendo con una exactitud **al menos igual
> a la de `naive-chunk`**, sobre preguntas **globales** — las que no puede
> contestar ningún trozo por separado.

Dos partes, y se juzgan por separado:

* **Factibilidad (H-F):** por encima de `S*`, `swarmbly` produce respuesta y
  `monolithic-capped` no. Esto es aritmética de empaquetado, no un resultado
  empírico, y se verifica antes de correr con `check_grid`.
* **Utilidad (H-U):** por encima de `S*`, la exactitud de `swarmbly` en preguntas
  globales **no es inferior** a la de `naive-chunk`, juzgada sobre la **cota
  inferior** de un bootstrap agrupado por documento, contra un margen de no
  inferioridad de **−5 puntos porcentuales**.

La cota **inferior** y no la superior: aquí la afirmación es "no es peor", así
que el lado conservador es el de abajo. Es la imagen espejo del criterio de
composición, y se declara así por la misma razón.

## Las preguntas, y por qué dos clases

Cada documento es una tabla de registros. Cada pregunta se califica
mecánicamente contra una clave calculada en la generación — sin juez, sin
modelo en el veredicto.

| clase | ejemplo | por qué está |
|---|---|---|
| `local` | el valor del registro `R-047` | un solo trozo la contesta. **Control:** si `naive-chunk` falla aquí, el troceado está roto y nada más se puede leer. |
| `global` | el total de la columna, cuál registro tiene el máximo, cuántos superan un umbral | **ningún trozo la contesta solo.** Aquí es donde un protocolo puede añadir algo sobre concatenar. |

**H-U se juzga sólo sobre `global`.** Las `local` son el control de que el
troceado funciona.

## Qué invalidaría la corrida

| # | condición | consecuencia |
|---|---|---|
| 1 | `naive-chunk` falla las `local` por debajo del 80 % | el troceado está roto **o el calificador está ciego**; nada por debajo se puede leer. En la corrida 1 fue lo segundo. |
| 2 | `monolithic-capped` resulta factible en todos los tamaños | `W` no está mordiendo; el diseño no probó nada |
| 3 | Cualquier brazo excede `W` en algún nodo | el presupuesto no se está imponiendo, y la factibilidad medida es ficticia |
| 4 | menos de 20 documentos con pregunta global | sin veredicto, como en toda medición declarada de este proyecto |

La condición 3 se comprueba **midiendo el contexto real de cada paquete
despachado**, no confiando en que el packer respetó su objetivo. Es el mismo
patrón que `packing_ceiling`: medir, no derivar.

## Qué NO se afirma

* **Nada sobre calidad de prosa.** Este corpus se califica contra una clave.
* **Nada sobre costo ni latencia.** Se registran tokens por nodo y contexto pico
  por nodo porque son los ejes donde fragmentar debería ganar, pero no forman
  parte de ninguna hipótesis declarada aquí. Medir sin declarar es describir.
* **Nada sobre modelos grandes.** Sigue siendo 3B, y un modelo que siguiera
  instrucciones mejor movería las dos ramas a la vez.
* **Nada sobre `W` distinto de 2048.** Un barrido de `W` sería otra prerregistración.

## Lo que el ensayo no puede probar, y por eso hay un fixture

El ensayo con backend mock demuestra que el tier **corre**: las funciones, las
invocaciones, el wrapper, las post-condiciones. No puede demostrar que el
calificador **lee**, porque un mock que no sabe contestar produce 0/5 tanto si
el calificador funciona como si está ciego, y las dos cosas se ven idénticas.

Ésa es la brecha que costó la corrida 1, y no estaba en la doctrina de ensayo.
El remedio es un **fixture**: una respuesta correcta escrita a mano, calificada,
que tiene que sacar 5/5 — y su imagen espejo, una respuesta absurda que tiene
que sacar 0/5. Ningún backend puede dar esos dos tests.

> **El ensayo valida la fontanería, no la semántica.**

## Los ejes que se registran sin declarar hipótesis

Porque nunca se han medido y porque son la mitad de la propuesta:

* `tokens_per_node` — total y máximo entre nodos.
* `peak_node_context` — el contexto de entrada más grande que vio cualquier nodo.
* `feasible` — booleano por celda y por brazo.
* `n_nodes` — cuántos hicieron falta.

Van al CSV y al resumen. No se convierten en un titular en esta corrida.

## El sesgo que hay que vigilar, dicho antes

Esta es la primera prueba diseñada donde la arquitectura **puede** ganar, y la
diseñé yo después de escribir un documento que decía que el planteamiento estaba
inclinado en su contra. Los dos riesgos concretos:

1. **Elegir `W` para que el resultado salga.** `W = 2048` se fija aquí, antes de
   generar el corpus, y no se toca. Si el resultado es feo con 2048, el remedio
   es publicarlo con 2048.
2. **Que el baseline obvio sea de paja.** `naive-chunk` debe ser el mejor
   troceado simple razonable — trozos que respeten los límites de registro, la
   misma pregunta a cada trozo, concatenación en orden — y no una versión
   torpe elegida para perder. Su implementación se revisa contra ese estándar
   antes de correr, y la revisión queda en el documento de resultados.

## La secuencia

```bash
python scripts/make_longform.py                    # genera y congela el corpus
python scripts/make_longform.py --verify
bash scripts/run_ollama.sh feas-dev                # ~1 h, fija W y valida las clases
bash scripts/run_ollama.sh feas-final results/feas-dev-<stamp>    # ~2 h
```

Split dev/final como en composición: la clase de pregunta, el tamaño declarado
`S*` y cualquier ajuste se fijan en dev; el final se evalúa una vez.
