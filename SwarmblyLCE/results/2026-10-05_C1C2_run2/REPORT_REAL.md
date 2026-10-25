# lce_validation — real-model run

**Run type: confirmatory.** Models: qwen2.5:3b, llama3.2:3b, gemma2:2b · 2026-10-05T07:31:52Z · commit 99a1d5246a

Pre-registration sha256 `508ba8f9af29f0ff…` · MCQ sha256 `c8991d3bab8578d0…`

Scope: fixture corpus (1 synthetic user) for C1; 3 synthetic users x 20 topics for H-C2/H-C17a; 1500 MMLU items x 3 families for H-C17b; canary unverified (descriptive only).

- Wiki: 12 claims; anchor rejection rate 0.00; malformed digester outputs 0.
- C1 (positive control): accuracy with memory 0.80 vs without 0.00.
- C2 / H-C2 lexicon adherence: 0.667 with Γ vs 0.033 without (difference 0.633, 95% CI [+0.500, +0.750]; 60 cells). Projection bytes 97.
- C2 / H-C17 homogeneity across users (mean cosine, 20 topics, T=0.7): baseline 0.879, projection 0.806, placebo 0.854. Reduction by projection +0.073 [+0.052, +0.096]; by placebo +0.025 [+0.004, +0.049]; projection beyond placebo +0.048 [+0.023, +0.070].
- C2 / H-C17 error agreement given both wrong (1500 MCQ items): without Γ 0.563 (chance 0.354, excess [+0.178, +0.241]); with Γ 0.602; delta 0.039 [+0.009, +0.069]; invalid answers 0.002/0.003.
- Canary (unverified, descriptive only): tail mass 0.00; identity violations 0.00.

## Verdicts (lce_validation.decide)

- **C1: holds** — positive control passed: retrieval over the real-model wiki answers user-specific questions
- **H-C2_lexicon: holds** — preferred terms appear more often with Γ than without (CI excludes 0)
- **H-C2_rho: not_tested** — redundancy rate rho needs the Swarmbly dispatch path; not part of this run
- **H-C17a: holds** — projection lowers cross-user homogeneity (CI excludes 0) (reduction exceeds a non-personal placebo)
- **H-C17b: holds** — error agreement unchanged within ±0.1 (equivalence)
- Replication of Kim et al. (2025), descriptive: errors shared above chance across families (excess CI excludes 0).
