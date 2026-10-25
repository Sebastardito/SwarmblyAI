---
status: current
lang: en
kind: descriptive
---

# Results — H-C2 closure (ρ versus its gain): description, no verdict

**11 October 2026 · pre-registration `PREREGISTRATION_BENCH_R1X_EN.md`,
Section 2.9, with Amendment 15.6 · commit `c614fd1` · Python 3.9.6
(Amendment 15.1) · 251 tasks, the cells of the R13 confirmatory run**

Outputs in `results/bench_hc2_closure/results.json`; code in
`lce_validation/bench_hc2_closure.py`.

## 1. Figures

| Measure | Value |
|---|---|
| tasks | 251 |
| mean gain with Γ (A4 − A3, QA accuracy) | +0.0159 |
| tasks with gain > 0 | 14 (fraction 0.0558); 10 with gain < 0; 227 unchanged |
| median Δρ | 40.98 % (range 15.0–96.2 %) |
| fraction with gain > 0 and Δρ ≤ 10 % | 0.0 |

## 2. Why this is a description and not a verdict

Section 2.9 asks, per task, for the **adherence** gain with Γ and the Δρ
measured with Swarmbly's **real planner and packer**. The run measured
something else on both axes (Amendment 15.6):

1. The gain is question-answering accuracy (A4 − A3), not adherence to the
   user's preferences, which is what H-C2 claims.
2. Δρ does not go through the packer: it is computed as the Γ tokens added
   to each fragment over the tokens of the retrieved context. It is an
   arithmetic bound, not a dispatch measurement; the measurement with the
   real packer (+5.8 to +7.8 % per packet, median +7 %) is in `results/bench_rho/`.
3. Each task's gain comes from a single digester = responder pair, because
   the per-question dictionary keeps the last diagonal cell.
4. The rule "fraction of tasks with gain > 0 and Δρ ≤ 10 % ≥ 0.8" is almost
   unattainable with binary per-task gains: it requires 80 % of tasks to
   improve. The error belongs to this pre-registration, not to the data.

## 3. Reading

In question answering, adding Γ costs context and barely changes accuracy
(also A4 − A3 in the R13 confirmatory run: −0.036, −0.024 and +0.016 by
digester). That is consistent with the design: Γ carries form
preferences, not facts, and is not expected to improve QA accuracy. **H-C2
remains undecided for its use case, writing**: the measure that decides it
(per-task adherence versus Δρ with the real packer) is still pending, and
its compensation rule must be rewritten by amendment before running.

## 4. What this document replaces

The run's commit and the first versions of the SWIP and the report stated
that "the projection does NOT survive the compensation rule" and spoke of
"adherence gain". That conclusion is retracted.

*Text CC BY 4.0.*
