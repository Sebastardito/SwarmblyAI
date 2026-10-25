---
status: current
lang: en
kind: exploratory
---

# Results — R12 exploratory (social plane, UNVERIFIED canary)

**9 October 2026 · pre-registration `PREREGISTRATION_R12_EN.md` · EXPLORATORY
run: mechanism only, no figures about the terms**

> **Notice (10 October 2026): conclusions CORRECTED.** The review (E7) showed
> that this run does not turn I4 into a measurement: 0/40 is by construction
> (no node knew any term before the exchange); the implemented "utility" rule
> adopts by novelty (the gloss is not in the node's own), not by the posterior
> benefit the pre-registration states; prevalence requires ≥3 identical
> free-text glosses and therefore can never form; it reports figures about
> the terms although the pre-registration only allows describing the
> mechanism; and it computes no F_ST. What it does show: the adoption circuit
> works and adopting by novelty spreads whatever arrives, which is COMPATIBLE
> with I4, not empirical support for it. The confirmatory run requires the
> verified canary and F_ST.

## Figures (as originally reported)

5 nodes (one family each) × 8 canary terms (0/8 verified), 2 exchange rounds.

| Arm | Adoptions per node | Correct after | Identity (2 rounds) |
|---|---|---|---|
| utility (novelty) | 6–7 | 0/40 | 1+1 |
| prevalence | 0 | 0/40 | 1+1 |

## Reading (corrected)

1. **The adoption circuit runs**: the novelty rule adopts 6–7 capsules per
   node. Prevalence adopts none because the exact-match majority cannot form
   with free-text glosses, a defect of the rule, not a property of rare tails.
2. **0/40 is by construction**: no base model knew the Ecuadorian terms, so
   every capsule carried a wrong gloss and novelty adoption spread it. This is
   compatible with I4 ("variation comes from people"), not a test of it.
3. **Identity**: 1+1 violations in 80 probes per arm, insufficient signal
   (<5 in total) under the pre-registered rule; it decides nothing.
4. **I5 guard** flagged the prevalence threshold rule, as it should.

## Consequence for the confirmatory run

The confirmatory run (canary VERIFIED by native speakers) must inject the
verified glosses as human knowledge into the source node's capsules (as I4
requires), judge utility by posterior benefit, form prevalence by semantic
grouping of glosses, and compute F_ST. The verification workflow is ready in
`lce_validation/data/canary_verification/`.

*Text CC BY 4.0.*
