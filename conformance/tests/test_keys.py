"""The committed test key material is what it says it is (P-001 issue 10).

    python3 -m unittest discover -s conformance/tests

[P-001](../../docs/prds/P-001-conformance-corpus.md) §4.9: *"Fixed Ed25519
keypairs, generated once, committed, and marked test-only in the filename and
in a header comment. Seeds from RFC 8032's test vectors where they fit."*

What this file can check is shape, marking, and internal consistency. What it
cannot check is that a public key really is the one derived from its seed —
that needs an Ed25519 implementation, and putting one here would be a third
implementation of the primitive in the repository, in the one place where being
wrong is invisible. The values come from RFC 8032 verbatim precisely so that
question is answered by a published source rather than by us; when the two
implementations exist, `known_answers` is what settles it.

The negative check is the one worth having: **no private seed appears anywhere
outside this directory**. A corpus vector that inlined one would look harmless
and would make the key file stop being the single place a key lives.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

CONFORMANCE = Path(__file__).resolve().parents[1]
REPO = CONFORMANCE.parent
KEYS = CONFORMANCE / "keys"
KEY_FILE = KEYS / "ed25519-test-only.json"

HEX = re.compile(r"\A[0-9a-f]*\Z")

SEED_BYTES = 32
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64


def load() -> dict:
    return json.loads(KEY_FILE.read_text(encoding="utf-8"))


class MarkingTest(unittest.TestCase):
    def test_the_filename_says_test_only(self):
        # §4.9 asks for the marking in the filename as well as inside, because
        # a file gets copied by its name long before anyone opens it.
        self.assertIn("test-only", KEY_FILE.name)

    def test_the_first_field_says_test_only(self):
        document = load()
        self.assertEqual(next(iter(document)), "test_only",
                         "the warning must be the first thing in the file")
        self.assertIn("NEVER USE", document["test_only"])

    def test_every_key_names_where_it_came_from(self):
        document = load()
        for key_id, key in document["keys"].items():
            with self.subTest(key=key_id):
                self.assertIn("RFC 8032", key["source"])
                self.assertEqual(key["algorithm"], "Ed25519")


class ShapeTest(unittest.TestCase):
    def test_seeds_and_public_keys_are_the_right_length(self):
        document = load()
        self.assertTrue(document["keys"], "no keys; this test would pass vacuously")
        for key_id, key in document["keys"].items():
            with self.subTest(key=key_id):
                for field, expected in (("seed", SEED_BYTES),
                                        ("public_key", PUBLIC_KEY_BYTES)):
                    value = key[field]
                    self.assertRegex(value, HEX,
                                     f"{field} must be lowercase hex")
                    self.assertEqual(len(value), expected * 2,
                                     f"{field} must be {expected} bytes")

    def test_signatures_are_the_right_length(self):
        document = load()
        self.assertTrue(document["known_answers"],
                        "no known answers; this test would pass vacuously")
        for answer in document["known_answers"]:
            with self.subTest(source=answer["source"]):
                self.assertRegex(answer["signature"], HEX)
                self.assertEqual(len(answer["signature"]), SIGNATURE_BYTES * 2)
                self.assertRegex(answer["message"], HEX)

    def test_no_key_is_reused(self):
        # Two ids sharing a keypair would make a wrong-key rejection vector
        # pass for the wrong reason -- the signature would verify.
        document = load()
        seeds = [key["seed"] for key in document["keys"].values()]
        self.assertEqual(len(seeds), len(set(seeds)))
        publics = [key["public_key"] for key in document["keys"].values()]
        self.assertEqual(len(publics), len(set(publics)))

    def test_every_known_answer_names_a_key_that_exists(self):
        document = load()
        for answer in document["known_answers"]:
            with self.subTest(source=answer["source"]):
                self.assertIn(answer["key"], document["keys"])


class ContainmentTest(unittest.TestCase):
    """No private seed lives anywhere but here."""

    def test_no_seed_appears_outside_the_keys_directory(self):
        document = load()
        seeds = {key["seed"] for key in document["keys"].values()}
        self.assertTrue(seeds)

        searched = 0
        for path in sorted(REPO.rglob("*")):
            if not path.is_file() or KEYS in path.parents or path == KEY_FILE:
                continue
            if ".git" in path.parts or path.suffix in (".pdf", ".docx", ".png"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # Binary or unreadable. Not a place a hex seed gets pasted by
                # hand, and skipping it must not abort the sweep over the files
                # that are.
                continue
            searched += 1
            for seed in seeds:
                with self.subTest(path=path.relative_to(REPO)):
                    self.assertNotIn(
                        seed, text,
                        f"{path.relative_to(REPO)} contains a private seed. "
                        f"Keys live in conformance/keys/ and nowhere else, so "
                        f"there is one place to look when one has to change")

        self.assertGreater(searched, 20,
                           "almost nothing was searched; this test would pass "
                           "over a repository it never read")

    def test_public_keys_may_appear_anywhere(self):
        # Stated as a test so the asymmetry is deliberate rather than an
        # omission: a public key in a vector is ordinary, and a rule that
        # forbade it would forbid the corpus doing its job.
        document = load()
        for key in document["keys"].values():
            self.assertNotEqual(key["public_key"], key["seed"])


if __name__ == "__main__":
    unittest.main()
