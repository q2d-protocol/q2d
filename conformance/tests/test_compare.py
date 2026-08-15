"""Comparison behaves as P-001 §4.4 defines it (P-001 issue 16).

    python3 -m unittest discover -s conformance/tests

Most of these are negative: the point of a comparison in this repository is
what it refuses to call equal. Python makes three of those refusals non-obvious
-- `True == 1`, `1 == 1.0`, and dict equality ignoring key order -- and two of
those three would let a divergence pass.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
sys.path.insert(0, str(HARNESS))

import compare  # noqa: E402


class EqualityTest(unittest.TestCase):
    def assert_equal(self, a, b):
        self.assertIsNone(compare.difference(a, b), f"{a!r} should equal {b!r}")

    def assert_differs(self, a, b, because):
        self.assertIsNotNone(compare.difference(a, b), f"called equal: {because}")

    def test_identical_documents(self):
        doc = {"signed": "abc.def.ghi", "routing": {"type": "query", "n": [1, 2]}}
        self.assert_equal(doc, {"routing": {"n": [1, 2], "type": "query"},
                                "signed": "abc.def.ghi"})

    def test_object_key_order_is_irrelevant(self):
        self.assert_equal({"a": 1, "b": 2}, {"b": 2, "a": 1})

    def test_array_order_is_significant(self):
        # permitted_sinks and authorities_consulted are sets whose serialized
        # order must still be reproducible across two implementations.
        self.assert_differs(["a", "b"], ["b", "a"], "arrays differ in order")

    def test_absent_is_not_null(self):
        # The two mean different things in every structure this protocol
        # defines: an omitted optional field is not a field set to null.
        self.assert_differs({"a": 1, "b": None}, {"a": 1}, "b absent vs null")
        self.assert_differs({"a": 1}, {"a": 1, "b": None}, "b null vs absent")

    def test_a_boolean_is_not_an_integer(self):
        # Python says True == 1. JSON does not, and neither may the harness:
        # an implementation returning `true` where the vector expects 1 would
        # otherwise pass.
        self.assert_differs(1, True, "1 vs true")
        self.assert_differs(0, False, "0 vs false")
        self.assert_differs({"ok": True}, {"ok": 1}, "true vs 1 in an object")

    def test_numbers_compare_by_parsed_value(self):
        # §4.4: "numbers compare by parsed value rather than by lexical form".
        # 1 and 1.0 are the same JSON number, and rejecting a runner for its
        # serializer's notation would be the harness disagreeing with the PRD
        # it implements.
        #
        # The ban on floats in signed structures is not weakened: it is
        # serialization.md §1's, enforced by a serializer that errors on a
        # float and by a `message/reject/` vector, which is where it is
        # specified.
        self.assert_equal(1000, 1000.0)
        self.assert_equal(0, 0.0)
        self.assert_differs(1000, 1000.5, "different numeric values")

    def test_no_string_to_number_coercion(self):
        self.assert_differs(1, "1", "1 vs '1'")

    def test_no_case_folding_or_whitespace_normalization(self):
        self.assert_differs("deny", "DENY", "case differs")
        self.assert_differs("sha256:abc", "sha256:abc ", "trailing space")
        self.assert_differs("a b", "a  b", "internal whitespace differs")

    def test_nested_difference_is_found(self):
        a = {"r": {"wire": {"status": "deny", "external_reason": "unavailable"}}}
        b = {"r": {"wire": {"status": "deny", "external_reason": "rate_limited"}}}
        self.assert_differs(a, b, "nested value differs")

    def test_unexpected_field_is_a_difference(self):
        self.assert_differs({"a": 1}, {"a": 1, "extra": 2}, "actual carries more")


class ReportTest(unittest.TestCase):
    def test_the_path_names_where_it_differs(self):
        found = compare.difference(
            {"rejection": {"wire": {"status": "deny"}}},
            {"rejection": {"wire": {"status": "allow"}}})
        self.assertIn("rejection.wire.status", found)
        self.assertIn("'deny'", found)
        self.assertIn("'allow'", found)

    def test_array_index_is_reported(self):
        found = compare.difference(["a", "b", "c"], ["a", "x", "c"])
        self.assertIn("[1]", found)

    def test_type_mismatch_names_both_kinds(self):
        found = compare.difference({"a": 1}, {"a": "1"})
        self.assertIn("number", found)
        self.assertIn("string", found)

    def test_the_first_reported_difference_is_stable(self):
        # Two runs must report the same difference first, or a failing vector
        # reads differently each time it is investigated.
        a = {"z": 1, "a": 2, "m": 3}
        b = {"z": 9, "a": 8, "m": 7}
        self.assertEqual({compare.difference(a, b) for _ in range(20)},
                         {compare.difference(a, b)})
        self.assertIn(".a", compare.difference(a, b))


class ModeTest(unittest.TestCase):
    def test_both_declared_modes_are_accepted(self):
        for mode in compare.MODES:
            with self.subTest(mode=mode):
                self.assertIsNone(compare.compare({"a": 1}, {"a": 1}, mode))
                self.assertIsNotNone(compare.compare({"a": 1}, {"a": 2}, mode))

    def test_an_unknown_mode_raises_rather_than_guessing(self):
        # A vector whose comparison the harness does not understand is one it
        # cannot judge; judging it under a guess is how a determinism
        # requirement gets quietly dropped.
        with self.assertRaises(ValueError):
            compare.compare({"a": 1}, {"a": 1}, "approximate")

    def test_bytes_and_semantic_agree_in_run_mode(self):
        # Not a shortcut: §4.8 makes the byte comparison a cross-implementation
        # assertion, and against an authored expectation there are no
        # transmitted bytes to compare. Recorded as a test so that a later
        # change to one mode has to confront this deliberately.
        for a, b in [({"a": 1}, {"a": 1}), ({"a": 1}, {"a": 2}),
                     (["x"], ["x", "y"]), ("s", "s")]:
            with self.subTest(pair=(a, b)):
                self.assertEqual(compare.compare(a, b, "bytes"),
                                 compare.compare(a, b, "semantic"))


class KindTest(unittest.TestCase):
    def test_json_types_are_kept_apart(self):
        cases = [(None, "null"), (True, "boolean"), (1, "number"),
                 (1.5, "number"), ("s", "string"), ([], "array"), ({}, "object")]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(compare.kind(value), expected)


if __name__ == "__main__":
    unittest.main()
