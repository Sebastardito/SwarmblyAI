"""Swarmbly LCE — reference implementation of the Local Cognitive Extension.

The package implements the architecture specified in ``docs/SPEC_LCE_ES.md``
(and its English companion): a local-first cognitive layer for Swarmbly
clients made of three planes.

* **Local plane** — source space and learning policy (layer 0), an anchored,
  typed and versioned wiki (layer 1), and a behavioural adapter regenerated
  from the base model plus the wiki (layer 2).
* **Inference plane** — Task Projection onto the existing global contract Γ,
  double privacy classification, worker rules (serve the base model, discard
  the task) and plural responses built from replica agreement.
* **Social plane** — signed knowledge capsules exchanged on demand, anchored
  variation, epistemic distance, prevalence-as-label, affinity with decay and
  normalisation, and replica counts derived from a churn tolerance.

Nothing in this package is evidence about language models. ``MockBackend`` and
the simulations in ``lce_validation`` validate *instruments*; only runs with a
real backend can adjudicate the hypotheses of the whitepaper.
"""

from __future__ import annotations

__version__ = "0.2.0.dev0"
SPEC_VERSION = "0.1"
CAPSULE_VERSION = "0.2"

__all__ = ["__version__", "SPEC_VERSION", "CAPSULE_VERSION"]
