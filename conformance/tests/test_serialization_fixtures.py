"""The Python authoring tool agrees with the fixtures the other two are held to.

    python3 -m unittest discover -s conformance/tests

## What this is for

[`testdata/README.md`](../../testdata/README.md) carries two fixtures, and each
is asserted three times — once per serializer, by tests that share no code. This
is the Python third of both; `cargo test` and `go test ./...` are the others.

`canonical-query` is a real query and is P-002 §7's first acceptance criterion.
`profile-edges` is not a Q2D message at all: it exists because the canonical
query is entirely ASCII, carries no escape, and has no integer near a boundary,
so three serializers could agree on it while disagreeing about most of §4.2.
They did — see that fixture's own note.

Python is the implementation that **generated** both files, so on its own this
assertion is circular. It is here for the case that is not circular: somebody
changes [`tools/author_vectors.py`](../../tools/author_vectors.py)'s profile and
regenerates a fixture, and the Rust and Go tests go red while this one stays
green. That pattern — one green and two reds — says the serializer changed;
three reds says a fixture was hand-edited. Neither is distinguishable if this
test does not exist.

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

FIXTURES = ROOT / "testdata"


def serialized(name: str) -> bytes:
    return (FIXTURES / f"{name}.serialized").read_bytes()


def readable(name: str) -> object:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class CanonicalQueryTest(unittest.TestCase):
    def test_the_authoring_tool_produces_the_fixture_bytes(self):
        self.assertEqual(av.serialize(am.QUERY), serialized("canonical-query"))

    def test_the_readable_copy_is_the_same_query(self):
        # `canonical-query.json` exists so a reader can see the structure the
        # other two tests build by hand. It is a second copy of QUERY, so it can
        # drift from it; this is what stops it drifting silently. Compared as
        # parsed objects rather than bytes, because the readable copy is
        # pretty-printed and the point is that it says the same thing.
        self.assertEqual(readable("canonical-query"), am.QUERY)

    def test_the_fixture_carries_no_signature_value(self):
        # E-31: under `eddsa-jws-2026` the signature is the compact form's third
        # segment, so a payload carrying `signature.value` would be signing
        # itself. Asserted over the serialized bytes, since that is what a
        # verifier sees.
        text = serialized("canonical-query").decode("utf-8")
        self.assertIn('"signature":{"key_id"', text)
        self.assertNotIn('"value"', text)


class ProfileEdgesTest(unittest.TestCase):
    def test_the_authoring_tool_produces_the_fixture_bytes(self):
        # Unlike the query, this fixture has no generator: the `.json` file is
        # the source and the `.serialized` file is what the profile makes of it.
        # So this is a real check on the Python side too, not only a guard
        # against silent regeneration.
        self.assertEqual(av.serialize(readable("profile-edges")), serialized("profile-edges"))

    def test_the_supplementary_key_sorts_before_the_bmp_one(self):
        # The property the canonical query could not carry, asserted on the
        # bytes rather than left to the fixture's shape: U+10000 encodes as the
        # surrogate pair D800 DC00 under UTF-16, so it sorts below U+FFFD --
        # where Unicode scalar order, which is what a Rust `BTreeMap<String>`
        # and a Go byte comparison both give, puts it above.
        text = serialized("profile-edges").decode("utf-8")
        self.assertLess(text.index('"\U00010000"'), text.index('"�"'))

    def test_the_characters_go_escapes_by_default_are_not_escaped(self):
        # `encoding/json` escapes <, > and & unless told otherwise. They are
        # representable directly, so §4.2's minimal-escaping rule forbids it,
        # and the Go serializer is hand-written rather than delegating for
        # exactly this reason.
        self.assertIn("<a>&b'c/d", serialized("profile-edges").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
