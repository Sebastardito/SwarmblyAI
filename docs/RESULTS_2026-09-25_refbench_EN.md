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
| T08R2 | §5 | ◌ refused | L curve on the admitted corpus: assembler coverage **54.9 %**; on the computable ones **+18.9** [**+1.4**, **+37.5**] in favour of the fragmented arm |
| T08R3 | §5 | ✔ | L curve v3: **+46.9** [**+33.3**, **+59.4**] against the monolithic arm; mixes splitting with aggregating by code |
| T08R4 | §5 | ▣ pending | N=1 control — `run_lcurve_v3.py --full-control` |
| T09R | — | ◌ refused | **+11.17 %** 95 % CI [**+4.80**, **+17.34**] over **95** cells, confounded with output length |
| T10R | M1 | ▣ blocked | no non-saturated regime in this corpus |
| T0RR | P2 | ✘ | AUC **0.57** with δ and reputation; **0.61** with neither |
| T0RR2 | P2 | ✘ | AUC **0.57** with capability probes |
| T0LR | §5.7 | ✔ | `L*` varies by family; mean gain over a common `L`: **+0.360** |
| T13 | — | ◌ refused | truncated tax flips sign with the reading budget T (**−15.66 %** at T=40, **+7.69 %** at T=120): the length coupling is structural |
| T13b | SWIP-0001 | ◌ refused | position tax corrected for omissions: displacement **+0.0036**, 95 % CI **[−0.0948, +0.0994]**, corpus halves disagree in sign — criterion remains **unmeasured** |

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

The abandonment criterion **has not been measured** — and the cleanest
measurement is a cost. The aggregate tax is confounded with output length in
**both directions** (full budget: the fragmented arm writes 1.39× the
monolithic and scores more; divided budget: 0.43× and scores less; T09R
refuses). Truncating both arms to a fixed reading budget **T** fails too: the
tax flips sign with T (T13). The position of first mention (T13b, SWIP-0001),
corrected so an omitted key is charged at the end of the text, also refuses:
displacement **+0.0036** of the arm's own length, 95 % CI
**[−0.0948, +0.0994]** — a null, ~5× wider than the threshold — and the corpus
halves disagree in sign (the worst-case imputation also re-couples the metric to length: ρ = **−0.452**; of 423 keys, the fragmented arm omits **217** against the monolithic's **82**). What survives is economic: under the equalised
budget, fragmenting **costs in all five families** (over the 95 criterion cells, T09R: means **+6.2 %** to
**+22.1 %**, medians **+4.3 %** to **+29.4 %**; aggregate **+11.17 %**, 95 % CI
**[+4.80, +17.34]**), and the measured per-class policy is **not to fragment**
(**+0.0 %** against **+14.8 %**).

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

The first fragmented run over the declared cells was **withdrawn**: each
fragment copied its rows verbatim, the concatenation reconstructed the
original document, and the 48 cells coincided with their monolithic
counterpart one for one (48/48) — it measured nothing about fragmentation, and
L was confounded with document size. The redesigned run (each fragment
*answers* per-row values and its own partial sum; the assembler combines
deterministically, `run_lcurve_v2.py`) has an assembler that computes only 3 of
the 6 global question forms (79 of 144 globals, 54.9 %); the rest are scored as
failures by construction. Against the monolithic arm on the same document
(T08R2):

| L | computable | fragmented (computable) | monolithic (computable) | fragmented (all) | monolithic (all) |
|---|---|---|---|---|---|
| 5 | 23/36 | 100.0 % | 73.9 % | 63.9 % | 77.8 % |
| 10 | 20/36 | 100.0 % | 75.0 % | 55.6 % | 69.4 % |
| 20 | 19/36 | 73.7 % | 63.2 % | 38.9 % | 58.3 % |
| 40 | 17/36 | 52.9 % | 47.1 % | 25.0 % | 44.4 % |

On the computable questions the fragmented arm beats the monolithic arm at
every L (**+18.9** points, 95 % CI **[+1.4, +37.5]**; exact aggregation by code
on one side, the model's own arithmetic on the other; 79 questions, one
family). Over all globals the figure (−16.7) measures the assembler's coverage,
and the verdict refuses. The slope in L and value fidelity are not measured.
`run_lcurve_v3.py` corrects all three.

**v3 run** (T08R3; six forms, L = 5–40 on the same 8 documents, monolithic arm
re-run and identical to the admission run):

| L | fragmented | monolithic | extraction fidelity |
|---|---|---|---|
| 5 | 24/24 = 100.0 % | 12/24 = 50.0 % | 960/960 |
| 10 | 24/24 = 100.0 % | 12/24 = 50.0 % | 958/960 |
| 20 | 24/24 = 100.0 % | 12/24 = 50.0 % | 960/960 |
| 40 | 21/24 = 87.5 % | 12/24 = 50.0 % | 923/960 |

Paired difference **+46.9** points, 95 % CI **[+33.3, +59.4]**; within-document
slope flat up to L=20 with a drop at L=40. The fragments sum their block
correctly 1 time in 360. The figure mixes two effects — splitting and
aggregating with code —; the N=1 control (`--full-control`, T08R4) separates
them, and until then it is not attributed to fragmentation.

## 5. Related documents

- `WHITEPAPER_V2_EN.md` §15.9 — the reasoned analysis and its design consequences.
- `PREREGISTRATION_2026-09-25_interaction_EN.md` and
  `RESULTS_2026-09-25_interaction_EN.md` — the hypothesis withdrawn during this
  campaign, and the pre-registration that made that possible.
- `VALIDATION_STRATEGY_V2_EN.md` §11 — what happens to the agenda once executed.

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Spanish companion:
`RESULTS_2026-09-25_refbench_ES.md`.*