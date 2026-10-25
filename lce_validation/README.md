# lce_validation — harness and validation tools

*Español abajo.*

This directory holds the validation harness of the Swarmbly LCE. It follows the method of the Swarmbly whitepaper v2 (section 3): **an instrument is tested before it is used to decide anything**, and simulated or mock results are never evidence.

## Two kinds of runs

| | what it is | output | evidence? |
|---|---|---|---|
| **Instruments** (`instruments.py`) | numpy simulations checking that each measurement detects what it must | `results/harness/results.json`, `results/harness/REPORT.md` | **No** — they validate instruments |
| **Mock experiments** (`experiments.py` with `MockBackend`) | the real pipeline (digest → anchors → wiki → projection → Γ) driven by a rule-based backend | same files | **No** — plumbing only |
| **Real runs** (`run_real.py`) | the same experiments against real models (Ollama or any OpenAI-compatible server) | `results_real.json`, `REPORT_REAL.md` | candidate evidence, with its scope declared |

## Instruments and the hypotheses they serve

| instrument | hypothesis (whitepaper 11.1) | passes when |
|---|---|---|
| `anchor_gate` | anchoring rule (5.2) | supported claims accepted ≥ 95 %; fabricated, misanchored or stale-hash claims accepted ≤ 5 % |
| `conformity` | H-C11 | the conformist arm loses a 20 % minority; the linear (utility) arm keeps its mean; the I5 guard flags a threshold rule |
| `migration` | H-C8 (instrument) | simulated F_ST decreases with Nm and tracks 1/(1+4Nm) within a factor of 2 in the band 0.5–2.25 |
| `persistence` | H-C5, H-C13 | simulated annual loss matches q^r; shared-operator placement is far worse |
| `selection_bias` | H-C15 | realised gain ≈ i·r·σ; the selection-set estimate is inflated; a fresh set is unbiased |
| `collapse` | H-C7, H-C12 | replace erodes the tail; accumulate bounds it; anchored variation preserves it |
| `error_agreement` | H-C17 (second clause) | independent wrong answers sit at chance (≈ 1/3); shared ones above it; with 1,500 items and no true change the paired-bootstrap CI falls inside ±0.10 in ≥ 80 % of replicates; a real change is detected in ≥ 80 % |
| `r13_abstention` | R13 types 5–6 (rubric) | 12/12 fabricated cases: abstentions vs answers, including numbers repeated from the question and an adversative continuation with content |
| `r13_contradiction` | R13 type 4 (rubric) | accepts the current value or a flagged disagreement and rejects the old value, ≥ 6/7 fabricated cases |
| `i1_equivalence` | I1 / LC6 leak procedure | an injected leak is detected in ≥ 95 % of replicates with ≤ 5 % false alarms |

`run_all` exits with status 1 if any instrument fails.

## Running

```bash
pip install -e '.[dev]'
python -m lce_validation.run_all              # instruments + mock experiments
python -m pytest                              # unit tests, including one test per invariant I1–I8
```

### Real runs: the pre-registered protocol

The confirmatory run of C1 and C2 follows [`docs/PREREGISTRATION_C1_C2_EN.md`](../docs/PREREGISTRATION_C1_C2_EN.md) (Spanish: `_ES`). In order, and without skipping steps:

```bash
# 0. the pre-registration is committed before anything below
# 1. draw the MCQ item set ONCE (1,500 MMLU test items, seed 20261005) and commit it
python -m lce_validation.fetch_mcq
git add lce_validation/data/mmlu_test_1500.json && git commit -s -m "MCQ item set for C2 (pre-registered)"
# 2. models (at least three families) and an embedding model
ollama pull qwen2.5:3b && ollama pull llama3.2:3b && ollama pull gemma2:2b && ollama pull nomic-embed-text
# 3. the run
python -m lce_validation.run_real --models qwen2.5:3b,llama3.2:3b,gemma2:2b \
    --embed-model nomic-embed-text --prereg docs/PREREGISTRATION_C1_C2_EN.md
```

`run_real` labels the run **confirmatory** only if the pre-registration and the item file are committed, the code tree is clean, an embedding model is given and three families respond; otherwise it runs as **exploratory** and reports no verdicts. It records the git commit, the SHA-256 of the pre-registration and of the item file, the Ollama version and model digests, and every raw answer. The verdicts come from [`decide.py`](decide.py), where the pre-registered thresholds live as code.

On the author's Mac the whole sequence is wrapped in `scripts/run_c1_c2_mac.sh`, which checks each step before the next, commits only the item file and pushes nothing.

### Canary verification

The canary items are verified by native speakers with [`data/canary_verification/INSTRUCCIONES.md`](data/canary_verification/INSTRUCCIONES.md) and the sheet `plantilla_verificacion.csv` (eight current items and twelve candidates). `python -m lce_validation.canary_verify verificador_*.csv` applies the rule (at least two of three or more pseudonymous verifiers confirm, none marks the term offensive) and lists corrected glosses for manual review.

Declare the scope with any result: one synthetic user corpus (C1), three synthetic users × 20 topics (H-C2, H-C17a), 1,500 MMLU items × three families (H-C17b), an **unverified** canary set (descriptive only). The canary items in `data/canary_es-EC.json` are drafts (`verified: false`) until a native speaker confirms each gloss.


### Benchmarks, analyses and figure anchoring

| Script | Run or role | Result document |
|---|---|---|
| `bench_hc1_scale.py` | F1a, local memory at scale (exploratory) | `results/BENCH_REPORT.md` |
| `bench_rho.py` | ρ cost of Γ with the real planner and packer | `results/BENCH_REPORT.md` |
| `run_r13.py`, `r13_analysis.py` | R13 pilot and confirmatory run; decision rules of Section 2.7 | `docs/RESULTS_2026-10-11_R13_confirm_EN.md` |
| `bench_forget.py`, `forget_analysis.py` | F-forget (Amendment 6 c) | `docs/RESULTS_2026-10-10_Fforget_AA_EN.md` |
| `aa_test.py` | A/A reproducibility (R14) | same |
| `bench_r11.py` | R11 adapter confirmatory run (refused: manipulation failure) | `docs/RESULTS_2026-10-11_R11_confirm_EN.md` |
| `bench_c2bis.py` | C2-bis (no verdict: within-user homogeneity) | `docs/RESULTS_2026-10-11_C2bis_EN.md` |
| `bench_hc2_closure.py` | H-C2 closure (descriptive) | `docs/RESULTS_2026-10-11_HC2_closure_EN.md` |
| `run_derive.py` | recomputes every stored figure from the raw outputs | fails on drift |
| `doc_figures.py` | every figure cited in documents, README and charts matches the stored results | `tests/test_doc_figures.py` |
| `readme_figures.py` | draws the README charts (light and dark) from the stored results; needs matplotlib | `docs/figures/` |

---

## Español

Este directorio contiene el arnés de validación de la LCE. Sigue el método del whitepaper v2 de Swarmbly (sección 3): **un instrumento se prueba antes de usarlo para decidir nada**, y los resultados simulados o con `MockBackend` nunca son evidencia.

Los **instrumentos** son simulaciones que comprueban que cada medida detecta lo que debe (tabla de arriba). Los **experimentos con mock** recorren el código real con un backend de reglas y solo validan la tubería. Las **corridas reales** (`run_real.py`) repiten C1 y C2 contra modelos reales vía Ollama u otro servidor compatible con OpenAI, y son las únicas que producen evidencia candidata, siempre con su alcance declarado. La corrida confirmatoria sigue el preregistro `docs/PREREGISTRATION_C1_C2_ES.md`: primero se confirma el preregistro, después se extrae una sola vez el conjunto de 1.500 preguntas de MMLU (`fetch_mcq`) y se confirma, y solo entonces se corre `run_real` con `--prereg`. Sin esas condiciones la corrida se etiqueta exploratoria y no emite veredictos; los umbrales viven como código en `decide.py`. `run_all` termina con código 1 si falla cualquier instrumento.

Los ítems del conjunto canario son borradores sin verificar hasta que un hablante nativo confirme cada glosa; con ellos se puede probar el arnés, pero no reportar un resultado.

### Benchmarks, análisis y anclaje de cifras

La tabla de scripts de la sección en inglés vale igual: `bench_hc1_scale.py` (F1a), `bench_rho.py` (costo de Γ en ρ), `run_r13.py` y `r13_analysis.py` (R13 piloto y confirmatoria), `bench_forget.py` y `forget_analysis.py` (F-forget), `aa_test.py` (A/A), `bench_r11.py` (confirmatoria de R11, rechazada por falla de manipulación), `bench_c2bis.py` (C2-bis, sin veredicto), `bench_hc2_closure.py` (cierre de H-C2, descriptivo), `run_derive.py` (recalcula cada cifra guardada), `doc_figures.py` (cada cifra citada en documentos, README y figuras coincide con los resultados) y `readme_figures.py` (dibuja las figuras del README; requiere matplotlib).
