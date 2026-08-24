# Swarmbly AI

[![DOI (software)](https://zenodo.org/badge/DOI/10.5281/zenodo.21956743.svg)](https://doi.org/10.5281/zenodo.21956743)
[![DOI (paper)](https://zenodo.org/badge/DOI/10.5281/zenodo.21957088.svg)](https://doi.org/10.5281/zenodo.21957088)
[![Licence: AGPL-3.0-or-later](https://img.shields.io/badge/licence-AGPL--3.0--or--later-blue.svg)](LICENSE)

**A decentralized inference protocol that fragments the *problem*, not the *model*.**

Swarmbly dispatches semantic micro-tasks to volunteer nodes running complete small language models (SLMs, 1–8B), and reassembles the answers on the client with an orchestrator SLM — using genome shotgun assembly (reads, contigs, overlap, scaffolding, consensus) as its design vocabulary.

Existing peer-to-peer inference systems split the **model**: layers or tensors live on different machines, and activations cross the public internet on **every token**. Swarmbly splits the **problem**: each fragment crosses the network **once**, and every worker runs a whole, small, independent model.

- **Start here (two pages):** [`docs/ONEPAGER_EN.md`](docs/ONEPAGER_EN.md) · [`docs/ONEPAGER_ES.md`](docs/ONEPAGER_ES.md)
- **Whitepaper:** [`docs/WHITEPAPER_EN.md`](docs/WHITEPAPER_EN.md) · [`docs/WHITEPAPER_ES.md`](docs/WHITEPAPER_ES.md)
- **Protocol specification:** [`docs/SPEC_EN.md`](docs/SPEC_EN.md) · [`docs/SPEC_ES.md`](docs/SPEC_ES.md)
- **Critical analysis and red team:** [`docs/`](docs/README.md) — the project publishes its own audit alongside its claims.
- **Annotated bibliography:** [`docs/REFERENCES.md`](docs/REFERENCES.md)
- **Licence:** AGPL-3.0-or-later. Network use triggers clause 13 — see [`NOTICE`](NOTICE).
- **Cite this:** the artifact as [`10.5281/zenodo.21956743`](https://doi.org/10.5281/zenodo.21956743), the paper as [`10.5281/zenodo.21957088`](https://doi.org/10.5281/zenodo.21957088). Machine-readable metadata in [`CITATION.cff`](CITATION.cff).

---

## What has been measured

The design rests on one falsifiable claim: **the more shared context each fragment carries, the less quality is lost when the pieces are rejoined.** A go/no-go threshold was registered publicly *before any data existed* — if the coherence tax never fell below 5 % in any task category, the architecture was to be abandoned.

Run against three real model families (`llama3.2:3b`, `qwen2.5:3b`, `gemma2:2b`), the prediction held:

| Shared context ρ | 1.00 | 1.25 | 1.50 | 2.00 |
|---|---|---|---|---|
| Coherence tax | 24.1 % | 20.4 % | 16.1 % | **13.7 %** |

Monotone in both the ratio and the denominator-free absolute difference. **Three task categories cleared the pre-registered threshold, and in two of them the tax went negative — fragmenting the problem and reassembling it produced a *better* answer than doing it in one piece, by as much as 9.0 %.**

The companion V3c run found **no relationship between inter-replica agreement and judged quality** (*r* = −0.030 over 597 units), which does not support the confidence map the whitepaper describes; that contribution has been demoted rather than defended. Eight prompts — one of which produced no usable baseline — one seed, 2–3B models, and one of the two coherence instruments produced no usable measurement at all: a signal to act on, not a benchmark. Everything, including the parts that went the wrong way: [`docs/RESULTS_V0_V3C.md`](docs/RESULTS_V0_V3C.md).

---

## The honest summary

Swarmbly does **not** claim to be faster than a centralized API. Single-node speculative decoding already delivers 2–3× with a *proof* that the output distribution is unchanged; no fragmentation scheme beats that on latency.

What Swarmbly claims is **access to capacity you do not own**, for workloads that are decomposable, latency-tolerant and token-intensive — bulk document processing, synthetic data generation, code-migration sweeps, evaluation at scale.

And it claims that this is bought at a **measurable price in coherence**, which the protocol is designed to report rather than hide.

That price is what this repository measures first.

---

**Why "Swarmbly"?** *Swarm* and *assembly*. The swarm is the easy half — running many models at once is a scheduling problem, and scheduling was solved decades ago. The assembly is the hard half: a swarm produces fragments, and turning fragments into one coherent answer is where quality is lost and where this design can fail. The name puts the difficult part in the word.

## V0 — the coherence-tax harness

The project's make-or-break question, asked before a single line of networking code:

> **How much output quality is lost by fragmenting a prompt and reassembling it — and how does that loss depend on how much context travels with each fragment?**

The controlling variable is **ρ** (*rho*), the contextual redundancy ratio: total dispatched input tokens divided by original prompt tokens. ρ is simultaneously the privacy leak, the coherence glue and the substitute for worker model capacity. V0 traces that curve.

### Go / no-go criterion

> There must exist a value of ρ at which coherence degradation is **< 5 % relative to monolithic generation**, in **at least one task category**.
>
> If no such ρ exists, the architecture is not viable, and the project should stop or pivot to workloads with no seam to break (classification, extraction, labelling).

The harness prints this verdict on every run.

### Quick start

```bash
pip install -e ".[dev]"
pytest -q

# Full sweep with the deterministic mock backend — no API keys, no downloads
python -m swarmbly_v0 run --rho 1.0,1.25,1.5,2.0 --n 2,4,8 --backend mock --out results/

# Standalone HTML report from an existing CSV
python -m swarmbly_v0 report results/results.csv --out results/report.html
```

### Running it against real models

One command, three model families, on your own machine. Start with the smoke tier — it exercises every code path the long runs use, on two prompts, in about five minutes:

```bash
./scripts/run_ollama.sh smoke     # ~5 min    does the wiring hold?
./scripts/run_ollama.sh all       # ~5-7 h    V0 (coherence tax) + V3c (agreement vs quality)
```

The script pulls what is missing, checks the round trip before committing hours to it, and refuses to start with fewer than three distinct model families — three replicas of *one* family measure that family's sampling variance, not the disagreement between independent estimators. See [`scripts/README.md`](scripts/README.md).

Under the hood it is any OpenAI-compatible endpoint (Ollama, llama.cpp's server, vLLM), configured by environment:

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export SWARMBLY_MODEL=llama3.2:3b
export SWARMBLY_EMBED_MODEL=nomic-embed-text
export SWARMBLY_REPLICA_MODELS='llama:llama3.2:3b,qwen:qwen2.5:3b,gemma:gemma2:2b'

python -m swarmbly_v0 run --backend openai --embedder api \
  --rho 1.0,1.25,1.5,2.0 --n 2,4,8 --k 1,3 --out results/real/
```

`--embedder api` uses the server's own `/embeddings` route (`nomic-embed-text` on Ollama), which needs no second model stack and no download from a model hub. `--embedder st` uses `sentence-transformers` instead; `pip install -e ".[embeddings]"` first. The default `hash` embedder is a deterministic stand-in whose cosine values carry no semantics — a τ calibrated on it is not a threshold, it is a number, and the run metadata says so.

### What the harness measures

| Metric | What it captures |
|---|---|
| `booook_like_score` | Fraction of sentences free of mechanically detectable seam errors, across eight classes: entity omission, duplicated content, contradiction, register/tense shift, dangling reference, missing transition, repeated introduction, inconsistent naming |
| `entity_grid` | Simplified Barzilay & Lapata entity-grid local coherence |
| `judge_score` | Overall answer quality, reported **separately** from coherence — an aggregate "which is better" judgement hides exactly the damage under study |
| `rho_achieved` | Realised context budget, versus the target |
| `coherence_tax_*` | Relative degradation against the monolithic baseline. **The headline number.** |
| `tau_sem` | Calibrated seam threshold — never a fixed constant (see below) |
| `k`, `n_families` | Micro-level replica count and how many distinct model families produced them |
| `mean_agreement` | Mean per-unit agreement across the aligned replicas |
| `frac_high` / `frac_medium` / `frac_low` | The confidence map: share of units taken by medoid, judge-selected, and judge-selected *and flagged* |
| `n_low_conf_regions` | Contiguous spans the swarm did not converge on — reported to the user, not smoothed away |
| `agreement_quality_correlation` | **The second headline number**: does agreement actually predict judged acceptability? |

### Two levels of assembly

Swarmbly assembles twice, and the two are different operations:

| Level | What is split | How it is resolved | Controlled by |
|---|---|---|---|
| **Macro** | Different sub-tasks of one large task | Overlap-and-splice with flanking context; synthesis only where a seam fails | `ρ`, `N` |
| **Micro** | *Nothing.* `k` **complete replicas of the same micro-task**, from deliberately different model families | Progressive multiple alignment over semantic units, then a per-unit agreement score routing to medoid / judge / flag | `k` |

Splitting an **atomic** question into partial sub-questions is supported at neither level, and the code says so where it would be tempting. Decomposition that removes information *before* sampling destroys information no amount of redundancy afterwards can recover — averaging `k` answers to the wrong question yields a confident wrong answer. An atomic request skips the macro level and goes straight to micro with `k` replicas of the whole request.

The micro level emits a **confidence map**, not just text: every unit carries its agreement score, the replicas that contributed, and a `HIGH` / `MEDIUM` / `LOW` label, and contiguous `LOW` units become named low-confidence regions.

```bash
# sweep both levels at once
python -m swarmbly_v0 run --rho 1.0,1.5 --n 2,4 --k 1,3 --backend mock --out results/
```

### Three privacy tiers

Routing has a second axis, orthogonal to how sensitive the content is: which *population of machines* a request may reach. `swarmbly_v0/privacy.py` is the reference implementation.

| Tier | Population | Transport | Confidence map |
|---|---|---|---|
| `GLOBAL` | Any conformant worker in the open registry | Authenticated worker identity | Yes, at the derived `k` |
| `TRUSTED` | Only nodes on the named swarm's public-key whitelist, under a declared operator | **Mutual TLS required on every link** | Yes — unless the operator drops to `k = 1`, which is permitted only with a recorded waiver |
| `LOCAL` | The requesting device only | No network egress | No — nothing to align |

The classifier is pure, local and **cannot** be given a remote backend: a privacy check that asks the network whether a prompt is private has already disclosed the prompt. A manual flag (`--privacy=trusted|local`) is authoritative and is never downgraded by the recall-oriented automatic triage.

```python
from swarmbly_v0 import classify, resolve_k, SwarmRegistry, routing_metadata

reg = SwarmRegistry(swarm_id="hospital-a", operator="Hospital A IT",
                    members=frozenset({"nodeA", "nodeB"}))
d  = classify("Summarise the patient's diagnosis.", swarm_id="hospital-a")
kd = resolve_k(1, d, reg)
routing_metadata(d, kd, reg)["consensus_waived_reason"]   # 'trusted_swarm_k1'
```

A trusted swarm relocates trust to whoever holds the whitelist; it does not remove it, and the specification says so rather than leaving it to be discovered.

### Design commitments the code enforces

1. **The router may refuse to fragment.** A system that fragments everything is strictly worse than Skeleton-of-Thought was in 2023. The router's decision threshold is asymmetric: wrongly fragmenting costs more than wrongly declining.
2. **Plans are DAGs, not lists.** Dependencies between sub-tasks are modelled explicitly; only same-level tasks run in parallel.
3. **Select before you synthesize.** When several candidates exist, the assembler picks one and splices it. Synthesis runs only when a seam actually fails.
4. **τ_sem is calibrated, never assumed.** Contextual embedding space is anisotropic and cosine values are not portable between models; `metrics.calibrate_tau` derives the threshold from labelled pairs with an asymmetric objective. The consensus thresholds `α_high` and `α_low` are on exactly the same footing: the defaults (0.80 / 0.55) are documented placeholders, and `metrics.calibrate_alpha` is what replaces them.
5. **Coherence is reported, not buried.** Every assembly returns a per-seam record and an error-class breakdown.
6. **Redundancy resolves sampling variance, never missing information.** `k` replicas are `k` complete answers to the same question — the micro level never splits an atomic request, because averaging answers to the wrong question cannot recover what the split threw away.
7. **Disagreement is surfaced, not averaged.** Where the replicas fail to converge the answer carries a low-confidence region instead of a smoothed-over sentence, and the coverage model in `metrics` bounds **availability under packet loss** — explicitly not correctness.
8. **A confidence map that was never computed is never reported.** Reducing `k` to 1 inside a trusted swarm is allowed and cheap; doing it silently is not. `privacy.resolve_k` returns the waiver reason with the number, and the coverage floor `k ≥ 2` under measured loss is not waivable.

### ⚠️ Limitations — read before quoting any number

- **`MockBackend` results are harness validation, not evidence.** The mock deliberately simulates context-dependent drift so the pipeline and metrics can be exercised without a GPU. Its coherence-tax curve says something about the harness; it says **nothing** about real language models. Every claim about Swarmbly's viability must come from a run against real models.
- The metrics are **mechanical proxies**. `booook_like_score` detects error classes that regex and entity tracking can find; it is not a human coherence judgement.
- `HashEmbedder` is a deterministic fallback so the code runs anywhere. Any τ calibrated on it is meaningless — use `[embeddings]` for real work.
- **Agreement is not truth.** Models sharing training data share errors, so replicas that agree may simply be wrong together; cross-family diversity is what makes the signal mean anything, and the agreement↔accuracy correlation must be **measured** (V3c) rather than assumed — which is why the harness reports `agreement_quality_correlation` on every run, including when it is flat.
- The prompt set is small (8 prompts across 8 categories) and is a smoke-test corpus, not a benchmark.
- V0 has **no networking, no verification, no adversarial nodes**. Those are V2 and V3.

---

## Repository layout

```
swarmbly_v0/        V0 harness: privacy (tier routing), router, planner, packing,
                   assembler (macro), consensus (micro), metrics, experiment, report
tests/             pytest suite
prompts/           labelled prompt set (category, expected_decomposable) — doubles as router eval
docs/              whitepaper, protocol spec, analysis, references
.github/           SWIP proposal template, PR template
```

## Prior art and patents

This is a **defensive publication**. The techniques described here — semantic
fragmentation of a request, the context budget *S*, the coverage model
`c ≥ ln(1/ε)/(1−p)`, two-level assembly with cross-family consensus, and
privacy-tier routing — are disclosed publicly and in enabling detail so that
they remain free for anyone to implement.

**The author asserts no patent claims over the disclosed techniques and places
them in the public domain for patenting purposes.**

The disclosure is dated by two independent Zenodo records —
[`10.5281/zenodo.21956743`](https://doi.org/10.5281/zenodo.21956743) for the
artifact and
[`10.5281/zenodo.21957088`](https://doi.org/10.5281/zenodo.21957088) for the
paper — and by this repository at tag `v1`.

## Contributing

DCO sign-off (`git commit -s`), not a CLA — see [`CONTRIBUTING.md`](CONTRIBUTING.md). Protocol changes go through a SWIP.

**One rule above the others: any performance or quality claim in a pull request must cite a measurement.** This project exists because a plausible architecture was mistaken for a validated one.

## Governance

Pre-foundation, benevolent maintainer, heading for a Swiss Verein and later a Stiftung. The Foundation will own copyright and trademark and will **not** sell proprietary exceptions — dual licensing is explicitly rejected as incompatible with the mandate. See [`GOVERNANCE.md`](GOVERNANCE.md).

---

## Resumen en español

**Swarmbly AI** es un protocolo de inferencia descentralizada que fragmenta **el problema**, no **el modelo**. Los sistemas P2P existentes reparten capas de una red neuronal entre máquinas y hacen viajar activaciones por internet **en cada token**; Swarmbly reparte micro-tareas semánticas que cruzan la red **una sola vez**, y cada nodo ejecuta un modelo pequeño completo e independiente.

**Lo que este repositorio mide primero** es el *impuesto de coherencia*: cuánta calidad se pierde al fragmentar y reensamblar, en función de **ρ**, la tasa de redundancia contextual. ρ es a la vez la fuga de privacidad, el pegamento de la coherencia y el sustituto de la capacidad del modelo trabajador.

**Criterio de continuación:** debe existir un ρ con degradación de coherencia **< 5 %** frente a la generación monolítica en al menos una categoría de tarea. Si no existe, la arquitectura no es viable — y conviene saberlo ahora, no dentro de dos años. El banco de pruebas imprime ese veredicto en cada ejecución.

```bash
pip install -e ".[dev]" && pytest -q
python -m swarmbly_v0 run --rho 1.0,1.25,1.5,2.0 --n 2,4,8 --k 1,3 --backend mock --out results/
```

**Dos niveles de ensamblado:** el nivel **macro** une sub-tareas distintas de una misma tarea por solapamiento y empalme (controlado por ρ); el nivel **micro** resuelve `k` réplicas **completas de la misma** micro-tarea, producidas por familias de modelos deliberadamente distintas, mediante alineamiento múltiple progresivo y consenso con puntuación de acuerdo por unidad (controlado por `k`). Dividir una pregunta **atómica** en sub-preguntas parciales no está soportado en ninguno de los dos niveles: eso elimina información *antes* del muestreo, y ninguna redundancia posterior la recupera.

**⚠️ Advertencia:** los resultados con `MockBackend` **validan el banco de pruebas, no son evidencia sobre modelos reales**. Cualquier afirmación sobre la viabilidad de Swarmbly debe provenir de una ejecución contra modelos reales (Ollama, llama.cpp, vLLM — ver arriba).

Swarmbly **no** afirma ser más rápido que una API centralizada: la decodificación especulativa ya entrega 2–3× con preservación demostrada de la distribución de salida. Lo que afirma es **acceso a capacidad que no se posee**, para cargas descomponibles y tolerantes a latencia, a un precio en coherencia que el protocolo está diseñado para **medir y reportar**, no para ocultar.

---

Copyright © 2026 Sebastián A. Espinoza-Ulloa. Licensed under AGPL-3.0-or-later.
