---
status: current
lang: en
kind: exploratory
---

# Results — forgetting test (F-forget) and A/A reproducibility test

**10–11 October 2026 · Amendment 6 (c) of
`PREREGISTRATION_BENCH_R1X_EN.md`, committed before running, with
Amendments 7, 10–12 and 15 · exploratory tests of mechanism and
reproducibility: they issue no verdict on H-C1 · digests checked against
`lce_validation/data/model_digests.json`**

This document replaces the 10 October version, which reported a run made
before Amendments 7–12 (13 valid cells, abstention 0.359 → 0.718, AA1 100 %
identical) and the equivalence "15 of 15 with the R13 wikis". Those
figures are retracted; the current ones come from the runs in the
confirmatory configuration and are described below.

| Run | Commit | Python | Outputs |
|---|---|---|---|
| F-forget | `a210e57` | 3.11.17 (locked `.venv`) | `results/bench_forget/` |
| A/A | `a05b234` | 3.9.6 (deviation; Amendment 15.1) | `results/aa_test/` |

Both use native seeded digestion and the tolerant parser (Amendments 7 and
10), in a single pass (Amendment 11's double pass was reverted by
Amendment 12). The behavioural figures that follow the pre-registration
and the comparison with the R13 confirmatory run are in
`results/bench_forget/analysis.json`; `run_derive` and
`tests/test_doc_figures.py` check them.

## 1. F-forget: does forgetting a source erase what was learned from it?

For each user (5) and digester (qwen2.5:3b, llama3.2:3b, gemma2:2b) three
wikis were built: W_full, digested with every `.md` source; W_forget, the
same after `Wiki.forget_source("teach/knowledge/borrada.md")`; and
W_never, digested in the same run without that source.

**Structure.** All 15 cells pass S1 (each W_full has between 1 and 7
claims anchored to the deleted source). In every one, W_forget keeps no
claim anchored to the forgotten source (S2 = 0) and loses or changes no
claim from other sources (S3 = 0). The same holds in the sweep that
forgets, one at a time, every source of every W_full: 116 forgets, residue
0 and collateral damage 0. Since `forget_source` deletes by anchor, zero is
expected: S2 and S3 verify that the implementation does what the
specification says on real wikis, not an empirical effect.
**Pre-registered structural verdict: holds.**

**Equivalence with never having digested it (S4, descriptive).** W_forget
matches the same run's W_never in 8 of 15 wikis (mean Jaccard 0.956), and
the context both deliver to the questions is identical in 70.8 % of cases.
A post-data analysis also compares with the wikis of the R13 confirmatory
run, digested in another run without the source: they match 0 of 15
(W_forget) and 0 of 15 (W_never). The differences come from digestion not
being reproducible run to run on this stack (AA2, Section 2; Amendment
12), not from forgetting: S2 and S3 show that `forget_source` leaves
nothing of the source and touches nothing else, but exact equality with a
wiki that never saw it cannot be checked while digestion is not
deterministic.

**Behaviour.** Abstention on the 5 questions about the deleted source,
with R13's prompt, retrieval and rubric (15 cells × 3 responders):

| Wiki | Abstention |
|---|---|
| W_full | 0.289 |
| W_forget | 0.778 |
| W_never | 0.756 |

forget − full = **+0.489 [+0.333, +0.644]** and forget − never = +0.022
[+0.000, +0.067] (question-clustered bootstrap). B1 (the full wiki
abstains at least 0.10 less than the one that never saw the source) and B2
(forgetting is complete in behaviour: abstention with W_forget exceeds
W_full's and lies within ±0.10 of W_never's) are met. 88.9 % of the
answers with W_forget and W_never are identical.

**Reading.** This is what R13's `deleted` type could not measure (N2):
here the wiki had learned from the source, forgot it and behaves as if it
had never had it. There are 5 questions, so power is low and the result is
one of mechanism, not magnitude. Nor is it a comparison with RAG: in a RAG,
forgetting a source means removing the file from the index. What F-forget
shows is that the wiki, which turns sources into claims, keeps that
property.

## 2. A/A reproducibility (R14 1.2–1.4)

AA1 and AA2 are evaluated against the outputs of the confirmatory run
(Amendment 10 c); AA2 compares two runs of native seeded digestion
(Amendment 7).

| Test | Result | Criterion |
|---|---|---|
| AA1 generation at T = 0 (A2 arm repeated on the v1–v3 own-user questions contained in the confirmatory run: Amendment 6's 126 minus the 3 N1 questions, 123 × 3 responders = 369 answers) | 98.4 % identical in the first 200 characters; accuracy 0.707 → 0.710 (Δ +0.0027) | **fails** (requires ≥ 99 %) |
| AA2 digestion (second digestion of the 15 wikis against F-forget's W_never) | 8 of 15 sets identical; mean Jaccard 0.961 | **fails** (requires ≥ 14 of 15) |
| AA3 seed at T = 0.7 (qwen2.5:3b, 20 topics × 3 seeds × 2 repetitions) | native endpoint 100 % identical (effective); OpenAI-compatible 80 % (not effective) | the native seed was adopted for digestion (Amendment 7) |
| AA4 homogeneity across repetitions | mean Δ −0.0011 [−0.0067, +0.0047] | **passes** (≤ 0.01) |

**R14's re-run criterion is not closed** (Amendment 12, as a documented
negative). The stochastic measure (AA4) is stable; generation at T = 0
nearly is, but misses the threshold against a run made hours earlier (in
the 10 October run, against the pilot, it was 100 %); digestion is not
reproducible run to run even with a seed. The AA2 in this table also
compares a digestion under Python 3.11.17 (F-forget) with one under 3.9.6
(A/A), so it mixes server non-determinism with an environment change.

## 3. Declared deviations

1. The A/A ran with Python 3.9.6, not the locked 3.11 that Amendment 6
   requires (Amendment 15.1); F-forget did use the `.venv`.
2. The comparison of W_forget with the R13 wikis was not pre-registered;
   it is reported as a post-data analysis.
3. The run script was adjusted before starting to accept the name
   `nomic-embed-text:latest` (commit `eca8f88`; `586eb21` in the
   provenance, before the weights purge: see `COMMIT_MAP_2026-10-10.md`);
   it affects no measure.

*Text CC BY 4.0.*
