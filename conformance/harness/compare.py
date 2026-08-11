"""Comparing what a runner produced against what a vector expects.

P-001 §4.4 defines `semantic` as **parse-then-deep-equal**, and only that:

- both sides parsed as JSON and compared as trees -- object key order
  irrelevant, array order **significant**, numbers by parsed value rather than
  lexical form;
- **absent and null are different**, because the two mean different things in
  every structure this protocol defines;
- no coercion of any kind: no string-to-number, no case folding, no whitespace
  normalization inside string values.

Array order is significant because every ordered thing in Q2D is
security-relevant: `permitted_sinks` and `authorities_consulted` are sets whose
serialized order must still be reproducible across two implementations, and a
comparison that ignored order would hide exactly the iteration-order divergence
CLAUDE.md forbids.

## Where `bytes` bites, and where it cannot

`bytes` and `semantic` are compared **the same way in `run` mode**, and that is
not a shortcut. §4.8 defines the byte comparison as a *cross-implementation*
assertion -- "for every `comparison: bytes` vector, both runners produce
identical bytes" -- which is `harness cross` (P-001 issue 9), where two runners'
raw output is available to compare. Against an authored expectation there are no
transmitted bytes to compare: the harness parsed the runner's JSON, and a
number's lexical form is gone with the parse. (Object key order is not -- a
Python parse preserves it -- which is why `cross_vector.py` can and does
compare wire responses without sorting keys. What `run` cannot recover is the
whitespace, escaping, and number notation of the original document.)

What survives parsing is every string, and every value the specification
requires determinism over is a string: a JWS compact serialization, a digest, a
signature. For those, deep equality *is* byte equality. So a `bytes` vector is
compared exactly here and byte-compared in `cross` mode, and the declaration is
what tells `cross` which vectors to hold to that.

The one thing this arrangement cannot catch on its own is a producer emitting
correct values with keys in the wrong order, violating P-002 §4.2's profile.
That is caught where it is visible: P-002's `message/serialize/` vectors compare
the serialized payload, which is a string.
"""

from __future__ import annotations

# Comparison modes a vector may declare (vector.schema.json's `comparison`).
MODES = ("bytes", "semantic")


def kind(value) -> str:
    """The JSON type of a Python value, keeping the distinctions JSON keeps.

    `bool` before the number check matters: in Python `True == 1` and
    `isinstance(True, int)` are both true, and a comparison that inherited that
    would let an implementation return `true` where the vector expects `1`.
    JSON keeps those apart, and §4.4 forbids coercion.

    Integers and floats are one kind, because §4.4 compares numbers by parsed
    value rather than by lexical form.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        # One kind, because §4.4 compares numbers "by parsed value rather than
        # by lexical form": 1 and 1.0 are the same JSON number. Keeping them
        # apart here would reject a conforming runner for its serializer's
        # choice of notation.
        #
        # It does not weaken the ban on floats in signed structures. That is
        # P-002 §4.3's, enforced where it is specified -- the serializer errors
        # on a float, and `message/reject/` carries a vector for it -- rather
        # than by a comparison silently disagreeing with §4.4.
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def difference(expected, actual, path: str = "") -> str | None:
    """The first way `actual` differs from `expected`, or None.

    Returns a description naming the path, so a failing vector says where it
    differs rather than printing two documents and leaving the reader to diff
    them by eye.
    """
    at = path or "(root)"

    if kind(expected) != kind(actual):
        # Also the absent/null case's sibling: null is a kind, so `null` against
        # a string is caught here, and a *missing* field is caught below.
        return f"{at}: expected {kind(expected)}, found {kind(actual)}"

    if isinstance(expected, dict):
        for key in expected:
            if key not in actual:
                return f"{at}.{key}: missing"
        for key in actual:
            if key not in expected:
                return f"{at}.{key}: unexpected"
        # Sorted so two runs of the harness report the same difference first.
        for key in sorted(expected):
            found = difference(expected[key], actual[key], f"{at}.{key}")
            if found:
                return found
        return None

    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{at}: expected {len(expected)} items, found {len(actual)}"
        for index, (want, got) in enumerate(zip(expected, actual)):
            found = difference(want, got, f"{at}[{index}]")
            if found:
                return found
        return None

    if expected != actual:
        return f"{at}: expected {expected!r}, found {actual!r}"

    return None


def equal(expected, actual) -> bool:
    return difference(expected, actual) is None


def compare(expected, actual, mode: str) -> str | None:
    """Compare under a declared mode. Returns a difference, or None.

    An unknown mode raises rather than defaulting: a vector whose comparison the
    harness does not understand is one it cannot judge, and judging it anyway
    under a guess is how a determinism requirement gets quietly dropped
    (P-001 §4.4).
    """
    if mode not in MODES:
        raise ValueError(f"unknown comparison mode {mode!r}; expected one of {MODES}")
    return difference(expected, actual)
