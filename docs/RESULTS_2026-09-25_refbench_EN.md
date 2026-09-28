---
status: current
lang: en
---

# Results — the reference campaign: 341 runs over five families

**25 September 2026**

This document is the record of the first campaign that subjects the five models
M1–M5 to measurement on real models. The reasoned analysis is in §15.9 of
`WHITEPAPER_V2_EN.md`; what follows is the instrument, the provenance of the
data, the table of verdicts, and what each one does and does not license.

## 1. What was run

| | |
|---|---|
| Reference implementation | `swarmbly_ref/` — router, planner, packing, triage, assembly, grading |
| Falsification harness | `swarmbly_validation/` — Python 3 stdlib, zero dependencies |
| Node families | `llama3.2:3b`, `qwen2.5:3b`, `gemma2:2b`, `phi3.5:3.8b`, `granite3.1-dense:2b` |
| Task corpus | 22 deterministic tasks with verifiable keys |
| Record | `swarmbly_ref/data/benchmark.jsonl` — **341** runs |
| Digest | sha256 `d94bb9cc7694d0f7…`, anchored in `T00` |

Full reproduction:

```bash
python3 swarmbly_validation/run_all.py --all
```

The harness returns a non-zero exit code if any test fails, and it **refuses** —
rather than issuing a verdict — when the data do not support the question. The
corpus digest is checked before use: if it changes, `T00` fails and the rest
never runs.

## 2. Verdicts

| Test | Model | Verdict | Deciding figure |
|---|---|---|---|
| T0R | P2 | ✔ | router against corpus truth: **22/22** |
| T02R | M3 | ✔ | the **3** contaminated packets are rejected; the 42/60 incident does not reproduce |
| T03R | M2 | ✔ corrected | **6/35** exactly once by node obedience; **35/35** after mechanical enforcement; **0** omissions |
| T04R | M4 | ✘ | Spearman(δ, tax) = **−0.13** over **127** intra-category cells |
| T05R | — | ✔ | packet accounting to within **7.5 %**; ρ falls from **2.61** to **1.33** as `L` goes from 10 to 40 |
| T06R | — | ✔ | grader **21/21** on the perfect answer; **100** of **105** monolithic runs above the floor |
| T07R | M4 | ✘ | δ rises in **32/32** pairs at equal ρ; the tax worsens in only **19/32** |
| T08R | — | ✘ | `L` band: factor **1.0** on `table_outturn`, **2.7** on `longform`; the predicted wide band does not appear |
| T09R | — | ◌ refused | **−18.32 %** 95 % CI [**−31.00**, **−6.95**] over **130** cells, confounded with output length |
| T10R | M1 | ▣ blocked | no non-saturated regime in this corpus |
| T0RR | P2 | ✘ | AUC **0.38** with δ and reputation; **0.43** with neither |
| T0RR2 | P2 | ✘ | AUC **0.47** with capability probes |
| T0LR | §5.7 | ✔ | `L*` varies by family; mean gain over a common `L`: **+0.015** |

## 3. What each verdict licenses

**M4 — falsified.** T07R is the test the strategy declared decisive in advance:
the same prompt, the same `L`, two cuts of different quality. ρ stays equal and
only δ moves. The prediction is that the strong cut worsens distortion in every
pair; it worsens in 19 of 32. T04R converges from an independent observational
measurement. δ is kept as a descriptive quantity of the plan and withdrawn as an
explanatory axis.

**M2 — survives corrected.** Real nodes do not obey `unique_here`: 6 of 35 terms
appear exactly once. But there are no omissions, and the assembler's mechanical
enforcement takes the result to 35/35. Assignment in the plan removes the
irreparable failure mode; the reparable one is removed by the assembler. "Zero
by construction" is withdrawn as a general statement.

**M3 — survives.** The mechanical predicate rejects packets carrying another
packet's answer.

**M1 — no instrument.** The aligner with semantic substitution is built and
verified on the bench (T10): it distinguishes `noon~midday` from
`noon~midnight`, which the identity aligner does not. The real corpus did not
produce the genuine-disagreement regime M1 needs, so the verdict is *blocked*
and not *falsified*.

**The per-cell router — refuted.** No subset of features beats chance. What
separates is the node class:

| node class | n | mean tax | median | within-class sd | expensive fraction |
|---|---|---|---|---|---|
| `granite3.1-dense:2b` | 16 | −41.9 % | −32.5 % | 44.1 | 19 % |
| `gemma2:2b` | 16 | −10.1 % | −9.4 % | 35.4 | 38 % |
| `qwen2.5:3b` | 16 | −7.8 % | −8.8 % | 47.4 | 38 % |
| `phi3.5:3.8b` | 16 | −0.4 % | −2.1 % | 22.9 | 38 % |
| `llama3.2:3b` | 16 | +7.6 % | +13.0 % | 31.3 | 56 % |

The distance between classes is large and the variance within a class is larger.
That explains at once why per-cell prediction fails and why a per-class policy
works: **−10.1 %** against **−10.5 %** for always fragmenting, without needing
the prediction that does not exist.

## 4. What cannot be claimed, and why

The abandonment criterion **has not been measured**. The fragmented arm received
more output budget than the monolithic one — each fragment inherited the whole
prompt's `max_out_tokens` — and within a single task writing more scores more.
The harness refuses to issue a verdict on that aggregate.

The cause is located in the code and corrected. The run that settles the matter
is a single command:

```bash
python3 swarmbly_ref/benchmarks/run_benchmark.py --matched
```

The fields `output_words` and `length_ratio` are now first-class fields of the
record, so that the confound is visible to any future analysis without having to
re-derive it from the text.

## 5. Related documents

- `WHITEPAPER_V2_EN.md` §15.9 — the reasoned analysis and its design consequences.
- `PREREGISTRATION_2026-09-25_interaction_EN.md` and
  `RESULTS_2026-09-25_interaction_EN.md` — the hypothesis withdrawn during this
  campaign, and the pre-registration that made that possible.
- `VALIDATION_STRATEGY_V2_EN.md` §11 — what happens to the agenda once executed.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Spanish companion:
`RESULTS_2026-09-25_refbench_ES.md`.*
