"""Swarmbly AI — validation harness.

Pure-stdlib implementation of the falsification tests and the arithmetic
checks implied by WHITEPAPER_V2_EN.md and its companion documents. Zero
third-party dependencies so it runs anywhere Python 3 is available.
"""

from . import constants, derivation, fixtures, report, stats  # noqa: F401

__all__ = ["constants", "derivation", "fixtures", "report", "stats"]
