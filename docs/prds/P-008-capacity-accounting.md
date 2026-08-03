# P-008 — Disclosure-capacity accounting

| Field | Detail |
|---|---|
| PRD | P-008 |
| Stage | 3 |
| Status | **Ready for decomposition** |
| Size | M |
| Risk | medium |
| Depends on | [P-004](P-004-replay-idempotency.md), [P-005](P-005-registry-client.md), [P-006](P-006-request-validation.md), [P-007](P-007-policy-engine.md) |
| Blocks | P-010, P-011 |

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
| [`spec/core-model.md`](../../spec/core-model.md) §9 | **Open:** whether `deny` and `escalate` debit |
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
| Enumerated | the entry's `capacity.millibits` |
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
skew — the same bound [P-004](P-004-replay-idempotency.md) §4.4 uses, and for the
same reason: a request cannot affect state for longer than it can be valid.

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

### 4.7 Escalation: do `deny` and `escalate` debit?

[`core-model.md`](../../spec/core-model.md) §9 records this as undecided, and the
subsetting resolution has narrowed it but not closed it.

**The argument for debiting.** A denial can be informative. Under the coarsening
rule, a *narrowing-induced* out-of-domain denial is now impossible — that was the
leak §2.5 closed. But a **policy** denial still carries information in some
deployments: a requester learning that a predicate is denied for a purpose learns
something about policy, and repeated probing across purposes could map it.

**The argument against.** Debiting denials means a requester can exhaust another
party's budget by making requests that will be denied — a denial-of-service on
the budget rather than on the service. And an escalation that a human ultimately
refuses would have consumed capacity for a disclosure that never happened.

**Proposal, not a decision.** Neither `deny` nor `escalate` debits the disclosure
budget. The probing they enable is bounded by a **separate rate limit** keyed the
same way, which is a different mechanism with different units and no claim
attached to it.

Rate limiting is honest here in a way that a capacity debit is not: what a
denial leaks is not measured in bits of answer alphabet, so charging it against
a bit budget would be measuring one thing with another thing's ruler.

**This needs a decision before issue 5.** It is a spec-level question
([`core-model.md`](../../spec/core-model.md) §9) and therefore not settled here.

## 5. Interfaces

```
capacity_for(entry, effective_domain) -> Result<Millibits>   // lookup; no log2
check(key: BudgetKey, debit: Millibits, now) -> Verdict      // reserves
   Verdict = Within { reservation } | Exhausted { spent, limit }
settle(reservation) -> Result                                // called by P-004's atomic commit
release(reservation) -> Result
spent(key, window, now) -> Millibits
```

`check` returning a reservation rather than a boolean makes §4.5 structural: a
caller cannot check and then debit later without holding the thing that reserved
the capacity.

`settle` is called from [P-004](P-004-replay-idempotency.md)'s `record`, inside
the same atomic commit as the replay-cache entry. It is not called directly by
the pipeline — that ordering is what makes a retry unable to debit twice.

## 6. Corpus sections

`budget/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `budget/lookup/` | Enumerated and computed domains; a cardinality absent from the table rejects |
| `budget/accumulate/` | A debit sequence and its permutations reach the same total |
| `budget/exhaustion/` | At, below, and above the limit; the boundary is exact |
| `budget/reserve/` | Concurrent checks; settle; release; reservation expiry |
| `budget/window/` | Debits ageing out of a rolling window |
| `budget/idempotent/` | A retry settles once — cross-references `replay/idempotent/` |

## 7. Acceptance

- [ ] No `log2`, `ln`, `exp`, or floating-point type appears in the module.
      Asserted by grep and by type, in both implementations.
- [ ] A debit sequence and every permutation of it reach the **same total** —
      the P-001 cross-vector accumulation assertion.
- [ ] The exhaustion boundary is exact: `spent + debit == limit` is within,
      `+1` millibit is exhausted, identically in both implementations.
- [ ] Two concurrent checks that would together exceed the limit result in one
      `Exhausted`.
- [ ] A reservation whose request never settles expires at `expires_at + skew`.
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
| A calendar-boundary budget reset | Window vectors show restoration at a predictable time |

Row 4 is enforced by the signature: `capacity_for` cannot see the request, so
there is nothing for a requester-asserted debit to be read from.

## 9. Escalate-if-changed decisions

1. **Capacity is read from the registry, never computed.** No logarithm in this
   module.
2. **A cardinality absent from the table rejects.** Computing it hides a registry
   defect.
3. **Check reserves; the reservation is what `settle` consumes.**
4. **Reservations expire at `expires_at + skew`** — the same bound as the replay
   cache.
5. **Rolling windows, never calendar.** A predictable reset is a probing schedule.
6. **The module reports `Exhausted`; policy decides `deny` or `escalate`.**
7. **§4.7's resolution**, once made — whether denials debit — is architecture.

## 10. Open questions

| Question | Belongs to |
|---|---|
| **§4.7 — do `deny` and `escalate` debit?** Proposed: no, with a separate rate limit doing that job, because what a denial leaks is not measured in bits of answer alphabet | **Escalated.** [`core-model.md`](../../spec/core-model.md) §9; blocks issue 5 |
| Does a rejected reservation appear in audit, or only settled debits? Proposed: both, since exhaustion is itself a fact an operator needs | This PRD |
| Where does the budget store live — same store as the replay cache, or separate? Proposed: same, since §4.5 requires atomic commit across both | This PRD; blocks issue 2 |
| Do reservations survive a restart? Proposed: no — they expire faster than a restart takes, and persisting them adds a failure mode for a bound already short | This PRD |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | `capacity_for` lookup, both kinds | `budget/lookup/` passes; grep finds no logarithm |
| 2 | Budget store with timestamped debits | Open question 3 resolved; shares the transaction with P-004 |
| 3 | `BudgetKey` derivation from decision context | Not derivable from requester-asserted fields |
| 4 | Rolling-window `spent` | `budget/window/` passes; no calendar boundary |
| 5 | `check` with reservation, and the exhaustion boundary | `budget/exhaustion/` and `budget/reserve/` pass; §4.7 resolved first |
| 6 | `settle` / `release` wired into P-004's atomic commit | `budget/idempotent/` passes |
| 7 | Reservation expiry | Unsettled reservation released at `expires_at + skew` |
| 8 | Accumulation order-independence | P-001 cross-vector permutation assertion passes |
| 9 | Author `budget/` corpus section | Six groups; `harness lint` clean |
| 10 | **Escalate §4.7 and record the outcome** | Decision written into §4.7 and `core-model.md` §9 |

Issue 10 blocks issue 5. Issue 2 blocks 5, 6, and 7.
