"""A JSON Schema validator covering exactly the keywords the vector schema uses.

Not a general implementation, and deliberately not one. Two properties matter:

  1. It is standard library only, so `python3 conformance/harness lint` runs
     wherever `python3 registry/validate.py` already runs.
  2. It refuses to validate against a schema using a keyword it does not
     implement. A validator that skipped unknown keywords would let the schema
     state a constraint nothing enforced -- the schema would say one thing and
     the linter check another, which is the failure the schema exists to avoid.

Adding a keyword to the vector schema therefore means adding it here, and the
error tells you so.
"""

from __future__ import annotations

import re

# Keywords with no validation effect: they document, they do not constrain.
ANNOTATIONS = frozenset({"$schema", "$id", "title", "description"})

ASSERTIONS = frozenset({
    "type", "enum", "const",
    "properties", "required", "additionalProperties",
    "items", "minItems", "maxItems",
    "minLength", "maxLength",
    "minimum", "maximum",
    "pattern",
    "oneOf",
})

SUPPORTED = ANNOTATIONS | ASSERTIONS


class UnsupportedKeyword(Exception):
    """The schema uses a keyword this validator does not implement."""


def assert_supported(schema: dict, where: str = "#") -> None:
    """Walk a schema and raise on the first keyword we cannot enforce."""
    if not isinstance(schema, dict):
        raise UnsupportedKeyword(f"{where}: schema must be an object")

    for key in schema:
        if key not in SUPPORTED:
            raise UnsupportedKeyword(
                f"{where}: unsupported keyword {key!r}. "
                f"Implement it in conformance/harness/schema.py or drop it from the schema."
            )

    for name, sub in schema.get("properties", {}).items():
        assert_supported(sub, f"{where}/properties/{name}")
    if isinstance(schema.get("items"), dict):
        assert_supported(schema["items"], f"{where}/items")
    if isinstance(schema.get("additionalProperties"), dict):
        assert_supported(schema["additionalProperties"], f"{where}/additionalProperties")
    for i, sub in enumerate(schema.get("oneOf", [])):
        assert_supported(sub, f"{where}/oneOf/{i}")


def _type_ok(value, want: str) -> bool:
    if want == "object":
        return isinstance(value, dict)
    if want == "array":
        return isinstance(value, list)
    if want == "string":
        return isinstance(value, str)
    if want == "integer":
        # bool is a subclass of int in Python and is not an integer here.
        return isinstance(value, int) and not isinstance(value, bool)
    if want == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if want == "boolean":
        return isinstance(value, bool)
    if want == "null":
        return value is None
    raise UnsupportedKeyword(f"unsupported type {want!r}")


def _name(value) -> str:
    return {
        dict: "object", list: "array", str: "string",
        bool: "boolean", int: "integer", float: "number",
    }.get(type(value), "null" if value is None else type(value).__name__)


def validate(instance, schema: dict, where: str = "") -> list[str]:
    """Return every way `instance` fails `schema`. Empty list means valid."""
    errors: list[str] = []
    at = where or "(root)"

    if "type" in schema and not _type_ok(instance, schema["type"]):
        # A wrong type makes every other assertion noise; stop at this level.
        return [f"{at}: expected {schema['type']}, found {_name(instance)}"]

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{at}: expected {schema['const']!r}, found {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        allowed = ", ".join(repr(v) for v in schema["enum"])
        errors.append(f"{at}: {instance!r} is not one of [{allowed}]")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{at}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{at}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{at}: {instance!r} does not match {schema['pattern']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{at}: below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{at}: above maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{at}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{at}: more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(instance):
                errors += validate(item, schema["items"], f"{at}[{i}]")

    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                errors.append(f"{at}: missing required field {name!r}")

        properties = schema.get("properties", {})
        for name, sub in properties.items():
            if name in instance:
                errors += validate(instance[name], sub, f"{at}.{name}")

        extra = sorted(set(instance) - set(properties))
        if schema.get("additionalProperties") is False and extra:
            errors.append(f"{at}: unexpected field(s) {', '.join(repr(e) for e in extra)}")
        elif isinstance(schema.get("additionalProperties"), dict):
            for name in extra:
                errors += validate(instance[name], schema["additionalProperties"], f"{at}.{name}")

    if "oneOf" in schema:
        branches = [validate(instance, sub, at) for sub in schema["oneOf"]]
        matched = [i for i, errs in enumerate(branches) if not errs]
        if len(matched) != 1:
            errors.append(_one_of_error(at, schema["oneOf"], branches, matched))

    return errors


def _one_of_error(at: str, subschemas: list[dict], branches: list[list[str]],
                  matched: list[int]) -> str:
    if len(matched) > 1:
        return f"{at}: matches more than one alternative; the schema is ambiguous"
    # Report the branch that came closest rather than every branch's complaints:
    # for a two-shape union, the nearest miss is almost always the intended one.
    closest = min(range(len(branches)), key=lambda i: len(branches[i]))
    label = subschemas[closest].get("description", f"alternative {closest}")
    return f"{at}: matches no alternative. Closest ({label}): " + "; ".join(branches[closest])
