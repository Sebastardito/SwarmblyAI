"""Strict parsing of the JSON action protocol.

Models without native tool calling answer with exactly one JSON object::

    {"action": "final", "text": "..."}
    {"action": "tool", "tool": "...", "arguments": {...}, "why": "..."}

Anything else is a final answer, not a guessed tool call. That rule is the
point of this module: a malformed answer that *looks* like a tool request must
never become one, because the runtime's next step would then execute a tool
the model did not validly ask for.

Unknown fields are ignored, following the protocol's forward-compatibility
rule (SPEC section 3): they cannot turn one action into another. Known fields
are type-checked, duplicate keys are rejected, and trailing prose or a second
object is an error rather than a parse of the first one.
"""

from __future__ import annotations

import json
from typing import Any

from .types import Action, Final, ToolRequest

__all__ = ["parse_json_action"]


def parse_json_action(text: str) -> Action:
    """Parse one JSON object into a :class:`Final` or :class:`ToolRequest`.

    On any doubt the return value is ``Final`` holding the original text and a
    ``parse_note`` that says what was wrong.
    """
    original = text if isinstance(text, str) else str(text)
    stripped = original.strip()
    if not stripped:
        return _fail(original, "empty response: expected one JSON object")

    try:
        data = json.loads(
            stripped,
            object_pairs_hook=_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return _fail(original, f"not one valid JSON object: {exc}")

    if not isinstance(data, dict):
        return _fail(
            original,
            f"top-level JSON is {type(data).__name__}, expected an object",
        )

    kind = data.get("action")
    if kind == "final":
        answer = data.get("text")
        if not isinstance(answer, str):
            return _fail(original, 'action "final" needs "text" as a string')
        return Final(answer)

    if kind == "tool":
        tool = data.get("tool")
        arguments = data.get("arguments")
        why = data.get("why", "")
        if not isinstance(tool, str) or not tool:
            return _fail(original, 'action "tool" needs a non-empty "tool" string')
        if not isinstance(arguments, dict):
            return _fail(original, 'action "tool" needs "arguments" as an object')
        if not isinstance(why, str):
            return _fail(
                original, 'action "tool" needs "why" as a string when present'
            )
        return ToolRequest(tool=tool, arguments=arguments, why=why)

    if kind is None:
        return _fail(original, 'missing "action"; expected "final" or "tool"')
    return _fail(original, f'unknown action {kind!r}; expected "final" or "tool"')


def _fail(text: str, message: str) -> Final:
    return Final(text, parse_note=f"parse error: {message}")


def _without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys instead of silently keeping the last one.

    ``{"action":"final","text":"a","text":"b"}`` has no single meaning, so it
    is not a valid action.
    """
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def _reject_constant(value: str) -> Any:
    """``NaN`` and ``Infinity`` are not JSON; do not let them through."""
    raise ValueError(f"non-JSON constant {value!r}")
