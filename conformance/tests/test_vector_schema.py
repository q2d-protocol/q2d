"""Tests for the vector schema and the lint checks around it (P-001 issue 1).

    python3 -m unittest discover -s conformance/tests

The negative cases outnumber the positive ones, which is the correct proportion
for this repository: the interesting behaviour is what the corpus refuses.
"""

from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
sys.path.insert(0, str(HARNESS))

import lint as lint_module  # noqa: E402
import schema as schema_module  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OK_VECTOR = FIXTURES / "valid" / "message" / "query-minimal.json"
REJECTED_VECTOR = FIXTURES / "valid" / "denial" / "unknown-predicate.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_lint(corpus: Path) -> tuple[int, str]:
    captured = io.StringIO()
    with redirect_stdout(captured):
        code = lint_module.lint(corpus)
    return code, captured.getvalue()


class SchemaSubsetTest(unittest.TestCase):
    """The validator must enforce everything the schema states, or refuse."""

    def test_vector_schema_is_within_the_supported_subset(self):
        schema_module.assert_supported(lint_module.load_schema())

    def test_an_unimplemented_keyword_is_refused_rather_than_ignored(self):
        with self.assertRaises(schema_module.UnsupportedKeyword):
            schema_module.assert_supported({"type": "integer", "multipleOf": 2})

    def test_refusal_reaches_nested_subschemas(self):
        nested = {"type": "object", "properties": {"a": {"type": "array", "uniqueItems": True}}}
        with self.assertRaises(schema_module.UnsupportedKeyword):
            schema_module.assert_supported(nested)


class PublishedCopyTest(unittest.TestCase):
    """The schema's $id names a URL, so something has to serve that URL.

    website/ is served as q2d.dev, so the file is copied there rather than
    referenced. Two copies drift; this is what stops them, and it names which
    one is stale rather than only that they differ.
    """

    def test_every_published_schema_is_served_byte_identically(self):
        conformance = lint_module.REPO_ROOT / "conformance"
        served_root = lint_module.REPO_ROOT / "website" / "conformance"
        schemas = sorted(conformance.glob("*.schema.json"))
        self.assertTrue(schemas, "no schemas found to check")
        for source in schemas:
            served = served_root / source.name
            with self.subTest(schema=source.name):
                self.assertTrue(served.exists(),
                                f"{served} is missing; the schema's $id would 404")
                self.assertEqual(
                    source.read_bytes(), served.read_bytes(),
                    f"{served} is stale -- copy {source} over it")

    def test_every_published_schema_declares_the_url_that_serves_it(self):
        # A $id nobody serves is a URL this project publishes and does not
        # answer; a $id that does not match where the file sits is worse,
        # because the drift check above would pass while the URL was wrong.
        for source in sorted((lint_module.REPO_ROOT / "conformance").glob("*.schema.json")):
            with self.subTest(schema=source.name):
                declared = json.loads(source.read_text(encoding="utf-8"))["$id"]
                self.assertEqual(declared,
                                 f"https://q2d.dev/conformance/{source.name}")


class ValidVectorTest(unittest.TestCase):
    def setUp(self):
        self.schema = lint_module.load_schema()

    def test_ok_shape_validates(self):
        self.assertEqual(schema_module.validate(load(OK_VECTOR), self.schema), [])

    def test_rejected_shape_validates(self):
        self.assertEqual(schema_module.validate(load(REJECTED_VECTOR), self.schema), [])

    def test_step_is_optional(self):
        vector = load(REJECTED_VECTOR)
        del vector["expect"]["rejection"]["step"]
        self.assertEqual(schema_module.validate(vector, self.schema), [])


class MalformedVectorTest(unittest.TestCase):
    """Each mutation of a valid vector must be rejected by the schema alone."""

    def setUp(self):
        self.schema = lint_module.load_schema()

    def assert_rejected(self, vector: dict, because: str):
        errors = schema_module.validate(vector, self.schema)
        self.assertTrue(errors, f"accepted a vector that {because}")

    def mutate(self, source: Path = OK_VECTOR, **_):
        return copy.deepcopy(load(source))

    def test_missing_requirement(self):
        vector = self.mutate()
        del vector["requirement"]
        self.assert_rejected(vector, "cites no requirement")

    def test_empty_requirement(self):
        vector = self.mutate()
        vector["requirement"] = []
        self.assert_rejected(vector, "cites an empty requirement list")

    def test_missing_comparison(self):
        vector = self.mutate()
        del vector["expect"]["comparison"]
        self.assert_rejected(vector, "leaves comparison unset")

    def test_unknown_comparison_mode(self):
        vector = self.mutate()
        vector["expect"]["comparison"] = "approximate"
        self.assert_rejected(vector, "invents a comparison mode")

    def test_unsettled_operation_name(self):
        # An anticipated Stage 5-8 name. It becomes valid when P-001 issue 17
        # settles the vocabulary, and not before.
        vector = self.mutate()
        vector["operation"] = "http_exchange"
        self.assert_rejected(vector, "uses an operation the vocabulary does not carry")

    def test_unknown_section(self):
        vector = self.mutate()
        vector["section"] = "receipts"
        self.assert_rejected(vector, "misspells its section")

    def test_unknown_top_level_field(self):
        vector = self.mutate()
        vector["skip"] = True
        self.assert_rejected(vector, "carries a field the harness would ignore")

    def test_expecting_a_runner_error(self):
        vector = self.mutate()
        vector["expect"] = {"outcome": "error", "output": {}, "comparison": "bytes"}
        self.assert_rejected(vector, "expects a runner fault as a passing outcome")

    def test_ok_without_output(self):
        vector = self.mutate()
        del vector["expect"]["output"]
        self.assert_rejected(vector, "expects success with nothing to compare")

    def test_rejected_without_rejection(self):
        vector = self.mutate(REJECTED_VECTOR)
        del vector["expect"]["rejection"]
        self.assert_rejected(vector, "expects a rejection with no internal reason or wire response")

    def test_rejection_without_wire_response(self):
        vector = self.mutate(REJECTED_VECTOR)
        del vector["expect"]["rejection"]["wire"]
        self.assert_rejected(vector, "reports one half of a rejection")

    def test_step_outside_the_processing_order(self):
        for step in (0, 20, "9", "a", "1a", "19z", "9A"):
            vector = self.mutate(REJECTED_VECTOR)
            vector["expect"]["rejection"]["step"] = step
            with self.subTest(step=step):
                self.assert_rejected(vector, f"names step {step!r}")

    def test_a_lettered_step_is_expressible(self):
        # core-model.md §4 carries step 9a, the rate-limit check, and it is
        # precisely the step whose ordering matters: a limiter running after
        # registry resolution leaves unknown predicates unlimited.
        vector = self.mutate(REJECTED_VECTOR)
        vector["expect"]["rejection"]["step"] = "9a"
        self.assertEqual(schema_module.validate(vector, self.schema), [])

    def test_identifier_without_a_section_segment(self):
        vector = self.mutate()
        vector["id"] = "message"
        self.assert_rejected(vector, "has an unstructured identifier")

    def test_empty_description(self):
        vector = self.mutate()
        vector["description"] = ""
        self.assert_rejected(vector, "describes itself with nothing")


class LintTest(unittest.TestCase):
    def test_valid_corpus_passes(self):
        code, output = run_lint(FIXTURES / "valid")
        self.assertEqual(code, 0, output)
        self.assertIn("2/2 vectors valid", output)

    def test_empty_corpus_passes_and_says_so(self):
        # A committed empty directory rather than a temporary one, so the suite
        # runs where no temporary directory is writable.
        code, output = run_lint(FIXTURES / "empty")
        self.assertEqual(code, 0, output)
        self.assertIn("corpus is empty", output)

    def test_misplaced_vector_is_rejected(self):
        code, output = run_lint(FIXTURES / "misplaced")
        self.assertEqual(code, 1)
        self.assertIn("but the file sits at", output)

    def test_duplicate_identifier_is_rejected(self):
        code, output = run_lint(FIXTURES / "duplicate-id")
        self.assertEqual(code, 1)
        self.assertIn("already used by", output)

    def test_citation_of_an_absent_claim_is_rejected(self):
        code, output = run_lint(FIXTURES / "bad-citation")
        self.assertEqual(code, 1)
        self.assertIn("is not a claim in spec/claims.md", output)

    def test_citation_of_an_absent_spec_file_is_rejected(self):
        code, output = run_lint(FIXTURES / "bad-citation")
        self.assertEqual(code, 1)
        self.assertIn("is not a document in", output)

    def test_citation_of_an_absent_section_is_rejected(self):
        # The file existing is not enough: core-model.md#99.7 would otherwise
        # read as traceability to anyone who does not go and look.
        code, output = run_lint(FIXTURES / "bad-citation")
        self.assertEqual(code, 1)
        self.assertIn("cites a section core-model.md does not have", output)

    def test_threat_model_citations_resolve(self):
        errors = lint_module.citation_errors(
            {"requirement": ["trust-matrix.md#5"]},
            *lint_module.known_identifiers(), lint_module.citable_sections())
        self.assertEqual(errors, [])

    def test_an_ordering_vector_must_state_its_step(self):
        # The section exists to assert *which* step rejected. A vector there
        # with no step asserts nothing about ordering and would pass silently,
        # because §4.8 holds a vector only to the step it states.
        code, output = run_lint(FIXTURES / "ordering-without-step")
        self.assertEqual(code, 1)
        self.assertIn("must state the step", output)

    def test_a_section_rule_never_crashes_on_a_malformed_vector(self):
        # Section rules run alongside the schema's checks, not after them, so
        # they are handed vectors of any shape. One malformed vector must not
        # abort the run that was going to report it.
        code, output = run_lint(FIXTURES / "ordering-malformed")
        self.assertEqual(code, 1)
        self.assertIn("expected object, found null", output)

    def test_malformed_json_is_rejected(self):
        code, output = run_lint(FIXTURES / "malformed-json")
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", output)

    def test_what_python_tolerates_but_json_does_not_is_rejected(self):
        # Both files parse under a default json.loads. A Rust or Go runner
        # rejects them, and a corpus that means two things is not a contract.
        code, output = run_lint(FIXTURES / "not-json")
        self.assertEqual(code, 1)
        self.assertIn("NaN is not valid JSON", output)
        self.assertIn("duplicate object key 'comparison'", output)
        self.assertIn("0/2 vectors valid", output)

    def test_missing_corpus_directory_is_an_error(self):
        with self.assertRaises(lint_module.CorpusError):
            lint_module.lint(FIXTURES / "does-not-exist")


if __name__ == "__main__":
    unittest.main()
