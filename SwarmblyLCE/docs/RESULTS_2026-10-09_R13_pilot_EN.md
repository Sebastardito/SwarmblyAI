---
status: current
lang: en
kind: exploratory
---

# Results — R13 exploratory pilot (the decisive question of H-C1)

**9 October 2026 · pre-registration `PREREGISTRATION_BENCH_R1X_EN.md` with
Amendment 1 · EXPLORATORY PILOT run: no pre-registered verdicts**

> **Notice (11 October 2026).** This pilot is superseded by the R13 confirmatory run (`RESULTS_2026-10-11_R13_confirm_EN.md`, 251 questions). Its figures, including those of Section 7, are kept as the record of the pilot cycle; the current ones are those of the confirmatory run.
>
> **Notice (10 October 2026).** Sections 1 to 6 keep the history of the pilot cycle and contain figures RETRACTED because of review defects E1–E3 (A3 from a single digester, recency sorted in reverse, deleted source digested into the wiki). Do not cite them. The current figures are those of Section 7.

**What the pilot says in one line.** The five-arm pipeline works end to end
and the per-type rubric behaves (abstention on unanswerable ≈ 0.95). The
decisive comparison is NOT yet fair: the arms ran with unequal budgets (A1
913 tokens, A2 206, A3 111) and the wiki lost to raw RAG almost everywhere —
but its per-token efficiency equals RAG's (0.380 vs 0.375 per 100 tokens),
pointing to the wiki's retrieval policy, not its representation, as the
defect to fix.

Models: digesters and responders qwen2.5:3b, llama3.2:3b, gemma2:2b. Raw
outputs in `results/bench_r13/results.json` (SHA in the commit).

## 1. Figures

Accuracy per arm (91 questions × 3 responders; A3/A4 crossed):

| Arm | Accuracy | Mean tokens |
|---|---|---|
| A0 no memory | 0.117 | 47 |
| A1 full document | **0.813** | 913 |
| A2 raw RAG | 0.773 | 206 |
| A3 wiki | 0.454 | 111 |
| A4 wiki + Γ | 0.476 | 138 |

Per question type (A1 / A2 / A3):

| Type | A1 | A2 | A3 | Reading |
|---|---|---|---|---|
| simple | 0.88 | 0.78 | 0.42 | the wiki loses simple facts |
| cross | 0.67 | **0.80** | 0.20 | RAG combines two sources better |
| updated | 0.73 | **1.00** | 0.22 | RAG is perfect on updated facts; the wiki retrieves the old claim |
| contradiction | 0.33 | 0.20 | 0.22 | all low |
| deleted | 0.53 | 0.80 | 0.56 | RAG abstains more than the wiki |
| unanswerable | 0.93 | 0.93 | 0.98 | all abstain well |

Crossed design: A3 diagonal 0.458 vs crossed 0.421 — a foreign digester costs
~4 points; a small effect that needs the confirmatory run to decide the
digester gate.

## 2. Honest reading (what it proves and what it does not)

**What the pilot proves.** The complete pipeline (digestion → anchoring →
wiki → retrieval → five arms → per-type rubric → token accounting) runs
without errors, abstention works, and the between-arm differences are large
and stable.

**What it does NOT prove (identified confounds, all fixable before the
confirmatory run):**

1. **Unequal budgets.** A3 received 111 tokens of context against 206 (A2)
   and 913 (A1). The pre-registration requires the same budget; the pilot
   did not equalise it and the ordering A1 > A2 > A3 correlates with context
   size. The per-token efficiency (A3 0.380 ≈ A2 0.375) suggests the gap
   closes substantially at equal budget.
2. **The wiki's retrieval policy is the defect.** On `updated`, the wiki
   holds TWO claims (old and new) and recency-blind BM25 retrieves the old
   one (0.22 vs 1.00 for RAG). The epistemic layer (maturity, versioning)
   exists but the pilot did not use it at retrieval time. Fix: retrieval
   preferring the most recent claim of the same fact first, then maturity,
   with the budget equalised to RAG's.
3. **A4 (wiki+Γ) worsens factual types** (updated 0.20, contradiction 0.13)
   — consistent with the accuracy cost of Γ measured in run 2; re-measured
   with equal budget and corrected retrieval.

## 3. Consequence for the plan

The pilot does NOT trigger the death condition (it is exploratory and
budget-unequal), but it makes clear that the confirmatory run without the
two fixes would trigger it for the wrong reason. Amendment 2 freezes: (a)
equal context budget for all arms (200 tokens, the pilot's RAG budget); (b)
recency-aware wiki retrieval (most recent claim of the same fact first, then
maturity); (c) a quick re-pilot with the already cached wikis before the
≥250-question confirmatory run.

## 4. Equal-budget re-pilot (Amendment 2)

**Figures.** A1 0.308 (250 tokens; the full document collapses at 200 words
— it only works when it fits entirely), A2 0.773 (206), A3 0.451 (226), A4
0.399 (252). Paired difference **A3 − A2 = −0.322, 95 % CI [−0.392, −0.253]**
(n=273); A4 − A2 = −0.374.

**Per type.** `updated`: A2 1.00 vs A3 0.20 (−0.733) — recency-aware
retrieval did NOT fix it: the update claim contains BOTH values in one text
("was 0.036; the corrected value is 0.041") and the model answers the first.
The defect is claim GRANULARITY (the digester proposed one claim per span
and the span covers two sentences), which violates the atomicity principle
the whitepaper itself requires. `deleted`: A2 0.80 vs A3 0.58 (−0.533) — the
wiki retrieves the related current claim and the model answers instead of
abstaining. `unanswerable`: tie (0.93 vs 0.91). `contradiction`: both at the
floor.

**Reading.** At equal budget the gap did NOT close: raw RAG's advantage is
real on this material (400–700 tokens per user, where the verbatim chunk
wins). The pre-registration's death condition ("RAG ≥ wiki overall AND the
wiki does not win on updates or forgetting") would fire TODAY in this regime
if this were the confirmatory run. Two implementation defects — not design
defects — are identified before judging: (a) claim atomicity (split by
sentence), (b) per-fact retrieval (group claims of the same fact and take
the most recent). The third pending element is the long-corpus subset the
pre-registration already declares: where the full document does NOT fit is
the only place the wiki's compression can pay, and corpus v2 does not
include it yet.

## 5. Verification re-pilot (Amendment 3: atomicity + per-fact + long corpus)

**Figures.** A0 0.085 · A1 0.222 (collapses at 200 words) · A2 0.780 · **A3
0.598** · A4 0.365. Paired **A3 − A2 = −0.183, 95 % CI [−0.241, −0.127]**
(n=378). The gap narrowed from −0.322 to −0.183: the repairs recovered ~14
points.

**Per type.** `updated`: A3 rose from 0.20 to 0.43 and the paired difference
is **−0.143 [−0.310, +0.000]** — atomicity and per-fact retrieval fixed
exactly the defect they targeted (the CI touches zero). `deleted`: still
−0.533 (the wiki retrieves the related current claim and the model answers
instead of abstaining). `cross`: −0.405. `simple`: −0.153. `unanswerable`:
tie.

**Long corpus (v3): A3 − A2 = −0.286 [−0.390, −0.181]** — the premise that
compression pays where the document does not fit did NOT materialise on this
material: BM25 over raw sentences finds the buried facts better than the
atomic claims. The long regime stays open, now against the wiki.

**Verdict of the pilot cycle.** After three declared repair rounds, the wiki
stays behind raw RAG on answer accuracy over this material (−0.183), and the
pre-registration's death condition (RAG ≥ wiki overall; no win on updates or
forgetting) would fire. What the benchmark measures is ONLY accuracy: the
wiki's untouched value is what it did not measure — auditable anchoring,
typing, versioning, the epistemic layer, the safe basis for training (I1)
and for Γ projection. v0.2 must say both things: on pure QA, simple RAG
wins; the wiki is justified by its epistemic layer, not by compression.

## 6. Clean re-pilot (Amendment 4: .md-only sources + exact abstention)

**Figures.** A0 0.079 · A1 0.206 · A2 0.765 · **A3 0.611** · A4 0.378.
Paired **A3 − A2 = −0.153, 95 % CI [−0.209, −0.098]** (n=378).

**Trajectory of the four declared rounds** (A3−A2 per type):

| type | rounds 1-2 | verification | CLEAN |
|---|---|---|---|
| updated | −0.733 | −0.143 | **−0.071 [−0.238, +0.095]** |
| unanswerable | 0.000 | 0.000 | **+0.067** |
| total | −0.322 | −0.183 | **−0.153** |
| deleted | −0.533 | −0.533 | −0.600 |
| v3 long | — | −0.286 | −0.219 |

**Final reading of the cycle.** Each repair converged on its target:
atomicity and per-fact retrieval took `updated` from −0.733 to a statistical
tie with RAG (the CI includes zero), and exact abstention made the wiki
BETTER at abstaining on unanswerable (+0.067). The residue is structural: on
`cross` (−0.381), `deleted` (−0.600) and long material (−0.219), RAG's
verbatim chunk preserves the literal answer that the compressed claim does
not. The death condition holds in direction — RAG ≥ wiki overall; no wiki
win on updates (tie) or forgetting — and the pre-registration's verdict for
v0.2 is: the compression justification dies; the epistemic layer stands,
unmeasured by an accuracy benchmark.

## 7. Current figures (re-measured on 10 October, with E1, E2 and E3 repaired)

Run at commit `ea04c81` (`7363881` in the provenance, before the weights purge: see `COMMIT_MAP_2026-10-10.md`) with a clean tree, verified digests and the 15
wikis digested again without the deleted source. The interpreter was Python
3.9.6, a deviation from R14 (the lock fixes 3.11). Every figure in this
section comes from `results/bench_r13/analysis.json`, which `run_derive`
recomputes from the stored cells; the interval is a bootstrap clustered by
question (10,000 resamples, seed 20261005).

| Arm | Accuracy |
|---|---|
| A0 no memory | 0.079 |
| A1 first 200 words | 0.206 |
| A2 raw RAG | 0.765 |
| A3 wiki (three digesters) | 0.509 (qwen2.5 0.553 · llama3.2 0.323 · gemma2 0.651) |
| A4 wiki + Γ | 0.471 |

**The wiki against RAG.** A3 − A2 = **−0.256 [−0.317, −0.194]** (126
questions). No digester ties with RAG: gemma2 −0.114 [−0.183, −0.045],
qwen2.5 −0.212 [−0.288, −0.138] and llama3.2 −0.442 [−0.529, −0.354]. By
type: `simple` −0.257 [−0.329, −0.186] (83 questions), `cross` −0.508
[−0.603, −0.405] (14), `updated` −0.341 [−0.563, −0.135] (14),
`contradiction` −0.044 [−0.400, +0.267] (5), `deleted` +0.156 [−0.067,
+0.378] (5) and `unanswerable` +0.089 [−0.067, +0.333] (5). Without the
three questions whose key is superseded (N1, Amendment 6 b) the figure
barely changes: −0.260 [−0.323, −0.198] (123 questions).

**Memory against nothing.** On the 116 answerable questions, A3 − A0 =
+0.479 [+0.420, +0.537] and A2 − A0 = +0.767 [+0.704, +0.828]. Local memory
helps a great deal; the wiki helps less than raw RAG.

**The cost of Γ.** A4 against the A3 diagonal of the same digester: gemma2
+0.016, llama3.2 −0.008, qwen2.5 −0.063. It is small and digester-dependent;
A4 is not fully isolated because it shares A3's retrieval.

**Abstention, always together with accuracy (N2).**

| Arm | Answerable accuracy | Abstention `deleted` | Abstention `unanswerable` |
|---|---|---|---|
| A0 | 0.000 | 1.000 | 1.000 |
| A2 | 0.767 | 0.600 | 0.867 |
| A3 qwen2.5 | 0.520 | 0.933 | 0.933 |
| A3 llama3.2 | 0.276 | 0.733 | 1.000 |
| A3 gemma2 | 0.641 | 0.600 | 0.933 |

The arm that knows nothing always abstains, and the gemma2 wiki, the one that
retrieves most, abstains exactly as RAG does on `deleted`. The +0.156 comes
from the wikis that retrieve less. Moreover, no arm ever saw the deleted
source: `deleted` measures abstention in the face of related information,
not forgetting. This section does not claim that the wiki wins on
forgetting; the F-forget test measures that (Amendment 6 c).

**Where the wiki loses.** On answerable questions the key is in RAG's
context in 99.1 % of cases and in the wiki's in 83.6 % (gemma2), 81.0 %
(qwen2.5) and 34.5 % (llama3.2). Given that coverage, the gemma2 wiki
converts almost as RAG does (0.641 out of 0.836 against 0.767 out of 0.991).
The loss is in digestion, which leaves out between 16 % and 65 % of the
answers depending on the digester, not in the representation or in
answering. Coverage needs the cached wikis (not versioned), which is why it
is the only figure in this section that `run_derive` does not recompute.

**Note on Amendment 4.** Its text says that exact abstention was applied to the wiki arms; in the code the prompt change was applied to every arm, and every arm was re-run with it. The figures in this section are therefore comparable across arms.

**Reading.** On question-answering accuracy over this material, raw RAG
beats the wiki and the wiki does not win on updates: the direction of the
death condition holds, as a pilot and without a pre-registered verdict. The
measured cause is digestion coverage, which depends strongly on the
digester. What justifies the wiki (anchoring, versioning, verifiable
forgetting, a safe basis for Γ and for training) is not measured by an
accuracy benchmark. The confirmatory run needs at least 250 questions, at
least 30 per type, the LongMemEval subset, the corpus without the three
superseded keys and the real forgetting test.

*Text CC BY 4.0.*
