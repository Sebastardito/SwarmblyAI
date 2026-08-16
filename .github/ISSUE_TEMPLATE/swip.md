---
name: SWIP — Swarmbly Improvement Proposal
about: Propose a change to the Swarmbly protocol, specification, or trust model
title: "[SWIP] "
labels: ["gip", "needs-triage"]
assignees: []
---

<!--
READ FIRST
==========
This template is for PROTOCOL changes. If you are fixing a bug, adding tests,
improving docs, or refactoring without changing behaviour, close this and open
a normal issue or PR instead — you do not need a SWIP.

A SWIP IS required if the change:
  - alters the wire format or any message schema
  - alters task decomposition or assembly semantics in a way that changes results
  - alters trust, privacy, or security assumptions
  - adds/removes a node obligation, or changes what a node may observe
  - alters the consensus rule or the coverage/redundancy model
  - breaks any public interface
  - is big enough that someone would reasonably ask "was this discussed?"

Process, in full: CONTRIBUTING.md Section 6.
This issue is STEP 1 (the discussion). If it gets traction, you then write
gips/SWIP-<this issue number>-short-title.md and open a PR containing only that
file. Implementation goes in a separate PR.

Review window: 14 days minimum for anything touching wire format, security, or
privacy; 7 days otherwise.

An incomplete SWIP is fine to open — "I don't know yet" is a real answer and is
more useful than a guess. Do not delete sections; write "unknown" or "not yet
determined" under them.
-->

## Metadata

| | |
|---|---|
| **Title** | <!-- short and descriptive --> |
| **Author** | <!-- name and @handle --> |
| **Targets spec version** | <!-- e.g. 0.2 --> |
| **Requires / builds on** | <!-- SWIP numbers, or "none" --> |
| **Supersedes** | <!-- SWIP numbers, or "none" --> |
| **Breaking change?** | <!-- yes / no / unsure --> |
| **Touches wire format, security, or privacy?** | <!-- yes / no — determines the review window --> |

## Abstract

<!-- Two or three sentences. What changes, in plain language, for someone who
has not been following the discussion. -->

## Motivation

<!--
What is broken or missing TODAY. Be concrete: describe the specific scenario
in which the current design produces a bad outcome. Who hits it, and what
happens to them?

If you have evidence — a measurement, a failed run, a log, a user report —
cite it here. Evidence is what separates a SWIP that gets read from one that
gets deferred.

A motivation that only says "it would be nicer if" is a weak motivation and
will be treated as one.
-->

## Specification

<!--
NORMATIVE. This is the section an independent implementer will build from, so
write it so they could do so WITHOUT reading the reference implementation.

Use RFC 2119 keywords (MUST, MUST NOT, SHOULD, SHOULD NOT, MAY) and use them
precisely — the difference between MUST and SHOULD is the difference between
an interoperability requirement and a recommendation.

Include, as applicable:
  - message schemas / record fields, with types and whether each is required
  - state transitions, and what happens on each edge
  - error cases and their handling — this is usually where the real design is
  - default values, and the valid range around each
  - timeouts, retries, and bounds
  - how a node that has NOT implemented this behaves when it meets one that has
-->

## Rationale

<!--
Why THIS design and not the obvious alternatives.

List the alternatives you considered and say why each was rejected. Include
"do nothing" if it was ever plausible. Be specific about the trade-off you are
accepting — every real design has one, and a SWIP claiming none has usually
just not found it yet.

This section is what makes the SWIP worth keeping after the decision is made:
in two years it stops someone re-proposing the alternative you already ruled
out.
-->

## Backwards compatibility

<!--
Does this break existing nodes, clients, in-flight tasks, or stored artifacts?

If YES:
  - what is the migration path?
  - what is the deprecation window?
  - how do old and new nodes behave when they meet on the network? (Answer
    this explicitly — a mixed network is the normal state during any rollout,
    not an edge case.)
  - is there a version negotiation, and what happens when it fails?

If NO: say "not applicable" and justify it in one line. Do not leave blank.
-->

## Security and privacy implications

<!--
MANDATORY. Every SWIP has this section, including the ones where the answer is
"none identified" — in which case say so AND say why you are confident.

Address at minimum:

  1. What can a MALICIOUS NODE now observe?
     Does this change how much of the original problem a single node can
     reconstruct? Does it widen any context slice? Does it make micro-tasks
     from one request more correlatable?

  2. What can a MALICIOUS NODE now cause?
     Can it poison a contig? Bias a consensus? Force a client to accept a
     low-coverage assembly? Cause a client to spend unbounded resources?

  3. What can a MALICIOUS or COERCED CLIENT cause on nodes?
     Resource exhaustion? Being made to generate content that harms the
     operator? Deanonymisation of node operators?

  4. Does this add a NEW TRUST ASSUMPTION, or strengthen an existing one?
     Name it explicitly. "Assumes the majority of selected nodes are honest"
     is a real assumption and must be written down as one.

  5. Does this create a new opportunity for TRAFFIC ANALYSIS or correlation
     across micro-tasks?

  6. Does this change the blast radius of a single compromised node?
-->

## Measurement plan

<!--
How will we know this worked? Fill this in BEFORE implementing.

  - Metric: what exactly is being measured?
  - Benchmark: which workload and configuration?
  - Baseline: what is it compared against?
  - Threshold: what result would count as success? What result would make you
    withdraw the SWIP?
  - Regression risk: what might this make worse, and how will you check?

If the change is genuinely not measurable, say so explicitly and explain how
it will be validated instead — a formal argument, a property-based test, an
adversarial test case.

Reminder: CONTRIBUTING.md Section 5 — any performance or quality claim in the
implementation PR must cite a measurement. Deciding what to measure now is
much cheaper than reverse-engineering it later.
-->

## Reference implementation

<!-- Link the PR, or "not yet implemented". Implementation goes in a SEPARATE
PR from the SWIP document. -->

## Open questions

<!--
Anything unresolved. Be generous here.

It is much better to open a SWIP with an honest list of open questions than to
paper over uncertainty — the open questions are usually where the useful part
of the discussion happens.
-->

## Checklist

- [ ] I have read `CONTRIBUTING.md` Section 6 (the SWIP process)
- [ ] This genuinely requires a SWIP (it is not a bug fix, test, doc, or
      behaviour-preserving refactor)
- [ ] I searched existing and closed SWIPs — including rejected ones — for this
      idea
- [ ] The **Specification** section is complete enough that an independent
      implementer could build from it without reading the reference code
- [ ] The **Security and privacy implications** section is filled in (not left
      blank, not deleted)
- [ ] The **Measurement plan** section is filled in, or explains why the change
      is not measurable
- [ ] Any claim I make about performance or quality cites a measurement
