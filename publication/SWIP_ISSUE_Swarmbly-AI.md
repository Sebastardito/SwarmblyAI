---
status: current
lang: en
---

# Discussion issue for the LCE SWIP (to open in Sebastardito/Swarmbly-AI)

Paste the block below into a new issue with the SWIP template (`.github/ISSUE_TEMPLATE/swip.md`), title **`[SWIP] Local Cognitive Extension and optional knowledge capsules`**. When the issue has a number N, the full proposal (`swips/SWIP-XXXX-local-cognitive-extension.md` in SwarmblyLCE) is renamed `SWIP-000N-local-cognitive-extension.md` and opened as a PR containing only that file. Review window: 14 days (it touches privacy).

---

## Metadata

| | |
|---|---|
| **Title** | Local Cognitive Extension and optional knowledge capsules |
| **Author** | Sebastián A. Espinoza-Ulloa (@Sebastardito) |
| **Targets spec version** | 0.3 (see open question 2) |
| **Requires / builds on** | none |
| **Supersedes** | none |
| **Breaking change?** | no |
| **Touches wire format, security, or privacy?** | yes: an optional profile block and optional capsule messages; privacy of the client's memory |

## Abstract

An optional, local-first extension in which each client keeps a readable memory anchored to its user's sources and a lightweight adapter trained only on behavior, never on facts. Personalization enters the protocol only through fields of the existing global contract Γ, and workers serving third parties keep using their base model, so verification is untouched. The only wire-visible additions are an optional coarse `cognitive` block in the node profile (≤ 1,024 bytes) and optional pull-only request/response messages for small signed knowledge capsules (≤ 16 KiB). A node that ignores all of it remains fully conformant.

## Motivation

The client is the only unit in Swarmbly that keeps memory, and today that memory is discarded: every request starts without the user's terminology, register or prior work, and the only way to personalize is to send more context, which raises ρ and widens what workers observe. The design, its evidence base and its failure modes are in the LCE whitepaper v0.1 (doi:10.5281/zenodo.23150478), with a reference implementation, a validation harness and the raw outputs of every run at github.com/Sebastardito/SwarmblyLCE (software v0.1.1: doi:10.5281/zenodo.23289041). The first measurements with real models now exist and are summarised under Measurement plan; the pre-registered confirmatory run is reported with its failed first attempt included.

## Specification

Summary; the normative text is the full SWIP (revision 3, which adds the measured validation status without changing the normative specification). The **cognitive capability block** is an optional profile field with `v`, `share_mode` (`none | metadata | pull`), coarse `capsule_kinds`, `domains`, `languages` and `max_capsule_bytes`, bounded in size and forbidden from carrying biographical attributes; clients treat it as advisory. **Capsules** are canonical-JSON objects identified by BLAKE2b-128 and signed with Ed25519, carrying an anchor (kind and digest), an epistemic distance, permissions (`cache`, `redistribute`, `train`) and, for descendants, the evidence that justifies the variation; descendants without new human evidence are rejected (`E_CAPSULE_NO_DELTA`), and material at distance greater than 1 may be cached but not redistributed or trained on. Exchange is pull only: no gossip, no global index. Two rules bind workers: a worker serving third parties MUST use its base model without adapter, and MUST NOT retain task content by default. Task Projection writes into Γ only, and re-classifies the request's privacy lane after retrieval, never lowering it.

## Rationale

Local state instead of a global knowledge graph keeps the protocol's low-communication design; reusing Γ avoids a second channel; base-model workers keep verification by activation commitments valid; capsules instead of adapters keep transfers small and inspectable; pull instead of gossip bounds traffic and correlation; prevalence is shown as a label and never used as an adoption criterion, because conformist adoption erodes minority variants; replica counts for preserved capsules derive from a churn tolerance rather than a fixed number. The alternatives considered and why each was rejected are in the full SWIP, Rationale 1–12.

## Backwards compatibility

Not breaking. Unknown profile fields are ignored under the minor-version rule; a client never assumes capsule support without the block; capsule errors never affect normal task execution; no change to decomposition, DAG planning, carry, ρ accounting, k, assembly, verification, tiers, lanes or credits.

## Security and privacy implications

A malicious node can observe at most the coarse capability block and the capsules it is explicitly asked for; it learns nothing more about the user's memory, because projection writes only Γ fields and raises lanes. It can serve poisoned capsules: they are signed but not trusted, anchored claims are verified locally, distance > 1 never trains, and no capsule becomes truth by being popular. A coerced client cannot make workers learn from requests, because workers retain nothing and serve their base model. New trust assumption: none beyond the existing ones; affinity is local and always subordinate to E12 family diversity. Traffic analysis: capsule pulls are a new observable and are bounded by pull-only exchange and size limits. Correlated errors: the LCE does not decorrelate errors within a request (whitepaper Sections 2.6, 6.4); that is recorded as a limitation, not hidden.

## Measurement plan

Experiments C0–C12 with kill conditions are in the whitepaper, Section 11. The first confirmatory run (C1, C2) was pre-registered with its decision rules as code (`lce_validation/decide.py`) and run with three local model families of 2–3B parameters (`docs/RESULTS_2026-10-05_C1_C2_run2_EN.md`):

- **Run 1 failed its manipulation**: the projection came out empty, so its C2 verdicts are refused and the failure is published. Amendments 2 and 3 (a manipulation check, then quote anchoring and span projection) were committed before run 2.
- **C1 (positive control)** holds: accuracy 0.80 with memory vs 0.00 without.
- **H-C2, lexicon part** holds: adherence 0.667 with Γ vs 0.033 without (difference 0.633, 95 % CI [0.500, 0.750]).
- **H-C17a** holds: homogeneity across users 0.879 → 0.806, exceeding a non-personal placebo by 0.048 [0.023, 0.070]. The placebo matched the form of Γ, not its amount of instruction.
- **H-C17b** holds as equivalence: cross-family error agreement rises by 0.039 [0.009, 0.069], inside ±0.10 but not zero; the excess over chance is unchanged (0.206 vs 0.209), and Γ has a small accuracy cost on factual items.

Local memory raises answer accuracy on user-specific questions by +0.500 (question-clustered 95 % CI [0.420, 0.578]; 5 synthetic users, 5 families; clean sources; exploratory). The pre-registered R13 confirmatory run (251 questions, including a LongMemEval subset) is a negative result for the anchored wiki as an answering memory: it loses to raw retrieval on accuracy (A3 − A2 = −0.146 [−0.186, −0.106], three digesters × three responders), the loss lying in digestion coverage, so the wiki is kept as a governance layer (provenance, forgetting, training) rather than the main answering context. Forgetting a source removes every claim anchored to it with no collateral damage and returns behaviour to the never-ingested level (mechanism, 5 questions). Digestion is not reproducible run to run on the tested stack, so the reproducibility criterion stays open. The per-packet projection adds +5.8 to +7.8 % to ρ with the real planner. The adapter confirmatory run (R11) was refused for a manipulation failure (the adapter was not applied at evaluation), and the C2-bis and H-C2 closure runs did not measure the pre-registered quantities; none of the three issues a verdict. The scope of every figure (synthetic users, small local models, MCQ items in English) is stated in the full SWIP, section "Validation status". Not yet tested: ρ against the projection's adherence gain (the actual kill condition of H-C2), the adapter against retrieval (H-C6), and the social plane (C9).

## Reference implementation

`swarmbly_lce` in github.com/Sebastardito/SwarmblyLCE (reference implementation of the full specification, one test per invariant I1–I8). Published for review, not for merging; protocol-facing code would come in separate PRs after acceptance.

## Open questions

1. One SWIP or two? The local layer and Task Projection need almost no wire change, while capsules do. Splitting into SWIP-A (worker base-model rule, Γ projection, lane re-classification) and SWIP-B (capability block, capsules) would let the first be judged on the C1/C2 results, which now exist, without waiting for capsule experiments.
2. Target spec version: `SPEC_EN.md` is v0.2 while whitepaper v2 points to v0.3.
3. Should the profile carry `domains` at all, or only a boolean `capsules: true` with topics discovered after connection?
4. BCP 47 for `languages`; registry or bounded free strings for `domains`.
5. Licence representation (SPDX) before capsules are used for training or redistribution, and signed revocation (tombstones).
6. Γ caching. Γ travels in every packet, so its ρ cost multiplies by the number of fragments. Should the protocol offer a per-request injection point or a per-user Γ cache on the node? This benefits every Γ user, not only the LCE; the per-request figure (about +1.5 to +2.6 %) is an arithmetic estimate, not a measurement.
7. Digester quality. In R13's crossed design the digester effect is separated from answering: digestion coverage (45–84 % of answerable keys reach the context, against 95 % with raw retrieval) explains the wiki's accuracy, and a floor on anchored claims does not discriminate. Is digestion quality a client concern only, or should the profile advertise it?

## Checklist

- [x] I have read `CONTRIBUTING.md` Section 6 (the SWIP process)
- [x] This genuinely requires a SWIP (optional wire fields and new node obligations)
- [x] I searched existing and closed SWIPs (only SWIP-0001, unrelated)
- [x] The Specification is complete in the full SWIP (revision 3)
- [x] The Security and privacy implications section is filled in
- [x] The Measurement plan is filled in and pre-registered, and the first confirmatory results are reported, failed run included
- [x] No performance or quality claim is made without a measurement
