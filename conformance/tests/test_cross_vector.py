"""Assertions a per-vector check structurally cannot make (P-001 issues 7, 8).

    python3 -m unittest discover -s conformance/tests

Every vector in these fixtures is individually valid. That is the point: the
failure exists only *between* vectors, so a suite of per-case tests would pass
over a corpus that contradicts itself.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONFORMANCE / "harness"))

import lint as lint_module  # noqa: E402

FIXTURES = CONFORMANCE / "tests" / "fixtures"


def lint(corpus: Path) -> tuple[int, str]:
    captured = io.StringIO()
    with redirect_stdout(captured):
        code = lint_module.lint(corpus)
    return code, captured.getvalue()


class DenialUniformityTest(unittest.TestCase):
    """P-001 issue 7, generalizing registry/validate.py's check."""

    def test_two_causes_claiming_one_class_must_be_indistinguishable(self):
        code, output = lint(FIXTURES / "denial-divergent")
        self.assertEqual(code, 1)
        self.assertIn("2 distinct wire responses claim external_reason", output)
        self.assertIn("unavailable", output)

    def test_both_vectors_are_individually_valid(self):
        # The whole reason this assertion exists: neither vector is wrong on
        # its own, so nothing per-case can catch the pair.
        _, output = lint(FIXTURES / "denial-divergent")
        self.assertIn("2/2 vectors valid", output)
        self.assertIn("cross-vector assertion(s) failed", output)

    def test_one_cause_behind_a_class_is_reported_not_failed(self):
        # Because P-009 §4.1's Tier A rejections are deliberately distinct: a
        # malformed envelope and an unknown version tell a requester different
        # things on purpose. Each is one cause under one external value, and
        # nothing in the format says which external values name a *normalized*
        # class -- so failing every single-cause class would reject a correct
        # corpus for containing the tier that exists to be informative.
        code, output = lint(FIXTURES / "denial-thin")
        self.assertEqual(code, 0)
        self.assertIn("with a single cause", output)
        self.assertIn("may simply be Tier A", output)

    def test_key_order_is_part_of_the_bytes(self):
        # Two wire responses with the same fields in a different order are
        # different bytes on the wire, which is the divergence a normalized
        # class must not contain. Sorting keys before comparing would normalise
        # away the thing being checked.
        code, output = lint(FIXTURES / "denial-key-order")
        self.assertEqual(code, 1)
        self.assertIn("distinct wire responses", output)


class BudgetAccumulationTest(unittest.TestCase):
    """P-001 issue 8: a debit sequence and its permutations agree."""

    def test_permutations_must_reach_the_same_total(self):
        code, output = lint(FIXTURES / "budget-divergent")
        self.assertEqual(code, 1)
        self.assertIn("different orders reach 2 different totals", output)

    def test_both_vectors_are_individually_valid(self):
        _, output = lint(FIXTURES / "budget-divergent")
        self.assertIn("2/2 vectors valid", output)


class MalformedInputTest(unittest.TestCase):
    def test_a_vector_of_any_shape_is_reported_not_fatal(self):
        # The assertions run alongside the per-vector checks rather than after
        # them, so they see vectors of every shape. One malformed file must not
        # abort the sweep that was about to report it.
        code, output = lint(FIXTURES / "malformed-shapes")
        self.assertEqual(code, 1)
        self.assertIn("expected object, found string", output)
        self.assertIn("cross-vector", output)


class NotAPermutationTest(unittest.TestCase):
    def test_two_vectors_in_the_same_order_are_not_a_permutation(self):
        # Grouping by multiset brings them together, and they exercise nothing:
        # order-independence needs two orders.
        code, output = lint(FIXTURES / "budget-same-order")
        self.assertEqual(code, 0)
        self.assertIn("0 permutation group(s)", output)
        self.assertIn("no permutation to compare against", output)


class EmptyCorpusTest(unittest.TestCase):
    def test_assertions_over_an_empty_corpus_say_nothing_and_pass(self):
        code, output = lint(FIXTURES / "empty")
        self.assertEqual(code, 0)
        self.assertIn("0 external class(es)", output)
        self.assertIn("0 permutation group(s)", output)


if __name__ == "__main__":
    unittest.main()
