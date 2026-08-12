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
| Timestamps | RFC 3339 with `Z`, second precision |
| Strings | minimal escaping; no `\uXXXX` for characters representable directly |
| Duplicate keys | prohibited on production, rejected on parse |

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

The serializer enforces this: a float reaching it is a programming error and
fails loudly rather than emitting a value two implementations might render
differently. Adding a float field is an escalation, not a schema change.

### 4.4 Envelope

```
{ "signed": "<JWS compact>", "routing": { … } }
```

`signed` is opaque to the envelope layer. Its internal structure belongs to
P-003; this PRD treats it as a string and never inspects it.

### 4.5 The routing projection is derived, never authored

A producer **derives** `routing` from the core object by projection. It never
constructs one independently.

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
`public_context` are **never** projected. They travel in the clear if projected,
and they are what the protocol exists to bound.

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

Enforced at §4 step 1, before allocation on attacker-controlled input.

| Limit | Value |
|---|---|
| Envelope | 64 KiB |
| `public_context` | 32 KiB |
| Any single string field | 2 KiB |
| Nesting depth | 16 |
| Object members per object | 64 |

Values are proposed, not derived. Open question 3.

## 5. Interfaces

```
serialize_core(core: CoreObject)          -> bytes        // §4.2 profile; errors on float
parse_core(payload: bytes)                -> CoreObject   // post-verification only
project_routing(core: CoreObject)         -> Routing      // derive; never authored
check_routing(core: CoreObject, r: Routing) -> Result     // compare only
build_envelope(signed: str, routing: Routing) -> Envelope
parse_envelope(bytes)                     -> Envelope     // bounded; §4.8
digest(bytes)                             -> DigestString
```

`parse_core` taking bytes that have already been verified is deliberate: the
signature is checked by P-003 before this function is reachable, so the type
system carries the ordering requirement rather than a comment.

## 6. Corpus sections

`message/` — authored under this PRD, against the P-001 format.

| Group | Vectors |
|---|---|
| `message/serialize/` | Key ordering, omitted optionals, integer forms, timestamp format, escaping |
| `message/envelope/` | Construction, parse, size limits, depth limit |
| `message/routing/` | Derivation, strict subset, each disagreement case, a routing field absent from signed |
| `message/digest/` | Each of the four digests against known bytes |
| `message/reject/` | Oversized, over-deep, duplicate keys, float present, unknown version |

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
| A float in a signed structure | `serialize_core` errors; no bytes produced |
| Duplicate JSON keys in a payload | `parse_core` rejects |
| Envelope above 64 KiB, or nesting beyond 16 | Rejected at step 1, before allocation |
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

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Core object type definitions, both languages | Types compile; optional fields distinguishable from null |
| 2 | `serialize_core` with the §4.2 profile | `message/serialize/` vectors byte-match across implementations |
| 3 | Float guard in the serializer | A float field errors at serialization, with a test proving it |
| 4 | `parse_core`, rejecting duplicate keys | Round-trip property test passes |
| 5 | Bounded `parse_envelope` | Size, depth, and member limits enforced before allocation |
| 6 | `project_routing` | Derivation is total; no code path constructs a `Routing` otherwise |
| 7 | `check_routing` | Every disagreement case in `message/routing/` rejects |
| 8 | Digest construction | `message/digest/` vectors match; prefix present |
| 9 | Version field handling | Unknown version rejects without interpreting other fields |
| 10 | Author `message/` corpus section | All five groups present; `harness lint` clean |
| 11 | Non-conformant-but-valid payload vector | Proves verification does not re-serialize |
| 12 | `routing` carries `type`; §4.8 limits enforced as normative | `message/routing/` covers a `type` disagreement; an over-limit payload rejects identically in both implementations |

Issue 1 blocks the rest.
