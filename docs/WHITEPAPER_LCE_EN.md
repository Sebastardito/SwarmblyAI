---
status: draft
lang: en
---

# Local Cognition and Anchored Transmission

## A local-first cognitive extension for Swarmbly: personal memory, user-model learning and lightweight knowledge transfer over untrusted volunteer nodes

**Sebastián A. Espinoza-Ulloa, Ph.D.**\
Independent Researcher\
ORCID: [0000-0003-1497-356X](https://orcid.org/0000-0003-1497-356X) · GitHub: [@Sebastardito](https://github.com/Sebastardito)

> **Note on affiliation and independence.** This work is carried out entirely in
> a personal capacity as an independent researcher. The author holds academic
> affiliations — Pontificia Universidad Católica del Ecuador and University of
> Saskatchewan — and employment at NRGene Canada, unrelated to the subject matter of
> this work. **None of these institutions has provided funding, materials,
> computing resources, personnel or institutional support for this project, and no
> institutional endorsement is claimed or implied.**
>
> **Relevant background.** The author holds a Ph.D. in Biology (University of
> Saskatchewan) in population genomics, and works on genetic improvement through
> selective breeding. The homologies from population genetics, quantitative
> genetics and cultural evolution used in this document derive from that
> background; Section 3 applies to each of them the whitepaper v2 criterion by
> which an analogy is accepted or discarded.

**Version 0.1 (draft) — 4 October 2026**

---

> ## Status of this document: DRAFT
>
> Version 0.1, dated 4 October 2026. **Draft preprint; not peer reviewed.**
> It is an extension of the protocol described in the whitepaper v2 [1] and does not
> modify it: nothing proposed here is part of specification v0.2
> or of v0.3.
>
> **Nothing this document proposes has been measured yet.** Each
> mechanism comes with its hypothesis, its experiment and its abandonment condition
> (Section 11), and the document will be published with the verdicts included, as
> the whitepaper v2 was. The figures that appear are calculations derived from
> published parameters or findings from the cited literature, never the author's own
> results.
>
> **Code and harness.** This version is published with a reference
> implementation (`swarmbly_lce/`) and a validation harness (`lce_validation/`).
> Six simulated instruments pass their instrument test and experiments C1, C2 and C10
> run end to end with a mock backend (Section 11.6). **None of
> that is evidence**: it shows that the measures respond to what they measure. The
> runs with real models are pending and will be reported in version 0.2.
>
> **Companion documents.** `SPEC_LCE_EN.md` (architecture and
> normative specification), `swips/SWIP-XXXX-local-cognitive-extension.md`
> (formal proposal in English for the protocol repository),
> `REFERENCES_LCE.md` (annotated bibliography) and the working drafts in
> `_archive/drafts/`.

---

## Contents

0. What this document is and where it comes from
1. Introduction
2. Background and related work
3. The method applied: which homologies serve here
4. Design principles
5. The local plane
6. Integration with the Swarmbly protocol
7. The social plane
8. Complete architecture and invariants
9. Economics and incentive
10. Privacy, security and adversary model
11. Evaluation: hypotheses, experiments and abandonment criterion
12. Limitations
13. Elements disclosed as prior art
14. Roadmap
15. Conclusion
16. References

---

## 0. What this document is and where it comes from

Swarmbly fragments the problem, not the model: an orchestrator on the client decomposes the request into semantic microtasks, dispatches them once to volunteer nodes that run complete small models, and assembles the results locally [1]. In that design the workers are deliberately almost stateless, and the client is the only unit that retains memory across requests. This document proposes what to do with that memory. It describes a **local cognitive extension (LCE)** in which each user keeps on their own device a readable and portable memory, a model that learns from them what they decide to teach it, and an optional, cheap way to share with other nodes the knowledge they wish to make public.

The proposal arose from a question the author asked: how to fine-tune a local model with its user's information without supervision, and whether the models in a network could learn from one another until they formed something resembling an organism, with neighborhoods of identity and knowledge that survives the disappearance of the nodes that originated it. That question went through four working drafts, preserved in `_archive/drafts/`. The first built a cognitive network parallel to Swarmbly, with a global knowledge graph, knowledge routing, a trust engine, gossip and active replication, and the author rejected it because it contradicted the principle that makes the protocol viable. The second (v0.2) rewrote the proposal as a local-first extension that reuses the existing primitives. The third (v0.3) subjected its analogies to the whitepaper v2 method and closed six gaps, among them model collapse and the clash with verification. The fourth (v0.4) rescued seven ideas from the exploratory phase that passed that same method. This document consolidates all four into a continuous text, with a new literature review that adds adverse evidence the drafts did not have.

**Table of changes from the drafts.**

| in the drafts | in this document |
|---|---|
| 200 sections in note form, with interleaved lists and pseudocode | **Rewritten** as a continuous paper of 16 sections; the normative detail moves to `SPEC_LCE_EN.md` |
| Principles P12–P16 stated as loose proposals (v0.2) | **Consolidated** with three new principles, P17–P19 (Section 4) |
| Diversity of model families as a guarantee of error independence | **Qualified** by the evidence of correlated errors across families and of homogeneity across models [35, 36] (Sections 2.6, 6.4 and LC3) |
| Conformity as a theoretical risk taken from human cultural evolution | **Supported** by measurements of conformity in LLMs [45] and by simulations of opinion dynamics with LLM agents [46] (Section 7.4) |
| The rule "the social is a minority" justified by a single result [29] | **Supported** by the formal stability condition of iterative retraining [31] and by the self-consuming result with fresh data [30] (Section 7.3) |
| The anchoring rule without a verification instrument | **Instrumented** with atomic-claim evaluation [20] and with the evidence that models do not cite reliably [21] (Section 5.2) |
| Forgetting in the weights as optional regeneration | **Turned into** the only verifiable path, in light of the negative results on unlearning [59, 60] (Section 5.8) |
| The diversity of local learning as a possible remedy for correlation across families | **Discarded** as a remedy within a request; recognized as a reduction of homogeneity across users (Sections 2.6 and 6.4, H-C17) |
| No code or harness | **Reference implementation** with 77 tests, one per invariant, and a **harness** with six instruments tested in simulation (Section 11.6) |
| Hypotheses H-C1–H-C15 scattered across three sections | **Gathered**, plus H-C16 and H-C17, with experiments C0–C12 and their kill conditions (Section 11) |

Two ideas from the exploratory phase entered the review and did not survive as mechanisms: the Hebbian neuron as a model of the network, which contributes only its failure mode, and horizontal gene transfer as a model of exchange between nodes, which brings no applicable instrument. Both are documented in Section 3, because the diagnosis of why they fail guides the design as much as the homologies that do transfer.

---

## 1. Introduction

### 1.1 A node without memory and a network without incentive

The whitepaper v2 states that the project's dominant risk is not technical [1, Section 16, L10]. Volunteer computing has gone from attracting on the order of a million participants to around two hundred thousand, and offering "network credits" in exchange for idle cycles does not explain why Swarmbly would meet a different fate. The underlying diagnosis is that classical volunteer computing asked for altruism: the volunteer gave their machine to someone else's problem and received nothing they wanted for themselves.

At the same time, Swarmbly's design leaves the most personal resource in the system unused. The client is the only stateful component, and every request it processes contains information about its user (their vocabulary, their register, their topics, their corrections) that is currently discarded when the request finishes. Commercial assistants solve that loss by storing the user's history on their servers, so that personalization becomes another form of concentration: whoever holds the memory holds the user. A protocol whose purpose is to democratize access to inference cannot solve it that way.

There is a third, less visible tension. The value the author attributes to a network such as Swarmbly is not only access to compute but **the diversity of responses**: models from different families, different users, different cultures. That diversity is threatened from two sides. Current language models tend to homogenize what they produce, across one another and relative to their training data [33, 34, 35], and any mechanism of learning between nodes that trains models on the output of other models runs the risk of collapsing precisely the rare variants that made the network valuable [28, 32].

### 1.2 The thesis

The thesis of this document is that **a local, portable, user-controlled cognitive state can reduce repeated work, improve personalization and preserve useful knowledge across nodes without destroying the economics, privacy and diversity that make Swarmbly viable**. The question is measurable, and it is formulated so that it can fail.

The architecture that supports this thesis has three planes. In the local plane, which lives entirely on the device, a readable wiki learns fast and a lightweight adapter learns slowly, with an epistemic layer that decides what may pass from memory to behavior. In the inference plane, Swarmbly does not change: personalization enters only through the global contract Γ that the protocol already defines, and workers serve their base model. In the social plane, which is optional, nodes request small capsules of written knowledge from one another, not weights, and keep them if they find them useful, so that what is used survives the disappearance of its origin without a replication service.

The shape of this architecture is not arbitrary. Each piece comes from a homology that passes the whitepaper v2 method or from an empirical result in the literature, and each brings its stated failure mode: catastrophic interference for local learning, model collapse and conformity for learning between nodes, overestimation through test reuse for adapter selection, transitive trust for provenance. Much of the design consists of the rules that prevent those failures.

### 1.3 Scope of the claims

Five claims a reader might expect are deliberately absent, and Section 12 develops each of them.

I do not claim that **the personal model learns facts**. The evidence is that fine-tuning a model with new knowledge performs worse than retrieving it and increases hallucination [13, 14], so in this design facts live in the wiki and only behavior goes to the weights.

I do not claim **verifiable forgetting in the weights** except through regeneration of the adapter. The available unlearning methods neither achieve effective forgetting nor withstand successive requests [59, 60].

I do not claim that **the diversity of model families guarantees independent errors**. The most recent evidence shows correlated errors among models from different architectures and developers [36] and homogeneity across models on open-ended tasks [35]. The LCE inherits that limitation from the protocol and does not resolve it.

I do not claim that **the network becomes more intelligent because it communicates**. That phrase from the exploratory phase is retained only as a measurable hypothesis about savings in repeated work (H-C4).

I do not claim to **solve the incentive problem of volunteer computing**. The extension offers a candidate mechanism and a metric that can refute it (Section 9), not a solution.

### 1.4 Contributions and structure

Section 2 situates the proposal against prior work, including the adverse evidence. Section 3 applies the whitepaper v2 method to the seven candidate homologies and discards three. Section 4 adds eight principles to the protocol's eleven. Sections 5 to 7 describe the three planes, and Section 8 brings them together into an architecture with eight invariants that any implementation must preserve. Section 9 deals with economics and incentive; Section 10, with privacy and the adversary model. Section 11 specifies the experiments and the conditions under which each component would be abandoned. Section 12 lists the limitations, Section 13 the elements that will be disclosed as prior art upon publication, and Section 14 the roadmap.

The substantive contributions are four. The first is a rule for dividing content between memory and weights, derived from the knowledge-injection literature and formalized as an epistemic layer with claim types and maturity states. The second is the translation of three results from population genetics and cultural evolution into quantitative design rules: a migration budget between neighborhoods, a rule against conformity, and rarity-weighted persistence with a number of replicas derived from a tolerance. The third is anchored variation, which reconciles the idea that shared knowledge should evolve with the constraint, imposed by model collapse, of not training on derivatives of derivatives. The fourth is adapter selection treated as artificial selection, with the breeder's equation as the instrument and test reuse as the failure mode.

---

## 2. Background and related work

### 2.1 Personalization of language models

LLM personalization has become established as a field with its own taxonomies [3] and evaluation benchmarks such as LaMP, which measures personalized generation across seven tasks and shows that profile retrieval improves base models [4]. The prior art closest to the local layer of this proposal is OPPU, which assigns each user a parameter-efficient fine-tuning (PEFT) module to store their behavioral patterns and preferences, and combines it with retrieval for knowledge that changes [5]. That division of labor, parameters for behavior and retrieval for knowledge, is the same one the LCE adopts, and arriving at it by two independent paths is an indication in its favor. Per-Pcs extends the idea to a collaborative regime in which users decompose their adapters into pieces that others can combine [6]. The LCE takes the opposite direction by default, sharing written knowledge rather than parameters, for reasons of privacy, verification and diversity that Section 7 develops.

### 2.2 Agent memory and model-maintained wikis

Agents with natural-language memory are the second antecedent. Generative Agents stores a complete stream of experiences, periodically synthesizes them into higher-level reflections and retrieves them for planning [8]; MemGPT manages memory tiers with techniques inspired by operating systems [9]; A-MEM organizes memories as a network of linked notes in the Zettelkasten manner, in which a new note can modify existing ones [10]. The LLM-maintained wiki pattern proposed by Karpathy [7] is the simplest and most readable version of this family: immutable raw sources, a Markdown wiki that the model writes and maintains, and three operations (ingest, query and check for contradictions). The LCE adopts that pattern as layer 1 because its representation is human-readable, versionable and decoupled from the model, three properties that coincide with the principles of local-first software: the data belong to the user, work without a network and outlive the tool that created them [11].

### 2.3 Knowledge injection: retrieval versus fine-tuning

The question of what should go into the weights now has an empirical answer. In the direct comparison between unsupervised fine-tuning and retrieval-augmented generation [12], retrieval consistently outperforms fine-tuning both for knowledge seen during pretraining and for new knowledge [13]. Gekhman et al. further show that examples with new knowledge are learned considerably more slowly than those consistent with what the model knows and that, once learned, they linearly increase the model's tendency to hallucinate [14]. To fix a fact in the parameters when the user demands it, synthetic continued pretraining generates many rephrasings of the same content and produces knowledge that adds to retrieval instead of replacing it [15]. As for the mechanism, LoRA [16] and its quantized variant [17] make fine-tuning viable on consumer hardware, and the systematic comparison with full fine-tuning shows that LoRA learns less but forgets less of what the base model knew [18]. Direct preference optimization makes it possible to use "preferred / rejected" pairs without a separate reward model [19].

Attribution is the other side of memory. FActScore decomposes a text into atomic claims and measures what fraction is supported by a reliable source, and found that a reference commercial model reached only 58 % on biographies [20]. In generation with citations, even the best models lacked complete support half of the time [21]. Both results matter for a wiki written by a model: the digester can invent, and its anchoring to the sources must be verified with code.

### 2.4 Continual learning and complementary systems

The theory of complementary learning systems explains why the mammalian brain separates a hippocampal system of fast learning from a neocortical system of slow consolidation: a distributed network that learns new information fast incorporates it at the expense of what it already knew [22]. That cost, catastrophic interference, was documented before the theory [23], and the update of the theory for artificial agents connects it with experience replay in deep learning [24]. In language models catastrophic forgetting is observed generally in the 1B to 7B parameter range during continual fine-tuning [26], which is exactly the range of Swarmbly nodes, and continual learning with replay preserves previous tasks in instruction-tuned models [27]. The regularization alternative, which penalizes changes to the weights important for previous tasks [25], requires keeping the state of the previous adapter, and Section 5.6 explains why the LCE prefers to regenerate each adapter from scratch.

### 2.5 Model collapse and homogenization

Training generative models recursively on data produced by previous models causes irreversible defects, and the first symptom is the disappearance of the tails of the original distribution [28]; the phenomenon can be described as a change in scaling laws that begins with the loss of the infrequent [32]. Without fresh real data in each generation of a self-consuming loop, the quality or the diversity of the models progressively decays [30]. Two results, however, bound the problem. Iterative retraining is stable if the initial model approximates the data well and the proportion of clean data is sufficiently large [31], and when synthetic data are accumulated alongside real data, instead of replacing them, the error remains bounded regardless of the number of iterations [29].

Homogenization also has a dimension that does not depend on retraining. Writing with a model fine-tuned with feedback reduces the diversity among texts by different authors [33]; models narrow their diversity relative to their own training data, and changing the sampling or the prompt does not correct it [34]; and different models produce surprisingly similar responses on open-ended tasks, an effect their authors call the "artificial hivemind" [35]. At the level of collective welfare, having all agents use the same algorithm can worsen the joint outcome even if that algorithm is individually the best [37], and current models reflect the opinions of human groups unevenly, with a misalignment that persists when one tries to steer them [38].

### 2.6 The main adverse evidence: correlated errors

The result that most affects this proposal is not about personalization but about the assumption on which Swarmbly's redundancy rests. Diversity-preserving dispatch (E12) assigns replicas to different model families because it assumes that their errors are approximately independent [1]. Kim et al. evaluated more than 350 models and found that, on one of the leaderboards studied, **two models agree on the answer 60 % of the time when both are wrong**, and that larger and more capable models correlate their errors even when they have different architectures and come from different developers [36]. The hivemind effect on open-ended tasks points in the same direction [35]. The LCE cannot correct this problem, which belongs to the protocol, but it can avoid aggravating it, and the rule of serving the base model (Section 6.3) exists partly for that reason: if nodes from different families trained adapters on the same capsules, they would add one more source of correlation.

One may ask whether the diversity generated by each user's own local learning corrects the problem, and the answer is that it does not within a single request. By design, workers serve their base model (Section 6.3), so what each client learns does not reach the replicas that E16 aligns. Even if it did, it would not change the structure of the errors: the adapter learns behavior and not facts (Section 5.3), and LoRA preserves the knowledge of the base model [18], and with it its errors. The correlation found by Kim et al. stems largely from what the models share before any personalization. In population-genetics terms it is **identity by descent**: the models share ancestry because they were pretrained on heavily overlapping corpora, and a local adapter resembles phenotypic plasticity, which changes expression, more than the incorporation of new alleles. The independence that a consensus needs requires another source of variation, and if anything provides it, it is the evidence on which each replica reasons, not its weights. That hypothesis belongs to the protocol and not to the LCE, and it has been recorded separately as a note for the next version of the whitepaper (`Swarmbly-AI/docs/FINDING_2026-10-04_correlated_errors_across_families.md`).

### 2.7 Decentralized learning

Federated learning trains a global model from local updates coordinated in rounds [62], and gossip learning eliminates the coordinator by exchanging models between peers, with competitive performance [63]. Both converge, by design, towards a common model, which is the opposite of what this proposal seeks, and both generate permanent traffic. Dynamic adapter composition makes it possible to combine LoRA modules for new tasks [64], but it requires the same model family and version, a condition that a network heterogeneous by design does not meet. Section 7.1 lists these alternatives as discarded.

### 2.8 Machine cultural evolution

The quantitative theory of cultural evolution distinguishes vertical, oblique and horizontal transmission, with different dynamics [39], and models transmission biases such as conformity, in which a variant is adopted with a probability disproportionate to its frequency [40], which reduces variation within groups and increases the difference between them [41]. The research program on "machine culture" holds that intelligent systems already alter the three processes of cultural evolution, variation, transmission and selection, and that chatbots function as new cultural models [42]. Open frameworks exist for simulating cultural evolution in LLM populations [43], and the norms that emerge in societies of LLM agents depend strongly on the base model [44]. Two recent measurements make the risk concrete for this proposal. LLMs show measurable conformity in collaborative settings, increasing with the size of the majority and with interaction time [45], and networks of LLM agents tend to converge towards consensus through a bias inherent to the model, whereas with an induced confirmation bias they fragment [46]. The outcome of a network of models therefore depends on the biases of its agents and not only on its topology.

---

## 3. The method applied: which homologies serve here

The whitepaper v2 establishes that a homology serves when it brings an instrument (a procedure, an inequality or a number applicable to the new problem) and that the homologies that transfer come accompanied by their failure mode [1, Section 3]. Its operational test has three questions: whether the homology brings an instrument, whether it brings the statement of what happens when its condition is violated, and whether the conditions of the source field hold here. The original LCE proposal arrived loaded with biological analogies, and this section subjects them to that test before building on any of them.

| candidate homology | instrument | failure mode | conditions | verdict |
|---|---|---|---|---|
| Complementary learning systems [22, 24] | interleaved replay; two learning rates | catastrophic interference [23] | partial: replay is deliberate sampling, not spontaneous reactivation | **transfers** (Section 5.5) |
| Wright's island model [47] | F_ST ≈ 1/(1+4Nm); migration budget | the inversion fails out of equilibrium, with selection or with finite islands [48] | partial: capsules are not neutral and the "generation" must be defined | **transfers as a starting point** (Section 7.5) |
| Cultural transmission and conformity [39, 40, 41] | pathway accounting; Δp = D·p(1−p)(2p−1) | conformity eliminates minority variants | yes, and measured in LLMs [45, 46] | **transfers** (Section 7.4) |
| Frequency-dependent selection [50] | negative selection maintains polymorphisms | it also maintains worthless variants | yes, with entry conditions | **transfers** (Section 7.6) |
| Artificial selection [51] | breeder's equation; restricted index | correlated response; overfitting to the criterion | yes | **transfers** (Section 5.6) |
| Hebbian neuron [52] | none applicable to the network | unbounded growth, corrected by normalization [53, 54] | no: nodes have owners, there is no central integration, they live 91 days on average | **failure mode only** (Section 7.7) |
| Horizontal gene transfer | none | not stated | no | **vocabulary** |
| "Organism" or "brain" | none | none | no | **vocabulary**; the exact reading is "population with cultural memory" |

Three observations on the table. The first is that the two homologies discarded as mechanisms fail for the same reason the whitepaper v2 found in the codon and *fountain codes*: they bring an attractive mechanism without the pathology that accompanies it. The Hebbian neuron was proposed as "nodes that communicate connect more", without saying that this rule, without normalization, grows without bound; and that unbounded growth is, in a network of nodes, exactly the echo chamber. The second observation is that the neural homology, even when discarded, leaves a useful rule: affinity between nodes decays and is normalized by domain. The third is that two of the homologies that transfer, Wright and frequency-dependent selection, do so with caveats about their conditions that the document states in full, and that is why they are used to set starting points and qualitative predictions, never exact values.

The reading of the word "organism" that survives, a word that has accompanied the proposal since its origin, is that of **a population with cultural memory**: individuals with owners who learn vertically from their users and horizontally from one another, whose diversity is governed by a migration budget, and whose memory survives the turnover of individuals through redundancy derived from a tolerance. It is less evocative than a brain and considerably more exact.

---
## 4. Design principles

The whitepaper v2 states eleven principles, P1 to P11 [1, Section 4], and the LCE modifies none of them. It adds to them under the same rule: each new principle comes out of a section of the document and decides something concrete. The first five come from draft v0.2; the last three, from revisions v0.3 and v0.4.

**P12 — Learn locally first; transmit only the abstraction that pays its network cost.** The network is used when its measured benefit exceeds its cost. By default, the extension adds no message to the protocol. (Sections 5 and 7)

**P13 — Personal memory is state; worker execution is work. They are not conflated.** A node that works for others serves its base model without an adapter, executes, returns and discards. The node owner's personal brain never touches other people's tasks. (Section 6.3)

**P14 — Repetition measures prevalence, not truth, and does not decide adoption.** That many nodes repeat something is a label that may be displayed; it is neither factual evidence nor a criterion for caching, consolidating or training. (Section 7.4)

**P15 — Preserve diversity before optimizing convergence, and report it.** Diversity is budgeted with a number (migration between neighborhoods) and measured with a statistic that the network can publish, in the spirit of P6. (Section 7.5)

**P16 — Shared cognition is optional and backward compatible.** A node without the LCE remains a fully valid Swarmbly worker, and a node with the LCE behaves towards one without it exactly as the current protocol does. (Section 6.6)

**P17 — Facts in the wiki, behavior in the weights.** Voice, register, terminology, procedures and formats go to the parameters. Facts are retrieved. (Section 5.3)

**P18 — Accumulate, never replace; variation comes from people.** Material from other nodes is always a minority, traceable to a human origin, and can only have descendants if it brings new human evidence. (Sections 7.3 and 7.8)

**P19 — What is not declared does not train.** The learning policy is explicit per source, and its default value produces a system that remembers but does not learn. (Section 5.7)

---
## 5. The local plane

### 5.1 Three layers that learn at different rates

The local plane has three layers, and their separation follows the complementary learning systems homology of Section 3. Layer 0 is the user's source space: a working folder into which the user places documents, writings, conversations, transcripts or code, which is kept immutable and serves as the single source of truth. Layer 1 is the wiki: Markdown pages that a local model writes and maintains from the sources, following the pattern of ingesting, querying and checking for contradictions [7]. It is the layer that learns fast, the hippocampal role. Layer 2 is the LoRA adapter: it learns slowly, is trained only when the device is idle, and receives only what layer 1 has consolidated. It is the neocortical layer.

Between the layers the principle that whitepaper v2 measured in its T08R3 experiment applies: the model extracts and the code aggregates [1, Section 15.4]. In the LCE the model digests sources and proposes claims, while the index, links, anchors, dependencies and revisions are deterministic code. This separation matters because models do not cite reliably [21] and because any decision that must be audited later (what entered training, why, from which source) has to be reproducible.

### 5.2 The epistemic layer

The wiki is not a collection of untyped notes. Every claim it contains carries four attributes, and together they form what this document calls the local epistemic layer.

The first is **anchoring**: every claim points to the exact fragment of the raw source from which it was extracted. The rule responds to a known failure of the model-maintained wiki pattern, which can store a hallucination and later retrieve it as if it were a fact. Its verification uses the logic of FActScore [20]: an atomic claim is anchored if the cited fragment supports it according to a verifier, and only anchored claims are eligible for any later use in training.

The second attribute is the **type**. A claim can be a fact about the world with an external source (`fact`), a claim, opinion or belief of the user (`user_claim`, `opinion`, `belief`), an open hypothesis (`hypothesis`), an episodic experience (`experience`), or a behavioral pattern (`preference`, `style`, `procedure`). The type decides the destination. If the user notes that a substance causes a disease, the system keeps it as a user claim with its source, retrieves it with attribution ("the user holds that…") and never treats it as a fact or trains on it as an assertion. Only the three behavioral types are eligible for the adapter.

The third is the **maturity state**. A claim moves through the states RAW, DIGESTED, ANCHORED, CONNECTED, CORROBORATED, CONSOLIDATED and, only for behavioral types, TRAINABLE. For a fact, CORROBORATED requires two independent human sources; for a style pattern, stability across several consolidation cycles. The states make slow consolidation explicit: nothing passes from memory to behavior for having been seen once.

The fourth is **provenance**, which records the epistemic distance of the claim from a human source and the path by which it arrived (vertical, from the user; horizontal, from another node; oblique, from established nodes towards a new one). Section 7 develops both.

The epistemic layer also includes two structures. A **dependency graph** links sources, claims, concepts, training examples and adapters with the semantics of a build system: when a source changes, is corrected or is forgotten, everything that depends on it is marked as stale and rebuilt in the next cycle. And a **versioned history**: since the wiki is Markdown, it lives in a local Git repository with one commit per consolidation cycle, so that a `diff` between two dates shows how what the user's model understands has changed, and a `revert` undoes a mistaken consolidation.

### 5.3 What goes into the weights and what does not

The most important decision of the local plane is the division between memory and parameters, and the literature of Section 2.3 settles it. Since retrieval outperforms fine-tuning for incorporating knowledge [13] and fine-tuning on new knowledge increases hallucination [14], **facts remain in the wiki and are served by retrieval**. Into the weights go the patterns that retrieval does not convey well because they are not statements but manners: the user's voice and register, preferred terminology, recurring procedures and formats. The choice of LoRA as the mechanism rests on the fact that it learns less and forgets less [18], the right trade-off for an adapter trained on little material on top of a base model that must retain its general capability. If the user insists on fixing a fact in the model, the route is synthetic continued pretraining [15], treated as an explicit and costly option.

This rule coincides with the one OPPU reached by another path [5], and it has a design consequence worth stressing: the wiki is the user's main asset and the adapter is a behavior cache that can be regenerated. If a better base model appears tomorrow, the user loses nothing; a new adapter is trained from the same wiki.

### 5.4 Unlabeled training data

Learning is unsupervised in the sense that nobody labels data, and the training examples come from three sources of different nature. The first is text written by the user, and only by the user, to train their voice; a document by another author placed in the folder would teach that author's style. The second is question-answer pairs generated from anchored claims in the wiki, each with its pointer to the source and accepted only if a verifier confirms that the answer follows from the cited fragment. The third is the user's corrections: every edit of a page or rewrite of an answer produces a "before / after" pair usable for direct preference optimization [19]. It is the system's only supervision and costs nothing extra.

### 5.5 Consolidation with interleaved replay

The consolidation cycle runs when the device is idle, connected to power and with enough new eligible material; there is no obligation to train at any fixed frequency. Following the homology of Section 3, each training batch **mixes new examples with a sample of already consolidated examples and with general text**, in a proportion that is recorded. The failure mode that replay prevents, catastrophic interference [23], is documented in Swarmbly's size range [26], and continual learning with replay has been shown to preserve earlier tasks in instruction-tuned models [27]. The falsifiable prediction is direct: an adapter trained without replay should degrade on questions about earlier consolidated material, and one trained with replay should not (H-C10).

### 5.6 Adapter selection as artificial selection

A new adapter does not replace the previous one merely by existing. Several candidates are trained with different recipes and the evaluation gate chooses, which turns each cycle into a generation of artificial selection. Quantitative genetics supplies the instrument [51]: the response to selection is the product of selection intensity, the accuracy of the criterion and the available variability. Choosing the best of 3 candidates is equivalent to an intensity of about 0.85 standard deviations, the best of 5 to 1.16 and the best of 10 to 1.54. Accuracy, the correlation between the gate score and the true quality of the adapter, is what dominates: with accuracy 0.3 the expected gain from choosing the best of 5 is about 0.35 standard deviations, and with 0.8 it rises to about 0.93. **Training more candidates yields little if evaluation is noisy**, and effort should go to evaluation first.

The gate has three conditions: the candidate improves on questions derived from the wiki; it does not worsen beyond a threshold on a general benchmark (the provisional thresholds of the SWIP, at least 10 points of improvement and at most 2 of loss, are a starting point); and it abstains on questions about content that is not in the wiki. The third condition guards against the effect of Gekhman et al. [14] and cannot be omitted. Taken together, the gate works as a restricted selection index, which maximizes one trait without allowing others to fall below a limit [51]; this is how genetic improvement controls correlated response, the second failure mode of the homology.

The first failure mode is overfitting to the criterion. Always selecting against the same test set makes the observed gain of the winner overestimate the real one, which is the problem of adaptive data analysis [55]. The LCE has an uncommon advantage here: the wiki is a practically inexhaustible source of new questions, so that **each generation is evaluated on a freshly generated test set** built from anchored claims that no candidate has seen.

There is a third rule, and it connects this section with model collapse. What is inherited across generations is the recipe (the eligible data, their mix with replay and the winning hyperparameters), not the weights: **every adapter is trained from the base model and the wiki, never from the previous adapter nor on text generated by it**. In this way there is no recursion of a model on its own output, the verifiable forgetting of Section 5.8 is the normal operation, and changing the base model costs the same as one more generation. It is also the reason why EWC-type regularization [25], which requires the state of the previous adapter, is not the default mechanism.

### 5.7 Learning policy

The user decides what their model learns, and that decision is written down. Each source or folder declares in a policy file what may be extracted from it: whether the text is authored by the user, whether it may train style or procedures, whether it feeds only the wiki, whether it retains episodic memory. The default value is "reference only", so that the most common error, forgetting to declare a folder, produces a system that remembers but does not learn, rather than one that learns what it should not. The authorship field enforces the rule of Section 5.4, and since the policy is recorded in the dependency graph, changing it marks as stale the examples that depended on it.

### 5.8 Forgetting

Forgetting a source in the wiki is immediate: it is deleted, its derivatives are marked and the affected pages are rebuilt. Forgetting it in an already trained adapter is not. Unlearning benchmarks show that baseline methods do not make a model behave as if it had never seen the data [59], and that the available algorithms degrade general utility and do not support successive requests [60]. For this reason **the only verifiable forgetting in the weights is to regenerate the adapter without the affected examples**, which Section 5.6 makes the normal operation. The Git history adds a failure mode of its own: a repository keeps in its history what was deleted from the current tree, so that forgetting requires rewriting the affected history, and backups must respect this.

---

## 6. Integration with the Swarmbly protocol

### 6.1 Personalization enters through Γ

The protocol's global contract Γ already includes the fields a personalization needs: audience, register, lexicon, entities and a style seed [2]. The LCE does not add a personalization package; it produces, for each request, a **task projection**: the minimum personal information relevant to that task, projected onto those fields. If the user prefers certain terms, they go into `Γ.lexicon`; their register goes into `Γ.register`; their canonical names, into `Γ.entities`. Workers receive what the task needs and never the full cognitive state. The projection competes with the rest of the context for the protocol's budget *S*, and therefore it must be a relevant compression, not a biography.

### 6.2 Double privacy classification

The protocol's sensitivity classification runs locally before content leaves the device [1, Section 13.4]. The LCE introduces a new risk: an innocuous question can become identifiable once personal memory is added to it. For this reason classification runs twice, before and after projection, and the second can only raise the lane, never lower it.

### 6.3 Workers serve the base model

The rule that a node working for others serves its base model with no adapter (P13) is not merely prudent; verification demands it. Layer 1 of the protocol's verification scheme binds a locality-sensitive commitment over the activations to the declared model, input and precision, and detects model substitution with full accuracy in the reported tests [1, Section 13.3]. A worker with its personal adapter loaded produces different activations, so it is indistinguishable from a node that substitutes its model: either it fails verification, or it publishes the adapter so that the commitment can be computed against it. The second way out is unacceptable, because an adapter trained on its user's voice and corrections is compressed personal information, and models can return near-verbatim training examples [57]; small adapters are less vulnerable to extraction than other forms of fine-tuning, but not immune [58]. Sampled audit, which re-executes tasks indistinguishable from real ones, suffers from the same problem. With the rule, verification layers 1 and 2 remain intact and the adapter never leaves the device.

The rule has a second motive, which Section 2.6 anticipated. If many nodes of different families trained adapters on the same social capsules, their errors would become correlated through that shared material, adding to the correlation between families that already exists [36]. The cost of the rule is that a worker's personal knowledge does not improve the service it provides to third parties, and this is accepted deliberately.

### 6.4 Plural response

The multiple-alignment consensus of E16 computes, for each unit of the response, the agreement between replicas of different families, and returns a map of low-confidence regions [1, Section 10.5]. The LCE proposes using that map not only to warn but to show: when replicas disagree systematically on a unit, the assembler can present the majority position and the alternative, and local memory adds the user's context. It is an implementation of Overton pluralism, which asks for the range of reasonable responses to be presented instead of converging on a single one [56], and it is the concrete form of the "democratization of response diversity" that motivated the proposal.

It has two failure modes. The first is false balance, presenting a marginal position as if it carried the same weight as the majority one; the rule is to show the minority position only when at least two families or anchored evidence support it, and always to label its proportion. The second is that disagreement does not prove controversy either, because it may reflect the error of a single family, and that agreement proves even less than the protocol assumed, in view of correlated errors [36] and homogeneity across models [35]: an agreement of three families can be a shared error. The plural response is therefore a presentation of uncertainty, subject to P6, and not a claim about the state of the debate in the world. As a complement, in tasks that admit replicas, one of them can be assigned to a peer of low local affinity, which counters the echo chamber with the same mechanism that E12 uses for family diversity.

There is, on the other hand, a form of diversity that the LCE does contribute and that should not be confused with the previous one. The artificial hivemind [35] describes homogeneity **across users**: different people who ask the same thing receive almost identical answers. The task projection injects into Γ each user's register, lexicon and style seed, so that two requests identical in content reach the workers with different contracts and produce different responses. This counters monoculture at population scale [33, 37] without touching the correlation of errors within a request, because all replicas of the same request share the same Γ. Hypothesis H-C17 separates the two so that they can be measured separately.

### 6.5 Learning from one's own results, not from other people's traffic

A worker sees fragments of other people's requests, and that does not entitle it to turn them into memory. The default rule is execute, return and discard. What the client can do is analyze the results of its own requests, once verified and used, in a local social summary that extracts terminology, domain patterns or ways of explaining without necessarily keeping the fragment. Any retention of other people's content would require explicit permission, and its default value is not to retain: the LCE cannot turn computational volunteering into involuntary data harvesting.

### 6.6 Compatibility

The extension respects the protocol's versioning rule, under which a participant must ignore unknown fields of a message instead of rejecting it [2]. The only optional addition to the node profile announcement is a small block of cognitive capabilities, and the capsule messages are new and optional. A node without the LCE sees no difference, and a node with the LCE that encounters one without it behaves exactly as protocol v0.2.

### 6.7 Hardware tiers

The extension does not require new hardware to participate. Tier C0 is Swarmbly unchanged; C1 adds the wiki and retrieval, which run on CPU with very little memory; C2 adds automatic digestion with the same local model the client already uses; C3 adds the social cache and capsules; and C4 adds LoRA or QLoRA fine-tuning [17], which needs the memory of a mid-range consumer machine. The specific memory requirements for each model size that circulate in practical guides do not come from peer-reviewed literature and must be measured in the prototype. A modest laptop with C1 and a workstation with C4 are full citizens of the same protocol.

---

## 7. The social plane

### 7.1 Written knowledge, not weights

The social plane is optional and is the only one that adds traffic. Its unit is the **cognitive capsule**: a small (at most 16 KiB), signed object that contains a statement of generalizable knowledge with its anchoring, its provenance and its separate permissions for caching, redistribution and training. A node announces only metadata on the topics it can serve; another requests the capsule when it needs it, uses it, and keeps it if it proved useful. There is no broadcast, no gossip, no global graph.

Sharing written knowledge instead of parameters is the most debatable decision of the social plane, because prior art exists in the opposite direction [6, 64]. The reasons are four. An adapter is compressed personal information and cannot be inspected [57]; a capsule can be read. An adapter only serves nodes of the same model family and version [64], and the network is heterogeneous by design. Training on other nodes' adapters correlates errors (Section 6.3). And capsules weigh kilobytes where an adapter weighs tens or hundreds of megabytes. Federated learning and gossip learning [62, 63] are discarded for a more basic reason: they converge towards a common model, which is the opposite of a diverse population. Adapter composition remains a later optimization for nodes of the same family, not a base mechanism.

### 7.2 Traffic-induced persistence

If a node A holds a capsule, B requests and caches it, C requests and caches it, and A disappears, the capsule remains in B and in C. The more useful a piece of knowledge is, the more copies appear without any replication service. It is the cheap answer to the original question of what happens to the knowledge of a node that goes down, and it has a structural bias that Section 7.6 corrects: it favors the popular.

For what a user explicitly decides to preserve, the number of replicas is not chosen by eye but derived from a tolerance, with the same logic as E17 [1]. If a node's lifetime is exponential with a mean of 91 days [65], the probability that a given node leaves the network within a weekly repair window is q = 1 − e^(−7/91) ≈ 0.074. If lost copies are replenished every week, the probability of losing all r copies in the same window is qʳ, and for a tolerance ε per window r ≥ ln(1/ε)/ln(1/q) suffices. Accumulated over a year, the probability of losing a preserved capsule is approximately 25 % with r = 2, 2.1 % with r = 3 and 0.16 % with r = 4. The calculation assumes independent departures, and the concentration of hosts among few users that the protocol documents [1, Section 13.6] breaks that assumption, so copy placement must require distinct operators, just as E12 requires distinct families.

### 7.3 Accumulate, never replace

Model collapse is the central failure mode of "models learning from each other" [28], and its first symptom, the loss of the tails [32], attacks precisely the regionalisms and infrequent terminology that a diverse network should preserve. The correction has empirical and formal support: accumulating synthetic data alongside real data bounds the error [29], and iterative retraining is stable if the proportion of clean data is large enough [31]. In the LCE this translates into three constraints. Material derived from other nodes is always a minority in any training batch, and the user's own corpus is never discarded. Every capsule used for training must be traceable to a declared human origin. And a capsule derived from another capsule without new human evidence is neither redistributed nor trained on. It is worth declaring what these results do not cover: they study the recursion of a single model lineage on its own output, and the Swarmbly network is a different case, with many lineages from different families exchanging summarized material. The transfer is directional and not quantitative, and the social experiment must measure collapse directly.

### 7.4 Cultural transmission and conformity

The theory of Cavalli-Sforza and Feldman distinguishes three transmission paths with different dynamics [39]: vertical (in the LCE, from the user to their model), horizontal (between nodes) and oblique (from established nodes, in particular the bootstrap anchor nodes [1, Section 14.4], towards new nodes). Horizontal transmission propagates faster and homogenizes more, and oblique transmission concentrates the risk in the bootstrap, when all new nodes receive from the same few sources. The instrument is accounting: each piece of local knowledge records its path, and the horizontal and oblique proportion in training is bounded.

The failure mode is conformity. With two variants and a conformist bias of strength D, the frequency p of a variant changes per generation according to Δp = D·p(1−p)(2p−1) [40]: the majority variant grows and the minority one disappears. A regional variant held by 20 % of a neighborhood falls below 1 % in about 37 generations with D = 0.1, in 18 with D = 0.2 and in 12 with D = 0.3. The risk is not theoretical: LLMs show measurable conformity, increasing with the size of the majority [45], and networks of LLM agents converge through biases specific to the model [46]. The social cache stores precisely how many nodes repeat a pattern, and if that count decided what is adopted with a probability that grows more than linearly with it, the network would implement conformity without having decided to. For this reason the count **is a prevalence label and not an adoption criterion** (P14): it is shown, it feeds confidence in the pattern, and adoption is decided by observed local utility. Henrich and Boyd add a nuance that cuts both ways: conformity reduces variation within groups but increases the difference between them [41], so it is a plausible mechanism for the emergence of the neighborhoods the original proposal sought and, at the same time, the one that impoverishes each of them.

### 7.5 Neighborhoods and migration budget

Neighborhoods are not global clusters but an emergent effect of local affinity caches: a client that reuses certain peers for a certain domain because they proved useful. The homology that puts a number on diversity between neighborhoods is Wright's island model [47]: nodes as individuals, capsules as variants, neighborhoods as subpopulations, and sharing capsules between neighborhoods as migration. The equilibrium relation F_ST ≈ 1/(1+4Nm) gives direct numbers. With Nm = 25, F_ST ≈ 0.01 and neighborhoods become indistinguishable; with Nm = 0.1, F_ST ≈ 0.71 and they are isolated, so that drift eliminates rare variants within each one; the "one migrant per generation" rule [49] corresponds to F_ST ≈ 0.2. From this comes an initial band for the migration budget, approximately 0.5 ≤ Nm ≤ 2.25, that is 0.1 ≤ F_ST ≤ 0.33, and a diversity statistic that the network can report (P15).

The failure mode of this homology is as well documented as the instrument. Inverting F_ST to estimate Nm rests on assumptions (infinite islands, symmetric migration, equilibrium, absence of selection) that are almost never met, and the relation can be off by orders of magnitude [48]. Here at least two are violated: capsules are not neutral because they are selected for utility, and "generation" is not defined in a network of persistent nodes, so it is fixed operationally as one consolidation cycle and the band is sensitive to that choice. For this reason the instrument is used in one direction: as a starting point and as a qualitative prediction (high Nm homogenizes, low Nm isolates), which the social experiment will confirm or refute.

### 7.6 Rarity-weighted persistence

Traffic-induced persistence is positive frequency-dependent selection, because the probability that a capsule has copies grows with the number of nodes that already use it, and that regime erodes the rare. The corrective homology is negative frequency-dependent selection, whose established property is to maintain stable polymorphisms [50]. The application is to make the tolerance stricter for the rare: a preserved capsule whose estimated number of holders falls below a threshold receives a smaller ε and, through the relation of Section 7.2, a larger r. Moving from ε = 10⁻³ to ε = 10⁻⁴ per week raises r from 3 to 4. The number of holders is estimated from the manifests, with no global census. The failure mode is symmetric: negative selection also maintains worthless variants, and a little-spread false claim would, by its rarity, be a candidate for more copies. For this reason the weighting applies only to capsules preserved by a user, anchored to human evidence with epistemic distance no greater than 1 and under a replica budget bounded per node. Rarity modulates how many copies are given to what someone decided to keep; it does not decide what is kept.

### 7.7 Affinity with Hebbian control

The affinity cache records which peers have been useful for which domains, and it is the practical implementation of neighborhoods. Its risk is the failure mode that the Hebbian neuron contributes: without normalization, affinity grows without bound and peer selection concentrates on the same peers, which is the echo chamber [52]. Neuroscience corrected that growth with weight-vector normalization [53] and with homeostatic scaling [54], and the equivalent design rule is that **affinity decays over time and is normalized per domain**, with a bounded influence on dispatch and always subordinate to the family diversity of E12. Affinity is kept separate from the protocol's reputation, which answers whether a worker executes correctly, and from epistemic provenance, which answers what support a piece of information has.

### 7.8 Anchored variation

The original proposal imagined that a capsule enters the network, each neighborhood reinterprets it, and the useful versions propagate while the others go extinct. The rule of Section 7.3, for its part, forbids redistributing derivatives of derivatives. The two are reconciled by distinguishing where variation comes from. A "mutation" produced because a model rewrites a capsule contributes no new information, only noise correlated with that model, and its propagation is exactly the recursion that causes collapse. A legitimate variant incorporates **new human evidence**: a speaker who qualifies the register of an expression, a source that corrects a procedure, a user correction. A capsule can have descendants only if each descendant declares that evidence; without it, the revision is a paraphrase that can be used locally but is neither redistributed nor trained on. Selection is done by use and inheritance by caching, as the original idea proposed, but variation has to come from outside the system of models, which is also the condition that the self-consumption literature demands: new real data in each generation [30].

### 7.9 Epistemic distance

Every claim records its distance from a human source, measured in **transformations and not in copies**: a capsule cached by B and served to C is the same capsule signed by its origin and does not increase the distance. Distance 0 is a source of the user; distance 1, a claim extracted by a model from an anchored human source, the user's own or that of a capsule's origin node; distance 2 or more, anything derived from distance-1 material without new human evidence. The rule fits in one line: what has distance greater than 1 can be cached and retrieved with its label, but is neither redistributed nor enters training. An anchored variant returns to distance 1. On the other hand, half of the exploratory idea that turned distance into transitive trust between nodes is discarded: transitive trust is what a Sybil adversary exploits by creating chains of identities that vouch for each other [61], and the protocol is not Sybil-resistant in the strong sense [1, Section 13.6]. Distance is a datum about the content, not a score about the nodes.

---
## 8. Complete architecture and invariants

### 8.1 View of the three planes

The figure brings together Sections 5 to 7. Everything that was not in the Swarmbly architecture is local to the device or is a rule about what already circulates, except capsules, which are optional and on demand. `SPEC_LCE_EN.md` develops each component with its schemas.

```text
╔══════════════════════════════════════════════════════════════════════════════╗
║ LOCAL PLANE — user's device (Local Cognitive Extension)                      ║
║                                                                              ║
║  Layer 0  Source space (immutable) + learning policy                   5.7   ║
║                         │ digestion: the model extracts, code aggregates     ║
║                         ▼                                                    ║
║  Layer 1  Markdown wiki, learns fast ("hippocampus")               5.1–5.2   ║
║          anchored claims · type · maturity · provenance                      ║
║          dependency graph · Git history · disputed claims                    ║
║            ┌────────────┴─────────────┐                                      ║
║            ▼                          ▼                                      ║
║   Retrieval (facts,           Training queue: TRAINABLE only,                ║
║   attributed beliefs,         distance ≤ 1, social in minority         5.3   ║
║   episodes)                           │                                      ║
║            │                          ▼                                      ║
║            │        Layer 2  LoRA adapter, learns slowly ("neocortex")       ║
║            │                interleaved replay · N candidates from base +    ║
║            │                wiki · gate with fresh test            5.5–5.6   ║
║            └────────────┬─────────────┘                                      ║
║                         ▼                                                    ║
║        Personal model = base + adapter + memory (for its user only)          ║
║  Social cache (prevalence ≠ adoption) · Affinity (decays, normalizes) 7.4–7.7║
║  Capsule store (copies through use; rarity-weighted r)                7.2,7.6║
╚═════════════════════════════════════╤════════════════════════════════════════╝
                                      │ user request
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║ INFERENCE PLANE — Swarmbly with no changes to the core                       ║
║  retrieval → task projection → double classification → router → DAG →        ║
║  Γ (register, lexicon, entities, style_seed) → candidates (E12, bounded      ║
║  affinity, 1 exploration replica) → workers with base model → triage →       ║
║  verification layers 1–3 → E16 consensus → plural response → assembly →      ║
║  coherence audit → social summary of own results                     6.1–6.5 ║
╚═════════════════════════════════════╤════════════════════════════════════════╝
                                      │ optional, with permission, on demand
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║ SOCIAL PLANE — capsules, the only source of new traffic                      ║
║  manifest → pull (≤ 16 KiB, signed) → use → observed benefit → cache         ║
║  · descendants only with new human evidence                            7.8   ║
║  · distance > 1: labeled cache; not redistributed nor trained on       7.9   ║
║  · migration Nm ≈ 0.5–2.25 (F_ST ≈ 0.1–0.33) as starting point         7.5   ║
║  · r from tolerance ε, copies on distinct operators                    7.2   ║
║  · no gossip, no global graph, no transitive trust, no adapters              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 8.2 Invariants

The invariants are listed because they are what any implementation must preserve and what the SWIP turns into normative requirements. Each one has an associated hypothesis and an abandonment condition in Section 11.

- **I1.** Facts live in the wiki; only behavioral patterns go into the weights (P17; Sections 5.2–5.3).
- **I2.** A worker serving third parties uses its base model with no adapter and discards the task content (P13; Sections 6.3 and 6.5).
- **I3.** Accumulate, never replace: social material is a minority, traceable to a human origin and with epistemic distance no greater than 1 for training or redistribution (P18; Sections 7.3 and 7.9).
- **I4.** Capsule variation comes from new human evidence, not from model paraphrases (P18; Section 7.8).
- **I5.** Prevalence is a label, not an adoption criterion (P14; Section 7.4).
- **I6.** Every adapter is trained from the base model and the wiki, with interleaved replay and evaluation on fresh tests (Sections 5.5–5.6).
- **I7.** Diversity is budgeted and reported: bounded migration, F_ST and tail mass (P15; Sections 7.5 and 11.3).
- **I8.** What the user did not declare in their learning policy is not trained on (P19; Section 5.7).

### 8.3 A complete walkthrough: "chuta"

One example runs through the entire architecture and, multiplied, becomes an instrument. A user who speaks Ecuadorian Spanish writes expressions such as "¡chuta, se cayó el servidor!" ("chuta, the server went down!") in their own texts. The learning policy marks those texts as theirs, and the digester extracts two anchored claims: one of type `style` (the user uses the interjection in an informal register, distance 0) and one linguistic `fact` (in Ecuadorian Spanish, "chuta" is an informal interjection of surprise or annoyance, distance 1). The first can reach the voice adapter when it reaches the TRAINABLE state; the second stays in the wiki and is served by retrieval. When the user asks for a text in their register, the task projection carries the term into `Γ.lexicon` and the register into `Γ.register`, and the workers, which serve their base model, receive only that.

If the user allows it, the linguistic claim is published as an anchored horizontal capsule. A second node, whose user writes from another country and receives a fragment with "chuta" in one of its own tasks, observes it in its social cache. The count of nodes and families that repeat the pattern remains a prevalence label, separate from factual confidence and without deciding adoption. If that node later needs the meaning, it requests the capsule, uses it and keeps it only if it proved useful. What it learns is "in Ecuador 'chuta' is used as…", never "I am Ecuadorian". If the origin node disappears, the capsule survives in the copies induced by use and, being rare and preserved, with a larger r. If a third speaker qualifies its usage, the revision enters as an anchored variant; if a model merely paraphrases it, the paraphrase stays local.

The example matters because a regionalism lives in the tails of the distribution, which model collapse [28, 32] and conformity [40] eliminate first. Multiplied, it becomes the **canary set** of Section 11.3.

---

## 9. Economics and incentive

### 9.1 A selfish reason to install the client

Classical volunteer computing asked for altruism. A client that maintains a model of its own that learns from its user is, by contrast, a selfish reason to install the software, and the idle compute the node contributes to the network becomes a side effect of something the user already wanted. It is, in all likelihood, the strongest strategic argument of the extension against L10 [1, Section 16].

The argument has its failure mode and is presented with it. If the LCE is useful without the node serving the network, the rational user installs the client for the LCE and disables worker mode: the selfish incentive attracts users, but not capacity. The rule of serving the base model does not solve this, because it says what is served and not whether anything is served. There are two possible designs and both have a cost. Tying certain social functions of the LCE, such as capsule retrieval, to the node's contribution reintroduces a credit accounting that the protocol treats with caution [1, Section 14.1]. Leaving contribution enabled by default and measuring how many users keep it on guarantees nothing, but it measures the question. This document does not choose: it states it as a hypothesis (H-C9) and leaves L10 open in the protocol, now with a candidate mechanism and a metric that can refute it.

### 9.2 Costs

The costs of the extension are very unbalanced, and it is worth making this explicit because they determine who can participate. What is cheap is almost everything: maintaining the wiki, the index, the embeddings, the dependency graph, the social cache and affinity, which run on CPU and occupy on the order of megabytes to a few gigabytes. The intermediate cost is digestion, which uses the same local model the client already loads for orchestration. What is expensive is training, and that is why the design makes it optional, infrequent, conditional on the machine being idle and regenerable. The default network cost is zero; with capsules, it is on the order of kilobytes per useful request, against the hundreds of megabytes of an adapter. Section 11 includes an accounting of the **cognitive cost**: the time, energy and traffic that the extension adds, which must be reported alongside its benefits with the same discipline with which the protocol reports its coherence tax (P6).

### 9.3 The extension within the governance model

The LCE inherits the protocol's license and governance: code under AGPL-3.0-or-later, texts under CC BY 4.0, and protocol changes through SWIPs [1, Section 14.2]. What is purely local (the wiki, the adapter, the policy, affinity) does not require a SWIP because it does not affect interoperability; what touches the node announcement or adds messages (the capability block and capsules) does. The draft SWIP proposes separating the two into two proposals if the discussion advises it.

---

## 10. Privacy, security and adversary model

The extension keeps the protocol's trust model and adds new surfaces, which are listed with their mitigation and with what the mitigation does not cover.

**Leakage through memory.** Personal memory can make a request identifiable that was not. Double classification (Section 6.2) raises the lane when this happens, but it depends on a local classifier that can fail; its error rate is an object of measurement (experiment C3), not an assumption.

**Leakage through the adapter.** A personal adapter can return fragments of its data [57, 58]. The mitigation is structural: the adapter never leaves the device nor is served to third parties (I2). What it does not cover is theft of the device, which falls outside the scope of the protocol as with any local software.

**Leakage through identity.** The cognitive capability block of the node announcement could reveal traits of the user if it were detailed. For this reason it is coarse (broad domains, languages, capsule availability) and optional, and it never contains identity, location or a preference profile.

**Social poisoning.** A malicious node can publish false or biased capsules. The mitigations are adoption by observed utility (not by popularity), the separation between confidence in the pattern and factual confidence, the epistemic distance limit, the minority share of social material in training, and the signature, which proves who signed but not that the content is true. What they do not cover is a Sybil adversary that fabricates many nodes that request and cache the same false capsule to inflate its persistence; rarity weighting does not aggravate this, because it applies only to capsules preserved by a user and anchored, but traffic-induced persistence is manipulable, and experiment C7 must measure it.

**Prompt injection.** A capsule or a returned fragment is data, never an instruction, just as in the protocol's assembler [1, Section 13.3]. Digestion of other nodes' capsules runs with the same output-handling defenses and with per-type content schemas.

**History and backups.** The Git history and backups keep what the user deleted. Forgetting must rewrite the affected history and propagate to backups (Section 5.8).

**Traffic analysis.** Capsule requests reveal interest in a topic. This is mitigated by requesting broad topics from manifests and by caching, but it is not eliminated, and it remains declared as a residual channel.

---
## 11. Evaluation: hypotheses, experiments and abandonment criterion

### 11.1 Hypotheses

The hypotheses are numbered as in the drafts to preserve traceability. Each one carries the condition that refutes it.

- **H-C1 — Local memory.** Retrieval over the wiki improves personalized tasks compared with the same model without memory. It dies if it does not improve on the local benchmark or on an external personalization benchmark [4].
- **H-C2 — Task projection.** A small projection into Γ preserves the user's preferences better than sending the prompt alone, without significantly increasing the redundancy rate ρ. It dies if the increase in ρ exceeds the gain.
- **H-C3 — Affinity.** Local affinity improves the quality / cost ratio of dispatch compared with selection without affinity. It dies if it does not improve measurably.
- **H-C4 — Capsule utility.** On-demand capsules reduce repeated requests by more than it costs to transmit them. It dies if their traffic and complexity exceed the savings, even on a benchmark designed to favor reuse.
- **H-C5 — Traffic-induced persistence.** Useful capsules survive node churn through usage-induced caching, without global replication. It dies if the observed survival falls below that predicted by the model of Section 7.2.
- **H-C6 — Retrieval before training.** Retrieval captures most of the benefit; fine-tuning adds benefit only on stable behavioral patterns. It dies if fine-tuning does not clearly beat retrieval alone on behavior.
- **H-C7 — Accumulation.** With social material that is a minority, traceable to human origin and with no re-sharing of derivatives, the mass in the tails does not decrease over the exchange cycles. It dies if the tails contract in a sustained way under the three restrictions.
- **H-C8 — Migration band.** Utility on infrequent content is maximal in an intermediate band of Nm and falls with high Nm and with low Nm. It dies if it is monotonic in Nm, in which case Wright's instrument reverts to vocabulary.
- **H-C9 — Incentive.** Among the users who adopt the LCE, a sufficient fraction keeps worker mode active at 30 and 90 days to increase net capacity. It dies if the LCE increases installations without increasing served capacity.
- **H-C10 — Interleaved replay.** An adapter trained without replay loses performance on questions about consolidated material earlier, and one with replay does not. It dies if there is no difference, and the CLS homology reverts to vocabulary.
- **H-C11 — Conformity.** With prevalence as a label and adoption by utility, the frequency of minority variants in the canary set remains stable within each neighborhood; without the rule, it follows the conformist dynamics. It dies if there is no difference between conditions.
- **H-C12 — Anchored variation.** Allowing only descendants with new human evidence preserves the diversity of the canary set, and allowing paraphrases reduces it. It dies if both conditions preserve it equally.
- **H-C13 — Rarity.** Rarity weighting reduces the loss of preserved rare capsules at a bounded replica cost. It dies if the reduction does not offset the traffic or if it preferentially replicates low-quality material.
- **H-C14 — Plural response.** Showing the alternative position when replicas systematically disagree improves perceived calibration without increasing confidence in marginal positions. It dies if users do not distinguish it from a single response or if it increases the adoption of weakly supported positions.
- **H-C15 — Adapter selection.** With fresh tests per generation, the gain of the selected adapter on an independent final test matches that predicted by the intensity and the estimated accuracy; with a reused test, it is overestimated. It dies if reuse produces no measurable overestimation.
- **H-C16 — Correlation through shared material.** If workers served adapters trained on common capsules, the error correlation between replicas of different families would increase with the overlap of those capsules. This is the prediction that justifies I2; it dies if no increase is observed, in which case I2 rests only on verification and privacy.
- **H-C17 — Diversity across users.** Task projection reduces the homogeneity among the responses that different users receive for the same open-ended query, measured in the manner of Infinity-Chat [35], without changing the correlation of factual errors between replicas of the same request. It dies if the homogeneity across users does not decrease; and if the error correlation also changed, the analysis of Sections 2.6 and 6.4 would be wrong and should be revised.

### 11.2 Experiments

Experiments C0 to C8 come from the SWIP draft; C9 to C12 are new. None of them is to be run with `MockBackend` as evidence: the mock backend validates the measuring instrument, and its results are reported separately, as in the protocol.

- **C0 — Baseline.** Swarmbly without the LCE on the same task set.
- **C1 — Local memory.** Wiki with retrieval compared with C0 (H-C1).
- **C2 — Task projection.** With and without projection into Γ, measuring preference and ρ (H-C2); and, on a set of open-ended queries requested by different user profiles, the homogeneity across users and the correlation of factual errors between replicas (H-C17).
- **C3 — Privacy reclassification.** Rate of requests whose lane rises after projection, and error rate of the classifier.
- **C4 — Affinity.** Dispatch with and without affinity, with the exploration quota (H-C3).
- **C5 — Capsule utility.** Requests avoided versus bytes transmitted (H-C4).
- **C6 — Persistence.** Capsule survival under simulated churn with a mean lifetime of 91 days, with and without rarity weighting (H-C5, H-C13).
- **C7 — Social poisoning.** False capsules injected by a fraction of nodes, including an adversary that inflates persistence with multiple identities.
- **C8 — Retrieval versus fine-tuning.** Wiki with retrieval versus wiki with retrieval and adapter, on factual and behavioral tasks (H-C6).
- **C9 — Social simulation.** N nodes with distinct corpora exchange capsules under several levels of Nm; measured are F_ST, utility on rare content, tail mass on the canary set, frequency of minority variants with and without the prevalence rule, diversity with and without anchored variation, and error correlation between replicas (H-C7, H-C8, H-C11, H-C12, H-C16). The LLM-population simulation framework of Perez et al. [43] is a candidate harness.
- **C10 — Local learning.** Voice adapter versus retrieval alone: whether the user can tell their own text from the generated text blind, whether hallucination outside the wiki increases, whether replay prevents forgetting, and whether the gain of the selected adapter is overestimated with a reused test (H-C10, H-C15).
- **C11 — Plural response.** User study on perceived calibration and on adoption of weakly supported positions (H-C14).
- **C12 — Pilot cohort.** Retention of worker mode at 30 and 90 days among users with and without the LCE (H-C9).

### 11.3 The canary set

The cross-cutting instrument of the social experiments is a **canary set**: a list of a few dozen to a few hundred regionalisms per variety of a language, with glosses contributed and verified by native speakers, used exclusively for measurement and never for training. Three things are measured on it over the cycles: the fraction of items that the nodes gloss correctly (tail mass), the frequency of each variant within each neighborhood (to detect the conformist curve) and the rate of identity violations, that is, first-person responses that attribute to the model a membership it has only observed. It is cheap, interpretable by any reader and sensitive precisely to the failures that this extension can cause. Its limitation is that it measures lexical rather than conceptual tails, and it must be complemented with metrics of semantic dispersion.

### 11.4 Cognitive cost

Each experiment reports, alongside its benefit, the cost that the extension adds: local latency of retrieval and projection, energy of digestion and training, storage, capsule traffic and bytes added to Γ. A benefit without its cost is not a result.

### 11.5 Abandonment criterion

The extension, or one of its parts, stays out of the protocol if any of these conditions is met, stated before measurement. Affinity is abandoned if it does not measurably improve dispatch. Capsules are abandoned if their traffic and complexity exceed the savings, and in that case Swarmbly keeps only the local layer. Social learning is abandoned if it contracts the tails even under the accumulation restrictions. Behavioral fine-tuning is abandoned if it does not clearly beat retrieval; factual fine-tuning is abandoned without further experiment, because the evidence [13, 14] already suffices. The capability block is abandoned if its information leakage exceeds its utility. The plural response is abandoned if it increases the adoption of weakly supported positions, even if it improves satisfaction. And the entire extension stays out if it requires continuous GPU training, synchronized global state, intensive gossip, exchange of large adapters, central knowledge services or mandatory disclosure of identity, because that contradicts the logic that allows Swarmbly to democratize inference on consumer hardware.

### 11.6 The harness and the testing of the instruments

The method of whitepaper v2 also applies to the measurements: an instrument is tested before it is used to decide anything. The `lce_validation/` harness contains six instrument tests, each a simulation with a prediction stated in advance and a pass criterion, and `run_all` exits with an error if any of them fails. The **anchoring** test fabricates claims in three ways (invented content words on a real span, a real claim pointed at the wrong span, and a stale file fingerprint) and requires the verifier to accept at least 95 % of the supported claims and at most 5 % of the fabricated ones. The **conformity** test simulates demes of agents that adopt a 20 % minority variant by the conformist rule or by the linear one, and requires the former to lose it and the latter to keep its mean, and the I5 guard to flag a threshold rule as non-conformant. The **migration** test simulates the Wright–Fisher island model and requires the simulated F_ST to decrease with Nm and to follow 1/(1+4Nm) within a factor of 2 in the band of Section 7.5. The **persistence** test simulates node churn with a mean lifetime of 91 days and weekly repair, and requires the simulated annual loss to match qʳ and placement on a single operator to be much worse. The **selection bias** test requires the realized gain to follow i·r·σ, the estimate on the selection set to be inflated and the estimate on a fresh set not to be. The **collapse** test self-trains a long-tailed categorical distribution and requires that replacing erodes the tail, that accumulating bounds it and that anchored variation preserves it.

All six pass in the published version, and the test is robust to the seed. Alongside them, experiments C1, C2 and C10 run through the real code (digestion, anchoring, wiki, projection into Γ, gate) with `MockBackend`, a rule-based backend that injects the effects one wants to detect, among them errors shared across families. With it, projection reduces the homogeneity across users and leaves the agreement of errors across families untouched, which is the prediction of H-C17, but it does so by construction, and for that reason it is reported as validation of the pipeline and never as a result. The `run_real` script repeats C1 and C2 against real models served by Ollama or any OpenAI-compatible server, refuses to run if any model does not respond or if all of them belong to the same family, and labels its output as real. Its scope must be declared with any figure: a synthetic corpus of one user, three projected users, ten factual questions and a canary set not yet verified.

---

## 12. Limitations

Stated plainly, as in the protocol. A proposal whose failure modes are documented can be improved by people who did not write it.

**LC1 — Nothing is measured.** This document is an architecture with hypotheses. The numbers it contains are calculations on published parameters or findings of others, and none of them is a result of the LCE.

**LC2 — The personal model does not learn facts.** This is a decision backed by the evidence [13, 14], but it has an experience cost: the user who expects "their model to know" something will have to understand that it is their wiki that knows it.

**LC3 — Family diversity is weaker than the protocol assumed, and local learning does not repair it.** Errors correlated across families [36] and homogeneity across models [35] reduce what E12, E16 and the plural response can promise; agreement across families can be a shared error. The LCE avoids aggravating the problem (I2) but does not correct it: local learning diversifies expression and reduces homogeneity across users, not the error correlation within a request, because that correlation comes from shared pretraining and the adapter does not touch facts (Sections 2.6 and 6.4). The candidate lever, diversity of evidence between replicas, is a hypothesis of the protocol, not of the LCE.

**LC4 — Population homologies transfer with caveats.** Wright's model assumes neutrality, equilibrium and infinite islands [48], and the "generation" must be defined operationally. The numbers in Section 7.5 are starting points.

**LC5 — The results on collapse do not cover Swarmbly's case.** They study a lineage that is retrained on its own output [28, 29, 31]; a network of many families exchanging summaries is a different case, and the transfer is directional.

**LC6 — Forgetting in the weights is verifiable only by regenerating.** Unlearning methods are not reliable [59, 60]; regeneration costs one training cycle per forgetting request that affects the adapter.

**LC7 — Traffic-induced persistence can be manipulated.** An adversary with many identities can inflate the persistence of a capsule by requesting and caching it. The protocol is not Sybil-resistant in the strong sense [1, Section 13.6], and neither is the LCE.

**LC8 — The replica calculation assumes independent departures.** The concentration of hosts in a few operators breaks it; requiring distinct operators mitigates this without guaranteeing it.

**LC9 — The incentive may attract users without capacity.** The mechanism of Section 9.1 has its own failure mode, the free rider, and it is not solved.

**LC10 — The epistemic layer depends on verifiers that fail.** Anchor verification, type classification and privacy classification use models, and models do not cite or classify reliably [20, 21]. The design measures their error rates; it does not eliminate them.

**LC11 — The canary set measures lexical tails.** Conceptual tails (ways of reasoning, cultural assumptions) require metrics that this document does not specify.

**LC12 — The homogenization of the user themselves.** Writing with a model reduces diversity across authors [33]. A model that learns its user's voice and gives it back could, over time, narrow that very voice. There is no designed mitigation beyond the fact that the voice is trained only on text written by the user, which may itself already have been written with the model's help.

---
## 13. Elements disclosed as prior art

> **Status note.** Elements EC1–EC11 **do not yet constitute prior
> art**: they will with the publication of this document in a dated
> registry (Zenodo or the public repository), not before. The decision on when
> to publish is open and depends on the same consideration that the protocol
> recorded in `publication/PRIOR_ART.md` about grace periods.

The elements will be disclosed with the intent that they enter the public domain for patenting purposes; the author reserves copyright in the text under CC BY 4.0 and licenses any implementation under AGPL-3.0-or-later.

**EC1.** In a distributed inference system that dispatches microtasks with a shared global contract, **personalization by projection**: the client retrieves from a local memory only the information relevant to the task and projects it onto existing fields of the contract (register, lexicon, entities, style seed), with a second sensitivity classification after projection that can only raise the lane. (Sections 6.1–6.2)

**EC2.** The rule by which a node that executes tasks for third parties **serves its base model without a personal adapter** and discards the content, as a simultaneous condition of compatibility with commitment-based verification over activations, of adapter privacy and of no error correlation through shared material. (Section 6.3)

**EC3.** A **local epistemic layer** in which each claim of a model-written memory is anchored to the span of its source, typed (fact, user claim, belief, hypothesis, experience, preference, style, procedure) and given a maturity state, where only behavioral types in the trainable state feed an adapter, with a dependency graph that invalidates in cascade and with regeneration of the adapter as the forgetting mechanism. (Sections 5.2, 5.3 and 5.8)

**EC4.** Small, signed, on-demand, non-broadcast **cognitive capsules**, with separate permissions for caching, redistribution and training, whose persistence in the network arises from the copies induced by their use. (Sections 7.1–7.2)

**EC5.** A **replica count derived from a tolerance** from the node departure rate, r ≥ ln(1/ε)/ln(1/q), with a stricter tolerance for rare and preserved capsules and with placement of copies on distinct operators. (Sections 7.2 and 7.6)

**EC6.** **Anchored variation**: a unit of shared knowledge may have descendants only if each one declares new human evidence, together with an epistemic distance measured in transformations rather than in copies, which limits redistribution and training to a distance no greater than 1. (Sections 7.8–7.9)

**EC7.** The rule of **prevalence as a label**: in a system that observes how many peers repeat a pattern, the probability of adopting, consolidating or training it grows no more than linearly with that count, together with the accounting of the route of arrival (vertical, horizontal, oblique) of each piece of knowledge. (Section 7.4)

**EC8.** A **migration budget** between emergent neighborhoods of a network of models, expressed as a band of Nm and reported as an F_ST statistic. (Section 7.5)

**EC9.** **Generational adapter selection** with a test set freshly generated from an anchored memory in each generation, inheritance of the recipe and not of the weights (each adapter is trained from the base model), and a restricted-index gate that requires abstention outside the memory. (Section 5.6)

**EC10.** A **plural response** built from the per-unit agreement map of a consensus between replicas of different families, which presents the alternative position only with minimum support and always labeled with its proportion. (Section 6.4)

**EC11.** A **canary set** of regionalisms verified by native speakers, used exclusively to measure tail mass, conformist dynamics and identity violations in a network of models that exchange knowledge. (Section 11.3)

---

## 14. Roadmap

The roadmap follows the protocol's principle of not claiming before measuring, and each stage ends in a verdict. Stage 0 fixes the harness: specification, task set, initial canary set and cognitive-cost accounting, all before implementing any component. The first prototype is strictly local and without network: wiki with anchoring, epistemic layer, retrieval and task projection into Γ, evaluated with C0 to C3. The second prototype adds the adapter with replay and generational selection, evaluated with C8 and C10; if fine-tuning does not beat retrieval, layer 2 is withdrawn and the LCE remains as memory plus projection. The third prototype is a social simulation without deployment, with simulated nodes on real backends, evaluated with C4 to C7 and C9; if the capsules do not pay their cost, the social plane is withdrawn. Only after those verdicts is the discussion of the SWIP opened in the protocol repository, considering whether the local part and the capsule part are better separated into two proposals. The plural response (C11) and the pilot cohort (C12) require real users and come last.

With this version, stage 0 and the code of the first two prototypes are implemented and tested (Section 11.6), with a real LoRA trainer for Apple Silicon as an experimental component. What separates version 0.1 from a first verdict is not code but runs: C1, C2 and C8 with real models, and the verification of the canary set by native speakers.

---

## 15. Conclusion

The proposal from which this document was born was ambitious: that each user should have a mini brain of their own capable of learning from them, that those brains should learn from one another, and that the resulting network should be a diverse organism whose knowledge would survive the loss of its parts. The version that survives the method of whitepaper v2 is more modest in its form and, I suspect, more solid in its substance.

The personal brain lives in the client, where Swarmbly already concentrates state, and it is made above all of text: a readable, anchored, typed and versioned wiki, from which a lightweight adapter learns only the user's way of speaking and working, never their facts. The network does not become another network: personalization enters through a contract the protocol already has, workers keep serving their base model, and verification remains intact. Learning between nodes exists, but as an optional exchange of written knowledge, whose variation has to come from real people, whose adoption depends on utility and not on popularity, and whose memory is preserved by use and protected when it is rare.

What the literature review adds to that form is a catalog of named failure modes: catastrophic interference, model collapse, conformity, overestimation through test reuse, transitive trust, unlearning that does not unlearn and, above all, the correlation of errors between models that the protocol assumed to be independent. None of them is resolved by declaring it. All of them are left, instead, with a rule that avoids them or with an experiment that measures them.

"Organism" thus finds its exact reading: a population with cultural memory. Owned individuals, who learn vertically from their users and horizontally from one another, whose diversity is budgeted and reported, and who know how to show their disagreements instead of hiding them. If the extension works, each Swarmbly node will gradually become more useful to its owner **while remaining cheap, autonomous and replaceable**, and the protocol will have moved from democratizing access to processing to democratizing control over memory as well. If it does not work, Section 11 says exactly which parts to withdraw.

---

## 16. References

> **Numbering.** Markers [1]–[65] correspond to `REFERENCES_LCE.md`,
> where each entry carries its usage annotation and its verification mark. The
> entries marked there with `[STD]` are cited according to their standard
> bibliographic record, and those marked ⚠️ have an unconfirmed field; both must be checked
> before publication. The rest were verified against the online source between
> 3 and 4 October 2026.

### Swarmbly

[1] Espinoza-Ulloa, S. A. (2026). *Semantic fragmentation and stochastic assembly, version 2: A protocol for decentralized language-model inference over untrusted volunteer nodes* (Whitepaper v2). Zenodo. https://doi.org/10.5281/zenodo.23031305

[2] Espinoza-Ulloa, S. A. (2026). *Swarmbly AI* (Version 2.0.0; protocol specification v0.2 and reference implementation) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21956743

### Personalization and agent memory

[3] Zhang, Z., Rossi, R. A., Kveton, B., Shao, Y., et al. (2025). Personalization of large language models: A survey. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2411.00027

[4] Salemi, A., Mysore, S., Bendersky, M., & Zamani, H. (2024). LaMP: When large language models meet personalization. In *Proceedings of the 62nd Annual Meeting of the ACL* (pp. 7370–7392). https://doi.org/10.18653/v1/2024.acl-long.399

[5] Tan, Z., Zeng, Q., Tian, Y., Liu, Z., Yin, B., & Jiang, M. (2024). Democratizing large language models via personalized parameter-efficient fine-tuning. In *Proceedings of EMNLP 2024* (pp. 6476–6491). https://doi.org/10.18653/v1/2024.emnlp-main.372

[6] Tan, Z., Liu, Z., & Jiang, M. (2024). Personalized pieces: Efficient personalized large language models through collaborative efforts. In *Proceedings of EMNLP 2024* (pp. 6459–6475). https://doi.org/10.18653/v1/2024.emnlp-main.371

[7] Karpathy, A. (2026, April 4). *llm-wiki.md* [GitHub Gist]. https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

[8] Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. In *Proceedings of UIST 2023*. https://doi.org/10.1145/3586183.3606763

[9] Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). MemGPT: Towards LLMs as operating systems. *arXiv*. https://arxiv.org/abs/2310.08560

[10] Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., & Zhang, Y. (2025). A-MEM: Agentic memory for LLM agents. In *Advances in Neural Information Processing Systems 38 (NeurIPS 2025)*. https://arxiv.org/abs/2502.12110

[11] Kleppmann, M., Wiggins, A., van Hardenberg, P., & McGranaghan, M. (2019). Local-first software: You own your data, in spite of the cloud. In *Proceedings of Onward! 2019* (pp. 154–178). ACM. https://doi.org/10.1145/3359591.3359737

### Knowledge injection, PEFT and attribution

[12] Lewis, P., Perez, E., Piktus, A., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. In *Advances in Neural Information Processing Systems 33*. https://arxiv.org/abs/2005.11401

[13] Ovadia, O., Brief, M., Mishaeli, M., & Elisha, O. (2024). Fine-tuning or retrieval? Comparing knowledge injection in LLMs. In *Proceedings of EMNLP 2024* (pp. 237–250). https://doi.org/10.18653/v1/2024.emnlp-main.15

[14] Gekhman, Z., Yona, G., Aharoni, R., Eyal, M., Feder, A., Reichart, R., & Herzig, J. (2024). Does fine-tuning LLMs on new knowledge encourage hallucinations? In *Proceedings of EMNLP 2024* (pp. 7765–7784). https://doi.org/10.18653/v1/2024.emnlp-main.444

[15] Yang, Z., Band, N., Li, S., Candès, E., & Hashimoto, T. (2025). Synthetic continued pretraining. In *ICLR 2025*. https://arxiv.org/abs/2409.07431

[16] Hu, E. J., Shen, Y., Wallis, P., et al. (2022). LoRA: Low-rank adaptation of large language models. In *ICLR 2022*. https://arxiv.org/abs/2106.09685

[17] Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L. (2023). QLoRA: Efficient finetuning of quantized LLMs. In *Advances in Neural Information Processing Systems 36*. https://arxiv.org/abs/2305.14314

[18] Biderman, D., Portes, J., González Ortiz, J. J., Paul, M., Greengard, P., Jennings, C., King, D., Havens, S., Chiley, V., Frankle, J., Blakeney, C., & Cunningham, J. P. (2024). LoRA learns less and forgets less. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2405.09673

[19] Rafailov, R., Sharma, A., Mitchell, E., Ermon, S., Manning, C. D., & Finn, C. (2023). Direct preference optimization: Your language model is secretly a reward model. In *NeurIPS 2023*. https://arxiv.org/abs/2305.18290

[20] Min, S., Krishna, K., Lyu, X., Lewis, M., et al. (2023). FActScore: Fine-grained atomic evaluation of factual precision in long form text generation. In *Proceedings of EMNLP 2023*. https://arxiv.org/abs/2305.14251

[21] Gao, T., Yen, H., Yu, J., & Chen, D. (2023). Enabling large language models to generate text with citations. In *Proceedings of EMNLP 2023*. https://arxiv.org/abs/2305.14627

### Continual learning and complementary systems

[22] McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). Why there are complementary learning systems in the hippocampus and neocortex. *Psychological Review, 102*(3), 419–457. https://doi.org/10.1037/0033-295X.102.3.419

[23] McCloskey, M., & Cohen, N. J. (1989). Catastrophic interference in connectionist networks: The sequential learning problem. *Psychology of Learning and Motivation, 24*, 109–165. https://doi.org/10.1016/S0079-7421(08)60536-8

[24] Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). What learning systems do intelligent agents need? Complementary learning systems theory updated. *Trends in Cognitive Sciences, 20*(7), 512–534. https://doi.org/10.1016/j.tics.2016.05.004

[25] Kirkpatrick, J., et al. (2017). Overcoming catastrophic forgetting in neural networks. *Proceedings of the National Academy of Sciences, 114*(13), 3521–3526. https://doi.org/10.1073/pnas.1611835114

[26] Luo, Y., Yang, Z., Meng, F., Li, Y., Zhou, J., & Zhang, Y. (2023). An empirical study of catastrophic forgetting in large language models during continual fine-tuning. *arXiv*. https://arxiv.org/abs/2308.08747

[27] Scialom, T., Chakrabarty, T., & Muresan, S. (2022). Fine-tuned language models are continual learners. In *Proceedings of EMNLP 2022* (pp. 6107–6122). https://doi.org/10.18653/v1/2022.emnlp-main.410

### Collapse, homogenization and correlated errors

[28] Shumailov, I., Shumaylov, Z., Zhao, Y., Papernot, N., Anderson, R., & Gal, Y. (2024). AI models collapse when trained on recursively generated data. *Nature, 631*(8022), 755–759. https://doi.org/10.1038/s41586-024-07566-y

[29] Gerstgrasser, M., Schaeffer, R., Dey, A., Rafailov, R., Sleight, H., Hughes, J., Korbak, T., Agrawal, R., Pai, D., Gromov, A., Roberts, D. A., Yang, D., Donoho, D. L., & Koyejo, S. (2024). Is model collapse inevitable? Breaking the curse of recursion by accumulating real and synthetic data. In *COLM 2024*. https://arxiv.org/abs/2404.01413

[30] Alemohammad, S., Casco-Rodriguez, J., Luzi, L., Humayun, A. I., Babaei, H., LeJeune, D., Siahkoohi, A., & Baraniuk, R. G. (2024). Self-consuming generative models go MAD. In *ICLR 2024*. https://arxiv.org/abs/2307.01850

[31] Bertrand, Q., Bose, A. J., Duplessis, A., Jiralerspong, M., & Gidel, G. (2024). On the stability of iterative retraining of generative models on their own data. In *ICLR 2024*. https://arxiv.org/abs/2310.00429

[32] Dohmatob, E., Feng, Y., Yang, P., Charton, F., & Kempe, J. (2024). A tale of tails: Model collapse as a change of scaling laws. In *Proceedings of ICML 2024*, PMLR 235, 11165–11197. https://proceedings.mlr.press/v235/dohmatob24b.html

[33] Padmakumar, V., & He, H. (2024). Does writing with language models reduce content diversity? In *ICLR 2024*. https://arxiv.org/abs/2309.05196

[34] Wu, F., Black, E., & Chandrasekaran, V. (2025). Generative monoculture in large language models. In *ICLR 2025*. https://arxiv.org/abs/2407.02209

[35] Jiang, L., Chai, Y., Li, M., Liu, M., Fok, R., Dziri, N., Tsvetkov, Y., Sap, M., Albalak, A., & Choi, Y. (2025). Artificial hivemind: The open-ended homogeneity of language models (and beyond). In *NeurIPS 2025, Datasets and Benchmarks*. https://arxiv.org/abs/2510.22954

[36] Kim, E. M., Garg, A., Peng, K., & Garg, N. (2025). Correlated errors in large language models. In *Proceedings of ICML 2025*, PMLR 267, 30038–30066. https://proceedings.mlr.press/v267/kim25e.html

[37] Kleinberg, J., & Raghavan, M. (2021). Algorithmic monoculture and social welfare. *Proceedings of the National Academy of Sciences, 118*(22), e2018340118. https://doi.org/10.1073/pnas.2018340118

[38] Santurkar, S., Durmus, E., Ladhak, F., Lee, C., Liang, P., & Hashimoto, T. (2023). Whose opinions do language models reflect? In *ICML 2023*. https://arxiv.org/abs/2303.17548

### Cultural evolution, LLM populations and conformity

[39] Cavalli-Sforza, L. L., & Feldman, M. W. (1981). *Cultural transmission and evolution: A quantitative approach* (Monographs in Population Biology 16). Princeton University Press.

[40] Boyd, R., & Richerson, P. J. (1985). *Culture and the evolutionary process*. University of Chicago Press.

[41] Henrich, J., & Boyd, R. (1998). The evolution of conformist transmission and the emergence of between-group differences. *Evolution and Human Behavior, 19*(4), 215–241. https://doi.org/10.1016/S1090-5138(98)00018-X

[42] Brinkmann, L., Baumann, F., Bonnefon, J.-F., Derex, M., Müller, T. F., Nussberger, A.-M., Czaplicka, A., Acerbi, A., Griffiths, T. L., Henrich, J., Leibo, J. Z., McElreath, R., Oudeyer, P.-Y., Stray, J., & Rahwan, I. (2023). Machine culture. *Nature Human Behavior, 7*(11), 1855–1868. https://doi.org/10.1038/s41562-023-01742-2

[43] Perez, J., Léger, C., Ovando-Tellez, M., Foulon, C., Dussauld, J., Oudeyer, P.-Y., & Moulin-Frier, C. (2024). Cultural evolution in populations of large language models. *arXiv*. https://arxiv.org/abs/2403.08882

[44] Vallinder, A., & Hughes, E. (2025). Cultural evolution of cooperation among LLM agents: Extended abstract. In *Proceedings of the 24th International Conference on Autonomous Agents and Multiagent Systems (AAMAS 2025)* (pp. 2771–2773). IFAAMAS. https://arxiv.org/abs/2412.10270

[45] Weng, Z., Chen, G., & Wang, W. (2025). Do as we do, not as you think: The conformity of large language models. In *ICLR 2025*. https://arxiv.org/abs/2501.13381

[46] Chuang, Y.-S., Goyal, A., Harlalka, N., et al. (2024). Simulating opinion dynamics with networks of LLM-based agents. In *Findings of NAACL 2024*. https://arxiv.org/abs/2311.09618

### Population and quantitative genetics

[47] Wright, S. (1931). Evolution in Mendelian populations. *Genetics, 16*(2), 97–159. https://doi.org/10.1093/genetics/16.2.97

[48] Whitlock, M. C., & McCauley, D. E. (1999). Indirect measures of gene flow and migration: F_ST ≠ 1/(4Nm+1). *Heredity, 82*(2), 117–125. https://doi.org/10.1038/sj.hdy.6884960

[49] Mills, L. S., & Allendorf, F. W. (1996). The one-migrant-per-generation rule in conservation and management. *Conservation Biology, 10*(6), 1509–1518. https://doi.org/10.1046/j.1523-1739.1996.10061509.x

[50] Ayala, F. J., & Campbell, C. A. (1974). Frequency-dependent selection. *Annual Review of Ecology and Systematics, 5*, 115–138. https://doi.org/10.1146/annurev.es.05.110174.000555

[51] Falconer, D. S., & Mackay, T. F. C. (1996). *Introduction to quantitative genetics* (4th ed.). Longman.

### Hebbian plasticity and its control

[52] Hebb, D. O. (1949). *The organization of behavior: A neuropsychological theory*. Wiley.

[53] Oja, E. (1982). Simplified neuron model as a principal component analyzer. *Journal of Mathematical Biology, 15*(3), 267–273. https://doi.org/10.1007/BF00275687

[54] Turrigiano, G. G., Leslie, K. R., Desai, N. S., Rutherford, L. C., & Nelson, S. B. (1998). Activity-dependent scaling of quantal amplitude in neocortical neurons. *Nature, 391*(6670), 892–896. https://doi.org/10.1038/36103

### Adaptive evaluation and pluralism

[55] Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., & Roth, A. (2015). The reusable holdout: Preserving validity in adaptive data analysis. *Science, 349*(6248), 636–638. https://doi.org/10.1126/science.aaa9375

[56] Sorensen, T., Moore, J., Fisher, J., Gordon, M., Mireshghallah, N., Rytting, C. M., Ye, A., Jiang, L., Lu, X., Dziri, N., Althoff, T., & Choi, Y. (2024). Position: A roadmap to pluralistic alignment. In *Proceedings of ICML 2024*. https://arxiv.org/abs/2402.05070

### Privacy, memorization, unlearning and Sybil

[57] Carlini, N., Tramèr, F., Wallace, E., Jagielski, M., et al. (2021). Extracting training data from large language models. In *30th USENIX Security Symposium*. https://arxiv.org/abs/2012.07805

[58] Mireshghallah, F., Uniyal, A., Wang, T., Evans, D., & Berg-Kirkpatrick, T. (2022). An empirical analysis of memorization in fine-tuned autoregressive language models. In *Proceedings of EMNLP 2022* (pp. 1816–1826). https://doi.org/10.18653/v1/2022.emnlp-main.119

[59] Maini, P., Feng, Z., Schwarzschild, A., Lipton, Z. C., & Kolter, J. Z. (2024). TOFU: A task of fictitious unlearning for LLMs. *arXiv*. https://arxiv.org/abs/2401.06121

[60] Shi, W., Lee, J., Huang, Y., Malladi, S., Zhao, J., et al. (2025). MUSE: Machine unlearning six-way evaluation for language models. In *ICLR 2025*. https://arxiv.org/abs/2407.06460

[61] Douceur, J. R. (2002). The Sybil attack. In *Peer-to-Peer Systems (IPTPS 2002)*, LNCS 2429 (pp. 251–260). Springer. https://doi.org/10.1007/3-540-45748-8_24

### Decentralized learning and volunteer computing

[62] McMahan, B., Moore, E., Ramage, D., Hampson, S., & Agüera y Arcas, B. (2017). Communication-efficient learning of deep networks from decentralized data. In *Proceedings of AISTATS 2017*, PMLR 54, 1273–1282. https://arxiv.org/abs/1602.05629

[63] Hegedűs, I., Danner, G., & Jelasity, M. (2021). Decentralized learning works: An empirical comparison of gossip learning and federated learning. *Journal of Parallel and Distributed Computing, 148*, 109–124. https://doi.org/10.1016/j.jpdc.2020.10.006

[64] Huang, C., Liu, Q., Lin, B. Y., Pang, T., Du, C., & Lin, M. (2024). LoraHub: Efficient cross-task generalization via dynamic LoRA composition. In *COLM 2024*. https://arxiv.org/abs/2307.13269

[65] Anderson, D. P., & Fedak, G. (2006). The computational and storage potential of volunteer computing. In *CCGRID'06* (pp. 73–80). IEEE. https://doi.org/10.1109/CCGRID.2006.101

---

*Swarmbly LCE — Sebastián A. Espinoza-Ulloa · Whitepaper version 0.1 (draft). Spanish version: `WHITEPAPER_LCE_ES.md`. Specification: `SPEC_LCE_EN.md`. Text under CC BY 4.0.*
