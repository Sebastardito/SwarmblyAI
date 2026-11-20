"""The broker registration for recipe 5: ``sandbox/python``.

The tool is local (nothing leaves the computer).  The broker still requires a
one-time token because its provider kind is ``sandbox``; the handler receives
the consumed token's approval reference and passes it to the runner.  Inputs
must be files inside the *current project folder*, checked after resolving
every symlink (realpath), and are never sent anywhere.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
from typing import Any, Callable

from ..tools.broker import ToolCall, ToolContext, ToolSpec
from .limits import Limits
from .runner import SandboxRunner

TOOL_ID = "sandbox/python"
SCRIPT_MAX = 20_000
INPUTS_MAX = 20
INPUT_PATH_MAX = 1_000


def input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "script": {"type": "string", "maxLength": SCRIPT_MAX},
            "inputs": {
                "type": "array",
                "maxItems": INPUTS_MAX,
                "items": {"type": "string", "maxLength": INPUT_PATH_MAX},
            },
        },
        "required": ["script"],
    }


def tool_spec() -> ToolSpec:
    return ToolSpec(
        TOOL_ID,
        kind="sandbox",
        destination="local",
        input_schema=input_schema(),
        description=(
            "Run a Python script (pandas/openpyxl available) with the selected "
            "project files copied read-only to /data and write the result to /out."
        ),
    )


def _project_root(project_path: Callable[[str], Path | None] | None,
                  project_id: str) -> Path:
    if project_path is None:
        raise ValueError("sandbox/python needs a project resolver")
    root = project_path(project_id)
    if root is None:
        raise ValueError("sandbox/python needs an open project folder")
    resolved = Path(root).expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError(f"project folder is not a directory: {resolved}")
    return resolved


def _resolve_inputs(inputs: Any, root: Path) -> list[Path]:
    if inputs is None:
        return []
    if not isinstance(inputs, list):
        raise ValueError("inputs must be a list of project-relative paths")
    paths: list[Path] = []
    for raw in inputs:
        if not isinstance(raw, str) or not raw:
            raise ValueError("each input must be a non-empty project-relative path")
        if "\x00" in raw:
            raise ValueError("input path contains a NUL byte")
        windows = PureWindowsPath(raw)
        if Path(raw).is_absolute() or windows.is_absolute() or windows.drive:
            raise ValueError(f"input {raw!r} is not project-relative")
        parts = raw.replace("\\", "/").split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise ValueError(f"input {raw!r} is not a clean project-relative path")
        try:
            candidate = (root / raw).resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"input {raw!r} cannot be read: {exc}") from exc
        if not candidate.is_relative_to(root):
            raise ValueError(f"input {raw!r} resolves outside the project folder")
        if not candidate.is_file():
            raise ValueError(f"input {raw!r} is not a regular file")
        paths.append(candidate)
    return paths


def make_handler(runner: SandboxRunner,
                 project_path: Callable[[str], Path | None],
                 *, keep_output: bool = False) -> Callable[
                     [ToolCall, ToolContext], dict[str, Any]]:
    """Return a broker handler bound to one runner and project resolver."""

    def handler(call: ToolCall, ctx: ToolContext) -> dict[str, Any]:
        arguments = call.arguments
        script = arguments.get("script")
        if not isinstance(script, str) or not script:
            raise ValueError("script must be a non-empty string")
        if len(script) > SCRIPT_MAX:
            raise ValueError(f"script exceeds {SCRIPT_MAX} characters")
        root = _project_root(project_path, call.project_id)
        inputs = _resolve_inputs(arguments.get("inputs") or [], root)
        result = runner.run(script, inputs, Limits(), approval=ctx.approved_by,
                            keep_output=keep_output)
        payload = result.as_dict()
        # The absolute output path stays server-side; the UI/download route
        # addresses a run by its opaque id.
        payload.pop("output_dir", None)
        payload["approval"] = ctx.approved_by
        payload["inputs"] = [path.name for path in inputs]
        return payload

    return handler


def register(broker: Any, *, project_path: Callable[[str], Path | None],
             runner: SandboxRunner | None = None,
             keep_output: bool = False) -> ToolSpec:
    """Register ``sandbox/python`` on a broker; return the spec that was approved.

    The caller still has to call ``broker.approve(spec.id, project_id)`` and
    issue a one-time token per call; registration grants nothing.
    """
    spec = tool_spec()
    backend = runner if runner is not None else SandboxRunner()
    broker.register(spec, make_handler(backend, project_path, keep_output=keep_output))
    return spec

