# Three-way serialization fixtures

Two documents, each serialized under [P-002](../docs/prds/P-002-message-envelope.md)
§4.2's deterministic production profile, and each held to those exact bytes by
**three implementations in three languages, by tests that share no code**:

| Implementation | Tests |
|---|---|
| Python — [`tools/author_vectors.py`](../tools/author_vectors.py) | [`conformance/tests/test_serialization_fixtures.py`](../conformance/tests/test_serialization_fixtures.py) |
| Rust — [`src/value.rs`](../src/value.rs) | [`tests/canonical_query.rs`](../tests/canonical_query.rs), [`tests/profile_edges.rs`](../tests/profile_edges.rs) |
| Go — [`value.go`](../value.go) | [`canonical_query_test.go`](../canonical_query_test.go), [`profile_edges_test.go`](../profile_edges_test.go) |

## `canonical-query`

The query [`tools/author_message.py`](../tools/author_message.py) signs: every
field [`core-model.md`](../spec/core-model.md) §2 marks required, and no optional
one, so the bytes are the smallest a conforming requester produces.

This is P-002 §7's first acceptance criterion — both implementations serialize
the same logical query to byte-identical output — with the authoring tool added
as a third reading. The third one matters because the corpus's expected bytes
come from it: two implementations agreeing with each other but not with the
authoring tool would pass every vector and still be wrong.

## `profile-edges`

**Not a Q2D message**, and nothing in it should be read as one. Every entry is a
property of §4.2 rather than a protocol field: key ordering above the BMP, the
empty key, every escape RFC 8259 names, the characters `encoding/json` escapes
by default and this profile must not, `i64`'s two boundaries, an empty object
and an empty array, and a present null.

It exists because the canonical query could not catch a real divergence. The
query is entirely ASCII, carries no escape, and has no integer near a boundary,
so three serializers can agree on it while disagreeing about most of the
profile — and they did. The Rust side emitted `BTreeMap` order, which is Unicode
scalar order, where §4.2 asks for UTF-16 code-unit order; the two differ only
above the BMP, and no field name in `core-model.md` §2 is outside ASCII. Codex
caught it in review. This fixture is the thing that would have.

The general lesson, which is why the fixture is kept rather than the case being
folded into a unit test: **a corpus made of realistic documents tests the
protocol, not the profile.** The profile's edges have to be authored on purpose,
because no *protocol field* reaches them — every field name in `core-model.md`
§2 is ASCII, and every value the protocol itself defines is a bounded string, a
count, or an enum.

They are reachable, though, and that is the reason this matters rather than a
reason it does not. A predicate's `public_context` is operation-defined (§2.6):
a conforming query can carry a non-ASCII key, a string needing every escape, or
an integer at the boundary, and all of it goes through §4.2 into the signed
payload. So these are edges a real message can reach and no *realistic-looking*
message will — which is the combination that makes them worth authoring and
easy to miss.

## What is *not* here

Refusals. All three implementations agree on what the profile rejects, and
those cases live in three parallel test files rather than a fixture:
[`tests/refusal.rs`](../tests/refusal.rs), [`refusal_test.go`](../refusal_test.go),
and `RefusalTest` in the Python file above.

What they agree on is `core-model.md` §2.2's timestamp, in the fields §2.2 names
and in the three places it names them — the core object, `routing`, and a
receipt. §2.2 states that reach explicitly, and stops there: a string in
operation-defined data is the predicate's, and an entry constrains its own
through `format: date-time` in its registry schema
([`scope.md`](../spec/scope.md) §4.1). [E-36](../docs/open-escalations.md),
closed as C.

Three of the refusals exist in one language and not the others, because each
language's types admit something the profile cannot emit and they are not the
same something:

| Refused | Where it can arise |
|---|---|
| Invalid UTF-8 | Go — a `string` is arbitrary bytes; ranging over one would substitute U+FFFD and sign a value the caller never supplied |
| An unpaired surrogate | Python — a `str` is code points, and that one has no UTF-8 encoding |
| A nil value, typed or untyped | Go — the `Value` interface admits both, and no concrete type is either. A `*String` is in the method set because the write methods have value receivers, so a nil one is an interface holding a type and no value: not equal to `nil`, and a panic on dispatch. A panic is not a refusal |
| An integer outside −2^63 … 2^63 − 1 | Python — `int` is arbitrary-precision, and both value models are not. The range is `scope.md` §4.1's ([E-37](../docs/open-escalations.md)), which chose it *because* it is the width every conforming producer carries exactly |

Rust appears in none of those rows, which is the point of the table rather than
a gap in it: `String` cannot hold invalid UTF-8 or a lone surrogate, `Value` is
an enum with no null state, and `i64` is the bound. Each row is a place where
one language had to be taught what another gets from its types, so that the set
of values that can be signed is the same on all three sides.

Three lists that must stay identical is the arrangement this directory exists
to avoid. It is temporary: a refused document cannot be a fixture until Rust and
Go can parse one, which is P-002 issue 4. When it lands, the shared cases move
here and the table above stays where it is, because those cases have no document
to be a fixture of.

Agreement on refusals matters as much as agreement on bytes — a serializer that
matches on everything the others accept and *also* emits bytes for what they
refuse is not the same serializer.

## Parsing is a two-way agreement, not three

Both fixtures are also **round-tripped**: parsed back and re-serialized, and the
bytes must not move. `tests/canonical_query.rs`, `tests/profile_edges.rs`, and
the two Go files do this; the Python column does not, and will not.

`tools/author_vectors.py` produces bytes and never consumes a payload. P-002 §5
gives `parse_core` to the implementations, and §7 asks for agreement between
*both implementations* — two is the requirement rather than a shortfall against
three. The serializer needed a third reading because the corpus's expected bytes
come from Python; nothing about parsing has that dependency.

What the round trip adds over the byte fixtures is the other direction. A
serializer and a parser can each be wrong in a way the other hides — a parser
that dropped an escape and a serializer that re-added it would agree with each
other and with nothing else — so the fixtures pin the bytes and these pin the
inverse.

## Regenerating

`canonical-query.json` is a readable copy of `author_message.py`'s `QUERY`; the
Python test asserts the two are the same document, so it cannot drift silently.
`profile-edges.json` has no generator — it *is* the source, and its `.serialized`
sibling is what the profile makes of it.

Either `.serialized` file is regenerated by serializing its `.json` with
`author_vectors.serialize`. Doing so and finding the Rust and Go tests red while
the Python one stays green is the intended signal: the serializer changed. Three
reds means a fixture was hand-edited.
