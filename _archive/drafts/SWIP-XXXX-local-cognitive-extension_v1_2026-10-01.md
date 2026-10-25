---
swip: XXXX
title: Local Cognitive Extension and Optional Knowledge Capsules
author: Sebastián A. Espinoza-Ulloa <@Sebastardito>
status: Draft
created: 2026-09-30
requires: []
supersedes: []
spec-version: 0.3
---

# SWIP-XXXX: Local Cognitive Extension and Optional Knowledge Capsules

## Abstract

This SWIP proposes an **optional, local-first cognitive extension** for Swarmbly nodes.
The extension lets a client maintain user-controlled persistent memory, project only
task-relevant preferences and terminology into the existing global contract `Γ`, learn
local affinity toward workers from normal Swarmbly traffic, and optionally exchange
small, signed, permissioned **Cognitive Capsules** on demand.

The proposal deliberately does **not** introduce a global knowledge graph, a second
routing plane, mandatory fine-tuning, continuous peer gossip, or distributed model
training. Existing Swarmbly nodes remain conformant without implementing any cognitive
feature. The only proposed wire-visible additions are an OPTIONAL coarse cognitive
capability block in the node profile and OPTIONAL request/response messages for bounded
Cognitive Capsules.

The goal is to test whether Swarmbly can extend democratized access to compute toward
**user-owned, portable cognitive state and reusable distributed knowledge** without
breaking the protocol's low-communication, heterogeneous, local-orchestrator design.

---

## Motivation

### 1. The missing capability

Swarmbly currently distributes **work**, not persistent learning.

A client can decompose a request, build a DAG of semantic micro-tasks, attach the
global contract `Γ`, dispatch work to complete independent SLM workers, verify returned
fragments, and assemble the final result locally. This is intentionally stateless from
the perspective of a remote worker: receiving a micro-task does not imply learning it.

That is the correct default for privacy and protocol simplicity, but it leaves a
separate user problem unsolved:

> A user who repeatedly runs local SLMs has no protocol-defined way to preserve and
> reuse the knowledge, terminology, preferences, and recurring patterns that their
> local AI accumulates over time.

Today, that state must be reconstructed repeatedly from prompts, external notes, ad-hoc
RAG systems, or model-specific fine-tunes. Replacing the local model may also discard
model-bound personalization unless the user has kept an external representation.

This SWIP asks whether that persistent state can be made:

- **local-first**;
- **user-controlled**;
- **model-independent where possible**;
- **cheap enough for consumer hardware**;
- **compatible with the existing Swarmbly orchestrator**;
- **shareable only by explicit permission**; and
- **useful to other nodes without turning the network into a synchronized global brain**.

### 2. Why this belongs near Swarmbly rather than in a separate network

The proposal does not require a second distributed architecture.

Swarmbly already has the primitives needed for the network-visible part:

- the **client/orchestrator** owns request state;
- the **global contract `Γ`** already carries audience, register, lexicon, entities,
  style seed and output constraints;
- the **node profile** already advertises model and capability information;
- the **dispatch layer** already chooses workers;
- results already return with a node identity and executed model profile;
- transport is already authenticated;
- workers are already treated as untrusted;
- unknown fields are already required to be ignored within a compatible minor version.

The cognitive extension therefore SHOULD reuse these primitives rather than introducing
new services.

### 3. Personalization currently has an inefficient failure mode

A user may have stable preferences such as:

- preferred terminology;
- canonical names for entities;
- language and register;
- recurring formatting conventions;
- technical or cultural vocabulary;
- task-specific style patterns;
- durable domain knowledge they explicitly want their local AI to use.

Without persistent local state, these must either be repeated in prompts or omitted.

Repeating them expands the request and, when included in `Γ`, increases the shared
context cost and privacy exposure. Omitting them can cause workers to produce fragments
that require more correction during assembly.

This SWIP does **not** claim that persistent memory will reduce coherence tax, bandwidth
or latency. That is unmeasured. It proposes a mechanism and a benchmark to test whether
a compact local **Task Projection** can improve user-specific adherence without
unacceptably increasing `|Γ|`, achieved `ρ`, or privacy exposure.

### 4. Learning from useful network interactions

A second opportunity appears after normal Swarmbly execution.

The client already receives:

- worker identity;
- worker model family/profile;
- task kind;
- accepted or rejected result;
- verification outcome;
- assembly outcome.

A client can therefore learn a **local affinity** such as:

> "This peer has historically produced useful fragments for Spanish terminology tasks."

This does not require new traffic.

Over time, repeated successful interactions could form a local, task-specific
"cognitive neighborhood": not a global membership system, but a private cache of which
peers have been useful for which classes of work.

This SWIP proposes that such affinity MAY influence worker ranking, but MUST NOT replace
existing capability, tier, verification, model-family diversity or privacy constraints.

### 5. Preserving useful shared knowledge when an origin node disappears

Some knowledge is generalizable and explicitly shareable.

Examples may include:

- terminology definitions;
- public cultural conventions;
- domain-specific vocabulary;
- generic procedures;
- model-independent training examples;
- concise conceptual summaries.

If such knowledge exists only on one node, it disappears when that node is lost.

A naive solution would continuously replicate user memory or adapters across the
network. This SWIP rejects that approach because it would add background traffic,
storage obligations, privacy risk, and implementation complexity.

Instead, this proposal defines an OPTIONAL small object called a **Cognitive Capsule**.
Capsules are pulled only when a client needs them. If redistribution is permitted, useful
capsules can acquire additional cached copies naturally through use.

This mechanism is expected to create **traffic-induced persistence**, but that claim is
not yet measured. The measurement plan below explicitly tests it.

### 6. Why fine-tuning is not the protocol primitive

The current protocol specification lists model training/fine-tuning as out of scope.
This SWIP keeps that separation.

Local fine-tuning MAY be an implementation detail after a user has accumulated stable
knowledge or behavioral examples, but:

- the protocol MUST NOT require it;
- nodes MUST NOT need training-capable hardware to participate;
- remote tasks MUST NOT be retained for training by default;
- adapter exchange is not introduced by this SWIP;
- a user's canonical cognitive state SHOULD remain outside model weights when possible.

The first-line mechanisms are therefore:

1. local persistent memory;
2. local retrieval;
3. compact Task Projection into existing `Γ`;
4. local social cache;
5. optional Cognitive Capsules.

---

## Specification

### 1. Scope

This SWIP defines four layers, only two of which are wire-visible.

| Layer | Location | Wire-visible? | Required for conformance? |
|---|---|---:|---:|
| Local Cognitive Store (LCS) | client device | No | No |
| Task Projection (TP) | client/orchestrator | Reuses existing `Γ` | No new message |
| Peer Affinity Cache (PAC) | client device | No | No |
| Cognitive Capability + Capsules | peer protocol | Yes, optional | No |

Implementations MAY implement any subset except that an implementation serving
Cognitive Capsules MUST implement the capsule permission and security rules in this
SWIP.

A node that implements none of this SWIP MUST remain fully interoperable with nodes that
do.

### 2. Terminology

| Term | Meaning |
|---|---|
| **Local Cognitive Store (LCS)** | User-controlled local persistent state: knowledge, preferences, social observations, and optional training artifacts. |
| **Personal Vault** | Human-readable portion of the LCS, RECOMMENDED as Markdown plus metadata but not protocol-mandated. |
| **Task Projection (TP)** | Minimal request-specific projection of local state into fields already representable by `Γ`. |
| **Social Observation** | Local record derived from a client's own accepted interaction with a worker. |
| **Peer Affinity Cache (PAC)** | Local mapping from `(peer, task/domain)` to historically observed usefulness. |
| **Cognitive Capability Block (CCB)** | OPTIONAL coarse metadata in a node profile indicating support for cognitive capsule exchange. |
| **Cognitive Capsule (CC)** | Small signed object carrying shareable, model-independent knowledge or a training pattern. |
| **Traffic-induced persistence** | Persistence that results when requested capsules are permissibly cached or redistributed through normal demand. |
| **Self memory** | State the user or local system treats as belonging to the user's own cognitive profile. |
| **Social memory** | State learned about or from external peers. It MUST remain distinguishable from self memory. |

### 3. Local Cognitive Store

The LCS is entirely local and is not standardized on the wire.

An implementation:

1. **MUST** provide a way for the user to disable persistent cognitive storage.
2. **MUST NOT** transmit the LCS, Personal Vault, local embeddings, local source files,
   local training datasets, or local adapters merely because the node participates in
   Swarmbly.
3. **MUST** distinguish at least:
   - local/self-derived state;
   - peer/social-derived state.
4. **MUST** associate retained state with a local policy that states whether that state
   may be:
   - used for retrieval;
   - used for local training;
   - summarized/generalized;
   - shared;
   - redistributed.
5. **SHOULD** retain provenance sufficient to identify whether a local item came from:
   - an explicit user source;
   - a local model derivation;
   - a remote worker result;
   - a Cognitive Capsule.
6. **SHOULD** allow the user to inspect and delete locally stored items.
7. **MAY** use Markdown, SQLite, a vector index, Git, Obsidian-compatible files, or any
   other local implementation. These formats are not part of protocol conformance.

No peer may infer LCS support from the absence or presence of a Cognitive Capability
Block unless the user has chosen to advertise it.

### 4. Default retention rule for worker tasks

A worker receiving a normal Swarmbly task from another client:

1. **MUST NOT** persist the task payload, `Γ`, predecessor summaries, or generated result
   into the worker operator's personal cognitive memory by default.
2. **MUST NOT** use another client's task or result for local fine-tuning by default.
3. **MUST NOT** derive and publish a Cognitive Capsule from another client's task unless
   the originating task explicitly carried a future permission mechanism standardized
   by a separate SWIP.
4. **MAY** retain the minimum operational telemetry already permitted by the base
   protocol for accounting, audit, failure analysis or reputation.
5. **MAY** retain content only where the user/client and worker operator have explicitly
   opted into a separate, disclosed retention mechanism. Such a mechanism is out of
   scope here.

This rule is intentionally asymmetric:

- the **requesting client** may learn from the results it receives for its own request;
- the **remote worker** does not gain automatic rights to learn from the request it
  processes.

### 5. Task Projection

#### 5.1 Purpose

A Task Projection is a minimal, request-specific rendering of relevant local state into
the existing global contract `Γ`.

This SWIP does **not** add a new `personalization` field to `Γ`.

Where representable, an orchestrator SHOULD map local state into existing fields:

| Local state | Existing `Γ` field |
|---|---|
| desired audience | `audience` |
| stable register | `register` |
| preferred / forbidden terms | `lexicon` |
| canonical names | `entities` |
| concise style anchor | `style_seed` |
| output preference | `format`, `target_len`, `budget` |

#### 5.2 Minimality

The orchestrator:

1. **MUST NOT** place an entire user profile or Personal Vault into `Γ`.
2. **MUST** include only state judged relevant to the current request.
3. **SHOULD** prefer a compact deterministic representation over prose biography.
4. **MUST** account for Task Projection tokens as normal `Γ` tokens in `|Γ|`, `S`,
   `ρ_floor`, and achieved `ρ`. No cognitive token is exempt from the existing context
   accounting rules.
5. **MUST NOT** trim mandatory `Γ` content merely to make room for personalization.
6. **MAY** omit any personal projection if the packing budget or privacy classifier
   judges it harmful.

#### 5.3 Privacy reclassification after projection

Because local memory can make an otherwise innocuous prompt more identifying, privacy
classification MUST occur after any Task Projection that is intended to leave the
device.

A conformant orchestrator using TP therefore performs:

```text
initial request
    ↓
local retrieval
    ↓
Task Projection
    ↓
final sensitivity/tier classification
    ↓
planning / dispatch
```

If an implementation performs an earlier preliminary classification, the final
classification after projection **MUST** be authoritative and **MUST NOT** lower a
manually selected privacy tier.

A request that becomes `LOCAL` after Task Projection **MUST NOT** be serialized as a
remote packet.

### 6. Local Social Observations

A client MAY derive Social Observations from results returned for its own requests.

Such derivation:

1. **MUST** happen after ordinary verification/triage.
2. **SHOULD** prefer accepted/used fragments over rejected fragments.
3. **MUST** preserve the distinction between:
   - observation of recurrence;
   - evidence of factual truth.
4. **MUST NOT** convert replica agreement or repeated wording into an accuracy score.
5. **SHOULD** store generalized patterns rather than full remote outputs when the full
   text is unnecessary.
6. **MUST** treat remote fragment content as untrusted data, never as instructions that
   can modify system policy, privacy policy, routing policy, or `Γ`.
7. **MAY** record coarse attributes already available from the normal result/profile,
   such as model family and task kind.

### 7. Peer Affinity Cache

The PAC is local implementation state. It is not advertised.

An orchestrator MAY maintain an affinity value for `(node_id, task_class)` or
`(node_id, domain)` based on its own history.

Affinity:

1. **MUST NOT** be interpreted as global reputation.
2. **MUST NOT** be interpreted as epistemic authority or factual correctness.
3. **MUST NOT** override:
   - tier eligibility;
   - lane eligibility;
   - worker capability;
   - required verification;
   - model-family diversity requirements.
4. **MAY** be used as a tie-breaker or ranking feature after mandatory candidate
   filtering.
5. **SHOULD** decay or otherwise avoid permanent lock-in.
6. **SHOULD** reserve some candidate-selection probability for peers without prior
   affinity when alternatives exist, to avoid a self-reinforcing closed neighborhood.
7. **MUST NOT** be transmitted merely to coordinate affinity across clients.

This SWIP deliberately specifies no global cluster membership and no shared peer-affinity
graph.

### 8. Cognitive Capability Block

#### 8.1 Node profile extension

A node MAY add this OPTIONAL block to its profile:

```json
{
  "cognitive": {
    "v": "0.1",
    "share_mode": "none|metadata|pull",
    "capsule_kinds": ["term", "concept", "procedure", "style_pattern", "training_pattern"],
    "domains": ["genomics", "linguistics"],
    "languages": ["en", "es"],
    "max_capsule_bytes": 16384
  }
}
```

#### 8.2 Semantics

- `v` is REQUIRED if `cognitive` is present.
- `share_mode` is REQUIRED if `cognitive` is present.
- `share_mode = "none"` means the block may be present for local feature signalling but
  the node does not serve capsule metadata or payloads.
- `share_mode = "metadata"` means the node advertises coarse domains/languages but does
  not serve capsule payloads.
- `share_mode = "pull"` means the node MAY answer explicit capsule requests.
- `capsule_kinds` is OPTIONAL and MUST contain only supported values.
- `domains` and `languages` are OPTIONAL coarse capability hints.
- `max_capsule_bytes` is OPTIONAL. If absent, the protocol maximum of 16,384 serialized
  bytes applies.

#### 8.3 Bounds

To prevent profile inflation and identity leakage:

1. The canonical serialized `cognitive` block **MUST NOT** exceed **1,024 bytes**.
2. `domains` **MUST NOT** contain more than 16 entries.
3. `languages` **MUST NOT** contain more than 16 entries.
4. Each `domains` or `languages` string **MUST NOT** exceed 48 UTF-8 bytes.
5. Entries **MUST** describe coarse capability or language, not personal biography.
6. Implementations **MUST NOT** require fields such as nationality, employer, age,
   profession, location, political identity, religion or personal interests.
7. A client **MUST** treat all self-declared cognitive metadata as advisory.
8. Existing nodes that do not implement this SWIP follow the base versioning rule and
   ignore the unknown `cognitive` field.

### 9. Cognitive Capsule

#### 9.1 Design goal

A Cognitive Capsule is a bounded, model-independent object suitable for retrieval and
optional local reuse. It is not a model, adapter, prompt transcript, user profile, or
proof of truth.

#### 9.2 Schema

```json
{
  "v": "0.1",
  "capsule_id": "hex",
  "origin_node": "base64url-ed25519-public-key",
  "kind": "term|concept|procedure|style_pattern|training_pattern",
  "topics": ["string"],
  "statement": "string",
  "examples": ["string"],
  "provenance_class": "public_source|user_curated_public|peer_derived|synthetic",
  "support": {
    "source_count": 0,
    "model_family_count": 0
  },
  "lineage": {
    "parent_id": null,
    "revision": 0
  },
  "permissions": {
    "cache": false,
    "redistribute": false,
    "train": false
  },
  "expires_at": null,
  "sig": "base64"
}
```

#### 9.3 Identifier

`capsule_id` MUST be:

```text
hex(BLAKE2b(
    RFC8785-canonical-json(capsule fields except capsule_id and sig),
    digest_size=16
))
```

A change to any signed capsule content therefore creates a new identifier.

#### 9.4 Signature

`sig` MUST be an Ed25519 signature by `origin_node` over the RFC 8785 canonical
serialization of every field preceding `sig`, including `capsule_id`.

A receiver MUST verify the signature before caching or using a capsule.

A valid signature proves only that the named node signed the object. It MUST NOT be
presented as evidence that the capsule is factually correct.

#### 9.5 Size bounds

1. A serialized capsule **MUST NOT** exceed **16,384 bytes**.
2. `topics` **MUST NOT** contain more than 16 entries.
3. Each topic **MUST NOT** exceed 64 UTF-8 bytes.
4. `statement` **MUST NOT** exceed 8,192 UTF-8 bytes.
5. `examples` **MUST NOT** contain more than 4 entries.
6. Each example **MUST NOT** exceed 1,536 UTF-8 bytes.
7. A receiver MUST reject a capsule that exceeds any bound with
   `E_CAPSULE_TOO_LARGE`.

These limits are protocol bounds, not performance claims.

#### 9.6 Permissions

`permissions` is REQUIRED.

- `cache = false`: the receiver MAY use the capsule for the immediate operation but MUST
  NOT persist it after the operation completes.
- `cache = true`: the receiver MAY persist it locally.
- `redistribute = false`: the receiver MUST NOT serve the capsule payload to another
  peer.
- `redistribute = true`: the receiver MAY serve the **unchanged signed capsule** to
  another peer.
- `train = false`: the receiver MUST NOT use the capsule as training data.
- `train = true`: the receiver MAY use it for local training, subject to local policy
  and any applicable licence. This permission is not an instruction to train and is not
  evidence that training is safe or useful.

A modified capsule MUST be issued as a new capsule, signed by the modifying node, with
`lineage.parent_id` set to the prior capsule's ID. A modified capsule MUST NOT preserve
the prior signature as if the original node endorsed the modification.

#### 9.7 Provenance and support fields are claims, not proof

`provenance_class`, `source_count` and `model_family_count` are self-declared metadata.

A receiver:

- **MAY** use them as retrieval or triage features;
- **MUST NOT** treat them as cryptographic proof;
- **MUST NOT** convert repetition or model-family count into a factual confidence score.

### 10. Capsule discovery model

This SWIP specifies **pull, not gossip**.

A node:

1. **MUST NOT** broadcast capsule payloads periodically.
2. **MUST NOT** push unsolicited capsules to peers.
3. **MAY** advertise coarse `domains`, `languages` and supported `capsule_kinds` in the
   Cognitive Capability Block.
4. A client MAY request a capsule only after it has selected or contacted a peer through
   the ordinary Swarmbly discovery/transport mechanism.
5. Peer discovery transport remains outside the scope of this SWIP.

This design intentionally prevents the cognitive layer from becoming a second overlay
network.

### 11. Capsule request

A node with `share_mode = "pull"` MAY accept:

```json
{
  "v": "0.1",
  "type": "cognitive_capsule_request",
  "request_id": "hex-128-bit-random",
  "kind": "term|concept|procedure|style_pattern|training_pattern|null",
  "topics": ["string"],
  "max_bytes": 16384
}
```

Rules:

1. `request_id` MUST be generated randomly and MUST NOT reuse a Swarmbly `session_id` or
   `task_id`.
2. `topics` MUST contain 1–8 entries.
3. Each topic MUST NOT exceed 64 UTF-8 bytes.
4. `max_bytes` MUST be in `[512, 16384]`.
5. The request MUST NOT include the user's original prompt, Personal Vault content,
   embedding vectors, user biography, or task transcript.
6. The serving node MAY return no capsule.
7. The serving node MAY locally rate-limit capsule requests.
8. A capsule request MUST NOT create a node obligation to answer.

### 12. Capsule response

Success:

```json
{
  "v": "0.1",
  "type": "cognitive_capsule_response",
  "request_id": "same-as-request",
  "capsules": [
    { "...": "Cognitive Capsule" }
  ],
  "error": null
}
```

Failure:

```json
{
  "v": "0.1",
  "type": "cognitive_capsule_response",
  "request_id": "same-as-request",
  "capsules": [],
  "error": {
    "code": "E_CAPSULE_NOT_FOUND",
    "retry_after_ms": null
  }
}
```

A response:

1. MUST contain at most **4 capsules**.
2. MUST NOT exceed the request's `max_bytes`.
3. MUST NOT exceed **16,384 bytes** total.
4. MUST return only capsules whose local policy permits serving.
5. MUST NOT silently substitute private local memory for an unavailable capsule.

### 13. Capsule error codes

| Code | Meaning | Client action |
|---|---|---|
| `E_COGNITIVE_DISABLED` | Node does not serve cognitive requests | Continue without cognitive exchange |
| `E_CAPSULE_NOT_FOUND` | No matching capsule is available | Continue without capsule |
| `E_CAPSULE_FORBIDDEN` | Matching item exists but local policy forbids serving it | Do not retry for the same item |
| `E_CAPSULE_TOO_LARGE` | Request or response violates bounds | Reduce request or reject response |
| `E_CAPSULE_RATE_LIMITED` | Node locally rate-limited the request | Respect `retry_after_ms`; do not count as dishonesty |
| `E_CAPSULE_BAD_SIGNATURE` | Received capsule fails signature validation | Reject capsule; MAY lower local cognitive affinity |
| `E_CAPSULE_UNSUPPORTED` | Capsule version or kind is unsupported | Ignore or request a supported form |

Capsule failures MUST NOT be counted as failures to execute a normal Swarmbly micro-task.

### 14. Capsule processing

A receiver MUST process a valid capsule as **untrusted external data**.

Specifically:

1. Capsule text MUST NOT be allowed to alter:
   - system instructions;
   - privacy policy;
   - tier/lane classification rules;
   - task decomposition;
   - dispatch policy;
   - `Γ` except through an explicit local assimilation step.
2. Capsule text MUST NOT be concatenated into privileged instruction channels.
3. A receiver MAY:
   - use it as quoted retrieval context;
   - store it in social memory if `cache = true`;
   - compare it against local knowledge;
   - reject it;
   - mark it contradictory;
   - ask the user to approve it;
   - create a derived local note.
4. The receiver MUST preserve that the source was social/external unless the user
   explicitly promotes it into self/local knowledge.
5. A capsule MUST NOT directly update model weights.

### 15. Local assimilation states

Implementations MAY maintain richer local state, but if they expose a capsule lifecycle,
the following semantic distinction is RECOMMENDED:

```text
RECEIVED
   ↓
OBSERVED
   ↓
REUSED
   ↓
LOCALLY_VALIDATED
   ↓
OPTIONALLY_CONSOLIDATED
```

`OBSERVED` and `REUSED` MUST NOT be described to users as "verified true".

A capsule may be retained indefinitely in `OBSERVED` state if the user never validates
it.

### 16. Traffic-induced persistence

This SWIP introduces no mandatory replica count for Cognitive Capsules.

Persistence MAY arise when:

1. a capsule permits caching;
2. a client requests it;
3. the client stores it;
4. the capsule permits redistribution;
5. later clients request and obtain the unchanged signed capsule from a cache holder.

No client is required to become a replica.

A future SWIP MAY define explicit preservation replication for rare public knowledge,
but such a mechanism is out of scope here.

### 17. Local fine-tuning

Fine-tuning remains outside the Swarmbly wire protocol.

An implementation MAY train local adapters from its LCS if:

1. the user has enabled local training;
2. every included source permits training;
3. peer-derived material has `permissions.train = true`;
4. private remote task content has not been retained in violation of Section 4;
5. the adapter remains local unless a later SWIP standardizes adapter exchange.

This SWIP defines no adapter format and no training schedule.

### 18. Feature negotiation and mixed networks

No explicit negotiation round trip is added.

- Absence of `cognitive` means "no advertised cognitive capability".
- A client MUST NOT assume capsule support when `cognitive` is absent.
- A client that does not understand `cognitive` ignores it under the normal minor-version
  compatibility rule.
- A node advertising `share_mode = "pull"` but returning
  `E_COGNITIVE_DISABLED` is treated as capability drift, not a protocol-security
  violation; clients MAY lower local affinity for the feature.
- Normal task execution MUST continue regardless of cognitive capability mismatch.

### 19. No change to normal task semantics

This SWIP does not alter:

- decomposability rules;
- DAG planning semantics;
- packet answerability;
- mandatory carry;
- `ρ` accounting;
- `k` redundancy semantics;
- assembly;
- verification commitments;
- privacy tiers;
- sensitivity lanes;
- credit accounting.

Cognitive metadata MUST NOT become a hidden substitute for any of these mechanisms.

---

## Rationale

### 1. Why local state instead of a global knowledge graph

A global knowledge graph would require:

- synchronized distributed state;
- identity resolution;
- conflict resolution;
- additional storage obligations;
- additional network traffic;
- governance over shared schema;
- a new trust model.

None of these are necessary to prove the core hypothesis.

The local-first design lets each user own and inspect their cognitive state while using
the existing Swarmbly network only when a task needs remote capacity or an explicitly
requested knowledge object.

### 2. Why Task Projection reuses `Γ`

The current contract already contains the fields needed for a large fraction of
personalization: audience, register, lexicon, entities and style seed.

Adding a second personalization envelope would:

- duplicate semantics;
- increase header size;
- create disagreement over which field is authoritative;
- complicate packing and context accounting.

Reusing `Γ` also forces the cognitive layer to pay the same context and privacy costs as
all other shared context rather than hiding them.

### 3. Why reclassify privacy after local retrieval

Memory can introduce identifiers or sensitive context that were absent from the original
prompt.

For example, a generic request such as:

> "Draft an update about the project."

may become identifying after local retrieval inserts a project name, employer, person
name or medical context.

A privacy classifier that runs only before retrieval has evaluated the wrong payload.

Therefore the final routing classification must see the actual Task Projection that may
leave the device.

### 4. Why workers do not learn from requests by default

Automatic worker retention creates a severe asymmetry:

- a client sends a micro-task expecting computation;
- the worker silently gains a durable copy or training signal.

That would materially widen the privacy model and make "volunteer compute" function as a
data collection channel.

Keeping remote execution ephemeral by default preserves the existing trust boundary.

### 5. Why local peer affinity instead of global cognitive reputation

Global reputation and local usefulness answer different questions.

Global/registry reputation asks whether a worker executes protocol work correctly.
Affinity asks whether a particular client has historically found that peer useful for a
specific class of tasks.

A node may be highly reliable but unhelpful for one domain, or locally useful while
having little network history.

Making affinity private also avoids turning user routing history into another network
identifier.

### 6. Why affinity cannot override model-family diversity

Repeatedly selecting the same cognitively similar peers can create an echo chamber.

Swarmbly already treats model-family diversity as valuable when replicas are used. The
cognitive extension must not silently collapse that diversity because one peer is
familiar.

Affinity is therefore a ranking feature after mandatory eligibility, not a replacement
for diversity or verification.

### 7. Why capsules instead of adapters

Adapters are:

- model-family dependent;
- potentially large;
- difficult to inspect;
- capable of encoding unintended behavior;
- more expensive to transmit and validate.

A compact declarative object is:

- model-independent;
- human-auditable;
- cheap to cache;
- cheap to reject;
- compatible with retrieval;
- optionally convertible into training data later.

Adapters may still be useful locally, but they are a poor first network primitive.

### 8. Why pull instead of gossip

Continuous gossip would make the cognitive layer consume bandwidth even when no user is
asking a relevant question.

It also increases traffic-analysis surface and creates pressure to replicate material
users may not need.

Pull preserves the existing Swarmbly philosophy: communication is justified by work.

### 9. Why traffic-induced persistence instead of mandatory replication

Mandatory replication introduces a new resource obligation on nodes and requires a new
coverage model.

Traffic-induced persistence is weaker, but it is nearly free in the common case because
copies arise from demand that already exists.

The trade-off is explicit: rarely used knowledge may disappear. This SWIP accepts that
limitation rather than introducing a global persistence subsystem before measuring
whether the weaker mechanism is sufficient.

### 10. Why no truth score

The current protocol already distinguishes agreement from correctness.

The cognitive layer must preserve the same epistemic discipline.

Repeated appearance of a term or convention can support a statement such as:

> "This pattern is common in my observations."

It cannot justify:

> "This claim is true."

Accordingly, support counts and model-family counts are metadata, not confidence.

### 11. Why no mandatory fine-tuning

Requiring local training would raise the minimum hardware cost of participation and work
against the accessibility goal of Swarmbly.

It would also make user state less portable because learned behavior becomes tied to a
model family.

Retrieval and Task Projection therefore come first. Fine-tuning remains optional and
must justify its own cost empirically.

### 12. Alternatives considered

#### A. Do nothing

**Advantage:** zero complexity.

**Rejected as the only path** because Swarmbly would remain a compute protocol with no
portable mechanism for users who want persistent local cognitive state or explicit
shareable knowledge.

This remains a valid deployment choice: all features in this SWIP are optional.

#### B. Global synchronized knowledge graph

**Rejected** because it adds persistent network state, synchronization and a larger trust
surface before a need has been demonstrated.

#### C. Gossip-based peer learning

**Rejected** because it creates background traffic and makes privacy harder to reason
about.

#### D. Federated training / model aggregation

**Rejected** for this SWIP because it pushes Swarmbly toward model convergence, adds
large training and communication costs, and conflicts with preserving heterogeneous
local models.

#### E. Share LoRA adapters directly

**Deferred/rejected as the base mechanism** because adapters are model-specific and
harder to audit than explicit data.

#### F. Add a separate knowledge router

**Rejected** because the existing orchestrator already owns candidate selection.
Cognitive features should be optional inputs to one routing pipeline.

#### G. Publish affinity globally

**Rejected** because local usefulness is client-specific and publication adds identity
and correlation risk.

#### H. Store entire remote outputs as social memory

**Rejected as the default** because generalized observations are usually sufficient and
full transcripts increase privacy, storage and prompt-injection exposure.

---

## Backwards compatibility

This proposal is designed to be MINOR-compatible with the current protocol versioning
rule.

### Existing nodes

A node that does not implement this SWIP:

- ignores the unknown OPTIONAL `cognitive` field in a node profile;
- never advertises capsule support;
- never receives a capsule request from a conformant client unless it advertised
  `share_mode = "pull"`;
- continues to execute normal Swarmbly tasks unchanged.

### Existing orchestrators

An orchestrator that does not implement this SWIP:

- ignores cognitive profile metadata;
- never requests capsules;
- assembles normal results exactly as before.

### Mixed networks

Mixed networks are the expected deployment.

Normal task dispatch MUST NOT depend on cognitive support.

A cognitive-capable orchestrator encountering an old worker treats it as:

```text
cognitive capability = absent
normal worker capability = unchanged
```

### Stored artifacts

No existing stored artifact requires migration.

The LCS is new local state and is outside the base wire format.

### Wire breakage

The proposed node-profile block is an OPTIONAL unknown field compatible with the
existing rule that participants ignore unknown fields within the same major version.

The capsule request/response messages are opt-in application messages and MUST NOT be
sent to a peer that has not advertised `share_mode = "pull"`.

### Spec version

This draft targets the protocol direction described for **v0.3**. If the normative spec
remains at v0.2 when this SWIP is accepted, the final editor MUST either:

1. assign the change to the next MINOR version; or
2. document why the optional additions fit the existing v0.2 minor-compatibility rule.

No implementation should infer a version bump from this draft alone.

---

## Security and privacy implications

This section is normative where it uses RFC 2119 language.

### 1. What can a malicious node now observe?

#### Cognitive profile metadata

If enabled, a malicious observer can learn coarse advertised:

- domains;
- languages;
- supported capsule kinds;
- whether the node serves capsules.

This is additional fingerprinting surface.

Mitigations:

1. Advertising the Cognitive Capability Block is OPTIONAL.
2. `domains` and `languages` are bounded.
3. Personal biography fields are prohibited.
4. Implementations SHOULD let users disable or coarsen these hints.
5. Clients SHOULD NOT interpret absence of metadata as absence of knowledge.

#### Capsule requests

A capsule-serving node can observe that a peer is interested in particular topics.

This creates a new interest-correlation channel.

Mitigations:

1. capsule requests contain structured coarse topics, not the original user prompt;
2. requests use an independent random `request_id`;
3. requests MUST NOT reuse session/task identifiers;
4. clients SHOULD avoid requesting a capsule when the topic itself would reveal
   sensitive information;
5. capsule lookup MUST occur only after the request remains eligible for the chosen
   network/tier under local policy.

### 2. Does this change how much of the original problem a worker can reconstruct?

Task Projection can add personalized lexicon, entities or style hints to `Γ`.

That can increase information disclosed to every worker receiving the contract.

Therefore:

- all TP tokens count normally toward `|Γ|` and `ρ`;
- the final privacy classification MUST run after TP;
- the orchestrator MUST omit TP material that is not required;
- LOCAL requests MUST remain local.

The proposal does not claim decontextualization provides confidentiality.

### 3. What can a malicious node now cause?

#### Knowledge poisoning

A malicious capsule server can send false, biased or adversarial content.

Mitigations:

1. signatures bind origin but are explicitly not truth proofs;
2. capsules are treated as untrusted data;
3. they cannot directly alter privileged instructions or routing;
4. they cannot directly update model weights;
5. support counts are not truth/confidence scores;
6. the receiver may reject, quarantine or require user approval;
7. training from a capsule requires both permission and local policy.

#### Prompt injection through capsule text

A malicious `statement` or `example` may contain instruction-like text.

Mitigations:

- capsule content MUST remain in a data channel;
- it MUST NOT be concatenated into system/developer instructions;
- normal LLM application-security controls apply;
- local sanitization MAY remove or quote imperative text before retrieval.

#### Resource exhaustion

A malicious or buggy peer can send large or repeated capsule responses.

Mitigations:

- strict 16 KiB response bound;
- at most four capsules per response;
- bounded string/list sizes;
- receivers MUST reject over-limit objects before model processing;
- serving nodes MAY rate-limit requests.

### 4. What can a malicious or coerced client cause on nodes?

A malicious client can issue repeated capsule queries to:

- consume bandwidth/CPU;
- enumerate advertised topic holdings;
- infer operator interests from availability.

Mitigations:

1. capsule serving is OPTIONAL;
2. nodes MAY return `E_CAPSULE_RATE_LIMITED`;
3. nodes MAY return `E_CAPSULE_NOT_FOUND` without proving whether a forbidden matching
   item exists;
4. implementations SHOULD avoid distinguishable timing between "not found" and locally
   forbidden objects where feasible;
5. capsule serving does not require model inference; implementations SHOULD use indexed
   lookup where possible.

### 5. Does this add a new trust assumption?

It adds one limited trust decision:

> A client choosing to use a capsule trusts its own local assimilation policy to treat
> peer-provided data safely.

It does **not** add an assumption that the capsule origin is honest or correct.

The base worker trust model remains unchanged.

### 6. Traffic analysis

Yes, capsule requests create a new observable relationship:

```text
requesting node ↔ topic ↔ serving node
```

This may expose interests over time.

The SWIP accepts this as a real residual channel and limits it by:

- no broadcast;
- no gossip;
- no original prompt in the request;
- coarse topics;
- optional use;
- local-only fallback.

A future privacy SWIP may define private information retrieval, relays, query padding or
oblivious lookup. None is claimed here.

### 7. Blast radius of a compromised node

A compromised worker without cognitive support has the same task-level blast radius as
before.

A compromised capsule-serving node additionally can poison the capsules it signs.

Because capsules cannot directly alter routing, privileged instructions or weights, the
blast radius is bounded to clients that choose to retrieve and use its data.

Clients MUST retain origin provenance so that locally cached objects from a compromised
origin can be identified and invalidated.

### 8. Privacy of Personal Vault and local embeddings

The Personal Vault, local embeddings and local adapters remain outside the wire
protocol.

A conformant cognitive implementation MUST NOT expose them merely to advertise
capability or serve a capsule.

Capsule creation from private material is permitted only when local policy explicitly
allows both:

```text
generalize = true
share = true
```

The fact that a summary contains no obvious PII is not sufficient permission by itself.

### 9. Redistributed capsules and revocation

Once a capsule with `redistribute = true` has been transmitted, deletion cannot be
cryptographically guaranteed across all caches.

User interfaces MUST NOT promise global deletion of previously redistributed capsules.

A future revocation mechanism MAY mark an origin capsule as withdrawn, but cannot force
untrusted peers to erase existing bytes.

This limitation is one reason the default permissions in implementations SHOULD be:

```json
{ "cache": false, "redistribute": false, "train": false }
```

unless the user has explicitly chosen otherwise.

### 10. Training privacy

Local adapters may memorize training examples.

Implementations enabling local training SHOULD:

- keep personal adapters local by default;
- record which local sources contributed;
- allow a user to invalidate/rebuild an adapter after source deletion;
- avoid training directly on raw remote transcripts when a smaller derived pattern is
  sufficient.

Adapter exchange is out of scope.

---

## Measurement plan

No performance, latency, quality, bandwidth-saving, resilience or personalization
improvement is claimed by this SWIP before measurement.

The implementation MUST be evaluated incrementally so each mechanism earns its cost.

### Experiment C0 — Baseline

**Purpose:** establish unmodified Swarmbly performance.

**Baseline:** current reference implementation, no cognitive features.

Record at minimum:

- task quality metric appropriate to benchmark;
- coherence report;
- achieved `ρ`;
- `|Γ|`;
- end-to-end latency;
- bytes transmitted;
- local model calls;
- model family usage.

### Experiment C1 — Local memory / retrieval only

**Arms:**

- A: base local SLM / Swarmbly client;
- B: same system + Local Cognitive Store retrieval.

**Workload:** a held-out set of user-specific tasks whose required preferences,
terminology and domain notes exist in a training/ingestion corpus but are absent from the
request.

**Metric:**

- exact adherence to explicit preference/terminology targets;
- task-quality score on held-out tasks;
- local retrieval latency;
- local storage growth.

**Success threshold proposed before implementation:**

- B improves preference/terminology adherence by **≥15 percentage points absolute**
  over A on the held-out set;
- median local retrieval overhead is **≤150 ms** on the declared reference machine;
- no network bytes are added in local-only mode.

If the adherence gain is <5 percentage points, the feature SHOULD be reconsidered before
protocol work continues.

The latency threshold is a design target, not a current claim.

### Experiment C2 — Task Projection into `Γ`

**Arms:**

- A: LCS retrieval used only by the local assembler;
- B: same retrieval + compact Task Projection into existing `Γ`.

**Metric:**

- distributed-fragment adherence to required terminology/entities/register;
- final assembled adherence;
- increase in `|Γ|`;
- increase in achieved `ρ`;
- privacy-tier changes caused by TP.

**Success threshold:**

- B improves distributed-fragment adherence by **≥10 percentage points absolute**
  relative to A;
- median TP growth is **≤64 tokens** beyond the baseline contract;
- no privacy-tier downgrade occurs after final classification;
- every TP token is accounted for in normal `ρ` reporting.

If TP requires >128 median added tokens to produce <5 points of adherence gain, it SHOULD
be rejected or redesigned.

### Experiment C3 — Privacy reclassification

Property/adversarial test.

Construct prompts that are benign before retrieval but become:

- personally identifying;
- commercially sensitive;
- health/legal/financial sensitive;

after Task Projection.

**Required result:** 100% of fixture cases are reclassified at or above the manually
labelled required tier/lane before network dispatch.

Any fixture in which sensitive projected context is dispatched at a lower class is a
**release blocker**, not a statistical failure.

### Experiment C4 — Peer affinity routing

**Arms:**

- A: normal candidate ranking;
- B: normal candidate ranking + local affinity as a bounded ranking feature.

**Workload:** repeated mixed-domain tasks over a heterogeneous worker pool with at least
three model families.

**Metric:**

- accepted-fragment rate;
- judge-selected fragment rate;
- verification failure rate;
- model-family diversity;
- end-to-end latency;
- per-domain peer concentration (e.g. Herfindahl index).

**Success threshold:**

- B improves accepted/judge-selected useful-fragment rate by **≥5 percentage points**
  without:
  - reducing distinct model-family participation by more than **10% relative**;
  - increasing p95 latency by more than **10%**;
  - increasing verification failures.

If affinity creates >25% relative increase in peer concentration without quality gain,
it SHOULD be disabled.

### Experiment C5 — Capsule utility

**Arms:**

- A: resolve a repeated missing concept by normal Swarmbly execution each time;
- B: first resolution may use Swarmbly; subsequent resolutions may hit a cached capsule.

**Metric:**

- capsule hit rate;
- additional bytes for capsule exchange;
- normal task calls avoided;
- quality on the repeated task;
- stale/incorrect capsule rate.

**Success threshold:**

Over a workload with repeated knowledge demand, the total bytes saved from avoided
normal task dispatch must exceed capsule bytes by **≥2×**, while task quality is not
worse by more than **2 percentage points**.

If capsule traffic is not net-positive under a repetition-heavy workload specifically
designed to favor caching, the network capsule mechanism SHOULD be withdrawn.

### Experiment C6 — Traffic-induced persistence

**Simulation:**

1. one origin node owns a redistributable capsule;
2. peers request/copy it only through normal demand;
3. nodes undergo measured/random churn;
4. the origin disappears.

**Metric:**

```text
P(capsule remains retrievable | origin lost)
```

as a function of:

- number of successful prior requests;
- cache permission;
- redistribution permission;
- churn rate.

**Pre-registered success condition:**

After at least **5 independent successful uses** by distinct nodes in the test topology,
the capsule remains retrievable after origin loss in **≥95%** of 1,000 simulated churn
trials under the declared churn model.

If this condition is not met, the SWIP MUST NOT claim use-induced caching is sufficient
for preservation. A future explicit replication proposal may then be justified.

### Experiment C7 — Social poisoning

Inject malicious capsules containing:

- false statements;
- prompt injection;
- misleading support counts;
- conflicting terminology;
- oversized payloads;
- invalid signatures.

**Required properties:**

- invalid signatures: 100% rejected;
- over-bound objects: 100% rejected before model assimilation;
- prompt-injection text: cannot change privileged policy in deterministic tests;
- support counts: never rendered as truth/confidence by the reference UI/API;
- direct weight update from capsule receipt: impossible by construction.

### Experiment C8 — Retrieval versus fine-tuning

This experiment is implementation-level, not wire-level.

**Arms:**

- A: LCS retrieval only;
- B: retrieval + local LoRA trained from stable, permitted examples.

**Metric:**

- held-out personalization quality;
- general benchmark regression;
- training energy/time;
- inference latency;
- adapter size.

**Adoption threshold:**

Fine-tuning should remain an optional optimization unless B improves the targeted
personalization metric by **≥10 percentage points absolute** over A while degrading the
chosen general-capability benchmark by **≤2 percentage points**.

No protocol feature depends on C8 succeeding.

### Cognitive overhead accounting

The reference implementation SHOULD emit a local diagnostic record such as:

```json
{
  "cognition": {
    "retrieved_items": 4,
    "retrieved_tokens": 510,
    "task_projection_tokens": 38,
    "social_cache_hits": 1,
    "capsule_requests": 0,
    "capsule_bytes_in": 0,
    "capsule_bytes_out": 0,
    "local_digest_ms": 0
  }
}
```

This block is local diagnostic metadata by default and MUST NOT be transmitted to
workers.

### Abandonment rule

The network-visible portion of this SWIP SHOULD be withdrawn if all of the following are
true after C1–C5:

1. local retrieval provides useful personalization;
2. Task Projection works;
3. but peer affinity provides no measurable routing benefit; and
4. Cognitive Capsules do not produce net reuse/traffic benefit.

In that outcome, the correct design is a purely local cognitive layer with no protocol
extension.

That is a valid result.

---

## Reference implementation

Not yet implemented.

A reference implementation should be staged in separate PRs after SWIP acceptance.

Suggested order:

1. local-only LCS prototype;
2. Task Projection adapter for `Γ`;
3. post-projection privacy classification tests;
4. local PAC using existing result metadata only;
5. optional Cognitive Capability Block;
6. capsule schemas and signature validation;
7. pull-only capsule endpoint/message handler;
8. measurement harness C0–C7;
9. optional local fine-tuning experiment C8.

No implementation PR should bundle all stages.

---

## Open questions

1. **Should this be one SWIP or two?**  
   The local cognitive layer and Task Projection require little/no wire change, while
   Cognitive Capsules do. Review may prefer to accept the local architecture separately
   and move capsule exchange into a follow-up SWIP.

2. **Is `spec-version: 0.3` the right target?**  
   The current normative `SPEC_EN.md` is v0.2 while Whitepaper v2 describes protocol
   direction toward v0.3. The final SWIP number/version should follow the state of the
   spec when the discussion issue is resolved.

3. **Should cognitive metadata live in the node profile at all?**  
   A privacy-minimal alternative is to advertise only a single boolean
   `capsules: true` and discover topics after an authenticated connection.

4. **Should `domains` use free strings or a registry?**  
   Free strings are decentralized and easy but inconsistent. A registry improves
   matching but creates governance overhead. This draft chooses bounded free strings.

5. **Are language tags BCP 47?**  
   The final specification should probably require BCP 47 tags rather than arbitrary
   language names.

6. **Should capsule `statement` allow Markdown?**  
   Plain UTF-8 text is simpler and safer; Markdown is more expressive for procedures.
   The reference implementation should test whether Markdown materially increases
   prompt-injection risk.

7. **Should a capsule carry source URLs or hashes?**  
   This could improve auditability for public-source capsules but also leaks browsing
   history and creates larger objects. The draft omits detailed sources.

8. **How should licences be represented?**  
   `permissions.train` is not enough for copyrighted/public-source material. A future
   revision may need an SPDX-compatible licence field before capsules are used for
   training or redistribution.

9. **How should capsule revocation work?**  
   A signed tombstone/revocation object may help honest peers stop serving a capsule,
   but cannot guarantee deletion. This draft documents the limitation instead of
   pretending revocation is enforceable.

10. **How much affinity exploration is enough?**  
    The draft requires avoiding permanent lock-in but intentionally does not hard-code
    an epsilon/exploration rate before measurement.

11. **Should affinity be keyed by free-form domain, task kind, embedding cluster, or all
    three?**  
    This is an implementation/measurement question until interoperability requires a
    shared representation.

12. **Should capsule lookup happen before or after ordinary worker selection?**  
    Doing it first may avoid compute; doing it later may reduce topic leakage. The
    reference benchmark should compare both.

13. **Should capsule requests be credit-metered?**  
    Unmetered requests invite abuse; metering tiny lookups may add more accounting
    complexity than value. This draft leaves capsule serving voluntary and rate-limited,
    with no credits.

14. **Can capsule availability itself deanonymize a node?**  
    Rare topic combinations may fingerprint an operator even without biography fields.
    Coarsening guidance may need to become normative.

15. **What does "independent successful use" mean in the persistence benchmark?**  
    Distinct `node_id` values are vulnerable to Sybils. The experiment should declare
    whether "independent" means distinct simulated failure domains rather than identities.

16. **Should training patterns be in the first capsule version?**  
    Removing `training_pattern` would narrow v0.1 and avoid conflating retrieval with
    training. It remains included here to invite explicit review.

17. **Should Social Observations be retained for SANITISABLE or SENSITIVE tasks?**  
    The safest initial reference implementation may restrict automatic social
    observation to PUBLIC tasks even on the requesting client.

18. **Should locally derived cultural patterns require a minimum diversity of model
    families before display?**  
    That may reduce single-family artifacts, but family diversity is still not evidence
    of truth.

19. **How should user corrections propagate to already generated local training
    artifacts?**  
    The LCS should track provenance, but adapter invalidation/retraining semantics are
    currently outside the wire protocol.

20. **Does traffic-induced persistence actually work?**  
    This is intentionally unresolved. Experiment C6 exists to decide it rather than
    assume it.

---

## Discussion checklist

Before converting this draft into `swips/SWIP-XXXX-local-cognitive-extension.md`:

- [ ] Open the required SWIP discussion issue.
- [ ] Replace `XXXX` with the zero-padded discussion issue number.
- [ ] Confirm target spec version.
- [ ] Decide whether Cognitive Capsules remain in this SWIP or move to a follow-up.
- [ ] Confirm the 1 KiB profile and 16 KiB capsule wire bounds.
- [ ] Review privacy implications for topic-interest leakage.
- [ ] Review whether `training_pattern` belongs in capsule v0.1.
- [ ] Pre-register C1–C7 benchmark fixtures before implementing network-visible code.
- [ ] Keep the SWIP PR design-only; implementation belongs in separate PRs.
- [ ] Apply the repository's required DCO sign-off to the SWIP commit.
