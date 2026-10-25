---
status: current
lang: en
kind: exploratory
---

# Results — R11 pilot (the fair adapter)

**9 October 2026 · pre-registration `PREREGISTRATION_BENCH_R1X_EN.md` Section 3,
with Amendment 5 · EXPLORATORY PILOT**

> **Notice (10 October 2026): conclusions RETRACTED.** The review (E6) showed
> that this pilot is not a fair test of the adapter: the adapter collapsed onto
> its batch (its answers reproduce the header of the procedures document);
> about half of the tasks are invalid (the 6 procedure questions are the same
> for every user and come from other domains; the gold of "Describe how you
> write" is the whole rule with spaces removed, which cannot be matched); there
> are 15–17 tasks per user instead of ≥30 and the code computes no intervals;
> the "retrieval + Γ" arm carries no Γ; and the I1 test uses general-knowledge
> questions, so it measures the interference of a collapsed adapter, not the
> leak of the user's facts. Nothing below may be cited as evidence about H-C6,
> H-C10 or I1. It is kept as history; the redesign belongs to the next phase.

## Figures (as originally reported)

12 qwen2.5-3b adapters (3 users × 2 seeds × replay yes/no), batch of 6–17
pairs ONLY from trainable claims (I1), 300 iterations, evaluation of FOUR
arms on reworded tasks. granite-3.1-2b was **skipped**: its digester produced
only 4 trainable claims per user (a digester defect, not an adapter one).

| Arm (mean per user) | mara | julian | carmen |
|---|---|---|---|
| base | 0.12 | 0.19 | 0.02 |
| retrieval (labelled "+ Γ", without Γ) | 0.54 | 0.55 | 0.52 |
| adapter | 0.11 | 0.07 | 0.10 |
| adapter + retrieval | 0.28 | 0.21 | 0.13 |

As originally written: "H-C6 (adapter − retrieval): mara −0.435, julian
−0.477, carmen −0.429; 0/3 users meet the margin", and "I1 leak: adapter −
base = −0.367 (n = 60), safe direction but outside the ±0.10 equivalence".
Both statements are retracted for the reasons in the notice.

## Reading (as originally written, retracted)

The original reading claimed that retrieval dominated the adapter by about 45
points and that the confirmatory run would very probably withdraw layer 2.
That reading compared retrieval against a collapsed adapter on partly
invalid tasks and is withdrawn. The next phase needs valid, user-specific
tasks (≥30 per user), iterations and learning rate chosen on a validation
split, retrieval arms with and without Γ, and an I1 test on the user's own
facts that were left out of the batch.

*Text CC BY 4.0.*
