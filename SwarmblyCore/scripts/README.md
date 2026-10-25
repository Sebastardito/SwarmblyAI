# scripts/

## `run_ollama.sh` — V0 and V3c against three local model families

The two measurements this project's viability rests on, run against real models
on your own machine. Nothing here talks to a hosted API and nothing leaves the
laptop.

```bash
./scripts/run_ollama.sh smoke     # ~5 min    does the wiring hold?
./scripts/run_ollama.sh v0        # ~2-4 h    the coherence-tax curve (H1)
./scripts/run_ollama.sh v3c       # ~2-3 h    agreement vs judged quality (V3c)
./scripts/run_ollama.sh all       # ~5-7 h    both, sequentially
```

**Run `smoke` first.** It exercises every code path the long runs use — model
pulls, transport, family dispatch, embeddings, consensus, the report — on two
prompts. If it finishes clean, the multi-hour run will not fail on wiring.

### What you need

[Ollama](https://ollama.com/download), Python 3.10+, and roughly 8 GB of disk
for four models. The script pulls whatever is missing on first run:

| Model | Family | Role |
|---|---|---|
| `llama3.2:3b` | llama | worker + orchestrator |
| `qwen2.5:3b` | qwen | worker |
| `gemma2:2b` | gemma | worker |
| `nomic-embed-text` | — | embeddings for τ calibration and unit alignment |

Substitute your own with
`SWARMBLY_MODELS="fam:model,fam:model,fam:model" ./scripts/run_ollama.sh v3c`.

**Three distinct families is a hard requirement, not a preference.** The script
refuses to start with fewer. Agreement between replicas is evidence only to the
extent the replicas could have disagreed; models sharing training data share
errors and will agree confidently on the same mistake. Three replicas of one
family measure that family's sampling variance and nothing else, and a V3c run
built that way would produce a high agreement score that means nothing at all.

### What each tier measures

**`v0` — the coherence tax.** Quality lost to fragmentation and reassembly as a
function of ρ, the contextual redundancy ratio. This is hypothesis H1 and the
project's make-or-break number. The go/no-go criterion was fixed before any
data existed: if the tax does not fall below 5% in at least one task category at
some ρ, the architecture is not fit for generative work and must be redirected.
The criterion is in the whitepaper, not in this script, precisely so that it
cannot be adjusted after seeing the result.

**`v3c` — does agreement predict quality?** Sweeps *k* ∈ {1, 3, 5} complete
replicas per micro-task, one per family, aligned at semantic-unit granularity.
The number that matters is the correlation between the per-unit agreement score
and judged acceptability. **If it is flat, the confidence map of Section 8.4b is
decoration, and the paper has to say so.** This is the experiment most likely to
falsify a claim the project currently makes, which is why it is worth running
before publication rather than after.

### Reading the output

Everything lands in `results/<tier>-<timestamp>/`: `results.csv`, the per-unit
sidecar, `summary.json`, `run_metadata.json`, `run.log` and a self-contained
`report.html`. Nothing is overwritten between runs.

Before quoting any number, open `run_metadata.json` and check three fields:

| Field | Required value | Why |
|---|---|---|
| `harness_validation_only` | `false` | `true` means the mock backend ran. The mock injects the failure modes under study; its curve says something about the harness and nothing about language models. |
| `embeddings_degraded` | `false` | `true` means the embedding route failed and hashed vectors were substituted. τ_sem, seam detection and unit alignment are then mechanically valid and semantically meaningless. The report prints a banner when this happens. |
| `n_families_mean` (in the k>1 rows of `summary.json`) | `3` | Below 3, the agreement score is not measuring disagreement between independent estimators. |

### Honest limits of these runs

The prompt corpus is 8 prompts across 8 categories. It is a smoke-test corpus,
not a benchmark, and a result on it is a signal to investigate rather than a
finding to publish as a headline. The judge is the same class of model doing the
work, which is a known weakness and is why `judge_score` is reported alongside
the mechanical metrics rather than instead of them. Three 2–3B models are the
low end of the capability range the protocol targets; a negative result here
bounds the architecture at that scale and does not settle it at 8B.

None of these caveats is a reason not to run it. They are the reasons to record
what the run actually was, which is what `run_metadata.json` is for.

---

## `build_pdfs.sh` — rebuild the PDF set from Markdown

```bash
./scripts/build_pdfs.sh docs/WHITEPAPER_EN.md docs/ONEPAGER_ES.md    # selected files
./scripts/build_pdfs.sh $(ls docs/*.pdf | sed 's/\.pdf$/.md/')        # the whole set
```

Requires `pandoc` and `wkhtmltopdf`. One stylesheet is applied to every document
so the set stays visually consistent; rebuild the *whole* set rather than a
single file if you change the stylesheet, otherwise the PDFs drift apart in
pagination and type size. Output lands beside each source as `<name>.pdf`.
