"""The reference runner honours the contract (P-001 issue 3).

    python3 -m unittest discover -s conformance/tests

The stub answers nothing, so what is testable is the part of
../RUNNER-CONTRACT.md that is not protocol: it reads a projection, recognises
the vocabulary or exits 1, writes a result that validates against
result.schema.json, and reports whether it *functioned* rather than whether the
vector passed.

That matters more than it sounds. The harness's own tests are written against
this runner, so a stub that reports its outcome wrongly would make every later
harness test agree with the wrong thing.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONFORMANCE / "harness"))

import projection  # noqa: E402
import schema as schema_module  # noqa: E402

STUB = CONFORMANCE / "runners" / "stub" / "q2d-conform"
RESULT_SCHEMA = json.loads((CONFORMANCE / "result.schema.json").read_text(encoding="utf-8"))
FIXTURES = CONFORMANCE / "tests" / "fixtures" / "valid"

EXIT_RESULT_PRODUCED = 0
EXIT_CANNOT_PROCESS = 1


def run_stub(payload, tmp: Path) -> subprocess.CompletedProcess:
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run([sys.executable, str(STUB), str(tmp)],
                          capture_output=True, text=True)


class ResultSchemaTest(unittest.TestCase):
    IMPL = {"name": "q2d-rs", "version": "0.1.0"}

    def test_result_schema_is_within_the_supported_subset(self):
        schema_module.assert_supported(RESULT_SCHEMA)

    def assert_valid(self, result, message=""):
        self.assertEqual(schema_module.validate(result, RESULT_SCHEMA), [], message)

    def assert_invalid(self, result, because):
        self.assertTrue(schema_module.validate(result, RESULT_SCHEMA),
                        f"accepted a result that {because}")

    def test_the_three_well_formed_shapes(self):
        self.assert_valid({"vector_id": "a/b", "outcome": "ok", "output": {},
                           "implementation": self.IMPL})
        self.assert_valid({"vector_id": "a/b", "outcome": "rejected",
                           "rejection": {"internal_reason": "unknown_predicate",
                                         "wire": {"status": "deny"}},
                           "implementation": self.IMPL})
        self.assert_valid({"vector_id": "a/b", "outcome": "error",
                           "implementation": self.IMPL})

    def test_an_outcome_without_its_payload_is_malformed(self):
        # Otherwise the failure surfaces later as a comparison error and gets
        # read as a vector failure, when it is the runner that is broken.
        self.assert_invalid({"vector_id": "a/b", "outcome": "ok",
                             "implementation": self.IMPL},
                            "says ok with nothing to compare")
        self.assert_invalid({"vector_id": "a/b", "outcome": "rejected",
                             "implementation": self.IMPL},
                            "says rejected with no reason and no wire response")

    def test_a_rejection_reports_both_halves(self):
        for missing in ("internal_reason", "wire"):
            rejection = {"internal_reason": "x", "wire": {}}
            del rejection[missing]
            with self.subTest(missing=missing):
                self.assert_invalid({"vector_id": "a/b", "outcome": "rejected",
                                     "rejection": rejection,
                                     "implementation": self.IMPL},
                                    f"reports a rejection with no {missing}")

    def test_an_answer_may_not_also_carry_a_rejection(self):
        self.assert_invalid({"vector_id": "a/b", "outcome": "ok", "output": {},
                             "rejection": {"internal_reason": "x", "wire": {}},
                             "implementation": self.IMPL},
                            "answers and rejects at once")

    def test_a_result_must_say_who_produced_it(self):
        self.assert_invalid({"vector_id": "a/b", "outcome": "ok", "output": {}},
                            "does not name its implementation")

    def test_a_lettered_step_can_be_reported(self):
        # core-model.md §4 carries step 9a, the rate-limit check. A schema that
        # could not express it would force a conforming runner to misreport the
        # ordering the corpus exists to assert.
        for step in (1, 9, 19, "9a"):
            with self.subTest(step=step):
                self.assert_valid({"vector_id": "a/b", "outcome": "rejected",
                                   "rejection": {"internal_reason": "rate_limited",
                                                 "wire": {"status": "deny"},
                                                 "step": step},
                                   "implementation": self.IMPL}, f"step={step!r}")

    def test_a_step_outside_the_processing_order_is_rejected(self):
        for step in (0, 20, "9", "a", "1a", "19z", "9A"):
            with self.subTest(step=step):
                self.assert_invalid({"vector_id": "a/b", "outcome": "rejected",
                                     "rejection": {"internal_reason": "x", "wire": {},
                                                   "step": step},
                                     "implementation": self.IMPL},
                                    f"names step {step!r}")


class StubContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = CONFORMANCE / "tests" / "_stub_input.json"
        self.addCleanup(lambda: self.tmp.unlink(missing_ok=True))
        self.vector = json.loads(
            (FIXTURES / "message" / "query-minimal.json").read_text(encoding="utf-8"))
        self.projected = projection.project(self.vector)

    def test_a_result_was_produced_so_the_run_exits_zero(self):
        result = run_stub(self.projected, self.tmp)
        self.assertEqual(result.returncode, EXIT_RESULT_PRODUCED, result.stderr)

    def test_the_result_validates_against_the_schema(self):
        result = run_stub(self.projected, self.tmp)
        parsed = json.loads(result.stdout)
        self.assertEqual(schema_module.validate(parsed, RESULT_SCHEMA), [])

    def test_it_answers_nothing(self):
        # The stub reporting `ok` for anything would make every harness test
        # written against it agree with the wrong thing.
        result = run_stub(self.projected, self.tmp)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["outcome"], "error")
        self.assertNotIn("output", parsed)
        self.assertNotIn("rejection", parsed)

    def test_it_answers_about_the_vector_it_was_given(self):
        result = run_stub(self.projected, self.tmp)
        self.assertEqual(json.loads(result.stdout)["vector_id"], self.vector["id"])

    def test_it_names_itself(self):
        parsed = json.loads(run_stub(self.projected, self.tmp).stdout)
        self.assertEqual(parsed["implementation"]["name"], "q2d-stub")

    def test_stdout_is_one_json_document(self):
        # The harness parses stdout whole; a diagnostic printed there would
        # make a working runner unreadable.
        result = run_stub(self.projected, self.tmp)
        json.loads(result.stdout)  # raises if anything else was printed
        self.assertIn("implements no Q2D behaviour", result.stdout + result.stderr)

    def test_an_unknown_operation_is_exit_one_not_a_skip(self):
        # Fail-closed applies to runners: a skipped vector is a vector nobody
        # notices is unimplemented (P-001 §4.5).
        payload = dict(self.projected, operation="http_exchange")
        result = run_stub(payload, self.tmp)
        self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)
        self.assertEqual(result.stdout, "")
        self.assertIn("unknown operation", result.stderr)

    def test_a_non_string_id_is_exit_one(self):
        # Otherwise it lands in `vector_id` and the runner emits a result the
        # harness cannot judge, while reporting that it functioned.
        for field, value in [("id", 7), ("operation", None), ("id", ["a"])]:
            payload = dict(self.projected)
            payload[field] = value
            with self.subTest(field=field, value=value):
                result = run_stub(payload, self.tmp)
                self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)
                self.assertEqual(result.stdout, "")

    def test_a_projection_missing_input_is_exit_one(self):
        # P-001 §6 fixes VectorInput = { id, operation, input }.
        payload = {k: v for k, v in self.projected.items() if k != "input"}
        result = run_stub(payload, self.tmp)
        self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)
        self.assertEqual(result.stdout, "")

    def test_a_vector_carrying_its_expectation_is_refused(self):
        # The corpus stops being evidence the moment an implementation can read
        # the answer, so the runner refuses rather than trusting the harness to
        # have projected correctly.
        result = run_stub(self.vector, self.tmp)   # the authored vector, unprojected
        self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)
        self.assertEqual(result.stdout, "")
        self.assertIn("expectation", result.stderr)

    def test_any_unexpected_field_is_exit_one(self):
        payload = dict(self.projected, hint="the answer is true")
        result = run_stub(payload, self.tmp)
        self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)
        self.assertEqual(result.stdout, "")

    def test_a_malformed_vector_file_is_exit_one(self):
        self.tmp.write_text("{ not json", encoding="utf-8")
        result = subprocess.run([sys.executable, str(STUB), str(self.tmp)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)

    def test_a_missing_file_is_exit_one(self):
        result = subprocess.run([sys.executable, str(STUB), str(CONFORMANCE / "nope.json")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)

    def test_wrong_argument_count_is_exit_one(self):
        result = subprocess.run([sys.executable, str(STUB)], capture_output=True, text=True)
        self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)

    def test_it_reads_nothing_but_the_vector_it_was_given(self):
        # A runner that consulted vector.schema.json would answer differently
        # depending on the checkout it ran in, and the shipped runners will not
        # have the corpus to consult at all.
        source = STUB.read_text(encoding="utf-8")
        self.assertNotIn("SCHEMA_PATH", source)
        self.assertNotIn('vector.schema.json"', source)

    def test_its_embedded_vocabulary_matches_the_schema(self):
        # The harness may read both, so drift is caught here rather than by
        # giving the runner an ambient dependency.
        import ast
        source = STUB.read_text(encoding="utf-8")
        literal = source.split("KNOWN_OPERATIONS = frozenset(", 1)[1].split(")", 1)[0]
        embedded = ast.literal_eval(literal)
        schema = json.loads((CONFORMANCE / "vector.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(embedded), set(schema["properties"]["operation"]["enum"]))

    def test_what_python_tolerates_but_json_does_not_is_exit_one(self):
        # A runner that accepted these would accept a file another runner
        # rejects -- the divergence the corpus exists to surface, arriving
        # inside the thing meant to surface it.
        for label, text in [
            ("NaN", '{"id": "a/b", "operation": "digest", "input": {"v": NaN}}'),
            ("duplicate key", '{"id": "a/b", "id": "c/d", "operation": "digest", "input": {}}'),
        ]:
            with self.subTest(case=label):
                self.tmp.write_text(text, encoding="utf-8")
                result = subprocess.run([sys.executable, str(STUB), str(self.tmp)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, EXIT_CANNOT_PROCESS)
                self.assertEqual(result.stdout, "")


class StubIsNotAnImplementationTest(unittest.TestCase):
    def test_every_operation_in_the_vocabulary_reports_error(self):
        vector_schema = json.loads(
            (CONFORMANCE / "vector.schema.json").read_text(encoding="utf-8"))
        tmp = CONFORMANCE / "tests" / "_stub_vocab.json"
        self.addCleanup(lambda: tmp.unlink(missing_ok=True))

        for operation in vector_schema["properties"]["operation"]["enum"]:
            with self.subTest(operation=operation):
                payload = {"id": f"message/sign/{operation}",
                           "operation": operation, "input": {}}
                result = run_stub(payload, tmp)
                self.assertEqual(result.returncode, EXIT_RESULT_PRODUCED)
                self.assertEqual(json.loads(result.stdout)["outcome"], "error")


if __name__ == "__main__":
    unittest.main()
