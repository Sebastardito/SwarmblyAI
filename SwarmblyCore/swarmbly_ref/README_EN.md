# Swarmbly AI — Reference architecture and benchmark (Ollama)

*Versión en español: [`README.md`](README.md).*

Reference implementation of the Swarmbly protocol (v0.3, simplified) that runs
the full cycle — router → planner → packing → multi-family dispatch → triage →
assembly → audit — over **local Ollama** with 5 SLM families (`llama3.2:3b`,
`qwen2.5:3b`, `gemma2:2b`, `phi3.5:3.8b`, `granite3.1-dense:2b`) plus
`nomic-embed-text` for semantic substitution costs. It produces the real data
that unblocks tests T04–T10 of the validation harness
(`../swarmbly_validation/run_all.py --real`).

## Requirements

- Ollama installed and the server running. Start it with the project's
  variables:

```bash
./run_server.sh
```

- Models: `ollama pull llama3.2:3b qwen2.5:3b gemma2:2b phi3.5:3.8b granite3.1-dense:2b nomic-embed-text`

## Components

| Module | Protocol piece | Notes |
|---|---|---|
| `planner.py` | P9/E20: weak-interface cuts, δ, uniqueness assignment (M2), router with refusal (P2) | coupling = content words shared between adjacent sentences |
| `packer.py` | E2/E6: Γ contract (never trimmed), flanks F, packets, ρ | H counted without models |
| `triage.py` | M3: mechanical per-fragment predicate | expected-item coverage, bounds, schema; RETRY→DISCARD |
| `assemble.py` | P4/E7: flank discounting, select-then-splice, bridge only on a failed seam, cardinality (M2), seam audit (P6) | seam similarity with embeddings (τ_sem) |
| `grader.py` | coverage, keys, constraints, seam-free fraction, tax | baseline floor 0.20 (refusal, §15.7) |
| `benchmark.py` | arms: monolithic / fragmented / fan / fault-injected / k_epist | JSONL records with resume-by-key |
| `benchmarks/corpus.py` | diverse, deterministic tasks with verifiable keys | perfect answers checkable by hand |

## Running it

```bash
python3 benchmarks/run_benchmark.py --pilot     # 1 task × 1 model (fast, exercises everything)
python3 benchmarks/run_benchmark.py --full      # corpus × 5 models + L curve + fault + k_epist (≈1 h)
python3 benchmarks/run_benchmark.py --strong-cut  # anti-P9 cuts (high δ) over the 4 tables (M4/T07R)
python3 benchmarks/run_benchmark.py --sc        # self-consistency baseline k=5 (v0.3, Zhang et al.)
python3 benchmarks/run_benchmark.py --router    # router decisions vs truth (no LLM)
python3 benchmarks/run_benchmark.py --matched   # re-runs frag with matched output budget
```

Resume is automatic: keys already present in the JSONL are not re-executed.

### The output budget

Until 25 September 2026 each fragment received the whole prompt's
`max_out_tokens`, so a plan of `N` fragments had `N` times the output of the
monolithic arm. Since the score rises with length, the measured tax stopped
being interpretable (harness test T11). `--matched` divides that budget among
the fragments and records the cells under the `|matched` suffix, so the two
measurements coexist in the same JSONL. The fields `output_words` and
`length_ratio` are written on every record so that the confound is visible
without re-deriving it from the text.

## Corpus (22 tasks)

| Task | Type | What it exercises |
|---|---|---|
| 16 table tasks (`table_outturn`, `table_bonded`, `portfolio_q1`–`q5`, `bond_municipal`, `bond_corporate`, `inventory_snapshot`–`spares`, `fleet_metrics`, `sales_regions`) | table summary (16 rows as sentences) | global aggregation + coverage; the DERIVED keys (totals) replicate the documented L-curve diagnosis |
| `long_report` | 5-section annual report, 40 sentences | `term_once` with in-plan assignment (M2), canonical entities |
| `fan_qa` | 6 independent questions, 30 sentences | fan topology, mechanical verification |
| `constrained_composition` | 4-paragraph briefing, exactly-once terms, no repeated phrases | the irreducible `no_repeated_ngram` class |
| `extraction_grid` | 8 manifests → JSON | schema verification |
| `longform` | 60-sentence annual review | L curve (L=10/20/40 sweep), solvability axis |
| `chain_refusal` | sequential computation (result dependency) | the router MUST refuse |

## The data

`data/benchmark.jsonl` holds the **341 runs** of the reference campaign, with a
sha256 digest anchored in the harness's `T00` test. It is version-controlled —
unlike `results/`, which is not — because it is not reproducible: model outputs
are non-deterministic, and without this file the claims in Section 15.9 of the
whitepaper cannot be checked. A non-reproducible result that supports a
published claim is a source, not an output.

## Honest design notes

- **H ≠ 39 here**: Γ includes the entity glossary (up to 16 names), so the fixed
  H is ≈100–150 tokens. The T05R accounting measures it and explains it.
- **Determinism**: temperature 0 + fixed `seed` per call.
- **Real heterogeneity**: ~98 tok/s (llama3.2/phi3.5 on GPU) vs ~7 tok/s
  (granite on CPU) — the node heterogeneity the design anticipates.
- **The criterion is currently REFUSED** (harness T09R): the aggregated tax is
  confounded with output length (the fragmented arm writes 1.39× the
  monolithic). Run `--matched` to re-measure with an equalised output budget.
- These results are NOT comparable with the project's v1.4 measurement:
  different corpus, different grader, 2–4B models. They are the first campaign
  of the new instrument, not a re-measurement of the criterion.

