---
status: current
lang: en
---

# Results — confirmatory run 2 of C1 and C2 (LCE)

**5 October 2026 · pre-registration `PREREGISTRATION_C1_C2_EN.md` with amendments 1–3 (sha256 `508ba8f9…`) · commit `99a1d52`**

**The three C2 hypotheses that could be decided hold, with qualifications that matter.** Task projection makes texts honour the user's preferred terms (H-C2, lexicon part) and reduces homogeneity across users beyond a non-personal placebo (H-C17 a). Error agreement across families stays within the ±0.10 equivalence margin (H-C17 b), but it is not unchanged: it rises by 0.039 with an interval that excludes zero. C1, the positive control, passes comfortably. The redundancy rate ρ, the other half of H-C2, was not tested.

The run was made after seeing run 1, which failed because the projection came out empty, and after an exploratory diagnosis that led to amendment 3. That order is declared here and in the pre-registration, and it limits what this run can claim (Section 5).

Models: `qwen2.5:3b` (digests and writes), `llama3.2:3b` and `gemma2:2b`, on Ollama 0.35.1; embeddings `nomic-embed-text`; the author's Apple Silicon machine. Settings of amendment 3: anchoring by verbatim quote, lexicon and register read from the anchored span, type reconciliation and preflight. Unmodified outputs in `results/2026-10-05_C1C2_run2/` (`results_real.json` sha256 `4c6d0b2f…`).

---

## 1. The treatment arrived

The manipulation check passed. The projection averaged 97 bytes and was non-empty in 100 % of the 60 writes and of the 1,500 items. All 60 carried the user's preferred lexicon; 32 also carried the register, and none carried a style seed, because the projector assigns the style claim to the register before considering it as a seed. Digestion anchored all 12 claims of the C1 corpus (rejection rate 0.00, against 0.67 in run 1), and the reconciliation rule changed the type of 2 of them. Three writes and 67 items fell in the sensitive lane, which in real use would not leave the client; they were written anyway and count in every figure.

## 2. Verdicts

| Hypothesis | Verdict | Estimate | 95 % CI |
|---|---|---|---|
| C1 (positive control) | holds | accuracy 0.80 with memory vs 0.00 without | — |
| H-C2, lexicon | holds | adherence 0.667 with Γ vs 0.033 without; difference 0.633 | [0.500, 0.750] |
| H-C2, ρ | not tested | needs the Swarmbly dispatch path | — |
| H-C17 (a) | holds | homogeneity 0.879 → 0.806; reduction 0.073 | [0.052, 0.096] |
| H-C17 (a), qualification | exceeds the placebo | projection vs placebo: 0.048 | [0.023, 0.070] |
| H-C17 (b) | holds (equivalence) | agreement 0.563 → 0.602; Δ = 0.039 | [0.009, 0.069] |

## 3. Reading

**Lexicon.** With projection, the preferred terms appear in two texts out of three; without it, almost never (two texts out of sixty). Adherence varies by user: 0.95 for "evolución cultural", 0.65 for "inferencia descentralizada" and 0.40 for "modelo pequeño", which the writing model tends to replace. The test measures that a 3B model honours a Γ field that names the term explicitly; it does not measure implicit preferences.

**Homogeneity.** The reduction by projection appears in all 20 topics and is almost three times that of the placebo (0.025), which repeats its run-1 value. Projection exceeds the placebo by 0.048, so the reduction is not explained by varying the prompt from user to user alone. One limit should be stated: the placebo matched the form of the contract, not the amount of instruction, and the projection carries a concrete term that changes the vocabulary of the text. Whether the difference comes from personal information rather than from more specific instructions is not separated by this design.

**Shared errors.** With Γ the three models are wrong on more items (accuracy from 0.606 to 0.597 for qwen2.5, from 0.579 to 0.545 for llama3.2 and from 0.535 to 0.519 for gemma2), and Γ changes the answer in 664 of 4,500 cases. Agreement when both are wrong rises from 0.563 to 0.602. The pre-registered verdict is equivalence, because the whole interval lies inside ±0.10, but the interval excludes zero: Γ does not leave error correlation intact, it raises it slightly. A non-pre-registered analysis suggests where this comes from: the computed chance level also rises, from 0.354 to 0.396, because with Γ the wrong answers concentrate on fewer letters, and the excess over chance stays practically the same (0.206 with Γ against 0.209 without). The cautious reading is that a contract shared by every replica homogenises their answers a little, wrong ones included, without changing the structure of shared errors that comes from pretraining. It is consistent with Sections 2.6 and 6.4 of the whitepaper, and it adds something they did not say: projection has a small accuracy cost on factual tasks.

**Reproducibility.** The 4,500 answers without projection are identical, letter by letter, to those of run 1, and the homogeneity baseline and placebo repeat their values (0.879 against 0.880; 0.854 against 0.853). The cross-family shared errors without projection, already measured in run 1, reproduce exactly: an excess of 0.209 (95 % CI [0.178, 0.241]) over chance.

## 4. What does not change from run 1

C1 remains a positive control and not a test of H-C1. The canary set, unverified, again gives a tail mass of 0.00 and is descriptive only.

## 5. Limits of this run

It is the second confirmatory run and was made after seeing the first. The settings of amendment 3 correct whether Γ reaches the writer, not the outcome measures, but the type-reconciliation rule was written while looking at these fixtures and is validated only on them. There are three users, synthetic, differing in one term and one register. The models are 2–3B and local; the multiple-choice items are in English while the users write in Spanish. Seeds did not reproduce sampling in Ollama, so the write conditions are independent samples paired only by topic. And a reduction of homogeneity across three synthetic users shows that the mechanism can work, not that it works in a population.

## 6. What comes next

For version 0.2 of the whitepaper: report H-C2 (lexicon) and H-C17 as holding with these qualifications, add the accuracy cost of Γ and the small rise in error agreement as findings, and incorporate the project's own measurement of errors shared across families. For a stronger test: real users, or at least more numerous and varied ones, a placebo matched in amount of instruction, and the rate ρ within the Swarmbly dispatch path.

---

*Text under CC BY 4.0.*
