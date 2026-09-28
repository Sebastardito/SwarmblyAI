---
status: current
lang: en
---

# Swarmbly AI — Whitepaper extension

## Fragmentation fundamentals: homologies that carry an instrument

**Extends whitepaper v1, which it assumes has been read.** Its subject is the new fundamentals: how large a fragment
is, what neighbouring fragments share, which constraints cut across the whole
set, how the work is coordinated, and what the theoretical price of all of it
is.

---

## 0. What this document is and is not

Whitepaper v1 describes an architecture. This document examines its
**fundamentals**: the biological analogies the design decisions came out of,
which of them survive, and what replaces them when they do not.

Three things are worth saying up front.

**It is written against the literature, not against intuition.** Every transfer
is checked against the primary literature of the source field. Four hypotheses
entered that check; **two did not survive**, and sections 5 and 8 document their
fall in more detail than their replacement, because the fall is the result.

**It cites the project's own evidence where that evidence supports a decision.**
This is not a catalogue of measurements — those live in the results record — but
when a measurement from the project justifies a change of fundamentals, it
appears.

**It is not ready to be published.** Several of the models it proposes are
falsifiable and have not been falsified yet. Section 10 states what each one
predicts and how to kill it.

---

## 1. The method: what makes a homology useful

### 1.1 The problem with analogies

Swarmbly was born of an analogy: a request too large for a small model resembles
a genome too long for a sequencer. It is broken up, read in parts, reassembled.

Analogies of that kind are productive at first and dangerous afterwards. They
are productive because they import mature vocabulary for a new problem. They are
dangerous because the vocabulary arrives with connotations that do not transfer,
and because an analogy that sounds good resists scrutiny precisely for that
reason.

Whitepaper v1 already states the caution — no genome assembly algorithm runs
inside Swarmbly — but it offers no criterion for deciding when a transfer is
real. This section proposes one.

### 1.2 The instrument test

> **A homology is useful when it brings an instrument: a procedure, an
> inequality or a number that can be applied to the new problem. It is not
> useful when all it brings is a way of talking.**

The clear case is the coverage equation. Lander & Waterman (1988) derive, for
genomic mapping by random clones, that the expected number of islands is
`N·e^(−cθ)` with `c = LN/G`. That derivation hands over a number — how many
replicas are needed — where before there was a guess. It is an instrument.

The opposite case, and it has to be said because it comes from the project
itself: calling a fragment of an answer a *contig* does nothing. It is
vocabulary.

### 1.3 The failure-mode test, which turned out to be the more discriminating one

Applying the instrument test to the five homologies the project uses, a pattern
emerged that had not been looked for:

> **Homologies that transfer come accompanied by their failure mode. Those that
> do not transfer bring a mechanism without its associated pathology.**

The minimum-overlap criterion comes with *mis-assembly*: if the overlap does not
exceed the repeat, the assembler glues the wrong stretches together. The protein
domain comes with its interface condition: independence is lost when the
interface is large and tightly packed. Chaperone triage comes with degradation:
what cannot be recovered is destroyed, not patched in.

By contrast the codon — which section 2 discards — was proposed as "the minimum
unit of meaning" with no statement whatsoever about what happens when it is
violated. Fountain codes — section 8 — were proposed for their recovery property
with no condition on when that property ceases to exist.

The reason is that a mature field does not discover an isolated mechanism: it
discovers a mechanism **and** the cases where it fails, and it usually publishes
the second with more care than the first. A transfer that brings only the good
part is importing the conclusion without the work.

This gives an operational test, and it is the one that organises the rest of the
document:

| question | if the answer is no |
|---|---|
| Does it bring a procedure, an inequality or a number? | It is vocabulary. Use it as vocabulary. |
| Does it bring a statement of what happens when the condition is violated? | It is half-imported. Find the failure mode before building on it. |
| Do the source field's conditions hold here? | Invalid transfer. Say why, which is usually informative. |

---

## 2. The semantic unit: two homologues for two different things

### 2.1 The codon is not the homologue

The original proposal took the **codon** — three nucleotides translated into one
amino acid — as the homologue of the minimum unit of meaning in text, and
derived from it that there exists a minimum fragment size below which meaning is
destroyed.

The conclusion is correct. The derivation is not. The codon has three structural
properties, and the sentence has none of them:

| property of the codon | the sentence |
|---|---|
| **Fixed width** — exactly 3 nucleotides | Variable. Measured over the project corpus: p25 = 9 tokens, p75 = 25. Nearly 3× range. |
| **Reading frame** — non-overlapping; a shift ruins everything downstream | There is no frame. A displaced cut does not destroy the rest of the text. |
| **Deterministic map** — `GGA` is always glycine | The same idea admits infinitely many textual surfaces. |

Three out of three. The transfer is not partial: it is null on all three
properties that define the codon.

### 2.2 The amino acid is the homologue of the alignment unit

The third row points at where it does fit. The amino acid is a unit of
**variable width**, **self-delimiting**, with **properties of its own**, and it
is **the unit of the folded structure**. The sentence shares all four.

And the distinction is not terminological, because computational biology has
**two alignment technologies** and the choice of homologue determines which one
is inherited:

- **Nucleotide alignment** — identity or not. `A` against `G` is a disagreement,
  full stop.
- **Protein alignment** — substitution matrices. Henikoff & Henikoff (1992)
  build BLOSUM by counting aligned amino acid pairs in ungapped blocks and
  computing, for each pair, `s_ij = log₂(q_ij / e_ij)`, the log ratio of
  observed to expected frequency, in half-bit units.

That formula is the instrument. It says that the interchangeability of two units
is not postulated: **it is counted**, over cases already known to be homologous.

For Swarmbly the consequence is direct. Two nodes that answer

> "The tide window closes at noon."
> "The channel shuts at midday."

are not in disagreement. Under nucleotide-style comparison they are a total
disagreement; under a substitution matrix they are a **conservative
substitution**.

### 2.3 The domain is the homologue of the fragment

Here is the most important correction in this document, and one the original
proposal did not contain.

The amino acid is not the homologue of the **fragment**. No amino acid folds
alone or has function alone. The unit that does is the **domain**.

Porter & Rose (2012) give the rigorous definition: a domain is "a contiguous
segment of the folded protein whose m-value remains largely unchanged when that
segment is excised from its parent structure", and they equate domain with
"cooperative folding unit; i.e., its cooperativity depends primarily on
intra-segment, not inter-segment, interactions".

Read the second clause carefully, because **it is the specification of a good
task fragment**: a piece whose resolution depends on what it contains and not on
what its neighbours contain.

The reference work on multidomain proteins (Han et al., 2007) confirms that more
than 70% of eukaryotic proteins are multidomain and that domain folding is
independent — **but with an explicit condition**: "where the interface is small
and poorly packed, or unstructured, folding of the domains is independent".

### 2.4 The interface condition is the cutting rule

That condition is not a footnote caveat. It is the instrument:

> **Fragment where the coupling between fragments is weak. A fragment boundary
> is a decision about the interface, not about size.**

This reorders the design. The planner must not cut every `L` sentences and hope
it works out: it must **look for the points of weak coupling** and cut there,
with `L` as a target and not as a rule. A cut that splits a strong dependency
produces two fragments that are not domains, and the independence guarantee
applies to neither.

The project already has an incident that is exactly this failure: the segmenter
separated a question from the material that answered it. That was not an
implementation error, it was a cut across a strong interface. Under the earlier
formulation — cut into N parts of similar size — that failure is structural and
recurrent. Under the interface rule, it is detectable before dispatch.

### 2.5 Functional autonomy is quantified, and it is not total

Bashton & Chothia (2007) compare homologous domains that appear both in
single-domain and in multidomain proteins, over 70 unique domain pairs in 45
protein sets: approximately **three quarters preserve their function** when the
context changes; **a little under one sixth changes substantially**.

The number is useful because it bounds the expectation. "A fragment solved in
isolation is worth the same as in context" is true most of the time and false
one time in six or seven. A design that assumes total autonomy is assuming
something nature does not deliver even in the system the idea was borrowed from.

### 2.6 Size: there is a band, there is no number

The natural question is whether a natural domain size exists that would suggest
a natural `L` for text. The honest answer is that **a characteristic band exists
and a number does not**, and the reason it does not is instructive.

Zhang et al. (2005) map sequence-defined domains against structure-defined
domains, over the same proteins: **Pfam averages 96 residues; SCOP averages
174**. Almost double, over the same material, in the same paper. The difference
is not noise: Pfam cuts by sequence family and SCOP by structure. **The
definition determines the number.**

Schaeffer et al. (2023), classifying domains over predicted structures, report
**99.8 ± 64.8 residues** — a standard deviation that is 65% of the mean.

The floor, by contrast, is sharp. Porter & Rose set **25 residues** as the
minimum, "approximating the size of a supersecondary structure unit"; UniDoc
(Zhu et al., 2023) uses 30 as a parsing constraint.

Both lessons transfer cleanly:

1. **The floor is hard and principled.** Below a certain size nothing folds
   cooperatively. For text, this predicts that an `L_min` exists below which a
   fragment is not independently solvable, and that this floor is sharper than
   the optimum.
2. **The optimum is a wide, definition-dependent band.** Any claim that
   `L* = 50` is a number is an over-reading. What can be expected is a band
   spanning a factor of 3 to 6, and the definition of "unit" chosen will move
   its centre.

### 2.7 The revised fundamentals of the semantic unit

1. The minimum alignment unit is the **sentence**, homologous to the amino acid:
   variable width, self-delimiting, with meaning of its own, and the unit over
   which substitution is computed.
2. The fragmentation unit is the **task domain**, homologous to the protein
   domain: the segment whose resolution depends on internal interactions and not
   on its neighbours.
3. The fragment boundary is chosen **where coupling is weak**, with `L` as a
   target in sentences and not as a division rule.
4. `L` is a property of the **node class**, measured and revisable. `N` is
   derived: `N = ⌈material / L⌉`.
5. There is a hard `L_min`; the optimum is a band.

---

## 3. Alignment and the confidence map

### 3.1 What the confidence map is, in design terms

When a micro-task is dispatched to `k` nodes from different families, `k`
answers to the same problem come back. The confidence map is the annotation,
**unit by unit**, of where those answers converged and where they diverged.

The structural property that makes it interesting is that **a provider with a
single model has nothing to align**. It can report the model's internal
probability over its own output, which is a measure of confidence in itself, not
an independent corroboration.

### 3.2 The state of the art: it clusters, it does not align

The recent literature on uncertainty in generation is abundant and good, and it
is worth locating oneself against it precisely.

**Semantic entropy** (Kuhn, Gal & Farquhar, ICLR 2023; Farquhar et al.,
*Nature* 2024) samples several answers, clusters them by semantic equivalence
via **bidirectional entailment** — A entails B and B entails A, therefore same
cluster — and computes entropy over meaning clusters instead of over token
sequences. Average AUROC 0.790 across 30 model-and-task combinations.

**SelfCheckGPT** (Manakul, Liusie & Gales, EMNLP 2023) produces **per-sentence**
factuality scores by comparing each sentence against complete samples.

**Semantic agreement across different models** (Soiffer, Kolawole & Smith, 2025 —
preprint) uses agreement among a set of smaller models as a deferral signal
toward a larger model: "when independently generated outputs are semantically
consistent — even if lexically distinct — their agreement suggests the
underlying meaning is reliable". Architecturally, it is the nearest neighbour to
Swarmbly.

**What all of them share, and this is the opening:** they treat the `k` answers
as **a bag to be clustered**. None treats them as **sequences to be aligned**.
That difference is not stylistic: clustering yields a scalar per answer (or, in
SelfCheckGPT, a per-sentence score obtained by comparison against whole samples);
alignment yields a **position-to-position** correspondence between the answers,
which is what allows one to say *where* they diverged and not only *how much*.

### 3.3 The instrument: multiple alignment with substitution cost

The machinery exists and is mature.

**Substitution cost is learned, not postulated.** That is the lesson of BLOSUM
(§2.2), and in the text domain it is already solved at the string level: Ristad &
Yianilos (1998) give "an efficient algorithm for learning the primitive edit
costs from a corpus of examples", via a stochastic transducer fitted by EM.

**And it is solved at the phrase level.** PPDB 2.0 (Pavlick et al., ACL 2015) is
a paraphrase database rescored discriminatively: they collected human judgements
over **26,455 pairs**, each rated by 5 people on a 5-point Likert scale, and
fitted a ridge regression over **209 features** (the 33 from PPDB 1.0 plus 176
new ones).

The result is the single most useful datum in this whole investigation for the
project:

> **The heuristic ranking correlated with human judgement at ρ = 0.41. The
> empirically fitted model reached ρ = 0.71. And in that model embedding cosine
> is one feature out of 209.**

That is published, quantified evidence that **raw embedding distance is not the
right instrument** for judging semantic interchangeability, which is exactly
what the confidence map needs to judge.

**Consistency-based alignment is the design Swarmbly wants.** T-Coffee
(Notredame, Higgins & Heringa, 2000) builds a primary library of pairwise
alignments and then **extends** it: for each pair of residues it examines their
alignment with residues from the other sequences, and "the weight associated
with a pair of residues will be the sum of all the weights gathered through the
examination of all the triplets involving that pair".

Translated: **an agreement corroborated through a third, independent answer
weighs more than an agreement between two.** And the progressive phase uses
"position-specific scoring" instead of a fixed matrix.

A consistency-weighted, position-specific agreement computed over `k`
independent answers **is** a confidence map. T-Coffee has been producing exactly
that object for biological sequences for twenty-five years.

**And the formalisation of the product exists too.** A profile HMM (Eddy, 1998)
"turns a multiple sequence alignment into a position-specific scoring system".
The HMMER guide defines it as "a position-specific scoring model that describes
which symbols are likely to be observed and how frequently insertions/deletions
occur at each position (column) of a multiple alignment".

A position-specific scoring model built from a set of aligned answers is, once
again, the formal description of a confidence map.

### 3.4 The proposed model

Gathering the verified pieces:

**M1 — Multiple alignment of answers with learned semantic substitution.**

1. **Segment** each of the `k` answers into sentences (the alignment unit of
   §2.7).
2. **Align** the `k` sentence sequences by dynamic programming with affine gap
   penalties (Gotoh, 1982), using a semantic substitution matrix.
3. **Build that matrix empirically**, BLOSUM-style: count pairs of sentences
   that appear as mutual substitutions in cases verified as correct, and score
   `log(q_obs / e_exp)`. The embedding enters as a feature, not as a verdict —
   the quantified lesson of PPDB 2.0.
4. **Extend by consistency**, T-Coffee-style: weight each correspondence by its
   corroboration through the other answers.
5. **Emit** a position-specific profile over the resulting alignment. That is
   the map.

**What is new and what is not.** Nothing in steps 2, 3 and 4 is invention: they
are Needleman-Wunsch with Gotoh, Henikoff with Ristad, and Notredame. What is
new is **applying them to outputs from different models instead of to biological
sequences**, and doing so to produce a per-unit annotation rather than a scalar
per answer. The contribution is the assembly of the instrument, not its parts,
and it must be stated that way.

---

## 4. Flanks, repeats and the information floor

### 4.1 Overlap solves a different problem here

In *de novo* assembly, overlap exists above all to **discover order**: nobody
knows which part of the genome each read came from. Swarmbly does not have that
problem — the orchestrator creates the fragments and knows their order.

Two reasons remain, and only one is genomic: **transition continuity** (that the
end of one fragment meets the beginning of the next) and **repeat detection**.

### 4.2 The minimum-overlap criterion has two forms, and the strong one is the interesting one

The folk statement — "overlap must exceed the longest repeat" — is correct but
weak. The information-theoretic literature sharpens it into two distinct
conditions (Bresler, Bresler & Tse, 2013):

**Sufficient condition for a greedy algorithm:**

```
L > ℓ_repeat + 1
```

"GREEDY reconstructs the original sequence if every repeat is bridged." That is
a statement about **one particular algorithm**.

**Necessary, information-theoretic condition:**

```
L > max{ℓ_interleaved, ℓ_triple} + 1
```

where an *interleaved* repeat is a pair of repeats whose positions interleave,
and a *triple* repeat is a subsequence that appears three times. Below that
threshold **no algorithm** can reconstruct, because two different sequences
produce identical read sets.

The distinction matters to Swarmbly more than it appears. The first form says
"do better". The second says **there exists a class of inputs where the
fragments simply do not contain the information needed to reassemble correctly,
however clever the assembler is.**

Motahari, Bresler & Tse (2013) formalise the threshold: for i.i.d. sequences
there is a sharp transition according to whether the normalised read length
exceeds the order-2 Rényi entropy of the source. Above it, "the obvious coverage
condition is also sufficient for reconstruction"; below it, no amount of coverage
suffices.

**The parallel this enables, and which the project should adopt:** coverage — how
many replicas — and solvability — whether the fragments contain the information —
are **two distinct questions**, and the first does not imply the second. A design
that reasons only about `k` is reasoning about coverage and keeping silent about
solvability.

### 4.3 A repeat is a property of a pair, and the project has already measured it

The semantic homologue of a genomic repeat is **a recurring phrase or
template**. Two fragments that cannot see each other repeat the same structure,
and the assembler cannot detect it because **a repeat is a property of a pair,
not of a fragment**.

This is not speculation: the formal definition in Bresler et al. is inherently
relational — a repeat "is a subsequence that appears twice" at positions `t₁`
and `t₂`. No individual read can be inspected to determine whether it lies in a
repeat.

And the project **has already measured the same phenomenon**. The
`no_repeated_ngram` constraint is the irreducible class in its composition
measurements: **4 of 12 against 11 of 12 for the monolithic arm**, and no
context-allocation policy reaches it. It was the defect that would not yield. The
reason, now nameable, is that no allocation *can* reach it: a fragment cannot
avoid repeating what it cannot see.

### 4.4 The flank F, defined by measurement

Hence the operational criterion:

> **`F` is the maximum of two quantities measured over the corpus: the longest
> repeatable unit the assembler must be able to detect, and the longest
> dependency that crosses a fragment boundary.**

Reference estimate for the project corpus: **`F ≈ 5–10` sentences**.

### 4.5 The bill

The context budget is derived from `L`, `F` and the header cost:

```
ρ ≈ (L + 2F) / L  +  H / (L · s)
```

where `H` is the fixed per-packet cost — contract, glossary, formatting
instructions — measured at **≈ 39 tokens** over the project corpus, and `s ≈ 15`
tokens per sentence.

With `L = 50`, `F = 10`: **ρ ≈ 1.45**. With a flank inherited by analogy,
`F = 25`: **ρ ≈ 2.05**.

**29% of the compute of the whole network**, from the single decision to measure
the flank instead of copying a percentage. And since §4.2 says exactly what to
measure, the saving relaxes no guarantee.

The second term deserves a note, because it explains something the project
observed without being able to name it: the header is paid **in full per
packet**, so its relative weight is inversely proportional to `L`. With 35-token
fragments — the actual fragment size in the project's composition measurements —
the 39-token header **weighs more than the material**. That is the regime in
which measurements were taken for months, and it explains why ρ appeared to have
a high floor: it was not a property of the protocol, it was a property of
fragmenting too finely.

---

## 5. The single-appearance constraint

### 5.1 A hypothesis that did not survive

The hypothesis was: *mate pairs are the homologue of global constraints —
"mention this term exactly once", "do not repeat a formulation" — because they
are the mechanism genomics invented for information that no individual read
contains.*

> **Background concept.** A *mate pair* or paired-end read is a pair of reads
> sequenced from the two ends of the same DNA fragment of approximately known
> length. Weber & Myers (1997) introduced it precisely because "read pairs from
> both ends have known spacing and orientation", which "aids the assembly of
> sequences containing dispersed repetitive elements".

Half the hypothesis is correct: constraints that cross fragments are real, they
are the central difficulty, and genomics did invent explicit machinery for
information that no single piece contains.

The other half is wrong, and it is wrong along four axes at once:

| axis | mate pair | "exactly once in the whole output" |
|---|---|---|
| **Arity** | Binary and pre-identified: it names two concrete reads, and the pair exists before assembly because library preparation created it | n-ary and quantified: it names no pair; it quantifies over all fragments |
| **Metric content** | It is fundamentally a **distance**, with a distribution — Myers et al. (2000) report insert lengths "normally distributed with 10% variance" | It has neither distance nor orientation |
| **Hardness** | **Soft**: Opera (Gao, Sung & Nagarajan, 2011) defines concordance as a predicate the optimiser **maximises**; a discordant mate pair is tolerated | **Hard**: a single violation is a failure, not a datum to be outvoted |
| **Direction of information** | **Evidence**: an additional observation sampled from a genome that already exists, reducing ambiguity about which reconstruction is the true one | **Specification**: there is no true answer to recover; it is a condition imposed on the output |

The fourth axis is the deepest. Genome assembly is **maximum-likelihood
inference toward a correct answer that pre-exists**. Swarmbly does **constraint
satisfaction over a space of acceptable outputs**. Mate pairs live on the
inference side.

### 5.2 The correct homologue is in the same literature

Genomics does have a mechanism whose form is "this must appear exactly N times
in the whole output". It is not mate pairs. It is **multiplicity** and
**uniqueness**.

**k-mer multiplicity.** Compeau, Pevzner & Tesler (2011) state it as a counting
operation that enters the graph structure: one must determine "how many times
each k-mer appears", and "if the multiplicity of a k-mer is m, we will connect
its prefix to its suffix using m directed edges (instead of just one)".

That is a global cardinality constraint on the reconstruction, imposed
**structurally** rather than as an after-the-fact check.

**U-unitigs.** Myers et al. (2000), in the *Drosophila* assembly, describe that
those units "that are certain to represent unique DNA were designated
U-unitigs" — and all the scaffolding is anchored on them.

It is literally the "exactly once in the whole output" mechanism: the assembler
**computes the set of sequences that must appear exactly once** and builds around
them.

**The failure mode, which confirms the transfer.** Myers (1995) names the
pathology when this is done badly: seeking the shortest string containing all
fragments means that "in the case of repetitive target sequences this objective
produces over-compressed answers".

**Over-compression** is exactly the failure of an assembler that merges two
passages that should have remained distinct. And its dual — emitting twice
something that should have appeared once — is the failure `no_repeated_ngram`
measures.

### 5.3 The proposed model

**M2 — Cardinality constraints resolved in the representation, not in the
output.**

The strongest architectural lesson comes from Medvedev et al. (2011), who argue
against after-the-fact treatment: mate pairs have been incorporated "as various
heuristic post-processing steps", which "may still fail to resolve complex
repeats"; their proposal is to incorporate the information **into the graph
structure itself**.

Applied to Swarmbly:

1. **Compute the uniqueness set before dispatch.** Which terms, entities and
   formulations must appear exactly once in the final output. It is the analogue
   of identifying U-unitigs.
2. **Assign each element of that set to exactly one fragment**, as a property of
   the plan and not as an instruction to the nodes. A node cannot satisfy
   "exactly once" because it does not know what the others wrote; the planner
   can.
3. **Verify cardinality at assembly**, against the set computed in step 1, not
   against a rule stated in the contract.
4. **Log the two failure modes separately**: over-compression (what should have
   been distinguished was merged) and over-expansion (what should have appeared
   once was repeated). They are different errors with different causes, and
   measuring them together hides both.

Point 2 is the real change. Today the project asks for `term_once` in the
contract and enforces it mechanically at the assembler. That works, and the
measurement confirms it — mechanical enforcement raised compliance from 6/24 to
18/24, above the monolithic arm's 13/24. But it is an after-the-fact correction.
**Assigning uniqueness in the plan makes the constraint impossible to violate
rather than detectable afterwards**, which is precisely the argument of Medvedev
et al.

### 5.4 What a mate pair actually is

The transfer is not null: it is narrower in scope than proposed. Mate pairs are
the correct homologue of a real class of Swarmbly constraint: **"fragment A and
fragment B must be mutually consistent at a known relative position"**.

Examples with mate-pair shape: the conclusion must pick up the anecdote from the
introduction; section 4 must resume the thread left open by section 2; a
reference to a figure in one fragment must correspond to a figure defined in
another. They are binary, they have a positional component, they are known in
advance because the plan created them, and they degrade gracefully when
partially violated.

For those, the Medvedev et al. argument transfers along with the homology.

---

## 6. The graph, the levels and triage

### 6.1 What the protein homology contributes, and what it does not

The planner **already is** a directed acyclic graph with topological levels. The
protein-folding analogy justifies it well but proposes nothing new there, and it
is worth saying so in order not to mistake a better narrative for a new
capability.

What it **does** contribute lies in a clause the earlier version did not have:
*tasks at one level begin only when their predecessors have returned **and have
been verified***.

### 6.2 Triage is the specification that was missing

Biology has a name for that control, and it is precise. Gottesman, Wickner &
Maurizi (1997) call it exactly that:

> "we propose […] a general model for what may be thought of as a **triage**
> system for handling misfolded proteins in vivo, ensuring the **rapid refolding
> of proteins with functional potential and the rapid degradation of irreversibly
> denatured or damaged proteins**."

That sentence is almost a specification of Swarmbly's quality-control stage:
classify each returned fragment as **recoverable → retry** or **unrecoverable →
discard and regenerate**, and **never splice a bad one into the assembly**.

The mechanism is equally instructive. The GroEL/GroES chaperonin does not repair
the piece in place: it **isolates** it. Xu, Horwich & Sigler (1997) describe how
GroES binding "stabilizes a folding chamber" whose elevation and twisting of the
apical domains "doubles the volume of the central cavity and buries the
hydrophobic peptide-binding residues", leaving a hydrophilic lining "conducive to
folding".

**Isolate and retry**, not patch in context.

### 6.3 The evidence that levels matter

There is a result that goes beyond justifying the DAG: it prefers it over flat
parallelism.

Netzer & Hartl (1997) found that two-domain polypeptides "fold efficiently by
sequential, co-translational folding" in eukaryotic translation, while the same
proteins folded post-translationally in *E. coli* suffer "intramolecular
misfolding of concurrently folding domains".

That is: **folding the domains one at a time, in order, succeeded where folding
them concurrently produced interference**. The argument is not that parallelism
is bad; it is that **unrestricted** parallelism is, and that the structure that
orders it is what makes it safe.

And Marsh et al. (2013) show that the assembly order of protein complexes "can
be predicted simply from their three-dimensional structures" and that there is
**evolutionary selection to preserve assembly order**. Order is not an
engineering convenience: in the system the analogy is taken from, it is under
selection.

### 6.4 An honest complication: assembly starts before folding finishes

Shiber et al. (2018), via ribosome profiling, found that **nine of twelve**
hetero-oligomeric complexes studied assemble co-translationally, and
"co-translational assembly often occurs unidirectionally, with a fully
synthesized subunit engaging its nascent partner subunit".

This complicates the "fold everything, then assemble" picture, and in a direction
Swarmbly can exploit: **a level-n fragment can be consumed while level n+1 is
still being generated**, provided the one being consumed is complete. It is an
argument for streaming assembly with a completeness condition, not for barrier
waiting.

### 6.5 The proposed model

**M3 — Triage gate per topological level.**

1. A level does not start until the carries from its predecessors have passed a
   **mechanical predicate**: *does the carry that arrived answer the task that
   requested it?* No judge, no model, cheap.
2. A fragment that does not pass is **isolated and retried**, not patched in
   context nor spliced in with a warning.
3. A fragment that does not pass after `r` retries is **discarded and
   regenerated** with a different plan. Degradation is a legitimate output of
   triage, not a system failure.
4. Consumption may begin **before the level is complete**, if the fragment being
   consumed is complete and verified.

**Why it matters.** The project has an incident this gate catches: 42 of 60
dispatched packets carried another packet's answers. Without a gate, carries pass
forward unreviewed and one level's error multiplies into the next. With a gate,
the blast radius is one fragment.

---

## 7. ρ as an indirect rate-distortion problem

### 7.1 Why formalise it

ρ has functioned as an empirical quantity: it is measured, compared, reported.
Section 4 derives it from `L`, `F` and `H`, which is already an advance over
treating it as a dial. But deriving it does not say **whether a floor exists**,
nor what it depends on.

Rate-distortion theory is the framework in which that question has an answer.

### 7.2 The theory, stated precisely

> **Background concept.** Rate-distortion theory (Shannon, 1959) answers: given
> that I am going to transmit an imperfect version of something, what is the
> minimum information rate needed for the imperfection not to exceed a given
> level?
>
> Shannon defines a distortion matrix in which "d_ij measures the 'cost' or
> 'distortion' if letter i is reproduced at the receiver as letter j", and
> `R(d*)` as the minimum rate subject to the average distortion not exceeding
> `d*`. Cover & Thomas write it as
>
> ```
> R(D) = min I(X; X̂)
> ```
>
> minimised over conditional distributions `p(x̂|x)` satisfying the expected
> distortion constraint. Their Theorem 13.2.1 establishes that the
> rate-distortion function of an i.i.d. source with bounded distortion **equals**
> the associated informational function.
>
> The shape of the curve is the essential part: `R(D)` decreases with `D`. Less
> fidelity demanded, less information needed. And there is a floor: below `R(D)`
> the distortion `D` is unreachable, whatever one does.

### 7.3 The framing already exists for prompts, and that has to be said

Nagle et al. (NeurIPS 2024) formalise **prompt compression** as a
rate-distortion problem for black-box language models. Their rate is

```
E[ len(M) / len(X) ]
```

— expected compressed prompt length over expected original length — which is
**structurally the same quantity as ρ**. Their distortion is the degradation of
model performance under logarithmic or 0/1 loss. They derive the
distortion-rate function via the dual of a linear program and report a large gap
between current compression methods and the optimal strategy.

**Consequence for Swarmbly:** the contribution cannot be "ρ is a
rate-distortion problem". That is published. The contribution has to be ρ **under
fragmentation with distributed reassembly**, which is a different and harder
problem, and one Nagle et al. do not cover.

### 7.4 Why Swarmbly's problem is *indirect*

The natural objection is that classical rate-distortion assumes a source that is
reconstructed, and Swarmbly does not reconstruct the prompt: it produces an
answer.

The theory has a name for that situation: the **indirect** or **remote**
rate-distortion problem, in which "the encoder cannot observe the source directly
but obtains only noisy observations" (the formulation goes back to Wolf & Ziv).

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

> **M4 — ρ is the rate of an indirect rate-distortion problem whose distortion
> is task loss. From this one inherits the existence of a lower bound and the
> qualitative monotonicity of the curve. One does not inherit a computable
> bound.**

### 7.5 What cannot be claimed, and why

Three limits, stated before a reviewer states them.

**The bound exists but is not computable here.** Nagle et al. obtain a number
because they restrict to token erasure over a known prompt with a black-box LLM,
and solve a finite linear program. Swarmbly's encoder is a decomposition policy
and its decoder is a language model; there is no tractable `p(x)` over the task
space and no single-letter distortion. One may claim the bound **exists**; not
that it has been computed.

**The theorem is asymptotic in i.i.d. blocks.** A user request is one
realisation, not a long sequence. The converse gives no per-request guarantee.

**And the most important one: distortion is not caused by rate alone.**

### 7.6 The second axis: dependency density

This is the section's own contribution, and it comes out of a datum from the
prior art.

Skeleton-of-Thought (Ning et al., ICLR 2024) generates a skeleton and expands the
points in parallel. It achieves speedups of up to **2.39×**. And its quality
degradation **is not uniform**: it improves "diversity and relevance while
hurting immersion and coherence", and **fails on maths and coding**.

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

This connects to §2.4 in a way that closes the document's argument: **the
weak-interface cutting rule is, in this language, the minimisation of δ**.
Cutting where coupling is weak is exactly choosing the decomposition of lowest
dependency density for a given ρ.

And to §4.2: the Bresler et al. information floor — the condition
`L > max{ℓ_interleaved, ℓ_triple} + 1` — is the statement, in assembly language,
that **there exists a region of the (ρ, δ) plane where no acceptable distortion
is reachable**, because the fragments do not contain the information.

The three formulations — weak interface, information floor, dependency density —
are the same claim in three vocabularies. That they converge from three
independent literatures is the reason to believe it.

### 7.7 What of this can be measured

The surface `D(ρ, δ)` is falsifiable without further theory:

- Fixing δ and varying only ρ (same cut, different flank) should produce a curve
  monotonically decreasing in distortion.
- Fixing ρ and varying δ (same budget, cuts of different coupling) should produce
  variation in distortion **at constant rate** — which is the result that would
  kill the idea that ρ suffices as an axis.
- The unreachability region should manifest as a distortion floor that no ρ
  improves.

**The second of these was measured, which is the decisive one, and the
result is negative.** The experiment cuts the **same prompt** twice at the
**same `L`**: once at weak-coupling interfaces and once maximising the coupling
that crosses the cut. δ rises in all **32** pairs and ρ stays equal to within
**5 %**, so the only axis that moved is δ. The prediction is that the strong cut
worsens distortion in every pair; it worsens in **19 of 32**. An observational
measurement over **127** intra-category cells converges: Spearman(δ, distortion)
= **−0.13**, with the sign opposite to the prediction.

> **Status of the `D(ρ, δ)` surface.** The first axis holds: the ρ accounting
predicts packet size to within **7.5 %** and the curve falls as `L` grows, as
derived. **The second axis does not.** This is not a clarification of scope: it
is the death condition of §10 being met. δ is kept as a descriptive quantity of
the plan — it is computed, recorded, and it orders the cuts — and **withdrawn as
an explanatory axis of distortion and as a predictive feature of the router**.

---

## 8. Redundancy: a refuted hypothesis and its replacement

### 8.1 The hypothesis

*Instead of sending the same packet to `k` nodes, send `N + m` encoded fragments
of which any `N` suffice to reconstruct.*

The motivation was good and is well founded in the storage literature.
Weatherspoon & Kubiatowicz (2002) show that erasure codes "use an order of
magnitude less bandwidth and storage than replication for systems with similar
MTTF": with a million machines and 10% down, two full replicas give "only two
nines of availability", while an encoding into 32 fragments gives "more than
eight nines" with the same storage.

Fountain codes take that to the limit. Luby (2002) proves that the `k` input
symbols are recovered "from any `k + O(√k · ln²(k/δ))` of the encoding symbols
with probability `1 − δ`". Shokrollahi (2006) improves it to "any subset of
symbols of size `(1+ε)k` is sufficient" with `O(1)` operations per symbol. In
practice, RaptorQ: two extra symbols give a failure probability of ~10⁻⁵, "valid
for all supported values of k" and "for all loss probabilities: 1% to 99%".

### 8.2 Why it does not transfer

The reason is clean and admits no nuance.

**Fountain codes are linear codes over shared unknowns.** Shokrollahi's
definition says so: "each output symbol is the sum of some of the input
symbols", and decoding is Gaussian elimination or peeling over that linear
system. The entire mechanism by which "any `k(1+ε)` suffice" **is** that the
received symbols are **linear equations in the same unknowns**.

Swarmbly's fragments are not equations in shared unknowns. Each node **generates
new text**. There is no XOR, no algebraic field, no inverse. There is nothing to
solve for.

And this is not an inference of our own: it is the explicit limitation stated in
the coded-computing literature. Kosaian, Rashmi & Venkataraman note that much
work employs erasure codes for computing **linear functions**, and that "to the
best of our knowledge, none of the existing works are applicable to broader
classes of non-linear computations".

What does exist confirms the diagnosis from the positive side. Mallick et al.
(2019) apply rateless codes to distributed matrix-vector multiplication and
obtain up to **3× speedup** with asymptotically zero redundancy, using stragglers'
partial work instead of discarding it. It works **because matrix-vector
multiplication is linear**. And the only serious attempt at coding non-linear
inference — ApproxIFER (AAAI-22) — achieves **approximate** recovery over
low-dimensional classification outputs, with reported accuracy losses of up to
~6–9% in degraded mode. That is the honest ceiling of "coding over model outputs"
today: approximation over classification, not exact recovery of generated text.

A specific search was made for prior work applying fountain codes to LLM agent
redundancy or to decentralised LLM inference. **None exists.** The transfer has
not been attempted, and linearity explains why.

### 8.3 What does transfer: the economics, not the mechanism

The real lesson of the storage literature is not about XOR. It is about
**thresholds and quorums**: for a target reliability, `(N, N+m)` beats `k`-fold
duplication.

That does transfer:

**M5 — Over-dispatch with early termination.** Dispatch `N` distinct sub-tasks
plus `m` extras, accept the first `N` that return, discard stragglers. It is a
threshold scheme, it delivers the ρ saving that was being sought, **and it is
not a fountain code**. Calling it one would be the very error this document
exists to avoid.

**With one condition that must be stated, because it is the core of the
trade-off:** the `m` extras are only free if the sub-tasks are **genuinely
interchangeable**. The entire point of erasure coding is that *any* `k` symbols
serve. Swarmbly's fragments are not interchangeable: if the content of fragment
`j` is needed, receiving the other `N−1` does not substitute for it. Making them
interchangeable requires content redundancy, which costs exactly the ρ one wanted
to save.

### 8.4 Separating availability from verification

The research left a finding that reorders the role of `k`, and that is probably
more valuable than the original hypothesis.

`k` today serves **two distinct purposes** that the design does not separate:

- **Availability** — that the task completes even if a node goes down.
- **Verification** — that a dishonest node cannot impose a false result.

Sarmenta (2002) measures the cost of each route in volunteer computing: voting
"reduces error rates exponentially with redundancy, but requires all work to be
done several times, and does not work well when there are many saboteurs";
spot-checking "reduces the error rate linearly with the amount of work to be
done, while only costing an extra fraction of the original time"; and the
credibility-based combination yields "mathematically guaranteeable levels of
correctness with much less slowdown".

BOINC implements the deployed version of that: adaptive replication achieving "a
low bound on the error rate […] even in the presence of malicious volunteers,
while imposing only a small performance overhead".

**The design consequence:**

> If `k` exists for **verification**, erasure codes were never the tool;
> credibility-based spot-checking is. If `k` exists for **availability**,
> threshold over-dispatch solves it. And if `k` exists for the **confidence
> map** — epistemic redundancy — then it is replaceable by neither, because its
> product is not fault tolerance but signal.

Three purposes, three mechanisms, and today a single parameter. Separating them
is an immediate improvement to the protocol, available without measuring
anything.

### 8.5 The field data that calibrates all of this

Anderson & Fedak (2006), over more than 330,000 SETI@home hosts: mean on-fraction
**0.81**, connected fraction **0.83**, mean active fraction **0.84**, **host mean
lifetime 91 days**. The 2018 version reports ~700,000 devices and availability of
**~60%** for desktop machines and **~40%** for mobile.

Those are the numbers the coverage equation must be fed. They are not
catastrophic: a loss rate of 16–40% is exactly the regime threshold redundancy is
designed for.

---

## 9. Prior art and positioning

### 9.1 What has to be acknowledged

**Layer parallelism over volunteers.** Petals (Borzunov et al., 2022) distributes
BLOOM-176B **by layers** across participating machines, ~1 step/second. SWARM
(Ryabinin et al., ICML 2023) is "a model-parallel training algorithm designed for
poorly connected, heterogeneous and unreliable devices" with "temporary
randomized pipelines" — but it is **training**, not inference.

Both distribute **the model**. Swarmbly distributes **the problem**. That is the
distinction of whitepaper v1 and it still stands.

**Task decomposition.** Skeleton-of-Thought (ICLR 2024) is the nearest neighbour
on the fragmentation axis: skeleton plus parallel expansion, up to 2.39×.
Decomposed Prompting (Khot et al.) delegates sub-tasks to "a shared library of
prompting-based LLMs". Chain of Agents (NeurIPS 2024) processes segments
sequentially with a manager agent that synthesises. Mixture-of-Agents (2024)
stacks proposers and aggregators, 65.1% on AlpacaEval 2.0.

**And the closest of all:** SWARM-LLM (Dahshan, Mamun & Debnath, VTC 2026) routes
a query to a local SLM, to several peer SLMs at the edge with **weighted
consensus where lower-uncertainty nodes weigh more**, or escalates to the cloud.
It reports ~28% cloud usage and accuracy on hard questions rising from 0% to 15%
over a load of **50 queries**. That is weak empirical evidence — 50 queries — but
it claims the territory, and it must be cited and differentiated from.

**The guarantee Swarmbly does not have.** Speculative decoding (Leviathan et al.,
ICML 2023; Chen et al., 2023) achieves 2–3× "with identical outputs", via a
rejection sampling scheme that **preserves the target model's distribution**. It
is the only decomposition scheme in the literature with a provable no-distortion
guarantee. Swarmbly has no analogue, and a reviewer will notice. Better to say it
before they do.

### 9.2 The adverse evidence that has to be faced

Two recent works are the most serious criticism of the entire multi-agent
architecture family, and the whitepaper must answer them, not walk around them.

**"Why Do Multi-Agent LLM Systems Fail?"** (Cemri et al., 2025) builds the MAST
taxonomy: **14 failure modes in 3 categories** — system design issues,
inter-agent misalignment, task verification — from more than 1,600 annotated
traces over **7 frameworks**, with 150 traces validated by expert annotators at
**κ = 0.88**.

**"If Multi-Agent Debate is the Answer, What is the Question?"** (Zhang et al.,
2025) finds that multi-agent debate methods "fail to consistently outperform
single-agent baselines such as Chain-of-Thought and Self-Consistency, even when
consuming additional inference-time compute", across 9 benchmarks, 4 models and 5
methods.

**Swarmbly's honest answer to this** is not that its architecture is immune. It
is that **MAST's three categories are exactly the three this document
addresses**:

| MAST category | where it is addressed here |
|---|---|
| System design issues | §2.4 interface cutting rule; §5.3 uniqueness assigned in the plan |
| Inter-agent misalignment | §3 alignment with semantic substitution; §1 global contract |
| Task verification | §6.5 per-level triage gate |

That a taxonomy built independently over 1,600 traces coincides with the three
areas the biological homologies pointed at is, if not a validation, at least a
convergence worth declaring.

And Zhang et al.'s criticism is more specific than it appears: it targets
**debate** — agents arguing to converge — not **decomposition** — agents solving
disjoint parts. Swarmbly does not debate. But the lesson transfers all the same:
**additional compute must be justified against a single-agent baseline with
self-consistency**, and that is the correct baseline, not the naive monolithic
model.

---

## 10. What each model predicts, and how to kill it

The five models in this document are falsifiable. Saying so here is what
separates a whitepaper extension from a manifesto.

**M1 — Alignment with learned semantic substitution.**
*Predicts:* a confidence map built by alignment with learned cost separates
correct from incorrect better than one built by match counting, and better than a
scalar per answer, **in a non-saturated regime**.
*Killed if:* with the correct instrument and in a regime where the models
genuinely disagree, per-unit agreement does not beat chance. Then localisation
creates no signal and the confidence map loses its reliability claim, though it
retains its ability to report divergence.

**M2 — Cardinality resolved in the representation.**
*Predicts:* assigning uniqueness in the plan makes `no_repeated_ngram` and
`term_once` inviolable by construction, not merely detectable. The violation rate
should fall to zero, not improve.
*Killed if:* assignment in the plan does not reduce violations below what
mechanical enforcement at the assembler already achieves (18/24).

**M3 — Per-level triage gate.**
*Predicts:* the blast radius of a defective fragment stays contained in that
fragment. An incident of the "42 of 60 packets contaminated" type becomes
impossible.
*Killed if:* the gate rejects so much legitimate work that the retry cost exceeds
the damage it prevents.

**M4 — ρ as indirect rate-distortion with a second axis δ.**
*Predicts:* at constant ρ, varying the dependency density of the cut moves the
distortion. And there exists a region where no ρ reaches an acceptable
distortion.
*Killed if:* distortion turns out to be a function of ρ alone, with δ having no
measurable effect. Then the second axis is decoration and the framing adds
nothing over the empirical derivation of §4.

**M5 — Threshold over-dispatch, and `k` split into three.**
*Predicts:* separating availability, verification and epistemic redundancy allows
the total cost to be lowered while keeping all three guarantees, because today a
single parameter pays for all three at the price of the most expensive.
*Killed if:* the three turn out to be so coupled in practice that separating them
saves nothing.

**Status after the reference campaign** (341 runs, five local model
families; the detail is in §15.9 of whitepaper v2):

| Model | Verdict | On what |
|---|---|---|
| **M1** | no instrument | the aligner is built and verified on the bench, but the corpus did not produce the non-saturated regime M1 requires |
| **M2** | survives, corrected | **6/35** by node obedience; **35/35** with the assembler's mechanical enforcement. "Zero by construction" is withdrawn: what is zero by construction is over-compression |
| **M3** | survives | contaminated packets do not pass the gate |
| **M4** | **falsified** | two independent instruments and a controlled experiment at constant ρ (§7.7) |
| **M5** | unmeasured | it remains a conceptual separation |

Two of the five models this document proposes are falsified or corrected by the
first serious measurement made of them. That is the result that justifies having
written them as death conditions rather than as claims.

### 10.1 The order in which to attack them

By increasing cost and by what each one unlocks:

1. **M5** needs no measurement: it is a conceptual separation of a parameter that
   already exists. Implement and observe.
2. **M3** is cheap and its prediction is binary: the incident happens or it does
   not.
3. **M2** is measured over the composition corpus that already exists.
4. **M4** needs the difficulty-calibrated corpus on which the entire current
   experimental agenda depends.
5. **M1** needs the aligner to be built, and is the most expensive. It is also
   the one that produces the most distinctive property.

---

## 11. What this document changes relative to whitepaper v1

| in v1 | after this extension |
|---|---|
| The codon as the minimum unit of meaning | **Withdrawn.** Three of three properties fail to transfer. The sentence is homologous to the amino acid (alignment unit); the domain is homologous to the fragment (unit of work) |
| Fragment into `N` parts of similar size | **Replaced** by cutting at weakly coupled interfaces, with `L` as a target and `N` derived |
| Overlap as a percentage of the fragment | **Replaced** by `F` = maximum of longest repeat and longest crossing dependency. Measured saving: 29% |
| ρ as a parameter to be tuned | **Replaced** by ρ derived from `L`, `F`, `H`; and formalised as the rate of an indirect problem |
| Confidence map by match counting | **Replaced** by multiple alignment with learned substitution cost and consistency extension |
| `term_once` enforced at the assembler | **Complemented** by uniqueness assignment in the plan, U-unitig style |
| DAG with no control between levels | **Extended** with a triage gate, by analogy with chaperones |
| `k` replicas as one parameter | **Split** into availability, verification and epistemic redundancy |
| Genomic analogy as vocabulary | **Formalised** as a method: the instrument test and the failure-mode test |
| The models M1–M5 stated | **Measured.** M4 falsified, M2 corrected, M3 survives, M1 has no regime, M5 unmeasured (§10) |

---

## 12. Bibliography

All references were verified against the online source indicated. Where only the
abstract could be confirmed and not the full text, this is noted.

### Alignment and substitution matrices

1. Henikoff, S. & Henikoff, J. G. (1992). "Amino acid substitution matrices from protein blocks." *PNAS* 89(22): 10915–10919. https://www.pnas.org/doi/10.1073/pnas.89.22.10915
2. Needleman, S. B. & Wunsch, C. D. (1970). "A general method applicable to the search for similarities in the amino acid sequence of two proteins." *J. Mol. Biol.* 48(3): 443–453. DOI 10.1016/0022-2836(70)90057-4
3. Smith, T. F. & Waterman, M. S. (1981). "Identification of common molecular subsequences." *J. Mol. Biol.* 147(1): 195–197. DOI 10.1016/0022-2836(81)90087-5
4. Gotoh, O. (1982). "An improved algorithm for matching biological sequences." *J. Mol. Biol.* 162(3): 705–708. DOI 10.1016/0022-2836(82)90398-9
5. Altschul, S. F. & Erickson, B. W. (1986). "Optimal sequence alignment using affine gap costs." *Bull. Math. Biol.* 48: 603–616. DOI 10.1007/BF02462326
6. Notredame, C., Higgins, D. G. & Heringa, J. (2000). "T-Coffee: A novel method for fast and accurate multiple sequence alignment." *J. Mol. Biol.* 302(2): 205–217. https://tcoffee.org/Publications/Ps_pdf/tcoffee.pdf
7. Thompson, J. D., Higgins, D. G. & Gibson, T. J. (1994). "CLUSTAL W…" *Nucleic Acids Research* 22(22): 4673–4680. DOI 10.1093/nar/22.22.4673
8. Eddy, S. R. (1998). "Profile hidden Markov models." *Bioinformatics* 14(9): 755–763. DOI 10.1093/bioinformatics/14.9.755
9. Eddy, S. R. et al. *HMMER User's Guide*, v3.2.1, 2018. http://eddylab.org/software/hmmer/Userguide.pdf

### Learned costs and text alignment

10. Ristad, E. S. & Yianilos, P. N. (1998). "Learning String-Edit Distance." *IEEE TPAMI* 20(5): 522–531.
11. Pavlick, E., Rastogi, P., Ganitkevitch, J., Van Durme, B. & Callison-Burch, C. (2015). "PPDB 2.0…" *ACL-IJCNLP 2015*, pp. 425–430. DOI 10.3115/v1/P15-2070
12. MacCartney, B., Galley, M. & Manning, C. D. (2008). "A Phrase-Based Alignment Model for Natural Language Inference." *EMNLP 2008*, pp. 802–811. https://aclanthology.org/D08-1084.pdf
13. Sultan, M. A., Bethard, S. & Sumner, T. (2014). "Back to Basics for Monolingual Alignment…" *TACL* 2: 219–230. https://aclanthology.org/Q14-1018.pdf
14. Barzilay, R. & Lee, L. (2003). "Learning to Paraphrase: An Unsupervised Approach Using Multiple-Sequence Alignment." *HLT-NAACL 2003*, pp. 16–23.
15. Barzilay, R. & Elhadad, N. (2003). "Sentence Alignment for Monolingual Comparable Corpora." *EMNLP 2003*. https://aclanthology.org/W03-1004.pdf
16. Cer, D., Diab, M., Agirre, E., Lopez-Gazpio, I. & Specia, L. (2017). "SemEval-2017 Task 1…" *SemEval-2017*, pp. 1–14. DOI 10.18653/v1/S17-2001

### Uncertainty and agreement between generations

17. Kuhn, L., Gal, Y. & Farquhar, S. (2023). "Semantic Uncertainty…" *ICLR 2023*. arXiv:2302.09664
18. Farquhar, S., Kossen, J., Kuhn, L. & Gal, Y. (2024). "Detecting hallucinations in large language models using semantic entropy." *Nature* 630: 625–630. DOI 10.1038/s41586-024-07421-0
19. Manakul, P., Liusie, A. & Gales, M. (2023). "SelfCheckGPT…" *EMNLP 2023*, pp. 9004–9017. DOI 10.18653/v1/2023.emnlp-main.557
20. Soiffer, D., Kolawole, S. & Smith, V. (2025). "Semantic Agreement Enables Efficient Open-Ended LLM Cascades." arXiv:2509.21837. *(preprint, not peer reviewed)*
21. Wang, X. et al. (2023). "Self-Consistency Improves Chain of Thought Reasoning in Language Models." *ICLR 2023*. arXiv:2203.11171
22. Jiang, D., Ren, X. & Lin, B. Y. (2023). "LLM-Blender…" *ACL 2023*, pp. 14165–14178.

### Assembly, coverage and repeats

23. Lander, E. S. & Waterman, M. S. (1988). "Genomic Mapping by Fingerprinting Random Clones: A Mathematical Analysis." *Genomics* 2(3): 231–239.
24. Motahari, A. S., Bresler, G. & Tse, D. N. C. (2013). "Information Theory of DNA Shotgun Sequencing." *IEEE Trans. Inf. Theory* 59(10): 6273–6288. https://web.stanford.edu/~dntse/papers/mbt.pdf
25. Bresler, G., Bresler, M. & Tse, D. (2013). "Optimal assembly for high throughput shotgun sequencing." *BMC Bioinformatics* 14(Suppl 5): S18. arXiv:1301.0068
26. Pevzner, P. A., Tang, H. & Waterman, M. S. (2001). "An Eulerian path approach to DNA fragment assembly." *PNAS* 98(17): 9748–9753. DOI 10.1073/pnas.171285098
27. Compeau, P. E. C., Pevzner, P. A. & Tesler, G. (2011). "How to apply de Bruijn graphs to genome assembly." *Nature Biotechnology* 29(11): 987–991. DOI 10.1038/nbt.2023
28. Miller, J. R., Koren, S. & Sutton, G. (2010). "Assembly algorithms for next-generation sequencing data." *Genomics* 95(6): 315–327.
29. Myers, E. W. (1995). "Toward Simplifying and Accurately Formulating Fragment Assembly." *J. Comput. Biol.* 2(2): 275–290. DOI 10.1089/cmb.1995.2.275
30. Nagarajan, N. & Pop, M. (2009). "Parametric Complexity of Sequence Assembly…" *J. Comput. Biol.* 16(7): 897–908. DOI 10.1089/cmb.2009.0005
31. Shomorony, I., Kim, S., Courtade, T. & Tse, D. (2016). "Information-optimal genome assembly via sparse read-overlap graphs." *Bioinformatics* 32(17): i494.
32. Treangen, T. J. & Salzberg, S. L. (2012). "Repetitive DNA and next-generation sequencing…" *Nature Reviews Genetics* 13(1): 36–46. *(abstract only verified)*

### Long-range constraints and scaffolding

33. Weber, J. L. & Myers, E. W. (1997). "Human Whole-Genome Shotgun Sequencing." *Genome Research* 7(5): 401–409.
34. Myers, E. W. et al. (2000). "A Whole-Genome Assembly of Drosophila." *Science* 287(5461): 2196–2204.
35. Pop, M., Kosack, D. S. & Salzberg, S. L. (2004). "Hierarchical Scaffolding With Bambus." *Genome Research* 14: 149–159. DOI 10.1101/gr.1536204
36. Medvedev, P., Pham, S., Chaisson, M., Tesler, G. & Pevzner, P. (2011). "Paired de Bruijn Graphs…" *RECOMB 2011*, LNCS 6577: 238–251. DOI 10.1007/978-3-642-20036-6_22
37. Gao, S., Sung, W.-K. & Nagarajan, N. (2011). "Opera: Reconstructing Optimal Genomic Scaffolds…" *J. Comput. Biol.* 18(11): 1681–1691. DOI 10.1089/cmb.2011.0170

### Pre-assembly correction

38. Tammi, M. T., Arner, E., Kindlund, E. & Andersson, B. (2003). "Correcting errors in shotgun sequences." *Nucleic Acids Research* 31(15): 4663–4672. DOI 10.1093/nar/gkg653
39. Kelley, D. R., Schatz, M. C. & Salzberg, S. L. (2010). "Quake: quality-aware detection and correction of sequencing errors." *Genome Biology* 11(11): R116.
40. Yang, X., Chockalingam, S. P. & Aluru, S. (2013). "A survey of error-correction methods for next-generation sequencing." *Briefings in Bioinformatics* 14(1): 56–66.

### Folding, domains and quality control

41. Anfinsen, C. B. (1973). "Principles that Govern the Folding of Protein Chains." *Science* 181(4096): 223–230. DOI 10.1126/science.181.4096.223
42. Levinthal, C. (1969). "How to Fold Graciously." *Mössbauer Spectroscopy in Biological Systems*, Univ. of Illinois Bulletin 67(41): 22–24.
43. Dill, K. A. & Chan, H. S. (1997). "From Levinthal to pathways to funnels." *Nature Struct. Mol. Biol.* 4(1): 10–19. DOI 10.1038/nsb0197-10
44. Porter, L. L. & Rose, G. D. (2012). "A thermodynamic definition of protein domains." *PNAS* 109(24): 9420–9425. DOI 10.1073/pnas.1202604109
45. Han, J.-H., Batey, S., Nickson, A. A., Teichmann, S. A. & Clarke, J. (2007). "The folding and evolution of multidomain proteins." *Nature Rev. Mol. Cell Biol.* 8(4): 319–330. DOI 10.1038/nrm2144
46. Bashton, M. & Chothia, C. (2007). "The Generation of New Protein Functions by the Combination of Domains." *Structure* 15(1): 85–99. DOI 10.1016/j.str.2006.11.009
47. Zhang, Y., Chandonia, J.-M., Ding, C. & Holbrook, S. R. (2005). "Comparative mapping of sequence-based and structure-based protein domains." *BMC Bioinformatics* 6:77. DOI 10.1186/1471-2105-6-77
48. Schaeffer, R. D. et al. (2023). "ECOD domain classification of 48 whole proteomes from AlphaFold Structure Database using DPAM2." *PLoS Comput. Biol.*
49. Hubbard, T., Murzin, A., Brenner, S. & Chothia, C. (1997). "SCOP: a Structural Classification of Proteins database." *Nucleic Acids Research* 25(1): 236–239. DOI 10.1093/nar/25.1.236
50. Orengo, C. et al. (1997). "CATH – a hierarchic classification of protein domain structures." *Structure* 5(8): 1093–1109. DOI 10.1016/S0969-2126(97)00260-8
51. Zhu, K., Su, H., Peng, Z. & Yang, J. (2023). "A unified approach to protein domain parsing with inter-residue distance matrix." *Bioinformatics* 39(2): btad070. DOI 10.1093/bioinformatics/btad070
52. Wheelan, S. J., Marchler-Bauer, A. & Bryant, S. H. (2000). "Domain size distributions can predict domain boundaries." *Bioinformatics* 16(7): 613–618. DOI 10.1093/bioinformatics/16.7.613
53. Gottesman, S., Wickner, S. & Maurizi, M. R. (1997). "Protein quality control: triage by chaperones and proteases." *Genes & Development* 11: 815–823.
54. Hartl, F. U., Bracher, A. & Hayer-Hartl, M. (2011). "Molecular chaperones in protein folding and proteostasis." *Nature* 475(7356): 324–332. DOI 10.1038/nature10317
55. Xu, Z., Horwich, A. L. & Sigler, P. B. (1997). "The crystal structure of the asymmetric GroEL–GroES–(ADP)₇ chaperonin complex." *Nature* 388(6644): 741–750. DOI 10.1038/41944
56. Rosenzweig, R., Nillegoda, N. B., Mayer, M. P. & Bukau, B. (2019). "The Hsp70 chaperone network." *Nature Rev. Mol. Cell Biol.* 20(11): 665–680. DOI 10.1038/s41580-019-0133-3
57. Netzer, W. J. & Hartl, F. U. (1997). "Recombination of protein domains facilitated by co-translational folding in eukaryotes." *Nature* 388(6640): 343–349. DOI 10.1038/41024
58. Frydman, J., Erdjument-Bromage, H., Tempst, P. & Hartl, F. U. (1999). "Co-translational domain folding as the structural basis for the rapid de novo folding of firefly luciferase." *Nature Struct. Mol. Biol.* 6(7): 697–705. DOI 10.1038/10754
59. Cassaignau, A. M. E., Cabrita, L. D. & Christodoulou, J. (2020). "How Does the Ribosome Fold the Proteome?" *Annu. Rev. Biochem.* 89: 389–415. DOI 10.1146/annurev-biochem-062917-012226
60. Marsh, J. A. et al. (2013). "Protein Complexes Are under Evolutionary Selection to Assemble via Ordered Pathways." *Cell* 153(2): 461–470. DOI 10.1016/j.cell.2013.02.044
61. Shiber, A. et al. (2018). "Cotranslational assembly of protein complexes in eukaryotes revealed by ribosome profiling." *Nature* 561(7722): 268–272. DOI 10.1038/s41586-018-0462-y

### Information theory and coding

62. Shannon, C. E. (1959). "Coding Theorems for a Discrete Source With a Fidelity Criterion." *IRE Int. Convention Record* 7: 325–350.
63. Cover, T. M. & Thomas, J. A. (1991). *Elements of Information Theory*, ch. 13, "Rate Distortion Theory". Wiley.
64. Nagle, A., Girish, A., Bondaschi, M., Gastpar, M., Makkuva, A. V. & Kim, H. (2024). "Fundamental Limits of Prompt Compression: A Rate–Distortion Framework for Black-Box Language Models." *NeurIPS 2024*. arXiv:2407.15504
65. Luby, M. (2002). "LT Codes." *FOCS 2002*, pp. 271–282. DOI 10.1109/SFCS.2002.1181950
66. Shokrollahi, A. (2006). "Raptor Codes." *IEEE Trans. Inf. Theory* 52(6): 2551–2567.
67. Luby, M., Shokrollahi, A., Watson, M., Stockhammer, T. & Minder, L. (2011). *RFC 6330: RaptorQ Forward Error Correction Scheme for Object Delivery*.
68. Weatherspoon, H. & Kubiatowicz, J. D. (2002). "Erasure Coding vs. Replication: A Quantitative Comparison." *IPTPS 2002*, LNCS 2429: 328–337.
69. Rodrigues, R. & Liskov, B. (2005). "High Availability in DHTs: Erasure Coding vs. Replication." *IPTPS 2005*, LNCS 3640: 226–239.
70. Huang, C. et al. (2012). "Erasure Coding in Windows Azure Storage." *USENIX ATC 2012*.
71. Mallick, A., Chaudhari, M., Palanikumar, G., Sheth, U. & Joshi, G. (2019). "Rateless Codes for Near-Perfect Load Balancing in Distributed Matrix-Vector Multiplication." *Proc. ACM Meas. Anal. Comput. Syst.* 3(3), art. 58.
72. Kosaian, J., Rashmi, K. V. & Venkataraman, S. "Learning a Code: Machine Learning for Approximate Non-Linear Coded Computation." arXiv:1806.01259
73. Soleymani, M., Ali, R. E., Mahdavifar, H. & Avestimehr, A. S. (2022). "ApproxIFER: A Model-Agnostic Approach to Resilient and Robust Prediction Serving Systems." *AAAI-22*, pp. 8342–8350.

### Volunteer computing

74. Anderson, D. P. (2004). "BOINC: A System for Public-Resource Computing and Storage." *5th IEEE/ACM Int. Workshop on Grid Computing*. DOI 10.1109/GRID.2004.14
75. Anderson, D. P. & Fedak, G. (2006). "The Computational and Storage Potential of Volunteer Computing." arXiv:cs/0602061
76. Anderson, D. P. (2018). "BOINC: A Platform for Volunteer Computing." arXiv:1903.01699
77. Sarmenta, L. F. G. (2002). "Sabotage-tolerance mechanisms for volunteer computing systems." *Future Generation Computer Systems* 18(4): 561–572.

### Decentralised and decomposed inference

78. Ning, X. et al. (2024). "Skeleton-of-Thought: Prompting LLMs for Efficient Parallel Generation." *ICLR 2024*. arXiv:2307.15337
79. Borzunov, A. et al. (2022). "Petals: Collaborative Inference and Fine-tuning of Large Models." arXiv:2209.01188
80. Ryabinin, M., Dettmers, T., Diskin, M. & Borzunov, A. (2023). "SWARM Parallelism…" *ICML 2023*, PMLR 202: 29416–29440
81. Leviathan, Y., Kalman, M. & Matias, Y. (2023). "Fast Inference from Transformers via Speculative Decoding." *ICML 2023*, PMLR 202: 19274–19286
82. Chen, C. et al. (2023). "Accelerating Large Language Model Decoding with Speculative Sampling." arXiv:2302.01318
83. Shazeer, N. et al. (2017). "Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer." arXiv:1701.06538
84. Fedus, W., Zoph, B. & Shazeer, N. (2022). "Switch Transformers…" *JMLR* 23(120): 1–39
85. Khot, T. et al. "Decomposed Prompting: A Modular Approach for Solving Complex Tasks." arXiv:2210.02406
86. Zhang, Y. et al. (2024). "Chain of Agents: Large Language Models Collaborating on Long-Context Tasks." *NeurIPS 2024*
87. Wang, J. et al. (2024). "Mixture-of-Agents Enhances Large Language Model Capabilities." arXiv:2406.04692
88. Dahshan, M., Mamun, Q. & Debnath, T. (2026). "SWARM-LLM: Collaborative Inference for Edge-based Small Language Models." *IEEE VTC2026-Spring*
89. Li, J. et al. (2024). "More Agents Is All You Need." *TMLR*

### Multi-agent system failure modes

90. Cemri, M. et al. (2025). "Why Do Multi-Agent LLM Systems Fail?" arXiv:2503.13657
91. Zhang, H. et al. (2025). "If Multi-Agent Debate is the Answer, What is the Question?" arXiv:2502.08788

---

*Swarmbly AI — Sebastián A. Espinoza-Ulloa · Spanish companion:
`WHITEPAPER_EXT_ES.md`. Main document: `WHITEPAPER_V2_EN.md`.*
