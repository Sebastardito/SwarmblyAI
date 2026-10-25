---
status: draft
lang: en
---
# SWIP (draft): `constraints.model_family` — requesting a model family from a multi-model worker

**Status:** draft for discussion in the SwarmblyAI repository. Implemented
experimentally by Swarmbly App; nothing here is normative until accepted.
**Compatibility:** MINOR (SPEC §3). A worker that does not know the field
ignores it and serves its default model; the result's `profile` reports what
was actually served, so the orchestrator can always tell.

## Motivation

SPEC §12 already lets a node advertise several models, and SPEC §11.2 requires
replicas of one task to maximise model-family diversity. But a packet has no
way to say *which* of a multi-model worker's families it wants, so an
orchestrator cannot use that diversity: every replica sent to such a node
lands on its default model. Consumer machines increasingly hold more than one
small model (one per family), so a single machine could contribute two
families to the same task.

## Proposal

Add an OPTIONAL field to the packet's `constraints` object (SPEC §8):

```json
"constraints": { "temperature": 0.2, "top_p": 0.95, "stop": [],
                 "model_family": "qwen2.5" }
```

Rules:

1. `model_family` names a family that appears in the target node's current
   advertisement (`models[].family`). An orchestrator MUST NOT send a family the
   node did not advertise.
2. A worker that serves the named family MUST use it; one that does not SHOULD
   serve its default model rather than refuse, and in all cases MUST report the
   model it actually used in `profile` (SPEC §10). A mismatch is visible, not
   silent.
3. The orchestrator MUST count replicas by (node, family) pair and MUST prefer
   distinct nodes when several are available: two families on one machine share
   hardware failures, so they add epistemic diversity but little availability.
4. The field never selects a personal adapter: LCE invariant I2 still applies
   (workers serve base models only).

## Interaction with L23

Family diversity attenuates correlated errors; it does not remove them
(`FINDING_2026-10-04`). This field increases the diversity an orchestrator can
reach; it does not change how agreement may be interpreted (SPEC §14b.6).

## Death condition

If, on the reference corpus, replicas obtained from (node, family) pairs on a
shared machine show no lower error concordance than same-family replicas, the
field adds complexity without signal and is withdrawn.
