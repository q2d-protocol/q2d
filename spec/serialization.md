# Q2D Deterministic Serialization — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

Q2D signs exact transmitted bytes, and digests sub-objects. Both need one answer
to the question *which bytes*. This document is that answer.

The profile is **protocol-wide, not suite-scoped.** A signature suite names a
serialization method ([`crypto-suites.md`](crypto-suites.md) §1) and the one
registered suite names this one — but the profile is also what the predicate
registry's `entry_digest` is computed over, where there is no signature and no
suite in play. A future suite needing different bytes would register a different
serialization method under that name; it would not change this one.

Terms: [`terminology.md`](terminology.md). Exchange:
[`core-model.md`](core-model.md). Suites: [`crypto-suites.md`](crypto-suites.md).

---

## 1. Production

**Producers must emit this profile. Verifiers must not depend on it** — §2 is the
second half of that split, and it is the single thing here most likely to be got
wrong.

The profile applies to every structure this specification says is serialized: a
query or response payload, a receipt, `routing`, a signature's protected header,
a registry entry, and every sub-object that is digested.

| Rule | Value |
|---|---|
| Encoding | UTF-8, no BOM |
| Whitespace | none between tokens |
| Object keys | sorted ascending by **UTF-16 code unit** |
| Absent optional fields | omitted, never `null` |
| Numbers | integers only — no exponent, no leading `+`, no leading zeros |
| Floating-point | prohibited |
| Timestamps | as [`core-model.md`](core-model.md) §2.2 spells them |
| Strings | minimal escaping — the two RFC 8259 requires, the five two-character forms it names, `\uXXXX` in lowercase hex for a control character with no short form, and **no escape for any character representable directly** |
| Duplicate keys | not producible; §2 says what a parser does with one |

Determinism is required here and only here. Signing exact transmitted bytes
takes canonicalization out of the security path — a verifier hashes the bytes it
received and never re-derives them — but two producers building the same logical
structure must still emit the same bytes, or two conforming implementations
disagree about a value neither of them got wrong.

**Key ordering is by UTF-16 code unit**, which is not Unicode scalar order and
differs above the Basic Multilingual Plane: U+10000 encodes as the surrogate
pair D800 DC00 and therefore sorts *below* U+FFFD, where scalar order puts it
above. A serializer using its language's default string comparison — ordering by
UTF-8 bytes, or by scalar — produces different bytes for the same value, and a
signature over one does not verify the other. No field name this specification
defines is outside ASCII, so the difference is reachable only through a
predicate's own `public_context`, which is exactly where it will not be noticed.

Ordering is lexicographic rather than by declaration order because declaration
order is brittle as fields are added, and two implementations disagreeing about
it produce no error at the point of disagreement. The rule is stated in the form
JCS (RFC 8785) states it, borrowed as an ordering convention; §4 is the boundary
of that borrowing.

**No signed or digested Q2D structure has a floating-point field, and none may be
added.** Capacity is integer millibits ([`core-model.md`](core-model.md) §3.1),
timestamps are strings, and cardinalities and sizes are integers. IEEE-754
rendering differs between languages, so a single float-valued field would be
enough for two conforming implementations to emit different bytes for the same
value. This removes that class of divergence from the protocol rather than
managing it. Adding such a field is an escalation, not a schema change.

## 2. Parsing

**A verifier must not require this profile of what it reads.** It verifies a
signature over the received bytes and parses them afterwards. The signature
covers the spelling along with everything else, but nothing in the model reads
anything from it: a payload with whitespace between tokens, or keys in another
order, parses to the same value and is accepted.

§1 binds producers. It is not a property a reader may require, and a reader that
required it would be enforcing an obligation it was not given.

A verifier that re-serializes a parsed value in order to check a signature has
reintroduced the dependency the envelope design exists to remove.

Everything below is about reading a **Q2D structure** — a payload, a receipt, a
`routing` object, a registry entry. A file an implementation reads for its own
purposes is not one, and this document does not reach it.

Three things are not production choices, and a parser **rejects** rather than
repairs them.

**Duplicate keys.** A parser resolving them has read one signed payload one of
two ways; a parser resolving them the other way reads the same bytes
differently, and both readings carry the same valid signature. Rejection is the
only resolution two implementations cannot disagree about. Several widely used
JSON libraries resolve silently by last-wins, so this is a rule about what
implementations do by default, not an edge case.

**Floating-point.** §1 prohibits it on production; a parser refuses it on
arrival. The refusal is **syntactic** — on the presence of a fraction or an
exponent, not on the value. Deciding that `1e2` denotes one hundred requires
exponent arithmetic, and `1e400` requires deciding in what.

**Bytes that are not valid UTF-8.** Not decoded with substitution. A replacement
character is a value nobody sent, and inside a signed structure it is one the
signature now appears to cover.

Each is [`core-model.md`](core-model.md) §5.2.1's `malformed` on the wire. The
internal reason distinguishing which of the three occurred is an operator's, and
does not reach the requester — §5.2 governs that separation.

Size limits are a separate matter and are [`core-model.md`](core-model.md) §2.8's.

## 3. What is being serialized

Whether a value is at **protocol level** is a property of *what it is* — which
this specification decides — and not of where it sits in the structure being
serialized.

[`core-model.md`](core-model.md) §2.2 gives the protocol's own fields their
meaning, and §2.4 leaves a predicate's `public_context` to its registry entry to
shape. So:

- A **protocol structure** — a core object, a response, a receipt, `routing`, a
  protected header — carries fields this specification names, and §2.2's
  timestamp spelling binds them.
- A predicate's **`public_context`** is operation data. Its field names are its
  entry's, and §2.2 binds none of them, so a member called `issued_at` means
  whatever the entry says it means.

**Neither changes when the value is serialized on its own.** A `public_context`
digested to produce a `public_context_digest` is the top-level value of that
serialization and is still operation data; being at the top makes it the root of
some bytes, not a protocol structure. Position is not what decides.

An implementation therefore needs **two entry points**, and one is a defect: a
single entry point would have to read the answer off the value's position, which
does not carry it — the same bytes would be held to §2.2 when digested and not
when reached through a query, or the reverse, decided by the call site rather
than by what the value is.

## 4. This is not canonicalization

The profile produces bytes. Nothing re-derives them.

A canonicalization step computes bytes from a *parsed* value, which makes
correctness depend on signer and verifier agreeing about parsing as well as
about serialization. [`crypto-suites.md`](crypto-suites.md) §3 declines to
register a canonicalization suite for that reason and names the hazards it
carries. This profile is the other arrangement: a producer emits these bytes, a
signature covers exactly those bytes, and a verifier checks the signature before
parsing the object it covers — which leaves the JSON parser outside the security
boundary rather than inside it.

So the key-ordering rule is borrowed from JCS as an ordering convention and
nothing more. It is not a canonicalization step, and no Q2D operation
re-serializes a parsed value in order to check a signature. An implementation
that did would satisfy §1 and still be non-conforming, because §2 is the half
that makes §1 safe to require.

## 5. Digests

A **digest** is a string:

```
digest = "<algorithm>:" + lowercase_hex(<algorithm>(bytes))
```

For every digest Q2D 0.1 defines, the algorithm is `sha256` — so
`"sha256:" + lowercase_hex(SHA-256(bytes))`, and `sha256:e3b0c442…` for the
empty input.

**Lowercase, and the prefix is mandatory.** Two implementations that agreed
about every byte hashed would still fail every comparison by disagreeing about
the case of the hex or whether to name the algorithm at all, and a digest is
compared for equality wherever it appears: a receipt against an exchange, a
requester's `registry_digest` against a custodian's entry.

The prefix makes the value **self-describing**, so a second algorithm is
additive rather than ambiguous. This is the one part of a digest that is a
suite's business rather than this document's: when a suite registering a
different hash exists, the algorithm comes from it and this section fixes only
the form. None does today.

This document says what a digest *is*. What each one is taken *over* is
[`core-model.md`](core-model.md) §6 for a receipt's, §2.4.1 for an entry's — and
which of them digest bytes as received rather than a value serialized under §1 is
§3's question, not this section's.
