# Q2D Conformance Classes — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

What an implementation must do to claim a class, and — more importantly — what
it may not claim if it does not implement one.

Classes exist so that a developer can build the useful Phase 1 protocol without
pretending to support zero knowledge or trusted execution, and so that a reader
of a conformance claim knows exactly what was tested.

Terms: [`terminology.md`](terminology.md). Properties: [`claims.md`](claims.md).
Exchange: [`core-model.md`](core-model.md).

---

## The honesty rule

> An implementation claims a class only when every check for that class passes.
> A class is not implied by another class unless this document says so.

**No conformance suite exists yet.** Until it does, no implementation can claim
any class. An implementation may state that it *targets* a class. The
distinction is not pedantic: the entire value of a conformance claim is that it
was tested.

There is no certification program and no conformance mark. See
[`../TRADEMARKS.md`](../TRADEMARKS.md).

---

## Core classes

### CC-1 — Core requester

**Must.** Construct well-formed answer contracts; resolve principal and
delegated agent identity through the interfaces in
[`core-model.md`](core-model.md) §2.3; sign queries covering every field in
[`core-model.md`](core-model.md) §2 under the mandatory-to-implement suite
`eddsa-jws-2026`; emit a `routing` projection that is a strict subset of the
signed object; **process every response in the order in
[`core-model.md`](core-model.md) §4.1**; handle all three response statuses;
verify response signatures against its own minimum acceptable suite policy before
exposing an answer; store receipts; honour idempotency on retry.

**Must not.** Expand a registered answer domain; re-sign a modified contract as
though it were the original; treat an `escalate` pending token as an answer;
**parse a response object before its signature verifies, or release any part of a
response to a caller before §4.1 step 9**; map an unrecognized status onto a
default; place a signature-covered field in `routing` only; accept a response
whose suite falls below its minimum acceptable policy.

**Supports.** Q2D-C-01, Q2D-C-05, Q2D-C-07.

### CC-2 — Core responder

**Must.** Execute the processing order in [`core-model.md`](core-model.md) §4
without reordering steps 1–16 **or the lettered steps among them, 5a, 9a and 11a**;
check the signature suite against its minimum
acceptable policy before verifying; authenticate and verify delegation through
the interfaces in [`core-model.md`](core-model.md) §2.3; reject any `routing` /
`signed` disagreement; enforce replay and expiry; **enforce a configured rate
limit at step 9a**, keyed on the relationship only
([`core-model.md`](core-model.md) §9.1); resolve the predicate against a pinned
registry and fail closed on anything unknown; compute the effective answer domain
itself by narrowing composition, per shape, per §3.2 **and §3.3**; validate
output against it **and against the entry's `output_schema`** (§4 step 17);
debit capacity once; issue a receipt with every outcome; record the suite in the
receipt; sign the response.

**Must not.** Read private input before step 16; parse the core object before
its signature verifies; use `routing` for any decision the signature covers;
accept a requester-asserted answer domain or capacity debit; **debit capacity for
a denial, an escalation, or a rate-limit rejection** (§9.1); rate-limit *after*
registry resolution, which would leave unknown predicates unlimited; start with
no rate limit configured; accept a suite below its policy floor or offer an alternative
suite in a rejection; silently downgrade a requested assurance profile;
serialize private input into an error.

**Supports.** Q2D-C-02, Q2D-C-03, Q2D-C-04, Q2D-C-06, Q2D-C-07, Q2D-C-09, Q2D-C-10.

**Requires.** CC-3 and at least one assurance-profile class.

### CC-3 — Policy engine

**Must.** Return deterministic `allow` / `deny` / `escalate` plus modifiers, from
the input contract in [`core-model.md`](core-model.md) §2; fail closed when
authorities conflict or required context cannot be resolved; compose multiple
authorities restrictively — every mandatory authority must permit, any mandatory
deny prevents; keep detailed reasons local.

**Must not.** Allow a user-authored rule to override a fail-closed invariant;
disclose policy reasoning in an externally visible response unless a policy
explicitly permits it.

**Supports.** Q2D-C-08, Q2D-C-09.

**Note.** Q2D specifies the policy input and output contract, not a policy
language. XACML, OPA/Rego, or local code may implement this class.

---

## Assurance-profile classes

Independent of each other. Implementing one grants nothing about the others, and
a later profile does **not** inherit Phase 1's security review.

### CC-4 — Authenticated Answer Profile

**Must.** Bind a valid computation-executor signature over the result or denial
status, the effective contract digest, the receipt, and the request digest;
publish a key-resolution path the requester can verify.

**May claim.** Origin and integrity of the response; binding to the request.

**Must not claim.** That the predicate was executed faithfully, that the correct
record was selected, that the data was current, or that the underlying fact is
true (Q2D-NC-01, Q2D-NC-10).

**Supports.** Q2D-C-06. **This is the minimum conforming profile for 0.1.**

### CC-5 — Credential-Backed Profile — future

**Must.** Verify issuer evidence and bind the presentation to the query nonce,
predicate, recipient, and public context; state exactly what is proved.

**Must not claim.** That the issuer is honest, or that basic selective
disclosure provides range, equality, or set-membership predicates over hidden
attributes without an additional proof construction.

### CC-6 — Verifiable Computation Profile — future

**Must.** Verify a proof binding program or circuit digest, input commitment,
public-context digest, query identifier and nonce, output, and predicate
version.

**Must not claim.** That the committed input was truthful, complete, or current.

### CC-7 — Attested-Use Profile — future

**Must.** Verify attestation, measurement, key binding, and the declared egress
policy before release.

**Must not claim.** Control over plaintext after it legitimately leaves the
attested environment. The term is **attested-use release** — never tamper-proof
courier or guaranteed destruction.

---

## Binding classes

### CC-8 — MCP binding

**Must.** Preserve every field and security semantic in
[`core-model.md`](core-model.md); construct and verify the signed core object in
the host-side runtime, not in model-visible tool arguments or results; keep
evidence out of the model-visible result where containment is claimed; compose
with, rather than duplicate, MCP authorization.

**Must not.** Broaden an answer domain or drop a declared sink because the
transport lacks a native field for it — fail instead.

**Supports.** Q2D-C-11.

### CC-9 — A2A binding

**Must.** Advertise the extension and supported core versions, registries,
identity profiles, and assurance profiles; preserve the signed core object
across intermediaries; map synchronous and asynchronous states without semantic
loss.

**Must not.** Permit an intermediary to rewrite purpose, sinks, or answer shape.

**Supports.** Q2D-C-11.

### CC-12 — Direct HTTPS binding

**Must.** Carry the [`core-model.md`](core-model.md) §2.1 envelope as the request
body, unmodified and unexamined by the transport; return **HTTP 200 with a signed
body for every Q2D outcome** — `answer`, `deny`, and `escalate` alike; return a
4xx with no signed body only where a request never became a Q2D exchange
(malformed framing, oversized body, wrong content type, unknown path); serve
capability discovery from configuration; where explicit escalation is supported,
return an identical response for unknown, expired, and still-pending tokens —
a **poll status object carrying no receipt**, since an unknown token has no
exchange a receipt could bind — and once decided, a **poll outcome object**
stating only that an authority approved or refused. A poll never returns the
answer: an approval is a grant, and the answer comes from a fresh revalidated
query ([`core-model.md`](core-model.md) §5.3).

**Must not.** Place any Q2D field in a path, query parameter, or header, or read
one from there; accept a transport-level idempotency key alongside the signed
`query_id` and `nonce`; vary any status code or response header with the
outcome — including `429`, `503`, and `Retry-After`, which are cause-specific
retry metadata by construction; serve a registry entry from an unauthenticated
endpoint, which is an existence oracle and makes the §2.4.1 entry-digest check
vacuous; attach a receipt to a poll response, which would attest to an exchange
that may not exist; log request or response bodies or headers.

**Supports.** Q2D-C-08 at the transport layer, and Q2D-C-11 as one of the two
bindings its equivalence requires.

**Note.** A rate-limit rejection (§9.1) is a Q2D outcome, not a transport event.
It is returned as a normalized denial under the rules above — HTTP 200, signed
body, no distinguishing header — for the same reason every other cause in its
class is.

---

## Requester-side class

### CC-10 — Contained requester runtime

**Must.** Verify all evidence outside model context; expose only the semantic
answer and policy-permitted metadata to the agent; label answers and derived
values; maintain a complete sink inventory including model endpoints, logs,
traces, and memory; mediate tool and network calls; propagate labels through
deterministic transformations; block or escalate unauthorized flows; fail closed
when provenance is lost.

**Must not claim** containment for any path it does not mediate.

**Supports.** Q2D-C-12, Q2D-C-13.

**Compatibility mode.** An implementation that omits CC-10 is still a valid
CC-1 requester. It may claim *"bounded authenticated answer from a participating
custodian."* It may **not** claim *"answer-derived flow restricted to permitted
sinks."* The response indicates which conformance class was achieved.

---

## Audit class

### CC-11 — Audit verifier

**Must.** Validate receipts and authorized audit evidence without receiving
unnecessary private source data; verify that a receipt's digests correspond to
the exchange it claims.

**Must not.** Require disclosure of the local audit event to verify an external
receipt.

---

## Composition

```
CC-2 (responder) ─ requires ─▶ CC-3 (policy engine)
                 └ requires ─▶ one of CC-4 … CC-7
CC-8 / CC-9 (bindings) ─ require ─▶ CC-1 and/or CC-2
CC-10 ─ requires ─▶ CC-1
```

An implementation states its classes as a set — for example
*"CC-1, CC-4, CC-8"* — never as a level or a tier. There is no ordering among
these classes, and no class is "higher" than another.

---

## Claim coverage

Every claim in [`claims.md`](claims.md) is owned by at least one class. A claim
with no owning class is a specification gap.

| Claim | Owned by |
|---|---|
| Q2D-C-01 pre-evaluation commitment | CC-1 |
| Q2D-C-02 responder-owned domain validation | CC-2 |
| Q2D-C-03 bounded output | CC-2 |
| Q2D-C-04 source confinement | CC-2 |
| Q2D-C-05 request binding | CC-1 |
| Q2D-C-06 response authentication | CC-2, CC-4 |
| Q2D-C-07 replay resistance | CC-1, CC-2 |
| Q2D-C-08 denial normalization | CC-2, CC-3 |
| Q2D-C-09 disclosure-capacity accounting | CC-2, CC-3 |
| Q2D-C-10 exchange-bound accountability | CC-2, CC-11 |
| Q2D-C-11 binding equivalence | CC-8, CC-9, CC-12 |
| Q2D-C-12 evidence segregation | CC-10 |
| Q2D-C-13 conditional flow confinement | CC-10 |

**Q2D-C-11 is the one claim no single owning class establishes.** Equivalence is
a statement *between* bindings, so implementing any one of CC-8, CC-9, or CC-12
supplies a binding to compare and demonstrates nothing on its own. The claim
holds only once two of them pass the same vector set.

Also note that Q2D-C-12 and Q2D-C-13 hold only under the
`q2d-contained-runtime-0.1` profile, per [`claims.md`](claims.md). CC-10's
compatibility mode is the honest position for a requester without it: a valid
CC-1 requester claiming neither.

---

## What a conformance suite must provide

Before any class can be claimed:

- executable test vectors for every signed structure;
- a positive and a negative test for each `must` and `must not` above;
- property tests for the fail-closed invariants in CC-3;
- parser and schema fuzzing;
- replay, expiry, nonce, and idempotency tests;
- malicious-registry and domain-understatement tests;
- a traceability matrix from each claim in [`claims.md`](claims.md) to the tests
  that exercise it.

Conformance cases are written **alongside** the normative specification, not
afterwards. A requirement with no test is not a requirement.
