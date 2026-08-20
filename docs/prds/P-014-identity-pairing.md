# P-014 — Identity and the local pairing profile

| Field | Detail |
|---|---|
| PRD | P-014 |
| Stage | 6 — closes it |
| Status | **Deferred 2026-08-19** — see the note below |
| Size | M |
| Risk | **high** — the key-to-principal binding is Q2D-C-06's trusted base, and in this profile a human establishes it by comparing a string |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-003](P-003-crypto-suites.md), [P-009](P-009-denial-normalization.md) |
| Blocks | P-013, P-016 |
| Pairs with | [P-013](P-013-https-binding.md) — the daemon cannot authenticate anyone without this, and this PRD owns no transport |


> **Deferred 2026-08-19 — not withdrawn.**
>
> Identity is a **configured key list**, exactly as `SuitePolicy` and
> `RegistryPins` already are — an operator enters keys by hand, and
> [P-003](P-003-crypto-suites.md)'s `resolve_key` interface (already built)
> resolves from it. [P-017](P-017-mcp-binding.md) §4.7 carries that, and the
> key-file permission enforcement from issue 8 with it.
>
> MCP moved toward standard OAuth / Client ID Metadata Documents; a bespoke pairing
> profile is a worse answer to a problem the ecosystem has solved.
>
> **Delegation becomes a no-op**, and [P-017](P-017-mcp-binding.md)'s quickstart
> says so rather than letting a reader assume
> [`core-model.md`](../../spec/core-model.md) §4 step 7 ran.
>
> **What would bring it back:** a deployment needing principal/agent separation, or
> a Q2D-C-06 claim that rests on more than an operator's own key list. §4.9's
> claim-language rules apply meanwhile — nothing may call a configured key list an
> identity model.
>
> Full reasoning: `private-docs/scope-reduction-proposal.md`. **Everything below
> is preserved as written**, and describes the scope that was planned.

---

## 1. Purpose

Supply the smallest identity technology that makes the exchange real: two
parties establish a mutual key binding out of band, pin it, and use it for
every subsequent exchange.

[P-003](P-003-crypto-suites.md) §4.6 defined `resolve_key` and deliberately
stopped there — *"where the key comes from, how it was established, how it
rotates, and whether a delegation chain authorizes it are P-014's concerns."*
This is that PRD.

**Claims served.** None added. Q2D-C-06 **rests** on this module:
[`claims.md`](../../spec/claims.md) makes it hold only when *"the
key-to-principal binding is sound under the selected identity profile"*, and
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §2 marks identity and
key infrastructure **Trusted** for it. Q2D-C-05 and Q2D-C-07 depend on the same
binding through key custody. Nothing here strengthens a claim; everything here
is what those claims already assume.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §2.3 | Principals, `requester.delegation`, and the three interfaces — named, not defined (§4.1) |
| [`spec/core-model.md`](../../spec/core-model.md) §2.7 | `signature.key_id` is resolvable under the identity profile |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 7 | Delegation verification, after signature and before anything it gates |
| [`spec/core-model.md`](../../spec/core-model.md) §9 | The core-vs-profile boundary is parked; a choice must not be described as the Q2D answer |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-06 | Holds only when the key-to-principal binding is sound; fails when the profile misbinds |
| [`spec/scope.md`](../../spec/scope.md) §2 | Capability 1 of a participating custodian: authenticate a principal, verify delegation to an agent |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §8 | Rotation and revocation are parked *per identity profile* — this is that profile |
| [`spec/terminology.md`](../../spec/terminology.md) §2 | Principal, agent, and runtime are three roles; the distinction is load-bearing |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-1, CC-2 | Resolve principal and delegated agent identity; authenticate and verify delegation |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §2, §3 | Identity infrastructure is Trusted for Q2D-C-06; the binding is its named failure point |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §4 | "Compromised requester or executor key — defeats C-05 or C-06 **until revocation**" (§4.5) |

## 3. Module boundary

**Inside:** the pairing ceremony and its store; the fingerprint and its
encoding; `resolve_key`'s implementation; principal identification; delegation
evidence and its verification; rotation and unpairing; private-key storage and
permission enforcement.

**Explicitly outside:** signature verification and suite policy
(**P-003**) — this module supplies keys and never decides whether a signature is
good. Denial classification (**P-009**), which already places every identity
failure in Tier B. Transport, endpoints, and pairing over the network
(**P-013**) — the pairing channel is deliberately not a Q2D endpoint (§4.2).
Policy authorities (**P-007**); being paired is not being authorized, and this
module grants nothing.

**Also outside:** enterprise OIDC/OAuth and DID/UCAN. Both are named in
[`core-model.md`](../../spec/core-model.md) §2.3 as profiles over the same
interfaces, and neither is in MVP. Building this one must not shape the
interfaces around it — see §4.1.

## 4. Design

### 4.1 Three interfaces the specification names and does not define

[`core-model.md`](../../spec/core-model.md) §2.3 says Q2D defines *"principal
identification, key resolution, and delegation verification"* rather than one
identity technology, and §9 records the leaning that **core defines the three
interfaces and profiles supply the technology.**

The interfaces are named in that one sentence and specified nowhere. Only
`resolve_key` has a shape, and it has one because
[P-003](P-003-crypto-suites.md) §4.6 needed it to verify a signature — it was
defined as a dependency, not as identity surface.

So this PRD cannot proceed cleanly. Writing the other two interfaces here would
put the core-vs-profile boundary in a PRD, which is exactly the failure
[`mvp-scope.md`](../mvp-scope.md) §3 names: a second source of truth that drifts,
and the mechanism by which a second profile later diverges while both pass their
own documents. The risk is concrete rather than theoretical — a delegation
interface shaped around local pairing will not fit OIDC, and the shape would be
discovered wrong only when someone builds the second profile.

**Recommended: add the three interface signatures to
[`core-model.md`](../../spec/core-model.md) §2.3, technology-free**, and leave
§9's separate question — which profile, if any, is mandatory to implement —
parked. §5 below carries a proposed shape, marked provisional, as input to that
decision rather than as a resolution of it.

Until it is decided, this module implements local pairing and **describes it as
one profile over those interfaces, never as the Q2D identity model**.
[`core-model.md`](../../spec/core-model.md) §9 is explicit: an implementation
may choose any parked item, and must not describe its choice as the answer until
the specification records it.

### 4.2 What local pairing is

Two parties exchange public keys through a channel Q2D does not define, confirm
the exchange out of band, and store the binding locally. Every later exchange
resolves against that store.

The store is the entire trust anchor. There is **no directory, no discovery, no
fetch, and no network path of any kind in this module** — the same posture as
[P-005](P-005-registry-client.md) §4.3 takes with the manifest, and for the same
reason: a channel that can supply an identity can substitute one.

**The pairing channel is deliberately not a Q2D endpoint.** A `POST /pair` would
make first contact with an unknown party a protocol operation, and the party you
are trying to authenticate is precisely the one who cannot be trusted to conduct
it. Pairing happens by whatever means two humans already trust — a file copied
by hand, a QR code, a value read aloud — and Q2D's job starts once it is done.

A binding records: principal identifier, public key, when it was established,
and **how it was confirmed** (§4.3).

### 4.3 The fingerprint, and the human step everything rests on

`fingerprint(key)` produces a short string a person can read to another person.

Encoding rules, because two implementations that print different fingerprints
for one key make the ceremony worthless:

| Rule | Value |
|---|---|
| Input | `"q2d-pairing-fingerprint-v1:"` as ASCII bytes, immediately followed by the raw 32-byte Ed25519 public key. No separator, no encoding of the key before hashing |
| Hash | SHA-256 over those exact 59 bytes |
| Truncation | The first 16 bytes of the digest |
| Encoding | Lowercase hex, grouped in fours by a single `-` for reading |
| Locale, normalization, case folding | None — the output is ASCII by construction |

The prefix is written out because "a domain-separation prefix" is not a
specification. Two implementations agreeing on SHA-256 and disagreeing on what
they hash produce different fingerprints for the same key, and the corpus would
catch it only for the keys someone thought to pin. The version suffix means a
future change is a new prefix rather than a silent reinterpretation of an
existing ceremony.

The grouping is presentation; the comparison is over the ungrouped string, so a
display change can never alter what verifies. A corpus vector pins the exact
output for known keys.

**Now the honest part.** A binding confirmed by comparing fingerprints out of
band is authenticated. A binding accepted without that comparison is
**trust-on-first-use**, and an attacker present at pairing time is bound as the
peer with nothing to detect it later. [`claims.md`](../../spec/claims.md)
Q2D-C-06 fails exactly there — *"the identity profile misbinds a key to a
claimed principal"*.

Three consequences:

- The store records the confirmation mode per binding, because it determines
  what may be said about that peer.
- **The daemon refuses unconfirmed bindings by default.** A deployment may
  enable trust-on-first-use deliberately; it is not what happens when nobody
  chooses.
- No artifact — quickstart, operator docs, comments — may describe an
  unconfirmed pairing as authenticated. The quickstart's fingerprint-comparison
  step is not a formality to be streamlined; in MVP it is the step on which
  Q2D-C-06 rests.

That is the profile's real security posture, and it should be stated plainly
rather than implied: **the strongest authentication claim in the MVP is only as
good as one human comparing one string.**

### 4.4 Delegation evidence

[`core-model.md`](../../spec/core-model.md) §2.3 makes `requester.delegation`
profile-dependent — *"evidence or reference proving the agent acts for the
principal"*. Its shape is therefore this profile's to define; its verification
interface is not (§4.1).

Under local pairing, delegation evidence is a statement signed by the
**principal's** key naming the **agent's** key, with a validity window:

```
principal, agent_key, not_before, not_after, signature(principal_key)
```

Nothing more. No scope, no predicate list, no purpose restriction — a delegation
that narrowed which predicates an agent may ask about would be a policy
mechanism arriving through the identity layer, unreachable by
[P-007](P-007-policy-engine.md) and invisible to the audit event that records
why a decision was made. Policy is one component's job.

Verification at [`core-model.md`](../../spec/core-model.md) §4 step 7: the
principal is paired, the evidence verifies under the principal's pinned key, the
window covers the request's `issued_at`, and the agent key is the one that
signed the query. All four, and any failure is Tier B (§4.7).

**Principal and agent are always two roles, even on one device.**
[`terminology.md`](../../spec/terminology.md) §2 calls the distinction
load-bearing, and a deployment where they collapse still produces a delegation
object — self-issued, but present and checked. Making the collapsed case skip
the check would leave the path untested in exactly the deployment MVP
demonstrates, and an untested path is one that does not work.

### 4.5 Rotation is re-pairing, and revocation does not propagate

This resolves [P-003](P-003-crypto-suites.md) open question 3 and, for this
profile, [`crypto-suites.md`](../../spec/crypto-suites.md) §8's parked item.

**Rotation is re-pairing.** A new key means a new out-of-band confirmation. There
is no signed key-rollover statement chaining a new key to an old one: it would
let anyone holding the current private key silently move the binding, which is
the one operation the ceremony exists to require a human for.

**Unpairing is local and immediate**, and it is the only revocation mechanism.

The consequence is the limitation to state everywhere it matters:

> A compromised requester key remains valid at every custodian that has not been
> told, by hand. There is no revocation list, no status endpoint, and no
> propagation. Revocation is per-deployment and manual.

[`trust-matrix.md`](../../threat-model/trust-matrix.md) §4 previously said a
compromised key defeats Q2D-C-05 or Q2D-C-06 *"until revocation"* and stopped
there, which read as though revocation were a mechanism with reach. Under this
profile it is a person editing a file on each machine. **§4 now says so**, and
adds that the exposure is bounded by who gets told rather than by a window that
closes — scoped to this profile, so a later one with real revocation
infrastructure is not retroactively described as having none. Open question 3,
resolved.

### 4.6 Private key storage

File-based, with the daemon refusing to start when permissions are loose — one
more row for [P-013](P-013-https-binding.md) §4.6's startup list.

No passphrase in MVP. A passphrase means an interactive prompt, and a daemon
that cannot start unattended fails the two-machine walkthrough for reasons
unrelated to the protocol. The trade is stated rather than hidden: **key
confidentiality rests on filesystem permissions**, and an OS keychain is a swap
behind the same interface rather than a redesign.

Test key material is the committed, test-only material from
[P-003](P-003-crypto-suites.md) §4.7. No fixture generates a key at runtime —
[P-001](P-001-conformance-corpus.md) §4.3.

### 4.7 Every identity failure is Tier B

[P-009](P-009-denial-normalization.md) §4.1 places unresolvable key, invalid
signature, and invalid or expired delegation in one externally uniform class,
because distinguishing them tells a requester whether its key is known to this
custodian — which is relationship existence.

This module adds failure modes to that tier and must not add a distinction:
unknown principal, unpaired peer, unconfirmed binding refused by policy,
delegation absent, delegation expired, delegation naming a different agent. All
of them, plus P-003's two, produce one wire response.

The internal audit event records which, because
[P-011](P-011-receipts-audit.md) §4.3 keeps that local. The wire does not.

### 4.8 What this profile is not

- **Not an identity provider.** It binds keys to identifiers a deployment
  chose. It does not establish who anyone is in the world.
- **Not authorization.** A paired peer is authenticated and nothing more; every
  release decision is [P-007](P-007-policy-engine.md)'s.
- **Not the Q2D identity model.** One profile, over interfaces
  [`core-model.md`](../../spec/core-model.md) §9 has not finished defining.
- **Not scalable, and not meant to be.** *n* peers means *n* ceremonies. That
  cost is why enterprise and DID profiles exist, and naming it here keeps anyone
  from reading local pairing as a general answer.

## 5. Interfaces

**Settled.** [`core-model.md`](../../spec/core-model.md) §2.3 now defines all
three, technology-free, taking these signatures as its input. This section
implements them; it no longer proposes them. The reasoning under
`identify_principal` and `verify_delegation` below moved into the specification
with the signatures, because it is the part a second profile must not
reinterpret.

```
// the three interfaces — core-model.md §2.3, technology-free
resolve_key(key_id: KeyId)            -> Result<PublicKey>        // P-003 §5
identify_principal(key_id: KeyId)     -> Result<PrincipalId>
verify_delegation(principal: PrincipalId, agent: KeyId,
                  evidence: Delegation, at: Timestamp) -> Result<()>

// local pairing technology
pair(peer: PrincipalId, key: PublicKey, confirmation: Confirmed | TrustOnFirstUse)
                                      -> Result<Binding>
fingerprint(key: PublicKey)           -> FingerprintString
unpair(peer: PrincipalId)             -> Result
load_own_key(path, policy: KeyFilePolicy) -> Result<PrivateKey>   // permission-checked
```

`identify_principal` is separate from `resolve_key` because they answer
different questions — *what key is this?* and *whose is it?* — and collapsing
them into one lookup returning both is how a caller ends up trusting a principal
it never checked was paired.

`verify_delegation` returns unit rather than a value. There is nothing a caller
should learn from a successful delegation check beyond that it passed;
returning the evidence invites something downstream to read a field out of it
and treat identity as policy input.

`Confirmation` is an explicit parameter with no default. A pairing call cannot
be written without stating whether a human checked.

## 6. Corpus sections

`identity/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `identity/fingerprint/` | Byte-identical output for the committed test keys; grouping does not affect comparison |
| `identity/pairing/` | Establish, resolve, unpair; unknown principal; unpaired peer |
| `identity/confirmation/` | Unconfirmed binding refused by default; accepted when TOFU is explicitly enabled |
| `identity/delegation/` | Valid; expired; not-yet-valid; wrong agent key; absent; self-issued for the collapsed-role case |
| `identity/rotation/` | Re-pairing replaces the binding; the old key stops resolving; no rollover statement is accepted |
| `identity/uniformity/` | Every §4.7 failure produces one byte-identical wire response |
| `identity/storage/` | Loose permissions refuse to load; no key is generated at runtime |

`identity/uniformity/` runs under [P-001](P-001-conformance-corpus.md) §4.8's
cross-vector denial-uniformity assertion, extended to Tier B by
[P-009](P-009-denial-normalization.md) §6.

## 7. Acceptance

- [ ] Both implementations produce **byte-identical** fingerprints for every
      committed test key.
- [ ] Both resolve, identify, and verify delegation identically for every
      `identity/` vector.
- [ ] An unconfirmed binding is refused unless trust-on-first-use is explicitly
      enabled, in both.
- [ ] Every §4.7 failure produces one byte-identical wire response — asserted
      across causes by the cross-vector check, not per case.
- [ ] Delegation is verified even when principal and agent collapse to one
      device; no code path skips it.
- [ ] Re-pairing replaces a binding and the previous key stops resolving; no
      signed rollover is accepted from any input.
- [ ] A key file with loose permissions refuses to load, and the daemon refuses
      to start.
- [ ] No network client is linked into this module — asserted by dependency
      check, as in [P-005](P-005-registry-client.md) §8.
- [ ] The [`mvp-scope.md`](../mvp-scope.md) §1 pairing step completes on two
      machines from the quickstart alone.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| Two implementations printing different fingerprints for one key | `identity/fingerprint/` cross-implementation comparison |
| An unconfirmed binding accepted silently | `identity/confirmation/` default vector pairs |
| "Unknown principal" distinguishable from "bad signature" | Cross-vector Tier B uniformity fails |
| Any two §4.7 causes distinguishable | Same |
| Delegation skipped when principal and agent are one device | Collapsed-role vector passes without evidence |
| A delegation carrying scope, predicates, or purpose honoured | Policy arriving through the identity layer, invisible to [P-007](P-007-policy-engine.md) |
| A signed key-rollover statement accepted | `identity/rotation/` rollover vector rebinds without a ceremony |
| A key resolved from anywhere but the local store | Any fetch, fallback, or "last known good" path exists |
| A pairing endpoint on the daemon | Present at all — §4.2 |
| A private key generated or written at runtime by a fixture | Two runs of a vector differ |
| A key file loaded despite loose permissions | `identity/storage/` vector loads |
| Text describing unconfirmed pairing as authenticated | Grep across quickstart, operator docs, comments |
| Text describing local pairing as the Q2D identity model | Grep; [`core-model.md`](../../spec/core-model.md) §9 forbids it |

Row 2 is the one that will actually happen. Refusing unconfirmed bindings makes
the quickstart longer and the demo slower, and the pressure to default it the
other way will be real every time someone runs the walkthrough. It is also the
row that decides whether Q2D-C-06 holds in the deployment being demonstrated.

Row 6 looks like a feature request rather than a defect, which is why it is
listed. A scoped delegation is a plausible-sounding addition that moves an
authorization decision somewhere it cannot be audited.

## 9. Escalate-if-changed decisions

1. **The pairing store is the only source of keys.** No directory, no discovery,
   no fetch, no fallback.
2. **Pairing is not a Q2D endpoint.**
3. **The confirmation mode is recorded per binding, and unconfirmed bindings are
   refused by default.**
4. **Fingerprint encoding is fixed.** Changing it invalidates every ceremony
   already performed and every corpus vector.
5. **Delegation evidence carries no scope.** Identity does not do policy.
6. **Delegation is verified even when the roles collapse.**
7. **Rotation is re-pairing; no signed rollover exists.**
8. **Every identity failure is Tier B and internally uniform.**
9. **Local pairing is one profile, never described as the Q2D identity model**,
   until [`core-model.md`](../../spec/core-model.md) §9 says otherwise.

## 10. Open questions

| Question | Belongs to |
|---|---|
| **1.** ~~[`core-model.md`](../../spec/core-model.md) §2.3 names three interfaces and defines only one~~ | **Resolved: all three are now defined in §2.3**, technology-free, with §5 as input. The two properties that carry security meaning moved into the spec with them — `identify_principal` separate from `resolve_key`, and `verify_delegation` returning success rather than the evidence. §9's mandatory-profile question stays parked, and §2.3 says so explicitly so the definition is not read as answering it |
| **2.** ~~Should a conformance class exist for an identity profile?~~ | **Resolved: not yet**, while [P-013](P-013-https-binding.md) open question 2 was resolved the other way. The distinction, stated here so the pair does not read as an oversight: **a conformance class can be written for a boundary that is settled.** P-013's binding has a complete must / must-not list today (its §4.1–4.5, now CC-12). An identity class would have to state which profile an implementation conforms to, and *which profile, if any, is mandatory* is exactly what [`core-model.md`](../../spec/core-model.md) §9 still parks. Revisit when a second profile exists |
| **3.** ~~[`trust-matrix.md`](../../threat-model/trust-matrix.md) §4 says a compromised key defeats a claim "until revocation"~~ | **Resolved: amended.** §4 now states that under this profile revocation is per-deployment and manual, with no propagation, and that the exposure is bounded by who gets told rather than by a window that closes. §4.5's wording was lifted into the threat model, which is where a reader doing adversary analysis actually looks |
| **4.** ~~What is a `PrincipalId` — an opaque string, a URI, a key digest?~~ | **Resolved: an opaque, deployment-chosen string**, compared only for equality. Not a URI and not a key digest. Anything with structure invites something downstream parsing it for authorization — a domain suffix, a namespace prefix — which turns identity into policy input and does it in a field no signature covers the *meaning* of. A key digest is worse still: it would make the principal change on rotation, and §4.5 makes rotation a routine re-pairing |
| **5.** ~~Does the requester delegate to itself in MVP?~~ | **Resolved: a self-issued delegation**, with `requester.agent` a distinct key from the principal. Collapsing the two — or allowing an empty delegation when they are equal — would leave `verify_delegation` unexercised on every MVP path, so the first real deployment would be the first test of it. Two keys and a signed delegation cost a fixture and keep the check on the critical path (§4.4) |
| **6.** ~~Passphrase or OS keychain for private keys?~~ | **Resolved: neither — file permissions**, enforced at startup (§4.6). A passphrase means an interactive prompt, and a daemon that cannot start unattended is one an operator will work around by storing the passphrase beside the key. A keychain is platform-specific and would put a third OS integration in a Stage 6 deliverable. `load_own_key` takes a `KeyFilePolicy`, so a keychain implementation is a substitution rather than a redesign. **The limitation is stated in the operational-security notes** rather than implied |
| **7.** ~~Does pairing need an expiry?~~ | **Resolved: no in MVP.** A lapsed pairing fails closed as a Tier B rejection, which is indistinguishable from a compromised or rotated key — so the expiry would generate exactly the alarm it was meant to make meaningful, on a schedule, until operators stopped reading it. Re-pairing is already required on rotation (§4.5), which is the event that matters. Revisit at Stage 8 if operating experience shows stale bindings accumulating |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | ~~Escalate open questions 1, 2, and 3~~ — **done** | Resolved; `core-model.md` §2.3 defines the three interfaces, `trust-matrix.md` §4 amended, identity conformance class deferred with the reason recorded; §4.5 and §5 cite the outcome |
| 2 | `fingerprint` with the §4.3 encoding | `identity/fingerprint/` byte-matches across implementations |
| 3 | Pairing store, `pair`, `unpair`, `identify_principal` | `identity/pairing/` passes; open question 4 resolved first. `identify_principal` is a **separate** lookup from `resolve_key` ([`core-model.md`](../../spec/core-model.md) §2.3) — no combined call returning both may exist |
| 4 | `verify_delegation` and the delegation object | `identity/delegation/` passes; the function returns success or failure and **never** the evidence (§2.3) |
| 5 | Confirmation mode, recorded and enforced | `identity/confirmation/` passes; unconfirmed refused by default |
| 6 | `resolve_key` over the pairing store | [P-003](P-003-crypto-suites.md)'s interface satisfied; no fallback path exists |
| 7 | Rotation and the no-rollover rule | `identity/rotation/` passes; rollover statements rejected |
| 8 | `load_own_key` with permission enforcement | `identity/storage/` passes; daemon startup row added to [P-013](P-013-https-binding.md) §4.6 |
| 9 | Tier B uniformity across every §4.7 cause | `identity/uniformity/` passes under the cross-vector check |
| 10 | Dependency assertion: no network client | CI check fails if one is linked |
| 11 | Author `identity/` corpus section | Seven groups; `harness lint` clean |
| 12 | Pairing ceremony in the quickstart, with the comparison step | An outsider completes it; the step is not described as optional |
| 13 | Claim-language audit | Nothing calls unconfirmed pairing authenticated, or this profile the Q2D identity model |

Issue 2 is independent and can start immediately; the fingerprint encoding is
settled and everything else waits on it being stable. Issues 3 and 4 are now
unblocked — [`core-model.md`](../../spec/core-model.md) §2.3 fixes the interface
shapes, so this module implements rather than proposes them.
