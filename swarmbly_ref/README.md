# Swarmbly AI — Arquitectura de referencia y benchmark (Ollama)

*English version: [`README_EN.md`](README_EN.md).*

Implementación de referencia del protocolo Swarmbly (v0.3, simplificada) que
ejecuta el ciclo completo — router → planner → packing → dispatch multi-familia →
triaje → ensamblado → auditoría — sobre **Ollama local** con 5 familias SLM
(`llama3.2:3b`, `qwen2.5:3b`, `gemma2:2b`, `phi3.5:3.8b`,
`granite3.1-dense:2b`) y `nomic-embed-text` para costos de sustitución
semántica. Genera los datos reales que desbloquean las pruebas T04–T10 del
arnés de validación (`../swarmbly_validation/run_all.py --real`).

## Requisitos

- Ollama instalado y servidor corriendo. Arranque con las variables del proyecto:

```bash
./run_server.sh
# equivalente a:
OLLAMA_MODELS="/Volumes/Workdrive/Models" OLLAMA_FLASH_ATTENTION="1" \
OLLAMA_KV_CACHE_TYPE="q8_0" OLLAMA_CONTEXT_LENGTH=65536 ollama serve
```

- Modelos: `ollama pull llama3.2:3b qwen2.5:3b gemma2:2b phi3.5:3.8b granite3.1-dense:2b nomic-embed-text`

## Componentes

| Módulo | Pieza del protocolo | Notas |
|---|---|---|
| `planner.py` | P9/E20: cortes en interfaz débil, δ, asignación de unicidad (M2), router con rechazo (P2) | coupling = palabras de contenido compartidas entre oraciones adyacentes |
| `packer.py` | E2/E6: contrato Γ (nunca recortado), flancos F, paquetes, ρ | H contado sin modelos |
| `triage.py` | M3: predicado mecánico por fragmento | cobertura de ítems esperados, cotas, esquema; RETRY→DISCARD |
| `assemble.py` | P4/E7: descuento de flancos, select-then-splice, puente solo en costura fallida, cardinalidad (M2), auditoría de costuras (P6) | similitud de costura con embeddings (τ_sem) |
| `grader.py` | cobertura, claves, restricciones, fracción sin costura, tax | piso baseline 0.20 (rechazo §15.7) |
| `benchmark.py` | armas: monolítico / fragmentado / fan / fallo inyectado / k_epist | registros JSONL con resume por key |
| `benchmarks/corpus.py` | 8 tareas diversas, deterministas, con claves verificables | ver respuestas perfectas a mano |

## Corpus (22 tareas)

| Tarea | Tipo | Qué ejercita |
|---|---|---|
| 16 tareas de tabla (`table_outturn`, `table_bonded`, `portfolio_q1`–`q5`, `bond_municipal`, `bond_corporate`, `inventory_snapshot`–`spares`, `fleet_metrics`, `sales_regions`) | resumen de tabla (16 filas como oraciones) | agregación global + cobertura; las claves derivadas (totales) replican el diagnóstico de la curva-L |
| `long_report` | reporte anual 5 secciones, 40 oraciones | term_once con asignación en el plan (M2), entidades canónicas |
| `fan_qa` | 6 preguntas independientes, 30 oraciones | topología fan, verificación mecánica |
| `constrained_composition` | briefing 4 párrafos, 3 términos exactamente-una-vez, sin frases repetidas | la clase irreducible `no_repeated_ngram` |
| `extraction_grid` | 8 manifiestos → JSON | verificación por esquema |
| `longform` | revisión anual 60 oraciones | curva-L (barrido L=10/20/40), eje de solvabilidad |
| `chain_refusal` | cómputo secuencial (result-dependency) | el router DEBE rechazar |

## Ejecución

```bash
python3 benchmarks/run_benchmark.py --pilot     # 1 tarea × 1 modelo (rápido, verifica todo)
python3 benchmarks/run_benchmark.py --full      # corpus × 5 modelos + curva-L + fallo + k_epist (≈1 h)
python3 benchmarks/run_benchmark.py --extend    # tablas nuevas (portfolio_q1, inventory_snapshot) × 5 modelos
python3 benchmarks/run_benchmark.py --strong-cut  # cortes anti-P9 (δ alto) sobre las 4 tablas (M4/T07R)
python3 benchmarks/run_benchmark.py --sc        # baseline self-consistency k=5 (v0.3, Zhang et al.)
python3 benchmarks/run_benchmark.py --pairs2    # pares controlados δ: 8 tablas × 5 familias × {mono, débil, fuerte}
python3 benchmarks/run_benchmark.py --tasks table_outturn,fan_qa --models llama3.2:3b
python3 benchmarks/run_benchmark.py --router    # decisiones del router vs verdad (sin LLM)
python3 benchmarks/run_benchmark.py --matched   # re-corre frag con presupuesto de salida igualado
```

### El presupuesto de salida

Hasta el 25 de septiembre de 2026 cada fragmento recibía el `max_out_tokens` del
prompt entero, de modo que un plan de `N` fragmentos disponía de `N` veces la
salida del brazo monolítico. Como el score sube con la longitud, el impuesto
medido dejaba de ser interpretable (T11 del arnés). `--matched` reparte ese
presupuesto entre los fragmentos y registra las celdas con el sufijo `|matched`,
así que las dos mediciones conviven en el mismo JSONL. Los campos
`output_words` y `length_ratio` van en cada registro para que el confundido sea
visible sin re-derivarlo del texto.

## Los datos

`data/benchmark.jsonl` contiene las **341 corridas** de la campaña de
referencia, con digest sha256 anclado en la prueba `T00` del arnés. Está
versionado —a diferencia de `results/`, que no lo está— porque no es
reproducible: las salidas de un modelo no son deterministas, y sin este archivo
las afirmaciones de la sección 15.9 del whitepaper no se pueden comprobar. Un
resultado no reproducible que sostiene una afirmación publicada es una fuente,
no una salida.

Resume automático: los keys ya en `data/benchmark.jsonl` no se re-ejecutan.

## Datos producidos

`data/benchmark.jsonl` — un registro por corrida con: `rho`, `delta`, `cuts`,
`triage` (veredictos y reintentos), `grade` (cobertura/claves/restricciones/
costuras), `cardinality`, `seams`, textos, tokens y tiempos por paquete.

Consumo por el arnés:

```bash
cd ../swarmbly_validation
python3 run_real.py --embed      # veredictos empíricos T02R–T10R + REPORT_REAL.md
```

## Notas de diseño honestas

- **H ≠ 39 aquí**: Γ incluye el glosario de entidades (hasta 16 nombres), así
  que H fijo ≈ 100–150 tok. La contabilidad de T05R lo mide y lo explica.
- **Determinismo**: temperatura 0 + `seed` fijo por llamada.
- **Heterogeneidad real**: ~98 tok/s (llama3.2/phi3.5 en GPU) vs ~7 tok/s
  (granite en CPU) — la heterogeneidad de nodos que el diseño anticipa.
- Los resultados NO son comparables con la medición v1.4 del proyecto: otro
  corpus, otro grader, modelos de 2–4B. Son la primera corrida del instrumento
  nuevo, no una re-medición del criterio.
