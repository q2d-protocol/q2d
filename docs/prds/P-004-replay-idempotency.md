# P-004 — Replay, expiry, idempotency

| Field | Detail |
|---|---|
| PRD | P-004 |
| Stage | 1 — closes it |
| Status | **Ready for decomposition** |
| Size | S |
| Risk | medium |
| Depends on | [P-001](P-001-conformance-corpus.md), [P-002](P-002-message-envelope.md), [P-003](P-003-crypto-suites.md) |
| Blocks | P-010, P-016 — ~~P-008, P-015~~ **deferred 2026-08-19** |


> **Reading this PRD after the 2026-08-19 scope reduction.**
>
> Where the sections below reason about the **disclosure-capacity budget**
> ([`claims.md`](../../spec/claims.md) Q2D-C-09, *not attempted in this release*)
> or the **escalation lifecycle** ([P-015](P-015-escalation-lifecycle.md),
> deferred), that reasoning is **preserved as written and is not a requirement of
> this release**.
>
> **What governs what gets built:** the **issue list**, the **acceptance** and
> **negative-acceptance** tables, and the **corpus-section** table. Struck rows in
> any of those say what does not. Design prose does not govern. Design prose has deliberately *not* been rewritten to
> remove deferred concepts: it records why each decision was made, and deleting
> it would leave the decisions standing with their reasons removed — which is
> worse than a reader having to hold one caveat.
>
> Deferred PRDs keep their numbers and their issue lists. Nothing was withdrawn.

---

## 1. Purpose

Nonce and replay caching, expiry and clock skew, and the idempotency rule that an
identical retry returns the same outcome without re-evaluating or changing its
mind. (*Re-debiting* until 2026-08-19 — Q2D-C-09 is not attempted, and not
re-evaluating is the property Q2D-C-07 claims.)

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
the **order** in which the debit and the cache entry are committed, and the rule
that they must be committed together.

**Inside as a rule, and not as a mechanism:** the atomic commit itself. §4.6
requires it; `record` cannot provide it, because the cache write is not inside
anything a caller can open or close. The transaction that delivers it is
[P-010](P-010-responder-pipeline.md) §5's, over the single store
[P-008](P-008-capacity-accounting.md)'s open question 3 resolved to. This PRD
therefore owns the requirement and the fallback order; neither of the two
modules that own the mechanism may weaken it.

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

key   = (requester_principal, nonce)          // E-50
value = (request_digest, expires_at)
```

On lookup, in this order:

| # | Index | Case | Outcome |
|---|---|---|---|
| 1 | `query_id` | present, `request_digest` matches | **Replay** — return `response_bytes` verbatim |
| 2 | `query_id` | present, `request_digest` differs | **Reject** — `query_id` reuse |
| 3 | nonce | present | **Reject** — nonce reuse ([E-50](../open-escalations.md)) |
| 4 | — | neither | New request; proceed |

**The `query_id` index is read first, and the order is load-bearing.** A genuine
retry matches *both* — same identifier and same nonce, by construction — so a
nonce-first order would have to carve out an exception for the case that happens
most, and a rule with an exception for its common case is a rule waiting to be
got wrong.

Row 3 needs no digest comparison. Reaching it means the `query_id` index held
nothing, and equal digests would imply equal signed bytes and therefore the same
`query_id` — so a nonce found here was used over *different* content, which is
what [`core-model.md`](../../spec/core-model.md) §5.2.1 rejects.

Row 2 is a decision, not a fallout. A `query_id` reused with different
content could be a requester retrying after correcting a contract, or an attacker
probing for cache confusion. Rejecting it makes one `query_id` mean one exchange,
which keeps the audit trail unambiguous and closes the confusion vector. A
requester that needs to correct a request issues a new identifier — a mild
inconvenience, and the correct behaviour, since
[`core-model.md`](../../spec/core-model.md) §7 already makes changed content a
distinct request requiring a new decision.

### 4.3 What the nonce is for

`query_id` is the audit handle. The **nonce** makes a request digest
unpredictable in advance, and is the value
[`conformance-classes.md`](../../spec/conformance-classes.md) CC-5 and CC-6 bind
evidence to.

**This paragraph used to say more, and the extra part was wrong.** It said the
nonce is what makes two semantically identical questions in the same second
produce distinct bytes — but two distinct exchanges carry different `query_id`s
and so already differ. Distinctness comes from the identifier;
[E-50](../open-escalations.md) found it while settling the index, and
[`freshness.md`](../../spec/freshness.md) §3.1 records the correction.

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

P-002's open question stays resolved — **second-precision timestamps are
sufficient** — but on the identifier rather than on the nonce, which is the
correction above.

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

The capacity debit and the cache entry are committed by **one call**, in one
order. A crash between them is the failure this section exists to bound:

| Order | Crash consequence |
|---|---|
| Debit, then cache | Retry re-debits — **over-charges** |
| Cache, then debit | Retry returns cached response — **under-charges** |
| Atomic | Neither |

Where a store cannot offer atomicity, **debit first**. Over-charging is the
conservative direction; under-charging means more disclosure than policy
intended, and Q2D-C-09 would not hold.

**This section used to open by saying the two are committed atomically**, and
issue 5 found that `record` alone cannot deliver that — at any store, by any
caller. It settles and then writes, and the write is not inside anything a
caller can open or close, so no implementation of the sink encloses it.

**The third row needs a transaction, and the transaction is not this module's.**
[P-010](P-010-responder-pipeline.md) §5 already describes it: step 18 stages the
debit rather than writing through, step 19 produces the response bytes, and the
commit — debit, grant consumption, and cache entry together — is the last act of
the exchange. [P-008](P-008-capacity-accounting.md)'s resolved open question 3 is
what makes that local rather than distributed, putting the budget and the replay
cache in **one store**, because two would need a distributed transaction and
[P-013](P-013-https-binding.md) §4.6 declines to solve that.

So the third row is reached by building those two things, and until they exist
`record` takes the first, which is what issue 5 built and what its row says is
left.

**What is settled here is a reservation, not a quantity.**
[P-008](P-008-capacity-accounting.md) §5's `check` returns a reservation rather
than a boolean so that a caller *"cannot check and then debit later without
holding the thing that reserved the capacity"*, and §5 there says `settle` is
called from this module's `record`. A millibit count in `record`'s signature
would hand that property straight back — anyone could commit an entry against a
number they invented, having reserved nothing. So this module never sees an
amount.

**The first row's over-charge is permanent, and reservation expiry does not
bound it.** Two partial failures are easy to run together and are not the same
one. A reservation that is *never settled* is released or expires
([P-010](P-010-responder-pipeline.md) §4.7), and the capacity returns — that
covers every interruption before this call. The row above is the other case:
`settle` **succeeded** and the crash came after it, so the capacity is spent, no
entry exists, and the retry spends it again. Nothing gives that back.

Which is why the third row is the arrangement to build rather than a nicety, and
why one store is only half of it: a shared store removes the *need* for a
distributed transaction, and the transaction still has to be opened. Until both
are there the over-charge is real and permanent, and the only argument for it is
that the alternative is worse.

### 4.7 Rejections are cached too

Any outcome reached at or after step 9 is cached, including rejections. Retries
of a rejected request are then cheap and consistent, and a rejection cannot
change to an acceptance within the window.

Rejections *before* step 9 — malformed, expired, bad signature — never reach the
cache, because they were never authenticated.

## 5. Interfaces

```
check_replay(principal, query_id, nonce, request_digest)
   -> Fresh | Replay(response_bytes) | QueryIdReuse | NonceReuse
   // four outcomes since E-50; the `query_id` index is read before the nonce
   // index, because a genuine retry matches both
record(budget, principal, query_id, nonce, request_digest, response_bytes, expires_at, reservation?) -> Result
   // settles P-008's reservation, if there is one, and commits the cache entry
   // — in §4.6's order

check_freshness(issued_at, expires_at, now, skew) -> Result
validate_nonce(nonce) -> Result
```

`record` taking the debit is deliberate. Two separate calls could be interleaved,
and a caller could forget the second; one call cannot be either.

**It can still be partially applied**, which this note used to deny: §4.6's first
row is exactly that state, and the sentence claimed the interface closed a window
only a shared store closes. What one call buys is that the two writes cannot be
*separated by a caller* — not that they cannot be separated by a crash.

`budget` is the sink the debit is settled against, and it is a **parameter rather
than something this module holds**, because §3 puts the arithmetic in
[P-008](P-008-capacity-accounting.md) and §4.6 puts the *commit* here. It was
absent from this list until issue 5 was built, which read as though `record` did
the arithmetic itself. Its contract is the one thing §4.6's guarantee rests on:
a refusal means **nothing was committed**.

**The last parameter was `debit` and is now `reservation`**, reconciling this
list with [P-008](P-008-capacity-accounting.md) §5, which has said since it was
written that `settle(reservation)` is called from here. Read as a quantity — which
is how it was built first — it defeats the reason `check` returns a reservation at
all. This module treats it as opaque: it never inspects an amount, so it has no
opinion about one, and a value that is negative or absurd is refused where the
arithmetic is.

**It is also optional**, because §4.7 caches every outcome from step 9 onward and
most of them never reach the budget — a rate-limit rejection at 9a, an unknown
predicate at 10, a schema or constraint failure at 11 and 11a, a policy denial at
14. [E-01](../open-escalations.md) settled that neither `deny` nor `escalate`
debits, so those have nothing to settle. Requiring a reservation would leave a
caller either not caching denials, which breaks §4.7 and lets a denial become an
answer on retry, or minting an empty one, which is a debit-shaped object where
E-01 says none belongs. **This module cannot tell an answer from a denial and
does not try**: an absent reservation is the caller's assertion that nothing was
released, and step 18 is where that assertion is made.

## 6. Corpus sections

`replay/` — authored under this PRD.

| Group | Vectors |
|---|---|
| `replay/idempotent/` | Retry returns byte-identical response; **no second evaluation** (was *no second debit*, retargeted 2026-08-19). A **`process_sequence`** vector of two identical requests — [E-51](../open-escalations.md) resolved the format question these two were blocked on |
| `replay/id-reuse/` | Same `query_id`, different digest, rejects. Two requests, the second refused: what makes the identifier a *reuse* is the first, which is why neither of these could be one vector until E-51 |
| `replay/nonce/` | A nonce below the **length floor** rejects; distinct nonces yield distinct digests. Not *below-minimum entropy*, which is what this row said and what no responder can detect — [`freshness.md`](../../spec/freshness.md) §3 |
| `replay/expiry/` | Expired; issued-in-future; both skew boundaries; window above maximum |
| `replay/ordering/` | Unauthenticated request never reaches the cache |

## 7. Acceptance

- [ ] A retry returns **byte-identical** response bytes, in both implementations.
- [ ] A retry produces **no second evaluation and no second quota tick** —
      asserted against the quota total and against the returned bytes, not
      against a call count. **Retargeted 2026-08-19**: this said *no second
      debit, asserted against the budget total*, and Q2D-C-09 is not attempted,
      so there is no budget total to compare. The property Q2D-C-07 actually
      claims is that the retry returns the **stored bytes**, which is the
      stronger observable and was always available.
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
| A second **evaluation** on retry | The retry reaches the predicate rather than returning stored bytes — the observable Q2D-C-07 actually claims. **Retargeted 2026-08-19** from *a second debit, observed as a differing budget total*: Q2D-C-09 is not attempted and there is no total to differ |
| Re-signing on replay | Two retries return differing bytes |
| Cached escalation outcome becoming an answer | The retry vector returns the normalized outcome after an approval is recorded |
| An unauthenticated request creating a cache entry | `replay/ordering/` vector shows an entry after a bad-signature request |
| `query_id` reuse silently accepted | Second request with differing digest returns the first response |
| Expiry evaluated from `routing` rather than the signed object | Vector with disagreeing routing expiry is decided on the signed value |
| Cache growth beyond retention | Entry survives past [`freshness.md`](../../spec/freshness.md) §1's retention instant |
| An entry evicted while its request is still acceptable | A retry within the skew tail after `expires_at` is treated as fresh and debits again |
| ~~Under-charging after a partial failure~~ | **Struck 2026-08-19** — an injected fault between debit and cache left the *budget* short, and there is no budget. The commit's remaining halves are the quota tick and the cache entry |

The last row needs a fault-injection test, not an ordinary vector. It is the
failure this PRD is most likely to actually have.

## 9. Escalate-if-changed decisions

1. **The replay check runs after verification.** Moving it earlier lets
   unauthenticated traffic fill the cache.
2. **Cache key is (principal, query_id); the digest is compared, not keyed on.**
   **A second index on (principal, nonce) carries the other half** —
   [`core-model.md`](../../spec/core-model.md) §5.2.1 rejects a `query_id`
   **or nonce** reused over different content, and a nonce reused under a new
   identifier shares no key with its first use ([E-50](../open-escalations.md)).
   Both indexes are written together and evicted together, and the nonce index is
   scoped to the requester so no peer can exhaust another's values.
3. **`query_id` reuse with a different digest rejects.** One identifier, one
   exchange.
4. **Response bytes are cached and returned verbatim.** Never re-signed, never
   re-evaluated.
5. **The maximum validity window bounds cache retention.** Relaxing the window
   relaxes memory bounds. Both are [`freshness.md`](../../spec/freshness.md) §1's
   now, so changing either is a specification change and not this PRD's to make.
6. **The quota tick and the cache entry are committed together, and where they
   cannot be, the tick goes first.** Over-counting is safe, under-counting is
   not. **Retargeted 2026-08-19** — this said *debit*, and Q2D-C-09 is not
   attempted. The ordering rule is unchanged and the reasoning in §4.6 stands
   as written: it was never about what was being committed, only about which of
   two writes survives a crash. The order is decided here and is built; the atomic commit is decided
   here and is **built elsewhere** — §4.6 and issue 5 say where. Both halves are
   escalate-if-changed, and the second is the one most likely to be quietly
   dropped, because the module that requires it is not the module that provides
   it.
7. **Outcomes at or after step 9 are cached, including rejections.**

## 10. Open questions

| Question | Belongs to |
|---|---|
| ~~Does step 9 track nonces as well as `query_id`s?~~ | **Resolved: yes — a second index on `(principal, nonce)`** ([E-50](../open-escalations.md)). §4.2 covered the `query_id` half and not the nonce half, since a nonce reused under a new identifier shares no key with its first use. The recommendation was to read [`core-model.md`](../../spec/core-model.md) §5.2.1 loosely and amend it; that was refused, and rightly — the specification governs, and *the implementation does not do this* is not evidence the specification is wrong. §5.2.1 is **unchanged**. The rule is [`freshness.md`](../../spec/freshness.md) §3.1 and it refuses only requester bugs, since a collision at 128 bits is negligible |
| ~~What happens when the cache cannot accept an entry — memory pressure, store failure?~~ | **Resolved: reject the request**, as a Tier C denial. A responder that cannot guarantee idempotency must not answer: the alternative is answering while unable to recognise the retry, which double-debits and can turn a normalized outcome into an answer. The rejection happens **before** the debit, so a cache failure costs the requester its request and the custodian nothing. It is a Tier C cause like any other — a distinguishable "cache unavailable" response would report custodian internal state |
| ~~Multi-instance responders sharing a cache~~ | **Answered:** single instance. Atomic debit-and-cache does not survive horizontal scaling without a distributed transaction. [P-013](P-013-https-binding.md) §4.6 |
| ~~Does an expired-but-cached entry still suppress a duplicate debit after eviction?~~ | **Resolved: no.** Once evicted, the entry is gone and a resubmission is a new request. This is safe only because [`freshness.md`](../../spec/freshness.md) §1 retains an entry **through `expires_at + skew` inclusive**, which is exactly as long as §2 still accepts the request — §2's comparison is strict, so that instant is inside the window and eviction is permitted only from the first instant §2 would reject. Eviction and expiry therefore cannot leave an interval in which a retry is accepted by a cache that has forgotten it. **The reason stated here was wrong until review caught it**: it said a resubmission cannot reach the debit because expiry rejects it at step 6, which is false for the skew tail after `expires_at`. The two bounds are one mechanism and neither may be relaxed alone |
| **Two identical requests in flight at once.** `check` and `record` are separate calls with no state between them, so two copies of one request arriving together both read `Fresh`, both evaluate, and both settle their own reservation — two debits for one exchange, and the second entry replacing the first. [P-008](P-008-capacity-accounting.md) §4.5 answers the *budget* half of concurrency, and only that half: reservations keep the total inside the limit, and say nothing about one exchange being paid for twice. §10's multi-instance row is a different question and was answered *single instance*, which does not help — one daemon serves concurrent requests. The resolutions are a design choice rather than a reading of the spec: an in-flight marker in the cache, or per-key serialization in the pipeline. **Raised by review of issue 5, and not resolved here** — it is a property of the pipeline, so it belongs with [P-010](P-010-responder-pipeline.md) alongside issue 7 | [P-010](P-010-responder-pipeline.md) |
| ~~Should the validity window be configurable downward?~~ | **Resolved: downward only, and it is now [`freshness.md`](../../spec/freshness.md) §1's rule** rather than this PRD's — configuration may only make a responder stricter, and a value on the wrong side of a bound fails at startup rather than being clamped. A longer window widens the interval in which a captured envelope is still replayable; a shorter one only costs a requester the ability to retry late, which is a local inconvenience rather than a protocol weakening |

## 11. Issues

| # | Issue | Done when |
|---|---|---|
| 1 | Nonce length floor | **Built** — [`src/freshness.rs`](../../src/freshness.rs) and [`freshness.go`](../../freshness.go); `replay/nonce/` waits on issue 8. **Renamed from *minimum entropy***: [`freshness.md`](../../spec/freshness.md) §3 splits the requirement, and the half a responder can enforce is a length floor. The floor is on the **decoded bytes**, and a test asserts the 22-character length a string check would have compared instead. A second test passes thirty-two zero bytes and expects success — it exists so nobody later reads the floor as an entropy check, since a responder holds one nonce and no distribution and there is nothing to measure. Two internal reasons, because a nonce that will not decode and one that is too short are different mistakes in a requester's own serializer; one wire value, `malformed`, at step 5 |
| 2 | Replay cache store with retention and eviction | **Built** — [`src/replay.rs`](../../src/replay.rs) and [`replay.go`](../../replay.go). Eviction reports a count, so it is observable rather than inferred: a sweep that silently did nothing looks identical to one that worked. **Retention is applied on read as well as by the sweep**, so idempotency does not depend on when a timer last fired, and the boundary is inclusive at [`freshness.md`](../../spec/freshness.md) §1's instant — an entry hidden one second early lets a retry through as fresh and debits twice. The store holds no opinion about whether a digest matches; that is issue 3, and a store with one would be a second place the idempotency rule lives. **Open question 1's cache-failure path is issue 9** and is not built. The **nonce index** landed with [E-50](../open-escalations.md): written and evicted with the primary one, scoped to the requester, and reporting what a nonce was last attached to without drawing a conclusion from it |
| 3 | `check_replay` with the **four**-way outcome | **Built**; the vectors wait on issue 8. Fresh, replay, `query_id` reuse, nonce reuse — [E-50](../open-escalations.md) added the fourth and issue 2 built the index it reads. **The `query_id` index is consulted first**, because a genuine retry matches both and a nonce-first order would have to special-case it; a rule with an exception carved out for the common case is a rule waiting to be got wrong. The two rejections are a **separate type from `Rejected`**, which settles what this row asked: every reason in that type maps to a value [`core-model.md`](../../spec/core-model.md) §5.2.1 fixes, and these two do not — §5.2.1 gives everything from step 9 onward the value the responder's **pinned registry** declares, which is data. A constant would compile one deployment's configuration into every deployment, so the type reports the internal reason and the step and says nothing about the wire. P-009 reads the registry |
| 4 | `check_freshness` with skew and window bound | **Built**; `replay/expiry/` waits on issue 8. Both boundaries asserted **at** the tolerance, not near it, in both implementations. The window is a range and a test walks the interval [`freshness.md`](../../spec/freshness.md) §2's counterexample describes — 111 values of `now` for which a ceiling-only implementation calls a negative window fresh — so the lower bound cannot be dropped silently. A timestamp §2.2 refuses is reported `malformed` rather than `expired`: the fault is in the requester's serializer, and `expired` would send them to their clock |
| 5 | `record` — atomic **quota tick** and cache commit *(was: debit)* | **Half done, and the half that is left is not this module's** — [`src/replay.rs`](../../src/replay.rs) and [`replay.go`](../../replay.go). What is built is §4.6's **first row**: `record` settles, then writes, in one call. What is *not* built is the third row, and review established that `record` cannot reach it at any store or by any caller — it settles and then writes, and the write is not inside anything a caller can open or close. The atomic row needs the transaction [P-010](P-010-responder-pipeline.md) §5 already describes, staging the debit at step 18 and committing it with the bytes step 19 produces, over the single store [P-008](P-008-capacity-accounting.md)'s open question 3 resolved to. Both are those PRDs'. **`record` settles a reservation and never sees an amount.** Built first taking a millibit `debit`, and that was wrong: P-008 §5 has always said `settle(reservation)` is called from here, and `check` returns a reservation precisely so a caller *"cannot check and then debit later without holding the thing that reserved the capacity"* — which a number as a parameter hands straight back. Opaque, so this module has no arithmetic to do and no value to get wrong, and the negative-value refusal an earlier version made here belongs where the arithmetic is. **The reservation is optional**, since §4.7 caches denials and [E-01](../open-escalations.md) gives them nothing to settle — review found the first version requiring one, which would have forced a caller to skip caching them or to mint an empty one. **`insert` is now private**: with a commit path that carries the debit, an exported writer that took none was a second path with the debit left out. **The fault injection refuses the way the contract says a refusal works** — nothing committed — and the crash *after* a successful settle is reached without it, by doing what `record` does and stopping where it would have stopped; the first version produced that state by having the sink apply a debit and then report failure, which contradicts the one thing `record` relies on. The retry then pays **twice**, which is §4.6's accepted direction written down as a test rather than as prose |
| 6 | Verbatim response storage and return | **Built**, and asserted as *two retries are equal* rather than as *the bytes are right* — the property is that nothing regenerates. Re-signing would remake `decided_at`, so two retries would differ, and that difference tells a requester the responder re-evaluated, which under opaque escalation is the transition [`core-model.md`](../../spec/core-model.md) §5.3 forbids revealing. Caching bytes rather than decisions makes it structural. Go copies on the way in and out (`CONVENTIONS-go.md`); Rust has it from the borrow checker |
| 7 | Ordering assertion: cache unreachable before step 9 | **Blocked on [P-010](P-010-responder-pipeline.md), and not on anything here.** Ordering is a property of the pipeline: a vector must show that a bad-signature request left no entry, which needs `process_query` — every `ordering/` vector uses it, because a `verify_query` vector cannot show that one step ran before another. The store deliberately does **not** enforce the ordering itself and says so at the type: a caller could insert at any point, and the assertion that the pipeline does not is this issue's |
| 8 | Author `replay/` corpus section | **Not authorable yet, and not for one reason.** Checked group by group rather than assumed: `expiry/` asserts step 6 and `ordering/` asserts step 9, both of which need `process_query` — a `verify_query` vector cannot show one step ran before another, which is why every existing `ordering/` vector uses it. `nonce/` needs an operation that calls this module's floor check, and `verify_query` is not it: P-003's sequence must not depend on P-004, or the two PRDs' dependency runs both ways. All three therefore wait on [P-010](P-010-responder-pipeline.md). `idempotent/` and `id-reuse/` waited on something else entirely — a vector could not describe a sequence — and **[E-51](../open-escalations.md) is now closed as C**, adding `process_sequence`: one operation whose input is an ordered list of requests. Those two are therefore no longer blocked on the *format*. They are still blocked on [P-010](P-010-responder-pipeline.md), because what the sequence runs through is the §4 pipeline and nothing implements it yet — so the whole issue moves behind one blocker instead of two, which is the useful change |
| 9 | Cache-failure rejection, eviction semantics, and the window bound | A store failure produces a **normalized denial**, and — since Q2D-C-09 is not attempted — **nothing is debited because there is nothing to debit**; an evicted entry does not suppress a **quota tick**, which is counted at step 9a and never rolled back (§9.1); a configured window above [`freshness.md`](../../spec/freshness.md) §1's maximum fails at startup |

Issue 5 was expected to be the one to schedule time for, on the reasoning that a
fault-injection harness is more work than the logic it tests. **It was not**, and
the reason is worth carrying to issue 9, which was to be tested through the same
harness: once the debit sink is a parameter, injecting a fault is a test double
that refuses — and it refuses the way the sink's contract says, committing
nothing. The case that mattered, a crash *after* a successful settle, needs no
injection at all, because a test can settle and then stop where `record` would
have stopped. A double that applied a debit and then reported failure would
contradict the contract and assert the behaviour of a store the interface
forbids; the first version did exactly that, and review caught it. A harness was
the right instinct for a store this module owned, and it does not own one.

What that leaves for issue 9 is unchanged and not yet checked group by group. Its
cache-failure half needs a cache store that *can* fail, and this module's cannot
— the indexes are in memory — so where that seam belongs is a question issue 9
has to answer rather than inherit from here.
