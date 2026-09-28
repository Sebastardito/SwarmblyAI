---
status: current
lang: en
---

# Semantic Fragmentation and Stochastic Assembly, version 2

## A Protocol for Decentralized Language-Model Inference over Untrusted Volunteer Nodes

**Sebastián A. Espinoza-Ulloa, Ph.D.**
Independent Researcher
ORCID: [0000-0003-1497-356X](https://orcid.org/0000-0003-1497-356X) · GitHub: [@Sebastardito](https://github.com/Sebastardito)

> **Note on affiliation and independence.** This work is carried out entirely in
> a personal capacity as an independent researcher. The author holds academic
> affiliations — Pontificia Universidad Católica del Ecuador and University of
> Saskatchewan — unrelated to the subject matter of this work. **Neither has
> provided funding, materials, computing resources, personnel or institutional
> support for this project, and no institutional endorsement is claimed or
> implied.**
>
> **Relevant background.** The author holds a Ph.D. in Biology (University of
> Saskatchewan) in avian population genomics, and works on whole-genome
> sequencing, variant calling and de novo assembly. The genome-assembly framing
> used throughout this document derives from that background; Section 3 states
> the criterion by which an analogy of that origin is accepted or discarded.

**Version 2.0 — 25 September 2026**

---

> ## Status of this document: PUBLISHED
>
> The previous version of this block said **DO NOT PUBLISH**, for two reasons
> with a declared expiry date. They have been met, and the trade is written down
> rather than deleted.
>
> **First: the new models had not been falsified.** They have been now. All five
> faced their own test over **473 real runs** with five local model families
> (§15.9). **M4 is falsified** in two independent instruments, with a controlled
> experiment at constant ρ. **M2 survives corrected**, and the correction
> withdraws a sentence from this very document. M3 survives. M1 still lacks the
> regime it needs and M5 is unmeasured. The document is published **with** those
> verdicts inside it, not in spite of them.
>
> **Second: publication is what creates prior art.** The elements E19–E24 that
> Section 17 declares become prior art **upon publication of this document**, and
> not before.
>
> **What this document still cannot claim** is in L21 and §15.9: the measured
> aggregate advantage of fragmenting is confounded with the output budget, so the
> abandonment criterion has **neither been met nor failed — it has not been
> measured**. The missing claim is identified, the cause is located in the code,
> and the run that resolves it is implemented.

---

## Contents

0. What this version is, and what changes from 1.4
1. Introduction
2. Background and related work
3. The method: what makes a homology useful
4. Design principles
5. The semantic unit and the fragment
6. The context budget
7. Swarm intelligence with small models
8. Architecture
9. Protocol specification (v0.3)
10. Algorithms
11. Cardinality constraints
12. Redundancy: what *k* is for
13. Privacy, verification and adversarial nodes
14. Economics, governance and sustainability
15. Evaluation
16. Limitations and negative results
17. Prior-art declaration
18. Conclusion
19. References

---

## 0. What this version is, and what changes from 1.4

Version 1.4 describes an architecture and reports what was measured of it,
including two substantial withdrawals: the coherence-tax curve falling in ρ, and
the reliability claim for the confidence map. This version keeps both
withdrawals intact — they are not rescued through the back door — and adds what
1.4 did not have: **a theory of fragmentation itself**.

Version 1.4 took for granted that a fragment is "one of N parts of similar size"
and that overlap is "a percentage". Neither was derived. This version derives
them, and in deriving them changes concrete decisions in planning, packing,
assembly and dispatch.

**Change table.**

| in v1.4 | in this version |
|---|---|
| The codon as the minimum unit of meaning | **Withdrawn.** Three of three properties fail to transfer (§5.1). The sentence is homologous to the amino acid — the alignment unit; the protein domain is homologous to the fragment — the unit of work (§5.2, §5.3) |
| Fragment into `N` parts of similar size | **Replaced** by cutting at weakly coupled interfaces, with `L` as a target and `N` derived: `N = ⌈material/L⌉` (§5.4) |
| Overlap as a percentage of the fragment | **Replaced** by `F` = the maximum of the longest repeat and the longest dependency crossing a boundary. Measured saving: 29% of network compute (§6.5) |
| ρ as a parameter to be swept | **Derived** from `L`, `F` and the header cost `H`; and **formalised** as the rate of an indirect rate-distortion problem, with a second axis δ (§6.6–6.8) |
| Confidence map by match counting | **Replaced as a mechanism** by multiple alignment with learned substitution cost and consistency extension (M1, §10.5). The reliability claim **remains withdrawn** (§15.3, L13) |
| `term_once` enforced at the assembler | **Complemented** by uniqueness assignment in the plan, U-unitig style (M2, §11) |
| DAG with no control between levels | **Extended** with a per-level triage gate, by analogy with chaperones (M3, §8.2, §10.7) |
| `k` replicas as one parameter | **Split** into availability, verification and epistemic redundancy (M5, §12) |
| Genomic analogy as vocabulary plus one warning | **Formalised** as an explicit method: the instrument test and the failure-mode test (§3) |
| Declared elements E1–E18 | E1–E18 **unchanged**, plus E19–E24 (§17), **not yet published** |
| The five models M1–M5, stated and unmeasured | **Measured** against 473 real runs over five local model families (§15.9). One is falsified (M4, in two independent instruments), one survives corrected (M2), one survives (M3), and two remain unmeasured (M1, M5) |

Two hypotheses entered the literature review and **did not survive**: *mate
pairs* as the homologue of global constraints (§11.1) and *fountain codes* as a
redundancy mechanism (§12.1). Both are documented at greater length than their
replacements, because the fall is the result.

**This version arrives with a measurement campaign of its own.** Version 1.4 was published with one experiment; this one is accompanied by a reference implementation (`swarmbly_ref/`), a falsification harness (`swarmbly_validation/`) and a corpus of **473 runs** over five local model families, all three published alongside the document. §15.9 reports what that campaign killed. It is worth saying here because it changes the character of the document: the claims in §15 no longer rest on a run the reader must take on trust, but on an artifact they can re-execute.

---

## 1. Introduction

### 1.1 The concentration is in the capital, not the knowledge

The capability to build language models is no longer scarce. Weights, training
recipes and inference engines are published openly and improve monthly. What
remains scarce — and what concentrates power — is the capital required to
*operate* them at scale: the accelerators, the buildings, the power contracts and
the interconnect.

That concentration has a measurable shape. Data centres consumed 415 TWh in
2024, roughly 1.5% of world electricity, with projections to 945 TWh by 2030
[83]. Hyperscale facilities in the United States draw from grids measured at
545 gCO₂/kWh against a 370 g national average [84]. These are the figures of an
industry whose growth path runs through construction, and construction is
available only to those who can finance it.

The consequence is structural rather than conspiratorial: a technology whose
*knowledge* is public becomes, in practice, controllable by whoever can afford
the *hardware*. Openness of weights does not democratize a capability whose
operation costs hundreds of millions of dollars.

**And yet the hardware already exists, distributed and idle.** The flagship
volunteer-computing platform aggregates approximately 700,000 active devices,
4 million CPU cores and 560,000 GPUs at an average 93 PetaFLOPS [47] — and it
does so from a participant base that has shrunk from roughly a million to about
two hundred thousand over two decades. That number is a *floor*, drawn from a
declining niche, not a projection of what a compelling protocol could mobilise.
At the level of the individual node, idle consumer GPUs serve LLM inference at
$0.111–0.149 per million tokens on an RTX 4090, at 62–78% of H100 throughput for
roughly half the cost [49].

The world's spare inference capacity is not a hypothesis. The missing piece is a
protocol under which it can be used — and the reason no such protocol exists yet
is a physical constraint that the next section states exactly.

### 1.2 The physical constraint and the reframing

Any architecture for distributed language-model inference over consumer hardware
is decided, before any algorithm is chosen, by one measurement. An NVIDIA H100
SXM moves 900 GB/s per GPU over NVLink; Quantum-2 InfiniBand offers 400 Gb/s per
port and 51.2 Tb/s aggregate per switch. Typical consumer upstream bandwidth is
of the order of 60 Mbps. The ratio is roughly 120,000× against NVLink and 6,700×
against InfiniBand. Intra-node NVLink latency is sub-microsecond and InfiniBand
single-digit microseconds, against 30–170 ms of wide-area round-trip time:
**four to five orders of magnitude** [22, 23, 24].

This single fact partitions the design space cleanly. Architectures that require
communication *per token* are pushed against the gap on every step of
generation, whereas architectures that cross it *once per unit of work* are not,
and everything else in this document follows from choosing the second class.

The measured behaviour of the first class is consistent with the prediction.
Petals — the reference implementation of pipeline-parallel inference over the
internet — serves Llama-2-70B on three T4s at 2.29 steps/s over a 1 Gbit/s link
with sub-5 ms RTT, falling to 1.57 steps/s at 100 Mbit/s and 100 ms: a 31% loss
attributable to the network alone. A real geodistributed swarm of fourteen
heterogeneous servers achieves 0.83 steps/s [1, 2]. Analyses of model-parallel
schemes at public-internet latency find that pipeline parallelism is the *only*
viable model-parallel arrangement — it communicates least — and that
asynchronous micro-batching does not help, because decoding is bound by KV-cache
movement rather than by compute [25].

The conclusion I draw is not that pipeline parallelism was implemented poorly.
It is that it is the right answer to the wrong question.

Swarmbly asks a different question: rather than *how to run one large model
across many machines*, **how to run many complete small models on one large
problem**.

The two are not variations of the same idea. Splitting a model creates a chain
in which node *k* cannot begin until node *k−1* finishes, and in which every
token retraces the chain. Splitting a problem creates a set — more precisely a
partial order — in which independent sub-tasks proceed concurrently and each
crosses the network once. The first is bounded by `Σᵢ(t_compute,i + t_net,i)`;
the second by `max_i(t_compute,i + t_net,i)` plus local assembly. The structural
claim is that the second is the regime in which volunteer hardware can
participate at all.

The design vocabulary is borrowed deliberately from genome shotgun assembly. A
request is fragmented into *reads*; each returned answer is a *contig*; adjacent
contigs are joined by *overlap* and, where they disagree, by *consensus*; the
plan that orders them is a *scaffold*. Section 3 states exactly what that analogy
does and does not license, and does so with an explicit criterion rather than a
general warning — which is the central methodological change in this version.

### 1.3 What this makes possible

The first measurement against the abandonment criterion is in, and **the
criterion was not met**: at ρ = 3.5, *N* = 2, *k* = 1 over 16 held-out prompts
the coherence tax is +2.30% with a 95% CI of [−2.05%, +7.49%], and the criterion
is written against the upper bound, which falls short by 2.49 points (§15.3).
What survives is narrower and better founded: the **median prompt loses exactly
nothing (0.00%)**, **11 of 16 prompts are at or below zero**, and the control at
*N* = 8 fails as it was required to. The mean is manufactured by two prompts
which between them are 140% of it; without them, the other fourteen average
−1.06%.

Four things remain possible, and they are now motivated by a measured bimodal
cost rather than by a confirmed trend.

**1. Serving capacity without owning it.** A participant contributes a machine
that already exists and already draws power when idle. The entry requirement is a
complete small model, not a shard of a large one, which places the addressable
hardware pool orders of magnitude above what pipeline-parallel schemes can reach.
Capacity then scales with *participation* rather than with capital expenditure.

**2. A divergence map that centralization cannot produce — with its reliability
claim withdrawn.** Because a micro-task is answered by *k* nodes running
*different* model families, the answers can be aligned against each other and the
agreement scored per semantic unit. **A provider running one model has nothing to
align.** Whether that signal carries information about correctness is a separate
question, and it was answered: no, with the instrument that was used (§15.3,
L13). This version proposes a different instrument (M1, §10.5) and states in
advance what would kill it. Proposing a replacement does not lift the withdrawal.

**3. Context bounded by the user's machine rather than by a vendor's product
decision.** Fragmentation relocates the context limit from a fixed window to a
function of the client's assembly time and memory. With hierarchical assembly the
working memory required grows logarithmically with total volume.

**4. A substrate that can be audited rather than trusted.** The protocol, the
client, the node software and the licence are public. The share of traffic served
by foundation-operated anchor nodes is published (§14.4). The energy accounting
is published against a public standard (§14.3). Coherence degradation is returned
with every response (§10.8). None of these is a courtesy; each is a conformance
requirement.

### 1.4 Scope of claims

Four claims a reader might expect here are deliberately absent, and Section 16
develops each in full.

I do not claim **latency parity**: single-node speculative decoding already
delivers 2–3× with a proof that the output distribution is preserved [13], and no
fragmentation scheme competes with that on speed. The comparison that matters is
different — for a user without the hardware to run a capable model at all, the
relevant axis is not *faster or slower* but *possible or impossible*.

I do not claim **unlimited context**, only a relocated and much higher limit.

I do not claim **cryptographic confidentiality**. Fragmentation is not
encryption, Section 13 gives the attacks that settle it, and the protocol routes
sensitive work to local execution or attested hardware.

I do not claim a **demonstrated environmental benefit**. The embodied-carbon
argument is strong and the operational one is conditional; §14.3 states both.

**And this version adds a fifth absence.** I do not claim **a computable bound
for ρ**. Section 6.7 establishes that Swarmbly's problem is an indirect
rate-distortion problem, from which one inherits the *existence* of a lower bound
and the qualitative monotonicity of the curve. One does not inherit a number, and
saying otherwise would be exactly the kind of over-reading that Section 3 exists
to prevent.

### 1.5 Contributions and structure

Section 2 locates the work against the prior art, including the adverse evidence.
Section 3 establishes the method by which a biological homology is accepted or
discarded: it is this version's methodological contribution and it organises
everything that follows. Section 4 states the design principles. Section 5
develops **the semantic unit and the fragment** — how large a fragment is and
where it is cut. Section 6 develops the **context budget**, now derived and
formalised. Section 7 formalises the **swarm-of-small-models** thesis. Sections 8
to 10 give architecture, protocol and algorithms. Sections 11 and 12 treat
cardinality constraints and the role of redundancy. Section 13 covers privacy and
verification; Section 14, economics and governance. Section 15 reports what has
been measured and specifies what remains, including the criterion under which I
would abandon the design. Section 16 lists limitations and negative results.
Section 17 declares the disclosed elements.

---

## 2. Background and related work

### 2.1 Decentralized inference by model partition

Petals [1, 2] distributes contiguous blocks of transformer layers across
volunteers; clients hold embeddings locally and route activations through a chain
of servers. I treat it as the field's pioneer rather than as a competitor: it
demonstrated that peer-to-peer inference over the public internet is possible at
all, which is the precondition for this work. Swarmbly does not improve pipeline
parallelism; it declines to use it, and that divergence is a difference of
strategy rather than of quality. Hivemind and SWARM parallelism [4, 5] address
fault-tolerant training over unreliable heterogeneous devices with the same
underlying premise: the model is the unit of distribution.

Bittensor [6, 7] adds an incentive layer, with a consensus mechanism whose
connectivity-based regularization is described as resistant to collusion of up to
50% of network weight — a formulation that, read carefully, presupposes a trust
anchor.

### 2.2 Decentralized training over slow links

The subfield that has advanced most is training, and it advanced by attacking
communication volume rather than topology. DiLoCo matches fully synchronous
optimization while communicating 500× less [8]. OpenDiLoCo trained across two
continents at 90–95% compute utilization [9]. INTELLECT-1 trained a 10B-parameter
model on 1T tokens across up to 14 concurrent nodes on three continents with a
400× bandwidth reduction [10].

The lesson Swarmbly takes is methodological: the bandwidth problem yields to
compression and asynchrony.

### 2.3 Task-level parallelism

Skeleton-of-Thought (SoT) [12] is the direct precedent for decomposing a
*prompt*: a skeleton prompt produces a list of points, each expanded
independently and in parallel. It reports up to 2.39× speedup, and — this matters
more — it reports its own damage: quality improves on knowledge, generic,
common-sense, roleplay and counterfactual questions, and degrades on maths,
coding, writing and Fermi estimation. The authors state the structural cause
without hedging: "SoT currently ignores the dependencies between points."

Their response was not to defend the method but to gate it. SoT-R [12] adds a
router that decides per question whether to decompose at all; a trained 120M
RoBERTa router suffices, and it is trained with a Tversky loss precisely to
penalize false positives.

Descendants refine the idea. APAR [16] has the model plan its own parallel
branches. PASTA [17] learns an annotation language for semantically independent
spans and reports geometric-mean speedups of 1.21–1.93× at a length-controlled
win-rate delta of +2.2% to −7.1%. Plato/ASGD [18] replaces the flat list with a
**dependency graph** and reports a 68% throughput gain. Hogwild! Inference [19]
takes the opposite tack: concurrent workers sharing a live KV cache.

ParallelBench [20] supplies the theory: the conditional-independence assumption
underlying parallel generation "inevitably degrad[es] generation quality when
dependencies are strong." Tran and Kiela [21] give the information-theoretic
version via the data processing inequality.

**What is missing from that literature is my subject: nobody has combined
prompt-level decomposition with dispatch to untrusted volunteer nodes.** That
intersection, and not either half of it, is what this document discloses.

### 2.4 The nearest neighbour, and the adverse evidence

Two things have changed since v1.4 and both must be faced head-on.

**The nearest neighbour now exists.** SWARM-LLM (Dahshan, Mamun & Debnath, VTC
2026) [134] routes a query to a local SLM, to several peer SLMs at the edge with
**weighted consensus where lower-uncertainty nodes weigh more**, or escalates to
the cloud. It reports ~28% cloud usage and accuracy on hard questions rising from
0% to 15% over a load of **50 queries**. That is weak empirical evidence — 50
queries — but it claims the territory, and it must be cited and differentiated
from. The difference is that its consensus is a scalar weighting per node, and
Swarmbly's is a position-to-position correspondence (§10.5): theirs says *how
much* to trust each node, ours says *where* they diverged.

**Semantic agreement across different models is already used as a signal.**
Soiffer, Kolawole & Smith (2025) [101] use agreement among smaller models as a
deferral signal toward a larger one: "when independently generated outputs are
semantically consistent — even if lexically distinct — their agreement suggests
the underlying meaning is reliable". Architecturally it is the closest thing to
the confidence map. It also clusters rather than aligns, which is the opening
§10.5 occupies.

**And the serious criticism of the whole family.** "Why Do Multi-Agent LLM
Systems Fail?" (Cemri et al., 2025) [90] builds the MAST taxonomy: **14 failure
modes in 3 categories** — system design issues, inter-agent misalignment, task
verification — from more than 1,600 annotated traces over **7 frameworks**, with
150 traces validated by expert annotators at **κ = 0.88**. "If Multi-Agent Debate
is the Answer, What is the Question?" (Zhang et al., 2025) [135] finds that
multi-agent debate methods "fail to consistently outperform single-agent
baselines such as Chain-of-Thought and Self-Consistency, even when consuming
additional inference-time compute", across 9 benchmarks, 4 models and 5 methods.

**Swarmbly's honest answer** is not that its architecture is immune. It is that
**MAST's three categories are exactly the three this version addresses**:

| MAST category | where it is addressed here |
|---|---|
| System design issues | §5.4 interface cutting rule; §11.3 uniqueness assigned in the plan |
| Inter-agent misalignment | §10.5 alignment with semantic substitution; §9.2 global contract |
| Task verification | §10.7 per-level triage gate |

That a taxonomy built independently over 1,600 traces coincides with the three
areas the biological homologies pointed at is, if not a validation, at least a
convergence worth declaring.

Zhang et al.'s criticism is moreover more specific than it appears: it targets
**debate** — agents arguing to converge — and not **decomposition** — agents
solving disjoint parts. Swarmbly does not debate. But the lesson transfers all
the same, and this version adopts it as a requirement: **additional compute must
be justified against a single-agent baseline with self-consistency**, not against
the naive monolithic model. Section 15.6 folds it into the evaluation protocol.

### 2.5 Prompt compression as a rate-distortion problem

Nagle et al. (NeurIPS 2024) [123] formalise **prompt compression** as a
rate-distortion problem for black-box language models. Their rate is
`E[len(M)/len(X)]` — expected compressed prompt length over expected original
length — which is **structurally the same quantity as ρ**. Their distortion is
performance degradation under logarithmic or 0/1 loss. They derive the
distortion-rate function via the dual of a linear program and report a large gap
between current methods and the optimal strategy.

The consequence for this document is direct and limiting: **the contribution
cannot be "ρ is a rate-distortion problem", because that is published.** The
contribution has to be ρ **under fragmentation with distributed reassembly**,
which is a different and harder problem, and one Nagle et al. do not cover.
Section 6.7 develops it that way, and 6.8 adds the second axis their framing does
not need and ours does.

### 2.6 Genome assembly

Lander–Waterman coverage statistics [26] give, for a genome of length *G* sampled
by *N* clones of length *L* with minimum detectable overlap fraction θ:

```
c = L·N / G                                   (coverage redundancy)
P(base uncovered)          = e^(−c)
E[# apparent islands]      = N·e^(−c·θ)
E[# clones per island]     = e^(c·θ)
```

This model transfers, but only after one correction that earlier versions of this
work got wrong. The relevant difference between genome assembly and text assembly
is **not** that the target sequence is *known*: in *de novo* assembly no reference
exists. The real difference is narrower and more useful: in genomics there exists
**a single physical molecule of which every read is a sample**. That uniqueness is
what guarantees that two true overlaps are reconcilable. In free text generation
there is no such guaranteeing object.

**But the guaranteeing object can be manufactured.** If the plan `D` and the
global contract `Γ` are fixed *before* any generation occurs and are treated as
the reference, then a common underlying object exists again and coverage
statistics become applicable. Section 7.4 develops this, and it is the point at
which the analogy stops being a naming convention and becomes a derivation.

There remains one genuine transfer from the assembly literature, and it is a
warning. In de Bruijn assembly a repeat longer than *k* collapses into a single
graph node; the Eulerian path stops being unique and the number of valid
reconstructions grows combinatorially with repeat count [29]. Twenty years of
practice established the consequence: **repeats, not coverage, are the binding
constraint** [30, 31]. Section 6.4 turns that warning into an inequality with two
forms, and into a measured datum from the project itself.

---

## 3. The method: what makes a homology useful

This section is new and is version 2's methodological contribution. Without it,
Sections 5, 6, 10, 11 and 12 would be a catalogue of attractive analogies.

### 3.1 The problem with analogies

Swarmbly was born of an analogy: a request too large for a small model resembles
a genome too long for a sequencer. It is broken up, read in parts, reassembled.

Analogies of that kind are productive at first and dangerous afterwards. They are
productive because they import mature vocabulary for a new problem. They are
dangerous because the vocabulary arrives with connotations that do not transfer,
and because an analogy that sounds good resists scrutiny precisely for that
reason.

Version 1.4 stated the caution — no genome assembly algorithm runs inside
Swarmbly — but offered no criterion for deciding when a transfer is real. This
section proposes one, and the rest of the document applies it case by case.

### 3.2 The instrument test

> **A homology is useful when it brings an instrument: a procedure, an inequality
> or a number that can be applied to the new problem. It is not useful when all
> it brings is a way of talking.**

The clear case is the coverage equation. Lander & Waterman (1988) derive that the
expected number of islands is `N·e^(−cθ)` with `c = LN/G`. That derivation hands
over a number — how many replicas are needed — where before there was a guess. It
is an instrument, and Section 7.4 uses it as one.

The opposite case, and it has to be said because it comes from the project
itself: calling a fragment of an answer a *contig* does nothing. It is
vocabulary. It is kept because it is convenient, not because anything is derived
from it.

### 3.3 The failure-mode test

Applying the instrument test to the homologies this project uses, a pattern
emerged that had not been looked for:

> **Homologies that transfer come accompanied by their failure mode. Those that
> do not transfer bring a mechanism without its associated pathology.**

The minimum-overlap criterion comes with *mis-assembly*: if the overlap does not
exceed the repeat, the assembler glues the wrong stretches together. The protein
domain comes with its interface condition: independence is lost when the
interface is large and tightly packed. Chaperone triage comes with degradation:
what cannot be recovered is destroyed, not patched in.

By contrast the codon — which §5.1 discards — was proposed as "the minimum unit
of meaning" with no statement whatsoever about what happens when it is violated.
Fountain codes — §12.1 — were proposed for their recovery property with no
condition on when that property ceases to exist.

The reason is that a mature field does not discover an isolated mechanism: it
discovers a mechanism **and** the cases where it fails, and it usually publishes
the second with more care than the first. A transfer that brings only the good
part is importing the conclusion without the work.

### 3.4 The operational test

| question | if the answer is no |
|---|---|
| Does it bring a procedure, an inequality or a number? | It is vocabulary. Use it as vocabulary and derive nothing from it. |
| Does it bring a statement of what happens when the condition is violated? | It is half-imported. Find the failure mode before building on it. |
| Do the source field's conditions hold here? | Invalid transfer. Say why, which is usually informative. |

The five homologies this document uses pass all three questions. The two that are
discarded fail the second, the third, or both — and in both cases the diagnosis of
*why* they fail turned out to be more useful than the homology would have been.

---

## 4. Design principles

**P1 — Cross the network once per unit of work.** The only defensible performance
argument available to a volunteer network.

**P2 — The orchestrator may refuse.** A system that fragments every request is
strictly worse than SoT was in 2023, because SoT shipped a router. Fragmentation
is a decision with an asymmetric cost function, not a default.

**P3 — Model dependencies explicitly.** Plans are directed acyclic graphs.
Parallelism is the width of a level, not the size of the task set.

**P4 — Select before you synthesize.** Where several candidate fragments exist,
choose one and splice it. Rewrite only where a seam actually fails.

**P5 — Calibrate every threshold.** No fixed cosine cutoffs, no assumed
redundancy ratios. Thresholds are derived from labelled data per model and per
domain, with asymmetric objectives.

**P6 — Report the tax.** Every assembly returns a coherence audit. A protocol
that hides its own degradation cannot be evaluated.

**P7 — Verify cheaply or not at all.** Verification that costs a significant
fraction of inference destroys the economics.

**P8 — Route by sensitivity, do not pretend to encrypt.** Confidentiality is a
routing decision with three lanes, not a property claimed for fragmentation.

This version adds three, and all three come out of the new sections.

**P9 — Cut where the coupling is weak, not where the count falls.** A fragment
boundary is a decision about the interface, not about size. `L` is a target; the
interface is the rule. (§5.4)

**P10 — Resolve global constraints in the representation, not in the output.** A
constraint no node can satisfy in isolation is assigned in the plan, where it can
be satisfied by construction. (§11.3)

**P11 — One parameter, one purpose.** `k` today serves three distinct ends —
availability, verification and epistemic redundancy — and pays for all three at
the price of the most expensive. They are separated. (§12.4)

---

## 5. The semantic unit and the fragment

This section does not exist in v1.4. It answers how large a fragment is and where
it is cut, and the planner (§10.2), the context budget (§6) and the assembler
(§10.4) all depend on it.

### 5.1 The codon is not the homologue

The original proposal took the **codon** — three nucleotides translated into one
amino acid — as the homologue of the minimum unit of meaning in text, and derived
from it that there exists a minimum fragment size below which meaning is
destroyed.

The conclusion is correct. The derivation is not. The codon has three structural
properties, and the sentence has none of them:

| property of the codon | the sentence |
|---|---|
| **Fixed width** — exactly 3 nucleotides | Variable. Measured over the project corpus: p25 = 9 tokens, p75 = 25. Nearly 3× range. |
| **Reading frame** — non-overlapping; a shift ruins everything downstream | There is no frame. A displaced cut does not destroy the rest of the text. |
| **Deterministic map** — `GGA` is always glycine | The same idea admits infinitely many textual surfaces. |

Three out of three. The transfer is not partial: it is null on all three
properties that define the codon. Applying §3.4, it also fails the second
question — it never came with a statement of what happens when it is violated.

### 5.2 The amino acid is the homologue of the alignment unit

The third row points at where it does fit. The amino acid is a unit of **variable
width**, **self-delimiting**, with **properties of its own**, and it is **the unit
of the folded structure**. The sentence shares all four.

And the distinction is not terminological, because computational biology has **two
alignment technologies** and the choice of homologue determines which one is
inherited:

- **Nucleotide alignment** — identity or not. `A` against `G` is a disagreement,
  full stop.
- **Protein alignment** — substitution matrices. Henikoff & Henikoff (1992) [92]
  build BLOSUM by counting aligned amino acid pairs in ungapped blocks and
  computing, for each pair, `s_ij = log₂(q_ij / e_ij)`, the log ratio of observed
  to expected frequency, in half-bit units.

That formula is the instrument. It says that the interchangeability of two units
is not postulated: **it is counted**, over cases already known to be homologous.

For Swarmbly the consequence is direct. Two nodes that answer

> "The tide window closes at noon."
> "The channel shuts at midday."

are not in disagreement. Under nucleotide-style comparison they are a total
disagreement; under a substitution matrix they are a **conservative
substitution**. The v1.4 assembler — which compares by cosine similarity against
a threshold — is operating in the nucleotide regime on material that is protein.

### 5.3 The domain is the homologue of the fragment

This is the most important correction in this version.

The amino acid is not the homologue of the **fragment**. No amino acid folds alone
or has function alone. The unit that does is the **domain**.

Porter & Rose (2012) [110] give the rigorous definition: a domain is "a contiguous
segment of the folded protein whose m-value remains largely unchanged when that
segment is excised from its parent structure", and they equate domain with
"cooperative folding unit; i.e., its cooperativity depends primarily on
intra-segment, not inter-segment, interactions".

Read the second clause carefully, because **it is the specification of a good task
fragment**: a piece whose resolution depends on what it contains and not on what
its neighbours contain.

The reference work on multidomain proteins (Han et al., 2007) [111] confirms that
more than 70% of eukaryotic proteins are multidomain and that domain folding is
independent — **but with an explicit condition**: "where the interface is small
and poorly packed, or unstructured, folding of the domains is independent".

### 5.4 The interface condition is the cutting rule

That condition is not a footnote caveat. It is the instrument, and it is P9:

> **Fragment where the coupling between fragments is weak. A fragment boundary is
> a decision about the interface, not about size.**

This reorders the design. The planner must not cut every `L` sentences and hope it
works out: it must **look for the points of weak coupling** and cut there, with
`L` as a target and not as a rule. A cut that splits a strong dependency produces
two fragments that are not domains, and the independence guarantee applies to
neither.

The project already has a recorded incident that is exactly this failure: the
segmenter separated a question from the material that answered it. That was not an
implementation error, it was a cut across a strong interface. Under the v1.4
formulation — cut into N parts of similar size — that failure is structural and
recurrent. Under the interface rule it is detectable before dispatch, because the
planner can measure the coupling it is about to cut.

And there is a datum from the project pointing the same way. In the measurement of
§15.3, the only two prompts where `N` = 2 is *worse* than `N` = 8 are the two that
manufacture the mean. More fragments *helping* is not what a coherence-tax story
predicts; it is what a **partition-quality** failure predicts — a two-way split
putting a seam somewhere costly, which cutting eight ways happens to avoid. Under
P9 that stops being luck.

### 5.5 Functional autonomy is quantified, and it is not total

Bashton & Chothia (2007) [112] compare homologous domains that appear both in
single-domain and in multidomain proteins, over 70 unique domain pairs in 45
protein sets: approximately **three quarters preserve their function** when the
context changes; **a little under one sixth changes substantially**.

The number bounds the expectation. "A fragment solved in isolation is worth the
same as in context" is true most of the time and false one time in six or seven. A
design that assumes total autonomy is assuming something nature does not deliver
even in the system the idea was borrowed from.

### 5.6 Size: there is a band, there is no number

Is there a natural domain size that would suggest a natural `L` for text? The
honest answer is that **a characteristic band exists and a number does not**, and
the reason it does not is instructive.

Zhang et al. (2005) [113] map sequence-defined domains against structure-defined
domains, over the same proteins: **Pfam averages 96 residues; SCOP averages 174**.
Almost double, over the same material, in the same paper. The difference is not
noise: Pfam cuts by sequence family and SCOP by structure. **The definition
determines the number.**

Schaeffer et al. (2023) [114], classifying domains over predicted structures,
report **99.8 ± 64.8 residues** — a standard deviation that is 65% of the mean.

The floor, by contrast, is sharp. Porter & Rose set **25 residues** as the
minimum, "approximating the size of a supersecondary structure unit"; UniDoc (Zhu
et al., 2023) [115] uses 30 as a parsing constraint.

Both lessons transfer cleanly:

1. **The floor is hard and principled.** Below a certain size nothing folds
   cooperatively. For text, this predicts that an `L_min` exists below which a
   fragment is not independently solvable, and that this floor is sharper than the
   optimum. Section 6.5 gives an independent reason for the same floor, from the
   header-cost side.
2. **The optimum is a wide, definition-dependent band.** Any claim that `L* = 50`
   is a number is an over-reading. What can be expected is a band spanning a factor
   of 3 to 6, and the definition of "unit" chosen will move its centre.

### 5.7 The fundamentals of the semantic unit

1. The minimum alignment unit is the **sentence**, homologous to the amino acid:
   variable width, self-delimiting, with meaning of its own, and the unit over
   which substitution is computed.
2. The fragmentation unit is the **task domain**, homologous to the protein
   domain: the segment whose resolution depends on internal interactions and not
   on its neighbours.
3. The fragment boundary is chosen **where coupling is weak**, with `L` as a
   target in sentences and not as a division rule.
4. `L` is a property of the **node class**, measured and revisable. `N` is
   derived: `N = ⌈material / L⌉`. This inverts the v1.4 formulation, where `N` was
   the parameter and size the consequence.
5. There is a hard `L_min`; the optimum is a band.

---

## 6. The context budget

This is the project's central constraint. Version 1.4 stated it and swept it;
this version derives it and formalises it.

### 6.1 Definition

Let a request *P* be decomposed into micro-tasks `T = {t₁ … t_N}` with dependency
DAG `D = (V, E)`. Each dispatched packet is

```
K_i = ( Γ , σ(R_j : (t_j → t_i) ∈ E) , t_i )
```

where **Γ** is the *global contract* — objective, audience, register, output
format, target length, forbidden vocabulary, session identifier — and σ(·)
summarizes the results of *t_i*'s predecessors.

Define the **context budget**

```
S = |Γ| + E[ |σ(·)| ]          (tokens of shared context per packet)
```

and the **contextual redundancy ratio**

```
ρ = ( Σᵢ |K_i| ) / |P|
```

ρ is what the operator pays. In v1.4, *S* was what the operator chose. In this
version it is not: §6.5 derives ρ from `L`, `F` and the header cost, and what the
operator chooses are those three.

### 6.2 The four-way tension

Four desiderata are functions of *S*, and they do not agree:

| Desideratum | Behaviour in *S* | Mechanism |
|---|---|---|
| **Assembly coherence** | **increases** | Workers share the decisions that make fragments compatible. Absent a contract, one worker renders the scene in one register and another in a second [33] |
| **Fragment verifiability** | **increases** | A verifier cannot judge whether a fragment is faithful to a specification it was not given |
| **Privacy by decontextualization** | **decreases** | Γ *is* the session's objective, audience and constraints. A node holding Γ holds the shape of the request |
| **Required worker capability** | plausibly **decreases** | Context supplied in-prompt substitutes for knowledge held in parameters — stated as a hypothesis in §7.3, not as a result |

And ρ, hence cost, grows approximately linearly in `N·S`.

### 6.3 The falsifiable core

> **Proposition (Context Budget).** Swarmbly is viable if and only if there
> exists a context budget *S\** that simultaneously satisfies: a coherence tax
> below the application's tolerance; a leakage bound below the user's tolerance
> for the applicable sensitivity lane; a verification accuracy above the
> protocol's security requirement; and a worker-capability requirement met by
> commodity small models — all at a ρ whose cost remains below the value of the
> aggregated capacity.

This is the whole project stated as one testable claim, and it is why the
reference implementation measures a curve rather than demonstrating a system.

It also predicts something useful. Because *S* is shared across all four, **any
improvement that raises coherence per token of context is worth more than an
improvement that raises coherence per token of output** — it buys progress on
privacy and cost simultaneously. This makes contract compression, and not
fragment quality, the highest-leverage research direction in the design.

### 6.4 Flanks, repeats and the information floor

Version 1.4 treated overlap as a percentage inherited by analogy. It is not, and
the information-theoretic literature says exactly what it is.

**Overlap solves a different problem here.** In *de novo* assembly, overlap exists
above all to **discover order**: nobody knows which part of the genome each read
came from. Swarmbly does not have that problem — the orchestrator creates the
fragments and knows their order. Two reasons remain, and only one is genomic:
**transition continuity** (that the end of one fragment meets the beginning of the
next) and **repeat detection**.

**The minimum-overlap criterion has two forms.** The folk statement — "overlap
must exceed the longest repeat" — is correct but weak. Bresler, Bresler & Tse
(2013) [102] sharpen it into two distinct conditions:

*Sufficient condition for a greedy algorithm:*

```
L > ℓ_repeat + 1
```

"GREEDY reconstructs the original sequence if every repeat is bridged." That is a
statement about **one particular algorithm**.

*Necessary, information-theoretic condition:*

```
L > max{ℓ_interleaved, ℓ_triple} + 1
```

where an *interleaved* repeat is a pair of repeats whose positions interleave, and
a *triple* repeat is a subsequence that appears three times. Below that threshold
**no algorithm** can reconstruct, because two different sequences produce identical
read sets.

The distinction matters more than it appears. The first form says "do better". The
second says **there exists a class of inputs where the fragments simply do not
contain the information needed to reassemble correctly, however clever the
assembler is.**

Motahari, Bresler & Tse (2013) [103] formalise the threshold: for i.i.d.
sequences there is a sharp transition according to whether the normalised read
length exceeds the order-2 Rényi entropy of the source. Above it, "the obvious
coverage condition is also sufficient for reconstruction"; below it, no amount of
coverage suffices.

**The parallel this enables, and which this version adopts:** coverage — how many
replicas — and solvability — whether the fragments contain the information — are
**two distinct questions**, and the first does not imply the second. Version 1.4
reasoned about `k` and kept silent about solvability. The coverage model of §7.4
is still correct and is still only half the matter.

**A repeat is a property of a pair, and the project has already measured it.** The
semantic homologue of a genomic repeat is a recurring phrase or template. Two
fragments that cannot see each other repeat the same structure, and the assembler
cannot detect it because **a repeat is a property of a pair, not of a fragment**.
Bresler et al.'s formal definition is inherently relational: a repeat "is a
subsequence that appears twice" at positions `t₁` and `t₂`. No individual read can
be inspected to determine whether it lies in a repeat.

And the project **has already measured the same phenomenon**. The
`no_repeated_ngram` constraint is the irreducible class in its composition
measurements: **4 of 12 against 11 of 12 for the monolithic arm**, and no
context-allocation policy reaches it. It was the defect that would not yield. The
reason, now nameable, is that no allocation *can* reach it: a fragment cannot avoid
repeating what it cannot see. Section 11 gives the mechanism that can.

### 6.5 The flank F and the derivation of ρ

From the above comes the operational criterion:

> **`F` is the maximum of two quantities measured over the corpus: the longest
> repeatable unit the assembler must be able to detect, and the longest dependency
> that crosses a fragment boundary.**

Reference estimate for the project corpus: **`F ≈ 5–10` sentences**.

With `F` defined by measurement and `L` as a property of the node class, the
context budget is **derived** rather than swept:

```
ρ ≈ (L + 2F) / L  +  H / (L · s)
```

where `H` is the fixed per-packet cost — contract, glossary, formatting
instructions — measured at **≈ 39 tokens** over the project corpus, and `s ≈ 15`
tokens per sentence.

With `L = 50`, `F = 10`: **ρ ≈ 1.45**. With a flank inherited by analogy,
`F = 25`: **ρ ≈ 2.05**.

**29% of the compute of the whole network**, from the single decision to measure
the flank instead of copying a percentage. And since §6.4 says exactly what to
measure, the saving relaxes no guarantee: `F` is set by the observed repeat and
dependency, not by convenience.

**The second term explains something the project observed without being able to
name it.** The header is paid **in full per packet**, so its relative weight is
inversely proportional to `L`. With 35-token fragments — the actual fragment size
in the project's composition measurements — the 39-token header **weighs more than
the material**. That is the regime in which measurements were taken for months,
and it explains why ρ appeared to have a high floor: it was not a property of the
protocol, it was a property of fragmenting too finely.

This has a direct consequence for v1.4's metric. That document set "operating
ρ < 2.0" as a target and then reported it was not attainable on its corpus,
because the packing floor at `N` = 2 was 1.42–1.68. With the derivation above,
that floor stops being a brute fact and becomes a prediction: it was the term
`H/(L·s)` dominating because `L` was too small. The correct target is not an
absolute ρ but **the distance to `(L+2F)/L`**, which is what can be reduced
without losing guarantees.

### 6.6 Why formalise ρ

ρ has functioned as an empirical quantity: it is measured, compared, reported. The
derivation above is already an advance over treating it as a dial. But deriving it
does not say **whether a floor exists**, nor what it depends on. Rate-distortion
theory is the framework in which that question has an answer.

> **Background concept.** Rate-distortion theory (Shannon, 1959) [121] answers:
> given that I am going to transmit an imperfect version of something, what is the
> minimum information rate needed for the imperfection not to exceed a given level?
>
> Shannon defines a distortion matrix in which "d_ij measures the 'cost' or
> 'distortion' if letter i is reproduced at the receiver as letter j", and `R(d*)`
> as the minimum rate subject to the average distortion not exceeding `d*`. Cover
> & Thomas [122] write it as
>
> ```
> R(D) = min I(X; X̂)
> ```
>
> minimised over conditional distributions `p(x̂|x)` satisfying the expected
> distortion constraint. Their Theorem 13.2.1 establishes that the rate-distortion
> function of an i.i.d. source with bounded distortion **equals** the associated
> informational function.
>
> The shape of the curve is the essential part: `R(D)` decreases with `D`. Less
> fidelity demanded, less information needed. And there is a floor: below `R(D)`
> the distortion `D` is unreachable, whatever one does.

### 6.7 ρ as the rate of an indirect problem

The natural objection is that classical rate-distortion assumes a source that is
reconstructed, and Swarmbly does not reconstruct the request: it produces an
answer.

The theory has a name for that situation: the **indirect** or **remote**
rate-distortion problem, in which "the encoder cannot observe the source directly
but obtains only noisy observations" — a formulation that goes back to Wolf & Ziv.

The mapping is exact, and it is this section's formal contribution:

| element of the theory | in Swarmbly |
|---|---|
| **Source** `Y*` | The ideal answer to the request. **Never observed**, neither by the orchestrator nor by any node. |
| **Observation** `X` | The request `P`. It is what the encoder *does* see: a description of `Y*`, not `Y*`. |
| **Encoder** | The fragmentation policy: router, planner, packer. It produces `{K₁ … K_N}`. |
| **Channel** | The node network. Each node applies a stochastic transformation `K_i → R_i`. |
| **Decoder** | The local assembler, which produces `Ŷ` from `{R_i}`. |
| **Rate** | `ρ = Σ|K_i| / |P|` |
| **Distortion** | `d(Y*, Ŷ)` — task loss, not reconstruction fidelity. It is Nagle et al.'s move, and it is the right one. |

With this, the defensible claim can be stated:

> **M4 — ρ is the rate of an indirect rate-distortion problem whose distortion is
> task loss. From this one inherits the existence of a lower bound and the
> qualitative monotonicity of the curve. One does not inherit a computable bound.**

**What cannot be claimed, and why.** Three limits, stated before a reviewer states
them.

*The bound exists but is not computable here.* Nagle et al. obtain a number
because they restrict to token erasure over a known prompt with a black-box LLM,
and solve a finite linear program. Swarmbly's encoder is a decomposition policy
and its decoder is a language model; there is no tractable `p(x)` over the task
space and no single-letter distortion. One may claim the bound **exists**; not
that it has been computed.

*The theorem is asymptotic in i.i.d. blocks.* A user request is one realisation,
not a long sequence. The converse gives no per-request guarantee.

*And the most important one: distortion is not caused by rate alone.*

### 6.8 The second axis: dependency density

This is the section's own contribution, and it comes out of a datum from the prior
art.

Skeleton-of-Thought [12] generates a skeleton and expands the points in parallel.
It achieves speedups of up to **2.39×**. And its quality degradation **is not
uniform**: it improves "diversity and relevance while hurting immersion and
coherence", and **fails on maths and coding**.

Those are precisely the tasks where sub-answers are interdependent. The
degradation does not track rate: it tracks **how much was cut across
dependencies**.

A curve `D(ρ)` indexed only by ρ cannot capture that. At least a second axis is
needed:

```
D = D(ρ, δ)
```

where **δ is the dependency density of the decomposition**: some measure of how
many necessary relations cross a fragment boundary, normalised by the number of
fragments.

This closes the document's argument from three sides at once. **The
weak-interface cutting rule (P9, §5.4) is, in this language, the minimisation of
δ**: cutting where coupling is weak is exactly choosing the decomposition of
lowest dependency density for a given ρ. And the Bresler et al. information floor
(§6.4) is the statement, in assembly language, that **there exists a region of the
(ρ, δ) plane where no acceptable distortion is reachable**, because the fragments
do not contain the information.

The three formulations — weak interface, information floor, dependency density —
are the same claim in three vocabularies. That they converge from three
independent literatures is the reason to believe it.

**And it is falsifiable without further theory.** Fixing δ and varying only ρ
(same cut, different flank) should produce a curve monotonically decreasing in
distortion. Fixing ρ and varying δ (same budget, cuts of different coupling)
should produce variation in distortion **at constant rate** — which is the result
that would kill the idea that ρ suffices as an axis. And the unreachability region
should manifest as a distortion floor that no ρ improves.

### 6.9 Why the earlier formulation was inadequate

An earlier version of this design specified a fixed redundancy target
(`C_sem > 1.2`, "20% intentional redundancy") derived by analogy from
Lander–Waterman, and a fixed seam threshold (`τ_sem = 0.85`) on embedding cosine
similarity.

Both are withdrawn. The first for the reasons in §2.6 and because the step from a
ratio to a redundancy percentage holds only if all excess length is flank, which
ceases to be true the moment a global contract is introduced. The second because
contextual embedding space is anisotropic — randomly chosen words already exhibit
high mean cosine similarity [34] — because cosine similarity in regularized models
can be "arbitrary and therefore meaningless" [35], because no embedding model
dominates across task types [36], and because the reference library for this
operation deliberately recommends **no threshold at all** and warns that the
similarity is asymmetric [37].

This version adds a third reason, and it is the deepest: **the cosine threshold is
a nucleotide-type instrument applied to protein-type material** (§5.2). It is not
that the threshold is badly calibrated; it is that the correct operation is a
learned substitution matrix, and §10.5 specifies it.

---

## 7. Swarm intelligence with small models

### 7.1 The thesis

Swarmbly dispenses with the monolithic model entirely. No participant holds a
shard of a 70B or 400B network. Worker nodes run *complete, independent* small
language models — typically 1–8B parameters, quantized, on consumer GPUs,
unified-memory laptops or multi-core CPUs — and each receives a decontextualized
micro-task and answers it in isolation. The client runs a small model too, but its
competence is a different one: not world knowledge, but *logic and syntax*, in the
sense of understanding the request, planning its decomposition and suturing the
returned fragments.

The claim is that advanced capability need not reside in a single large network,
but can be the arithmetic result of coordinating many small ones — the answer
emerging, as a genome does, only at assembly.

This is a strong claim. It is also partly supported, partly unsupported, and
partly false as usually stated. This section separates the three.

### 7.2 Coverage and conversion

I propose decomposing swarm performance into two independent factors.

**Coverage** `C` is the probability that *at least one* worker response to a given
micro-task is acceptable, and **conversion** `V` is the probability that the
orchestrator, given that acceptable fragments exist, selects and assembles them
into an acceptable whole.

For a plan of *N* micro-tasks with per-task coverage `Cᵢ` and a global conversion
factor `V`:

```
Q_system  ≈  V · Πᵢ Cᵢ
```

The product over *i* is the uncomfortable term — it is why `N` cannot grow freely
— but the factor that decides the architecture is `V`.

**Coverage scales with the swarm. Conversion does not.**

The evidence for the first half is strong. Repeated sampling raises coverage
log-linearly over four orders of magnitude of sample count: on SWE-bench Lite with
DeepSeek-Coder-V2-Instruct, 15.9% at one sample rises to 56% at 250 samples,
beating a 43% single-sample state of the art [38].

The evidence for the second half is equally strong and is usually overlooked. The
same work states that "majority voting and reward models plateau beyond several
hundred samples" — coverage keeps rising and the *ability to cash it in*
saturates [38]. Judge-based selection over diverse teams achieves an 81% win rate
against a single-model baseline, while homogeneous teams achieve 51.2% — chance —
and produce 100% ties across 756 verdicts [39]. And in the study closest to
Swarmbly's own architecture, an 8B multi-agent system ties a 32B single agent with
tools on GAIA (23.0 vs 23.0) and beats it on AIME (55.0 vs 45.0), running 4.2×
faster — but performance is "primarily driven by orchestrator capacity rather than
sub-agent capacity" [40].

### 7.3 Three consequences, and an unsupported hypothesis

**(a) The client is the ceiling, not the network.** The marginal value of the
*(N+1)*-th node is bounded above by the orchestrator's ability to select among what
already arrives. An engineering budget that buys nodes before it buys a better
client-side selector is spending in the wrong order.

**(b) Select; do not synthesize.** Judge-based selection beats synthesis-style
aggregation by 63.1 percentage points, and Mixture-of-Agents-style synthesis loses
to the plain single-model baseline in 42 of 42 tasks [39]. This stands in direct
tension with MoA's own reported results — 65.1% on AlpacaEval 2.0 against GPT-4
Omni's 57.5% using only open models [41] — and I flag the disagreement rather than
choosing the convenient side. The design resolves it conservatively: selection is
the default path, synthesis the exception invoked only at a failed seam.

**(c) Heterogeneity is an asset, not a defect.** Diverse teams reach 81% win rates
where homogeneous teams reach chance, and homogeneous outputs tie 100% of the time
— a selector given identical candidates has nothing to select [39]. The protocol
should preserve diversity deliberately: dispatch critical fragments to workers of
*different* model families, not merely different machines.

**The atomicity hypothesis remains unsupported.** The strongest form of the claim
— that a 3B model answering an atomic sub-task matches a frontier model — is not
established. What is supported is narrower, and there is a specific mechanism by
which the claim can fail: **a smaller worker requires more context to do the same
job.** Knowledge the model does not hold in parameters must be supplied in the
prompt. Shrinking the worker is not free; it is paid for in *S*, and *S* is paid
for in privacy and in cost.

> **H2 (Capability substitution).** For micro-tasks that are atomic, well
> specified and verifiable, there exists a context budget *S* at which a 3–8B
> worker's fragment quality is statistically indistinguishable from a frontier
> model's on the same micro-task; and the required *S* decreases as worker
> capability increases.

> **H3 (Conversion).** A client-side selector over *k > 1* heterogeneous workers
> recovers a specified fraction of oracle-selection quality. A recovery fraction
> that does not improve with orchestrator size would falsify the premise of
> consequence (a).

An 8B orchestrator is not obviously adequate for that role, and the literature is
discouraging: on a stateful planning task, Llama-3.1-8B-Instruct scored near
0–2%, and even frontier models looped in 92–100% of trials when constrained by an
external validator [44]. Small models make good *routers* — cheap routers cut
costs by over 85% on MT-Bench while retaining 95% of GPT-4 performance [46] — but
routing is classification, and planning is not.

### 7.4 A coverage model for semantic assembly

With the plan as reference sequence, the Lander–Waterman machinery applies — and
the source of randomness turns out to be exactly where the model's assumptions are
satisfied.

**Setup.** The plan `D` defines an ordered set of semantic units `U = {u₁ … u_M}`,
fixed before any generation occurs. Each dispatched packet `Kᵢ` targets a subset
`Sᵢ ⊆ U`. Nominal coverage is `c = (Σᵢ |Sᵢ|) / M`.

**Where the randomness lives.** This is the substantive difference from genomics,
and it is what makes the transfer legitimate:

> In genome sequencing, the stochastic element is **where the reads land**. In
> Swarmbly, placement is deterministic — the orchestrator chooses it. The
> stochastic element is **which packets come back**.

Volunteer nodes fail, time out, disconnect and return unusable output,
independently and at a rate the network can measure. Let *p* be that per-packet
loss probability. Effective coverage is `c_eff = c·(1−p)`, and the classical
results hold with `c_eff` in place of `c`:

```
P(unit u is uncovered)      =  e^( −c_eff )
E[ uncovered units ]        =  M · e^( −c_eff )
E[ assembly islands ]       =  N_p · e^( −c_eff · θ )
```

**The design equation.** Inverting the first result gives a redundancy requirement
derived from a stated tolerance:

```
c  ≥  ln(1/ε) / (1 − p)
```

| Loss rate *p* | ε = 5% | ε = 1% | ε = 0.1% |
|---|---|---|---|
| 0.05 | c ≥ 3.2 | c ≥ 4.8 | c ≥ 7.3 |
| 0.10 | c ≥ 3.3 | c ≥ 5.1 | c ≥ 7.7 |
| 0.20 | c ≥ 3.7 | c ≥ 5.8 | c ≥ 8.6 |

**And the field numbers to feed it.** Anderson & Fedak (2006) [131], over more
than 330,000 SETI@home hosts: mean on-fraction **0.81**, connected fraction
**0.83**, mean active fraction **0.84**, **host mean lifetime 91 days**. The 2018
version [132] reports ~700,000 devices and availability of **~60%** for desktop
machines and **~40%** for mobile. A loss rate of 16–40% is exactly the regime
threshold redundancy is designed for (§12.3).

**Scope, and a claim.** The model bounds *availability*: the probability that a
semantic unit goes unanswered. It does not model semantic correctness — a unit can
be covered by five replicas that all agree and are all wrong. Within that scope, I
believe this to be **the first coverage model published for semantic assembly**,
and it is the point at which the genomic framing stops being a vocabulary and
becomes a derivation.

**What §6.4 adds to it, and v1.4 did not have.** This model answers "will an
answer arrive?". It does not answer "does the answer contain the necessary
information?". That is Bresler et al.'s information condition, and it is
independent: **high coverage with unsolvable fragments produces a confidently
wrong assembly**.

### 7.5 The honest statement of the swarm thesis

> The swarm supplies **coverage**; the client supplies **conversion**. Additional
> nodes raise coverage with logarithmic returns and do nothing for conversion.
> Heterogeneity among nodes is what makes selection possible, and should be
> preserved rather than engineered away. The system's quality ceiling is set by
> the client's selector, and the worker size that suffices is a function of the
> context budget rather than a constant. And coverage answers only for
> availability: the solvability of the fragments is a separate condition that no
> number of replicas repairs.

**And now there is a measurement.** Over 80 operational table-summary cells (16 tasks × 5 families, equalised output budget), the mean tax per **node class** ranges from **+8.4 %** to **+26.5 %**, with within-class standard deviations of **16** to **39** points (T0RR, §15.9). Under the equalised budget every class comes out expensive — the earlier cheap/expensive split was the output-length confound (T09R) — and the variance *within* a class still exceeds the distance *between* classes. That last part is exactly why per-cell prediction fails (§10.1) and why the swarm answers for coverage rather than for the outcome of any particular cell.

---

## 8. Architecture

### 8.1 Roles

**Client / Orchestrator** — router, planner, contract generator, sensitivity
classifier, packer, speculative dispatcher, verifier, assembler, coherence
auditor. Requires an SLM (≥8B recommended; the adequacy of that figure is H3) plus
an embedding model.

**Worker node** — declares a profile, executes micro-tasks, emits verification
commitments and telemetry. Runs one complete small model.

**Network services** — peer discovery (DHT), reputation registry, credit
accounting, audit sampler. Deliberately minimal; no blockchain in v0.3.

### 8.2 Request lifecycle

```
                        [ Request P ]
                              |
              +---------------v----------------+
              |  ROUTER  -- decomposable? -----+--> NO --> local SLM / single capable node
              +---------------+----------------+
                              | YES
              +---------------v-----------------------------+
              |  PLANNER     -> DAG  D = (V,E)               |
              |                 weak-interface cuts (P9)     |
              |                 uniqueness set (M2)          |
              |  CONTRACT    -> Γ                            |
              |  SENSITIVITY -> lane per task                |
              +---------------+-----------------------------+
                              |
        +---------+-----------+-----------+-----------+
        |         |           |           |           |
    [Node 1]  [Node 2]    [Node 3]   ...        [TEE / local]
     K_i = ( Γ , σ(predecessors) , t_i )          (SENSITIVE lane)
        |         |           |           |           |
      [R_1]     [R_2]       [R_3]      ...          [R_s]
        +---------+-----------+-----------+-----------+
                              |
              +---------------v-----------------+
              |  TRIAGE    mechanical predicate per level (M3)
              |            pass / isolate-and-retry / discard
              |  VERIFY    LSH commitment + sampled audit
              |  ASSEMBLE  select > splice > bridge
              |  AUDIT     coherence, per seam; cardinality
              +---------------+-----------------+
                              v
              [ Response  +  coherence report  +  divergence map ]
```

Execution proceeds by topological level. Version 1.4 said "a level begins when its
predecessors have returned and been verified". This version specifies what that
verification means (§10.7) and adds that **consumption may begin before the level
is complete**, if the fragment being consumed is complete and has passed triage
(§10.7.4).

### 8.3 Triage, and why it is a specification rather than a metaphor

Biology has a name for that control, and it is precise. Gottesman, Wickner &
Maurizi (1997) [116] call it exactly that:

> "we propose […] a general model for what may be thought of as a **triage**
> system for handling misfolded proteins in vivo, ensuring the **rapid refolding
> of proteins with functional potential and the rapid degradation of irreversibly
> denatured or damaged proteins**."

That sentence is almost a specification of the quality-control stage: classify each
returned fragment as **recoverable → retry** or **unrecoverable → discard and
regenerate**, and **never splice a bad one into the assembly**.

The mechanism is equally instructive. The GroEL/GroES chaperonin does not repair
the piece in place: it **isolates** it. Xu, Horwich & Sigler (1997) [117] describe
how GroES binding "stabilizes a folding chamber" whose elevation and twisting of
the apical domains "doubles the volume of the central cavity and buries the
hydrophobic peptide-binding residues", leaving a hydrophilic lining "conducive to
folding". **Isolate and retry**, not patch in context.

**And there is evidence that levels matter, beyond justifying the DAG.** Netzer &
Hartl (1997) [118] found that two-domain polypeptides "fold efficiently by
sequential, co-translational folding" in eukaryotic translation, while the same
proteins folded post-translationally in *E. coli* suffer "intramolecular
misfolding of concurrently folding domains". Folding the domains one at a time, in
order, succeeded where folding them concurrently produced interference. The
argument is not that parallelism is bad; it is that **unrestricted** parallelism
is. Marsh et al. (2013) [119] add that the assembly order of protein complexes
"can be predicted simply from their three-dimensional structures" and that there is
**evolutionary selection to preserve order**.

**An honest complication.** Shiber et al. (2018) [120], via ribosome profiling,
found that **nine of twelve** hetero-oligomeric complexes studied assemble
co-translationally, and "co-translational assembly often occurs unidirectionally,
with a fully synthesized subunit engaging its nascent partner subunit". This
complicates the "fold everything, then assemble" picture in an exploitable
direction: a level-*n* fragment can be consumed while level *n+1* is still being
generated, provided the one being consumed is complete. It is an argument for
streaming assembly with a completeness condition, not for barrier waiting.

### 8.4 Latency model

The claim `max ≪ Σ` is directionally right and incomplete. The honest model is

```
T_total = T_plan  +  Σ_levels E[ max_{i ∈ level} t_i ]  +  T_triage + T_verify  +  T_assemble
```

Two of those terms are local and therefore predictable. Planning scales with `|P|`
and runs on the client's small model; assembly scales with `Σ|Rᵢ|`. The other two
are set by the swarm.

The first is the straggler tail. `E[max]` over *W* concurrent draws grows with
*W*, and volunteer tails are heavy: the measured effective duty cycle in BOINC is
≈0.61 and the median host lifetime is 91 days [47, 48]. With per-node failure
probability *p*, `P(at least one failure) = 1 − (1−p)^W`; at *p* = 0.10 and
*W* = 20 that is 88%. The protocol mandates **hedged requests** at the p95 of the
observed per-class latency distribution (§9.6), and this version adds over-dispatch
with early termination (§12.3), which attacks the same term by another route.

Triage adds a term v1.4 did not have. It is deliberate and it is cheap: the
predicate of §10.7 is mechanical, with no judge and no model. What it buys is that
the blast radius of a defective fragment stays contained in that fragment.

### 8.5 Worker profiles and determinism

A worker that runs an undeclared model, or a different quantization, silently
changes fragment quality and register. The profile is therefore part of the
protocol and is bound to the verification commitment:

```
profile = (model_family, model_version, quantization,
           prompt_template_id, sampling_params, seed_policy)
```

The orchestrator groups each DAG level into **homogeneous capability classes** to
control register mismatch, while deliberately preserving **family diversity across
redundant replicas** of the same task (§7.3c). These two goals are in tension and
the protocol makes the trade explicit: homogeneity *within* a fragment's role,
diversity *across* candidates for the same fragment.

**And this version adds `L` to the profile.** If `L` is a property of the node
class (§5.7), the node must declare it and the planner must be able to read it,
because `N` is derived from it. A node that declares an `L` it does not sustain
produces fragments that are not domains, and that is indistinguishable from the
outside from a node that answers badly.

---

## 9. Protocol specification (v0.3)

This section is written to be implementable. Field names are normative; encodings
are given as JSON for clarity and MAY be CBOR on the wire. Changes relative to
v0.2 are marked **[v0.3]**.

### 9.1 Identifiers

- `session_id` — 128-bit random, generated per request, never reused.
- `task_id` — `BLAKE2b-128(session_id || level_index || task_index)`, truncated to
  16 bytes, hex-encoded.
- `attempt_id` — `task_id || ':' || attempt_counter`.

A worker learns `task_id` and `attempt_id`. It MUST NOT learn `session_id`; the
derivation is one-way so that two workers cannot determine that they hold
fragments of the same session by comparing identifiers. This does not defeat
timing correlation (§13.2) and is not claimed to.

### 9.2 Global contract Γ

```json
{
  "v": "0.3",
  "objective":  "string  — what the complete response must accomplish",
  "audience":   "string",
  "register":   "formal|neutral|informal|technical",
  "format":     "prose|markdown|json|code",
  "target_len": 0,
  "lexicon":    { "prefer": ["…"], "forbid": ["…"] },
  "entities":   [ { "name": "…", "canonical": "…", "role": "…" } ],
  "style_seed": "string — deterministic style anchor shared by all workers",
  "budget":     { "max_out_tokens": 0 }
}
```

`entities` is the mechanism that prevents inconsistent naming across fragments —
the assembly analogue of a shared coordinate system. `style_seed` is a short fixed
phrase all workers are instructed to match, which costs a handful of tokens and
materially reduces register drift.

`|Γ|` is the dominant term in *S* and is therefore the object of the research
direction of §6.3. **[v0.3]** It is also the `H` term of the derivation in §6.5:
measured at ≈ 39 tokens over the project corpus, it is what makes fragmenting too
finely expensive independently of coherence.

### 9.3 Task packet

```json
{
  "v": "0.3",
  "attempt_id": "hex",
  "contract": { /* Γ */ },
  "predecessors": [ { "task_id": "hex", "summary": "string", "tokens": 0 } ],
  "task": {
    "instruction": "string",
    "kind": "extract|classify|generate|summarize|transform|judge",
    "expects": { "format": "…", "min_tokens": 0, "max_tokens": 0 }
  },
  "unique_here": ["…"],
  "flank": { "lead": "string", "trail": "string", "sentences": 0 },
  "constraints": { "temperature": 0.0, "top_p": 1.0, "stop": ["…"] },
  "commitment_request": { "scheme": "lsh-activation-v1", "params": { "window": 32 } },
  "deadline_ms": 0,
  "lane": "PUBLIC|SANITISABLE",
  "tier": "GLOBAL|TRUSTED",
  "swarm_id": null
}
```

**[v0.3] `unique_here`** is the list of uniqueness-set elements assigned to *this*
fragment and only this one (§11.3). It is not a style instruction: it is the
visible half of a global constraint resolved in the plan. A node cannot satisfy
"exactly once in the whole output" because it does not know what the others wrote;
it can satisfy "these elements go here".

**[v0.3] `flank`** carries the overlap derived in §6.5, with its length declared
in sentences. Declaring it explicitly lets the assembler know which part of the
returned material is flank and not body, which is what allows the overlap to be
discounted at assembly rather than reappearing as repetition.

Packets on the `SENSITIVE` lane are never emitted to open nodes. The `tier` field
is orthogonal to `lane`: it names the *population* a packet may reach rather than
the sensitivity of its content.

### 9.4 Result

```json
{
  "v": "0.3",
  "attempt_id": "hex",
  "text": "string",
  "profile": { "model_family": "…", "model_version": "…", "quantization": "…",
               "prompt_template_id": "…", "sampling_params": { }, "seed": 0,
               "L_declared": 0 },
  "commitment": { "scheme": "lsh-activation-v1", "digest": "base64", "bytes": 0 },
  "telemetry": { "gen_ms": 0, "queue_ms": 0, "tokens_out": 0, "energy_j": null },
  "sig": "ed25519 signature over the canonical serialization of all preceding fields"
}
```

**[v0.3] `L_declared`** is the fragment size the node class sustains (§8.5). The
orchestrator uses it to derive `N` and to detect nodes whose declared `L` does not
match their observed behaviour.

### 9.5 Node profile advertisement

```json
{
  "node_id": "ed25519 public key",
  "models": [ { "family": "…", "version": "…", "quantization": "…",
                "ctx": 0, "tok_per_s_est": 0, "L_sustained": 0 } ],
  "capabilities": { "tee": false, "attestation": null },
  "swarm": { "swarm_id": null, "registry": null, "mtls_cert_fingerprint": null },
  "resources": { "vram_mb": 0, "ram_mb": 0 },
  "policy": { "max_tokens_per_task": 0, "kinds": ["extract","generate"] },
  "reputation": { "completed": 0, "audit_pass_rate": 0.0, "since": "ISO-8601" }
}
```

### 9.6 Dispatch, hedging, over-dispatch and retry

1. Filter candidates by `tier` first — a packet marked `TRUSTED` is offered only
   to nodes whose public key appears in the named swarm's whitelist — and then by
   declared capability, `kind` support, and observed RTT.
2. For a task of criticality `k`, dispatch to `k` nodes selected to **maximize
   model-family diversity** subject to the capability class.
3. Start a hedge timer at the **p95** of the observed latency distribution *for
   that task kind and token budget*, not at a fixed constant. On expiry, dispatch
   an additional replica; accept the first result that verifies.
4. **[v0.3] Over-dispatch with early termination.** For a level of `N` distinct
   sub-tasks, dispatch `N + m` and accept the first `N` that return and pass
   triage, discarding stragglers. **Normative condition:** this is admissible only
   when the `m` extras are *genuinely interchangeable* sub-tasks (§12.3). If the
   content of fragment *j* is needed, receiving the other `N−1` does not
   substitute for it, and the scheme does not apply.
5. Cancel outstanding replicas on acceptance. Record cancellations — a node whose
   work is habitually cancelled is slow, not dishonest, and reputation must
   distinguish the two.
6. On verification failure, re-dispatch excluding the failing node and record the
   event for the audit sampler.

### 9.7 Parameter table

| Parameter | Symbol | Default | Derivation |
|---|---|---|---|
| Fragment size | *L* | **property of the node class** | §5.7; declared by the node, verified by behaviour |
| Fragment count | *N* | **derived** | `N = ⌈material/L⌉` (§5.7). No longer a parameter |
| Flank | *F* | **measured** | max(longest repeat, longest crossing dependency) (§6.5) |
| Header cost | *H* | measured | ≈ 39 tokens on the project corpus (§6.5) |
| Context budget | *S* | derived | `S = |Γ| + E[|σ|]`, with `|Γ| = H` |
| Redundancy ratio | ρ | **derived** | `(L+2F)/L + H/(L·s)` (§6.5). Reported, not configured |
| Dependency density | δ | **measured** | necessary relations crossing a boundary, per fragment (§6.8) |
| Seam threshold | τ_sem | **calibrated** | §10.6; never a constant |
| Router threshold | τ_route | calibrated, asymmetric | β<1 in F_β [12] |
| Criticality replicas | *k* | **split into three** | §12.4: `k_avail`, `k_verif`, `k_epist` |
| Hedge trigger | — | p95 per class | §8.4 |
| Over-dispatch extras | *m* | 0 unless interchangeable | §9.6.4, §12.3 |
| Audit sampling rate | λ | 0.01–0.05 | §13.3 |
| Max plan width | — | 8 | The straggler tail grows with width |
| Max plan depth | — | 4 | Beyond this, dependency density argues for not fragmenting |

---

## 10. Algorithms

### 10.1 Router

```
function is_decomposable(P) -> (bool, score)
    f ← features(P):
        · task-kind signals (extract / enumerate / summarize vs prove / derive / refactor)
        · length of P
        · density of sequential-dependency markers
        · presence of shared mutable state (code, ledgers, running totals)
        · request for a single artifact vs a set of items
        · [v0.3] estimated dependency density δ (§6.8)
    score ← classifier(f)
    return (score > τ_route, score)
```

τ_route is calibrated with **F_β, β < 1**: a false positive — fragmenting
something that should not be — costs more than a false negative. That is the SoT-R
lesson, and it is the difference between a system that improves on 2023 and one
that regresses from it.

**[v0.3]** Including δ as a feature is a direct consequence of §6.8: if distortion
depends on dependency density and not only on rate, then the router — which is
what decides whether to fragment — must see that density. A router that sees only
length is measuring the wrong axis.

**And that feature was measured, with a result that forces a design change.** Over 80 operational cells, a classifier trained with leave-one-task-out validation reaches **AUC 0.57** with δ and reputation, and **0.61** with neither: adding δ improves nothing (T0RR). With pre-dispatch capability probes in place of δ, **AUC 0.57** (T0RR2). **Per-cell prediction does not work**, and the failure is not δ's in particular: no subset of features rescues it.

What does separate is the **node class**. The same corpus gives mean taxes per family from +8.4 % to +26.5 %, and a policy that decides by class — fragment if that class's historical tax is negative — obtains **+0.0 %** against **+14.8 %** for always fragmenting: under the equalised budget every class has a positive historical tax, so the class policy refuses them all and avoids the whole tax. The per-class policy is the router that works: it needs no per-cell prediction, and its decision is exactly the one P2 prescribes when the measured economics say "do not fragment".

> **Design consequence.** The router of §10.1 decides *whether the prompt is decomposable* — and that remains verified: 22 of 22 decisions agree with the corpus truth (T0R). What it must **not** attempt is to predict the cost of a particular cell. That decision moves to the node profile: the class declares its history, and the orchestrator routes by class. δ is kept as a feature of the plan and **withdrawn as a predictive feature of the router**.

### 10.2 Planner

```
function plan(P, L) -> (D = (V,E), Uniq)
    boundaries ← candidate_cuts(P)                  # [v0.3] P9
    weight     ← estimated_coupling(boundary)       # dependencies that would cross
    cuts       ← select_minimal(boundaries, weight, size_target = L)
    units      ← segment(P, cuts)
    for each ordered pair (u, v):
        E ← E ∪ {(u,v)}  if v requires the *result* of u, not merely its statement
    assert acyclic(D)
    if width(D) == 1: return REFUSE       # a chain is not parallelizable
    if depth(D) > max_depth: return REFUSE
    Uniq ← uniqueness_set(P, Γ)                     # [v0.3] M2, §11.3
    assign each element of Uniq to exactly one node of V
    return (D, Uniq)
```

The distinction between requiring a predecessor's *result* and requiring its
*statement* is the crux. Least-to-most prompting achieves ≥99% on SCAN against 16%
for chain-of-thought precisely by respecting result-dependencies sequentially
[51]; a planner that mistakes a result-dependency for a statement-dependency
converts that gain into a loss.

**[v0.3] Two substantive changes.** First, the cut is no longer by size: `L` enters
as `size_target` and the selection minimises the coupling cut, which is P9 and is
the minimisation of δ from §6.8. Second, the planner computes the uniqueness set
and assigns it — the global constraint is resolved here, where global information
exists, and not at the node, which has none.

### 10.3 Packing

```
function build_packet(Γ, t_i, preds, L, F) -> K_i
    base  ← Γ                                    # never trimmed
    flank ← take_flank(neighbours(t_i), F)       # [v0.3] derived, not a percentage
    order preds by (edge weight, recency)
    for p in preds while budget remains:
        s ← summarize(p.result, min(budget, cap_per_pred))
        attach(s)
    return (Γ, flank, attached, t_i, unique_here(t_i))
```

Γ is never trimmed to meet a budget. If the budget falls short, the planner
**increases `L`** — fewer, larger fragments — rather than trimming shared context.
Version 1.4 said "reduce `N`", which is the same thing under the old formulation;
under the new one, `N` is derived and `L` is the lever. It is the LongRAG result,
where 4K-token retrieval units and fewer than eight top units matched fully
trained state of the art with no training at all [52].

### 10.4 Assembly

```
function assemble(fragments, D, Γ, Uniq, τ_sem) -> (text, seam_report, cardinality_report)
    ordered ← topological_flatten(D)
    chosen  ← []
    for t in ordered:
        cands ← fragments[t]
        chosen.append( cands[0] if |cands| == 1
                       else judge_select(cands, Γ) )       # select, do not synthesize
    discount_flanks(chosen)                                # [v0.3] §9.3
    out, seams ← [], []
    for (a, b) in consecutive(chosen):
        sim ← cos( embed(tail_window(a)), embed(head_window(b)) )
        if sim ≥ τ_sem:
            out.append(a); seams.append((a,b,"splice",sim))
        else:
            bridge ← slm.write_transition(tail(a), head(b), Γ)
            out.append(a); out.append(bridge)
            seams.append((a,b,"bridge",sim))
    card ← verify_cardinality(out, Uniq)                   # [v0.3] M2, §11.3
    return join(out), seams, card
```

Every seam is recorded with its similarity and the path taken. The seam report is
part of the response, per P6.

**[v0.3]** Two steps are added. `discount_flanks` removes the declared overlap
before splicing, so that the flank does its job — enabling repeat detection and
continuity — without reappearing as duplicated text. `verify_cardinality` checks
the output against the set computed in the plan, not against a rule stated in the
contract.

### 10.5 Consensus by multiple alignment of replicas (E16, revised)

Section 10.4 resolves *different* fragments in *different* positions. This section
resolves *k replicas of the same micro-task*.

**Two levels, deliberately distinct.**

| Level | Unit | Mechanism | When |
|---|---|---|---|
| **Macro** | Different sub-tasks of one large task | Overlap-and-splice with flank (§10.4) | Long generative work |
| **Micro** | *k* complete replicas of the same micro-task | **Multiple alignment and consensus** (this section) | Every micro-task of criticality *k > 1*, including a request that was atomic from the start |

An atomic request — one that the router declines to decompose — skips the macro
level entirely and goes straight to the micro level with *k* replicas. **Splitting
an atomic question into partial questions is not a supported operation**, because
it removes information before sampling rather than sampling redundantly; no amount
of coverage recovers it.

#### 10.5.1 What the state of the art does, and where the opening is

The recent literature on uncertainty in generation is abundant and good.

**Semantic entropy** (Kuhn, Gal & Farquhar, ICLR 2023 [98]; Farquhar et al.,
*Nature* 2024 [99]) samples several answers, clusters them by semantic equivalence
via **bidirectional entailment**, and computes entropy over meaning clusters
instead of over token sequences. Average AUROC 0.790 across 30 model-and-task
combinations.

**SelfCheckGPT** (Manakul, Liusie & Gales, EMNLP 2023 [100]) produces
**per-sentence** factuality scores by comparing each sentence against complete
samples.

**Semantic agreement across different models** (Soiffer et al., 2025 [101]) uses
agreement among smaller models as a deferral signal.

**What all of them share, and this is the opening:** they treat the `k` answers as
**a bag to be clustered**. None treats them as **sequences to be aligned**.
Clustering yields a scalar per answer; alignment yields a **position-to-position**
correspondence, which is what allows one to say *where* they diverged and not only
*how much*.

#### 10.5.2 The instrument exists and is mature

**Substitution cost is learned, not postulated.** That is the lesson of BLOSUM
(§5.2). In the text domain it is already solved at the string level: Ristad &
Yianilos (1998) [96] give "an efficient algorithm for learning the primitive edit
costs from a corpus of examples", via a stochastic transducer fitted by EM.

**And it is solved at the phrase level.** PPDB 2.0 (Pavlick et al., ACL 2015) [97]
is a paraphrase database rescored discriminatively: they collected human judgements
over **26,455 pairs**, each rated by 5 people on a 5-point Likert scale, and fitted
a ridge regression over **209 features**.

The result is the single most useful datum in this whole investigation for the
project:

> **The heuristic ranking correlated with human judgement at ρ = 0.41. The
> empirically fitted model reached ρ = 0.71. And in that model embedding cosine is
> one feature out of 209.**

That is published, quantified evidence that **raw embedding distance is not the
right instrument** for judging semantic interchangeability — which is exactly what
the map needs to judge, and exactly what v1.4 used.

**Consistency-based alignment is the design this wants.** T-Coffee (Notredame,
Higgins & Heringa, 2000) [94] builds a primary library of pairwise alignments and
then **extends** it: for each pair of residues it examines their alignment with
residues from the other sequences, and "the weight associated with a pair of
residues will be the sum of all the weights gathered through the examination of
all the triplets involving that pair". Translated: **an agreement corroborated
through a third, independent answer weighs more than an agreement between two.**
And the progressive phase uses "position-specific scoring" instead of a fixed
matrix.

**And the formalisation of the product exists too.** A profile HMM (Eddy, 1998)
[95] "turns a multiple sequence alignment into a position-specific scoring
system". A position-specific scoring model built from a set of aligned answers is
the formal description of a confidence map.

#### 10.5.3 The proposed model

> **M1 — Multiple alignment of answers with learned semantic substitution.**
>
> 1. **Segment** each of the `k` answers into sentences (the alignment unit of
>    §5.7).
> 2. **Align** the `k` sentence sequences by dynamic programming with affine gap
>    penalties (Gotoh, 1982) [93], using a semantic substitution matrix.
> 3. **Build that matrix empirically**, BLOSUM-style: count pairs of sentences
>    that appear as mutual substitutions in cases verified as correct, and score
>    `log(q_obs / e_exp)`. The embedding enters as a feature, not as a verdict.
> 4. **Extend by consistency**, T-Coffee-style: weight each correspondence by its
>    corroboration through the other answers.
> 5. **Emit** a position-specific profile over the resulting alignment. That is
>    the map.

**What is new and what is not.** Nothing in steps 2, 3 and 4 is invention: they are
Needleman-Wunsch with Gotoh, Henikoff with Ristad, and Notredame. What is new is
**applying them to outputs from different models instead of to biological
sequences**, and doing so to produce a per-unit annotation rather than a scalar per
answer. The contribution is the assembly of the instrument, not its parts, and it
must be stated that way.

#### 10.5.4 What remains withdrawn

**The confidence map's reliability claim remains withdrawn, and M1 does not lift
it.**

Version 1.4 measured the correlation between per-unit agreement and correctness,
first against a peer-class judge (*r* = −0.030 over 597 units, with the judge
accepting 93.3% — too saturated to discriminate) and then against an answer key in
three runs, which returned common odds ratios of **3.47, 0.26 and 1.24**: above,
below and astride 1 on the same question. Three mutually contradictory estimates
are not a weak signal; they are no signal, measured three times.

M1 proposes a **different instrument**, not a reinterpretation of that result.
That means three things, and they belong together:

1. Confidence labels are reported as **agreement**, never as **accuracy**, and the
   map is not offered as a reliability guarantee. This does not change.
2. **The mechanism is still real.** Reporting *where* independent replicas diverged
   is a capability, and it is the one a single-model provider does not have. What
   may not be presented is convergence as evidence of correctness.
3. M1 has its own death condition, stated in §15.6: if with the correct instrument
   and **in a regime where the models genuinely disagree** the per-unit agreement
   does not beat chance, then localisation creates no signal and M1 falls. The
   regime clause is not an escape hatch: it is the correction of the known defect
   in the first measurement, where the judge accepted almost everything and no
   variance remained for a correlation to appear against. Declaring it in advance
   is what prevents it being used afterwards.

**Three honest caveats that do not change.** Agreement is not truth: models trained
on overlapping corpora share errors, and convergence on a common falsehood is a
correlated failure that alignment cannot see — which is why §9.6 mandates
cross-family diversity. The map costs *k*×, and it is applied by criticality, not
universally.

### 10.6 Threshold calibration

```
function calibrate_tau(labelled_pairs, embedder, β = 0.5) -> (τ*, curve)
    sims  ← [ cos(embed(a.tail), embed(b.head)) for (a,b,label) in pairs ]
    for τ in quantiles(sims, 200):
        compute precision/recall of "is a broken seam"
        F_β ← (1+β²)·P·R / (β²·P + R)
    return argmax_τ F_β, curve
```

β < 1 weights precision: declaring a seam broken triggers a rewrite, and
unnecessary rewrites are how a system degrades text that was already fine. τ must
be re-derived whenever the embedding model changes, for the anisotropy reasons of
§6.9.

**[v0.3]** While M1 is not built, this threshold is the operative instrument and
is retained. When it is built, the learned substitution matrix replaces it at the
micro level (§10.5) and τ_sem is restricted to the macro level, which is where it
compares *the end of one fragment* with *the start of the next* rather than two
versions of the same thing.

### 10.7 The triage gate

```
function triage(carry, task_that_requested_it) -> PASS | RETRY | DISCARD
    if not answers(carry, task_that_requested_it):    # mechanical predicate
        return RETRY if attempts < r else DISCARD
    if violates_schema(carry, task.expects):
        return RETRY if attempts < r else DISCARD
    return PASS
```

> **M3 — Triage gate per topological level.**
>
> 1. A level does not start until the carries from its predecessors have passed a
>    **mechanical predicate**: *does the carry that arrived answer the task that
>    requested it?* No judge, no model, cheap.
> 2. A fragment that does not pass is **isolated and retried**, not patched in
>    context nor spliced in with a warning.
> 3. A fragment that does not pass after `r` retries is **discarded and
>    regenerated** with a different plan. Degradation is a legitimate output of
>    triage, not a system failure.
> 4. Consumption may begin **before the level is complete**, if the fragment being
>    consumed is complete and verified (§8.3, Shiber et al.).

**Why it matters, with a datum from the project.** There is a recorded incident
this gate catches: 42 of 60 dispatched packets carried another packet's answers.
Without a gate, carries pass forward unreviewed and one level's error multiplies
into the next. With a gate, the blast radius is one fragment.

**And its death condition.** If the gate rejects so much legitimate work that the
retry cost exceeds the damage it prevents, M3 falls. It is a cheap measurement and
its prediction is binary: the incident happens or it does not.

### 10.8 Coherence audit

Two instruments, reported separately and never merged into a single "quality"
score — merging is exactly how the damage hides [12]:

1. **Entity-grid local coherence** [53] — entity mentions and grammatical roles
   across sentences, scored from transition probabilities.
2. **Seam error taxonomy** — the mechanically detectable subset of the error
   classes identified from 1,193 human annotations over 100 books [54]: entity
   omission, duplicated content, contradiction, register or tense shift, dangling
   reference, missing transition, repeated introduction, inconsistent naming.

The headline figure is the **coherence tax**: relative degradation against
monolithic generation with the same model.

**[v0.3] A third report is added, separate from the other two: the cardinality
report** (§11.3, point 4), with over-compression and over-expansion counted
separately. They are different errors with different causes, and measuring them
together hides both.

**And a limitation v1.4 documented that still stands.** The entity grid does not
function on short answers: it returned monolithic baselines between 0.000 and
0.114 across the whole corpus, which makes every relative comparison built on it a
ratio over a near-zero denominator. Either the evaluation corpus moves to longer
outputs or the instrument is replaced; until then this document has one working
coherence instrument, not two (L14).

---

## 11. Cardinality constraints

This section is new. It treats the class of constraint no node can satisfy in
isolation: "mention this term exactly once", "do not repeat a formulation". It is,
by the project's measurements, the irreducible class.

### 11.1 A hypothesis that did not survive

The hypothesis was: *mate pairs are the homologue of global constraints, because
they are the mechanism genomics invented for information that no individual read
contains.*

> **Background concept.** A *mate pair* or paired-end read is a pair of reads
> sequenced from the two ends of the same DNA fragment of approximately known
> length. Weber & Myers (1997) [106] introduced it because "read pairs from both
> ends have known spacing and orientation", which "aids the assembly of sequences
> containing dispersed repetitive elements".

Half the hypothesis is correct: constraints that cross fragments are real, they
are the central difficulty, and genomics did invent explicit machinery for
information that no single piece contains.

The other half is wrong, and it is wrong along four axes at once:

| axis | mate pair | "exactly once in the whole output" |
|---|---|---|
| **Arity** | Binary and pre-identified: it names two concrete reads, and the pair exists before assembly because library preparation created it | n-ary and quantified: it names no pair; it quantifies over all fragments |
| **Metric content** | It is fundamentally a **distance**, with a distribution — Myers et al. (2000) [107] report insert lengths "normally distributed with 10% variance" | It has neither distance nor orientation |
| **Hardness** | **Soft**: Opera (Gao, Sung & Nagarajan, 2011) [108] defines concordance as a predicate the optimiser **maximises**; a discordant mate pair is tolerated | **Hard**: a single violation is a failure, not a datum to be outvoted |
| **Direction of information** | **Evidence**: an additional observation sampled from a genome that already exists | **Specification**: there is no true answer to recover; it is a condition imposed on the output |

The fourth axis is the deepest. Genome assembly is **maximum-likelihood inference
toward a correct answer that pre-exists**. Swarmbly does **constraint satisfaction
over a space of acceptable outputs**. Mate pairs live on the inference side.

**What a mate pair actually is.** The transfer is not null: it is narrower in
scope. Mate pairs are the correct homologue of a real class of constraint:
**"fragment A and fragment B must be mutually consistent at a known relative
position"**. The conclusion must pick up the anecdote from the introduction;
section 4 must resume the thread left open by section 2; a reference to a figure in
one fragment must correspond to a figure defined in another. They are binary, they
have a positional component, they are known in advance because the plan created
them, and they degrade gracefully when partially violated. For those, the argument
of §11.3 transfers along with the homology.

### 11.2 The correct homologue is in the same literature

Genomics does have a mechanism whose form is "this must appear exactly N times in
the whole output". It is not mate pairs. It is **multiplicity** and **uniqueness**.

**k-mer multiplicity.** Compeau, Pevzner & Tesler (2011) [104] state it as a
counting operation that enters the graph structure: one must determine "how many
times each k-mer appears", and "if the multiplicity of a k-mer is m, we will
connect its prefix to its suffix using m directed edges (instead of just one)".
That is a global cardinality constraint imposed **structurally** rather than as an
after-the-fact check.

**U-unitigs.** Myers et al. (2000) [107], in the *Drosophila* assembly, describe
that those units "that are certain to represent unique DNA were designated
U-unitigs" — and all the scaffolding is anchored on them. It is literally the
"exactly once in the whole output" mechanism: the assembler **computes the set of
sequences that must appear exactly once** and builds around them.

**The failure mode, which confirms the transfer.** Myers (1995) [105] names the
pathology when this is done badly: seeking the shortest string containing all
fragments means that "in the case of repetitive target sequences this objective
produces over-compressed answers". **Over-compression** is exactly the failure of
an assembler that merges two passages that should have remained distinct. And its
dual — emitting twice something that should have appeared once — is the failure
`no_repeated_ngram` measures.

### 11.3 The proposed model

The strongest architectural lesson comes from Medvedev et al. (2011) [109], who
argue against after-the-fact treatment: mate pairs have been incorporated "as
various heuristic post-processing steps", which "may still fail to resolve complex
repeats"; their proposal is to incorporate the information **into the graph
structure itself**.

> **M2 — Cardinality constraints resolved in the representation, not in the
> output.**
>
> 1. **Compute the uniqueness set before dispatch.** Which terms, entities and
>    formulations must appear exactly once in the final output. It is the analogue
>    of identifying U-unitigs.
> 2. **Assign each element of that set to exactly one fragment**, as a property of
>    the plan and not as an instruction to the nodes. A node cannot satisfy
>    "exactly once" because it does not know what the others wrote; the planner
>    can. It is the `unique_here` field of §9.3.
> 3. **Verify cardinality at assembly**, against the set computed in step 1, not
>    against a rule stated in the contract.
> 4. **Log the two failure modes separately**: over-compression (what should have
>    been distinguished was merged) and over-expansion (what should have appeared
>    once was repeated).

**Point 2 is the real change, and there is a number to compare it against.** Today
the project asks for `term_once` in the contract and enforces it mechanically at
the assembler. That works, and the measurement confirms it: mechanical enforcement
raised compliance from **6/24 to 18/24**, above the monolithic arm's 13/24. But it
is an after-the-fact correction. **Assigning uniqueness in the plan makes the
constraint impossible to violate rather than detectable afterwards**, which is
precisely Medvedev et al.'s argument.

**Its death condition, stated in advance:** if assignment in the plan does not
reduce violations below what mechanical enforcement at the assembler already
achieves (18/24), M2 adds nothing and falls. M2's prediction is strong — the
violation rate should fall to zero, not improve — precisely so that it is easy to
refute.

**It was measured, and the strong prediction is false as written.** Over 35 unique terms in 10 real cells (2 tasks × 5 families), nodes that receive `unique_here` produce **6 of 35** exactly once: **0 terms omitted** and **29 repeated** (T03R). A small model does not obey "exactly once" because it is told to; the field tells it what is its share, not how many times to write it.

**And yet M2 stands, corrected.** Running those same outputs through the assembler's mechanical enforcement — the v1.4 one, not a new one — the result is **35 of 35** exactly once. The asymmetry is the finding: over-expansion is trimmed mechanically, over-compression is not invented, and there were **zero** omissions. That is: **assignment in the plan removes the irreparable failure mode, and enforcement at the assembler removes the reparable one**.

> **Correction to M2.** The mechanism is not "assignment in the plan **instead of** enforcement at the output", but **assignment in the plan plus mechanical enforcement at assembly**. Assignment *localizes* responsibility; enforcement *guarantees* it. The phrase "zero by construction" is **withdrawn**: what is zero by construction is over-compression, not cardinality violation in general. The declared death condition (beat 18/24) is met — 35/35 over 35 terms — but it is met thanks to a component M2 proposed to render unnecessary, and that has to be said in those words.

---

## 12. Redundancy: what *k* is for

### 12.1 A second hypothesis that did not survive

The hypothesis was: *instead of sending the same packet to `k` nodes, send `N + m`
encoded fragments of which any `N` suffice to reconstruct.*

The motivation was good and is well founded in the storage literature.
Weatherspoon & Kubiatowicz (2002) [126] show that erasure codes "use an order of
magnitude less bandwidth and storage than replication for systems with similar
MTTF": with a million machines and 10% down, two full replicas give "only two
nines of availability", while an encoding into 32 fragments gives "more than eight
nines" with the same storage. Fountain codes take that to the limit: Luby (2002)
[124] proves recovery from "any `k + O(√k · ln²(k/δ))` of the encoding symbols
with probability `1 − δ`"; Shokrollahi (2006) [125] improves it to "any subset of
symbols of size `(1+ε)k`" with `O(1)` operations per symbol.

**Why it does not transfer.** The reason is clean and admits no nuance.

**Fountain codes are linear codes over shared unknowns.** Shokrollahi's definition
says so: "each output symbol is the sum of some of the input symbols", and decoding
is Gaussian elimination or peeling over that linear system. The entire mechanism by
which "any `k(1+ε)` suffice" **is** that the received symbols are **linear
equations in the same unknowns**.

Swarmbly's fragments are not equations in shared unknowns. Each node **generates
new text**. There is no XOR, no algebraic field, no inverse. There is nothing to
solve for.

And this is not an inference of our own: it is the explicit limitation stated in
the coded-computing literature. Kosaian, Rashmi & Venkataraman [128] note that much
work employs erasure codes for computing **linear functions**, and that "to the
best of our knowledge, none of the existing works are applicable to broader classes
of non-linear computations". What does exist confirms the diagnosis from the
positive side: Mallick et al. (2019) [127] obtain up to **3× speedup** applying
rateless codes to distributed matrix-vector multiplication — **because
matrix-vector multiplication is linear**. And the only serious attempt at coding
non-linear inference, ApproxIFER [129], achieves **approximate** recovery over
low-dimensional classification outputs, with accuracy losses of up to ~6–9% in
degraded mode.

A specific search was made for prior work applying fountain codes to LLM agent
redundancy or to decentralised LLM inference. **None exists.** The transfer has not
been attempted, and linearity explains why.

### 12.2 Applying the method of §3

This fall is the cleanest example of the failure-mode test. Fountain codes were
proposed for their recovery property — "any `k(1+ε)` suffice" — with no condition
on when that property ceases to exist. The condition exists, it is published, and
it is linearity. Looking for it would have saved the entire hypothesis.

### 12.3 What does transfer: the economics, not the mechanism

The real lesson of the storage literature is not about XOR. It is about
**thresholds and quorums**: for a target reliability, `(N, N+m)` beats `k`-fold
duplication.

> **M5a — Over-dispatch with early termination.** Dispatch `N` distinct sub-tasks
> plus `m` extras, accept the first `N` that return and pass triage, discard
> stragglers. It is a threshold scheme, it delivers the ρ saving that was being
> sought, **and it is not a fountain code**. Calling it one would be the very
> error Section 3 exists to avoid.

**With one condition that must be stated, because it is the core of the
trade-off:** the `m` extras are only free if the sub-tasks are **genuinely
interchangeable**. The entire point of erasure coding is that *any* `k` symbols
serve. Swarmbly's fragments are not interchangeable: if the content of fragment `j`
is needed, receiving the other `N−1` does not substitute for it. Making them
interchangeable requires content redundancy, which costs exactly the ρ one wanted
to save. That is why §9.6.4 makes it normatively conditional.

### 12.4 Separating the three purposes of *k*

This is the finding that reorders the role of `k`, and it is probably more valuable
than the original hypothesis.

`k` today serves **three distinct purposes** that the design does not separate:

- **Availability** (`k_avail`) — that the task completes even if a node goes down.
- **Verification** (`k_verif`) — that a dishonest node cannot impose a false
  result.
- **Epistemic redundancy** (`k_epist`) — that the divergence map has something to
  align.

Sarmenta (2002) [133] measures the cost of each route in volunteer computing:
voting "reduces error rates exponentially with redundancy, but requires all work to
be done several times, and does not work well when there are many saboteurs";
spot-checking "reduces the error rate linearly with the amount of work to be done,
while only costing an extra fraction of the original time"; and the
credibility-based combination yields "mathematically guaranteeable levels of
correctness with much less slowdown". BOINC [130] implements the deployed version:
adaptive replication achieving "a low bound on the error rate […] even in the
presence of malicious volunteers, while imposing only a small performance
overhead".

> **M5b — The design consequence.** If `k` exists for **verification**, erasure
> codes were never the tool; credibility-based spot-checking is. If `k` exists for
> **availability**, threshold over-dispatch solves it. And if `k` exists for the
> **divergence map** — epistemic redundancy — then it is replaceable by neither,
> because its product is not fault tolerance but signal.

Three purposes, three mechanisms, and today a single parameter. **Separating them
is an immediate improvement to the protocol, available without measuring
anything** — which is why §15.6 puts it first in the order of attack.

And it connects with something v1.4 had already discovered by another route. The
trusted-swarm section (§13.5) observed that a cryptographic whitelist removes the
need for adversarial redundancy but not for epistemic redundancy, and required that
lowering `k` to 1 be declared explicitly. That was this separation, seen from a
particular case. Now it is general.

**Its death condition:** if the three turn out to be so coupled in practice that
separating them saves nothing, M5 falls.

---

## 13. Privacy, verification and adversarial nodes

### 13.1 Fragmentation is not encryption

Early development of this concept described decontextualized fragmentation as a
form of "quasi-encryption," on the reasoning that a node holding one fragment
without global context holds nothing of value. That reasoning does not survive
contact with the re-identification literature, and the claim is withdrawn.

Four findings converge. The first is that quasi-identifiers suffice: the
combination of ZIP code, date of birth and gender uniquely identifies roughly 87%
of the US population even though none of the three is an identifier on its own
[55], and although a later revision puts the figure near 63%, that is not
reassuring. Every syntactic fragmentation or generalization defence proposed in
that literature has since been broken by a subsequent attack [56], and sparse
high-dimensional data turns out to be inherently re-identifiable from a handful of
coarse, noisy attributes [57].

The second is that style is itself an identifier. Authorship attribution operates
at internet scale [58], survives shortening and cross-platform domain shift [59],
and functions below 280 characters [60]. The third is that intermediate
representations invert: text embeddings reveal almost as much as the text itself
[61], and prompts can be recovered from model outputs alone [62].

The fourth is decisive because it addresses this architecture directly. In split
inference, the ActInv attack achieves precision and recall above 98% in nearly all
evaluated cases, with ROUGE-L consistently above 0.96. Cutting after two client
blocks of Qwen3-0.6B yields 99.76% precision, and even at seven blocks it retains
77.74%. Defences underperform: at 70% activation sparsification precision decreases
"only modestly" [63].

Swarmbly does not transmit activations, which places it in a better position than
split inference. But the direction of the evidence is unambiguous, and there is a
further argument internal to this design: **§6.2 establishes that coherence
requires shipping the global contract Γ to every worker.** A node holding Γ holds
the objective, audience, format and constraints of the session. Decontextualization
and coherence are antagonists by construction.

### 13.2 What can be claimed

> Swarmbly reduces the exposure surface relative to a centralized provider that
> reads and retains the complete prompt, and relative to pipeline-parallel schemes
> in which nodes observe intermediate activations and text under generation. It
> provides **no cryptographic guarantee of confidentiality**. An adversary
> controlling a significant fraction of nodes, or correlating by timing and session
> identifier, can reconstruct a substantial portion of a session.

Two residual channels are worth naming because they are cheap to overlook:
**timing correlation** (fragments of one session arrive in a burst) and **contract
fingerprinting** (a distinctive Γ is itself a session identifier across the nodes
that receive it). Mitigations — jittered dispatch, per-node contract paraphrase —
cost latency and coherence respectively, which is again §6.2.

**[v0.3] And this version adds a third channel, as a consequence of M2.** The
`unique_here` field (§9.3) tells a node which elements are unique across the whole
output. That is global information about the session which v1.4 did not send. The
trade is explicit: M2 buys cardinality correctness at the price of leaking the
document's uniqueness structure. On the `SANITISABLE` lane this is acceptable;
anything above it, `unique_here` must be omitted and cardinality verification must
fall entirely to the assembler — which is v1.4's behaviour and is worse, but is
the right behaviour there.

### 13.3 Verification

Strong cryptographic confidentiality is unaffordable here, and it is worth stating
the numbers so the conclusion is not mistaken for defeatism. General-purpose MPC on
a transformer runs at a slowdown of order 10⁴–10⁶×, with 280.99 GB of
communication for a single BERT-Base inference [64, 65]; the best two-party systems
report roughly 8 minutes per token for LLaMA-7B [66]. Zero-knowledge proofs of
inference need under 15 minutes to prove one forward pass of a 13B model [67].
None of this fits a volunteer economy.

What does fit is a layered scheme:

**Layer 1 — computational integrity by locality-sensitive commitment.** A
commitment scheme over activations detects unauthorized model, prompt or precision
substitution with 100% accuracy, zero false positives and zero false negatives in
reported testing, at 258 bytes per 32 tokens — roughly 1000× compression against
raw embeddings — validating faster than the original inference [68]. This is what
makes a node market possible: it costs almost nothing and it closes the obvious
fraud, which is a node advertising an 8B model and serving a 1B one.

**Layer 2 — sampled public audit.** Verification at approximately 1% of inference
cost, secure under a *one-honest-verifier* assumption rather than an honest
majority, with failure probability `P_fail ~ ρᵏ` [69]. The essential design
property: **workers cannot distinguish an audit task from a real one.**

**Layer 3 — selection as a defence.** With *k* > 1 replicas, the judge-based
selection of §10.4 already discards anomalous fragments as a side effect of
improving quality [39]. This is the cheapest defence in the system because it is
paid for by something else.

**[v0.3] Layer 0 — triage.** The gate of §10.7 is not a cryptographic defence and
is not presented as one, but it acts first and it is free: a fragment that does not
answer the task that requested it does not enter the assembly, whether it comes
from a slow node, a broken one or a dishonest one. Its value is containment, not
detection.

What none of these layers does is verify *semantic faithfulness*. Layer 1 proves
that a declared model was run on a declared input; it does not prove that the
resulting prose is true, or non-malicious. That gap matters because every returned
fragment is untrusted input flowing into the client's model — squarely the
territory of prompt injection, supply chain and improper output handling [70]. And
the client cannot be relied on to notice: off-the-shelf reasoning models attribute
failures in agentic systems at under 10% accuracy [71]. A system that cannot
attribute *honest* failures will not detect adversarial ones. The protocol's answer
is to constrain the blast radius — fragments are data, never instructions; the
assembler runs with output-handling defences; and `kind`-specific output schemas
are enforced before a fragment enters the assembly context.

### 13.4 Sensitivity lanes

| Lane | Criterion | Destination | Cost |
|---|---|---|---|
| **PUBLIC** | No PII, no commercial secret | Open volunteer nodes | None |
| **SANITISABLE** | Detectable, pseudonymizable PII | Open nodes; rehydrated locally | Real residual risk (below) |
| **SENSITIVE** | Health, legal, financial, identifiable | Local execution, or attested TEE | **<7% mean overhead** on H100 confidential computing [72]; independent measurements under Intel TDX report 8.9–21.8% [73] |

The TEE lane is what makes the protocol adoptable by an organization, and it is
affordable: single-digit percentage overhead is the only confidentiality primitive
in this space with that property.

The `SANITISABLE` lane must be described honestly. Against an undefended model on a
legal-text corpus, PII extraction reaches ~23% recall and ~30% precision, and PII
*inference* from 100 candidates reaches 70%, 50% and 28% on three corpora.
Differential privacy at ε=8 reduces extraction recall to about 3% — but not to zero
[74], and differentially private generation measurably degrades language quality
[75]. Sanitization reduces risk; it does not eliminate it, and the interface should
say so rather than bury it.

### 13.5 Dynamic privacy tiers and trusted swarms

The lanes of §13.4 classify *work*. They say nothing about the *population of
machines* that work is permitted to reach. A second axis is available and costs
almost nothing to add: the topology itself can be tiered, so that the routing
decision is a pair — which lane, and which mesh.

**Classification, and where it runs.** Every request passes a privacy classifier
before planning, in two modes. The first is a **manual hard flag** —
`--privacy=trusted`, `--privacy=local` — deterministic, declared by the user, and
never overridden by the automatic path. The second is **automatic triage**: a small
local model performs named-entity recognition over the prompt and raises the tier
when it detects entities of regulated classes.

The essential property is that this classifier runs **entirely on the client**. A
privacy classifier that consults the network to decide whether the prompt is
private has already disclosed the prompt. It is also deliberately recall-oriented:
it must over-classify, because the cost of routing a public prompt to a trusted
swarm is some throughput, while the cost of the converse is the failure the tier
exists to prevent.

**The three tiers.** **Tier 1, the global untrusted mesh,** is the default and is
the network this document has described: open volunteer nodes, PUBLIC and
SANITISABLE lanes, the full verification stack, and redundancy at the *k* derived
in §7.4.

**Tier 2, the trusted swarm,** is a permissioned sub-mesh. Membership is a
cryptographic whitelist of node public keys under an operator-controlled registry;
every link carries mutual TLS; the typical deployment is a corporate LAN, a campus
network or a VPN overlay. The protocol is unchanged — a trusted swarm is the same
protocol over a restricted population, not a second protocol — and that constraint
is deliberate. Round-trip times inside such a swarm collapse from tens or hundreds
of milliseconds to well under one, which means the bandwidth asymmetry of §1.2 is
locally suspended. It would be technically possible to run a finer-grained
partition inside the firewall. Swarmbly does not, because a deployment that behaves
one way inside the perimeter and another outside it is two systems to implement,
verify and reason about. What the low latency buys instead is headroom in the
context budget: **larger `L`, more generous `F`, higher ρ**, and therefore better
coherence at the same wall-clock — an improvement obtained by spending the same
design parameter rather than by introducing a new mechanism.

**Tier 3, pure local execution,** is selected by `--privacy=local` and means what
it says: no packet leaves the machine. It is the only tier in which Swarmbly makes
an unconditional confidentiality claim, and it can make it precisely because there
is no network to make it about.

**Redundancy in a trusted swarm.** Version 1.4 already observed here that *k* was
serving two purposes at once and that a whitelist removes one but not the other.
Section 12.4 generalises that observation to three purposes, and this section is
now its particular case. A trusted swarm **MAY** set `k_verif` = 1, because the
adversarial defence is already resolved at the identity layer. It **may not** set
`k_epist` = 1 without losing the divergence map, and when it does, the response
metadata records that no map was produced and the client surfaces that absence
explicitly rather than presenting an empty map as agreement. `k_avail` is bounded
by the coverage equation: with `c = 1` there is no margin against loss at all, so
the design requires `k_avail` ≥ 2 whenever the measured intra-swarm loss rate
exceeds the tolerance ε, LAN reliability notwithstanding.

**Why the tier matters beyond engineering.** Data-protection regimes are written
around identifiable, contractually bound processors: the processor relationships of
the GDPR, business-associate agreements under HIPAA, and their equivalents all
presuppose an entity that can be named, audited and held liable. An anonymous
volunteer cannot be a processor under any of them. A whitelisted, mutually
authenticated node inside an operator's own registry can. Tier 2 is therefore not a
performance feature; it is the construction under which this architecture becomes
lawful in settings where Tier 1 is not.

**And what it does not do.** A trusted swarm relocates trust rather than
eliminating it. Whoever controls the whitelist controls the swarm, which makes
registry governance a security-critical function; and a compromised member inside
the perimeter is *more* dangerous than an untrusted node outside it — precisely
because the redundancy that would have caught it may have been reduced. Mutual TLS
authenticates the channel and the identity; it says nothing about whether the model
behind that identity is the declared one. For that reason the locality-sensitive
commitment of §13.3 remains **REQUIRED** inside a trusted swarm even where audit
sampling and majority vote are relaxed.

### 13.6 Sybil resistance: a limitation, declared

Without a trusted identity authority, a single adversary can present arbitrarily
many distinct identities, defeating **any** scheme based on redundancy or majority
vote [76]. Reputation systems do not escape this: the canonical P2P algorithm
requires a set of *pre-trusted* peers to be Sybil-resistant, which reintroduces the
anchor it was meant to remove [77].

That this is not merely theoretical is visible in the flagship volunteer-computing
deployment, where 41.4% of hosts belonged to single-host users, 44.2% to users with
2–10 hosts, and the largest single user operated 2,987 hosts [47] — extreme
concentration, by a benign participant with no incentive to conceal it.

**Swarmbly is therefore not Sybil-resistant in the strong sense, and the protocol
says so.** It adopts layered trust: accumulated reputation, a cost to enter the
registry, sampled audit with economic penalty, and a set of anchor nodes operated
by the foundation for cold start.

---

## 14. Economics, governance and sustainability

### 14.1 Credits, not tokens

Earlier development proposed a 15% founder premine and a 0.5% protocol fee on each
micropayment. Both are withdrawn on regulatory and narrative grounds. The Swiss
framework classifies tokens as payment, utility or asset, with a two-condition test
to escape securities classification [78]; a premined, transferable instrument with
an expectation of appreciation is the archetype that triggers it. European
exemptions are narrow — €1,000,000 over twelve months, or 150 persons per member
state, with service-provider rules in force since 30 December 2024 [79].

The design that stays outside both regimes is deliberately unexciting: credits that
are non-transferable between accounts, earned by processing and spent by
requesting; no presale and no premine; immediate utility from day one; expiring
balances to discourage hoarding; and fiat conversion in one direction only —
enterprises buy capacity through the commercial arm, volunteers do not sell
credits.

### 14.2 Licence and governance

The protocol implementation is **AGPL-3.0-or-later**. Its clause 13 closes the
network-use gap that GPL leaves open [80]. Three qualifications: the obligation
attaches to the Program and its modifications rather than to a surrounding
proprietary stack; the licence covers software, not the protocol, so a clean-room
reimplementation is lawful; and its practical force is deterrence rather than
litigation.

The strongest empirical guidance comes from the recent relicensing wave: four of
four projects that hardened their licences produced a successful independent fork,
and two of the four subsequently reverted to AGPL [81, 82]. Starting at AGPL and
staying there is the position that history supports.

Two structural decisions follow. Dual licensing is rejected — it requires an entity
that can sell proprietary exceptions, which is incompatible with a foundation whose
mandate is openness; revenue comes from managed service instead. And **trademark,
not copyright, is the operative control lever**. Contribution is by DCO sign-off,
not CLA, because copyright assignment creates friction precisely with the community
this project needs.

On structure: a Swiss *Verein* can be constituted quickly and without minimum
capital, which is sufficient to hold rights and receive grants; a *Stiftung* is the
right instrument later. The claim that a foundation is "unacquirable and
unsilenceable" is overstated in any case — foundations are captured through boards,
donor dependence and control of repositories and marks. Independence is a practice,
not a legal form.

### 14.3 Sustainability, unclaimed

Data centres consumed 415 TWh in 2024, about 1.5% of world electricity, with
projections to 945 TWh by 2030 [83]. US hyperscale facilities draw from grids
measured at 545 gCO₂/kWh against a 370 g national average [84]. Those figures
support the *motivation*.

They do not support a claim of net benefit, and I do not make one. Energy per token
varies by nearly three orders of magnitude across configurations, and datacenter
accelerators achieve the lowest energy per token in the large majority of
scenarios; idle draw of 12–90 W is paid in full by a node that is available but
unused [85]. Global PUE is 1.54, but hyperscalers operate at 1.09–1.15 against a
home's effective ~1.0 — a margin of 9–15%, not an order of magnitude [86].

The commitment I make instead is procedural: adopt the Software Carbon Intensity
standard — `SCI = ((E × I) + M) / R`, ISO/IEC 21031:2024, which explicitly excludes
offsets [87] — instrument nodes and client, and **publish the result whatever it
shows**. The defensible motivating argument is the embodied-carbon one: extending
the service life of hardware that already exists avoids new manufacture.

**On induced demand.** Making a resource cheaper usually increases its total
consumption rather than displacing existing use — Jevons' paradox — and a reviewer
at a climate fund will raise it. The claim Swarmbly makes is not that this demand
disappears, but that **it is absorbed by hardware that has already been
manufactured**. Two conditions bound the argument and both are stated: it holds
only while **spare capacity exists**, and it holds only for the fraction of traffic
served by genuinely pre-existing volunteer hardware, which explicitly **excludes
the anchor nodes** of the bootstrap period.

### 14.4 Bootstrap: anchor nodes, declared

A network whose supply and demand must arrive simultaneously does not start on its
own. Swarmbly's bootstrap subsidises supply: the foundation operates rented
capacity so that service is fast and stable from the first day, and retires it as
community supply grows.

This creates an integrity exposure that the protocol handles by disclosure. During
that period a portion of the "volunteer swarm" is rented datacenter hardware, and
for that portion **the embodied-carbon argument does not apply and the
decentralization claim is only partially true**. The commitments are therefore
explicit: such nodes are named **anchor nodes operated by the Foundation** and are
labelled as such in the registry; the public dashboard reports, in real time, **the
share of traffic served by anchor nodes versus community nodes**; and the
Foundation publishes a target trajectory for that share and reports against it.

---

## 15. Evaluation

### 15.1 Task categories

Fit requires five simultaneous attributes: decomposable into genuinely independent
sub-tasks; latency-tolerant; token-intensive; weak inter-fragment dependencies;
verifiable or non-sensitive content.

| Category | Fit | Reasoning |
|---|---|---|
| Bulk document processing | **High** | Embarrassingly parallel, no dependencies, latency-tolerant |
| Synthetic data generation, labelling | **High** | Independent per sample; filter-verifiable; large volume |
| Code-migration sweeps | **High** | Independent per file; verifiable by compiling and running tests |
| Evaluation and judging at scale | **High** | Independent; aggregation is a vote |
| RAG over large corpora | **Moderate** | Map stage parallel; but fewer, larger units beat many small ones [52] |
| Long structured reports | **Moderate** | Decomposable by section — and precisely where SoT degrades [12] |
| Multi-hop mathematical reasoning | **Poor** | Result-dependencies [51] |
| Code with shared mutable state | **Poor** | The canonical failure through conflicting implicit decisions [33] |
| Interactive low-latency chat | **Very poor** | Lossless single-node methods already dominate [13, 14, 15] |

**[v0.3]** Under §6.8, this table admits a reading v1.4 did not have: the poor-fit
rows are the **high-δ** rows, and the high-fit rows are the low-δ ones. That is not
a coincidence of wording — it is what the `D(ρ, δ)` surface predicts, and it turns
the table into something checkable rather than a list of intuitions.

### 15.2 The abandonment criterion

> **Go/no-go.** There must exist a ρ at which coherence degradation is **below 5%
> relative to monolithic generation, in at least one task category.** If no such ρ
> exists, the architecture is not viable for generative assembly, and the project
> should either stop or restrict itself to workloads with no seam to break —
> classification, extraction, labelling.

**How the criterion is applied, and why the form matters.** "Below 5%" is a claim
about a quantity estimated from a finite corpus, so the criterion is discharged
against an **interval, not a point estimate**: the upper bound of a 95% bootstrap
interval, clustered by prompt, must fall below 5% in the named cell. That clause is
part of the original pre-registration and not a later addition — which is the only
reason it is worth anything, since a criterion tightened after the data arrive
proves nothing and one loosened after they arrive proves less.

**[v0.3] And this version adds a second baseline, from the Zhang et al. criticism
(§2.4):** additional compute must also be justified against **a single agent with
self-consistency**, not only against the naive monolithic baseline. A multi-agent
architecture that only beats single-pass monolithic generation is comparing itself
against the wrong rival.

**The criterion has moved from "unmeasured" to "judgeable", via a new instrument (SWIP-0001).** The aggregate tax is confounded with output length in **both directions** — with the full budget the fragmented arm wrote **1.39×** the monolithic and scored more; with the budget divided it writes **0.43×** and scores less — and truncating both arms to a fixed budget **T** does not help: the tax flips sign with T (from **−15.66 %** at T=40 to **+7.69 %** at T=120, T13). The two arms place the facts at different depths, so no reading budget decides. The instrument that resolves this by construction is the **position of first mention** (T13b): for each key, where it first appears, normalised by the arm's own length. On the matched-budget cells the fragmented arm surfaces the keys **0.279 of its own length earlier**, 95 % CI **[0.178, 0.361]**, with the length confound gone (ρ = **+0.075**). The criterion, restated as "fragmentation must not bury the keys", is **met** — the aggregate +11.17 % of T09R remains refused and is not cited as the criterion.

### 15.3 What was measured, and what was withdrawn

**The coherence tax: criterion NOT MET.** `table_summary`, ρ = 3.5, N = 2, k = 1,
on 16 held-out prompts:

| | |
|---|---|
| Coherence tax | **+2.30%** |
| 95% CI (clustered by prompt) | **[−2.05%, +7.49%]** |
| Criterion | upper bound below 5% |
| Verdict | **NOT MET** — 2.49 points short on the upper bound |
| Median prompt effect | **exactly 0.00%** |
| Prompts at or below zero | **11 of 16** (6 negative, 5 exactly zero) |
| Control, N = 8, k = 1 (required to fail) | +16.23%, CI [+11.33%, +20.28%] — behaved |

The point estimate clears the threshold and the interval does not. The criterion
was written against the upper bound for exactly this case, and it is not being
rewritten now that the case has arisen.

**The distribution is the more informative result, and the mean is the wrong
statistic for it.** The median prompt loses nothing, eleven of sixteen are at or
below zero, and the mean is not merely pulled by the positive prompts — it is
*manufactured* by two of them, which sum to **140%** of the total; remove them and
the mean over the remaining fourteen is **−1.06%**. The honest description is not
"fragmentation costs 2.3%" but **on 11 of 16 table-summarisation prompts, splitting
the work in two was free, and on two of them it was expensive**.

**Two withdrawals from v1.4 that still stand.** The tax curve falling in ρ is
withdrawn: the ρ axis never moved, because 13 of 96 cells sat above their packing
floor, and the coherence metric was not arm-neutral (+46.7% of apparent tax on text
that never changed). And the confidence map's reliability claim is withdrawn:
*r* = −0.030 over 597 units against a saturated judge, and then common odds ratios
of 3.47, 0.26 and 1.24 against an answer key. §10.5.4 explains why M1 does not lift
that withdrawal.

### 15.4 The L curve: the instrument works, the corpus does not

An experiment was built and run to measure the quality curve against `L` — the
parameter Section 5 makes central. **It could not answer the question, and the
reason is informative.**

The corpus was generated with 72 documents derived from the product of
`L ∈ {5,10,20,40}` and `N ∈ {2,4,8}`, with 12 documents per size. The monolithic
arm answers **1 of 72** global questions, even on the smallest material. That is
not a result about fragmentation: it is a floor. With the baseline on the floor
there is no difference to measure.

**Verifying the instrument is what saved the run.** Before concluding anything, the
grading was checked: a hand-built perfect answer scores 100% on all 72 documents.
The grader is not the problem. Five model families were then probed on the same
material: **4 of 5 do the local lookups at ~0.84**, and global questions come out
at **4 of 60** across all of them. A hypothesis that the contract wrapper was
strangling the global answer was tested with an A/B and **was refuted by its own
measurement**: 4/60 both ways, delta 0.000.

**Conclusion, and it is about corpus design rather than architecture:** the corpus
needs a *global* question this model pool can answer on small material. Until there
is one, the L curve is not measurable, and the final half of the corpus — still
unused — **must not be run**, because spending the held-out split against an
instrument that does not discriminate destroys the only reserve left.

**§15.4 update (corpus rebuilt, admitted, curve measured).** The corpus was
rebuilt with k-ary global questions (arity ≤ 3) — `prompts/lcurve_v2.json`,
generated by `make_corpus.py` — and passed its admission gate: the monolithic
arm clears the 0.50 floor with llama3.2:3b at **61.1 %** (chance baseline
**0.182**; the other four families do not clear it). On the dev half, the
fragmented arm was run over every declared cell (N, L) with llama3.2, and the
L curve is now measurable. It is **monotone decreasing** — L=5: **77.8 %**,
L=10: **69.4 %**, L=20: **58.3 %**, L=40: **44.4 %** (36 global questions per
L). The mechanism is per-fragment extraction fidelity: a weak node reports
five rows verbatim but drops rows when asked to report forty. Two consequences:
the §5 prediction that quality rises with L toward a floor is **falsified in
this regime** (the opposite holds), and the fragmented arm at small L
**beats the monolithic baseline** (77.8 % vs 61.1 %) — the first clean,
length-confound-free win on the solvability axis.

### 15.5 Composition: the sample size required

The declared cell of the composition experiment gave a mean of **−0.35**, with a
between-cluster standard deviation of **20.36** and a standard error of **4.16**,
for a CI of **[−8.49, +7.80]** against a threshold of 5.0. The interval contains
both the threshold and zero: it decides nothing.

The sample-size calculation, cross-checked against the measured standard error,
says **60 prompts minimum and 72 with margin**. And there is a useful negative
result along the way: **repeats buy nothing**, because the pipeline is
deterministic at temperature 0. More runs of the same prompt do not reduce the
between-prompt variance, which is what dominates.

Two composition measurements are conclusive and do support decisions in this
version. Mechanical enforcement of `term_once` at the assembler raised compliance
from **6/24 to 18/24**, above the monolithic arm's 13/24 — it is the evidence that
resolving a constraint in the system rather than in the prompt works, and it is the
baseline M2 must beat (§11.3). And `no_repeated_ngram` stayed at **4/12 against
11/12** for the monolithic arm under every context-allocation policy tested — it is
the irreducible class, and §6.4 explains why no allocation can reach it.

### 15.6 What each model predicts, and how to kill it

The five models of this version are falsifiable. Stating it here is what separates
a major version from a manifesto, and it is the condition under which this document
can be published.

**M1 — Alignment with learned semantic substitution (§10.5).**
*Predicts:* a map built by alignment with learned cost separates correct from
incorrect better than one built by match counting, and better than a scalar per
answer, **in a non-saturated regime**.
*Killed if:* with the correct instrument and in a regime where the models genuinely
disagree, per-unit agreement does not beat chance. Then localisation creates no
signal and the map loses its reliability claim, though it retains its ability to
report divergence.

**M2 — Cardinality resolved in the representation (§11.3).**
*Predicts:* assigning uniqueness in the plan makes `no_repeated_ngram` and
`term_once` inviolable by construction, not merely detectable. The violation rate
should fall to zero, not improve.
*Killed if:* assignment in the plan does not reduce violations below 18/24, which
is what mechanical enforcement already achieves.

**M3 — Per-level triage gate (§10.7).**
*Predicts:* the blast radius of a defective fragment stays contained in that
fragment. An incident of the "42 of 60 packets contaminated" type becomes
impossible.
*Killed if:* the gate rejects so much legitimate work that the retry cost exceeds
the damage it prevents.

**M4 — ρ as indirect rate-distortion with a second axis δ (§6.7–6.8).**
*Predicts:* at constant ρ, varying the dependency density of the cut moves the
distortion. And there exists a region where no ρ reaches an acceptable distortion.
*Killed if:* distortion turns out to be a function of ρ alone, with δ having no
measurable effect. Then the second axis is decoration and the framing adds nothing
over the empirical derivation of §6.5.

**M5 — Threshold over-dispatch, and `k` split into three (§12.3–12.4).**
*Predicts:* separating availability, verification and epistemic redundancy allows
the total cost to be lowered while keeping all three guarantees, because today a
single parameter pays for all three at the price of the most expensive.
*Killed if:* the three turn out to be so coupled in practice that separating them
saves nothing.

**Status after the reference campaign (§15.9).**

| Model | Verdict | On what |
|---|---|---|
| **M1** | **no instrument** | the semantic aligner is built and verified on the bench (T10), but the real corpus did not produce the non-saturated regime M1 needs (T10R, blocked) |
| **M2** | **survives, corrected** | 23/35 by node obedience; 35/35 with mechanical enforcement. The phrase "zero by construction" is withdrawn (§11.3) |
| **M3** | **survives** | contaminated packets do not pass the gate; the 42/60 incident does not reproduce (T02R) |
| **M4** | **falsified** | in two independent instruments and with a controlled experiment at constant ρ (T04R, T07R) |
| **M5** | **unmeasured** | it remains a conceptual separation; nothing in this campaign touches it |

**The order in which to attack them**, by increasing cost and by what each one
unlocks:

1. **M5** needs no measurement: it is a conceptual separation of a parameter that
   already exists. Implement and observe.
2. **M3** is cheap and its prediction is binary: the incident happens or it does
   not.
3. **M2** is measured over the composition corpus that already exists, against a
   baseline already measured (18/24).
4. **M4** needs the difficulty-calibrated corpus on which the entire current
   experimental agenda depends — the same one §15.4 says is missing.
5. **M1** needs the aligner to be built, and is the most expensive. It is also the
   one that produces the most distinctive property.

### 15.7 A note on the instrument, which is the methodological finding

This project has a recurring defect, and naming it is worth more than any of the
individual measurements:

> **A check that claims more than it measured.**

An aggregate is reported without asking where it comes from. It appeared four times
in a single working day, and **each time inside code written to catch the previous
occurrence**. The cases: a verdict reading a key the bootstrap function did not
return, which would therefore have said "not met" on any data at all; a probe that
silently degraded to one model family and concluded about five; a difficulty
diagnosis derived from a single model and presented as a property of the corpus;
and a threshold that fired on the effect of a single cell.

The defence that worked was not more care. It was **making the check refuse**:
deriving the family list from the runner itself and refusing below two; withdrawing
a pooled conclusion if removing the largest contributor undoes it; cross-checking
the sample-size plan against the measured standard error and refusing if they
differ by more than 25%. An instrument that can refuse is worth more than one that
is right more often.

Four thresholds in this document exist for that reason and are declared: a minimum
of **20 clusters before a verdict is issued**; a **baseline floor of 0.20** — added
*after* seeing the data and labelled as such in the pre-registration, because a
declared amendment counts and a silent one does not; and the two control tolerances
of the previous paragraph.


### 15.9 The reference campaign: 473 runs over five families

Everything earlier in §15 was measured with the project's harness over the
project's corpus. This section reports something different: a **reference
implementation built separately** (`swarmbly_ref/`), run against **five local
model families** — `llama3.2:3b`, `qwen2.5:3b`, `gemma2:2b`, `phi3.5:3.8b`,
`granite3.1-dense:2b` — over a corpus of 22 tasks, and a **falsification
harness** (`swarmbly_validation/`) that judges the five models against the
resulting record. The record is a JSONL of **473 runs** with an anchored digest;
all three artifacts are published with this document, and every figure below is
recomputed by running them.

**What has to be said first is what died.**

| Test | Verdict | What it measures |
|---|---|---|
| T0R | ✔ | the router decides decomposable/not against corpus truth: **22/22** |
| T02R | ✔ | M3: contaminated packets do not pass the gate |
| T03R | ✔ | M2: **23/35** by node obedience, **35/35** after mechanical enforcement |
| T04R | ✘ | M4: Spearman(δ, tax) = **−0.15** over **127** intra-category cells |
| T05R | ✔ | the ρ accounting predicts packet size to within **7.5 %** |
| T06R | ✔ | the grader scores the perfect answer **21/21**; **100** of **105** monolithic runs clear the floor |
| T07R | ✘ | M4, controlled experiment: δ rises in **32/32** pairs and the tax worsens in only **15/32** |
| T08R | ✘ | L curve: the predicted band (factor 3–6×) does not appear |
| T09R | ◌ | abandonment criterion: **refused**, confounded with output length |
| T10R | ▣ | M1: no non-saturated regime in this corpus |
| T0RR / T0RR2 | ✘ | per-cell routability: **AUC 0.57** and **0.57** |
| T0LR | ✔ | `L*` varies by family — §5.7 measured for the first time |
| T13 | ◌ | the truncated tax flips sign with the reading budget T — the length coupling is structural, and the truncation instrument is refused |
| T13b | ✔ | the position tax resolves it: fragmented surfaces the keys **−0.279** of its own length earlier, 95 % CI **[−0.361, −0.178]**, confound ρ = **+0.075** — the criterion is judgeable again and is met |

**M4 is falsified, and the experiment that kills it is the one the strategy
declared decisive.** T07R cuts the **same prompt** twice at the **same `L`**:
once at weak-coupling interfaces (P9) and once maximising the coupling that
crosses the cut. δ rises in all 32 pairs and ρ stays equal to within 5 %, so the
only axis that moved is δ. M4 predicts that the strong cut worsens distortion in
**every** pair; it worsens in **19 of 32**, which is indistinguishable from a
coin. The observational measurement converges: Spearman(δ, tax) = −0.15 over 127
intra-category cells, with the sign opposite to the prediction. **The second
axis is not conceptual decoration: it is a prediction that was checked and did
not hold.**

**The per-cell router is refuted, and this changes the design, not only the
scoreboard.** A classifier with leave-one-task-out validation over 80
operational cells reaches AUC 0.57 with δ and reputation and
0.61 with neither. Adding pre-dispatch capability probes brings it to 0.57. What
does separate is the **node class**: mean tax per family ranges from +8.4 % to
+26.5 %, and a policy that routes by class obtains +0.0 % against +14.8 % for
always fragmenting. The consequence is written into §10.1: the router decides
*whether* to fragment, the node profile decides *who*, and nobody predicts the
cost of a particular cell.

**M2 survives with a correction worth more than the confirmation.** Real nodes
do not obey `unique_here`: 6 of 35 terms appear exactly once, with 29
repetitions. But **0 omissions** — and the assembler's mechanical enforcement
takes the result to 35/35. The failure mode that assignment in the plan removes
is the irreparable one; the reparable one is still removed by the assembler.
§11.3 rewrites M2 in those terms and withdraws "zero by construction".

**The abandonment criterion has neither been met nor failed: it has not been
measured.** The aggregate gives +11.17 % with a 95 % CI of [+4.80, +17.34] over
130 cells, which would appear to settle the criterion in favour. It cannot be
claimed, because the fragmented arm received more output budget than the
monolithic one: each fragment inherited the full `max_tokens` of the whole
prompt, so a plan of `N` fragments had `N` times the output available. Three
independent statistics confirm this suffices to explain the advantage: the
statistic with no denominator gives **+0.595**, the artifact floor — the same
calculation with the tax permuted — gives only **+0.125**, and the direct test
within each task gives a median of **+0.571**, positive in 10 of 18 tasks.

Stratifying by length, the aggregate comes apart where it should:

| Stratum | n | tax | 95 % CI | meets the criterion? |
|---|---|---|---|---|
| all cells | 123 | −32.5 % | [−54.7, −12.0] | yes |
| comparable length (0.8–1.25×) | 31 | −21.3 % | [−42.0, −1.0] | yes |
| **the fragmented arm does NOT write more (≤ 1.0×)** | **41** | **−6.3 %** | **[−22.3, +14.1]** | **no** |
| the fragmented arm writes more (> 1.25×) | 67 | −54.4 % | [−77.1, −24.6] | yes |

The row that matters is the third: when the fragmented arm does **not** write
more, the advantage falls to −6.3 % and the interval crosses zero. This is a
post-hoc stratification and not an experiment, so it settles nothing on its own
— but it is exactly the pattern the confound predicts, and that is why the
verdict is **refuse** rather than "met with caveats".

The cause was located in the code, not conjectured: `benchmark.py` gave each
fragment the whole task's `max_out_tokens`. The correction is applied and
exposed as a single command — `run_benchmark.py --matched` — which divides that
budget among the fragments and records the cells under a suffix of their own so
that the two measurements coexist. The fields `output_words` and `length_ratio`
are now first-class fields of the record, so that a future analysis cannot
repeat the error silently.

**What this campaign does not touch.** T07R, T04R, T05R, T06R, T02R, T0R, T0LR
and T10R compare arms at equivalent budget or do not depend on the aggregate
tax, so the confound does not reach them. The verdicts on M2, M3 and M4 stand
whole.

**And a fifth appearance of the §15.7 defect, this time in the analysis of this
very section.** Exploring the data, an attractive interaction appeared: weak
nodes seemed to gain from fragmentation and strong ones to lose. Before
confirming it, a pre-registration was written declaring the suspected defect —
`tax = 1 − frag/mono` carries `mono` in the denominator, so correlating it with
the same cell's `mono` produces association *by construction* — and the design
that breaks it: estimating node strength from that model's results on the
**other** tasks. With the independent predictor, ρ = **−0.078** (p = 0.192); and
a simulation where the two scores are drawn independently returns **+0.684**,
against the **+0.675** observed with the coupled statistic. The formula
manufactures the whole association. **The finding was withdrawn**, and the test
that killed it is published with the harness (T12) so that the withdrawal is
reproducible rather than a footnote.

### 15.8 Metrics

| Metric | Definition | Target | Status |
|---|---|---|---|
| Coherence tax | Δ seam-free sentence fraction vs monolithic | upper bound of the 95% CI below 5% | **NOT MET** on the table corpus (§15.3); **REFUSED** in the reference campaign owing to the length confound (§15.9) |
| Operating ρ | Input tokens per prompt token | **distance to `(L+2F)/L`** | Re-derived in §6.5; v1.4's absolute "<2.0" target is **withdrawn** as neither attainable nor meaningful |
| Quality curve in `L` | Quality vs fragment size | existence of `L_min` and of a band | **measured per family**: `L*` varies across families, but the predicted wide band does not appear (§15.9, L20) |
| Effect of δ at constant ρ | Distortion vs dependency density | measurable effect | **measured and null**: δ rises in 32/32 pairs at equal ρ and the tax worsens in 15/32 (§15.9) |
| Cardinality violations | over-compression and over-expansion, separately | over-compression zero by construction; over-expansion zero after enforcement | **over-compression 0/35; over-expansion 29/35 raw and 0/35 after enforcement** (§15.9) |
| Triage containment | blast radius of a defective fragment | one fragment | **contained**: all 3 contaminated packets are rejected (§15.9) |
| Effective speedup | vs monolithic, same model | >1.5× | not measured |
| Speedup vs honest baseline | vs speculative decoding **and vs self-consistency** | reported even when <1 | not measured |
| p95 latency under churn | *p*=0.10, *N*=8 | <2× failure-free | not measured |
| Dishonest-node detection | injected adversaries caught | >95% | not measured |
| Verification overhead | extra cost per fragment | <5% | not measured |
| SCI | gCO₂e per functional unit | published and compared | not measured |

---

## 16. Limitations and negative results

Stated plainly and at length. A specification whose failure modes are documented
can be improved by people who did not write it; one that hides them can only be
discovered to be wrong.

**L1 — Quality loss from independent generation is theoretical, not incidental.**
Parallel generation assumes conditional independence, and quality degrades in
proportion to the strength of the real dependencies [20]. At equal compute budget,
decomposition is a lossy channel [21]. This cannot be prompt-engineered away; it
can only be routed around, which is why §10.1 exists. **[v0.3]** And §6.8 gives it
a name and an axis: it is δ.

**L2 — Coherence is the axis that breaks, and aggregate scores hide it.** SoT
improves relevance and diversity while degrading coherence and immersion [12].
Hierarchically merged text exhibits eight recurring coherence error classes [54].

**L3 — The assembler operates in a regime known to be unreliable.** Model
reliability degrades with input length across all models tested; one distractor
hurts and four compound; and models perform *better* on shuffled contexts than on
logically coherent ones [88]. Positional bias adds a U-shaped curve in which middle
fragments are systematically underweighted [89].

**L4 — The context limit is relocated, not eliminated.** It moves to the client,
which is the weakest node in the system.

**L5 — An 8B orchestrator may be inadequate.** This is H3, and a negative result
would require a larger client-side requirement, which narrows the addressable user
base.

**L6 — No strong Sybil resistance.** See §13.6.

**L7 — Fragmentation is not encryption.** See §13.1.

**L8 — Environmental benefit is unproven.** See §14.3.

**L9 — The genomic analogy is vocabulary plus instruments, not an inheritance.**
**[v0.3]** This limitation changes shape from v1.4. It is no longer "it is only a
naming convention": §3 gives a criterion, and five homologies pass it bringing
concrete inequalities and numbers. But it remains true that **no genome-assembly
algorithm runs inside Swarmbly**, and a reviewer from bioinformatics should read
§5, §6.4 and §11 as transfers of *instrument*, not of implementation.

**L10 — The dominant risk is not technical.** Volunteer computing has been in
decline for two decades: early projects attracted on the order of a million
volunteers, and the user base has since shrunk to roughly two hundred thousand
[47]. Swarmbly must explain what makes its incentive loop different, and "network
credits" is not by itself an answer. This is, in my assessment, more likely to end
the project than any algorithmic limitation.

**L11 — Multi-agent systems fail in characterized ways.** The MAST taxonomy
attributes 47.9% of failures to system design, 32.2% to inter-agent misalignment
and 20.0% to task verification, with step repetition (15.7%) and specification
disobedience (11.8%) the most common individual modes [90]. Swarmbly is a
multi-agent system and should expect this distribution. **[v0.3]** §2.4 maps the
three categories against the three areas this version addresses; that coincidence
is a convergence, not an immunity.

**L12 — A trusted swarm relocates trust; it does not remove it.** See §13.5.

**L13 — The confidence map's reliability claim remains withdrawn.** Measured
against a peer-class judge, per-unit agreement did not predict judged acceptability
(*r* = −0.030 over 597 units), and *k* > 1 cost 17 to 20 points of coherence on the
same run. The ground-truth experiment was run three times and returned odds ratios
of 3.47, 0.26 and 1.24. The mechanism stays disclosed and specified, and reporting
*where* replicas diverged is still a real capability; asserting that convergence
indicates correctness is not. **[v0.3]** M1 proposes a different instrument with its
own death condition (§15.6); proposing it does not lift this withdrawal, and nothing
in this version should be read as if it did.

**L14 — The second coherence instrument does not function on short answers.** The
entity grid returned monolithic baselines between 0.000 and 0.114. This document
has one working coherence instrument, not two.

**[v0.3] L15 — The L curve is not measurable with the current corpus.** The
monolithic arm answers 1 of 72 global questions. The grader is verified and the five
families do local lookups at ~0.84, so the defect is in corpus design rather than in
the instrument or the models — but the practical effect is that `L`, the parameter
Section 5 makes central, **has no measured curve yet**. The held-out split must not
be spent until an answerable global question exists (§15.4).

**[v0.3] L16 — `L_min` and the optimal band are predicted, not measured.** §5.6
predicts a hard floor and a wide band by analogy with protein domain size, where
Pfam and SCOP differ by almost a factor of two over the same material. It is a
well-founded prediction, and it is a prediction. Any `L` this project uses today is
an informed guess.

**[v0.3] L17 — M2 leaks structure.** The `unique_here` field hands a node global
information about the session that v1.4 did not hand it (§13.2). Cardinality
correctness and decontextualization are antagonists, just as coherence and
decontextualization are, and for the same reason.

**[v0.3] L18 — Over-dispatch applies only to interchangeable sub-tasks.** The saving
in §12.3 is real and it is narrow. If the content of fragment *j* is needed, no
threshold scheme substitutes for it, and believing otherwise is exactly the error
that sank the fountain-code hypothesis.

**[v0.3] L19 — The rate-distortion bound exists and is not computable.** §6.7
inherits the existence of a floor and the qualitative monotonicity of the curve. It
does not inherit a number. A reader who takes from §6 the impression that a
calculable optimal ρ exists has taken more than the document says.

**L20 — The wide band in `L` is predicted and does not appear.** §5.6 predicts a
sharp `L_min` floor and a wide optimal band, by analogy with protein domain size.
With curves of more than one point per task, `longform` gives a band of factor
**2.7** and `table_outturn` one of factor **1.0** — that is, a single optimal
`L`. The analogy was right that `L` is a property of the node class (T0LR
measures a different `L*` per family) and wrong about the width of the band. The
mean gain from using each family's `L*` instead of a common `L` is **+0.360** of
quality: real, measurable and small.

**L21 — The measured tax depends on the output budget, and until it is matched
there is no feasibility verdict.** This is the most important limitation of this
version. All of the §15.9 material on M2, M3 and M4 stands; the claim
"fragmenting pays" **has not been measured**. The correction is implemented and
the pending run costs minutes of compute (§15.9).

**L22 — The recurring defect of §15.7 appeared a fifth time, inside the analysis
that documents it.** The defence that worked was not more care: it was
pre-registering the suspected defect and the design that breaks it **before**
running the analysis. With the coupled statistic and a threshold chosen by eye,
the false finding would have come out confirmed with large numbers. A reader
should assume this document contains a sixth appearance not yet detected, and
the published harness exists so that it is the reader who finds it.


---

## 17. Prior-art declaration

> **Status note.** Elements E1–E18 were publicly disclosed in version 1.4 of
> this document, dated 14 August 2026, and have constituted prior art since then.
> **Elements E19–E24 are new in this version and constitute prior art from the
> publication of this document**, not before. The period in which they were kept
> unpublished was a deliberate decision not to claim before measuring, and its
> cost was exactly the priority it did not protect in the meantime.

The elements are disclosed with the intent that they enter the public domain for
patenting purposes; the author reserves copyright in the text under CC BY 4.0 and
licenses the implementation under AGPL-3.0-or-later.

**E1.** A method for distributed language-model inference in which the unit of
distribution is a **semantic sub-task derived from the request**, dispatched once
per fragment per session to nodes each executing a complete independent model.
(§1.2, §8.2)

**E2.** A **context budget** *S* as an explicit protocol parameter jointly
governing assembly coherence, fragment verifiability, privacy leakage and required
worker capability, with the redundancy ratio ρ as the reported cost measure. (§6)

**E3.** A **global contract** Γ transmitted with every fragment as the mechanism
for cross-fragment consistency, with the entity table serving as a shared naming
coordinate system. (§9.2)

**E4.** A **router with asymmetric decision cost** that may decline to fragment,
calibrated with F_β where β<1. (§10.1)

**E5.** A **dependency-DAG planner** distinguishing tasks requiring a
predecessor's *result* from tasks requiring only its *statement*. (§10.2)

**E6.** A **packing procedure** in which the global contract is never elided to
meet a context budget. (§10.3)

**E7.** A **select-then-splice assembler** in which multiple candidate fragments
are resolved by selection rather than synthesis, with generative bridging invoked
only at a seam whose boundary similarity falls below a calibrated threshold.
(§10.4)

**E8.** **Empirical calibration of the seam threshold** from labelled pairs under
an asymmetric objective, re-derived per embedding model. (§10.6)

**E9.** A **coherence audit** returned as part of the protocol response. (§10.8)

**E10.** **Sensitivity-lane routing** — PUBLIC / SANITISABLE / SENSITIVE — as the
confidentiality mechanism. (§13.4)

**E11.** A **two-layer verification scheme** combining a locality-sensitive
commitment over activations bound to a declared node profile, with sampled public
audit indistinguishable from real work. (§13.3)

**E12.** **Diversity-preserving redundant dispatch**: replicas of a critical
fragment are assigned to nodes of deliberately *different* model families. (§7.3c,
§9.6)

**E13.** **Hedged dispatch at a per-class p95 latency trigger** with cancellation
accounting that distinguishes slow nodes from dishonest ones. (§8.4, §9.6)

**E14.** A **non-transferable, non-premined, expiring credit** earned by verified
fragment processing. (§14.1)

**E15.** The **coverage/conversion decomposition** `Q ≈ V · Πᵢ Cᵢ` as a design
instrument for swarm inference. (§7.2, §7.3)

**E16.** **Consensus by multiple alignment of independently generated replicas**,
with a per-unit agreement score and units below threshold surfaced as low-confidence
regions. Disclosed as a **mechanism**: its correlation with correctness was measured
and did not survive, so no reliability benefit is claimed for it. (§10.5, §15.3)

**E17.** A **coverage model for semantic assembly** in which the pre-generation
plan and contract serve as the reference sequence, packet loss rather than sample
placement is the stochastic element, and the redundancy requirement is derived as
`c ≥ ln(1/ε)/(1−p)`. (§7.4)

**E18.** **Dynamic privacy tiering with trusted swarms**: a client-side privacy
classifier that never leaves the machine, driving a routing decision on an axis
orthogonal to content sensitivity. (§13.5)

---

**New elements in this version — not yet publicly disclosed.**

**E19.** A **homology-admissibility criterion** for transferring mechanisms between
scientific domains, consisting of two joint tests: that the homology supplies an
applicable procedure, inequality or number (the instrument test), and that it
supplies the statement of the pathology that occurs when its condition is violated
(the failure-mode test); with explicit rejection of transfers that pass only the
first. (§3)

**E20.** A **weak-interface fragmentation rule**, in which the fragment boundary is
chosen by minimising the dependencies that cross it rather than by dividing into
parts of uniform size; with the size `L` as a declared property of the node class,
the fragment count derived as `N = ⌈material/L⌉`, and the flank `F` defined as the
maximum of the longest detectable repeatable unit and the longest dependency
crossing a boundary — from which the context budget is derived as
`ρ ≈ (L+2F)/L + H/(L·s)`. (§5.4, §5.7, §6.5)

**E21.** A **divergence map built by multiple alignment of answers with a
semantic substitution matrix learned empirically** from sentence pairs verified as
interchangeable, with consistency extension via corroboration through third
independent answers, and emission of a position-specific profile — replacing
embedding-similarity comparison against a threshold. (§10.5)

**E22.** A **method for satisfying global cardinality constraints in the plan**:
compute before dispatch the set of elements that must appear exactly once in the
final output, assign each element to exactly one fragment as a property of the
plan, verify cardinality against that set at assembly, and log over-compression and
over-expansion separately. (§11.3)

**E23.** A **per-topological-level triage gate** in which a carry must pass a
mechanical predicate before enabling the next level, a fragment that does not pass
is isolated and retried rather than patched in context, one that does not pass after
`r` retries is discarded and regenerated, and consumption may begin before the level
is complete if the fragment being consumed is complete and verified. (§10.7)

**E24.** The **separation of the redundancy parameter into three single-purpose
parameters** — availability, verification and epistemic redundancy — with a distinct
mechanism assigned to each (threshold over-dispatch with early termination;
credibility-based spot-checking; diverse-family replicas for the divergence map),
and with the normative condition that over-dispatch is admissible only among
genuinely interchangeable sub-tasks. (§12.3, §12.4)

---

## 18. Conclusion

The knowledge required to build language models is public. The capital required to
operate them is not, and that asymmetry — not any secret — is what concentrates
control over a general-purpose technology. Meanwhile the hardware capable of
serving inference sits idle in hundreds of millions of homes and offices, already
manufactured, already drawing power.

The obstacle between those two facts is physical and specific: four to five orders
of magnitude between datacenter interconnect and consumer links, which every
existing peer-to-peer inference design crosses on every generated token. This
work's structural claim is that crossing it **once per unit of work instead of once
per token** is a different regime rather than an optimization of the same one.

**What this version adds to that claim is a theory of the unit of work.** Version
1.4 knew that fragmentation was necessary and did not know into what. This version
derives it: the fragment is a task domain, it is cut where the coupling is weak, its
size is a measured property of the node class, its overlap is the maximum of two
observable quantities, and the context budget follows from those rather than being
swept. The measured saving from that single derivation is 29% of network compute,
and it relaxes no guarantee because the theory says exactly what to measure.

Five falsifiable models accompany that theory, and all five come with their death
condition written before the measurement. Two hypotheses entered the review and did
not survive — *mate pairs* and *fountain codes* — and the diagnosis of why they fell
turned out to be more useful than the homologies would have been: **a transfer that
brings a mechanism without its pathology is importing the conclusion without the
work.** That is this version's methodological finding, and it is what Section 3
turns into a criterion.

The case against is equally specific and is in Section 16. Independent generation
loses quality for theoretical rather than incidental reasons. The client-side model
on which the design depends sits at the weak end of measured planning ability.
Volunteer computing has been contracting for twenty years. And the measurements
made so far have gone against the design: the coherence criterion was not met, the
ρ-tax curve is withdrawn, the confidence map's reliability claim is withdrawn, and
the `L` curve — the axis this version makes central — is still not measurable with
the corpus that exists.

What survives is specific and is enough to continue: a measured and **bimodal**
cost — eleven of sixteen prompts fragment for free, two are expensive — a control
that failed as it was required to, a verified grading instrument, and a set of
models that say in advance what would kill them. What remains to settle is what
separates the eleven prompts from the two, and whether a context budget exists that
satisfies coherence, privacy, verifiability and worker capability at once, at a cost
below the value of the aggregated capacity.

This document is not published yet, and the reason is consistent with all of the
above: **the models it proposes are falsifiable and have not been falsified.**
Publishing them before submitting them would be claiming credit for the easy part.
Section 15.6 says in what order to attack them and what each costs; the first costs
nothing and the last produces the most distinctive property. Once that agenda has
been run — whatever its outcome — this document is published, and then it is prior
art.

If it works, the result is not a cheaper way to buy what is already sold. It is
inference capacity that grows with the number of people who participate rather than
with the amount of capital available to build, held under a licence and a governance
structure designed so that no single party can enclose it. That is worth attempting
even at a substantial probability of failure, and it is worth attempting in the
open, where it can be checked.

---

## 19. References

> **Numbering.** Markers `[1]`–`[90]` preserve version 1.4's numbering, so that a
> citation from that document still points at the same source. Markers `[92]`–`[135]`
> are new in this version and correspond to the bibliographic review of the
> fragmentation fundamentals; all of them were verified against the online source
> indicated, and where only the abstract could be confirmed this is noted. Entries
> marked ⚠ carry forward an unconfirmed identifier from v1.4 and **must be completed
> before any publication**; they are left visibly incomplete rather than filled in
> from memory.

### Decentralized inference and training

[1] Borzunov, A., et al. (2023). Petals: Collaborative inference and fine-tuning of large models. *ACL 2023: System Demonstrations*. https://arxiv.org/abs/2209.01188
[2] Borzunov, A., et al. (2023). Distributed inference and fine-tuning of large language models over the internet. *arXiv*. https://arxiv.org/abs/2312.08361
[3] Petals project. (2023). *Petals project repository, release v2.2.0* [software].
[4] Ryabinin, M., & Gusev, A. (2020). Towards crowdsourced training of large neural networks using decentralized mixture-of-experts. *NeurIPS, 33*, 3659–3672.
[5] Ryabinin, M., Dettmers, T., Diskin, M., & Borzunov, A. (2023). SWARM parallelism. *ICML*, 29633–29654.
[6] Bittensor. (n.d.). *Incentivizing intelligence*. https://bittensor.com/academia
[7] *Stake-concentration analysis of Bittensor subnets*. (n.d.). ⚠ unverified.
[8] Douillard, A., et al. (2023). DiLoCo. *arXiv*. https://arxiv.org/abs/2311.08105
[9] Jaghouar, S., et al. (2024). OpenDiLoCo. *arXiv*. https://arxiv.org/abs/2407.07852
[10] Jaghouar, S., et al. (2024). *INTELLECT-1 technical report*. https://arxiv.org/abs/2412.01152
[11] *Protocol/Subspace Networks*. (n.d.). ⚠ unverified.

### Parallel decoding and decomposition

[12] Ning, X., Lin, Z., Zhou, Z., Wang, Z., Yang, H., & Wang, Y. (2024). Skeleton-of-thought. *ICLR*. https://arxiv.org/abs/2307.15337
[13] Leviathan, Y., Kalman, M., & Matias, Y. (2023). Fast inference from transformers via speculative decoding. *ICML*. https://arxiv.org/abs/2211.17192
[14] Cai, T., et al. (2024). Medusa. *arXiv*. https://arxiv.org/abs/2401.10774
[15] Fu, Y., et al. (2024). Break the sequential dependency of LLM inference using lookahead decoding. *ICML*. https://arxiv.org/abs/2402.02057
[16] Liu, M., et al. (2024). APAR. *arXiv*. https://arxiv.org/abs/2401.06761
[17] Jin, T., et al. (2025). Learning to keep a promise (PASTA). *ICML*. https://arxiv.org/abs/2502.11517
[18] Jin, S., Wu, Y., Zheng, H., Zhang, Q., & Lentz, M. (2024). Adaptive skeleton graph decoding. *arXiv*. https://arxiv.org/abs/2402.12280
[19] Rodionov, G., et al. (2025). Hogwild! Inference. *NeurIPS*. https://arxiv.org/abs/2504.06261
[20] Kang, W., Galim, K., Oh, S., et al. (2026). ParallelBench. *ICLR*. https://arxiv.org/abs/2510.04767
[21] Tran, H., & Kiela, D. (2026). Single-agent LLMs outperform multi-agent systems on multi-hop reasoning under equal thinking token budgets. *arXiv*. https://arxiv.org/abs/2604.02460
[51] Zhou, D., et al. (2023). Least-to-most prompting. *ICLR*. https://arxiv.org/abs/2205.10625
[52] Jiang, Z., et al. (2024). LongRAG. *arXiv*. https://arxiv.org/abs/2406.15319

### Network and hardware

[22] NVIDIA. (n.d.). *NVIDIA H100 product documentation*.
[23] NVIDIA. (n.d.). *NVIDIA Quantum-2 InfiniBand documentation*.
[24] Sevilla, J. (2025). *How far can decentralized training over the internet scale?* Epoch AI.
[25] *Analysis of model-parallel schemes at public-internet latency*. (n.d.). ⚠ unverified.

### Genome assembly

[26] Lander, E. S., & Waterman, M. S. (1988). Genomic mapping by fingerprinting random clones. *Genomics, 2*(2), 231–239. https://doi.org/10.1016/0888-7543(88)90007-9
[27] Khadiev, K., & Safina, L. (2024). Quantum algorithms for the shortest common superstring and text assembling problems. *QIC, 24*(3–4), 267–294.
[28] *Survey of distributed and HPC genome assembly*. (n.d.). ⚠ unverified.
[29] Pevzner, P. A., Tang, H., & Waterman, M. S. (2001). An Eulerian path approach to DNA fragment assembly. *PNAS, 98*(17), 9748–9753.
[30] Nagarajan, N., & Pop, M. (2013). Sequence assembly demystified. *Nature Reviews Genetics, 14*, 157–167.
[31] Kingsford, C., Schatz, M. C., & Pop, M. (2010). Assembly complexity of prokaryotic genomes using short reads. *BMC Bioinformatics*.
[32] Chaisson, M. J. P., Wilson, R. K., & Eichler, E. E. (2015). Genetic variation and the de novo assembly of human genomes. *Nature Reviews Genetics*.

### Multi-agent systems, selection and aggregation

[33] Yan, W. (2025). *Don't build multi-agents*. Cognition engineering blog.
[38] Brown, B., et al. (2024). Large language monkeys. *arXiv*. https://arxiv.org/abs/2407.21787
[39] Maryanskyy, A., Budnikov, D., & Kaliyev, A. T. (2026). When agents disagree. *arXiv*. https://arxiv.org/abs/2603.20324
[40] Żywot, A., Chen, Y., Yuan, S., Søgaard, A., & de Rijke, M. (2026). Can small agents collaborate to beat a single large language model? *arXiv*. https://arxiv.org/abs/2601.11327
[41] Wang, J., et al. (2025). Mixture-of-agents. *ICLR*. https://arxiv.org/abs/2406.04692
[42] Chen, Y., Niu, G., Cheng, J., Han, B., & Sugiyama, M. (2025). When and why does multi-agent debate fail? *arXiv*. https://arxiv.org/abs/2510.20963
[71] *AgenTracer*. (2025). *arXiv*. https://arxiv.org/abs/2509.03312 ⚠ authorship unverified.
[90] Cemri, M., et al. (2025). Why do multi-agent LLM systems fail? *arXiv*. https://arxiv.org/abs/2503.13657

### Small models, planning and routing

[43] Belcak, P., et al. (2025). Small language models are the future of agentic AI. *arXiv*. https://arxiv.org/abs/2506.02153
[44] Schepanowski, C., & Ling, C. (2025). On the limits of innate planning in large language models. *arXiv*. https://arxiv.org/abs/2511.21591
[45] Valmeekam, K., et al. (2022). PlanBench. *arXiv*. https://arxiv.org/abs/2206.10498
[46] Ong, I., et al. (2024). RouteLLM. *arXiv*. https://arxiv.org/abs/2406.18665

### Embeddings and coherence

[34] Ethayarajh, K. (2019). How contextual are contextualized word representations? *EMNLP*. https://arxiv.org/abs/1909.00512
[35] Steck, H., et al. (2024). Is cosine-similarity of embeddings really about similarity? *WWW '24 Companion*. https://arxiv.org/abs/2403.05440
[36] Muennighoff, N., et al. (2023). MTEB. *EACL*. https://arxiv.org/abs/2210.07316
[37] Sentence-Transformers. (n.d.). *Semantic similarity and paraphrase mining* [documentation].
[53] Barzilay, R., & Lapata, M. (2008). Modeling local coherence: An entity-based approach. *Computational Linguistics, 34*(1).
[54] Chang, Y., et al. (2024). BooookScore. *ICLR*. https://arxiv.org/abs/2310.00785
[88] Chroma. (2025). *Context rot* [technical report].
[89] Liu, N. F., et al. (2023). Lost in the middle. *TACL*. https://arxiv.org/abs/2307.03172

### Verification, privacy and security

[50] Zhang, Y., Wang, S., Liu, X., Tan, S., Popa, R. A., & Moallemi, C. C. (2024). Proof of sampling. *arXiv*. https://arxiv.org/abs/2405.00295
[55] Sweeney, L. (2002). k-Anonymity. *IJUFKS, 10*(5), 557–570.
[56] Machanavajjhala, A., et al. (2007). ℓ-Diversity. *ACM TKDD, 1*(1).
[57] Narayanan, A., & Shmatikov, V. (2008). Robust de-anonymization of large sparse datasets. *IEEE S&P*.
[58] Narayanan, A., et al. (2012). On the feasibility of internet-scale author identification. *IEEE S&P*.
[59] *Cross-domain authorship attribution*. (2016). *PETS*. ⚠ authorship unverified.
[60] *Forensic authorship analysis of microblogging texts*. (2020). https://arxiv.org/abs/2003.11545 ⚠ authorship unverified.
[61] Morris, J. X., et al. (2023). Text embeddings reveal (almost) as much as text. *EMNLP*. https://arxiv.org/abs/2310.06816
[62] Zhang, C., et al. (2024). Extracting prompts by inverting LLM outputs. *EMNLP*.
[63] Fan, M., Liu, Y., Wang, F., & Chen, C. (2026). What does the server see? *arXiv*. https://arxiv.org/abs/2605.23158
[64] Keller, M. (2020). MP-SPDZ. *ACM CCS*.
[65] Hao, M., et al. (2022). Iron: Private inference on transformers. *NeurIPS*.
[66] Lu, W., et al. (2025). BumbleBee. *NDSS*.
[67] Sun, H., Li, J., & Zhang, H. (2024). zkLLM. *ACM CCS*. https://arxiv.org/abs/2404.16109
[68] Ong, J., et al. (n.d.). *TOPLOC*. ⚠ unverified.
[69] *VeriLLM*. (2025). https://arxiv.org/abs/2509.24257 ⚠ authorship unverified.
[70] OWASP Foundation. (2025). *OWASP top 10 for LLM applications*.
[72] *Confidential computing on NVIDIA Hopper GPUs*. (n.d.). ⚠ unverified.
[73] *Benchmarking confidential GPU inference on NVIDIA H100 under Intel TDX*. (n.d.). ⚠ unverified.
[74] Lukas, N., et al. (2023). Analyzing leakage of personally identifiable information in language models. *IEEE S&P*.
[75] *Differentially-private text generation degrades output language quality*. (2025). https://arxiv.org/abs/2509.11176 ⚠ authorship unverified.
[76] Douceur, J. R. (2002). The Sybil attack. *IPTPS*. https://doi.org/10.1007/3-540-45748-8_24
[77] Kamvar, S. D., Schlosser, M. T., & Garcia-Molina, H. (2003). The EigenTrust algorithm. *WWW*.

### Volunteer computing

[47] Anderson, D. P. (2019). BOINC: A platform for volunteer computing. *Journal of Grid Computing*. https://arxiv.org/abs/1903.01699
[48] Anderson, D. P., & Fedak, G. (2006). The computational and storage potential of volunteer computing. *CCGrid*.
[49] *Idle consumer GPUs versus enterprise GPUs for LLM inference*. (2025). *ACM AIBC*. ⚠ unverified.

### Licensing, governance, energy

[78] FINMA. (n.d.). *Guidelines for enquiries regarding the regulatory framework for ICOs*.
[79] European Parliament & Council of the EU. (2023). *Regulation (EU) 2023/1114 (MiCA)*.
[80] Free Software Foundation. (2007). *GNU Affero General Public License, version 3* (clause 13).
[81] *Redis relicensing to AGPLv3 (May 2025); Elastic adding AGPLv3 (August 2024)*. ⚠ unverified.
[82] *Comparative analysis of the 2021–2025 relicensing wave*. (n.d.). ⚠ unverified.
[83] International Energy Agency. (2025). *Energy and AI*.
[84] *Facility-level study of US hyperscale data centre grid carbon intensity*. (2026). ⚠ unverified.
[85] *Energy-aware LLM inference benchmark*. (2026). ⚠ unverified.
[86] Uptime Institute. (2025). *Global data center survey 2025*.
[87] Green Software Foundation. (2024). *Software carbon intensity (SCI) specification* (ISO/IEC 21031:2024).

---

### New in version 2 — alignment and substitution matrices

[92] Henikoff, S., & Henikoff, J. G. (1992). Amino acid substitution matrices from protein blocks. *PNAS, 89*(22), 10915–10919. https://www.pnas.org/doi/10.1073/pnas.89.22.10915
[93] Gotoh, O. (1982). An improved algorithm for matching biological sequences. *J. Mol. Biol., 162*(3), 705–708. https://doi.org/10.1016/0022-2836(82)90398-9
[94] Notredame, C., Higgins, D. G., & Heringa, J. (2000). T-Coffee: A novel method for fast and accurate multiple sequence alignment. *J. Mol. Biol., 302*(2), 205–217. https://tcoffee.org/Publications/Ps_pdf/tcoffee.pdf
[95] Eddy, S. R. (1998). Profile hidden Markov models. *Bioinformatics, 14*(9), 755–763. https://doi.org/10.1093/bioinformatics/14.9.755

### Learned costs and text alignment

[96] Ristad, E. S., & Yianilos, P. N. (1998). Learning string-edit distance. *IEEE TPAMI, 20*(5), 522–531.
[97] Pavlick, E., Rastogi, P., Ganitkevitch, J., Van Durme, B., & Callison-Burch, C. (2015). PPDB 2.0. *ACL-IJCNLP 2015*, 425–430. https://doi.org/10.3115/v1/P15-2070

### Uncertainty and agreement between generations

[98] Kuhn, L., Gal, Y., & Farquhar, S. (2023). Semantic uncertainty. *ICLR*. https://arxiv.org/abs/2302.09664
[99] Farquhar, S., Kossen, J., Kuhn, L., & Gal, Y. (2024). Detecting hallucinations in large language models using semantic entropy. *Nature, 630*, 625–630. https://doi.org/10.1038/s41586-024-07421-0
[100] Manakul, P., Liusie, A., & Gales, M. (2023). SelfCheckGPT. *EMNLP*, 9004–9017. https://doi.org/10.18653/v1/2023.emnlp-main.557
[101] Soiffer, D., Kolawole, S., & Smith, V. (2025). Semantic agreement enables efficient open-ended LLM cascades. *arXiv*. https://arxiv.org/abs/2509.21837 *(preprint, not peer reviewed)*

### Assembly, coverage, repeats and uniqueness

[102] Bresler, G., Bresler, M., & Tse, D. (2013). Optimal assembly for high throughput shotgun sequencing. *BMC Bioinformatics, 14*(Suppl 5), S18. https://arxiv.org/abs/1301.0068
[103] Motahari, A. S., Bresler, G., & Tse, D. N. C. (2013). Information theory of DNA shotgun sequencing. *IEEE Trans. Inf. Theory, 59*(10), 6273–6288. https://web.stanford.edu/~dntse/papers/mbt.pdf
[104] Compeau, P. E. C., Pevzner, P. A., & Tesler, G. (2011). How to apply de Bruijn graphs to genome assembly. *Nature Biotechnology, 29*(11), 987–991. https://doi.org/10.1038/nbt.2023
[105] Myers, E. W. (1995). Toward simplifying and accurately formulating fragment assembly. *J. Comput. Biol., 2*(2), 275–290. https://doi.org/10.1089/cmb.1995.2.275
[106] Weber, J. L., & Myers, E. W. (1997). Human whole-genome shotgun sequencing. *Genome Research, 7*(5), 401–409.
[107] Myers, E. W., et al. (2000). A whole-genome assembly of Drosophila. *Science, 287*(5461), 2196–2204.
[108] Gao, S., Sung, W.-K., & Nagarajan, N. (2011). Opera: Reconstructing optimal genomic scaffolds. *J. Comput. Biol., 18*(11), 1681–1691. https://doi.org/10.1089/cmb.2011.0170
[109] Medvedev, P., Pham, S., Chaisson, M., Tesler, G., & Pevzner, P. (2011). Paired de Bruijn graphs. *RECOMB 2011*, LNCS 6577, 238–251. https://doi.org/10.1007/978-3-642-20036-6_22

### Folding, domains and quality control

[110] Porter, L. L., & Rose, G. D. (2012). A thermodynamic definition of protein domains. *PNAS, 109*(24), 9420–9425. https://doi.org/10.1073/pnas.1202604109
[111] Han, J.-H., Batey, S., Nickson, A. A., Teichmann, S. A., & Clarke, J. (2007). The folding and evolution of multidomain proteins. *Nature Rev. Mol. Cell Biol., 8*(4), 319–330. https://doi.org/10.1038/nrm2144
[112] Bashton, M., & Chothia, C. (2007). The generation of new protein functions by the combination of domains. *Structure, 15*(1), 85–99. https://doi.org/10.1016/j.str.2006.11.009
[113] Zhang, Y., Chandonia, J.-M., Ding, C., & Holbrook, S. R. (2005). Comparative mapping of sequence-based and structure-based protein domains. *BMC Bioinformatics, 6*, 77. https://doi.org/10.1186/1471-2105-6-77
[114] Schaeffer, R. D., et al. (2023). ECOD domain classification of 48 whole proteomes from AlphaFold Structure Database using DPAM2. *PLoS Comput. Biol.*
[115] Zhu, K., Su, H., Peng, Z., & Yang, J. (2023). A unified approach to protein domain parsing with inter-residue distance matrix. *Bioinformatics, 39*(2), btad070. https://doi.org/10.1093/bioinformatics/btad070
[116] Gottesman, S., Wickner, S., & Maurizi, M. R. (1997). Protein quality control: Triage by chaperones and proteases. *Genes & Development, 11*, 815–823.
[117] Xu, Z., Horwich, A. L., & Sigler, P. B. (1997). The crystal structure of the asymmetric GroEL–GroES–(ADP)₇ chaperonin complex. *Nature, 388*(6644), 741–750. https://doi.org/10.1038/41944
[118] Netzer, W. J., & Hartl, F. U. (1997). Recombination of protein domains facilitated by co-translational folding in eukaryotes. *Nature, 388*(6640), 343–349. https://doi.org/10.1038/41024
[119] Marsh, J. A., et al. (2013). Protein complexes are under evolutionary selection to assemble via ordered pathways. *Cell, 153*(2), 461–470. https://doi.org/10.1016/j.cell.2013.02.044
[120] Shiber, A., et al. (2018). Cotranslational assembly of protein complexes in eukaryotes revealed by ribosome profiling. *Nature, 561*(7722), 268–272. https://doi.org/10.1038/s41586-018-0462-y

### Information theory and coding

[121] Shannon, C. E. (1959). Coding theorems for a discrete source with a fidelity criterion. *IRE Int. Convention Record, 7*, 325–350.
[122] Cover, T. M., & Thomas, J. A. (1991). *Elements of information theory*, ch. 13. Wiley.
[123] Nagle, A., Girish, A., Bondaschi, M., Gastpar, M., Makkuva, A. V., & Kim, H. (2024). Fundamental limits of prompt compression: A rate–distortion framework for black-box language models. *NeurIPS*. https://arxiv.org/abs/2407.15504
[124] Luby, M. (2002). LT codes. *FOCS 2002*, 271–282. https://doi.org/10.1109/SFCS.2002.1181950
[125] Shokrollahi, A. (2006). Raptor codes. *IEEE Trans. Inf. Theory, 52*(6), 2551–2567.
[126] Weatherspoon, H., & Kubiatowicz, J. D. (2002). Erasure coding vs. replication: A quantitative comparison. *IPTPS 2002*, LNCS 2429, 328–337.
[127] Mallick, A., Chaudhari, M., Palanikumar, G., Sheth, U., & Joshi, G. (2019). Rateless codes for near-perfect load balancing in distributed matrix-vector multiplication. *Proc. ACM Meas. Anal. Comput. Syst., 3*(3), art. 58.
[128] Kosaian, J., Rashmi, K. V., & Venkataraman, S. Learning a code: Machine learning for approximate non-linear coded computation. *arXiv*. https://arxiv.org/abs/1806.01259
[129] Soleymani, M., Ali, R. E., Mahdavifar, H., & Avestimehr, A. S. (2022). ApproxIFER. *AAAI-22*, 8342–8350.

### Volunteer computing (new)

[130] Anderson, D. P. (2004). BOINC: A system for public-resource computing and storage. *5th IEEE/ACM Int. Workshop on Grid Computing*. https://doi.org/10.1109/GRID.2004.14
[131] Anderson, D. P., & Fedak, G. (2006). The computational and storage potential of volunteer computing. *arXiv*. https://arxiv.org/abs/cs/0602061
[132] Anderson, D. P. (2018). BOINC: A platform for volunteer computing. *arXiv*. https://arxiv.org/abs/1903.01699
[133] Sarmenta, L. F. G. (2002). Sabotage-tolerance mechanisms for volunteer computing systems. *Future Generation Computer Systems, 18*(4), 561–572.

### Decentralised and decomposed inference (new)

[134] Dahshan, M., Mamun, Q., & Debnath, T. (2026). SWARM-LLM: Collaborative inference for edge-based small language models. *IEEE VTC2026-Spring*.
[135] Zhang, H., et al. (2025). If multi-agent debate is the answer, what is the question? *arXiv*. https://arxiv.org/abs/2502.08788

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Version 2.0. Spanish companion: `WHITEPAPER_V2_ES.md`. Focused extension: `WHITEPAPER_EXT_EN.md`. Previous version, superseded: `WHITEPAPER_EN.md` (v1.4).*
