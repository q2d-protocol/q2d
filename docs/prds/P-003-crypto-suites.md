# P-003 — Cryptographic suites, key handling, downgrade policy

| Field | Detail |
|---|---|
| PRD | P-003 |
| Stage | 1 |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | **high** — the only module where a subtle error is silently exploitable |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-002](P-002-message-envelope.md) |
| Blocks | P-004, P-005, P-010, P-011, P-012, P-014, P-016 |
| Pairs with | [P-002](P-002-message-envelope.md) — P-002 produces the bytes this PRD signs |

---

## 1. Purpose

Implement `eddsa-jws-2026`, the suite registry that carries it, the verifier's
minimum-acceptable policy, and the downgrade rejection that makes agility
something other than a downgrade oracle.

This is the highest-risk module in Stage 1. Every other module fails loudly when
wrong; this one can be wrong and still return `true`.

**Claims served:** Q2D-C-05 (request binding) and Q2D-C-06 (response
authentication) — both of which hold only *relative to the suite in force and the
verifier's minimum acceptable policy*, which is precisely what this PRD
implements.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §1 | A suite names algorithm, serialization, and hash as one unit |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §2 | Registry entry fields, status, deprecation dates |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §3 | `eddsa-jws-2026`; no canonicalization suite is registered |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §4 | The three downgrade rules |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §5 | The receipt records the suite used |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §6 | `deprecated` still verifies; `withdrawn` does not |
| [`spec/core-model.md`](../../spec/core-model.md) §2.7 | `signature.profile` is a field of the signed core object |
| [`spec/core-model.md`](../../spec/core-model.md) §4 steps 3–5 | Suite check before verification; verification before parse |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-05, Q2D-C-06 | Both qualified by suite and verifier policy |

## 3. Module boundary

**Inside:** JWS compact construction and verification; the suite registry and its
loading; suite resolution and the verifier's acceptable set; downgrade rejection;
the key-resolution interface; test key material; the suite value handed to the
receipt.

**Explicitly outside:** the payload bytes (**P-002**). Identity profiles, key
rotation, delegation chains, and pairing (**P-014**) — this PRD defines the
resolver *interface* and P-014 supplies an implementation. Replay and expiry
(**P-004**). Receipt construction (**P-011**), which consumes the suite value
this PRD produces.

## 4. Design

### 4.1 JWS compact, and the one place trust is unavoidable

```
signed = BASE64URL(protected_header) "." BASE64URL(payload) "." BASE64URL(signature)
signing_input = ASCII(BASE64URL(protected_header) "." BASE64URL(payload))
```

The protected header is covered by the signature. The payload is the byte string
[P-002](P-002-message-envelope.md) produced.

There is exactly one moment where a verifier must read attacker-controlled data
before verifying anything: **it must know which algorithm to verify with.** That
is the classic JWS algorithm-confusion surface, and the mitigation is not to
avoid reading the header — it is to never let the header *decide*.

### 4.2 The header declares; local policy decides

```
1. Read the declared suite from the protected header.
2. Reject unless it is a member of the verifier's own acceptable set.
3. Verify using the parameters of the registry entry for that suite —
   never parameters taken from the header.
4. After verification, confirm the payload's signature.profile equals the
   header's declared suite. Mismatch rejects.
```

Step 2 is the whole defence. A verifier that verifies with whatever the header
names has agility in the same sense that an unlocked door has a lock.

Step 4 looks redundant — both header and payload are signature-covered, so
neither can be altered without detection. It is not redundant. It catches a
**producer** that signs a payload declaring one suite using a header declaring
another, which is a real implementation bug and one that no verifier would
otherwise notice. The two declarations exist for different readers, and confirming
they agree costs one comparison.

**`alg: none`, and any header presenting an unsigned or unregistered algorithm,
is rejected at step 2** by construction — it is not in the acceptable set. No
special case is written for it, and no code path may exist that treats absence of
an algorithm as a valid state.

### 4.3 The suite registry is data, not code

Suites live in `registry/suites.json`, mirroring the shape of
[`registry/manifest.json`](../../registry/manifest.json): entries with `id`,
`algorithm`, `serialization`, `hash`, `status`, effective and deprecation dates,
security notes, references.

One suite is registered for MVP. Making it a file anyway is deliberate: adding a
second suite becomes a data change rather than a code change in two languages,
and the pinning and status-checking code paths are exercised from the first day
rather than retrofitted after they are needed. A pinning path that has never run
is a pinning path that does not work.

### 4.4 Status semantics

| Status | Producing | Verifying |
|---|---|---|
| `active` | permitted | permitted |
| `deprecated` | **refused** | permitted |
| `withdrawn` | refused | **refused** |

The asymmetry is the point. A deprecated suite must still verify, because
receipts signed under it remain evidence. A withdrawn suite must not, because
continuing to accept it is the downgrade the registry exists to prevent.

Neither status retroactively invalidates a receipt. A verifier assessing an old
receipt reads the suite it records ([`crypto-suites.md`](../../spec/crypto-suites.md)
§5) and judges accordingly — which is only possible because the suite is recorded.

### 4.5 Rejection is not negotiation

A suite rejection returns a failure that names **no alternative** and reveals
nothing about the acceptable set. Suggesting a suite the verifier would accept
turns every rejection into a probe of local policy.

Supported suites are advertised through capability discovery, where advertising
them is a deliberate choice made once, rather than leaked one rejection at a time.

### 4.6 Key resolution interface

```
resolve_key(key_id: KeyId) -> Result<PublicKey, ResolutionError>
```

That is the entire surface this PRD owns. Where the key comes from, how it was
established, how it rotates, and whether a delegation chain authorizes it are
[P-014](P-014-identity-pairing.md)'s concerns.

Two invariants this PRD does enforce:

- **A key that cannot be resolved is a rejection, never a default.** No
  fallback key, no "try the last known good", no unauthenticated acceptance.
- **The resolver is consulted before verification, and its failure is
  indistinguishable on the wire from a signature failure.** Distinguishing them
  tells a requester whether a key is known, which is relationship existence.

### 4.7 Test key material

Fixed Ed25519 keypairs, committed, marked test-only in filename and header.
Seeded from RFC 8032 §7.1 test vectors where they fit, so key handling is
checkable against an independently published source before any Q2D structure is
involved. If our Ed25519 does not reproduce RFC 8032's known signatures, nothing
above it is worth testing.

## 5. Interfaces

```
sign(payload: bytes, key: PrivateKey, suite: SuiteId)  -> Result<CompactJws>
verify(compact: CompactJws, policy: SuitePolicy)       -> Result<VerifiedPayload>
    // returns the payload bytes; P-002's parse_core consumes them

load_suites(path)                 -> SuiteRegistry
resolve_suite(id, registry)       -> Result<SuiteEntry>     // status-aware
acceptable(id, policy)            -> bool                   // local policy only
resolve_key(key_id)               -> Result<PublicKey>
```

`verify` returning payload **bytes** rather than a parsed object is deliberate:
the ordering requirement in [`core-model.md`](../../spec/core-model.md) §4 steps
4–5 becomes a type-level fact rather than a comment. There is no way to obtain a
parsed core object without having verified it first.

`SuitePolicy` is constructed from local configuration and **never** from anything
in a message. There is no code path that derives it from received data.

## 6. Corpus sections

`suite/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `suite/rfc8032/` | Raw Ed25519 against RFC 8032 §7.1 known-answer vectors |
| `suite/sign/` | JWS compact construction, byte-exact, over P-002 payloads |
| `suite/verify/` | Valid, tampered payload, tampered header, tampered signature |
| `suite/downgrade/` | Below-floor suite, unregistered suite, `alg: none`, header/payload mismatch |
| `suite/status/` | Deprecated verifies but will not produce; withdrawn refuses both |
| `suite/keys/` | Unresolvable key; rejection indistinguishable from signature failure |

## 7. Acceptance

- [ ] Raw Ed25519 reproduces every RFC 8032 §7.1 vector in both implementations.
- [ ] Both produce **byte-identical** compact JWS for the same key and payload —
      Ed25519 determinism makes this a byte comparison, not a both-verify check.
- [ ] Each implementation verifies the other's signatures. **This is
      [P-001](P-001-conformance-corpus.md) issue 19, not the `harness cross`
      that exists today** — that one compares what two runners each produced,
      which exercises both signers and neither verifier. Blocked until 19 lands,
      and this PRD is one of the two it is blocked on: issue 19 needs to know
      which operation consumes a signed envelope, which is settled here.
- [ ] `verify` returns bytes; no path exists from a compact JWS to a parsed core
      object that skips verification. Asserted by type signature, not by test.
- [ ] A deprecated suite verifies and refuses to sign; a withdrawn suite refuses
      both.
- [ ] The suite registry loads from `registry/suites.json` and status is honoured
      from the file, not from a compiled-in table.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| `alg: none`, or any unregistered algorithm | Rejected at step 2; no special case in the code, and none may be added |
| A suite below the verifier's floor | Rejected, with **no alternative named** in the response |
| Header suite ≠ payload `signature.profile` | Rejected after verification |
| Verifying with parameters taken from the header rather than the registry entry | Header-parameter vector verifies when it must not |
| A withdrawn suite | Verification refuses |
| Signing under a deprecated suite | Production refuses |
| An unresolvable key distinguishable from a bad signature | Two rejections with differing wire responses; caught by the P-001 denial-uniformity assertion |
| A `SuitePolicy` derived from message content | No constructor accepts message-derived input; caught by review and interface shape |
| Signature valid over a *different* payload | Rejected |

The fourth row is the one worth building a vector for deliberately: a
malformed-but-plausible header carrying parameters that would weaken
verification, which a correct implementation ignores entirely because it uses the
registry entry.

## 9. Escalate-if-changed decisions

1. **The verifier's acceptable set is local policy and is never derived from a
   message.** This is the entire downgrade defence.
2. **Verification parameters come from the registry entry, never from the
   header.** The header declares; it does not configure.
3. **Header suite and payload suite must match.** Catches a producer bug no
   verifier would otherwise see.
4. **Rejection names no alternative.** Otherwise every rejection probes local
   policy.
5. **Deprecated verifies; withdrawn does not.** Reversing either breaks receipt
   evidence or reopens downgrade.
6. **Suites are data.** Compiling them in makes a second suite a code change in
   two languages and leaves the pinning path untested.
7. **`verify` returns bytes, not a parsed object.** The ordering requirement is
   carried by the type system.

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Does `registry/suites.json` need its own signature and pinned digest while it holds one entry?~~ | **Resolved: yes**, the same mechanism as the predicate manifest ([`core-model.md`](../../spec/core-model.md) §2.4.1, [P-005](P-005-registry-client.md) §4.2). One entry today is exactly why: the verification path is cheap to build now and becomes load-bearing the moment a second suite exists, and a file that decides which algorithms a verifier accepts is the last one that should be unauthenticated. The daemon refuses to start on a digest mismatch, like the predicate manifest |
| ~~Where does `SuitePolicy` come from — config file, environment, compiled default?~~ | **Resolved: a config file, over a compiled-in floor that configuration may raise and may never lower.** Environment variables are rejected as a source: they are invisible in review, trivially altered by anything sharing the process, and a downgrade that lands via an environment variable leaves no artifact anyone would think to check. Startup fails if configuration attempts to lower the floor — it is not silently clamped, because a clamped misconfiguration reads as success ([P-013](P-013-https-binding.md) §4.6) |
| ~~Key rotation and revocation semantics~~ | **Answered for this profile:** rotation is re-pairing, revocation is local and does not propagate. [P-014](P-014-identity-pairing.md) §4.5 |
| ~~Does an unresolvable key debit anything, or leave state?~~ | **Answered: no.** The budget is first touched at step 15 ([P-008](P-008-capacity-accounting.md) §4.2) and key resolution fails at step 4, so nothing reachable holds state |
| ~~Should capability discovery advertise suites at all in MVP, given §4.5~~ | **Answered:** yes, from configuration, defaulting to the MTI alone. [P-013](P-013-https-binding.md) §4.4 |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Ed25519 primitive wired to a vetted library, both languages | `suite/rfc8032/` passes; no hand-rolled curve arithmetic |
| 2 | Base64url without padding, both languages | Round-trip property test; rejects padded input |
| 3 | `registry/suites.json` format, file, and loader | Loads; status read from file; open question 1 resolved |
| 4 | `SuitePolicy` construction from config | No constructor accepts message-derived input |
| 5 | `sign` — compact JWS construction | `suite/sign/` byte-matches across implementations |
| 6 | `verify` — the four-step sequence in §4.2 | `suite/verify/` and `suite/downgrade/` pass |
| 7 | Header/payload suite agreement check | Mismatch vector rejects |
| 8 | Status enforcement, both directions | `suite/status/` passes |
| 9 | `resolve_key` interface plus a test-fixture implementation | Unresolvable key rejects; wire response identical to signature failure |
| 10 | Test key material, RFC 8032-seeded | Committed, marked test-only, referenced by fixtures |
| 11 | Author `suite/` corpus section | Six groups present; `harness lint` clean |
| 12 | Header-parameter attack vector | A header carrying weakening parameters is ignored, not honoured |
| 13 | Suite value exposed for receipt construction | [P-011](P-011-receipts-audit.md) can record it without reaching into this module |

Issue 1 blocks everything. Issue 3 blocks 4, 6, and 8, and now includes signing
`registry/suites.json` and pinning its digest.
