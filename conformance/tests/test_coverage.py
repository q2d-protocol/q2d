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


class StageZeroExpectedStateTest(unittest.TestCase):
    def test_the_real_corpus_covers_no_claim_yet(self):
        # The assertion .github/workflows/checks.yml prescribes instead of a
        # red job: true while the corpus is empty, green, and red the day a
        # vector cites a claim without this being updated.
        code, output = coverage(CONFORMANCE / "corpus")
        self.assertEqual(code, 0)
        self.assertIn("0/13 claims covered", output)
        self.assertIn("no claim is covered", output)

    def test_all_thirteen_claims_are_named(self):
        # Reported, not silently absent: a report listing only what passed is
        # a marketing document.
        _, output = coverage(CONFORMANCE / "corpus")
        for number in range(1, 14):
            with self.subTest(claim=number):
                self.assertIn(f"UNCOVERED  Q2D-C-{number:02d}", output)


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

    def test_unreadable_files_are_not_counted_silently(self):
        # Their citations cannot be read, so a report that ignored them would
        # overstate coverage.
        _, output = coverage(FIXTURES / "not-json")
        self.assertIn("could not be read", output)
        self.assertIn("harness lint", output)


if __name__ == "__main__":
    unittest.main()
