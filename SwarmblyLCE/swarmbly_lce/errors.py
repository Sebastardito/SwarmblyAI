"""Error types and the capsule error codes of SPEC section 18."""

from __future__ import annotations

from enum import Enum


class LCEError(Exception):
    """Base class for every error raised by swarmbly_lce."""


class InvariantViolation(LCEError):
    """An operation would break one of the invariants I1–I8 (SPEC 4.2).

    These are programming or configuration errors, not runtime conditions to
    recover from: a conformant implementation must never reach them.
    """

    def __init__(self, invariant: str, message: str) -> None:
        self.invariant = invariant
        super().__init__(f"[{invariant}] {message}")


class PolicyError(LCEError):
    """Malformed learning policy."""


class TransitionError(LCEError):
    """A maturity transition whose normative condition does not hold (SPEC 6.5)."""


class CycleError(LCEError):
    """The dependency graph would stop being acyclic (SPEC 6.7)."""


class CryptoUnavailable(LCEError):
    """Ed25519 operations requested but the ``cryptography`` package is missing."""


class CapsuleCode(str, Enum):
    """Capsule error codes (SWIP section 13 plus SPEC section 18)."""

    COGNITIVE_DISABLED = "E_COGNITIVE_DISABLED"
    NOT_FOUND = "E_CAPSULE_NOT_FOUND"
    FORBIDDEN = "E_CAPSULE_FORBIDDEN"
    TOO_LARGE = "E_CAPSULE_TOO_LARGE"
    RATE_LIMITED = "E_CAPSULE_RATE_LIMITED"
    BAD_SIGNATURE = "E_CAPSULE_BAD_SIGNATURE"
    UNSUPPORTED = "E_CAPSULE_UNSUPPORTED"
    DISTANCE = "E_CAPSULE_DISTANCE"
    NO_DELTA = "E_CAPSULE_NO_DELTA"


class CapsuleError(LCEError):
    """A capsule failed validation; ``code`` is the wire error code."""

    def __init__(self, code: CapsuleCode, message: str) -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}")
