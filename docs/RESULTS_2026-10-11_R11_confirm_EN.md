---
status: current
lang: en
kind: confirmatory
---

# Results — R11 confirmatory run (the fair adapter): REFUSED for manipulation failure

**11 October 2026 · pre-registration `PREREGISTRATION_BENCH_R1X_EN.md`,
Section 3, with Amendments 9 and 13 (before evaluating) and 15.4 (after) ·
commit `b836e84` (`b8b474e` in the provenance, before the weights purge:
see `COMMIT_MAP_2026-10-11.md`) · Python 3.9.6 (Amendment 15.1) · 48 MLX
LoRA trainings (2 base families × 3 users × 2 seeds × 2 rehearsal settings
× 2 budgets) and 1454 evaluation cells**

Outputs in `results/bench_r11_confirm/results.json` (every cell with the
base and adapter text). The adapters and their batches were generated
locally and are not versioned: they derive partly from
Qwen2.5-3B-Instruct, whose licence (qwen-research) does not allow
redistributing them (Amendment 15.8).

## 1. What was measured

| User | base | retrieval + Γ | adapter | adapter + retrieval + Γ |
|---|---|---|---|---|
| mara | 0.050 | 0.617 | 0.050 | 0.617 |
| julian | 0.133 | 0.650 | 0.133 | 0.650 |
| carmen | 0.000 | 0.633 | 0.000 | 0.633 |

(30 tasks per user × 8 full-budget configurations; 720 rows.)

## 2. Why the run is refused

The adapter and the base model produce **the same text, byte for byte, on
all 720 tasks**, and the same correctness on **all 1454 cells** (main
tasks, I1, LC6 and H-C10). The trained LoRA weights are non-zero, so the
adapter exists but did not reach the evaluation. Two likely causes in
`lce_validation/bench_r11.py`: the MLX server is started with
`--adapter-path`, but every request sends `"model": base_model`, which can
make the server serve the base model; and the evaluation uses
`/v1/completions` without the chat template the adapter was trained with.

This is a manipulation failure, like C2 run 1: the treatment did not
arrive. An "adapter − base = +0.000 exactly" does not say the adapter is
inert; it says it was not applied. Therefore:

| Hypothesis | Verdict |
|---|---|
| H-C6 (adapter versus retrieval + Γ) | **no verdict**: run refused. Layer 2 is NOT withdrawn by this run |
| I1 (fact leakage) | **no verdict**: the +0.000 equivalence is that of two identical outputs |
| LC6 (forgetting in the adapter) | **no verdict** |
| H-C10 (rehearsal) | **no verdict** |

The only thing the run does show is that retrieval with Γ (0.62–0.65)
carries the user's behaviour far above the base (0.00–0.13) on these
tasks, consistent with R13 and F1a.

## 3. What the next run requires

A manipulation check BEFORE evaluating anything (Amendment 15.4): the
adapter must change the output on its own training examples relative to
the base, with the same chat template as training and the request
addressed to the adapter. If it does not, the run is refused. It must
also record the base/adapter text difference per cell, so that a
treatment that does not arrive shows up in the summary.

Two design notes for that run: batches are small (6–15 examples per user,
from the trainable claims of the canonical wiki), and Amendment 9 counts
"24 trainings" where its own formula (2 × 3 × 2 × 2 × 2) gives 48, which is
what was run.

## 4. What this document replaces

The first version of this document stated that "the pre-registered death
rule fires" and that "layer 2 is withdrawn". That conclusion is retracted:
a decision rule is not applied to a run whose treatment was not
administered.

*Text CC BY 4.0.*
