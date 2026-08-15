# P-002 — Message envelope and canonical structures

| Field | Detail |
|---|---|
| PRD | P-002 |
| Stage | 1 |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md) — corpus format |
| Blocks | P-003, P-004, P-005, P-006, P-010, P-011, P-012, P-016 |
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
| [`spec/core-model.md`](../../spec/core-model.md) §3.1 | Capacity is integer millibits — see §4.3 below |
| [`spec/core-model.md`](../../spec/core-model.md) §4 steps 1, 5, 8 | Bounded parse; parse only after verification; routing/signed consistency |
| [`spec/core-model.md`](../../spec/core-model.md) §5 | Response shapes for `answer`, `deny`, `escalate` |
| [`spec/core-model.md`](../../spec/core-model.md) §6 | Receipt fields and the digests they bind |
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

> **Producers MUST emit the deterministic profile in §4.2. Verifiers MUST NOT
> depend on it.**

A verifier that re-serializes to check a signature has reintroduced the
canonicalization dependency the envelope design exists to remove. That is a
`blocker`, not a style preference.

### 4.2 Deterministic production profile

Applies to the JWS payload and to every sub-object that is digested.

| Rule | Value |
|---|---|
| Encoding | UTF-8, no BOM |
| Whitespace | none between tokens |
| Object keys | sorted ascending by UTF-16 code unit |
| Absent optional fields | omitted, never `null` |
| Integers | no exponent, no leading `+`, no leading zeros |
| **Floats** | **prohibited — see §4.3** |
| Timestamps | [`core-model.md`](../../spec/core-model.md) §2.2 |
| Strings | minimal escaping; no `\uXXXX` for characters representable directly |
| Duplicate keys | prohibited on production, rejected on parse |

The timestamp row **cites rather than states**. This table used to carry the
rule itself — "RFC 3339 with `Z`, second precision" — and was the only place in
the repository that said `Z`, while `core-model.md` said only "RFC 3339, second
precision". A PRD holding a rule `spec/` needs is the second source of truth
CLAUDE.md's hierarchy exists to prevent, and it showed: the rule did not reach
`routing`, which this profile does not cover and which §4 step 8 compares.

It showed a second way, which is why the row now cites a §2.2 that says more
than it used to. §2.2 fixed a spelling without saying which strings it bound,
and the authoring tool resolved that by refusing *every* string that looked like
a timestamp and was spelled differently — a rule in no specification, which
issue 2 then copied into both implementations. [E-36](../open-escalations.md)
settled it: §2.2 reaches the fields it names, and a predicate constrains its own
through its registry entry.

Key ordering is lexicographic rather than schema-declaration order because
declaration order is brittle as fields are added and produces no compile-time
error when two implementations disagree. The rule is borrowed from JCS (RFC 8785)
**as an ordering convention only** — it is not a canonicalization step, and
nothing verifies by re-deriving.

### 4.3 No floating-point in signed structures

There is no float-valued field in any signed Q2D structure, and none may be
added.

Capacity is integer millibits ([`core-model.md`](../../spec/core-model.md) §3.1).
Timestamps are strings. Cardinalities and sizes are integers. This removes JSON
float-precision divergence from the protocol entirely rather than managing it.

The **value model** enforces this, which is stronger than the serializer
enforcing it: neither implementation's value type has a float variant
([`src/value.rs`](../../src/value.rs), [`value.go`](../../value.go)), so a float
reaching the serializer is a compile error rather than a runtime one. There is
no failure path to test because there is no failure path.

That moves the check rather than removing it. Bytes arriving from outside can
contain a float, and `parse_core` is where one is refused — the boundary where a
value comes into existence, rather than downstream of a value that already
exists. Adding a float field is an escalation, not a schema change.

`serialize_core` is still fallible, for a different rule: `core-model.md` §2.2
permits one spelling of a timestamp, and §4.2 cites it. That check has to live
here, because serialization is the last point at which a value can be refused
before it becomes bytes somebody signs — and inside a signed payload a malformed
timestamp is past the reach of anything that reads it as text.

That rule needs a **second entry point**, which §5 now lists. §2.2 gives a field
name a meaning at protocol level — the core object, `routing`, and a receipt —
and §2.4 makes a predicate's `public_context` its entry's to shape. Whether a
value is at protocol level is therefore a property of *what the caller is
serializing*, not of how deep it sits: reached through a query, `public_context`
is already below protocol level; digested on its own for §4.7's
`public_context_digest` it is the root. One entry point would hold the same
bytes to two different rules depending on which path reached them.

### 4.4 Envelope

```
{ "signed": "<JWS compact>", "routing": { … } }   // routing optional — §2.1
```

`signed` is opaque to the envelope layer. Its internal structure belongs to
P-003; this PRD treats it as a string and never inspects it.

`routing` may be absent ([E-38](../open-escalations.md)), so both the type and
the parse result carry that: an envelope with one member is a message, and a
responder must accept it.

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

```
digest = "sha256:" + lowercase_hex(SHA-256(bytes))
```

The algorithm prefix is mandatory so the digest is self-describing and a future
algorithm is additive rather than ambiguous.

| Digest | Over |
|---|---|
| `request_digest` | The exact `signed` bytes of the query |
| `response_digest` | The response's **semantic content**, excluding the receipt and the signature — §4.2 profile. [`core-model.md`](../../spec/core-model.md) §6 is authoritative |
| `effective_contract_digest` | The effective answer contract, §4.2 profile |
| `public_context_digest` | The public context, §4.2 profile |

Only `request_digest` digests received bytes, with no re-serialization. The other
three digest a sub-object and therefore need the production profile, which is why
§4.2 applies beyond the payload.

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
serialize_core(core: CoreObject)          -> bytes        // §4.2 profile; errors on a §2.2 timestamp
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
| `message/serialize/` | Key ordering, omitted optionals, integer forms, timestamp format, escaping | new — but see `testdata/` below |
| `message/envelope/` | Construction, parse, size limits, depth limit | new |
| `message/routing/` | Derivation, strict subset, each disagreement case, a routing field absent from signed | **three landed** under P-001 issue 12 |
| `message/digest/` | Each of the four digests against known bytes | new |
| `message/reject/` | Oversized, over-deep, duplicate keys, float present, unknown version | new — **and now owed by issue 4 as well as issue 5**: both parsers refuse duplicate keys, a float, invalid UTF-8 and over-depth input, asserted by mirrored unit tests, which catch a divergence only where the same case was written twice |

Ahead of `message/serialize/`, [`testdata/`](../../testdata/README.md) already
holds all three serializers to the same bytes, from Python, Rust and Go, by tests
that share no code. Two fixtures, and the second one is the point:

- `canonical-query` is §7's first acceptance criterion — a real query, the
  smallest a conforming requester produces.
- `profile-edges` is **not a Q2D message**. It carries key ordering above the
  BMP, every escape RFC 8259 names, `i64`'s boundaries, and the characters
  `encoding/json` escapes by default and this profile must not.

The second exists because the first could not catch a real divergence: the Rust
serializer was emitting Unicode scalar key order where §4.2 asks for UTF-16
code-unit order, and the canonical query is entirely ASCII, so it agreed anyway.
The generalisation is worth stating, because `message/serialize/` will inherit
it — **a corpus of realistic documents tests the protocol, not the profile.** No
*protocol field* reaches those edges: every field name in `core-model.md` §2 is
ASCII, and every value §2 defines is a bounded string, a count, or an enum.

A conforming query can still reach them, through `predicate.public_context`,
which §2.4 leaves to its entry's schema — a non-ASCII key, a string needing every
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
- [ ] Round trip: `parse_core(serialize_core(x)) == x` for every vector.
- [ ] `harness cross` reports agreement for every `message/` vector. Note that
      agreement is exit **3**, not 0, until [P-001](P-001-conformance-corpus.md)
      issue 19 lands — §4.8 asks for two things and this mode does one of them.
      Read the report, not the status.

The fourth item is the one that proves §4.1. A suite where every payload happens
to be profile-conformant cannot distinguish a correct verifier from one that
re-serializes.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| A verifier that re-serializes to check a signature | The non-conformant-but-valid payload vector is rejected |
| `routing` disagreeing on any projected field | Rejected at step 8, internal reason `routing_mismatch` |
| `routing` carrying a field absent from the signed object | Same |
| A float in a signed structure | `parse_core` rejects the payload carrying it. Not `serialize_core`: §4.3 puts the prohibition in the value model, so a float cannot be constructed to serialize — the case is unreachable from inside and is only observable on bytes from outside |
| Duplicate JSON keys in a payload | `parse_core` rejects |
| Envelope above 64 KiB | Rejected at step 1, on the byte slice, before allocation |
| Nesting beyond 16, or more than 64 members in an object | Rejected during the parse — §4.8. Not *before* allocation, and the distinction is real: the envelope bound is what makes the parse's work finite, and these bound its shape |
| Unknown `q2d_version` | Rejected; no attempt to interpret unknown fields |
| Hand-authored routing that happens to match | Not observable at runtime — caught by review; the interface offers no way to supply one |

The last row is honest about a limit: §4.5 is enforced by the interface shape and
by review, not by a test. An implementation could route around it, and that is
what `AGENTS.md`'s architectural-pivot rule exists for.

## 9. Escalate-if-changed decisions

1. **Producers emit the deterministic profile; verifiers must not depend on it.**
   A verifier that re-serializes reintroduces the dependency the envelope design
   removes.
2. **No floating-point in any signed structure.** Adding one reintroduces
   cross-language divergence the protocol currently has none of.
3. **`routing` is derived by projection, never authored.**
4. **The routing field allowlist is closed.** Adding a field puts it in the clear
   for every relay on the path — a disclosure decision, not a plumbing one.
5. **Lexicographic key ordering.** Changing it invalidates every byte-comparison
   vector.
6. **Digest is `sha256:` + lowercase hex.** Changing the encoding changes every
   receipt.

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Does `routing` need `type`, or is dispatch determined by endpoint?~~ | **Resolved: keep it.** Dispatch-by-endpoint is an HTTPS assumption, and `routing` exists for transports that have no endpoint to dispatch on — an A2A intermediary is the case. Dropping it would make the projection useful only where it is least needed. It stays advisory: §4.5's consistency check rejects any disagreement with `signed`, so carrying `type` adds a field an attacker can lie about only by being caught |
| ~~Does the envelope carry its own version distinct from `q2d_version`?~~ | **Resolved: no.** One version, inside the signed object. A separate envelope version would be unsigned and therefore rewritable by any intermediary, and two version numbers for one message is a negotiation surface Q2D does not have (`core-model.md` §1: no negotiation round trip) |
| ~~Are the §4.8 limits right?~~ | **Resolved for MVP: adopted as stated, and they are normative rather than advisory** — a limit an implementation may choose is not a limit, and the two implementations must reject the same payload. They are engineering estimates, not measurements, and §4.8 says so; Stage 8 measures real payloads and may lower them. Raising one is an escalation, because a limit that grows to fit a payload is not bounding anything |
| ~~Second-precision timestamps sufficient, or is sub-second needed for replay windows?~~ | **Answered: sufficient.** Uniqueness comes from the nonce, not the clock. [P-004](P-004-replay-idempotency.md) §4.3 |
| ~~Does `semantic` comparison from P-001 apply to `routing`, given it is unsigned?~~ | **Answered: yes**, and only because it is outside the signature. Anything inside `signed` compares as `bytes`. [P-001](P-001-conformance-corpus.md) §4.4 |
| ~~Does §2.1's justification for the projection allowlist hold under 0.1?~~ | **Resolved: it did not, and §2.1 no longer makes it.** [E-41](../open-escalations.md), closed as A **with B**. The 0.1 suite signs the payload without encrypting it — I decoded the corpus's own `routing/subset` vector with no key and read its `purpose` — so withholding a field from `routing` withholds nothing. §2.1 now says that outright and keeps the rule on the two grounds that hold: a projected field is legible *without decoding* and is therefore the one infrastructure indexes at scale, and the list is what makes the projection correct once a payload-encryption suite exists. [`claims.md`](../../spec/claims.md) gains **Q2D-NC-13**, recording that Q2D **does not claim** query confidentiality from an intermediary — which is where the correction belongs whichever way §2.1 is worded. Q2D-C-05 is untouched: it claims integrity |
| ~~May an envelope omit `routing`?~~ | **Resolved: yes**, and [`core-model.md`](../../spec/core-model.md) §2.1 says so — *"`routing` may be absent, and a responder must accept a message carrying only `signed`"*. [E-38](../open-escalations.md), closed as B. §2.1's opening sentence changed with it: *"a message has two parts"* implied something about presence it never meant, and now reads *"an authoritative part and an optional advisory one"*. Absence removes no guarantee — a projection that is *present* is the thing that can disagree — and requiring it would publish `predicate.id` and `target.custodian` in the clear in the one case, a direct exchange, where least disclosure could be best. **I implemented the opposite first**, arguing the corpus was evidence of intent; CLAUDE.md's hierarchy answers that directly, and the register keeps the reasoning because the mistake is the reusable part. `suite/` is routing-less again and `message/` carries the projection, so the corpus exercises both shapes |
| ~~Should §4.8's limits live in `spec/` rather than here?~~ | **Resolved: yes** — [`core-model.md`](../../spec/core-model.md) §2.8 now carries them and §4.8 cites it. [E-39](../open-escalations.md), closed as A. The argument was E-16's, unchanged: `spec/` said only *reject oversized*, so a third implementation enforced nothing. §2.8 also records what §4.8 had learned — that only the envelope limit can run before allocation, and why `signed` is exempt from the string limit. |
| ~~Does the 2 KiB string limit reach inside `public_context`?~~ | **Resolved: no** — [E-40](../open-escalations.md), closed as B, consistent with E-36. §2.8's string limit covers the fields the specification defines; a predicate's own field is bounded by its registry entry, where [`scope.md`](../../spec/scope.md) §4.1 now requires a `maxLength` on every schema describing what a requester may send, and by the 32 KiB the whole object may not exceed. §4.1's *"this document does not decide it"* is gone: §2.8 decided the message-level part, which would have left the per-field part with no owner at all. `private_input_schema` is excluded — a requester cannot send it. |
| ~~Does an integer in a signed structure have a range?~~ | **Resolved: [`scope.md`](../../spec/scope.md) §4.1** — an `integer` in any of an entry's schemas states `minimum` and `maximum`, both within −2^63 … 2^63 − 1. [E-37](../open-escalations.md), closed as B. `core-model.md` still states none, deliberately: every integer the protocol itself defines is a count, a cardinality, or a capacity in integer millibits, and the bound is a fact about registry data rather than about the protocol. So `i64` in both value models is the width §4.1 names rather than a choice the implementations made and the specification then followed. `registry/validate.py` enforces it across all three of an entry's schemas — wider than the release rule, which asks only about `output_schema`, because this is a representability question rather than a disclosure one |
| ~~Does §2.2's timestamp spelling bind every string, or only the fields §2.2 names?~~ | **Resolved: only the fields §2.2 names**, and §2.2 now says so — *"the rule reaches the fields this specification names, and no further"*. [E-36](../open-escalations.md), closed as C. A predicate wanting one spelling for a field of its own declares `format: date-time` in its registry entry, where [`scope.md`](../../spec/scope.md) §4.1 makes that an assertion rather than the annotation JSON Schema leaves it as. The three serializers already had this behaviour; what changed is that it is now what the specification says, rather than the narrowest thing they could do while the question was open. `conformance/harness/lint.py` keeps the wider rule deliberately — it lints authored vectors, which are ours |
| **Who owns `message/sign/` and `message/verify/`?** | Open, and surfaced by building §6's serializer. [P-001](P-001-conformance-corpus.md) issue 12 authored both, under P-001's §6 row naming signing and verification as part of `message/`; this PRD's §6 table names neither. Meanwhile [P-003](P-003-crypto-suites.md) §6 gives `suite/sign/` as *"JWS compact construction, byte-exact, over P-002 payloads"* — which is what `message/sign/query-minimal` already is. My view: leave the two vectors where they are and let P-003 own the mechanism, because `message/sign/` proves a P-002 payload is signable end to end and `suite/sign/` proves the suite, and those are different failures even when the bytes coincide. But that is a corpus-organisation call across three PRDs, so it belongs to whoever builds P-003, not to this one |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Core object type definitions, both languages | **Done.** [`src/value.rs`](../../src/value.rs) and [`value.go`](../../value.go). An absent optional and a null one are different documents, not merely distinguishable values — a field is in the map or it is not |
| 2 | `serialize_core` with the §4.2 profile | **Done, against a narrower gate than this row asked for.** `message/serialize/` does not exist yet (issue 10), so the byte match is asserted against [`testdata/`](../../testdata/README.md)'s two fixtures instead — read by all three serializers, including the authoring tool the corpus's own expected bytes come from. Refusals agree too, case for case: §2.2's timestamp spelling, and the protocol-level rule that a field name means what `core-model.md` says only outside `public_context`. Building it found five Rust/Go divergences, raised E-31 through E-35, and took two Codex rounds — UTF-16 key ordering, then this. The row is not closed until issue 10 lands the section |
| 3 | Float guard in the serializer | **Done, in the place the guard belongs.** Neither value model has a float variant, so §4.3's *"programming error"* is a compile error and there is no runtime path to test — and issue 4's parser refuses one on the way in, which is where external bytes arrive. Refused **syntactically**: a fraction or an exponent, rather than a value that happens to be integral. `1e2` is a hundred and no conforming producer emits it, and deciding that it *is* a hundred means exponent arithmetic — with `1e400`, arithmetic in what — which is the float-precision divergence §4.3 removes rather than manages. A `message/reject/` vector covers it under issue 10 |
| 4 | `parse_core`, rejecting duplicate keys | **Done, against a narrower gate than this row asked for** — the same position issue 2 is in. [`src/parse.rs`](../../src/parse.rs) and [`parse.go`](../../parse.go), hand-written from RFC 8259 in both. Not `encoding/json` on the Go side, and the reason is sharper than the serializer's: it resolves duplicate keys by last-wins, which is the rule §4.2 requires *rejecting*; it decodes every number into `float64`, losing an `int64` above 2^53 silently; and it substitutes U+FFFD for invalid UTF-8. Three of the four refusals are behaviours the standard library deliberately does not have. Round-tripped against both [`testdata/`](../../testdata/README.md) fixtures rather than a value invented for the test — parsing is a **two-way** agreement, and §7 asks for both implementations rather than the serializer's three. Carries §4.8's depth bound alone, because recursive descent without one is a stack overflow and *verified* is not *trusted*; issue 5 applies the full set at the envelope. **What is owed is `message/reject/`** — duplicate keys, a float, invalid UTF-8, and over-depth input are asserted today by two test suites written to mirror each other, which is weaker than a shared vector: mirrored tests catch a divergence only where someone thought to write the same case twice, where a vector is one document both runners are handed. Issue 10 authors it, and no runner answers a vector until [P-001](P-001-conformance-corpus.md) issue 19, so the section cannot be *run* against these parsers before Stage 1 either way |
| 5 | Bounded `parse_envelope` | **Done, against a narrower gate than this row asked for** — as issues 2 and 4 are. Every boundary here is a *rejection* boundary — oversize, unknown member, routing string and key length, depth, member count — and each is asserted by two suites written to mirror each other, which catches a divergence only where the same case was written twice. `message/envelope/` and `message/reject/` are issue 10's, and no runner answers a vector until [P-001](P-001-conformance-corpus.md) issue 19. [`src/envelope.rs`](../../src/envelope.rs) and [`envelope.go`](../../envelope.go). The envelope bound is checked on the byte slice before a parser exists, which is the only one of §4.8's five that *can* run before allocation; depth, members and string length are enforced during the parse, and are bounded by it. Building it corrected §4.8 twice: `public_context`'s limit cannot be enforced at step 1, because it is inside the payload that step 5 parses, and the 2 KiB string limit cannot reach `signed`, because a JWS compact of the canonical query is ~1.6 KiB before any public context and the protocol could not otherwise carry its own worked example. An unknown envelope member **denies** rather than being ignored |
| 6 | `project_routing` | **Done.** [`src/routing.rs`](../../src/routing.rs) and [`routing.go`](../../routing.go). `Routing` wraps a private value whose only origin is the projection, so §4.5's *never authored* is a property of the type rather than a rule a caller keeps — the honest limit being §8's last row: code *inside* the crate or package can still construct one, and what the type removes is the accident rather than the determined bypass. Go's reader returns a **deep copy**, because `Object` is a map and handing back the stored value would let a caller write `r.Value().(q2d.Object)["purpose"] = …` — authoring a routing field through the API that exists to stop it. Rust's `as_value` gets that from an immutable borrow; Go has to copy, and a test mutates a nested member to prove a shallow one would not do. Go also admits `q2d.Routing{}` where Rust's private tuple field does not — harmless, because the zero value carries no fields and reads as the projection of nothing, which §2.1 permits: a caller can construct an empty projection and cannot construct one with fields it chose. Derivation is total: a core object missing a projected field does not project it, which is what §2.1's *strict subset* and §4.6's *each field present* already describe, so there is no error path to handle wrongly and no temptation to default a field that was not there. **Checked against something authored independently** — projecting the canonical query reproduces `author_message.py`'s hand-written `ROUTING` byte for byte, and every `message/` vector's envelope carries that literal, so a disagreement would mean either §4.5 or five merged vectors are wrong |
| 7 | `check_routing` | **Done.** In [`src/routing.rs`](../../src/routing.rs) and [`routing.go`](../../routing.go), beside the projection they check. Objects recurse — a projection carrying `target.custodian` is a subset of a `target` that also has `subjects` — and everything else compares whole, because §4.4 makes array order significant and a subset rule for arrays would let a relay drop an element and call it a projection. Nothing is coerced: an integer never equals the string that spells it, which is what §4 step 8's *same type, same value* asks for. The mismatch carries the **path and neither value** — the projection is attacker-supplied and the core object is the requester's — and it is the *internal* reason, kept a separate type from the wire response P-009 builds even though §5.2.1 spells the external value the same. **A field outside §4.5's allowlist is refused however faithful the copy** — §2.1 says `routing` *carries at most* those six, so `purpose` matching the signed value byte for byte is still rejected, because the harm is the projection rather than the mismatch. `message/routing/introduces-field` pins exactly that and the first version of this check would have passed it; the two internal reasons take the corpus's own names, `routing_signed_mismatch` and `routing_introduced_field`, rather than a third vocabulary for the same two facts. **The comparison is against `project_routing(core)`, not against the core object.** Comparing against the core object means enumerating what `routing` may *not* contain, and review found three of those one at a time — a field outside the allowlist, a literal `"predicate.id"` key read as a nested path, a value that differs. §4.5 already says what a projection holds, and says it by construction, so *is this a subset of that* answers all three at once. The two reasons then mean what their names say: introduced is **not in the derivation**, mismatch is **in it and different**. One case is deliberately accepted and **[E-42](../open-escalations.md) closed as A**: `{"target":{}}` is not something the projection emits and is refused by nothing §2.1 states, which is where *not derivable* and *not permitted* come apart. §2.1 now says it rather than leaving it to be inferred — *"may carry fewer, or none of them, at any depth"* — because the next implementation will meet the same question, and an unstated answer inside a security check is where two implementations quietly differ. An absent projection passes: nothing that is not there can disagree ([E-38](../open-escalations.md)). A test asserts the two halves agree — a derived projection always passes the check, which is what stops every conforming exchange failing at step 8 |
| 8 | Digest construction | **The construction is done**; the four call sites are not, and cannot be here. [`src/digest.rs`](../../src/digest.rs) and [`digest.go`](../../digest.go) implement `"sha256:" + lowercase_hex(SHA-256(bytes))`, held to [`testdata/digests.txt`](../../testdata/README.md) across three provenances: Rust writes SHA-256 out by hand — its standard library has none and the crate takes no dependencies — gated on FIPS 180-4's published known answers; Go uses `crypto/sha256`; `hashlib` wrote the fixture. A defect in the hand-written one therefore shows up as a disagreement with two standard libraries rather than as its own private truth. **What each of the four digests covers is P-011's and P-012's**, and `response_digest` is the one to watch: the receipt travels inside the response and carries the digest, so digesting the whole response would include it — P-011 §4.2 is authoritative. `message/digest/` is issue 10's |
| 9 | Version field handling | **Done.** [`src/version.rs`](../../src/version.rs) and [`version.go`](../../version.go). One value, not a range — a range implies a negotiation and [`core-model.md`](../../spec/core-model.md) §1 has none. The function **reads exactly one key**, which makes *without interpreting other fields* structural rather than a discipline a caller keeps, and a test hands it a message whose every other field is wrong to prove nothing else is consulted. **Not the stronger claim that nothing is read first**: step 5 is *parse the verified core object*, so parsing precedes this and may reject on its own — those are §5.2.1's `malformed`, the other cause that row gives for step 5, so a message that never reaches the check is still refused under the right external value. It takes the verified core object and has **no parameter for `routing`**: §5.2.1 puts `unsupported_version` at step 5 precisely because the authoritative value is inside the signed object, and §4 step 2's shedding on a projected copy is load shedding rather than a rejection reason. **Absent and non-string are `malformed`, not `unsupported_version`** — §5.2.1 gives those two rows separately, and §2.2 requires the field, so *missing a field §2 requires* is the row that applies. The internal value keeps the distinction because the external ones differ, which is the mirror image of `routing`'s two internal reasons collapsing into one external: there normalization is the point, here it would send a requester looking for a version it does not have. `message/reject/`'s unknown-version vector is issue 10's |
| 10 | Author `message/` corpus section | All five groups present; `harness lint` clean. **To be authored through the operations that already exist.** Worth stating because the first reading of the `operation` enum is that four of these five groups need names it does not have; they do not. The corpus tests protocol behaviour through protocol operations, so §4.2's serializer is exercised by a `sign_query` vector asserting the compact string byte for byte — `message/sign/query-minimal` is the one that exists and does exactly this — and the parser and §2.8's limits *will be* exercised by `verify_query` and `process_query` vectors whose payloads are malformed one way each. `digest` is in the enum on its own account and no vector uses it yet.

**`serialize/` is written** — four vectors, generated by [`tools/author_message.py`](../../tools/author_message.py) with a `--check` in the suite: key order above the BMP, minimal escaping and what must *not* be escaped, `i64`'s boundaries, and empty containers beside a present null. Each signs a query whose `public_context` carries the shape and asserts the compact string byte for byte, so a wrong key order or a stray escape changes the payload segment and fails the comparison. They are deliberately not schema-valid for any registered entry — `sign_query` resolves no predicate, and §4.2's edges are unreachable through a public context an entry would declare, which is the same reason `testdata/profile-edges` exists.

**`envelope/`, `digest/` and `reject/` are not**, and three of their cases cannot be authored in this format at all: a vector's `input.envelope` is a parsed object, so **an oversized envelope** (a byte limit), **duplicate keys** (which no JSON object can carry) and **a float in a payload** (which the authoring tool refuses to emit, by §4.3) have no expression. Over-depth, too many members, an over-long string, an unknown member and an unknown version all do. This is the shape P-001 issue 14 hit from the other side — a vector must be able to *say* the thing it asserts — and it is a P-001 format question rather than one to settle here.

**`digest/` waits on one small decision**: `digest` is in the operation enum and no vector uses it, so the first one settles whether its input carries base64url, hex, or a value to serialize. That is a runner-contract choice every implementation then keeps. Until they do, every behaviour listed below is covered only by two suites written to mirror each other.

P-001 issue 17's remit is the **Stage 5–8** extension; P-002 is Stage 1, and nothing here waits on it.

**What the implementations owe this section**, gathered here rather than repeated in each issue row: duplicate keys, a float, invalid UTF-8, over-depth and over-wide input (issue 4); an oversize envelope, an unknown envelope member, and a `routing` string or key above 2 KiB (issue 5); and §2.8's three string bounds by position — a protocol field at 2 KiB, `predicate.public_context` at 32 KiB both per string and as an object, and `signed` at the envelope limit ([E-40](../open-escalations.md)). Each is asserted today by two suites written to mirror each other, which catches a divergence only where the same case was written twice. None can be *run* against the implementations until [P-001](P-001-conformance-corpus.md) issue 19 gives a runner that answers. |
| 11 | Non-conformant-but-valid payload vector | Proves verification does not re-serialize |
| 12 | `routing` carries `type`; §4.8 limits enforced as normative | `message/routing/` covers a `type` disagreement; an over-limit payload rejects identically in both implementations |

Issue 1 blocks the rest.
