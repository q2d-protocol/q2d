"""The Python authoring tool agrees with the fixture the other two are held to.

    python3 -m unittest discover -s conformance/tests

## What this is for

[`testdata/README.md`](../../testdata/README.md) names three tests, one per
implementation, each asserting that its own serializer turns the canonical query
into the exact bytes of `testdata/canonical-query.serialized`. This is the
Python third; `cargo test canonical` and `go test -run Canonical` are the others.

Python is the implementation that **generated** those bytes, so on its own this
assertion is circular. It is here for the case that is not circular: somebody
changes `tools/author_vectors.py`'s profile and regenerates the fixture, and the
Rust and Go tests go red while this one stays green. That pattern — one red pair
and one green — says the serializer changed. Three reds would say the fixture
was hand-edited. Neither is distinguishable if this test does not exist.

The corpus's expected bytes come from the same Python serializer, which is why
the third reading matters: two implementations agreeing with each other but not
with the authoring tool would pass every vector and still be wrong.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import author_message as am  # noqa: E402  (after sys.path)
import author_vectors as av  # noqa: E402  (after sys.path)

FIXTURE_DIR = ROOT / "testdata"


class CanonicalQueryTest(unittest.TestCase):
    def test_the_authoring_tool_produces_the_fixture_bytes(self):
        self.assertEqual(
            av.serialize(am.QUERY),
            (FIXTURE_DIR / "canonical-query.serialized").read_bytes(),
        )

    def test_the_readable_copy_is_the_same_query(self):
        # `canonical-query.json` exists so a reader can see the structure the
        # other two tests build by hand. It is a second copy of QUERY, so it can
        # drift from it; this is what stops it drifting silently. Compared as
        # parsed objects rather than bytes, because the readable copy is
        # pretty-printed and the point is that it says the same thing.
        readable = json.loads((FIXTURE_DIR / "canonical-query.json").read_text())
        self.assertEqual(readable, am.QUERY)

    def test_the_fixture_carries_no_signature_value(self):
        # E-31: under `eddsa-jws-2026` the signature is the compact form's third
        # segment, so a payload carrying `signature.value` would be signing
        # itself. Asserted over the serialized bytes, since that is what a
        # verifier sees, and in all three languages, since all three build the
        # payload independently.
        text = (FIXTURE_DIR / "canonical-query.serialized").read_text("utf-8")
        self.assertIn('"signature":{"key_id"', text)
        self.assertNotIn('"value"', text)


if __name__ == "__main__":
    unittest.main()
