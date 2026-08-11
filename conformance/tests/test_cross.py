"""Two runners held to producing the same thing (P-001 issue 9).

    python3 -m unittest discover -s conformance/tests

This is the assertion the project rests on: two implementations built from one
specification, where a divergence is a specification ambiguity found before an
outsider finds it. The runners here stand in for those two, and each divergence
they simulate is one that has to be reported rather than absorbed.
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
import cross as cross_module  # noqa: E402

FIXTURES = CONFORMANCE / "tests" / "fixtures"
RUNNERS = CONFORMANCE / "tests" / "runners"
STUB = CONFORMANCE / "runners" / "stub" / "q2d-conform"
VALID = FIXTURES / "valid"

CORRECT = RUNNERS / "answers-correctly"
OTHER_KEY_ORDER = RUNNERS / "answers-correctly-other-key-order"
DIVERGENT = RUNNERS / "answers-with-a-different-signature"


def cross(a: Path, b: Path, corpus: Path = VALID) -> tuple[int, str]:
    captured = io.StringIO()
    with redirect_stdout(captured):
        code = cross_module.cross(corpus, a, b)
    return code, captured.getvalue()


class AgreementTest(unittest.TestCase):
    def test_two_runners_producing_the_same_values_agree(self):
        code, output = cross(CORRECT, CORRECT)
        self.assertEqual(code, 0, output)
        self.assertIn("3/3 vectors agree", output)

    def test_the_result_envelope_s_key_order_is_not_a_divergence(self):
        # Whether a runner writes `outcome` before `vector_id` is a property of
        # its JSON writer. Reporting that as a divergence would fail two
        # correct implementations for something that is not Q2D at all.
        code, output = cross(CORRECT, OTHER_KEY_ORDER)
        self.assertEqual(code, 0, output)
        self.assertIn("3/3 vectors agree", output)


class DivergenceTest(unittest.TestCase):
    def test_one_differing_byte_is_reported_with_its_offset(self):
        # §8's last row, and the one the PRD says it exists for: a `bytes`
        # vector where two implementations differ by one byte, naming the
        # offset. A report that said only "differs" would leave the reader to
        # find a canonicalization divergence by eye.
        code, output = cross(CORRECT, DIVERGENT, FIXTURES / "message-only")
        self.assertEqual(code, 1)
        self.assertIn("DIFFER", output)
        self.assertIn("first differing byte at offset", output)
        self.assertIn("output:", output)

    def test_one_runner_faulting_is_a_divergence(self):
        # The stub emits `outcome: "error"`, which the contract uses to say the
        # runner produced no Q2D answer. One side answering and the other
        # faulting is the two of them disagreeing, same as exit 1.
        code, output = cross(CORRECT, STUB)
        self.assertEqual(code, 1)
        self.assertIn("DIFFER", output)
        self.assertIn("faulted", output)

    def test_two_runners_faulting_alike_is_not_agreement(self):
        # The only field two errors share is the word `error`. Comparing them
        # would report agreement for a vector on which neither implementation
        # produced anything at all.
        code, output = cross(STUB, STUB, FIXTURES / "valid")
        self.assertEqual(code, 0, output)
        self.assertIn("SKIP", output)
        self.assertIn("nothing was compared", output)
        self.assertNotIn("agree   ", output)

    def test_two_runners_answering_a_different_vector_do_not_agree(self):
        # `comparable()` drops `vector_id`, so without an explicit check these
        # two agree on every field they are compared on while neither has
        # answered anything asked of them.
        canned = RUNNERS / "answers-a-different-vector"
        code, output = cross(canned, canned)
        self.assertEqual(code, 0, output)
        self.assertIn("SKIP", output)
        self.assertIn("answered 'some/other/vector'", output)
        self.assertIn("nothing was compared", output)
        self.assertNotIn("agree   ", output)

    def test_only_one_runner_answering_is_itself_a_divergence(self):
        # One implementation handles the vector and the other does not, which
        # is the two of them disagreeing. Calling it merely unusable would let
        # a `bytes` vector that only one language implements pass this mode in
        # silence -- the coverage gap the Stage 1 gate exists to close.
        code, output = cross(CORRECT, RUNNERS / "cannot-process")
        self.assertEqual(code, 1)
        self.assertIn("DIFFER", output)
        self.assertIn("while A produced a result", output)

    def test_neither_runner_answering_is_skipped_not_scored(self):
        # Neither claimed anything, so there is nothing they disagree about.
        # Judging either against the corpus is `run`'s job.
        unable = RUNNERS / "cannot-process"
        code, output = cross(unable, unable)
        self.assertEqual(code, 0, output)
        self.assertIn("SKIP", output)
        self.assertIn("nothing was compared", output)


class PartialCorpusTest(unittest.TestCase):
    def test_an_unreadable_corpus_file_fails_the_run(self):
        # A file that will not parse is a vector neither runner was asked
        # about, so the corpus reported on is smaller than the corpus on disk.
        # Exiting 0 with a note would make a partial run look like a complete
        # one.
        code, output = cross(CORRECT, CORRECT,
                             FIXTURES / "malformed-json")
        self.assertEqual(code, 1)
        self.assertIn("could not be read", output)
        self.assertIn("could not be put to either runner", output)

    def test_a_non_conforming_vector_fails_the_run(self):
        # Same class: a vector nobody was asked about. It is the corpus being
        # wrong rather than the runners, so it is counted and named apart from
        # a pair that could not answer.
        code, output = cross(CORRECT, CORRECT, FIXTURES / "schema-invalid")
        self.assertEqual(code, 1)
        self.assertIn("INVALID", output)
        self.assertIn("could not be put to either runner", output)


class StageZeroExpectedStateTest(unittest.TestCase):
    """The assertion .github/workflows/checks.yml asks for, now cross exists.

    There is one runner in this repository and it answers nothing, so there is
    no pair to compare and the real corpus is empty besides. Both facts are
    asserted rather than a job being left red: this turns red when a second
    runner appears, which is the moment to compare them for real.
    """

    def test_the_stub_against_itself_compares_nothing(self):
        code, output = cross(STUB, STUB, CONFORMANCE / "corpus")
        self.assertEqual(code, 0, output)
        self.assertIn("nothing was compared", output)


class NothingComparedTest(unittest.TestCase):
    def test_an_empty_corpus_compares_nothing_and_says_so(self):
        # Two runners agreeing about nothing is not agreement.
        code, output = cross(CORRECT, CORRECT, FIXTURES / "empty")
        self.assertEqual(code, 0)
        self.assertIn("nothing was compared", output)

    def test_a_missing_runner_is_an_error(self):
        with self.assertRaises(corpus_module.CorpusError):
            cross_module.cross(VALID, CORRECT, RUNNERS / "does-not-exist")


if __name__ == "__main__":
    unittest.main()
