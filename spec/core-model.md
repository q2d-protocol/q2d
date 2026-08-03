# Q2D Core Model — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

The abstract exchange: what a query carries, what a response carries, and the
order in which a responder processes them. Bindings map this onto MCP, A2A, or
direct HTTPS without changing its meaning.

This document defines the **model**. Field names below are the canonical names a
binding should preserve where its transport allows. Signature algorithms and
serialization are not fixed here — they are named by suite in
[`crypto-suites.md`](crypto-suites.md).

Terms: [`terminology.md`](terminology.md). Boundaries: [`scope.md`](scope.md).
Properties: [`claims.md`](claims.md). Suites: [`crypto-suites.md`](crypto-suites.md).

Where this document and the technical report disagree, this document governs.

---

## 1. The exchange

One query, one response. The response is exactly one of three outcomes.

```
requester runtime  ──  query  ──▶  responder
                   ◀── response ──
                                   status ∈ { answer, deny, escalate }
```

There is no partial answer and no negotiation round trip. A requester that
cannot accept the effective contract abandons the task and may submit a
different query.

## 2. Query

### 2.1 Envelope

A message has two parts. Only one of them is authoritative.

```
{
  "signed":  "<opaque: the core object and its signature>",
  "routing": { ... non-authoritative projection ... }
}
```

**`signed`** carries the core object and its signature under a registered suite
([`crypto-suites.md`](crypto-suites.md)). The signature covers the exact bytes
transmitted. There is nothing to canonicalize, and a verifier parses the core
object **only after** verifying those bytes.

**`routing`** is a projection for intermediaries that must dispatch or
capability-match without unwrapping. It is advisory:

- a responder **must not** use `routing` for any decision the signature covers;
- `routing` **must** be a strict subset of what `signed` contains — it may
  never introduce a field;
- if the two disagree on any field, the request is **rejected**, not
  reconciled. Disagreement is a tampering signal;
- an intermediary may read `routing`. It must not modify `signed`.

`routing` is kept minimal, because it travels in the clear. It carries at most
`q2d_version`, `type`, `target.custodian`, `predicate.id`, `predicate.version`,
and `expires_at`. **Purpose, sinks, subjects, the answer contract, and public
context are never projected** — a relay has no need for them, and exposing them
would leak precisely what the protocol exists to bound.

This structure is what makes Q2D-C-05 hold by construction rather than by every
intermediary's JSON library behaving identically. It also matters for
interoperability: canonicalization disagreements across language ecosystems are
a classic source of cross-implementation failure, and Q2D targets two
implementations from the start.

### 2.2 Protocol metadata

| Field | Required | Meaning |
|---|---|---|
| `q2d_version` | yes | Core protocol version. |
| `type` | yes | `query`. |
| `query_id` | yes | Identifies this exchange. |
| `issued_at` | yes | Issue time. |
| `expires_at` | yes | After this, the responder rejects. |
| `nonce` | yes | High-entropy; replay context. |
| `correlation_id` | no | For asynchronous escalation. |

### 2.3 Principals and authority

| Field | Required | Meaning |
|---|---|---|
| `requester.principal` | yes | The accountable party. |
| `requester.agent` | yes | The delegated software acting for it. |
| `requester.delegation` | profile-dependent | Evidence or reference proving the agent acts for the principal. |
| `target.custodian` | yes | The participating custodian addressed. |
| `target.executor` | no | Intended computation executor, where a deployment distinguishes it. |
| `target.subjects` | no | Relevant data subjects, where applicable. |
| `policy_authority_hint` | no | A hint the responder **may ignore**. It never determines which authorities apply. |

Q2D defines three interfaces here rather than one identity technology: principal
identification, key resolution, and delegation verification. Local pairing,
enterprise OIDC/OAuth, and DID/UCAN are profiles over those interfaces. See §9.

### 2.4 Predicate

| Field | Required | Meaning |
|---|---|---|
| `predicate.id` | yes | Stable identifier. |
| `predicate.version` | yes | Registered version. |
| `predicate.registry_digest` | yes | The manifest digest the requester believes is in force. |
| `predicate.public_context` | one of | Public input inline. |
| `predicate.public_context_digest` | one of | Or its digest, where the value travels separately. |
| `predicate.requested_assurance` | no | Defaults to `authenticated-answer`. |

A requester selects from registered predicates. Free-form expressions are out of
scope ([`scope.md`](scope.md) §4).

### 2.5 Answer contract

The requester's pre-evaluation commitment (Q2D-C-01).

| Field | Required | Meaning |
|---|---|---|
| `answer_contract.release_shape` | yes | One of the eight identifiers in [`terminology.md`](terminology.md) §4. |
| `answer_contract.domain` | yes | The requested domain, or a reference to the registry-defined one. |
| `answer_contract.maximum_cardinality` | shape-dependent | For `set` and `object`. |
| `answer_contract.allowed_detail_fields` | yes | May be empty. Never unconstrained — every disclosed field is part of the contract and the capacity calculation. |
| `answer_contract.precision` | shape-dependent | Granularity for `scalar` and `interval`. |
| `answer_contract.disclosure_class` | no | Requester's sensitivity assertion; advisory only. |

**A requester may request a subset or a coarser form of the registered domain. It
may never expand one.** The domain in the query is a request, not an assertion
the responder honours (Q2D-C-02).

### 2.6 Purpose and delivery

| Field | Required | Meaning |
|---|---|---|
| `purpose.code` | yes | Machine-readable purpose. |
| `purpose.description` | yes | Human-readable, for the approval interface. |
| `purpose.requested_retention` | no | A request and an obligation, not an enforced control. |
| `purpose.onward_transfer` | no | Likewise. |
| `delivery.answer_recipient` | yes | Who receives the verified answer. |
| `delivery.model_endpoint` | no | **Required if a remote model will receive the answer.** A model provider is a sink. |
| `delivery.permitted_sinks` | yes | May be empty. |
| `delivery.required_containment_profile` | no | e.g. `q2d-contained-runtime-0.1`. |

The protocol separates **declared** purpose from **authorized** purpose. The
query records what the requester claims; the receipt records what the responder
permitted. Neither predicts human behaviour (Q2D-NC-02).

### 2.7 Freshness and authentication

| Field | Required | Meaning |
|---|---|---|
| `freshness.maximum_source_age` | no | Maximum acceptable age of source data or credential evidence. |
| `signature.profile` | yes | The **signature suite** identifier — algorithm, serialization, and hash as one unit. See [`crypto-suites.md`](crypto-suites.md). |
| `signature.key_id` | yes | Resolvable under the identity profile. |
| `signature.value` | yes | Covers every field above. |

`signature.profile` is a field of the **signed** core object, never of the outer
envelope. An intermediary rewriting the envelope therefore cannot change which
suite a verifier believes was used. A verifier applies its own minimum
acceptable policy and rejects suites below it, whatever the sender selected.

## 3. Effective answer domain

The responder computes, and never accepts:

```
effective_domain = registry_entry.canonical_domain
                 ∩ answer_contract.domain
                 ∩ policy_modifiers
```

If the intersection is empty, the request fails closed. The capacity debit
(Q2D-C-09) is computed from this value, not from anything the requester asserted.

## 4. Processing order

Order is a security property, not an implementation detail. It determines what
work an unauthenticated party can make a responder do, and what an attacker
learns from *which* step rejected.

A conforming responder processes in this order:

| # | Step | Why here |
|---|---|---|
| 1 | Parse the **envelope**; reject oversized or malformed input | Before any allocation on attacker-controlled data. |
| 2 | *Optional:* shed obviously stale traffic using `routing.expires_at` | Load shedding only. **Never a security decision** — `routing` is advisory. |
| 3 | Read the suite identifier; reject if below the verifier's minimum acceptable policy | The sender's declared suite selects how to verify, so it is read before verification — but it is checked against local policy, never trusted. Prevents algorithm-confusion and downgrade. |
| 4 | Resolve the key; **verify the signature over the exact signed bytes** | **Nothing below this line runs for an unauthenticated request.** |
| 5 | Parse the verified core object | Parsing happens *after* verification, so parser behaviour is outside the security boundary. |
| 6 | Expiry and clock-skew check — authoritative | The signed value governs; step 2 was advisory. |
| 7 | Delegation verification | Establishes the agent acts for the principal. |
| 8 | `routing` / `signed` consistency | Any disagreement is tampering. Reject; do not reconcile. |
| 9 | Replay-cache check | After signature, so unauthenticated traffic cannot pollute the cache. |
| 10 | Registry: predicate known, version known, not revoked, digest pinned | Fails closed on anything unrecognized. |
| 11 | Public context validated against the entry's input schema | Schema comes from the registry, not the request. |
| 12 | Answer contract no broader than the registry entry | Q2D-C-02. |
| 13 | Requested assurance profile supported | Refuse rather than downgrade. |
| 14 | Policy evaluation → `allow` / `deny` / `escalate` + modifiers | First step that consults policy authorities. |
| 15 | Budget: sufficient capacity for the computed debit | Before private access, so exhaustion never reads data. |
| 16 | **Private input accessed; predicate evaluated** | Everything above gates this line. |
| 17 | Output validated against the effective domain | Q2D-C-03. Fails closed. |
| 18 | Budget debited | Once, idempotently. |
| 19 | Receipt constructed; response signed | Q2D-C-10. |

Three invariants follow:

- **Steps 1–15 complete before any private input is read.** A denial at any of
  them is reachable without touching protected data.
- **The core object is parsed only after its signature verifies** (step 5). An
  attacker cannot reach the JSON parser for the security-relevant object without
  a valid signature.
- **The external response must not reveal which step failed** where the
  sensitivity class requires normalization (Q2D-C-08). Internal audit records
  the true cause; the wire does not.

Step 17 failing is an implementation or integrity error, not a policy outcome.
It is logged as such, and the runtime must not serialize an exception carrying
private input.

## 5. Response

### 5.1 answer

| Field | Meaning |
|---|---|
| `status` | `answer` |
| `result` | The bounded semantic result, conforming to the effective domain. |
| `effective_contract_digest` | What was actually authorized — may be narrower than requested. |
| `assurance.profile` | The profile actually used. Never a silent downgrade. |
| `assurance.executor` | Identity of the computation executor. |
| `evidence` | Reference or compact object, where the profile carries one. |
| `receipt` | §6. |
| `signature` | Covers all of the above. |

### 5.2 deny

| Field | Meaning |
|---|---|
| `status` | `deny` |
| `external_reason` | The **normalized class**, not the true cause. |
| `receipt` | Reduced: request digest, decision class, decision time. |
| `signature` | |

Within a sensitivity class configured for normalization, `external_reason`,
response size, and retry semantics are identical for absent data, policy
refusal, budget exhaustion, unsupported predicate, failed freshness, and
internal escalation. **No cause-specific retry guidance.** If retry metadata is
present, its value is identical across every cause mapped to that class.

### 5.3 escalate

An authorized human or policy authority must decide before release. Two modes,
and the choice is itself a policy decision.

**Explicit escalation** returns `status: escalate` with an opaque
`pending_token` and `expires_at`. This reveals that a relationship, record, or
applicable policy path may exist. Use only where that disclosure is acceptable.
It is **not** denial-normalized and must never be described as such.

**Opaque escalation** returns the same normalized envelope as §5.2. The
authority is prompted out of band. Then:

1. The original query stays idempotent — identical retries keep returning the
   cached normalized outcome, and **never** become an answer after approval.
2. On approval the responder records a time-bounded grant keyed to an
   **approval-scope digest** covering requester principal and agent, predicate
   and version, answer-contract digest, purpose, answer recipient, sink set, and
   public-context commitment — and excluding `query_id`, `nonce`, `issued_at`,
   and `expires_at`.
3. The requester submits a **fresh signed query** with new identifier and nonce
   but the same approval scope.
4. The responder revalidates registry state, delegation, policy, freshness,
   budget, and current data before answering, and issues a new receipt.

The resulting unavailable-to-answer transition is a **residual timing and state
oracle**. It is named, not hidden. A binding may define authenticated push
delivery instead, but must not mutate the cached result of an identical retry.

## 6. Receipt

Binds one exchange (Q2D-C-10): request digest, response digest, predicate
identifier and version, effective answer-contract digest, policy version or
decision-policy digest, release shape, assurance profile, disclosure-capacity
debit, decision time, responder identity, and optionally a requester
acknowledgment.

The receipt is deliberately **smaller than the local audit event**. Diagnostic
and policy detail stays local and is not disclosed to the requester by default.

## 7. Idempotency and replay

An identical retry — same signed `query_id` and `nonce` — returns the same
cached outcome. It must not debit the budget twice, and must not transition from
a normalized outcome to an answer.

A changed purpose, sink set, public context, predicate version, or answer
contract is a **different request** requiring a new signature and a new policy
decision, even when the approval-scope digest matches.

## 8. Versioning

Core protocol, bindings, assurance profiles, registries, and implementation
packages version independently. A query and receipt bind the core version,
predicate version, registry digest, and assurance profile so that later code or
registry updates cannot reinterpret an earlier exchange.

## 9. Parked — not decided here

These are open in the technical report's Appendix C and stay open. Recorded so
that no implementation quietly settles them by accident.

| Open item | Current leaning | Blocked on |
|---|---|---|
| **Identity/delegation core-vs-profile boundary** | Core defines the three interfaces; profiles supply the technology | Which profile, if any, is mandatory to implement |
| **Approval-scope digest field list** | The seven fields in §5.3 | Grant lifetime and revocation semantics |
| **Capacity calculation for `object` outputs** | Registry supplies an upper bound from field domains, precision, and length | A formal calculation |
| **Whether `deny` and `escalate` debit the budget** | Undecided. Debiting leaks; not debiting permits free probing | Analysis of which leaks more |
| **Timing and padding requirements** | None normative in 0.1 | A defined indistinguishability property and its tests |

An implementation may choose any of these. It must not describe its choice as
the Q2D answer until this document records it.

**Resolved since the first draft of this document.** Serialization and the
signature container are no longer open. The envelope in §2.1 signs exact
transmitted bytes, so canonicalization is not on the security path, and
algorithms are named by suite rather than fixed —
[`crypto-suites.md`](crypto-suites.md) carries the registry, the
mandatory-to-implement suite, and the downgrade rules.
