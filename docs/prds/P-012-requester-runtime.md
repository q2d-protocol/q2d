# P-012 — Requester runtime

| Field | Detail |
|---|---|
| PRD | P-012 |
| Stage | 5 — the whole stage |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | low |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-002](P-002-message-envelope.md), [P-003](P-003-crypto-suites.md), [P-005](P-005-registry-client.md), [P-006](P-006-request-validation.md), [P-011](P-011-receipts-audit.md) |
| Blocks | P-013, P-015, P-016 |

---

## 1. Purpose

Build the other side of the exchange: construct and sign a query, verify a
response before anything reaches a caller, store the receipt, and hand back the
answer rather than the evidence.

Ten PRDs have built a responder. Nothing yet asks it a question, and
[`mvp-scope.md`](../mvp-scope.md) §1 item 7 — a Rust requester against a Go
custodian and the reverse — is not testable until something does.

**Claims served.** Q2D-C-01 (pre-evaluation commitment) directly;
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §3 names the requester
runtime as its trusted base, and this module is that runtime. Q2D-C-05 and
Q2D-C-06 are partly *enforced* here — [`claims.md`](../../spec/claims.md)
Q2D-C-06's "enforced by" line names requester-side verification before the
answer reaches the agent, and this PRD is where that happens. Q2D-C-07's
requester half — an identical retry — is honoured here.

**Q2D-C-12 is not claimed.** [`mvp-scope.md`](../mvp-scope.md) §4 previously
listed it as partial for this stage; that attribution has been removed and Stage
5 now claims Q2D-C-01 alone. §4.8 explains why the module builds the mechanism
and still cannot claim the property.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-1 | The complete must / must-not list for a core requester |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-10 | The containment class this module does **not** implement, and its compatibility mode |
| [`spec/conformance-classes.md`](../../spec/conformance-classes.md) CC-11 | Receipt verification without private source data |
| [`spec/core-model.md`](../../spec/core-model.md) §2.2–2.7 | Every field the query must carry and sign |
| [`spec/core-model.md`](../../spec/core-model.md) §2.4.1 | The entry digest the requester declares |
| [`spec/core-model.md`](../../spec/core-model.md) §2.5 | Coarsening permitted, expansion and subsetting prohibited |
| [`spec/core-model.md`](../../spec/core-model.md) §5.1, §5.2, §5.3 | The three response shapes, and what an `escalate` is |
| [`spec/core-model.md`](../../spec/core-model.md) §7 | Identical retry; what makes a request distinct |
| [`spec/core-model.md`](../../spec/core-model.md) §8 | A query binds core version, predicate version, registry digest, and profile |
| [`spec/crypto-suites.md`](../../spec/crypto-suites.md) §4 | The verifier's minimum acceptable policy — here the requester is the verifier |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-01 | The field set committed before evaluation |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-06 | Requester-side verification before the answer reaches the agent |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-12 | Conditional on `q2d-contained-runtime-0.1` |
| [`spec/terminology.md`](../../spec/terminology.md) §2 | Requester runtime and requester agent are different roles |
| [`spec/terminology.md`](../../spec/terminology.md) §5 | A requested profile is never silently downgraded |
| [`spec/terminology.md`](../../spec/terminology.md) §7 | Model context, evidence segregation, compatibility mode |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §2 | The requester runtime is untrusted for every source-side claim |
| [`docs/mvp-scope.md`](../mvp-scope.md) §2 | CC-10 is explicitly not built |

## 3. Module boundary

**Inside:** answer-contract construction; query assembly and issuance; the
response processing order; response verification against the requester's own
suite floor; receipt verification and storage; the semantic-answer projection;
idempotent retry; the requester's partial-failure behaviour.

**Explicitly outside:** serialization and the routing projection (**P-002**),
signing and verification primitives (**P-003**), manifest loading and pinning
(**P-005**), the per-shape narrowing rules — normative in
[`core-model.md`](../../spec/core-model.md) §3.2 and implemented by
(**P-006**) — receipt field
definitions and `verify_receipt` (**P-011**). This module composes those; it
reimplements none of them, and a second copy of any of them here is the
divergence this repository exists to prevent.

**Also outside:** capacity arithmetic. A requester asserts no debit and computes
none — [`claims.md`](../../spec/claims.md) Q2D-C-09 states that any debit a
requester asserts is ignored, so producing one would be dead weight that later
reads as authoritative. Escalation polling and pending tokens beyond the type
(**P-015**). Transport (**P-013**). Sink mediation, labelling, and the sink
inventory (**CC-10**, not built — §4.8).

## 4. Design

### 4.1 The runtime is not the agent, and in MVP there is no agent

[`terminology.md`](../../spec/terminology.md) §2 calls the distinction between
requester runtime and requester agent load-bearing. MVP builds only the runtime:
there is no MCP binding, no framework, and no model in the loop.

That has a consequence worth stating before the design rather than discovering
at review. **Evidence segregation cannot be demonstrated against a model that
does not exist.** What this module can do is make the boundary structural — the
caller-facing value carries no evidence and there is no accessor to any — so
that a later CC-10 runtime inherits a boundary rather than retrofitting one.
That is a property of this module's interface, and §4.8 is careful about what it
is not.

### 4.2 Building a query, and a local check that is not a control

The requester holds the same pinned manifest as a custodian, loaded through
[P-005](P-005-registry-client.md)'s client, and builds its contract against a
resolved entry. It declares that entry's digest
([`core-model.md`](../../spec/core-model.md) §2.4.1).

Before signing, it runs [P-006](P-006-request-validation.md)'s
`check_narrowing` against its own contract.

**This is not enforcement.** [`trust-matrix.md`](../../threat-model/trust-matrix.md)
§2 marks the requester runtime untrusted for Q2D-C-02, and the responder's check
is the only one that decides anything. The local check exists because the
alternative is worse for both parties: an over-broad contract returns a Tier C
denial ([P-009](P-009-denial-normalization.md) §4.1) that correctly tells the
requester nothing, so a requester without a local check learns only that
*something* was refused. Checking locally converts a silent denial into an
immediate, precise local error, and costs the custodian one fewer request.

Documentation and comments must not describe it as enforcing anything.

**Nonce and clock are injected, never ambient.**
[P-001](P-001-conformance-corpus.md) §4.3 requires every varying input to come
from the vector, and Ed25519 determinism is what makes the Stage 5 cross-
implementation comparison a byte comparison. A runtime that calls a clock or an
RNG internally cannot be pinned by a vector, so both are parameters of query
construction rather than calls inside it.

**So is the requester's own suite floor.** §6's `requester/verify/` group needs
a below-floor vector, and a requester's acceptable set is configuration rather
than anything in the response it is checking — the responder-side form of which
was [E-48](../open-escalations.md). It closed as `input.verifier`, described in
[P-001](P-001-conformance-corpus.md) §4.3, and the same key carries a
requester's configuration; this PRD does not need a second mechanism and should
not invent one. What `verifier` does **not** carry is accumulated state, which
matters for `requester/retry/`: *configuration is declared, history is
replayed*, and no mechanism for the second exists yet.

### 4.3 The response processing order

[`core-model.md`](../../spec/core-model.md) §4 is the responder's order. The
requester has its own, smaller one, and it is now **normative**:
[`core-model.md`](../../spec/core-model.md) §4.1 states it, and CC-1 requires it.
This section implements that order and adds the two steps §4.1 leaves to a
runtime — the assurance-profile check and projection.

The reason it became normative rather than staying derived here: CC-1's
obligations are a set, not a sequence, so two requesters could satisfy every one
of them while one parsed attacker-controlled bytes before authenticating them.
A corpus vector cannot assert an order the model does not state.

| # | Step | Why here |
|---|---|---|
| 1 | Parse the envelope under the [P-002](P-002-message-envelope.md) §4.8 limits | Before allocation on remote-controlled bytes |
| 2 | Read the declared suite; reject below the **requester's own** floor | The floor is local configuration, never message-derived |
| 3 | Resolve the responder key; verify over the exact bytes | Nothing below this line runs for an unauthenticated response |
| 4 | Parse the verified response object | Parser sits outside the security boundary, as on the responder side |
| 4a | Confirm the header's `suite` and `key_id` equal the payload's `signature.profile` and `signature.key_id` | [`core-model.md`](../../spec/core-model.md) §4 response step 4a (E-32). The header is untrusted; the payload's copies are authoritative |
| 5 | Confirm the receipt binds the request digest of the query actually sent | The Stage 5 gate |
| 6 | Confirm the assurance profile is the one requested | [`terminology.md`](../../spec/terminology.md) §5 — a downgrade is a rejection |
| 7 | Confirm the result conforms as far as §4.5 permits | Integrity check, not a control |
| 8 | Project (§4.4) | The first point at which anything reaches a caller |

Steps 1–4 are P-003's four-step sequence applied to a response; this module
supplies the policy and calls it. A requester that verifies with parameters the
response declared has the same bug P-003 §4.2 exists to prevent, on the other
side of the wire.

### 4.4 An answer is constructible only by verification

```
verify_response(...) -> VerifiedResponse        // the only producer
project(VerifiedResponse) -> Outcome            // the only consumer
Outcome = Answer | Denied | Pending             // closed
```

`Answer` has **no public constructor and no accessor to the response, the
receipt, the signature, or any key material.** CC-1's *"verify response
signatures before exposing an answer"* therefore becomes a fact about what
compiles, in the same way [P-010](P-010-responder-pipeline.md) §4.1's capability
token makes *"no private input before step 16"* one.

`Outcome` being closed is the other half. CC-1's *"must not treat an `escalate`
pending token as an answer"* holds because there is no coercion between the
variants — a caller that wants an answer must handle the other two to get at it.

How the no-accessor property is enforced is language idiom and belongs in
`CONVENTIONS-{rust,go}.md`, not here. The property does not.

### 4.5 What a requester can actually validate about a result

Less than it looks, and the reason is structural.

[`core-model.md`](../../spec/core-model.md) §5.1 returns
`effective_contract_digest` — a digest, not the contract. The effective domain is
the narrowing composition of the registry entry, the requester's contract, and
policy modifiers, and **the requester never sees the modifiers.** So it cannot
reconstruct the effective domain, cannot recompute the digest, and cannot check
membership of the result in the domain that actually bounded it.

This is a deliberate boundary, not an oversight —
[`core-model.md`](../../spec/core-model.md) §4.1 now says so in the specification
rather than leaving it to be inferred here. Open question 2 records why the
response does not carry the effective domain.

Worse, membership in the *requested* domain is not implied either. A modifier
coarsens ([`terminology.md`](../../spec/terminology.md) §6), and a value
coarsened past what the requester asked for is a member of a set the requester
never named — a four-hour band where it requested two-hour bands.

So step 7 checks only what is well-defined without the modifiers:

- the release shape equals the shape the contract declared;
- the result is not **finer** than the contract requested — precision,
  granularity, and cardinality at or below the requested bound.

The asymmetry is the point. Coarser than requested is a policy narrowing and is
expected. Finer than requested is more disclosure than the contract permitted,
which is the only direction that matters.

Two limits, stated rather than left to be found:

**`enum` is checkable, because the requester declared the mapping.**
[`core-model.md`](../../spec/core-model.md) §3.2 puts the coarsening in
`answer_contract.coarsening`, so a requester holds the label set it asked for
and can test membership directly — the result must be one of its own labels.
That was not true while the mapping was inferred: the answer carried labels from
a mapping the responder applied and the requester never saw, so there was no
membership test and the check degraded to shape identity. **E-17 removed that
degradation**, which was the downstream consequence this section recorded when
it was still open.

**"Finer than requested" is a directional comparison, and that is now what the
model describes.** [`core-model.md`](../../spec/core-model.md) §3 previously
wrote the effective domain as `registry ∩ contract ∩ modifiers`, which has no
set-theoretic reading across granularities — two-hour bands do not intersect
four-hour bands. §3 now states **narrowing composition** and §3.2 carries the
per-shape rules normatively, so this check being directional is consistent with
the model rather than a workaround for it.

**This is an integrity check, not a security control.**
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §2 makes the computation
executor trusted for Q2D-C-03; a requester cannot verify bounded output and no
text here may suggest it can. What the check catches is a responder that
disagrees with its own registry entry — a divergence, which is exactly what this
project's two implementations exist to surface.

Open question 2 records what it would take to close the gap properly, and why
that is a specification change rather than a decision for this PRD.

### 4.6 A retry resends bytes; nothing is ever re-issued

[`core-model.md`](../../spec/core-model.md) §7 makes an identical retry — same
signed `query_id` and `nonce` — return the cached outcome without a second
debit. Identical means byte-identical, so the runtime stores the exact envelope
bytes it sent and resends those. **There is no re-signing path**, mirroring
[P-004](P-004-replay-idempotency.md) §4.5's rule that the responder caches
response bytes rather than decisions.

**The runtime never reissues a query with a fresh nonce on its own** — not on
expiry, not on a denial, not on a timeout.

This is the requester-side security decision in this PRD. A retry loop that
mints a new nonce when the old request expires turns one caller-visible question
into an unbounded series of distinct exchanges, each independently decided and
independently debited. That is an adaptive-probing engine assembled by accident,
against a claim — Q2D-C-09 — whose "fails if" line already names repeated
querying, and whose `conformance/adaptive-probing` test exists to catch exactly
this shape.

An expired or unanswered query returns a distinct local outcome. Asking again is
the caller's decision, made once, visibly.

### 4.7 Receipts, and why there is no second audit store

The runtime verifies the receipt through [P-011](P-011-receipts-audit.md)'s
`verify_receipt` and stores it. That closes [P-011](P-011-receipts-audit.md)
§10's question about whether a requester keeps its own audit event:

> **It does not.** The receipt already binds every field a requester-side audit
> event would carry, and a second store would duplicate that content while
> creating a second retention obligation over what
> [`claims.md`](../../spec/claims.md) already warns may itself be personal data.

The runtime retains, beyond the receipt, only what idempotent retry needs: the
sent envelope bytes and the outcome, for the life of the query's validity
window.

**The response is not retained by default.** The same reasoning as
[P-011](P-011-receipts-audit.md) §4.4, applied on this side: the answer has
already been delivered to the caller, so a second copy adds no capability and
creates an obligation. The cost is real and is not hidden — `verify_receipt`
without a response verifies everything except `response_digest`, and reports
which check it skipped rather than quietly checking less. Retention of responses
is configurable for deployments that want full later verification, and it is off
unless chosen.

Receipt retention is configured, with no default. An unbounded receipt store is
a growing record of what this requester asked about whom.

### 4.8 Sinks are declared, not enforced — and Q2D-C-12 is not claimed

`delivery.permitted_sinks`, `delivery.model_endpoint`, and
`purpose.requested_retention` are constructed, signed, and bound into the
receipt. **This module enforces none of them.** No sink is mediated, no value is
labelled, no inventory exists.

That is not an omission; [`mvp-scope.md`](../mvp-scope.md) §2 defers CC-10
deliberately, and [`conformance-classes.md`](../../spec/conformance-classes.md)
CC-10's compatibility mode says what such a deployment may say about itself: a
bounded authenticated answer from a participating custodian, and **not**
answer-derived flow restricted to permitted sinks.

Q2D-C-12 sits under `claims.md`'s heading *"Requester-side claims — conditional
… these hold only under the `q2d-contained-runtime-0.1` profile"*, and CC-10's
must-list includes the sink inventory and mediation this module does not build.
By [`conformance-classes.md`](../../spec/conformance-classes.md)'s honesty rule,
a class is claimed only when every check passes — so this module implements the
segregation *mechanism* (§4.4) and claims the *property* not at all. In
`claims.md`'s own vocabulary it is a design intention.

[`mvp-scope.md`](../mvp-scope.md) §4 previously attributed *"Q2D-C-12 (partial —
evidence segregation without full sink mediation)"* to this stage. **That
attribution has been removed.** "Partial" is not a state
[`claims.md`](../../spec/claims.md) defines: a claim holds under its conditions
or it is a design intention, and a qualifier in a stage table does not survive
being copied into a coverage summary.

Stage 5 claims **Q2D-C-01** — pre-evaluation commitment, requester-side,
unconditional, owned by CC-1, and genuinely demonstrated here. It claims nothing
else. The alternative considered and declined was splitting Q2D-C-12 into an
unconditional and a conditional half; the value of that claim is the
sink-mediation half, and a claim carrying the easy half under a name a reader
takes for the whole is worse than no claim.

### 4.9 Partial failure

| Interrupted after | State | Resolution |
|---|---|---|
| Signed, never sent | No exchange occurred | Bytes discarded or resent unchanged; never re-signed |
| Sent, no response | **Unknown** — may or may not have debited | Resend the same bytes; the responder's cache decides. Never a fresh query |
| Response received, verification fails | Nothing exposed | Local failure; the response is discarded and never partially projected |
| Verified, receipt storage fails | Answer verified but unrecorded | Fail the exchange to the caller. A requester that cannot record what it received should not act on it |
| Verified, projection succeeded, caller crashes | Answer delivered | Out of scope — [`scope.md`](../../spec/scope.md) §8: a released answer cannot be retracted |

Row 2 is the one that matters. The safe response to an unknown outcome is the
identical bytes, because that is the only form of retry the protocol makes
free.

## 5. Interfaces

```
build_contract(entry: Entry, request: ContractRequest) -> Result<AnswerContract>
build_query(parts: QueryParts, nonce: Nonce, now: Timestamp) -> Result<CoreObject>
issue(core: CoreObject, key: PrivateKey, suite: SuiteId) -> Result<IssuedQuery>

verify_response(bytes, sent: IssuedQuery, policy: SuitePolicy, keys)
    -> Result<VerifiedResponse>
project(v: VerifiedResponse) -> Outcome            // Answer | Denied | Pending

retry_bytes(sent: IssuedQuery) -> bytes            // the stored bytes; no re-signing
store_receipt(v: VerifiedResponse, store) -> Result<ReceiptHandle>
evidence(handle: ReceiptHandle, store) -> Result<Receipt>
```

`verify_response` taking the `IssuedQuery` is deliberate: the receipt-binding
check of §4.3 step 5 has no parameterless form and therefore no path that
skips it. The same device as [P-005](P-005-registry-client.md)'s `resolve`
taking the declared digest.

`IssuedQuery` owns the exact bytes. `retry_bytes` is the only way to send
anything twice, and it cannot produce different bytes because it holds no key.

`evidence` is separate from `project` and takes a handle, so obtaining a receipt
is an explicit act rather than something that arrives attached to an answer.

`SuitePolicy` is the requester's own, constructed from local configuration —
[P-003](P-003-crypto-suites.md) §5's rule, and the response is the message it
must never be derived from.

## 6. Corpus sections

`requester/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `requester/contract/` | Construction per shape; expansion and subset attempts rejected locally |
| `requester/sign/` | Byte-identical signed query for a fixed key, nonce, and clock |
| `requester/verify/` | Valid; below-floor suite; bad signature; unresolvable responder key; tampered result; **header/payload suite mismatch and key-id mismatch**, each rejected at step 4a; and a response whose `receipt.signature_suite` differs from its `signature.profile`, rejected at step 7 ([`core-model.md`](../../spec/core-model.md) §6) |
| `requester/receipt/` | Receipt binds the request sent; a receipt binding another request rejects; verification without a stored response reports the skipped check |
| `requester/outcome/` | All three statuses; `escalate` unreadable as an answer; a denial carrying no cause; **an `external_reason` outside [`core-model.md`](../../spec/core-model.md) §5.2.1's vocabulary**, which is an opaque rejection rather than a malformed response — a requester that errored instead would break on the first value a later version adds |
| `requester/profile/` | Requested profile returned passes; a lower profile rejects |
| `requester/retry/` | Retry bytes identical to the original; expiry produces a local outcome, not a new query |
| `requester/order/` | The [`core-model.md`](../../spec/core-model.md) §4.1 order: a response failing at each step is rejected without the later steps having run, and nothing reaches the caller before step 9 |

`requester/sign/` is the Stage 5 cross-implementation gate. It is a byte
comparison for the reason [P-001](P-001-conformance-corpus.md) §4.3 gives, which
is also why §4.2 injects the nonce and the clock.

## 7. Acceptance

- [ ] Both implementations produce **byte-identical** signed queries for every
      `requester/sign/` vector.
- [ ] Each implementation's requester query verifies in the other's responder,
      and each verifies the other's response. **This is
      [P-001](P-001-conformance-corpus.md) issue 19**, not the `harness cross`
      that exists today — that one compares what two runners each produced,
      which exercises both signers and neither verifier.
- [ ] No path exists from response bytes to an `Answer` that skips verification
      — asserted by the type, not by a test.
- [ ] A response below the requester's suite floor, with a failing signature, or
      with a receipt binding a different request, is rejected by both. This is
      the Stage 5 gate, stated in [`mvp-scope.md`](../mvp-scope.md) §4.
- [ ] An assurance profile below the one requested is rejected, with no path that
      accepts it.
- [ ] A result finer than the contract requested is rejected by both, identically.
- [ ] A retry emits bytes identical to the original, and a responder budget total
      is unchanged across one query and that query retried.
- [ ] Two runs of every vector produce identical output — no ambient clock, no
      ambient RNG.
- [ ] Receipt retention is configured, and startup fails when it is not.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| An unverified response reaching a caller | No constructor for `Answer` outside `verify_response` |
| An `escalate` read as an answer | `Outcome` is closed; no coercion exists |
| A response accepted below the requester's suite floor | `requester/verify/` below-floor vector returns an answer |
| A `SuitePolicy` derived from the response | No constructor accepts message-derived input; interface shape plus review |
| A receipt binding a different request accepted | `requester/receipt/` mismatch vector returns an answer |
| A silently accepted profile downgrade | `requester/profile/` returns a profile the query did not request |
| A result finer than requested accepted | `requester/verify/` over-precise vector |
| **Any §4.1 step running before the signature verifies** | `requester/order/` — a response with a malformed body and a bad signature is rejected on the signature, not the parse |
| An unrecognized status mapped onto a default | `requester/outcome/` unknown-status vector produces an answer or a denial instead of a hard rejection |
| An unrecognized `external_reason` treated as a malformed response | `requester/outcome/` unknown-reason vector errors instead of reporting a denial |
| **Re-signing on retry** | Two retries of one query differ in any byte |
| **Automatic reissue with a fresh nonce** | Responder budget total rises across what the caller saw as one question |
| Inferring a denial cause | Any code path on the denial branch that reads elapsed time, response size, or arrival latency |
| An ambient clock or RNG in query construction | Two runs of a vector differ |
| Evidence reachable from a projected answer | An accessor exists from `Answer` to receipt, signature, or key material |
| A second requester-side audit store | Present at all — §4.7 |
| Any text claiming containment, sink enforcement, or Q2D-C-12 | Grep across code, comments, and docs for the compatibility-mode boundary |

Rows 8 and 9 are the two this module is most likely to get wrong, because both
are what a helpful library would do. A retry helper that re-signs "to refresh
the timestamp" and a client that transparently reissues an expired query are
both ordinary engineering instincts, and both defeat a claim.

Row 10 is subtler. The wire carries no cause, so there is nothing to read — but
a client that times denials and branches on the result has rebuilt the oracle
[P-009](P-009-denial-normalization.md) closed, on the only side that can still
observe [`trust-matrix.md`](../../threat-model/trust-matrix.md) §5's residual
channels.

## 9. Escalate-if-changed decisions

1. **`Answer` is constructible only by successful verification**, and `Outcome`
   is closed.
2. **No accessor from a projected answer to any evidence.** Obtaining a receipt
   is an explicit call against a handle.
3. **A retry resends stored bytes.** There is no re-signing path.
4. **The runtime never reissues a query on its own** — not on expiry, denial, or
   timeout.
5. **The requester's suite floor is local configuration**, never derived from a
   response.
6. **The local narrowing check is convenience, not control.** Q2D-C-02 is
   responder-owned and stays that way.
7. **Nonce and clock are injected**, so every vector is reproducible and the
   cross-implementation comparison stays a byte comparison.
8. **The receipt is stored; the response is not, by default; there is no second
   audit store.**
9. **Sinks are declared and unenforced, and Q2D-C-12 is not claimed** until
   CC-10 exists.
10. **The response processing order is [`core-model.md`](../../spec/core-model.md)
    §4.1's**, not this module's. Reordering it is a spec change.

## 10. Open questions

| Question | Belongs to |
|---|---|
| **1.** ~~[`mvp-scope.md`](../mvp-scope.md) §4 attributes "Q2D-C-12 (partial)" to Stage 5, against `claims.md` and CC-10's honesty rule~~ | **Resolved.** `mvp-scope.md` §4 Stage 5 now claims **Q2D-C-01 only**; the C-12 attribution is removed and §4.4's boundary is a design intention with no passing test. Splitting C-12 was considered and declined — see §4.8. Note the resolution is narrower than this question proposed: Q2D-C-01 *is* requester-side and unconditional, so "claim nothing requester-side" would have overshot |
| **2.** ~~A requester cannot validate a result against the effective domain, because §5.1 carries only its digest (§4.5)~~ | **Resolved: do not add it in 0.1.** Q2D-C-03 is a responder claim resting on a trusted executor, so an echoed domain is as forgeable as the result and buys nothing against the adversary that matters. It would also disclose *which* modifier policy applied — a policy map assembled from successful answers rather than from probing denials, which is the channel Q2D-C-08 exists to keep closed. [`core-model.md`](../../spec/core-model.md) §4.1 now records the boundary; the shape is kept for a later profile with an attested executor |
| **2a.** ~~[`core-model.md`](../../spec/core-model.md) §3 states the effective domain as a set intersection, but §2.5 permits coarsening~~ | **Resolved.** §3 states **narrowing composition**, and §3.2 carries the per-shape rules **normatively in `spec/`** — they were briefly delegated to [P-006](P-006-request-validation.md) §4.5, which put protocol surface in a PRD and was corrected. P-006 now implements §3.2 and defines nothing |
| **3.** ~~Does the requester pin its own manifest independently, and how does it learn a custodian's differs?~~ | **Resolved: it pins independently, and it does not learn.** The entry-digest check only means anything because the two copies were obtained independently ([`core-model.md`](../../spec/core-model.md) §2.4.1) — a channel telling the requester which digest the custodian holds would collapse that, and would be a probe for what a custodian has accepted. So a mismatch surfaces as an opaque Tier C denial, indistinguishable from a policy refusal, and the operator resolves it out of band. **The operability cost is real and is documented in the quickstart** rather than mitigated: a requester and custodian on different manifest versions fail in a way neither can diagnose from the wire, and that is the price of the check not being a discovery endpoint |
| **4.** ~~Should §4.3's response processing order be normative in `core-model.md` rather than derived here from CC-1?~~ | **Resolved: yes.** [`core-model.md`](../../spec/core-model.md) §4.1 states it, kept minimal — the orderings whose violation is a vulnerability, not every action a runtime performs. CC-1's must and must-not lists now reference it, so a corpus vector can assert it |
| **5.** ~~Where does the requester's signing key live, and how is delegation evidence assembled?~~ | **Answered:** a permission-checked key file, and a self-issued delegation signed by the principal key. [P-014](P-014-identity-pairing.md) §4.4, §4.6 |
| **6.** ~~Does the caller see the capacity the answer will cost, before asking?~~ | **Resolved: yes, as read-only registry data.** The runtime exposes the entry's `disclosure_capacity_millibits` so a caller can decide whether a question is worth asking. It is a **lookup, not a prediction** — the responder computes the real debit from the effective domain after modifiers it never shows ([P-006](P-006-request-validation.md) §4.1), so the displayed value is an upper bound on an unmodified request and nothing more. It never travels in a query: Q2D-C-02 makes any requester-asserted debit non-conforming, and the type carrying it is not the type `build_query` accepts |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | ~~Escalate open question 1~~ — **done** | Resolved; `mvp-scope.md` §4 Stage 5 amended to claim Q2D-C-01 only; §4.8 cites the outcome |
| 2 | `IssuedQuery` and the stored-bytes model | No path produces a second signature for one query |
| 3 | `build_contract` over a resolved entry, with the local narrowing check | `requester/contract/` passes; comments describe it as convenience |
| 4 | `build_query` with injected nonce and clock | Two runs of a vector are identical; no ambient call exists |
| 5 | `issue` over [P-003](P-003-crypto-suites.md)'s `sign` | `requester/sign/` byte-matches across implementations |
| 6 | `verify_response`, steps 1–7 of §4.3 | `requester/verify/`, `requester/receipt/`, `requester/profile/` pass; **the order matches [`core-model.md`](../../spec/core-model.md) §4.1**, asserted by an ordering vector rather than by review |
| 7 | The §4.5 directional conformance check | Finer-than-requested rejects; coarser passes; both implementations agree |
| 8 | `Outcome`, `Answer`, and the no-accessor property | No accessor exists in either language; recorded in `CONVENTIONS-{rust,go}.md` |
| 9 | `project` and the caller-facing surface | `requester/outcome/` passes; nothing reaches a caller before §4.1 step 9 |
| 10 | Receipt store with retention, response retention off by default | Startup fails with no retention configured; skipped-check report surfaces |
| 11 | `retry_bytes` and the no-reissue rule | `requester/retry/` passes; responder budget unchanged across a retry |
| 12 | Author `requester/` corpus section | Seven groups; `harness lint` clean |
| 13 | Cross-implementation exchange | Rust requester ↔ Go custodian and the reverse, under `harness cross` |
| 14 | Claim-language audit | No artifact claims containment, sink enforcement, or Q2D-C-12 |

Issue 2 blocks 5 and 11. Issue 13 is the first time
[`mvp-scope.md`](../mvp-scope.md) §1 item 7 is testable, and it is the reason
this stage exists.
