"""Limits for one recipe-5 sandbox run.

The first five fields are handed to ``wasi-python``; the rest are host-side
guards implemented by this package.  The defaults follow D-010 and the T7.0
spike (§7.4): 10 s, 256 MiB of guest memory, 4 MiB per output stream, no fuel
(a metered compilation costs several seconds and GiB), 256 MiB / 10 000
entries of output, and a 384 MiB kernel file-size cap on POSIX.
"""

from __future__ import annotations

from dataclasses import dataclass

MIB = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    """Resource limits for a single sandbox run."""

    deadline_s: float = 10.0
    memory_bytes: int | None = 256 * MIB
    output_bytes: int | None = 4 * MIB
    fuel: int | None = None

    # Host-side output guards (soft watchdog, plus a hard RLIMIT_FSIZE on POSIX).
    max_out_bytes: int | None = 256 * MIB
    max_out_files: int | None = 10_000
    max_file_bytes: int | None = 384 * MIB

    # How long the parent waits past ``deadline_s`` before killing the worker.
    hard_grace_s: float = 5.0
    # Optional explicit wall-clock kill for the guest run (tests); ``None``
    # means deadline + grace.  A fuel run's metered pre-warm is paid before
    # this clock starts (see ``SandboxRunner.run``).
    hard_wall_s: float | None = None
    poll_s: float = 0.01

    # Collection guard: never hash or report more than this from ``/out``.
    max_collect_bytes: int | None = 256 * MIB
    discard_over_budget: bool = True

    def __post_init__(self) -> None:
        if self.deadline_s is not None and (
                isinstance(self.deadline_s, bool) or self.deadline_s <= 0):
            raise ValueError("deadline_s must be positive or None")
        for name in ("memory_bytes", "output_bytes", "max_out_bytes", "max_out_files",
                     "max_file_bytes", "max_collect_bytes", "fuel"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                                      or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.hard_grace_s < 0:
            raise ValueError("hard_grace_s must be non-negative")
        if self.hard_wall_s is not None and self.hard_wall_s <= 0:
            raise ValueError("hard_wall_s must be positive when set")
        if self.poll_s <= 0:
            raise ValueError("poll_s must be positive")

    def wall_s(self) -> float:
        """How long the parent waits for the guest before killing the worker.

        A fuel run's separate metered compile is paid before this window
        starts, so it is never charged to ``deadline_s``, ``hard_grace_s`` or
        ``hard_wall_s``.
        """
        if self.hard_wall_s is not None:
            return float(self.hard_wall_s)
        return float((self.deadline_s or 0.0) + self.hard_grace_s)
