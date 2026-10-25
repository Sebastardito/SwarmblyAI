---
status: current
lang: en
---

# Pre-registration — C1 and C2 of the Swarmbly LCE with real models

**5 October 2026 · written BEFORE any real-model run**

This document fixes the hypotheses, the design, the statistics, the refusal conditions and the death conditions of the first runs of the Swarmbly Local Cognitive Extension with real language models, before a single real answer exists. It refers to the whitepaper version 0.1 (doi:10.5281/zenodo.23150478), Sections 11.1 to 11.5, and it will be published together with its results whatever they are. A hypothesis that dies here is reported as dead.

The decision rules are not only written here: they are code in `lce_validation/decide.py`, committed together with this document, so that they cannot drift once the data are seen. `run_real` records the SHA-256 of this file, of the item set and the git commit in every result.

Spanish version: `PREREGISTRATION_C1_C2_ES.md`.

---

## 1. Declaration of origin: three defects found before measuring

No real-model run of the LCE has been made. While preparing this protocol, reading the harness of version 0.1 against the hypotheses it claims to serve, three defects were found that would have produced uninterpretable results. They were found in the code, not in data, and this document exists partly to record them.

**The homogeneity baseline was identical by construction.** Version 0.1 compared the responses that three users receive with and without task projection, but generated the condition without projection at temperature 0 with the same prompt for every user. With a deterministic decoder the three responses are identical, homogeneity equals 1 by construction, and any projection appears to reduce it. The mock run printed exactly 1.000, and the number was not suspicious enough at the time. The corrected design samples every response at temperature 0.7 with the same per-user seed in every condition, and adds a non-personal placebo.

**The error-agreement metric was biased towards zero and underpowered.** Version 0.1 compared free-text answers to ten factual questions by exact match of their first eight normalised words. Two models that give the same wrong entity in different words count as disagreeing, so the metric cannot detect the shared errors it is meant to measure, and with ten questions there would be almost no jointly wrong pairs. The corrected design uses multiple-choice items, as Kim et al. (2025) do, where the same wrong answer is unambiguous and has a computable chance level, and fixes the number of items from an instrument simulation (Section 7).

**C1 cannot falsify H-C1.** The ten questions of C1 ask for terms that the synthetic user prefers, which no base model can know. A model without memory is expected to score near zero and a model with retrieval near one, whatever the merit of the LCE. C1 is therefore reclassified as a positive control of the pipeline (real-model digestion, anchoring, retrieval), not as a test of H-C1. A failure of C1 indicts the pipeline; a success says nothing about H-C1 at scale.

A fourth, smaller gap is also closed: lexicon adherence (H-C2) was measured only with projection, without a baseline. It is now compared against the same writes without projection.

## 2. What is tested and what is not

| Hypothesis | Part tested here | Status in this run |
|---|---|---|
| H-C1, local memory | retrieval pipeline over a real-model wiki | positive control only |
| H-C2, task projection | preferred terms honoured with Γ vs without | lexicon part; the redundancy rate ρ is **not tested** |
| H-C17 (a), diversity across users | homogeneity of responses across users, with vs without projection | confirmatory |
| H-C17 (b), error correlation unchanged | agreement between families on the same wrong answer, with vs without projection | confirmatory (equivalence) |
| Kim et al. (2025) on small models | errors shared above chance across families | descriptive |
| Canary set (C8) | tail mass and identity violations | descriptive only; the items are unverified |

Nothing here tests adapters (C4, C10), capsules, affinity or the social plane.

## 3. Design

**Models.** `qwen2.5:3b`, `llama3.2:3b` and `gemma2:2b`, served by Ollama on the author's Apple Silicon machine through its OpenAI-compatible endpoint. The first model digests the corpora and writes all open-ended responses; the three act as replicas of different families for the multiple-choice items. Embeddings for homogeneity come from `nomic-embed-text`. The Ollama version and the digest of every model are recorded by `run_real`. These choices are fixed now; changing a model after seeing results is a deviation.

**Materials.** For C1, the fixture corpus of one synthetic user (`lce_validation/fixtures/corpus/`, learning policy `policy.json`) and its ten questions (`questions.json`). For H-C2 and H-C17 (a), three synthetic users (`fixtures/users/u1–u3/`, policy `users_policy.json`) who differ in register and in one preferred term each, and the twenty open-ended topics of `fixtures/open_queries.json`. For H-C17 (b), 1,500 items of the MMLU test split (Hendrycks et al., 2021; MIT licence), drawn uniformly without replacement with seed 20261005 by `python -m lce_validation.fetch_mcq`. The item file is drawn once, after this document is committed and before any model call, and committed with its SHA-256; re-drawing it is a deviation.

**Generation.** Every open-ended response is sampled at temperature 0.7 with a maximum of 160 tokens and seed 1000+u for user slot u, identical across conditions, so that the conditions differ only in the contract. Multiple-choice and C1 answers use temperature 0 (8 and 96 tokens). The three write conditions are the **baseline** (no Γ fields), the **projection** (the user's own Γ: register, preferred lexicon, style seed, as produced by the projector from the wiki digested by the real model) and the **placebo** (one of three generic contracts carrying no personal information: "Write in plain language.", "Use a measured tone.", "Be direct and brief.", each with a neutral register). For the multiple-choice items, the condition with projection rotates the three users' Γ across items.

## 4. Measures and statistics

**C1.** Accuracy with and without retrieval (gold term contained in the answer), and the descriptive digestion statistics (claims, anchor rejection rate, malformed digester outputs).

**H-C2, lexicon.** For every user and topic, the share of the user's preferred terms that appear in the response with projection and in the baseline response; the statistic is the mean difference over the sixty cells, with a 95 % percentile bootstrap interval (10,000 resamples, seed 20261005).

**H-C17 (a).** For every topic and condition, the homogeneity across users is the mean pairwise cosine similarity of the three responses' embeddings. The primary statistic is the mean over topics of baseline minus projection, with a bootstrap interval over the twenty topics. The secondary statistic, which qualifies but does not decide, is placebo minus projection.

**H-C17 (b).** For every pair of families and every item, a jointly wrong item is one both answered with a valid wrong letter. Agreement is the pooled share of jointly wrong pair-items with the same letter. Chance is computed per item from each model's own distribution of wrong letters over that item's three distractors. The primary statistic is the difference in agreement with minus without projection, with a paired bootstrap over items (the same resampled items enter both conditions; 10,000 resamples, seed 20261005). The equivalence margin is ±0.10. It is less than half of the excess over chance reported by Kim et al. (about 0.27, from 60 % against a chance of one third), so a change inside the margin cannot alter the conclusion that errors are shared.

## 5. Decision rules

| Hypothesis | Holds | Falsified | Otherwise |
|---|---|---|---|
| C1 (positive control) | accuracy with memory ≥ 0.70 and gain ≥ 0.50 | — | refused: the pipeline failed, H-C1 not testable |
| H-C2, lexicon | 95 % CI of the difference > 0 | point estimate ≤ 0 | inconclusive |
| H-C17 (a) | 95 % CI of the reduction > 0 | point estimate ≤ 0 | inconclusive |
| H-C17 (b) | 95 % CI of Δ inside [−0.10, +0.10] | CI excludes 0 and \|Δ\| > 0.10 | inconclusive |

H-C17 (a) is always reported with its qualification: if the reduction by projection does not exceed the placebo (CI of placebo minus projection not above 0), the reduction is attributed to per-user variation in the prompt, not to personalisation, and the whitepaper must say so.

## 6. Refusal conditions

The analysis refuses rather than guesses. The whole run is labelled exploratory, and `decide` emits no verdict, if this document or the item file is not committed, if the code tree is dirty, if no embedding model is given, or if fewer than three families respond. C1 is refused if the digested wiki has fewer than five claims, because nothing downstream would be interpretable. H-C17 (b) is refused if either condition has fewer than 200 jointly wrong pair-items, or if more than 10 % of answers in either condition cannot be parsed as a letter.

## 7. Instrument evidence before the run

Following the method of the Swarmbly whitepaper v2, the new measure was tested before use. The `error_agreement` instrument in `lce_validation/instruments.py` simulates three families with correlated difficulty and a tunable probability of choosing a shared wrong option. In simulation, independent wrong answers sit at the computed chance level (about one third) and shared ones above it, and a true increase in sharing from 0.4 to 0.8 is detected in every replicate. The number of items was fixed from the share of replicates in which, with no true change, the bootstrap interval of Δ falls inside ±0.10: 0.30 with 600 items, 0.78 with 1,000, 0.90 with 1,500 and 1.00 with 2,000. The simulation is pessimistic, because it redraws every wrong answer in the second condition, while at temperature 0 an answer changes only if the contract changes it. With 1,500 items an equivalence verdict is attainable and the run takes on the order of one to two hours on a consumer machine; that is the reason for the number. These are simulations and are not evidence about models.

## 8. Run protocol

There is one confirmatory run. If it fails for infrastructure reasons (the server stops, a model cannot be loaded), the partial output is discarded, the failure is recorded in the amendments and the run is repeated unchanged. No run is repeated because of its results, no model or setting is changed after results are seen, and any additional run is labelled exploratory. Raw answers are kept in `results_real.json` and published.

## 9. What this run does not decide

It does not test the LCE with real users: the three users are synthetic and differ in only a few traits. It does not test H-C1 at scale, nor the redundancy rate that H-C2 also names. It does not generalise beyond 2–3B models served locally, nor beyond English multiple-choice items, although the users write in Spanish. And a reduction of homogeneity across synthetic users shows that the mechanism can work, not that it works in a population.

## 10. Amendments

Any change to this document after its first commit is recorded here with a date and a reason. A declared amendment counts; a silent one does not.

**Amendment 1 — 5 October 2026, before any real-model run.** The projection is computed once per request, for each user and topic and for each user and multiple-choice item, instead of once per user over all twenty topics together. The reason is that the privacy lane is classified per request, and a single projection over all topics put every user in the sensitive lane because one topic mentions health. Requests classified sensitive would stay on the client in real use; here they are still written with their Γ, never dropped, and their number is reported (`local_only_writes`, `local_only_items`). No statistic, threshold or decision rule changes.

**Amendment 2 — 5 October 2026, after confirmatory run 1 and before any further run.** Run 1 (commit `f7a8919`, outputs in `results/2026-10-05_C1C2_run1/`) delivered no treatment: the projection was empty for all 60 writes and all 1,500 multiple-choice items (mean size 2 bytes, the empty object). The condition "with Γ" was therefore the baseline. Under the rules of Section 5 the code emitted H-C17 (a) *falsified* and H-C17 (b) *holds*, and refused H-C2; the first two verdicts were produced by construction and say nothing about the hypotheses. The omission is this protocol's: it had no manipulation check. Those verdicts are kept in the record exactly as emitted and are declared uninterpretable. This amendment adds the check to Section 6 and to `decide.py`: the verdicts of H-C2, H-C17 (a) and H-C17 (b) are refused unless the mean projection is at least 20 bytes and at least 80 % of the writes and of the items carry a non-empty Γ. Re-evaluated with it, run 1 refuses all three. The cause will be located with an exploratory diagnosis (`python -m lce_validation.diagnose`), which decides nothing; the delivery fix it supports (anchoring by verbatim quote instead of model-reported offsets, and reading lexicon and register from the user's anchored words) will be fixed in a third amendment, before run 2. Run 2 reuses the same models, items, topics, statistics and thresholds. The data of run 1 for homogeneity and error agreement have been seen; the fix concerns only whether Γ reaches the writer, not the outcome measures.

**Amendment 3 — 5 October 2026, after the exploratory diagnosis and before run 2.** The diagnosis (`results/diagnostics/diagnose_qwen2.5_3b.md`, exploratory, decides nothing) located two causes. First, anchoring by model-reported offsets failed: with `qwen2.5:3b` none of the six claims of the three users and only 4 of the 12 claims of the C1 corpus were anchored, because the offsets cut the spans short; anchoring by verbatim quote, with the offsets computed by code, anchored all 18. Second, typing: the model typed every explicit preference ("Prefiero el término X en lugar de Y") as `user_claim`, a type the projector excludes, so the lexicon never reached Γ even with quote anchoring, which delivered only the register. Run 2 therefore fixes four settings: `--anchor-mode quote`; `--span-projection` (lexicon and register are read from the user's anchored words); `--reconcile-types`, a deterministic rule that changes a proposed `user_claim`, `opinion`, `belief` or `fact` into `preference` when the anchored span of a source the user authored contains a first-person preference cue ("prefiero", "I prefer"), or into `style` when it contains a first-person writing cue ("escribo", "I write"), and never in the opposite direction; and `--preflight`, which stops the run before any outcome is generated if the projection fails the manipulation check of amendment 2. C1 is digested with the same settings. The rule was written after seeing these fixtures and is validated only on them; that is declared as a limitation of run 2. Because Ollama did not reproduce sampling by seed in run 1, the analysis does not assume pairing by seed; the statistics, which pair by topic, are unchanged. Everything else stays as pre-registered: models, the committed item file (sha256 `c8991d3b…`), topics, statistics, thresholds and decision rules. Run 2 is the confirmatory run; run 1 stays published as a failed run.

---

**References**

Hendrycks, D., Burns, C., Basart, S., Zou, A., Mazeika, M., Song, D., & Steinhardt, J. (2021). Measuring massive multitask language understanding. In *International Conference on Learning Representations (ICLR 2021)*. https://arxiv.org/abs/2009.03300

Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. In *Proceedings of ICML 2025*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

*Text under CC BY 4.0; code under AGPL-3.0-or-later.*
