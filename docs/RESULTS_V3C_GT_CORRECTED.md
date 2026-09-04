# V3c against ground truth — the confidence map fails, and this run says why

**Run:** `results/v3c-gt-20260903-201624`. 15 prompts × 150 items,
`prompts/ground_truth.json`, ρ = 2.5, N = 4, k ∈ {1, 3, 5}, five distinct model
families. Graded mechanically against an answer key by `swarmbly_v0.grading` —
**no model in the verdict**. 60 rows.

> **Provenance.** `harness_validation_only: false`, `embeddings_degraded: false`,
> τ_sem 0.765 fitted on 180 pairs, seed 0, code fingerprint `4abed34a…`.
> **`rows_excluded_below_floor: 0`** and ρ achieved 2.49–2.51 against a target of
> 2.50. `n_families_mean` 3.0 at k=3 and 5.0 at k=5 — the k=5 arm really did run
> five distinct lineages, which the contaminated run of 24 August did not.

**This is the first time this experiment has been run above its own packing
floor.** Every previous v3c tier swept ρ = 1.5 against floors of 1.51–2.37, so
every fragmented cell collapsed to a bare task: those runs measured agreement
between replicas answering *context-free* micro-tasks. Their odds ratios of 3.47,
0.26 and 1.24 describe a configuration nobody chose.

---

## 1. The verdict

| statistic | value | reading |
|---|---|---|
| **AUC, pooled** | **0.507** | 0.500 is chance |
| **Flagging lift** at 10 / 20 / 30 % flag rate | **1.12 / 1.21 / 0.99** | 1.0 is random |
| Pearson *r* | +0.117 | see §3 — it rests on three items |
| items in the calibration | 181 (127 right, 54 wrong) | |

The tier's own instructions, written before the run: *"lift near 1.0 means the
flag is no better than random, and that result retires the confidence map."*

Flagging the lowest-agreement 30 % of items catches 29.6 % of the errors. That is
what flagging 30 % of items at random does.

**Per category, the AUCs scatter on both sides of chance and cancel:**

| category | n | accuracy | AUC |
|---|---|---|---|
| unit_conversion | 51 | 0.941 | 0.812 |
| arithmetic | 22 | 0.455 | 0.583 |
| date_arithmetic | 51 | 0.353 | 0.530 |
| **threshold_decision** | 40 | 0.850 | **0.382** |
| field_extraction | 17 | 1.000 | — (no errors) |

`threshold_decision` is **below** chance: there, higher agreement predicts a
*wrong* answer. Categories landing on both sides of 0.5 and pooling to 0.507 is
the signature of no signal, not of a weak one.

**And adding families does not help.** k=3 gives AUC 0.483, k=5 gives 0.527. Two
more independent lineages bought nothing.

## 2. Why — and this is the part the earlier runs could not reach

The earlier verdict was "agreement does not predict correctness". This run shows
the mechanism, and it is worse than a weak relationship.

**Mean agreement is 0.966. One hundred and seventy-three of 181 items sit in the
top bin.**

| agreement bin | items | accuracy |
|---|---|---|
| 0.0 – 0.2 | 0 | — |
| 0.2 – 0.4 | 2 | 0.000 |
| 0.4 – 0.6 | 1 | 0.000 |
| 0.6 – 0.8 | 5 | 0.800 |
| **0.8 – 1.0** | **173** | **0.711** |

Five model families — five organisations, five pretraining lineages, chosen for
diversity precisely so they could disagree — **agree with each other almost
always. And where they agree nearly perfectly, they are wrong 29 % of the time.**

The confidence map does not fail because the correlation is weak. It fails
because **the predictor has almost no variance to offer**, and what variance it
has does not track error. A signal cannot be extracted from a constant.

This is the failure mode the project's own design notes named and then assumed
away: *models sharing training data share errors, so they agree confidently on
the same mistake*. It has now been measured directly. Independent families are
not independent estimators on this workload.

**That is a finding about model ecology, not about Swarmbly**, and it is the more
useful half of this run. It bounds any architecture — not only this one — that
proposes to derive reliability from cross-model agreement at this scale.

## 3. Why the Pearson *r* is not evidence

`pearson_r = +0.117` is positive and points the "right" way. It should not be
quoted. It rests on the 0.2–0.6 range, which holds **three items** in total, all
of them wrong. Remove those three and the predictor is a constant.

Read AUC before *r* — which is what the tier's instructions say, and why they say
it. AUC 0.507 is the honest summary.

## 4. A separate problem this run exposes: format compliance

The denominators, which the tier's instructions say to read before anything else:

| | |
|---|---|
| units produced | 719 |
| **units with no parsable item label** | **323 (45 %)** |
| items seen | 387 |
| items graded | 308 |
| items unintelligible | 79 (20 % of items seen) |
| items echoed | 50 |
| reaching the calibration | **181** |

**Three quarters of the dispatched work does not reach the calibration.** Nearly
half of all units emitted nothing a parser could label, and a fifth of the items
that were labelled were unintelligible.

This is a real defect and it is not the confidence map's. At N = 4 on 2–3B
models, format compliance is poor enough that most of the run is thrown away
before any question is asked. Two consequences:

- **It weakens nothing in §1–2, and arguably strengthens them.** The surviving
  181 items are the subset where the models *did* behave. Even there, agreement
  is uninformative. If attrition selected for easier items — the likely
  direction — then this is the friendliest possible sample for the confidence
  map, and it still fails.
- **It is the next thing worth fixing.** A protocol that discards 75 % of
  dispatched work to format failure has a cost that no coherence metric measures.
  It belongs in the packet contract, not in the analysis.

## 5. What this settles

The confidence map has now been measured **five times**: once against a saturated
judge (r = −0.030, uninterpretable), three times against an answer key on
below-floor runs (common odds ratios 3.47, 0.26, 1.24 — above, below and astride
1), and once here, above the floor, with five genuine families and a mechanical
verdict.

**AUC 0.507. Flagging lift 1.0. It is retired.**

The mechanism stays in the protocol: replicas are still dispatched, agreement is
still computed and reported, and a low-agreement region is still a place a reader
might look. What is withdrawn is the *claim* — that the agreement score carries
information about whether the answer is right. It does not, and now there is an
explanation rather than only a null.

**What must not be said:** that this is a weak or preliminary result. It is the
cleanest run this question has had, and it is unambiguous. The honest cost of the
consensus mechanism should be stated alongside it: k = 5 costs a large share of
output quality against a signal that does not exist.
