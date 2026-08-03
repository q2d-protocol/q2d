# Q2D Cryptographic Suites — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

Q2D does not specify a signature algorithm. It specifies a **suite registry** and
the rules for using it, so that algorithms can be added, deprecated, and
withdrawn without a protocol revision. This follows the algorithm-agility
guidance in BCP 201 (RFC 7696).

Terms: [`terminology.md`](terminology.md). Exchange:
[`core-model.md`](core-model.md). Properties: [`claims.md`](claims.md).

---

## 1. What a suite is

A **signature suite** names three coupled choices as one unit:

1. the **signature algorithm** and its parameters;
2. the **serialization method** — how the signed bytes are produced from the
   core object;
3. the **hash** where the algorithm does not fix one.

They are one identifier because they fail together. The same algorithm over a
different serialization is a different security object, and treating them
separately is how signature-substitution bugs happen.

Identifier form: `<algorithm>-<serialization>-<year>`, lowercase, stable
forever. A registered identifier is never reused for different parameters.

## 2. Registry entry

| Field | Meaning |
|---|---|
| `id` | The suite identifier. |
| `algorithm` | Signature algorithm and parameters. |
| `serialization` | How signed bytes are derived from the core object. |
| `hash` | Where not fixed by the algorithm. |
| `status` | `active`, `deprecated`, or `withdrawn`. |
| `effective_from` | When it became usable. |
| `deprecated_from` | When new signatures should stop using it. |
| `withdrawn_from` | When verification must stop accepting it. |
| `security_notes` | Known weaknesses, size characteristics, constraints. |
| `references` | Defining specifications. |

This is deliberately the same shape as the predicate registry: versioned,
signed, pinned by the verifier, with revocation. Suites are distributed by the
same mechanism and pinned the same way.

## 3. Registered suites — version 0.1

### `eddsa-jws-2026` — mandatory to implement

Ed25519 (RFC 8032) over **JWS compact serialization** with the core object as an
opaque base64url payload. The signature covers the exact transmitted bytes.
**No canonicalization is involved**, and none is required.

This is the default and the only suite an implementation must support to claim
[`conformance-classes.md`](conformance-classes.md) CC-1 or CC-2.

Signature size: 64 bytes. Public key: 32 bytes.

This is the only suite registered in 0.1.

### Why no canonicalization suite

A canonicalization-based suite — Ed25519 over JCS (RFC 8785), for instance — was
considered and **deliberately not registered**.

Canonicalization re-derives signed bytes from a *parsed* value, which makes
correctness depend on signer and verifier agreeing about parsing as well as
serialization. That dependency carries known hazards: JCS inherits ECMAScript
number semantics, so integers above 2^53 do not round-trip safely, and JSON
permits duplicate keys, which parsers handle inconsistently. Both become
security-relevant when a signature's validity rests on them.

Signing exact transmitted bytes removes the dependency entirely, and lets a
verifier check a signature *before* parsing the object it covers — so the JSON
parser sits outside the security boundary rather than inside it. It also removes
the most common source of cross-implementation failure, which matters for a
protocol targeting a Rust and a Go implementation validated against shared test
vectors.

A future binding whose transport cannot carry an opaque payload would need a
canonicalization suite. None does today. If one appears, it is registered here
with its hazards documented — not assumed.

## 4. Downgrade resistance

Three rules. Each is a `must`.

**The suite identifier is inside the signed material.** It is a field of the
signed core object, not of the outer envelope. An intermediary that rewrites the
outer envelope cannot change which suite a verifier believes was used.

**The verifier holds a minimum acceptable policy.** Accepting whatever suite the
sender selected is not agility; it is a downgrade oracle. A verifier maintains
its own set of acceptable suites and rejects anything outside it, including
suites that are registered and `active` but below its local floor.

**Rejection is not negotiation.** A responder that will not accept a suite
returns a failure. It does not suggest an alternative in the response, because
that is a probe-able oracle for what a deployment accepts. Supported suites are
advertised through capability discovery, where advertising them is a deliberate
choice.

## 5. Receipts record the suite

The receipt records the suite used for the response signature.

A receipt may be presented as audit evidence years after the exchange. A
verifier at that point needs to know which suite was used and can then judge
whether it has since been deprecated or withdrawn. A receipt whose suite has
been withdrawn is not thereby void — it is evidence whose strength a verifier
must assess, which is only possible if the suite is recorded.

## 6. Deprecation

- `deprecated` — implementations should stop producing new signatures under it.
  Verification continues.
- `withdrawn` — verification must stop accepting it for new exchanges.

Neither status retroactively invalidates a receipt. The distinction between "was
valid when produced" and "would be accepted now" is preserved deliberately.

Because the suite registry is pinned like the predicate registry, a custodian
that never accepts an unpinned registry digest cannot be forced onto a weakened
suite by an attacker who compromises registry distribution — the failure mode is
availability, not disclosure.

## 7. Post-quantum posture

Q2D 0.1 registers no post-quantum suite. The registry can carry one without a
protocol change, which is the point of this document.

The urgency differs sharply between the two uses, and conflating them leads to
the wrong priority.

**Payload encryption is the pressing case.** Where a store-and-forward relay
carries HPKE-protected payloads, harvest-now-decrypt-later is a real threat: an
observer stores ciphertext today and decrypts it once a cryptographically
relevant quantum computer exists. If a relayed payload carries an answer and
receipt that stay sensitive for years, that exposure is already accruing. A
**hybrid KEM** is therefore the higher-priority post-quantum move.

**Signatures are far less pressing.** A signature needs to be unforgeable at
verification time. Forging a 2026 query in 2035 achieves nothing; the exchange
is over. The exception is a **long-lived receipt** relied on as audit evidence,
where an algorithm break degrades evidentiary strength. That is better addressed
by timestamping and batch-root anchoring than by adopting post-quantum
signatures now.

There is also a cost specific to Q2D. Standardized post-quantum signatures are
kilobytes where Ed25519 is 64 bytes. A protocol whose case rests on releasing a
bounded answer rather than a record should not casually attach a multi-kilobyte
signature to a one-bit result. Any post-quantum suite must be evaluated with
that measured, and the evaluation must report semantic answer size separately
from total wire bytes.

### Reserved shapes

Named so the registry structure accommodates them. **Neither is specified here,
and neither is registered.**

- **Hybrid signature suite** — a classical and a post-quantum signature, both
  required to verify, so the suite is no weaker than the stronger component.
- **Hybrid KEM** — a classical and a post-quantum key encapsulation combined,
  for payload protection through untrusted relays.

### What Q2D claims about this

> Q2D is **algorithm-agile**, with a suite registry that can carry
> post-quantum or hybrid suites.

Q2D does **not** claim to be post-quantum ready, post-quantum secure, or
quantum-resistant. No registered 0.1 suite offers any post-quantum property.
Adding such a claim requires a registered suite, an implementation, and review —
see [`claims.md`](claims.md) and the claim-language rules in
[`terminology.md`](terminology.md) §9.

## 8. Parked

| Open item | Blocked on |
|---|---|
| Whether any suite beyond the MTI is mandatory for a binding | Binding implementation experience |
| Payload-encryption suites for HPKE through relays | The relay profile, which 0.1 does not specify |
| Key rotation and revocation semantics per identity profile | The identity/delegation profile boundary |
| Whether hybrid signatures are required before any long-lived-receipt profile | Anchoring design |
