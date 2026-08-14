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


class DeclaredTimestampTest(unittest.TestCase):
    """E-36 in the manifest validator: the schema says which strings are §2.2's.

    This scanned every date-shaped string until E-36 closed — the same rule the
    three serializers carried and lost, in a sixth place, and the one where it
    mattered most: `registry/validate.py` takes a manifest path, so being
    stricter than `scope.md` §4.1 here rejects a **conforming entry** rather
    than tidying our own corpus. That is why `conformance/harness/lint.py`
    keeps its copy and this file does not.
    """

    OFFSET = "2026-07-31T19:30:00+01:00"

    def declared(self, value, schema):
        return sorted(validate.declared_timestamps(value, schema, "v"))

    def test_a_declared_field_is_held_to_2_2(self):
        schema = {"type": "object", "properties": {
            "at": {"type": "string", "format": "date-time"}}}
        found = self.declared({"at": self.OFFSET}, schema)
        self.assertEqual(found, [("v.at", self.OFFSET)])
        self.assertFalse(validate.q2d_timestamp(self.OFFSET))

    def test_an_undeclared_field_is_the_predicate_s_own(self):
        # The booking case E-36 was raised about. A predicate declaring a
        # bounded string carries the offset, and the offset is the local time
        # the requester meant — which `Z` does not record.
        schema = {"type": "object", "properties": {
            "booked_for": {"type": "string", "maxLength": 40}}}
        self.assertEqual(self.declared({"booked_for": self.OFFSET}, schema), [])

    def test_the_walk_follows_arrays_and_nesting(self):
        # Where the reference manifest's own timestamps live:
        # `candidates[].start` under `availability_window`.
        schema = {"type": "object", "properties": {
            "candidates": {"type": "array", "items": {
                "type": "object", "properties": {
                    "start": {"type": "string", "format": "date-time"}}}}}}
        found = self.declared({"candidates": [{"start": self.OFFSET}]}, schema)
        self.assertEqual(found, [("v.candidates[0].start", self.OFFSET)])

    def test_a_value_with_no_matching_subschema_is_not_reached(self):
        # §4.1 requires `additionalProperties: false`, so a field with no
        # subschema is already a registry error caught elsewhere. This walk
        # must not also guess at it.
        schema = {"type": "object", "properties": {}}
        self.assertEqual(self.declared({"stray": self.OFFSET}, schema), [])

    def test_the_manifest_s_declared_timestamps_are_all_found(self):
        import json
        manifest = json.loads((REPO / "registry" / "manifest.json").read_text("utf-8"))
        found = list(validate.entry_timestamps(manifest))
        self.assertEqual(len(found), 36)
        self.assertTrue(all(validate.q2d_timestamp(value) for _, value in found))


class RequesterStringBoundTest(unittest.TestCase):
    """`scope.md` §4.1's second boundedness rule — E-40's other half.

    `core-model.md` §2.8's 2 KiB string limit stops at
    `predicate.public_context`, so a predicate's own text is bounded by its
    entry or by nothing but the 32 KiB whole-object limit. This is the check
    that makes "or by its entry" true.

    The reference manifest bounds every string it admits, so as with the
    integer rule the negative cases live here.
    """

    def findings(self, schema):
        return sorted(validate.unbounded_request_string(schema, "s"))

    def test_a_string_states_a_max_length(self):
        self.assertEqual(len(self.findings({"type": "string"})), 1)
        self.assertEqual(self.findings({"type": "string", "maxLength": 64}), [])

    def test_a_timestamp_is_bounded_by_its_spelling(self):
        # §2.2 fixes twenty characters, so `maxLength` would add nothing.
        self.assertEqual(self.findings({"type": "string", "format": "date-time"}), [])

    def test_an_enum_bounds_every_string_in_it(self):
        self.assertEqual(self.findings({"type": "string", "enum": ["a", "bb"]}), [])

    def test_a_subschema_with_no_type_is_refused(self):
        # It admits a string among everything else and bounds none of them, so
        # a `maxLength` test alone would never fire on it — the gap review
        # found in the first version of this rule.
        self.assertEqual(len(self.findings({"properties": {"a": {}}})), 1)

    def test_the_rule_reaches_nested_schemas(self):
        nested = {"type": "object", "properties": {
            "menu": {"type": "array", "items": {"type": "object", "properties": {
                "note": {"type": "string"}}}}}}
        found = self.findings(nested)
        self.assertEqual(len(found), 1)
        self.assertIn("menu.items.properties.note", found[0])

    def test_the_manifest_bounds_every_string_a_requester_may_send(self):
        import json
        manifest = json.loads((REPO / "registry" / "manifest.json").read_text("utf-8"))
        for entry in manifest["predicates"]:
            for field in ("public_context_schema", "input_schema"):
                if field in entry:
                    self.assertEqual(
                        self.findings(entry[field]), [],
                        f"{entry['id']}.{field}")

    def test_private_input_is_not_reached(self):
        # A requester cannot send it, so it is not attacker-controlled. The
        # manifest's one unbounded string lives there, which is why the check
        # above passes.
        import json
        manifest = json.loads((REPO / "registry" / "manifest.json").read_text("utf-8"))
        unbounded = [
            entry["id"] for entry in manifest["predicates"]
            if self.findings(entry.get("private_input_schema", {}))
        ]
        self.assertTrue(unbounded, "if this ever empties, the exclusion is untested")


if __name__ == "__main__":
    unittest.main()
