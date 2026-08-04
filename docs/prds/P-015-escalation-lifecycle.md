# P-015 — Escalation lifecycle

| Field | Detail |
|---|---|
| PRD | P-015 |
| Stage | 7 — the last MVP item |
| Status | **Blocked on escalation** — open questions 1, 2, and 3 |
| Size | M |
| Risk | **high** — the most intricate semantics in the protocol, and three of its questions are open in the specification rather than in this PRD |
| Depends on | [P-004](P-004-replay-idempotency.md), [P-007](P-007-policy-engine.md), [P-008](P-008-capacity-accounting.md), [P-009](P-009-denial-normalization.md), [P-010](P-010-responder-pipeline.md), [P-013](P-013-https-binding.md) |
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

**Three of this PRD's questions are open in `spec/`, not here.** Grant
multiplicity, whether an `escalate` carries a receipt, and the approval-scope
field list are all either unspecified or parked. §4 marks each where it arises
rather than choosing quietly.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §5.3 | Both modes; the four-step opaque sequence; the residual oracle, named |
| [`spec/core-model.md`](../../spec/core-model.md) §7 | Idempotency; what makes a request distinct even when the approval scope matches (§4.6) |
| [`spec/core-model.md`](../../spec/core-model.md) §9 | **Parked:** the approval-scope field list, blocked on grant lifetime and revocation |
| [`spec/core-model.md`](../../spec/core-model.md) §9 | **Parked:** whether `deny` and `escalate` debit — escalated by [P-008](P-008-capacity-accounting.md) §4.7 |
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

### 4.2 Explicit escalation: the token and its lifecycle

| Property | Value |
|---|---|
| Content | None. High-entropy random; encodes no `query_id`, principal, or predicate |
| Lifetime | The `expires_at` on the escalate response |
| Polling | Does not extend the token, does not re-evaluate, does not debit |
| Retry of the original query | Returns the cached escalate response verbatim, same token ([P-004](P-004-replay-idempotency.md) §4.7) |

**The token is a bearer capability in MVP, and that is a real weakening worth
naming.** Anyone holding it can learn the outcome, because the poll response is
a signed Q2D response bound to the original request digest and the endpoint
authenticates nobody. Mitigations are entropy, a short lifetime, and TLS —
which reduce exposure without changing the shape.

The right long-term answer is a **signed poll**: a small message type carrying
the token under the requester's signature, so the outcome is released only to
the principal that asked. That is a core-model addition rather than a binding
detail, which is why MVP does not improvise one. Open question 4, and it
resolves [P-013](P-013-https-binding.md) open question 7.

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
changes, and P-007 is amended in the same change as this module rather than
after it.

### 4.5 How many answers is one approval?

**Unspecified, and it decides what a human is agreeing to.**

[`core-model.md`](../../spec/core-model.md) §5.3 says a grant is *time-bounded*
and says nothing about how many times it may be used. Both readings are
implementable and they are very different products:

| Reading | One approval authorizes |
|---|---|
| **Single-use** | One answer. The grant is consumed by the first successful release |
| **Multi-use within the window** | Any number of answers until the window closes, throttled only by the budget |

**Recommended: single-use.** A person approving *"tell them whether the room is
free on Thursday"* has agreed to one disclosure. No approval interface can
honestly convey *"and to every repetition of this question for the next hour"*,
and a deployment that genuinely wants standing permission should express it as a
policy rule — where [P-007](P-007-policy-engine.md) evaluates it, the audit
records it, and it is visible as a rule rather than as the residue of a
prompt somebody answered once.

The counter-argument is real and should be recorded: single-use means a
transient failure after approval — a network drop between the grant and the
fresh query — costs the requester another human approval. That is friction, and
it is the safer direction to fail in.

The multi-use reading also interacts badly with the budget. Under it, one
approval plus a large window converts a consent decision into a capacity
question, and Q2D-C-09's accounting was never intended to be the thing bounding
how much a single approval discloses.

**Escalated, not decided here** — open question 1.

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

**One thing to flag rather than fix.**
[`core-model.md`](../../spec/core-model.md) §7 says a changed purpose, sink set,
public context, predicate version, or answer contract is a distinct request
*"even when the approval-scope digest matches"*. Under §5.3's leaning that clause
is vacuous — every field it names is covered by the digest, so changing one
necessarily changes the digest and it cannot match.

The charitable reading, and probably the intended one, is that §7 constrains
whatever narrower list §9 eventually settles on. That is worth saying out loud,
because as written a reader may reasonably infer the digest is narrower than
§5.3 states, and implement a narrower one. Open question 3.

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
> not when the grant appears. [P-004](P-004-replay-idempotency.md) §4.4 bounds
> validity at five minutes and retention at seven, so the cache always outlives
> the request. Past expiry an identical retry is rejected as expired — Tier A,
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
| `escalation/grant/` | Revoked authority overrides a grant; expired grant does not apply; mismatched scope does not match |
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
| The approval prompt showing an evaluation result | Policy runs at step 14; a result at prompt time means evaluation moved |
| Replay-cache retention extended to cover a grant | Retention beyond window + 2×skew |
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
6. **The approval prompt never shows an evaluation result.**
7. **Replay-cache retention is not extended for grants.**
8. **No approval API, notification transport, or push delivery in MVP.**
9. **Explicit escalation is never described as normalized.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| **1.** Is a grant single-use or multi-use within its window? [`core-model.md`](../../spec/core-model.md) §5.3 does not say, and it decides what a human is agreeing to. **Recommended: single-use** (§4.5) | **Escalation.** A `core-model.md` §5.3 addition; blocks issues 6 and 7 |
| **2.** Does an `escalate` response carry a receipt? §5.3 does not say, and [P-011](P-011-receipts-audit.md) §4.1's table has answer and deny columns only — so an escalated exchange currently produces no evidence it happened, against Q2D-C-10's "one exchange". **Recommended: yes, the reduced deny-shaped receipt with `decision_class: escalate`**, leaving [P-009](P-009-denial-normalization.md)'s uniformity untouched since explicit escalation is not in a normalized class | **Escalation.** `core-model.md` §5.3 and P-011 §4.1 in lockstep |
| **3.** [`core-model.md`](../../spec/core-model.md) §7's "even when the approval-scope digest matches" is vacuous under §9's current leaning (§4.6). Recommended: state that it constrains whatever list §9 settles on, so nobody infers a narrower digest from it | **Escalation.** A `core-model.md` clarification that carries meaning |
| **4.** Should the poll be a signed request rather than a bearer token? Recommended: yes eventually, no in MVP — it needs a core message type, and improvising one here is worse than naming the weakness. Resolves [P-013](P-013-https-binding.md) open question 7 | Escalation if adopted; `core-model.md` addition |
| **5.** ~~Do `deny` and `escalate` debit?~~ | Already escalated by [P-008](P-008-capacity-accounting.md) §4.7. This module inherits the answer and must not pre-empt it; issue 5 blocks on it |
| **6.** Who may approve — any configured authority, or the specific one policy named? Proposed: the specific one, since an approval by an authority that was not consulted is not the decision policy asked for | This PRD; blocks issue 6 |
| **7.** Does a refusal record anything that suppresses re-asking? Proposed: no. A stored refusal that shortened later evaluation would be a decision cache, which §4.4 rejects for the same reason grants are not one | This PRD |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Escalate open questions 1, 2, 3, and 4 | Resolved; `core-model.md` §5.3/§7 and P-011 §4.1 amended or the recommendations declined, with §4.5, §4.6, and §4.2 citing the outcome |
| 2 | `ApprovalScope` and `approval_scope_digest` | `escalation/scope/` passes; digest stable across the four excluded fields |
| 3 | Pending record and store | Survives restart; no state reachable from an unauthenticated path |
| 4 | Asynchronous prompt dispatch | `escalation/opaque/` timing assertion passes; response unchanged when approval never arrives |
| 5 | Opaque mode end to end | Tier C uniformity check passes with escalation among the causes; open question 5 resolved |
| 6 | `approve` / `refuse` with authority recording | `escalation/grant/` passes; open questions 1 and 6 resolved first |
| 7 | Grant store, lifetime, and consumption | Startup fails without a configured lifetime; multiplicity per open question 1 |
| 8 | `grant_lookup` and the `PolicyInput` amendment | [P-007](P-007-policy-engine.md) §4.2 amended in the same change; no call converts a grant to a response |
| 9 | Fresh-query revalidation path | `escalation/fresh/` shows every step running |
| 10 | `issue_token` and `poll` | `escalation/explicit/` and `escalation/poll/` pass; two polls leave identical state |
| 11 | Approval CLI | An operator approves and refuses locally; no network surface added |
| 12 | Author `escalation/` corpus section | Seven groups; `harness lint` clean |
| 13 | Claim-language audit | Nothing calls explicit escalation normalized, or claims a §4.9 channel is closed |

Issue 1 blocks 5, 6, and 7 — three of the four open escalations change what gets
built rather than what gets written. Issue 4 is the one to schedule properly: a
timing assertion needs a harness capability the corpus does not have yet, and
[P-001](P-001-conformance-corpus.md) §10 deferred timing bands to Stage 8 on the
assumption nothing before then would need them. This does.
