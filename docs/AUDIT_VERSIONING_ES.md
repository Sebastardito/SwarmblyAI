---
status: historical
reason: >
  Una auditoría fechada del 27 de agosto. Sus hallazgos se dejan tal como
  fueron escritos; los pasos correctivos que prescribe se ejecutaron y no son
  una instrucción viva.
lang: es
---
# Auditoría de versionado — 27 de agosto de 2026

> ## Actualización de estado — los pasos correctivos se ejecutaron
>
> Esta es una auditoría fechada y sus hallazgos se dejan tal como fueron
> escritos. Lo que ha cambiado desde entonces, para que nadie trabaje a partir
> de una instrucción superada:
>
> - **F2 está resuelto.** El trabajo está commiteado. La historia ya no se
>   detiene antes de V6, y la lista de archivos de F2 describe un árbol de
>   trabajo que ya no existe.
> - **F4 y el paso 1 de F6 están resueltos.** El conjunto privado está listado
>   explícitamente en `.gitignore` y eliminado del índice. **El bloque `git` de
>   F6 ya se ejecutó y no debe volver a ejecutarse tal como está escrito** — en
>   particular su mensaje de commit nombra solo "V6 through tables-final", que
>   ya no es lo que es el trabajo sin commitear. Redacte un mensaje nuevo;
>   conserve el paso 2, la verificación de archivos privados, antes de
>   cualquier push.
> - **El remedio de F5 se ha extendido.** `run_metadata.json` lleva
>   `code_sha256`, y ahora existen dos compuertas de reporte adicionales,
>   posteriores a esta auditoría: las filas por debajo del piso se descartan de
>   toda cifra mediante `publishable()` en lugar de anotarse, y un nivel
>   fallido estampa un marcador `FAILED` en su propio directorio, de modo que
>   un directorio de resultados encontrado después no pueda confundirse con una
>   corrida completada. Al auditar un directorio de resultados, **revise
>   `FAILED` antes de leer nada en él.**
> - **No resuelto:** `results/` sigue gitignorado y sigue existiendo en un solo
>   disco. Los pasos de copias obsoletas y de limpieza que siguen se sostienen
>   tal como están escritos.

Motivada por una sospecha de deriva tras varias desconexiones del puente. La
sospecha acertó en el síntoma y erró en la causa: **no hay deriva de
contenido.** Lo que hay es un repositorio cuya historia se detiene dos semanas
antes que su árbol de trabajo, dos copias obsoletas del proyecto en el mismo
disco, un conjunto de documentos privados sin nada que les impida llegar a un
remoto público, y resultados que no podían decir qué código los produjo.

Método: hashear cada ruta rastreada en ambas copias y comparar, en lugar de leer
listados. El primer intento de esta auditoría comparó una lista transcrita a
mano y reportó dieciocho diferencias falsas; queda registrado aquí porque es la
misma clase de error que la auditoría buscaba.

---

## F1 — No hay deriva de contenido. El código es una sola versión.

113 rutas rastreadas comparadas por SHA-256.

| | |
|---|---|
| idénticas en ambas copias | **95** |
| **diferentes** | **0** |
| ausentes de la copia de trabajo | 18 — todas ellas el conjunto privado, ver F4 |

La copia de trabajo y este clon coinciden byte a byte en todo lo que se solapan.
Cualquier temor de que una falla del puente haya dejado archivos fuente a medio
escribir o divergentes es infundado.

## F2 — La historia de la copia de trabajo se detiene antes de V6

```
working copy HEAD:  6e554ee  "Preflight: nine defects found before the run"
```

Ese commit es anterior a la corrida de V6. Todo lo posterior existe **solo como
archivos sin rastrear o modificados en el árbol de trabajo**:

`swarmbly_v0/stats.py` · `tests/test_instrument.py` · `prompts/tables24.json` ·
`scripts/make_tables.py` · `scripts/reanalyse.py` · `scripts/rescore.py` ·
`docs/RESULTS_V6.md` · `docs/RESULTS_TABLES_DEV.md` ·
`docs/RESULTS_TABLES_DEV2.md` · `docs/RESULTS_TABLES_FINAL.md` ·
`docs/RUNBOOK.md` — más las modificaciones a `metrics.py`, `experiment.py`,
`planner.py`, `grading.py`, `cli.py`, `composition_trace.py`,
`scripts/run_ollama.sh`, `scripts/make_complex.py` y cuatro archivos de prueba.

**Nada posterior al 25 de agosto está commiteado en ningún lugar durable.**
`git log` en esa carpeta cuenta una historia que termina antes de la corrección
de la métrica, antes del Test 0, antes de la división del corpus, y antes de las
tres corridas de tablas. Si la carpeta se pierde, el trabajo también; si una
segunda máquina clona el remoto, obtiene código de agosto.

Este es el verdadero problema de versionado. No es deriva — es la ausencia de un
registro.

## F3 — Tres copias del proyecto, dos obsoletas

| directorio | HEAD | `metrics.py` | archivos fuente | resultados |
|---|---|---|---|---|
| **`Swarmbly-AI_Clean`** | `6e554ee` | **27 ago** | 20 | 18 |
| `Swarmbly-AI` | `fbb2665` | 14 ago | 15 | 5 |
| `Ori_Swarmbly-AI_Clean` | `453baf3` "Initial commit" | 14 ago | 15 | 5 |

Solo la primera está viva; nada ha escrito en las otras dos en dos semanas. No
compiten entre sí — pero `Swarmbly-AI` lleva el nombre que usa el repositorio
público, y todavía contiene los documentos privados. Un comando ejecutado en el
directorio equivocado empujaría código de agosto, o documentos privados, o
ambos.

## F4 — Los documentos privados no tenían nada que los protegiera

`.gitignore` en la copia de trabajo excluía exactamente un archivo privado,
`docs/AUDIT_V0.md`. **No** excluía:

`docs/DISCUSION_PUNTOS.*` · `docs/NAMING.*` · `docs/RESOLUCIONES.*` ·
`docs/Swarmbly_AI_Documento_Maestro_ES.*` ·
`docs/Swarmbly_AI_Master_Document_EN.*` · `publication/` (seis documentos,
incluidos la divulgación y el borrador de envío)

y el remoto de la copia de trabajo es:

```
origin  https://github.com/Sebastardito/Swarmbly-AI.git  (push)
```

Esos archivos están **ausentes** de ese árbol de trabajo, así que nada corría
riesgo de ser commiteado por accidente hoy. Pero nada impedía que se volvieran a
añadir, y **este clon todavía los tenía todos en su índice** — de modo que
cualquier parche, archivo o pull tomado de él los habría llevado consigo.

**Corregido aquí:** eliminados del índice de este clon, y listados
explícitamente en `.gitignore` — una ruta por línea en lugar de un comodín, de
modo que añadir un documento privado nuevo sea un acto deliberado y la lista se
lea como un inventario.

**Pendiente en la copia de trabajo:** el mismo cambio de `.gitignore`, en F6 más
abajo.

## F5 — Ningún resultado podía decir qué lo produjo

`run_metadata.json` registraba la huella del corpus pero nada sobre el código.

| corrida | corpus | métrica | cómo se podía saber |
|---|---|---|---|
| `tables-dev-20260826-115300` | `47ceb5f0` *(no registrado)* | **defectuosa** | marca de tiempo del directorio |
| `tables-dev-20260827-095758` | `0c5cb7e2` | corregida | marca de tiempo del directorio |
| `tables-final-20260827-102014` | `0c5cb7e2` | corregida | marca de tiempo del directorio |

Tres corridas del mismo nivel, dos puntuadas por una métrica neutral entre
brazos y una por la predecesora que inflaba el brazo fragmentado, distinguibles
solo por el nombre de una carpeta contra el recuerdo de cuándo aterrizó la
corrección. Eso no es evidencia.

**Corregido:** `run_metadata.json` ahora lleva `code_sha256` — una huella sobre
las fuentes del paquete — y `code_files`. Toda corrida futura se describe a sí
misma. `tests/test_instrument.py` afirma que la huella se mueve cuando se mueve
cualquier byte de las fuentes.

`results/` está gitignorado, y correctamente — las corridas son grandes y
reproducibles a partir del código más el corpus. Pero eso significa que los
dieciocho directorios de resultados existen **solo** en ese disco, sin versionar
y sin respaldo.

## F6 — Qué ejecutar, y por qué no lo estoy ejecutando yo

Los comandos de escritura de Git a través del puente del dispositivo dejan un
`.git/index.lock` que el montaje no puede borrar. Incluso
`git status --untracked-files=all` escribe el índice. Así que los comandos de
abajo son para que usted los ejecute; yo he verificado el estado sobre el que
actúan.

```bash
cd ~/Desktop/Dev/P2PAI/Swarmbly-AI_Clean

# 1. Protect the private documents FIRST, before anything is staged.
#    Copy the .gitignore from this session's delivery, or append by hand:
cat >> .gitignore <<'EOF'
docs/AUDIT_V0.md
docs/DISCUSION_PUNTOS.*
docs/NAMING.*
docs/RESOLUCIONES.*
docs/Swarmbly_AI_Documento_Maestro_ES.*
docs/Swarmbly_AI_Master_Document_EN.*
publication/
_interno/
_to_delete/
_audit_*.txt
EOF

# 2. Confirm nothing private is about to be staged. Expect NO output.
git status --porcelain | grep -E 'DISCUSION|NAMING|RESOLUCIONES|Maestro|Master_Document|publication/|AUDIT_V0'

# 3. See what will be committed.
git status --short

# 4. Commit the two weeks of work.
git add -A
git commit -m "V6 through tables-final: instrument corrections, corpus split, results"

# 5. Push only when step 2 gave no output.
git push origin main
```

**No omita el paso 2.** Es la única verificación entre un documento privado y un
repositorio público.

### Las copias obsoletas

```bash
cd ~/Desktop/Dev/P2PAI
mv Swarmbly-AI            _archive/Swarmbly-AI-stale-20260814
mv Ori_Swarmbly-AI_Clean  _archive/Ori_Swarmbly-AI_Clean-20260814
```

Renombrar en lugar de borrar: son las únicas copias de cierto estado de agosto,
y `_archive/` ya existe. Una vez movidas, `Swarmbly-AI_Clean` es el único
directorio en el que un comando puede aterrizar por accidente.

### Limpieza

`_to_delete/` contiene tres scripts de borrador que escribí en su disco durante
la investigación de la métrica. El puente no puede borrar; elimine esa carpeta
usted mismo. `_audit_cloud_manifest.txt` en la raíz del repositorio es la entrada
de esta auditoría y también puede irse.

---

## Lo que la auditoría **no** encuentra

- Ningún archivo fuente divergente o a medio escribir.
- Ningún resultado calculado a partir de un corpus distinto del que nombran sus
  metadatos.
- Ninguna señal de que una falla del puente haya corrompido algo. Cada entrega o
  aterrizó completa o falló ruidosamente.

Las desconexiones costaron tiempo y forzaron reentregas. No costaron corrección.
