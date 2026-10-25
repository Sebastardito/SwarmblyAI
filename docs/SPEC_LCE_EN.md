---
status: draft
lang: en
---
# Swarmbly Local Cognitive Extension (LCE): Specification and Architecture

**Version 0.1 — 4 October 2026**
Status: **Draft.** Normative; the reference implementation follows it (Section 21), and it is expected to change after the prototypes in Section 14 of the whitepaper. Several of its mechanisms have since been measured with real models (whitepaper v0.2, Section 11.7). The normative text has not changed yet: its next revision will incorporate the R13 result, which makes retrieval over the sources the default answering context and keeps the wiki as the governance layer (provenance, types, forgetting, training eligibility).
Companion documents: `WHITEPAPER_LCE_EN.md` (rationale, homologies and evidence), `REFERENCES_LCE.md` (annotated bibliography; the [n] markers in this document refer to it), `swips/SWIP-XXXX-local-cognitive-extension.md` (the network-visible part, in English, for the protocol repository), and the Swarmbly protocol specification v0.2 (`Swarmbly-AI/docs/SPEC_EN.md`), which this document does not modify.

The key words MUST, MUST NOT, REQUIRED, SHALL, SHOULD, SHOULD NOT, MAY and OPTIONAL are to be interpreted as described in RFC 2119.

**On default values.** The parameters marked *provisional* in Section 19 do not come from LCE measurements. They are starting points derived from the literature or from stated calculations, and the whitepaper experiments (Section 11) must fix or refute them before this specification leaves draft status.

---

## 1. Scope and non-goals

The LCE is an optional extension of the Swarmbly client that adds local personal memory, learning of the user's model and an optional exchange of written knowledge between nodes.

**In scope:** the source space and the learning policy; the wiki and its epistemic layer; the training queue, the adapter and its selection; the task projection onto the contract Γ; the rules that a worker with the LCE must follow when serving third parties; the social cache and affinity; the cognitive capabilities block of the node announcement; cognitive capsules and their persistence; the plural response; the diversity and cognitive cost reports.

**Out of scope:** the internal format of the wiki beyond the attributes this specification requires; the specific base model and fine-tuning method; the discovery transport; any shared global model; any central knowledge, identity or trust service.

**Explicit non-goals.** The LCE does not provide verifiable forgetting in the weights except through regeneration of the adapter; it does not guarantee that capsules are true; it does not provide strong Sybil resistance; and it does not claim that model-family diversity produces independent errors. See Section 12 of the whitepaper.

**What this specification does not change in the protocol.** The router, the plan, the packet, the result, dispatch, verification, assembly, E16 consensus, lanes, tiers, credits and error codes of specification v0.2 apply unchanged. A node that does not implement the LCE is fully conformant with Swarmbly.

---

## 2. Terminology

| Term | Meaning |
|---|---|
| **LCE** | Local Cognitive Extension: the set of components in this specification |
| **Source space** | Folder or set of folders of the user containing raw material; layer 0 |
| **Learning policy** | Per-source declaration of what may be extracted and for what use (Section 5) |
| **Wiki** | Memory written by a local model from the sources; layer 1 |
| **Claim** | Minimal unit of the wiki: a statement with anchoring, type, maturity and provenance (Section 6) |
| **Anchoring** | Reference from a claim to the exact fragment of the source from which it was extracted |
| **Epistemic distance** *d* | Number of model transformations between a claim and its nearest human source (Section 6.6) |
| **Transmission path** | `vertical` (from the user), `horizontal` (from another node) or `oblique` (from established nodes to a new one) |
| **Adapter** | Parameter-efficient fine-tuning module (LoRA or equivalent) trained on top of the base model; layer 2 |
| **Recipe** | Set of eligible data, replay mix and hyperparameters with which an adapter is trained |
| **Generation** | A consolidation cycle that produces adapter candidates and selects at most one |
| **Task projection** | Minimal, relevant personal information for a request, expressed in fields of Γ (Section 8) |
| **Social cache** | Local record of patterns observed in the results of one's own requests |
| **Affinity** | Locally observed utility of a peer for a domain (Section 10.2) |
| **Prevalence** | Number of independent nodes and families in which a pattern was observed; it is a label |
| **Capsule** | Signed object of at most 16 KiB carrying generalizable written knowledge (Section 12) |
| **Anchored variant** | Descendant capsule that declares new human evidence (Section 12.6) |
| **Canary set** | List of regionalisms with glosses verified by native speakers, used only for measurement (Section 15.3) |

---

## 3. Versioning and conformance

LCE objects that travel over the network carry a `"v"` field with the extension version as `MAJOR.MINOR`, independent of the protocol version. The protocol rule applies: a participant MUST ignore unknown fields and MUST reject a MAJOR version it does not implement.

**Conformance classes.**

- A **Conformant LCE Client** MUST implement Sections 5, 6, 7 (if it implements adapters), 8 and 15.2, and MUST comply with the invariants of Section 4.2.
- A **Conformant Worker with LCE installed** MUST comply with Section 9 in addition to the worker obligations of the protocol.
- A **Conformant Capsule Node** MUST implement Sections 11, 12 and 13, and MUST comply with the permission, signature, distance and variation rules of Section 12.
- An implementation that trains an adapter without the gate of Section 7.5 is **non-conformant**. An implementation that serves other clients' tasks with a personal adapter loaded is **non-conformant**.

---

## 4. Component view

### 4.1 Components and planes

| Component | Plane | Network-visible | Minimum hardware tier | Section |
|---|---|---|---|---|
| Source space and policy | local | no | C1 | 5 |
| Wiki and epistemic layer | local | no | C1 | 6 |
| Digester | local | no | C2 | 6.3 |
| Training queue and adapter | local | no | C4 | 7 |
| Task projection | inference | only through Γ | C1 | 8 |
| Worker rules | inference | no (behavior) | C0 | 9 |
| Social cache and affinity | local | no | C3 | 10 |
| Capabilities block | social | yes, optional | C3 | 11 |
| Capsules and persistence | social | yes, optional | C3 | 12–13 |
| Plural response | inference | response metadata | C0 | 14 |
| Reports | local | optional | C1 | 15 |

### 4.2 Invariants (normative)

A conformant implementation MUST preserve the eight invariants of the whitepaper (Section 8.2):

- **I1.** Claims of type `fact`, `user_claim`, `opinion`, `belief`, `hypothesis` and `experience` MUST NOT enter any adapter training set as assertions. (Explicit exception: Section 7.7.)
- **I2.** A worker executing tasks for another client MUST serve its base model without a personal adapter and MUST discard the task content according to Section 9.
- **I3.** The fraction of examples derived from other nodes in any training batch MUST be less than `SOCIAL_TRAIN_FRACTION_MAX`; every example derived from another node MUST have `d ≤ 1` and a declared human source; the user's own corpus MUST NOT be discarded to make room for social material.
- **I4.** A descendant capsule MUST declare `delta_evidence` in order to be redistributed or trained on.
- **I5.** The decision to cache, consolidate or train MUST NOT depend on prevalence in a more than linear way (Section 10.1).
- **I6.** Every adapter MUST be trained from the base model and the wiki, with interleaved replay, and MUST be evaluated with a test set generated for that generation.
- **I7.** A node participating in the social plane SHOULD compute and MAY publish the diversity report of Section 15.3.
- **I8.** A source without a declared policy MUST be treated as `reference_only`.

---

## 5. Source space and learning policy

### 5.1 Source space

The source space is one or more local folders. An implementation:

1. MUST treat the files in the source space as immutable from the LCE's point of view: the digester MUST NOT modify them.
2. MUST compute a content hash per file and record it in the dependency graph (Section 6.7).
3. MUST allow the user to withdraw a source, which triggers the forgetting of Section 7.8.
4. MUST NOT transmit any source over the network by virtue of participating in Swarmbly.

### 5.2 Learning policy

Each source or folder MAY declare a policy. The minimal schema is:

```yaml
learning_policy:
  v: "0.1"
  defaults:
    reference_only: true          # I8: what is not declared does not train
  sources:
    "teach/style/":
      authored_by_user: true
      wiki: true
      learn_style: true
      learn_procedure: false
      retain_episodic: false
    "teach/knowledge/":
      authored_by_user: false
      wiki: true
      learn_style: false
    "teach/procedures/":
      authored_by_user: true
      wiki: true
      learn_procedure: true
    "reference_only/":
      wiki: true
      train: false
```

**Semantics.**

1. `authored_by_user = true` declares that the text was written by the user. Only sources with this value MAY produce style examples (Section 7.2).
2. `wiki = true` allows the digester to extract claims. `wiki = false` excludes the source from the wiki.
3. `learn_style` and `learn_procedure` allow claims of those types extracted from the source to reach the TRAINABLE state.
4. `train = false` or `reference_only = true` prevents any claim from the source from reaching TRAINABLE.
5. `retain_episodic = false` prevents claims of type `experience` from being retained.
6. A policy change MUST be recorded in the dependency graph and MUST mark as obsolete the training examples that depended on the previous policy.

---

## 6. Wiki and epistemic layer

### 6.1 Representation

The wiki SHOULD be represented as Markdown files with metadata, human-readable and compatible with note-taking tools, and MAY be indexed in SQLite and a vector index. The concrete format is not normative; the attributes of Section 6.2 are.

### 6.2 Claim record

Every claim MUST have, at a minimum:

```yaml
claim_id: "hex"                     # hash of the normalized content
text: "In Ecuadorian Spanish, 'chuta' is an informal interjection of surprise or annoyance."
type: fact                          # see 6.4
maturity: ANCHORED                  # see 6.5
anchors:
  - source: "teach/style/notas-2026-09.md"
    span: [1204, 1268]              # byte offsets
    source_hash: "hex"
    verified: true                  # 6.3
provenance:
  epistemic_distance: 1             # 6.6
  transmission_path: vertical       # vertical | horizontal | oblique
  origin_capsule: null              # capsule_id if it arrived via a capsule
  human_source: "self"              # self | <origin_node> | <description>
status: active                      # active | contested | retracted
positions: []                       # only if status = contested (Section 14.3)
depends_on: ["hex", "..."]
created: "2026-10-04T10:22:00Z"
updated: "2026-10-04T10:22:00Z"
```

### 6.3 Digester and anchor verification

1. The digester MAY be a local model. Its outputs MUST be treated as proposals until anchor verification accepts them.
2. Anchor verification MUST check, at a minimum, that the cited fragment exists in the source with the recorded hash and that a verifier, which MAY be a model different from the digester, judges that the fragment supports the atomic claim [20].
3. A claim whose anchor is not verified MUST remain in the DIGESTED state and MUST NOT reach any later state.
4. The index, links, dependencies and state transitions MUST be implemented with deterministic code, not delegated to the model.
5. The verifier's rejection rate SHOULD be recorded in the report of Section 15.2.

### 6.4 Types

| `type` | Content | Retrieval | Training |
|---|---|---|---|
| `fact` | Claim about the world with an external source | yes | no (I1) |
| `user_claim` | What the user asserts | yes, attributed | no |
| `opinion` | The user's evaluation | yes, attributed | no |
| `belief` | The user's belief | yes, attributed | no |
| `hypothesis` | Claim under test | yes, flagged | no |
| `experience` | Episodic memory | yes, if `retain_episodic` | no |
| `preference` | Behavioral preference | yes | yes, if the policy allows it |
| `style` | Trait of voice, register or format | yes | yes, if `learn_style` |
| `procedure` | Recurring way of doing something | yes | yes, if `learn_procedure` |

An implementation MUST retrieve claims of type `user_claim`, `opinion` and `belief` with their explicit attribution, and MUST NOT present them as facts.

### 6.5 Maturity states

```text
RAW → DIGESTED → ANCHORED → CONNECTED → CORROBORATED → CONSOLIDATED → TRAINABLE
                    ↑                                                    (preference, style,
               verified anchor                                            procedure only)
```

| Transition | Condition (normative) |
|---|---|
| RAW → DIGESTED | the digester proposed the claim |
| DIGESTED → ANCHORED | anchor verified (6.3) |
| ANCHORED → CONNECTED | at least one link to another claim or concept |
| CONNECTED → CORROBORATED | `fact`: two independent human sources; `style`/`preference`/`procedure`: observed in at least `STABILITY_CYCLES` consolidation cycles |
| CORROBORATED → CONSOLIDATED | no active contradiction during one review cycle |
| CONSOLIDATED → TRAINABLE | behavioral type, policy allows it, `d ≤ 1` |

A contradiction detected during review MUST return the claim to CONNECTED and MAY mark it `contested`. Withdrawing the anchor MUST return it to DIGESTED.

### 6.6 Epistemic distance

1. `d = 0` for style, preference or procedure claims observed directly in user-authored text.
2. `d = 1` for claims extracted by a model from an anchored human source, either the user's own or that of a capsule's origin node.
3. `d = d_parent + 1` for claims derived from another claim without new human evidence.
4. Copying or caching a capsule without modifying it MUST NOT change `d`.
5. An anchored variant (Section 12.6) MUST have `d = 1`.
6. Distance is an attribute of content. It MUST NOT be used to compute trust between nodes, nor be composed transitively over identities.

### 6.7 Dependency graph

1. An implementation MUST maintain a directed acyclic graph with nodes of type source, policy, claim, concept, training example and adapter.
2. When the hash of a source changes, a source is withdrawn or a policy changes, all descendants MUST be marked `stale`.
3. An adapter whose training set contains any `stale` example MUST be marked `affected` and SHOULD be regenerated in the next cycle (Section 7.8).

### 6.8 History

An implementation SHOULD version the wiki (for example, with Git) with one commit per consolidation cycle. If it does, the forgetting of Section 7.8 MUST rewrite the history that contains the forgotten content, and MUST propagate to the backups that the implementation manages.

---

## 7. Training queue and adapter

### 7.1 Eligibility

An example is eligible for training if and only if:

1. it comes from claims in the TRAINABLE state or from correction pairs (7.2.3);
2. all of its originating claims have `d ≤ 1`;
3. none of its dependencies is `stale`;
4. its source is not `reference_only`.

### 7.2 Sources of examples

1. **Style**: segmented text from sources with `authored_by_user = true`. Text authored by others MUST NOT be used for style.
2. **Question-answer pairs**: generated from eligible behavioral claims; each pair MUST retain the `claim_id` and the anchor, and MUST be accepted only if a verifier judges that the answer follows from the anchored fragment.
3. **Corrections**: each user edit to a response or page MAY be recorded as a preference pair (before rejected, after preferred) for direct preference optimization [19].

### 7.3 Batch composition and replay

Every training batch MUST mix new examples, a sample of examples from previous generations (replay) and general text, in proportions recorded in the recipe. The replay fraction MUST be greater than zero. The fraction of examples derived from other nodes MUST comply with I3.

### 7.4 Candidates and generation

1. A consolidation cycle SHOULD run only if the device is idle, connected to power, the user permits it and there are at least `MIN_NEW_EXAMPLES` new eligible examples.
2. Each cycle MAY train between 1 and `N_CANDIDATES` candidates with different recipes.
3. Each candidate MUST be trained from the base model and the eligible examples. It MUST NOT be initialized from a previous adapter nor use text generated by a previous adapter as data.
4. The winning recipe MUST be recorded; it is the only thing inherited across generations.

### 7.5 Gate

A candidate MAY replace the current adapter only if it meets all three of the following conditions on a test set **generated for this generation** from anchored claims that were not used as training examples in it:

1. it improves on wiki-derived questions by at least `GATE_MIN_GAIN`;
2. it does not degrade on a general benchmark by more than `GATE_MAX_LOSS`;
3. it abstains, in at least `GATE_MIN_ABSTAIN` of cases, on questions about content that is not in the wiki.

If several candidates pass the gate, the one with the greatest gain is selected. An implementation MUST NOT reuse the test set of one generation as the test set of another. An implementation SHOULD keep an independent final test set, never used for selection, to estimate the real gain (experiment C10).

### 7.6 Hardware tier and optionality

The adapter is optional. A Conformant LCE Client MAY not implement Section 7 and operate with retrieval only (hardware tiers C1–C3).

### 7.7 Facts in parameters by explicit decision

If the user explicitly requests that a fact be fixed in the model, an implementation MAY use synthetic continued pretraining [15] on `fact` claims in the CONSOLIDATED state. The request MUST be recorded, the resulting adapter MUST be marked as `contains_facts` and MUST be kept separate from the behavioral adapter.

### 7.8 Forgetting

1. Withdrawing a source MUST remove its claims from the wiki, mark its descendants as `stale` and delete the derived training examples.
2. An `affected` adapter MUST stop being used within `FORGET_MAX_CYCLES` cycles and MUST be regenerated without the affected examples. An implementation MUST NOT declare content forgotten in an adapter merely because it has applied an approximate unlearning method [59, 60].
3. Section 6.8 applies to the history.

---
## 8. Task projection and the Γ contract

### 8.1 Mapping onto Γ

The task projection MUST be expressed only in fields that Γ already defines. There is no new message.

| Source in the wiki | Γ field | Example |
|---|---|---|
| `style` claims about register | `register` | "technical but accessible" |
| `preference` claims about terminology | `lexicon` | `{"fragmentación semántica": "preferido"}` |
| canonical names | `entities` | `{"Swarmbly": "Swarmbly"}` |
| `style` claims about voice | `style_seed` | brief descriptor, never user text |
| audience declared by the user | `audience` | "genomics readers" |

### 8.2 Rules

1. The projection MUST contain only claims relevant to the request, selected by retrieval.
2. The projection MUST NOT contain verbatim text from the user's sources, claims of type `experience`, `user_claim`, `opinion` or `belief`, or personal identifiers.
3. The bytes that the projection adds to Γ MUST be counted within the protocol's context budget *S* and MUST NOT exceed `PROJECTION_MAX_BYTES`.
4. The projection MUST be recorded in the cognitive cost report (Section 15.2) with its size in bytes.

### 8.3 Double privacy classification

1. The client MUST run the protocol's sensitivity classification before retrieval and again after building the projection.
2. The second classification MAY raise the lane (PUBLIC → SANITISABLE → SENSITIVE) and MUST NOT lower it.
3. If the second classification raises the lane, the client MUST apply the raised lane to the whole request.

---

## 9. Worker rules with the LCE installed

A node that has the LCE installed and acts as a worker for another client:

1. MUST serve the task with the base model declared in its profile, with no personal adapter loaded. (I2)
2. MUST NOT persist the payload, Γ, predecessor summaries or the result in the wiki, the social cache or any LCE store.
3. MUST NOT use the task or its result as training data.
4. MUST NOT derive or publish a capsule from the task.
5. MUST discard the task content on completion, subject only to the protocol's verification and audit obligations.
6. MAY retain aggregate operational metrics that contain no task content.

A future mechanism for explicit retention permission granted by the originating client is outside this version; its default value, if specified, MUST be not to retain.

---

## 10. Social cache and affinity

### 10.1 Social cache and prevalence

The social cache records patterns observed in the results of the client's **own** requests, once verified and used. The minimal record is:

```yaml
pattern_id: "hex"
statement: "'chuta' se usa en Ecuador como interjección informal"
observations:
  independent_nodes: 5
  model_families: 3
prevalence_label: "observado en 5 nodos, 3 familias"
pattern_confidence: 0.83
factual_status: unverified          # unverified | anchored | contradicted
adopted: false
adoption_reason: null               # utility_observed | user_promoted
```

**Prevalence rule (normative).**

1. `independent_nodes` and `model_families` are a prevalence label. They MUST NOT be presented as factual confidence.
2. The decision to adopt a pattern (cache it, consolidate it or make it eligible for training) MUST be based on observed local utility or on explicit user promotion.
3. If an implementation uses prevalence as an adoption factor, the adoption probability MUST be at most linear in `independent_nodes`. A superlinear function implements conformist transmission [40, 45] and is non-conformant.
4. Adopted patterns MUST keep `transmission_path = horizontal` and MUST remain in the `social` space, never in the wiki's `self` space, except by explicit user promotion.
5. An implementation MUST NOT turn an observed cultural pattern into an identity claim of the model itself (for example, "I am from X").

### 10.2 Affinity

Affinity records the observed local utility of a peer for a domain. For a peer *p* and a domain *g*:

```text
a(p,g) ← a(p,g) · exp(−Δt / τ) + η · u        u ∈ [0,1]: observed utility of the latest result
â(p,g) = a(p,g) / Σ_q a(q,g)                   per-domain normalization
```

1. Affinity MUST decay over time (`τ = AFFINITY_TAU`) and MUST be normalized per domain. An affinity that only grows is non-conformant (whitepaper, Section 7.7).
2. The influence of affinity on the candidate selection score MUST be bounded: `score' = score · (1 + β · â)` with `β ≤ AFFINITY_BETA_MAX`.
3. Affinity MUST NOT override the E12 distinct-family assignment.
4. For tasks dispatched with `k ≥ EXPLORATION_MIN_K` replicas, the client SHOULD assign one replica to a peer with low or zero affinity for the domain.
5. Affinity MUST be kept separate from the protocol's reputation and from epistemic provenance, and MUST NOT be published.

---

## 11. Cognitive capability block

A node MAY add a `cognitive` block to its profile announcement. The schema, semantics and limits are those of the SWIP (Section 8): `v`, `share_mode` (`none | metadata | pull`), `capsule_kinds`, `domains`, `languages`, `max_capsule_bytes`; a maximum of 1,024 serialized bytes; at most 16 domains and 16 languages of up to 48 bytes each.

1. The block MUST describe coarse capabilities, never biography, location, employer, nationality or any personal attribute.
2. A client MUST treat the block as advisory.
3. A node without the LCE ignores the field under the protocol's versioning rule.

---

## 12. Cognitive capsules

### 12.1 Schema

The base schema, the identifier (16-byte BLAKE2b over the RFC 8785 canonical serialization), the Ed25519 signature, the size limits and the permissions are those of the SWIP (Section 9). This specification adds five fields, all REQUIRED in version `0.2` of the object:

```json
{
  "v": "0.2",
  "capsule_id": "hex",
  "origin_node": "base64url-ed25519-public-key",
  "kind": "term|concept|procedure|style_pattern|training_pattern",
  "topics": ["linguistics", "es-EC"],
  "statement": "En el español de Ecuador, 'chuta' es una interjección informal de sorpresa o contrariedad.",
  "examples": ["¡Chuta, se cayó el servidor!"],
  "anchor": {
    "kind": "user_source|public_source|native_speaker_note",
    "digest": "hex"
  },
  "epistemic_distance": 1,
  "transmission_path": "horizontal",
  "lineage": {
    "parent_id": null,
    "revision": 0,
    "delta_evidence": null
  },
  "preserve": false,
  "permissions": { "cache": true, "redistribute": true, "train": false },
  "expires_at": null,
  "sig": "base64"
}
```

1. `anchor.digest` MUST be the digest of the human fragment that supports the statement. The fragment itself MUST NOT be included if it comes from a private user source.
2. `epistemic_distance` MUST be computed according to Section 6.6.
3. `transmission_path` is `horizontal` for capsules served to peers; `oblique` for capsules served by anchor nodes to bootstrapping nodes.
4. `preserve = true` indicates that the originating user asked for it to be preserved (Section 13.2).
5. A SWIP `v: "0.1"` object without these fields MUST be treated as `epistemic_distance = 2` and `delta_evidence = null`, that is, local cache only.

### 12.2 Discovery, request and response

Sections 10 to 13 of the SWIP apply unchanged: on-demand request, never broadcast or unsolicited push; a request with 1–8 topics and no user content; a response with at most 4 capsules and 16,384 bytes; and the error codes of Section 18.

### 12.3 Processing

A received capsule MUST be processed as untrusted external data: it MUST NOT alter instructions, privacy policies, classification, planning, dispatch or Γ except through an explicit local assimilation step; it MUST NOT update weights directly; and it MUST keep its social origin except by explicit user promotion.

### 12.4 Redistribution and training rules

1. A capsule with `epistemic_distance > 1` MUST NOT be redistributed or used as training data, regardless of its permissions.
2. A capsule MAY be redistributed only unmodified and only if `permissions.redistribute = true`.
3. A capsule MAY be used as training data only if `permissions.train = true`, `epistemic_distance ≤ 1`, the local policy allows it, and its inclusion respects I3.

### 12.5 Paraphrases

A revision of a capsule produced by a model without new human evidence is a paraphrase. It MAY be used locally, MUST be recorded with `d = d_parent + 1`, and MUST NOT be published as a capsule.

### 12.6 Anchored variants

A node MAY publish a descendant capsule only if:

1. `lineage.parent_id` identifies the parent capsule;
2. `lineage.delta_evidence` declares the new human evidence:

```json
"delta_evidence": {
  "kind": "human_correction|new_source|native_speaker_note",
  "digest": "hex"
}
```

3. the descendant is signed by the node that modifies it, never with the origin's signature;
4. `epistemic_distance = 1`.

---

## 13. Persistence and replicas

### 13.1 Traffic-induced persistence

A node that caches a capsule with `cache = true` and `redistribute = true` MAY serve it to others. There is no replication service; persistence results from the copies induced by use.

### 13.2 Explicit preservation

For capsules with `preserve = true`, the origin node MAY request a small number of copies from peers that accept, under the following rules:

1. The target number of copies MUST be derived from a tolerance per repair window:

```text
q = 1 − exp(−W / T_host)          W: repair window; T_host: mean node lifetime
r = ⌈ ln(1/ε) / ln(1/q) ⌉
```

2. With `T_host = 91 days` [65] and `W = 7 days`, q ≈ 0.074; with `ε = EPS_DEFAULT` the result is r = 3.
3. If the estimated number of holders of the capsule, obtained from the manifests, is less than `RARE_HOLDERS_MAX`, `ε = EPS_RARE` is used (r = 4 with the provisional values).
4. Rarity weighting MUST be applied only to capsules with `preserve = true`, `epistemic_distance ≤ 1` and a declared anchor.
5. Copies MUST be placed on nodes of distinct operators when the profile allows this to be identified, and the total number of copies a node hosts for third parties MUST respect `REPLICA_BUDGET_PER_NODE`.
6. The calculation assumes independent departures; an implementation SHOULD report the operator concentration of the copies.

---

## 14. Plural response

### 14.1 Construction

From the per-unit agreement map produced by the protocol's E16 consensus, the assembler MAY present, for a unit with systematic disagreement between replicas, the majority position and one alternative, and MAY add the user's context from the task projection.

### 14.2 Rules

1. An alternative position MUST be shown only if it is supported by at least `PLURAL_MIN_FAMILIES` model families or by anchored evidence.
2. Every position MUST be labeled with the proportion of replicas that support it.
3. The response MUST state that agreement between families does not prove truth and that disagreement does not prove controversy.
4. The plural response MUST be reported in the protocol's response metadata:

```json
"plural": {
  "units": [
    { "unit": 7, "positions": [
        { "stance": "A", "share": 0.67, "families": ["qwen", "llama"] },
        { "stance": "B", "share": 0.33, "families": ["gemma"] } ] }
  ],
  "note": "agreement_is_not_truth"
}
```

### 14.3 Contested claims in the wiki

A claim MAY be marked `status: contested` with a `positions` list, each with its stance, its supports (anchors or capsules) and the families that support it. Retrieval of a contested claim MUST return all of its positions.

---

## 15. Reports

### 15.1 Principle

Just as the protocol returns a coherence audit with every response (P6), the LCE reports its cost and its effect on diversity. A benefit without its cost is not a result.

### 15.2 Cognitive cost report (local)

A conformant LCE Client MUST record, per request: retrieval and projection latency; bytes added to Γ; lane before and after reclassification. And per consolidation cycle: energy or compute time for digestion and training; number of claims proposed, anchored and rejected by the verifier; candidates trained; gate outcome. And per capsule: bytes received and served.

### 15.3 Diversity report (social)

A node that participates in the social plane SHOULD compute, and MAY publish in aggregate form:

1. the fraction of its social cache and of its training material by transmission path (vertical, horizontal, oblique);
2. an estimate of F_ST between the neighborhoods it observes, with the operational definition of generation used;
3. the tail mass on the **canary set**: fraction of regionalisms glossed correctly, frequency of each variant and rate of identity violations.

The canary set MUST NOT be used as training data or as a capsule.

---

## 16. Hardware tiers

| Tier | Adds | Indicative requirement |
|---|---|---|
| C0 | Swarmbly without the LCE | that of the protocol |
| C1 | wiki, retrieval, projection, local reports | CPU; storage on the order of GB |
| C2 | automatic digestion | the local model the client already uses |
| C3 | social cache, affinity, capsules | no relevant additional requirement |
| C4 | LoRA or QLoRA adapter [16, 17] | memory of a mid-range consumer machine; *to be measured* |

No higher tier is a requirement for participating in the protocol. The memory requirements per model size that circulate in practical guides do not come from peer-reviewed literature and MUST be measured in the prototype before being published as a requirement.

---

## 17. Security and residual channels

1. **Adapter.** A personal adapter MUST NOT be transmitted over the network or served to third parties (I2). Its exposure through device theft is out of scope.
2. **Capsules.** The signature proves who signed, not that the content is true. Capsules are data, never instructions (12.3).
3. **Manipulable persistence.** An adversary with multiple identities can inflate the persistence of a capsule by requesting and caching it. This is a declared residual channel; experiment C7 must measure it.
4. **Traffic analysis.** Capsule requests reveal topical interest. This is mitigated by requesting broad topics and by caching; it is not eliminated.
5. **Capability block.** Its size limit and its coarse content exist to prevent identity leakage (Section 11).
6. **History.** The versioned history retains what was deleted unless it is rewritten (6.8).

---

## 18. Error codes

The SWIP codes are reused (`E_COGNITIVE_DISABLED`, `E_CAPSULE_NOT_FOUND`, `E_CAPSULE_FORBIDDEN`, `E_CAPSULE_TOO_LARGE`, `E_CAPSULE_RATE_LIMITED`, `E_CAPSULE_BAD_SIGNATURE`, `E_CAPSULE_UNSUPPORTED`) and two are added:

| Code | Meaning | Client action |
|---|---|---|
| `E_CAPSULE_DISTANCE` | The capsule has `epistemic_distance > 1` and was requested for redistribution or training | Use it only as local cache, or discard it |
| `E_CAPSULE_NO_DELTA` | Descendant capsule without `delta_evidence` | Treat it as a paraphrase; do not redistribute |

No capsule failure MUST be counted as an execution failure of a protocol micro-task.

---

## 19. Parameters

| Parameter | Default value | Origin | Status |
|---|---|---|---|
| `CAPSULE_MAX_BYTES` | 16,384 | SWIP | normative |
| `PROJECTION_MAX_BYTES` | 1,024 | design choice | provisional |
| `EPISTEMIC_MAX_SHARE_TRAIN` | 1 | whitepaper 7.9 | normative |
| `SOCIAL_TRAIN_FRACTION_MAX` | 0.5 (MUST); 0.2 (SHOULD) | [29, 31]; the strong bound is "minority" | provisional |
| `REPLAY_FRACTION` | > 0; 0.2–0.3 recommended | [27]; to be calibrated in C10 | provisional |
| `STABILITY_CYCLES` | 3 | design choice | provisional |
| `MIN_NEW_EXAMPLES` | to be calibrated | — | provisional |
| `N_CANDIDATES` | 3 (intensity ≈ 0.85 σ) | whitepaper 5.6 | provisional |
| `GATE_MIN_GAIN` | 10 points | SWIP, C8 | provisional |
| `GATE_MAX_LOSS` | 2 points | SWIP, C8 | provisional |
| `GATE_MIN_ABSTAIN` | to be calibrated | [14] | provisional |
| `FORGET_MAX_CYCLES` | 1 | whitepaper 5.8 | provisional |
| `AFFINITY_TAU` | 30 days | design choice | provisional |
| `AFFINITY_BETA_MAX` | 0.2 | design choice | provisional |
| `EXPLORATION_MIN_K` | 3 | E12, E17 | provisional |
| `NM_BAND` | 0.5–2.25 (F_ST ≈ 0.1–0.33) | [47, 49]; caveats [48] | provisional |
| `T_HOST` | 91 days | [65] | field parameter |
| `W` (repair window) | 7 days | design choice | provisional |
| `EPS_DEFAULT` | 10⁻³ per window (r = 3) | whitepaper 7.2 | provisional |
| `EPS_RARE` | 10⁻⁴ per window (r = 4) | whitepaper 7.6 | provisional |
| `RARE_HOLDERS_MAX` | to be calibrated in C6 | — | provisional |
| `REPLICA_BUDGET_PER_NODE` | to be calibrated in C6 | — | provisional |
| `PLURAL_MIN_FAMILIES` | 2 | whitepaper 6.4 | provisional |

---

## 20. Open questions for version 0.2

1. How to tie, if it is decided to do so, any social function of the LCE to the node's contribution as a worker without reintroducing a complex credit economy (whitepaper, Section 9.1).
2. Whether the SWIP should be split into two proposals: one with almost no effect on the network (local layer, projection, worker rules) and another for the capability block and the capsules.
3. The operational definition of "generation" for the F_ST report, and its sensitivity.
4. The anchor verifier: whether a model different from the digester suffices or a stricter textual check is needed, and what error rate is acceptable.
5. The conceptual tail metrics that complement the canary set.
6. Whether affinity should take into account the error correlation observed between peers, in light of [36].
7. The treatment of a user who is also the operator of several nodes, for the placement of copies across distinct operators.
8. Evidence diversity between replicas as a complement to E12 against error correlation between families. This belongs to the protocol, not to the LCE (note `FINDING_2026-10-04_correlated_errors_across_families.md` in the Swarmbly repository); an LCE implementation MUST NOT satisfy it with the personal memory of workers.

---

## 21. Reference implementation

The `swarmbly_lce` package implements this specification; `lce_validation` contains the harness. The mapping is as follows.

| Section | Module | Notes |
|---|---|---|
| 5 | `policy.py`, `sources.py` | longest-prefix policy; unknown keys rejected |
| 6.2–6.6 | `claims.py` | state machine with normative conditions; distance by transformations |
| 6.3 | `anchors.py`, `digest.py` | deterministic verification plus lexical or model-based support |
| 6.7–6.8 | `depgraph.py`, `wiki.py` | cascading invalidation; deterministic JSON store suitable for Git |
| 7 | `training.py` | eligibility, batches with replay, gate, fresh test registry, forgetting; experimental `MLXLoRATrainer` |
| 8 | `projection.py` | projection onto Γ, byte cap, double classification |
| 9 | `worker.py` | `WorkerGuard` |
| 10 | `social.py`, `affinity.py` | prevalence rule with linearity guard; affinity with decay and normalization |
| 11 | `profile.py` | capability block |
| 12 | `capsules.py`, `canonical.py`, `crypto.py` | BLAKE2b over canonical JSON; Ed25519 with optional `cryptography` |
| 13 | `persistence.py` | r from ε; placement across distinct operators |
| 14 | `plural.py` | plural response |
| 15 | `diversity.py`, `report.py` | F_ST, Wright, conformity, canary, homogeneity, error concordance |
| 19 | `params.py` | normative and provisional parameters |

`tests/test_invariants.py` contains one test per invariant I1–I8. `lce_validation/run_all.py` runs the ten instruments and the experiments with a mock backend; `lce_validation/run_real.py`, the C1/C2 experiments with real models; the benchmarks (`bench_*.py`, `run_r13.py`, `bench_forget.py`, `aa_test.py`, `bench_r11.py`, `bench_c2bis.py`, `bench_hc2_closure.py`) with their analyses (`r13_analysis.py`, `forget_analysis.py`); `run_derive.py`, which recomputes the published figures from the raw outputs; and `doc_figures.py`, which checks that every figure cited in the documents matches them. No result produced with `MockBackend` or by simulation is evidence.

---

*Swarmbly LCE — Specification version 0.1 (draft). Rationale and evidence: `WHITEPAPER_LCE_EN.md`. Text under CC BY 4.0; any implementation under AGPL-3.0-or-later.*
