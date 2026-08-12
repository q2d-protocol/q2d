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


class PartialResponseTest(unittest.TestCase):
    """A comparison over part of a response is reported as one.

    core-model.md §5.2's deny response is four fields, and the two every corpus
    vector currently asserts -- `status` and `external_reason` -- are both fixed
    by the normalized class. So comparing them compares two constants and cannot
    fail, and a summary that said "1 external class, 5 vectors" and stopped
    would read as evidence of uniformity while proving nothing about it.

    §5.3 puts the leak exactly where the vectors are silent: *"a receipt that
    recorded escalate for an outcome the wire made uniform would defeat
    Q2D-C-08 through the evidence attached to it, in the one place nobody looks
    for a normalization leak."*
    """

    def test_a_partial_wire_is_named_in_the_summary(self):
        _, output = lint(FIXTURES / "denial-thin")
        self.assertIn("compared a partial response", output)
        self.assertIn("receipt", output)
        self.assertIn("cannot detect a receipt-level divergence", output)

    def test_the_real_corpus_still_compares_partial_responses(self):
        # The Stage 0 expected state, asserted rather than assumed: every
        # denial vector in the corpus is a projection today, because a whole
        # response carries a signature and the JWS protected header's member
        # set is unspecified (P-001 §10). This turns red on the first
        # whole-response denial vector -- which is when vector.schema.json's
        # `wire` rule should tighten from prose into a schema requirement.
        _, output = lint(CONFORMANCE / "corpus")
        self.assertIn("compared a partial response", output)

    def test_a_whole_response_is_not_reported_as_partial(self):
        code, output = lint(FIXTURES / "denial-whole-response")
        self.assertEqual(code, 0, output)
        self.assertNotIn("compared a partial response", output)


class ReducedReceiptShapeTest(unittest.TestCase):
    """§6: "exactly five fields, and no others".

    A wrong-shaped receipt is not a narrower comparison, which is why these
    fail rather than report. Omitting `receipt` asserts nothing about it and is
    legitimate; asserting a four-field or six-field one asserts that a
    conforming implementation emits it, and §6 says none does.
    """

    def test_a_receipt_missing_a_field_is_rejected(self):
        code, output = lint(FIXTURES / "denial-malformed-receipt")
        self.assertEqual(code, 1)
        self.assertIn("receipt: missing signature_suite", output)
        self.assertIn("Omit `receipt` entirely", output)

    def test_a_receipt_with_an_extra_field_is_rejected(self):
        # The case that matters most. §6 forbids it because a field present for
        # some causes and absent for others reintroduces the distinction
        # normalization removes -- and this fixture's extra field is the one
        # claims.md names outright: "a denial receipt that named the predicate
        # would partition denials by predicate, defeating Q2D-C-08".
        code, output = lint(FIXTURES / "denial-extra-receipt-field")
        self.assertEqual(code, 1)
        self.assertIn("receipt: carries predicate", output)
        self.assertIn("exactly five fields, and no others", output)

    def test_a_correct_receipt_passes(self):
        code, output = lint(FIXTURES / "denial-whole-response")
        self.assertEqual(code, 0, output)

    def test_omitting_the_receipt_is_not_an_error(self):
        # The real corpus does exactly this, and it is legitimate: a registry/
        # vector tests predicate evaluation, not response construction. It is
        # *reported* as a partial comparison, not rejected.
        code, output = lint(CONFORMANCE / "corpus")
        self.assertEqual(code, 0, output)
        self.assertIn("compared a partial response", output)


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
