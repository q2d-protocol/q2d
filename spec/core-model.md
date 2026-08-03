# Q2D Core Model — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

The abstract exchange: what a query carries, what a response carries, and the
order in which a responder processes them. Bindings map this onto MCP, A2A, or
direct HTTPS without changing its meaning.

This document defines the **model**. It does not yet define the wire format —
canonical serialization and the signature container are parked in §9. Field
names below are the canonical names a binding should preserve where its
transport allows.

Terms: [`terminology.md`](terminology.md). Boundaries: [`scope.md`](scope.md).
Properties: [`claims.md`](claims.md).

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

### 2.1 Protocol metadata

| Field | Required | Meaning |
|---|---|---|
| `q2d_version` | yes | Core protocol version. |
| `type` | yes | `query`. |
| `query_id` | yes | Identifies this exchange. |
| `issued_at` | yes | Issue time. |
| `expires_at` | yes | After this, the responder rejects. |
| `nonce` | yes | High-entropy; replay context. |
| `correlation_id` | no | For asynchronous escalation. |

### 2.2 Principals and authority

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

### 2.3 Predicate

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

### 2.4 Answer contract

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

### 2.5 Purpose and delivery

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

### 2.6 Freshness and authentication

| Field | Required | Meaning |
|---|---|---|
| `freshness.maximum_source_age` | no | Maximum acceptable age of source data or credential evidence. |
| `signature.profile` | yes | Identifies algorithm and canonicalization. |
| `signature.key_id` | yes | Resolvable under the identity profile. |
| `signature.value` | yes | Covers every field above. |

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
| 1 | Structural parse; reject oversized or malformed input | Before any allocation on attacker-controlled data. |
| 2 | Expiry and clock-skew check | Cheap; discards stale traffic. |
| 3 | Signature verification and key resolution | **Nothing below this line runs for an unauthenticated request.** |
| 4 | Delegation verification | Establishes the agent acts for the principal. |
| 5 | Replay-cache check | After signature, so unauthenticated traffic cannot pollute the cache. |
| 6 | Registry: predicate known, version known, not revoked, digest pinned | Fails closed on anything unrecognized. |
| 7 | Public context validated against the entry's input schema | Schema comes from the registry, not the request. |
| 8 | Answer contract no broader than the registry entry | Q2D-C-02. |
| 9 | Requested assurance profile supported | Refuse rather than downgrade. |
| 10 | Policy evaluation → `allow` / `deny` / `escalate` + modifiers | First step that consults policy authorities. |
| 11 | Budget: sufficient capacity for the computed debit | Before private access, so exhaustion never reads data. |
| 12 | **Private input accessed; predicate evaluated** | Everything above gates this line. |
| 13 | Output validated against the effective domain | Q2D-C-03. Fails closed. |
| 14 | Budget debited | Once, idempotently. |
| 15 | Receipt constructed; response signed | Q2D-C-10. |

Two invariants follow:

- **Steps 1–11 complete before any private input is read.** A denial at any of
  them is reachable without touching protected data.
- **The external response must not reveal which step failed** where the
  sensitivity class requires normalization (Q2D-C-08). Internal audit records
  the true cause; the wire does not.

Step 13 failing is an implementation or integrity error, not a policy outcome.
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
| **Canonical serialization and signature container** | JCS (RFC 8785) with Ed25519 (RFC 8032) as the Phase 1 profile | Implementation experience; must be pinned before any test vector is published |
| **Identity/delegation core-vs-profile boundary** | Core defines the three interfaces; profiles supply the technology | Which profile, if any, is mandatory to implement |
| **Approval-scope digest field list** | The seven fields in §5.3 | Grant lifetime and revocation semantics |
| **Capacity calculation for `object` outputs** | Registry supplies an upper bound from field domains, precision, and length | A formal calculation |
| **Whether `deny` and `escalate` debit the budget** | Undecided. Debiting leaks; not debiting permits free probing | Analysis of which leaks more |
| **Timing and padding requirements** | None normative in 0.1 | A defined indistinguishability property and its tests |

An implementation may choose any of these. It must not describe its choice as
the Q2D answer until this document records it.
