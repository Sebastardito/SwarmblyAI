# Open list battery · Batería abierta de listas

**Language / Idioma:** [English](#english) · [Español](#español)

---

## English

Fictitious material for recipe 4 (“process a list on the swarm”) in Swarmbly
3.4. Every expected cell is fixed in `casos.json` before a run: the operation
states its own rule, so the answer can be checked with a regular expression and
no world knowledge a small model may lack. Names are invented (Inés Carvallo,
Tomás Vera, Nadia Sotelo; the lots Aliso, Canelo, Lingue and Maqui); none of the
people or companies is real.

The battery is open: anyone may read it and tune with it. It is **not** a sealed
measurement.

| Case | Source | What it checks |
|---|---|---|
| CL-01 | pasted | classify each word by its first letter; 2 blank lines and a duplicate |
| CV-01 | pasted | convert inches to centimetres with the factor in the operation |
| EX-01 | pasted | extract a code from a short record |
| EX-02 | pasted | extract a date in `dd/mm/aaaa` |
| TR-01 | pasted | translate six common words |
| SI-01 | pasted | yes/no on the parity of the record number |
| SI-02 | pasted | yes/no on a letter present in the word |
| MX-01 | pasted, 18 items | add 7 to each number; crosses the 12-item wave boundary |
| CS-01 | CSV column | count the letters of each lot name; one empty cell is dropped, one value repeats |
| EX-03 | pasted | one record gives no basis: the table must say `missing`, not invent a code |
| PN-01 | pasted, personal names | personal names with e-mail; preview must propose local and say why |
| DO-01 | project document | each lot's deposit code is only in `fichas_lotes.md`; recipe 4 must use the document per item |

A case may declare `corpus` (paths relative to the battery) to see only those
files; without it the whole `corpus/` folder is copied. `DO-01` uses this so its
document cannot leak into the other cases.

The runner starts one App per case and repetition with its own data folder and
the internet blocked, reads the preview (`POST /api/recipes/list/preview`), sends
the list locally (`recipe: "list"`, `where: "local"`) and scores `meta.table` /
`meta.list` and the receipt. It checks: one row per input item in input order,
stable ids `1..n`, duplicate rows marked, the status column present, every cell
against its expected regex (or `—`/`missing` where the case expects no basis),
no extra rows, `meta.table.by_code` true, the expected wave count, the preview’s
items and privacy, and zero sends.

```bash
python3 bench/run_dev.py --model qwen2.5:7b --battery bench/dev_list --repeat 3 --label list
python3 bench/run_dev.py --rescore bench/dev_list/ejecuciones/<run>
```

The run is written under `bench/dev_list/ejecuciones/` (git-ignored):
`resumen.json`, `resumen.md`, one JSON per case and repetition, app logs and the
network log. `--rescore` re-scores the same answers with the current
`casos.json`; it does not ask the model again.

---

## Español

Material ficticio para la receta 4 («procesar una lista en el enjambre») de
Swarmbly 3.4. Cada celda esperada está fijada en `casos.json` antes de ejecutar:
la operación enuncia su propia regla, así que la respuesta se comprueba con una
expresión regular y sin conocimiento del mundo que un modelo pequeño pueda no
tener. Los nombres son inventados (Inés Carvallo, Tomás Vera, Nadia Sotelo; los
lotes Aliso, Canelo, Lingue y Maqui); ninguna persona ni empresa es real.

La batería es abierta: cualquiera puede leerla y ajustar con ella. **No** es una
medición sellada.

| Caso | Origen | Qué comprueba |
|---|---|---|
| CL-01 | pegado | clasificar cada palabra por su primera letra; 2 líneas en blanco y un duplicado |
| CV-01 | pegado | convertir pulgadas a centímetros con el factor de la operación |
| EX-01 | pegado | extraer un código de una ficha corta |
| EX-02 | pegado | extraer una fecha en `dd/mm/aaaa` |
| TR-01 | pegado | traducir seis palabras comunes |
| SI-01 | pegado | sí/no sobre la paridad del número de la ficha |
| SI-02 | pegado | sí/no sobre una letra presente en la palabra |
| MX-01 | pegado, 18 elementos | sumar 7 a cada número; cruza el límite de ola de 12 |
| CS-01 | columna de CSV | contar las letras de cada nombre de lote; una celda vacía se descarta y un valor se repite |
| EX-03 | pegado | una ficha no da base: la tabla debe decir `missing`, no inventar un código |
| PN-01 | pegado, nombres personales | nombres con correo; la vista previa debe proponer local y explicar por qué |
| DO-01 | documento del proyecto | el código de depósito de cada lote solo está en `fichas_lotes.md`; la receta 4 debe usar el documento por elemento |

Un caso puede declarar `corpus` (rutas relativas a la batería) para ver solo
esos archivos; sin ese campo se copia toda la carpeta `corpus/`. `DO-01` lo usa
para que su documento no se mezcle con los demás casos.

El arnés inicia una App por caso y repetición, con carpeta de datos propia y la
red bloqueada, lee la vista previa (`POST /api/recipes/list/preview`), envía la
lista en local (`recipe: "list"`, `where: "local"`) y puntúa `meta.table` /
`meta.list` y el recibo. Comprueba: una fila por elemento de entrada en orden,
ids estables `1..n`, filas duplicadas marcadas, columna de estado presente, cada
celda contra su regex esperada (o `—`/`missing` donde el caso no da base), sin
filas extra, `meta.table.by_code` verdadero, el número de olas esperado, los
elementos y la privacidad de la vista previa, y cero envíos.

```bash
python3 bench/run_dev.py --model qwen2.5:7b --battery bench/dev_list --repeat 3 --label list
python3 bench/run_dev.py --rescore bench/dev_list/ejecuciones/<run>
```

La corrida se escribe en `bench/dev_list/ejecuciones/` (ignorada por git):
`resumen.json`, `resumen.md`, un JSON por caso y repetición, los registros de la
App y el registro de red. `--rescore` vuelve a puntuar las mismas respuestas con
el `casos.json` actual; no vuelve a preguntar al modelo.
