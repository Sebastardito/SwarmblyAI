# Swarmbly AI — Arnés de validación

*English version: [`README_EN.md`](README_EN.md).*

Arnés ejecutable en **Python 3 stdlib** (cero dependencias) que valida el
razonamiento de `docs/WHITEPAPER_V2_ES.md` y sus documentos acompañantes, e
implementa las pruebas de falsación de los cinco modelos M1–M5 con sus
condiciones de rechazo declaradas.

Corre dos baterías:

- **derivación** (T00–T12) — reproduce la aritmética de los documentos, prueba
  sus propios predicados de rechazo, y mide δ, la longitud de salida y la
  interacción sobre los artefactos del repositorio.
- **empírica** (T0R–T10R, T0RR, T0RR2, T0LR) — juzga M1–M5 contra las **341
  corridas reales** de `swarmbly_ref/data/benchmark.jsonl`.

## Ejecución

```bash
python3 swarmbly_validation/run_all.py            # derivación   → REPORT.md
python3 swarmbly_validation/run_all.py --real     # empírica     → REPORT_REAL.md
python3 swarmbly_validation/run_all.py --all      # las dos      → REPORT_COMBINED.md
python3 swarmbly_validation/tests/t4_delta.py     # una prueba suelta
```

Sale con código distinto de cero si alguna prueba falla, para que sirva en CI sin
que nadie tenga que leer el resumen.

## Qué se puede reproducir desde un clon, y qué no

El corpus de la campaña de referencia **sí está versionado**
(`swarmbly_ref/data/benchmark.jsonl`, sha256 anclado en T00), así que las trece
pruebas empíricas corren tal cual desde un clon limpio.

Las corridas anteriores que cita el whitepaper v1.4 **no lo están**: el
repositorio no versiona `results/`. Tres pruebas de derivación —T00, T04 y T06—
dependen de esos directorios y en un clon devuelven `REFUSE` con la razón
escrita, en lugar de pasar o fallar sobre datos que no están. Para activarlas,
apunta `SWARMBLY_REPO` a un checkout que conserve sus directorios de corrida:

```bash
export SWARMBLY_REPO=/ruta/al/checkout/con/results
export SWARMBLY_BENCH=/ruta/a/benchmark.jsonl   # opcional; se autodetecta
```

Que una comprobación se niegue en vez de adivinar es el punto, no un defecto:
§15.7 del whitepaper explica por qué.

## Veredictos

| Veredicto | Significado |
|---|---|
| `PASS` | el razonamiento o el mecanismo se verifica (o la aritmética reproduce) |
| `FAIL` | la predicción se refuta |
| `REFUSE` | el instrumento no discrimina o le falta el insumo: se niega a emitir veredicto |
| `BLOCKED` | falta un insumo para el veredicto empírico |
| `CONCEPTUAL` | chequeo de razonamiento sin medición nueva |

`REFUSE` y `FAIL` no son lo mismo y el arnés no los confunde: un artefacto
**ausente** produce `REFUSE`; un artefacto **presente que no reproduce su cifra**
produce `FAIL`.

## Estructura

```
swarmbly_validation/
├── run_all.py               # orquestador de las dos baterías
├── run_real.py              # batería empírica sobre benchmark.jsonl
├── make_corpus.py           # generador del corpus candidato (T06)
├── funding_case.py          # genera FUNDING_CASE.md desde el JSONL
├── swarmblyval/
│   ├── constants.py         # constantes y umbrales declarados
│   ├── fixtures.py          # números transcritos de los documentos
│   ├── loaders.py           # carga artefactos reales; se niega si no cuadran
│   ├── delta.py             # estimador de δ con componentes declarados
│   ├── corpus.py            # generador + compuerta de admisión
│   ├── interaction.py       # H-INT con predictor leave-one-out
│   ├── derivation.py        # fórmulas derivadas (ρ, cobertura, muestra, …)
│   ├── stats.py             # bootstrap, tests exactos, predicados de rechazo
│   └── report.py            # esquema de resultado + render consola/Markdown
└── tests/
    ├── t0_provenance.py     # reconciliación + autocomprobación + ancla del corpus
    ├── t1_split_k.py        # M5 — separar k en tres
    ├── t2_triage.py         # M3 — compuerta de triaje (42/60)
    ├── t3_uniqueness.py     # M2 — unicidad en el plan
    ├── t4_delta.py          # M4 — δ explica la bimodalidad
    ├── t5_rho_scaling.py    # ley de escala de ρ
    ├── t6_corpus.py         # corpus con pregunta global (bloqueador)
    ├── t7_rd_surface.py     # M4 — superficie D(ρ,δ)
    ├── t8_l_curve.py        # curva-L
    ├── t9_criterion.py      # re-prueba del criterio de abandono
    ├── t10_aligner.py       # M1 — alineador con sustitución semántica
    ├── t11_length.py        # confundido de longitud de salida
    └── t12_interaction.py   # H-INT, retirada de forma reproducible
```

## Qué establece y qué no

**Lo que el arnés sostiene.** M4 queda falsado en dos instrumentos
independientes, con un experimento controlado a ρ constante (T04R, T07R). M2
sobrevive corregido (T03R). M3 sobrevive (T02R). La ley de escala de ρ se
verifica contra datos reales (T05R). El router queda refutado a nivel de celda
(T0RR, T0RR2). `L*` varía por clase de nodo (T0LR).

**Lo que el arnés se niega a sostener.** El criterio de abandono. El impuesto
agregado está confundido con el presupuesto de salida (T11), así que T09R
`REFUSE` en vez de reportar un criterio cumplido. La corrida que lo resuelve es
`swarmbly_ref/benchmarks/run_benchmark.py --matched`.

**Autocomprobación.** Los predicados de rechazo se prueban con casos de respuesta
conocida (T00). Dos fallaban en silencio y sus regresiones quedan fijadas:
`withdraw_if_largest_cell_undoes` callaba justo cuando la inversión era grande y
sólo quitaba un contribuyente —no veía el caso documentado, donde la media la
fabrican dos prompts juntos—, y `bimodality_summary` mezclaba lista y dict, así
que reventaba con ambas. T12 conserva una hipótesis **retirada** para que la
retirada sea reproducible en vez de una nota al pie.

## Documentos relacionados

- `docs/WHITEPAPER_V2_ES.md` §15.9 — el análisis de la campaña.
- `docs/RESULTS_2026-09-25_refbench_ES.md` — el registro de la campaña.
- `docs/VALIDATION_STRATEGY_V2_ES.md` — la agenda que este arnés ejecuta.
