"""The small, strict JSON-Schema subset accepted for tool arguments.

There is deliberately no ``jsonschema`` dependency. Tool specs are data that
can arrive from a remote source, so an unsupported keyword is refused instead
of ignored: a tool may not rely on ``pattern``, ``oneOf``, ``$ref`` or any
other check this module does not enforce.

Accepted keywords::

    type, properties, required, additionalProperties, enum,
    minLength, maxLength, minimum, maximum, items, maxItems

Only a single ``type`` is accepted (``object``, ``string``, ``number``,
``integer``, ``boolean``, ``array`` or ``null``). ``additionalProperties``
defaults to **false** for every object in a tool spec; a remote schema cannot
silently accept fields its author did not declare. Arrays must declare
``items``. The root schema is an object because a tool call's arguments are a
JSON object.

``canonical_json`` is shared with the approval hash and the one-time token
binding: the same arguments always produce the same bytes, and values that
cannot be represented as JSON (NaN, infinity, bytes, …) are rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

TYPES = frozenset({"object", "string", "number", "integer", "boolean", "array", "null"})
KEYWORDS = frozenset({
    "type", "properties", "required", "additionalProperties", "enum",
    "minLength", "maxLength", "minimum", "maximum", "items", "maxItems",
})


class SchemaError(ValueError):
    """A tool schema or a set of arguments is outside the accepted subset."""


def canonical_json(value: Any) -> str:
    """Deterministic JSON used by hashes and token bindings."""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"value is not canonical JSON: {exc}") from exc


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(value)


def _matches_type(value: Any, kind: str) -> bool:
    if kind == "object":
        return isinstance(value, dict)
    if kind == "string":
        return isinstance(value, str)
    if kind == "number":
        return _is_number(value)
    if kind == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or \
            (isinstance(value, float) and value.is_integer())
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "null":
        return value is None
    return False


def _ensure_json(value: Any, path: str) -> None:
    """Reject values that JSON (and therefore a token binding) cannot carry."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SchemaError(f"{path}: non-finite number")
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _ensure_json(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SchemaError(f"{path}: object keys must be strings")
            _ensure_json(item, f"{path}.{key}")
        return
    raise SchemaError(f"{path}: {type(value).__name__} is not JSON")


def _non_negative_int(value: Any, keyword: str, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchemaError(f"{path}: {keyword} must be a non-negative integer")
    return value


def _bound(value: Any, keyword: str, path: str) -> int | float:
    if not _is_number(value):
        raise SchemaError(f"{path}: {keyword} must be a finite number")
    return value


def validate_schema(schema: Any, path: str = "$", *, root: bool = False) -> dict[str, Any]:
    """Validate and normalise a schema, returning a fresh dict.

    ``additionalProperties`` is added as ``False`` for objects when absent.
    The root may be an empty dict, meaning an object with no arguments.
    """
    if not isinstance(schema, dict):
        raise SchemaError(f"{path}: schema must be an object")
    if root and not schema:
        schema = {"type": "object"}
    unknown = sorted(set(schema) - KEYWORDS)
    if unknown:
        raise SchemaError(
            f"{path}: unsupported schema keyword(s): {', '.join(unknown)}; "
            f"accepted: {', '.join(sorted(KEYWORDS))}")
    kind = schema.get("type")
    if not isinstance(kind, str) or kind not in TYPES:
        raise SchemaError(f"{path}: type must be one of {', '.join(sorted(TYPES))}")
    if root and kind != "object":
        raise SchemaError(f"{path}: the root schema must be an object")
    out: dict[str, Any] = {"type": kind}

    enum = schema.get("enum")
    if enum is not None:
        if not isinstance(enum, list) or not enum:
            raise SchemaError(f"{path}: enum must be a non-empty list")
        seen: set[str] = set()
        for i, item in enumerate(enum):
            _ensure_json(item, f"{path}.enum[{i}]")
            if not _matches_type(item, kind):
                raise SchemaError(f"{path}.enum[{i}]: value does not match type {kind!r}")
            key = canonical_json(item)
            if key in seen:
                raise SchemaError(f"{path}.enum: duplicate value {item!r}")
            seen.add(key)
        out["enum"] = list(enum)

    if kind == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise SchemaError(f"{path}: properties must be an object")
        normalised: dict[str, Any] = {}
        for name, sub in properties.items():
            if not isinstance(name, str) or not name:
                raise SchemaError(f"{path}: property names must be non-empty strings")
            normalised[name] = validate_schema(sub, f"{path}.properties.{name}")
        out["properties"] = normalised
        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
            raise SchemaError(f"{path}: required must be a list of strings")
        if len(set(required)) != len(required):
            raise SchemaError(f"{path}: required contains duplicates")
        missing = sorted(set(required) - set(normalised))
        if missing:
            raise SchemaError(f"{path}: required names not in properties: {', '.join(missing)}")
        out["required"] = list(required)
        additional = schema.get("additionalProperties", False)
        if not isinstance(additional, bool):
            raise SchemaError(f"{path}: additionalProperties must be true or false")
        out["additionalProperties"] = additional
        for keyword in ("minLength", "maxLength", "minimum", "maximum", "items", "maxItems"):
            if keyword in schema:
                raise SchemaError(f"{path}: {keyword} does not apply to an object")

    elif kind == "string":
        for keyword in ("properties", "required", "additionalProperties", "items", "maxItems",
                        "minimum", "maximum"):
            if keyword in schema:
                raise SchemaError(f"{path}: {keyword} does not apply to a string")
        if "minLength" in schema:
            out["minLength"] = _non_negative_int(schema["minLength"], "minLength", path)
        if "maxLength" in schema:
            out["maxLength"] = _non_negative_int(schema["maxLength"], "maxLength", path)
        if out.get("minLength", 0) > out.get("maxLength", float("inf")):
            raise SchemaError(f"{path}: minLength is greater than maxLength")

    elif kind in ("number", "integer"):
        for keyword in ("properties", "required", "additionalProperties", "items", "maxItems",
                        "minLength", "maxLength"):
            if keyword in schema:
                raise SchemaError(f"{path}: {keyword} does not apply to a {kind}")
        if "minimum" in schema:
            out["minimum"] = _bound(schema["minimum"], "minimum", path)
        if "maximum" in schema:
            out["maximum"] = _bound(schema["maximum"], "maximum", path)
        if out.get("minimum", float("-inf")) > out.get("maximum", float("inf")):
            raise SchemaError(f"{path}: minimum is greater than maximum")

    elif kind == "array":
        for keyword in ("properties", "required", "additionalProperties", "minLength",
                        "maxLength", "minimum", "maximum"):
            if keyword in schema:
                raise SchemaError(f"{path}: {keyword} does not apply to an array")
        if "items" not in schema:
            raise SchemaError(f"{path}: an array schema must declare items")
        out["items"] = validate_schema(schema["items"], f"{path}.items")
        if "maxItems" in schema:
            out["maxItems"] = _non_negative_int(schema["maxItems"], "maxItems", path)

    else:  # boolean or null
        for keyword in ("properties", "required", "additionalProperties", "items", "maxItems",
                        "minLength", "maxLength", "minimum", "maximum"):
            if keyword in schema:
                raise SchemaError(f"{path}: {keyword} does not apply to a {kind}")

    return out


def _validate(value: Any, schema: dict[str, Any], path: str) -> None:
    kind = schema["type"]
    if not _matches_type(value, kind):
        raise SchemaError(f"{path}: expected {kind}, got {type(value).__name__}")
    if "enum" in schema:
        allowed = {canonical_json(item) for item in schema["enum"]}
        if canonical_json(value) not in allowed:
            raise SchemaError(f"{path}: value is not in enum")
    if kind == "object":
        for name in schema["required"]:
            if name not in value:
                raise SchemaError(f"{path}: missing required property {name!r}")
        properties = schema["properties"]
        for name, item in value.items():
            if name in properties:
                _validate(item, properties[name], f"{path}.{name}")
            elif not schema["additionalProperties"]:
                raise SchemaError(f"{path}: additional property {name!r} is not allowed")
            else:
                _ensure_json(item, f"{path}.{name}")
    elif kind == "string":
        length = len(value)
        if length < schema.get("minLength", 0):
            raise SchemaError(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and length > schema["maxLength"]:
            raise SchemaError(f"{path}: longer than maxLength {schema['maxLength']}")
    elif kind in ("number", "integer"):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(f"{path}: above maximum {schema['maximum']}")
    elif kind == "array":
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaError(f"{path}: more than maxItems {schema['maxItems']}")
        for i, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{i}]")


def validate_arguments(schema: dict[str, Any], arguments: Any) -> None:
    """Raise :class:`SchemaError` unless ``arguments`` matches ``schema``.

    A raw (not yet normalised) schema is accepted too; it is validated with
    the same defaults the broker uses.
    """
    if not isinstance(schema, dict):
        raise SchemaError("tool input schema must be an object")
    normalised = validate_schema(schema, root=True)
    if not isinstance(arguments, dict):
        raise SchemaError("arguments must be an object")
    _ensure_json(arguments, "arguments")
    _validate(arguments, normalised, "arguments")
