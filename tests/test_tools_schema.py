"""The strict schema subset used by tool specs."""

from __future__ import annotations

import math

import pytest

from swarmbly_app.tools.schema import (SchemaError, canonical_json,
                                       validate_arguments, validate_schema)


def test_valid_nested_schema_and_arguments():
    schema = validate_schema({
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 2, "maxLength": 10},
            "count": {"type": "integer", "minimum": 1, "maximum": 5},
            "ratio": {"type": "number", "minimum": 0, "maximum": 1},
            "mode": {"type": "string", "enum": ["fast", "safe"]},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
            "nested": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
            "nothing": {"type": "null"},
        },
        "required": ["name", "count"],
    }, root=True)
    validate_arguments(schema, {
        "name": "Ada", "count": 2, "ratio": 0.5, "mode": "safe",
        "tags": ["a", "b"], "nested": {"ok": True}, "nothing": None,
    })


def test_additional_properties_defaults_to_false():
    schema = validate_schema({"type": "object", "properties": {"x": {"type": "string"}}})
    assert schema["additionalProperties"] is False
    with pytest.raises(SchemaError, match="additional property"):
        validate_arguments(schema, {"x": "a", "y": "b"})


def test_required_and_types_are_enforced():
    schema = validate_schema({"type": "object", "properties": {
        "x": {"type": "string"}, "n": {"type": "integer"}},
        "required": ["x"]})
    with pytest.raises(SchemaError, match="missing required"):
        validate_arguments(schema, {"n": 1})
    with pytest.raises(SchemaError, match="expected integer"):
        validate_arguments(schema, {"x": "a", "n": 1.5})
    with pytest.raises(SchemaError, match="expected string"):
        validate_arguments(schema, {"x": 1})


@pytest.mark.parametrize("value,message", [
    ("a", "shorter than minLength"),
    ("abcdef", "longer than maxLength"),
])
def test_string_length_bounds(value, message):
    schema = validate_schema({"type": "object", "properties": {
        "x": {"type": "string", "minLength": 2, "maxLength": 5}}})
    with pytest.raises(SchemaError, match=message):
        validate_arguments(schema, {"x": value})


@pytest.mark.parametrize("value,message", [
    (0, "below minimum"), (11, "above maximum"),
])
def test_number_bounds(value, message):
    schema = validate_schema({"type": "object", "properties": {
        "x": {"type": "number", "minimum": 1, "maximum": 10}}})
    with pytest.raises(SchemaError, match=message):
        validate_arguments(schema, {"x": value})


def test_enum_and_array_bounds():
    schema = validate_schema({"type": "object", "properties": {
        "x": {"type": "string", "enum": ["a", "b"]},
        "xs": {"type": "array", "items": {"type": "integer"}, "maxItems": 2}}})
    with pytest.raises(SchemaError, match="not in enum"):
        validate_arguments(schema, {"x": "c"})
    with pytest.raises(SchemaError, match="maxItems"):
        validate_arguments(schema, {"xs": [1, 2, 3]})


def test_unsupported_keywords_are_refused():
    with pytest.raises(SchemaError, match="unsupported schema keyword"):
        validate_schema({"type": "object", "properties": {
            "x": {"type": "string", "pattern": ".*"}}})
    with pytest.raises(SchemaError, match="unsupported schema keyword"):
        validate_schema({"type": "object", "oneOf": []})


@pytest.mark.parametrize("schema", [
    {"type": ["string", "null"]},
    {"type": "array"},
    {"type": "object", "required": ["x"]},
    {"type": "object", "additionalProperties": {"type": "string"}},
    {"type": "string", "minLength": 5, "maxLength": 1},
    {"type": "number", "minimum": 2, "maximum": 1},
])
def test_invalid_schema_shapes_are_refused(schema):
    with pytest.raises(SchemaError):
        validate_schema(schema, root=True)


def test_canonical_json_is_stable_and_rejects_non_json():
    assert canonical_json({"b": 1, "a": [2, True]}) == '{"a":[2,true],"b":1}'
    with pytest.raises(SchemaError, match="canonical JSON"):
        canonical_json({"x": math.nan})
    with pytest.raises(SchemaError, match="is not JSON"):
        validate_arguments(validate_schema({"type": "object"}), {"x": b"bytes"})
