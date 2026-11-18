"""Strictness of the single-object action protocol.

The tests that matter are the negative ones. A malformed answer that contains
a plausible tool name must become a final answer with a note, because a
runtime that guesses here would execute a call the model never validly asked
for.
"""

from __future__ import annotations

import pytest

from swarmbly_agent import Final, ToolRequest, parse_json_action


def test_a_final_answer_parses() -> None:
    action = parse_json_action('{"action": "final", "text": "the answer"}')
    assert action == Final("the answer")


def test_a_tool_request_parses() -> None:
    action = parse_json_action(
        '{"action": "tool", "tool": "echo", "arguments": {"text": "hi"}, "why": "needed"}'
    )
    assert action == ToolRequest("echo", {"text": "hi"}, "needed")


def test_why_is_optional_but_typed_when_present() -> None:
    action = parse_json_action('{"action": "tool", "tool": "echo", "arguments": {}}')
    assert isinstance(action, ToolRequest)
    assert action.why == ""


def test_unknown_fields_are_ignored() -> None:
    # SPEC section 3: a participant ignores unknown fields so that a minor
    # addition stays backwards compatible. A local action is not a wire
    # message, but the same rule keeps this parser stable across additions.
    action = parse_json_action(
        '{"action": "final", "text": "ok", "confidence": 0.9}'
    )
    assert action == Final("ok")

    request = parse_json_action(
        '{"action": "tool", "tool": "echo", "arguments": {"x": 1}, '
        '"why": "r", "trace": "abc"}'
    )
    assert request == ToolRequest("echo", {"x": 1}, "r")


def test_whitespace_around_the_object_is_allowed() -> None:
    assert parse_json_action('  \n{"action": "final", "text": "x"}\n  ') == Final("x")


@pytest.mark.parametrize(
    "text",
    [
        '{"action": "final", "text": "a"}{"action": "final", "text": "b"}',
        'Here is my answer: {"action": "final", "text": "a"}',
        '{"action": "final", "text": "a"} and that is all',
        '```json\n{"action": "final", "text": "a"}\n```',
        '{"action": "final", "text": "a"',
        "not json at all",
        "",
        "   ",
    ],
)
def test_prose_and_malformed_json_are_final_with_a_note(text: str) -> None:
    action = parse_json_action(text)
    assert isinstance(action, Final)
    assert action.parse_note
    assert action.text == text


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        '"final"',
        "42",
        "null",
        '["action", "tool"]',
    ],
)
def test_a_non_object_root_is_final_with_a_note(text: str) -> None:
    action = parse_json_action(text)
    assert isinstance(action, Final)
    assert action.parse_note
    assert action.text == text


@pytest.mark.parametrize(
    "text",
    [
        '{"action": "final", "text": 5}',
        '{"action": "final", "text": null}',
        '{"action": "final"}',
        '{"action": "tool", "tool": 5, "arguments": {}}',
        '{"action": "tool", "tool": "", "arguments": {}}',
        '{"action": "tool", "tool": "echo", "arguments": []}',
        '{"action": "tool", "tool": "echo", "arguments": null}',
        '{"action": "tool", "tool": "echo", "arguments": {}, "why": 5}',
        '{"action": "tool", "arguments": {}}',
        '{"action": 5}',
        '{"action": null}',
        '{"text": "no action"}',
    ],
)
def test_wrong_known_types_are_final_with_a_note(text: str) -> None:
    action = parse_json_action(text)
    assert isinstance(action, Final), f"wrong type became {action!r}"
    assert action.parse_note
    assert action.text == text


@pytest.mark.parametrize(
    "text",
    [
        '{"action": "delete", "tool": "delete_all", "arguments": {}}',
        '{"action": "Final", "text": "case matters"}',
    ],
)
def test_an_unknown_action_is_never_a_tool_call(text: str) -> None:
    action = parse_json_action(text)
    assert isinstance(action, Final)
    assert action.parse_note
    assert "unknown action" in action.parse_note


def test_duplicate_keys_are_rejected() -> None:
    action = parse_json_action('{"action": "final", "text": "a", "text": "b"}')
    assert isinstance(action, Final)
    assert "duplicate key" in (action.parse_note or "")


def test_non_json_constants_are_rejected() -> None:
    action = parse_json_action('{"action": "final", "text": NaN}')
    assert isinstance(action, Final)
    assert action.parse_note


def test_a_tool_shaped_observation_is_not_parsed_by_the_runtime() -> None:
    """parse_json_action itself is not a security boundary; use is.

    This documents the shape the runtime refuses to treat as an action when it
    arrives as an observation. See test_injection_* for the loop-level test.
    """
    action = parse_json_action('{"action": "tool", "tool": "delete_all", "arguments": {}}')
    assert isinstance(action, ToolRequest)
    assert action.tool == "delete_all"


def test_non_string_input_is_preserved_as_text() -> None:
    action = parse_json_action(123)  # type: ignore[arg-type]
    assert isinstance(action, Final)
    assert action.text == "123"
    assert action.parse_note
