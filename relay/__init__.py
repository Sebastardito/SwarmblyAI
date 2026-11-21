# SPDX-License-Identifier: AGPL-3.0-only
"""Swarmbly circle relay (prototype, T10.5 spike).

A small rendezvous and byte-splicing service a circle owner runs; the nodes'
end-to-end TLS 1.3 session passes through it.  See ``README.md`` and
``docs/orchestration/spikes/T10.5_relay_design.md``.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
