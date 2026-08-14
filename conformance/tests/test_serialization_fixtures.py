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


class RefusalTest(unittest.TestCase):
    """What the profile refuses, and where it stops caring.

    The same cases as [`tests/refusal.rs`](../../tests/refusal.rs) and
    [`refusal_test.go`](../../refusal_test.go). They are not driven from a
    shared fixture because Rust and Go cannot yet parse one — that is P-002
    issue 4, and this docstring is the reason to revisit the three lists when it
    lands.

    Agreement on refusals matters as much as agreement on bytes. A serializer
    that produces the same bytes for every document the others accept, and also
    produces bytes for documents they refuse, is not the same serializer.
    """

    def refused(self, value):
        with self.assertRaises(av.ProfileError) as raised:
            av.serialize(value)
        return str(raised.exception)

    def accepted(self, value):
        av.serialize(value)  # raising is the failure

    @staticmethod
    def public_context(pairs):
        return {"predicate": {"public_context": pairs}}

    def test_a_malformed_timestamp_field_is_refused(self):
        # By name: §2.2 gives `issued_at` a timestamp, so anything else in it is
        # wrong however wrong it is.
        self.refused({"issued_at": "2026-07-31t09:00:00Z"})
        self.refused({"expires_at": "2026-99-99T99:99:99Z"})
        self.refused({"decided_at": "not a date at all"})
        self.refused({"issued_at": 42})
        self.refused({"issued_at": None})

    def test_a_timestamp_outside_a_timestamp_field_is_left_alone(self):
        # §2.2 states its spelling for the fields it names. A string somewhere
        # else is not a Q2D timestamp however much it looks like one, and §2.6
        # says a predicate's `public_context` may mean anything at all.
        #
        # Whether §2.2 should reach further is **E-36, open**. All three
        # implementations do what §2.2 states and no more until it is decided.
        # If E-36 closes as A, these two become refusals and nothing else moves.
        self.accepted(self.public_context({"booked_for": "2026-07-31T19:30:00+01:00"}))
        self.accepted(["2026-07-31T09:00:00.000Z"])

    def test_the_field_name_rule_applies_only_at_protocol_level(self):
        # §2.6: a predicate's `public_context` may mean anything at all.
        self.accepted(self.public_context({"issued_at": "whenever the kitchen opens"}))

    def test_routing_and_receipt_re_enter_protocol_level(self):
        self.refused({"routing": {"expires_at": "2026-07-31T09:00:00z"}})
        self.refused({"receipt": {"decided_at": "2026-02-30T00:00:00Z"}})
        self.accepted(self.public_context({"receipt": {"decided_at": "on the night"}}))

    def test_a_string_the_profile_cannot_encode_is_refused(self):
        # The counterpart of `refusal_test.go`'s
        # `TestInvalidUTF8IsRefusedRatherThanSubstituted`. Each language has a
        # string type that can hold something UTF-8 cannot represent, and they
        # are not the same thing: Python's `str` admits an unpaired surrogate,
        # Go's `string` admits arbitrary bytes, and Rust's `String` admits
        # neither. All three refuse, so the set of values that can be signed is
        # the same on all three sides.
        lone_surrogate = "\ud800"
        self.refused({"a": lone_surrogate})
        self.refused({lone_surrogate: "a"})

    def test_operation_data_is_serializable_on_its_own(self):
        # P-002 §4.7 digests `public_context` as a sub-object, so it becomes the
        # root of a serialization. If protocol level were read off the nesting,
        # the same bytes would be held to §2.2 when digested and not when
        # reached through a query — one object, two rules, decided by the call
        # site.
        context = {"issued_at": "whenever the kitchen opens"}
        self.assertEqual(av.serialize_operation_data(context),
                         b'{"issued_at":"whenever the kitchen opens"}')
        with self.assertRaises(av.ProfileError):
            av.serialize(context)
        # The two differ in what they refuse, not in what they emit.
        real = {"issued_at": "2026-07-31T09:00:00Z"}
        self.assertEqual(av.serialize(real), av.serialize_operation_data(real))

    def test_an_integer_outside_the_pair_s_range_is_refused(self):
        # E-37. Python's `int` is arbitrary-precision and both value models hold
        # a signed 64-bit one, so without this the tool could author a vector
        # neither implementation can reproduce — and the first sign would be a
        # byte disagreement blamed on the implementations rather than the
        # vector. The boundaries themselves serialize, since `profile-edges`
        # carries both and all three agree on them.
        self.refused({"a": 2**63})
        self.refused({"a": -2**63 - 1})
        self.accepted({"a": 2**63 - 1})
        self.accepted({"a": -2**63})

    def test_a_refusal_names_the_field_and_nothing_else(self):
        message = self.refused({
            "issued_at": "2026-07-31t09:00:00Z",
            "nonce": "Ux7kFQ2mS0aVvJ1cPzN4bw",
        })
        self.assertIn("issued_at", message)
        self.assertNotIn("Ux7kFQ2mS0aVvJ1cPzN4bw", message)
        # And not the refused value either. This serializer runs over responses
        # and receipts, whose strings derive from data the requester never sees,
        # so an error message is a disclosure path.
        self.assertNotIn("2026-07-31t09:00:00Z", message)


if __name__ == "__main__":
    unittest.main()
