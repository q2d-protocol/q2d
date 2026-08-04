# P-005 — Registry client: pinning, resolution, fail-closed

| Field | Detail |
|---|---|
| PRD | P-005 |
| Stage | 2 |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | **high** — a registry compromise defines what "bounded" means |
| Depends on | [P-002](P-002-message-envelope.md), [P-003](P-003-crypto-suites.md) |
| Blocks | P-006, P-007, P-008, P-010, P-011, P-012 |
| Pairs with | [P-006](P-006-request-validation.md) — this PRD obtains a trusted entry; P-006 validates a request against it |

---

## 1. Purpose

Load and verify the predicate manifest, pin it, resolve a requested predicate to
a trusted entry, and fail closed on everything else.

This is where Q2D-C-02 lives, and Q2D-C-02 is the claim that most distinguishes
Q2D from a hand-written predicate API. A responder that resolves predicates
loosely is a predicate API with extra ceremony.

**Claims served:** Q2D-C-02 (responder-owned domain validation) directly.
Q2D-C-03 and Q2D-C-09 depend on it — a bounded output and a correct debit are
both computed from an entry this module vouches for.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/scope.md`](../../spec/scope.md) §2 | Capability 2 of a participating custodian: resolve against a registry it trusts and reject the unknown |
| [`spec/scope.md`](../../spec/scope.md) §4 | Phase 1 registry is a signed manifest whose key and digest the custodian pins |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 10 | Predicate known, version known, not revoked, digest pinned; fail closed |
| [`spec/core-model.md`](../../spec/core-model.md) §2.4 | `predicate.registry_digest` — what the requester believes is in force |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-02 | Effective domain resolved from a registry the responder trusts |
| [`spec/terminology.md`](../../spec/terminology.md) §3 | Registry entry field set |
| [`registry/README.md`](../../registry/README.md) | Pinning model; the manifest is currently unsigned and therefore not a trust anchor |
| [`registry/manifest.json`](../../registry/manifest.json) | The entry format this client parses |

## 3. Module boundary

**Inside:** manifest loading and signature verification; key and digest pinning;
predicate resolution by id and version; status and revocation handling; the
fail-closed enumeration; the audit record of a requester/custodian digest
mismatch.

**Explicitly outside:** schema validation of `public_context`, answer-contract
narrowing, and effective-domain computation (**P-006**). Capacity arithmetic
(**P-008**) — this module supplies the entry's authored value and computes
nothing. Predicate evaluation (**P-010**). The suite registry (**P-003**), which
is a separate file with a separate pin.

## 4. Design

### 4.1 Two pins, and why both

| Pin | Establishes |
|---|---|
| Signing key(s) | The manifest came from a publisher this custodian recognises |
| Manifest digest | The manifest is **this exact content**, which this custodian has accepted |

The signature is **authentication**. The digest pin is **authorization**. Both
are required, and the digest pin is the stronger of the two:

> A compromised registry signing key cannot change what a custodian evaluates,
> because the new manifest will not match the pinned digest. Registry compromise
> becomes an availability problem rather than a disclosure one.

That property holds only if a custodian never auto-accepts a new digest, which is
why §4.3 forbids automatic refresh. Accepting a new manifest is an operator
action: read the diff, change the pin, restart.

### 4.2 Failure to load means failure to serve

If the manifest is missing, unsigned, signed by an unpinned key, or does not
match the pinned digest, the responder **does not serve**. Every query rejects.

There is no fallback to a previously loaded manifest and no degraded mode. A
responder that keeps answering from stale definitions after failing to verify
current ones has silently chosen availability over the property Q2D-C-02 asserts.

### 4.3 No automatic refresh

The manifest is loaded from local configuration at startup. There is no network
fetch, no polling, no update channel.

An automatic update path is a remote-controlled redefinition of what this
custodian considers bounded. Even signed and digest-checked, it moves the
authorization decision from the operator to whoever controls the channel.

### 4.4 No unsigned-manifest bypass

The loader requires a signature. There is **no** flag, environment variable, or
build feature that accepts an unsigned manifest.

Test fixtures carry a real signature under a committed test key. A bypass added
for tests is a bypass available in production, and this is the module where that
matters most.

This is work: [`registry/manifest.json`](../../registry/manifest.json) is
currently unsigned by design, and signing it is issue 2 below.

### 4.5 The requester's declared entry digest must match

`predicate.registry_digest` is the digest of the **registry entry** the requester
built against ([`core-model.md`](../../spec/core-model.md) §2.4.1). It is not the
manifest digest, and the two do different jobs: the manifest digest is what this
custodian accepted, the entry digest is whether both parties mean the same thing
by this predicate.

**A mismatch rejects**, before private access, under the normalized class.

This was originally specified as advisory — proceed under the custodian's entry
and record the mismatch — on the reasoning that predicate id and version are
immutable, so a differing digest meant the manifest changed elsewhere. That
reasoning was sound and its premise was unenforceable: nothing detected a
publisher mutating an entry in place.

The failure it left open is **semantic mutation without shape change**. A
predicate edited from *"is any item compatible"* to *"does any item conflict"*
keeps its release shape, domain, capacity, and schema. Every check passes, the
intersection is clean, the debit is right — and the answer means the opposite of
what the requester believes. Per-entry digests turn an unenforceable convention
into a comparison.

The custodian was always protected here, by reviewing the diff before changing
its pin. The requester was not. This closes that asymmetry.

### 4.6 Status

| `status` | Behaviour |
|---|---|
| `active` | Resolvable |
| `deprecated` | **Rejected for new requests.** Receipts referencing it remain valid evidence |
| `revoked`, or `revoked_from` in the past | Rejected |

Unlike a cryptographic suite, a predicate is evaluated fresh on every request, so
there is no "still verify old ones" case. Deprecated and revoked both reject; they
differ only in what an operator is being told about intent.

An entry whose `effective_from` is in the future is not yet resolvable.

### 4.7 The fail-closed enumeration

Every way resolution can fail, all rejecting before private access, all mapping
to one normalized external class:

1. manifest absent, unreadable, or malformed
2. manifest signature invalid
3. manifest signed by an unpinned key
4. manifest digest does not match the pin
5. predicate id unknown
6. version unknown for a known id
7. entry `deprecated` or `revoked`
8. entry not yet effective
9. entry requires an assurance profile the responder does not support

Items 1–4 prevent the responder from serving at all (§4.2). Items 5–9 reject the
individual request. **All nine produce the same wire response** — a requester
must not learn which predicates this custodian supports, because that is
custodian-private policy.

## 5. Interfaces

```
load_manifest(path, pins: RegistryPins) -> Result<Registry, LoadError>
   // verifies signature against pinned keys, then digest against pinned digest
   // also verifies every entry_digest against its entry's canonical bytes
   // LoadError is fatal to serving; there is no partial success

resolve(registry, id: PredicateId, version: Version, declared: DigestString)
   -> Result<Entry, ResolveError>
   // status-aware; effective-date aware; rejects on entry-digest mismatch
```

`resolve` taking the declared digest is deliberate. A separate comparison call
could be skipped; a parameter cannot.

`RegistryPins` is constructed from local configuration and never from anything in
a message — the same rule as `SuitePolicy` in
[P-003](P-003-crypto-suites.md) §5, and for the same reason.

`digest_matches` returning `bool` rather than `Result` is deliberate: a `Result`
invites a caller to propagate it as a failure, and this value must never gate an
exchange.

## 6. Corpus sections

`registry/` — this PRD authors the client groups. The predicate evaluation
vectors already in [`registry/manifest.json`](../../registry/manifest.json) are
consumed by [P-010](P-010-responder-pipeline.md).

| Group | Vectors |
|---|---|
| `registry/pin/` | Correct key and digest; unpinned key; wrong digest; unsigned manifest |
| `registry/resolve/` | Known id and version; unknown id; unknown version of a known id |
| `registry/status/` | Active resolves; deprecated rejects; revoked rejects; not-yet-effective rejects |
| `registry/entry-digest/` | Match resolves; mismatch rejects; a manifest whose stored entry digest is wrong fails to load |
| `registry/uniformity/` | All nine failure modes produce one wire response |

## 7. Acceptance

- [ ] Both implementations reject an unsigned manifest, with no bypass reachable
      from configuration, environment, or build features.
- [ ] Both reject a validly-signed manifest whose digest is not pinned.
- [ ] A load failure leaves the responder rejecting every query, not serving from
      a previous manifest.
- [ ] All nine failure modes in §4.7 produce a **byte-identical** wire response —
      asserted by the P-001 cross-vector denial-uniformity check, not per-case.
- [ ] A requester-declared entry-digest mismatch rejects, under the same wire
      response as every other resolution failure.
- [ ] `load_manifest` recomputes every `entry_digest` and refuses a manifest where
      any is wrong — a stored digest is never trusted as authored.
- [ ] `registry/manifest.json` is signed, and the committed signature verifies in
      both implementations.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| Loading an unsigned manifest | No configuration reaches a loaded state; grep for a bypass finds none |
| Loading a manifest signed by an unpinned key | Rejected even though the signature is valid |
| Loading a manifest whose digest is unpinned | Rejected even though signature and key are valid |
| Serving after a load failure | Every query rejects; no cached entry is reachable |
| Any network fetch of a manifest | No HTTP client is linked into this module — asserted by dependency check |
| Resolving a revoked or deprecated entry | Rejected |
| A rejection revealing which predicates are supported | Uniformity assertion fails |
| An entry-digest mismatch proceeding | `registry/entry-digest/` mismatch vector returns an answer |
| A stored `entry_digest` trusted without recomputation | Manifest with a tampered entry and matching stored digest loads |

Row 5 is checkable mechanically and worth doing: the registry client having no
network dependency at all is stronger than a rule saying it must not fetch.

## 9. Escalate-if-changed decisions

1. **Signature authenticates; the digest pin authorizes. Both are required.**
2. **No automatic refresh.** Accepting a new manifest is an operator action.
3. **No unsigned-manifest bypass exists**, in any build configuration.
4. **A load failure means the responder does not serve.** No fallback, no
   degraded mode.
5. **The requester-declared entry digest must match, and a mismatch rejects.**
6. **Every `entry_digest` is recomputed at load.** A stored digest is data, not
   evidence.
7. **All resolution failures share one wire response.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Nothing detects a publisher mutating an entry without a version bump~~ | **Resolved.** Per-entry digests added to `registry/manifest.json`; `core-model.md` §2.4.1 written; §4.5 rewritten to fail closed |
| Which key signs `registry/manifest.json` for MVP, and where does its private half live? | This PRD; blocks issue 2 |
| Should a custodian be able to pin a *subset* of a manifest's entries? | Deferred; adds a second authorization surface with no MVP need |
| ~~How does a custodian learn a new digest exists?~~ | **Answered:** out of band; the capability document carries no manifest digest, for the update-channel reason in §4.3. [P-013](P-013-https-binding.md) §4.4 |

Open question 1 is resolved. §4.5 no longer rests on immutability being observed;
it rests on a digest comparison.

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | `RegistryPins` from configuration | No constructor accepts message-derived input |
| 2 | Sign `registry/manifest.json`; commit signature and public key | Signature verifies in both implementations; open question 2 resolved |
| 3 | `load_manifest` with signature then digest verification | `registry/pin/` passes; no bypass exists |
| 4 | Manifest parsing into typed entries | Every field in `terminology.md` §3 is represented or explicitly unused |
| 5 | `resolve` with status and effective-date handling | `registry/resolve/` and `registry/status/` pass |
| 6 | Fail-to-serve state | Load failure leaves every query rejecting |
| 7 | Entry-digest comparison inside `resolve` | `registry/entry-digest/` passes; mismatch rejects |
| 8 | Uniformity across all nine failure modes | `registry/uniformity/` passes under the cross-vector check |
| 9 | Dependency assertion: no network client in this module | CI check fails if one is linked |
| 10 | Author `registry/` client corpus groups | Five groups; `harness lint` clean |
| 11 | ~~Escalate open question 1~~ — **done** | Resolved; manifest, spec, and §4.5 updated |
| 12 | Recompute every `entry_digest` at load | Tampered-entry manifest with a matching stored digest is refused |

Issue 2 blocks 3. Issue 11 is complete, and it landed **before** issue 2 as
required — the manifest gained its entry digests before anything signed it.
