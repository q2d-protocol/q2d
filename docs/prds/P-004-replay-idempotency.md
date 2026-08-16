# P-004 — Replay, expiry, idempotency

| Field | Detail |
|---|---|
| PRD | P-004 |
| Stage | 1 — closes it |
| Status | **Ready for decomposition** |
| Size | S |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-002](P-002-message-envelope.md), [P-003](P-003-crypto-suites.md) |
| Blocks | P-008, P-010, P-015, P-016 |

---

## 1. Purpose

Nonce and replay caching, expiry and clock skew, and the idempotency rule that an
identical retry returns the same outcome without re-evaluating, re-debiting, or
changing its mind.

Small, but it is where the protocol's state lives, and state is where partial
failure does its damage.

**Claims served:** Q2D-C-07 (replay resistance) directly. Q2D-C-09 depends on
this PRD for the "debit once" half — accounting is only sound if a retry cannot
charge twice.

## 2. Spec citations

| Source | What it constrains here |
|---|---|
| [`spec/core-model.md`](../../spec/core-model.md) §2.2 | `query_id`, `issued_at`, `expires_at`, `nonce` |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 2 | Advisory shed on `routing.expires_at` — never a security decision |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 6 | Authoritative expiry, post-verification |
| [`spec/core-model.md`](../../spec/core-model.md) §4 step 9 | Replay check after signature, so unauthenticated traffic cannot pollute the cache |
| [`spec/core-model.md`](../../spec/core-model.md) §7 | Idempotency; what constitutes a distinct request |
| [`spec/core-model.md`](../../spec/core-model.md) §5.3 | An identical retry never becomes an answer after approval |
| [`spec/claims.md`](../../spec/claims.md) Q2D-C-07 | Nonce, expiry, query identifier, replay cache |
| [`spec/freshness.md`](../../spec/freshness.md) §1 | Skew, validity window, retention, nonce length floor — every value this PRD used to state |
| [`spec/freshness.md`](../../spec/freshness.md) §2 | The three freshness conditions, and the exact boundary |
| [`spec/freshness.md`](../../spec/freshness.md) §3 | What a responder checks about a nonce, and what it cannot |

## 3. Module boundary

**Inside:** nonce requirements; the replay cache and its key; expiry and skew
evaluation; validity-window bounds; cache retention; the verbatim-response rule;
atomic commit of debit and cache entry.

**Explicitly outside:** the escalation lifecycle (**P-015**) — this PRD
guarantees a cached outcome is returned unchanged, and P-015 relies on that
guarantee rather than restating it. Budget arithmetic (**P-008**). Policy
(**P-007**). Signature verification (**P-003**), which must already have
succeeded before anything here runs.

## 4. Design

### 4.1 The cache is reached only by authenticated requests

The replay check sits at step 9, after signature verification at step 4.
Unauthenticated traffic therefore cannot enter the cache, and an attacker without
a valid key cannot fill it.

An attacker *with* a valid key can, which is why §4.4 bounds retention.

### 4.2 Cache key, and what counts as the same request

```
key   = (requester_principal, query_id)
value = (request_digest, response_bytes, expires_at)
```

On lookup:

| Case | Outcome |
|---|---|
| Absent | New request; proceed |
| Present, `request_digest` matches | **Replay** — return `response_bytes` verbatim |
| Present, `request_digest` differs | **Reject** — `query_id` reuse |

The third row is a decision, not a fallout. A `query_id` reused with different
content could be a requester retrying after correcting a contract, or an attacker
probing for cache confusion. Rejecting it makes one `query_id` mean one exchange,
which keeps the audit trail unambiguous and closes the confusion vector. A
requester that needs to correct a request issues a new identifier — a mild
inconvenience, and the correct behaviour, since
[`core-model.md`](../../spec/core-model.md) §7 already makes changed content a
distinct request requiring a new decision.

### 4.3 What the nonce is for

`query_id` is the audit handle. The **nonce** supplies entropy so that two
semantically identical questions asked in the same second still produce distinct
bytes and distinct digests, and so a request's digest is not predictable in
advance.

The rule is [`freshness.md`](../../spec/freshness.md) §3 and this PRD does not
restate it. **This section used to**, which was [E-49](../open-escalations.md):
it read *"minimum 128 bits, base64url, supplied by the requester — a nonce below
the minimum rejects"*, and that was a normative interoperability requirement
living in a PRD.

What the escalation found is worth carrying here, because it changes what this
module builds. **A responder cannot check entropy.** It holds one nonce and no
distribution; sixteen zero bytes have none and satisfy any length check. So §3
splits the requirement in two — 128 bits of entropy is a **requester's**
obligation, a 16-byte length floor is what a **responder** enforces — and this
module implements the second only.

This resolves [P-002](P-002-message-envelope.md)'s open question: **second-precision
timestamps are sufficient**, because uniqueness comes from the nonce and not from
the clock.

### 4.4 Expiry, skew, and why the window is bounded

The conditions and every value are
[`freshness.md`](../../spec/freshness.md) §1 and §2. This section stated them
until [E-49](../open-escalations.md), which is how the escalation was found: two
implementations reading only `spec/` would have chosen different numbers and both
passed their own tests.

Two things that landed with it change what this module builds:

- **The window bound is a range, not a ceiling.** §2's third condition rejects a
  window outside `(0, window]`, because a *negative* window is above no maximum
  and the other two conditions do not catch it — with `expires_at` ten seconds
  before `issued_at` and sixty seconds of skew, there is a seventy-second
  interval in which such a message is fresh. This PRD's table had the ceiling
  alone.
- **The boundary is exact and stated as such.** A request at exactly
  `expires_at + skew` is within tolerance. §7's acceptance already asked for
  identical behaviour at ±60 s; §2 is now where the answer is, rather than in
  whichever implementation was written first.

Leap seconds are §2.1's: `23:59:60` is evaluated as `23:59:59` throughout, which
is what `timestamp` already does and now has a normative home.

### 4.5 The response is cached, not the decision

A replay returns the **stored response bytes, verbatim**. It does not re-evaluate
and it does not re-sign.

Re-signing would regenerate `decided_at`, so two retries would differ. That
difference is observable, and it tells a requester the responder re-evaluated —
which under opaque escalation is precisely the state transition
[`core-model.md`](../../spec/core-model.md) §5.3 forbids revealing. Caching bytes
rather than decisions makes the guarantee structural instead of a rule someone
must remember.

It also makes P-015's job simple: an escalated query's cached normalized outcome
is returned unchanged for the life of the entry, regardless of what an authority
decides in the meantime.

### 4.6 Debit and cache commit together

The capacity debit and the cache entry are committed **atomically**. A crash
between them is the failure this PRD exists to prevent:

| Order | Crash consequence |
|---|---|
| Debit, then cache | Retry re-debits — **over-charges** |
| Cache, then debit | Retry returns cached response — **under-charges** |
| Atomic | Neither |

Where a store cannot offer atomicity, **debit first**. Over-charging is the
conservative direction; under-charging means more disclosure than policy
intended, and Q2D-C-09 would not hold.

### 4.7 Rejections are cached too

Any outcome reached at or after step 9 is cached, including rejections. Retries
of a rejected request are then cheap and consistent, and a rejection cannot
change to an acceptance within the window.

Rejections *before* step 9 — malformed, expired, bad signature — never reach the
cache, because they were never authenticated.

## 5. Interfaces

```
check_replay(principal, query_id, request_digest) -> Replay | Fresh | IdReuse
record(principal, query_id, request_digest, response_bytes, expires_at, debit) -> Result
   // commits the cache entry and the debit atomically

check_freshness(issued_at, expires_at, now, skew) -> Result
validate_nonce(nonce) -> Result
```

`record` taking the debit is deliberate. Two separate calls could be interleaved
or partially applied; one call cannot.

## 6. Corpus sections

`replay/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `replay/idempotent/` | Retry returns byte-identical response; no second debit |
| `replay/id-reuse/` | Same `query_id`, different digest, rejects |
| `replay/nonce/` | A nonce below the **length floor** rejects; distinct nonces yield distinct digests. Not *below-minimum entropy*, which is what this row said and what no responder can detect — [`freshness.md`](../../spec/freshness.md) §3 |
| `replay/expiry/` | Expired; issued-in-future; both skew boundaries; window above maximum |
| `replay/ordering/` | Unauthenticated request never reaches the cache |

## 7. Acceptance

- [ ] A retry returns **byte-identical** response bytes, in both implementations.
- [ ] A retry produces no second debit — asserted against the budget total, not
      against a call count.
- [ ] `query_id` reuse with a differing digest rejects.
- [ ] Both skew boundaries behave identically in both implementations, including
      at exactly ±60 s.
- [ ] A validity window outside [`freshness.md`](../../spec/freshness.md) §2's
      range rejects — above the maximum, and also zero or negative, which the
      other two conditions do not catch.
- [ ] No cache entry exists for any request rejected before step 9.
- [ ] Cache entries are evicted at retention expiry, and eviction is observable
      in a test rather than inferred.

## 8. Negative acceptance

| Must fail | Observed as |
|---|---|
| A second debit on retry | Budget total differs between one request and one request retried |
| Re-signing on replay | Two retries return differing bytes |
| Cached escalation outcome becoming an answer | The retry vector returns the normalized outcome after an approval is recorded |
| An unauthenticated request creating a cache entry | `replay/ordering/` vector shows an entry after a bad-signature request |
| `query_id` reuse silently accepted | Second request with differing digest returns the first response |
| Expiry evaluated from `routing` rather than the signed object | Vector with disagreeing routing expiry is decided on the signed value |
| Cache growth beyond retention | Entry survives past window + 2×skew |
| Under-charging after a partial failure | Injected fault between debit and cache leaves the budget short |

The last row needs a fault-injection test, not an ordinary vector. It is the
failure this PRD is most likely to actually have.

## 9. Escalate-if-changed decisions

1. **The replay check runs after verification.** Moving it earlier lets
   unauthenticated traffic fill the cache.
2. **Cache key is (principal, query_id); the digest is compared, not keyed on.**
3. **`query_id` reuse with a different digest rejects.** One identifier, one
   exchange.
4. **Response bytes are cached and returned verbatim.** Never re-signed, never
   re-evaluated.
5. **The maximum validity window bounds cache retention.** Relaxing the window
   relaxes memory bounds. Both are [`freshness.md`](../../spec/freshness.md) §1's
   now, so changing either is a specification change and not this PRD's to make.
6. **Debit and cache entry commit atomically; debit first if they cannot.**
   Over-charging is safe, under-charging is not.
7. **Outcomes at or after step 9 are cached, including rejections.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~What happens when the cache cannot accept an entry — memory pressure, store failure?~~ | **Resolved: reject the request**, as a Tier C denial. A responder that cannot guarantee idempotency must not answer: the alternative is answering while unable to recognise the retry, which double-debits and can turn a normalized outcome into an answer. The rejection happens **before** the debit, so a cache failure costs the requester its request and the custodian nothing. It is a Tier C cause like any other — a distinguishable "cache unavailable" response would report custodian internal state |
| ~~Multi-instance responders sharing a cache~~ | **Answered:** single instance. Atomic debit-and-cache does not survive horizontal scaling without a distributed transaction. [P-013](P-013-https-binding.md) §4.6 |
| ~~Does an expired-but-cached entry still suppress a duplicate debit after eviction?~~ | **Resolved: no.** Once evicted, the entry is gone and a resubmission is a new request. This is safe only because §4.2 bounds the window: retention is `window + 2×skew`, and a query whose `expires_at` has passed is rejected at step 6 before the cache is consulted at step 9 — so a resubmission after eviction cannot reach the debit, because it cannot get past expiry. The two bounds are one mechanism and neither may be relaxed alone |
| ~~Should the 5-minute window be configurable downward?~~ | **Resolved: downward only.** Five minutes is the ceiling, configuration may lower it, and startup fails on a configured value above it rather than clamping. A longer window widens the interval in which a captured envelope is still replayable; a shorter one only costs a requester the ability to retry late, which is a local inconvenience rather than a protocol weakening |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Nonce length floor | `replay/nonce/` passes. **Renamed from *minimum entropy*** — [`freshness.md`](../../spec/freshness.md) §3 splits the requirement, and the half a responder can enforce is a length floor |
| 2 | Replay cache store with retention and eviction | Eviction observable in test; open question 1 resolved |
| 3 | `check_replay` with the three-way outcome | `replay/idempotent/` and `replay/id-reuse/` pass |
| 4 | `check_freshness` with skew and window bound | `replay/expiry/` passes, both boundaries exact, and a zero or negative window rejects |
| 5 | `record` — atomic debit and cache commit | Fault-injection test shows no under-charge |
| 6 | Verbatim response storage and return | Two retries byte-identical |
| 7 | Ordering assertion: cache unreachable before step 9 | `replay/ordering/` passes |
| 8 | Author `replay/` corpus section | Five groups; `harness lint` clean |
| 9 | Cache-failure rejection, eviction semantics, and the window bound | A store failure produces a Tier C denial with no debit; an evicted entry does not suppress a debit; a configured window above five minutes fails at startup |

Issue 5 is the one to schedule time for — the fault-injection harness is more
work than the logic it tests, and issue 9's cache-failure path is tested through
the same harness.
