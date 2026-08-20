# P-002 — Message envelope and canonical structures

| Field | Detail |
|---|---|
| PRD | P-002 |
| Stage | 1 |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md) — corpus format |
| Blocks | P-003, P-004, P-005, P-006, P-010, P-011, P-016 — ~~P-012~~ **deferred 2026-08-19** |
| Pairs with | [P-003](P-003-crypto-suites.md) — this PRD produces the bytes P-003 signs |

---

## 1. Purpose

Define the message envelope, the layout of the core object inside it, the
advisory routing projection, and the digest construction the receipt depends on.

This PRD owns **what gets signed and how it is laid out**. P-003 owns **how it is
signed**. The boundary is exact: P-002 produces a byte string and P-003 turns
that byte string into a signature. Neither knows the other's internals.

**Claims served:** Q2D-C-05 (request binding) directly. Q2D-C-01 (pre-evaluation
commitment) depends on the answer contract, purpose, recipient, and sinks all
being inside the signed object rather than beside it.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §2.1 | Envelope: `signed` plus advisory `routing`; the strict-subset and disagreement rules |
| [`spec/core-model.md`](../../spec/core-model.md) §2.2–2.7 | Query field groups and which are required |
| [`spec/core-model.md`](../../spec/core-model.md) §3.1 | Capacity is integer millibits — `serialization.md` §1 prohibits the alternative |
| [`spec/core-model.md`](../../spec/core-model.md) §4 steps 1, 5, 8 | Bounded parse; parse only after verification; routing/signed consistency |
| [`spec/core-model.md`](../../spec/core-model.md) §5 | Response shapes for `answer`, `deny`, `escalate` |
| [`spec/core-model.md`](../../spec/core-model.md) §6 | Receipt fields and the digests they bind |
| [`spec/serialization.md`](../../spec/serialization.md) §1 | The production profile — every rule about the bytes |
| [`spec/serialization.md`](../../spec/serialization.md) §2 | What a parser rejects rather than repairs, and what a verifier must not depend on |
| [`spec/serialization.md`](../../spec/serialization.md) §3 | Protocol level is a property of what is being serialized — hence two entry points |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §3 | JWS compact is the container; the payload is what this PRD produces |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-05 | The field set the signature must cover |

## 3. Module boundary

**Inside:** envelope construction and parsing; core-object field layout;
deterministic production serialization; the routing projection and its
consistency check; digest construction and encoding; size limits; version field
handling.

**Explicitly outside:** signature algorithms, key resolution, suite selection and
downgrade policy (**P-003**). Replay caching, expiry evaluation, clock skew
(**P-004**). Registry resolution and schema validation of `public_context`
(**P-005**, **P-006**). Any policy decision.

## 4. Design

### 4.1 The determinism split

The single subtlety in this PRD, and the thing most likely to be got wrong.

Signing exact transmitted bytes removed canonicalization from the **security**
path: a verifier hashes the bytes it received and never re-derives them, so no
parser or serializer agreement is required to verify.

Determinism is still required on the **production** path, for a different reason.
The Stage 1 gate compares Rust's output to Go's byte for byte. Two producers
building the same logical query must emit the same bytes, or the gate fails on a
difference that is not a defect.

So:

> **Producers MUST emit the deterministic profile. Verifiers MUST NOT depend on
> it.**

That is [`serialization.md`](../../spec/serialization.md) §1 and §2, which is
where it belongs and where it did not used to be —
[E-43](../open-escalations.md).

A verifier that re-serializes to check a signature has reintroduced the
canonicalization dependency the envelope design exists to remove. That is a
`blocker`, not a style preference.

### 4.2 Deterministic production profile

[`serialization.md`](../../spec/serialization.md) §1 **is** the profile. This
section states nothing about the bytes.

It used to hold the table, and that was the defect [E-43](../open-escalations.md)
closed. Three artifacts above this PRD in the hierarchy — `crypto-suites.md`,
`core-model.md`, and `registry/manifest.json` — each referred to *"the
deterministic production profile"* as something defined above them, and it was
defined nowhere but here. The registry showed what that costs: its abbreviated
copy said *"object keys sorted ascending"* without saying by what, and Rust's
default `BTreeMap` order is one of the answers that produces wrong bytes. An
implementer working from `spec/` and the registry, as the hierarchy tells them
to, could not have got it right.

Two rules that used to live in this table are worth recording as history, because
each was a second source of truth that drifted before anyone noticed:

**The timestamp row once carried the rule itself** — "RFC 3339 with `Z`, second
precision" — and was the only place in the repository that said `Z`, while
`core-model.md` §2.2 said only "RFC 3339, second precision". The rule did not
reach `routing`, which the profile does not cover and which §4 step 8 compares.

It drifted a second way. §2.2 fixed a spelling without saying which strings it
bound, and the authoring tool resolved that by refusing *every* string that
looked like a timestamp and was spelled differently — a rule in no specification,
which issue 2 then copied into both implementations.
[E-36](../open-escalations.md) settled it: §2.2 reaches the fields it names, and
a predicate constrains its own through its registry entry.

**Key ordering** is lexicographic rather than by schema-declaration order, and
[`serialization.md`](../../spec/serialization.md) §1 now carries both the rule
and the reason. §4 there draws the boundary this PRD used to draw in a paragraph:
the rule is borrowed from JCS (RFC 8785) as an ordering convention only, and
nothing in Q2D verifies by re-deriving bytes.

### 4.3 No floating-point in signed structures

The rule is [`serialization.md`](../../spec/serialization.md) §1, and the parse
side is §2. What this section owns is **where each implementation enforces
them**, which is a build decision rather than a protocol one.

The **value model** enforces production, which is stronger than the serializer
enforcing it: neither implementation's value type has a float variant
([`src/value.rs`](../../src/value.rs), [`value.go`](../../value.go)), so a float
reaching the serializer is a compile error rather than a runtime one. There is
no failure path to test because there is no failure path.

That moves the check rather than removing it. Bytes arriving from outside can
contain a float, and `parse_core` is where one is refused — the boundary where a
value comes into existence, rather than downstream of a value that already
exists. Adding a float field is an escalation, not a schema change.

`serialize_core` is still fallible, for a different rule:
[`core-model.md`](../../spec/core-model.md) §2.2 permits one spelling of a
timestamp. That check has to live here, because serialization is the last point
at which a value can be refused before it becomes bytes somebody signs — and
inside a signed payload a malformed timestamp is past the reach of anything that
reads it as text.

That rule needs a **second entry point**, which §5 lists, and
[`serialization.md`](../../spec/serialization.md) §3 is why: protocol level is a
property of *what a value is*, not of where it sits. A predicate's
`public_context` is operation data reached through a query and operation data
digested on its own for §4.7's `public_context_digest` — being the top-level
value there makes it the root of some bytes, not a protocol structure. One entry
point would have to read the answer off the position, which does not carry it.

### 4.4 Envelope

```
{ "signed": "<JWS compact>", "routing": { … } }   // routing optional — §2.1
```

`signed` is opaque to the envelope layer. Its internal structure belongs to
P-003; this PRD treats it as a string and never inspects it.

`routing` may be absent ([E-38](../open-escalations.md)), so both the type and
the parse result carry that: an envelope with one member is a message, and a
responder must accept it.

**The envelope is closed**, and [`core-model.md`](../../spec/core-model.md) §2.1
says so — a member outside the two is `malformed` at step 1 rather than ignored
([E-44](../open-escalations.md)). Both implementations already denied and this
PRD already said they should; what was missing was a normative source, which is
[E-43](../open-escalations.md)'s class exactly. §2.1 gives the reason the
implementations could not: an ignored member is one a relay may act on and a
responder may not, and that disagreement is the vulnerability rather than the
field.

### 4.5 The routing projection is derived, never authored

A producer that sends `routing` **derives** it from the core object by
projection. It never constructs one independently, and it may send none at all —
§2.1, as [E-38](../open-escalations.md) settled it.

Hand-authoring routing makes producer-side disagreement possible — two fields
built from two code paths that can drift. Deriving makes the strict-subset
property structurally true and leaves the consistency check with exactly one job:
detecting tampering in transit.

Projected fields, and no others:

| Field | Why a relay needs it |
|---|---|
| `q2d_version` | Reject an unsupported version without unwrapping |
| `type` | Dispatch |
| `target.custodian` | Route |
| `predicate.id`, `predicate.version` | Capability matching |
| `expires_at` | Shed stale traffic |

`purpose`, `delivery`, `answer_contract`, `target.subjects`, and
`public_context` are **never** projected — and
[`core-model.md`](../../spec/core-model.md) §2.1 now says why in terms that hold
under 0.1 ([E-41](../open-escalations.md)). Not because withholding them is
confidentiality: the registered suite signs the payload without encrypting it,
so an intermediary reads them from `signed` regardless, which
[`claims.md`](../../spec/claims.md) **Q2D-NC-13** now states outright. Because a
projected field is legible *without decoding* and is therefore the one
infrastructure indexes and retains, and because the list is what makes the
projection correct once a payload-encryption suite exists.

### 4.6 Consistency check

After verification and parse (§4 step 8): for each field present in `routing`,
compare against the corresponding field of the verified core object. Any
mismatch, and any routing field absent from the core object, rejects.

The check never reads a value *from* routing for use. It only compares.

### 4.7 Digests

The construction is [`serialization.md`](../../spec/serialization.md) §5 —
`"sha256:" + lowercase_hex(SHA-256(bytes))`, prefix mandatory. It used to be
stated here and nowhere else, which is why [E-45](../open-escalations.md) moved
it: two implementations agreeing about every byte hashed would still fail every
receipt comparison by disagreeing about the case of the hex.

What this section owns is **which four digests exist and what each is over**.

| Digest | Over |
|---|---|
| `request_digest` | The exact `signed` bytes of the query |
| `response_digest` | The response's **semantic content**, excluding the receipt and the signature — `serialization.md` §1. [`core-model.md`](../../spec/core-model.md) §6 is authoritative |
| `effective_contract_digest` | The effective answer contract, `serialization.md` §1 |
| `public_context_digest` | The public context — `serialization.md` §1's bytes through the **operation-data** entry point, because §3 makes a public context operation data whether it is reached through a query or serialized on its own |

Only `request_digest` digests received bytes, with no re-serialization. The other
three digest a sub-object and therefore need the production profile, which is why
[`serialization.md`](../../spec/serialization.md) §1 applies beyond the payload.

**`response_digest` is the one to watch.** The obvious definition — the exact
`signed` bytes of the response, symmetric with `request_digest` — is not
implementable: the receipt travels inside the response and carries this digest,
so digesting the whole response would include the digest itself
([P-011](P-011-receipts-audit.md) §4.2). The symmetry is real and it is broken on
purpose.

### 4.8 Size limits

**The limits are [`core-model.md`](../../spec/core-model.md) §2.8's**, and this
section cites them rather than restating them. They were here, and
[E-39](../open-escalations.md) moved them, on E-16's reasoning: normative wire
constraints stated only in a PRD mean a third implementation built from `spec/`
alone accepts messages both of ours reject, neither wrong by the document it was
built from.

What stays here is where each one can be applied, which is an implementation
question and belongs at this level:

| Limit | Enforced |
|---|---|
| Envelope | §4 step 1, on the byte slice — the only one that runs before allocation |
| Nesting depth | during the parse |
| Object members per object | during the parse |
| Any single string field | wherever the fields are known: `parse_envelope` for `routing`, `parse_core` for the payload |
| `predicate.public_context` | `parse_core`, at step 5 |

The string row is the one to read carefully. §2.8's limit covers the fields the
specification defines and **stops at `public_context`**
([E-40](../open-escalations.md)), so applying it means knowing which subtree a
string is in. Both parsers track that: 2 KiB everywhere, 32 KiB inside
`predicate.public_context`, and the envelope limit for `signed`.

That is protocol knowledge in a parser, and it is the same knowledge
`serialize` already carries for §2.2's field names — the mechanism mirrors its
protocol level. The alternative was to bound every string at 32 KiB and owe the
2 KiB to a `parse_core` that does not exist, which would have accepted protocol
fields §2.8 refuses.

## 5. Interfaces

```
serialize_core(core: CoreObject)          -> bytes        // serialization.md §1; errors on a §2.2 timestamp
serialize_operation_data(value)           -> bytes        // §2.4 data; same bytes, no §2.2 field names
parse_core(payload: bytes)                -> CoreObject   // post-verification only
project_routing(core: CoreObject)         -> Routing      // derive; never authored
check_routing(core: CoreObject, r: Routing) -> Result     // compare only
build_envelope(signed: str, routing: Routing?) -> Envelope  // routing optional — §2.1
parse_envelope(bytes)                     -> Envelope     // bounded; §4.8
digest(bytes)                             -> DigestString
```

`parse_core` taking bytes that have already been verified is deliberate: the
signature is checked by P-003 before this function is reachable, so the type
system carries the ordering requirement rather than a comment.

### What a vector supplies to each of these

The corpus reaches these functions through the operations
[P-001](P-001-conformance-corpus.md) §4.5 defines, and two of them take more
than one kind of input. A runner cannot tell which from a value alone, so the
**field name says which**, and exactly one may be present:

| Operation | Field | Means |
|---|---|---|
| `verify_query` | `envelope` | A parsed envelope. Everything downstream of `parse_envelope`. |
| `verify_query` | `envelope_bytes_base64url` | **Received bytes.** `parse_envelope`, and every limit [`core-model.md`](../../spec/core-model.md) §2.8 places on an envelope. |
| `digest` | `bytes_base64url` | Digest these bytes as they are — `request_digest`. |
| `digest` | `value` | A protocol structure: serialize under [`serialization.md`](../../spec/serialization.md) §1, then digest. |
| `digest` | `operation_data` | §2.4 data: `serialization.md` §3's other entry point. |

**`envelope_bytes_base64url` exists because §2.8 bounds received bytes.** A
vector handing over a parsed object leaves the runner to reconstruct them, and
what it then measures depends on how it chose to spell what it was given rather
than on what the vector says. The two forms are not interchangeable and a vector
carrying both is malformed.

**Base64url rather than JSON text**, so one field means *received bytes* wherever
a vector supplies them, including bytes that are not valid UTF-8 — which text
could not carry. The cost is a group that cannot be read without decoding it, and
`message/envelope/above-the-envelope-limit` is 88 KB on disk because 64 KiB is
what it is testing. Both are accepted: the alternative is no shared vector for
the one limit that can be enforced before allocation.

`digest`'s three forms are P-002 §4.7's three kinds of input. `request_digest` is
over bytes that arrived; the other three digest a sub-object and therefore need a
serializer, and which serializer is `serialization.md` §3's question rather than
a value's.

## 6. Corpus sections

`message/` — authored under this PRD, against the P-001 format, **and partly
landed already**. [P-001](P-001-conformance-corpus.md) issue 12 authored
`message/sign/`, `message/verify/` and three of `message/routing/`, because the
harness needed a section with real signatures over real bytes before anything
here was built. Two consequences, both deliberate:

- `message/routing/` is shared. Its `subset`, `disagrees` and
  `introduces-field` vectors exist; this PRD adds derivation and the remaining
  disagreement cases to the same group rather than a parallel one.
- `sign/` and `verify/` have no owner in this table. P-001's own §6 row for
  `message/` names *"envelope construction, signing, verification, routing
  projection, routing/signed disagreement"* — five things — and the table below
  lists three of them under different group names. The two documents describe
  the same section differently, and §10 records the question rather than this
  PRD settling it by writing a row.

| Group | Vectors | State |
|---|---|---|
| `message/serialize/` | Key ordering above the BMP, escaping and what must not be escaped, `i64`'s boundaries, empty containers beside a present null | **four landed** — and see `testdata/` below |
| `message/envelope/` | Routing absent, unknown member, an over-long `routing` string, an envelope above 64 KiB | **four landed** — the group that tests `parse_envelope`, so every vector supplies received bytes (§5) |
| `message/routing/` | Strict subset, an `expires_at` disagreement, a `type` disagreement, a field outside the allowlist | **four landed** — three under P-001 issue 12, `type-disagrees` under issue 12 here |
| `message/digest/` | Received bytes, the empty input, a protocol structure, operation data | **four landed** — one per input shape §5 defines, and the empty input besides |
| `message/reject/` | Duplicate keys, a float, over-deep, too many members, an over-long protocol string, unknown version | **six landed** — **owed by issue 4 as well as issue 5**: both parsers refuse duplicate keys, a float, invalid UTF-8 and over-depth input, asserted by mirrored unit tests, which catch a divergence only where the same case was written twice |

This table used to promise a vector for **a routing field absent from the
signed object**, and there is no such vector because there is no such message.
Every field §4.5 projects is required by §2 — `q2d_version`, `type`,
`target.custodian`, `predicate.id`, `predicate.version`, `expires_at` — so a
signed object missing one is rejected at §4 step 5 for missing a field §2
requires, and step 8 is never reached. `project_routing` still handles it,
because derivation is total and a field that is not there is not projected; what
does not exist is a conforming pipeline that reaches the check with such a
message. `introduces-field` covers the reachable half of the same rule, a field
outside the allowlist entirely.

Ahead of `message/serialize/`, [`testdata/`](../../testdata/README.md) already
holds all three serializers to the same bytes, from Python, Rust and Go, by tests
that share no code. Two fixtures, and the second one is the point:

- `canonical-query` is §7's first acceptance criterion — a real query, the
  smallest a conforming requester produces.
- `profile-edges` is **not a Q2D message**. It carries key ordering above the
  BMP, every escape RFC 8259 names, `i64`'s boundaries, and the characters
  `encoding/json` escapes by default and this profile must not.

The second exists because the first could not catch a real divergence: the Rust
serializer was emitting Unicode scalar key order where the profile asks for UTF-16
code-unit order, and the canonical query is entirely ASCII, so it agreed anyway.
The generalisation is worth stating, because `message/serialize/` will inherit
it — **a corpus of realistic documents tests the protocol, not the profile.** No
*protocol field* reaches those edges: every field name in `core-model.md` §2 is
ASCII, and every value §2 defines is a bounded string, a count, or an enum.

A conforming query can still reach them, through `predicate.public_context`,
which §2.4 leaves to the registered predicate — a non-ASCII key, a string needing every
escape, or an integer at the boundary all travel into the signed payload. So
`message/serialize/` has to author them on purpose: they are reachable by a real
message and by no realistic-looking one.

## 7. Acceptance

- [ ] Both implementations serialize the same logical query to **byte-identical**
      output, for every `message/serialize/` vector.
- [ ] Both derive byte-identical `routing` from the same core object.
- [ ] Both produce identical digests for every `message/digest/` vector.
- [ ] A verifier accepts bytes that verify but do not match the production
      profile — proving verification does not depend on serialization.
      `message/verify/non-conformant-payload` is that vector.
- [ ] Round trip: `parse_core(serialize_core(x)) == x` for every vector.
- [ ] `harness cross` reports agreement for every `message/` vector. Note that
      agreement is exit **3**, not 0, until [P-001](P-001-conformance-corpus.md)
      issue 19 lands — §4.8 asks for two things and this mode does one of them.
      Read the report, not the status.

The fourth item is the one that proves §4.1. A suite where every payload happens
to be profile-conformant cannot distinguish a correct verifier from one that
re-serializes.

**Every box is unticked and every one of them now has its vector.** Each says
*both implementations*, and what puts a vector to an implementation is a runner
that answers it. Both runners exist and both answer `error` to everything —
[`conformance/RUNNER-CONTRACT.md`](../../conformance/RUNNER-CONTRACT.md) is
explicit that adding behaviour to them is a deliberate act rather than a
consequence.

**Not [P-001](P-001-conformance-corpus.md) issue 19.** That is cross-verification
— A's artefact put to B — and P-001 says in terms that P-002 §7 does not need it:
byte agreement over `message/` is what `harness cross` already does, and issue 9
delivered that. The dependency here is narrower and different.

**Of the three operations this section uses, this PRD owns one.** `digest` is
answerable from what is built. `sign_query` and `verify_query` are not: signing
and verifying are [P-003](P-003-crypto-suites.md)'s, so twenty-two of the
section's twenty-six vectors cannot be answered by anything P-002 delivers —
seventeen `verify_query` and five `sign_query`. That is why no
issue here owns wiring the runner — it is Stage 1 work spanning both PRDs, and
[`mvp-scope.md`](../mvp-scope.md) Stage 1 is where the two meet.

Ticking these off the mirrored unit tests instead would say the corpus had been
run when it has not, which is the overstatement this repository is most careful
about.

The nearest thing to evidence today is [`testdata/`](../../testdata/README.md):
three serializers, no shared code, held to the same bytes, plus the digests over
them from three provenances. That covers the first and third items for two
fixtures rather than for every vector, which is why it is written here as a note
and not as a tick.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| A verifier that re-serializes to check a signature | The non-conformant-but-valid payload vector is rejected |
| `routing` disagreeing on any projected field | Rejected at step 8, internal reason `routing_mismatch` |
| `routing` carrying a field absent from the signed object | Same |
| A float in a signed structure | `parse_core` rejects the payload carrying it. Not `serialize_core`: §4.3 puts `serialization.md` §1's prohibition in the value model, so a float cannot be constructed to serialize — the case is unreachable from inside and is only observable on bytes from outside |
| Duplicate JSON keys in a payload | `parse_core` rejects |
| Envelope above 64 KiB | Rejected at step 1, on the byte slice, before allocation |
| Nesting beyond 16, or more than 64 members in an object | Rejected during the parse — §4.8. Not *before* allocation, and the distinction is real: the envelope bound is what makes the parse's work finite, and these bound its shape |
| Unknown `q2d_version` | Rejected; no attempt to interpret unknown fields |
| Hand-authored routing that happens to match | Not observable at runtime — caught by review; the interface offers no way to supply one |

The last row is honest about a limit: §4.5 is enforced by the interface shape and
by review, not by a test. An implementation could route around it, and that is
what `AGENTS.md`'s architectural-pivot rule exists for.

## 9. Escalate-if-changed decisions

Items 1, 2 and 5 are now [`serialization.md`](../../spec/serialization.md)'s
rather than this PRD's ([E-43](../open-escalations.md)), which makes changing
them a `spec/` change and therefore an escalation by the general rule rather than
by this list. They stay listed because a reader of this PRD is who needs to know.

1. **Producers emit the deterministic profile; verifiers must not depend on it.**
   A verifier that re-serializes reintroduces the dependency the envelope design
   removes. `serialization.md` §1 and §2.
2. **No floating-point in any signed structure.** Adding one reintroduces
   cross-language divergence the protocol currently has none of.
   `serialization.md` §1.
3. **`routing` is derived by projection, never authored.**
4. **The routing field allowlist is closed.** Adding a field puts it in the clear
   for every relay on the path — a disclosure decision, not a plumbing one.
5. **Lexicographic key ordering, by UTF-16 code unit.** Changing it invalidates
   every byte-comparison vector. `serialization.md` §1.
6. **Digest is `sha256:` + lowercase hex.** Changing the encoding changes every
   receipt. [`serialization.md`](../../spec/serialization.md) §5, as of
   [E-45](../open-escalations.md) — so changing it is a `spec/` change and an
   escalation by the general rule, as items 1, 2 and 5 are.

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Does `routing` need `type`, or is dispatch determined by endpoint?~~ | **Resolved: keep it.** Dispatch-by-endpoint is an HTTPS assumption, and `routing` exists for transports that have no endpoint to dispatch on — an A2A intermediary is the case. Dropping it would make the projection useful only where it is least needed. It stays advisory: §4.5's consistency check rejects any disagreement with `signed`, so carrying `type` adds a field an attacker can lie about only by being caught |
| ~~Does the envelope carry its own version distinct from `q2d_version`?~~ | **Resolved: no.** One version, inside the signed object. A separate envelope version would be unsigned and therefore rewritable by any intermediary, and two version numbers for one message is a negotiation surface Q2D does not have (`core-model.md` §1: no negotiation round trip) |
| ~~Are the §4.8 limits right?~~ | **Resolved for MVP: adopted as stated, and they are normative rather than advisory** — a limit an implementation may choose is not a limit, and the two implementations must reject the same payload. They are engineering estimates, not measurements, and §4.8 says so; Stage 8 measures real payloads and may lower them. Raising one is an escalation, because a limit that grows to fit a payload is not bounding anything |
| ~~Second-precision timestamps sufficient, or is sub-second needed for replay windows?~~ | **Answered: sufficient.** Uniqueness comes from `query_id`, not the clock — the nonce's own work is an unpredictable digest, corrected by [E-50](../open-escalations.md) and stated in [`freshness.md`](../../spec/freshness.md) §3.1. [P-004](P-004-replay-idempotency.md) §4.3 |
| ~~Does `semantic` comparison from P-001 apply to `routing`, given it is unsigned?~~ | **Answered: yes**, and only because it is outside the signature. Anything inside `signed` compares as `bytes`. [P-001](P-001-conformance-corpus.md) §4.4 |
| ~~Does §2.1's justification for the projection allowlist hold under 0.1?~~ | **Resolved: it did not, and §2.1 no longer makes it.** [E-41](../open-escalations.md), closed as A **with B**. The 0.1 suite signs the payload without encrypting it — I decoded the corpus's own `routing/subset` vector with no key and read its `purpose` — so withholding a field from `routing` withholds nothing. §2.1 now says that outright and keeps the rule on the two grounds that hold: a projected field is legible *without decoding* and is therefore the one infrastructure indexes at scale, and the list is what makes the projection correct once a payload-encryption suite exists. [`claims.md`](../../spec/claims.md) gains **Q2D-NC-13**, recording that Q2D **does not claim** query confidentiality from an intermediary — which is where the correction belongs whichever way §2.1 is worded. Q2D-C-05 is untouched: it claims integrity |
| ~~May an envelope omit `routing`?~~ | **Resolved: yes**, and [`core-model.md`](../../spec/core-model.md) §2.1 says so — *"`routing` may be absent, and a responder must accept a message carrying only `signed`"*. [E-38](../open-escalations.md), closed as B. §2.1's opening sentence changed with it: *"a message has two parts"* implied something about presence it never meant, and now reads *"an authoritative part and an optional advisory one"*. Absence removes no guarantee — a projection that is *present* is the thing that can disagree — and requiring it would publish `predicate.id` and `target.custodian` in the clear in the one case, a direct exchange, where least disclosure could be best. **I implemented the opposite first**, arguing the corpus was evidence of intent; CLAUDE.md's hierarchy answers that directly, and the register keeps the reasoning because the mistake is the reusable part. `suite/` is routing-less again and `message/` carries the projection, so the corpus exercises both shapes |
| ~~Should §4.8's limits live in `spec/` rather than here?~~ | **Resolved: yes** — [`core-model.md`](../../spec/core-model.md) §2.8 now carries them and §4.8 cites it. [E-39](../open-escalations.md), closed as A. The argument was E-16's, unchanged: `spec/` said only *reject oversized*, so a third implementation enforced nothing. §2.8 also records what §4.8 had learned — that only the envelope limit can run before allocation, and why `signed` is exempt from the string limit. |
| ~~Does the 2 KiB string limit reach inside `public_context`?~~ | **Resolved: no** — [E-40](../open-escalations.md), closed as B, consistent with E-36. §2.8's string limit covers the fields the specification defines; a predicate's own field is bounded by its registry entry, where [`scope.md`](../../spec/scope.md) §4.1 now requires a `maxLength` on every schema describing what a requester may send, and by the 32 KiB the whole object may not exceed. §4.1's *"this document does not decide it"* is gone: §2.8 decided the message-level part, which would have left the per-field part with no owner at all. `private_input_schema` is excluded — a requester cannot send it. |
| ~~Does an integer in a signed structure have a range?~~ | **Resolved: [`scope.md`](../../spec/scope.md) §4.1** — an `integer` in any of an entry's schemas states `minimum` and `maximum`, both within −2^63 … 2^63 − 1. [E-37](../open-escalations.md), closed as B. `core-model.md` still states none, deliberately: every integer the protocol itself defines is a count, a cardinality, or a capacity in integer millibits, and the bound is a fact about registry data rather than about the protocol. So `i64` in both value models is the width §4.1 names rather than a choice the implementations made and the specification then followed. `registry/validate.py` enforces it across all three of an entry's schemas — wider than the release rule, which asks only about `output_schema`, because this is a representability question rather than a disclosure one |
| ~~Does §2.2's timestamp spelling bind every string, or only the fields §2.2 names?~~ | **Resolved: only the fields §2.2 names**, and §2.2 now says so — *"the rule reaches the fields this specification names, and no further"*. [E-36](../open-escalations.md), closed as C. A predicate wanting one spelling for a field of its own declares `format: date-time` in its registry entry, where [`scope.md`](../../spec/scope.md) §4.1 makes that an assertion rather than the annotation JSON Schema leaves it as. The three serializers already had this behaviour; what changed is that it is now what the specification says, rather than the narrowest thing they could do while the question was open. `conformance/harness/lint.py` keeps the wider rule deliberately — it lints authored vectors, which are ours |
| ~~Is the envelope object closed?~~ | **Resolved: yes** — [E-44](../open-escalations.md). [`core-model.md`](../../spec/core-model.md) §2.1 carries `signed` and `routing` *"and no others"*, and a member outside the set is `malformed` at step 1. Both implementations already denied; what was missing was the normative source, and §2.1 now gives the reason they could not: an ignored member is one a relay may act on and a responder may not |
| ~~Where is the digest string form defined?~~ | **Resolved: [`serialization.md`](../../spec/serialization.md) §5** — [E-45](../open-escalations.md). §4.7 keeps which four digests exist and what each is over; the form was stated only here, and two implementations agreeing about every byte hashed would still have failed every comparison over the case of the hex |
| **Who owns `message/sign/` and `message/verify/`?** | Open, and surfaced by building §6's serializer. [P-001](P-001-conformance-corpus.md) issue 12 authored both, under P-001's §6 row naming signing and verification as part of `message/`; this PRD's §6 table names neither. Meanwhile [P-003](P-003-crypto-suites.md) §6 gives `suite/sign/` as *"JWS compact construction, byte-exact, over P-002 payloads"* — which is what `message/sign/query-minimal` already is. My view: leave the two vectors where they are and let P-003 own the mechanism, because `message/sign/` proves a P-002 payload is signable end to end and `suite/sign/` proves the suite, and those are different failures even when the bytes coincide. But that is a corpus-organisation call across three PRDs, so it belongs to whoever builds P-003, not to this one |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Core object type definitions, both languages | **Done.** [`src/value.rs`](../../src/value.rs) and [`value.go`](../../value.go). An absent optional and a null one are different documents, not merely distinguishable values — a field is in the map or it is not |
| 2 | `serialize_core` with the `serialization.md` §1 profile | **Done.** It was recorded here as *done against a narrower gate*, because `message/serialize/` did not exist and the byte match was asserted against [`testdata/`](../../testdata/README.md)'s two fixtures instead — read by all three serializers, including the authoring tool the corpus's own expected bytes come from. Refusals agree too, case for case: §2.2's timestamp spelling, and the protocol-level rule that a field name means what `core-model.md` says only outside `public_context`. Building it found five Rust/Go divergences, raised E-31 through E-35, and took two Codex rounds — UTF-16 key ordering, then this. Issue 10 has since landed the section, so the wider gate is in place: four `message/serialize/` vectors carrying the profile's edges. What no longer waits on this PRD waits on a runner that answers `sign_query`, which is [P-003](P-003-crypto-suites.md)'s |
| 3 | Float guard in the serializer | **Done, in the place the guard belongs.** Neither value model has a float variant, so `serialization.md` §1's prohibition is a compile error and there is no runtime path to test — and issue 4's parser refuses one on the way in, which is where external bytes arrive. Refused **syntactically**: a fraction or an exponent, rather than a value that happens to be integral. `1e2` is a hundred and no conforming producer emits it, and deciding that it *is* a hundred means exponent arithmetic — with `1e400`, arithmetic in what — which is the divergence `serialization.md` §1 removes rather than manages. A `message/reject/` vector covers it under issue 10 |
| 4 | `parse_core`, rejecting duplicate keys | **Done**, and the narrower gate issue 2 describes was the position this row was in too. [`src/parse.rs`](../../src/parse.rs) and [`parse.go`](../../parse.go), hand-written from RFC 8259 in both. Not `encoding/json` on the Go side, and the reason is sharper than the serializer's: it resolves duplicate keys by last-wins, which is the rule `serialization.md` §2 requires *rejecting*; it decodes every number into `float64`, losing an `int64` above 2^53 silently; and it substitutes U+FFFD for invalid UTF-8. Three of the four refusals are behaviours the standard library deliberately does not have. Round-tripped against both [`testdata/`](../../testdata/README.md) fixtures rather than a value invented for the test — parsing is a **two-way** agreement, and §7 asks for both implementations rather than the serializer's three. Carries §4.8's depth bound alone, because recursive descent without one is a stack overflow and *verified* is not *trusted*; issue 5 applies the full set at the envelope. **`message/reject/` was owed and issue 10 has landed it** — six vectors, and duplicate keys and a float go in as signed payload *bytes*, since neither is expressible as an object. Before that, these refusals were asserted by two suites written to mirror each other, which catches a divergence only where someone thought to write the same case twice; a vector is one document both runners are handed. Both runners answer `error` to every operation by design, and `verify_query` is [P-003](P-003-crypto-suites.md)'s, so the section still cannot be *run* against these parsers before Stage 1 |
| 5 | Bounded `parse_envelope` | **Done**, and as with issues 2 and 4 the gate has since widened. Every boundary here is a *rejection* boundary — oversize, unknown member, routing string and key length, depth, member count — and each is asserted by two suites written to mirror each other, which catches a divergence only where the same case was written twice. `message/envelope/` and `message/reject/` are issue 10's, and both reach the parser through `verify_query`, which is [P-003](P-003-crypto-suites.md)'s to make answerable. [`src/envelope.rs`](../../src/envelope.rs) and [`envelope.go`](../../envelope.go). The envelope bound is checked on the byte slice before a parser exists, which is the only one of §4.8's five that *can* run before allocation; depth, members and string length are enforced during the parse, and are bounded by it. Building it corrected §4.8 twice: `public_context`'s limit cannot be enforced at step 1, because it is inside the payload that step 5 parses, and the 2 KiB string limit cannot reach `signed`, because a JWS compact of the canonical query is ~1.6 KiB before any public context and the protocol could not otherwise carry its own worked example. An unknown envelope member **denies** rather than being ignored, and [`core-model.md`](../../spec/core-model.md) §2.1 now says so rather than this PRD ([E-44](../open-escalations.md)). `message/envelope/` has since landed under issue 10, carrying received bytes rather than a parsed envelope, which is the only shape in which a limit on received bytes can be asserted |
| 6 | `project_routing` | **Done.** [`src/routing.rs`](../../src/routing.rs) and [`routing.go`](../../routing.go). `Routing` wraps a private value whose only origin is the projection, so §4.5's *never authored* is a property of the type rather than a rule a caller keeps — the honest limit being §8's last row: code *inside* the crate or package can still construct one, and what the type removes is the accident rather than the determined bypass. Go's reader returns a **deep copy**, because `Object` is a map and handing back the stored value would let a caller write `r.Value().(q2d.Object)["purpose"] = …` — authoring a routing field through the API that exists to stop it. Rust's `as_value` gets that from an immutable borrow; Go has to copy, and a test mutates a nested member to prove a shallow one would not do. Go also admits `q2d.Routing{}` where Rust's private tuple field does not — harmless, because the zero value carries no fields and reads as the projection of nothing, which §2.1 permits: a caller can construct an empty projection and cannot construct one with fields it chose. Derivation is total: a core object missing a projected field does not project it, which is what §2.1's *strict subset* and §4.6's *each field present* already describe, so there is no error path to handle wrongly and no temptation to default a field that was not there. **Checked against something authored independently** — projecting the canonical query reproduces `author_message.py`'s hand-written `ROUTING` byte for byte, and every `message/` vector's envelope carries that literal, so a disagreement would mean either §4.5 or five merged vectors are wrong |
| 7 | `check_routing` | **Done.** In [`src/routing.rs`](../../src/routing.rs) and [`routing.go`](../../routing.go), beside the projection they check. Objects recurse — a projection carrying `target.custodian` is a subset of a `target` that also has `subjects` — and everything else compares whole, because §4.4 makes array order significant and a subset rule for arrays would let a relay drop an element and call it a projection. Nothing is coerced: an integer never equals the string that spells it, which is what §4 step 8's *same type, same value* asks for. The mismatch carries the **path and neither value** — the projection is attacker-supplied and the core object is the requester's — and it is the *internal* reason, kept a separate type from the wire response P-009 builds even though §5.2.1 spells the external value the same. **A field outside §4.5's allowlist is refused however faithful the copy** — §2.1 says `routing` *carries at most* those six, so `purpose` matching the signed value byte for byte is still rejected, because the harm is the projection rather than the mismatch. `message/routing/introduces-field` pins exactly that and the first version of this check would have passed it; the two internal reasons take the corpus's own names, `routing_signed_mismatch` and `routing_introduced_field`, rather than a third vocabulary for the same two facts. **The comparison is against `project_routing(core)`, not against the core object.** Comparing against the core object means enumerating what `routing` may *not* contain, and review found three of those one at a time — a field outside the allowlist, a literal `"predicate.id"` key read as a nested path, a value that differs. §4.5 already says what a projection holds, and says it by construction, so *is this a subset of that* answers all three at once. The two reasons then mean what their names say: introduced is **not in the derivation**, mismatch is **in it and different**. One case is deliberately accepted and **[E-42](../open-escalations.md) closed as A**: `{"target":{}}` is not something the projection emits and is refused by nothing §2.1 states, which is where *not derivable* and *not permitted* come apart. §2.1 now says it rather than leaving it to be inferred — *"may carry fewer, or none of them, at any depth"* — because the next implementation will meet the same question, and an unstated answer inside a security check is where two implementations quietly differ. An absent projection passes: nothing that is not there can disagree ([E-38](../open-escalations.md)). A test asserts the two halves agree — a derived projection always passes the check, which is what stops every conforming exchange failing at step 8 |
| 8 | Digest construction | **The construction is done**; the four call sites are not, and cannot be here. [`src/digest.rs`](../../src/digest.rs) and [`digest.go`](../../digest.go) implement `"sha256:" + lowercase_hex(SHA-256(bytes))`, held to [`testdata/digests.txt`](../../testdata/README.md) across three provenances: Rust writes SHA-256 out by hand — its standard library has none and the crate takes no dependencies — gated on FIPS 180-4's published known answers; Go uses `crypto/sha256`; `hashlib` wrote the fixture. A defect in the hand-written one therefore shows up as a disagreement with two standard libraries rather than as its own private truth. **What each of the four digests covers is P-011's and P-012's**, and `response_digest` is the one to watch: the receipt travels inside the response and carries the digest, so digesting the whole response would include it — P-011 §4.2 is authoritative. `message/digest/` is issue 10's |
| 9 | Version field handling | **Done.** [`src/version.rs`](../../src/version.rs) and [`version.go`](../../version.go). One value, not a range — a range implies a negotiation and [`core-model.md`](../../spec/core-model.md) §1 has none. The function **reads exactly one key**, which makes *without interpreting other fields* structural rather than a discipline a caller keeps, and a test hands it a message whose every other field is wrong to prove nothing else is consulted. **Not the stronger claim that nothing is read first**: step 5 is *parse the verified core object*, so parsing precedes this and may reject on its own — those are §5.2.1's `malformed`, the other cause that row gives for step 5, so a message that never reaches the check is still refused under the right external value. It takes the verified core object and has **no parameter for `routing`**: §5.2.1 puts `unsupported_version` at step 5 precisely because the authoritative value is inside the signed object, and §4 step 2's shedding on a projected copy is load shedding rather than a rejection reason. **Absent and non-string are `malformed`, not `unsupported_version`** — §5.2.1 gives those two rows separately, and §2.2 requires the field, so *missing a field §2 requires* is the row that applies. The internal value keeps the distinction because the external ones differ, which is the mirror image of `routing`'s two internal reasons collapsing into one external: there normalization is the point, here it would send a requester looking for a version it does not have. `message/reject/`'s unknown-version vector is issue 10's |
| 10 | Author `message/` corpus section | **Done.** All five groups present — twenty-six vectors, `harness lint` clean, `--check` in the suite. What remains is not authoring: both runners answer `error` by design, and twenty-two of the twenty-six vectors reach an operation [P-003](P-003-crypto-suites.md) owns, so the section is a contract nothing has been run against yet. Original criterion: all five groups present; `harness lint` clean. **To be authored through the operations that already exist.** Worth stating because the first reading of the `operation` enum is that four of these five groups need names it does not have; they do not. The corpus tests protocol behaviour through protocol operations, so `serialization.md` §1's serializer is exercised by a `sign_query` vector asserting the compact string byte for byte — `message/sign/query-minimal` is the one that exists and does exactly this — and the parser and §2.8's limits are exercised by `verify_query` vectors whose payloads or envelopes are malformed one way each. `digest` is in the enum on its own account, and `message/digest/`'s four vectors are the only use of it in the corpus.

**`serialize/` is written** — four vectors, generated by [`tools/author_message.py`](../../tools/author_message.py) with a `--check` in the suite: key order above the BMP, minimal escaping and what must *not* be escaped, `i64`'s boundaries, and empty containers beside a present null. Each signs a query whose `public_context` carries the shape and asserts the compact string byte for byte, so a wrong key order or a stray escape changes the payload segment and fails the comparison. They are deliberately not schema-valid for any registered entry — `sign_query` resolves no predicate, and `serialization.md` §1's edges are unreachable through a public context an entry would declare, which is the same reason `testdata/profile-edges` exists.

**`reject/` is written** — six vectors. Duplicate keys and a float go in as **payload bytes**, since neither is expressible as an object and both are exactly what a JSON library does silently: `encoding/json` resolves a duplicate key by last-wins, which is the rule `serialization.md` §2 requires *rejecting*, and every library reads a float into a double. `jws_over_payload_bytes` signs them, so each is a validly signed message wrong in one stated way rather than corrupt bytes that would fail at step 4 for a reason the vector is not about. Over-depth, member count and an over-long protocol string go in as objects. Five are `malformed` on the wire with five different internal reasons; the sixth is the only `unsupported_version` in the corpus.

**`envelope/` is written** — four vectors, and the group carries **received
bytes** rather than a parsed envelope. That was recorded here as awkward and it
was the wrong shape rather than a hard case: §2.8 bounds the bytes as
transmitted, so a vector handing over an object leaves the runner to reconstruct
them and measures its choice of spelling instead. §5 now defines
`envelope_bytes_base64url` beside `envelope`, and the two are not
interchangeable. `above-the-envelope-limit` is 88 KB on disk, which is what 64
KiB base64urls to; the alternative was no shared vector for the one limit that
can be enforced before allocation. `routing-absent` is the positive case the
other three are measured against — an implementation that required `routing`
would reject every message from a producer that sends none ([E-38](../open-escalations.md)),
and nothing else in the section catches it.

**`digest/` is written** — four vectors, and the decision it waited on is in §5:
the input's **field name** says which of three things it carries, because §4.7
takes four digests over three different kinds of thing and a runner cannot tell
them apart from a value alone. `bytes_base64url` digests bytes as they are
(`request_digest`); `value` serializes a protocol structure first; and
`operation_data` is `serialization.md` §3's other entry point, which is what
`public_context_digest` needs. The fourth vector is the one that makes those two
entry points different rather than redundant: a public context whose `issued_at`
is not a timestamp, which an implementation with a single entry point either
refuses here or wrongly accepts through a query.

P-001 issue 17's remit is the **Stage 5–8** extension; P-002 is Stage 1, and nothing here waits on it.

**What the implementations owe this section**, gathered here rather than repeated in each issue row: duplicate keys, a float, invalid UTF-8, over-depth and over-wide input (issue 4); an oversize envelope, an unknown envelope member, and a `routing` string or key above 2 KiB (issue 5); and §2.8's three string bounds by position — a protocol field at 2 KiB, `predicate.public_context` at 32 KiB both per string and as an object, and `signed` at the envelope limit ([E-40](../open-escalations.md)). Each is asserted today by two suites written to mirror each other, which catches a divergence only where the same case was written twice. None can be *run* against the implementations until a runner answers `verify_query`, which is [P-003](P-003-crypto-suites.md)'s.<br><br>**And they owe the internal reasons by name.** A runner reports `internal_reason` and the harness compares it, so the names this section uses are the contract: `envelope_too_large`, `envelope_unknown_member`, `envelope_string_too_long`, `core_object_duplicate_key`, `core_object_float`, `core_object_too_deep`, `core_object_too_many_members`, `core_object_string_too_long`, `core_object_unsupported_version`. Only the two routing reasons are typed values today (`routing.rs`, `routing.go`); every parse-level rejection returns a formatted string, which no runner can report as a reason. Nothing is *wrong* — the strings say the right thing to an operator, and there is no runner yet to be wrong at — but a typed reason per case is what an answering runner will need, and inventing the names then rather than reading them from here is how two implementations end up with two vocabularies for one set of facts |
| 11 | Non-conformant-but-valid payload vector | **Done.** `message/verify/non-conformant-payload` — a payload spaced where `serialization.md` §1 emits nothing, validly signed over those bytes, expecting `ok`. The **only** vector in the corpus whose input is deliberately non-conformant and whose outcome is not a rejection, which is what makes it worth having: a suite where every payload happens to be profile-conformant cannot distinguish a correct verifier from one that re-serializes, and every other vector here is such a payload. Both **parsers** already accept a payload spelled this way — `parse_core` was written to RFC 8259 rather than to the profile, and each suite has a test saying so. That is narrower than the vector: nothing implements `verify_query` yet — it is [P-003](P-003-crypto-suites.md)'s — so no runner has been handed this envelope. The case is one a *third* implementation gets wrong, and the corpus is where a third implementation meets it |
| 12 | `routing` carries `type`; the size limits enforced as normative | **Done.** `message/routing/type-disagrees` rewrites `type` to `response` over a signed query. Worth its own vector beside `routing/disagrees`, which moves `expires_at` by a second: a responder trusting that one sheds a live message, and a responder trusting this one hands a query to the code that reads responses. The limits are normative and now live in [`core-model.md`](../../spec/core-model.md) §2.8 rather than in this PRD ([E-39](../open-escalations.md)); `message/envelope/` and `message/reject/` assert four of the five, each rejecting with its own internal reason and the same wire response |

Issue 1 blocks the rest.
