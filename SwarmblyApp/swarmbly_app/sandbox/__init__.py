"""Recipe 5 sandbox: WebAssembly CPython in a disposable worker.

This package is importable without the optional ``[sandbox]`` extra.  The only
module that imports ``wasi_python`` is :mod:`swarmbly_app.sandbox.worker`, and
it does so inside a child process; ``available()`` reports whether the extra is
present so the rest of the app (and recipe 5) can degrade to "unavailable"
without failing at import time.

Public surface:

* :class:`SandboxRunner` / :meth:`SandboxRunner.run` / :class:`RunResult`
* :class:`Limits` (10 s, 256 MiB, 4 MiB, 256 MiB / 10 000 files by default)
* :func:`available`, :meth:`SandboxRunner.warm_up`
* :func:`register_tool` for the broker's ``sandbox/python`` spec
"""

from __future__ import annotations

from .limits import Limits
from .runner import RunResult, SandboxError, SandboxRunner, available
from .tool import TOOL_ID, input_schema, register as register_tool, tool_spec

__all__ = [
    "Limits",
    "RunResult",
    "SandboxError",
    "SandboxRunner",
    "TOOL_ID",
    "available",
    "input_schema",
    "register_tool",
    "tool_spec",
]
