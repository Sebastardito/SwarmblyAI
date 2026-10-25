---
status: current
lang: es
---
# Runbook

Los comandos, en orden, y la verificación que tiene que pasar antes de cada uno.
Escrito después de una sesión en la que un defecto de métrica invalidó cuatro
documentos y un umbral casi viaja a través de un cambio de corpus — dos cosas que
ahora rechaza una verificación mecánica en vez de tener que recordarlas una
persona.

**Leer `## 0` antes que nada.** Todo lo demás supone que pasó.

---

## 0. ¿El árbol está sano?

```bash
cd ~/Desktop/Dev/P2PAI/Swarmbly-AI_Clean
python -m pytest
```

Se espera: **558 passed, 9 skipped**. Cualquier otra cosa — parar, y decirlo. Las
fallas acá no son intermitentes; la suite no tiene red, ni modelos, ni reloj.

```bash
python scripts/make_tables.py --verify
```

Se espera: `verified prompts/tables24.json: 0c5cb7e2a041cd231b020bb24d65f55251ece8fccce6a421638eccd953566b4b`

Una discrepancia significa que el corpus en disco no es el que construye el
generador, y cualquier umbral congelado contra el digest guardado ya no aplica.
Regenerar con `python scripts/make_tables.py` y dar por nulo todo umbral aguas
abajo.

---

## 1. Corrida en seco — segundos, sin GPU, sin Ollama

```bash
python -m swarmbly_v0 run --prompts prompts/tables24.json --split dev \
  --rho 3.5 --n 2 --k 3 --backend mock --embedder hash --out /tmp/smoke
```

Buscar tres líneas y nada más:

| línea | tiene que decir |
|---|---|
| `corpus split:` | `dev (8 prompts)` |
| el pie | `*** MockBackend: ... NOT evidence about real models ***` |
| `wrote /tmp/smoke/results.csv` | presente |

Si `corpus split` dice cualquier cosa que no sea `dev`, el split no se está
aplicando y la corrida ajustaría umbrales sobre los datos que después juzga.
Parar.

---

## 2. `tables-dev` — la corrida que decide, ~1 h

```bash
bash scripts/run_ollama.sh tables-dev
```

Nunca `./scripts/...` — el bit de ejecutable no sobrevive a la entrega de
archivos.

**El script ahora verifica sus propias precondiciones antes de empezar a
generar.** Se niega a seguir salvo que haya al menos cinco familias de modelos
distintas presentes en `SWARMBLY_MODELS`, *y* salvo que el *k* más alto que barre
el tier pedido esté dentro de la cantidad de familias — `tables-dev`,
`tables-final` y `v4` barren hasta *k* = 3, los tiers `v3c` hasta *k* = 5. Leer la
línea `max k here:` que imprime. Por debajo de esa cantidad
`select_diverse_nodes` repite una familia para completar *k*, y réplicas de un
mismo linaje coinciden con confianza en el mismo error, lo que sesga hacia arriba
el brazo *k*. Eso ya pasó una vez, así que esto es un rechazo duro y no una
advertencia.

**Un tier que falla ahora aborta ruidosamente y deja un marcador.** Si se viola un
invariante en mitad del barrido, el directorio del tier recibe un archivo `FAILED`
que nombra el tier y el estado de salida, el script avisa en el momento, los demás
tiers independientes igual corren, y el script sale con código distinto de cero
con un resumen `ABORTED TIERS:` que nombra lo que se rompió. Dos consecuencias
para este runbook:

- **Buscar `FAILED` en el directorio de la corrida antes de leer cualquier otra
  cosa.** Un directorio que lleva ese marcador tiene salida parcial de una corrida
  que el harness se negó a completar; no tiene `results.csv`, y ningún número de
  ahí es citable.
- **Un código de salida distinto de cero ahora significa algo.** Antes un tier
  roto aparecía solo como un stack trace en medio de un log que nadie lee después
  de un barrido de seis horas.

**Antes de citar cualquier número de ahí**, revisar `run_metadata.json`:

| campo | tiene que ser |
|---|---|
| `harness_validation_only` | `false` — `true` significa que corrió el mock |
| `embeddings_degraded` | `false` — si no, τ_sem no significa nada |
| `transport_retries` | bajo; una cuenta alta significa que el endpoint venía sufriendo |
| `corpus_split` | `dev` |
| `corpus_frozen_sha256` | **el digest que imprimió `## 0`** — `0c5cb7e2…` |

Hay dos digests y no son intercambiables. `corpus_frozen_sha256` es sobre el id,
el split y el texto del prompt — el propio `_frozen.sha256` del corpus, el que
imprime `--verify`, y aquel al que queda fijado un umbral congelado.
`corpus_file_sha256` es sobre los bytes crudos y se mueve cuando se mueve un
comentario. Comparar el **frozen**.

Después:

```bash
python scripts/reanalyse.py results/tables-dev-<stamp>
```

Leer en este orden:

1. **`rho fidelity`** — cada celda en `ok`. Una celda `OUT` no corrió con el
   presupuesto que nombra su etiqueta, así que su comparación no es la que la
   etiqueta describe. En la corrida del 26 de agosto, N=8 quedó en ρ 3.91 contra
   un objetivo de 3.5.
   **Las filas por debajo del piso ya no llegan a ninguna cifra.**
   `publishable()` es ahora la única compuerta por la que pasa cada cifra, y
   descarta las filas cuyo `rho_target` queda por debajo del `rho_floor` de ese
   prompt en vez de anotarlas — una celda por debajo del piso no tiene
   información sobre ρ, porque cada paquete de ella colapsa a su contenido
   obligatorio y dos etiquetas de ρ producen paquetes idénticos. Así que hay que
   esperar que un reanálisis reporte *menos* filas de las que tiene el CSV, y leer
   una caída en `prompts=` como la compuerta funcionando y no como pérdida de
   datos. Si falta por completo una celda que esperabas, toda su fila de ρ estaba
   por debajo del piso; el arreglo es un ρ más alto, no una re-corrida con el
   mismo objetivo.
2. **`go/no-go`** — la celda declarada es `table_summary@rho=3.5@N=2@k=1`.
   **`prompts=`, y no `n_observations`, es el tamaño de muestra**: las filas de un
   mismo prompt comparten su dificultad.
3. **`accuracy at each distinct agreement value`** y **`the declared test`** —
   **retirados, no meramente no declarados.** Tres corridas con ground truth
   ubicaron el odds ratio común en 3.47, 0.26 y 1.24 — por encima, por debajo y a
   caballo del 1 sobre la misma pregunta — así que el mapa de confianza queda
   retirado y sacado del benchmark de V7. Esas líneas se siguen imprimiendo como
   diagnósticos de instrumento. No fijar un umbral contra ellas, no reportarlas
   como resultado, y no tratar un valor favorable en alguna corrida futura como
   una resurrección: reabrir la pregunta necesita un instrumento nuevo y un
   pre-registro nuevo.

Si aparece un banner que dice que el results.csv **es anterior a la corrección de
la métrica**, los impuestos de coherencia impresos son las cifras viejas,
dependientes del brazo. Correr:

```bash
python scripts/rescore.py results/<run>
```

que repuntúa las propias respuestas ensambladas de la corrida con la métrica
actual.

Se niega con cualquier corrida escrita antes del **27 de agosto**, porque esas
trazas no guardan los offsets de oración del ensamblador y las clases de error
locales a la costura se disparan exactamente en esos índices. Reconstruirlos como
una partición uniforme movió el puntaje recalculado por hasta 0.15 — suficiente
para invalidar la corrección que estaría reportando. Para una corrida así no hay
atajo: **correrla de nuevo.**

---

## 3. `tables-final` — se gasta una vez, y solo una

```bash
bash scripts/run_ollama.sh tables-final results/tables-dev-<stamp>
```

**Nombrar la corrida dev, no un valor de τ.** El script lee τ_sem *y* el digest
del corpus desde la metadata de esa corrida y se niega si:

- el corpus cambió desde esa corrida — un umbral ajustado sobre otros prompts;
- esa corrida no tiene `corpus_frozen_sha256` — es anterior al digest, así que no
  hay forma de confirmar sobre qué fue ajustado;
- esa corrida no fue sobre el split `dev` — un umbral ajustado sobre los datos que
  juzga.

> ## ⚠ ESTA MITAD YA FUE GASTADA — 27 de agosto de 2026, re-corrida el 3 de septiembre de 2026
>
> **La corrida del 27 de agosto se hizo sobre un instrumento defectuoso y sus
> cifras están superadas.** Se conservan acá como el registro de lo que pasó, no
> como resultados. `results/tables-final-20260827-102014`: la celda declarada
> volvió en **+3.26 %, IC [−0.02 %, +6.93 %]** sobre 16 prompts, control N=8 en
> +17.6 %.
>
> La misma celda se volvió a correr sobre un instrumento corregido el 3 de
> septiembre de 2026 (`results/tables-final-20260903-153237`) después de arreglar
> doce defectos: **+2.30 %, IC [−2.05 %, +7.49 %]**, criterio **NO CUMPLIDO**,
> corto por 2.49 puntos en el límite superior. Control N=8, k=1 en **+16.23 %**,
> IC [+11.33 %, +20.28 %] — se comportó, sin solapamiento.
>
> La medición que se sostiene es `docs/RESULTS_TABLES_FINAL_CORRECTED.md`.
>
> **No volver a correr este tier sobre este corpus.** Agregar prompts a un split
> ya gastado es el mismo estudio, y este estudio está terminado. Una prueba
> posterior necesita un corpus nuevo con su propio split, declarado de antemano
> antes de correr, y reportado como un segundo estudio y no como una continuación
> de este.

---

## Cosas que salieron mal, y qué las atrapa ahora

| qué pasó | qué lo atrapa ahora |
|---|---|
| La métrica puntuaba texto idéntico de forma distinta según la partición | `test_identical_text_scores_identically_however_it_was_partitioned` |
| Filas de réplica única entraban a la calibración de acuerdo con un centinela de 0.0 | `excluded_single_replica`, y el filtro está sobre `k`, no sobre el valor |
| Un marcado por percentil partía un grupo de empate en un predictor de cuatro valores | los grupos de empate se toman enteros; `achieved_rate` reporta en cuánto quedó |
| La celda declarada promediaba dos brazos (primero N, después k) | la celda es `(category, ρ, N, k)`; `n_cells_examined` declara las oportunidades |
| Una celda corrió en ρ 3.91 contra un objetivo de 3.5 y nada lo dijo | `rho_fidelity`, `within_tolerance` |
| Los intervalos trataban 8 400 oraciones de 20 prompts como 8 400 extracciones | `cluster_bootstrap`; `n_clusters` impreso al lado de `n_records` |
| τ_sem ajustado dentro de la corrida que después evaluaba | `--split final` se niega sin una corrida dev; digests comparados |
| Un CSV rancio reproducía el antecesor de una cifra corregida | banner de `reanalyse.py` + `rescore.py` |
| Se publicó una curva de ρ sobre celdas cuyo objetivo de ρ estaba por debajo del piso de empaquetado, así que el eje nunca se había movido | `publishable()`, la única compuerta por la que pasa cada cifra; las filas por debajo del piso se descartan, no se anotan |
| El piso de empaquetado omitía el encabezado del contrato y el carry obligatorio, así que `rho_reachable` volvía verdadero para celdas que después se pasaban | `packing_floor` cuenta encabezado y carry; `assert_packet_invariants` se niega a despachar |
| Un tier murió en mitad del barrido y la única traza fue un stack trace en un log que nadie leyó | `run_tier` estampa `FAILED`, avisa en el momento, y el script sale con código distinto de cero con un resumen `ABORTED TIERS:` |
| k barrió hasta 5 con tres familias cargadas, así que dos réplicas repetían un linaje | `run_ollama.sh` se niega cuando el k máximo de un tier excede la cantidad de familias distintas |

---

## Notas operativas que siguen mordiendo

- **`bash scripts/...`, nunca `./scripts/...`.** Los archivos entregados pierden
  el `+x`.
- **Nunca correr un comando de escritura de git a través del puente del
  dispositivo.** Deja un `.git/index.lock` que el mount no puede borrar. Incluso
  `git status --untracked-files=all` escribe el índice. `git ls-files` y
  `git check-ignore` son de solo lectura y seguros.
- **El puente no puede borrar archivos.** Todo lo que haya que eliminar se mueve a
  una carpeta `_to_delete/` para que lo borres vos.
- **`docs/AUDIT_V0.md`, `RESOLUCIONES.md`, `DISCUSION_PUNTOS.md`, `NAMING.md`
  y todo lo que está en `publication/` quedan privados.** No son parte del
  repositorio público.
