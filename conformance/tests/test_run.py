"""`harness run` executes a corpus and judges what comes back (P-001 issue 4).

    python3 -m unittest discover -s conformance/tests

The runners under `runners/` misbehave in one specific way each, so every way a
runner can be wrong has a test that catches it. Two of them answer correctly,
from a hardcoded table -- a test runner that computed anything would be a
partial implementation hiding in a test directory.

The first test is P-001 §7's gate: the harness runs, and reports fail for every
vector, because no implementation exists.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONFORMANCE / "harness"))

import corpus as corpus_module  # noqa: E402
import run as run_module  # noqa: E402

FIXTURES = CONFORMANCE / "tests" / "fixtures"
RUNNERS = CONFORMANCE / "tests" / "runners"
STUB = CONFORMANCE / "runners" / "stub" / "q2d-conform"
VALID = FIXTURES / "valid"


def run(runner: Path, corpus: Path = VALID) -> tuple[int, str]:
    captured = io.StringIO()
    with redirect_stdout(captured):
        code = run_module.run(corpus, runner)
    return code, captured.getvalue()


class TheStageZeroGateTest(unittest.TestCase):
    def test_the_harness_runs_and_fails_every_vector(self):
        # P-001 §7: "A harness that cannot fail is not a harness." Until an
        # implementation exists, every vector must fail -- and it must fail by
        # being judged, not by the harness falling over.
        code, output = run(STUB)
        self.assertEqual(code, 1)
        self.assertIn("0/3 vectors passed", output)
        self.assertEqual(output.count("  FAIL"), 3)
        self.assertIn("expected outcome 'ok', got 'error'", output)

    def test_an_empty_corpus_proves_nothing_and_says_so(self):
        code, output = run(STUB, FIXTURES / "empty")
        self.assertEqual(code, 1)
        self.assertIn("nothing is proven", output)


class StageZeroExpectedStateTest(unittest.TestCase):
    """The assertion .github/workflows/checks.yml said to add when run landed.

    Not `harness run` as a failing CI job -- a permanently red check trains
    everyone to ignore red. The expected state is asserted instead: **no vector
    passes against the reference stub**, which is true while no implementation
    exists, green, and turns red the day someone makes the stub answer or wires
    a real runner in without updating this.
    """

    def test_no_vector_in_the_real_corpus_passes_against_the_stub(self):
        corpus = CONFORMANCE / "corpus"
        code, output = run(STUB, corpus)
        vectors, _ = corpus_module.load(corpus)
        if not vectors:
            self.assertEqual(code, 1)
            self.assertIn("nothing is proven", output)
        else:
            self.assertEqual(code, 1, output)
            self.assertIn(f"0/{len(vectors)} vectors passed", output)


class PartialWireTest(unittest.TestCase):
    """A vector asserting a subset of §5.2 asserts nothing about the rest.

    vector.schema.json says so on `wire`. If `run` compared the whole object,
    a conforming implementation returning §5.2's four fields would fail every
    registry/ vector for returning too much — the corpus contract and the
    comparison would disagree, and the comparison would win.
    """

    def test_a_whole_response_passes_a_projecting_vector(self):
        code, output = run(RUNNERS / "answers-the-whole-response",
                           FIXTURES / "registry-style-projection")
        self.assertEqual(code, 0, output)
        self.assertIn("1/1 vectors passed", output)

    def test_an_asserted_field_still_has_to_match(self):
        # The subset rule drops what the vector does not mention; it does not
        # soften what it does.
        code, output = run(RUNNERS / "answers-denial-with-another-reason",
                           FIXTURES / "registry-style-projection")
        self.assertEqual(code, 1)
        self.assertIn("internal reason", output)


class DenialExactnessTest(unittest.TestCase):
    def test_an_extra_field_on_a_denial_fails(self):
        # denial/ is not projected. A runner returning the four fields plus a
        # cause-specific fifth is the oracle Q2D-C-08 exists to catch, and a
        # subset rule applied here would drop it.
        code, output = run(RUNNERS / "answers-denial-with-an-extra-field",
                           FIXTURES / "denial-single")
        self.assertEqual(code, 1)
        self.assertIn("debug_cause", output)


class PassingTest(unittest.TestCase):
    def test_a_correct_runner_passes_every_vector(self):
        code, output = run(RUNNERS / "answers-correctly")
        self.assertEqual(code, 0, output)
        self.assertIn("3/3 vectors passed", output)


class ExpectationNeverReachesTheRunnerTest(unittest.TestCase):
    def test_the_runner_receives_only_the_projection(self):
        # §4.2 is enforced by projection.py; this proves the wiring uses it,
        # which is the half a unit test of the projection cannot show.
        _, output = run(RUNNERS / "reports-what-it-was-given")
        self.assertIn("fields: id,input,operation", output)
        self.assertNotIn("expect", output.replace("expected", ""))


class RunnerFailureTest(unittest.TestCase):
    """A malformed result is the runner's fault, and is reported as such.

    Conflating it with a vector failure sends whoever is debugging to the wrong
    file: one means the implementation is wrong about Q2D, the other means it
    is wrong about the contract.
    """

    def assert_runner_failure(self, runner_name: str, expected: str):
        code, output = run(RUNNERS / runner_name)
        self.assertEqual(code, 1)
        self.assertIn(expected, output)
        self.assertIn("did not produce a result the harness could judge", output)

    def test_a_runner_that_cannot_process_the_vector(self):
        self.assert_runner_failure("cannot-process", "could not process")

    def test_a_runner_that_emits_malformed_json(self):
        self.assert_runner_failure("emits-malformed-json", "not valid JSON")

    def test_a_runner_whose_result_does_not_conform(self):
        self.assert_runner_failure("emits-a-nonconforming-result", "does not conform")

    def test_a_runner_that_answers_a_different_vector(self):
        # Otherwise it would be scored against an expectation belonging to a
        # question it was not asked.
        self.assert_runner_failure("answers-a-different-vector", "is for")

    def test_a_runner_that_never_answers(self):
        # A hang must be reported, not inherited: the suite has to be able to
        # say "this one never answered" rather than stopping at it.
        original = run_module.TIMEOUT_SECONDS
        run_module.TIMEOUT_SECONDS = 1
        self.addCleanup(setattr, run_module, "TIMEOUT_SECONDS", original)
        code, output = run(RUNNERS / "never-answers")
        self.assertEqual(code, 1)
        self.assertIn("no result within", output)


class DeterminismTest(unittest.TestCase):
    """P-001 §8, row 1: two runs of the same vector must produce one answer.

    Nothing else catches an ambient clock or RNG. The vector passes, the corpus
    looks green, and the byte comparison the Stage 1 gate rests on fails later
    against the other implementation for reasons nobody can place.
    """

    def test_a_runner_reading_a_clock_is_caught(self):
        code, output = run(RUNNERS / "answers-differently-each-time")
        self.assertEqual(code, 1)
        self.assertIn("two runs of this vector produced different output", output)
        self.assertIn("did not produce a result the harness could judge", output)

    def test_a_deterministic_runner_is_not_accused(self):
        code, _ = run(RUNNERS / "answers-correctly")
        self.assertEqual(code, 0)


class RejectionJudgementTest(unittest.TestCase):
    def test_the_right_denial_for_the_wrong_reason_fails(self):
        # The wire response matches; the internal reason does not. Checking
        # only the wire would pass an implementation that denied correctly by
        # accident, which is the failure the internal/external split exists to
        # make visible.
        code, output = run(RUNNERS / "rejects-for-the-wrong-reason")
        self.assertEqual(code, 1)
        self.assertIn("internal reason", output)
        self.assertIn("budget_exhausted", output)
        self.assertNotIn("did not produce a result", output)


class ReportingTest(unittest.TestCase):
    def test_vectors_are_reported_in_a_stable_order(self):
        # A report whose line order depends on the filesystem cannot be diffed
        # between runs.
        first = run(STUB)[1]
        self.assertEqual([first for _ in range(3)], [run(STUB)[1] for _ in range(3)])

    def test_an_unreadable_vector_is_a_failure_not_a_crash(self):
        # A corpus with one broken file is still worth running: reporting only
        # the breakage would hide whatever else is wrong.
        code, output = run(STUB, FIXTURES / "not-json")
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", output)

    def test_a_nonconforming_vector_is_reported_not_fatal(self):
        # It parses, so corpus loading accepts it; it states no expectation, so
        # judging it would reach into a field that is not there. Aborting would
        # hide every result after it.
        code, output = run(STUB, FIXTURES / "schema-invalid")
        self.assertEqual(code, 1)
        self.assertIn("does not conform to the schema", output)
        self.assertIn("harness lint", output)
        # Including a file that is not an object at all: every mode has to be
        # able to *name* a malformed vector in order to say it is malformed.
        self.assertIn("suite/not-an-object.json", output)
        self.assertIn("0/2 vectors passed", output)

    def test_a_missing_runner_is_an_error_rather_than_a_failing_suite(self):
        with self.assertRaises(corpus_module.CorpusError):
            run_module.run(VALID, RUNNERS / "does-not-exist")


if __name__ == "__main__":
    unittest.main()
