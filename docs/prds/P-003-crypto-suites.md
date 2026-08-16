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

**The header's members are `suite` and `key_id`, and no others** —
[`crypto-suites.md`](../../spec/crypto-suites.md) §3 defines them and why the
set is closed. Two consequences for this module: `key_id` is what §4.2 step 1's
sibling resolves at [`core-model.md`](../../spec/core-model.md) §4 step 4,
because the payload's `signature.key_id` cannot be read yet; and `resolve_key`
takes that identifier as a **lookup into a set the implementation already
trusts**, never a path or a URL, since it is attacker-controlled and read before
anything is authenticated.

There is exactly one moment where a verifier must read attacker-controlled data
before verifying anything: **it must know which algorithm to verify with.** That
is the classic JWS algorithm-confusion surface, and the mitigation is not to
avoid reading the header — it is to never let the header *decide*.

### 4.2 The header declares; local policy decides

```
1. Read the declared suite from the protected header's `suite` member.
2. Reject unless it is a member of the verifier's own acceptable set.
3. Verify using the parameters of the registry entry for that suite —
   never parameters taken from the header.
4. After verification, confirm the payload's signature.profile equals the
   header's `suite`, and signature.key_id equals the header's `key_id`.
   Either mismatch rejects, with `structurally_invalid`
   ([`core-model.md`](../../spec/core-model.md) §5.2.1). This is that
   document's §4 query step **5a**, and its response step 4a — the numbering
   here is this sequence's own.
```

**This procedure is the same for a response.** E-32 settled that §5.1–§5.3's
payloads carry the same two copies, and
[`core-model.md`](../../spec/core-model.md) §4 performs step 4 above at its
query step **5a** and its response step **4a** (E-35) — the producer this catches is no less able to lie to a requester
than to a responder, and the check had existed in one direction only.

Step 2 is the whole defence. A verifier that verifies with whatever the header
names has agility in the same sense that an unlocked door has a lock.

Step 4 looks redundant — both header and payload are signature-covered, so
neither can be altered without detection. It is not redundant. It catches a
**producer** that signs a payload declaring one suite using a header declaring
another, which is a real implementation bug and one that no verifier would
otherwise notice. The two declarations exist for different readers, and confirming
they agree costs one comparison.

**The key identifier is checked the same way and for the same reason.** A
producer that signs with one key while the header names another is the identical
bug, and it is worse in one respect: the verifier resolved and used the header's
key, so the signature verifies and nothing downstream is aware the signed object
disagrees about who signed it. Two comparisons, not one.

**`alg: none` is not a state a Q2D header can express.** The header has no `alg`
member ([`crypto-suites.md`](../../spec/crypto-suites.md) §3), so there is
nothing for `none` to be the value of — and a header carrying an unregistered
suite is rejected at step 2 by construction, since it is not in the acceptable
set. No special case is written for either, and no code path may exist that
treats absence of a suite as a valid state.

Not carrying `alg` is the point rather than an omission: a header a
general-purpose JOSE library can process is one where that library selects the
verification algorithm from attacker-controlled data, which is the decision step
2 exists to take away from the sender. The JWS compact *form* is the container
here, not JOSE's algorithm negotiation — and since RFC 7515 §4.1.1 requires
`alg`, a Q2D signed string is not a conformant JWS and JOSE tooling rejects it.
[`crypto-suites.md`](../../spec/crypto-suites.md) §3 states that outright, so
nobody discovers it from a library error.

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
| `suite/rfc8032/` | Raw Ed25519 against RFC 8032 §7.1 known-answer vectors. **Not authored as corpus vectors**, and this row is the record of why: a raw signature is not a Q2D operation, and [P-001](P-001-conformance-corpus.md) §4.5's vocabulary has no name for one. Adding a name is issue 17's, deliberately a single coordinated change. The known answers are a unit gate in both implementations instead, reading the same committed key material, and the cross-implementation half lives in `testdata/ed25519-acceptance.txt` where the other three-way fixtures are |
| `suite/sign/` | JWS compact construction, byte-exact, over P-002 payloads |
| `suite/verify/` | Valid, tampered payload, tampered header, tampered signature |
| `suite/downgrade/` | Below-floor suite, unregistered suite, a header carrying `alg`, header/payload suite mismatch, header/payload key mismatch |
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
| A header carrying `alg` at all, or any unregistered suite | The first is not a member the format has, so it is rejected as an unexpected member before step 2; the second is rejected *at* step 2. No special case in the code for either, and none may be added |
| A header whose `key_id` differs from the payload's `signature.key_id` | Rejected at step 4. The signature verifies — the verifier used the header's key — so nothing else would catch it |
| A suite below the verifier's floor | Rejected, with **no alternative named** in the response |
| Header suite ≠ payload `signature.profile` | Rejected after verification, on a query and on a response alike, with `structurally_invalid` |
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
| 1 | Ed25519 primitive wired to a vetted library, both languages | **Done.** [`src/ed25519.rs`](../../src/ed25519.rs) on `ed25519-dalek`, [`ed25519.go`](../../ed25519.go) on `crypto/ed25519` plus `filippo.io/edwards25519` — [E-47](../open-escalations.md), and `CONVENTIONS-{rust,go}.md` §2 carry the policy. **The acceptance rule is pinned, not inherited**, and that was not a formality: dalek's `verify_strict` and Go's `ed25519.Verify` disagree, and the case they disagree on is a *universal forgery* — `A = R =` the identity point with `S = 0` satisfies the verification equation for every message, with no private key, and the standard library accepts it. Go carries an explicit small-order check because of it, computed as `[8]P == identity` rather than looked up in a blacklist that would need its own completeness argument. The four rules are [`crypto-suites.md`](../../spec/crypto-suites.md) §3's — they were in the module headers first, and Codex was right that a third implementation reads `spec/` and would have picked its own edge cases. [`testdata/ed25519-acceptance.txt`](../../testdata/README.md) holds both implementations to the same answers on ten cases RFC 8032 does not decide. The RFC 8032 §7.1 gate reads its seeds from `conformance/keys/`, so it asserts the material the corpus signs with rather than a copy |
| 2 | Base64url without padding, both languages | **Done.** [`src/base64url.rs`](../../src/base64url.rs) and [`base64url.go`](../../base64url.go), hand-written — `base64.RawURLEncoding` accepts non-canonical trailing bits, which RFC 4648 §3.5 permits and a signature does not. Refuses padding, the standard alphabet, a one-character group, and a non-zero trailing bit. The last is the one that matters: the signature segment is an input to nothing, so a second spelling of the same 64 bytes verifies while the `signed` string differs — one exchange, two `request_digest` values. `suite/verify/respelled-signature-segment` is that case, and `tools/author_vectors.py` has a third implementation so the corpus is not derived from either |
| 3 | `registry/suites.json` format, file, and loader | **Done.** [`registry/suites.json`](../../registry/suites.json), read by [`src/suites.rs`](../../src/suites.rs) and [`suites.go`](../../suites.go) with **each implementation's own parser** rather than a JSON library: this file decides which algorithms a verifier accepts, so a registry with `status` twice is not a registry with one of them. Every field §2 lists is required — a registry missing `withdrawn_from` omitted the field that says when verification must stop, so a partial entry is refused rather than read for the parts that happen to be there. An unknown status fails the load rather than defaulting, because defaulting to `active` is how a withdrawn suite becomes usable. The **digest is checked before the bytes are parsed**, which is §4's ordering for a signature and for the same reason. The file is unsigned, exactly as `registry/manifest.json` is; that signature is P-005's |
| 4 | `SuitePolicy` construction from config | **Done.** [`src/policy.rs`](../../src/policy.rs) and [`policy.go`](../../policy.go). The property is carried by the type: the only constructor takes a registry and a list an operator wrote down, and nothing in either implementation produces such a list from a message. The floor is three things, and the third is the one review found missing: a suite must be **registered**, **implemented by this build**, and permitted to verify by its status. A registry is data and may name a suite whose algorithm this code cannot execute — accepting one would sign Ed25519 under another suite's identifier, breaking the coupling `crypto-suites.md` §1 makes an identifier carry. **The check is on the identifier and not on the entry's `algorithm`, `serialization` and `hash`**, and review pressed on that three times, so the boundary is written down in both modules: those fields are prose for a human reader, nothing selects a code path from them, §2 makes a registered identifier permanent and never reused for different parameters, and an entry claiming one identifier with other parameters is a registry wrong about itself — which the pinned digest catches and a comparison of free text would only appear to. Configuration may raise the floor and never lower it, and lowering it **fails startup** rather than being clamped or dropped — a clamped misconfiguration reads as success, and the operator's belief that they configured something survives until the day it matters. The default is the MTI suite alone, so adding a suite to the registry does not change what an unconfigured deployment accepts |
| 5 | `sign` — compact JWS construction | **Done.** [`src/jws.rs`](../../src/jws.rs) and [`jws.go`](../../jws.go). The header goes through the same serializer as everything else, so `key_id` precedes `suite` by `serialization.md` §1's ordering rather than by the order the code writes them — writing that JSON by hand would put a second serializer in each implementation whose output has to match the first one's. **`sign` takes the registry entry, not a suite identifier**, and the entry's fields are private so that resolving it is the only way to obtain one — an entry a caller could *build* would make the status check a restatement rather than an enforcement, which is what Codex caught. The honest limit is P-002 §8's, for the same reason `Routing` has it: code inside the crate can still construct one, and what the type removes is the accident rather than the determined bypass. Byte agreement is asserted through [`testdata/canonical-query.signed`](../../testdata/README.md), which a Python test ties to `message/sign/query-minimal`'s expected output: neither implementation can read a corpus vector with its own parser, because seven vectors carry a string past §2.8's limits — they exist to *test* those limits |
| 6 | `verify` — the four-step sequence in §4.2 | **Blocked on [E-46](../open-escalations.md)**, and the cryptographic half is built beneath it. `verify_compact` splits the compact string, checks all three segments are base64url, and verifies the signature over the received text of the first two — it is **crate-internal in Rust and unexported in Go**, deliberately: it does not read the suite, consult the policy, compare header against payload, or check the header is §3's closed two-member object, so a public function returning *verified payload bytes* from a string whose header was never inspected would invite a caller to treat those bytes as a Q2D message. They are bytes with a good signature over them, which is weaker. It becomes public when this row is done |
| 7 | Header/payload suite agreement check | **Done**, as step 5a of issue 6's sequence. The test that proves it signs the payload with the key the **header** names — so the signature verifies and nothing else would catch the disagreement, which is the whole reason the check exists. Two comparisons, not one: the suite and the key |
| 8 | Status enforcement, both directions | **The producing half is done**, and it is enforced where it cannot be forgotten: `sign` takes a `SuiteEntry` and refuses unless its status permits production, so there is no path that signs under a deprecated or withdrawn suite by naming it. The **verifying** half is `policy`'s floor, which already refuses a withdrawn suite at startup rather than at verification. What remains is `suite/status/`, which needs `verify_query` vectors and therefore issue 6 |
| 9 | `resolve_key` interface plus a test-fixture implementation | **Done.** [`src/keys.rs`](../../src/keys.rs) and [`keys.go`](../../keys.go). Both invariants are carried by the signature rather than by a comment: it returns a key or an error, so there is no third case to be lenient about; and it returns the **same error value** a bad signature does, so there is no second value to accidentally map onto a second wire response. A key the suite would refuse never enters the set, so it cannot resolve and then fail verification — one refusal, at the boundary, rather than two chances to get it right |
| 10 | Test key material, RFC 8032-seeded | **Done before this PRD opened**, by [P-001](P-001-conformance-corpus.md) issue 10: `conformance/keys/ed25519-test-only.json`, three keypairs with RFC 8032 §7.1's known answers beside them. Issue 1's gate now reads from it rather than repeating the seeds, which a containment test in `test_keys.py` requires — it asserts no seed appears anywhere else in the repository, and it caught the first version of both `ed25519` modules doing the obvious thing |
| 11 | Author `suite/` corpus section | **Five of six groups present**, and `suite/rfc8032/` is not one of them for the reason §6 records: a raw Ed25519 signature is not a Q2D operation. `suite/verify/` gained `not-three-segments` and `header-not-base64url` under [E-46](../open-escalations.md). **`suite/status/` is what remains, and it needs something the vector format does not have**: a way for a vector to state the *verifier's* registry state, since a deprecated or withdrawn suite is a fact about the verifier rather than about the message. That is a [P-001](P-001-conformance-corpus.md) format question, not a P-003 one |
| 12 | Header-parameter attack vector | **Done, and there is no code for it** — which is the result this row wanted. §3's member set is closed, so `alg: none`, `alg: HS256`, `crit` and `b64` are refused by the *set* before the suite is looked up, with no rule naming any of them and none permitted to be added. The test asserts the signature over those bytes is valid and the message is refused anyway |
| 13 | Suite value exposed for receipt construction | **Done, and it is one accessor.** `SuiteEntry::id()` is the value a receipt records, and `sign` already takes the entry — so a responder that signed a response holds the identifier without reaching into this module for it. P-011 cannot confirm the seam until it is built, which is why this row says what the seam *is* rather than that a consumer is using it |

Issue 1 blocks everything. Issue 3 blocks 4, 6, and 8, and now includes signing
`registry/suites.json` and pinning its digest.
