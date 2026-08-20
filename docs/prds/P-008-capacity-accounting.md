# P-008 — Disclosure-capacity accounting

| Field | Detail |
|---|---|
| PRD | P-008 |
| Stage | 3 |
| Status | **Deferred 2026-08-19** — see the note below |
| Size | M |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-004](P-004-replay-idempotency.md), [P-005](P-005-registry-client.md), [P-006](P-006-request-validation.md), [P-007](P-007-policy-engine.md) |
| Blocks | P-010, P-011, P-015, P-016 |


> **Deferred 2026-08-19 — not withdrawn.**
>
> Q2D-C-09 metered disclosure in millibits of answer-alphabet capacity. But
> [`claims.md`](../../spec/claims.md) already recorded that it is **not** an
> inference or privacy guarantee, and its own *Fails if* list conceded that
> collusion, correlated predicates, auxiliary knowledge and cross-custodian
> spreading all defeat it — so it measured a quantity nobody is worried about. No
> operator can say what a budget of *N* millibits permits.
>
> It was also the largest complexity source in the repository: integer millibits,
> capacity tables, the no-runtime-`log2` rule, reservations, `settle`/`release`,
> reservation expiry, [P-004](P-004-replay-idempotency.md) issue 5's atomic commit,
> and the whole [E-25 … E-30](../open-escalations.md) coarsening chain.
>
> **What replaces it:** a **request quota keyed on the relationship, and on
> nothing finer** — required configuration with no default, checked at step 9a.
> An earlier draft of this note said `(requester, predicate, subject, window)`,
> which is wrong and contradicts [`core-model.md`](../../spec/core-model.md)
> §9.1: predicate and sensitivity class are known only **after** registry
> resolution at step 10, so a limiter keyed on them would either run too late or
> skip unresolved requests — leaving unknown predicates unlimited, which is a
> difference a requester can measure and therefore the existence oracle the quota
> exists to close.
> E-01 had already established that a rate limit is the mechanism bounding probing;
> this makes it the only one. Issue 5a survives as that quota.
>
> **What would bring it back:** a deployment that genuinely wants a subject-level
> cap enforced in bits — a data-protection authority asking *how much did this
> subject disclose this quarter, and cap it*. **[E-01](../open-escalations.md) and
> [E-25 … E-30](../open-escalations.md) park here** rather than being closed:
> nothing was decided, the questions simply have no consumer.
>
> Full reasoning: `private-docs/scope-reduction-proposal.md`. **Everything below
> is preserved as written**, and describes the scope that was planned.

---

## 1. Purpose

Store, key, debit, and enforce the disclosure-capacity budget in integer
millibits.

The arithmetic is already settled — [`core-model.md`](../../spec/core-model.md)
§3.1 fixed it, and [`registry/manifest.json`](../../registry/manifest.json)
carries the authored values. What remains is the *state*: where a budget lives,
what it is keyed by, when it is debited, and what happens when it runs out.

**Claims served:** Q2D-C-09 (disclosure-capacity accounting) directly.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §3.1 | Millibits; ceiling rounding; **a responder never computes `log2`** |
| [`spec/core-model.md`](../../spec/core-model.md) §4 steps 15, 18 | Budget checked before private access; debited after output validation |
| [`spec/core-model.md`](../../spec/core-model.md) §7 | A retry must not debit twice |
| [`spec/core-model.md`](../../spec/core-model.md) §9.1 | `deny` and `escalate` do not debit; a required rate limit bounds probing, and its rejection is normalized |
| [`spec/terminology.md`](../../spec/terminology.md) §6 | Budget, capacity debit, disclosure history, the keying tuple |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-09 | What the claim holds and does not hold |
| [`registry/manifest.json`](../../registry/manifest.json) | `capacity_unit`, per-entry `millibits`, and the computed-domain tables |

## 3. Module boundary

**Inside:** the budget store; the budget key; reading the authored capacity for
an effective domain; the check-before / debit-after split; exhaustion behaviour;
window semantics; the audit record of a debit.

**Explicitly outside:** computing capacity — it is read, never calculated
(§4.1). The effective domain itself (**P-006**). The policy decision that
consumes an exhaustion verdict (**P-007**). Idempotency and the atomic commit
(**P-004**), which this module supplies a debit *to* rather than implements.
Receipt construction (**P-011**).

## 4. Design

### 4.1 The module contains no logarithm

The capacity for an effective domain is **looked up**, never computed:

| Domain kind | Source |
|---|---|
| Enumerated, entry carries `capacity.millibits` | that value. The entry admits no coarsening ([`core-model.md`](../../spec/core-model.md) §3.2), so there is one debit and this is it |
| Enumerated, entry carries `capacity.table` | the table, keyed by the **label count** — which is the registered cardinality when nothing is coarsened. The table is the entry's only capacity source, and `registry/validate.py` rejects an entry carrying both |
| Computed | the entry's `capacity.table`, keyed by effective cardinality |
| Cardinality absent from the table | **reject** — a registry error, not a fallback |

IEEE-754 does not require a correctly-rounded `log2`, and a rounding boundary
would turn a last-place difference into a different integer
([`core-model.md`](../../spec/core-model.md) §3.1). A `log2` call anywhere in
this module is a `blocker`, including one that returns the right answer today.

The last row matters: a coarsening that produces a cardinality the table does not
cover means the registry entry is incomplete. Silently computing the value would
paper over a registry defect and reintroduce the divergence the table exists to
prevent.

### 4.2 Check before, debit after

| Step | Action |
|---|---|
| 15 | **Check** — is `spent + debit ≤ limit`? |
| 16 | private input read |
| 17 | output validated |
| 18 | **Debit** |

Checking before private access means exhaustion is reachable without touching
protected data. Debiting after output validation means a request that fails
validation — an implementation or integrity error, not a policy outcome — does
not consume budget for an answer that was never released.

The gap between check and debit is where a concurrent request can overspend. See
§4.5.

### 4.3 The budget key

```
key = (requester_relationship, subject, sensitivity_class, sink_set, window)
```

Every component is policy-defined, and a deployment may collapse any of them.
What the module fixes is that the key is **derived from the decision context**
and never from anything the requester asserts.

Two properties the key must have, neither of which the module can guarantee
alone:

- **Relationship, not identity.** Keying on a raw principal makes a new identity
  a fresh budget. Keying on an established relationship makes the cost of a new
  budget the cost of establishing a relationship. This is why
  [`claims.md`](../../spec/claims.md) Q2D-C-09 lists relationship recreation
  among the ways it fails — the mitigation is deployment-side, and the claim says
  so.
- **Sink set, not sink.** Two requests differing only in declared sinks must not
  share a budget, or a requester splits its spend by varying a field it controls.

### 4.4 Windows

A rolling window, not a calendar one.

A calendar window — resets at midnight, or on the first of the month — creates a
predictable moment at which an adversary's budget is restored, and a probing
strategy that waits for it. A rolling window has no such moment.

The window length, the limit, and whether they vary by sensitivity class are all
policy. The module stores timestamped debits and computes `spent` over the window
at decision time.

### 4.5 Concurrency

Between the check at step 15 and the debit at step 18, another request under the
same key can pass its own check. Both then debit, and the total can exceed the
limit.

**Reserve at check, settle at debit.** The check places a reservation for its
debit amount; `spent` includes reservations. A reservation is settled by the
debit, or released if the exchange fails before step 18, or expires with the
request.

An unsettled reservation that outlives its request must expire, or a crashed
request permanently consumes budget. Expiry is the request's `expires_at` plus
skew — [`freshness.md`](../../spec/freshness.md) §1's skew, the same value the
replay cache's retention is derived from, and for the same reason: a request
cannot affect state for longer than it can be valid.

**Reservations make the budget conservative under concurrency.** Two concurrent
requests that would together exceed the limit result in one being refused, not
both succeeding.

### 4.6 Exhaustion is a policy input, not a decision

When `spent + debit > limit`, this module reports **exhausted**. It does not
decide what happens.

[P-007](P-007-policy-engine.md) decides whether exhaustion produces `deny` or
`escalate`, because that is a policy question — a deployment may want a human to
approve spending beyond a threshold, and another may want a hard stop.

The module reporting a verdict rather than an outcome is what keeps that
choosable.

**But policy cannot be consulted here, and saying it decides "when exhaustion
occurs" would describe an ordering the protocol does not have.**
[`core-model.md`](../../spec/core-model.md) §4 runs policy once, at step 14, and
checks the budget at step 15 — because the debit cannot be computed until step
14's modifiers have produced the effective domain. By the time this module
reports `Exhausted`, policy has already run and will not run again.

So the disposition is decided **in advance, at step 14**, from the
`disclosure_history` [P-007](P-007-policy-engine.md) §4.2 already carries into
`PolicyInput`. Its `Decision` names what to do if step 15 finds exhaustion, and
step 15 applies it without a second consultation.

The distinction is not pedantic. Re-consulting policy at step 15 would be a
reordering of [`core-model.md`](../../spec/core-model.md) §4 — the kind that
arrives as a plausible convenience and has to be escalated, not implemented.

**`on_exhaustion` is an internal outcome and gets no special path to the wire.**
An exhaustion-triggered `escalate` passes through
[P-009](P-009-denial-normalization.md) §4.6's visibility gate like any other,
and is opaque unless the sensitivity class permits otherwise. Letting it bypass
that gate would make budget state externally observable, which
[P-011](P-011-receipts-audit.md) §4.3 keeps out of receipts precisely because it
reveals other requesters' activity.

### 4.7 `deny` and `escalate` do not debit

**Resolved.** [`core-model.md`](../../spec/core-model.md) §9.1 now decides this:
neither a denial nor an escalation debits the disclosure-capacity budget, and a
**rate limit** bounds the probing they would otherwise permit.

The reasoning is recorded in §9.1 and is not restated here. What this module
owes it:

| Requirement | Where |
|---|---|
| Only a released answer debits — nothing is charged at any earlier failure point | §4.2's step-15/step-18 boundary already produces this |
| A rate limit keyed on the **relationship component only** — not the full `BudgetKey` | §4.3's key also carries sensitivity class and sink set, which come from the registry entry and the contract. The rate limit is checked at [`core-model.md`](../../spec/core-model.md) §4 step 9a, before registry resolution, so it cannot use them — and must not, because a limiter that counted only requests which resolved a predicate would leave unknown predicates unlimited, which a requester can measure |
| The rate limit is **required configuration with no default** | The daemon refuses to start without it — [P-013](P-013-https-binding.md) §4.6's list gains a row |
| A rate-limit rejection is **normalized** | [P-009](P-009-denial-normalization.md) §4.2's Tier C, indistinguishable from every other cause, with no retry metadata |

The units argument is why the two mechanisms stay separate rather than one
being expressed as the other. Q2D-C-09 accounts for disclosure in millibits of
answer alphabet; what a denial can leak is policy structure, which has no
bit-count in this model. A rate limit counts requests, which is the thing
actually being bounded. Charging denials against the bit budget would make
`disclosure_capacity_debit_millibits` a number that no longer means what
Q2D-C-09 says it means — and would let any reachable party spend a subject's
budget without ever receiving an answer.

**The rate limiter is the sharp edge in this module.** Its rejection is the one
new denial cause introduced since [P-009](P-009-denial-normalization.md) was
written, and a rate limiter's natural output — a 429, a `Retry-After`, a
"try again in 40 seconds" — is cause-specific by construction. Every one of
those is forbidden. If the limiter is distinguishable, it has become the oracle
it was introduced to close, and the decision above is not merely unhelpful but
worse than debiting would have been.

## 5. Interfaces

```
capacity_for(entry, effective_domain) -> Result<Millibits>   // lookup; no log2
check(key: BudgetKey, debit: Millibits, now) -> Verdict      // reserves
   Verdict = Within { reservation } | Exhausted { spent, limit }
settle(reservation) -> Result                                // called by P-004's `record`
release(reservation) -> Result
spent(key, window, now) -> Millibits
```

`check` returning a reservation rather than a boolean makes §4.5 structural: a
caller cannot check and then debit later without holding the thing that reserved
the capacity.

`settle` is called from [P-004](P-004-replay-idempotency.md)'s `record` rather
than directly by the pipeline, which is what makes a retry unable to debit twice.

**It is to be called inside the same transaction as the replay-cache entry, and
is not yet**, which this paragraph stated as though it already were. P-004 issue
5 built `record` as settle-then-write — §4.6's first row there — and review of it
established that `record` cannot reach the atomic row on its own: the cache write
is not inside anything a caller of `settle` can open or close. The transaction is
[P-010](P-010-responder-pipeline.md) §5's, staging the debit at step 18 and
committing it with the bytes step 19 produces, over the single store open
question 3 resolved to; issue 2 here is where this module's half lands. Until
then a crash between the settle and the cache write **over-charges** — the
conservative direction P-004 §4.6 chose, and not one this PRD may describe as
already closed.

## 6. Corpus sections

`budget/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `budget/lookup/` | Enumerated and computed domains; a cardinality absent from the table rejects |
| `budget/accumulate/` | A debit sequence and its permutations reach the same total. **Not a `process_sequence` group**, and it never needed [E-51](../open-escalations.md): `capacity_debit` already takes `{"debits": [...]}` and P-001 §4.8's cross-vector check compares permutations *across* vectors. A running total over separate requests is the sequence problem; a list of debits to one call is not |
| `budget/exhaustion/` | At, below, and above the limit; the boundary is exact |
| `budget/reserve/` | Concurrent checks; settle; release; reservation expiry |
| `budget/window/` | Debits ageing out of a rolling window |
| `budget/idempotent/` | A retry settles once — cross-references `replay/idempotent/`, and like it is a **`process_sequence`** vector, since settling once is a property of the second request ([E-51](../open-escalations.md)) |
| `budget/nodebit/` | A denial, an escalation, and a rate-limit rejection each leave `spent` unchanged ([`core-model.md`](../../spec/core-model.md) §9.1) |
| `budget/ratelimit/` | A rate-limit rejection is byte-identical to every other Tier C denial; no retry metadata; no header varies — asserted **across** causes, not per cause |

## 7. Acceptance

- [ ] No `log2`, `ln`, `exp`, or floating-point type appears in the module.
      Asserted by grep and by type, in both implementations.
- [ ] A debit sequence and every permutation of it reach the **same total** —
      the P-001 cross-vector accumulation assertion.
- [ ] The exhaustion boundary is exact: `spent + debit == limit` is within,
      `+1` millibit is exhausted, identically in both implementations.
- [ ] Two concurrent checks that would together exceed the limit result in one
      `Exhausted`.
- [ ] A reservation whose request never settles is held **through**
      `expires_at + skew` and released only after it — the inclusive boundary
      [`freshness.md`](../../spec/freshness.md) §1 states for a replay-cache
      entry, for the same reason: §2's comparison is strict, so the request is
      still acceptable at that instant.
- [ ] A retry produces one settlement, verified against the budget total rather
      than a call count.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| Any runtime logarithm | grep finds one; **`blocker` even if the value is correct** |
| A float in the budget path | Type check fails |
| A cardinality absent from the entry's table silently computed | Lookup returns a value where it must reject |
| A requester-asserted debit honoured | `capacity_for` takes the entry and the domain; the request is not a parameter |
| Budget keyed on raw principal rather than relationship | A new identity receives a fresh budget in the fixture deployment |
| Two requests differing only in declared sinks sharing a budget | Spend splits across sink sets |
| Concurrent overspend | Both concurrent requests succeed past the limit |
| A crashed request holding budget forever | Reservation outlives `expires_at + skew` |
| A reservation released while its request is still acceptable | Released **at** `expires_at + skew` rather than after it, so a concurrent request passes on capacity the first one may still settle |
| A calendar-boundary budget reset | Window vectors show restoration at a predictable time |

Row 4 is enforced by the signature: `capacity_for` cannot see the request, so
there is nothing for a requester-asserted debit to be read from.

## 9. Escalate-if-changed decisions

1. **Capacity is read from the registry, never computed.** No logarithm in this
   module.
2. **A cardinality absent from the table rejects.** Computing it hides a registry
   defect.
3. **Check reserves; the reservation is what `settle` consumes.**
4. **Reservations are held through `expires_at + skew` and released after it** — [`freshness.md`](../../spec/freshness.md) §1's skew and its inclusive boundary, and the same bound as the replay
   cache.
5. **Rolling windows, never calendar.** A predictable reset is a probing schedule.
6. **The module reports `Exhausted`; policy decides `deny` or `escalate`.**
7. **§4.7's resolution**, once made — whether denials debit — is architecture.

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~**§4.7** — do `deny` and `escalate` debit?~~ | **Resolved: neither debits.** A required rate limit bounds probing instead. [`core-model.md`](../../spec/core-model.md) §9.1; see §4.7 |
| ~~Does a rejected reservation appear in audit, or only settled debits?~~ | **Resolved: both.** Exhaustion is a fact an operator needs — a budget silently refusing traffic with no local record is indistinguishable from an outage. The audit is local and never disclosed to the requester, so recording it costs nothing externally; [P-011](P-011-receipts-audit.md) §4.3 already keeps budget state out of receipts for the separate reason that it reveals other requesters' activity |
| ~~Where does the budget store live — same store as the replay cache, or separate?~~ | **Resolved: the same store.** §4.5 requires the debit and the cache entry to commit atomically, and two stores means a distributed transaction — the same problem [P-013](P-013-https-binding.md) §4.6 declines to solve for two daemons, arriving inside one process. One store, one transaction, and the atomicity is a local property rather than a protocol |
| ~~Do reservations survive a restart?~~ | **Resolved: no.** A reservation is released just after `expires_at + skew`, which is shorter than a restart takes to complete, so persisting them would add a recovery path for state that is already gone by the time it could be read. Dropping them is also the safe direction: a lost reservation under-reserves briefly, never under-charges, because a debit only exists after §4.2's step-18 settle |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | `capacity_for` lookup, both kinds | `budget/lookup/` passes; grep finds no logarithm |
| 2 | Budget store with timestamped debits | Open question 3 resolved; shares the transaction with P-004 |
| 3 | `BudgetKey` derivation from decision context | Not derivable from requester-asserted fields |
| 4 | Rolling-window `spent` | `budget/window/` passes; no calendar boundary |
| 5 | `check` with reservation, and the exhaustion boundary | `budget/exhaustion/` and `budget/reserve/` pass |
| 5a | **Rate limiter**, keyed on the **relationship component only** — never the full `BudgetKey` — checked at [`core-model.md`](../../spec/core-model.md) §4 step 9a; required configuration with no default | Startup fails when unconfigured; the limiter is reachable without registry resolution, so a request naming an unknown predicate counts identically to one naming a known predicate; `budget/ratelimit/` shows a rejection byte-identical to a Tier C denial, with no retry metadata and no distinguishing header |
| 6 | `settle` / `release` wired into P-004's `record`, **inside a transaction with the cache entry** | `budget/idempotent/` passes. The wiring is the easy half: P-004 issue 5 built `record` as settle-then-write, and review there established that it cannot enclose the cache write on its own — so this issue also carries the transaction, over the single store open question 3 resolved to, opened where [P-010](P-010-responder-pipeline.md) §5 says. Until it lands, a crash between the two over-charges |
| 7 | Reservation expiry | Unsettled reservation held **through** `expires_at + skew` and released after it — [`freshness.md`](../../spec/freshness.md) §1's inclusive boundary |
| 8 | Accumulation order-independence | P-001 cross-vector permutation assertion passes |
| 9 | Author `budget/` corpus section | Six groups; `harness lint` clean |
| 10 | ~~Escalate §4.7 and record the outcome~~ — **done** | Resolved: neither debits; `core-model.md` §9.1 written; §4.7 rewritten; issue 5a added |

Issue 2 blocks 5, 6, and 7. Issue 5a is independent of the budget store and can
start immediately.
