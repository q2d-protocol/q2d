"""`process_sequence` carries a sequence, and the vocabulary is settled (E-51).

    python3 -m unittest discover -s conformance/tests

[E-51](../../docs/open-escalations.md) closed as C: one operation whose input is
an ordered list of requests, because idempotency is a property of the *second*
request and no vector could describe one. The thing that can go wrong is a
vector using the operation and carrying one request — it lints, it runs, and it
asserts nothing about a sequence, which is the same silent pass the `ordering/`
step rule exists to stop.

Nothing in the committed corpus uses the operation yet: P-004's `idempotent/`
and `id-reuse/` are still blocked on [P-010](../../docs/prds/P-010-responder-pipeline.md),
because what a sequence runs through is the §4 pipeline. So these are checks on
the rule rather than on authored vectors, and the last one asserts that absence
deliberately — it turns red when the first sequence vector lands, which is when
the corpus-level checks here should be written.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONFORMANCE / "harness"))

import lint as lint_module  # noqa: E402

CORPUS = CONFORMANCE / "corpus"


def a_request() -> dict:
    """Stand-in for what `process_query` takes. Its shape is P-010's."""
    return {"envelope": {"signed": "eyJ.eyJ.c2ln", "routing": {}}}


def a_vector(requests) -> dict:
    """A `process_sequence` vector carrying whatever `requests` is given."""
    return {
        "id": "replay/idempotent/retry-returns-the-same-bytes",
        "section": "replay",
        "requirement": ["Q2D-C-07"],
        "description": "A retry returns the stored bytes and debits nothing further.",
        "operation": "process_sequence",
        "input": {"requests": requests},
        "expect": {"outcome": "ok", "output": {}, "comparison": "structural"},
    }


class SequenceRuleTest(unittest.TestCase):
    def test_two_requests_is_a_sequence(self):
        self.assertEqual([], lint_module.sequence_errors(a_vector([a_request(), a_request()])))

    def test_more_than_two_is_still_a_sequence(self):
        # No upper bound: what the count has to clear is "there is a prior
        # request", and a ceiling would be invented here.
        self.assertEqual([], lint_module.sequence_errors(a_vector([a_request()] * 5)))

    def test_one_request_asserts_nothing_about_a_sequence(self):
        errors = lint_module.sequence_errors(a_vector([a_request()]))
        self.assertTrue(errors, "a sequence of one was accepted")
        self.assertIn("at least two", errors[0])

    def test_an_empty_list_is_refused(self):
        self.assertTrue(lint_module.sequence_errors(a_vector([])))

    def test_a_missing_requests_list_is_refused(self):
        vector = a_vector([a_request(), a_request()])
        del vector["input"]["requests"]
        errors = lint_module.sequence_errors(vector)
        self.assertTrue(errors, "a vector with no requests list was accepted")
        self.assertIn("'requests' list", errors[0])

    def test_other_operations_are_not_held_to_it(self):
        # The rule is the operation's, not the section's: a `replay/` vector
        # using `process_query` is a single request on purpose.
        vector = a_vector([a_request()])
        vector["operation"] = "process_query"
        self.assertEqual([], lint_module.sequence_errors(vector))


class ItDoesNotCrashOnWhatItRejectsTest(unittest.TestCase):
    """The rule runs *alongside* the schema's checks, not after them.

    P-001 §4.8, and the failure this repository has now had four times: a check
    reaching into a field of a vector malformed in exactly the way the check
    exists to catch. Aborting hides every finding after it, which is worse than
    the malformed file.
    """

    def test_every_malformed_shape_returns_rather_than_raises(self):
        for name, vector in [
            ("input is a string", {"operation": "process_sequence", "input": "requests"}),
            ("input is a list", {"operation": "process_sequence", "input": []}),
            ("input is null", {"operation": "process_sequence", "input": None}),
            ("input is absent", {"operation": "process_sequence"}),
            ("requests is an integer", {"operation": "process_sequence",
                                        "input": {"requests": 2}}),
            ("requests is null", {"operation": "process_sequence",
                                  "input": {"requests": None}}),
            ("requests is an object", {"operation": "process_sequence",
                                       "input": {"requests": {"first": {}}}}),
            ("the vector is empty", {}),
        ]:
            with self.subTest(shape=name):
                self.assertIsInstance(lint_module.sequence_errors(vector), list)


class VocabularyTest(unittest.TestCase):
    def test_the_operation_is_in_the_schema(self):
        enum = lint_module.load_schema()["properties"]["operation"]["enum"]
        self.assertIn("process_sequence", enum)

    def test_the_two_sequence_senses_have_two_names(self):
        # P-001 §4.5 recorded the requester-side ordering need as "a
        # sequence-asserting operation", meaning a sequence of *steps* over one
        # response. E-51's is a sequence of *requests*. Two things under one
        # word, inside the list that exists to stop two names for one thing.
        enum = lint_module.load_schema()["properties"]["operation"]["enum"]
        self.assertIn("process_response", enum)
        self.assertIn("process_sequence", enum)

    def test_no_vector_uses_it_yet(self):
        # Asserted rather than assumed. P-004's two groups are still blocked on
        # P-010, so the first sequence vector landing is a real event — and this
        # file is where its corpus-level checks belong.
        using = [path.name for path in sorted(CORPUS.rglob("*.json"))
                 if json.loads(path.read_text(encoding="utf-8")).get("operation")
                 == "process_sequence"]
        self.assertEqual([], using,
                         "a process_sequence vector exists; write its corpus checks here")


if __name__ == "__main__":
    unittest.main()
