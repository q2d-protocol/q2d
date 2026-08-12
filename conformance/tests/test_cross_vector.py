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
        # Only reachable outside `denial/` now, since a denial/ vector
        # asserting a projection is rejected outright. The real corpus is
        # exactly this case: registry/ rejections, which test predicate
        # evaluation rather than response construction.
        _, output = lint(CONFORMANCE / "corpus")
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


class WholeResponseTest(unittest.TestCase):
    """A denial/ vector asserts core-model.md §5.2's whole response.

    Enforced rather than documented, because the rule's whole content is that a
    projection here *cannot fail*: `status` and `external_reason` are both
    fixed by the normalized class, so a vector asserting only those compares
    two constants across every cause. A prose rule with nothing behind it would
    be a corpus that looks like it verifies Q2D-C-08.
    """

    def test_a_denial_vector_asserting_a_projection_is_rejected(self):
        code, output = lint(FIXTURES / "denial-projection")
        self.assertEqual(code, 1)
        self.assertIn("wire: missing receipt, signature", output)
        self.assertIn("cannot fail", output)

    def test_a_denial_carrying_an_extra_field_is_rejected(self):
        # §5.2 is "exactly four fields, and no others". The fixture uses the
        # field that would actually appear — a rate limiter's retry value,
        # which core-model.md §9.1 makes every deployment capable of producing
        # and which is cause-specific by construction.
        code, output = lint(FIXTURES / "denial-extra-response-field")
        self.assertEqual(code, 1)
        self.assertIn("wire: carries retry_after", output)
        self.assertIn("vary by cause", output)

    def test_the_values_5_2_determines_are_checked_not_only_the_keys(self):
        # Presence alone would accept a vector asserting `status: "answer"` on
        # a rejection, or an empty signature — either then scored against both
        # implementations as though it were a conforming denial.
        code, output = lint(FIXTURES / "denial-bad-values")
        self.assertEqual(code, 1)
        self.assertIn("wire.status: 'answer'", output)
        self.assertIn("wire.signature: empty", output)

    def test_a_variable_length_timestamp_is_rejected(self):
        # §6's length guarantee rests on none of the reduced fields being
        # variable-length, and `decided_at` is the one that can vary. A vector
        # asserting sub-second precision asserts away the property.
        _, output = lint(FIXTURES / "denial-bad-values")
        self.assertIn("not RFC 3339 at second precision", output)
        self.assertIn("variable-length", output)

    def test_an_explicit_escalation_is_held_to_its_own_shape(self):
        # §5.3's explicit escalation is a different response, not a denial with
        # optional parts: `status: escalate`, `pending_token`, `expires_at`,
        # and no external_reason, because it is "not denial-normalized and must
        # never be described as such". Holding it to §5.2's list would reject a
        # correct vector.
        code, output = lint(FIXTURES / "denial-explicit-escalation")
        self.assertEqual(code, 0, output)

    def test_an_explicit_escalation_missing_its_own_fields_is_rejected(self):
        code, output = lint(FIXTURES / "denial-escalation-incomplete")
        self.assertEqual(code, 1)
        self.assertIn("missing expires_at, pending_token", output)
        self.assertIn("explicit escalation", output)

    def test_an_escalation_described_as_normalized_is_rejected(self):
        # Determinate, unlike extra fields in general: `external_reason` is the
        # field that describes an outcome as belonging to a normalized class,
        # and §5.3 says an explicit escalation is not one.
        code, output = lint(FIXTURES / "denial-escalation-described")
        self.assertEqual(code, 1)
        self.assertIn("must never be described as such", output)

    def test_a_corpus_mixing_rfc3339_spellings_fails(self):
        # No spelling is rejected — §6 says only "RFC 3339, second precision",
        # and deciding between them here would settle a specification question
        # in a lint rule. A corpus using several is defective whichever way §6
        # goes: no implementation emits several, so none can satisfy it.
        code, output = lint(FIXTURES / "denial-mixed-timestamp-forms")
        self.assertEqual(code, 1)
        self.assertIn("spellings of RFC 3339", output)
        self.assertIn("is not", output)

    def test_any_single_spelling_is_allowed_and_reported(self):
        # RFC 3339 permits `T`/`t`, `Z`/`z`, and a numeric offset. §6 names no
        # profile, so each is allowed on its own — and named, so a corpus
        # cannot drift across them unnoticed.
        for fixture in ("denial-offset-timestamp", "denial-lowercase-timestamp",
                        "denial-whole-response"):
            with self.subTest(fixture=fixture):
                code, output = lint(FIXTURES / fixture)
                self.assertEqual(code, 0, output)
                self.assertIn("receipt timestamps:", output)
                self.assertIn("open (P-001 §10)", output)

    def test_an_impossible_offset_is_rejected(self):
        # The regex matches the offset's shape; these are its ranges. Accepting
        # the form is a specification question and validating its syntax is not.
        sys.path.insert(0, str(CONFORMANCE / "harness"))
        import lint as lint_mod
        self.assertTrue(lint_mod.valid_timestamp("2026-01-01T00:00:00-05:30"))
        self.assertFalse(lint_mod.valid_timestamp("2026-01-01T00:00:00+99:99"))
        self.assertFalse(lint_mod.valid_timestamp("2026-01-01T00:00:00+24:00"))

    def test_a_leap_second_must_be_at_a_month_end(self):
        # §5.7 puts ":60" "at the end of months in which a leap second
        # occurs". The month end is fixed by the RFC and checked; *which*
        # months is IERS data, not statically decidable, and deliberately not.
        sys.path.insert(0, str(CONFORMANCE / "harness"))
        import lint as lint_mod
        self.assertTrue(lint_mod.valid_timestamp("2017-06-30T23:59:60Z"))
        self.assertFalse(lint_mod.valid_timestamp("2026-01-01T23:59:60Z"))

    def test_a_leap_second_under_an_offset_is_accepted(self):
        # RFC 3339 §5.7 puts a leap second at 23:59 *UTC*, which is a different
        # wall time under an offset. Checking the local fields rejected the
        # same instant written a different way.
        sys.path.insert(0, str(CONFORMANCE / "harness"))
        import lint as lint_mod
        self.assertTrue(lint_mod.valid_timestamp("2016-12-31T15:59:60-08:00"))
        self.assertTrue(lint_mod.valid_timestamp("2017-01-01T08:59:60+09:00"))
        self.assertFalse(lint_mod.valid_timestamp("2026-01-01T12:00:60+00:00"))

    def test_a_leap_second_is_accepted(self):
        # RFC 3339 permits second 60 and §6 asks for RFC 3339. Excluding it
        # would be narrowing the specification in harness code — and it is a
        # boundary two implementations could genuinely disagree about, which
        # makes it worth a vector rather than worth banning.
        sys.path.insert(0, str(CONFORMANCE / "harness"))
        import lint as lint_mod
        self.assertTrue(lint_mod.valid_timestamp("2016-12-31T23:59:60Z"))
        self.assertFalse(lint_mod.valid_timestamp("2026-02-30T00:00:00Z"))

    def test_a_timestamp_with_no_real_instant_behind_it_is_rejected(self):
        # Digit placement is not a date. The shape carries §6's length
        # argument; parsing carries the rest.
        _, output = lint(FIXTURES / "denial-bad-values")
        self.assertIn("impossible-timestamp", output)
        self.assertIn("2026-99-99T99:99:99Z", output)

    def test_a_receipt_recording_escalate_behind_a_uniform_wire_is_rejected(self):
        # The case §5.3 names outright, and the one this whole section exists
        # for: the response is uniform and the receipt attached to it is not.
        code, output = lint(FIXTURES / "denial-escalate-in-receipt")
        self.assertEqual(code, 1)
        self.assertIn("in the one place nobody looks", output)

    def test_other_sections_may_assert_a_projection(self):
        # The real corpus is registry/ rejections, which test predicate
        # evaluation rather than response construction.
        code, _ = lint(CONFORMANCE / "corpus")
        self.assertEqual(code, 0)


class MixedCompletenessTest(unittest.TestCase):
    """A projection beside a whole response, in one normalized class.

    The corpus will be in exactly this state the day after the first
    whole-response denial vector is authored: `registry/` projections and
    `denial/` whole responses sharing an `external_reason`. Comparing them
    whole would report "distinct wire responses" because one vector declined to
    mention two fields — blocking the work rather than catching a divergence.
    """

    def test_a_projection_does_not_disagree_with_a_whole_response(self):
        code, output = lint(FIXTURES / "denial-mixed-completeness")
        self.assertEqual(code, 0, output)
        self.assertIn("compared a partial response", output)

    def test_but_two_whole_responses_are_still_compared_whole(self):
        # denial-divergent differs by a `retry_after` present in one. Both are
        # whole responses, so that is the divergence it is rather than a field
        # one of them declined to mention.
        code, output = lint(FIXTURES / "denial-divergent")
        self.assertEqual(code, 1)
        self.assertIn("distinct wire responses", output)


class CoherenceOutsideDenialTest(unittest.TestCase):
    def test_a_leaking_receipt_is_caught_outside_denial_too(self):
        # A registry/ rejection whose receipt records `escalate` behind a
        # `deny` leaks the true outcome exactly as completely, and is no more
        # conforming for being in another section.
        code, output = lint(FIXTURES / "registry-escalate-in-receipt")
        self.assertEqual(code, 1)
        self.assertIn("nobody looks", output)


class ValuesOutsideDenialTest(unittest.TestCase):
    def test_asserted_values_are_checked_outside_denial_too(self):
        # Which fields a vector must assert depends on its section; what a
        # field may contain does not. A projection asserting `status: answer`
        # would otherwise be scored against a conforming runner.
        code, output = lint(FIXTURES / "registry-bad-wire-values")
        self.assertEqual(code, 1)
        self.assertIn("wire.status: 'answer'", output)
        self.assertIn("wire.external_reason: empty", output)


class PairwiseComparisonTest(unittest.TestCase):
    def test_one_projection_does_not_blind_the_class(self):
        # Two whole responses whose receipts differ, plus a third vector that
        # omits the receipt. Intersecting across the class would drop `receipt`
        # and report agreement — the receipt-level oracle Q2D-C-08 exists to
        # catch, discarded because an unrelated vector said nothing about it.
        code, output = lint(FIXTURES / "denial-blinded-by-projection")
        self.assertEqual(code, 1)
        self.assertIn("distinct wire responses", output)


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

    def test_a_receipt_is_checked_outside_denial_too(self):
        # A registry/ vector may carry a receipt, and an empty digest in it is
        # no more conforming for being in a different section.
        code, output = lint(FIXTURES / "registry-bad-receipt")
        self.assertEqual(code, 1)
        self.assertIn("wire.receipt.request_digest: empty", output)
        self.assertIn("not RFC 3339", output)

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
