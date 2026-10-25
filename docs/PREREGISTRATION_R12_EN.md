---
status: current
lang: en
---

# Pre-registration — R12: the social plane (C9, H-C11, H-C8)

**9 October 2026 · written BEFORE any R12 run**

Separate pre-registration of the social plane, as declared in
`PREREGISTRATION_BENCH_R1X_EN.md` Section 4. **The canary set must be VERIFIED by
native speakers for the confirmatory run** (≥2 of 3 pseudonymous verifiers
confirm each gloss and none marks it offensive; rule in `canary_verify.py`).
The EXPLORATORY run with the unverified canary is allowed and reports only
the MECHANISM, never figures about the terms.

## 1. Redesign (fixes the declared limits of C9-lite)

1. **Identity probe WITH the adopted capsules in context** — the previous
   version passed it without context and counted the same answer twice in
   both arms.
2. **Real PREVALENCE arm**: adopts the MAJORITY VARIANT among the nodes'
   glosses (even if wrong) — not matches against the key.
3. **Utility judged by posterior benefit, key-free**: a node adopts if the
   capsule's gloss is not contained in its own previous answer.
4. **Capsules with the source node's knowledge**: the capsule's gloss is the
   source node model's answer, not the file's.
5. **Several rounds** (2 exchange rounds) and **F_ST** over variant
   frequencies per round, with Nm = rounds.

## 2. Design

5 nodes (one family each: qwen2.5:3b, llama3.2:3b, gemma2:2b, phi3.5:3.8b,
granite3.1-dense:2b), 8 canary terms. Pre-test: each node glosses each term
with its base model. Round 1: each node publishes capsules with ITS glosses
(correct per the key or its own: recorded which). The others adopt per the
arm. Post-test and identity per round. Round 2: repeated with the
accumulated store.

## 3. Decision rules

| Hypothesis | Holds | Dies | Otherwise |
|---|---|---|---|
| H-C11 (direction) | UTILITY identity violations < PREVALENCE with ≥5 total violations | UTILITY ≥ PREVALENCE | insufficient signal |
| H-C5 (persistence by use) | tail mass does not fall between rounds in the utility arm | falls persistently | — |
| H-C8 (migration band) | utility on rare content is maximal at an intermediate Nm | monotonic in Nm | the Wright homology reverts to vocabulary |

**Refusals**: unverified canary (confirmatory only), <5 nodes responding,
>10 % of answers unscoreable.

## 4. Declared scope

Exploratory (unverified canary): mechanism only. Confirmatory (verified
canary): the H-C11/H-C5/H-C8 figures.

*Text CC BY 4.0.*
