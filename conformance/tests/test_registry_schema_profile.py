"""`scope.md` §4.1's integer rule, which the manifest cannot exercise.

    python3 -m unittest discover -s conformance/tests

`registry/validate.py` is normally checked by running it over
[`registry/manifest.json`](../../registry/manifest.json), which is the right
arrangement for a rule every entry uses. This one is different: **no entry in
the reference manifest carries an integer at all**, so the manifest would pass
whether the check worked or not.

That is not an argument for deferring the rule — [E-37](../../docs/open-escalations.md)
was closed before the first entry needs it precisely because that is the only
moment it costs nothing. It is an argument for testing it here, against schemas
written to break it, since the corpus offers nothing that would.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "registry"))

import validate  # noqa: E402  (after sys.path)


def findings(schema) -> list[str]:
    return sorted(validate.unrepresentable_integer(schema, "s"))


class IntegerRangeTest(unittest.TestCase):
    def test_an_integer_states_both_bounds(self):
        self.assertEqual(len(findings({"type": "integer"})), 2)
        self.assertEqual(len(findings({"type": "integer", "minimum": 0})), 1)
        self.assertEqual(findings({"type": "integer", "minimum": 0, "maximum": 10}), [])

    def test_the_boundaries_themselves_are_admitted(self):
        # A bound *at* the edge conforms; the rule is "within", inclusive. An
        # off-by-one here would refuse the widest schema §4.1 permits.
        self.assertEqual(
            findings({"type": "integer", "minimum": -2**63, "maximum": 2**63 - 1}), [])

    def test_a_bound_outside_the_range_is_refused(self):
        for schema in ({"type": "integer", "minimum": 0, "maximum": 2**63},
                       {"type": "integer", "minimum": -2**63 - 1, "maximum": 0}):
            with self.subTest(schema=schema):
                self.assertEqual(len(findings(schema)), 1)

    def test_an_enum_names_its_values_and_needs_no_range(self):
        # §4.1 states this exemption rather than leaving it to the validator:
        # an `enum` has named the values it admits, so a range beside it would
        # add nothing, and §4.1's release rule already treats `enum` as a
        # complete bound. Review caught the spec text and this check
        # disagreeing about it, which is the drift a registry rule stated in
        # two places produces.
        self.assertEqual(findings({"type": "integer", "enum": [1, 2, 3]}), [])

    def test_an_enum_literal_is_still_checked(self):
        # **The case that separates this rule from the release rule**, where
        # `enum` prunes the walk. A finite set of literals bounds a value's
        # length; it says nothing about whether each literal is representable.
        self.assertEqual(len(findings({"enum": [2**64]})), 1)
        self.assertEqual(len(findings({"type": "integer", "enum": [1, -2**70]})), 1)

    def test_a_boolean_literal_is_not_an_integer(self):
        # In Python `True` is an `int` and `isinstance(True, int)` holds. A
        # check that inherited that would report a boolean enum as an
        # unbounded integer.
        self.assertEqual(findings({"type": "boolean", "enum": [True, False]}), [])

    def test_the_rule_reaches_nested_schemas(self):
        # Where an unrepresentable integer would actually arrive: inside a
        # predicate's `public_context`, several levels down.
        nested = {"type": "object", "properties": {
            "slots": {"type": "array", "items": {"type": "object", "properties": {
                "count": {"type": "integer"}}}}}}
        found = findings(nested)
        self.assertEqual(len(found), 2)
        self.assertTrue(all("slots.items.properties.count" in f for f in found))

    def test_the_reference_manifest_carries_no_integer(self):
        # The premise of this file. If it ever fails, the manifest has grown an
        # integer — good news, and the moment to check that the entry states
        # its range rather than that this test still holds.
        import json
        manifest = json.loads((REPO / "registry" / "manifest.json").read_text("utf-8"))

        def integers(node):
            if isinstance(node, dict):
                if node.get("type") == "integer":
                    yield node
                for value in node.values():
                    yield from integers(value)
            elif isinstance(node, list):
                for item in node:
                    yield from integers(item)

        for entry in manifest["predicates"]:
            for field in ("input_schema", "public_context_schema",
                          "private_input_schema", "output_schema"):
                self.assertEqual(list(integers(entry.get(field, {}))), [],
                                 f"{entry['id']}.{field} now carries an integer")


if __name__ == "__main__":
    unittest.main()
