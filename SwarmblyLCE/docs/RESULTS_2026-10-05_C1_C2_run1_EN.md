---
status: current
lang: en
---

# Results — confirmatory run 1 of C1 and C2 (LCE)

**5 October 2026 · pre-registration `PREREGISTRATION_C1_C2_EN.md` (sha256 `f60937a5…`) · commit `f7a8919`**

**Verdict of the run: the manipulation failed.** The projection into Γ came out empty for every request, so the condition "with Γ" was identical to the baseline. The verdicts the code emitted for H-C17 (a) and H-C17 (b) were produced by construction and are declared uninterpretable; under the manipulation check of amendment 2 all three C2 hypotheses are refused. What the run does measure, because it does not depend on Γ, is reported below as descriptive.

Models: `qwen2.5:3b`, `llama3.2:3b` and `gemma2:2b` on Ollama 0.35.1, embeddings `nomic-embed-text`, on the author's Apple Silicon machine. Unmodified outputs in `results/2026-10-05_C1C2_run1/` (`results_real.json` sha256 `0d32f365…`), with every raw answer.

---

## 1. What happened to the treatment

The projection had a mean size of 2 bytes, the empty object `{}`, in all 60 writes (3 users by 20 topics) and all 1,500 items. The 4,500 multiple-choice answers with Γ are identical, letter by letter, to the 4,500 without Γ, because the prompts were identical. No user ended up with preferred terms in the projection, which is why the code itself refused H-C2.

The most likely cause is in digestion. On the C1 corpus, the verifier rejected 8 of the 12 claims the model proposed (rejection rate 0.67), all for lack of support: the anchor pointed at a fragment that did not contain the claim. The version 0.1 digester asks the model for the character offsets of each claim, and small models count characters poorly; a claim with wrong offsets is not anchored, and the projector uses only anchored claims. In addition, the projector looks for lexicon and register with patterns over the claim text, which the model paraphrases, instead of over the user's own words. The exploratory diagnosis (`lce_validation.diagnose`) will confirm or rule out these two causes before run 2.

## 2. Verdicts

| Hypothesis | Emitted by the pre-registered code | With amendment 2 | Reading |
|---|---|---|---|
| C1 (positive control) | holds | holds | accuracy 0.70 with memory vs 0.00 without; exactly at the threshold |
| H-C2, lexicon | refused | refused | no preferred term reached the projection |
| H-C2, ρ | not tested | not tested | needs the Swarmbly dispatch path |
| H-C17 (a) | falsified | refused | no treatment; uninterpretable |
| H-C17 (b) | holds | refused | Δ = 0 exactly from identical prompts; uninterpretable |

The design error belongs to the protocol, not to the data: the pre-registration had no check that the treatment arrived. It is written down here, with the original verdicts in view, so that nobody can cite "H-C17 (a) falsified" or "H-C17 (b) holds" from this run.

## 3. What the run does measure (descriptive)

**Errors shared across families.** Without projection, when two of the three models are wrong on the same item they choose the same wrong letter 56.3 % of the time, against a computed chance of 35.4 %: an excess of 0.209 (95 % CI [0.178, 0.241]) over 1,264 jointly wrong pair-items. By pair: gemma2 and qwen2.5 0.608 (chance 0.360), gemma2 and llama3.2 0.576 (0.356), llama3.2 and qwen2.5 0.496 (0.344). Accuracies were 0.606 (qwen2.5), 0.579 (llama3.2) and 0.535 (gemma2), with 0.2 % unparseable answers. The result reproduces in 2–3B models what Kim et al. (2025) report for large models, and it is the project's first own measurement supporting the Swarmbly note `FINDING_2026-10-04` and the limitation L23 it proposes. It does not depend on Γ, because it uses only the condition without projection.

**An unintended A/A test of the homogeneity instrument.** Because the projection was empty, the "baseline" and "projection" conditions were two independent samples of the same condition. Their difference was −0.003 (95 % CI [−0.010, +0.003]) over 20 topics, which puts the instrument's noise floor at about ±0.01 cosine similarity. A real effect of projection will have to exceed it.

**The placebo did reduce homogeneity.** The three generic contracts carrying no personal information lowered homogeneity across users from 0.880 to 0.853, a reduction of 0.026 (95 % CI [0.006, 0.049]). It is an exploratory observation, because the placebo was a control and not a hypothesis: any per-user variation in the prompt reduces homogeneity, and the personal projection will have to exceed it to be attributed to personalisation.

**Seeds did not fix the sampling.** With identical prompts and the same seed, the baseline and the empty projection produced different texts, so Ollama's OpenAI-compatible endpoint did not reproduce sampling by seed in this configuration. The design remains valid as random sampling per condition, but the pairing by seed described in Section 3 of the pre-registration did not hold, and is declared as such.

**Digestion and canary.** Anchoring rejected 67 % of the real digester's claims (Section 1). The canary set, still unverified, gave a tail mass of 0.00: `qwen2.5:3b` glossed none of the eight Ecuadorian regionalisms correctly. It is descriptive only until native-speaker verification.

## 4. What comes next

Amendment 2 of the pre-registration adds the manipulation check. The exploratory diagnosis shows, claim by claim, where the treatment is lost under each anchoring mode. With its result, an amendment 3 fixes the correction before run 2, which repeats the protocol with the same models, items, topics, statistics and thresholds. This run stays published as it is, failed parts included.

---

**References**

Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. In *Proceedings of ICML 2025*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

*Text under CC BY 4.0.*
