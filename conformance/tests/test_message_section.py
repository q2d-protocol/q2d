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


class ExpectedStateTest(unittest.TestCase):
    """What the section contains today, asserted rather than described.

    `.github/workflows/checks.yml` prescribes an assertion over the expected
    state instead of a job that is red by design, and this is `message/`'s: the
    section is positive-only, because every rejection it wants needs an
    `external_reason` and that vocabulary does not exist
    ([`open-escalations.md`](../../docs/open-escalations.md) E-33).

    It turns red the day a rejection vector lands, which is the day to delete
    it and assert what the rejections say instead.
    """

    def test_every_vector_expects_ok(self):
        outcomes = {v["expect"]["outcome"] for v in vectors()}
        self.assertEqual(outcomes, {"ok"},
                         "a rejection vector landed in message/ — E-33 has "
                         "presumably closed, so replace this assertion with "
                         "one over what the rejections assert")

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
