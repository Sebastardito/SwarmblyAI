# Swarmbly Protocol Specification

**Version 0.2 — 13 August 2026**
*Revision 2, 14 August 2026: adds Section 15c (privacy tiers and trusted swarms), the `tier` and `swarm_id` packet fields, the optional `swarm` block in the node advertisement, the `routing` response block, and the error codes `E_TIER_VIOLATION`, `E_MTLS_REQUIRED` and `E_SWARM_UNKNOWN`. Every addition is MINOR-compatible under Section 3: an implementation that ignores the new fields behaves exactly as tier `GLOBAL`, so the wire version remains `0.2`.*
Status: **Draft.** Normative for the reference implementation; expected to change before v1.0.
Companion documents: `WHITEPAPER_EN.md` (rationale and evidence), `SPEC_ES.md` (Spanish).

The key words MUST, MUST NOT, REQUIRED, SHALL, SHOULD, SHOULD NOT, MAY and OPTIONAL are to be interpreted as described in RFC 2119.

---

## 1. Scope and non-goals

Swarmbly is a protocol for executing a language-model request by decomposing it into semantic micro-tasks, dispatching those micro-tasks to independent worker nodes each running a complete small model, and reassembling the results on the requesting client.

**In scope:** request decomposition and planning; the packet, result and profile formats; dispatch, hedging and retry; verification of untrusted workers; assembly and coherence reporting; sensitivity-based routing; credit accounting.

**Out of scope (v0.2):** model training or fine-tuning; peer discovery transport (any DHT or rendezvous mechanism MAY be used); payment settlement; a consensus ledger. v0.2 deliberately specifies **no blockchain**.

**Explicit non-goals.** The protocol does not provide cryptographic confidentiality of request content on the PUBLIC or SANITISABLE lanes; does not provide strong Sybil resistance; and does not claim latency parity with centralized inference. See Sections 9 and 12 of `WHITEPAPER_EN.md`.

---

## 2. Terminology

| Term | Meaning |
|---|---|
| **Request** *P* | The complete user input to be answered |
| **Plan** *D* = (V,E) | Directed acyclic graph; vertices are micro-tasks, edges are result-dependencies |
| **Micro-task** *tᵢ* | One vertex of the plan; the unit of distribution |
| **Global contract** Γ | Shared specification transmitted with every packet (Section 5) |
| **Packet** *Kᵢ* | What a worker receives: Γ, predecessor summaries, and the micro-task |
| **Contig** *Rᵢ* | A worker's returned result for one micro-task |
| **Seam** | The boundary between two consecutive contigs in the assembly |
| **Context budget** *S* | Tokens of shared context per packet |
| **Redundancy ratio** ρ | Σ\|Kᵢ\| / \|P\| — the measured cost of the context budget |
| **Lane** | PUBLIC, SANITISABLE or SENSITIVE — the confidentiality routing class of the *content* |
| **Tier** | GLOBAL, TRUSTED or LOCAL — the routing class of the *population of workers* (Section 15c) |
| **Trusted swarm** | A permissioned sub-mesh whose membership is a public-key whitelist under a declared operator, with mutual TLS on every link |
| **Criticality** *k* | Number of redundant replicas dispatched for a micro-task |
| **Orchestrator** | The client-side component executing Sections 6 to 11 |
| **Worker** | A node executing Section 12 |

---

## 3. Versioning and conformance

Every message carries a `"v"` field with the protocol version as `MAJOR.MINOR`. A participant MUST reject a message whose MAJOR version it does not implement. A participant MUST ignore unknown fields within a message rather than rejecting it, so that MINOR additions are backwards compatible.

**Conformance classes.**

- A **Conformant Worker** MUST implement Sections 7, 8, 12 and 13, and MUST emit a verification commitment when one is requested.
- A **Conformant Orchestrator** MUST implement Sections 5 to 11 and Section 14, MUST implement the router of Section 6 (a client that always fragments is **non-conformant**), and MUST return a coherence report with every response.
- An implementation that omits the coherence report is non-conformant. This is deliberate: the protocol's usefulness depends on its degradation being observable.

---

## 4. Identifiers and cryptography

**Node identity.** An Ed25519 key pair. `node_id` is the public key, base64url without padding.

**Session identity.** `session_id` is 128 bits from a CSPRNG, generated per request, never reused, and **never transmitted to a worker**.

**Task identity.**

```
task_id    = hex( BLAKE2b(session_id || u16(level) || u16(index), digest_size=16) )
attempt_id = task_id || ":" || u8(attempt_counter)
```

The derivation is one-way so that two colluding workers cannot establish that they hold fragments of the same session by comparing identifiers. This does **not** defeat timing correlation or contract fingerprinting; see Section 16.

**Signatures.** Results MUST be signed with the worker's Ed25519 key over the canonical serialization (RFC 8785 JSON Canonicalization Scheme) of all fields preceding `sig`.

**Transport.** All exchanges MUST occur over an authenticated encrypted channel (TLS 1.3 or Noise). Transport security is orthogonal to the confidentiality limits of Section 15.

---

## 5. Global contract Γ

```json
{
  "v": "0.2",
  "objective":  "string",
  "audience":   "string",
  "register":   "formal|neutral|informal|technical",
  "format":     "prose|markdown|json|code",
  "target_len": 1200,
  "lexicon":    { "prefer": ["…"], "forbid": ["…"] },
  "entities":   [ { "name": "…", "canonical": "…", "role": "…" } ],
  "style_seed": "string",
  "budget":     { "max_out_tokens": 600 }
}
```

`objective`, `register`, `format` and `entities` are REQUIRED; the rest are OPTIONAL.

`entities` is the canonical naming table. Workers MUST use the `canonical` form for any listed entity. This is the primary defence against inconsistent naming across fragments.

`style_seed` is a short fixed phrase all workers are instructed to match in register. It costs few tokens and materially reduces drift.

**Γ MUST NOT be trimmed to meet a context budget.** If `S_target < |Γ|`, the orchestrator MUST reduce the number of micro-tasks instead (Section 9).

**Γ is the dominant term in the context budget and therefore the dominant privacy exposure.** Implementations SHOULD minimize it, and MAY paraphrase it per worker to frustrate fingerprinting, at a cost in cross-fragment consistency.

---

## 6. Router

```json
{ "decomposable": true, "score": 0.87, "threshold": 0.72, "features": { } }
```

The orchestrator MUST evaluate decomposability before planning and MUST have a path that declines to fragment. Tier classification (Section 15c) MUST precede decomposability evaluation: a request classified `LOCAL` is never routed.

`threshold` MUST be calibrated with an asymmetric objective (F_β, β < 1) so that erroneous fragmentation is penalized more heavily than erroneous refusal. A hard-coded symmetric threshold is non-conformant.

Features SHOULD include: task-kind signals; request length; density of sequential-dependency markers; presence of shared mutable state; and whether the request asks for a single artifact or a set of items.

---

## 7. Plan

```json
{
  "v": "0.2",
  "nodes": [ { "task_id": "…", "level": 0, "instruction": "…",
               "kind": "extract|classify|generate|summarize|transform|judge",
               "criticality": 1, "lane": "PUBLIC" } ],
  "edges": [ { "from": "…", "to": "…", "type": "result|statement" } ]
}
```

An edge of type `result` means the target requires the *output* of the source and MUST be scheduled after it. An edge of type `statement` means the target requires only knowledge that the source exists, and MAY be scheduled concurrently.

The plan MUST be acyclic. The orchestrator MUST refuse to fragment when the plan width is 1 at every level (a chain is not parallelizable), and SHOULD refuse when depth exceeds 4.

Default maximum width is 8. Width increases the straggler tail (Section 11).

---

## 8. Packet

```json
{
  "v": "0.2",
  "attempt_id": "…",
  "contract": { },
  "predecessors": [ { "task_id": "…", "summary": "…", "tokens": 128 } ],
  "task": { "instruction": "…", "kind": "generate",
            "expects": { "format": "markdown", "min_tokens": 80, "max_tokens": 400 } },
  "constraints": { "temperature": 0.2, "top_p": 0.95, "stop": [] },
  "commitment_request": { "scheme": "lsh-activation-v1", "params": { "window": 32 } },
  "deadline_ms": 20000,
  "lane": "PUBLIC",
  "tier": "GLOBAL",
  "swarm_id": null
}
```

A packet with `lane` of `SENSITIVE` MUST NOT be transmitted to a node outside the attested set (Section 15). An orchestrator that emits one is non-conformant.

`tier` is orthogonal to `lane`: `lane` classifies the content, `tier` names the population of workers the packet may reach (Section 15c). `tier` defaults to `GLOBAL`. A packet with `tier` of `TRUSTED` MUST carry a non-null `swarm_id` and MUST NOT be offered to a node absent from that swarm's whitelist. Requests classified `LOCAL` are never serialized as packets.

`predecessors[].summary` carries results, not raw upstream packets. Summaries MUST be produced locally by the orchestrator.

---

## 9. Packing and the context budget

```
S           = |Γ| + E[ Σ |predecessors[].summary| ]
ρ           = ( Σᵢ |Kᵢ| ) / |P|
ρ_floor     = ( Σᵢ ( |taskᵢ| + |Γ_min| + |carryᵢ| ) ) / |P|
```

The orchestrator MUST report the achieved ρ **and** ρ_floor in the response metadata.

### 9.1 Mandatory content: what a packet minimally is

Three parts of a packet are **mandatory**. They are counted into ρ_floor and are
never funded out of discretionary slack, never trimmed, and never dropped:

1. **The micro-task block.** A packet without its task is not a packet.
2. **The contract header `Γ_min`** — the minimal rendering of Γ (Section 5).
   A fragment scored against a contract it never received measures the
   contract's *absence*, not the cost of fragmenting. This is the same
   requirement as the prohibition in Section 5 on trimming Γ, stated on the
   packing side.
3. **The carry**, for a dependent micro-task that *consumes a predecessor's
   value*. A task whose text says "divide the net value from step 2" cannot be
   answered without that value. A packet that cannot state the value its task
   consumes is **unanswerable by construction**, and no fragment size repairs
   it; **answerability outranks the budget.** So the carry is added to ρ_floor
   on the same footing as the task text, rather than competing for slack with
   the glossary as ordinary context.

The carry is mandatory on the basis of the **micro-task text**, not the plan's
shape. An enumerated plan of independent items is sequential in form but
consumes nothing, and forcing predecessor output into packets with no use for
it makes the successor restate it as its own. Implementations MUST gate the
mandatory carry on whether the task consumes a predecessor value, and SHOULD
use a typed carry (`[02]=2247`) rather than a prose summary: it is the same
guarantee at a small fraction of the tokens, which is what makes the mandatory
carry affordable rather than a new tax on ρ.

Everything else — the length note, non-consumed predecessor summaries, the
glossary, the forbidden-term list, and deterministic expansion material at high
ρ — is **discretionary context**, attached in priority order from whatever
remains.

### 9.2 Packing algorithm (normative)

Let *B* = ρ_target · |P| be the total budget for the tasks being dispatched.

1. Compute `mandatoryᵢ` for each micro-task: task block + `Γ_min` + carry
   (Section 9.1).
2. Compute `ρ_floor`. If `ρ_target < ρ_floor`, the cell is **unreachable**:
   record `rho_reachable = false` and apply Section 9.3. The orchestrator MUST
   NOT satisfy an unreachable target by trimming mandatory content; it either
   proceeds at the floor or reduces the micro-task count and re-plans.
3. `slack ← max(0, B − Σᵢ mandatoryᵢ)`.
4. Allocate `budgetᵢ ← mandatoryᵢ + slack · desiredᵢ / Σⱼ desiredⱼ`, where
   `desiredᵢ` is the tokens packet *i* would consume with no rationing at all.
   A uniform `B / N` split is non-conformant: it starves exactly the packets
   that carry dependencies.
5. For each packet, set its own budget to `max(mandatoryᵢ, budgetᵢ)`, emit the
   mandatory content, then attach discretionary blocks in priority order while
   room remains, truncating the first block that does not fit at a token
   boundary and stopping there.
6. When a plan is dispatched in topological levels, each level MUST be
   allocated at least the sum of its own `mandatoryᵢ`, and `desiredᵢ` MUST be
   computed once from the plan alone. Recomputing it per level lets a late
   integration node claim slack an earlier level already reserved, which
   overshoots ρ_target by exactly that amount and grows with *N*.
7. Run a bounded correction pass to absorb the residue left by atomic block
   boundaries, then verify the invariants of Section 9.4.

Implementations SHOULD prefer fewer, larger fragments over many small ones when
the budget binds.

### 9.3 A below-floor cell is not a measurement of ρ

Below ρ_floor there is no context to ration: every packet collapses to its
mandatory content, so **two different ρ labels produce byte-identical packets.**
A cell whose target is below its own floor therefore carries no information
about ρ at all, whatever value its label names, and a curve drawn through such
cells reports that packets holding nothing score worse than packets holding
something — a true statement about content, and not a measurement of the context
budget.

Accordingly:

- An implementation MUST record `rho_reachable` per cell, from a floor that
  includes the contract header and any mandatory carry.
- An implementation **MUST refuse to report a ρ-indexed figure computed from a
  below-floor cell** — including any aggregate, mean, trend or verdict over a
  set of cells that contains one. Dropping the row is conformant; annotating it
  and publishing it anyway is not.
- An implementation MUST NOT report `rho_reachable = true` from an optimistic
  floor that omits a carry which will exist by dispatch time.

### 9.4 Invariants (normative)

Before dispatch, and for every reachable cell, the orchestrator MUST refuse to
proceed unless all three hold:

1. Every packet contains its contract header.
2. Every micro-task that consumes a predecessor value, and whose dependency has
   produced a summary, carries it.
3. Achieved ρ is within a declared tolerance of ρ_target (the reference
   implementation uses 5 %). ρ is the independent variable; a cell outside
   tolerance is not the cell its label names.

A violation is a refusal to dispatch, not a warning. These checks are waived
for an **unreachable** cell, whose packets are at the floor by definition and
whose achieved ρ necessarily overshoots the target it could not meet; such a
cell may still be dispatched, and Section 9.3 governs what may be reported
from it. Waiving the check is not permission to publish the cell.

---

## 10. Result

```json
{
  "v": "0.2",
  "attempt_id": "…",
  "text": "…",
  "profile": { "model_family": "…", "model_version": "…", "quantization": "…",
               "prompt_template_id": "…", "sampling_params": { }, "seed": 0 },
  "commitment": { "scheme": "lsh-activation-v1", "digest": "base64", "bytes": 258 },
  "telemetry": { "gen_ms": 0, "queue_ms": 0, "tokens_out": 0, "energy_j": null },
  "sig": "base64"
}
```

The worker MUST report the profile it actually used. The commitment binds the declared profile to the computation; a mismatch is a verification failure, not a formatting error.

`energy_j` is OPTIONAL and nullable; most consumer hardware cannot report it.

---

## 11. Dispatch, hedging and retry

1. **Filter** candidates by `tier` first — a packet with `tier` of `TRUSTED` is offered only to nodes whose `node_id` appears in the whitelist of the swarm named by `swarm_id`, over a mutually authenticated channel — and then by declared `kind` support, capability class, and observed RTT.
2. **Select** `k` nodes for a task of criticality `k`, **maximizing model-family diversity** subject to the capability class. Candidate diversity is what makes selection effective; implementations MUST NOT collapse replicas onto a single model family when alternatives are available.
3. **Hedge.** Start a timer at the observed **p95** of the latency distribution *for that task kind and token budget*. On expiry, dispatch an additional replica. Accept the first result that verifies. A fixed timeout is non-conformant: with per-node failure probability *p* and width *W*, `P(≥1 failure) = 1 − (1−p)^W`, which at *p*=0.10, *W*=20 is 88 %, so a fixed timeout lands on the critical path routinely.
4. **Cancel** outstanding replicas on acceptance, and record the cancellation as *slow*, not *dishonest*. Reputation MUST distinguish these.
5. **Retry** on verification failure, excluding the failing node, and report the event to the audit sampler.

---

## 12. Node profile advertisement

```json
{
  "node_id": "base64url",
  "models": [ { "family": "…", "version": "…", "quantization": "…",
                "ctx": 8192, "tok_per_s_est": 42.0 } ],
  "capabilities": { "tee": false, "attestation": null },
  "swarm": { "swarm_id": null, "registry": null, "mtls_cert_fingerprint": null },
  "resources": { "vram_mb": 8192, "ram_mb": 32768 },
  "policy": { "max_tokens_per_task": 800, "kinds": ["extract", "generate"] },
  "reputation": { "completed": 0, "audit_pass_rate": 0.0, "since": "2026-08-13T00:00:00Z" }
}
```

A node MUST NOT accept a task whose `kind` is absent from `policy.kinds` or whose `expects.max_tokens` exceeds `policy.max_tokens_per_task`.

Reputation is advisory and is computed by the orchestrator and the registry independently; a node's self-reported reputation MUST NOT be trusted.

`swarm` is OPTIONAL and absent for a node serving only the global mesh. A self-declared `swarm_id` confers nothing: membership is established by the swarm registry's whitelist and by the mutually authenticated channel, never by the advertisement (Section 15c).

---

## 13. Verification

**Layer 1 — commitment (REQUIRED when requested).** The worker computes a locality-sensitive commitment over activations and returns a digest bound to the declared profile. The orchestrator validates before the result may enter assembly. Target cost: ~258 bytes per 32 tokens, with validation faster than the original generation.

**Layer 2 — sampled audit (REQUIRED of the network).** A fraction λ of tasks is re-executed by an auditor. Audit tasks MUST be **indistinguishable** from real tasks from the worker's perspective — same format, same identifiers, same latency envelope. Default λ ∈ [0.01, 0.05]. Failure probability under a corruption rate ρ_c and committee size *k* is approximately `ρ_c^k`.

**Layer 3 — selection (implicit).** With `k > 1`, the judge-based selection of Section 14 discards anomalous candidates as a side effect.

**What verification does NOT provide.** Layers 1–3 establish that a declared model was run on a declared input and that the result is not an outlier. They do **not** establish semantic faithfulness or absence of malicious content. Accordingly:

- Fragments are **data, never instructions**. Orchestrators MUST NOT allow fragment text to alter Γ, the plan, or dispatch behaviour.
- `kind`-specific output schemas MUST be validated before a fragment enters the assembly context.
- Standard LLM application-security controls apply to the assembly step.

---

## 14. Assembly

1. Flatten the plan topologically.
2. For each micro-task with one candidate, take it. With several, **select** one by judge score against Γ. Synthesis across candidates is NOT the default path.
3. For each consecutive pair, embed the tail window of the left and the head window of the right and compute cosine similarity.
   - `sim ≥ τ_sem` → splice directly.
   - `sim < τ_sem` → generate a transition bridge with the local model, given both boundaries and Γ.
4. Record every seam: the pair, the similarity, and the path taken.

**τ_sem MUST be calibrated, never fixed.** Calibration uses labelled seam/non-seam pairs, maximizing F_β with β < 1, and MUST be re-derived whenever the embedding model changes. An implementation shipping a hard-coded cosine threshold is non-conformant. Rationale: contextual embedding spaces are anisotropic, cosine values are not comparable across models, and no canonical threshold exists in the literature.

---

## 14b. Consensus by multiple alignment

Section 14 resolves *different* fragments at *different* positions. This section resolves *k* replicas of the *same* micro-task.

1. For a micro-task of criticality `k > 1`, the orchestrator MUST resolve the replicas by multiple alignment at semantic-unit granularity. It MUST NOT simply concatenate the replicas, and MUST NOT pick one arbitrarily.
2. Replicas MUST be dispatched to nodes of different `model_family` wherever the candidate pool allows it. The response MUST report which families contributed.
3. The response MUST include a per-unit agreement score, and MUST label each unit `HIGH`, `MEDIUM` or `LOW` against the calibrated thresholds α_high and α_low.
4. **α_high and α_low MUST be calibrated per embedding model, exactly as τ_sem is.** An implementation shipping hard-coded agreement thresholds is non-conformant.
5. Units scoring below α_low MUST be surfaced to the user as low-confidence regions. Suppressing them is non-conformant.
6. **An implementation MUST NOT present an agreement score as an accuracy or truthfulness score.** Agreement among replicas is evidence of convergence, not of correctness; models sharing training data share errors.
7. **Splitting an atomic request into partial sub-requests is NOT a supported operation.** An orchestrator that does so is non-conformant. Rationale: it removes information prior to sampling, and redundancy cannot recover information that was removed before sampling.

---

## 15. Sensitivity lanes

| Lane | Criterion | Permitted destinations |
|---|---|---|
| `PUBLIC` | No PII, no commercial secret | Any conformant worker |
| `SANITISABLE` | PII detectable and pseudonymizable | Any conformant worker, after local pseudonymization; rehydrated locally at assembly |
| `SENSITIVE` | Health, legal, financial, identifiable | Local execution, or a worker presenting valid TEE attestation |

Classification MUST run before any packet leaves the device. Pseudonymization mappings MUST NOT leave the device.

**Implementations MUST NOT describe fragmentation as encryption in user-facing text.** The SANITISABLE lane reduces risk; it does not eliminate it, and interfaces SHOULD say so.

---

## 15b. Anchor nodes

During bootstrap the network MAY include foundation-operated rented capacity.

1. Such nodes MUST be labelled `anchor: true` in the registry.
2. The network MUST publish the share of traffic served by anchor nodes.
3. **Presenting anchor-served traffic as community-served is non-conformant.**

---

## 15c. Privacy tiers and trusted swarms

**Classification.** Every request MUST be assigned a tier before planning, by a classifier that runs entirely on the requesting device. A classifier that consults the network in order to decide whether a request is private is non-conformant.

1. A **manual flag** (`--privacy=trusted`, `--privacy=local`) is authoritative and MUST NOT be overridden or downgraded by automatic triage.
2. **Automatic triage** MAY raise a tier on local named-entity detection of regulated classes. It MUST NOT lower one.
3. Implementations MUST NOT present automatic triage as certifying the absence of sensitive content. It raises a tier; it does not clear one.

**Tiers.**

| Tier | Population | Transport | Permitted lanes |
|---|---|---|---|
| `GLOBAL` | Any conformant worker in the open registry | Authenticated worker identity; server-side TLS | `PUBLIC`, `SANITISABLE` |
| `TRUSTED` | Only nodes on the named swarm's public-key whitelist | **Mutual TLS REQUIRED** on every link | `PUBLIC`, `SANITISABLE`, and `SENSITIVE` where swarm policy and applicable law permit |
| `LOCAL` | The requesting device only | No network egress | All, unconditionally |

**Trusted-swarm requirements.**

1. Swarm membership MUST be a whitelist of node public keys held by a swarm registry under a declared operator. A node's self-declaration of membership MUST be ignored.
2. Every link inside a trusted swarm MUST use mutual TLS. A link that authenticates only one endpoint is non-conformant for `tier` of `TRUSTED`.
3. The commitment of Section 13, Layer 1 remains **REQUIRED** inside a trusted swarm. Mutual TLS authenticates an identity, not the model behind it, and membership MUST NOT be accepted as evidence that a declared profile was served.
4. A trusted swarm MAY relax Layer 2 sampled audit and MAY reduce criticality *k*. It MUST NOT relax Layer 1.
5. A trusted swarm MAY set `k = 1`. When it does, the response metadata MUST report `consensus: null` with `consensus_waived_reason: "trusted_swarm_k1"`, and the client MUST surface the absence of a confidence map rather than render an empty or default-high one. Reporting a confidence map that was not computed is non-conformant.
6. Notwithstanding rule 5, `k` MUST be at least 2 whenever the swarm's measured loss rate *p* exceeds the configured tolerance ε, since `c_eff = c(1 − p)` leaves no margin at `c = 1`.
7. The latency headroom of a trusted swarm MUST NOT be spent on a finer-grained partitioning scheme. A conformant implementation runs the same protocol at every tier and spends the headroom on the context budget *S* of Section 9.

**Trust boundary.** A trusted swarm relocates trust to the whitelist operator. Whoever administers the registry can admit a node; a compromised member inside the perimeter is more dangerous than an untrusted node outside it, because the redundancy that would have detected it may have been reduced under rule 5. Implementations MUST NOT describe a trusted swarm as removing the need to trust anybody.

---

## 16. Known residual channels

Declared rather than concealed:

1. **Timing correlation.** Fragments of one session are dispatched in a burst. The one-way `task_id` derivation does not hide this. Mitigation: jittered dispatch, at a cost in latency.
2. **Contract fingerprinting.** A distinctive Γ is itself a session identifier across the workers receiving it. Mitigation: per-worker paraphrase, at a cost in consistency.
3. **Content inference.** A single micro-prompt may be sensitive on its own regardless of the absence of global context.
4. **Sybil concentration.** See Section 17.

---

## 17. Trust model

- Workers are **untrusted** and assumed rational rather than merely faulty.
- The orchestrator is trusted by its own user only.
- The registry is **semi-trusted**: it MAY censor or bias discovery; orchestrators SHOULD use more than one and SHOULD retain a local view.
- Inside a `TRUSTED` swarm, workers are **authenticated and accountable but still not verified**: the whitelist bounds *who* may serve, not *what* they served. Section 13 Layer 1 therefore applies at every tier.
- **Sybil resistance is not provided.** Layered mitigation only: accumulated reputation, cost of entry, sampled audit with economic penalty, and foundation-operated anchor nodes for cold start. Implementations MUST NOT claim Byzantine or Sybil resistance.

---

## 18. Credits

Non-transferable, non-premined, expiring. Earned by a verified accepted fragment; spent by submitting a request. No secondary market and no account-to-account transfer. Balances expire on a published schedule.

```json
{ "node_id": "…", "balance": 0, "earned_total": 0, "spent_total": 0,
  "expires": [ { "amount": 0, "at": "ISO-8601" } ] }
```

Fiat conversion is unidirectional: enterprises purchase capacity through a commercial service layer; volunteers do not sell credits. The design intent is to remain outside securities and crypto-asset regimes; it is a design goal, **not legal advice**, and requires counsel in the operating jurisdiction.

---

## 19. Response metadata

Every response MUST include:

```json
{
  "rho_achieved": 1.47,
  "rho_target": 1.50, "rho_floor": 1.31, "rho_reachable": true,
  "n_tasks": 6, "n_levels": 2,
  "tau_sem": 0.71, "tau_source": "calibrated:2026-08-13:e5-base",
  "seams": [ { "left": "…", "right": "…", "similarity": 0.68, "path": "bridge" } ],
  "coherence": { "entity_grid": 0.31, "seam_free_sentence_fraction": 0.94,
                 "errors": { "entity_omission": 0, "duplicated_content": 1 } },
  "verification": { "commitments_checked": 6, "failures": 0, "audited": 1 },
  "consensus": {
    "k": 3, "families": ["…", "…", "…"], "mean_agreement": 0.0,
    "units": [ { "label": "HIGH|MEDIUM|LOW", "agreement": 0.0 } ],
    "low_confidence_regions": [ { "unit_index": 0, "agreement": 0.0 } ]
  },
  "coverage": { "c": 0.0, "p_observed": 0.0, "c_eff": 0.0,
                "expected_uncovered_fraction": 0.0 },
  "routing": { "tier": "GLOBAL|TRUSTED|LOCAL", "swarm_id": null,
               "classifier": "manual|auto", "mtls": false },
  "consensus_waived_reason": null,
  "nodes": [ { "family": "…", "version": "…", "role": "worker" } ]
}
```

Omitting `coherence` is non-conformant. Omitting `consensus` when `k > 1` is non-conformant. Omitting `routing` is non-conformant. When `consensus` is `null` because the swarm reduced *k* to 1, `consensus_waived_reason` MUST state why (Section 15c, rule 5).

Omitting `rho_floor` or `rho_reachable` is non-conformant. Without them a consumer of the response cannot tell whether the cell measured the context budget at all, which is the condition Section 9.3 turns on.

---

## 20. Error codes

| Code | Meaning | Orchestrator action |
|---|---|---|
| `E_KIND_UNSUPPORTED` | Worker does not serve this `kind` | Re-dispatch elsewhere; not a fault |
| `E_BUDGET_EXCEEDED` | `max_tokens` above node policy | Re-dispatch or re-plan |
| `E_DEADLINE` | Deadline passed | Hedge already fired; count as slow |
| `E_COMMITMENT_UNSUPPORTED` | Scheme unknown to worker | Downgrade to redundancy, or exclude |
| `E_VERIFY_FAILED` | Commitment mismatch | Exclude node; report to audit sampler |
| `E_SCHEMA` | Output violates `expects` | Retry once, then exclude |
| `E_LANE_VIOLATION` | Sensitive packet offered to open node | **Abort the request.** Implementation defect |
| `E_TIER_VIOLATION` | `TRUSTED` packet offered to a node absent from the swarm whitelist | **Abort the request.** Implementation defect |
| `E_MTLS_REQUIRED` | Trusted-swarm link presented without mutual authentication | Refuse the node; report to the swarm registry |
| `E_SWARM_UNKNOWN` | `swarm_id` not resolvable in any configured registry | Abort; do not fall back to `GLOBAL` |

---

## 21. Open questions for v1.0

1. The commitment scheme is specified by interface, not by construction; `lsh-activation-v1` needs a normative definition or a normative reference.
2. Registry federation and censorship resistance are unspecified.
3. Credit expiry schedule and audit penalty magnitudes are unset pending the economics of a live network.
4. Contract compression is the highest-leverage open problem: because Γ is simultaneously the coherence mechanism, the privacy exposure and the dominant cost term, any reduction in `|Γ|` at equal effect improves three properties at once.
5. Whether the orchestrator can be an 8B-class model at acceptable quality is unresolved and is the subject of hypothesis H3 in the whitepaper.
6. The granularity of a semantic unit — sentence versus clause — is unresolved, and it materially affects both alignment quality in Section 14b and the parameters of the coverage model.
7. The correlation between the agreement score of Section 14b and factual accuracy has now been measured, and **no relationship was found.** Against a peer-class judge it came back at *r* = −0.030 over 597 semantic units; three subsequent runs graded against an answer key put the Mantel-Haenszel common odds ratio at 3.47, then 0.26, then 1.24 — above, below and astride 1 on the same question, which is no signal measured three times. The confidence map is therefore **withdrawn** as a reliability claim, and it is dropped from the V7 benchmark. The mechanism of Section 14b remains specified and MAY be reported, but an implementation MUST report its output as *agreement* and MUST NOT present it as accuracy, confidence or a reliability guarantee. What remains open is not whether the correlation is there, but whether any per-unit signal of this kind can be recovered at all; a new instrument, not a re-run of this one, is the precondition for reopening it.
8. Trusted-swarm registry federation, key rotation and revocation latency are unspecified. Until they are, the failure mode of rule 1 in Section 15c is a stale whitelist rather than an unauthenticated one.
9. Whether a client-side named-entity triage model small enough to run on the requesting device reaches acceptable recall on regulated entity classes is unmeasured, and the manual flag exists because it is unmeasured.

---

*Specification v0.2 (revision 2), 14 August 2026. Normative for the reference implementation in `swarmbly_v0/`. Rationale, evidence and citations: `WHITEPAPER_EN.md`.*
