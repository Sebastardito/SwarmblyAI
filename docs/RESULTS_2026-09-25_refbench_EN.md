---
status: current
lang: en
---

# Results — the reference campaign: 473 runs over five families

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
| Record | `swarmbly_ref/data/benchmark.jsonl` — **473** runs |
| Digest | sha256 `dcd1931d98f7f0ec…`, anchored in `T00` |

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
| T03R | M2 | ✔ corrected | **23/35** exactly once by node obedience; **35/35** after mechanical enforcement; **0** omissions |
| T04R | M4 | ✘ | Spearman(δ, tax) = **−0.15** over **127** intra-category cells |
| T05R | — | ✔ | packet accounting to within **7.5 %**; ρ falls from **2.61** to **1.33** as `L` goes from 10 to 40 |
| T06R | — | ✔ | grader **21/21** on the perfect answer; **100** of **105** monolithic runs above the floor |
| T07R | M4 | ✘ | δ rises in **32/32** pairs at equal ρ; the tax worsens in only **15/32** |
| T08R | — | ✘ | `L` band: factor **1.0** on `table_outturn`, **2.7** on `longform`; the predicted wide band does not appear |
| T09R | — | ◌ refused | **+11.17 %** 95 % CI [**+4.80**, **+17.34**] over **95** cells, confounded with output length |
| T10R | M1 | ▣ blocked | no non-saturated regime in this corpus |
| T0RR | P2 | ✘ | AUC **0.57** with δ and reputation; **0.61** with neither |
| T0RR2 | P2 | ✘ | AUC **0.57** with capability probes |
| T0LR | §5.7 | ✔ | `L*` varies by family; mean gain over a common `L`: **+0.360** |
| T13 | — | ◌ refused | truncated tax flips sign with the reading budget T (**−15.66 %** at T=40, **+7.69 %** at T=120): the length coupling is structural |
| T13b | SWIP-0001 | ✔ | position tax: keys surface **−0.279** of the arm's own length earlier, 95 % CI **[−0.361, −0.178]**, confound ρ = **+0.075** — criterion restated and **met** |

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
| `granite3.1-dense:2b` | 16 | +8.4 % | +15.5 % | 38.8 | 56 % |
| `gemma2:2b` | 16 | +11.5 % | +15.7 % | 17.5 | 75 % |
| `qwen2.5:3b` | 16 | +13.4 % | +13.1 % | 37.3 | 56 % |
| `llama3.2:3b` | 16 | +14.3 % | +22.9 % | 38.3 | 75 % |
| `phi3.5:3.8b` | 16 | +26.5 % | +30.4 % | 16.1 | 88 % |

The distance between classes is large and the variance within a class is larger.
That explains at once why per-cell prediction fails and why a per-class policy
works: **+0.0 %** against **+14.8 %** for always fragmenting, without needing
the prediction that does not exist.

## 4. What cannot be claimed, and why

The abandonment criterion **was unmeasured, and is now judgeable** — via a
new instrument, not a new budget setting. The aggregate tax is confounded with
output length in **both directions** (full budget: the fragmented arm writes
1.39× the monolithic and scores more; divided budget: 0.43× and scores less;
aggregate **+11.17 %**, 95 % CI **[+4.80, +17.34]**, T09R — refused and not
cited as the criterion). Truncating both arms to a fixed reading budget **T**
fails too: the tax flips sign with T (T13). What resolves the coupling **by
construction** is the **position of first mention** (T13b, SWIP-0001): each
key's first occurrence, normalised by the arm's own length. On the
matched-budget cells the fragmented arm surfaces the keys **0.279 of its own
length earlier**, 95 % CI **[0.178, 0.361]**, with the confound gone
(ρ = **+0.075**). The criterion, restated as "fragmentation must not bury the
keys", is **met**.

The cause is located in the code and corrected. The run that settles the matter
is a single command:

```bash
python3 swarmbly_ref/benchmarks/run_benchmark.py --matched
```

The fields `output_words` and `length_ratio` are now first-class fields of the
record, so that the confound is visible to any future analysis without having to
re-derive it from the text.

## 4b. The L-curve corpus is admitted

The candidate corpus `prompts/lcurve_v2.json` (k-ary global questions, arity
≤3, generated by `make_corpus.py`) passed its admission gate: all mechanical
checks and the monolithic floor. On the dev half (24 documents), the
monolithic arm clears the **0.50** floor with **llama3.2:3b at 61.1 %**
(44/72 global questions; chance baseline **0.182**). The other four families
do not clear it (19.4–30.6 %), so the L-curve campaign must run with llama3.2
or be reported per family. The auditable run is `data/admission.json`.

## 5. Related documents

- `WHITEPAPER_V2_EN.md` §15.9 — the reasoned analysis and its design consequences.
- `PREREGISTRATION_2026-09-25_interaction_EN.md` and
  `RESULTS_2026-09-25_interaction_EN.md` — the hypothesis withdrawn during this
  campaign, and the pre-registration that made that possible.
- `VALIDATION_STRATEGY_V2_EN.md` §11 — what happens to the agenda once executed.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Spanish companion:
`RESULTS_2026-09-25_refbench_ES.md`.*