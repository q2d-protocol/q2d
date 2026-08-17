# P-015 — Escalation lifecycle

| Field | Detail |
|---|---|
| PRD | P-015 |
| Stage | 7 — the last MVP item |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | **high** — the most intricate semantics in the protocol; the timing property in §4.1 fails a stopwatch rather than a test |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-004](P-004-replay-idempotency.md), [P-007](P-007-policy-engine.md), [P-008](P-008-capacity-accounting.md), [P-009](P-009-denial-normalization.md), [P-010](P-010-responder-pipeline.md), [P-012](P-012-requester-runtime.md), [P-013](P-013-https-binding.md) |
| Blocks | P-016 |

---

## 1. Purpose

Implement what happens when a policy authority must decide before release: both
escalation modes, the grant an approval records, and the fresh-query
revalidation that turns an approval into an answer.

[P-007](P-007-policy-engine.md) can already return `escalate` and
[P-009](P-009-denial-normalization.md) already decides whether that outcome is
visible. Neither owns what happens next, and what happens next is where the
protocol's hardest semantics live.

**Claims served.** Q2D-C-07, extended: [`claims.md`](../../spec/claims.md) makes
an identical retry return the cached outcome, and
[`core-model.md`](../../spec/core-model.md) §5.3 extends that to the case that
matters most — a retry must never become an answer after an approval. Q2D-C-08
depends on this module too: opaque escalation is only normalized if it is
indistinguishable from every other Tier C outcome, **including in latency**
(§4.1).

**Four of this PRD's questions were open in `spec/` rather than here, and are
now decided.** Grant multiplicity is single-use (§4.5), an explicit `escalate`
carries a receipt while an opaque one does not distinguish itself (§4.1), §7's
distinctness clause is a floor rather than a description (§4.6), and the poll
stays a bearer token with the weakness recorded in the threat model (§4.2). The
approval-scope **field list** and **grant lifetime** remain parked in
[`core-model.md`](../../spec/core-model.md) §9; §4.6 explains how this module
builds against a parked value without settling it.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §5.3 | Both modes; the four-step opaque sequence; the residual oracle, named |
| [`spec/core-model.md`](../../spec/core-model.md) §7 | Idempotency; what makes a request distinct even when the approval scope matches (§4.6) |
| [`spec/core-model.md`](../../spec/core-model.md) §9 | **Still parked:** the approval-scope digest field list, and grant lifetime |
| [`spec/core-model.md`](../../spec/core-model.md) §9.1 | `deny` and `escalate` do not debit; a required rate limit bounds probing. [P-008](P-008-capacity-accounting.md) §4.7 |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 14 | Escalation is a policy outcome, produced where policy is evaluated |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-07 | The retry guarantee this module must not break |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-08 | Normalization, and the channels it does not close |
| [`spec/claims.md`](../../spec/claims.md) Q2D-NC-05 | Timing and state channels remain — §4.9 |
| [`spec/terminology.md`](../../spec/terminology.md) §6 | Explicit escalation, opaque escalation, approval-scope digest, residual oracle |
| [`threat-model/trust-matrix.md`](../../threat-model/trust-matrix.md) §5 | The unavailable-to-answer transition is already a named residual |

## 3. Module boundary

**Inside:** the pending record and its token; the poll outcome; the grant, its
lifetime, and its consumption; approval-scope digest computation; the
out-of-band approval mechanism; the fresh-query path and what it revalidates.

**Explicitly outside:** deciding to escalate (**P-007**). Deciding whether an
escalation is visible (**P-009** §4.6) — this module receives that verdict.
Response caching and the verbatim-retry guarantee (**P-004** §4.5), which this
module relies on and must not reimplement. Transport shape of the poll endpoint
(**P-013** §4.5). Budget arithmetic (**P-008**).

**Also outside:** authenticated push delivery.
[`core-model.md`](../../spec/core-model.md) §5.3 permits a binding to define it;
[P-013](P-013-https-binding.md) does not, and adding it in MVP would replace the
residual oracle §4.9 names with a different one that has had no analysis.

## 4. Design

### 4.1 Two modes, and the one that must not wait

The mode is a policy input ([P-009](P-009-denial-normalization.md) §4.6),
defaulting to opaque.

**Opaque escalation returns its normalized response immediately and prompts the
authority asynchronously.** This is the single most important rule in this PRD
and the easiest to get wrong, because waiting is the natural implementation: the
authority is being asked a question, so hold the request until they answer.

Holding it defeats Q2D-C-08 completely. A Tier C denial that arrives in
milliseconds and one that arrives after four minutes are trivially
distinguishable, and the slow one means *a human was asked* — which reveals that
a relationship, a record, or an applicable policy path exists. That is precisely
the disclosure explicit escalation exists to make deliberately, arriving by
accident through latency.

So the response is constructed and returned at step 14's outcome, and the prompt
is dispatched afterwards on a path that cannot delay it.
[P-009](P-009-denial-normalization.md) §4.7's rule against adding gratuitous
timing differences is the general form; this is the specific case that would
break the claim outright.

**Explicit escalation** returns `status: escalate` with a pending token, and is
a deliberate disclosure. [`core-model.md`](../../spec/core-model.md) §5.3 is
emphatic that it **must never be described as denial-normalized**, and no
artifact in this module may do so.

**Both modes now carry a receipt, and the difference between them is the trap.**
Q2D-C-10 binds every exchange, so an escalated exchange that produced no evidence
it happened was an unstated exception to the claim
([P-011](P-011-receipts-audit.md) §4.1, amended).

| Mode | Response | Receipt |
|---|---|---|
| **Explicit** | `status: escalate`, token, `expires_at` | Reduced shape, `decision_class: escalate` |
| **Opaque** | The §5.2 normalized envelope | The **ordinary deny receipt** — same fields, same class, same bytes |

An opaque escalation carrying `decision_class: escalate` would defeat Q2D-C-08
through the evidence attached to a response the wire had made uniform, and
[P-009](P-009-denial-normalization.md)'s response-body uniformity check would
still pass. The value comes from the visibility verdict this module receives, not
from the internal reason — so there is no code path by which an opaque
escalation can reach it.

### 4.2 Explicit escalation: the token and its lifecycle

| Property | Value |
|---|---|
| Content | None. Encodes no `query_id`, principal, or predicate |
| Entropy | **Minimum 128 bits**, from a cryptographic source — the same floor [`freshness.md`](../../spec/freshness.md) §3 sets for the nonce, and for the same reason: it is the only thing standing between a guesser and the outcome. **The parallel stops at one place**: a nonce is the requester's and a responder can only check its length, where this token is the *responder's own* — so here the entropy requirement is on the party that also builds the check, and is enforceable rather than assumed |
| Encoding | base64url, unpadded, fixed length |
| Under the corpus | **Supplied by the vector**, never generated. [P-001](P-001-conformance-corpus.md) §4.3 — a token the runtime invents appears inside a signed response, so two implementations would produce different bytes for one vector and the comparison would fail on entropy rather than on behaviour |
| Lifetime | The `expires_at` on the escalate response |
| Polling | Does not extend the token, does not re-evaluate, does not debit |
| Poll response | Undecided, expired, or unknown → a **poll status object**, identical across all three. Decided → a **poll outcome object** stating approved or refused. Neither carries a receipt, and **neither is an answer** — an approval is a grant, and the answer comes from a fresh revalidated query ([P-013](P-013-https-binding.md) §4.5, §4.4 here) |
| Retry of the original query | Returns the cached escalate response verbatim, same token ([P-004](P-004-replay-idempotency.md) §4.7) |

**The token is a bearer capability in MVP, and that is a real weakening worth
naming.** The endpoint authenticates nobody, so anyone holding the token learns
**whether an authority approved or refused** — which reveals that a relationship
exists, that a human was asked, and how they decided.

It does **not** hand over the answer. A poll returns a decision, never a release
(§4.4): the answer requires a fresh query signed by the requester's key, which a
token holder does not have. That bounds the disclosure without excusing it —
"this person agreed to tell them" is often the sensitive part, and it is exactly
what explicit escalation is meant to disclose *to the requester* and to nobody
else.

Mitigations are entropy, a short lifetime, and TLS, which reduce exposure without
changing the shape.

The right long-term answer is a **signed poll**: a small message type carrying
the token under the requester's signature, so the outcome is released only to
the principal that asked. That is a core-model addition rather than a binding
detail, which is why MVP does not improvise one. **Resolved: bearer token in
MVP**, and it resolves [P-013](P-013-https-binding.md) open question 7.

The weakness is now recorded in
[`trust-matrix.md`](../../threat-model/trust-matrix.md) §5 as a residual channel,
not only here. A bearer capability on the consent path disclosed solely in an
implementation document is disclosed in the wrong place: the threat model is
where someone deciding whether to trust the protocol looks, and a named
limitation is worth more than one a reader finds for themselves.

**A poll never constructs a receipt**, and the reason is worth stating because
the alternative looks reasonable. Q2D-C-10 binds every exchange to a receipt, so
attaching one to a poll seems consistent — until an *unknown* token arrives,
which has no originating query, no request digest, and therefore nothing a
receipt could truthfully bind. Signing one anyway would attest to an exchange
that never happened. So a decided poll returns evidence that already exists, an
undecided one returns an object that binds nothing, and
[`core-model.md`](../../spec/core-model.md) §6 says a poll is not a response to a
query.

Token expiry does not destroy a grant. The two have different clocks and
different jobs: the token addresses *this exchange*, the grant addresses *this
approval scope*. A requester whose token expired submits a fresh query, exactly
as an opaque-mode requester would.

### 4.3 Opaque escalation: what the requester is actually left with

[`core-model.md`](../../spec/core-model.md) §5.3's four steps describe the
responder's side. The requester's side deserves stating plainly, because it is
the operational cost of the mode and it is not written down anywhere.

The requester receives a Tier C denial. It has no token, no signal, and no way
to distinguish *refused permanently* from *a human is being asked right now*. If
an approval is recorded an hour later, **nothing tells the requester.** The only
way to discover it is to submit a fresh query and see.

Two consequences follow, and they compose with decisions already made:

- **A speculative re-ask cadence is an adaptive probing strategy.** Each attempt
  is a full exchange with its own policy decision, and on success its own debit.
- **[P-012](P-012-requester-runtime.md) §4.6 forbids the runtime from
  reissuing on its own.** So in MVP a re-ask is always a deliberate act by the
  caller, never a background loop. That is the correct behaviour and it is also
  why the Stage 7 demonstration needs a human to ask twice.

This is inherent to the mode rather than a gap in the implementation. The
alternative — telling the requester an escalation is pending — *is* explicit
escalation, and it is available where a deployment finds that disclosure
acceptable.

### 4.4 The grant is a policy input, never a bypass

On approval the responder records a time-bounded grant keyed to the
approval-scope digest. When a matching fresh query arrives,
[`core-model.md`](../../spec/core-model.md) §5.3 step 4 requires revalidation of
registry state, delegation, policy, freshness, budget, and current data before
answering, with a new receipt.

So the grant is **a fact supplied to policy**, not a stored decision:

```
grant_lookup(scope_digest, now) -> Option<GrantRef>     // reports; decides nothing
```

The same shape as [P-008](P-008-capacity-accounting.md) §4.6's `Exhausted`
verdict — the module reports, [P-007](P-007-policy-engine.md) decides. A grant
that short-circuited the pipeline would be an answer cached under a different
name, and the Stage 7 gate exists to catch exactly that: *a fresh query with a
matching approval-scope digest is revalidated end to end rather than served from
the grant.*

Two properties fall out of this shape rather than needing enforcement:

- **A revoked authority overrides a grant.**
  [`AGENTS.md`](../../AGENTS.md)'s fifth domain names the case — a grant
  recorded while the authority that permitted it was concurrently revoked.
  Because policy runs fresh and the grant is only an input,
  [P-007](P-007-policy-engine.md) §4.4's most-restrictive composition denies
  regardless of the grant. No special case is needed, and none may be added.
- **A revoked predicate, an exhausted budget, or stale data all still refuse.**
  Every step revalidates.

**Cross-PRD amendment.** [P-007](P-007-policy-engine.md) §4.2's `PolicyInput`
carries no grant field and needs one. It is policy state rather than
private-derived data, so §4.1's invariant is untouched — but the contract
changes, and the change belongs to P-007.

**Applied.** [P-007](P-007-policy-engine.md) §4.2 now carries the field. Because
grants are single-use (§4.5), it reports an *unconsumed, unexpired* match, and
consumption is a release-time act rather than a policy-time one — policy reads
it, and nothing in [P-007](P-007-policy-engine.md) may consume it.

### 4.5 One approval is one answer

**Resolved: a grant is single-use.**
[`core-model.md`](../../spec/core-model.md) §5.3 now says so — it is consumed by
the first release made under it, and a second fresh query in the same window
escalates again.

The reading that lost was multi-use-within-the-window, and it is worth recording
why, because it is the more convenient one:

| Reading | One approval authorizes |
|---|---|
| **Single-use** — adopted | One answer |
| Multi-use within the window | Any number of answers until the window closes, throttled only by the budget |

The test is what an approval interface can truthfully say. A prompt can say
*"tell them whether the room is free on Thursday."* No prompt can convey *"and
every repetition of this question for the next hour"* to a person deciding in a
moment. Under multi-use, the disclosure one approval authorizes would be bounded
by Q2D-C-09's capacity accounting rather than by the consent — and that
accounting was never intended to be the thing bounding how much a single
approval discloses.

A deployment that genuinely wants standing permission expresses it as a **policy
rule**, where [P-007](P-007-policy-engine.md) evaluates it, the audit records it,
and it is visible as a rule rather than as the residue of a prompt somebody
answered once.

The cost is real and is the safe direction to fail in: a transient failure
between approval and the fresh query — a dropped connection — costs the requester
another human approval.

**Consumption happens at release, not at policy.** The grant is read at step 14
as a [P-007](P-007-policy-engine.md) §4.2 input and consumed alongside the budget
debit at step 18, inside [P-004](P-004-replay-idempotency.md) §4.6's atomic
commit. Consuming it earlier would spend a person's approval on an exchange that
then failed output validation or found the budget exhausted.

### 4.6 The approval-scope digest, provisional

[`core-model.md`](../../spec/core-model.md) §9 parks the field list, with the
leaning being the seven fields in §5.3: requester principal and agent, predicate
and version, answer-contract digest, purpose, answer recipient, sink set, and
public-context commitment — excluding `query_id`, `nonce`, `issued_at`, and
`expires_at` so that a fresh query can carry the same scope.

MVP implements the leaning and marks it provisional. There is a circularity
worth naming: §9 blocks the field list on *grant lifetime and revocation
semantics*, and this PRD has to pick a lifetime to build anything. The resolution
is that lifetime is **required configuration with no default**, the way retention
is in [P-011](P-011-receipts-audit.md) §4.7 — MVP does not choose a number on
Q2D's behalf, and the operating experience is the input §9 was waiting for.

**The §7 clause, resolved.**
[`core-model.md`](../../spec/core-model.md) §7 says a changed purpose, sink set,
public context, predicate version, or answer contract is a distinct request
*"even when the approval-scope digest matches"*. Under §5.3's field list that
clause is vacuous — every field it names is covered by the digest, so changing
one necessarily changes the digest and it cannot match.

§7 now states that the clause is a **floor, not a description**: those five must
remain request-distinguishing whatever narrower list §9 eventually settles on,
and a reader must not infer a narrower digest from it. The inference was the
danger — a digest omitting, say, the sink set would let an approval granted for
one delivery path satisfy a fresh query naming another, and every other document
would still read as correct.

The alternative of deleting the clause was declined: if §9 does narrow the field
list, the clause becomes load-bearing, and it would be gone.

### 4.7 The retry guarantee is structural, and briefly held

[`core-model.md`](../../spec/core-model.md) §5.3 requires that identical retries
keep returning the cached normalized outcome and **never** become an answer
after approval.

This module implements none of it. [P-004](P-004-replay-idempotency.md) §4.5
caches response **bytes** and returns them verbatim without re-evaluating or
re-signing, so the guarantee holds for anything in the cache regardless of what
an authority decided meanwhile. That was the reason for the design, and this PRD
is its beneficiary.

The part worth stating is what happens **after** the cache entry goes:

> An identical retry stops returning the cached outcome when the query expires,
> not when the grant appears. [`freshness.md`](../../spec/freshness.md) §1 derives
> retention from the validity window rather than setting it beside one, so the
> cache always outlives the request — not by arithmetic that happens to work out,
> but because that is what the derivation is for. Past expiry an identical retry is rejected as expired — Tier A,
> per [P-009](P-009-denial-normalization.md) §4.2 — and never reaches policy at
> all.

So "never becomes an answer" is guaranteed for the whole life of the query and
trivially true afterwards, and no cache needs to be retained for the lifetime of
a grant. An implementation that extends retention to cover a grant has
misunderstood the requirement and has built a memory-exhaustion vector for it.

### 4.8 The approval prompt

Out of band, and deliberately small: the daemon records a pending approval, and
an operator approves or refuses through a local CLI against the daemon's store.
No web interface, no notification transport, no approval API. Any of those is a
new external surface with its own authentication and its own oracles, in the
stage with the least remaining budget for either.

What the prompt shows the authority: the human-readable
`purpose.description` — which [`core-model.md`](../../spec/core-model.md) §2.6
says exists for this — the predicate's registered question, the requester
principal and agent, the answer recipient, the declared sinks, and the release
shape that would be disclosed.

What it must not show: any private input, and any evaluation result. **The
authority decides whether to permit a disclosure, not whether they like the
answer.** A prompt that showed the result would make approval conditional on it,
which is [P-007](P-007-policy-engine.md) §4.1's answer-conditioned-policy leak
arriving through a human instead of a rule — and policy runs at step 14, before
private input is read at step 16, so the result does not exist yet. The ordering
makes the leak unbuildable; the prompt must not be the thing that reintroduces
it by deferring until after evaluation.

### 4.9 Residual oracles, named

[`core-model.md`](../../spec/core-model.md) §5.3 names the unavailable-to-answer
transition, and [`trust-matrix.md`](../../threat-model/trust-matrix.md) §5 lists
it among residual channels. This module adds no mechanism that closes any of
them, and documentation must not suggest otherwise.

| Channel | What it reveals |
|---|---|
| Unavailable → answer across two fresh queries | An approval happened between them |
| Poll timing under explicit escalation | Roughly when a human decided |
| Existence of an `escalate` response at all | A relationship or policy path may exist — deliberate, per §4.1 |
| Approval latency distribution | Whether a deployment escalates to a person or a standing rule |

Q2D-NC-05 already scopes the claim so that none of these is a surprise. Naming
them here is so that no future artifact quietly implies MVP addresses them.

## 5. Interfaces

```
record_pending(scope: ApprovalScope, decision: Decision, mode: Opaque | Explicit)
                                        -> Result<PendingRef>
issue_token(pending: PendingRef, expires_at) -> Token       // explicit mode only
poll(token: Token, now)                 -> PollOutcome      // no side effects

approve(pending: PendingRef, authority, now) -> Result<Grant>
refuse(pending: PendingRef, authority, now)  -> Result

approval_scope_digest(core: CoreObject) -> DigestString     // provisional; §4.6
grant_lookup(scope: DigestString, now)  -> Option<GrantRef> // reports; decides nothing
consume_grant(grant: GrantRef)          -> Result           // §4.5, pending decision
```

`poll` having no side effects is deliberate: it cannot extend a token, cannot
re-evaluate, and cannot debit. A polling endpoint that mutates state is one an
attacker can drive.

`grant_lookup` returning an `Option` rather than a decision is the §4.4
constraint in the type. There is no call that turns a grant into a response.

`approve` and `refuse` take an authority, so the audit event records **who**
decided — [P-011](P-011-receipts-audit.md) §4.3 keeps that local and out of the
receipt.

## 6. Corpus sections

`escalation/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `escalation/opaque/` | Normalized response byte-identical to a plain Tier C denial; no token; prompt dispatched without delaying the response |
| `escalation/explicit/` | Token issued; retry returns the same token verbatim; token encodes nothing |
| `escalation/poll/` | Pending, decided, unknown, and expired outcomes; polling mutates nothing |
| `escalation/retry/` | Identical retry after an approval returns the cached outcome; after expiry rejects as expired |
| `escalation/fresh/` | Fresh query with a matching scope is revalidated end to end — registry, delegation, policy, freshness, budget, data |
| `escalation/grant/` | Revoked authority overrides a grant; expired grant does not apply; mismatched scope does not match; **a consumed grant does not apply — a second fresh query in the same window escalates again** |
| `escalation/receipt/` | Explicit escalation carries the reduced receipt with `decision_class: escalate`; an opaque escalation's receipt is byte-identical to a plain Tier C denial's. The pair is the vector |
| `escalation/scope/` | Digest stable across `query_id`, `nonce`, `issued_at`, `expires_at`; changes with each of the seven covered fields |

`escalation/opaque/`'s first vector runs under
[P-009](P-009-denial-normalization.md)'s Tier C uniformity check rather than as
its own comparison — an escalation that is normalized must be indistinguishable
from the other Tier C causes, and testing it against them is the only way to
show that.

## 7. Acceptance

- [ ] An opaque escalation produces a response **byte-identical** to every other
      Tier C denial, in both implementations.
- [ ] The opaque response is returned without waiting for the prompt — asserted
      by a vector in which approval never arrives and the response is unchanged.
- [ ] An identical retry after an approval returns the cached outcome, in both.
- [ ] A fresh query with a matching scope digest is **revalidated end to end**,
      observable as each step running rather than as the outcome alone. This is
      the Stage 7 gate.
- [ ] A grant whose authorizing authority was revoked does not produce an answer.
- [ ] The approval-scope digest is stable across `query_id`, `nonce`,
      `issued_at`, and `expires_at`, and changes with every covered field.
- [ ] `poll` mutates nothing — asserted by running a vector twice and comparing
      full store state.
- [ ] Grant lifetime is required configuration; startup fails without it.
- [ ] **A grant authorizes exactly one answer.** A second fresh query with the
      same scope, inside the same window, escalates rather than answering.
- [ ] An explicit `escalate` carries a receipt; an **opaque** escalation's
      receipt is byte-identical to a plain Tier C denial's — asserted over the
      pair, not over either alone.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| **An opaque escalation whose response is delayed by the prompt** | Latency differs from a plain Tier C denial; the claim fails on timing |
| An opaque escalation returning anything but the Tier C class | Uniformity check fails |
| An identical retry becoming an answer after approval | `escalation/retry/` returns an answer |
| A grant served as an answer without revalidation | `escalation/fresh/` shows a skipped step |
| A revoked authority's grant still answering | `escalation/grant/` returns an answer |
| A token encoding the query, principal, or predicate | Token content is decodable |
| Polling extending a token, debiting, or re-evaluating | Store state differs across two polls |
| A grant surviving past its configured lifetime | `escalation/grant/` expiry vector answers |
| **A grant answering twice** | `escalation/grant/` second-use vector returns an answer. This is the multi-use reading arriving by omission rather than by decision |
| A grant consumed at policy time rather than at release | An exchange that fails output validation or the budget check still burns the approval |
| **An opaque escalation's receipt carrying `decision_class: escalate`** | `escalation/receipt/` fails. The response bodies match, so no other check catches it |
| The approval prompt showing an evaluation result | Policy runs at step 14; a result at prompt time means evaluation moved |
| Replay-cache retention extended to cover a grant | An entry retained past [`freshness.md`](../../spec/freshness.md) §1's instant, `expires_at + skew` |
| An approval API, notification transport, or web surface | Present at all — §4.8 |
| Text describing explicit escalation as denial-normalized | Grep; [`core-model.md`](../../spec/core-model.md) §5.3 forbids it |
| Text claiming MVP closes any §4.9 channel | Grep across docs and comments |

Row 1 is the one this PRD exists for. Every other row fails a test; this one
fails a stopwatch, and it will look correct in every functional vector while
defeating Q2D-C-08 in deployment. It needs a timing assertion, not an
equality assertion.

Row 9 is subtle. Nothing in the pipeline permits it today — the result does not
exist when policy runs — so the failure mode is someone deferring evaluation to
make the prompt more useful, which is a reordering of
[`core-model.md`](../../spec/core-model.md) §4 and an escalation in its own
right.

## 9. Escalate-if-changed decisions

1. **Opaque escalation returns immediately; the prompt is dispatched on a path
   that cannot delay it.**
2. **The grant is an input to policy, never a stored decision.** There is no call
   that turns a grant into a response.
3. **Every fresh query revalidates end to end**, regardless of a matching scope.
4. **The token encodes nothing and polling has no side effects.**
5. **Grant lifetime is required configuration with no default.**
6. **A grant is single-use**, consumed at release and not at policy time
   ([`core-model.md`](../../spec/core-model.md) §5.3).
7. **The approval prompt never shows an evaluation result.**
8. **Replay-cache retention is not extended for grants.**
9. **No approval API, notification transport, or push delivery in MVP.**
10. **Explicit escalation is never described as normalized**, and only explicit
    escalation carries `decision_class: escalate` in its receipt.

## 10. Open questions

| Question | Belongs to |
|---|---|
| **8.** **A vector cannot describe two queries with a human approval between them.** [E-51](../open-escalations.md) added `process_sequence` — one operation, an ordered list of requests, one responder — and closed as C with its limit stated: it is right for a sequence *one responder processes end to end*, and wrong for anything needing an external event mid-sequence. §5.3's shape is exactly that: query, escalate, an authority approves out of band, second query. The approval is not a request, so no list of requests expresses it. **Raised as [E-52](../open-escalations.md)**, which E-51's resolution says to do — recorded now rather than when `escalation/` is authored, because a question living only in the PRD that found it is findable by nobody else. It names the four groups it blocks, recommends **B** (the sequence's entries become a tagged union of request-or-approval), and recommends **deciding it when issue 12 is picked up** rather than now: settling an operation's shape against no vector is how E-51's own brief got two details wrong | [E-52](../open-escalations.md) · this PRD, issues 4 and 12 |
| **1.** ~~Is a grant single-use or multi-use within its window?~~ | **Resolved: single-use.** [`core-model.md`](../../spec/core-model.md) §5.3; see §4.5. Consumption is a release-time act, so [P-007](P-007-policy-engine.md) §4.2's new `grant` field reports an *unconsumed* match and policy never consumes it |
| **2.** ~~Does an `escalate` response carry a receipt?~~ | **Resolved: yes**, the reduced shape with `decision_class: escalate` — **for explicit escalation only.** An opaque escalation carries the ordinary deny receipt, byte-identical to any other Tier C denial. §5.3 and [P-011](P-011-receipts-audit.md) §4.1 amended together; §4.1 here carries the table |
| **3.** ~~[`core-model.md`](../../spec/core-model.md) §7's "even when the approval-scope digest matches" is vacuous~~ | **Resolved.** §7 now states the clause as a **floor** on whatever list §9 settles, with an explicit instruction not to infer a narrower digest from it. Deleting the clause was declined — it becomes load-bearing precisely if §9 narrows the list. See §4.6 |
| **4.** ~~Should the poll be a signed request rather than a bearer token?~~ | **Resolved: bearer token in MVP**, no improvised message type. The weakness is recorded in [`trust-matrix.md`](../../threat-model/trust-matrix.md) §5 as a residual channel rather than only in this PRD. Resolves [P-013](P-013-https-binding.md) open question 7 |
| **5.** ~~Do `deny` and `escalate` debit?~~ | **Resolved: neither does.** [`core-model.md`](../../spec/core-model.md) §9.1; a required rate limit bounds probing instead. [P-008](P-008-capacity-accounting.md) §4.7 |
| **6.** ~~Who may approve — any configured authority, or the specific one policy named?~~ | **Resolved: the specific authority policy named**, recorded on the pending record at step 14. An approval from an authority that was not consulted is not the decision policy asked for, and accepting one would make the set of people who can release a disclosure larger than the set the policy identified — silently, and without anything in the audit showing the substitution. An approval from any other authority is refused and audited as such |
| **7.** ~~Does a refusal record anything that suppresses re-asking?~~ | **Resolved: no.** A stored refusal that shortened a later evaluation would be a decision cache — the same thing §4.4 refuses to let a grant become, in the direction that looks harmless. It would also be a *negative* oracle: a second identical request returning faster than the first tells the requester a human said no. The refusal is audited, and it changes nothing about how the next request is evaluated. Repeated prompting is a policy problem, solved by a policy rule that denies without escalating |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | ~~Escalate open questions 1, 2, 3, and 4~~ — **done** | Resolved; `core-model.md` §5.3 and §7, `trust-matrix.md` §5, and P-011 §4.1 amended; §4.1, §4.2, §4.5, and §4.6 cite the outcome |
| 2 | `ApprovalScope` and `approval_scope_digest` | `escalation/scope/` passes; digest stable across the four excluded fields |
| 3 | Pending record and store | Survives restart; no state reachable from an unauthenticated path |
| 4 | Asynchronous prompt dispatch | `escalation/opaque/` timing assertion passes; response unchanged when approval never arrives |
| 5 | Opaque mode end to end | Tier C uniformity check passes with escalation among the causes, **for the receipt as well as the response** |
| 6 | `approve` / `refuse` with authority recording | `escalation/grant/` passes; open question 6 resolved first |
| 7 | Grant store, lifetime, and **single-use consumption** | Startup fails without a configured lifetime; consumption commits atomically with the debit at step 18 ([P-004](P-004-replay-idempotency.md) §4.6); a second fresh query under a consumed grant escalates again |
| 7a | Escalate receipts, both modes | `escalation/receipt/` passes; no code path lets an opaque escalation reach `decision_class: escalate` |
| 8 | `grant_lookup` | [P-007](P-007-policy-engine.md) §4.2 already carries the field; `grant_lookup` reports and no call converts a grant to a response |
| 9 | Fresh-query revalidation path | `escalation/fresh/` shows every step running |
| 10 | `issue_token` and `poll` | `escalation/explicit/` and `escalation/poll/` pass; two polls leave identical state |
| 11 | Approval CLI | An operator approves and refuses locally; no network surface added |
| 12 | Author `escalation/` corpus section | **Eight** groups; `harness lint` clean. This row said seven and §6 has listed eight since `escalation/scope/` was added — a count nobody re-read, which would have closed the issue a group short. **Four of the eight are blocked on [E-52](../open-escalations.md)**: `retry/`, `fresh/`, `grant/` and `poll/`'s decided outcome each need an approval *between* two requests, and [E-51](../open-escalations.md)'s `process_sequence` carries requests only. The other four are single requests and are authorable when the pipeline is |
| 13 | Claim-language audit | Nothing calls explicit escalation normalized, or claims a §4.9 channel is closed |

Issue 4 is the one to schedule properly: a
timing assertion needs a harness capability the corpus does not have yet, and
[P-001](P-001-conformance-corpus.md) §10 deferred timing bands to Stage 8 on the
assumption nothing before then would need them. This does.
