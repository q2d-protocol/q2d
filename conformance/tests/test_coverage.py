"""Coverage reports what is missing, which is the only thing it is for.

    python3 -m unittest discover -s conformance/tests

P-001 §4.8: uncited claims are **reported, not silently absent**. The Stage 0
answer is that all thirteen are uncovered, and that is correct rather than a
failure -- so this also carries the expected-state assertion the workflow asks
for in place of a permanently red check.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONFORMANCE / "harness"))

import coverage as coverage_module  # noqa: E402

FIXTURES = CONFORMANCE / "tests" / "fixtures"


def coverage(corpus: Path) -> tuple[int, str]:
    captured = io.StringIO()
    with redirect_stdout(captured):
        code = coverage_module.coverage(corpus)
    return code, captured.getvalue()


# What the real corpus covers today, and nothing more. Issue 11 folded in
# `registry/`, which cites these three; every other claim is still uncovered,
# and stays named in the report for that reason.
COVERED_TODAY = ("Q2D-C-03", "Q2D-C-08", "Q2D-C-09")


class StageZeroExpectedStateTest(unittest.TestCase):
    """The assertion .github/workflows/checks.yml prescribes instead of a red
    job. It is not "nothing is covered" -- that stopped being true when the
    registry section landed -- but *exactly* what is covered, so a vector that
    starts citing a claim without anyone updating this turns it red.
    """

    def test_the_real_corpus_covers_exactly_the_claims_it_cites(self):
        code, output = coverage(CONFORMANCE / "corpus")
        self.assertEqual(code, 0)
        self.assertIn(f"{len(COVERED_TODAY)}/13 claims covered", output)
        for claim in COVERED_TODAY:
            with self.subTest(claim=claim):
                self.assertIn(f"covered    {claim}", output)

    def test_every_other_claim_is_named_as_uncovered(self):
        # Reported, not silently absent: a report listing only what passed is
        # a marketing document.
        _, output = coverage(CONFORMANCE / "corpus")
        for number in range(1, 14):
            claim = f"Q2D-C-{number:02d}"
            if claim in COVERED_TODAY:
                continue
            with self.subTest(claim=claim):
                self.assertIn(f"UNCOVERED  {claim}", output)

    def test_ten_claims_still_have_no_vector(self):
        # The number is worth asserting on its own. Three of thirteen is the
        # honest Stage 0 answer and reads very differently from "covered".
        _, output = coverage(CONFORMANCE / "corpus")
        self.assertEqual(output.count("UNCOVERED  Q2D-C-"), 13 - len(COVERED_TODAY))


class CountingTest(unittest.TestCase):
    def test_a_cited_claim_is_covered(self):
        code, output = coverage(FIXTURES / "valid")
        self.assertEqual(code, 0)
        self.assertIn("covered    Q2D-C-05", output)
        self.assertIn("covered    Q2D-C-08", output)
        self.assertIn("2/13 claims covered", output)

    def test_conformance_classes_are_reported_too(self):
        # conformance-classes.md's honesty rule needs the same instrument, and
        # P-016 issue 8 reports both in one matrix.
        _, output = coverage(FIXTURES / "valid")
        self.assertIn("conformance classes", output)
        self.assertIn("CC-12", output)

    def test_classes_are_listed_in_numeric_order(self):
        _, output = coverage(FIXTURES / "valid")
        block = output.split("conformance classes")[1]
        self.assertLess(block.index("CC-2"), block.index("CC-12"))

    def test_a_non_claim_citation_is_shown_but_not_required(self):
        # A non-claim is something the project states it does not claim, so
        # nothing is missing when no vector cites one.
        _, output = coverage(FIXTURES / "valid")
        self.assertNotIn("UNCOVERED  Q2D-NC", output)

    def test_a_vector_that_cannot_run_cannot_cover_a_claim(self):
        # claims.md's traceability rule is about *executable* checks. A file
        # that parses but does not conform is rejected by `run`, so counting
        # its citation would report a claim as backed by a check that cannot be
        # performed -- the overstatement this mode exists to prevent.
        _, output = coverage(FIXTURES / "schema-invalid")
        self.assertIn("0/13 claims covered", output)
        self.assertNotIn("covered    Q2D-C-05", output)
        self.assertIn("corpus rejects it", output)

    def test_a_vector_the_corpus_rejects_cannot_cover_a_claim(self):
        # Not merely schema-invalid: these are schema-valid and rejected by
        # lint -- a citation pointing at nothing, and a vector filed under the
        # wrong section. A claim reported as covered by evidence the corpus
        # refuses is the overstatement traceability exists to prevent.
        # duplicate-id is a corpus-level rejection rather than a per-vector
        # one, and counts for the same reason.
        for fixture in ("bad-citation", "misplaced", "duplicate-id"):
            with self.subTest(fixture=fixture):
                _, output = coverage(FIXTURES / fixture)
                self.assertIn("0/13 claims covered", output)
                self.assertIn("corpus rejects it", output)

    def test_a_corpus_invalid_as_a_whole_covers_nothing(self):
        # Every vector in these fixtures is individually valid, and the corpus
        # still contradicts itself. Counting its citations would report a claim
        # as covered by a corpus lint refuses.
        for fixture in ("denial-divergent", "budget-divergent"):
            with self.subTest(fixture=fixture):
                _, output = coverage(FIXTURES / fixture)
                self.assertIn("0/13 claims covered", output)
                self.assertIn("invalid as a whole", output)

    def test_citation_and_demonstration_are_reported_together(self):
        # §4.8 defines coverage as citation, so a claim cited once is covered.
        # Printing that number alone would overstate: the reader needs to see
        # that the cross-vector property behind it is not yet demonstrated.
        _, output = coverage(FIXTURES / "denial-thin")
        self.assertIn("cross-vector, over what was counted", output)
        self.assertIn("with a single cause", output)

    def test_unreadable_files_are_not_counted_silently(self):
        # Their citations cannot be read, so a report that ignored them would
        # overstate coverage.
        _, output = coverage(FIXTURES / "not-json")
        self.assertIn("could not be read", output)
        self.assertIn("harness lint", output)


if __name__ == "__main__":
    unittest.main()
