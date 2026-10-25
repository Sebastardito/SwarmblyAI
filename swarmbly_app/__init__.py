"""Swarmbly App — integrated decentralized AI client and network dashboard.

Integrates SwarmblyAI (``swarmbly_v0``, the protocol reference implementation)
and SwarmblyLCE (``swarmbly_lce``) behind a local API and a lightweight web UI.
Fragments the *problem*, not the *model*.
"""

from __future__ import annotations

__version__ = "0.3.0"
__license__ = "AGPL-3.0-or-later"
PROTOCOL_SPEC_VERSION = "0.2"  # SwarmblyAI docs/SPEC_EN.md (wire version)
LCE_SPEC_VERSION = "0.1"       # SwarmblyLCE SPEC_LCE

__all__ = ["__version__", "__license__", "PROTOCOL_SPEC_VERSION", "LCE_SPEC_VERSION"]
