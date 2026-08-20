# P-011 — Receipts and local audit

| Field | Detail |
|---|---|
| PRD | P-011 |
| Stage | 4 — closes it |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-002](P-002-message-envelope.md), [P-003](P-003-crypto-suites.md), [P-005](P-005-registry-client.md), [P-007](P-007-policy-engine.md), [P-008](P-008-capacity-accounting.md), [P-010](P-010-responder-pipeline.md) |
| Blocks | P-012, P-013, P-016 |


> **Partially shrunk 2026-08-19 — and one cut was reversed by review.**
>
> **Kept:** the receipt types, `build_receipt`, `response_digest`,
> `build_deny_receipt`, `verify_receipt`, the corpus section, the claim-language
> audit — and the **`AuditEvent` type and a local append-only audit store**.
>
> **The audit store was cut and restored.** The first draft of the scope
> reduction cut all four audit issues on the grounds that a demonstration returns
> receipts rather than storing them. Review found that
> [`claims.md`](../../spec/claims.md) **Q2D-C-10 holds when the responder issues a
> receipt for every outcome *and retains detailed audit locally*** — so cutting
> the store while still claiming C-10 would have delivered less than the claim
> states. §4.3's audit/receipt delta is the reason the store is not merely a log:
> it is where the internal reason, the rejecting step, and the policy reasoning
> live, none of which may reach the wire.
>
> **Still cut:** encryption at rest, and retention/deletion machinery. Both are
> enterprise hardening rather than the property C-10 rests on. **§4.7's argument
> that an audit store with no expiry is an ever-growing record of who asked what
> about whom remains true**, and is the first thing to restore if this is ever
> deployed rather than demonstrated.

---

## 1. Purpose

Construct the disclosure receipt, write the local audit event, and keep the two
different in exactly the ways they must be.

**Claims served:** Q2D-C-10 (exchange-bound accountability) directly. Q2D-C-06
depends on it — a response signature binds the receipt, so a receipt that binds
the wrong things weakens what the signature attests.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §6 | Receipt field set; the receipt is deliberately smaller than the audit event |
| [`spec/core-model.md`](../../spec/core-model.md) §2.4.1 | The entry digest, which the receipt now carries |
| [`spec/core-model.md`](../../spec/core-model.md) §5.1, §5.2 | Receipt shape in `answer` and in `deny` |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §5 | The receipt records the suite used, so an old receipt stays assessable |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-10 | What a receipt is evidence of, and what it is not |
| [`spec/terminology.md`](../../spec/terminology.md) §3 | Disclosure receipt — evidence a runtime processed an exchange, nothing more |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-11 | An audit verifier validates receipts without receiving private source data |

## 3. Module boundary

**Inside:** receipt construction and its field set; the digest definitions the
receipt depends on; the audit event and what distinguishes it from the receipt;
audit storage, retention, and encryption at rest; the receipt-verification
interface CC-11 needs.

**Explicitly outside:** signing (**P-003**), which signs a response that
*contains* a receipt. Deciding outcomes (**P-007**). Computing the debit
(**P-008**). Any transparency log or public anchoring — deferred by
[`scope.md`](../../spec/scope.md) §7 and not a Phase 1 mechanism.

## 4. Design

### 4.1 Receipt fields

| Field | Source | Present on |
|---|---|---|
| `request_digest` | the exact `signed` bytes received | answer, deny, escalate |
| `response_digest` | §4.2 | answer |
| `predicate` | id and version | answer |
| `entry_digest` | the resolved registry entry ([`core-model.md`](../../spec/core-model.md) §2.4.1) | answer |
| `effective_contract_digest` | the effective answer contract | answer |
| `policy_version` | the decision-policy digest | answer |
| `release_shape` | the effective domain's shape | answer |
| `assurance_profile` | the profile actually used | answer |
| `signature_suite` | the suite the response was signed under | answer, deny, escalate |
| ~~`disclosure_capacity_debit_millibits`~~ | **Removed 2026-08-19** from `claims.md` Q2D-C-10 and [`core-model.md`](../../spec/core-model.md) §6. A field whose only available value is zero is a lie in waiting — a reader seeing `0` concludes the answer disclosed nothing. A future disclosure-magnitude field gets a **new name**, not this one restored meaning something else | ~~answer~~ |
| `decided_at` | A timestamp — [`core-model.md`](../../spec/core-model.md) §2.2 | answer, deny, escalate |
| `responder` | the computation executor's identity | answer, deny, escalate |
| `decision_class` | the normalized external class, or `escalate` — see below | deny, escalate |
| `requester_acknowledgment` | **reserved, not implemented** — §4.6 | — |

The deny receipt carries five fields and no variable-length value, which is what
makes [P-009](P-009-denial-normalization.md) §4.3's uniformity structural.

**The escalate column is the same five fields.** An explicit `escalate` carries
the reduced receipt with `decision_class: escalate`
([`core-model.md`](../../spec/core-model.md) §5.3). Q2D-C-10 binds every
exchange, and without this an escalated exchange produced no evidence it had
happened — an unstated exception to the claim rather than a gap someone had
decided on.

**One boundary, and it is the whole reason this is safe.** `decision_class:
escalate` belongs only to an **explicit** escalation. An *opaque* escalation
returns the §5.2 normalized envelope and carries the **ordinary deny receipt**,
with the ordinary deny `decision_class` — indistinguishable from every other
Tier C cause. A receipt recording `escalate` for an outcome the wire had made
uniform would defeat Q2D-C-08 through the evidence attached to the response,
while [P-009](P-009-denial-normalization.md)'s response-body uniformity check
still passed. `denial/receipt-uniformity/` exists to catch exactly that.

Explicit escalation costs nothing in uniformity because it is not in a
normalized class to begin with.

`entry_digest` is new since the option-2 change. Without it a receipt records
*which predicate and version* were used but not *which definition of them*, which
is precisely the ambiguity per-entry digests closed.

`signature_suite` is what lets a receipt remain assessable after that suite is
deprecated or withdrawn ([`crypto-suites.md`](../../spec/crypto-suites.md) §5) —
a verifier years later can tell what was used and judge accordingly.

### 4.2 `response_digest` and the circularity

The receipt travels **inside** the response, and binds a digest **of** the
response. Taken literally that is circular.

`response_digest` is therefore computed over the response's **semantic content**
— result, effective contract digest, assurance profile — **excluding the receipt
and the signature**. Well-defined, non-circular, and computable before the
receipt exists. [`core-model.md`](../../spec/core-model.md) §6 carries this
normatively; [`serialization.md`](../../spec/serialization.md) §1 supplies the
production profile it needs and §5 the digest construction, since unlike
`request_digest` it is taken over a sub-object rather than over received bytes.

Its purpose is standalone verification. When a receipt travels with its response
the signature already binds them, and the digest is redundant. It earns its place
when an **auditor holds a receipt separately** and needs to confirm it
corresponds to a response they also hold — which is exactly CC-11's job.

### 4.3 The audit event is larger, and differently shaped

[`core-model.md`](../../spec/core-model.md) §6 requires the audit event to be
larger so diagnostic and policy detail is not automatically disclosed. The delta
is enumerated rather than left to judgement:

| In audit, never in a receipt | Why |
|---|---|
| The **internal** rejection reason | [P-009](P-009-denial-normalization.md) Tier C exists to hide it |
| The **step** at which a rejection occurred | A per-step oracle |
| Policy reasoning and authorities consulted | CC-3 forbids disclosing it |
| Budget state before and after | Reveals other requesters' activity |
| A requester/custodian entry-digest mismatch, and both values | Reveals which registry this custodian pinned |
| Predicate fault detail | Reveals implementation state |
| Timing | Reveals cost, and therefore path |

### 4.4 Neither one contains private input

The audit event is **more detailed, not less careful**. It records decisions, not
data.

**Specifically, the audit does not store the answer.** It stores
`response_digest`, which pins what was answered without retaining it. Anyone
holding the response can verify against the digest; anyone without it cannot
reconstruct the answer from the audit.

This is deliberate, and the reasoning is not only privacy hygiene. A released
answer is already known to its recipient, so storing a second copy adds no
operational capability while creating a retention obligation over personal data —
which the technical report already warns about for receipts and logs themselves.

The cost is real: a dispute about what was answered cannot be settled from the
audit alone. It can be settled by anyone holding the response, which is both
parties.

### 4.5 A receipt is evidence of processing, and nothing else

A receipt attests that a particular runtime processed and authenticated an
exchange. It is **not** evidence that:

- the underlying facts were true, complete, or current;
- the correct record was selected;
- the predicate was executed faithfully;
- a legal basis existed;
- the recipient honoured a retention or onward-transfer obligation.

Documentation, code comments, and any operator-facing text describing a receipt
must not imply otherwise. This is the claim-honesty surface of this module, and
"proof of disclosure" is the phrasing to watch for — a receipt is proof of an
*exchange*, and the difference is the entire content of Q2D-NC-01.

### 4.6 Acknowledgment is reserved, not implemented

[`core-model.md`](../../spec/core-model.md) §6 lists an optional requester
acknowledgment, and Appendix C of the technical report records countersignature
semantics as unresolved.

MVP reserves the field and implements nothing. A half-specified countersignature
is worse than none: a receipt carrying an acknowledgment whose semantics are
undefined invites a reader to assume bilateral agreement that was never
established.

### 4.7 Audit storage

**Append-only** — and, before any real deployment, encrypted at rest with a
configured retention period after which events are deleted rather than archived.

**Append-only is the part [`claims.md`](../../spec/claims.md) Q2D-C-10 rests on**,
because an audit that can be rewritten attests to nothing. **Encryption and
retention are deferred as hardening** by the 2026-08-19 reduction — see the note
at the top of this PRD — and the paragraph below is why they are deferred rather
than dropped.

Retention is a **deployment** decision this module does not choose, and the
mechanism is mandatory the moment there is a deployment: an audit store with no
expiry is an ever-growing record of who asked what about whom. [`claims.md`](../../spec/claims.md) is explicit
that receipts, logs, identifiers, and policy history may themselves be personal
data.

No transparency log, no public anchoring, no shared store. All deferred by
[`scope.md`](../../spec/scope.md) §7, and the report notes that public disclosure
logs create correlation and dictionary-attack risks that Phase 1 does not attempt
to manage.

## 5. Interfaces

```
build_receipt(facts: ExchangeFacts) -> Receipt
build_deny_receipt(request_digest, decision_class, suite, now, responder) -> DenyReceipt
write_audit(event: AuditEvent) -> Result
verify_receipt(receipt, response: Option<bytes>, keys) -> VerificationResult   // CC-11
```

`ExchangeFacts` is assembled by [P-010](P-010-responder-pipeline.md) and contains
**no private-derived value except the digests**. A receipt builder that could see
the answer could put it in a receipt.

`build_deny_receipt` takes its five fields individually rather than an
`ExchangeFacts`, so there is no path by which an answer-side field reaches a
denial.

`verify_receipt` accepting an optional response is what makes CC-11 possible:
with the response it verifies the full binding, without it it verifies everything
except `response_digest` and says so in its result rather than silently checking
less.

## 6. Corpus sections

`receipt/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `receipt/fields/` | Every field present and correctly sourced, for answer, deny, and explicit escalate |
| ~~`receipt/escalate/`~~ | **Deferred 2026-08-19** with the escalation lifecycle. ~~An explicit `escalate` carries the reduced receipt with `decision_class: escalate`; an **opaque** escalation's receipt is byte-identical to a plain Tier C denial's — the pair is the vector, not either alone |
| `receipt/digests/` | `request_digest`, `response_digest`, `effective_contract_digest`, `entry_digest` against known bytes |
| `receipt/verify/` | With response; without response; tampered response; wrong key; **`signature_suite` disagreeing with the response's `signature.profile`** — [`core-model.md`](../../spec/core-model.md) §6 requires rejection, since one of the two is false and a verifier cannot tell which |
| `receipt/exclusion/` | Internal reason, step, and policy reasoning absent from every receipt. **Budget state removed from this list 2026-08-19** — there is none, and the capacity debit has left the receipt entirely |
| `receipt/audit/` | Audit contains the §4.3 delta; contains no answer plaintext |

## 7. Acceptance

- [ ] Both implementations produce **byte-identical** receipts for the same
      exchange facts.
- [ ] `response_digest` is computable before the receipt exists, and excludes the
      receipt and signature.
- [ ] `verify_receipt` without a response verifies everything except
      `response_digest`, and **reports which checks it skipped**.
- [ ] No receipt in any vector contains any §4.3 field.
- [ ] No audit event contains the answer plaintext or any private input.
- [ ] A deny receipt has five fields, no variable-length value, and constant
      length across causes.
- [ ] An explicit `escalate` carries a receipt; **no outcome is returned without
      one**.
- [ ] ~~An opaque escalation's receipt is byte-identical to a plain Tier C
      denial's~~ — **struck 2026-08-19**, deferred with
      [P-015](P-015-escalation-lifecycle.md).
- [ ] The audit store is **append-only**, and a test shows an event cannot be
      amended or removed.
- [ ] ~~Audit events are deleted at retention expiry, observably.~~ **Struck
      2026-08-19** — retention is deferred hardening. Restore before any real
      deployment.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| An internal rejection reason in a receipt | `receipt/exclusion/` finds it |
| A rejection step in a receipt | Same — it is a per-step oracle |
| Policy reasoning or authorities in a receipt | Same |
| Budget state in a receipt | Same; it reveals other requesters' activity |
| The answer plaintext in an audit event | `receipt/audit/` finds it |
| Private input anywhere in either | Review plus `receipt/audit/` |
| A deny receipt with a variable-length field | Length varies across causes; P-009 uniformity fails |
| **An opaque escalation's receipt carrying `decision_class: escalate`** | `receipt/escalate/` fails. The response bodies still match, so nothing else catches it |
| An `escalate` response returned with no receipt | `receipt/fields/` has no escalate case to check |
| `verify_receipt` silently checking less without a response | Result does not report the skipped check |
| An acknowledgment field populated | It is reserved; populating it asserts semantics that do not exist |
| Documentation calling a receipt proof of truth or proof of disclosure | Grep across artifacts |
| An audit store with no expiry | Retention configuration absent or unbounded |

Row 8 is subtle and worth a vector. A verifier that returns "valid" having
checked less than the caller assumes is more dangerous than one that returns an
error, because the caller acts on it.

## 9. Escalate-if-changed decisions

1. **`response_digest` excludes the receipt and signature.** Any other definition
   is circular.
2. **The §4.3 delta is the boundary between audit and receipt**, and is
   enumerated rather than judged case by case.
3. **Neither the receipt nor the audit contains private input.**
4. **The audit stores `response_digest`, not the answer.**
5. **Acknowledgment is reserved and unpopulated.**
6. **A deny receipt has no variable-length field.**
7. **`verify_receipt` reports what it could not check.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Does a rejected exchange write an audit event at all, or only one that reached policy?~~ | **Resolved: every exchange at or after step 9**, the same boundary [P-004](P-004-replay-idempotency.md) uses for caching. Before step 9 a request is unauthenticated or expired, and writing an audit event for it would let anyone fill a custodian's audit store from the network. From step 9 the requester is authenticated and the exchange is one the custodian chose to process, so it is one the operator needs a record of |
| ~~Is `policy_version` a version string or a digest of the effective rule set?~~ | **Resolved: a digest** of the effective rule set, computed at load. A version string is set by hand and can be left unchanged across a rule edit, which would make a receipt attest to a policy that no longer exists — and a receipt's value is precisely that it binds what was in force. The digest covers the composed rule set including which authorities are mandatory ([P-007](P-007-policy-engine.md) §4.4), because that determines the decision as much as the rules do |
| ~~Does the requester store its own audit event, or only the receipt?~~ | **Answered:** only the receipt. [P-012](P-012-requester-runtime.md) §4.7 |
| ~~What is the default retention period?~~ | **Resolved: none — it is required configuration**, and the daemon refuses to start without it ([P-013](P-013-https-binding.md) §4.6). Any default is wrong: a short one silently destroys evidence an operator needed, a long one silently accumulates a record of who asked what about whom, which [`claims.md`](../../spec/claims.md) already warns may itself be personal data. A deployment that has not chosen has not thought about it, and startup is where that is cheapest to discover |
| ~~Should `decided_at` be coarsened in the receipt to blunt timing correlation?~~ | **Resolved: no in MVP**, second precision, for the replay-window arithmetic reason. One answer, both places — [P-009](P-009-denial-normalization.md) §10 carries it |
| ~~**Does an `escalate` response carry a receipt?**~~ | **Resolved: yes**, the reduced shape with `decision_class: escalate` — but only for *explicit* escalation; an opaque one carries the ordinary deny receipt. [`core-model.md`](../../spec/core-model.md) §5.3; §4.1 amended |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | `Receipt` and `DenyReceipt` types | Deny type cannot hold an answer-side field |
| 2 | `build_receipt` from `ExchangeFacts` | `receipt/fields/` passes; open question 2 resolved |
| 3 | `response_digest` definition and computation | `receipt/digests/` passes; computable pre-receipt |
| 4 | `build_deny_receipt`, serving deny and both escalation modes | Five fields; constant length; feeds P-009 uniformity. One builder, with `decision_class` supplied by the caller — an opaque escalation must not be able to reach the `escalate` value, so the caller is [P-015](P-015-escalation-lifecycle.md)'s visibility verdict, never the internal reason |
| ~~4a~~ | ~~`receipt/escalate/` uniformity pair~~ | **Cut 2026-08-19** — tests the explicit/opaque split, deferred with [P-015](P-015-escalation-lifecycle.md). ~~Explicit carries `escalate`; opaque is byte-identical to a Tier C denial |
| 5 | `AuditEvent` type and the §4.3 delta | `receipt/audit/` passes; no answer plaintext |
| 6 | **Local append-only audit store** — *plain; encryption at rest deferred* | **Append-only enforced and observable.** Cut 2026-08-19 and **restored 2026-08-20**: `claims.md` Q2D-C-10 holds when the responder *retains detailed audit locally*, so a store is what the claim rests on. **Append-only is the load-bearing half** — an audit that can be rewritten attests to nothing. Encryption at rest is deferred as hardening, and restoring it is the first thing before any real deployment. ~~Encryption verified; append-only enforced |
| ~~7~~ | ~~Retention and deletion~~ | **Deferred 2026-08-19** — enterprise hardening rather than a property Q2D-C-10 rests on. **§4.7's argument stands and is why this is deferred rather than dropped**: an audit store with no expiry is an ever-growing record of who asked what about whom, and `claims.md` says receipts and logs may themselves be personal data. Synthetic fixtures do not have that problem; a deployment does, immediately. ~~Deletion observable; startup fails with no retention configured |
| 8 | `verify_receipt` including the skipped-check report | `receipt/verify/` passes both with and without a response |
| 9 | Author `receipt/` corpus section | **Four** groups; `harness lint` clean. `receipt/escalate/` goes with issue 4a |
| 10 | Claim-language audit across artifacts | No text describes a receipt as proof of truth or of disclosure |

Issue 1 blocks 2 and 4. Issue 3 blocks 2 — the digest definition must settle
before anything is built that depends on its value.
