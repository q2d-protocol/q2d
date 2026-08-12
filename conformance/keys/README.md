# Test key material

**Everything in this directory is test-only, and every private seed in it is
published.** They are RFC 8032's own Ed25519 test vectors. Anyone can read them
out of the RFC, so a deployment that used one would be signing with a key an
attacker already has. The filename says `test-only` and so does the first field
of the file, because a key file is exactly the artefact that gets copied
somewhere else by someone in a hurry.

## Why published keys rather than generated ones

[P-001](../../docs/prds/P-001-conformance-corpus.md) §4.9 asks for seeds from
RFC 8032's test vectors *"where they fit, so key handling is checkable against
an independently published source before any Q2D structure is involved"*.

That ordering matters. When the two implementations exist and a signature
disagrees between them, the first question is whether the disagreement is in
Q2D's canonicalization or in the Ed25519 underneath it. If the keys are ours,
nothing answers that: both implementations are being compared against each
other and against nothing else. If the keys are RFC 8032's, the RFC's own
message/signature pairs answer it before any Q2D structure is involved — an
implementation that cannot reproduce them has a problem that is not about this
protocol, and one that can has been checked against a source neither
implementation's author wrote.

Generating our own would also mean generating them *with* something. Whatever
that was would be a third implementation of Ed25519 in the repository, in the
one place where being wrong is invisible.

So nothing here derives a public key from a seed — and that is a rule rather
than a check. No test can decide whether a file implements Ed25519; what is
checked is that the harness imports nothing outside the standard library, and
that no private seed appears anywhere outside this directory.

## What is here

`ed25519-test-only.json`:

- **`keys`** — three keypairs, keyed by the `key_id` a vector's `input` names.
  `test-requester-1` and `test-custodian-1` are the two sides of an ordinary
  exchange; `test-requester-2` exists so a vector can present a signature from
  the wrong key, which is a rejection the corpus has to contain.
- **`known_answers`** — the RFC's published message/signature pairs for those
  same keys. Reference data, not vectors: turning them into `suite/` vectors is
  [P-001](../../docs/prds/P-001-conformance-corpus.md) issue 13, and inventing
  the section here would be authoring a corpus section from a key file.

Seeds and public keys are 32 bytes, signatures 64, all lowercase hex. The
`seed` is RFC 8032's "secret key": the 32-byte seed, not an expanded private
key.

## What is not here, and why

**No signature over a Q2D structure.** Not because one cannot be produced —
[`tools/author_vectors.py`](../../tools/author_vectors.py) produces them — but
because a signature belongs in the vector that asserts it, not in the key file.
This directory holds keys and the RFC's own known answers; anything signed over
a Q2D structure is corpus data.

That was [P-001](../../docs/prds/P-001-conformance-corpus.md) §10's question
about how signed vectors get authored at all, and it is a real problem rather
than a scheduling one: the corpus is supposed to be the thing an implementation
is checked against, so a corpus whose signatures were produced *by* an
implementation checks that implementation against itself.

**Settled:** [`tools/author_vectors.py`](../../tools/author_vectors.py) produces
them from the specification text, written before either implementation exists.
Its Ed25519 comes from RFC 8032 §5.1 and it refuses to run until it reproduces
the `known_answers` in this directory — which is what those are for, beyond
documenting the source of the keys.

The protected header that string needs is
[`crypto-suites.md`](../../spec/crypto-suites.md) §3's, which was the last thing
missing and is now specified. Nothing blocks authoring a signed vector.
