"""V7 — the frozen benchmark. Deliberately separate from the diagnostic harness.

V0 through V6 were a cumulative line of research and they earned their keep by
finding real instrument defects: a grader that inverted a baseline, a contract
that never reached a fragment, a coherence metric that was not arm-neutral, a
packing floor that disagreed with its own definition. That is what a laboratory
is for. It is not what evidence looks like, because the corpus, the metrics, the
contracts and the criteria all moved while the questions were being asked.

So this package is a benchmark, not a laboratory:

* **Its own instances**, generated from a fact graph with canonical answers and
  full traceability, so that for every claim a grader can say whether it is
  correct, whether the worker had the data needed to produce it, and which
  packet was supposed to carry that data.
* **Its own evaluator**, which does NOT import ``swarmbly_v0.metrics``. That is
  the single most important boundary here. The defect that cost this project
  four documents was a scorer whose behaviour depended on metadata about the
  partition; a benchmark sharing that scorer inherits the risk. The first test
  in ``test_evaluate.py`` is the arm-neutrality invariant.
* **A minimal runner** over the protocol's public interfaces. Router, packing,
  assembler and consensus are reused, not rewritten.

What V7 can and cannot establish
--------------------------------

A fact-graph corpus is synthetic and its answers are canonical by construction.
That is what makes it measurable, and it is also the limit. V7 can establish
**the protocol does not lose information it was given**; it cannot establish
**the protocol works on your documents**. This is stated here, before the first
result, so that it is a property of the design rather than a caveat added under
pressure.

The arms
--------

``monolithic``      the model's ceiling on this instance.
``oracle``          fragmented, every packet handed exactly the facts its task
                    needs. Whether the partition is viable *in principle*.
``real``            fragmented through router, packer and assembler.
``real+carry``      the causal effect of state transport.
``real+editor``     the causal effect of formal repair.

There is deliberately no consensus arm. The confidence map was declared, tested
and failed three times -- odds ratios of 3.47, 0.26 and 1.24 with an interval
straddling 1.0 on the largest sample -- and the plan's own rule was that a lift
which does not clearly exceed 1 leaves consensus as a diversity mechanism, not a
risk signal. k>1 remains available and its cost is measured; it is no longer
asked to predict error.

**The oracle arm is the point.** Every packaging failure this project spent weeks
on would have read as *oracle fine, real broken*, which localises the fault to
planning, packing or assembly in a single reading. It is implemented first.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
