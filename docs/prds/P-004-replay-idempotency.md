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
living in a PRD. It also did not say what the minimum was measured on, which §3
now does: the **decoded bytes**, not the string, since the two differ by a factor
this module would otherwise have got to choose.

What the escalation found is worth carrying here, because it changes what this
module builds: **a responder cannot check entropy.** It holds one nonce and no
distribution, and a nonce of the right length made entirely of zero bytes
satisfies every check available to it. So §3 splits the requirement between the
two parties, and **this module implements the responder's half only** — the
length floor. The entropy requirement is real and is not this module's to
enforce.

This resolves [P-002](P-002-message-envelope.md)'s open question: **second-precision
timestamps are sufficient**, because uniqueness comes from the nonce and not from
the clock.

### 4.4 Expiry, skew, and the window bound

The three conditions, every value, and the reasoning behind each are
[`freshness.md`](../../spec/freshness.md) §1 and §2.

This section used to state them, which is how [E-49](../open-escalations.md) was
found: two implementations reading only `spec/` would have chosen different
numbers and both passed their own tests. Writing §2 also corrected the rule this
section had — the window bound is a **range and not a ceiling** — and the
correction is in §2 with the counterexample that motivates it, rather than
repeated here where it would be a second copy of the reasoning as well as of the
number.

What it means for this module is that `check_freshness` has three conditions and
the third is two-sided.

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
- [ ] Both skew boundaries behave identically in both implementations, **at
      exactly the tolerance** — [`freshness.md`](../../spec/freshness.md) §2 makes
      the comparison strict, so a request at exactly `expires_at + skew` is
      within it.
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
| Cache growth beyond retention | Entry survives past [`freshness.md`](../../spec/freshness.md) §1's retention instant |
| An entry evicted while its request is still acceptable | A retry within the skew tail after `expires_at` is treated as fresh and debits again |
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
| **Does step 9 track nonces as well as `query_id`s?** | **Open — [E-50](../open-escalations.md).** §4.2 keys the cache on `(principal, query_id)` and compares the digest, and §9 item 2 makes that escalate-if-changed. [`core-model.md`](../../spec/core-model.md) §5.2.1 says step 9 rejects *"a `query_id` **or nonce** reused over different content"*, which either means the nonce *of* that identifier — already covered by the digest comparison — or requires a second index this PRD does not describe. Raised by review of issue 2; the store is built to §4.2 meanwhile. It bites at **issue 3**, where the three-way outcome is decided |
| ~~What happens when the cache cannot accept an entry — memory pressure, store failure?~~ | **Resolved: reject the request**, as a Tier C denial. A responder that cannot guarantee idempotency must not answer: the alternative is answering while unable to recognise the retry, which double-debits and can turn a normalized outcome into an answer. The rejection happens **before** the debit, so a cache failure costs the requester its request and the custodian nothing. It is a Tier C cause like any other — a distinguishable "cache unavailable" response would report custodian internal state |
| ~~Multi-instance responders sharing a cache~~ | **Answered:** single instance. Atomic debit-and-cache does not survive horizontal scaling without a distributed transaction. [P-013](P-013-https-binding.md) §4.6 |
| ~~Does an expired-but-cached entry still suppress a duplicate debit after eviction?~~ | **Resolved: no.** Once evicted, the entry is gone and a resubmission is a new request. This is safe only because [`freshness.md`](../../spec/freshness.md) §1 retains an entry **through `expires_at + skew` inclusive**, which is exactly as long as §2 still accepts the request — §2's comparison is strict, so that instant is inside the window and eviction is permitted only from the first instant §2 would reject. Eviction and expiry therefore cannot leave an interval in which a retry is accepted by a cache that has forgotten it. **The reason stated here was wrong until review caught it**: it said a resubmission cannot reach the debit because expiry rejects it at step 6, which is false for the skew tail after `expires_at`. The two bounds are one mechanism and neither may be relaxed alone |
| ~~Should the validity window be configurable downward?~~ | **Resolved: downward only, and it is now [`freshness.md`](../../spec/freshness.md) §1's rule** rather than this PRD's — configuration may only make a responder stricter, and a value on the wrong side of a bound fails at startup rather than being clamped. A longer window widens the interval in which a captured envelope is still replayable; a shorter one only costs a requester the ability to retry late, which is a local inconvenience rather than a protocol weakening |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Nonce length floor | **Built** — [`src/freshness.rs`](../../src/freshness.rs) and [`freshness.go`](../../freshness.go); `replay/nonce/` waits on issue 8. **Renamed from *minimum entropy***: [`freshness.md`](../../spec/freshness.md) §3 splits the requirement, and the half a responder can enforce is a length floor. The floor is on the **decoded bytes**, and a test asserts the 22-character length a string check would have compared instead. A second test passes thirty-two zero bytes and expects success — it exists so nobody later reads the floor as an entropy check, since a responder holds one nonce and no distribution and there is nothing to measure. Two internal reasons, because a nonce that will not decode and one that is too short are different mistakes in a requester's own serializer; one wire value, `malformed`, at step 5 |
| 2 | Replay cache store with retention and eviction | **Built** — [`src/replay.rs`](../../src/replay.rs) and [`replay.go`](../../replay.go). Eviction reports a count, so it is observable rather than inferred: a sweep that silently did nothing looks identical to one that worked. **Retention is applied on read as well as by the sweep**, so idempotency does not depend on when a timer last fired, and the boundary is inclusive at [`freshness.md`](../../spec/freshness.md) §1's instant — an entry hidden one second early lets a retry through as fresh and debits twice. The store holds no opinion about whether a digest matches; that is issue 3, and a store with one would be a second place the idempotency rule lives. **Open question 1's cache-failure path is issue 9** and is not built |
| 3 | `check_replay` with the three-way outcome | `replay/idempotent/` and `replay/id-reuse/` pass |
| 4 | `check_freshness` with skew and window bound | **Built**; `replay/expiry/` waits on issue 8. Both boundaries asserted **at** the tolerance, not near it, in both implementations. The window is a range and a test walks the interval [`freshness.md`](../../spec/freshness.md) §2's counterexample describes — 111 values of `now` for which a ceiling-only implementation calls a negative window fresh — so the lower bound cannot be dropped silently. A timestamp §2.2 refuses is reported `malformed` rather than `expired`: the fault is in the requester's serializer, and `expired` would send them to their clock |
| 5 | `record` — atomic debit and cache commit | Fault-injection test shows no under-charge |
| 6 | Verbatim response storage and return | Two retries byte-identical |
| 7 | Ordering assertion: cache unreachable before step 9 | `replay/ordering/` passes |
| 8 | Author `replay/` corpus section | Five groups; `harness lint` clean |
| 9 | Cache-failure rejection, eviction semantics, and the window bound | A store failure produces a Tier C denial with no debit; an evicted entry does not suppress a debit; a configured window above [`freshness.md`](../../spec/freshness.md) §1's maximum fails at startup |

Issue 5 is the one to schedule time for — the fault-injection harness is more
work than the logic it tests, and issue 9's cache-failure path is tested through
the same harness.
