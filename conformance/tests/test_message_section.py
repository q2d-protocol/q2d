"""The committed `message/` section still matches its author (P-001 issue 12).

    python3 -m unittest discover -s conformance/tests

`message/`'s vectors assert the exact bytes a conforming implementation
produces, and those bytes come from
[`tools/author_vectors.py`](../../tools/author_vectors.py) by way of
[`tools/author_message.py`](../../tools/author_message.py). Committing them
without a way to reproduce them would leave the corpus asserting numbers nobody
can re-derive — and the failure that catches is quiet in the same way the
registry fold's is: somebody changes the serializer, every implementation is
measured against bytes no producer now emits, and the disagreement is in neither
the implementation nor the corpus.

**This does not make the vectors derived data.** An implementation is compared
against what is committed. The check keeps the committed bytes and the tool that
produced them from drifting apart; it does not make the tool authoritative at
run time.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTHOR = REPO / "tools" / "author_message.py"
SECTION = REPO / "conformance" / "corpus" / "message"


def vectors() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(SECTION.rglob("*.json"))]


class AuthoredSectionTest(unittest.TestCase):
    def test_the_committed_section_matches_its_author(self):
        result = subprocess.run([sys.executable, str(AUTHOR), "--check"],
                                capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0,
                         f"{result.stdout}\n{result.stderr}")

    def test_the_section_is_not_empty(self):
        # A generator producing nothing satisfies the check above vacuously.
        self.assertGreater(len(vectors()), 0)


# core-model.md §5.2.1's closed vocabulary, embedded rather than parsed out of
# the spec. A test that read the list from the document it is checking against
# would pass whatever that document said, including a typo.
EXTERNAL_REASONS = frozenset({
    "malformed", "unsupported_version", "unsupported_suite", "routing_mismatch",
    "expired",          # Tier A, distinct
    "unauthenticated",  # Tier B, one class
    "unavailable",      # Tier C, as the reference registry declares it
})


class RejectionTest(unittest.TestCase):
    """What this section's rejections assert.

    It replaces an assertion that the section was positive-only, which held
    while E-33 was open and no `external_reason` had an identifier. That
    escalation closed by enumerating them in §5.2.1, so the thing worth
    asserting is that these vectors use that vocabulary and keep the two halves
    of a rejection apart.
    """

    def rejections(self):
        return [v for v in vectors() if v["expect"]["outcome"] == "rejected"]

    def test_the_section_has_rejections(self):
        # CLAUDE.md: the interesting behaviour of this protocol is what it
        # refuses. A section that lost its negative vectors would still lint.
        self.assertGreaterEqual(len(self.rejections()), 3)

    def test_every_external_reason_is_in_the_vocabulary(self):
        for vector in self.rejections():
            with self.subTest(vector=vector["id"]):
                self.assertIn(
                    vector["expect"]["rejection"]["wire"]["external_reason"],
                    EXTERNAL_REASONS)

    def test_the_internal_reason_is_never_the_external_one(self):
        # P-001 §4.6 and core-model.md §5.2: they are separate values, and an
        # implementation deriving one from the other has lost the property the
        # corpus is checking. A vector whose two halves were equal would be
        # asserting the leak rather than the separation.
        for vector in self.rejections():
            rejection = vector["expect"]["rejection"]
            with self.subTest(vector=vector["id"]):
                self.assertNotEqual(rejection["internal_reason"],
                                    rejection["wire"]["external_reason"])

    def test_rejections_project_rather_than_assert_a_whole_response(self):
        # These vectors test verification and the routing comparison, not
        # response construction. Asserting a receipt would claim this section
        # checks something it does not, and `denial/` is where a whole
        # normalized response belongs -- P-009's to author, and it may not
        # project.
        for vector in self.rejections():
            with self.subTest(vector=vector["id"]):
                self.assertEqual(set(vector["expect"]["rejection"]["wire"]),
                                 {"status", "external_reason"})

    def test_the_signed_vector_compares_as_bytes(self):
        # The reason `message/sign/` exists. A `semantic` comparison here would
        # accept two implementations that serialize the same object
        # differently, which is the one thing this vector is for.
        signing = [v for v in vectors() if v["operation"] == "sign_query"]
        self.assertTrue(signing)
        for vector in signing:
            with self.subTest(vector=vector["id"]):
                self.assertEqual(vector["expect"]["comparison"], "bytes")
                self.assertIsInstance(vector["expect"]["output"], str)

    def test_no_payload_carries_a_signature_value(self):
        # E-31: under `eddsa-jws-2026` the value is the compact form's third
        # segment, so a payload carrying one would sign itself. Asserted over
        # every query any vector supplies or expects, because a vector that
        # reintroduced it would be asserting bytes no conforming producer emits.
        for vector in vectors():
            for where, obj in (("input", vector["input"].get("query")),
                               ("expect", vector["expect"].get("output"))):
                if not isinstance(obj, dict):
                    continue
                with self.subTest(vector=vector["id"], where=where):
                    self.assertNotIn("value", obj.get("signature", {}))


if __name__ == "__main__":
    unittest.main()
