---
status: current
lang: en
---
# Errors from different model families are correlated: what that takes away from E12 and E16

**Found:** 4 October 2026, during the literature review for the local cognitive
extension (LCE).
**Class:** external evidence against a design assumption. **Not a measurement by
this project**; no figure in this note comes from Swarmbly runs.
**Status:** **open.** Proposes a new limitation (L23) and a wording amendment for
the next whitepaper version, and a cheap measurement on the existing corpus. It
does not modify the published whitepaper v2.

---

## 1. What was found

Two recent papers measure what whitepaper v2 treated as mitigated by model-family
diversity.

Kim et al. (2025) evaluated more than 350 models and found that, on one of the
leaderboards studied, **two models agree 60% of the time when both are wrong**.
Correlation grows with shared architecture and provider, as expected, but the
finding that matters here is different: **larger and more capable models have
highly correlated errors even with distinct architectures and different
developers** [1].

Jiang et al. (2025) show, over 26,000 real open-ended queries, that different
models produce strikingly similar responses to one another, in addition to
repeating themselves, an effect they call the "artificial hivemind" [2].

## 2. Which whitepaper v2 claims it touches

The whitepaper already acknowledges the problem and assigns it a remedy. Section
10.5.4 says agreement is not truth because "models trained on overlapping corpora
share errors", and that this is why Section 9.6 mandates cross-family diversity.
**The new evidence says that remedy is partial**: family diversity reduces the
correlation due to shared architecture and provider, but not the correlation that
comes from overlapping pretraining data, which reaches models of different families
and developers and is strongest in the most capable models.

Three claims are affected:

- **E12** (diversity-preserving redundant dispatch): assigns replicas to different
  families assuming approximately independent errors. The assumption weakens; the
  mechanism remains useful against architecture and provider correlation.
- **E16 / M1** (consensus by multiple alignment and low-confidence map): agreement
  among three families can be a shared error. The reliability withdrawal of L13
  already forbids presenting convergence as correctness; this evidence gives a
  further mechanical reason to keep it, and it narrows the regime in which M1 was to
  show signal ("where models genuinely disagree").
- **E17** (semantic coverage): unaffected in what it claims, since it already bounds
  availability, not correctness.

## 3. What does not change

Reporting **where** replicas diverged remains a real capability, and remains the
one a single-model provider does not have. What changes is how much can be
inferred from **where they converged**.

## 4. What the LCE can and cannot contribute

A natural question is whether the diversity produced by each user's local learning
fixes the problem. The answer, developed in the LCE whitepaper
(Espinoza-Ulloa, 2026, doi:10.5281/zenodo.23150478; Sections 2.6, 6.4 and LC3), is **not within a single request**: in the LCE,
workers serve their base model with no adapter, so the user's learning never
reaches the replicas E16 aligns; and even if it did, the adapter learns behaviour,
not facts, and LoRA preserves the base model's knowledge and with it its errors. In
population-genetic terms the correlation is **identity by descent**: the models
share ancestry because they were pretrained on overlapping corpora, and a local
adapter is closer to phenotypic plasticity than to new alleles. The LCE does reduce
homogeneity **across users** on open-ended tasks, which is the effect in [2],
through each user's projection onto Γ; that is real diversity, but not error
independence.

## 5. Proposal for the next whitepaper version

**5.1 New limitation (proposed text).**

> **L23 — Family diversity attenuates error correlation; it does not remove it.**
> Over more than 350 models, two models agree 60% of the time when both fail on a
> leaderboard, and the most capable models correlate their errors even across
> architectures and developers [Kim et al., 2025]; different models also produce
> very similar open-ended responses [Jiang et al., 2025]. E12 still reduces
> architecture and provider correlation, but correlation from overlapping
> pretraining corpora reaches different families. Agreement across families can be
> a shared error.

**5.2 Amendment to 10.5.4.** Where it says Section 9.6 mandates cross-family
diversity "for this reason", add that such diversity is a partial remedy and point
to L23.

**5.3 Candidate hypothesis: evidence diversity.** If correlation comes from shared
knowledge, the lever to reduce it is evidence, not family. Proposed as a
hypothesis, not as an element: **replicas reasoning over different public
evidence** (e.g., retrieving from different sources, never from workers' personal
memory) have less correlated errors than replicas of different families without
evidence. Death condition: if error correlation between replicas with different
evidence is not lower than between replicas of different families without
evidence, the idea is withdrawn.

## 6. A cheap measurement is available

The reference corpus of Section 15.9 (473 runs over five local model families)
allows a direct estimate, with no new runs, of the probability of answer agreement
conditional on two families both failing, which is the metric of [1]. It is an
instrument the project already has, and it would turn this note from external
evidence into an own measurement, with its scope declared (five small families,
benchmark tasks, not a general leaderboard).

## References

[1] Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. In *Proceedings of the 42nd International Conference on Machine Learning*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

[2] Jiang, L., Chai, Y., Li, M., Liu, M., Fok, R., Dziri, N., Tsvetkov, Y., Sap, M., Albalak, A., & Choi, Y. (2025). Artificial hivemind: The open-ended homogeneity of language models (and beyond). In *NeurIPS 2025, Datasets and Benchmarks Track*. https://arxiv.org/abs/2510.22954
