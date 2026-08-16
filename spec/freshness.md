# Q2D Freshness and Replay Bounds — version 0.1

**Protocol version:** 0.1 (pre-release)
**Document status:** Specification spine — working draft, not yet a normative specification.

[`core-model.md`](core-model.md) §4 step 6 requires an *"expiry and clock-skew
check"* and §4 step 9 a replay-cache check. Both are mechanisms stated without
magnitudes, and a magnitude is what a requester and a responder have to agree on
before either can build a request the other accepts. This document supplies them.

Interoperability, not tuning. A requester whose custodian permits a ten-minute
validity window builds queries a five-minute responder rejects, and neither party
is wrong about anything else written down — so these values belong where both
parties read them rather than in either one's implementation notes.

Terms: [`terminology.md`](terminology.md). Exchange:
[`core-model.md`](core-model.md). Timestamp spelling:
[`core-model.md`](core-model.md) §2.2.

---

## 1. The bounds

| Bound | Value | Configurable |
|---|---|---|
| Clock skew tolerance | 60 s | downward |
| Maximum validity window, `expires_at − issued_at` | 300 s | downward |
| Replay-cache retention, per entry | through `expires_at + skew` **inclusive** | derived, not set |
| Minimum `nonce` length | 16 bytes | upward |

**Configuration may only make a responder stricter, and a value on the wrong
side of a bound fails at startup rather than being clamped.** A clamped
misconfiguration reads as success: the operator believes they configured
something they did not, and the belief survives until the day it matters. This is
the same rule [`crypto-suites.md`](crypto-suites.md) §4 states for the suite
floor, for the same reason.

Retention has no independent value because it is not an independent decision. **A
request stays replayable for exactly as long as it stays valid, so the cache must
retain its entry for exactly that long.** Setting retention separately would
either evict entries that can still be replayed, which readmits a replay, or
retain entries that cannot, which is memory spent on nothing. Both directions are
wrong, so it is derived.

**It is derived per entry, and from `expires_at + skew` rather than from a
duration.** §2's first condition rejects only when `now` is *strictly* greater
than `expires_at + skew`, so a request is still acceptable **at** that instant
and an entry must be retained through it. Eviction is permitted from the first
instant §2 would reject the request and not before.

The inclusive boundary is not pedantry: it is the same strictness §2 states for
its comparisons, and the two have to agree or the cache and the freshness check
disagree at exactly one second. An entry evicted at the signed `expires_at`
disagrees for a **whole skew-length interval**, in which a retry is accepted by a
cache that no longer recognises it — which debits twice and can turn a normalized
outcome into an answer, the two failures this mechanism exists to prevent.
Stating retention as a duration invites that off-by-one, because the natural
instant to measure a duration from is the one the message names.

`window + 2 × skew` is what that derivation **bounds** any single entry to, and
it is the memory argument rather than the rule: a request is acceptable over
`[issued_at − skew, expires_at + skew]`, whose length cannot exceed the window
plus skew at each end. Bounding the window is therefore what bounds the cache,
and the two may not be relaxed independently.

An unbounded validity window would therefore mean unbounded retention, which is
a memory-exhaustion path available to any holder of a valid key — and
[`core-model.md`](core-model.md) §4 step 9 places the cache after verification
precisely so that only such a holder can reach it.

## 2. Freshness

Evaluated at [`core-model.md`](core-model.md) §4 step 6, on the **verified core
object**. Step 2 may shed load on `routing.expires_at`, and that is advisory: a
responder that sheds has answered nothing, and a responder that proceeds decides
here on the signed value. No freshness decision is ever taken on `routing`.

Three rejections, all with `external_reason` `expired`:

| Condition | Meaning |
|---|---|
| `now > expires_at + skew` | expired |
| `now < issued_at - skew` | issued in the future |
| `expires_at - issued_at` is not in `(0, window]` | validity window unusable or above the maximum |

The comparisons are **strict**: a request at exactly `expires_at + skew` is
within tolerance and a request at exactly `issued_at - skew` is too. Stating the
boundary rather than the neighbourhood is deliberate — two implementations that
agree on "about sixty seconds" disagree at second sixty, and that disagreement is
invisible until a vector lands on it.

The third condition is a **range and not a ceiling**, and the lower end is not
decoration. A window of zero or negative length is above no maximum, and the
first two conditions do not catch it: with `expires_at` ten seconds before
`issued_at` and sixty seconds of skew, every `now` in a seventy-second interval
is both within tolerance of the expiry and not far enough ahead of the issue
time. Such a message would otherwise be fresh, which is not a state a responder
should have to reason about. Requiring a strictly positive window removes it.

**The third condition shares `expired` rather than earning a value.**
[`core-model.md`](core-model.md) §5.2.1 admits a value when it sends a requester
somewhere a neighbouring value would not, and all three of these send it to the
same two fields of its own message. Nothing is withheld by sharing: an over-long
window is visible in the bytes the requester itself produced.

### 2.1 Leap seconds

[`core-model.md`](core-model.md) §2.2 accepts `23:59:60` at a month end, which
RFC 3339 §5.7 permits. **For every comparison and subtraction in this document it
is evaluated as `23:59:59`.**

The alternative is a table of which leap seconds were actually inserted. That is
IERS data, it is not derivable from the timestamp, and two implementations
carrying different vintages of it would disagree about an instant — in the one
part of the protocol whose whole job is deciding whether two parties agree about
a moment. The cost is that a leap second is not distinguishable from the second
before it. It remains correctly ordered against both of its neighbours, which is
all a freshness comparison needs.

## 3. The nonce

[`core-model.md`](core-model.md) §2.2 requires a `nonce` and describes it as
high-entropy. This section states what each party is responsible for, because
they are not the same thing and the difference is load-bearing.

**A requester must generate the nonce with at least 128 bits of entropy from a
cryptographically secure source.** This is what
[`claims.md`](claims.md) Q2D-C-07 names under *Holds when*, and it is a
requester-side obligation.

**`nonce` is base64url without padding**, as every other binary value the
protocol carries in a JSON string is — the alphabet and the refusal of padding
are RFC 4648 §5's, and a value that does not decode under it is a malformed core
object.

**A responder must reject a `nonce` that decodes to fewer than 16 bytes.** The
floor is on the **decoded bytes** and not on the string, which is a distinction
worth stating because the two differ: 16 bytes is 22 base64url characters, so a
responder measuring the string against 16 would accept a 12-byte nonce. Nothing
in a message reveals which of the two a responder applied, so the disagreement
surfaces only when a nonce lands between the values.

It is a length floor, and it is all a responder can check: it holds one nonce and
no distribution, so it cannot measure entropy. Sixteen zero bytes have none and
satisfy this rule.

**These are not two statements of one requirement.** The floor is necessary and
not sufficient. A responder that enforces it has established that the requester
had room for 128 bits, not that it used them, and no responder-side check can
establish the latter — so Q2D-C-07's entropy condition is an **assumption about
the requester**, which is why `claims.md` states it under *Holds when* rather
than under *Enforced by*. A conformance vector may assert the floor; none can
assert the entropy, and a suite describing itself as testing the latter would be
testing the former under a name that overstates it.

The floor is stated here and applies to a field
[`core-model.md`](core-model.md) §2 requires, so a nonce below it is rejected at
that document's §4 step 5 with `external_reason` `malformed`, alongside the other
core-object faults — not at step 6 with
freshness, and not at step 9 with the replay cache. It is a property of the
message rather than of the moment or of any prior exchange.

The nonce is what makes second-precision timestamps sufficient. Two semantically
identical questions asked in the same second still produce distinct bytes and
distinct digests, because the nonce differs; uniqueness comes from it and not
from the clock.

## 4. What this document does not fix

The **cache's implementation** — how many entries it holds, its eviction
discipline, what it does under memory pressure, whether it survives a restart —
is a deployment's, not the protocol's. §1's retention is the interval an entry
must remain replayable for, not a memory budget.

One consequence of that boundary is normative and belongs here rather than in an
implementation note: **a responder that cannot record a cache entry must reject
the request, before any capacity debit.** A responder unable to recognise a retry
cannot guarantee idempotency, and answering anyway double-debits and can turn a
normalized outcome into an answer. The rejection is normalized like every other
outcome from step 9 onward — a distinguishable *cache unavailable* would report
custodian internal state, and would tell a requester whether the custodian's
cache is healthy.

**Rate limiting** is [`core-model.md`](core-model.md) §9.1's, checked at step 9a,
with its own units and no claim attached. It is not a freshness bound and the two
are not substitutes: freshness bounds how long one captured message stays useful,
a rate limit bounds how many fresh ones a requester may send.
