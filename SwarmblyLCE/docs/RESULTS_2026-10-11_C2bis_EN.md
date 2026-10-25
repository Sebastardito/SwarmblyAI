---
status: current
lang: en
kind: confirmatory
---

# Results — C2-bis (instruction-matched placebo): does not test H-C17a

**11 October 2026 · pre-registration `PREREGISTRATION_BENCH_R1X_EN.md`,
Section 2.8, with Amendments 14 (before the re-run) and 15.5 (after) ·
commit `9fd3a1a` (`1e363f2` in the provenance, before the weights purge:
see `COMMIT_MAP_2026-10-11.md`) · Python 3.9.6 (Amendment 15.1) · 5 users
× 20 topics × 3 seeds, qwen2.5:3b through the native seeded endpoint, the
Projector's full Γ (empty request) and a placebo with the same number of
tokens**

Outputs in `results/bench_c2bis/results.json`.

## 1. Figure

Homogeneity difference placebo − Γ = **+0.0652 [+0.0557, +0.0742]** (100
user × topic cells, bootstrap over cells, 10,000 resamples, seed
20261005). Mean homogeneity: with Γ 0.844, with placebo 0.910. Γ is 21–45
tokens depending on the user; the placebo is the same length.

## 2. What it measures and what it does not

Section 2.8 asks to test H-C17a: that the projection reduces homogeneity
**across users** (texts by different people on the same topic become less
alike) more than an instruction-matched placebo. The implementation
(`lce_validation/bench_c2bis.py`) computes something else: the homogeneity
across the **three seeds of the same user and topic**. What the +0.065
shows is that, with their Γ, a user's three samples are less alike than
with the placebo. That is within-user variability, not differentiation
across users.

There are two further problems. There is no no-contract arm, so it cannot
be said whether Γ lowers homogeneity or the placebo raises it; and the
placebo explicitly asks for "a neutral register" and "a general, common
vocabulary", that is, it pushes towards homogeneity. Finally, Amendment 14
said the first run's numbers would be reported as an instrument check, but
they were not kept (Amendment 15.5).

| Hypothesis | Verdict |
|---|---|
| H-C17a (Section 2.8) | **no verdict**: the run does not measure the quantity the hypothesis defines |

H-C17a stays as it was after run 2 of C1/C2: it holds, with the
qualification that its placebo matched Γ's form and not its amount of
instruction. The qualification is not closed.

## 3. What a re-run requires

Cross-user homogeneity per topic (the five users with the same seed), three
arms (no contract, Γ, matched placebo) and a neutral placebo that does not
prescribe register or vocabulary.

## 4. What this document replaces

The first version stated that "H-C17a holds" and that the run-2 reduction
"was a real projection effect, not contract length". That conclusion is
retracted.

*Text CC BY 4.0.*
