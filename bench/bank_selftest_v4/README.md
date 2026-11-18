# Banco de autoprueba v4 · Cuenca Viva

**No reservado.** Reproduce el banco de ejemplo de `ejemplobancov4.md` con la
persona ficticia Tomás Aravena Lillo y el proyecto Cuenca Viva. Sirve para
probar el arnés 1.3; no es una medición de la 3.4.

## Contenido

- 24 fichas en `02_CASOS_RESERVADOS/S2_S3_S4_reservados.md` (6 de regresión,
  7 de código, 5 de listas y 6 de herramientas/permisos).
- Corpus privado con CSV limpio y sucio, XLSX de dos hojas, informe, acta,
  glosario y notas de campo largas con dos trampas sembradas.
- Dos fichas públicas, cuatro catálogos MCP (uno con `.cambio.json`), tres
  registros de autores, dos skills (una con script marcador) y los scripts de
  referencia de las fichas `código-exacto`.

## Cifras de referencia

| Ficha | Referencia | Valor copiado en la ficha |
|---|---|---|
| EJ4-07 | `03_REFERENCIA/EJ4-07.py` | 4,173; 6,274; 8,836 m³/s; varía más Quilén Medio |
| EJ4-08 | `03_REFERENCIA/EJ4-08.py` | 24,6 m³/s |
| EJ4-09 | `03_REFERENCIA/EJ4-09.py` | 86 filas válidas (1 duplicada, 3 vacías, 5 comas, 1 fórmula) |
| EJ4-13 | `03_REFERENCIA/EJ4-13.py` | 838,4; 890,9; 1267,5 mm; coinciden: no |

Los scripts se ejecutaron antes de sellar; el arnés **no** los ejecuta.

## Uso

```bash
python3 bench/run_bank.py --bank bench/bank_selftest_v4 --model qwen2.5:7b --check
python3 bench/run_bank.py --bank bench/bank_selftest_v4 --model qwen2.5:7b \
    --persona "Tomás Aravena Lillo" --executor "<tu nombre>" --repeat 1
```

El sello se rehace con el comando del paso 8 de `ejemplobancov4.md`:

```bash
cd bench/bank_selftest_v4
find 01_MATERIALES 02_CASOS_RESERVADOS 03_REFERENCIA -type f ! -name '.DS_Store' \
  -print0 | sort -z | xargs -0 shasum -a 256 > 05_SELLO/SELLO.sha256
```
